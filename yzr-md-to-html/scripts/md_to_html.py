#!/usr/bin/env python3
"""把一份 Markdown 转成自包含、可双击浏览的 HTML。

默认深色阅读主题 + 侧边栏目录（TOC）+ 离线代码高亮（Pygments），
按需自动挂 KaTeX（数学公式）与 Mermaid（图表）CDN——只有源文件真出现
对应语法才挂，普通文档零额外网络请求。

Python >= 3.7。依赖：markdown / pymdown-extensions / pygments / jinja2。
资源（模板 / 样式）相对本脚本解析，vendored 副本同样可用。
"""

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# 资源目录相对脚本定位：scripts/ 的上一级 yzr-md-to-html/assets/
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_TEMPLATE = ASSETS_DIR / "template.html"
DEFAULT_STYLE = ASSETS_DIR / "style.css"

# 依赖：(import 名 → pip 包名)。find_spec 用 import 名，安装提示用 pip 包名——
# 二者不一致时（如 pymdownx → pymdown-extensions）只此处维护，是依赖清单的单一来源。
DEPENDENCIES = {
    "markdown": "markdown",
    "pymdownx": "pymdown-extensions",
    "pygments": "pygments",
    "jinja2": "jinja2",
}
DEP_INSTALL_HINT = "pip install --user --break-system-packages " + " ".join(DEPENDENCIES.values())

# 数学公式检测：源里出现裸 $ 即挂 KaTeX（arithmatex 只渲染合法定界符，多挂无副作用）
MATH_HINT = "$"
# Mermaid 检测：fenced ```mermaid 或缩进 ~~~mermaid
MERMAID_RE = re.compile(r"^(?:```|~~~)mermaid\b", re.MULTILINE)


def ensure_deps() -> None:
    """缺失依赖时直接退出并给出安装命令（而非抛 ImportError 栈）。"""
    missing = [imp for imp in DEPENDENCIES if importlib.util.find_spec(imp) is None]
    if missing:
        # 报 pip 包名（而非 import 名），用户照抄即可装上
        missing_pip = [DEPENDENCIES[imp] for imp in missing]
        sys.exit(f"缺少依赖: {', '.join(missing_pip)}\n请先安装:\n    {DEP_INSTALL_HINT}")


def derive_title(text: str, src_path: Path) -> str:
    """标题取首个 # 一级标题，退回文件名 stem。"""
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return src_path.stem


def render_html(
    text: str,
    title: str,
    template_path: Path,
    style_path: Path,
    want_toc: bool,
    lang: str,
) -> str:
    import markdown
    from jinja2 import Template
    from pygments.formatters import HtmlFormatter
    from pymdownx.superfences import fence_div_format

    has_math = MATH_HINT in text
    has_mermaid = bool(MERMAID_RE.search(text))

    # 不用 'extra'（它含 fenced_code，与 superfences 冲突）——显式列出需要的扩展
    extensions = [
        "tables",
        "footnotes",
        "attr_list",
        "def_list",
        "sane_lists",
        "toc",
        "pymdownx.highlight",
        "pymdownx.superfences",
        "pymdownx.inlinehilite",
        "pymdownx.arithmatex",
        "pymdownx.tilde",
        "pymdownx.tasklist",
    ]
    extension_configs = {
        "toc": {"permalink": "¶", "baselevel": 1},
        "pymdownx.highlight": {
            "css_class": "highlight",
            "guess_lang": False,
        },
        "pymdownx.superfences": {
            "custom_fences": [{"name": "mermaid", "class": "mermaid", "format": fence_div_format}]
        },
        "pymdownx.arithmatex": {"generic": True},
    }

    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    content = md.convert(text)
    toc_html = md.toc or ""
    if not want_toc:
        toc_html = ""

    # Pygments 深色样式运行时生成，避免手维护一份 CSS
    pygments_css = HtmlFormatter(style="monokai").get_style_defs(".highlight")
    styles = style_path.read_text(encoding="utf-8")

    template_src = template_path.read_text(encoding="utf-8")
    # content/toc/styles 均为已安全的 HTML/CSS；autoescape 关，title 单独用 |e 转义
    template = Template(template_src, autoescape=False)

    return template.render(
        title=title,
        lang=lang,
        content=content,
        toc=toc_html,
        styles=styles,
        pygments_css=pygments_css,
        has_math=has_math,
        has_mermaid=has_mermaid,
        has_toc=bool(toc_html.strip()),
    )


def convert_file(
    src: Path,
    out: Path,
    title: Optional[str],
    template: Path,
    style: Path,
    want_toc: bool,
    lang: str,
) -> Path:
    text = src.read_text(encoding="utf-8")
    if title is None:
        title = derive_title(text, src)
    html = render_html(text, title, template, style, want_toc, lang)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def convert_dir(src_dir: Path, out_dir: Path, template: Path, style: Path, lang: str) -> int:
    files = sorted(src_dir.rglob("*.md"))
    if not files:
        sys.exit(f"目录下没有 .md 文件: {src_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in files:
        rel = f.relative_to(src_dir).with_suffix(".html")
        convert_file(f, out_dir / rel, None, template, style, True, lang)
        count += 1
    return count


# --- 部署（--deploy）-----------------------------------------------------------
# 配置发现顺序：项目本地 → 用户全局；样例见 assets/deploy-config.example.json
CONFIG_CWD_NAME = ".md2html-deploy.json"
CONFIG_HOME_PATH = Path.home() / ".config" / "md2html" / "deploy.json"
RSYNC_BIN = "rsync"
DEPLOY_REQUIRED_FIELDS = ("host", "path", "base_url")


def _find_deploy_config(explicit: Optional[str]) -> Path:
    """解析部署配置路径：--deploy-config > ./.md2html-deploy.json > ~/.config/md2html/deploy.json。"""
    if explicit:
        p = Path(explicit)
        if not p.exists():
            sys.exit(f"部署配置不存在: {p}")
        return p
    cwd_cfg = Path.cwd() / CONFIG_CWD_NAME
    if cwd_cfg.exists():
        return cwd_cfg
    if CONFIG_HOME_PATH.exists():
        return CONFIG_HOME_PATH
    sys.exit(
        "未找到部署配置。请在项目根写一份 .md2html-deploy.json（样例见 "
        "assets/deploy-config.example.json），或用 --deploy-config 指定路径。"
    )


def _load_target(config_path: Path, target_name: str) -> dict:
    """从配置里取命名 target 并校验必填字段（host/path/base_url）。"""
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"部署配置 JSON 解析失败 ({config_path}): {e}")
    targets = cfg.get("targets", {})
    if target_name not in targets:
        avail = ", ".join(targets) or "(无)"
        sys.exit(f"配置里没有 target '{target_name}'。可用: {avail}")
    target = targets[target_name]
    missing = [k for k in DEPLOY_REQUIRED_FIELDS if k not in target]
    if missing:
        sys.exit(f"target '{target_name}' 缺字段: {', '.join(missing)}（需 host/path/base_url）")
    return target


def _build_rsync_cmd(local: Path, target: dict, remote: str, is_dir: bool) -> List[str]:
    """构造 rsync over SSH 命令（list 形式，避免 shell 注入）。"""
    port = target.get("port", 22)
    ssh = f"ssh -p {port}" if port != 22 else "ssh"
    extra = target.get("rsync_flags", "").split() if target.get("rsync_flags") else []
    cmd = [RSYNC_BIN, "-avz", "-e", ssh] + extra
    if is_dir:
        # 目录批量：排除 .md 源，其余（含 .html / 图片 / 资源）一并发布
        cmd += ["--exclude=*.md", str(local).rstrip("/") + "/", remote]
    else:
        cmd += [str(local), remote]
    return cmd


def _ensure_rsync() -> None:
    if shutil.which(RSYNC_BIN) is None:
        sys.exit(f"未找到 {RSYNC_BIN}。请先安装（Debian/Ubuntu: apt install rsync；macOS 自带）。")


def deploy(
    local: Path,
    target_name: str,
    config_path: Optional[str],
    yes: bool,
    is_dir: bool,
) -> None:
    """转换后把产物 rsync 到 server web 目录，打印访问 URL。

    安全模型：只走 SSH key 认证（靠本机 ssh agent / ~/.ssh/config，不碰私钥或密码）；
    发布即公开，推送前必须确认——交互 tty 问 y/n，非交互（agent / 管道）须传 -y。
    """
    _ensure_rsync()
    cfg_path = _find_deploy_config(config_path)
    target = _load_target(cfg_path, target_name)

    base_url = target["base_url"].rstrip("/")
    url = base_url + "/" if is_dir else base_url + "/" + local.name
    remote = f"{target['host']}:{target['path'].rstrip('/')}/"

    print("ℹ 将发布（公开可访问）:")
    print(f"   本地 : {local}")
    print(f"   远端 : {remote}")
    print(f"   URL  : {url}")
    if not yes:
        if not sys.stdin.isatty():
            sys.exit("非交互环境（agent / 管道）需传 -y 才能推送；agent 推送前应已向用户确认 target 与 URL")
        ans = input("确认推送? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            sys.exit("已取消")

    cmd = _build_rsync_cmd(local, target, remote, is_dir)
    print("推送中…")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.stdout.strip():
        print(res.stdout.rstrip())
    if res.returncode != 0:
        sys.exit(f"rsync 失败 (exit {res.returncode}):\n{res.stderr.strip()}")
    print("✓ 已发布，访问: " + url)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="把 Markdown 转成自包含、深色主题的可浏览 HTML。")
    parser.add_argument("input", help="Markdown 文件，或目录（批量转该目录下所有 *.md）")
    parser.add_argument("-o", "--output", default=None, help="输出 .html（文件输入）或输出目录（目录输入）")
    parser.add_argument("--title", default=None, help="<title>，默认取首个 # 标题")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="自定义 Jinja2 HTML 模板路径")
    parser.add_argument("--style", default=str(DEFAULT_STYLE), help="自定义 CSS 路径")
    parser.add_argument("--no-toc", action="store_true", help="关闭侧边栏目录")
    parser.add_argument("--lang", default="zh-CN", help="<html lang>，默认 zh-CN")
    parser.add_argument(
        "--deploy",
        default=None,
        metavar="TARGET",
        help="转换后经 rsync+SSH 推送到配置里的命名 target，并打印访问 URL",
    )
    parser.add_argument(
        "--deploy-config",
        default=None,
        metavar="PATH",
        help="部署配置 JSON 路径（默认 ./.md2html-deploy.json → ~/.config/md2html/deploy.json）",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="跳过推送前确认（agent / 脚本用；推送即公开发布）",
    )
    args = parser.parse_args(argv)

    ensure_deps()

    src = Path(args.input)
    if not src.exists():
        sys.exit(f"输入不存在: {src}")

    template = Path(args.template)
    style = Path(args.style)
    if not template.exists():
        sys.exit(f"模板不存在: {template}")
    if not style.exists():
        sys.exit(f"样式不存在: {style}")

    if src.is_dir():
        out_dir = Path(args.output) if args.output else src
        n = convert_dir(src, out_dir, template, style, args.lang)
        print(f"已批量转换 {n} 个文件 → {out_dir}/")
        deploy_target = out_dir
        deploy_is_dir = True
    else:
        out = Path(args.output) if args.output else src.with_suffix(".html")
        convert_file(src, out, args.title, template, style, not args.no_toc, args.lang)
        print(f"已生成: {out}")
        source_text = src.read_text(encoding="utf-8")
        if "$" in source_text or "mermaid" in source_text:
            print("（含公式 / Mermaid，首次打开需联网加载 CDN）")
        deploy_target = out
        deploy_is_dir = False

    if args.deploy:
        deploy(deploy_target, args.deploy, args.deploy_config, args.yes, deploy_is_dir)


if __name__ == "__main__":
    main()

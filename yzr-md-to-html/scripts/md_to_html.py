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
import re
import sys
from pathlib import Path
from typing import Optional

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


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="把 Markdown 转成自包含、深色主题的可浏览 HTML。")
    parser.add_argument("input", help="Markdown 文件，或目录（批量转该目录下所有 *.md）")
    parser.add_argument("-o", "--output", default=None, help="输出 .html（文件输入）或输出目录（目录输入）")
    parser.add_argument("--title", default=None, help="<title>，默认取首个 # 标题")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="自定义 Jinja2 HTML 模板路径")
    parser.add_argument("--style", default=str(DEFAULT_STYLE), help="自定义 CSS 路径")
    parser.add_argument("--no-toc", action="store_true", help="关闭侧边栏目录")
    parser.add_argument("--lang", default="zh-CN", help="<html lang>，默认 zh-CN")
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
    else:
        out = Path(args.output) if args.output else src.with_suffix(".html")
        convert_file(src, out, args.title, template, style, not args.no_toc, args.lang)
        print(f"已生成: {out}")
        source_text = src.read_text(encoding="utf-8")
        if "$" in source_text or "mermaid" in source_text:
            print("（含公式 / Mermaid，首次打开需联网加载 CDN）")


if __name__ == "__main__":
    main()

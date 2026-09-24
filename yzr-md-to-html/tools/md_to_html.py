#!/usr/bin/env python3
"""把 Markdown 转成自包含、可双击浏览的 HTML（深色主题 + 侧边栏 + 离线高亮 / 公式 / Mermaid ASCII）。"""

import argparse
import html
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# 资源目录相对脚本定位：tools/ 的上一级 yzr-md-to-html/assets/
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_TEMPLATE = ASSETS_DIR / "template.html"
DEFAULT_STYLE = ASSETS_DIR / "style.css"
# Mermaid → ASCII wrapper（Node 脚本，与 md_to_html.py 同级）
MERMAID_WRAPPER = Path(__file__).resolve().parent / "mermaid_to_ascii.mjs"

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


# 围栏块整体：取标题时先剔除，避免 bash 围栏的 `# 注释` 行被当成 H1
FENCE_BLOCK_RE = re.compile(r"^(?:```|~~~).*?^(?:```|~~~)[ \t]*$", re.DOTALL | re.MULTILINE)


def derive_title(text: str, src_path: Path) -> str:
    """标题取首个 # 一级标题（跳过代码围栏），退回文件名 stem。"""
    m = re.search(r"^#\s+(.+?)\s*$", FENCE_BLOCK_RE.sub("", text), re.MULTILINE)
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
    want_mermaid_ascii: bool = True,
) -> Tuple[str, List[Tuple[int, str]]]:
    """渲染 HTML，返回 (页面全文, mermaid 回退记录 [(块号, 原因)])。"""
    import markdown
    from jinja2 import Template
    from pygments.formatters import HtmlFormatter
    from pymdownx.superfences import fence_div_format

    has_math = MATH_HINT in text
    mermaid_present = bool(MERMAID_RE.search(text))

    # 逐块转 ASCII：成功 → <pre>；失败 / 无 node → 回退 CDN 渲染并记录原因
    mermaid_failures = []  # [(第几个 mermaid 块, 原因)]
    node_bin = shutil.which("node") if (want_mermaid_ascii and mermaid_present) else None
    block_no = [0]

    def mermaid_ascii_format(source, language, css_class, options, md, **kwargs):
        """mermaid 围栏格式器：优先转 ASCII，失败或缺 node 时回退 CDN 并记录原因。"""
        block_no[0] += 1
        if not want_mermaid_ascii:
            return fence_div_format(source, language, css_class, options, md, **kwargs)
        if node_bin is not None:
            try:
                proc = subprocess.run(
                    [node_bin, str(MERMAID_WRAPPER)],
                    input=source,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    timeout=30,
                )
                if proc.returncode == 0:
                    return f'<div class="mermaid-ascii"><pre>{html.escape(proc.stdout)}</pre></div>'
                reason = proc.stderr.strip() or f"退出码 {proc.returncode}"
                mermaid_failures.append((block_no[0], reason))
            except (OSError, subprocess.TimeoutExpired) as exc:
                mermaid_failures.append((block_no[0], str(exc)))
        else:
            mermaid_failures.append((block_no[0], "未找到 node 可执行文件"))
        return fence_div_format(source, language, css_class, options, md, **kwargs)

    # 是否挂 Mermaid CDN：ASCII 模式下仅当存在回退块；关闭 ASCII 则照旧按源检测
    # 注意：须在 md.convert 之后计算（mermaid_failures 在转换过程中填充）

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
            "custom_fences": [
                {
                    "name": "mermaid",
                    "class": "mermaid",
                    "format": mermaid_ascii_format,
                }
            ]
        },
        "pymdownx.arithmatex": {"generic": True},
    }

    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    content = md.convert(text)
    toc_html = md.toc or ""
    if not want_toc:
        toc_html = ""

    has_mermaid = ((not want_mermaid_ascii) and mermaid_present) or bool(mermaid_failures)

    # Pygments 深色样式运行时生成，避免手维护一份 CSS
    pygments_css = HtmlFormatter(style="monokai").get_style_defs(".highlight")
    styles = style_path.read_text(encoding="utf-8")

    template_src = template_path.read_text(encoding="utf-8")
    # content/toc/styles 均为已安全的 HTML/CSS；autoescape 关，title 单独用 |e 转义
    template = Template(template_src, autoescape=False)

    html_out = template.render(
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
    return html_out, mermaid_failures


def convert_file(
    src: Path,
    out: Path,
    title: Optional[str],
    template: Path,
    style: Path,
    want_toc: bool,
    lang: str,
    want_mermaid_ascii: bool,
) -> Tuple[Path, List[Tuple[Path, int, str]], bool]:
    """转换单个文件，返回 (输出路径, mermaid 回退记录, 是否含公式)。"""
    text = src.read_text(encoding="utf-8")
    if title is None:
        title = derive_title(text, src)
    html_out, failures = render_html(text, title, template, style, want_toc, lang, want_mermaid_ascii)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")
    # 与 convert_dir 统一为 (源文件, 块号, 原因) 3 元组
    return out, [(src, block_no, reason) for block_no, reason in failures], MATH_HINT in text


def convert_dir(
    src_dir: Path,
    out_dir: Path,
    template: Path,
    style: Path,
    lang: str,
    want_toc: bool,
    want_mermaid_ascii: bool,
) -> Tuple[int, List[Tuple[Path, int, str]], int]:
    """批量转换目录下全部 md，返回 (转换数, mermaid 回退记录, 含公式的文件数)。"""
    files = sorted(src_dir.rglob("*.md"))
    if not files:
        sys.exit(f"目录下没有 .md 文件: {src_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    math_files = 0
    failures = []
    for f in files:
        rel = f.relative_to(src_dir).with_suffix(".html")
        _, file_failures, has_math = convert_file(
            f, out_dir / rel, None, template, style, want_toc, lang, want_mermaid_ascii
        )
        failures.extend(file_failures)
        math_files += has_math
        count += 1
    return count, failures, math_files


def main(argv=None) -> None:
    """CLI 入口：解析参数、转换文件或目录、打印产物与回退摘要。"""
    parser = argparse.ArgumentParser(description="把 Markdown 转成自包含、深色主题的可浏览 HTML。")
    parser.add_argument("input", help="Markdown 文件，或目录（批量转该目录下所有 *.md）")
    parser.add_argument("-o", "--output", default=None, help="输出 .html（文件输入）或输出目录（目录输入）")
    parser.add_argument("--title", default=None, help="<title>，默认取首个 # 标题")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="自定义 Jinja2 HTML 模板路径")
    parser.add_argument("--style", default=str(DEFAULT_STYLE), help="自定义 CSS 路径")
    parser.add_argument("--no-toc", action="store_true", help="关闭侧边栏目录")
    parser.add_argument("--lang", default="zh-CN", help="<html lang>，默认 zh-CN")
    parser.add_argument(
        "--no-mermaid-ascii",
        action="store_true",
        help="关闭 Mermaid 转 ASCII，回退为挂 Mermaid CDN 渲染",
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

    want_mermaid_ascii = not args.no_mermaid_ascii

    if src.is_dir():
        out_dir = Path(args.output) if args.output else src
        n, failures, math_files = convert_dir(
            src, out_dir, template, style, args.lang, not args.no_toc, want_mermaid_ascii
        )
        print(f"已批量转换 {n} 个文件 → {out_dir}/")
        math_note = f"{math_files} 个文件含公式" if math_files else ""
    else:
        out = Path(args.output) if args.output else src.with_suffix(".html")
        _, failures, has_math = convert_file(
            src, out, args.title, template, style, not args.no_toc, args.lang, want_mermaid_ascii
        )
        print(f"已生成: {out}")
        math_note = "含公式" if has_math else ""

    if math_note:
        print(f"（{math_note}，首次打开需联网加载 KaTeX CDN）")

    if failures:
        print(f"（{len(failures)} 个 Mermaid 块转 ASCII 失败，已回退为 CDN 渲染，需联网加载）")
        for fpath, block_no, reason in failures:
            print(f"  - {fpath} 第 {block_no} 个 mermaid 块: {reason}")


if __name__ == "__main__":
    main()

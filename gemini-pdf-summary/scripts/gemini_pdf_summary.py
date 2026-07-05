#!/usr/bin/env python3
"""
gemini_pdf_summary: 用 Gemini 多模态读 PDF 并按文档类型路由到对应模板,
输出中文 Markdown 总结。

本脚本是 gemini-pdf-summary skill 的核心可执行入口。
它也可以被 agent 在 bash 命令行里直接调用。

支持的文档类型（--type）：
    paper      - 学术论文（含 quick + full 双模式，quick 默认抽原始图）
    manual     - 产品手册 / datasheet / 用户手册（单模式，概念用 mermaid / 表格）
    whitepaper - 行业 / 技术 / vendor 白皮书（单模式，概念用 mermaid / 表格）
    book       - 书籍 / 长篇技术文档（仅 full 模式，按 PDF 原生章节全量转写）

依赖：
    pip install -U google-genai
    export GEMINI_API_KEY="你的 key"

Python 兼容：3.7+（与 yzr-skill-creator 脚本保持一致；避开 PEP 604/585 语法）。

使用示例：
    # 显式指定类型
    python3 gemini_pdf_summary.py --pdf paper.pdf --type paper --output raw/papers/foo/
    python3 gemini_pdf_summary.py --pdf manual.pdf --type manual --output raw/manuals/foo/
    python3 gemini_pdf_summary.py --pdf book.pdf --type book --output raw/books/foo/

    # auto-detect 类型
    python3 gemini_pdf_summary.py --pdf unknown.pdf --auto-detect --output raw/papers/foo/

    # paper 的 --full 模式（双产物 quick + full；其他类型忽略此 flag）
    python3 gemini_pdf_summary.py --pdf paper.pdf --type paper --full --output <wiki-root>

    # 显式覆盖模型 / focus
    python3 gemini_pdf_summary.py --pdf paper.pdf --type paper --model gemini-3.1-pro-preview
    python3 gemini_pdf_summary.py --pdf paper.pdf --type paper --focus "重点看数学推导"
"""

import argparse
import json
import os
import re
import sys
from typing import Optional, Tuple  # noqa: F401  # 仅在 # type: 注释中使用

# 第三方 SDK（运行时通过 importlib 探测，缺包时报清晰错误，不让栈跟踪一片红）
try:
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except ImportError:  # pragma: no cover - 纯运行时分支
    sys.stderr.write(
        "ERROR: 缺少 google-genai SDK。\n"
        "       安装命令: pip install -U google-genai\n"
        "       Debian/WSL 系统 Python 需要 --break-system-packages 或 --user。\n"
    )
    sys.exit(2)

# pymupdf 是 --extract-figures 的软依赖，不强制安装；缺包时仅在该 flag 启用时报错。
try:
    import fitz  # type: ignore  # pymupdf

    _HAS_PYMUPDF = True
except ImportError:  # pragma: no cover - 纯运行时分支
    fitz = None  # type: ignore
    _HAS_PYMUPDF = False

# Pillow 是 WebP 输出的软依赖；pymupdf 原生不支持 WebP 写入，需用 Pillow。
# PNG/JPEG 输出无需 Pillow（pymupdf 自带）。
try:
    from PIL import Image  # type: ignore  # Pillow

    _HAS_PILLOW = True
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    _HAS_PILLOW = False


# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-3.5-flash"
# 503/429 等高并发 / 限流错误:走 3 次重试(2s/4s 退避),终失败**直接抛**给用户,
# 不静默降级到便宜模型(2026-06-21 决策)。理由:不同模型对 v3.2 prompt 模板的
# 输出质量差异显著(alt 字段偏差、表格行数错位、章节遗漏等),silent fallback 用户
# 感知不到是模型降级导致的,只看到"结果怪"——质量风险 > 便利。换模型用
# `--model <id>` 显式指定。SSOT: 实际策略见 _gemini_call_with_retry;与 SKILL.md
# §核心原则 #8 对齐。
MAX_PDF_BYTES_INLINE = 20 * 1024 * 1024  # 20 MB 走 inline Part.from_bytes；更大走 File API
# Full 模板产物需要全文级展开,默认 output token 上限(约 8192)撞顶会截断尾部
# 章节。此值**仅此一处定义**(SSOT);prompt-template.md / SKILL.md 不重抄避免散落。
# 决策背景:见 prompt-template.md ## 全文级抽取模板(full) 头部 2026-06-30 加固
# 的"完整性 > 篇幅"block。
FULL_MAX_OUTPUT_TOKENS = 65536

# 4 类文档路由常量。paper 的 quick 模板就是从前的 academic；manual / whitepaper / book 各一份。
# 任何模板变更只需要改 assets/template-<type>.md，本脚本不再持有 prompt 文本。
VALID_TYPES = ("paper", "manual", "whitepaper", "book")
DEFAULT_TYPE = "paper"  # 兼容旧调用（不带 --type 时默认走 paper）

# 模板文件位于 assets/template-<type>.md；book / manual / whitepaper 是单一模板，
# paper 拆为 quick（默认）和 full（--full）。
ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "assets")
)

# 抽取 `````text ... `````（4-backtick）包裹的模板正文。允许前置空白。
# 每个 type 的 template-<type>.md 用 `````text` 4-backtick fence 包裹 prompt 正文
# （因为 prompt 内部要嵌套 markdown / mermaid 代码块示例），本函数用正则抽取。
_DEFAULT_PROMPT_FENCE_RE = re.compile(
    r"^````text\s*\n(.*?)^````\s*$",
    re.MULTILINE | re.DOTALL,
)


def _load_prompt_for_type(doc_type, mode="quick"):
    # type: (str, str) -> str
    """从 assets/template-<doc_type>.md 的对应段读出 prompt 正文。

    - doc_type ∈ {"paper", "manual", "whitepaper", "book"}
    - mode:
        * "quick" (默认): paper → ## quick 模式段; manual / whitepaper → 唯一模板;
          book → **报错**（book 仅支持 full）
        * "full": 所有类型都按 full 模板走；paper → ## full 模式段;
          manual / whitepaper → 唯一模板（自身就是全文级风格）;
          book → 唯一模板

    失败时（文件缺失 / 段不存在 / 没有 text fence）立即报错退出——这是开发期
    应该立刻发现的问题，不允许静默回退到老模板。"""
    if doc_type not in VALID_TYPES:
        sys.stderr.write(
            f"ERROR: 未知 doc_type {doc_type!r}；合法值: {VALID_TYPES}\n"
        )
        sys.exit(2)

    if doc_type == "book" and mode == "quick":
        sys.stderr.write(
            "ERROR: book 类型仅支持 full 模式（--full）。\n"
            "       书籍无法做 quick 速读总结，请用 --type book --full。\n"
        )
        sys.exit(2)

    template_path = os.path.join(ASSETS_DIR, f"template-{doc_type}.md")
    if not os.path.isfile(template_path):
        sys.stderr.write(
            f"ERROR: 找不到 prompt 模板文件: {template_path}\n"
            f"       仓库结构破坏，请检查 {ASSETS_DIR}/ 目录。\n"
        )
        sys.exit(2)

    with open(template_path, encoding="utf-8") as f:
        md = f.read()

    # 段标题定位规则（与 paper 的 quick / full 区分）：
    #   paper     → "## quick 模式（默认）" 或 "## full 模式（--full）"
    #   manual    → "## 模板"（唯一模板，不分模式）
    #   whitepaper→ "## 模板"
    #   book      → "## 模板"
    head_patterns = {
        ("paper", "quick"): r"^##\s+quick\s*模式\s*[（(]默认[)）]\s*$",
        ("paper", "full"): r"^##\s+full\s*模式\s*[（(].*--full.*[)）]\s*$",
        ("manual", "quick"): r"^##\s+模板\s*$",
        ("manual", "full"): r"^##\s+模板\s*$",
        ("whitepaper", "quick"): r"^##\s+模板\s*$",
        ("whitepaper", "full"): r"^##\s+模板\s*$",
        ("book", "full"): r"^##\s+模板\s*$",
    }
    pattern = head_patterns[(doc_type, mode)]
    head_match = re.search(pattern, md, re.MULTILINE)
    if not head_match:
        sys.stderr.write(
            f"ERROR: {template_path} 里找不到 '{pattern}' 对应的段。\n"
            "       模板文件结构破坏，请补回该小节。\n"
        )
        sys.exit(2)

    after_head = md[head_match.end() :]
    fence_match = _DEFAULT_PROMPT_FENCE_RE.search(after_head)
    if not fence_match:
        sys.stderr.write(
            f"ERROR: {template_path} 的模板段里找不到 `````text` fence。\n"
            "       请确认模板正文仍由 4-backtick fence 包裹。\n"
        )
        sys.exit(2)

    return fence_match.group(1).rstrip() + "\n"


# 兼容旧调用：DEFAULT_PROMPT = paper quick 模板（与 gemini-paper-summary 行为一致）
DEFAULT_PROMPT = _load_prompt_for_type("paper", "quick")
FULL_PROMPT = _load_prompt_for_type("paper", "full")


FOCUS_INJECTION = (
    "\n\n[额外关注点]\n"
    '用户在调用时指定了以下关注点，请在"方法 / 关键结果"小节中相应侧重，'
    '并在"启发 / 追问"小节展开 2-3 个延伸思考：\n\n{focus}\n'
)

# full 模板的焦点注入片段(2026-06-30 重新定位后,full 模板不再有
# "方法设计 / 代表性实验结果 / 业务启示 & 价值"这些 summary 段——章节按
# PDF 原生顺序转写。用户的关注点以"在对应的 PDF 原生章节下追加 focus 子段"
# 形式插入,例如 `### 用户关注点: <focus>` 子节)
FOCUS_INJECTION_FULL = (
    "\n\n[额外关注点]\n"
    "用户在调用时指定了以下关注点，请在 **对应的 PDF 原生章节下**(如 "
    "`### Section 3.2` / `### Section 5.4`)以子段形式追加原文级细节关注"
    "(例如 `### 用户关注点: <focus>` 子节),"
    "\n\n{focus}\n"
)


# ----------------------------------------------------------------------------
# 图片导出（--extract-figures，软依赖 pymupdf）
# ----------------------------------------------------------------------------

# 匹配 `](PDF p.<page> fig.<N> [bbox=<x0,y0,x1,y1>])` 形式
# - group(1): 1-based 页码
# - group(2): 论文里的 Figure 编号
# - group(3): 可选 bbox "x0,y0,x1,y1"（PDF point 单位，左上原点）
#   模型可能包一层方括号 `bbox=[300,250,550,420]`，已在解析时剥掉
FIGURE_REF_RE = re.compile(
    r"\(PDF p\.(\d+)\s+fig\.(\d+)(?:\s+bbox=\[?([\d.,]+)\]?)?\)",
    re.IGNORECASE,
)


def parse_figure_refs(md_text):
    # type: (str) -> list
    """从 Markdown 里抽 `(page, fig_num, bbox_or_None)` 三元组，按首次出现去重。"""
    seen = set()
    out = []
    for m in FIGURE_REF_RE.finditer(md_text):
        page = int(m.group(1))
        fig_num = int(m.group(2))
        bbox_str = m.group(3)
        bbox = None
        if bbox_str:
            try:
                parts = [float(x) for x in bbox_str.split(",")]
                if len(parts) == 4:
                    bbox = tuple(parts)
            except ValueError:
                bbox = None
        key = (page, fig_num, bbox_str)
        if key not in seen:
            seen.add(key)
            out.append((page, fig_num, bbox))
    return out


def find_figure_caption(page, fig_num):
    # type: (object, int) -> object
    r"""在该页搜 `Figure N:` caption，返回 caption 整体 bbox 或 None。

    关键细节：pymupdf 会把视觉上同一行的 caption 拆成多 line（典型：
    "Fig. 10." 一个 line、"Single-threaded lookup throughput..." 另一个 line，
    因为 span 之间有 x 间隔，pymupdf 不合并）。本函数找到首个匹配 line 后，
    在**同一 block 内** union 所有 y 相同的 line，返回 union bbox——
    这样 `cap_x_center` 反映 caption 真实横向跨度（关键用于 figure 是否
    跨双栏的判断，详见 find_figure_bbox_by_caption）。

    约束：仅在 block 内 union，不会跨 block 误吞另一栏的 Fig.N（实测 p5
    Fig.6 的 "Fig. 6." 在 block[21] line[0]，续行 "Illustration..." 在
    block[21] line[1]；同页 Fig.7 的 "Fig. 7. Search algorithm." 在
    block[39]，不同 block，安全）。

    **正/误匹配甄别**（2026-06-21 修复，ART-ICDE'13 p.11 Fig 16 case）：
    正文里常出现 "Figure 16 shows that..." 这类引用，line 文本以
    "Figure N" 起头 + 数字后是字母，被原正则命中，返回正文 block 的
    bbox（y=692），与真正的 caption（y=209.9）相距甚远，后续 caption
    locator 会算出错误的 figure 区域（把"D. End-to-End Evaluation" +
    整段正文当成 figure 16）。修复：line 文本总长（同行同 block line
    合并后）超过 120 字符时视为正文引用，跳过；caption 一般 < 80 字符。
    备选：用正则锚定 `[.]\s*$`（line 末尾以句号结束，类似 "Fig. 16."）
    来区分 caption 标签 vs 正文引用（"Figure 16 shows" 末尾是 s）。两者
    结合：长度 ≤ 120 字符 **且** 句号结尾（caption 行通常是
    "Fig. N. <caption text>." 形式）。
    """
    pat = re.compile(rf"^\s*(?:Figure|Fig\.?)\s*{fig_num}\b", re.IGNORECASE)
    candidates = []  # (block, line, line_text)
    for block in page.get_text("dict").get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            line_text = "".join(s.get("text", "") for s in line["spans"]).strip()
            if pat.match(line_text):
                candidates.append((block, line, line_text))
    if not candidates:
        return None

    # 过滤掉正文引用,留下真 caption
    # 判定:line 文本在 "Figure N" / "Fig. N" 之后必须紧跟 `[.:]` + 空白 + 描述
    # caption 形式: "Fig. 16. TPC-C performance." / "Figure 16: ..." / "Figure 16. ..."
    # 正文引用形式: "Figure 16 shows that..." / "Figure 16 illustrates..."(数字后是空格+动词)
    # 长度 ≤ 120 字符是辅助判定(caption 第一行典型 < 60 字符;pymupdf 单行截断
    # 可能让正文引用也变短,如 "Figure 16 shows that the index structure choice
    # is critical for" — 仍 63 字符;靠主判定区分)
    cap_pat = re.compile(
        rf"^\s*(?:Figure|Fig\.?)\s*{fig_num}\s*[.:]\s*\S",
        re.IGNORECASE,
    )
    real_captions = [
        c for c in candidates if cap_pat.match(c[2]) and len(c[2]) <= 120
    ]
    if not real_captions:
        # 没找到匹配的真 caption 形式,退而求其次用最短的
        real_captions = [min(candidates, key=lambda c: len(c[2]))]
    matched_block, matched_line, _ = real_captions[0]

    # Union 同 block 内所有 y 与 matched line 接近（容忍 3pt）的 line
    # 3pt 覆盖 pymupdf line 分组的微小 y 偏移；不会跨 y 跨到下一段正文
    y_tolerance = 3.0
    matched_y = matched_line["bbox"][1]
    x0, y0, x1, y1 = matched_line["bbox"]
    for line in matched_block["lines"]:
        if abs(line["bbox"][1] - matched_y) > y_tolerance:
            continue
        x0 = min(x0, line["bbox"][0])
        y0 = min(y0, line["bbox"][1])
        x1 = max(max(x1, line["bbox"][2]), line["bbox"][2])
        y1 = max(y1, line["bbox"][3])
    return (x0, y0, x1, y1)


def find_figure_bbox_by_caption(page, fig_num, include_caption=True):
    # type: (object, int, bool) -> object
    """无 Gemini bbox 时按 `Figure N:` caption 自动定位，返回 fitz.Rect 或 None。
    include_caption=True 时包含 caption，False 时只到 caption 顶。

    定位算法（多策略，从精确到兜底）：
    1. **正文段落边界**：caption 上方最近的"宽+多行"正文段落底部（旧启发式，
       处理 figure 上方紧跟段落的常见情形）。
    2. **figure annotation 顶部**：caption 上方同栏所有非正文块（即 figure
       annotation / label）的最上 y0。新增逻辑，专门解决 figure 上方只有
       figure annotation、没有正文段落的情形（如 ART-ICDE'13 第 5 页）。
    3. **page 顶兜底**：以上都失败时退到 page 顶（保证 figure 一定被框入，
       但可能含 page header）。

    双栏 / 跨双栏判定：
    - 普通双栏论文：caption 在某一栏 → 只在该栏内向上找正文 + 裁剪
    - **跨双栏 figure**（如 ART-ICDE'13 第 9 页 Figure 10，三个子图并排占
      满整个页宽）：caption 横向跨度跨越 `page_mid_x` → 视为 wide figure，
      使用整页文本区域宽度裁剪
    """
    cap_bbox = find_figure_caption(page, fig_num)
    if not cap_bbox:
        return None
    cap_limit_y = cap_bbox[3] if include_caption else cap_bbox[1]

    # 双栏论文处理：根据 caption 的 x 中心判断 figure 所在栏，
    # 只在该栏内向上找正文 + 裁剪（避免把另一栏的图/正文框进来）
    cap_x_center = (cap_bbox[0] + cap_bbox[2]) / 2
    page_rect = page.rect
    page_mid_x = (page_rect.x0 + page_rect.x1) / 2

    # === 跨双栏 figure 检测 ===
    # 判据: caption bbox 横向跨越 page_mid_x（说明 caption 本身就跨栏,
    # 对应的 figure 必然也是跨栏宽图）
    is_wide_figure = (cap_bbox[0] < page_mid_x) and (cap_bbox[2] > page_mid_x)
    if is_wide_figure:
        # 跨双栏 figure: 用整页文本区域宽度裁剪 (两侧 36pt 边距)
        col_left = page_rect.x0 + 36
        col_right = page_rect.x1 - 36
    elif cap_x_center < page_mid_x:
        col_left = page_rect.x0 + 36
        col_right = page_mid_x - 5
    else:
        col_left = page_mid_x + 5
        col_right = page_rect.x1 - 36

    col_width = col_right - col_left
    if col_width < 100:
        return None

    def is_body_text_block(block):
        line_count = len(block.get("lines", []))
        block_width = block["bbox"][2] - block["bbox"][0]
        return line_count >= 2 and block_width >= col_width * 0.6

    # 单次遍历:分类正文块 vs annotation 块
    body_bottom = page_rect.y0  # 正文段落底部候选
    found_body = False
    annotation_top = None  # annotation 块最上 y0
    for block in page.get_text("dict").get("blocks", []):
        if "lines" not in block:
            continue
        bbox = block["bbox"]
        block_x_center = (bbox[0] + bbox[2]) / 2
        if block_x_center < col_left or block_x_center > col_right:
            continue
        if bbox[3] >= cap_limit_y:
            continue
        if is_body_text_block(block):
            # 正文段落:取最下的正文块底部
            if bbox[3] > body_bottom:
                body_bottom = bbox[3]
                found_body = True
        else:
            # annotation / label 块:取最上的 y0
            if annotation_top is None or bbox[1] < annotation_top:
                annotation_top = bbox[1]

    # === 策略 1: 正文段落底部（紧贴 figure 上方的正文）===
    if found_body and cap_limit_y - body_bottom >= 30:
        return fitz.Rect(col_left, body_bottom, col_right, cap_limit_y)

    # === 策略 2: annotation 顶部（figure 上方只有 annotation / label 时）===
    # 即使策略 1 找到了正文,如果正文离 caption 太近（< 30pt）,说明"正文"其实是
    # figure 自己的 caption label,不是真正文;这时仍用 annotation 顶部。
    if annotation_top is not None and annotation_top > page_rect.y0:
        return fitz.Rect(col_left, annotation_top, col_right, cap_limit_y)

    # === 策略 3: page 顶兜底 ===
    return fitz.Rect(col_left, page_rect.y0, col_right, cap_limit_y)


def refine_bbox(page, fig_num, bbox, padding=5.0):
    # type: (object, int, tuple, float) -> object
    """对 Gemini 给的 bbox 做后处理：加 padding；用 caption 顶部裁剪 y1
    （**不**包含 caption —— caption 由 Markdown 文本承载，图片只保留 figure 主体）。

    关键：原设计把 `y1` 扩展到 caption 底部（`cap_bbox[3]`）让图片含 caption，
    但 caption 文字本身是文本信息，搜不到、不能选、不能索引。新设计把 caption
    移到 Markdown body（用 `replace_alt_with_full_caption` 在图片后插入
    `**图 N**：<caption>` 单独一行），图片只裁 figure 主体。
    """
    x0, y0, x1, y1 = bbox
    page_rect = page.rect
    cap_bbox = find_figure_caption(page, fig_num)
    if cap_bbox is not None:
        # y1 钳到 caption 顶部（cap_bbox[1]）—— 裁掉 caption 文字
        y1 = min(y1, cap_bbox[1])
    x0 = max(page_rect.x0, x0 - padding)
    y0 = max(page_rect.y0, y0 - padding)
    x1 = min(page_rect.x1, x1 + padding)
    y1 = min(page_rect.y1, y1 + padding)
    return fitz.Rect(x0, y0, x1, y1)


def _flatten_to_rgb(pix):
    # type: (object) -> object
    """把 RGBA Pixmap 合成到白底 RGB（用于 JPEG 输出）。
    pymupdf 官方做法：`fitz.Pixmap(fitz.csRGB, pix)` 会用 alpha 做预乘合成，背景默认白。
    """
    if not pix.alpha:
        return pix
    return fitz.Pixmap(fitz.csRGB, pix)


def _save_pixmap_with_constraints(pix, path, format_ext, base_quality=85, max_size_kb=None):
    # type: (object, str, str, int, int) -> tuple
    """保存 Pixmap，自动满足 max_size_kb 体积上限。

    降级顺序：quality (85→65→45→30) → format (PNG→WebP，若 Pillow 不可用则保持 PNG) → scale
    返回 (final_fmt, final_quality, attempts, size_kb)。
    若 max_size_kb=None 则只做一次保存，不降级。
    """
    ext_map = {"png": "png", "webp": "webp", "jpeg": "jpg"}
    budget = max_size_kb * 1024 if max_size_kb is not None else None

    # 当前状态
    current_pix = pix
    current_fmt = format_ext
    current_quality = base_quality
    attempts = 0
    webp_unavailable_warned = False

    # 最多 8 轮降级；quality 4 次 + 格式切换 1 次 + shrink 若干次
    for attempts in range(8):
        # 确定输出路径的扩展名
        base, _ = os.path.splitext(path)
        out_path = base + "." + ext_map[current_fmt]

        # 保存
        if current_fmt == "webp" and not _HAS_PILLOW:
            # pymupdf 原生不支持 WebP；没有 Pillow 时降级到 PNG 并告知
            if not webp_unavailable_warned:
                sys.stderr.write(
                    "INFO: --figure-format=webp 需要 Pillow（pymupdf 不支持 WebP 直存），"
                    "但未安装 Pillow，自动降级到 PNG。\n"
                    "      安装命令: pip install --user --break-system-packages Pillow\n"
                )
                webp_unavailable_warned = True
            current_fmt = "png"
            out_path = base + ".png"

        # 准备保存用的 Pixmap（JPEG 需要 flatten alpha）
        if current_fmt == "jpeg":
            save_pix = _flatten_to_rgb(current_pix)
            save_pix.save(out_path, jpg_quality=current_quality)
        elif current_fmt == "webp":
            # Pillow 路径：把 Pixmap 转 PIL Image 后存 webp
            img = Image.frombytes(
                "RGBA" if current_pix.alpha else "RGB",
                (current_pix.width, current_pix.height),
                current_pix.samples,
            )
            img.save(out_path, "WEBP", quality=current_quality, method=4)
        else:  # png
            current_pix.save(out_path)

        size_bytes = os.path.getsize(out_path)

        # 检查是否满足体积上限
        if budget is None or size_bytes <= budget:
            return (current_fmt, current_quality, attempts, size_bytes / 1024.0)

        # 降级决策
        # 1) 优先降 quality（85 → 65 → 45 → 30）
        if current_quality > 30:
            current_quality = max(30, current_quality - 20)
            continue

        # 2) PNG → WebP 切换（重置 quality；若无 Pillow 则跳过此步）
        if current_fmt == "png" and _HAS_PILLOW:
            current_fmt = "webp"
            current_quality = base_quality
            continue

        # 3) 降 scale：用 Pixmap.shrink（整数因子）整数倍降采样
        #    只在像素仍够大时降（避免降到 < 100px）
        if current_pix.width > 200 and current_pix.height > 200:
            factor = 2
            current_pix = current_pix.shrink(factor)
            # shrink 后下次保存按新尺寸；quality 保留当前值
            continue

        # 4) 已无路可降，保留文件并在 stderr 提示
        sys.stderr.write(
            f"WARN: {out_path} 体积 {size_bytes / 1024.0:.0f} KB 仍超过 {max_size_kb} KB 上限，保留当前结果\n"
        )
        return (current_fmt, current_quality, attempts, size_bytes / 1024.0)

    # 走完 8 轮仍未达标（理论上不会到这里）
    return (current_fmt, current_quality, attempts, os.path.getsize(out_path) / 1024.0)


def render_figures_to_pngs(
    pdf_path,
    refs,
    out_dir,
    dpi_scale=2.0,
    figure_format="png",
    figure_quality=85,
    max_width=None,
    max_size_kb=None,
    make_thumbnail=False,
    thumbnail_width=400,
    visual_bbox_map=None,
    naming_scheme="legacy",
    slug=None,
):
    # type: (str, list, str, float, str, int, int, int, bool, int, dict, str, Optional[str]) -> tuple
    """对每条 (page, fig_num, bbox_or_None) 截取图本身，存为图片文件。

    定位策略（优先级从高到低）：
    1. **visual_bbox**（Stage 2 Gemini 视觉定位，PDF point）— 已紧贴 figure+caption，加 padding=2
    2. **caption 定位**（本地算法）— 包含 caption 但不延伸到正文，加 padding=5
    3. **Gemini bbox hint**（Stage 1 prompt 嵌入的 bbox=...）— 仅作最后兜底，去 padding
    4. 若都没有，跳过该图并 stderr WARN

    渲染策略：
    - max_width：在渲染阶段钳 `effective_scale = min(dpi_scale, max_width / clip.width_pt)`
      避免后期重采样损失
    - figure_format：png（无损）/ webp（有损，支持透明）/ jpeg（有损，alpha 自动 fallback webp）
    - max_size_kb：保存后超限则按 quality → format → scale 降级（详见 _save_with_constraints）
    - make_thumbnail：额外生成 figures/<name>.thumb.<ext>，受 --max-size-kb 约束
      （--max-width 不约束缩略图；thumbnail_width 自带尺寸上限）

    命名方案（naming_scheme, 2026-06-30 加固）：
    - "legacy"（默认，向后兼容）: 文件 `figure-pX-fY.<ext>`，rel path 加
      `figures/` 前缀。用于 `--extract-figures` 模式。
    - "raw": 文件 `fig-NN.<ext>`（fig_num 零填充），rel path 加
      `../assets/<slug>/` 前缀。用于 `--full` 模式（对齐
      `MEMORY/gemini-paper-summary-full-mode-design.md §7` + `eval/evals.json`
      契约）。缩略图同套命名加 `-thumb` 后缀。
      slug 必填（raw 模式的 rel path 前缀依赖 slug）；None 时走
      `figures/` 前缀退化处理（与 legacy 一致，避免 silent 错误）。
    - 决策背景：raw 端产物被下游消费方按 `fig-NN.png` 规律找文件，
      legacy 命名 + `figures/` 前缀会导致消费方按约定找不到图。

    返回 (full_map, thumb_map, dim_map)：
      - full_map: {(page, fig_num): "<prefix><file>.<ext>"}
        - legacy: "figures/figure-pX-fY.<ext>"
        - raw:    "../assets/<slug>/fig-NN.<ext>"
      - thumb_map: {(page, fig_num): "<prefix><file>.thumb.<ext>"}（无缩略图时为空）
      - dim_map: {(page, fig_num): (width_px, height_px)}——full 图的实际像素尺寸,
        给 embed_figure_refs 用来在 markdown image title 字段写 `=WxH` 提示
        （缩略图也共用同图尺寸——点缩略图跳原图看到的也是这张的尺寸）"""
    if not _HAS_PYMUPDF:
        sys.stderr.write(
            "ERROR: --extract-figures 需要 pymupdf，但未安装。\n"
            "       安装命令: pip install --user --break-system-packages pymupdf\n"
        )
        sys.exit(2)
    if not refs:
        return {}, {}, {}

    os.makedirs(out_dir, exist_ok=True)

    ext_map = {"png": "png", "webp": "webp", "jpeg": "jpg"}
    full_result = {}
    thumb_result = {}
    dim_result = {}  # v3.2+: (page, fig_num) → (width_px, height_px)，给 embed_figure_refs 加 =WxH
    visual_bbox_map = visual_bbox_map or {}

    # 命名方案：把 file_stem（不含扩展名）与 rel_prefix 解耦（2026-06-30）
    # raw 模式需要 slug；缺失时降级到 legacy 避免 silent 错误。
    use_raw = naming_scheme == "raw" and slug

    doc = fitz.open(pdf_path)
    try:
        pages_needed = sorted({p for p, _, _ in refs})
        for page_num in pages_needed:
            if page_num < 1 or page_num > len(doc):
                sys.stderr.write(f"WARN: 跳过越界页 {page_num}\n")
                continue
            page = doc[page_num - 1]
            for p, f, bbox in refs:
                if p != page_num:
                    continue
                key = (p, f)
                if key in full_result:
                    continue
                page_rect = page.rect
                clip = None
                # 1) 最高优先级：Stage 2 Gemini 视觉定位结果（PDF point，已紧贴）
                v_entry = visual_bbox_map.get((p, f))
                if v_entry and "bbox_pt" in v_entry:
                    x0, y0, x1, y1 = v_entry["bbox_pt"]
                    # 用 caption 顶部 **减去 2pt 安全边距** 钳 y1——caption 文字不放进图片
                    # 直接 cap_bbox[1] 不够,Stage 2 的 y1 可能略低于 caption top(几像素),
                    # 加 2pt 还会推进 caption 内;先 -2 留 buffer,再不加 y1 padding
                    cap_bbox = find_figure_caption(page, f)
                    if cap_bbox is not None:
                        y1 = min(y1, cap_bbox[1] - 2.0)
                    pad = 2.0
                    x0 = max(page_rect.x0, x0 - pad)
                    y0 = max(page_rect.y0, y0 - pad)
                    x1 = min(page_rect.x1, x1 + pad)
                    # y1 钳完 caption 顶后, **不再加 padding**——加 padding 会把 caption 重新框进来
                    y1 = min(page_rect.y1, y1)
                    if x1 - x0 >= 20 and y1 - y0 >= 20:
                        clip = fitz.Rect(x0, y0, x1, y1)
                # 2) 次优先级：本地 caption 定位（**不**包含 caption，caption 由 Markdown 文本承载）
                if clip is None:
                    clip = find_figure_bbox_by_caption(page, f, include_caption=False)
                    if clip is not None:
                        # caption 定位用 +5 padding 在左/上/右;**y1 不加 padding**——
                        # find_figure_bbox_by_caption(include_caption=False) 返回的 y1
                        # 已经是 caption 顶,加 padding 会把 caption 框回来
                        clip = fitz.Rect(
                            max(page_rect.x0, clip.x0 - 5),
                            max(page_rect.y0, clip.y0 - 5),
                            min(page_rect.x1, clip.x1 + 5),
                            min(page_rect.y1, clip.y1),  # 不加 y1 padding
                        )
                # 3) 最后兜底：Stage 1 Gemini bbox hint（精度差）
                if clip is None and bbox is not None:
                    x0, y0, x1, y1 = bbox
                    x0 = max(page_rect.x0, min(x0, page_rect.x1))
                    x1 = min(page_rect.x1, max(x1, page_rect.x0))
                    y0 = max(page_rect.y0, min(y0, page_rect.y1))
                    y1 = min(page_rect.y1, max(y1, page_rect.y0))
                    hint_h = y1 - y0
                    # sanity check:Gemini Stage 1 自由发挥写 bbox 时,容易把 figure
                    # 下面紧跟的整段正文都框进去(典型 case:ART-ICDE'13 p.11 Fig 16,
                    # Gemini 给的 hint bbox 高 ~375pt,实际图只有 ~150pt)。
                    # 若 hint 高度超过 250pt 且 caption locator 能算出更紧的 bbox,
                    # 用 caption locator 替掉 hint——避免整段正文被框进图。
                    if hint_h > 250:
                        caption_clip = find_figure_bbox_by_caption(page, f, include_caption=False)
                        if caption_clip is not None and (caption_clip.y1 - caption_clip.y0) >= 50:
                            sys.stderr.write(
                                f"INFO: 第 {p} 页 Figure {f} Gemini bbox hint 高度 {hint_h:.0f}pt 过大,"
                                f"改用 caption locator 算出 {caption_clip.y1 - caption_clip.y0:.0f}pt\n"
                            )
                            x0, y0, x1, y1 = caption_clip.x0, caption_clip.y0, caption_clip.x1, caption_clip.y1
                    if x1 - x0 < 50 or y1 - y0 < 50:
                        clip = None
                    else:
                        sys.stderr.write(
                            f"INFO: 第 {p} 页 Figure {f} 回退到 Gemini bbox hint "
                            f"({x1-x0:.0f}x{y1-y0:.0f}pt)\n"
                        )
                        clip = fitz.Rect(x0, y0, x1, y1)
                if clip is None:
                    sys.stderr.write(
                        f"WARN: 第 {p} 页 Figure {f} 定位失败（既无 visual bbox 也无 caption 也无有效 hint），跳过\n"
                    )
                    continue

                # === 渲染主体：max_width 在 scale 阶段钳 ===
                effective_scale = dpi_scale
                if max_width is not None:
                    target_w_px = clip.width * dpi_scale
                    if target_w_px > max_width:
                        effective_scale = max_width / clip.width
                matrix = fitz.Matrix(effective_scale, effective_scale)
                pix = page.get_pixmap(matrix=matrix, clip=clip)

                # === alpha + jpeg fallback ===
                actual_fmt = figure_format
                if figure_format == "jpeg" and pix.alpha:
                    # JPEG 不支持 alpha；优先 fallback 到 webp（需 Pillow），否则回 PNG
                    if _HAS_PILLOW:
                        sys.stderr.write(f"INFO: 第 {p} 页 Figure {f} 含 alpha 通道，JPEG 不支持透明，自动改用 webp\n")
                        actual_fmt = "webp"
                    else:
                        sys.stderr.write(
                            f"INFO: 第 {p} 页 Figure {f} 含 alpha 通道，JPEG 不支持透明；"
                            f"未装 Pillow 走 webp，回退到 PNG\n"
                        )
                        actual_fmt = "png"

                # === 保存主体 ===
                # 注意：_save_pixmap_with_constraints 可能降级到不同格式（PNG→WebP）
                # 返回的 fmt_used 才是最终落盘的扩展名
                # 命名按 naming_scheme 走(2026-06-30 加固,见函数头 docstring):
                # - raw: file="fig-NN.<ext>"(fig_num 零填充), rel="../assets/<slug>/"
                # - legacy: file="figure-pX-fY.<ext>", rel="figures/"
                if use_raw:
                    file_stem = f"fig-{f:02d}"
                    rel_prefix = f"../assets/{slug}/"
                else:
                    file_stem = f"figure-p{p}-f{f}"
                    rel_prefix = "figures/"
                full_name = f"{file_stem}.{ext_map[actual_fmt]}"
                full_path = os.path.join(out_dir, full_name)
                fmt_used, qual_used, attempts, size_kb = _save_pixmap_with_constraints(
                    pix=pix,
                    path=full_path,
                    format_ext=actual_fmt,
                    base_quality=figure_quality,
                    max_size_kb=max_size_kb,
                )
                # 用 fmt_used 重算最终文件名（覆盖降级的情况）
                final_full_name = f"{file_stem}.{ext_map[fmt_used]}"
                full_result[key] = rel_prefix + final_full_name
                dim_result[key] = (pix.width, pix.height)  # v3.2+: 供 embed_figure_refs 写 =WxH
                sys.stderr.write(
                    f"OK: p{p}.f{f} → {final_full_name} "
                    f"({pix.width}x{pix.height}, {size_kb:.0f} KB, "
                    f"fmt={fmt_used}, q={qual_used}, attempts={attempts + 1})\n"
                )

                # === 缩略图 ===
                if make_thumbnail:
                    thumb_scale = thumbnail_width / clip.width
                    thumb_pix = page.get_pixmap(matrix=fitz.Matrix(thumb_scale, thumb_scale), clip=clip)
                    # 缩略图用 `.thumb.<ext>` 后缀，与原图同目录
                    final_base, _ = os.path.splitext(final_full_name)
                    _thumb_ext = os.path.splitext(final_full_name)[1]
                    thumb_name = f"{final_base}.thumb{_thumb_ext}"
                    thumb_path = os.path.join(out_dir, thumb_name)
                    thumb_fmt_used, _, _, thumb_size_kb = _save_pixmap_with_constraints(
                        pix=thumb_pix,
                        path=thumb_path,
                        format_ext=fmt_used,
                        base_quality=figure_quality,
                        max_size_kb=max_size_kb,
                    )
                    # 若缩略图也降级格式（理论上不会），同步更新名字
                    if thumb_fmt_used != fmt_used:
                        thumb_name = f"{final_base}.thumb.{ext_map[thumb_fmt_used]}"
                    thumb_result[key] = rel_prefix + thumb_name
                    sys.stderr.write(
                        f"OK: p{p}.f{f} → {thumb_name} ({thumb_pix.width}x{thumb_pix.height}, {thumb_size_kb:.0f} KB)\n"
                    )
    finally:
        doc.close()
    return full_result, thumb_result, dim_result


# ----------------------------------------------------------------------------
# Stage 2: Gemini 视觉定位 (refine bbox + 读完整 caption + 过滤装饰图)
# ----------------------------------------------------------------------------

# Gemini Robotics-ER 官方约定 + 仓库 PDF 场景的折中:
# - 字段名 box_2d,顺序 [ymin, xmin, ymax, xmax],归一化 0-1000 整数,原点左上
# - 1000 ↔ 页面渲染图的宽/高像素比例 = 页面 PDF point 的宽/高(渲染图未做宽高变形),
#   所以 0-1000 直接换算为 PDF point: x_pt = x_norm * page.rect.width / 1000
VISUAL_BBOX_SCHEMA = {
    "type": "object",
    "properties": {
        "page": {"type": "integer", "description": "PDF 页码 (1-based)"},
        "figures": {
            "type": "array",
            "description": "该页所有 figure,按 fig_num 升序",
            "items": {
                "type": "object",
                "properties": {
                    "fig_num": {"type": "integer", "description": "论文里的 Figure 编号 (如 1)"},
                    "bbox_2d": {
                        "type": "array",
                        "description": "[ymin, xmin, ymax, xmax],归一化 0-1000 整数,原点左上",
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "full_caption": {
                        "type": "string",
                        "description": "图片下方 caption 完整文本(可能跨多行,逐字合并)",
                    },
                    "is_key_figure": {
                        "type": "boolean",
                        "description": "true=整体架构/核心模块/概念流程/关键对比;false=装饰/logo/坐标轴/表格",
                    },
                },
                "required": ["fig_num", "bbox_2d", "full_caption", "is_key_figure"],
            },
        },
    },
    "required": ["page", "figures"],
}

VISUAL_BBOX_PROMPT = (
    "你将看到一张论文 PDF 页面渲染图(已用 pymupdf 渲染为 PNG)。\n\n"
    "请识别页面中所有的 Figure(图),按论文中的出现顺序返回。每张图给:\n"
    "- fig_num: 论文里的 Figure 编号(从 caption 中读,如 'Figure 1' → 1)\n"
    "- bbox_2d: 该 figure 的紧致边界框(含 caption),格式 [ymin, xmin, ymax, xmax],"
    "归一化到 0-1000 整数,原点在图像左上角。框必须紧贴 figure 主体与 caption,"
    "不要把无关正文、页眉、页脚、栏外边距框进来。\n"
    "- full_caption: 从图片下方 caption 完整读出(可能跨多行,逐字合并,不要截断)。"
    "包含 'Figure N:' 前缀。\n"
    "- is_key_figure: true=整体架构/核心模块/概念流程/关键对比示意;"
    "false=装饰/logo/坐标轴标注/表格截图/补充材料\n\n"
    '返回 JSON {"page": <页码>, "figures": [...]};'
    "figures 数组按 fig_num 升序。\n"
    '若该页没有 figure,返回 {"page": <页码>, "figures": []}。'
)


def render_pages_for_gemini(pdf_path, refs, dpi_scale=2.0):
    # type: (str, list, float) -> dict
    """Stage 2 辅助: 把含 fig 引用的页面渲染成 PNG,按 page 分组共用一次渲染。
    输入 refs: parse_figure_refs() 的输出 [(page, fig_num, bbox_or_None), ...]
    返回 {page_num: png_bytes};同一页只渲染一次。
    渲染图未做宽高变形,因此 Gemini 返回的 0-1000 归一化坐标可直接换算为 PDF point。"""
    if not _HAS_PYMUPDF:
        sys.stderr.write(
            "ERROR: --refine-figures 需要 pymupdf,但未安装。\n"
            "       安装命令: pip install --user --break-system-packages pymupdf\n"
        )
        sys.exit(2)
    pages_needed = sorted({p for p, _, _ in refs})
    out = {}
    doc = fitz.open(pdf_path)
    try:
        for page_num in pages_needed:
            if page_num < 1 or page_num > len(doc):
                sys.stderr.write(f"WARN: Stage 2 跳过越界页 {page_num}\n")
                continue
            page = doc[page_num - 1]
            matrix = fitz.Matrix(dpi_scale, dpi_scale)
            pix = page.get_pixmap(matrix=matrix)
            out[page_num] = pix.tobytes("png")
    finally:
        doc.close()
    sys.stderr.write(f"INFO: Stage 2 已渲染 {len(out)} 页 (dpi_scale={dpi_scale})\n")
    return out


def _parse_visual_bbox_response(response_json, page_num):
    # type: (object, int) -> list
    """校验 + 标准化 Gemini 返回的 JSON,返回 [(fig_num, (x0,y0,x1,y1)_pt, full_caption), ...]。
    bbox 越界则 clamp 到 [0, 1000];若完全退化(ymin>=ymax 或 xmin>=xmax)则丢弃该条。
    full_caption 去前后空白。"""
    out = []
    if not isinstance(response_json, dict):
        return out
    figures = response_json.get("figures", [])
    if not isinstance(figures, list):
        return out
    for fig in figures:
        if not isinstance(fig, dict):
            continue
        try:
            fig_num = int(fig.get("fig_num"))
            bbox = fig.get("bbox_2d", [])
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            # bbox_2d = [ymin, xmin, ymax, xmax]
            ymin, xmin, ymax, xmax = [int(round(float(v))) for v in bbox]
            # clamp 到 [0, 1000]
            ymin = max(0, min(1000, ymin))
            xmin = max(0, min(1000, xmin))
            ymax = max(0, min(1000, ymax))
            xmax = max(0, min(1000, xmax))
            if ymax <= ymin or xmax <= xmin:
                continue  # bbox 退化,丢弃
            full_caption = str(fig.get("full_caption", "")).strip()
            is_key = bool(fig.get("is_key_figure", True))
            out.append((fig_num, (ymin, xmin, ymax, xmax), full_caption, is_key))
        except (TypeError, ValueError):
            continue
    return out


def _gemini_call_with_retry(client, model, contents, config, max_attempts=3, label="Gemini"):
    # type: (object, str, list, object, int, str) -> object
    """统一 Gemini 调用 + 临时错误重试,**不切模型**(2026-06-21 决策, SSOT)。

    重试策略:
    - 最多 max_attempts 次(默认 3)
    - 临时错误 (5xx / 429) 退避 2s, 4s 后重试
    - 永久错误 (400/401/403/404) 直接抛(不重试)
    - 网络异常 / 超时也走重试(无 status_code 时一律重试)

    **无自动 fallback**: 重试全程使用同一个 model,绝不静默切到便宜模型。
    终失败抛 RuntimeError, 错误信息含 model 名 + status_code + 用户可执行的下一步
    (稍后重试 / 检查 GEMINI_API_KEY 与配额 / 用 `--model <id>` 显式换模型)。

    SSOT: 与 SKILL.md §核心原则 #8 "无自动 fallback" 决策对齐;主调用
    (call_gemini) 与 Stage 2 (_call_gemini_with_retry) 都委托本函数,保证两处
    不会策略漂移。
    """
    import time  # 局部 import,避免顶层 import 副作用

    # google.genai.errors.APIError 子类都有 status_code 属性
    last_err = None
    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            last_err = e
            status = getattr(e, "status_code", None) or getattr(e, "code", None)
            # 永久错误:直接抛(由外层 catch 报 WARN/ERROR)
            if status is not None and status in {400, 401, 403, 404}:
                raise
            # 临时错误或无 status_code:重试
            if attempt + 1 < max_attempts:
                backoff = 2 ** (attempt + 1)  # 2s, 4s
                sys.stderr.write(
                    f"INFO: {label} 调用第 {attempt + 1}/{max_attempts} 次失败"
                    f"({type(e).__name__}: {e}),{backoff}s 后重试...\n"
                )
                time.sleep(backoff)
                continue
            # 已到 max_attempts,跑完重试
            break
    # 终失败:抛带上下文的 RuntimeError(供上层 / 用户判断)
    status = getattr(last_err, "status_code", None) or getattr(last_err, "code", None)
    raise RuntimeError(
        f"{label} 调用 {max_attempts} 次仍失败: model={model}, status={status}, "
        f"error={type(last_err).__name__}: {last_err}\n"
        f"  → 不自动降级到更便宜的模型(质量风险 > 便利,见 SKILL.md §核心原则 #8)。\n"
        f"  → 下一步(由用户决定,agent 勿自动执行):\n"
        f"     1) 稍后重试  2) 检查 GEMINI_API_KEY / 配额 / 服务状态\n"
        f"     3) 用 --model <id> 显式换模型"
    )


def _call_gemini_with_retry(client, model, png_bytes, prompt, temperature, page_num, max_attempts=3):
    # type: (object, str, bytes, str, float, int, int) -> object
    """Stage 2 单页 Gemini 调用,委托给 _gemini_call_with_retry 走统一策略。

    - 临时错误 (5xx / 429) 退避 2s, 4s 后重试
    - 永久错误 (400/401/403/404) 直接抛
    - 最多 max_attempts 次, 终失败抛 RuntimeError(错误信息含 page_num)
    - **不切模型**(无自动 fallback,与 _gemini_call_with_retry 同策略)
    """
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=VISUAL_BBOX_SCHEMA,
    )
    contents = [types.Part.from_bytes(data=png_bytes, mime_type="image/png"), prompt]
    return _gemini_call_with_retry(
        client,
        model,
        contents,
        config,
        max_attempts=max_attempts,
        label=f"Stage 2 第 {page_num} 页",
    )


def call_gemini_for_visual_bbox(pdf_path, page_to_png, model, temperature):
    # type: (str, dict, str, float) -> dict
    """Stage 2: 对每页调用 Gemini,要求返回精确 bbox + 完整 caption + 是否关键图。
    返回 {(page, fig_num): {"bbox_pt": (x0,y0,x1,y1), "full_caption": str,
                              "is_key_figure": bool}}
    - bbox_pt 是 PDF point 单位(由 Gemini 0-1000 归一化 × page.rect.width/1000 换算)
    - 失败页面(stderr WARN)返回该页空字典,不让 Stage 2 整体失败
    - 过滤 is_key_figure=False 的图(装饰/logo/表格)
    - 对每页 Gemini 调用做最多 3 次重试(应对 503/429 等临时错误)"""
    if not page_to_png:
        return {}
    client = genai.Client()
    result = {}
    pages_sorted = sorted(page_to_png.keys())
    sys.stderr.write(f"INFO: Stage 2 调用 Gemini ({model}) 视觉定位 {len(pages_sorted)} 页...\n")
    # 读一次 page.rect 宽度/高度,用于坐标换算
    doc = fitz.open(pdf_path)
    try:
        page_rects = {}
        for page_num in pages_sorted:
            if 1 <= page_num <= len(doc):
                page_rects[page_num] = doc[page_num - 1].rect
    finally:
        doc.close()

    for page_num in pages_sorted:
        png_bytes = page_to_png[page_num]
        page_rect = page_rects.get(page_num)
        if page_rect is None:
            sys.stderr.write(f"WARN: Stage 2 跳过越界页 {page_num}\n")
            continue
        try:
            response = _call_gemini_with_retry(client, model, png_bytes, VISUAL_BBOX_PROMPT, temperature, page_num)
            text = getattr(response, "text", None)
            if not text:
                sys.stderr.write(f"WARN: Stage 2 第 {page_num} 页 Gemini 返回为空\n")
                continue
            parsed = json.loads(text)
        except Exception as e:
            sys.stderr.write(f"WARN: Stage 2 第 {page_num} 页 Gemini 调用失败: {type(e).__name__}: {e}\n")
            continue

        figs = _parse_visual_bbox_response(parsed, page_num)
        if not figs:
            continue
        for fig_num, bbox_2d, full_caption, is_key in figs:
            # 注意：不再因为 is_key_figure=False 就跳过 — 视觉上 Gemini 在混排页
            # （如 Fig 15/Fig 16/Table IV 同页）容易把关键图误判为非关键图，丢掉
            # bbox 后上层只能回退到精度差的 bbox hint / caption locator,导致整段
            # 正文被框进图。is_key 只用来打日志,决定"是否在 summary 中引用这张图"
            # 由 prompt 端（用户提供的 fig 引用列表）控制,Stage 2 不越权。
            if not is_key:
                sys.stderr.write(
                    f"INFO: Stage 2 第 {page_num} 页 Figure {fig_num} 标记为非关键图,"
                    f"仍保留 bbox(由调用方决定是否引用)\n"
                )
            ymin, xmin, ymax, xmax = bbox_2d
            # 0-1000 归一化 → PDF point
            x0_pt = xmin * page_rect.width / 1000.0
            y0_pt = ymin * page_rect.height / 1000.0
            x1_pt = xmax * page_rect.width / 1000.0
            y1_pt = ymax * page_rect.height / 1000.0
            result[(page_num, fig_num)] = {
                "bbox_pt": (x0_pt, y0_pt, x1_pt, y1_pt),
                "full_caption": full_caption,
            }
    sys.stderr.write(f"INFO: Stage 2 视觉定位完成,共 {len(result)} 个图\n")
    return result


# 抓整行 `![alt](PDF p.X fig.N ...)` 用于在图后追加 caption 行
FIGURE_LINE_RE = re.compile(r"(!\[[^\]]*\])\(PDF p\.(\d+)\s+fig\.(\d+)(?:\s+bbox=\[?[\d.,]+\]?)?\)")
# 抓已插入的 `**图 N**：<caption>` 行,防止重复插入
CAPTION_LINE_RE = re.compile(r"^\s*\*\*图\s*\d+\s*[：:]\*\*\s*", re.MULTILINE)


def insert_caption_after_figure(md_text, visual_bbox_map):
    # type: (str, dict) -> str
    """已弃用（v3.2, 2026-06-21）：caption 写在 image alt 字段,不再注入 markdown body。

    历史设计（v3.1 及更早）:在每个 `![alt](PDF p.X fig.N ...)` 引用行后追加
    一行 `**图 N**：<caption>`。但 outline-wiki 把单 `\n` 渲染成软空格,caption
    视觉紧贴图片底部;且 image alt 已经渲染了 caption,body 重复显示。

    现设计（v3.2 终版）:caption 写到 markdown image 的 alt 字段
    (`![图 N: <中文翻译+总结>](<url> "=WxH")`)——这是 outline UI 唯一渲染
    为图片下方 caption 文字的通道。markdown body **不**写独立 caption 行,
    也不带 `— <role>` 后段。详见 `MEMORY/gemini-paper-summary-figure-extraction-edges.md` §8。

    本函数保留为 **no-op + 清理**(只剥已存在的 `**图 N**：...` 行,不再插入新行),
    让旧调用点不会报错。**新代码不应再调用本函数**——caption 走 image alt 通道。

    输入 visual_bbox_map: 保留参数签名兼容旧调用,但完全忽略
    - 仍执行:去除已注入的 `**图 N**：<caption>` 行(防遗留脚本残留)
    - 不再执行:在图片行后插入 caption 行
    """
    # 防御性清理:去掉旧版注入的 caption 行(`**` 在冒号之前)
    # 匹配 `\n**图 N**：<caption 文字>` 整行
    cleaned = re.sub(
        r"\n+\*\*图\s*\d+\s*\*\*\s*[：:][^\n]*",
        "",
        md_text,
    )
    return cleaned


# 缩略图二次包裹：`![alt](figures/figure-pX-fY.thumb.png)` → `[![alt](thumb)](full)`
# 缩略图二次包裹：`![alt](figures/figure-pX-fY.thumb.png)` → `[![alt](thumb)](full)`
# 2026-06-30 扩展:同时匹配 raw 模式的 `../assets/<slug>/fig-NN-thumb.png`(naming_scheme="raw"),
# 让 full + --thumbnail 走同款 click-to-full 体验,虽然该组合与 raw 端单图约定略冲突(已 WARN)。
THUMB_IMG_RE = re.compile(
    r"(!\[[^\]]*\])\(("
    r"figures/figure-[^\)]+\.thumb\.[a-z]+"  # legacy: --extract-figures
    r"|"
    r".+/fig-\d+-thumb\.[a-z]+"  # raw: --full(--thumbnail 反模式,WARN 但仍工作)
    r")\)"
)


def _strip_failed_figure_lines(md_text, failed_figs):
    # type: (str, set) -> str
    """把 failed_figs 里 (page, fig_num) 对应的 `![...](PDF p.X fig.N ...)` 整行删除，
    并剥掉"如图 N 所示 / 见图 N / Figure N 展示了..."等独立呼应句里的图编号引用
    （保留描述文字）。failed_figs 为空时原样返回。

    复用自 embed_figure_refs 的失败兜底逻辑（2026-06-21），提取成独立 helper 供
    "quick 模式未导出图时清破图"路径复用（2026-07-01，strip_pdf_figure_refs）。
    """
    if not failed_figs:
        return md_text

    # 1) 整行删除含失败图引用的 ![...](PDF p.X fig.N ...) 行
    lines = md_text.split("\n")
    new_lines = []
    fig_ref_line_re = re.compile(r"!\[.*?\]\(PDF p\.\d+\s+fig\.\d+")
    for line in lines:
        if fig_ref_line_re.search(line):
            line_failed = False
            for m in FIGURE_REF_RE.finditer(line):
                p_, f_ = int(m.group(1)), int(m.group(2))
                if (p_, f_) in failed_figs:
                    line_failed = True
                    break
            if line_failed:
                continue  # 整行丢弃（图行）
        new_lines.append(line)
    md_text = "\n".join(new_lines)

    # 2) 剥"如图 N 所示 / 见图 N / 图 N 展示了..." 等呼应句里的图编号（保留描述）
    all_fig_nums = {f for (_, f) in failed_figs}

    def strip_fig_ref(text, fnum):
        # "如图 16 所示" / "如图16所示" / "图 16 展示了" / "见图 16" / "(图 16)"
        patterns = [
            rf"如?\s*图\s*{fnum}\s*所示[，,。\s]*",
            rf"如?\s*图\s*{fnum}\s*展示[了]?[，,。\s]*",
            rf"如?\s*图\s*{fnum}\s*所示，",
            rf"见\s*图\s*{fnum}\s*[，,。\s]*",
            rf"图\s*{fnum}\s*[：:]?\s*",
        ]
        for pat in patterns:
            text = re.sub(pat, "", text)
        return text

    lines = md_text.split("\n")
    cleaned = []
    for line in lines:
        for fnum in all_fig_nums:
            line = strip_fig_ref(line, fnum)
        # 清理掉因剥掉图号而失去指代的孤立引导词
        line = re.sub(r"如\s*[，,。；;]\s*", "如，", line)
        line = re.sub(r"^\s*[,，;；]\s*", "", line)
        line = re.sub(r"[,，;；]\s*[,，;；]\s*", "，", line)
        if line.strip():
            cleaned.append(line)
    return "\n".join(cleaned)


def strip_pdf_figure_refs(md_text):
    # type: (str) -> str
    """清理 Markdown 里**所有** `![...](PDF p.X fig.N ...)` 破图引用。

    把全部 PDF figure reference 当作"失败图"走 _strip_failed_figure_lines（整行删 +
    剥"如图 N 所示"呼应句）。用于 quick 模式 `--no-figures` / 缺 pymupdf / stdout 等
    不导出图的边界，避免产物残留任何渲染器都显示不了的 PDF reference 破图。
    与 embed_figure_refs 的产图失败兜底同源清理逻辑（2026-07-01）。
    """
    all_refs = set()
    for m in FIGURE_REF_RE.finditer(md_text):
        all_refs.add((int(m.group(1)), int(m.group(2))))
    return _strip_failed_figure_lines(md_text, all_refs)


def embed_figure_refs(md_text, ref_to_relpath, ref_to_fullpath=None, ref_to_dim=None):
    # type: (str, dict, dict, dict) -> str
    """把 Markdown 里的 `(PDF p.X fig.N [bbox=...])` 替换为 `(相对路径 "=WxH")`。
    key 用 (page, fig_num)，忽略 bbox 差异（同图号应指向同一文件）。

    缩略图模式（--thumbnail）：`ref_to_fullpath` 是按 (page, fig_num) 的全图路径映射
    （与 ref_to_relpath 同 key 体系，只是 value 是 full_path 而非 thumb_path）。
    函数会先把 ref_to_fullpath 反向成 `{thumb_path: full_path}`，再把 Markdown 里的
    `![alt](thumb)` 二次包裹为 `[![alt](thumb)](full)`，实现点击缩略图跳原图。

    尺寸提示（v3.2+）：`ref_to_dim` 是按 (page, fig_num) 的 (width_px, height_px)
    映射，由 `render_figures_to_pngs` 在保存 PNG 后填入。函数会把 title 字段
    自动补成 `=WxH` 格式（仓库内 `=WxH` 等宽约定），让 outline-wiki 渲染时
    按正确比例显示图片——Gemini 在 prompt 阶段不知道精确像素，本步骤是
    渲染后用本地 pymupdf 读到的真值反填。

    **失败兜底**（2026-06-21，回应用户"实在处理不了不入总结"）：
    如果 (page, fig_num) 不在 `ref_to_relpath` 中（即 `render_figures_to_pngs`
    三层定位都失败、被跳过的图），把整行 `![alt](PDF p.X fig.N ...)` 删除，
    并去掉前一行"如图 N 所示" / "见图 N" / "Figure N 展示了..."等独立呼应句
    中的图编号引用（保留描述文字）。避免 outline 出现破图 + 死引用。
    """
    ref_to_fullpath = ref_to_fullpath or {}
    ref_to_dim = ref_to_dim or {}

    failed_figs = set()  # 收集失败的 (page, fig_num) 集合

    def repl(m):  # type: (re.Match) -> str
        page = int(m.group(1))
        fig_num = int(m.group(2))
        rel = ref_to_relpath.get((page, fig_num))
        if not rel:
            failed_figs.add((page, fig_num))
            return m.group(0)  # 保留原 match,行级删除在下面做
        # v3.2+: 补 =WxH title 字段（仓库内 =WxH 等宽约定）
        dim = ref_to_dim.get((page, fig_num))
        title = ' "={}x{}"'.format(dim[0], dim[1]) if dim else ""
        return f"({rel}{title})"

    md_text = FIGURE_REF_RE.sub(repl, md_text)

    # 缩略图二次包裹：ref_to_fullpath 是 (key) → full_path 字典，需要反向成 thumb→full
    if ref_to_fullpath:
        # 反向索引：thumb_path → full_path
        thumb_to_full = {}
        for key, full_path in ref_to_fullpath.items():
            thumb_path = ref_to_relpath.get(key)
            if thumb_path and thumb_path != full_path:
                thumb_to_full[thumb_path] = full_path

        def wrap_repl(m):  # type: (re.Match) -> str
            img_tag = m.group(1)  # ![alt]
            thumb_path = m.group(2)  # figures/figure-pX-fY.thumb.<ext>
            full_path = thumb_to_full.get(thumb_path)
            if not full_path:
                return m.group(0)
            return f"[{img_tag}({thumb_path})]({full_path})"

        md_text = THUMB_IMG_RE.sub(wrap_repl, md_text)

    # === 失败图行处理（委托给 _strip_failed_figure_lines，与 quick 未导出图清破图同源）===
    md_text = _strip_failed_figure_lines(md_text, failed_figs)
    if failed_figs:
        sys.stderr.write(
            f"INFO: 跳过 {len(failed_figs)} 张图（视觉定位 + caption locator + "
            f"bbox hint 三层均失败），已从 markdown 删除对应行 + 呼应句\n"
        )

    return md_text


# ----------------------------------------------------------------------------
# 参数解析
# ----------------------------------------------------------------------------


def parse_args(argv=None):  # type: (Optional[list]) -> argparse.Namespace
    parser = argparse.ArgumentParser(
        prog="gemini_pdf_summary",
        description="用 Gemini 多模态读 PDF 并按文档类型路由到对应模板，输出中文 Markdown 总结。",
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="本地 PDF 文件的路径（绝对或相对路径均可）。",
    )
    parser.add_argument(
        "--type",
        choices=VALID_TYPES,
        default=None,
        help=(
            "PDF 文档类型；决定加载哪个模板与图表处理策略：\n"
            "  paper      - 学术论文（含 quick + full 双模式，quick 默认抽原始图）\n"
            "  manual     - 产品手册 / datasheet / 用户手册（单模式，概念用 mermaid / 表格）\n"
            "  whitepaper - 行业 / 技术 / vendor 白皮书（单模式，概念用 mermaid / 表格）\n"
            "  book       - 书籍 / 长篇技术文档（仅 full 模式，按 PDF 原生章节全量转写）\n"
            "默认 None → 与 --auto-detect 互斥；必须二选一。\n"
            "未传且未传 --auto-detect 时，agent 应反问用户确定类型（见 SKILL.md 工作流）。"
        ),
    )
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        help=(
            "自动识别 PDF 类型（PDF 元数据 + 首页文本启发式 + Gemini 看首页 1-3 页验证）。\n"
            "与 --type 互斥：必须二选一。识别失败时报错并列出 4 类候选让用户显式选。"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "输出路径。quick 模式默认带图：--output 视作 **目录**（写 summary.md + figures/）；"
            "加 --no-figures 则视作 .md 文件路径；不传则打印到 stdout"
            "（不导出图，Markdown 里的 PDF 图引用自动清理成纯文本）。"
            "--full 模式 --output 视作 wiki 仓根（见 SKILL.md §D）。"
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini 模型 ID，默认 {DEFAULT_MODEL}（稳定版，支持 PDF + 1M 上下文）。",
    )
    parser.add_argument(
        "--focus",
        default=None,
        help="用户关注点，会拼接到 prompt 末尾。",
    )
    parser.add_argument(
        "--template",
        default="academic",
        choices=["academic", "full"],
        help=(
            "总结模板；academic（默认，精炼速读版，6 段 ## 骨架；字符目标 SSOT 见 assets/prompt-template.md）或 "
            "full（全文级结构化转储，解除字符数约束，按 PDF 章节逐小节展开；"
            "通常配合 --full 模式使用）。"
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "全文级抽取模式：单次调用同时产 quick summary (academic 模板，默认带图) "
            "+ 全量转写 (full 模板，自包含无图，给 agent 多轮查询用)，**两份**产物。"
            "产物 layout 强制 raw-compatible：--output 视为 wiki 仓根，"
            "写到 <wiki-root>/raw/papers/<slug>.quick.md + .full.md；"
            "quick 的图落到 <wiki-root>/raw/assets/<slug>/fig-NN.png（full 不落 PNG、不跑 Stage 2）。"
            "用 --slug 显式指定论文 slug（默认从 PDF 文件名推断）。"
            "若 raw 端产物已存在默认拒绝覆盖（用 --force-full 显式允许）。"
        ),
    )
    parser.add_argument(
        "--slug",
        default=None,
        help=(
            "论文 slug（kebab-case；如 'attention-is-all-you-need'）。"
            "默认从 PDF 文件名去后缀后再 kebab-case 化推断。"
            "仅在 --full 模式下有意义；否则忽略。"
        ),
    )
    parser.add_argument(
        "--force-full",
        action="store_true",
        help=(
            "允许 --full 模式覆盖 raw/papers/<slug>.full.md 与 .quick.md（默认拒绝覆盖，"
            "理由：full 抽取是'贵读一次'的产物，意外重写会丢下游已经多次引用的 raw）。"
            "仅在 --full 模式下有意义。"
        ),
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="生成温度，默认 0.2（更稳定）。",
    )
    parser.add_argument(
        "--extract-figures",
        action="store_true",
        help=(
            "[向后兼容] quick 模式默认就带图，无需显式传 --extract-figures；"
            "传了等价默认行为。保留此 flag 仅为不破坏既有调用（如 outline-wiki-upload）。"
        ),
    )
    parser.add_argument(
        "--no-figures",
        action="store_true",
        help=(
            "关闭图导出，回到纯 Markdown：--output 视作 .md 文件路径，"
            "Markdown 里的 PDF 图引用被清理成纯文本呼应（不留破图）。"
            "用于批量速读 / 纯文字速览 / 不需要图的场景。"
        ),
    )
    parser.add_argument(
        "--figure-dpi",
        type=float,
        default=2.0,
        help="pymupdf 渲染倍率（默认 2.0，对应 144 DPI），仅在 --extract-figures 启用时生效。",
    )
    parser.add_argument(
        "--figure-format",
        choices=["png", "webp", "jpeg"],
        default="png",
        help="图输出格式（默认 png；webp/jpeg 支持 --figure-quality 压缩）。",
    )
    parser.add_argument(
        "--figure-quality",
        type=int,
        default=85,
        help="webp/jpeg 压缩质量，1-100（默认 85；仅 --figure-format 非 png 时生效）。",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=None,
        help="单张图最大宽度（像素）。超过则等比缩放；None 不限制。",
    )
    parser.add_argument(
        "--max-size-kb",
        type=int,
        default=None,
        help="单张图最大文件体积（KB）。超过则按 quality → format → scale 自动降级；None 不限制。",
    )
    parser.add_argument(
        "--thumbnail",
        action="store_true",
        help="同时生成缩略图。Markdown 引用缩略图，点击跳原图。",
    )
    parser.add_argument(
        "--thumbnail-width",
        type=int,
        default=400,
        help="缩略图宽度（像素，默认 400）。",
    )
    parser.add_argument(
        "--refine-figures",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Stage 2: 用 Gemini 看图视觉定位每个 figure 的精确 bbox + 读完整 caption + "
            "过滤装饰图（默认 True）。关闭用 --no-refine-figures，沿用 Stage 1 的 bbox hint 或 caption 定位。"
            "需要 pymupdf + GEMINI_API_KEY。"
        ),
    )
    parser.add_argument(
        "--refine-dpi",
        type=float,
        default=2.0,
        help=(
            "Stage 2 渲染页面给 Gemini 看的 DPI 倍率（默认 2.0）。"
            "增大可提升定位精度但增加 token 成本与延迟。仅 --refine-figures 启用时生效。"
        ),
    )
    return parser.parse_args(argv)


# ----------------------------------------------------------------------------
# 校验
# ----------------------------------------------------------------------------


def validate_inputs(args):  # type: (argparse.Namespace) -> Tuple[str, bytes, str]
    """校验 PDF 存在 + API key 已设；返回 (model, pdf_bytes, focus_or_empty)。"""
    pdf_path = args.pdf
    if not os.path.isfile(pdf_path):
        sys.stderr.write(f"ERROR: PDF 文件不存在或不可读: {pdf_path}\n")
        sys.exit(2)

    if not os.environ.get("GEMINI_API_KEY"):
        sys.stderr.write(
            "ERROR: 环境变量 GEMINI_API_KEY 未设置。\n"
            "       在 https://aistudio.google.com/apikey 创建后：\n"
            '         export GEMINI_API_KEY="你的 key"\n'
        )
        sys.exit(2)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    if not pdf_bytes:
        sys.stderr.write(f"ERROR: PDF 文件为空: {pdf_path}\n")
        sys.exit(2)

    # 简单 magic-bytes 校验：PDF 头应是 %PDF-
    if not pdf_bytes.startswith(b"%PDF-"):
        sys.stderr.write(
            f"WARNING: 文件 {pdf_path} 的头部不是 %PDF-，可能不是合法 PDF。\n"
            "         仍会尝试提交，但 Gemini 可能返回 400。\n"
        )

    return args.model, pdf_bytes, args.focus or ""


# ----------------------------------------------------------------------------
# 核心：调用 Gemini
# ----------------------------------------------------------------------------


def build_prompt(focus, doc_type=DEFAULT_TYPE, mode="quick"):  # type: (str, str, str) -> str
    """按 doc_type + mode 选择 prompt 源，必要时追加 --focus 注入。

    - doc_type ∈ {"paper", "manual", "whitepaper", "book"}
        * paper → quick / full 双模式
        * manual / whitepaper → 单一模板（mode 参数被忽略，按 quick 加载）
        * book → 仅 full 模式（mode 参数被忽略，按 full 加载）
    - mode:
        * "quick" (默认): paper → DEFAULT_PROMPT (academic 模板); focus 走 FOCUS_INJECTION
        * "full": paper → FULL_PROMPT; focus 走 FOCUS_INJECTION_FULL
    """
    prompt_text = _load_prompt_for_type(doc_type, mode)
    if mode == "full" or doc_type == "paper" and mode == "full":
        injection = FOCUS_INJECTION_FULL
    else:
        injection = FOCUS_INJECTION
    if focus:
        return prompt_text + injection.format(focus=focus.strip())
    return prompt_text


def call_gemini(model, pdf_bytes, prompt, temperature, max_output_tokens=None):  # type: (str, bytes, str, float, Optional[int]) -> str
    """调用 Gemini，返回 Markdown 文本。短 PDF 走 inline；长 PDF 走 File API。

    **无自动 fallback**(2026-06-21 决策): 503/429/500 等高并发 / 限流错误
    先做 3 次重试(2s/4s 退避),仍失败则**直接抛**给上层,**绝不**降级到便宜模型。
    理由: 不同模型对 v3.2 prompt 模板的输出质量差异显著(alt 字段偏差、表格行数
    错位、章节遗漏等),silent fallback 用户感知不到是模型降级导致的,只看到
    "结果怪"——质量风险 > 便利。换模型用 `--model <id>` 显式指定。

    终失败错误信息会明示: model 名 + status_code + 用户可执行的下一步
    (稍后重试 / 检查 GEMINI_API_KEY 与配额 / 用 --model 换模型)。统一策略
    实现见 `_gemini_call_with_retry`(本函数委托给它)。

    `max_output_tokens`（2026-06-30 加固）: None 走模型默认(约 8192 for
    3.5-flash);full 模板需要全文级展开时由 caller 显式传 `FULL_MAX_OUTPUT_TOKENS`
    (65536),避免撞顶截断尾部章节。**SSOT**: 数值仅在 FULL_MAX_OUTPUT_TOKENS
    模块常量定义;prompt-template.md / SKILL.md 不重抄。
    """
    client = genai.Client()  # 自动读 GEMINI_API_KEY

    if len(pdf_bytes) <= MAX_PDF_BYTES_INLINE:
        # 走 inline Part:单请求延迟最低
        contents = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ]
    else:
        # 走 File API:先 upload,再把 uploaded file 放进 contents
        sys.stderr.write(
            "INFO: PDF 超过 20 MB,走 File API 上传。\n"
            "      (文件会在 Google 服务端保留 48 小时;如需立即清理,"
            "参考 references/api-quickstart.md §3。)\n"
        )
        uploaded = client.files.upload(
            file=pdf_bytes,
            config={"display_name": "paper-pdf", "mime_type": "application/pdf"},
        )
        contents = [uploaded, prompt]
        # 把 uploaded.name 暂存,调用方如需清理可从返回值再调用 client.files.delete(name=...)

    config_kwargs = {"temperature": temperature}
    if max_output_tokens is not None:
        config_kwargs["max_output_tokens"] = max_output_tokens
    config = types.GenerateContentConfig(**config_kwargs)
    response = _gemini_call_with_retry(client, model, contents, config, label="主调用")
    text = getattr(response, "text", None)
    if not text:
        sys.stderr.write(f"ERROR: Gemini 返回为空。原始 response: {response}\n")
        sys.exit(3)
    return text


# ----------------------------------------------------------------------------
# --full 模式 helpers：slug 推断 + raw 端冲突检测
# ----------------------------------------------------------------------------

# 沿用 Karpathy LLM Wiki 约定的 kebab-case slug，与 raw/papers/<slug>.* 路径布局同源
_SLUG_NON_KEBAB_RE = re.compile(r"[^a-z0-9-]+")
_SLUG_RUN_DASH_RE = re.compile(r"-+")


def slug_from_path(pdf_path):  # type: (str) -> str
    """从 PDF 文件名推断 kebab-case slug。

    例子：
      /papers/Attention Is All You Need.pdf  -> attention-is-all-you-need
      ./my_paper-v2.PDF                      -> my-paper-v2
      ./ART-ICDE'13.pdf                      -> art-icde-13
    """
    base = os.path.basename(pdf_path)
    stem = re.sub(r"\.[Pp][Dd][Ff]$", "", base)
    slug = stem.lower()
    slug = _SLUG_NON_KEBAB_RE.sub("-", slug)
    slug = _SLUG_RUN_DASH_RE.sub("-", slug).strip("-")
    return slug


def detect_full_overwrite(full_md_path, force):  # type: (str, bool) -> None
    """检测 raw/papers/<slug>.full.md 是否已存在；存在且未 --force-full 时退出非零。

    设计意图（SSOT 引用 MEMORY/gemini-paper-summary-full-mode-design.md §3）：
    full 抽取是"贵读一次"的产物,意外重写会丢下游已经多次引用的 raw——默认拒绝。
    用户显式 --force-full 才允许覆盖,stderr 仍 INFO 提示这次是覆盖。
    """
    if not os.path.isfile(full_md_path):
        return
    if force:
        sys.stderr.write(
            "INFO: {0} 已存在,用户显式 --force-full,覆盖现有 full 抽取。\n".format(
                full_md_path
            )
        )
        return
    sys.stderr.write(
        "ERROR: {0} 已存在;full 抽取默认拒绝覆盖以防丢失下游已经多次引用的 raw。\n"
        "       若确认要覆盖,加 --force-full 显式允许。\n".format(full_md_path)
    )
    sys.exit(1)


def _run_full_mode(args):  # type: (argparse.Namespace) -> int
    """--full 模式独立子流程:产出两份 (quick + full) + raw-compatible layout。

    输入约定:
        args.pdf         -- PDF 路径
        args.output      -- wiki 仓根(下含 raw/)
        args.slug / --slug / 自动从 PDF 文件名推断(见 slug_from_path)
        args.model / args.temperature / args.focus  -- Gemini 调用参数
        args.force_full                              -- 允许覆盖冲突

    写出:
        <wiki_root>/raw/papers/<slug>.quick.md       -- academic 模板产物(含 ![图 N] 引用 + 落 PNG)
        <wiki_root>/raw/papers/<slug>.full.md        -- full 模板产物(自包含,无 PNG 配套)
        <wiki_root>/raw/assets/<slug>/fig-NN.png     -- 仅由 quick 模式产生,full 不写(2026-06-30 第二轮翻面)

    关键决策 SSOT:../../MEMORY/gemini-paper-summary-full-mode-design.md

    2026-06-30 第二轮翻面:full 模式不再落 PNG / 不跑 Stage 2 / 不创建
    raw/assets/<slug>/ 目录。架构/概念图直接 mermaid 画在 markdown 里,
    数据可视化图转 markdown 表格(详见 prompt-template.md full 模板)。quick
    模式 + `--extract-figures` 单跑仍走落 PNG 路径。
    """
    # 必填校验
    if not args.output:
        sys.stderr.write(
            "ERROR: --full 模式必须配合 --output 使用(--output 视为 wiki 仓根,\n"
            "       产物写到 <wiki_root>/raw/papers/<slug>.quick.md + .full.md;\n"
            "       full 模式不落 PNG,quick 模式或 --extract-figures 单跑仍会落图)。\n"
        )
        sys.exit(2)

    # 2026-06-30 第二轮翻面:--refine-figures / --thumbnail 在 full 模式是
    # 哑参数(quick 模式或 --extract-figures 才生效),INFO 提示而非 WARN。
    # 不阻断用户使用,full 模式不消费这些 flag。
    if args.refine_figures or args.thumbnail:
        sys.stderr.write(
            "INFO: --full 模式已不再落 PNG(2026-06-30),--refine-figures / --thumbnail "
            "在 full 模式是哑参数;仅 quick 模式或 --extract-figures 单跑生效。\n"
        )

    wiki_root = os.path.abspath(args.output)
    raw_root = os.path.join(wiki_root, "raw")
    papers_dir = os.path.join(raw_root, "papers")

    # slug 推断(--slug 优先,否则从 PDF 文件名)
    slug = args.slug if args.slug else slug_from_path(args.pdf)
    if not slug:
        sys.stderr.write(
            "ERROR: 无法推断论文 slug(从 PDF 文件名 '{0}' 得到空字符串)。\n"
            "       用 --slug <kebab-case-slug> 显式指定。\n".format(args.pdf)
        )
        sys.exit(2)

    os.makedirs(papers_dir, exist_ok=True)
    # 2026-06-30 第二轮翻面:full 模式不再创建 raw/assets/<slug>/ 目录,
    # 仅在 papers_dir 写两份 .md

    quick_md_path = os.path.join(papers_dir, "{0}.quick.md".format(slug))
    full_md_path = os.path.join(papers_dir, "{0}.full.md".format(slug))

    # 冲突检测(SSOT §3):full 抽取默认拒绝覆盖;quick 也走同规则
    detect_full_overwrite(full_md_path, args.force_full)
    if os.path.isfile(quick_md_path) and not args.force_full:
        sys.stderr.write(
            "ERROR: {0} 已存在;full 模式默认拒绝覆盖 quick 产物以保持 raw 端稳定。\n"
            "       若确认要覆盖,加 --force-full 显式允许。\n".format(quick_md_path)
        )
        sys.exit(1)

    # 1) 校验输入(隐式 GEMINI_API_KEY + PDF 完整性)
    model, pdf_bytes, focus = validate_inputs(args)

    # 2) 调用 Gemini 两次:先 academic(quick) 再 full
    sys.stderr.write(
        "INFO: --full 模式开始 (slug={slug});产物落 raw-compatible layout ({wiki_root}/raw/)\n".format(
            slug=slug, wiki_root=wiki_root
        )
    )
    sys.stderr.write(
        "INFO: 第 1 次调用 Gemini (academic 模板 = quick summary)\n"
    )
    quick_prompt = build_prompt(focus, template="academic")
    quick_md = call_gemini(model, pdf_bytes, quick_prompt, args.temperature)

    sys.stderr.write(
        f"INFO: 第 2 次调用 Gemini (full 模板 = PDF→Markdown 全量转写, max_output_tokens={FULL_MAX_OUTPUT_TOKENS})\n"
    )
    full_prompt = build_prompt(focus, template="full")
    # max_output_tokens=65536(SSOT: FULL_MAX_OUTPUT_TOKENS 模块常量),避免
    # 撞顶截断尾部章节(决策背景见 prompt-template.md ## 全文级抽取模板
    # 头部 2026-06-30 加固的"完整性 > 篇幅"block)。
    full_md = call_gemini(
        model, pdf_bytes, full_prompt, args.temperature,
        max_output_tokens=FULL_MAX_OUTPUT_TOKENS,
    )

    # 3) 2026-06-30 第二轮翻面:full 模式不再落 PNG / 不跑 Stage 2 / 不创建
    #    raw/assets/<slug>/ 目录。full.md 自包含(架构图直接 mermaid 画在
    #    markdown 里,数据图转表格,装饰图省略)。--extract-figures 单跑仍
    #    落 PNG,服务于人类用户。
    #    移除的函数调用(parse_figure_refs / render_pages_for_gemini /
    #    call_gemini_for_visual_bbox / insert_caption_after_figure /
    #    render_figures_to_pngs / embed_figure_refs)由 quick 模式与
    #    --extract-figures 单跑消费。

    # 4) 写两份 .md 到 raw/papers/
    with open(quick_md_path, "w", encoding="utf-8") as f:
        f.write(quick_md)
        if not quick_md.endswith("\n"):
            f.write("\n")
    sys.stderr.write(
        "OK: quick summary 已写入 {0} ({1} 字符, 模型 {2})\n".format(
            quick_md_path, len(quick_md), model
        )
    )
    with open(full_md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
        if not full_md.endswith("\n"):
            f.write("\n")
    sys.stderr.write(
        "OK: full 抽取已写入 {0} ({1} 字符, 模型 {2})\n".format(
            full_md_path, len(full_md), model
        )
    )

    # 5.5) full 模式内容完整性自检(2026-06-30 加固):6 H2 + ≥5 ### Section,
    # 防止模型撞 token 截断或偷懒。WARN/FAIL 写 stderr,不阻塞退出(同
    # self_check_figures 模式)。
    try:
        check_result = self_check_full_content(full_md)
        sys.stderr.write("INFO: " + check_result["report"] + "\n")
        for w in check_result.get("warnings", []):
            sys.stderr.write("WARN: " + w + "\n")
        for fl in check_result.get("failures", []):
            sys.stderr.write("FAIL: " + fl + "\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            f"WARN: self_check_full_content 异常: {e}(自检未跑全,不影响主流程)\n"
        )

    return 0


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------


def main(argv=None):  # type: (Optional[list]) -> int
    args = parse_args(argv)

    # ---- 解析 doc_type（--type 显式 / --auto-detect 自动 / 互斥校验）----
    if args.type is None and not args.auto_detect:
        sys.stderr.write(
            "ERROR: 必须传 --type 或 --auto-detect 二者之一。\n"
            "       --type 取值: paper / manual / whitepaper / book\n"
            "       agent 在调用前应反问用户确定类型（见 SKILL.md §工作流 §A）。\n"
        )
        return 2
    if args.type is not None and args.auto_detect:
        sys.stderr.write(
            "ERROR: --type 与 --auto-detect 互斥，只能传一个。\n"
            "       显式知道类型用 --type；不确定用 --auto-detect（脚本会用 PDF 元数据 + Gemini 验证）。\n"
        )
        return 2

    doc_type = args.type
    if args.auto_detect:
        try:
            from auto_detect import detect_doc_type  # type: ignore
        except ImportError:
            sys.stderr.write(
                "ERROR: --auto-detect 需要 scripts/auto_detect.py，但导入失败。\n"
                "       请确认 gemini-pdf-summary/scripts/auto_detect.py 存在。\n"
            )
            return 2
        try:
            detected = detect_doc_type(args.pdf)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(
                f"ERROR: auto-detect 失败: {e}\n"
                f"       请显式传 --type {VALID_TYPES} 中的一个。\n"
            )
            return 3
        if detected not in VALID_TYPES:
            sys.stderr.write(
                f"ERROR: auto-detect 返回未知类型 {detected!r}；合法值: {VALID_TYPES}\n"
                f"       请显式传 --type <paper|manual|whitepaper|book>。\n"
            )
            return 3
        sys.stderr.write(f"INFO: auto-detect 判定 --type {detected}\n")
        doc_type = detected
        args.type = detected  # 同步回 args，后续 main 分支用 args.type

    # ---- 类型相关的隐式约束（无需用户传 flag）----
    # - book 仅支持 full 模式：自动打开 args.full
    # - manual / whitepaper 不抽原始图：自动打开 args.no_figures（且忽略 --extract-figures）
    # - paper 不变（保留原有 quick + full + --extract-figures 行为）
    if doc_type == "book" and not args.full:
        sys.stderr.write("INFO: book 类型仅支持 full 模式，自动启用 --full。\n")
        args.full = True
    if doc_type in ("manual", "whitepaper", "book") and not args.no_figures:
        sys.stderr.write(
            f"INFO: {doc_type} 类型不抽原始 PDF 图（产物给 LLM 消费，"
            f"概念用 mermaid / 表格 / ASCII 在 markdown 内直接画）。自动启用 --no-figures。\n"
        )
        args.no_figures = True

    # --full 模式走独立分支;设计决策 SSOT 见
    # ../../MEMORY/gemini-paper-summary-full-mode-design.md(D1 / D2 / D3 / D4)
    if args.full:
        return _run_full_mode(args)

    model, pdf_bytes, focus = validate_inputs(args)
    # 非 paper 类型按 full 模式加载 prompt（自包含风格）；paper 走 quick（默认）。
    # book 已在前面被自动设为 full；manual / whitepaper 单模式，无 quick/full 区分。
    prompt_mode = "full" if (args.full or doc_type in ("manual", "whitepaper", "book")) else "quick"
    prompt = build_prompt(focus, doc_type=doc_type, mode=prompt_mode)
    summary_md = call_gemini(
        model, pdf_bytes, prompt, args.temperature,
        max_output_tokens=(FULL_MAX_OUTPUT_TOKENS if prompt_mode == "full" else None),
    )

    # ---- quick 模式默认带图（2026-07-01）：给人看，必须带高质量图 ----
    # Stage 2（--refine-figures 默认 True）用 Gemini 视觉定位精修 bbox + 完整 caption，
    # 保证图质量（代价：每张引用页多一次 Gemini 调用 + ~5-15s）。
    # --no-figures 关闭；--extract-figures 为向后兼容冗余 flag（传了等价默认）。
    if args.extract_figures:
        sys.stderr.write(
            "INFO: --extract-figures 是向后兼容 flag；quick 模式默认就带图，无需显式传。\n"
        )
    want_figures = not args.no_figures
    refs = parse_figure_refs(summary_md)
    figures_exported = False
    figures_dir_abs = ""

    if refs and want_figures and _HAS_PYMUPDF and args.output:
        # === 正常产图路径（Stage 2 默认开保质量）===
        out_dir = args.output
        figures_dir_abs = os.path.join(out_dir, "figures")
        visual_bbox_map = {}
        # Stage 2 (可选): 用 Gemini 看图视觉定位 + 读完整 caption + 过滤装饰图
        if args.refine_figures:
            if not os.environ.get("GEMINI_API_KEY"):
                sys.stderr.write("WARN: --refine-figures 需要 GEMINI_API_KEY,未设置;跳过 Stage 2。\n")
            else:
                page_to_png = render_pages_for_gemini(args.pdf, refs, dpi_scale=args.refine_dpi)
                if page_to_png:
                    visual_bbox_map = call_gemini_for_visual_bbox(args.pdf, page_to_png, model, args.temperature)
                    # caption 写到 image alt（v3.2）；Stage 2 读到的完整 caption 覆盖 Stage 1 估算
                    summary_md = insert_caption_after_figure(summary_md, visual_bbox_map)
        os.makedirs(out_dir, exist_ok=True)
        ref_to_fullpath, ref_to_thumbpath, ref_to_dim = render_figures_to_pngs(
            args.pdf,
            refs,
            figures_dir_abs,
            dpi_scale=args.figure_dpi,
            figure_format=args.figure_format,
            figure_quality=args.figure_quality,
            max_width=args.max_width,
            max_size_kb=args.max_size_kb,
            make_thumbnail=args.thumbnail,
            thumbnail_width=args.thumbnail_width,
            visual_bbox_map=visual_bbox_map,
        )
        # 选择 Markdown 引用源：缩略图模式用 thumb，否则用 full
        if args.thumbnail and ref_to_thumbpath:
            ref_to_relpath = ref_to_thumbpath
            ref_to_full_for_wrap = ref_to_fullpath  # embed_figure_refs 内部反向索引
        else:
            ref_to_relpath = ref_to_fullpath
            ref_to_full_for_wrap = None
        summary_md = embed_figure_refs(
            summary_md, ref_to_relpath, ref_to_full_for_wrap, ref_to_dim=ref_to_dim
        )
        figures_exported = True
        refine_note = f", Stage 2 定位 {len(visual_bbox_map)} 个" if visual_bbox_map else ""
        sys.stderr.write(
            f"OK: 已导出 {len(ref_to_fullpath)} 张图到 {figures_dir_abs}（倍率 {args.figure_dpi}，"
            f"{args.figure_dpi * 72:.0f} DPI，格式 {args.figure_format}"
            f"{' + 缩略图' if args.thumbnail else ''}{refine_note}）\n"
        )
    elif refs:
        # === 边界：有图引用但不导出图 → 清破图引用，按原因打 WARN/INFO ===
        summary_md = strip_pdf_figure_refs(summary_md)
        if args.no_figures:
            sys.stderr.write("INFO: --no-figures 已跳过图导出，PDF 图引用已清理成纯文本。\n")
        elif not _HAS_PYMUPDF:
            sys.stderr.write(
                "WARN: quick 默认带图需要 pymupdf，未安装 → 本次未导出图，PDF 图引用已清理。\n"
                "      装后重跑: pip install --user --break-system-packages pymupdf（或 --no-figures 显式跳过）。\n"
            )
        elif not args.output:
            sys.stderr.write(
                "WARN: stdout 模式无法导出图，PDF 图引用已清理。要看图请加 --output <dir>。\n"
            )
    # refs 为空（纯理论论文，Gemini 未写图引用）：无需导出图，也不打日志

    # ---- 写文件或打印 stdout ----
    if args.output:
        if figures_exported:
            # 带图模式：--output 是目录，.md 固定写在 summary.md
            out_path = os.path.join(args.output, "summary.md")
        else:
            out_path = args.output
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(summary_md)
            if not summary_md.endswith("\n"):
                f.write("\n")
        sys.stderr.write(f"OK: 总结已写入 {out_path}（模型 {model}，PDF {args.pdf}，{len(summary_md)} 字符）\n")
    else:
        sys.stdout.write(summary_md)
        if not summary_md.endswith("\n"):
            sys.stdout.write("\n")

    # ---- 生成后自检(2026-06-21):图片完整性 + 边界破坏 ----
    # 阶段 1/3/4 必跑(本地);阶段 2(outline attachment)只在环境变量指定时跑
    figures_dir = figures_dir_abs  # 带图时是 figures/ 绝对路径；否则空串（自检跳过本地 PNG 校验）
    outline_endpoint = os.environ.get("OUTLINE_ENDPOINT", "")
    outline_api_key = os.environ.get("OUTLINE_API_KEY", "")
    try:
        check_result = self_check_figures(
            summary_md,
            figures_dir,
            outline_check=bool(outline_endpoint and outline_api_key),
            outline_endpoint=outline_endpoint or None,
            outline_api_key=outline_api_key or None,
        )
        # 报告到 stderr(不阻塞)
        sys.stderr.write("INFO: " + str(check_result["report"]) + "\n")
        for w in check_result.get("warnings", []):
            sys.stderr.write("WARN: " + w + "\n")
        for fl in check_result.get("failures", []):
            sys.stderr.write("FAIL: " + fl + "\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"WARN: self_check_figures 异常: {e}(自检未跑全,不影响主流程)\n")

    return 0


# -----------------------------------------------------------------------------
# 自检:图片完整性与边界(2026-06-21)
# -----------------------------------------------------------------------------


def self_check_figures(md_text, figures_dir, outline_check=False, outline_endpoint=None, outline_api_key=None):  # type: (str, str, bool, Optional[str], Optional[str]) -> Dict[str, object]
    """生成后自检:校验 doc body 里的图片引用是否完整、本地 PNG 尺寸是否与 markdown title 一致、可选 outline attachment 二进制完整性。

    Args:
        md_text: 已生成的 summary.md 全文(本地产物)
        figures_dir: 本地 figures 目录绝对路径(用于阶段 3/4 校验本地 PNG 尺寸)
        outline_check: 是否额外做 outline attachment 二进制校验(阶段 1/2)
        outline_endpoint: outline-wiki endpoint, 例 https://myoutline.ddnsto.com
        outline_api_key: outline API key(Authorization: Bearer ...)

    Returns:
        {
          "ok": bool,                # True = 0 失败;False = 至少 1 项失败
          "warnings": [str, ...],    # 警告项(尺寸不匹配 / 缺本地 PNG 等)
          "failures": [str, ...],    # 失败项(失效引用 / 0 字节 attachment / 缺 markdown 引用)
          "report": str,             # 单行摘要,例 "Self-check: 3/3 OK"
        }
    """
    import re  # 局部 import,避免污染模块级命名空间

    result = {"ok": True, "warnings": [], "failures": [], "report": ""}  # type: Dict[str, object]

    # ---- 阶段 1: 解析 doc body 里的图片引用 ----
    # 形如: ![alt](/api/attachments.redirect?id=<id> "=WxH")  或  ![alt](figures/figure-pX-fY.png "=WxH")
    md_refs = re.findall(
        r'!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?:\s+"(?P<title>[^"]*)")?\)',
        md_text,
    )
    # (url, title) 列表
    md_pairs = [(m[1], m[2] or "") for m in md_refs]

    # outline attachment ID 集合
    outline_ref_ids = set()
    for url, _ in md_pairs:
        m = re.search(r"attachments\.redirect\?id=([0-9a-f-]{36})", url)
        if m:
            outline_ref_ids.add(m.group(1))

    # 本地相对路径列表(用于阶段 4 校验)
    local_paths = []
    for url, _ in md_pairs:
        if url.startswith("http") or url.startswith("/api/"):
            continue
        # url 形如 "figures/figure-p4-f5.png"
        local_paths.append(url)

    # ---- 阶段 2: outline attachment 完整性(可选) ----
    if outline_check and outline_endpoint and outline_api_key and outline_ref_ids:
        # 2a) attachments.list 拉 in-use ID 集合
        try:
            list_resp = _outline_api_request(
                outline_endpoint,
                outline_api_key,
                "attachments.list",
                {"limit": 100},
            )
            existing_ids = set()
            for a in list_resp.get("data", []):
                if a.get("id"):
                    existing_ids.add(a["id"])
            # 差集 = 失效引用
            missing = outline_ref_ids - existing_ids
            for mid in sorted(missing):
                result["failures"].append(f"outline attachment 失效引用: id={mid} 在 attachments.list 不存在")
        except Exception as e:  # noqa: BLE001
            result["warnings"].append(f"attachments.list 调用失败: {e}")

        # 2b) 每个 in-use attachment HEAD 校验
        for aid in sorted(outline_ref_ids):
            try:
                status, ctype, size = _outline_attachment_head(outline_endpoint, outline_api_key, aid)
                if status != 200:
                    result["failures"].append(f"attachment {aid} HEAD 状态码 {status}(非 200)")
                elif not ctype or not ctype.startswith("image/"):
                    result["failures"].append(f"attachment {aid} content-type 异常: {ctype!r}(非 image/...)")
                elif size <= 0:
                    result["failures"].append(f"attachment {aid} size=0(0 字节破图)")
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"attachment {aid} HEAD 失败: {e}")

    # ---- 阶段 3: 本地 PNG 存在性 ----
    if not _HAS_PYMUPDF:
        if local_paths:
            result["warnings"].append("本地 figures 校验需要 pymupdf,但未安装;pip install -U pymupdf 后重跑")
    elif figures_dir and os.path.isdir(figures_dir):
        for rel in local_paths:
            abs_path = os.path.join(figures_dir, os.path.basename(rel))
            if not os.path.isfile(abs_path):
                result["failures"].append(f"本地 PNG 缺失: {abs_path}")
    elif local_paths:
        result["warnings"].append(
            f"本地 figures 目录不存在: {figures_dir}(doc 引用了 {len(local_paths)} 张本地图,无法做尺寸校验)"
        )

    # ---- 阶段 4: 本地 PNG 尺寸 vs markdown title "=WxH" ----
    if _HAS_PYMUPDF and figures_dir and os.path.isdir(figures_dir):
        import fitz  # type: ignore  # pymupdf

        for rel, title in [(p[0], p[1]) for p in zip(local_paths, [t for _, t in md_pairs])]:
            if not title:
                continue
            # title 形如 "=506x548" 或 "=506X548"
            m = re.match(r"=(\d+)[xX](\d+)", title)
            if not m:
                continue
            claimed_w, claimed_h = int(m.group(1)), int(m.group(2))
            abs_path = os.path.join(figures_dir, os.path.basename(rel))
            if not os.path.isfile(abs_path):
                continue  # 阶段 3 已报告
            try:
                # 与 embed_figure_refs 写入 title 时的口径一致：直接读 PNG 像素数
                # （不能用 fitz.open(...).page.rect.width——pymupdf 默认按 96 DPI 把
                # 像素数换算成 PDF points，结果会比真实像素数小 25% 触发误报）
                pix = fitz.Pixmap(abs_path)
                actual_w, actual_h = pix.width, pix.height
                pix = None
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(f"本地 PNG 读尺寸失败 {abs_path}: {e}")
                continue
            # 差 ≥ 5% 视为不匹配
            if claimed_w <= 0 or claimed_h <= 0:
                continue
            dw = abs(actual_w - claimed_w) / float(claimed_w)
            dh = abs(actual_h - claimed_h) / float(claimed_h)
            if dw >= 0.05 or dh >= 0.05:
                result["warnings"].append(
                    f"本地 PNG 尺寸与 title 不一致: {abs_path} 实际 {actual_w}x{actual_h} "
                    f"vs 标题 {claimed_w}x{claimed_h} (差 {dw * 100:.1f}% / {dh * 100:.1f}%)"
                )

    # ---- 收尾 ----
    if result["failures"]:
        result["ok"] = False
    summary_line = (
        f"Self-check: {len(outline_ref_ids) + len(local_paths) - len(result['failures'])} ok, "
        f"{len(result['warnings'])} warnings, {len(result['failures'])} failures"
    )
    result["report"] = summary_line
    return result


def self_check_full_content(
    md_text,
    min_h2=3,
    min_sections=5,
    placeholder_ratio_warn=0.5,
    min_chars=8000,
):
    # type: (str, int, int, float, int) -> Dict[str, object]
    """full 模式产物内容完整性自检(2026-06-30 重新定位后)。

    与 self_check_figures 同款 return shape({ok, warnings, failures, report}),
    WARN/FAIL 写 stderr、不阻塞退出。

    校验项(2026-06-30 重新定位 — 不再查 6 H2 骨架,改为按"PDF 章节保真度"校验):

    1. **H2 章节保真度**:`^## ` 行数 ≥ min_h2(默认 3)。意味着 PDF 章节未被
       保真展开时 FAIL(stderr 不阻塞)。**不**再限定具体 H2 名称白名单——
       full 模式现在按 PDF 原生章节顺序转写,章节名因论文而异。
    2. **`### Section X.Y` 数量** ≥ min_sections(默认 5,按 eval/evals.json
       契约下限)。算法 / 系统类论文有 ≥ 5 个 `Section X.Y` 子标题是基本密度。
    3. **Definition / Theorem / Lemma / Algorithm 标注数**(关键保真指标):
       4 类任一出现次数合计。若 0 次 WARN(意味着原文无标 *或者* 模型未保真);
       对算法 / 数学类论文 ≥ 1 是基本密度。
    4. **`$$...$$` 公式 block 数** ≥ 1。若 0 次 WARN(原文无独立公式或模型未
       保真 LaTeX 转写)。
    5. **字符下限** ≥ min_chars(默认 8000)。过短意味着模型偷懒或撞 token。
    6. **"原文未明确"占位比例** > placeholder_ratio_warn(默认 50%) 时 WARN,
       防止模型偷懒("该小节内容少" 不应该成为大量占位的理由)。

    Args:
        md_text: 已生成的 full.md 全文(本地产物)
        min_h2: 最少 H2 章节数(默认 3)
        min_sections: 最少 `### Section X.Y` 数(默认 5)
        placeholder_ratio_warn: "原文未明确"占位 / ### Section 比例阈值(默认 0.5)
        min_chars: 字符下限(默认 8000)

    Returns:
        {
          "ok": bool,                # True = 0 failures;False = 至少 1 项失败
          "warnings": [str, ...],
          "failures": [str, ...],
          "report": str,             # 单行摘要,例
                                       # "Content self-check: H2=12, ###Section=18,
                                       #  Def+Thm+Lem+Alg=4, $$block=3, 0w 0f"
        }
    """
    import re  # 局部 import,避免污染模块级命名空间

    result = {"ok": True, "warnings": [], "failures": [], "report": ""}  # type: Dict[str, object]

    # ---- 检查 1:H2 章节保真度(2026-06-30:不查具体名称,只保底数量) ----
    h2_re = re.compile(r"^##\s+", re.MULTILINE)
    n_h2 = len(h2_re.findall(md_text))
    if n_h2 < min_h2:
        result["failures"].append(
            f"full.md H2 章节数 {n_h2} < {min_h2},PDF 章节未被保真展开"
        )
        result["ok"] = False

    # ---- 检查 2:### Section X.Y 数量 ----
    # 匹配 `### Section 3` / `### Section 3.1` / `### Section 3.1.2` 等
    section_re = re.compile(
        r"^###\s+Section\s+\d+(?:\.\d+)*",
        re.MULTILINE | re.IGNORECASE,
    )
    section_matches = list(section_re.finditer(md_text))
    n_sections = len(section_matches)
    if n_sections < min_sections:
        result["warnings"].append(
            f"full.md ### Section X.Y 数量 {n_sections} < {min_sections}(evals.json 契约下限)"
        )

    # ---- 检查 3:Definition / Theorem / Lemma / Algorithm 标注数 ----
    # 按 "**Label N.** ..." 模式统计 4 类标注(原文若有,模型必须保真标注)
    label_re = re.compile(
        r"^\s*\*\*(Definition|Theorem|Lemma|Corollary|Algorithm)\s+\d",
        re.MULTILINE,
    )
    n_labels = len(label_re.findall(md_text))
    if n_labels == 0:
        result["warnings"].append(
            "full.md 未发现 Definition/Theorem/Lemma/Corollary/Algorithm 标注"
            "(原文无此类标注 或 模型未保真)"
        )

    # ---- 检查 4:`$$...$$` 公式 block 数 ----
    block_re = re.compile(r"\$\$.+?\$\$", re.DOTALL)
    n_blocks = len(block_re.findall(md_text))
    if n_blocks == 0:
        result["warnings"].append(
            "full.md 未发现 $$...$$ 公式 block(原文无独立公式 或 模型未保真 LaTeX 转写)"
        )

    # ---- 检查 5:字符下限 ----
    n_chars = len(md_text)
    if n_chars < min_chars:
        result["warnings"].append(
            f"full.md 字符数 {n_chars} < {min_chars},可能偷懒或撞 token 上限"
        )

    # ---- 检查 6:"原文未明确" 占位比例 ----
    placeholder_count = md_text.count("原文未明确")
    if n_sections > 0:
        ratio = placeholder_count / float(n_sections)
        if ratio > placeholder_ratio_warn:
            result["warnings"].append(
                f"full.md 含 {placeholder_count} 处'原文未明确'占位 / {n_sections} 个 ### Section = {ratio:.0%},"
                f"超过 {placeholder_ratio_warn:.0%} 阈值,可能存在偷懒"
            )

    # ---- 收尾 ----
    summary_line = (
        f"Content self-check: H2={n_h2}, ###Section={n_sections}, "
        f"Def+Thm+Lem+Alg={n_labels}, $$block={n_blocks}, "
        f"chars={n_chars}, {len(result['warnings'])}w {len(result['failures'])}f"
    )
    result["report"] = summary_line
    return result


def _outline_api_request(endpoint, api_key, path, payload):  # type: (str, str, str, dict) -> dict
    """outline-wiki REST API POST 调用,返 data 字段。失败抛 RuntimeError。"""
    import json as _json
    import urllib.request

    url = endpoint.rstrip("/") + "/api/" + path
    req = urllib.request.Request(
        url,
        data=_json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    d = _json.loads(body)
    if not d.get("ok"):
        raise RuntimeError("outline API {} 失败: {}".format(path, d.get("error") or d))
    return d


def _outline_attachment_head(endpoint, api_key, attachment_id):  # type: (str, str, str) -> Tuple[int, Optional[str], int]
    """attachments.redirect HEAD 校验,返 (status, content_type, size)。"""
    import urllib.request

    url = endpoint.rstrip("/") + "/api/attachments.redirect?id=" + attachment_id
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + api_key},
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            ctype = resp.headers.get("Content-Type")
            cl = resp.headers.get("Content-Length")
            size = int(cl) if cl and cl.isdigit() else 0
            return (resp.status, ctype, size)
    except urllib.error.HTTPError as e:
        return (e.code, e.headers.get("Content-Type") if e.headers else None, 0)


if __name__ == "__main__":
    sys.exit(main())

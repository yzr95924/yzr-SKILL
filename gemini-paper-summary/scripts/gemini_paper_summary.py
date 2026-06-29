#!/usr/bin/env python3
"""
gemini_paper_summary: 用 Gemini 多模态读 PDF 论文并按 6+3 段学术结构化模板
输出中文 Markdown 总结。

本脚本是 gemini-paper-summary skill 的核心可执行入口。
它也可以被 agent 在 bash 命令行里直接调用。

依赖：
    pip install -U google-genai
    export GEMINI_API_KEY="你的 key"

Python 兼容：3.6+（与 yzr-skill-creator 脚本保持一致；避开 PEP 604/585 语法）。

使用示例：
    python3 gemini_paper_summary.py --pdf paper.pdf
    python3 gemini_paper_summary.py --pdf paper.pdf --output paper.summary.md
    python3 gemini_paper_summary.py --pdf paper.pdf --model gemini-3.1-pro-preview
    python3 gemini_paper_summary.py --pdf paper.pdf --focus "重点看数学推导"
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
# 无自动 fallback 链：503/429 等高并发 / 限流错误**直接抛**给用户，不静默降级。
# 理由：不同模型的输出质量差异显著，silent fallback 容易引入质量问题（漏掉章节、
# alt 字段偏差、表格行数错位等），用户感知不到是模型降级导致的——只看到结果怪。
# 用户如要换模型，用 `--model gemini-3.1-flash-lite` 显式指定。
MAX_PDF_BYTES_INLINE = 20 * 1024 * 1024  # 20 MB 走 inline Part.from_bytes；更大走 File API

# 默认 prompt 从 assets/prompt-template.md 的 `## 默认模板（academic）` 段
# 读取，让 markdown 模板成为单一事实来源（SSOT）——避免脚本 / md 双份维护。
#
# 模板 markdown 内的 prompt 用 `````text` 4-backtick fence 包裹（因为 prompt
# 内部要嵌套 markdown / mermaid 代码块示例），本函数用正则抽取该 fence 内容。
#
# 任何模板变更只需要改 assets/prompt-template.md，本脚本不再持有 prompt 文本。
DEFAULT_TEMPLATE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "assets", "prompt-template.md")
)

# 抽取 `````text ... `````（4-backtick）包裹的默认模板正文。允许前置空白。
_DEFAULT_PROMPT_FENCE_RE = re.compile(
    r"^````text\s*\n(.*?)^````\s*$",
    re.MULTILINE | re.DOTALL,
)


def _load_default_prompt():
    # type: () -> str
    """从 assets/prompt-template.md 的 `## 默认模板（academic）` 段读出 prompt 正文。

    失败时（文件缺失 / 段不存在 / 没有 text fence）立即报错退出——这是开发期
    应该立刻发现的问题，不允许静默回退到老模板。"""
    if not os.path.isfile(DEFAULT_TEMPLATE_PATH):
        sys.stderr.write(
            f"ERROR: 找不到 prompt 模板文件: {DEFAULT_TEMPLATE_PATH}\n"
            "       仓库结构破坏，请检查 gemini-paper-summary/assets/ 目录。\n"
        )
        sys.exit(2)

    with open(DEFAULT_TEMPLATE_PATH, encoding="utf-8") as f:
        md = f.read()

    # 定位 `## 默认模板（academic）` 标题位置，section 起点从这里之后开始。
    # 注意：不能用 `(?=^##\s|\Z)` 之类前瞻去截取 section 末尾——prompt 正文里
    # 也包含 `## 目标场景选择` / `## 团队背景介绍` 之类的独立行，会被误判。
    # 因此直接找标题之后的第一个 `````text` fence 起止，fence 区间就是 prompt 正文。
    head_match = re.search(
        r"^##\s+默认模板\s*[（(]academic[)）]\s*$",
        md,
        re.MULTILINE,
    )
    if not head_match:
        sys.stderr.write(
            f"ERROR: {DEFAULT_TEMPLATE_PATH} 里找不到 '## 默认模板（academic）' 段。\n"
            "       模板文件结构破坏，请补回该小节。\n"
        )
        sys.exit(2)

    after_head = md[head_match.end() :]
    fence_match = _DEFAULT_PROMPT_FENCE_RE.search(after_head)
    if not fence_match:
        sys.stderr.write(
            f"ERROR: {DEFAULT_TEMPLATE_PATH} 的默认模板段里找不到 `````text` fence。\n"
            "       请确认模板正文仍由 4-backtick fence 包裹。\n"
        )
        sys.exit(2)

    return fence_match.group(1).rstrip() + "\n"


DEFAULT_PROMPT = _load_default_prompt()


def _load_full_prompt():
    # type: () -> str
    """从 assets/prompt-template.md 的 `## 全文级抽取模板（full）` 段读出 prompt 正文。

    失败时（文件缺失 / 段不存在 / 没有 text fence）立即报错退出——与
    `_load_default_prompt` 同样的态度：开发期问题不允许静默回退。

    设计决策 SSOT: 见
    ../../MEMORY/gemini-paper-summary-full-mode-design.md §4(D3 沿用同 H2 骨架)。
    """
    if not os.path.isfile(DEFAULT_TEMPLATE_PATH):
        sys.stderr.write(
            "ERROR: 找不到 prompt 模板文件: {0}\n".format(DEFAULT_TEMPLATE_PATH)
        )
        sys.exit(2)

    with open(DEFAULT_TEMPLATE_PATH, encoding="utf-8") as f:
        md = f.read()

    head_match = re.search(
        r"^##\s+全文级抽取模板[（(]full[)）]\s*$",
        md,
        re.MULTILINE,
    )
    if not head_match:
        sys.stderr.write(
            "ERROR: {0} 里找不到 '## 全文级抽取模板（full）' 段。\n"
            "       模板文件结构破坏，请补回该小节。\n".format(DEFAULT_TEMPLATE_PATH)
        )
        sys.exit(2)

    after_head = md[head_match.end() :]
    fence_match = _DEFAULT_PROMPT_FENCE_RE.search(after_head)
    if not fence_match:
        sys.stderr.write(
            "ERROR: {0} 的 full 模板段里找不到 `````text` fence。\n"
            "       请确认模板正文仍由 4-backtick fence 包裹。\n".format(
                DEFAULT_TEMPLATE_PATH
            )
        )
        sys.exit(2)

    return fence_match.group(1).rstrip() + "\n"


FULL_PROMPT = _load_full_prompt()


FOCUS_INJECTION = (
    "\n\n[额外关注点]\n"
    '用户在调用时指定了以下关注点，请在"方法 / 关键结果"小节中相应侧重，'
    '并在"启发 / 追问"小节展开 2-3 个延伸思考：\n\n{focus}\n'
)

# full 模板的焦点注入片段（在全文级抽取上下文里，`启发 / 追问` 段不存在——
# 用户的关注点以"在 ## 方法设计 / ## 代表性实验结果 段下加关注点子段"形式插入）
FOCUS_INJECTION_FULL = (
    "\n\n[额外关注点]\n"
    "用户在调用时指定了以下关注点，请在 **方法设计 / 代表性实验结果 / 业务启示 & 价值** "
    "章节内以子段形式追加原文级细节关注(例如 `### 用户关注点: <focus>` 子节),"
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
):
    # type: (str, list, str, float, str, int, int, int, bool, int, dict) -> tuple
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

    返回 (full_map, thumb_map, dim_map)：
      - full_map: {(page, fig_num): "figures/figure-pX-fY.<ext>"}
      - thumb_map: {(page, fig_num): "figures/figure-pX-fY.thumb.<ext>"}（无缩略图时为空）
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
                full_name = f"figure-p{p}-f{f}.{ext_map[actual_fmt]}"
                full_path = os.path.join(out_dir, full_name)
                fmt_used, qual_used, attempts, size_kb = _save_pixmap_with_constraints(
                    pix=pix,
                    path=full_path,
                    format_ext=actual_fmt,
                    base_quality=figure_quality,
                    max_size_kb=max_size_kb,
                )
                # 用 fmt_used 重算最终文件名（覆盖降级的情况）
                final_full_name = f"figure-p{p}-f{f}.{ext_map[fmt_used]}"
                full_result[key] = "figures/" + final_full_name
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
                    thumb_name = f"{final_base}.thumb{os.path.splitext(final_full_name)[1]}"
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
                    thumb_result[key] = "figures/" + thumb_name
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


def _call_gemini_with_retry(client, model, png_bytes, prompt, temperature, page_num, max_attempts=3):
    # type: (object, str, bytes, str, float, int, int) -> object
    """Stage 2 单页 Gemini 调用,带临时错误重试。

    重试策略:
    - 最多 max_attempts 次(默认 3)
    - 临时错误 (5xx / 429) 退避 2s, 4s 后重试
    - 永久错误 (400/401/403/404) 直接抛出(不重试)
    - 其他异常也走重试(网络抖动等)

    返回 response 对象;最终失败抛 RuntimeError。"""
    import time  # 局部 import,避免顶层 import 副作用

    # google.genai.errors.APIError 子类都有 status_code 属性
    last_err = None
    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_json_schema=VISUAL_BBOX_SCHEMA,
                ),
            )
            return response
        except Exception as e:
            last_err = e
            status = getattr(e, "status_code", None) or getattr(e, "code", None)
            # 永久错误:直接抛(由外层 catch 报 WARN)
            if status is not None and status in {400, 401, 403, 404}:
                raise
            # 临时错误或无 status_code:重试
            if attempt + 1 < max_attempts:
                backoff = 2 ** (attempt + 1)  # 2s, 4s
                sys.stderr.write(
                    f"INFO: Stage 2 第 {page_num} 页 第 {attempt + 1}/{max_attempts} 次失败"
                    f"({type(e).__name__}: {e}),{backoff}s 后重试...\n"
                )
                time.sleep(backoff)
                continue
            # 已到 max_attempts,跑完重试
            break
    raise RuntimeError(f"Stage 2 Gemini 调用 {max_attempts} 次仍失败: {type(last_err).__name__}: {last_err}")


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
THUMB_IMG_RE = re.compile(r"(!\[[^\]]*\])\((figures/figure-[^\)]+\.thumb\.[a-z]+)\)")


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

    # === 失败图行处理 ===
    # 先做替换,把 `![...](PDF p.X fig.N ...)` 整行删除
    lines = md_text.split("\n")
    new_lines = []
    fig_ref_line_re = re.compile(r"!\[.*?\]\(PDF p\.\d+\s+fig\.\d+")
    for line in lines:
        if fig_ref_line_re.search(line):
            # 检查是否有失败的 (p, f) 在该行
            line_failed = False
            for m in FIGURE_REF_RE.finditer(line):
                p_, f_ = int(m.group(1)), int(m.group(2))
                if (p_, f_) in failed_figs:
                    line_failed = True
                    break
            if line_failed:
                # 整行丢弃（图行）
                continue
        new_lines.append(line)
    md_text = "\n".join(new_lines)

    # 清理"如图 N 所示" / "如图 N 所示，" / "见图 N" / "Figure N 展示了..."等
    # 独立呼应句：去掉"图 N"字样 + 标点 + 引导词（"如图 N 所示，"→"，"）
    # 但若同一句还含其他实质内容则保守处理，只剥"图 N"引用
    if failed_figs:
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
            orig = line
            for fnum in all_fig_nums:
                line = strip_fig_ref(line, fnum)
            # 清理掉"如上文" / "如下图" 这类因剥掉图号而失去指代的孤立引导词
            line = re.sub(r"如\s*[，,。；;]\s*", "如，", line)
            line = re.sub(r"^\s*[,，;；]\s*", "", line)
            line = re.sub(r"[,，;；]\s*[,，;；]\s*", "，", line)
            if line.strip():
                cleaned.append(line)
        md_text = "\n".join(cleaned)
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
        prog="gemini_paper_summary",
        description="用 Gemini 多模态读 PDF 论文并输出中文 Markdown 总结。",
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="本地 PDF 文件的路径（绝对或相对路径均可）。",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "输出路径。默认 stdout；"
            "若同时启用 --extract-figures，则视作 **目录** 路径，"
            "目录内写 summary.md 与 figures/ 子目录。"
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
            "总结模板；academic（默认，≤2500 字符精炼速读，6 段 ## 骨架）或 "
            "full（全文级结构化转储，解除字符数约束，按 PDF 章节逐小节展开；"
            "通常配合 --full 模式使用）。"
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "全文级抽取模式：单次调用同时产 quick summary (academic 模板) "
            "+ 全量结构化转储 (full 模板)，**两份**产物。"
            "产物 layout 强制 raw-compatible：--output 视为 wiki 仓根，"
            "写到 <wiki-root>/raw/papers/<slug>.quick.md + .full.md + "
            "<wiki-root>/raw/assets/<slug>/fig-NN.png。"
            "隐式开启 --refine-figures（Stage 2 视觉定位必带）。"
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
            "把总结中引用的 `PDF p.<N>` 对应页用 pymupdf 渲染成图片，"
            "并把 Markdown 里的引用替换为相对路径。"
            "需要安装 pymupdf；启用时 --output 视作目录路径。"
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


def build_prompt(focus, template="academic"):  # type: (str, str) -> str
    """按 template 选择 prompt 源，必要时追加 --focus 注入。

    - academic (默认): DEFAULT_PROMPT, focus 走 FOCUS_INJECTION(启发 / 追问 段)
    - full: FULL_PROMPT, focus 走 FOCUS_INJECTION_FULL(方法/实验/业务 子段追加)
    """
    if template == "full":
        base = FULL_PROMPT
        injection = FOCUS_INJECTION_FULL
    else:
        base = DEFAULT_PROMPT
        injection = FOCUS_INJECTION
    if focus:
        return base + injection.format(focus=focus.strip())
    return base


def call_gemini(model, pdf_bytes, prompt, temperature):  # type: (str, bytes, str, float) -> str
    """调用 Gemini，返回 Markdown 文本。短 PDF 走 inline；长 PDF 走 File API。

    **无自动 fallback**（2026-06-21 决策）：503/429/500 等高并发 / 限流错误
    **直接抛**给上层——silent 降级到便宜模型容易引入质量问题（不同模型对
    v3.2 prompt 模板的输出质量差异显著，比如 alt 字段偏差、表格行数错位），
    用户感知不到是模型降级导致的，只看到结果怪。换模型用 `--model <id>`
    显式指定。
    """
    client = genai.Client()  # 自动读 GEMINI_API_KEY

    if len(pdf_bytes) <= MAX_PDF_BYTES_INLINE:
        # 走 inline Part：单请求延迟最低
        contents = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ]
    else:
        # 走 File API：先 upload，再把 uploaded file 放进 contents
        sys.stderr.write(
            "INFO: PDF 超过 20 MB，走 File API 上传。\n"
            "      （文件会在 Google 服务端保留 48 小时；如需立即清理，"
            "参考 references/api-quickstart.md §3。）\n"
        )
        uploaded = client.files.upload(
            file=pdf_bytes,
            config={"display_name": "paper-pdf", "mime_type": "application/pdf"},
        )
        contents = [uploaded, prompt]
        # 把 uploaded.name 暂存，调用方如需清理可从返回值再调用 client.files.delete(name=...)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    text = getattr(response, "text", None)
    if not text:
        sys.stderr.write(f"ERROR: Gemini 返回为空。原始 response: {response}\n")
        sys.exit(3)
    return text

    # response.text 在出错时可能为 None，做一次防御
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
        args.refine_figures / args.refine_dpi       -- Stage 2(必需)
        args.figure_dpi / args.figure_format / args.figure_quality
        args.max_width / args.max_size_kb / args.thumbnail / args.thumbnail_width
        args.force_full                              -- 允许覆盖冲突

    写出:
        <wiki_root>/raw/papers/<slug>.quick.md       -- academic 模板产物
        <wiki_root>/raw/papers/<slug>.full.md        -- full 模板产物
        <wiki_root>/raw/assets/<slug>/fig-NN.png     -- Stage 2 裁剪的图(只 full 用)

    关键决策 SSOT:../../MEMORY/gemini-paper-summary-full-mode-design.md
    """
    # 必填校验
    if not args.output:
        sys.stderr.write(
            "ERROR: --full 模式必须配合 --output 使用(--output 视为 wiki 仓根,\n"
            "       产物写到 <wiki_root>/raw/papers/<slug>.quick.md + .full.md +\n"
            "       <wiki_root>/raw/assets/<slug>/fig-NN.png)。\n"
        )
        sys.exit(2)

    wiki_root = os.path.abspath(args.output)
    raw_root = os.path.join(wiki_root, "raw")
    papers_dir = os.path.join(raw_root, "papers")
    assets_root = os.path.join(raw_root, "assets")

    # slug 推断(--slug 优先,否则从 PDF 文件名)
    slug = args.slug if args.slug else slug_from_path(args.pdf)
    if not slug:
        sys.stderr.write(
            "ERROR: 无法推断论文 slug(从 PDF 文件名 '{0}' 得到空字符串)。\n"
            "       用 --slug <kebab-case-slug> 显式指定。\n".format(args.pdf)
        )
        sys.exit(2)

    os.makedirs(papers_dir, exist_ok=True)
    # assets/<slug>/ 在 Stage 2 渲染时再创建;这里先确保 raw/ 与 raw/papers/ 存在

    quick_md_path = os.path.join(papers_dir, "{0}.quick.md".format(slug))
    full_md_path = os.path.join(papers_dir, "{0}.full.md".format(slug))
    assets_dir = os.path.join(assets_root, slug)

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
        "INFO: 第 2 次调用 Gemini (full 模板 = 全文级抽取)\n"
    )
    full_prompt = build_prompt(focus, template="full")
    full_md = call_gemini(model, pdf_bytes, full_prompt, args.temperature)

    # 3) full 产物的图引用处理:Stage 2 视觉定位 + raw-compatible assets 落盘
    #    --full 隐式开启 --refine-figures(SSOT §D4)
    full_refs = parse_figure_refs(full_md)
    visual_bbox_map = {}
    if full_refs:
        # full 模式强制 Stage 2(WARN 而非 ERROR:用户或 pymupdf 缺时 fallback)
        if not args.refine_figures:
            sys.stderr.write(
                "WARN: --full 模式默认开启 Stage 2 视觉定位(--refine-figures),"
                "你显式传了 --no-refine-figures;raw 端图可能不准 bbox。\n"
            )
        if not _HAS_PYMUPDF:
            sys.stderr.write(
                "WARN: --full 需要 pymupdf 做 Stage 2,但未安装;fallback 到 caption locator。\n"
                "      安装命令: pip install --user --break-system-packages pymupdf\n"
            )
        elif not os.environ.get("GEMINI_API_KEY"):
            sys.stderr.write("WARN: Stage 2 需要 GEMINI_API_KEY,未设置;fallback 到 caption locator。\n")
        else:
            if args.refine_figures:
                page_to_png = render_pages_for_gemini(args.pdf, full_refs, dpi_scale=args.refine_dpi)
                if page_to_png:
                    visual_bbox_map = call_gemini_for_visual_bbox(
                        args.pdf, page_to_png, model, args.temperature
                    )
                    full_md = insert_caption_after_figure(full_md, visual_bbox_map)

        # 4) 渲图到 raw/assets/<slug>/  (沿用 Karpathy LLM Wiki raw/assets 布局)
        if full_refs:
            os.makedirs(assets_dir, exist_ok=True)
            ref_to_fullpath, ref_to_thumbpath, ref_to_dim = render_figures_to_pngs(
                args.pdf,
                full_refs,
                assets_dir,
                dpi_scale=args.figure_dpi,
                figure_format=args.figure_format,
                figure_quality=args.figure_quality,
                max_width=args.max_width,
                max_size_kb=args.max_size_kb,
                make_thumbnail=args.thumbnail,
                thumbnail_width=args.thumbnail_width,
                visual_bbox_map=visual_bbox_map,
            )
            if args.thumbnail and ref_to_thumbpath:
                ref_to_relpath = ref_to_thumbpath
                ref_to_full_for_wrap = ref_to_fullpath
            else:
                ref_to_relpath = ref_to_fullpath
                ref_to_full_for_wrap = None
            full_md = embed_figure_refs(
                full_md, ref_to_relpath, ref_to_full_for_wrap, ref_to_dim=ref_to_dim
            )
            refine_note = (
                ", Stage 2 定位 {0} 个".format(len(visual_bbox_map))
                if visual_bbox_map
                else ""
            )
            sys.stderr.write(
                "OK: 已导出 {0} 张图到 {1}(倍率 {2},{3:.0f} DPI,格式 {4}{5}{6})\n".format(
                    len(ref_to_fullpath),
                    assets_dir,
                    args.figure_dpi,
                    args.figure_dpi * 72,
                    args.figure_format,
                    " + 缩略图" if args.thumbnail else "",
                    refine_note,
                )
            )

    # 5) 写两份 .md 到 raw/papers/
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

    # 6) 写一份 .quick.md + .full.md 都跳开 self-check(quick 不带图, full 走
    #    assets/ 不走 figures/;自检路径分支不值得引入)— 当前 self_check_figures
    #    只对 .full.md 的本地图做粗校验,后续迭代再加 raw-specific self-check。
    return 0


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------


def main(argv=None):  # type: (Optional[list]) -> int
    args = parse_args(argv)

    # --full 模式走独立分支;设计决策 SSOT 见
    # ../../MEMORY/gemini-paper-summary-full-mode-design.md(D1 / D2 / D3 / D4)
    if args.full:
        return _run_full_mode(args)

    model, pdf_bytes, focus = validate_inputs(args)
    prompt = build_prompt(focus)
    summary_md = call_gemini(model, pdf_bytes, prompt, args.temperature)

    # ---- 可选：截取每张关键图本身为图片，并替换 Markdown 里的 (PDF p.X fig.N) 引用 ----
    if args.extract_figures:
        if not args.output:
            sys.stderr.write("ERROR: --extract-figures 必须配合 --output 使用（提供输出目录）。\n")
            sys.exit(2)
        out_dir = args.output
        figures_dir_abs = os.path.join(out_dir, "figures")
        refs = parse_figure_refs(summary_md)
        visual_bbox_map = {}
        if refs:
            # Stage 2 (可选): 用 Gemini 看图视觉定位 + 读完整 caption + 过滤装饰图
            if args.refine_figures:
                if not _HAS_PYMUPDF:
                    sys.stderr.write(
                        "WARN: --refine-figures 需要 pymupdf,但未安装;跳过 Stage 2,沿用 caption 定位。\n"
                        "      安装命令: pip install --user --break-system-packages pymupdf\n"
                    )
                elif not os.environ.get("GEMINI_API_KEY"):
                    sys.stderr.write("WARN: --refine-figures 需要 GEMINI_API_KEY,未设置;跳过 Stage 2。\n")
                else:
                    page_to_png = render_pages_for_gemini(args.pdf, refs, dpi_scale=args.refine_dpi)
                    if page_to_png:
                        visual_bbox_map = call_gemini_for_visual_bbox(args.pdf, page_to_png, model, args.temperature)
                        # 在每张图引用行后追加 `**图 N**：<caption>` 行（caption 不再塞进图片或 alt）
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
            refine_note = f", Stage 2 定位 {len(visual_bbox_map)} 个" if visual_bbox_map else ""
            sys.stderr.write(
                f"OK: 已导出 {len(ref_to_fullpath)} 张图到 {figures_dir_abs}（倍率 {args.figure_dpi}，"
                f"{args.figure_dpi * 72:.0f} DPI，格式 {args.figure_format}"
                f"{' + 缩略图' if args.thumbnail else ''}{refine_note}）\n"
            )
        else:
            sys.stderr.write("INFO: 总结里没有 `PDF p.X fig.N` 引用，无需导出图。\n")

    # ---- 写文件或打印 stdout ----
    if args.output:
        if args.extract_figures:
            # --output 在该模式下是目录，.md 固定写在 summary.md
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
    figures_dir = ""
    if args.extract_figures and args.output:
        figures_dir = os.path.join(args.output, "figures")
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

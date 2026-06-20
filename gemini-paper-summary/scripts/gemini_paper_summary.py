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


FOCUS_INJECTION = (
    "\n\n[额外关注点]\n"
    '用户在调用时指定了以下关注点，请在"方法 / 关键结果"小节中相应侧重，'
    '并在"启发 / 追问"小节展开 2-3 个延伸思考：\n\n{focus}\n'
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
    """在该页搜 `Figure N:` caption，返回 caption 所在 line 的 bbox 或 None。
    同一行的多 span 文本（如双栏 PDF 中 "Fig." 与 "4." 分在两个 span），
    拼成 line 文本后再匹配。返回 line bbox 而非 block bbox，避免
    pymupdf 把 caption 与后续正文合并到同一 block 造成 y 越界。"""
    pat = re.compile(rf"^\s*(?:Figure|Fig\.?)\s*{fig_num}\b", re.IGNORECASE)
    for block in page.get_text("dict").get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            line_text = "".join(s.get("text", "") for s in line["spans"]).strip()
            if pat.match(line_text):
                return line["bbox"]
    return None


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
       但可能含 page header）。"""
    cap_bbox = find_figure_caption(page, fig_num)
    if not cap_bbox:
        return None
    cap_limit_y = cap_bbox[3] if include_caption else cap_bbox[1]

    # 双栏论文处理：根据 caption 的 x 中心判断 figure 所在栏，
    # 只在该栏内向上找正文 + 裁剪（避免把另一栏的图/正文框进来）
    cap_x_center = (cap_bbox[0] + cap_bbox[2]) / 2
    page_rect = page.rect
    page_mid_x = (page_rect.x0 + page_rect.x1) / 2
    if cap_x_center < page_mid_x:
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
    """对 Gemini 给的 bbox 做后处理：加 padding；用 caption 位置裁剪 y1
    （包含 caption 但不延伸到 caption 后的正文）。"""
    x0, y0, x1, y1 = bbox
    page_rect = page.rect
    cap_bbox = find_figure_caption(page, fig_num)
    if cap_bbox is not None:
        x0 = min(x0, cap_bbox[0])
        x1 = max(x1, cap_bbox[2])
        y1 = min(y1, cap_bbox[3])
        y0 = min(y0, cap_bbox[1])
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

    返回 (full_map, thumb_map)：
      - full_map: {(page, fig_num): "figures/figure-pX-fY.<ext>"}
      - thumb_map: {(page, fig_num): "figures/figure-pX-fY.thumb.<ext>"}（无缩略图时为空）"""
    if not _HAS_PYMUPDF:
        sys.stderr.write(
            "ERROR: --extract-figures 需要 pymupdf，但未安装。\n"
            "       安装命令: pip install --user --break-system-packages pymupdf\n"
        )
        sys.exit(2)
    if not refs:
        return {}, {}

    os.makedirs(out_dir, exist_ok=True)

    ext_map = {"png": "png", "webp": "webp", "jpeg": "jpg"}
    full_result = {}
    thumb_result = {}
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
                    pad = 2.0
                    x0 = max(page_rect.x0, x0 - pad)
                    y0 = max(page_rect.y0, y0 - pad)
                    x1 = min(page_rect.x1, x1 + pad)
                    y1 = min(page_rect.y1, y1 + pad)
                    if x1 - x0 >= 20 and y1 - y0 >= 20:
                        clip = fitz.Rect(x0, y0, x1, y1)
                # 2) 次优先级：本地 caption 定位（包含 caption，不延伸到正文）
                if clip is None:
                    clip = find_figure_bbox_by_caption(page, f, include_caption=True)
                    if clip is not None:
                        # caption 定位用 +5 padding（更保守一点）
                        clip = fitz.Rect(
                            max(page_rect.x0, clip.x0 - 5),
                            max(page_rect.y0, clip.y0 - 5),
                            min(page_rect.x1, clip.x1 + 5),
                            min(page_rect.y1, clip.y1 + 5),
                        )
                # 3) 最后兜底：Stage 1 Gemini bbox hint（精度差）
                if clip is None and bbox is not None:
                    sys.stderr.write(
                        f"INFO: 第 {p} 页 Figure {f} 未找到 caption/visual bbox，回退到 Gemini bbox hint\n"
                    )
                    x0, y0, x1, y1 = bbox
                    x0 = max(page_rect.x0, min(x0, page_rect.x1))
                    x1 = min(page_rect.x1, max(x1, page_rect.x0))
                    y0 = max(page_rect.y0, min(y0, page_rect.y1))
                    y1 = min(page_rect.y1, max(y1, page_rect.y0))
                    if x1 - x0 < 50 or y1 - y0 < 50:
                        clip = None
                    else:
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
    return full_result, thumb_result


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
            if not is_key:
                sys.stderr.write(f"INFO: Stage 2 第 {page_num} 页 Figure {fig_num} 标记为非关键图,跳过\n")
                continue
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


# 抓整行 `![alt](PDF p.X fig.N ...)` 用于 alt 文本替换
FIGURE_LINE_RE = re.compile(r"(!\[[^\]]*\])\(PDF p\.(\d+)\s+fig\.(\d+)(?:\s+bbox=\[?[\d.,]+\]?)?\)")


def replace_alt_with_full_caption(md_text, visual_bbox_map):
    # type: (str, dict) -> str
    """用 Stage 2 返回的完整 caption 覆盖 Markdown 里的残缺 alt 文本。

    输入 visual_bbox_map: {(page, fig_num): {"bbox_pt": ..., "full_caption": str}}

    替换规则: 仅当 (page, fig_num) 在 visual_bbox_map 中且 full_caption 非空时:
    - 把 `![图 N：<原 alt 余部>](PDF p.X fig.N ...)` 改为
      `![图 N：<full_caption>](PDF p.X fig.N ...)`
    - "图 N：" 前缀保留(便于按 alt 中的"图 N"对应 Markdown 行号)
    - 若原 alt 已含"—"说明段(如"— 展示了..."),保留"—"之后部分(Stage 1 的角色说明)

    未命中或 full_caption 为空时,保持原 alt 不动。"""
    if not visual_bbox_map:
        return md_text

    def repl(m):  # type: (re.Match) -> str
        img_tag = m.group(1)  # ![...]
        page = int(m.group(2))
        fig_num = int(m.group(3))
        entry = visual_bbox_map.get((page, fig_num))
        if not entry or not entry.get("full_caption"):
            return m.group(0)
        full_caption = entry["full_caption"].strip()
        if not full_caption:
            return m.group(0)
        # 解析原 alt: ![图 N：<title>(— <role>)?]
        alt_match = re.match(r"!\[(图\s*\d+\s*[：:])\s*(.*)\]", img_tag)
        if not alt_match:
            return m.group(0)
        prefix = alt_match.group(1)  # "图 N："
        rest = alt_match.group(2).strip()  # "<title>(— <role>)?"
        # 拆 "—" 分隔符:caption 之前是 title,"—" 之后是 Stage 1 写的角色说明
        parts = re.split(r"\s*—\s*", rest, maxsplit=1)
        # 新 alt = "图 N：<full_caption>(— <role>)?"
        if len(parts) == 2:
            new_alt = f"{prefix}{full_caption} — {parts[1]}"
        else:
            new_alt = f"{prefix}{full_caption}"
        return "!" + "[" + new_alt + "]" + m.group(0)[len(img_tag) :]

    return FIGURE_LINE_RE.sub(repl, md_text)


# 缩略图二次包裹：`![alt](figures/figure-pX-fY.thumb.png)` → `[![alt](thumb)](full)`
THUMB_IMG_RE = re.compile(r"(!\[[^\]]*\])\((figures/figure-[^\)]+\.thumb\.[a-z]+)\)")


def embed_figure_refs(md_text, ref_to_relpath, ref_to_fullpath=None):
    # type: (str, dict, dict) -> str
    """把 Markdown 里的 `(PDF p.X fig.N [bbox=...])` 替换为 `(相对路径)`。
    key 用 (page, fig_num)，忽略 bbox 差异（同图号应指向同一文件）。

    缩略图模式（--thumbnail）：`ref_to_fullpath` 是按 (page, fig_num) 的全图路径映射
    （与 ref_to_relpath 同 key 体系，只是 value 是 full_path 而非 thumb_path）。
    函数会先把 ref_to_fullpath 反向成 `{thumb_path: full_path}`，再把 Markdown 里的
    `![alt](thumb)` 二次包裹为 `[![alt](thumb)](full)`，实现点击缩略图跳原图。"""
    ref_to_fullpath = ref_to_fullpath or {}

    def repl(m):  # type: (re.Match) -> str
        page = int(m.group(1))
        fig_num = int(m.group(2))
        rel = ref_to_relpath.get((page, fig_num))
        return f"({rel})" if rel else m.group(0)

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
        choices=["academic"],
        help="总结模板；当前只内置 academic（6 段 ## + 3 段 ### 的学术结构化），默认 academic。",
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


def build_prompt(focus):  # type: (str) -> str
    if focus:
        return DEFAULT_PROMPT + FOCUS_INJECTION.format(focus=focus.strip())
    return DEFAULT_PROMPT


def call_gemini(model, pdf_bytes, prompt, temperature):  # type: (str, bytes, str, float) -> str
    """调用 Gemini，返回 Markdown 文本。短 PDF 走 inline；长 PDF 走 File API。"""
    client = genai.Client()  # 自动读 GEMINI_API_KEY

    config = types.GenerateContentConfig(temperature=temperature)

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
        config=config,
    )

    # response.text 在出错时可能为 None，做一次防御
    text = getattr(response, "text", None)
    if not text:
        sys.stderr.write(f"ERROR: Gemini 返回为空。原始 response: {response}\n")
        sys.exit(3)
    return text


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------


def main(argv=None):  # type: (Optional[list]) -> int
    args = parse_args(argv)
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
                        # 用 Gemini 读出的完整 caption 覆盖 Markdown alt 中可能残缺的标题
                        summary_md = replace_alt_with_full_caption(summary_md, visual_bbox_map)
            os.makedirs(out_dir, exist_ok=True)
            ref_to_fullpath, ref_to_thumbpath = render_figures_to_pngs(
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
            summary_md = embed_figure_refs(summary_md, ref_to_relpath, ref_to_full_for_wrap)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

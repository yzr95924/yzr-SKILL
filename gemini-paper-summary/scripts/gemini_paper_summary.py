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

# 6 段 ## + 3 段 ### 的结构化 prompt；关键架构图 / 开源实现 / 局限 合并或降级处理。
# 完整注释版见 assets/prompt-template.md。
# 任何模板变更需要同步更新 assets/prompt-template.md 与 SKILL.md §输出。
DEFAULT_PROMPT = (
    "你是一位学术论文阅读助手。请基于这篇论文，用**中文**输出一份结构化总结，"
    "严格包含以下 6 个 ## 级小节和 3 个 ### 级子小节（标题与顺序保持一致）：\n\n"
    "# <论文标题> - 阅读总结\n\n"
    "## 一句话速览\n"
    "用一句话说清楚这篇论文解决了什么问题、核心贡献是什么（不超过 80 字）。\n\n"
    "## 研究问题 / 动机\n"
    "为什么要做这个研究？现有方法的不足是什么？论文自述的目标是什么？\n\n"
    "## 方法\n"
    "核心思路与技术路线。在叙述中**呼应关键架构图**"
    '（如"如图 1 所示，..."）。本小节末尾追加子列表：\n\n'
    "  **关键架构图 / 示意图**（若论文含关键图，2-5 张为宜）：\n"
    "  - ![图 1：<图标题>](PDF p.3 fig.1 bbox=100,80,500,400) — <1-2 句说明它在方法中的角色>\n"
    "  - ![图 2：<图标题>](PDF p.5 fig.2) — <1-2 句说明>\n\n"
    '  只收"关键图"：整体架构、核心模块示意、概念流程图、关键对比示意。\n'
    "  **URL 格式**：](PDF p.<页> fig.<N>) 中 N 是论文里的 Figure 编号（图 N）。\n"
    "  若你能从 PDF 看到该图的边界，**强烈建议附加 bbox=x0,y0,x1,y1**（PDF point 单位，"
    "1 point = 1/72 inch，原点在左上角；A4 ≈ 595×842，Letter ≈ 612×792），"
    "用 4 个整数/小数逗号分隔，**不要**加方括号或尖括号。脚本会用 bbox 精确截取该图本身而非整页。\n"
    "  若你无法给出准确 bbox，省略即可——脚本会在该页自动按 `Figure N:` caption 定位并截取 caption 上方区域。\n"
    "  **无论是否给 bbox，都不要写 `https://`、`figure/xxx.png` 等占位 URL**——本 skill 自己管图片输出。\n\n"
    "跳过装饰图、坐标轴标注、表格截图、附录图、补充材料中的非核心图。"
    '页码以 PDF 实际页码为准（首页为 p.1），不要写"图 1 在第 3 页附近"。\n\n'
    "## 关键结果\n"
    "主要实验结论与数据。**保留具体数值**"
    '（如"在 GLUE 上达到 91.2，比 BERT 提升 3.1"），避免"显著提升"这类空话。\n\n'
    "## 贡献、开源与局限\n"
    "本节包含三个 ### 子小节，按以下顺序：\n\n"
    "### 贡献与创新点\n"
    "用编号列出 3-5 条贡献。区分“方法创新”与“实验发现”。\n\n"
    "### 开源实现\n"
    "（若论文提到 prototype / source code / dataset / online demo 的可访问链接，"
    "按下列形式列出；**只写论文中明确给出的 URL，不要编造**；若无则整个 ### 子小节省略）\n\n"
    "- **代码仓库**：<URL> （简述：实现语言 / 仓库活跃度）\n"
    "- **数据集**：<URL> （简述）\n"
    "- **在线 Demo**：<URL> （简述）\n\n"
    "  链接类型未知时（如脚注里的 project page），归到“代码仓库”那行；"
    "若有多个相关链接，可加多行（如 paper-website、video、slides）。\n\n"
    "### 局限与未来工作\n"
    "作者自己承认的局限（如有），以及论文未覆盖但明显是下一步的方向。\n\n"
    "## 高频引用 / Take-aways\n"
    "（若论文有引言 / 相关工作章节，按下表给 3-8 条；否则整段省略）\n\n"
    "| # | 引用次数 | 论文（作者-年份 + 标题 + 会议/期刊） | 一句话核心观点 | 论文中位置 |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| 1 | ~10+ | Vaswani et al. 2017, Attention is All You Need, NeurIPS | 提出 Transformer 架构 | §2.1 |\n"
    "| 2 | ~5+ | Devlin et al. 2019, BERT: Pre-training of Deep Bidirectional Transformers, NAACL | 双向预训练语言模型 | §2.2 |\n\n"
    "  **会议/期刊命名**：用领域惯用缩写，例如 NeurIPS / ICML / SIGMOD / VLDB / ICDE / OSDI /\n"
    "  TODS / VLDBJ；不确定时按论文 PDF 中参考文献列表里的写法。\n\n"
    "  **表格列数**：每行必须严格 5 列（# / 引用次数 / 论文 / 一句话核心观点 / 论文中位置），\n"
    "  不可省略“引用次数”列（即使只是估算也要填 ~3 / ~5+ 这种）。\n\n"
    '排序按"对本文重要性"或"引用频次"降序；剔除一次性提及、自引、'
    "与本文方法无直接关系的工作。引用次数从引言/相关工作部分数，"
    '作为"高频"近似估计。\n\n'
    "## 启发 / 追问\n"
    "（仅在用户提供了关注点时输出）基于关注点延伸的 2-3 个思考点或追问。\n\n"
    "---\n"
    "要求：\n"
    '1. **忠于原文**：论文未提及的内容不要编造，不确定处标注"原文未明确"。\n'
    "2. **不强制全中文，英文该留就留**：默认中文叙述，"
    "但学术专有名词/方法名、模型/产品/工具名、库/API/文件名、"
    "算法/协议/标准名、度量/缩写等五类术语直接保留英文不硬译"
    "（如 Transformer、RLHF、LoRA、Gemini、PyTorch、"
    "`transformers`、Top-p、BLEU、perplexity）。\n"
    '   中英混排是常态（如"训练使用 LoRA（低秩适配）"）；'
    "表格中整项为英文术语时整项保持英文。\n"
    '3. **引用出处**：引用关键结论时点明出自论文哪个章节（"见 4.2 实验"）。\n'
    "4. **总字数 600-1500 字**（合并段后偏短属正常）。\n"
    "5. **Markdown 标题分节**，使用二级标题（##）作为小节标题，"
    "一级标题用论文标题。\n"
)


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
    include_caption=True 时包含 caption，False 时只到 caption 顶。"""
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

    # 找同一栏内、caption 上方最近的"正文段落"（宽 + 多行）底部作为 figure 顶。
    # 启发式：body text 跨满栏宽，figure annotation/label 都很窄。
    # 找不到合适的正文段落时退回到 page 顶，保证 figure 一定被框入。
    col_width = col_right - col_left

    def is_body_text_block(block):
        line_count = len(block.get("lines", []))
        block_width = block["bbox"][2] - block["bbox"][0]
        return line_count >= 2 and block_width >= col_width * 0.6

    text_above_bottom = page.rect.y0
    found_body = False
    for block in page.get_text("dict").get("blocks", []):
        if "lines" not in block:
            continue
        block_x_center = (block["bbox"][0] + block["bbox"][2]) / 2
        if block_x_center < col_left or block_x_center > col_right:
            continue
        block_bottom = block["bbox"][3]
        if block_bottom >= cap_limit_y:
            continue
        if not is_body_text_block(block):
            continue
        if block_bottom > text_above_bottom:
            text_above_bottom = block_bottom
            found_body = True
    if not found_body:
        text_above_bottom = page.rect.y0

    # 若 text_above_bottom 离 caption 太近（< 30 pt），说明紧贴的是 figure 自身的
    # label/annotation（不算正文），退回用 page 顶
    if cap_limit_y - text_above_bottom < 30:
        text_above_bottom = page.rect.y0

    if col_right - col_left < 100:
        return None
    return fitz.Rect(col_left, text_above_bottom, col_right, cap_limit_y)


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
):
    # type: (str, list, str, float, str, int, int, int, bool, int) -> tuple
    """对每条 (page, fig_num, bbox_or_None) 截取图本身，存为图片文件。

    定位策略：caption 定位为主，bbox 仅作 hint
    1. 优先在该页按 `Figure N:` caption 定位 → 截取 caption 上方到 caption 底（包含 caption）
    2. 若无 caption 可用 Gemini 提供的 bbox 作为兜底
    3. 若都没有，跳过该图

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
                # 1) 优先：caption 定位（最准，包含 caption 但不延伸到正文）
                clip = find_figure_bbox_by_caption(page, f, include_caption=True)
                if clip is None and bbox is not None:
                    # 2) 兜底：Gemini bbox（去掉 padding / 不裁剪，作为最后手段）
                    sys.stderr.write(f"INFO: 第 {p} 页 Figure {f} 未找到 caption，回退到 Gemini bbox\n")
                    page_rect = page.rect
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
                    sys.stderr.write(f"WARN: 第 {p} 页 Figure {f} 定位失败（既无 caption 也无有效 bbox），跳过\n")
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
        if refs:
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
            )
            # 选择 Markdown 引用源：缩略图模式用 thumb，否则用 full
            if args.thumbnail and ref_to_thumbpath:
                ref_to_relpath = ref_to_thumbpath
                ref_to_full_for_wrap = ref_to_fullpath  # embed_figure_refs 内部反向索引
            else:
                ref_to_relpath = ref_to_fullpath
                ref_to_full_for_wrap = None
            summary_md = embed_figure_refs(summary_md, ref_to_relpath, ref_to_full_for_wrap)
            sys.stderr.write(
                f"OK: 已导出 {len(ref_to_fullpath)} 张图到 {figures_dir_abs}（倍率 {args.figure_dpi}，"
                f"{args.figure_dpi * 72:.0f} DPI，格式 {args.figure_format}"
                f"{' + 缩略图' if args.thumbnail else ''}）\n"
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

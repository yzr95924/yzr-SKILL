"""
auto_detect: PDF 类型自动识别（PDF 元数据 + Gemini 看首页验证）

被 gemini_pdf_summary.py 的 --auto-detect 路径调用。

两层策略：
1. 本地启发式（快、零成本）：读 PDF 元数据（Title / Subject / Keywords / Producer）+ 首页
   文本的关键词匹配 → 给出粗判 + 置信度
2. Gemini 验证（慢、消耗 token）：当本地启发式置信度不足时，把首页 1-3 页渲染成 PNG 送
   Gemini 多模态，让它从版式 / 标题 / 排版风格判断 paper / manual / whitepaper / book

返回值（仅合法 doc_type 之一）："paper" / "manual" / "whitepaper" / "book"
"""

import os
import re
import sys
from typing import Optional, Tuple  # noqa: F401

# 复用 gemini_pdf_summary.py 的常量；ImportError fallback 仅在 standalone 调试时触发，
# SSOT 仍以主脚本为准（2026-07-06 起全 skill 统一 DEFAULT_MODEL = "gemini-3.1-pro-preview"）。
try:
    from gemini_pdf_summary import DEFAULT_MODEL, VALID_TYPES  # type: ignore
except ImportError:
    DEFAULT_MODEL = "gemini-3.1-pro-preview"
    VALID_TYPES = ("paper", "manual", "whitepaper", "book")

# 启发式关键词权重表（命中 1 次 = +N 分；总分 ≥ 阈值则跳过 Gemini 验证）
KEYWORD_HINTS = {
    "paper": [
        (r"\b(abstract|introduction|methodology|related work|references)\b", 3),
        (r"\b(arxiv|doi:|proceedings of|acm|springer|ieee)\b", 2),
        (r"\b(neural network|transformer|gradient|backpropagation|loss function)\b", 2),
        (r"\b(et al\.|\[1\]|\[\d+\])\b", 2),
    ],
    "manual": [
        (r"\b(user manual|installation guide|getting started|quick start)\b", 3),
        (r"\b(datasheet|specifications?|technical specs|product specifications)\b", 2),
        (r"\b(operating instructions|setup guide|configuration)\b", 2),
        (r"\b(command line|cli|api reference|endpoint)\b", 1),
        (r"\b(warranty|troubleshooting|faq)\b", 1),
    ],
    "whitepaper": [
        (r"\b(white paper|industry report|market analysis|market research)\b", 3),
        (r"\b(executive summary|introduction|challenges?|solutions?)\b", 1),
        (r"\b(case study|customer success|roi|total cost of ownership)\b", 2),
        (r"\b(gartner|forrester|idc|mckinsey|deloitte)\b", 2),
    ],
    "book": [
        (r"\b(chapter \d+|part [ivx]+|appendix|index)\b", 3),
        (r"\b(table of contents|foreword|preface|acknowledg(?:e?)ments)\b", 2),
        (r"\b(edition|hardcover| paperback|publisher:?|isbn)\b", 2),
        (r"\b(exercises?|review questions|further reading)\b", 1),
    ],
}

# 启发式阈值：总分 ≥ 此值则跳过 Gemini 验证（高置信度）
HEURISTIC_CONFIDENCE_THRESHOLD = 6
# 总分差阈值：top1 - top2 ≥ 此值则视为可决策
HEURISTIC_MARGIN_THRESHOLD = 3


def _score_first_page_text(first_page_text: str) -> dict:
    """对首页文本按 KEYWORD_HINTS 打分，返回 {type: score} 字典。"""
    scores = {t: 0 for t in VALID_TYPES}
    text_lower = first_page_text.lower()
    for doc_type, patterns in KEYWORD_HINTS.items():
        for pattern, weight in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                scores[doc_type] += weight
    return scores


def _decide_from_scores(scores: dict) -> Optional[Tuple[str, float]]:
    """从分数字典返回 (best_type, confidence_margin)；分数太低返回 None。

    confidence_margin = top1 - top2
    """
    sorted_types = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not sorted_types or sorted_types[0][1] == 0:
        return None
    top1_type, top1_score = sorted_types[0]
    top2_score = sorted_types[1][1] if len(sorted_types) > 1 else 0
    margin = top1_score - top2_score
    if top1_score >= HEURISTIC_CONFIDENCE_THRESHOLD and margin >= HEURISTIC_MARGIN_THRESHOLD:
        return top1_type, margin
    return None


def _extract_pdf_metadata_and_first_page(pdf_path: str) -> Tuple[dict, str]:
    """读 PDF 元数据 + 首页文本（用 pymupdf；缺包时报清晰错误）。"""
    try:
        import fitz  # type: ignore  # pymupdf
    except ImportError:
        sys.stderr.write(
            "ERROR: auto-detect 需要 pymupdf 读 PDF 元数据 + 首页。\n"
            "       安装: pip install --user --break-system-packages pymupdf\n"
        )
        sys.exit(2)

    doc = fitz.open(pdf_path)
    try:
        metadata = dict(doc.metadata or {})
        # 首页文本
        first_page = doc.load_page(0) if doc.page_count > 0 else None
        first_page_text = first_page.get_text() if first_page is not None else ""
    finally:
        doc.close()

    return metadata, first_page_text


def _ask_gemini_for_type(pdf_path: str, model: str = DEFAULT_MODEL) -> str:
    """把 PDF 首页 1-3 页渲染给 Gemini 多模态，让它判断文档类型。

    返回 VALID_TYPES 之一；判断不出时抛 RuntimeError（让上层处理）。
    """
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        sys.stderr.write(
            "ERROR: auto-detect Gemini 验证路径需要 google-genai SDK。\n"
            "       安装: pip install -U google-genai\n"
        )
        sys.exit(2)

    try:
        import fitz  # type: ignore  # pymupdf
    except ImportError:
        sys.stderr.write(
            "ERROR: auto-detect Gemini 验证路径需要 pymupdf。\n"
            "       安装: pip install --user --break-system-packages pymupdf\n"
        )
        sys.exit(2)

    if not os.environ.get("GEMINI_API_KEY"):
        sys.stderr.write(
            "ERROR: auto-detect Gemini 验证路径需要 GEMINI_API_KEY 环境变量。\n"
            "       仅靠本地启发式置信度不足时无法决策。\n"
        )
        sys.exit(2)

    doc = fitz.open(pdf_path)
    try:
        page_count = min(doc.page_count, 3)
        png_bytes_list = []
        for i in range(page_count):
            page = doc.load_page(i)
            mat = fitz.Matrix(2.0, 2.0)  # 2x DPI，约 144 DPI
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes_list.append(pix.tobytes("png"))
    finally:
        doc.close()

    # 拼装 Gemini 调用
    client = genai.Client()
    prompt = (
        "你是文档类型分类助手。基于这份 PDF 的首页 1-3 页版式 / 标题 / 排版风格，"
        "判断它属于以下哪一类（只输出单词，不解释）：\n"
        "  paper      - 学术论文（含 abstract / introduction / 双栏 / 公式 / 引用列表）\n"
        "  manual     - 产品手册 / datasheet / 用户手册（含产品规格表 / 安装步骤 / API endpoint）\n"
        "  whitepaper - 行业 / 技术 / vendor 白皮书（含 executive summary / market analysis / case study）\n"
        "  book       - 书籍 / 长篇技术文档（含 chapter / part / appendix / 索引）\n"
        "如果无法判断，输出: unknown"
    )
    contents = [types.Part.from_bytes(data=p, mime_type="image/png") for p in png_bytes_list]
    contents.append(prompt)

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=16),
        )
    except Exception as e:
        raise RuntimeError(f"Gemini 验证调用失败: {e}") from e

    text = (getattr(response, "text", None) or "").strip().lower()
    text = text.split()[0] if text else ""  # 取首个 token
    text = text.strip(".,;:!?\"'")
    if text in VALID_TYPES:
        return text
    raise RuntimeError(f"Gemini 验证返回非合法类型: {text!r}")


def detect_doc_type(pdf_path: str, model: str = DEFAULT_MODEL) -> str:
    """主入口：返回 doc_type 之一。

    策略：
    1. 读 PDF 元数据 + 首页文本 → 本地启发式打分
    2. 决策（高置信度）→ 返回；否则进入 3
    3. Gemini 看首页验证 → 返回；判断不出抛 RuntimeError
    """
    if not os.path.isfile(pdf_path):
        raise RuntimeError(f"PDF 文件不存在: {pdf_path}")

    metadata, first_page_text = _extract_pdf_metadata_and_first_page(pdf_path)

    # 把元数据 + 首页文本拼起来一起打启发式
    md_text = " ".join(str(v) for v in metadata.values() if v) + "\n" + first_page_text
    scores = _score_first_page_text(md_text)
    decision = _decide_from_scores(scores)
    if decision is not None:
        doc_type, margin = decision
        sys.stderr.write(
            f"INFO: auto-detect 启发式高置信度 → {doc_type} (score={scores[doc_type]}, "
            f"margin={margin})\n"
        )
        return doc_type

    # 启发式不足 → Gemini 验证
    sys.stderr.write(
        f"INFO: auto-detect 启发式置信度不足 (scores={scores})，调用 Gemini 验证...\n"
    )
    try:
        return _ask_gemini_for_type(pdf_path, model=model)
    except Exception as e:
        raise RuntimeError(
            f"auto-detect 失败：本地启发式置信度不足且 Gemini 验证异常 ({e})。"
            f"请显式传 --type <paper|manual|whitepaper|book>。"
        ) from e

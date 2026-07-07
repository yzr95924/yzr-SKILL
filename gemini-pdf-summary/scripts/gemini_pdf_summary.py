#!/usr/bin/env python3
"""
gemini_pdf_summary: 用 Gemini 多模态读 PDF 并按文档类型路由到对应模板,
输出中文 Markdown 总结。

本脚本是 gemini-pdf-summary skill 的核心可执行入口。
它也可以被 agent 在 bash 命令行里直接调用。

支持的文档类型（--type）：
    paper      - 学术论文（双模式：quick 默认抽原始图给**人**看；full 按 PDF 原生章节全文级转写）
    manual     - 产品手册 / datasheet / 用户手册（full 风格，按 PDF 原生目录结构全文级转写；
                 产物供 LLM 消费并进入 llm-wiki 二次 ingest）
    whitepaper - 行业 / 技术 / vendor 白皮书（full 风格，按 PDF 原生目录结构全文级转写；
                 产物供 LLM 消费并进入 llm-wiki 二次 ingest）
    book       - 书籍 / 长篇技术文档（仅 full 风格，按 Chapter / Part / Appendix / Index
                 顺序全量转写）

**风格归属（2026-07-05 翻面）**：
- quick 风格 = paper quick（唯一保留 quick 的类型；给**人**看；有字符上限）
- full 风格 = paper full + manual + whitepaper + book（按 PDF 原生章节顺序全文级转写；
  无字符上限；产物供 LLM 消费）
- 脚本 `prompt_mode = "full"` 已硬编码到 main()，对 manual / whitepaper / book 无需传 `--full`

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

    # paper 的 --full 模式（单产物 full 自包含无图；其他类型忽略此 flag；其他类型默认就是 full 风格）
    python3 gemini_pdf_summary.py --pdf paper.pdf --type paper --full --output <wiki-root>
    # 想看论文精炼速读 + 带图，用 --type paper 默认（quick 模式）；要看 PNG 用 quick + --extract-figures

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

DEFAULT_MODEL = "gemini-3.1-pro-preview"
# 全 skill 统一默认走 pro-preview(2026-07-06 决策):
# - --by-chapter 单调用 + JSON 结构化输出下,3.5-flash 实测撞 FULL_MAX_OUTPUT_TOKENS
#   (65536) 上限导致 JSON 未闭合;pro-preview 长上下文注意力更稳
# - pro-preview 在 full 风格(manual/whitepaper/book/paper --full)下 mermaid 架构图
#   完整保留;flash 在结构化输出下会默默丢 mermaid block
# - 全 skill 统一默认(不再按 by-chapter 特判),减少 agent 推理"哪个模式走哪个模型"
#   的认知负担;代价是 flash 性价比优势消失,4 类 PDF 全部按 preview 计费
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
ASSETS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "assets"))

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
    - mode（2026-07-05 翻面后语义）：
        * "quick": 仅 paper 适用（论文精炼速读，给**人**看；manual / whitepaper / book
          历史上也走这条路径，但 2026-07-05 翻面后改走 "full"）
        * "full"（默认；manual / whitepaper / book 强制走这条路径）:
          paper → ## full 模式段（按 PDF 原生 Section 顺序）
          manual → ## 模板（按 PDF 原生目录结构全文级转写，单模板不分模式）
          whitepaper → ## 模板（同 manual）
          book → ## 模板（按 Chapter / Part / Appendix / Index 顺序）

    **历史兼容**：manual / whitepaper 旧实现里 ("manual", "quick") / ("whitepaper", "quick")
    都映射 `## 模板` 段（旧模板正文是 quick 风格）；2026-07-05 翻面后该模板正文已重写为
    full 风格，main() 也已把 manual / whitepaper 走 `prompt_mode = "full"`，**没有调用方**
    再用 mode="quick" 加载 manual / whitepaper——但 head_patterns 仍保留该映射以防
    历史脚本兼容。

    失败时（文件缺失 / 段不存在 / 没有 text fence）立即报错退出——这是开发期
    应该立刻发现的问题，不允许静默回退到老模板。"""
    if doc_type not in VALID_TYPES:
        sys.stderr.write(f"ERROR: 未知 doc_type {doc_type!r}；合法值: {VALID_TYPES}\n")
        sys.exit(2)

    if doc_type == "book" and mode == "quick":
        sys.stderr.write(
            "ERROR: book 类型仅支持 full 风格（按 PDF 原生章节全文级转写）。\n"
            "       书籍无法做 quick 速读总结——脚本 main() 已自动启用 full，"
            "如果此报错出现在调用链路，请检查调用方是否传 mode='quick'。\n"
        )
        sys.exit(2)

    template_path = os.path.join(ASSETS_DIR, f"template-{doc_type}.md")
    if not os.path.isfile(template_path):
        sys.stderr.write(
            f"ERROR: 找不到 prompt 模板文件: {template_path}\n       仓库结构破坏，请检查 {ASSETS_DIR}/ 目录。\n"
        )
        sys.exit(2)

    with open(template_path, encoding="utf-8") as f:
        md = f.read()

    # 段标题定位规则（2026-07-05 翻面后）：
    #   paper     → "## quick 模式（默认）" 或 "## full 模式（--full）"
    #   manual    → "## 模板"（单模板即 full；mode 参数被忽略，走 full 风格）
    #   whitepaper→ "## 模板"（单模板即 full；mode 参数被忽略，走 full 风格）
    #   book      → "## 模板"（单 full 模式）
    head_patterns = {
        ("paper", "quick"): r"^##\s+quick\s*模式\s*[（(]默认[)）]\s*$",
        ("paper", "full"): r"^##\s+full\s*模式\s*[（(].*--full.*[)）]\s*$",
        ("manual", "quick"): r"^##\s+模板\s*$",  # 历史兼容；模板正文已是 full 风格
        ("manual", "full"): r"^##\s+模板\s*$",
        ("whitepaper", "quick"): r"^##\s+模板\s*$",  # 历史兼容；模板正文已是 full 风格
        ("whitepaper", "full"): r"^##\s+模板\s*$",
        ("book", "full"): r"^##\s+模板\s*$",
    }
    pattern = head_patterns[(doc_type, mode)]
    head_match = re.search(pattern, md, re.MULTILINE)
    if not head_match:
        sys.stderr.write(
            f"ERROR: {template_path} 里找不到 '{pattern}' 对应的段。\n       模板文件结构破坏，请补回该小节。\n"
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
# --by-chapter 模式：单次 API 调用 + JSON 结构化输出 + 按章节拆文件
# ----------------------------------------------------------------------------

# Gemini response_schema：强制每个章节独立 {title, level, content}
# 适用 manual / whitepaper / book / paper 全文级拆分；不适用于 paper quick 速读
CHAPTER_SCHEMA = {
    "type": "object",
    "properties": {
        "chapters": {
            "type": "array",
            "description": "PDF 全部章节，按 PDF 原生顺序",
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "章节标题，保留 PDF 原语言（中文/英文保留原文，**不要**翻译）",
                    },
                    "level": {
                        "type": "integer",
                        "description": "章节层级：1=Chapter / Part / 大节，2=Section / Subsection，3=Sub-subsection，4=Appendix / Index",
                    },
                    "content": {
                        "type": "string",
                        "description": "该章节的完整 markdown 转写（不含 H1 标题，标题由 title 字段承载）",
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    "required": ["chapters"],
}

BY_CHAPTER_PROMPT = """你是一位 PDF 章节拆分助手。请基于这份 PDF，按 PDF 原生章节结构，
把每个章节拆分到一个独立的 JSON 对象中（title + level + content）。

## 输出要求

1. **严格按 PDF 原生章节顺序**输出（Chapter 1 → Chapter 2 → ... → Appendix → Index），
   **不要**重排、合并、跳过任何章节
2. 每个章节的 `content` 字段是该章节的**完整 markdown 转写**（full 风格）：
   - 章节标题保留 PDF 原语言（中文 PDF 保留中文标题；英文保留英文）
   - 所有正文段落完整保留，**不**摘要化、**不**省略
   - 表格行级转写（参数表 / 接口表 / 错误码表 / 行业数据表 / 对比表），
     数字精度保留（不要"约""大约"模糊化）
   - 命令清单 / API endpoint / 配置项用 ```bash / ```yaml / ```json 代码块
   - 公式用 `$...$`（独立公式可用 `$$...$$` block）
   - 架构 / 概念 / 流程图用 ```mermaid block（`graph TD` / `graph LR` / `sequenceDiagram` 等；
     用标准 mermaid 语法，不要用 `mermaid`）
   - 数据可视化图转 markdown 表格
   - 关键数字与单位原样保留（如 "160 万 IOPS"、"4 GB/s"、"≤ 2 ms"）
3. `content` 字段**不**包含 H1（一级标题由 `title` 字段承载；正文从 `##` 或 `###` 起步）
4. 章节末尾的特色内容**原样保留**：
   - manual: 故障排查 / FAQ / 更新日志要点
   - whitepaper: Conclusion / Key Takeaways / Recommendations
   - book: 小结 / 思考题 / 参考文献 / 索引 term → page
   - paper: 参考文献 / 附录
5. **不**输出 summary / TLDR / 整体归纳段 / 业务启示 / 局限与未来工作
6. 章节拆分贴合 PDF 原生层级（Chapter / Section / Subsection / Appendix / Index），
   **不要**把整本 PDF 塞进一个对象
7. 如果某些内容不属于任何章节（如封面、目录、版权页），可跳过；但**章节正文**必须全保留

## 字段填写规则

- `title`：该章节在 PDF 中的标题原文（如 `## 1 产品概述` → `"1 产品概述"`）
- `level`：1 表示最大层级（Chapter / 大节）；2 表示次级 Section；依此类推
- `content`：从 `##` 或 `###` 起步的完整 markdown；表格 / 代码块 / mermaid 完整保留

请直接输出符合 schema 的 JSON，**不要**输出任何解释性文本。"""


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
    real_captions = [c for c in candidates if cap_pat.match(c[2]) and len(c[2]) <= 120]
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
                            f"INFO: 第 {p} 页 Figure {f} 回退到 Gemini bbox hint ({x1 - x0:.0f}x{y1 - y0:.0f}pt)\n"
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
            "  paper      - 学术论文（双模式：quick 默认抽原始图给**人**看；full 按 PDF 原生章节全文级转写）\n"
            "  manual     - 产品手册 / datasheet / 用户手册（full 风格，按 PDF 原生目录结构全文级转写；"
            "产物供 LLM 消费并进入 llm-wiki 二次 ingest）\n"
            "  whitepaper - 行业 / 技术 / vendor 白皮书（full 风格，按 PDF 原生目录结构全文级转写；"
            "产物供 LLM 消费并进入 llm-wiki 二次 ingest）\n"
            "  book       - 书籍 / 长篇技术文档（仅 full 风格，按 Chapter / Part / Appendix / Index 顺序全量转写）\n"
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
        help=f"Gemini 模型 ID，默认 {DEFAULT_MODEL}（全 skill 统一默认值；长上下文注意力稳，mermaid 架构图完整保留）。",
    )
    parser.add_argument(
        "--refine-model",
        default=None,
        help="Stage 2 视觉定位专用模型（仅 paper quick + --refine-figures 生效）。"
        "默认 None → 跟 --model 走。结构化 JSON bbox 输出 + 单页 PNG 输入，"
        "理论上 flash-lite 已够用，可用此 flag 拆开以降低 503 概率 + 节省成本。"
        "例：--model gemini-3.1-pro-preview --refine-model gemini-3.1-flash-lite"
        "（主总结保 pro-preview 的复杂推理 + 长文稳，Stage 2 走更便宜的轻量模型）。"
        "模型选型指南见 SKILL.md §模型选型。",
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
            "全文级抽取模式：仅对 --type paper 有意义——单次调用产**一份** PDF→Markdown "
            "全量转写（full 模板，自包含无图，给 agent 多轮查询用）。\n"
            "产物 layout 强制 raw-compatible：--output 视为 wiki 仓根，"
            "写到 <wiki-root>/raw/papers/<slug>.full.md（不写 .quick.md）。"
            "用 --slug 显式指定论文 slug（默认从 PDF 文件名推断）。"
            "若 raw 端产物已存在默认拒绝覆盖（用 --force-full 显式允许）。\n"
            "**manual / whitepaper / book 默认就是 full 风格**（脚本 main() 自动启用 full），"
            "传 --full 无效果——这 3 类无 quick 风格。\n"
            "**想看论文精炼速读 + 带图**：不传 --full（默认 quick 模式，跑 --type paper 即可）；"
            "要看 PNG 走 quick + --extract-figures 单跑，详见 SKILL.md §输出 / §图表处理策略。"
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
            "允许 --full 模式覆盖已存在的 raw/papers/<slug>.full.md（默认拒绝覆盖，"
            "理由：full 抽取是'贵读一次'的产物，意外重写会丢下游已经多次引用的 raw）。"
            "仅在 --full 模式下有意义。"
        ),
    )
    parser.add_argument(
        "--by-chapter",
        action="store_true",
        help=(
            "按 PDF 原生章节拆分产物为多个 markdown 文件。\n"
            "适用 manual / whitepaper / book / paper full 场景：当用户希望按章节粒度拥有独立 .md 文件、"
            "便于 llm-wiki 二次 ingest 与逐章 Q&A 时使用。\n"
            "拆法由 --granularity 控制（默认 L1：按 L1 章 N 次独立调用 + L2 子节合并进 L1）。\n"
            "产物 layout: <output>/00-index.md (TOC) + <output>/01-<L1-slug>.md + ...\n"
            "与 --full 互斥（--by-chapter 已隐含全文级转写）。\n"
            "受 FULL_MAX_OUTPUT_TOKENS (65536) 上限约束；L1 模式按章拆每章 ≤ 50 页，"
            "撞限概率近 0；auto 模式单调用撞限用 --pages 拆段缓解。"
        ),
    )
    parser.add_argument(
        "--granularity",
        choices=("L1", "auto"),
        default="L1",
        help=(
            "--by-chapter 模式的章节拆法（默认 L1）。\n"
            "  L1   : 按 PDF 原生 L1 章 N 次独立 API 调用，每章 1 个 .md + L2 子节合并进 L1。"
            "长 PDF 首选；自带 File API 缓存，节省 N-1 次 PDF 上传。\n"
            "  auto : 单次 API 调用，Gemini 自决粒度（仅适用 ≤ 50 页短 PDF）；"
            "保留旧行为以便对比。超长 PDF 撞 token 限会失败。\n"
            "L1 模式与 --pages 互斥（L1 按章自动切页，不需要 --pages）；"
            "auto 模式可与 --pages 组合拆段。"
        ),
    )
    parser.add_argument(
        "--pages",
        default=None,
        help=(
            "页范围过滤（仅在 --by-chapter --granularity auto 模式下生效），格式 '1-30' / '31-60'。\n"
            "用 PyMuPDF 在调用 Gemini 前切出指定页范围为临时 PDF；"
            "配合 --by-chapter --granularity auto 可拆超长 PDF（先按页切 + 每段内按章节拆）。\n"
            "示例：--pages 1-50 --by-chapter --granularity auto --output out/p1/ "
            "拆前 50 页为按章节的多个 .md。\n"
            "L1 模式下传 --pages 会报错（L1 按 L1 章边界自动切页）。"
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


def call_gemini_structured(
    model, pdf_bytes, prompt, schema, temperature, max_output_tokens=None, file_part=None
):
    # type: (str, bytes, str, dict, float, Optional[int], Optional[object]) -> dict
    """调用 Gemini 结构化输出（response_schema 约束），返回 JSON dict。

    与 call_gemini 的差异：
    - 强制 response_mime_type="application/json" + response_schema=<schema>
    - 返回值是 dict（已 json.loads），不再是 Markdown 文本
    - 同样委托 _gemini_call_with_retry 走统一重试 + 不切模型策略
    - 同样走 inline Part / File API 分流（pdf_bytes > 20 MB 走 File API）

    `file_part`（2026-07-06 L1 模式新增，可选）：由调用方预上传 File API 拿到的 Part
    对象。传非 None 时直接复用（不再走 inline / 重新 upload），用于 L1 模式 N 次调用
    共享同一上传、节省 N-1 次 PDF 上传 token。**仅在 caller 已经持有 file_part 时
    才传**；一般场景保持 None。

    适用 --by-chapter 模式。
    """
    import json  # 局部 import，容错 JSON 解析失败时给更清晰的错误

    client = genai.Client()

    if file_part is not None:
        # L1 模式复用已上传 PDF：直接引用 file_part，零额外上传
        contents = [file_part, prompt]
    elif len(pdf_bytes) <= MAX_PDF_BYTES_INLINE:
        contents = [
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ]
    else:
        sys.stderr.write("INFO: PDF 超过 20 MB，走 File API 上传。\n      (文件会在 Google 服务端保留 48 小时)\n")
        uploaded = client.files.upload(
            file=pdf_bytes,
            config={"display_name": "by-chapter-pdf", "mime_type": "application/pdf"},
        )
        contents = [uploaded, prompt]

    config_kwargs = {
        "temperature": temperature,
        "response_mime_type": "application/json",
        "response_schema": schema,
    }
    if max_output_tokens is not None:
        config_kwargs["max_output_tokens"] = max_output_tokens
    config = types.GenerateContentConfig(**config_kwargs)

    response = _gemini_call_with_retry(client, model, contents, config, label="by-chapter 调用")

    text = getattr(response, "text", None)
    if not text:
        sys.stderr.write(f"ERROR: Gemini 返回为空。原始 response: {response}\n")
        sys.exit(3)

    # 截断检测（撞 FULL_MAX_OUTPUT_TOKENS 上限 → 末位章节可能不完整）
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        out_tokens = getattr(usage, "candidates_token_count", 0) or 0
        if max_output_tokens and out_tokens >= max_output_tokens - 10:
            sys.stderr.write(
                f"WARN: 输出撞 token 上限（{out_tokens}/{max_output_tokens}），"
                "末位章节可能截断。默认已走 pro-preview，建议用 --pages 拆段重跑末段。\n"
            )

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 把原始响应写到磁盘以便排查
        debug_path = "/tmp/gemini-by-chapter-debug.json"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(text)
        sys.stderr.write(
            f"ERROR: Gemini 返回的不是合法 JSON: {e}\n"
            f"       原始响应已写到 {debug_path}（长度 {len(text)} 字符）\n"
            "       可能原因：1) PDF 内容超出 schema 容量；2) 模型未严格遵守 schema。\n"
            "       默认已走 pro-preview，建议用 --pages 拆段重试。\n"
        )
        sys.exit(3)


# ----------------------------------------------------------------------------
# --by-chapter 模式 helpers：slug 化、页范围切 PDF、章节截尾检测
# ----------------------------------------------------------------------------


def slugify_chapter(title, used_slugs=None):
    # type: (str, Optional[set]) -> str
    """章节标题 → 文件安全 slug；保留中英文 + 数字，处理冲突。

    - 中文保留（CJK 范围 \\u4e00-\\u9fff）；ASCII 转小写
    - 非字母数字中文字符转 `-`；连续 `-` 合并
    - 长度上限 60 字符
    - used_slugs 用于冲突检测：同名 chapter 自动追加 `-2` / `-3` 后缀
    """
    s = re.sub(r"[^a-zA-Z0-9一-鿿-]+", "-", title.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    s = s[:60] or "chapter"
    if used_slugs is None:
        return s
    candidate = s
    n = 2
    while candidate in used_slugs:
        candidate = f"{s[: 60 - len(f'-{n}')]}-{n}" if len(s) + len(f"-{n}") > 60 else f"{s}-{n}"
        n += 1
        if n > 999:  # 防死循环
            break
    return candidate


def _filter_pdf_pages(pdf_bytes, pages_range):
    # type: (bytes, str) -> bytes
    """按 'start-end' 切出指定页范围为新 PDF 的 bytes。

    需要 PyMuPDF；缺失时报错退出。
    页号 1-indexed（含两端），与人类阅读习惯一致。
    """
    try:
        import fitz  # type: ignore
    except ImportError:
        sys.stderr.write(
            "ERROR: --pages 需要 PyMuPDF（pymupdf），未安装。\n"
            "       pip install --user --break-system-packages pymupdf\n"
        )
        sys.exit(2)

    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", pages_range)
    if not m:
        sys.stderr.write(f"ERROR: --pages 格式应为 'start-end'（如 '1-30'），收到: {pages_range!r}\n")
        sys.exit(2)

    start, end = int(m.group(1)), int(m.group(2))
    if start < 1 or end < start:
        sys.stderr.write(f"ERROR: --pages 范围非法: {pages_range!r}（start ≥ 1 且 end ≥ start）\n")
        sys.exit(2)

    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = src.page_count
    if end > total:
        sys.stderr.write(f"WARN: --pages 结束页 {end} 超过 PDF 总页数 {total}，自动截到 {total}。\n")
        end = total

    dst = fitz.open()
    # PyMuPDF 的 insert_pdf 用 0-indexed，[from_page, to_page] 均含
    dst.insert_pdf(src, from_page=start - 1, to_page=end - 1)
    out_bytes = dst.tobytes()
    dst.close()
    src.close()

    sys.stderr.write(f"INFO: --pages {start}-{end} 切出 {end - start + 1} 页（PDF 原 {total} 页）\n")
    return out_bytes


def _looks_truncated_chapter(content):
    # type: (str) -> bool
    """粗略检测章节 content 是否在句子中间被截断（用于末位章节截断 WARN）。

    启发式：
    - 末尾不是常见的 markdown 闭合符（`.` / `。` / `!` / `！` / `?` / `？` /
      ``` / `)` / `]` / `>` 等）
    - 且末尾 50 字符内没有完整闭合代码块 / 表格行
    """
    if not content or len(content) < 100:
        return False
    s = content.rstrip()
    if not s:
        return False
    # 末字符是 markdown 闭合符 → 视为完整
    closing = {"。", ".", "!", "！", "?", "？", "`", ")", "]", ">", "|", "*", "#"}
    if s[-1] in closing:
        return False
    # 末 100 字符含未闭合 ``` 代码块 → 可能截断
    last_block = s[-100:]
    fence_count = last_block.count("```")
    if fence_count % 2 == 1:
        return True
    # 末 50 字符含未闭合 | 表格行 → 可能截断
    last_line = s.rstrip("\n").split("\n")[-1] if "\n" in s else s
    if last_line.strip().startswith("|") and not last_line.strip().endswith("|"):
        return True
    return True  # 末字符不闭合 + 走过基本检查 → 视为可能截断


def _upload_pdf_to_file_api(pdf_bytes, display_name="by-chapter-pdf"):
    # type: (bytes, str) -> object
    """上传 PDF 到 File API，返回可供 `client.files.upload` / `Part.from_uri` 用的 Part。

    L1 模式 N 次调用共享同一上传 → 节省 N-1 次 PDF 上传 token。失败时直接抛
    (不静默退 inline —— L1 模式需要 Part.from_uri 引用 file API)。
    """
    client = genai.Client()
    sys.stderr.write(
        f"INFO: L1 模式预上传 PDF ({len(pdf_bytes) / 1024 / 1024:.1f}MB) 到 File API（48h 保留）。\n"
    )
    uploaded = client.files.upload(
        file=pdf_bytes,
        config={"display_name": display_name, "mime_type": "application/pdf"},
    )
    return uploaded


def _read_pdf_toc(pdf_bytes):
    # type: (bytes) -> list
    """PyMuPDF 读 PDF 的 TOC（PDF 内嵌的 bookmarks / outline）。

    返回 list of `(level, title, page_1indexed)`，缺 TOC 时返回 []。失败抛异常。

    与 `--granularity L1` 配套：调用方按 level==1 过滤出 L1 章列表。L1 章末尾页
    是到下一个 L1 章起始页 - 1（最后一章到 PDF 总页数）。
    """
    import fitz  # type: ignore  # noqa: F811

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        toc = doc.get_toc() or []
    finally:
        doc.close()
    return toc


def _cleanup_stub_files(out_dir, threshold=100, keep_filename="00-index.md"):
    # type: (str, int, str) -> int
    """清理 out_dir 下 < threshold 字节的 .md stub 文件（视为模型放弃的章节）。

    返回删除的文件数。`keep_filename` 永不删（默认 00-index.md）。每个被删文件
    写一行 stderr INFO（汇总在最后一行 WARN）。
    """
    removed = 0
    for fname in sorted(os.listdir(out_dir)):
        if not fname.endswith(".md") or fname == keep_filename:
            continue
        fpath = os.path.join(out_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            if os.path.getsize(fpath) < threshold:
                os.remove(fpath)
                removed += 1
        except OSError:
            # 文件 IO 异常不影响整体
            continue
    if removed:
        sys.stderr.write(
            f"WARN: 清理 {removed} 个 < {threshold}B stub 章节（疑似模型放弃）。\n"
            "      （00-index.md 仍保留原引用，必要时手删或重跑对应页范围）\n"
        )
    return removed


def _run_by_chapter_one_call(
    pdf_bytes, model, temperature, focus, out_dir, file_part=None, label=""
):
    # type: (bytes, str, float, str, str, Optional[object], str) -> dict
    """单次 by-chapter API 调用：调 Gemini + 写各章节 .md，返回 metadata。

    与原 `_run_by_chapter_mode` 的核心循环等价，但**不**写 00-index.md（index 由
    caller 写），且**不**做 stub 清理（caller 在合并后统一清理）。

    返回 dict：
        {
          "chapters": [
            {"title": str, "level": int, "content": str,
             "filename": "01-<slug>.md", "truncated": bool, "slug": str},
            ...
          ],
          "truncated_titles": [str, ...],
          "raw_count": int,
        }

    参数:
        pdf_bytes    -- PDF 二进制（整本或 --pages 切过的）
        model / temperature / focus  -- Gemini 调用参数
        out_dir      -- 章节 .md 写出目录（已存在；caller makedirs）
        file_part    -- 预上传的 File API Part（L1 模式复用）；None 走 inline/File API 自分流
        label        -- 调度标签（写 stderr 日志用，如 "L1-3/14 硬件架构"）
    """
    if label:
        sys.stderr.write(f"INFO: --by-chapter 调用 {label} 开始\n")

    # 构造 prompt
    prompt = BY_CHAPTER_PROMPT
    if focus:
        prompt = prompt + FOCUS_INJECTION_FULL.format(focus=focus.strip())

    # 调 Gemini 结构化输出
    data = call_gemini_structured(
        model,
        pdf_bytes,
        prompt,
        CHAPTER_SCHEMA,
        temperature,
        max_output_tokens=FULL_MAX_OUTPUT_TOKENS,
        file_part=file_part,
    )

    chapters = data.get("chapters") or []
    if not isinstance(chapters, list) or not chapters:
        # L1 模式下走"失败 L1 写占位"路径，auto 模式依然 sys.exit
        raise ValueError(
            f"Gemini 返回的 chapters 字段为空或非数组 (data keys: {list(data.keys())})"
        )

    used_slugs = set()
    written = []
    truncated_titles = []

    for i, ch in enumerate(chapters, 1):
        title = str(ch.get("title") or f"chapter-{i}").strip()
        level = int(ch.get("level") or 2)
        content = str(ch.get("content") or "").strip()

        # 防御：content 里如果以 "# " 开头（H1 越界），剥掉首行 H1
        content = re.sub(r"^#\s+[^\n]*\n+", "", content, count=1)

        # 截断检测（仅末位章节有效）
        is_last = i == len(chapters)
        truncated = is_last and _looks_truncated_chapter(content)
        if truncated:
            truncated_titles.append(title)
            content += "\n\n<!-- ⚠ 末位章节疑似截断（content 末尾未正常闭合）；"
            content += "默认已走 pro-preview，建议用 --pages 拆段重跑末段 -->\n"

        slug = slugify_chapter(title, used_slugs)
        used_slugs.add(slug)
        fname = f"{i:02d}-{slug}.md"
        out_path = os.path.join(out_dir, fname)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        written.append(
            {"title": title, "level": level, "content": content,
             "filename": fname, "truncated": truncated, "slug": slug}
        )

    return {
        "chapters": written,
        "truncated_titles": truncated_titles,
        "raw_count": len(chapters),
    }


def _run_by_chapter_mode(args):
    # type: (argparse.Namespace) -> int
    """--by-chapter --granularity auto 模式：单次 API 调用 + JSON 结构化输出 + 按章节拆文件。

    输入约定:
        args.pdf         -- PDF 路径
        args.output      -- 输出目录（写 00-index.md + 各章节 .md）
        args.pages       -- 可选 'start-end'，先用 PyMuPDF 切页范围
        args.model / args.temperature / args.focus  -- Gemini 调用参数

    写出:
        <output>/00-index.md       -- TOC（按 level 缩进）
        <output>/01-<slug>.md      -- 第 1 章 markdown
        <output>/02-<slug>.md      -- 第 2 章 markdown
        ...

    关键决策:
    - 单次 API 调用，受 FULL_MAX_OUTPUT_TOKENS (65536) 限制
    - 走 Gemini response_schema 强制 JSON 结构，避免 delimiter 法的脆弱性
    - 末位章节若截断，写 stderr WARN + 在 00-index.md 末尾追加截断标记
    - 与 --full 互斥（已隐含全文级）；与 --pages 组合可拆超长 PDF
    - 与 --granularity L1 互斥（auto 仅适用 ≤ 50 页短 PDF；>50 页走 pre-flight 拦截）
    """
    # 必填校验
    if not args.output:
        sys.stderr.write(
            "ERROR: --by-chapter 模式必须配合 --output 使用\n"
            "       （--output 视作输出目录，写 00-index.md + 各章节 .md）。\n"
        )
        sys.exit(2)

    # 校验 --full / --by-chapter 互斥（main() 早检查过，这里防御）
    if args.full:
        sys.stderr.write("ERROR: --by-chapter 与 --full 互斥，请只传一个。\n")
        sys.exit(2)

    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)

    # 1) 校验输入（隐式 GEMINI_API_KEY + PDF 完整性）
    model, pdf_bytes, focus = validate_inputs(args)

    # 2) 若指定 --pages，先切页范围（仅 auto 模式支持）
    if args.pages:
        pdf_bytes = _filter_pdf_pages(pdf_bytes, args.pages)

    pdf_size_mb = len(pdf_bytes) / 1024 / 1024
    sys.stderr.write(
        f"INFO: --by-chapter --granularity auto 开始 (PDF {pdf_size_mb:.1f}MB, 模型 {model}, max_output_tokens={FULL_MAX_OUTPUT_TOKENS})\n"
    )

    # 3) 单次调用 + 写章节文件（提取到 _run_by_chapter_one_call）
    result = _run_by_chapter_one_call(
        pdf_bytes, model, args.temperature, focus, out_dir, file_part=None, label=""
    )
    written_files = result["chapters"]
    truncated_chapters = result["truncated_titles"]

    # 4) 写 master TOC
    toc_lines = ["# 目录", ""]
    for entry in written_files:
        indent = "  " * max(0, entry["level"] - 1)
        toc_marker = " ⚠" if entry["truncated"] else ""
        toc_lines.append(f"{indent}- [{entry['title']}{toc_marker}]({entry['filename']})")

    if truncated_chapters:
        toc_lines.append("")
        toc_lines.append("## 截断告警")
        toc_lines.append("")
        toc_lines.append("以下章节 content 末尾疑似未正常闭合，可能受 65536 输出 token 上限影响：")
        for t in truncated_chapters:
            toc_lines.append(f"- {t}")
        toc_lines.append("")
        toc_lines.append(
            "建议处置：默认已走 pro-preview；用 `--pages start-end` 拆出末段重跑，保留前段结果。"
        )
    _write_text(os.path.join(out_dir, "00-index.md"), "\n".join(toc_lines) + "\n")

    # 5) Stub 清理（< 100B 文件视为模型放弃的章节，删 + WARN）
    _cleanup_stub_files(out_dir)

    # 6) 总结报告
    total_chars = sum(
        os.path.getsize(os.path.join(out_dir, entry["filename"]))
        for entry in written_files
        if os.path.isfile(os.path.join(out_dir, entry["filename"]))
    )
    kept = [e for e in written_files if os.path.isfile(os.path.join(out_dir, e["filename"]))]
    sys.stderr.write(
        f"OK: --by-chapter --granularity auto 完成 → {out_dir}/\n"
        f"     拆出 {len(kept)} 个章节 + 1 个索引（{len(kept)} 个 .md + 00-index.md）\n"
        f"     总大小 {total_chars / 1024:.1f} KB（平均每章 {total_chars // max(len(kept), 1) / 1024:.1f} KB）\n"
    )
    if truncated_chapters:
        sys.stderr.write(
            f"WARN: {len(truncated_chapters)} 个末位章节疑似截断，详见 {out_dir}/00-index.md 截断告警段。\n"
        )

    return 0


def _run_by_chapter_l1_orchestrator(args):
    # type: (argparse.Namespace) -> int
    """--by-chapter --granularity L1 模式（2026-07-06 新增，默认 by-chapter 行为）。

    流程：
      1. PyMuPDF 读 TOC（bookmarks / outline），过滤"目  录"等空 L1，取 L1 列表
      2. PDF > 20MB → File API 预上传 1 次；后续 N 次调用复用 file_part
      3. 对每个 L1 章串行：
         a. PyMuPDF 切 [start_page, next_L1_start - 1] 页范围
         b. _run_by_chapter_one_call → 拿 K_i 个子章节（L2 为主，可能有 L3）
         c. 把 K_i 个子章节合并到 1 个 .md：## <L1.title> + ### <L2.title> + content
         d. 失败 → 写 FAILED 占位 .md + 继续
      4. 写 00-index.md（N_L1 行 TOC，FAILED 项标 ⚠）
      5. Stub 清理（< 100B 文件）

    产物 layout：
        <output>/
        ├── 00-index.md
        ├── 01-<L1-slug>.md      （## L1.title + ### L2.title + content）
        ├── 02-<L1-slug>.md
        ├── ...
        └── NN-<L1-slug>.md      （最后一章，末尾可能含 L1 截断 ⚠）

    关键决策（SSOT: references/full-mode-contract.md §by-chapter §L1 模式）：
    - 走 File API 缓存，节省 N-1 次 PDF 上传（85% 输入 token）
    - 单个 L1 失败不中断（写 FAILED 占位 + 继续后续）
    - TOC 读不出 / pymupdf 缺 → 报错 + 自动 fallback auto 模式
    - 与 --pages 互斥（L1 按 L1 章边界自动切页，无需 --pages）
    """
    # 必填校验
    if not args.output:
        sys.stderr.write(
            "ERROR: --by-chapter --granularity L1 模式必须配合 --output 使用\n"
            "       （--output 视作输出目录，写 00-index.md + 各 L1 章 .md）。\n"
        )
        sys.exit(2)

    # 与 --full 互斥（main() 早检查过，这里防御）
    if args.full:
        sys.stderr.write("ERROR: --by-chapter 与 --full 互斥，请只传一个。\n")
        sys.exit(2)

    # L1 模式与 --pages 互斥
    if args.pages:
        sys.stderr.write(
            "ERROR: --by-chapter --granularity L1 模式与 --pages 互斥。\n"
            "       L1 模式按 PDF 原生 L1 章边界自动切页，无需 --pages。\n"
            "       若要按自定义页段拆，请用 --granularity auto。\n"
        )
        sys.exit(2)

    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)

    # 1) 校验输入
    model, pdf_bytes, focus = validate_inputs(args)

    if not _HAS_PYMUPDF:
        sys.stderr.write(
            "ERROR: --by-chapter --granularity L1 需要 PyMuPDF（pymupdf），未安装。\n"
            "       pip install --user --break-system-packages pymupdf\n"
            "       或改用 --granularity auto 走单次调用（不需 pymupdf）。\n"
        )
        sys.exit(2)

    # 2) 读 TOC → 取 L1 列表
    try:
        toc = _read_pdf_toc(pdf_bytes)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            f"WARN: 读 PDF TOC 失败: {e}\n"
            "      自动 fallback 到 --granularity auto 模式。\n"
        )
        args.granularity = "auto"
        return _run_by_chapter_mode(args)

    l1_list = [
        (title, page)
        for level, title, page in toc
        if level == 1 and title.strip() not in ("目  录", "目录", "Table of Contents", "Contents")
    ]
    if not l1_list:
        sys.stderr.write(
            "WARN: PDF TOC 里没有 L1 章（可能 PDF 未嵌 bookmarks / 仅含封面 + 目录）。\n"
            "      自动 fallback 到 --granularity auto 模式。\n"
        )
        args.granularity = "auto"
        return _run_by_chapter_mode(args)

    # 取 PDF 总页数（用于最后一章的结束页）
    import fitz  # type: ignore  # noqa: F811
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = doc.page_count
    finally:
        doc.close()

    n_l1 = len(l1_list)
    pdf_size_mb = len(pdf_bytes) / 1024 / 1024
    sys.stderr.write(
        f"INFO: --by-chapter --granularity L1 开始 (PDF {pdf_size_mb:.1f}MB, {total_pages} 页, "
        f"{n_l1} 个 L1 章, 模型 {model}, max_output_tokens={FULL_MAX_OUTPUT_TOKENS})\n"
    )

    # 3) 预上传到 File API（如需要）
    file_part = None
    if len(pdf_bytes) > MAX_PDF_BYTES_INLINE:
        try:
            file_part = _upload_pdf_to_file_api(pdf_bytes)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(
                f"ERROR: File API 上传失败: {e}\n"
                "       L1 模式依赖 File API 缓存；失败不静默退 inline（inline 无法跨调用复用）。\n"
                "       处置：1) 重试  2) 用 --granularity auto 走单次调用  3) 缩小 PDF 后重试\n"
            )
            return 3
    else:
        sys.stderr.write(
            "INFO: PDF < 20MB，每次调用走 inline Part（不需 File API 缓存）。\n"
        )

    # 4) 逐 L1 章串行调用
    used_slugs = set()
    l1_written = []  # [(filename, l1_title, l1_page, status), ...]
    used_temp_files = []  # 临时子目录，待 L1 全部跑完一起删

    for idx, (l1_title, l1_start) in enumerate(l1_list, 1):
        # 算 L1 章的页范围
        if idx < n_l1:
            l1_end = l1_list[idx][1] - 1  # 下一 L1 章起始页 - 1
        else:
            l1_end = total_pages  # 最后一章到 PDF 末尾
        if l1_end < l1_start:
            l1_end = l1_start  # 0 章防御

        # 切页范围到临时目录（用 PyMuPDF 走已有 helper）
        pages_range = f"{l1_start}-{l1_end}"
        try:
            l1_pdf_bytes = _filter_pdf_pages(pdf_bytes, pages_range)
        except SystemExit:
            # _filter_pdf_pages 失败 → 标 FAILED + 继续
            slug = slugify_chapter(l1_title, used_slugs)
            used_slugs.add(slug)
            failed_fname = f"{idx:02d}-FAILED-{slug}.md"
            failed_path = os.path.join(out_dir, failed_fname)
            with open(failed_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# {l1_title}\n\n"
                    f"<!-- ⚠ L1 章失败：页范围 {pages_range} 切割失败；见 stderr -->\n"
                )
            l1_written.append((failed_fname, l1_title, l1_start, "failed"))
            continue

        # 用临时子目录存 K_i 个子章节文件，跑完一起合并 + 删
        import shutil
        import tempfile
        tmp_subdir = tempfile.mkdtemp(prefix="by-chapter-l1-")
        used_temp_files.append(tmp_subdir)
        label = f"L1-{idx}/{n_l1} '{l1_title}' (页 {pages_range})"

        try:
            result = _run_by_chapter_one_call(
                l1_pdf_bytes, model, args.temperature, focus, tmp_subdir,
                file_part=file_part, label=label,
            )
        except Exception as e:  # noqa: BLE001
            # L1 调用失败 → 写 FAILED 占位 + 继续后续
            slug = slugify_chapter(l1_title, used_slugs)
            used_slugs.add(slug)
            failed_fname = f"{idx:02d}-FAILED-{slug}.md"
            failed_path = os.path.join(out_dir, failed_fname)
            with open(failed_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# {l1_title}\n\n"
                    f"<!-- ⚠ L1 章失败：{type(e).__name__}: {e} -->\n"
                    f"<!-- 页范围 {pages_range}；可单独重跑：--pages {pages_range} --granularity auto -->\n"
                )
            l1_written.append((failed_fname, l1_title, l1_start, "failed"))
            sys.stderr.write(f"WARN: L1 章 {idx}/{n_l1} '{l1_title}' 失败: {e}（写 FAILED 占位 + 继续）\n")
            continue

        # 5) 合并 K_i 个子章节到 1 个 L1 .md
        slug = slugify_chapter(l1_title, used_slugs)
        used_slugs.add(slug)
        l1_fname = f"{idx:02d}-{slug}.md"
        l1_path = os.path.join(out_dir, l1_fname)

        # L1 合并策略：
        # - 第 1 个子章节若是 L1 level（1 或 2），content 已是 L1 主体（无 L1 标题行）
        # - 把第 1 个子章节的 content 升 1 级（## L1 主标题，### L2 子节）
        # - 后续子章节（L2/L3+）保持原 ## / ### 关系
        # 简化实现：直接写 L1 title 作为 ## 标题 + 所有子章节 content 拼起来
        sub = result["chapters"]
        merged_lines = [f"## {l1_title}", ""]
        truncated_any = False
        if not sub:
            # 模型返回空 → 写空 stub
            merged_lines.append(
                f"<!-- ⚠ L1 章 '{l1_title}' 返回空内容；页范围 {pages_range} -->\n"
            )
        else:
            for j, ch in enumerate(sub):
                sub_content = ch["content"].strip()
                # 第一个子章节：去掉其首行 H1/H2（如果存在），主体接在 L1 标题下
                if j == 0 and sub_content:
                    sub_content = re.sub(r"^#{1,3}\s+[^\n]*\n+", "", sub_content, count=1)
                if ch["truncated"]:
                    truncated_any = True
                if sub_content:
                    merged_lines.append(sub_content)
                    merged_lines.append("")

        if truncated_any:
            merged_lines.append(
                "<!-- ⚠ 该 L1 章含截断子章节（末位章节 content 末尾未正常闭合）；"
                "默认已走 pro-preview；L1 模式按章 ≤ 50 页时通常不会截断 -->\n"
            )

        with open(l1_path, "w", encoding="utf-8") as f:
            f.write("\n".join(merged_lines).rstrip() + "\n")
        l1_written.append((l1_fname, l1_title, l1_start, "ok"))

    # 6) 写 master TOC（N_L1 行）
    toc_lines = ["# 目录", ""]
    for fname, title, page, status in l1_written:
        marker = " ⚠FAILED" if status == "failed" else ""
        toc_lines.append(f"- [{title}（p.{page}）{marker}]({fname})")
    _write_text(os.path.join(out_dir, "00-index.md"), "\n".join(toc_lines) + "\n")

    # 7) Stub 清理
    _cleanup_stub_files(out_dir)

    # 8) 清理临时子目录
    for tmp_dir in used_temp_files:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except OSError:
            pass

    # 9) 总结报告
    kept = [(f, t, p) for f, t, p, s in l1_written if s == "ok"]
    failed = [(f, t, p) for f, t, p, s in l1_written if s == "failed"]
    total_chars = sum(
        os.path.getsize(os.path.join(out_dir, f)) for f, _, _ in kept
        if os.path.isfile(os.path.join(out_dir, f))
    )
    sys.stderr.write(
        f"OK: --by-chapter --granularity L1 完成 → {out_dir}/\n"
        f"     {n_l1} 个 L1 章（{len(kept)} OK + {len(failed)} FAILED）+ 1 个索引（00-index.md）\n"
        f"     总大小 {total_chars / 1024:.1f} KB（平均每 L1 {total_chars // max(len(kept), 1) / 1024:.1f} KB）\n"
    )
    if failed:
        sys.stderr.write(
            f"WARN: {len(failed)} 个 L1 章失败：{', '.join(t for _, t, _ in failed)}\n"
            "      失败项已写 FAILED-<slug>.md 占位；可单独用 --pages 范围 + auto 重跑\n"
        )

    return 0


def _write_text(path, text):
    """小工具：写文本到指定路径（os.makedirs 处理父目录）。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


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
        sys.stderr.write("INFO: {0} 已存在,用户显式 --force-full,覆盖现有 full 抽取。\n".format(full_md_path))
        return
    sys.stderr.write(
        "ERROR: {0} 已存在;full 抽取默认拒绝覆盖以防丢失下游已经多次引用的 raw。\n"
        "       若确认要覆盖,加 --force-full 显式允许。\n".format(full_md_path)
    )
    sys.exit(1)


def _run_full_mode(args):  # type: (argparse.Namespace) -> int
    """--full 模式独立子流程:产出**一份** full PDF→Markdown 转写 + raw-compatible layout。

    2026-07-07 翻面:原设计是"单次调用同时产 quick summary + full"双产物,
    现翻面为"单产物 full"——与 manual / whitepaper / book 的 full 风格对齐,
    4 类 full 全部是"单文件 + LLM 消费底座"。想看 quick summary + 带图请跑
    `--type paper` 默认（quick 模式）；要看 PNG 走 `--extract-figures` 单跑。

    输入约定:
        args.pdf         -- PDF 路径
        args.output      -- wiki 仓根(下含 raw/)
        args.slug / --slug / 自动从 PDF 文件名推断(见 slug_from_path)
        args.model / args.temperature / args.focus  -- Gemini 调用参数
        args.force_full                              -- 允许覆盖冲突

    写出:
        <wiki_root>/raw/papers/<slug>.full.md        -- full 模板产物(自包含,无 PNG 配套)
        <wiki_root>/raw/assets/<slug>/fig-NN.png     -- 由 `--extract-figures` 单跑或 quick 模式产生,full 不写

    关键决策 SSOT:../../MEMORY/gemini-pdf-summary-paper-full-single-output.md

    2026-06-30 第二轮翻面:full 模式不再落 PNG / 不跑 Stage 2 / 不创建
    raw/assets/<slug>/ 目录。架构/概念图直接 mermaid 画在 markdown 里,
    数据可视化图转 markdown 表格(详见 prompt-template.md full 模板)。quick
    模式 + `--extract-figures` 单跑仍走落 PNG 路径。

    2026-07-07 翻面:full 模式不再产 quick summary。`--extract-figures` 单跑
    仍是产出 PNG 的合法路径；用户要 quick + 带图就走 `--type paper` 默认不加 `--full`。
    """
    # 必填校验
    if not args.output:
        sys.stderr.write(
            "ERROR: --full 模式必须配合 --output 使用(--output 视为 wiki 仓根,\n"
            "       产物写到 <wiki_root>/raw/papers/<slug>.full.md 单文件,不写 .quick.md;\n"
            "       full 模式不落 PNG;想看 PNG 走 quick 模式或 --extract-figures 单跑)。\n"
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
    # 2026-07-07 翻面:full 模式只产 full.md,不再写 quick.md;也不再创建 raw/assets/<slug>/ 目录

    full_md_path = os.path.join(papers_dir, "{0}.full.md".format(slug))

    # 冲突检测(SSOT §3):full 抽取默认拒绝覆盖,保护下游已多次引用的 raw
    detect_full_overwrite(full_md_path, args.force_full)

    # 1) 校验输入(隐式 GEMINI_API_KEY + PDF 完整性)
    model, pdf_bytes, focus = validate_inputs(args)

    # 2) 2026-07-07 翻面:full 模式只调用 Gemini 一次(产物单份 full.md);
    #    想看 quick summary 请跑 --type paper 默认(quick 模式)。
    sys.stderr.write(
        "INFO: --full 模式开始 (slug={slug});产物落 raw-compatible layout ({wiki_root}/raw/papers/<slug>.full.md)\n".format(
            slug=slug, wiki_root=wiki_root
        )
    )
    sys.stderr.write(
        f"INFO: 调用 Gemini (full 模板 = PDF→Markdown 全量转写, max_output_tokens={FULL_MAX_OUTPUT_TOKENS})\n"
    )
    full_prompt = build_prompt(focus, doc_type="paper", mode="full")
    # max_output_tokens=65536(SSOT: FULL_MAX_OUTPUT_TOKENS 模块常量),避免
    # 撞顶截断尾部章节(决策背景见 prompt-template.md ## 全文级抽取模板
    # 头部 2026-06-30 加固的"完整性 > 篇幅"block)。
    full_md = call_gemini(
        model,
        pdf_bytes,
        full_prompt,
        args.temperature,
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

    # 4) 2026-07-07 翻面:full 模式只写一份 .md 到 raw/papers/
    with open(full_md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
        if not full_md.endswith("\n"):
            f.write("\n")
    sys.stderr.write("OK: full 抽取已写入 {0} ({1} 字符, 模型 {2})\n".format(full_md_path, len(full_md), model))

    # 5.5) full 模式内容完整性自检(2026-06-30 加固;2026-07-05 扩 manual/whitepaper/book):
    # 防止模型撞 token 截断或偷懒。WARN/FAIL 写 stderr,不阻塞退出(同
    # self_check_figures 模式)。paper full 走 _check_paper_full_content。
    try:
        check_result = self_check_full_content(full_md, doc_type="paper")
        sys.stderr.write("INFO: " + check_result["report"] + "\n")
        for w in check_result.get("warnings", []):
            sys.stderr.write("WARN: " + w + "\n")
        for fl in check_result.get("failures", []):
            sys.stderr.write("FAIL: " + fl + "\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"WARN: self_check_full_content 异常: {e}(自检未跑全,不影响主流程)\n")

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
            sys.stderr.write(f"ERROR: auto-detect 失败: {e}\n       请显式传 --type {VALID_TYPES} 中的一个。\n")
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
    # - book 仅支持 full 风格：自动打开 args.full
    # - manual / whitepaper / book 不抽原始图：自动打开 args.no_figures（且忽略 --extract-figures）；
    #   概念用 mermaid / 表格 / ASCII 在 markdown 内直接画
    # - paper 不变（保留原有 quick + full + --extract-figures 行为）
    if doc_type == "book" and not args.full:
        sys.stderr.write("INFO: book 类型仅支持 full 风格，自动启用 --full。\n")
        args.full = True
    if doc_type in ("manual", "whitepaper", "book") and not args.no_figures:
        sys.stderr.write(
            f"INFO: {doc_type} 类型不抽原始 PDF 图（产物给 LLM 消费并进入 llm-wiki 二次 ingest，"
            f"概念用 mermaid / 表格 / ASCII 在 markdown 内直接画）。自动启用 --no-figures。\n"
        )
        args.no_figures = True

    # --full 模式走独立分支;设计决策 SSOT 见
    # ../../MEMORY/gemini-pdf-summary-paper-full-single-output.md（D1）
    # 仅 paper `--full` 走 _run_full_mode；manual / whitepaper / book 即便 args.full=True
    # 也走下方通用分支（prompt_mode 已自动设为 "full"，调用同一条 call_gemini + max_tokens）
    if args.full and doc_type == "paper":
        return _run_full_mode(args)

    # --by-chapter 模式：默认走 L1（2026-07-06 起，按 L1 章 N 次独立调用 + L2 合并），
    # auto 保留旧单次调用行为（仅适用 ≤ 50 页短 PDF；>50 页走 pre-flight 拦截）。
    # 设计决策 SSOT：见 SKILL.md §A Step 1 + references/full-mode-contract.md §by-chapter
    # 与 --full 互斥（--by-chapter 已隐含全文级转写，--full 是 paper 单产物路径）
    if args.by_chapter:
        if args.full:
            sys.stderr.write(
                "ERROR: --by-chapter 与 --full 互斥；请只传一个。\n"
                "       --full 仅 paper 类型有效（产 .full.md 单份）；\n"
                "       --by-chapter 适用于所有 4 类文档（产 N 个章节 + 1 个 TOC）。\n"
            )
            return 2

        # Pre-flight check：auto 模式 + 无 --pages + PDF > 50 页 → 拦截并推荐 L1
        # 失败背景：单次 by-chapter 调用对长 PDF 必撞 FULL_MAX_OUTPUT_TOKENS (65536)
        # 限，30%+ 章节截断（实测华为 OceanDisk 98 页白皮书）。
        if args.granularity == "auto" and not args.pages and _HAS_PYMUPDF:
            try:
                import fitz  # type: ignore  # noqa: F811
                _doc = fitz.open(args.pdf)
                try:
                    _n_pages = _doc.page_count
                finally:
                    _doc.close()
                if _n_pages > 50:
                    sys.stderr.write(
                        f"ERROR: --by-chapter --granularity auto 仅适用 ≤ 50 页 PDF；\n"
                        f"       {args.pdf} 共 {_n_pages} 页，单次调用必撞 65536 token 上限。\n"
                        "       改用 --granularity L1（默认）：按 PDF 原生 L1 章 N 次独立调用，\n"
                        "       每章 ≤ 50 页，撞限概率近 0；自带 File API 缓存。\n"
                    )
                    return 2
            except Exception:  # noqa: BLE001
                # 读 PDF 失败由后续 validate_inputs / 调用层报
                pass

        if args.granularity == "L1":
            return _run_by_chapter_l1_orchestrator(args)
        return _run_by_chapter_mode(args)

    model, pdf_bytes, focus = validate_inputs(args)
    # 全 4 类 prompt 模式路由：
    #   paper          → "quick"（默认）或 "full"（用户传 --full，args.full=True 已上面 early-return）
    #   manual         → "full"（单模板即 full，2026-07-05 翻面）
    #   whitepaper     → "full"（单模板即 full，2026-07-05 翻面）
    #   book           → "full"（args.full 已自动 True，但实际走通用分支）
    prompt_mode = "full" if (args.full or doc_type in ("manual", "whitepaper", "book")) else "quick"
    prompt = build_prompt(focus, doc_type=doc_type, mode=prompt_mode)
    summary_md = call_gemini(
        model,
        pdf_bytes,
        prompt,
        args.temperature,
        max_output_tokens=(FULL_MAX_OUTPUT_TOKENS if prompt_mode == "full" else None),
    )

    # ---- quick 模式默认带图（2026-07-01）：给人看，必须带高质量图 ----
    # Stage 2（--refine-figures 默认 True）用 Gemini 视觉定位精修 bbox + 完整 caption，
    # 保证图质量（代价：每张引用页多一次 Gemini 调用 + ~5-15s）。
    # --no-figures 关闭；--extract-figures 为向后兼容冗余 flag（传了等价默认）。
    if args.extract_figures:
        sys.stderr.write("INFO: --extract-figures 是向后兼容 flag；quick 模式默认就带图，无需显式传。\n")
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
                    # 2026-07-06 拆分：Stage 2 可独立指定模型(--refine-model)，
                    # 默认 None → 跟主 --model 走。允许主总结 pro-preview +
                    # Stage 2 flash-lite 的"按场景拆模型"配置。
                    stage2_model = args.refine_model or model
                    if stage2_model != model:
                        sys.stderr.write(
                            f"INFO: Stage 2 视觉定位使用独立模型 {stage2_model}（主模型 {model}）\n"
                        )
                    visual_bbox_map = call_gemini_for_visual_bbox(args.pdf, page_to_png, stage2_model, args.temperature)
                    # caption 写到 image alt（v3.2）；Stage 2 读到的完整 caption 覆盖 Stage 1 估算
                    summary_md = insert_caption_after_figure(summary_md, visual_bbox_map)
                    # 2026-07-06 加 Stage 2 结果摘要(2026-07-06 测试暴露：Stage 2 单页失败只打
                    # WARN,用户无法判断整体是否成功;此处汇总 N 页 / M 个图,让用户一眼看清
                    # 走了 Stage 2 还是回退到 Stage 1 caption-based bbox)
                    n_pages = len(page_to_png)
                    n_bbox = len(visual_bbox_map)
                    if n_bbox == 0 and n_pages > 0:
                        sys.stderr.write(
                            f"WARN: Stage 2 {n_pages} 页全部失败/无结果,"
                            f"回退到 Stage 1 caption-based bbox 导出图(精度低于视觉定位)。\n"
                            f"      可考虑: 1) 稍后重试  2) --refine-model <轻量模型> 降低 503 概率\n"
                            f"               3) --no-refine-figures 跳过 Stage 2 走纯 Stage 1\n"
                        )
                    elif n_bbox < n_pages:
                        # 部分页失败,仅提示(Stage 1 已兜底),不阻塞
                        sys.stderr.write(
                            f"INFO: Stage 2 {n_pages} 页中 {n_bbox} 页有视觉定位结果,"
                            f"其余页回退 Stage 1 caption-based bbox。\n"
                        )
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
        summary_md = embed_figure_refs(summary_md, ref_to_relpath, ref_to_full_for_wrap, ref_to_dim=ref_to_dim)
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
            sys.stderr.write("WARN: stdout 模式无法导出图，PDF 图引用已清理。要看图请加 --output <dir>。\n")
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

    # ---- full 模式内容完整性自检(2026-07-05 扩展)----
    # paper full 已在 _run_full_mode 末尾跑过 _check_paper_full_content；
    # 这里处理 manual / whitepaper / book 走通用分支后的自检。
    # 通用分支(prompt_mode="full" + doc_type in manual/whitepaper/book)产物走类型专属检查。
    if prompt_mode == "full" and doc_type in ("manual", "whitepaper", "book"):
        try:
            check_result = self_check_full_content(summary_md, doc_type=doc_type)
            sys.stderr.write("INFO: " + check_result["report"] + "\n")
            for w in check_result.get("warnings", []):
                sys.stderr.write("WARN: " + w + "\n")
            for fl in check_result.get("failures", []):
                sys.stderr.write("FAIL: " + fl + "\n")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"WARN: self_check_full_content ({doc_type}) 异常: {e}(自检未跑全,不影响主流程)\n")

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
    doc_type="paper",
):
    # type: (str, int, int, float, int, str) -> Dict[str, object]
    r"""full 模式产物内容完整性自检——按 doc_type 分发到类型专属子检查。

    **2026-07-05 翻面**：之前只服务于 paper `--full` 模式；现在 manual / whitepaper / book
    也走 full 风格，需要按类型调整检查项：

    - **paper**（默认；保留原 6 项 paper 专属检查）：
      1. H2 ≥ min_h2 (3)
      2. `### Section X.Y` ≥ min_sections (5)
      3. Definition/Theorem/Lemma/Corollary/Algorithm 标注 ≥ 1
      4. `$$...$$` 公式 block ≥ 1
      5. 字符 ≥ min_chars (8000)
      6. "原文未明确"占位比例 > placeholder_ratio_warn (0.5)

    - **manual**：H2 ≥ 3 / H3 ≥ 5（通用 `^###\s+`）/ 表格行 ≥ 5 / 命令代码块 ≥ 1 /
      字符 ≥ 6000 / 占位比例 ≤ 0.5
    - **whitepaper**：H2 ≥ 3 / H3 ≥ 5 / 表格行 ≥ 5 / mermaid block ≥ 1 /
      字符 ≥ 7000 / 占位比例 ≤ 0.5

    - **book**（2026-07-05 暂未启用，调用 `_check_general_full_content`）:
      H2 ≥ 3 / `## Chapter N` 或 `## Part N` ≥ 3 / 字符 ≥ 8000 / 占位比例 ≤ 0.5

    与 self_check_figures 同款 return shape({ok, warnings, failures, report})，
    WARN/FAIL 写 stderr、不阻塞退出。

    Args:
        md_text: 已生成的 full 产物全文
        min_h2: 最少 H2 章节数(默认 3,适用 paper)
        min_sections: 最少 `### Section X.Y` 数(默认 5,适用 paper)
        placeholder_ratio_warn: "原文未明确"占位 / ### Section 比例阈值(默认 0.5)
        min_chars: 字符下限(默认 8000,适用 paper;manual/whitepaper 走类型专属阈值)
        doc_type: 文档类型——"paper"(默认)/"manual"/"whitepaper"/"book"

    Returns:
        {
          "ok": bool,                # True = 0 failures;False = 至少 1 项失败
          "warnings": [str, ...],
          "failures": [str, ...],
          "report": str,             # 单行摘要
        }
    """
    if doc_type == "paper":
        return _check_paper_full_content(
            md_text,
            min_h2=min_h2,
            min_sections=min_sections,
            placeholder_ratio_warn=placeholder_ratio_warn,
            min_chars=min_chars,
        )
    if doc_type == "manual":
        return _check_manual_full_content(md_text)
    if doc_type == "whitepaper":
        return _check_whitepaper_full_content(md_text)
    if doc_type == "book":
        return _check_book_full_content(md_text)
    # 未知 doc_type:fallback 到 paper 检查(行为兼容旧调用)
    sys.stderr.write(f"WARN: self_check_full_content 收到未知 doc_type {doc_type!r}，fallback 到 paper 检查。\n")
    return _check_paper_full_content(
        md_text,
        min_h2=min_h2,
        min_sections=min_sections,
        placeholder_ratio_warn=placeholder_ratio_warn,
        min_chars=min_chars,
    )


def _check_paper_full_content(md_text, min_h2=3, min_sections=5, placeholder_ratio_warn=0.5, min_chars=8000):
    # type: (str, int, int, float, int) -> Dict[str, object]
    """paper full 模式专属自检（2026-06-30 重新定位后，6 项 paper 专属检查）。

    校验项(2026-07-06 放宽正则以匹配 Gemini paper full 实际产出):
    1. 顶层章节保真度：`## ` 或 `### ` 行数合计 ≥ min_h2(默认 3)。
       WARN（学术论文 Gemini 倾向 `### L1` + `#### L2` 体系，旧正则只查 `##` 会
       对 Roman / 阿拉伯数字子节风格的论文全 FAIL，实际产出并未失真，故降级 WARN）
    2. `### Section X.Y` 数量 ≥ min_sections(默认 5,按 eval/evals.json 契约下限)。
       接受三种 PDF 学术论文常见命名格式:`Section X.Y` / Roman 数字 `### I.`
       `### II.` / 阿拉伯数字 `### 1.` `### 2.` 任一即算
    3. Definition/Theorem/Lemma/Algorithm 标注数 ≥ 1（WARN）
    4. 行内公式 `$...$` 或公式 block `$$...$$` 总数 ≥ 1（WARN，paper full 默认
       走 inline 公式与 mermaid 风格一致；block 公式同样接受）
    5. 字符下限 ≥ min_chars(默认 8000)（WARN）
    6. "原文未明确"占位比例 > placeholder_ratio_warn(默认 50%)（WARN）
    """
    import re  # 局部 import,避免污染模块级命名空间

    result = {"ok": True, "warnings": [], "failures": [], "report": ""}

    # ---- 检查 1:顶层章节保真度(2026-07-06:## / ### 合计;FAIL→WARN) ----
    h2_re = re.compile(r"^##\s+", re.MULTILINE)
    h3_re = re.compile(r"^###\s+", re.MULTILINE)
    n_h2 = len(h2_re.findall(md_text))
    n_h3 = len(h3_re.findall(md_text))
    n_top = n_h2 + n_h3
    if n_top < min_h2:
        result["warnings"].append(
            f"paper full 顶层章节数 {n_top}(##={n_h2}+###={n_h3}) < {min_h2},"
            f"PDF 章节未被保真展开"
        )

    # ---- 检查 2:##/### Section X.Y / Roman / 阿拉伯 三选一(2026-07-06 v2) ----
    # Gemini 对 L1 章节层级非确定:有时 ## 有时 ###;同一篇 run 内统一。
    # regex 同时接受 ## / ### 两层,覆盖两种风格任一即可。
    section_res = [
        re.compile(r"^##\s+Section\s+\d+(?:\.\d+)*", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^##\s+[IVX]+\.\s+", re.MULTILINE),  # ## I. ## II. ...
        re.compile(r"^##\s+\d+\.\s+", re.MULTILINE),  # ## 1. ## 2. ...
        re.compile(r"^###\s+Section\s+\d+(?:\.\d+)*", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^###\s+[IVX]+\.\s+", re.MULTILINE),  # ### I. ### II. ...
        re.compile(r"^###\s+\d+\.\s+", re.MULTILINE),  # ### 1. ### 2. ...
    ]
    n_sections = sum(len(rx.findall(md_text)) for rx in section_res)
    if n_sections < min_sections:
        result["warnings"].append(
            f"paper full L1 章节数 {n_sections} < {min_sections}"
            f"(evals.json 契约下限;接受 Section X.Y / Roman / 阿拉伯数字格式)"
        )

    # ---- 检查 3:Definition / Theorem / Lemma / Algorithm 标注数 ----
    label_re = re.compile(
        r"^\s*\*\*(Definition|Theorem|Lemma|Corollary|Algorithm)\s+\d",
        re.MULTILINE,
    )
    n_labels = len(label_re.findall(md_text))
    if n_labels == 0:
        result["warnings"].append(
            "paper full 未发现 Definition/Theorem/Lemma/Corollary/Algorithm 标注(原文无此类标注 或 模型未保真)"
        )

    # ---- 检查 4:行内公式 + block 公式合计(2026-07-06 加 inline) ----
    # 行内公式 $...$ 用 negative lookaround 避免与 block $$...$$ 重复计数
    block_re = re.compile(r"\$\$.+?\$\$", re.DOTALL)
    inline_re = re.compile(r"(?<!\$)\$(?!\$)[^\$\n]+?\$(?!\$)", re.MULTILINE)
    n_blocks = len(block_re.findall(md_text))
    n_inlines = len(inline_re.findall(md_text))
    n_formulas = n_blocks + n_inlines
    if n_formulas == 0:
        result["warnings"].append(
            "paper full 未发现公式(原文无公式 或 模型未保真 LaTeX 转写)"
        )

    # ---- 检查 5:字符下限 ----
    n_chars = len(md_text)
    if n_chars < min_chars:
        result["warnings"].append(f"paper full 字符数 {n_chars} < {min_chars},可能偷懒或撞 token 上限")

    # ---- 检查 6:"原文未明确" 占位比例 ----
    placeholder_count = md_text.count("原文未明确")
    if n_sections > 0:
        ratio = placeholder_count / float(n_sections)
        if ratio > placeholder_ratio_warn:
            result["warnings"].append(
                f"paper full 含 {placeholder_count} 处'原文未明确'占位 / {n_sections} 个 ### Section = {ratio:.0%},"
                f"超过 {placeholder_ratio_warn:.0%} 阈值,可能存在偷懒"
            )

    summary_line = (
        f"Content self-check (paper): top={n_top}(##{n_h2}+###{n_h3}), "
        f"L1={n_sections}, Def+Thm+Lem+Alg={n_labels}, "
        f"formula={n_formulas}($${n_blocks}+$inline${n_inlines}), "
        f"chars={n_chars}, {len(result['warnings'])}w {len(result['failures'])}f"
    )
    result["report"] = summary_line
    return result


def _check_manual_full_content(md_text):
    # type: (str) -> Dict[str, object]
    """manual full 模式自检(2026-07-05)：manual 是 full 风格但有 manual 特有必保真元素。

    校验项:
    1. H2 章节保真度 ≥ 3 (FAIL)
    2. H3 子节数 ≥ 5（通用 `^###\\s+`，manual 章节命名无 Section X.Y 体系）
    3. 表格行数 ≥ 5（manual 核心是参数表 / 错误码表）
    4. 命令 / API / 配置代码块 ≥ 1（```bash / ```yaml / ```json）
    5. 字符下限 ≥ 6000（manual 文档较短；比 paper 8000 略低）
    6. "原文未明确"占位比例 > 0.5 (WARN)
    """
    import re

    result = {"ok": True, "warnings": [], "failures": [], "report": ""}

    # H2
    h2_re = re.compile(r"^##\s+", re.MULTILINE)
    n_h2 = len(h2_re.findall(md_text))
    if n_h2 < 3:
        result["failures"].append(f"manual full H2 章节数 {n_h2} < 3,PDF 章节未被保真展开")
        result["ok"] = False

    # H3 通用
    h3_re = re.compile(r"^###\s+", re.MULTILINE)
    n_h3 = len(h3_re.findall(md_text))
    if n_h3 < 5:
        result["warnings"].append(f"manual full H3 子节数 {n_h3} < 5(manual 章节命名无 Section X.Y 体系，按通用 H3 计)")

    # 表格行（markdown 表格以 `|---|` 分隔行）
    table_sep_re = re.compile(r"^\s*\|?\s*:?-+:?\s*\|", re.MULTILINE)
    n_tables = len(table_sep_re.findall(md_text))
    if n_tables < 5:
        result["warnings"].append(f"manual full 表格行数 {n_tables} < 5(manual 核心是参数表 / 接口表 / 错误码表)")

    # 命令 / API / 配置代码块（```bash / ```yaml / ```json / ```python）
    code_block_re = re.compile(
        r"```(bash|yaml|json|python|sh|console)\b",
        re.MULTILINE,
    )
    n_code_blocks = len(code_block_re.findall(md_text))
    if n_code_blocks < 1:
        result["warnings"].append(
            "manual full 未发现 bash/yaml/json/python 代码块(manual 核心是命令清单 / API endpoint / 配置项)"
        )

    # 字符下限
    n_chars = len(md_text)
    if n_chars < 6000:
        result["warnings"].append(f"manual full 字符数 {n_chars} < 6000,可能偷懒或撞 token 上限")

    # 占位比例
    placeholder_count = md_text.count("原文未明确")
    if n_h3 > 0:
        ratio = placeholder_count / float(n_h3)
        if ratio > 0.5:
            result["warnings"].append(
                f"manual full 含 {placeholder_count} 处'原文未明确'占位 / {n_h3} 个 H3 = {ratio:.0%},"
                f"超过 50% 阈值,可能存在偷懒"
            )

    summary_line = (
        f"Content self-check (manual): H2={n_h2}, H3={n_h3}, "
        f"tables={n_tables}, codeblocks={n_code_blocks}, "
        f"chars={n_chars}, {len(result['warnings'])}w {len(result['failures'])}f"
    )
    result["report"] = summary_line
    return result


def _check_whitepaper_full_content(md_text):
    # type: (str) -> Dict[str, object]
    """whitepaper full 模式自检(2026-07-05)：whitepaper 必保真行业数据 / 客户案例。

    校验项:
    1. H2 章节保真度 ≥ 3 (FAIL)
    2. H3 子节数 ≥ 5（通用 H3，whitepaper 章节命名无 Section X.Y 体系）
    3. 表格行数 ≥ 5（行业数据表 / 对比表 / 客户案例表）
    4. mermaid block ≥ 1（架构 / 价值链 / 流程图）
    5. 字符下限 ≥ 7000（whitepaper 居中）
    6. "原文未明确"占位比例 > 0.5 (WARN)
    """
    import re

    result = {"ok": True, "warnings": [], "failures": [], "report": ""}

    # H2
    h2_re = re.compile(r"^##\s+", re.MULTILINE)
    n_h2 = len(h2_re.findall(md_text))
    if n_h2 < 3:
        result["failures"].append(f"whitepaper full H2 章节数 {n_h2} < 3,PDF 章节未被保真展开")
        result["ok"] = False

    # H3 通用
    h3_re = re.compile(r"^###\s+", re.MULTILINE)
    n_h3 = len(h3_re.findall(md_text))
    if n_h3 < 5:
        result["warnings"].append(f"whitepaper full H3 子节数 {n_h3} < 5(whitepaper 章节命名无 Section X.Y 体系)")

    # 表格行
    table_sep_re = re.compile(r"^\s*\|?\s*:?-+:?\s*\|", re.MULTILINE)
    n_tables = len(table_sep_re.findall(md_text))
    if n_tables < 5:
        result["warnings"].append(
            f"whitepaper full 表格行数 {n_tables} < 5(whitepaper 核心是行业数据 / 对比 / 客户案例表)"
        )

    # mermaid block
    mermaid_re = re.compile(r"```mermaid\b", re.MULTILINE)
    n_mermaid = len(mermaid_re.findall(md_text))
    if n_mermaid < 1:
        result["warnings"].append("whitepaper full 未发现 mermaid block(whitepaper 常用架构 / 价值链 / 流程图)")

    # 字符下限
    n_chars = len(md_text)
    if n_chars < 7000:
        result["warnings"].append(f"whitepaper full 字符数 {n_chars} < 7000,可能偷懒或撞 token 上限")

    # 占位比例
    placeholder_count = md_text.count("原文未明确")
    if n_h3 > 0:
        ratio = placeholder_count / float(n_h3)
        if ratio > 0.5:
            result["warnings"].append(
                f"whitepaper full 含 {placeholder_count} 处'原文未明确'占位 / {n_h3} 个 H3 = {ratio:.0%},"
                f"超过 50% 阈值,可能存在偷懒"
            )

    summary_line = (
        f"Content self-check (whitepaper): H2={n_h2}, H3={n_h3}, "
        f"tables={n_tables}, mermaid={n_mermaid}, "
        f"chars={n_chars}, {len(result['warnings'])}w {len(result['failures'])}f"
    )
    result["report"] = summary_line
    return result


def _check_book_full_content(md_text):
    # type: (str) -> Dict[str, object]
    """book full 模式自检(2026-07-05)：book 章节命名是 Chapter N / Part N。

    校验项:
    1. H2 章节保真度 ≥ 3 (FAIL)
    2. `## Chapter N` 或 `## Part N` 数量 ≥ 3
    3. H3 子节数 ≥ 5
    4. 字符下限 ≥ 8000
    5. "原文未明确"占位比例 > 0.5 (WARN)
    """
    import re

    result = {"ok": True, "warnings": [], "failures": [], "report": ""}

    # H2
    h2_re = re.compile(r"^##\s+", re.MULTILINE)
    n_h2 = len(h2_re.findall(md_text))
    if n_h2 < 3:
        result["failures"].append(f"book full H2 章节数 {n_h2} < 3,PDF 章节未被保真展开")
        result["ok"] = False

    # Chapter N / Part N
    chapter_re = re.compile(
        r"^##\s+(Chapter|Part|Appendix|Index)\s+\d",
        re.MULTILINE | re.IGNORECASE,
    )
    n_chapters = len(chapter_re.findall(md_text))
    if n_chapters < 3:
        result["warnings"].append(f"book full ## Chapter/Part/Appendix/Index 数量 {n_chapters} < 3")

    # H3 通用
    h3_re = re.compile(r"^###\s+", re.MULTILINE)
    n_h3 = len(h3_re.findall(md_text))
    if n_h3 < 5:
        result["warnings"].append(f"book full H3 子节数 {n_h3} < 5")

    # 字符下限
    n_chars = len(md_text)
    if n_chars < 8000:
        result["warnings"].append(f"book full 字符数 {n_chars} < 8000,可能偷懒或撞 token 上限")

    # 占位比例
    placeholder_count = md_text.count("原文未明确")
    if n_h3 > 0:
        ratio = placeholder_count / float(n_h3)
        if ratio > 0.5:
            result["warnings"].append(
                f"book full 含 {placeholder_count} 处'原文未明确'占位 / {n_h3} 个 H3 = {ratio:.0%},"
                f"超过 50% 阈值,可能存在偷懒"
            )

    summary_line = (
        f"Content self-check (book): H2={n_h2}, Chapter/Part/Appendix/Index={n_chapters}, "
        f"H3={n_h3}, chars={n_chars}, "
        f"{len(result['warnings'])}w {len(result['failures'])}f"
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

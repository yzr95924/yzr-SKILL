# gemini-pdf-summary · 共享基础约定

> 本文件是 `scripts/gemini_pdf_summary.py` 拼装 prompt 时的**底层片段**——
> 被 4 类文档模板（`template-{paper,manual,whitepaper,book}.md`）共同引用。
>
> 维护规则：模板变更需同步更新 SKILL.md "输出"小节里的章节骨架。
>
> 风格基线遵守仓库既定指纹：`*` bullet / `==高亮==` /
> ` ```mermaidjs ` block-level / 表格 / 行宽 ≤ 120。

<!-- markdownlint-disable MD051 -->
## 目录

- [**API 调用契约**](#api-调用契约) — Gemini 多模态直接读 PDF，不先抽文本
- [**风格约定（仓库统一基线）**](#风格约定仓库统一基线) — bullet / 高亮 / mermaidjs / 行宽 / 不写 H1
- [**基础要求（4 类共用）**](#基础要求4-类共用) — 忠于原文 / 英文保留 / 字符数纪律
- [**图表处理约定**](#图表处理约定) — paper quick 抽原始图，paper full / manual / whitepaper / book 用 mermaid / ASCII / 表格
- [**错误处理契约**](#错误处理契约) — 端到端不降级 / 3 次重试 / 抛错含三步建议
<!-- markdownlint-enable MD051 -->

## API 调用契约

**PDF 原文直接喂 Gemini，不要先抽文本**：

```python
from google import genai
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
response = client.models.generate_content(
    model="gemini-3.5-flash",  # 默认值；用户显式覆盖走 --model
    contents=[
        Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        template_text,  # 从 _base + template-<type> 拼装
    ],
)
```

**禁止**先用 pdftotext / PyPDF2 / pdfplumber 抽纯文本再喂 Gemini——会丢图表、公式、版式信息。

**模型选择**：默认 `gemini-3.5-flash`（stable，2026-06 选型结果）。
用户显式传 `--model <id>` 时按用户；具体可用模型以
`gemini-api-docs-mcp` 的 `get_current_model` 实时结果为准。

**端到端不降级**（与 gemini-paper-summary 同源；详见 SKILL.md §核心原则）：

- 主模型遇 503 UNAVAILABLE / 429 RESOURCE_EXHAUSTED / 5xx → 走 3 次重试（2s/4s 退避）
- 4xx 永久错误不重试直接抛
- 仍失败 → 脚本抛 `RuntimeError`，含 `model=<id>` + `status=<code>` + 三步建议：
  1. 稍后重试
  2. 检查 `GEMINI_API_KEY` 与配额
  3. `--model <id>` 显式换模型
- **绝不**静默切到 lite / pro 或其它便宜模型——不同模型对 prompt 模板的输出质量差异显著
- agent 收到此错**不得**自行换模型重跑，把错误原文 + 三步建议如实呈现给用户，换不换模型由用户决定

## 风格约定（仓库统一基线）

1. **bullet marker**: 一律用 `*`，**不要**用 `-` 或 `+`
2. **高亮术语**: 关键概念 / 参数 / 状态用 `==text==`（默认色）
   - Markdown 无法写彩色高亮，**不要**硬造颜色语法
3. **Mermaid**: 复杂结构 / 概念关系用 fenced code block，块名**统一用 `mermaidjs`**
   （标准 Markdown 渲染器也兼容，对 outline-wiki / Obsidian 直接可用），仅用 `graph` 系列
   （TD / LR）；仓库内**不**用 sequenceDiagram / classDiagram / stateDiagram / erDiagram。
   放在 bullet **之外**（block-level），不要嵌在 bullet 子项内。
4. **代码块语言必填**：bash / python / json / yaml ... 不写空语言
5. **表格**: 数据示例 / 概念对比 / 字段定义用 table；其他场景优先 bullet
6. **引用块**: 行首 > 加空格 仅在引用原始资料原话时使用，**不要**当容器用
7. **行宽**: 单行 ≤ 120 字符
8. **不写私造语法**: 不写 `!!! warning` / `:::tip` / `<mark>` / `<details>` /
   装饰性 emoji 占位（🎉🎉🎉）
9. **数学 / 范围 / 公式**: 禁用 MathJax（`$...$` / `$$...$$` outline-wiki 不渲染）——改用
   纯文本或 Unicode：范围 `[1, 2^64)`、上标 `2^64` 或 `2⁶⁴`、比较 / 运算
   `≥` `≤` `×` `→` `≈`。例外：book 模板的全文转写可保留 `$...$` 行内公式
   （agent Q&A 底座场景可消费 LaTeX），但仍不用 `$$...$$` block。
10. **不写 H1**: 文档标题由文件名 / 上层目录承载，正文从 ## 起步

## 基础要求（4 类共用）

1. **忠于原文**：PDF 未提及的内容不要编造，不确定处标注"原文未明确"
2. **不强制全中文，英文该留就留**：默认中文叙述，但以下五类直接保留英文，不硬译：
   - 学术专有名词 / 方法名：Transformer、RLHF、LoRA、Mixture-of-Experts、Beam Search
   - 模型 / 产品 / 工具名：Gemini、GPT-4、Claude、PyTorch、vLLM、Hugging Face
   - 库 / API / 文件名：`transformers`、`pip`、`<config>` 字段名
   - 算法 / 协议 / 标准名：Top-p、TCP、gRPC、REST、IEEE 802.11ax
   - 度量 / 缩写 / 专有指标：BLEU、ROUGE、ACL、GPU、FLOPS、perplexity
   - 中英混排是常态（如"训练使用 LoRA（低秩适配）"）；表格中整项为英文术语时整项保持英文
3. **引用出处**（按模板要求）：引用关键结论时点明出自 PDF 哪个章节
4. **字符数纪律**：
   - **paper quick**（唯一精炼优先档位）：字符数 ≤ 2500（SSOT 见 `template-paper.md` 头部）——
     能 1 句话讲清的事不要拆 3 句；能省略的铺垫 / 重复 / 概念定义就省略；
     判断标准："删掉这段读者就理解错 / 漏掉关键信息"才是"必须留"，否则一律砍
   - **paper full / manual / whitepaper / book**（full 风格）：**无字符数上限**——按 PDF 原生章节顺序
     逐小节展开，token 预算紧张时**优先精简措辞、缩具体例子**；**禁止**合并整段、删除小节、
     跳过该类型必保真的元素（paper full: 公式 / 定理 / 算法；manual: 命令 / 参数 / 错误码；
     whitepaper: 行业数据 / 客户案例；book: Chapter / 小结 / 思考题）
   - **数字精度约定（self-aware 注）**："3 位有效数字"是**风格约定**，非可调阈值，散落在多份
     `template-*.md` + `full-mode-contract.md`；改此约束请改各 `assets/template-*.md` 必保真元素段 +
     `references/full-mode-contract.md` 类型专属保真元素表，不要在 prose 里逐字面改单点数字
5. **Markdown 标题分节**：每个章节标题**必须用 `##`（二级标题）**——**不要**写成 `###` / `####`；
   prompt 里出现的 `###`（图引用约定 / 风格约定 / 高频引用表格 / 本基础要求等）
   是给你的 meta 说明，**不是**输出标题；正文不写 H1（`#`）

## 图表处理约定

> **核心原则**：4 类文档的"消费对象"不同，图表处理策略也不同。
>
> - **paper quick**：给**人**看的速读总结（含图才能扫），**抽原始 PDF 图** → `figures/*.png`
> - **paper full / manual / whitepaper / book**：产物主要给 **agent / LLM** 消费（无 PDF 时 Q&A 底座），
>   **不抽原始图**，把概念 / 架构 / 流程类信息用 ` ```mermaidjs ` block / markdown 表格 /
>   ASCII 示意图在正文里直接画

### 4.1 paper quick 模式（保留原 gemini-paper-summary 行为）

**抽原始图**：脚本 `scripts/figure_extraction.py`（含 Stage 1 caption locator + Stage 2 Gemini 视觉定位），把 PDF 中的关键图按 bbox 截下来存 `<output>/figures/figure-pX-fN.png`。

**Markdown 图引用三阶段**：

```text
Gemini 输出          →  ![图 N: <中文翻译+总结>](PDF p.<页> fig.<N> bbox=<x0,y0,x1,y1>)
脚本图导出后         →  ![图 N: <中文翻译+总结>](figures/figure-pX-fN.png "=WxH")
推到 outline 后      →  ![图 N: <中文翻译+总结>](/api/attachments.redirect?id=<uuid> "=WxH")
```

图引用约定（caption 写到 alt / bbox 写进 url / 不要独立 `**图 N**` 行 / 不要 `— <role>` 后段等）
详见 gemini-paper-summary 旧 SKILL.md §核心原则 #5 与
[`references/figure-extraction.md`](../references/figure-extraction.md)。

### 4.2 manual / whitepaper / book + paper full（full 风格，4 类通用）

**不抽原始图**——manual / whitepaper / book 脚本自动启用 `--no-figures`，paper full 走
`_run_full_mode`（按设计不写 `![图 N]` 引用）。Prompt 强约束 Gemini 把图按类型分流：

- **架构 / 概念图**（Node 数据结构、流程图、模块关系、状态机等）→
  用 ` ```mermaidjs ` block 直接画（`graph TD` / `graph LR`）；label 用 `<br/>` 换行，关系用 `-->|文字|` 标注
- **数据可视化图**（性能柱状图、accuracy 对比、loss 曲线、heatmap、市场份额等）→
  转 markdown 表格（数字精度 3 位有效数字）；图本身就是表格的可视化形式，转表更准
- **纯装饰图 / setup 截图 / logo** → 直接省略 + 在上下文写一句"图 N 是 `<场景描述>` 的示意图"，**不**画图、不写 `![图 N]` 引用
- **接口 / API / 命令清单** → markdown 表格 + 代码块（` ```bash ` / ` ```yaml `）——manual 必保真

**禁止写 `![图 N](PDF p.X ...)` 引用**——full 风格产物自包含，无 PNG 配套；脚本后处理
`strip_pdf_figure_refs()` 会在检测到该模式时把该行整段删除（避免 outline 渲染破图）。

## 错误处理契约

```text
GEMINI_API_KEY 未设置        → 启动时检查；缺失则报清晰错误
google-genai 未安装          → 启动时检查；缺失则报清晰错误
--type 缺失且未传 --auto-detect → argparse error，提示用法
--type 取值非法               → argparse error，列出合法值
--auto-detect 都判定不出      → 返回 "无法识别" + 4 类候选 + 建议用户显式传
书籍 > Gemini 文件 API 上限    → 报错并提示拆 PDF；不自动降级
Gemini 503/429/5xx 重试耗尽   → 抛 RuntimeError 含 model + status + 三步建议（不降级）
模型 404 / 已 deprecated       → 报错并提示用 gemini-api-docs-mcp 查当前可用模型
非 paper full / manual / whitepaper / book 类型的输出含 PDF ref → strip_pdf_figure_refs() 强制转 mermaid / 删除
输出被 token 上限截断          → 检测到不完整章节 → 报错 + 建议缩小范围 / 换模型
```

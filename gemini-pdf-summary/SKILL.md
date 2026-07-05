---
name: gemini-pdf-summary
description: 在用户给出一份本地 PDF 文档（学术论文 / 产品手册 / datasheet / 用户手册 / 行业白皮书 / vendor 技术白皮书 / 书籍 / 长篇技术文档）想要用 Gemini 多模态直接读 PDF（含图表 / 公式 / 版式，不抽 OCR）并按文档类型路由到对应结构化模板输出中文 Markdown 时使用本 skill。**`--type` 必填**（paper / manual / whitepaper / book 四选一），不确定时可用 `--auto-detect`（PDF 元数据 + 首页文本启发式 + Gemini 看首页验证）。默认中文、必要时英文术语保留原文；Markdown 风格遵守仓库既定指纹（`*` bullet / `==高亮==` / ` ```mermaidjs ` block / 表格 / 行宽 ≤ 120）。paper quick 模式抽原始 PDF 图（默认开，给**人**看）— paper **唯一保留的 quick 风格**；manual / whitepaper / book + paper full 模式**不抽原始图**，按 PDF 原生章节顺序做**全文级转写**（产物给 LLM 消费并进入 llm-wiki 二次 ingest）。`--full` 模式契约详见 [`references/full-mode-contract.md`](references/full-mode-contract.md)。**不适用**：非 PDF 来源、要求逐字翻译全文、仅做关键词抽取等。
metadata:
  author: Zuoru YANG
  modify time: 2026-07-05
  category: pdf-reading
  supersedes: gemini-paper-summary
---

用 Gemini 多模态长上下文直接"读懂"任意 PDF，按文档类型路由到对应结构化模板输出**中文 Markdown**。
4 类文档（学术论文 / 产品手册 / 白皮书 / 书籍）共用同一套 SDK 调用 + Markdown 风格指纹 + 错误处理契约，
各自走一份独立模板（`assets/template-{paper,manual,whitepaper,book}.md` + 共享 `_base.md`）。
**agent 可以直接调用本 skill 的脚本做单篇处理，也可以按 `references/api-quickstart.md` 在会话内自行调用 SDK。**

> 依赖：Python ≥ 3.7、`google-genai`（`pip install -U google-genai`）、
> 环境变量 `GEMINI_API_KEY`（在 [Google AI Studio](https://aistudio.google.com/apikey) 创建）。
> 详细的依赖与失败排查见文末"前置条件"。

## 何时使用 / 不使用

### 使用

- 用户给出一份**本地 PDF**，要按文档类型（论文 / 手册 / 白皮书 / 书）输出中文结构化总结
- 用户要在多份 PDF 里**批量过稿**，每份走同一种类型
- PDF 含大量图表 / 公式 / 版式信息，纯文本抽取（pdftotext / PyPDF2）会丢信息
- 用户希望用 Gemini 直接读 PDF，而不是先 OCR
- 产物最终要落到 `llm-wiki-management` 的 `raw/<type>/<slug>/` 下做后续 ingest
- 用户不确定 PDF 类型——`--auto-detect` 让脚本自动识别（PDF 元数据 + 首页文本 + Gemini 看首页 1-3 页验证）

### 不使用

- PDF 不是 PDF（网页、Markdown、纯文本）——先转 PDF 或改用其他 skill
- 需要**逐字翻译 / 复刻全文**（本 skill 是"总结"，不是翻译）
- 需要**对比多份 PDF**——本 skill 一次一份，多份请调用多次再人工拼接
- 只想抽关键句、抽取式摘要——本 skill 是生成式结构化总结
- 用户不愿或不能提供 `GEMINI_API_KEY`
- **`--type` 缺失且未传 `--auto-detect`**——脚本会报错并提示 agent 反问用户确定类型（见 §工作流 §A）

## 输入 / 输出

### 输入

| 字段 | 必选 | 说明 |
| --- | --- | --- |
| PDF 路径 | ✓ | 本地 `.pdf` 文件，绝对或相对路径均可 |
| 文档类型 | ✓ | `--type <paper\|manual\|whitepaper\|book>` 二选一；不确定用 `--auto-detect`（脚本自动判） |
| `GEMINI_API_KEY` | ✓ | 环境变量 |
| 模型 ID | ✗ | 默认 `gemini-3.5-flash`（不传 `--model` 即可）；**仅在有明确理由时**才覆盖，详见下方"模型选型"小节 |
| 关注点 | ✗ | `--focus "重点关注实验部分"` 之类，会追加到 prompt |
| 输出路径 | ✗ | `--output <path>`：paper quick 默认带图时视作**目录**（写 summary.md + figures/）；非 paper 类型 / --no-figures / book / paper full 模式视作 .md 文件路径（或 raw 端目录）；不传则 stdout |
| 模板 / 模式 | ✗ | paper quick 默认；`--full` 启用 paper full 或 book 模式 |
| 提取图片 | ✗ | 仅 paper quick 生效：`--no-figures` 关闭图导出（手动 / 白皮书 / 书默认即不开图） |
| 渲染倍率 | ✗ | `--figure-dpi 2.0`（默认 2.0 = 144 DPI），仅 paper quick 图导出启用时生效 |
| 图片格式 | ✗ | `--figure-format {png,webp,jpeg}`，默认 png；webp/jpeg 时可用 `--figure-quality` 压缩 |
| 压缩质量 | ✗ | `--figure-quality 1-100`，默认 85；仅 webp/jpeg 生效 |
| 像素上限 | ✗ | `--max-width N`，渲染后等比缩放到 ≤ N px 宽；None 不限制 |
| 体积上限 | ✗ | `--max-size-kb N`，超 N KB 自动降级（quality → format → scale）；None 不限制 |
| 缩略图 | ✗ | `--thumbnail` 额外生成缩略图；`--thumbnail-width`（默认 400px）控制宽度 |
| Stage 2 视觉定位 | ✗ | `--refine-figures / --no-refine-figures`（默认 True），仅 paper quick 生效 |
| Stage 2 渲染倍率 | ✗ | `--refine-dpi 2.0`，仅 paper quick 启用 refine 时生效 |
| 强制覆盖 | ✗ | `--force-full`，仅 paper `--full` 模式生效；raw 端产物已存在时默认拒绝覆盖 |

### 模型选型

> **默认 = 不传 `--model`**。脚本默认值 `gemini-3.5-flash` 是经过选型的
> （stable、无 shutdown 日期、官方作为 deprecated 2.5 系列的推荐替代），
> **不知道选什么 / 没特殊理由 → 直接用默认**。

**判断流程**：

```text
1. 跑 gemini_pdf_summary.py（不传 --model，用默认）
2. 输出不满意？
   ├─ 否 → 用默认就好
   └─ 是 → 先调 prompt（--focus 或改 template-*.md），再考虑换模型
3. 真要换模型 → 从下方"当前推荐"里按场景选；不要凭印象写 model 字符串
```

**当前推荐（基于 gemini-api-docs-mcp 实测，2026-06）**：

| 模型 | 状态 | 定位 | 何时显式覆盖（vs 默认） |
| --- | --- | --- | --- |
| `gemini-3.5-flash`（**默认**） | Stable | 通用质量/成本最优 | 大多数场景下不传 `--model` 即可 |
| `gemini-3.1-flash-lite` | Stable | 最便宜、轻量 | 批量过稿 / 简单综述 / 上下文大但要求低 |
| `gemini-3.1-pro-preview` | Preview | 复杂推理最强 | book full / 长篇 / 形式化证明 / 难数学 |

> **主模型不可用 → 报错退出，端到端不降级**（2026-06-30 强化，2026-07-01 补 agent 盲区）：
> 上表里**任一**模型遇到 503 / 429 / 5xx，脚本走 3 次重试后**直接抛错**给上层——
> 绝不静默切到 lite/pro 或其它便宜模型。**且 agent 收到此错也不得自行换模型重跑**
> （脚本错误里的"用 `--model <id>` 换模型"是给用户的、不是给 agent 的指令），须如实
> 把错误 + 三步建议呈现给用户，由用户决定。换模型必须用 `--model <id>` 显式指定，
> **完整策略见 §核心原则 #8**（包含错误信息格式与三步建议）。

**避免使用**：

- ==`gemini-2.5-flash`==：deprecated，官方推荐替代 `gemini-3.5-flash`（**有 shutdown 日期**）
- `gemini-2.5-pro`：deprecated，替代 `gemini-3.1-pro-preview`
- `gemini-2.5-flash-lite`：deprecated，替代 `gemini-3.1-flash-lite`
- 任何 `*-preview-09-2025` / `*-preview-12-2025` 等老 preview snapshot——过期，官方已弃

> **deprecated 系列会随时间关停**。本表里的 shutdown 日期以
> `mcp__gemini-api-docs-mcp__search_documentation` / `get_current_model`
> 实测为准；agent / 用户使用前**先查一次**确认未变。**不要**把 shutdown
> 日期 / deprecated 列表固化到月；本节每年/每季 review 一次。

### 输出

按文档类型路由到对应模板，**统一章节顺序、命名、字符数目标**由各模板头部声明（**单一来源**）：

- **paper quick**（默认）：开篇 3 列表格 → 团队 item → `## 3 句话总结` → 背景与动机 → 方法设计 → 代表性实验结果 → 业务启示 & 价值 → 局限与未来工作
  - 评测 / benchmark 类论文自动把"方法设计 + 代表性实验结果"替换为"评测设计 + 评测发现"
- **paper full**（`--full`）：按 PDF 原文章节顺序逐小节展开（含 Definition / Theorem / Algorithm 标注 + 公式 `$...$` + 表格行级转写 + 数字精度 3 位有效数字）；不抽原始图
- **manual**：按 PDF 原生目录结构逐小节展开（full 风格全文级转写，含命令清单 / 参数表 / 错误码；章节末尾的故障排查 + FAQ + 更新日志要点原样保留）；**不抽原始图**
- **whitepaper**：按 PDF 原生目录结构逐小节展开（full 风格全文级转写，含行业数据表 / 对比表 / 客户案例；章节末尾的 Conclusion + Key Takeaways + Recommendations 原样保留）；**不抽原始图**
- **book**（仅 full）：按 PDF 原生 `Chapter` / `Section` / `Appendix` / `Index` 顺序全量转写；**不抽原始图**

**字符数目标**：

> **SSOT 例外说明**：本表与 `assets/template-paper.md` 头部同源——模板头部是给 Gemini 看的目标，
> **本表是给 agent 速查的镜像**，两处必须同步改。SSOT 在模板头部（脚本 `_load_prompt_for_type`
> 抽该字段），本表是 SKILL.md 内的镜像。
> manual / whitepaper / book 是 **full 风格**，无字符数上限——不在 SSOT 例外范围。

- paper quick ≤ 2500
- paper full / manual / whitepaper / book：无字符数上限；token 预算紧张时**优先精简措辞、
  缩具体例子**，**禁止**合并整段、删除小节、跳过公式 / 定理 / 算法步骤（paper full）/
  命令 / 参数 / 错误码（manual）/ 行业数据 / 客户案例（whitepaper）/ Chapter 内容（book）

**图表处理策略**（SSOT 在 `assets/_base.md` §图表处理约定）：

| 类型 / 模式 | 图处理 | 原因 |
| --- | --- | --- |
| paper quick | 抽原始 PDF 图 → `figures/*.png`（默认开） | 给**人**看的速读总结，必须带图 |
| paper full | 不抽图，mermaid / 表格 / ASCII 在 markdown 内画 | agent Q&A 底座，PNG 仅 ~50% agent 能消费 |
| manual / whitepaper | 同 paper full | 产物主要给 LLM 消费，进入 llm-wiki 二次 ingest |
| book | 同 paper full | 长篇转写，agent 后续按章节 Q&A |

**不存在的章节可省略**；**默认中文**（标题、叙述、连接词），但术语、模型名、产品名、库名等必要时
**直接保留英文**（详见下文核心原则 #4 与 #9）。

> **精炼优先**（仅适用于 paper quick；full 风格走全文级）：
> **每一段、每一条 bullet 都应该能删则删**——能 1 句话讲清的事不要拆 3 句；
> 能省略的铺垫 / 重复 / 概念定义就省略；判断标准："删掉这段读者就理解错 / 漏掉关键信息"
> 才是"必须留"，否则一律砍。总结的密度 > 总结的篇幅。

## 执行原则 / 边界

### 核心原则

1. **PDF 原文直接喂 Gemini，不要先抽文本**
   - 用 `Part.from_bytes(data=<bytes>, mime_type="application/pdf")` 走多模态
   - 不用 pdftotext / PyPDF2 / pdfplumber 之类先抽纯文本（会丢图表、公式、版式）
2. **结构化总结，不是复述**
   - 按文档类型路由到对应模板的**主线顺序与命名**输出；字符数目标见各模板头部（**单一来源**，勿在正文写死数值）
   - **不存在的章节可省略**（如纯理论论文无实验数据时省"代表性实验结果"）
   - 关键数据 / 数值必须保留，避免泛泛而谈
3. **忠于原文，不脑补**
   - 文档没说就标"原文未明确"
   - 引用结论时点明出处（如"见 4.2 实验部分"）
4. **不强制全中文：英文该留就留**
   - 输出主语言仍是中文，但以下五类**直接保留英文**，不要硬译：
     - 学术专有名词 / 方法名：Transformer、RLHF、LoRA、Mixture-of-Experts、Beam Search
     - 模型 / 产品 / 工具名：Gemini、GPT-4、Claude、PyTorch、vLLM、Hugging Face
     - 库 / API / 文件名：`transformers`、`pip`、`requirements.txt`、`<config>` 字段名
     - 算法 / 协议 / 标准名：Top-p、TCP、gRPC、REST、IEEE 802.11ax
     - 度量 / 缩写 / 专有指标：BLEU、ROUGE、ACL、GPU、FLOPS、perplexity
   - **判定标准**：翻译反而引发歧义、丢失语义、或该英文已是该领域标准用法时，
     无条件保留。中英混排是常态（如"训练使用 LoRA（低秩适配）"）
   - 列表 / 表格中若一项本身就是英文术语，整项保持英文
5. **图表处理分两套**（详细规则见 `assets/_base.md` §图表处理约定）
   - **paper quick**：抽原始 PDF 图（默认开）→ `figures/figure-pX-fN.png`；
     caption 写到 markdown image 的 alt 字段（`![图 N: <中文翻译+总结>](<url> "=WxH")`）；
     bbox 写在 PDF reference 字符串里供脚本精确截取
   - **其他 3 类（manual / whitepaper / book + paper full）**：不抽原始图，
     概念用 ` ```mermaidjs ` block（架构 / 流程图）/ markdown 表格（数据可视化图）/
     文字一句（装饰图省略）在 markdown 内直接画
6. **GitHub 风格的 paper 相关工作 / 高频引用**：仅 paper quick 输出，作为"业务启示 & 价值"子段
   - 论文有引言 / 相关工作章节时**才**输出；无相关工作时整段省略
   - 排序按"对本文重要性"降序，**3-5 条**；省略"引用次数"列
   - 重点收录：实验直接对比过的 baseline > 奠基性工作 / 近期 SOTA / 本文方法直接前身
   - 引文细节以 PDF 参考列表为准；不确定时只填作者 + 年份（**不要编造**）
7. **paper quick 开源实现**：作为"业务启示 & 价值"子段（适用规则见 `template-paper.md` quick 模式）
8. **模型选择**：默认与"何时显式覆盖"指南见 §模型选型小节
   （脚本 `DEFAULT_MODEL` 常量，见 `scripts/gemini_pdf_summary.py`）。实际可用模型以
   当前 Gemini 文档为准（用 `gemini-api-docs-mcp` 的 `get_current_model` 核实）。
   **为什么不在本条重列模型名**：模型选型表是 SSOT，列在 §模型选型小节里
   - **结果质量 > 系统可用性 · 无自动 fallback**（2026-06-21 决策，2026-06-30 加固）：
     默认模型遇到 503 UNAVAILABLE / 429 RESOURCE_EXHAUSTED / 5xx 等高并发 / 限流
     错误时，统一走 3 次重试（2s/4s 退避；4xx 永久错误不重试直接抛）——仍失败则
     脚本**直接抛错**给上层，**绝不**静默降级到便宜模型
   - **端到端不降级 · agent 也不得自行换模型**（2026-07-01 加固）：脚本抛 `RuntimeError`
     （含 `model=` + `status=` + 三步建议）即任务失败，**agent 不得**自行加
     `--model gemini-3.1-flash-lite` 等便宜模型重跑
9. **Markdown 风格约定（仓库统一基线）**
   - **bullet marker 一律用 `*`**，**不要**用 `-` 或 `+`
   - **关键术语用 `==text==` 高亮**（默认色），不要硬造彩色语法
   - **Mermaid 块 block-level**：` ```mermaidjs ` 放在 bullet 之外，不要嵌在 bullet 子项内
   - **代码块语言必填**：` ```bash ` / ` ```python ` / ` ```json ` / ` ```yaml ` ，
     **不要**写空语言 ` ``` `
   - **表格 vs bullet**：数据示例 / 概念对比 / 字段定义用 table；其他场景优先 bullet
   - **引用块** 行首 > 加空格 仅在引用原始资料原话时使用，**不要**当容器用
   - **行宽 ≤ 120 字符**（与 `.markdownlint.jsonc` MD013 对齐）
   - **章节标题用 `##`**：每个章节标题一律 `##`（二级），**不要**降级成 `###`；正文不写 H1（`#`），标题由文件名 / 上层目录承载
   - **不写私造语法**：`!!! warning` / `:::tip` / `<mark>` / `<details>` /
     装饰性 emoji 占位（🎉🎉🎉）等**不要**出现
   - **数学 / 范围 / 公式禁用 MathJax**：`$...$` / `$$...$$` outline-wiki 不渲染——
     改纯文本 / Unicode：范围 `[1, 2^64)`、上标 `2^64` / `2⁶⁴`、运算 `≥` `≤` `×` `→` `≈`
     （book 模板的全文级转写可保留 `$...$` 行内公式——agent Q&A 场景可消费 LaTeX）

### 边界

- 只处理本地 PDF；非 PDF 一律先转 PDF
- 不做全文翻译；不做多份对比
- 一次一份 PDF
- 单 PDF 大小受 File API 硬上限约束（数值与超大文件处置见 §前置条件）
- **`--type` 与 `--auto-detect` 互斥，必传其一**；都不传 → 脚本报错并提示 agent 反问用户
- **manual / whitepaper / book 仅支持 full 风格**：脚本自动启用 `--full` 风格的 prompt
  加载（无需用户传 `--full`；full 模式契约见 `references/full-mode-contract.md`）
- **manual / whitepaper / book + paper full 不抽原始图**：自动启用 `--no-figures`（脚本 INFO 提示）
- **paper quick 模式图处理**：沿用 gemini-paper-summary 的三层定位（Stage 2 视觉定位 +
  caption locator + bbox hint），全失败时整图删除 + 剥呼应句
- **paper quick 模式图引用甄别**：line 文本必须以 `Figure N[.:]` + 描述形式才算 caption；
  高度 sanity check 250pt 阈值；详见 `references/figure-extraction.md`

## 工作流 / 步骤

### A. agent 在会话中调用（推荐流程）

**Step 1 — 类型确认**（**关键**：脚本强制要求）：

```text
1. 用户说"总结这个 PDF" / agent 拿到本地 .pdf 文件
2. 如果用户已说明类型（"这是产品手册"/"这是白皮书"/"这是论文"/"这是书"） → 直接传 --type
3. 如果用户没说 / agent 无法确定 → 反问用户：
     "这份 PDF 属于哪种类型？
      - paper      - 学术论文
      - manual     - 产品手册 / datasheet / 用户手册
      - whitepaper - 行业 / 技术 / vendor 白皮书
      - book       - 书籍 / 长篇技术文档
      或者让我用 --auto-detect 自动识别"
4. 用户回答后传 --type <answer>
```

**Step 2 — 输出路径确认**（**关键**：避免落盘到错位置）：

```text
1. 如果用户已说明输出位置（"落到 raw/manuals/foo/"）→ 直接传 --output
2. 如果用户没说 → 反问用户：
     "输出到哪个路径？建议：
      - 落到 llm-wiki 的 raw 端：<wiki-root>/raw/<type>/<slug>/
      - 落到临时目录：~/tmp/<slug>/
      - 打印到 stdout（仅纯文字速读用，不导出图）"
3. 用户回答后传 --output <answer>
```

> **为什么 agent 必须反问**：4 类文档对应不同的产物布局（`raw/papers/` / `raw/manuals/` /
> `raw/whitepapers/` / `raw/books/`）——agent 替用户拍板容易落错目录，
> 后续 `llm-wiki-management` 的 `ingest_diff.py` 找不到产物就白跑。

**Step 3 — 调用脚本**：

```text
1. 确认 PDF 存在且可读
2. 确认 GEMINI_API_KEY 已设置；未设置则提示用户去 aistudio.google.com/apikey 申请
3. 确认 google-genai 已安装：python3 -c "import google.genai" 或 pip install -U google-genai
4. 调用 scripts/gemini_pdf_summary.py：
   python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
     --pdf <path> \
     --type <paper|manual|whitepaper|book> \
     --output <output-dir>    # 或不传 → stdout
   # paper quick 默认带图 + Stage 2 视觉定位（--refine-figures 默认开），保证图质量；
   # --no-figures 关闭图导出
5. 把生成的 Markdown 总结（含图）呈现给用户
6. 标注所用模型与 PDF 文件名
7. **失败处理（重要）**：若第 4 步脚本抛 RuntimeError（503/429/5xx 重试耗尽），
   agent **不得**自行加 `--model` 换便宜模型重跑——把错误原文 + 三步建议如实
   呈现给用户并停下，换不换模型由用户决定（见 §核心原则 #8 端到端不降级）
```

也可以直接在会话里调 SDK（API 细节见 `references/api-quickstart.md`）。

### B. auto-detect（不确定类型时）

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf unknown.pdf \
  --auto-detect \
  --output raw/manuals/foo/    # 类型识别后产物仍落用户指定目录
```

**auto-detect 流程**（详见 `references/auto-detect.md`）：

1. 读 PDF 元数据（Title / Subject / Keywords / Producer）+ 首页文本
2. 本地启发式打分（KEYWORD_HINTS 表）→ 高置信度直接返回；否则进入 3
3. 把首页 1-3 页渲染给 Gemini 多模态识别 → 返回 paper / manual / whitepaper / book

失败时（启发式不足 + Gemini 验证异常）：报错 + 4 类候选 + 建议用户显式传 `--type`。

### C. 4 类输出模板（章节骨架 SSOT 在 `assets/template-*.md`）

完整模板与图引用规范见 `assets/template-{paper,manual,whitepaper,book}.md`。
**任何模板变更只需要改对应 `template-<type>.md`，SKILL.md 不重抄避免散落。**

#### paper quick（默认）

学术论文速读版。详见 `assets/template-paper.md` §quick 模式 + `assets/_base.md`。

```text
章节顺序：
  开篇 3 列表格（Title / Venue / Topic）
  + 论文链接 item（含 > <TODO> 占位）
  + 团队/机构 item
  → ## 3 句话总结
  → ## 背景与动机
  → ## 方法设计    ─┐ 二选一
  → ## 代表性实验结果 ─┘
       或 评测设计 + 评测发现（评测 / benchmark 类论文）
  → ## 业务启示 & 价值（含开源实现 / 相关工作子段）
  → ## 局限与未来工作
  → ## 启发 / 追问（仅 --focus 时输出）

字符目标 ≤ 2500；含图（默认）。
```

#### paper full（`--full`）

按 PDF 原生章节顺序全量转写。详见 `assets/template-paper.md` §full 模式 +
`references/full-mode-contract.md`。

```text
章节顺序：严格按 PDF 原生 Section N / Section N.M / Section N.M.K 顺序展开
必保真元素：Definition / Theorem / Lemma / Corollary / Algorithm 标注 + 公式 $...$ +
            表格行级转写 + 数字精度 3 位有效数字
图处理：mermaidjs block（架构 / 概念）/ markdown 表格（数据可视化）/ 文字一句（装饰图省略）
字符目标：解除上限；token 紧张时优先精简措辞、缩例子；禁止合并整段 / 删小节 / 跳公式
产物：<output>/<slug>.quick.md + <slug>.full.md（quick 用 academic 模板 + 带图；full 自包含无图）
```

#### manual（产品手册 / datasheet / 用户手册；full 风格全文级转写）

详见 `assets/template-manual.md`。

```text
章节顺序：严格按 PDF 原生目录结构逐小节展开（Section N / Section N.M / Appendix）
          原英文标题保留（如 ## Hardware Specifications、## Installation Guide）

必保真元素：命令清单 / API endpoint（fenced code block）
            参数 / 配置 / 环境变量表（markdown 表格，3 位有效数字）
            错误码 / 异常表（markdown 表格）
            产品参数表（型号 / 容量 / 性能 / 接口 / 协议 / 标准）
            章节末尾的故障排查 / FAQ / 更新日志要点（manual 特色，原样保留）
            术语表 / Glossary / 参考链接（附录）

图处理：架构 / 模块关系 → mermaidjs block；数据图 → markdown 表格；装饰图省略
字符目标：无上限；完整性 > 篇幅；token 超限时先详写前 N 章 + 末章占位
不含原始 PNG；产物 <output>/summary.md（单文件）
```

#### whitepaper（行业 / 技术 / vendor 白皮书；full 风格全文级转写）

详见 `assets/template-whitepaper.md`。

```text
章节顺序：严格按 PDF 原生目录结构逐小节展开（Executive Summary / Market Analysis /
          Challenge / Solution / Case Studies / Conclusion 等）
          原英文标题保留（如 ## Executive Summary、## Market Analysis）

必保真元素：行业数据表（市场规模 / CAGR / 渗透率，3 位有效数字）
            对比表 / benchmark 表（vendor 对比 / 方案对比）
            客户案例 / 实证数据（ROI / 收益 / 客户名）
            章节末尾的 Conclusion / Key Takeaways / Recommendations（whitepaper 特色，原样保留）
            About the Publisher / Methodology / References（附录）

立场甄别：vendor 自家方案 vs 行业中立 vs 学术 / 政策 / 咨询——必须在元信息段"发布立场"标注，
          立场影响读者如何解读结论，识别不出时写"原文未明确"

图处理：架构 / 价值链 / 流程 → mermaidjs block；数据图 → markdown 表格；装饰图省略
字符目标：无上限；完整性 > 篇幅；token 超限时先详写前 N 章 + 末章占位
不含原始 PNG；产物 <output>/summary.md（单文件）
```

#### book（书籍 / 长篇技术文档；仅 full 模式）

详见 `assets/template-book.md`。

```text
章节顺序：严格按 PDF 原生 Chapter / Part / Appendix / Index 顺序
必保真元素：章节标题层级 / Definition-Theorem-Lemma-Algorithm 标注 / 公式 / 表格 / 代码 /
            章节末尾小结 + 思考题 + 参考文献 / 索引（term → page 列表原样保留）
字符目标：无上限；完整性 > 篇幅；token 超限时先详写前 N 章 + 末章占位
不含图（mermaid / 表格 / ASCII）。
产物：<output>/<slug>.md（单文件，章节级展开）
```

### D. 与 llm-wiki-management 的接力

> **本 skill 只产出本地文件**——manual / whitepaper / book 全程不抽原始图；
> paper full / book 自包含；paper quick 默认带图（PNG）。
> **上传到 outline-wiki 不归本 skill 管**。

**端到端工作流（PDF → wiki 沉淀）**：

```text
1. 本 skill：跑 gemini_pdf_summary.py --type <type> --output <dir>
   产出 <dir>/summary.md（paper quick 同时含 figures/*.png）
2. 把产物复制到 <wiki-root>/raw/<type>/<slug>/（保持 llm-wiki 仓布局）
3. llm-wiki-management：跑 ingest_diff.py 发现 raw 新增
   → 生成 wiki/sources/<slug>.md（含 frontmatter type: source + sources 字段指向 raw 路径）
   → 同步 entity / concept 页（如有）
   → 更新 index.md + log.md
```

**反模式**（**别**这么干）：

- 把 PDF 总结直接写在 outline-wiki 文档里而**不**走 wiki ingest——丢失 source 页 frontmatter 与交叉引用
- 把产物落到与 `--type` 不匹配的目录（如 `--type manual` 却落到 `raw/papers/`）——ingest_diff 找不到
  （**注**：`raw/papers/` 在本行仅作反例，不代表 layout 标准；4 类 layout 见 §工作流 §A Step 2 反问提示）
- 假设本 skill 会**自动**推到 outline-wiki——**不会**，本 skill 只到本地为止

### E. 故障排查

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `ModuleNotFoundError: google.genai` | SDK 未装 | `pip install --user --break-system-packages google-genai` |
| `import fitz` 失败 / pymupdf 缺失 | pymupdf 未装 | `pip install --user --break-system-packages pymupdf` |
| `DefaultCredentialsError` / `api_key not set` | 缺 `GEMINI_API_KEY` | `export GEMINI_API_KEY=...` 或 `.env` + `direnv` |
| `400 INVALID_ARGUMENT` + `mime type` 报错 | PDF 损坏 / 加密 / 非 PDF 头 | 用 `file <pdf>` 核实；解密或重新下载 |
| `413 REQUEST_TOO_LARGE` | PDF 超 50 MB | 走 File API 上传（见 `references/api-quickstart.md` §超大 PDF） |
| `必须传 --type 或 --auto-detect 二者之一` | 调用缺类型 | agent 反问用户确定类型（见 §工作流 §A） |
| `--auto-detect` 都判定不出 | 启发式 + Gemini 都置信不足 | 显式传 `--type <paper\|manual\|whitepaper\|book>` |
| `book 类型仅支持 full 模式` | 试图 `--type book` 不带 `--full` | 加 `--full`，或改用 `paper` 类型 |
| `manual / whitepaper / book 仅支持 full 风格` | 试图 `--type manual` 等后传 `--no-figures` 关闭 mermaid | 关闭 `--no-figures`；manual / whitepaper / book 是 full 风格，不接受"压缩总结"模式 |
| 模型 404 | 模型名拼错或已下线 | 用 `gemini-api-docs-mcp` 的 `get_current_model` 查当前可用模型 |
| 用 deprecated 模型（`gemini-2.5-*`）跑通了但快 shutdown | 模型还在生效但已 deprecated | 迁移到 `gemini-3.5-flash`（默认）或 `gemini-3.1-pro-preview` |
| 跑出来字符数远超 prompt 里声明的目标 | Gemini 不严格遵守 prompt 字符数约束 | 先调 prompt（具体值在 `assets/template-*.md`）/ `--focus`；后处理裁剪 |
| 输出空 / 截断 | 撞输出 token 上限 | paper quick → 调 prompt 字符目标（SSOT 见 `assets/template-paper.md`）/ `--focus`；full / book 截尾 → 多为模型未保真转写，换模型重跑或拆书 |
| `503 UNAVAILABLE` / `429 RESOURCE_EXHAUSTED` 重试 3 次后仍失败 | 主模型暂时不可用 / 限流 | **端到端不降级**——脚本直接抛错（含 model 名 + status + 三步建议）；**agent 收到此错不得自行换模型重跑**，须如实报给用户、由用户决定是否 `--model` 显式重试 |
| 产出的 md 里出现 `![图 N](PDF p.X ...)` 引用 | 非 paper 类型或 paper full 模式产物 | **自动处理**：脚本 `strip_pdf_figure_refs` 在 main 末尾清理；如出现说明 prompt 漏改 |

## 参考样例

### 样例一：单篇论文总结

**用户**："帮我把 `~/papers/attention_is_all_you_need.pdf` 总结成中文"

**agent 工作流**：
1. 用户已说明是论文 → `--type paper`
2. 反问输出路径 → 用户答 `~/papers/summaries/attention_is_all_you_need/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/papers/attention_is_all_you_need.pdf \
  --type paper \
  --output ~/papers/summaries/attention_is_all_you_need  # 目录：summary.md + figures/*.png
```

### 样例二：产品手册（manual · full 风格）

**用户**："这是我们新硬件的 datasheet，整理一下"

**agent 工作流**：
1. 用户提到 datasheet → `--type manual`
2. 反问输出路径 → 用户答 `~/wiki/llm-systems/raw/manuals/h100-sxm/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/h100-sxm-datasheet.pdf \
  --type manual \
  --output ~/wiki/llm-systems/raw/manuals/h100-sxm/
# 产物：summary.md（按 PDF 原生章节顺序全文级转写；含命令清单 / 参数表 / 错误码 / 故障排查；无 PNG）
# 产物供 llm-wiki ingest_diff 二次蒸馏，不直接给人阅读
```

### 样例三：行业白皮书（whitepaper · full 风格）

**用户**："读一下这份 Gartner 关于 AI Infra 的报告"

**agent 工作流**：
1. "Gartner 报告" → `--type whitepaper`
2. 反问输出路径 → 用户答 `~/wiki/industry/raw/whitepapers/ai-infra-2026/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/gartner-ai-infra-2026.pdf \
  --type whitepaper \
  --output ~/wiki/industry/raw/whitepapers/ai-infra-2026/
# 产物：summary.md（按 PDF 原生章节顺序全文级转写；含行业数据表 / 对比表 / 客户案例 /
#         章节末尾的 Conclusion + Key Takeaways；无 PNG；发布立场"行业中立"在元信息段标注）
# 产物供 llm-wiki ingest_diff 二次蒸馏，不直接给人阅读
```

### 样例四：书籍（full 模式）

**用户**："我想把这本《Crafting Interpreters》转成 markdown 方便后续 Q&A"

**agent 工作流**：
1. 书籍 → `--type book`（脚本自动启用 `--full`）
2. 反问输出路径 → 用户答 `~/wiki/llm-systems/raw/books/crafting-interpreters/`

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/books/crafting-interpreters.pdf \
  --type book \
  --model gemini-3.1-pro-preview \
  --output ~/wiki/llm-systems/raw/books/crafting-interpreters/
# 产物：<slug>.md（按 Chapter / Part / Appendix 顺序全量转写）
# book 默认 token 预算高，建议显式传 --model pro-preview
```

### 样例五：不确定类型（auto-detect）

**用户**："总结一下这份 PDF"

**agent 工作流**：
1. 用户没说类型 → 用 `--auto-detect`；同时反问输出路径

**执行**：

```bash
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/unknown.pdf \
  --auto-detect \
  --output ~/wiki/llm-systems/raw/manuals/foo/    # 类型由 auto-detect 决定，路径仍是用户指定
# 脚本 INFO: auto-detect 判定 --type manual
# 产物：summary.md（manual 模板）
```

## 配套引用

- **共享基础约定**：`assets/_base.md` —— 4 类模板共用的 API 调用 / 风格基线 / 字符数纪律 / 图表处理规则
- **paper quick + full 模板**：`assets/template-paper.md`
- **manual 模板**：`assets/template-manual.md`
- **whitepaper 模板**：`assets/template-whitepaper.md`
- **book 模板**：`assets/template-book.md`
- **API 快速上手**：`references/api-quickstart.md` —— 直接调 SDK 时的样例 + 超大 PDF 的 File API 走法
- **auto-detect 实现细节**：`references/auto-detect.md` —— 启发式关键词表 + Gemini 验证流程 + 失败兜底
- **paper quick 图导出**：`references/figure-extraction.md` —— Stage 1/2 + caption locator + bbox sanity check
- **paper full 契约**：`references/full-mode-contract.md` —— `--full` 模式的产物约束 / 完整性校验 / token 预算
- **生成后自检**：`references/post-generation-self-check.md` —— 引用完整性 / mermaid 语法 / 行宽 / 章节完整性

## 前置条件

```text
1. Python ≥ 3.7
2. pip install -U google-genai
3. pip install --user --break-system-packages pymupdf   # paper quick 图导出 / auto-detect 需要
4. export GEMINI_API_KEY="你的 key"   # 在 https://aistudio.google.com/apikey 创建
```

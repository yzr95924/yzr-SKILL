---
name: gemini-pdf-summary
description: 用户给出一份本地 PDF（论文 / 产品手册 / datasheet / 用户手册 / 行业白皮书 / vendor 技术白皮书 / 书籍 / 长篇技术文档），需要按文档类型路由到对应模板、用 Gemini 多模态直读 PDF（含图表 / 公式 / 版式，不抽 OCR）输出中文结构化 Markdown 时使用本 skill。`--type` 必填（paper / manual / whitepaper / book 四选一；不确定用 `--auto-detect`）。支持 4 种产物模式：paper quick（精炼速读带图）/ paper full（全文级 PDF→Markdown 转写，单产物）/ manual/whitepaper/book single-full（单文件全文级）/ by-chapter（默认 L1 模式按 PDF 原生 L1 章拆 N 个 .md + TOC，供 llm-wiki 多次 ingest）。**不适用**：非 PDF 来源、逐字翻译、关键词抽取、多份对比。常见触发："老板扔来一份英文产品 datasheet 让我先做中文速读" / "把这本技术书的章节拆成 N 个 .md 方便 wiki ingest" / "这个 PDF 里有大量架构图和公式，纯文本抽取会丢" / "我不确定这 PDF 是论文还是手册，先自动识别一下"。
metadata:
  author: Zuoru YANG
  modify time: 2026-07-07
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
| 模型 ID | ✗ | 默认 `gemini-3.1-pro-preview`（不传 `--model` 即可；2026-07-06 起全 skill 统一默认走 pro-preview，长上下文注意力稳 + mermaid 架构图完整保留）；**仅在有明确理由时**才覆盖，详见下方"模型选型"小节 |
| 关注点 | ✗ | `--focus "重点关注实验部分"` 之类，会追加到 prompt |
| 输出路径 | ✗ | `--output <path>`：paper quick 默认带图时视作**目录**（写 summary.md + figures/）；非 paper 类型 / --no-figures / book / paper full 模式视作 .md 文件路径（或 raw 端目录）；不传则 stdout |
| 模板 / 模式 | ✗ | paper quick 默认；`--full` 启用 paper full 或 book 模式；`--by-chapter` 按章节拆 N 个 .md（与 `--full` 互斥） |
| 章节拆法（by-chapter 配套） | ✗ | `--granularity {L1\|auto}`（**默认 L1**，2026-07-06 起）：L1 按 PDF 原生 L1 章 N 次独立 API 调用 + L2 子节合并进 L1（自带 File API 缓存，节省 N-1 次上传）；auto 单次调用（仅适用 ≤ 50 页短 PDF，>50 页走 pre-flight 拒绝并推荐 L1） |
| 页范围（auto by-chapter 配套） | ✗ | `--pages 1-50`：先用 PyMuPDF 切页范围再交给 Gemini；与 `--by-chapter --granularity auto` 组合可拆超长 PDF。**L1 模式下传 --pages 会报错**（L1 按章自动切页） |
| 提取图片 | ✗ | 仅 paper quick 生效：`--no-figures` 关闭图导出（手动 / 白皮书 / 书默认即不开图） |
| 渲染倍率 | ✗ | `--figure-dpi 2.0`（默认 2.0；**144 DPI = 72 × 2.0 换算值**，并非独立阈值；改 `--figure-dpi` 时本表无需同步），仅 paper quick 图导出启用时生效 |
| 图片格式 | ✗ | `--figure-format {png,webp,jpeg}`，默认 png；webp/jpeg 时可用 `--figure-quality` 压缩 |
| 压缩质量 | ✗ | `--figure-quality 1-100`，默认 85；仅 webp/jpeg 生效 |
| 像素上限 | ✗ | `--max-width N`，渲染后等比缩放到 ≤ N px 宽；None 不限制 |
| 体积上限 | ✗ | `--max-size-kb N`，超 N KB 自动降级（quality → format → scale）；None 不限制 |
| 缩略图 | ✗ | `--thumbnail` 额外生成缩略图；`--thumbnail-width`（默认 400px）控制宽度 |
| Stage 2 视觉定位 | ✗ | `--refine-figures / --no-refine-figures`（默认 True），仅 paper quick 生效 |
| Stage 2 渲染倍率 | ✗ | `--refine-dpi 2.0`，仅 paper quick 启用 refine 时生效 |
| Stage 2 模型 | ✗ | `--refine-model <id>`（2026-07-06 加），仅 paper quick + `--refine-figures` 生效；默认 None → 跟 `--model` 走。详见 §模型选型小节 |
| 强制覆盖 | ✗ | `--force-full`，仅 paper `--full` 模式生效；raw 端产物已存在时默认拒绝覆盖 |

### 模型选型

> **默认 = 不传 `--model`**。脚本默认值 `gemini-3.1-pro-preview` 是全 skill 统一默认
> （2026-07-06 决策）：
>
> - 3.5-flash 在 `--by-chapter` 单调用 + JSON 结构化输出下撞 `FULL_MAX_OUTPUT_TOKENS` 上限实测不可用
> - pro-preview 长上下文注意力更稳、mermaid 架构图完整保留（flash 在结构化输出下会默默丢 mermaid block）
> - 4 类文档（paper / manual / whitepaper / book）统一走 pro-preview，不再按模式特判
>
> **不知道选什么 / 没特殊理由 → 直接用默认**。

**判断流程**：

```text
1. 跑 gemini_pdf_summary.py（不传 --model，用默认 pro-preview）
2. 输出不满意？
   ├─ 否 → 用默认就好
   └─ 是 → 先调 prompt（--focus 或改 template-*.md），再考虑换模型
3. 真要换模型 → 从下方"当前推荐"里按场景选；不要凭印象写 model 字符串
```

**当前推荐（基于 gemini-api-docs-mcp 实测 + 本地 by-chapter 实测，2026-07）**：

| 模型 | 状态 | 定位 | 何时显式覆盖（vs 默认） |
| --- | --- | --- | --- |
| `gemini-3.1-pro-preview`（**默认，全 skill 统一**） | Preview | 复杂推理最强 + 长上下文稳 | 大多数场景下不传 `--model` 即可 |
| `gemini-3.5-flash` | Stable | 通用质量/成本最优 | 批量过稿 / 简单综述 / 上下文大但要求低（**已知风险**：结构化输出下会丢 mermaid block，--by-chapter 单调用易撞 `FULL_MAX_OUTPUT_TOKENS` 上限） |
| `gemini-3.1-flash-lite` | Stable | 最便宜、轻量 | 海量低成本过稿 / 摘要 / 内容探索 |

> **主模型不可用 → 报错退出，端到端不降级**（2026-06-30 强化，2026-07-01 补 agent 盲区）：
> 上表里**任一**模型遇到 503 / 429 / 5xx，脚本走 3 次重试后**直接抛错**给上层——
> 绝不静默切到 lite/pro 或其它便宜模型。**且 agent 收到此错也不得自行换模型重跑**
> （脚本错误里的"用 `--model <id>` 换模型"是给用户的、不是给 agent 的指令），须如实
> 把错误 + 三步建议呈现给用户，由用户决定。换模型必须用 `--model <id>` 显式指定，
> **完整策略见 §核心原则 #8**（包含错误信息格式与三步建议）。

> **Stage 2 可独立配模型**（2026-07-06 加 `--refine-model`，仅 paper quick + `--refine-figures` 生效）：
> Stage 2 是单页 PNG + 结构化 JSON bbox/caption 输出，任务简单、不是长上下文推理，
> 理论上 `flash-lite` 够用。可拆模型配置：
> ```bash
> # 主总结 pro-preview（保复杂推理 + 长文稳）+ Stage 2 flash-lite（保结构化输出 + 降 503 概率 + 便宜）
> python3 gemini_pdf_summary.py --pdf paper.pdf --type paper \
>   --model gemini-3.1-pro-preview --refine-model gemini-3.1-flash-lite
> ```
> 默认 `--refine-model` 为 None → Stage 2 跟 `--model` 走，保持旧行为不变。
> 拆分后如出现 bbox 精度退化（图切到 caption / 多框无关内容），回退到不传 `--refine-model` 让 Stage 2 跟主模型走。

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
- **by-chapter**（`--by-chapter`，4 类文档通用，**默认 L1** 模式，2026-07-06 起）：按 PDF 原生 L1 章 N 次独立 API 调用 + L2 子节合并进 L1。
  产物 layout 是 `<output>/00-index.md`（N_L1 行 TOC）+ `<output>/01-<L1-slug>.md`（含 ## L1.title + ### L2 子节）+ ...。
  **L1 模式自带 File API 缓存**（PDF > 20MB 走 File API upload 1 次 + N 次 `Part.from_uri()` 引用，节省 N-1 次上传 token）。
  L2/L3 等细粒度可通过单 L1 内的 Gemini 拆分自然获得；旧 `auto` 模式（单次 API 调用，Gemini 自决粒度）保留供 ≤ 50 页短 PDF + 习惯旧行为的用户使用，
  > 50 页走 pre-flight 拦截并推荐 L1。详细契约见 `references/full-mode-contract.md` §by-chapter

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
     概念用 ` ```mermaid ` block（架构 / 流程图）/ markdown 表格（数据可视化图）/
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
9. **Markdown 风格约定（仓库统一基线）**——详细 10 节规则见
   [`references/markdown-style.md`](references/markdown-style.md)。SKILL.md 只点 3 条关键：
   - bullet marker 一律用 `*`（不要 `-` 或 `+`）
   - mermaid 块放在 bullet 外（block-level），不要嵌 bullet 子项内
   - **数学 / 范围 / 公式禁用 MathJax**：`$...$` / `$$...$$` outline-wiki 不渲染——
     改纯文本 / Unicode（`[1, 2^64)` / `2⁶⁴` / `≥` `≤` `×` → `≈`）；
     book 模板的全文级转写产物可保留 `$...$` 行内公式（agent Q&A 场景可消费 LaTeX）

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

**Step 1 — 类型 + 拆法 + 输出路径 三维反问**（**关键**：脚本强制要求）：

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

**Step 1b — 拆法反问**（**关键**：仅在 --by-chapter 模式下生效）：

```text
1. 跑 --by-chapter 前，agent 必须反问拆法（**禁止 agent 拍板粒度**——粒度差异
   直接决定产物文件数 + 后续 ingest 路径）：
     "希望按什么粒度拆？
      - L1 (默认): 按 PDF 原生 L1 章 N 次独立调用 + L2 子节合并进 L1。
        产物少、撞 token 限概率近 0、自带 File API 缓存。
        例：98 页白皮书 14 个 L1 章 → 14 个 .md
      - auto: 单次 API 调用，Gemini 自决粒度。仅适用 ≤ 50 页短 PDF。
        例：98 页白皮书 1 次调用 → 35%+ 章节截断（不推荐长 PDF）"
2. 用户回答后传 --granularity <L1|auto>（默认 L1，不传走 L1）
3. **不**反问场景：用户已说"按章节拆"未指定粒度 → agent 仍需反问要 L1 还是 auto
   （"按章节"是模糊诉求；体验教训：98 页白皮书直接拆出 118 个细粒度 .md，
   后续合并丢数据，见 /root/gemini-white-paper-err.md）
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

   # by-chapter 模式（默认 L1，2026-07-06 起）：
   python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
     --pdf <path> \
     --type <type> \
     --by-chapter \
     --granularity L1         # 默认；可省略；长 PDF 首选
     # --granularity auto     # 单次调用，仅 ≤ 50 页短 PDF
     --output <output-dir>
   # L1 模式产物：<output>/00-index.md + N_L1 个 <NN>-<L1-slug>.md
5. 把生成的 Markdown 总结（含图）呈现给用户
6. 标注所用模型与 PDF 文件名
7. **失败处理（重要）**：若第 4 步脚本抛 RuntimeError（503/429/5xx 重试耗尽），
   agent **不得**自行加 `--model` 换便宜模型重跑——把错误原文 + 三步建议如实
   呈现给用户并停下，换不换模型由用户决定（见 §核心原则 #8 端到端不降级）
8. **by-chapter 失败处理**：L1 模式下若个别 L1 章失败，脚本写 FAILED-<slug>.md
   占位 + 继续后续 L1（不中断）；00-index.md 标 ⚠FAILED 指向失败项；agent 可
   单独用 `--pages <失败页范围> --granularity auto` 重跑失败段。
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

4 类文档的章节骨架块与 5 个参考样例已下放到
[`references/output-skeletons-and-examples.md`](references/output-skeletons-and-examples.md)
——本节只点出每个类型的"消费对象"差异（人在读 vs LLM 在读），详细骨架与样例读那个文件即可。

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
| 用 deprecated 模型（`gemini-2.5-*`）跑通了但快 shutdown | 模型还在生效但已 deprecated | 迁移到 `gemini-3.1-pro-preview`（默认）或 `gemini-3.5-flash` / `gemini-3.1-flash-lite` |
| 跑出来字符数远超 prompt 里声明的目标 | Gemini 不严格遵守 prompt 字符数约束 | 先调 prompt（具体值在 `assets/template-*.md`）/ `--focus`；后处理裁剪 |
| 输出空 / 截断 | 撞输出 token 上限 | paper quick → 调 prompt 字符目标（SSOT 见 `assets/template-paper.md`）/ `--focus`；full / book 截尾 → 多为模型未保真转写，换模型重跑或拆书；**`--by-chapter` 末位章节截断** → 已是 pro-preview 默认，用 `--pages` 拆段重跑末段（详见 `references/full-mode-contract.md` §by-chapter） |
| `--by-chapter` 与 `--full` 互斥 | 同时传了 `--by-chapter --full` | 二选一：`--full` 走 paper full 单产物（`.full.md`）；`--by-chapter` 走 N 次 API 按 L1 章拆 N 个 .md（默认 L1） |
| `--by-chapter --granularity auto` + PDF > 50 页 + 无 `--pages` | 单次 API 调用撞 `FULL_MAX_OUTPUT_TOKENS` 上限 → 末位章节截断（实测 35%+） | 改用 `--granularity L1`（默认）：按 PDF 原生 L1 章 N 次独立调用，每章 ≤ 50 页撞限概率近 0 |
| `--by-chapter --granularity L1` + `--pages` | L1 模式按章自动切页，`--pages` 不兼容 | 删 `--pages`；L1 模式按 PDF 原生 L1 章边界自动切。如需按自定义页段拆 → 改用 `--granularity auto` |
| L1 模式缺 pymupdf | `--granularity L1` 需要 PyMuPDF 读 TOC + 切页 | `pip install --user --break-system-packages pymupdf`；或改 `--granularity auto` 走单次调用（不需 pymupdf） |
| L1 模式 PDF 无 TOC | PDF 未嵌 bookmarks / outline | 脚本自动 fallback `--granularity auto`（stderr WARN 提示）；如需严格 L1 拆 → 重新生成 PDF 时加 bookmarks |
| L1 模式某 L1 章失败 | 该 L1 页范围 API 调用抛错（API 限流 / PDF 损坏等） | 脚本写 `FAILED-<slug>.md` 占位 + 继续后续 L1；agent 可单独 `--pages <失败页范围> --granularity auto` 重跑 |
| L1 模式 File API 上传失败 | PDF > 20MB 时 L1 模式依赖 File API 缓存 | 脚本直接抛错（不静默退 inline——inline 无法跨调用复用）；处置：1) 重试  2) `--granularity auto` 走单次调用  3) 缩小 PDF |
| by-chapter 产物里出现 `< 100B` 空文件 | 模型放弃的章节（截断 / 内容缺失） | 脚本自动清理 + stderr WARN 数字（00-index.md 仍含原引用，必要时手删或重跑） |
| `503 UNAVAILABLE` / `429 RESOURCE_EXHAUSTED` 重试 3 次后仍失败 | 主模型暂时不可用 / 限流 | **端到端不降级**——脚本直接抛错（含 model 名 + status + 三步建议）；**agent 收到此错不得自行换模型重跑**，须如实报给用户、由用户决定是否 `--model` 显式重试 |
| 产出的 md 里出现 `![图 N](PDF p.X ...)` 引用 | 非 paper 类型或 paper full 模式产物 | **自动处理**：脚本 `strip_pdf_figure_refs` 在 main 末尾清理；如出现说明 prompt 漏改 |

## 参考样例

5 个端到端样例（单篇论文 / 产品手册 / 白皮书 / 书籍 / auto-detect）已下放到
[`references/output-skeletons-and-examples.md` §参考样例](references/output-skeletons-and-examples.md#参考样例)
——每个样例含"用户原话 → agent 反问 → 最终 bash 调用 + 产物说明"。

## 配套引用

- **4 类模板骨架 + 参考样例**：`references/output-skeletons-and-examples.md` —— SKILL.md §C / §参考样例的下放层（章节骨架块 + 5 个端到端样例）
- **共享基础约定**：`assets/_base.md` —— 4 类模板共用的 API 调用 / 风格基线 / 字符数纪律 / 图表处理规则
- **paper quick + full 模板**：`assets/template-paper.md`
- **manual 模板**：`assets/template-manual.md`
- **whitepaper 模板**：`assets/template-whitepaper.md`
- **book 模板**：`assets/template-book.md`
- **API 快速上手**：`references/api-quickstart.md` —— 直接调 SDK 时的样例 + 超大 PDF 的 File API 走法
- **auto-detect 实现细节**：`references/auto-detect.md` —— 启发式关键词表 + Gemini 验证流程 + 失败兜底
- **paper quick 图导出**：`references/figure-extraction.md` —— Stage 1/2 + caption locator + bbox sanity check
- **Stage 2 / 图大小 / 缩略图参数**：`references/figure-processing.md` —— `--refine-figures` / `--figure-dpi` / `--thumbnail` 等详细规范
- **4 类模板对照速查**：`references/templates.md` —— 维度对照表 / 模板变更规则 / 加新类型 checklist
- **paper full 契约**：`references/full-mode-contract.md` —— `--full` 模式的产物约束 / 完整性校验 / token 预算

## 前置条件

```text
1. Python ≥ 3.7
2. pip install -U google-genai
3. pip install --user --break-system-packages pymupdf   # paper quick 图导出 / auto-detect 需要
4. export GEMINI_API_KEY="你的 key"   # 在 https://aistudio.google.com/apikey 创建
```

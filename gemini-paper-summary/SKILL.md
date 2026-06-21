---
name: gemini-paper-summary
description: 用 Gemini 多模态读 PDF 论文并按 outline 风格结构化模板（开篇 3 列表格 + 团队 item + 3 句话总结 / 背景与动机 / 方法设计 / 代表性实验结果 / 业务启示 & 价值 / 局限与未来工作，**无 Reference / 团队背景介绍 章节**）输出中文 Markdown 总结，默认中文主语、必要时保留英文术语避免歧义。Markdown 风格与 outline-wiki-management 一致（`*` bullet / `==高亮==` / `mermaidjs` block / 表格 / 行宽 ≤ 120）。在用户给出一篇本地 PDF 论文想要快速生成结构化总结、需要在多篇论文里批量过稿、或想用 Gemini 读论文（不抽 OCR）时使用。不适用：非 PDF 来源、要求逐字翻译全文、仅做关键词抽取等。
metadata:
  author: Zuoru YANG
  modify time: 2026-06-20
  category: paper-reading
---

# Gemini Paper Summary

用 Gemini 多模态长上下文直接"读懂"PDF 论文（含图表、公式），按 **outline 风格**
结构化模板输出**中文 Markdown 总结**。**开篇无 `# Reference` / 无独立 `## 团队背景介绍` 章节**——元信息
走 3 列表格（Title / Venue / Topic）+ 引用块链接 + 紧跟论文链接的团队 item，**章节骨架统一为**：
开篇表 + 团队 item → `## 3 句话总结` → `## 背景与动机` / 方法设计 / 代表性实验结果 / 业务启示 & 价值 / 局限与未来工作。
**Markdown 风格与 `outline-wiki-management` 完全对齐**（`*` bullet / `==高亮==` /
` ```mermaidjs ` block-level / 表格 / 行宽 ≤ 120），输出可直接复制到 outline-wiki
或 Obsidian 显示。agent 可以直接调用本 skill 的脚本做单篇或批量总结，
也可以按 `references/api-quickstart.md` 在会话内自行调用 SDK。

> 依赖：Python ≥ 3.6、`google-genai`（`pip install -U google-genai`）、
> 环境变量 `GEMINI_API_KEY`（在 [Google AI Studio](https://aistudio.google.com/apikey) 创建）。
> 详细的依赖与失败排查见文末"前置条件"。

## 何时使用 / 不使用

### 使用

- 用户给出一篇**本地 PDF 论文**，要一份中文结构化总结
- 用户要在多篇论文里**批量过稿**，每篇**精炼速读**（字符数目标单一来源在 `assets/prompt-template.md`）
- 论文含大量图表 / 公式，纯文本抽取（pdftotext / PyPDF2）会丢信息
- 用户希望用 Gemini 直接读 PDF，而不是先 OCR

### 不使用

- 论文不是 PDF（网页、Markdown、纯文本）——先转 PDF 或改用其他 skill
- 需要**逐字翻译 / 复刻全文**（本 skill 是"总结"，不是翻译）
- 需要**对比多篇论文**——本 skill 一次一篇，多篇请调用多次再人工拼接
- 只想抽关键句、抽取式摘要——本 skill 是生成式结构化总结
- 用户不愿或不能提供 `GEMINI_API_KEY`

## 输入 / 输出

### 输入

| 字段 | 必选 | 说明 |
| --- | --- | --- |
| PDF 路径 | ✓ | 本地 `.pdf` 文件，绝对或相对路径均可 |
| `GEMINI_API_KEY` | ✓ | 环境变量 |
| 模型 ID | ✗ | 默认 `gemini-3.5-flash`（不传 `--model` 即可）；**仅在有明确理由时**才覆盖，详见下方"模型选型"小节 |
| 关注点 | ✗ | `--focus "重点关注实验部分"` 之类，会追加到 prompt |
| 输出路径 | ✗ | `--output` 写文件；不传则打印到 stdout |
| 模板 | ✗ | `--template academic`（默认） |
| 提取图片 | ✗ | `--extract-figures` 把关键图截成图片嵌入 Markdown；详见下文 A' |
| 渲染倍率 | ✗ | `--figure-dpi 2.0`（默认 2.0 = 144 DPI），仅 `--extract-figures` 启用时生效 |
| 图片格式 | ✗ | `--figure-format {png,webp,jpeg}`，默认 png；webp/jpeg 时可用 `--figure-quality` 压缩 |
| 压缩质量 | ✗ | `--figure-quality 1-100`，默认 85；仅 webp/jpeg 生效 |
| 像素上限 | ✗ | `--max-width N`，渲染后等比缩放到 ≤ N px 宽；None 不限制 |
| 体积上限 | ✗ | `--max-size-kb N`，超 N KB 自动降级（quality → format → scale）；None 不限制 |
| 缩略图 | ✗ | `--thumbnail` 额外生成缩略图；`--thumbnail-width`（默认 400px）控制宽度 |
| Stage 2 视觉定位 | ✗ | `--refine-figures / --no-refine-figures`（默认 True），详见下文 A' §Stage 2 |
| Stage 2 渲染倍率 | ✗ | `--refine-dpi 2.0`，仅 `--refine-figures` 启用时生效 |

### 模型选型

> **默认 = 不传 `--model`**。脚本默认值 `gemini-3.5-flash` 是经过选型的
> （stable、无 shutdown 日期、官方作为 deprecated 2.5 系列的推荐替代），
> **不知道选什么 / 没特殊理由 → 直接用默认**。

**判断流程**：

```text
1. 跑 gemini_paper_summary.py（不传 --model，用默认）
2. 输出不满意？
   ├─ 否 → 用默认就好
   └─ 是 → 先调 prompt（--focus 或改 prompt-template.md），再考虑换模型
3. 真要换模型 → 从下方"当前推荐"里按场景选；不要凭印象写 model 字符串
```

**当前推荐（基于 gemini-api-docs-mcp 实测，2026-06）**：

| 模型 | 状态 | 定位 | 何时显式覆盖（vs 默认） |
| --- | --- | --- | --- |
| `gemini-3.5-flash`（**默认**） | Stable | 通用质量/成本最优 | 大多数场景下不传 `--model` 即可 |
| `gemini-3.1-flash-lite` | Stable | 最便宜、轻量 | 批量过稿 / 简单综述 / 上下文大但要求低 |
| `gemini-3.1-pro-preview` | Preview | 复杂推理最强 | 形式化证明 / 难数学 / 推理敏感论文 |

**避免使用**：

- ==`gemini-2.5-flash`==：deprecated，官方推荐替代 `gemini-3.5-flash`（**有 shutdown 日期**）
- `gemini-2.5-pro`：deprecated，替代 `gemini-3.1-pro-preview`
- `gemini-2.5-flash-lite`：deprecated，替代 `gemini-3.1-flash-lite`
- 任何 `*-preview-09-2025` / `*-preview-12-2025` 等老 preview snapshot——过期，官方已弃

> **deprecated 系列会随时间关停**。本表里的 shutdown 日期以
> `mcp__gemini-api-docs-mcp__search_documentation` / `get_current_model`
> 实测为准；agent / 用户使用前**先查一次**确认未变。**不要**把 shutdown
> 日期 / deprecated 列表固化到月；本节每年/每季 review 一次。

**反模式**（**别**这么干）：

- 凭印象写 `--model "gemini-2.5-flash"` / 任何 2.5-* 字符串——已 deprecated
- 默认值能用，却"为了稳妥"手动加 `--model <默认>`——多此一举、易写错
- 用 preview 模型但没意识到 preview 限流更严
- 在 prompt / SKILL 注释里**写死** `model="gemini-X.Y-Z"`——模型可用性会变，
  应该走"默认值 / 用户显式覆盖"两路径

### 输出

按 **outline 风格结构化模板** 输出 Markdown（**字符数目标单一来源**：`assets/prompt-template.md` 头部声明 + §基础要求 #4，**不要**在这里再写具体数值——避免双份维护漂移）。**统一章节顺序**：
开篇 3 列表格 → 团队 item（紧跟论文链接） → `## 3 句话总结` → `## 背景与动机` → `## 方法设计` →
`## 代表性实验结果` → `## 业务启示 & 价值` → `## 局限与未来工作`。
**不存在的章节可省略**。"开源实现"与"相关工作 / 高频引用"作为
`## 业务启示 & 价值` 的子段呈现；"启发 / 追问"仅在传 `--focus` 时输出。
**默认中文**（标题、叙述、连接词），但术语、模型名、产品名、库名等必要时
**直接保留英文**（详见下文核心原则 #4 与 #9）。

> **精炼优先**（具体字符数见 `assets/prompt-template.md` 头部，**单一来源**）：**每一段、每一条 bullet 都
> 应该能删则删**——能 1 句话讲清的事不要拆 3 句；能省略的铺垫 / 重复 /
> 概念定义就省略；判断标准："删掉这段读者就理解错 / 漏掉关键信息"
> 才是"必须留"，否则一律砍。总结的密度 > 总结的篇幅。

**开篇结构**（统一，无 A / B 之分）：

```markdown
| **Title** | **Venue** | **Topic** |
|-------|-------|-------|
| 论文全英文标题 | 会议'年份（如 OSDI'06） | 领域关键词 |

* 论文链接（**留空，由用户在 Outline UI 手动填写**；Gemini 不必补）

  > <TODO>

* **团队/机构**：<一作 姓名>、<导师 姓名（如能识别）>；<机构> <Lab 名（如有）>；<Lab 研究方向（如知道）>

## 3 句话总结

1. **论文主旨一句话**：方法 + 关键 insight
2. **核心设计 / 关键数据**：用具体数字说话
3. **落地 / 影响**：被谁采用、超越了什么 baseline
```

**关键约定**：

- **不要**单独的 `## 团队背景介绍` 小节——团队信息**只一条 item** `* **团队/机构**：<作者>；<机构> <Lab（可选）>；<Lab 研究方向（可选）>`，用分号衔接
- **不知道哪个字段就省**（不编造作者姓名 / Lab 名 / 研究方向），但**任何情况下都不要**在团队 item 末尾写论文内容一句话总结（如"针对 X 问题提出 Y 方法"）——
  总结是 `## 3 句话总结` 的职责，不要挤到团队 item 里
- 不另起 `* **背景**：…` / `* **会议级别**：…` 等副条目
- **不要**写"会议级别" / "tier-1?" / "best paper?" / "顶级会议" 这类主观评级——论文本身的会议级别由 doc 标题/3 列表格承载,正文不重复
- `## 3 句话总结` 是开篇后的**第一个**章节（紧跟团队 item），用 3 条编号列表 1-2-3 总结论文主旨，每条 1 句话
  - 句 1 = 论文要解决什么问题、给什么方法
  - 句 2 = 核心设计点 / 关键数据
  - 句 3 = 落地 / 关键 baseline 对比

> **为什么不带 `# Reference` 章节 / 不录作者主页 / 不录参考实现？**
> - 论文标题、作者主页、参考实现等元信息在 outline-wiki 由 `title` 字段
>   承载（且 Gemini 容易**自由发挥编造**作者主页、参考仓库 URL）；
>   再写 `# Reference` 会与 `title` 重复，**且** Gemini 编造链接是常见的
>   错误来源
> - 论文链接字段**保留位置**作为占位符，由用户在 Outline UI 手动填写——
>   这样既统一了本地 Markdown / Obsidian 与 outline-wiki 场景的模板，
>   也避免 Gemini 猜错 URL

**正文章节**（从 `## 背景与动机` 起完全统一）：

```markdown
## 背景与动机

* 论文要解决的领域问题（一句话定位：什么场景、什么痛点）
* 现有方法 / 现状的不足（**2–3 条最关键的**，避免展开成 related work）
* 论文核心目标 / 关键约束 / 假设（一两句话）

> 概念 / 术语 / 数据模型 / 系统组件等细节**不在本章展开**——在
> `## 方法设计` 节里随算法 / 协议一并介绍即可；"## 背景与动机"只
> 负责把"问题是什么、为什么需要解决"讲清楚。

## 方法设计

* 总体架构 / 核心思路
* 关键组件 / 数据结构 / 算法（bullet 嵌套 / mermaid 块示意）
* 关键流程 / 协议
* **主要设计点推荐用 `###` 三级标题单独列出**（参见核心原则 #2）

### 自适应内部节点（示例）

* 4 种节点类型按子节点数量动态选择（Node4 / 16 / 48 / 256）
* 关键 insight：节点大小自适应 + 路径压缩 + 延迟扩展叠加
* 如图 N 所示，<在这里插入图> — <1-2 句说明这张图在方法中的角色>

## 代表性实验结果

* 实验设置（一句话：数据集 / baseline / 评测指标，**不展开**）
* **最关键的 2–3 条**关键性能数据（**保留具体数值**，避免"显著提升"这类空话）；
  优先选最能说明问题的 1–2 个图 / 表，不要把全文实验都搬进来

## 业务启示 & 价值

* 工业界落地 / 后续工作 / 同领域影响
* 关键设计取舍 / 实践中的经验教训
* **开源实现**（若无任何链接则整段省略，参见核心原则 #7）
* **相关工作 / 高频引用**（可选表格，3-5 条；无相关工作时整段省略，参见核心原则 #6）

## 局限与未来工作

* 作者自陈的局限（如有，忠实原文）
* 论文未覆盖但明显是下一步的方向

## 启发 / 追问
（仅在 `--focus` 关注点时输出）
```

完整模板与图引用规范见 `assets/prompt-template.md`。

## 执行原则 / 边界

### 核心原则

1. **PDF 原文直接喂 Gemini，不要先抽文本**
   - 用 `Part.from_bytes(data=<bytes>, mime_type="application/pdf")` 走多模态
   - 不用 pdftotext / PyPDF2 / pdfplumber 之类先抽纯文本（会丢图表、公式）
2. **结构化总结，不是复述**
   - 按 outline 风格模板的**主线顺序与命名**输出（开篇表 → 团队 item →
     `## 3 句话总结` → 背景与动机 → 方法设计 → 代表性实验结果 → 业务启示 & 价值 → 局限与未来工作），**最好每篇不超过
     **（不是"写到 1500 字"——具体数值见 `assets/prompt-template.md`）
   - **不存在的章节可省略**（如纯理论论文无实验数据时省"代表性实验结果"）
   - 关键数据 / 数值必须保留，避免泛泛而谈
   - **"代表性实验结果"小节：最关键的 2–3 条**——挑最能说明问题的 1–2 个
     图 / 表 / 关键数字即可；不要把全文实验数据 / 所有 baseline 对比
     都搬进来，那属于复述而非总结
   - **`## 方法设计` 节内：主要设计点推荐用 `###` 三级标题单独列出**（如
     `### 自适应内部节点` / `### 路径压缩与延迟扩展` / `### 二进制可比键`），
     便于扫读；与 outline-wiki 的二级子小节惯例保持一致。**判定标准**：
     - 单个设计点 ≥ 3 个 bullet
     - 概念独立成段（如算法、数据结构、协议各自独立）
     - 需要配 mermaid 块 / 关键图
     - 读者必须停下来才能理解的概念
   - 少于 2-3 个设计点时退回到 bullet 嵌套即可，**不强求**
   - `###` 标题下的内容仍用 bullet 而非纯段落（与 #9 bullet 约定一致）
3. **忠于原文，不脑补**
   - 论文没说就标"原文未明确"
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
5. **关键架构图 / 概念示意图：(page, fig_num, bbox) 引用 + 内联到对应方法上下文，caption 写到 image alt 字段（v3.2 终版）**

   > **Stage 2（`--refine-figures`）默认开**——除非用户明确说"不要用 Gemini 视觉定位 / 嫌慢 / 不想花 token"，否则**不要**加 `--no-refine-figures`。Stage 2 用 Gemini 看图直接给精确 bbox，能解决边界不准确 / 标题残缺 / 上方留白三个老问题，详细规范见 [`references/figure-processing.md`](references/figure-processing.md)。

   > **图片选择 / 排版 / alt 写法 / 处理不了的图兜底**——这些是给 Gemini 看的真权威规则，
   > 统一收在 `assets/prompt-template.md` §图引用约定。本节只讲 Gemini 看不到的 meta / 流程约束。

   - **图片不包含 caption**（v3.2 终版）：caption 写到 markdown image 的 alt 字段——
     `![图 N: <中文翻译+总结>](<url> "=WxH")` 是 outline UI 唯一渲染为图片下方 caption 文字的通道
   - **三阶段格式**（同一 image 引用在 3 个阶段的不同形态）：
     - Gemini 输出: `![图 N: <中文翻译+总结>](PDF p.<页> fig.<N> bbox=<x0,y0,x1,y1>)`
     - 脚本 `--extract-figures` 处理后: `![图 N: <中文翻译+总结>](figures/figure-pX-fN.png "=WxH")`
     - 推到 outline 后: `![图 N: <中文翻译+总结>](/api/attachments.redirect?id=<uuid> "=WxH")`
   - `=WxH` 由脚本 `embed_figure_refs` 在 `render_figures_to_pngs` 拿到精确像素尺寸后自动注入
   - `fig.N` 是论文里的 Figure 编号，与 alt 文本中的"图 N"对应
   - `bbox=<x0,y0,x1,y1>`（可选，**强烈建议给**）是图在 PDF 中的边界框，
     单位 PDF point（1 point = 1/72 inch），原点在左上角；A4 ≈ 595×842，Letter ≈ 612×792
   - 启用 `--extract-figures` 时，**脚本会用 bbox 精确截取该图本身**（不含 caption，caption 由 markdown 承载）
   - 若不写 bbox：脚本会在该页按 `Figure N:` caption 自动定位，**裁到 caption 顶部**（caption 文字保留给 markdown）
   - 页码以 PDF 实际页码为准（论文首页为 p.1），不要写 "图 1 在第 3 页附近"
   - 若论文没有关键图（如纯理论论文），**完全省略**——既无单独章节也无内联图
6. **相关工作 / 高频引用：作为"业务启示 & 价值"的子段**
   - 不再是独立 `## 高频引用 / Take-aways` 段，而是 `## 业务启示 & 价值` 末尾的
     一个 bullet 子段（如有）
   - 表格列：`#` / 论文（作者-年份 + 标题 + 会议/期刊）/ 一句话核心观点
   - **省略"引用次数"列**——Gemini 难以精确估算，强行写会注水
   - 排序按"对本文重要性"降序，**3-5 条**
   - 重点收录：奠基性工作、近期 SOTA、本文方法的直接前身
   - 剔除一次性提及、自引、与本文方法无直接关系的工作
   - 会议/期刊用领域惯用缩写（NeurIPS / ICML / SIGMOD / VLDB / ICDE / OSDI / TODS / VLDBJ 等），
     不确定时按论文 PDF 中参考文献列表里的写法
   - **引文细节准确度**（关键，避免 Gemini 编造）：
     - 会议/期刊 + 年份**以论文 PDF 中的参考文献列表为准**
     - **不确定时只填作者 + 年份，省略会议/期刊缩写**——宁可留空也不要写错
     - 作者姓名顺序按 PDF 参考列表里的写法，不擅自补全成 `First M. Last`
     - 标题保留 PDF 原文（通常是英文），不擅自翻译或缩写
   - 论文没有引言 / 相关工作章节时（如短文、纯实验报告），整段省略
7. **开源实现：作为"业务启示 & 价值"的子段**
   - 放在 `## 业务启示 & 价值` 段内，不另起 `### 开源实现` 子小节
   - 链接**只从论文正文 / 脚注 / 参考列表里提取**，绝不编造
   - 格式：`- **代码仓库**：<URL>（简述：实现语言 / 仓库活跃度）`、`- **数据集**：...`、`- **在线 Demo**：...`
   - 链接类型不明确时（如脚注里的 project page）归到"代码仓库"那行
   - 若有多个相关链接，可加多行（如 paper-website、video、slides）
   - 论文**完全未提**任何 prototype 链接时，**整段省略**（不要写"无开源"或占位文本）
8. **模型选择**：默认见 §模型选型小节（脚本 `DEFAULT_MODEL` 常量，`scripts/gemini_paper_summary.py:65`）。复杂论文换 `gemini-3.1-pro-preview`，批量速览换 `gemini-3.1-flash-lite`。实际可用模型以当前 Gemini 文档为准（用 `gemini-api-docs-mcp` 的 `get_current_model` 核实）。**为什么不在本条重列默认值**：模型选型表是 SSOT，列在 §模型选型小节里
   - **无自动 fallback**（2026-06-21 决策）：默认模型遇到 503 UNAVAILABLE /
     429 RESOURCE_EXHAUSTED 等高并发 / 限流错误时，脚本**直接抛错**给上层，
     不静默降级。理由：不同模型对 v3.2 prompt 模板的输出质量差异显著
     （alt 字段偏差、表格行数错位、章节遗漏等），silent fallback 用户感知不到
     是模型降级导致的，只看到"结果怪"——质量风险大于便利。换模型用
     `--model <id>` 显式指定。
9. **Markdown 风格约定（与 `outline-wiki-management` 完全对齐）**
   - **bullet marker 一律用 `*`**，**不要**用 `-` 或 `+`（与 `outline-wiki-management`
     的 doc_style.md 基线一致；本仓库其他 skill 也按此约定）
   - **关键术语用 `==text==` 高亮**（默认色），不要硬造彩色语法（Markdown 写不出来）
   - **Mermaid 块 block-level**：` ```mermaidjs ` 放在 bullet 之外，不要嵌在 bullet
     子项内；只用 `graph` 系列（TD / LR）
   - **Mermaid 标识符统一用 `mermaidjs`**：对标准 Markdown 渲染器、outline-wiki、
     Obsidian 都可直接可用，不需要按目标场景手动切换
   - **代码块语言必填**：` ```bash ` / ` ```python ` / ` ```json ` / ` ```yaml ` ，
     **不要**写空语言 ` ``` `
   - **表格 vs bullet**：数据示例 / 概念对比 / 字段定义用 table；其他场景优先 bullet
   - **引用块** 行首 > 加空格 仅在引用原始资料原话时使用，**不要**当容器用
   - **行宽 ≤ 120 字符**（与 `.markdownlint.jsonc` MD013 对齐）
   - **不写 H1**：文档标题由文件名 / 上层目录承载，正文从 `##` 起步
   - **不写私造语法**：`!!! warning` / `:::tip` / MathJax / `<mark>` / `<details>` /
     装饰性 emoji 占位（🎉🎉🎉）等**不要**出现（Outline 不支持，仓库
     `.markdownlint.jsonc` 也会拒）

### 边界

- 只处理本地 PDF；非 PDF 一律先转 PDF
- 不做全文翻译；不做多篇对比
- 一次一篇论文
- 单 PDF 大小建议 ≤ 50 MB（File API 硬上限）
- **实在处理不了的图不入总结**（2026-06-21 用户要求）：
  `render_figures_to_pngs` 的三层定位（Stage 2 visual_bbox → caption locator → bbox hint）
  **全失败**时，整张图从 markdown 里**整行删除**，**且**前一句"如图 N 所示" /
  "见图 N" / "Figure N 展示了..." 等独立呼应句的图编号引用也剥掉（保留描述文字）。
  - 触发场景：Stage 2 视觉定位返回的 bbox 越界 / Gemini 整页调用失败 /
    caption locator 找不到 caption / bbox hint 宽度 < 50pt 等
  - 反模式：**不要**保留 `![图 N: ...](PDF p.X fig.N ...)` 这种没替换的 PDF
    reference 字符串——outline 渲染会成**破图**（`![]()` 协议 outline 不识别）
  - 脚本日志：`INFO: 跳过 N 张图（视觉定位 + caption locator + bbox hint 三层
    均失败），已从 markdown 删除对应行 + 呼应句`
- **正文里的图引用 vs 真 caption 甄别**（2026-06-21 ART-ICDE'13 p.11 Fig 16 case）：
  论文正文常出现 "Figure 16 shows that..." 这类引用，line 文本以
  `Figure N` 开头。原 `find_figure_caption` 简单正则会被这种正文引用命中，
  返回正文 block 的 bbox（而非真 caption），导致 caption locator 把整段正文
  当成 figure 区域。修复：line 文本必须以 `Figure N[.:]` + 描述形式才算 caption
  （`Figure 16 shows...` 中数字后是空格+动词，会被过滤掉）。同时 line 长度
  ≤ 120 字符作为辅助判定。
- **bbox hint sanity check**（2026-06-21）：Stage 1 Gemini 自由发挥写
  `bbox=...` 时容易把 figure 下面紧跟的整段正文都框进去（典型 case：p.11
  Fig 16，hint 高 ~375pt，实际图只有 ~150pt）。`render_figures_to_pngs` 在
  走 bbox hint fallback 前先检查高度：超过 250pt 且 caption locator 能算出更
  紧的 bbox（≥ 50pt）时，用 caption locator 替掉 hint。

## 生成后自检（图片完整性 + 边界破坏）

**Why：** 用户在 2026-06-21 反馈——图片完整性、attachment 上传失败、边界破坏常被遗漏。自检是生成流程的最后一道防线，分 3 层面（引用完整性 / 二进制完整性 / 边界破坏）。

**完整规范见 [`references/post-generation-self-check.md`](references/post-generation-self-check.md)：** 自动化分层、运行时策略、失败处理、visual diff 不自动做的原因。

## 工作流 / 步骤

### A. agent 在会话中调用（推荐流程）

```text
1. 确认 PDF 存在且可读
2. 确认 GEMINI_API_KEY 已设置；未设置则提示用户去 aistudio.google.com/apikey 申请
3. 确认 google-genai 已安装：python3 -c "import google.genai" 或 pip install -U google-genai
4. 调用 scripts/gemini_paper_summary.py：
   python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
     --pdf <path> \
     --output <path-to-md>  # 可省，省略则打印到 stdout
   # 默认值护栏：Stage 2 视觉定位（`--refine-figures`）默认开，
   # 仅在用户明确要求"完全跳过 Gemini 视觉定位"时才加 `--no-refine-figures`
5. 把生成的 Markdown 总结呈现给用户
6. 标注所用模型与论文文件名
```

也可以直接在会话里调 SDK（API 细节见 `references/api-quickstart.md`）。

### A'. 导出关键架构图（推荐做法）

启用 `--extract-figures` 后，脚本会用 pymupdf **只截取 figure 本身的矩形区域**（而非整页），
并把 Markdown 里的 `(PDF p.X fig.N [bbox=...])` 替换为 `figures/figure-pX-fN.png`。
该模式下 `--output` 视作目录路径，目录结构：

```text
<--output 指定的目录>/
├── summary.md              # 自动写到这里
└── figures/
    ├── figure-p1-f1.png    # Figure 1 在第 1 页
    ├── figure-p4-f4.png    # Figure 4 在第 4 页
    ├── figure-p4-f5.png    # Figure 5 在第 4 页（同页多图各自一张）
    └── figure-p5-f6.png    # Figure 6 在第 5 页
```

`summary.md` 中的图引用形如：

```markdown
- ![图 1：自适应基数树节点](figures/figure-p1-f1.png) — 展示了 ART 如何...
- ![图 4：传统基数树对比](figures/figure-p4-f4.png) — ...
```

**截取逻辑**（按优先级，从高到低）：

1. **Stage 2 Gemini 视觉定位**（仅在 `--refine-figures` 启用时）：把页面渲染成 PNG 送给 Gemini
   多模态，让它**用视觉方式**给出每个 figure 的紧致 bbox + 完整 caption + 是否关键图。
   精度最高，且能自动跳过装饰图/logo/坐标轴/表格。详见下文 §Stage 2。
2. **caption 定位**（本地算法，多策略 fallback）：在该页按 `Figure N:` caption 反向推断 figure 区域——
   - 双栏布局下，根据 caption 的 x 中心判断 figure 所在栏（左 / 右）
   - figure 顶部检测按以下三策略按顺序尝试：
     1. **正文段落底部**：caption 上方最近的"宽+多行"正文段落底部（≥2 行 + 宽度 ≥ 栏宽 60%）。
        处理 figure 上方紧跟正文的常见情形。
     2. **annotation 顶部**：caption 上方同一栏所有"非正文"文本块（figure annotation / label /
        节点编号等"窄+单行"块）的最上 y0。**专门解决 figure 上方只有 annotation 没有正文**
        的情形（如 ART-ICDE'13 第 5 页的 Figure 6，caption 上方全是 B/F/A/O/R/O 节点 label +
        path compression / lazy expansion 标注），避免旧版退到 page 顶把 header 全框进来。
     3. **page 顶兜底**：以上都失败时退到 page 顶（保证 figure 一定被框入，但可能含 page header）
3. **Stage 1 Gemini bbox hint**（仅作最后兜底，精度差）：脚本直接用 Stage 1 prompt 嵌入的
   `bbox=x0,y0,x1,y1` 区域裁剪，不做 caption 校验
4. **定位失败**：跳过该图并在 stderr 打印 WARN；Markdown 里的引用保持原样

**已知边界**（无 Stage 2 时，caption 定位 fallback 兜底）：

- 单栏 PDF：caption 定位工作得很好
- 双栏 PDF：每栏各自裁剪，不会跨栏"吃"另一栏的图
- 同一栏上下相邻多张图：上方那张的 caption 会被识别成"正文段落"（策略 1 命中），
  但如果上方那张**没有正文段落**，策略 2 会用 annotation 顶部避免切错
- 图在页顶（如 page 1 标题下方）：caption 上方通常有正文段落，策略 1 命中；
  完全没正文时策略 2 仍可能框到 page header，需要 Stage 2 精修

> **推荐始终启用 `--refine-figures`**（默认开）：Stage 2 用 Gemini 看图直接给精确 bbox，
> 上述三个边界问题基本消失；唯一代价是每张引用页多一次 Gemini 调用 + ~5-15s 延迟。

#### Stage 2 / 大小格式 / 缩略图参数

**何时必须读 [`references/figure-processing.md`](references/figure-processing.md)（默认值护栏外的任何情况）：**

- 用户问 Stage 2 / `--refine-figures` 的具体行为、为什么失败、失败如何兜底
- 用户传 `--no-refine-figures` 或要求"不用 Gemini 视觉定位"
- 用户改 DPI / `--figure-format` / `--thumbnail` / `--max-size-kb` 的预期效果
- 用户问"图被裁错了 / 留白过多 / caption 残缺"等具体故障
- 用户问对照实验 / Stage 2 成本估算

**何时**不**需要读**：日常调脚本（默认值已护栏）→ 直接 `python3 gemini_paper_summary.py --extract-figures` 即可。

**关键摘要**（避免漏读导致错误决策）：

- **Stage 2 默认开**（`--refine-figures`），必须显式 `--no-refine-figures` 才关闭——别凭印象加 `--no-refine-figures` "为了快"
- **算法原理、caption 甄别、bbox sanity check** 见 [`references/figure-extraction.md`](references/figure-extraction.md)
- **默认参数真源**：`scripts/gemini_paper_summary.py` argparse（`--refine-dpi` @ line 1191、`--figure-format` @ line 1146、`--figure-quality` @ line 1152、`--thumbnail-width` @ line 1175、`--figure-dpi` @ line 1140）—— 改默认值先改脚本，再同步本文档表
- **DPI**：Stage 2 与最终输出图各自独立（`--refine-dpi` / `--figure-dpi`）
- **失败兜底**：单页 Stage 2 失败不影响其他页，自动退 caption locator

#### Stage 2 对照实验

把 Stage 2 关闭,与开启的产物做视觉对比:

```bash
# 开启 Stage 2(默认)
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf --output ~/out_with_stage2 \
  --extract-figures

# 关闭 Stage 2
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf --output ~/out_without_stage2 \
  --extract-figures --no-refine-figures

# 对比每张图
ls -la ~/out_with_stage2/figures/ ~/out_without_stage2/figures/
```

### A''. 输出目标与图片处理（跨 skill 分工）

> **本 skill 只产出本地文件**——A' 节的 `--extract-figures` 截下来的
> PNG 全部落在本地 `figures/` 目录，**不会**自动上传到 outline-wiki。
> **上传到 outline-wiki 不归本 skill 管**，请走
> [`outline-wiki-management`](../outline-wiki-management/SKILL.md) 的
> attachment 3 步流程（`create_attachment` → `curl` 上传 → Markdown 引用
> `/api/attachments.redirect?id=...`）。

**按输出目标决定本 skill 的参数**：

| 输出目标 | `--extract-figures` | 理由 |
| --- | --- | --- |
| **本地 Markdown / VS Code / Obsidian** | 可选（按需） | 读者可在本地直接看 `figures/*.png` |
| **直接上传到 outline-wiki** | ==**必须开**== | 关掉的话，Markdown 里的 `![图 N](PDF p.X fig.Y ...)` 引用是**破图**——outline 不识别 PDF 路径 / bbox 引用，必须有真实的 attachment URL |
| 仅文字速读 / 不带图 | 关（默认） | 不需要 PNG，省时间 + pymupdf 依赖 |

**端到端工作流（论文总结 → outline-wiki 笔记含图）**：

```text
1. 本 skill：跑 gemini_paper_summary.py --extract-figures → 产出
   <output_dir>/summary.md + <output_dir>/figures/*.png
2. outline-wiki-management：拿每张 figures/*.png 走 attachment 3 步
   （create_attachment → curl 上传 → 拿到 /api/attachments.redirect?id=...）
3. 用 update_document + editMode=patch + findText 把 summary.md 里的
   ![图 N](figures/figure-pX-fN.png) 替换为
   ![图 N](/api/attachments.redirect?id=<uuid> "=WxH")
4. （可选）删本地 figures/ 目录与 summary.md 的 figures/ 引用条目
```

**反模式**（**别**这么干）：

- 在 outline-wiki 文档里写 `![图 N](figures/figure-p1-f1.png)`——本地路径在
  outline 是**破图**（除非先走 attachment 3 步拿到真 URL）
- 在 outline-wiki 文档里写 `![图 N](PDF p.X fig.Y ...)`——同上
- 假设 gemini-paper-summary 会**自动**把图传到 outline-wiki——**不会**，
  本 skill 只到本地为止

### B. 批量速览

```text
1. 列出目录下所有 *.pdf
2. 对每篇并行（或限流并发）调用 gemini_paper_summary.py
3. 每篇输出文件名 <paper-stem>.summary.md，放在同目录
4. 结束时汇总哪些论文成功 / 失败
```

### C. 故障排查

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `ModuleNotFoundError: google.genai` | SDK 未装 | `pip install --user --break-system-packages google-genai` |
| `--extract-figures` 报 "需要 pymupdf" | pymupdf 未装 | `pip install --user --break-system-packages pymupdf` |
| `DefaultCredentialsError` / `api_key not set` | 缺 `GEMINI_API_KEY` | `export GEMINI_API_KEY=...` 或 `.env` + `direnv` |
| `400 INVALID_ARGUMENT` + `mime type` 报错 | PDF 损坏 / 加密 / 非 PDF 头 | 用 `file <pdf>` 核实；解密或重新下载 |
| `413 REQUEST_TOO_LARGE` | PDF 超 50 MB | 走 File API 上传（见 `references/api-quickstart.md` §超大 PDF） |
| 模型 404 | 模型名拼错或已下线 | 用 `gemini-api-docs-mcp` 的 `get_current_model` 查当前可用模型；避免用 deprecated 系列（`gemini-2.5-*` 等） |
| 用 deprecated 模型（`gemini-2.5-*`）跑通了但快 shutdown | 模型还在生效但已 deprecated | 迁移到 `gemini-3.5-flash`（默认）或 `gemini-3.1-pro-preview`；见"模型选型"小节 |
| 跑出来字符数远超 prompt 里声明的目标 | Gemini 不严格遵守 prompt 字符数约束 | 先调 prompt（具体值在 `assets/prompt-template.md`）/ `--focus`；后处理裁剪；不要靠 prompt 单点约束 |
| 输出空 / 截断 | 输出 token 上限（默认 65k）撞顶 | 减小 `max_output_tokens` 不会影响——缩短 prompt 或换模型 |

## 参考样例

### 样例一：单篇总结

**用户**："帮我把 `~/papers/attention_is_all_you_need.pdf` 总结成中文"

**执行**：

```bash
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention_is_all_you_need.pdf \
  --output ~/papers/attention_is_all_you_need.summary.md
```

把生成的 `.summary.md` 内容呈现给用户，注明所用模型（默认见 §模型选型小节）。

### 样例二：带关注点

**用户**："总结 `~/papers/diffusion.pdf`，重点看数学推导和采样效率"

**执行**：

```bash
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/diffusion.pdf \
  --focus "重点关注数学推导的关键步骤和采样效率优化" \
  --output ~/papers/diffusion.summary.md
```

生成的总结会在"方法 / 关键结果"小节侧重，并在末尾补"启发 / 追问"小节。

### 样例三：批量速览

**用户**："~/papers/ 下面有 20 篇 PDF，帮我每篇 300 字速读一下"

**执行**：

```bash
for pdf in ~/papers/*.pdf; do
  python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
    --pdf "$pdf" \
    --model gemini-3.1-flash-lite \
    --focus "300 字内的速览版" \
    --output "${pdf%.pdf}.summary.md"
done
```

### 样例四：导出关键架构图（让 Markdown 预览能直接看到图）

**用户**："总结 `~/papers/attention.pdf`,关键架构图要能直接看到"

**执行**：

```bash
# 一次性：Gemini 总结 + 渲染关键页为 PNG + 替换 Markdown 引用 + 写文件
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf \
  --output ~/papers/summaries/attention \
  --extract-figures
```

产出：

```text
~/papers/summaries/attention/
├── summary.md
└── figures/
    ├── figure-01-p1.png
    ├── figure-02-p3.png
    └── figure-03-p5.png
```

`summary.md` 中的图引用全部变为相对路径（`figures/figure-01-p1.png`），
在 VS Code / Obsidian / GitHub 等任何 Markdown 预览器里都能直接看到图。

## 前置条件

- **Python ≥ 3.6**（脚本遵循仓库 3.6 兼容规范）
- **`google-genai` Python SDK**（旧 `google-generativeai` 已弃用，请用新包）：
  `pip install -U google-genai`（Debian/WSL 系统 Python 加 `--break-system-packages`）
- **`pymupdf`**（**软依赖**，仅启用 `--extract-figures` 时需要）：
  `pip install --user --break-system-packages pymupdf`
- **`GEMINI_API_KEY`**：
  在 [Google AI Studio](https://aistudio.google.com/apikey) 创建后
  `export GEMINI_API_KEY="你的 key"`
- **可读 PDF 文件**：单文件 ≤ 50 MB；如需处理更大文件改用 File API
  （`references/api-quickstart.md` §超大 PDF）

## 参考文档

- [Gemini API 文档](https://ai.google.dev/gemini-api/docs)
- [google-genai Python SDK](https://github.com/googleapis/python-genai)
- 仓库内 `yzr-skill-creator/`（skill 写作规范）
- 仓库内 `design-doc-edit/`（Markdown 写作规范同源，行宽 ≤ 120）

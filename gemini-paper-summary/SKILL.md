---
name: gemini-paper-summary
description: 用 Gemini 多模态读 PDF 论文并按 outline 风格结构化模板（开篇 3 列表格 + 团队 item + 3 句话总结 / 背景与动机 / 方法 / 实验 / 业务启示&价值 / 局限，**无 Reference / 团队背景介绍 章节**）输出中文 Markdown 总结，默认中文主语、必要时保留英文术语避免歧义。Markdown 风格与 outline-wiki-management 一致（`*` bullet / `==高亮==` / `mermaid` block / 表格 / 行宽 ≤ 120）。在用户给出一篇本地 PDF 论文想要快速生成结构化总结、需要在多篇论文里批量过稿、或想用 Gemini 读论文（不抽 OCR）时使用。不适用：非 PDF 来源、要求逐字翻译全文、仅做关键词抽取等。
metadata:
  author: Zuoru YANG
  modify time: 2026-06-20
  category: paper-reading
---

# Gemini Paper Summary

用 Gemini 多模态长上下文直接"读懂"PDF 论文（含图表、公式），按 **outline 风格**
结构化模板输出**中文 Markdown 总结**。**开篇无 `# Reference` / 无独立 `## 团队背景介绍` 章节**——元信息
走 3 列表格（Title / Venue / Topic）+ 引用块链接 + 紧跟论文链接的团队 item，**章节骨架统一为**：
开篇表 + 团队 item → `## 3 句话总结` → `## 背景与动机` / 方法 / 实验 / 业务启示&价值 / 局限。
**Markdown 风格与 `outline-wiki-management` 完全对齐**（`*` bullet / `==高亮==` /
` ```mermaid ` block-level / 表格 / 行宽 ≤ 120），输出可直接复制到 outline-wiki
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
1. 跑 gemini_paper_summary.py（不传 --model，用默认 gemini-3.5-flash）
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

* **团队/机构**：…（如"麻省理工学院 CSAIL"）；研究背景是…（一句话上下文）

## 3 句话总结

1. **论文主旨一句话**：方法 + 关键 insight
2. **核心设计 / 关键数据**：用具体数字说话
3. **落地 / 影响**：被谁采用、超越了什么 baseline
```

**关键约定**：

- **不要**单独的 `## 团队背景介绍` 小节——团队信息**只一条 item** `* **团队/机构**：<机构>；<一句话研究背景>`，用分号/句号衔接，不另起 `* **背景**：…`
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
     `## 3 句话总结` → 背景与动机 → 方法 → 实验 → 业务启示&价值 → 局限），**最好每篇不超过
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
   - **不**单独成"关键架构图 / 示意图"小节；每张关键图紧贴它说明的算法 /
     协议 / 数据结构那段 bullet 放（"方法 bullet → 图 → caption 文字 → 下一个方法 bullet" 的顺序），
     让读者扫读时不用先看文字再翻到节末找图
   - **图片不包含 caption**（v3.2 终版，2026-06-21）：caption 文字**写到 markdown
     image 的 alt 字段**（`![图 N: <中文翻译+总结>](<url> "=WxH")`）——这是 outline UI
     唯一渲染为图片下方 caption 文字的通道。markdown body **不**写独立的
     `**图 N**：<caption>` 行，也**不**加 `— <role>` 后段（避免与 alt 重复 +
     inline element 短而独立）
   - alt 字段规则：
     - 中文翻译+总结（不是论文英文 caption 原文——面向中文读者，含术语细节的
       英文原文不易扫读）
     - 必须以 `图 N: ` 开头（中文版, 不是 `Figure N: `）
     - 中文 caption 通常 ≤ 100 字符; 个别超 120 也可, markdown 链接不能拆行
   - 格式（v3.2 终版）：
     - Gemini 输出: `![图 N: <中文翻译+总结>](PDF p.<页> fig.<N> bbox=<x0,y0,x1,y1>)`
     - 脚本 `--extract-figures` 处理后: `![图 N: <中文翻译+总结>](figures/figure-pX-fN.png "=WxH")`
     - 推到 outline 后: `![图 N: <中文翻译+总结>](/api/attachments.redirect?id=<uuid> "=WxH")`
     - `=WxH` 由脚本 `embed_figure_refs` 在 `render_figures_to_pngs` 拿到精确像素尺寸后自动注入
   - `fig.N` 是论文里的 Figure 编号，与 alt 文本中的"图 N"对应
   - `bbox=<x0,y0,x1,y1>`（可选，**强烈建议给**）是图在 PDF 中的边界框，
     单位 PDF point（1 point = 1/72 inch），原点在左上角；A4 ≈ 595×842，Letter ≈ 612×792
   - 启用 `--extract-figures` 时，**脚本会用 bbox 精确截取该图本身**（不含 caption，caption 由 markdown 承载）
   - 若不写 bbox：脚本会在该页按 `Figure N:` caption 自动定位，**裁到 caption 顶部**（caption 文字保留给 markdown）
   - 只收录**关键图**：整体架构、核心模块示意、概念流程图、关键对比示意
   - **跳过**纯装饰、坐标轴标注、表格截图、附录图、补充材料中的非核心图
   - 页码以 PDF 实际页码为准（论文首页为 p.1），不要写 "图 1 在第 3 页附近"
   - **图前**一句必须呼应（"如图 N 所示" / "见图 N"），把图和上下文绑死；
     **图后**一句不要重复同样的内容
   - **实在处理不了的图宁可不引**（2026-06-21 用户要求）：如果某张图
     你**自己都没把握准确定位**（figure 跨页 / 编号混乱 / 在附录但正文
     引用），**不要**硬写 `![图 N: ...](PDF p.X fig.N)`——脚本三层定位全失败
     时会**整行删除**该图引用 + 剥掉"如图 N 所示"等呼应句的图编号。**为了
     凑数硬引**会留下"如图 N 所示，xxx" 但图缺失的死引用，比"完全不提"
     还糟。如果**完全不提**这张图，反而更干净。
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
8. **模型选择**
   - 默认 `gemini-3.5-flash`（2026-05 稳定版，质量与成本平衡，支持 PDF + 1M 上下文）
   - 复杂论文可换 `gemini-3.1-pro-preview`（preview，质量更高但成本高）
   - 速览批量过稿可换 `gemini-3.1-flash-lite`（更便宜）
   - 实际可用模型以当前 Gemini 文档为准：用 `gemini-api-docs-mcp` 的 `get_current_model` 核实
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

**Why：** 用户在 2026-06-21 反馈——"最终生成完的论文总结，要自检一下图片是否完整，是否存在图片边界破坏的情况"。单看 doc body 字面 ok 不代表图真的 ok（attachment 可能 0 字节 / doc body 引用的尺寸与实际 PNG 尺寸不一致 / 图片被错误裁剪）。自检是生成流程的**最后一道防线**，分 3 个层面：

| 层面 | 自动化 | 检测什么 | 失败信号 |
| --- | --- | --- | --- |
| 1. 引用完整性 | ✓（脚本） | doc body 里的 `attachments.redirect?id=<id>` 引用 ID 是否在 `attachments.list` 返回中存在 | attachment 被删但 doc 还引用 → 破图 |
| 2. 二进制完整性 | ✓（脚本） | 每个 in-use attachment 的 `attachments.redirect` HEAD 是否 200 + image/... + size > 0 | 0 字节 / HTML 错误页 = 上传失败未发现 |
| 3. 边界破坏 | ✓ + 人工 | (a) 本地 `figures/*.png` 实际像素尺寸 vs markdown title `=WxH` 差 ≥ 5% → 标题尺寸字段失效；(b) 人工到 outline UI 看图是否截断 / 留白过多 / 边界切错 | 裁剪坐标错误 / 重新上传导致 title 尺寸与实际不符 |

**How to apply：**

- **脚本侧**（自动）：`gemini_paper_summary.py` 主流程末尾调 `self_check_figures()`，挂在 `--output` 写文件**之后**、进程退出**之前**；返回 `{ok, warnings[], failures[]}`，不抛异常（warning 继续 / failure 才抛）
  - 阶段 1：parse markdown text 抽 `attachments.redirect?id=<id>` 引用 ID 集合
  - 阶段 2：`attachments.list` 拉真实存在 ID 集合（用 outline API key 走 curl/MCP）→ 差集 = 失效引用
  - 阶段 3：每个 in-use ID 走 `attachments.redirect` HEAD，验证 200 + content-type image/ + size > 0
  - 阶段 4：本地 `figures/` 目录每个 PNG 用 pymupdf 读像素尺寸，对照 markdown 里 `=WxH` title 字段；差 ≥ 5% 警告
  - 输出：`Self-check: 3/3 attachments OK, 0 size mismatch, 0 broken references` 或列出失败项
- **人工侧**（必做）：agent 把生成的 doc 链接给用户后，**让用户在 outline UI 看一眼**3 张图——是否完整、是否截断、是否切到不该切的位置；用户反馈"图破了"再回查（脚本不会自动做视觉 diff）
- **运行时**：本地 summary.md 生成时（`--extract-figures`）走 阶段 1+3+4；推到 outline 后走 阶段 1+2+3；不阻塞主流程（warning log）
- **失败处理**：阶段 1/2/3 失败 → stderr WARNING + 返回值里 `failures[]` 列出，**不抛异常**（生成成功 ≠ 上传成功，agent 据此决定要不要重试 / 走 fallback）；阶段 4 失败 → stderr WARNING（标题尺寸字段失效，UI 仍可显示，只是尺寸不准）

**Why not visual diff 自动做**：outline doc 渲染图含 outline UI chrome（背景色 / padding / 标题区），与原 figure 直接像素 diff 噪声大；可靠方案是按论文 PDF 原 page 渲染 + bbox 内裁剪后与 `figures/*.png` 对比——成本高，作为可选 Step 4b（默认不跑，agent 怀疑有问题时手动启用）。

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

#### Stage 2: Gemini 视觉定位精修（默认开启）

Stage 1 拿到 `PDF p.X fig.N` 引用后,Stage 2 把对应页面渲染成 PNG 送给 Gemini,**用视觉方式**
给出每个 figure 的精确边界 + 完整 caption,直接从源头解决三个老问题:

| 老问题 | Stage 2 怎么解决 |
| --- | --- |
| 边界不准确 | Gemini 看渲染图直接给归一化 0-1000 bbox,按图像像素精确定位,不再是基于 PDF 内容的估算 |
| 图片标题残缺 | Gemini 直接读出图片下方完整 caption(含多行),覆盖 Stage 1 LLM 生成的残缺 alt |
| 上方留白过多 | Gemini 自动判断 figure 顶部边界,不会把页眉/标题/作者框进来 |

**Stage 2 流程**：

```text
Stage 1 输出: "见 PDF p.3 fig.1 / PDF p.4 fig.2 ..."
   ↓
1) 把 p.3 / p.4 渲染成 PNG(默认 2x DPI;改用 --refine-dpi 调整)
   ↓
2) 每页一次 Gemini 调用,prompt 要求返回 JSON:
   { "page": 3, "figures": [
       { "fig_num": 1, "bbox_2d": [ymin,xmin,ymax,xmax],
         "full_caption": "Figure 1: ...",
         "is_key_figure": true }, ...
   ]}
   ↓
3) 把 Gemini 返回的 0-1000 bbox 换算为 PDF point:
   x_pt = x_norm * page.rect.width / 1000
   ↓
4) 用 Stage 2 bbox 替换 Stage 1 提示词里的 bbox hint,再做后续裁剪
5) 把 Stage 2 读出的完整 caption 覆盖 Markdown 里残缺的 alt 文本
```

**坐标约定**(Gemini 官方 `gemini-robotics-er-1.6-preview` 同款):

- `bbox_2d = [ymin, xmin, ymax, xmax]`(y 在前)
- 归一化 0-1000 整数
- 原点在图像左上角
- 渲染图未做宽高变形 → 1000 ↔ 页面 PDF point 的宽/高

**Stage 2 参数**:

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--refine-figures` / `--no-refine-figures` | `True` | 是否启用 Stage 2。关闭后回到 Stage 1 bbox hint + 本地 caption 定位 |
| `--refine-dpi` | `2.0` | Stage 2 渲染页面的 DPI 倍率。增大可提升定位精度但增加 token 成本 |

**Stage 2 失败行为**(单页失败不影响其他页):

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `INFO: Stage 2 第 X 页 第 N/3 次失败,2s 后重试...` | 临时错误 (503/429/500/502/504) | 自动退避重试 2s / 4s,最多 3 次 |
| `WARN: Stage 2 第 X 页 Gemini 调用失败` | 重试 3 次仍失败 / 永久错误 (400/401/403/404) | 该页退回 caption 定位(策略 1/2/3 自动选最优),其他页继续 |
| `WARN: Stage 2 第 X 页 Gemini 返回为空` | 模型无输出 | 同上 |
| `INFO: Stage 2 第 X 页 Figure N 标记为非关键图,跳过` | Gemini 判断为装饰/logo/表格 | 该 fig 不裁剪,沿用 Stage 1 流程 |
| `WARN: 第 X 页 Figure Y 未找到 caption/visual bbox` | Stage 2 失败 + caption 三策略都未命中 | 走 Stage 1 bbox hint 兜底 |

**Stage 2 重试机制**(临时错误自愈):

- 默认 3 次尝试,指数退避 (2s, 4s)
- 临时错误 (`429 / 500 / 502 / 503 / 504`) 触发重试
- 永久错误 (`400 / 401 / 403 / 404`) 立即放弃(重试也没用)
- 网络异常 / 超时也走重试路径(无 `status_code` 时一律重试)

**Stage 2 成本**:

- 多 N 次 Gemini 调用(N = 引用 figure 的页面去重数,通常 2-5 页)
- 每页输入 ~1k token(image + prompt)+ 输出 ~200 token
- 延迟:每页 ~5-15s(串行)
- 用 `--no-refine-figures` 可完全跳过

#### 大小 / 格式 / 缩略图控制（仅在 `--extract-figures` 启用时生效）

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--figure-format` | `{png,webp,jpeg}` | `png` | 输出格式。WebP/JPEG 有损压缩，体积更小 |
| `--figure-quality` | int 1-100 | `85` | WebP/JPEG 质量（pymupdf 内部用 `jpg_quality`），PNG 无效 |
| `--max-width` | int | None | 最大宽度（像素）。超过则等比缩放；None 不限制 |
| `--max-size-kb` | int | None | 最大体积（KB）。超限自动降级：先降 quality → 再换格式（PNG→WebP）→ 再降 scale |
| `--thumbnail` | flag | 关 | 同时生成缩略图，Markdown 引用缩略图、点击跳原图 |
| `--thumbnail-width` | int | `400` | 缩略图宽度（像素） |

**自动 fallback**：

- `--figure-format=jpeg` 但图含 alpha 通道（`pix.alpha=1`）→ 自动改用 WebP 并 stderr 提示
- `--max-size-kb` 降级到最低规格仍超限 → 保留当前结果，stderr 打 WARN（不无限循环）

**缩略图目录结构**：

```text
<--output 指定的目录>/
├── summary.md
└── figures/
    ├── figure-p1-f1.png         # 原图（与 --figure-format 对应）
    ├── figure-p1-f1.thumb.png   # 缩略图
    └── ...
```

注意：缩略图**不**走 `figures/thumbnails/` 子目录，而是与原图并列 + `.thumb` 后缀，
方便一对图片保持目录一致。缩略图**不**应用 `--max-width`（`thumbnail-width` 自带尺寸上限），
但仍受 `--max-size-kb` 约束（缩略图也可能意外偏大）。

**Markdown 引用形式**：

- 默认模式：`![图 1：xxx](figures/figure-p1-f1.png)`
- 缩略图模式：`[![图 1：xxx](figures/figure-p1-f1.thumb.png)](figures/figure-p1-f1.png)`

完整调用：

```bash
# 1) 先装 pymupdf（一次性）
pip install --user --break-system-packages pymupdf

# 2) 一次性跑通：Stage 1 总结 + Stage 2 视觉定位 + 裁剪 + 路径替换 + 写文件
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf \
  --output ~/papers/summaries/attention \
  --extract-figures
# --refine-figures 默认开启;想完全跳过 Stage 2 加 --no-refine-figures
```

`--figure-dpi` 可改最终输出图的渲染倍率（默认 2.0 = 144 DPI；想要更清晰用 3.0 / 4.0）；
`--refine-dpi` 单独控制 Stage 2 喂给 Gemini 看的渲染倍率（同样默认 2.0）。

> 总结里没有 `PDF p.X fig.N` 引用时，`--extract-figures` 不会报错，只是不导出图。

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
> [`outline-wiki-management`](../../outline-wiki-management/SKILL.md) 的
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

把生成的 `.summary.md` 内容呈现给用户，注明 `模型=gemini-3.5-flash`。

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

# Book 模板（书籍 / 长篇技术文档）

> 4 类之一：`--type book`。书籍 PDF → **full 模式全文级转写**——按 PDF 原生章节顺序逐小节展开。
>
> 适用对象：教材、技术专著、工具书、reference manual、长篇技术手册（> 100 页且章节自成体系）。
>
> **重要**：book **只有 full 模式**——quick 不适用（书籍无法"一句话总结"）。
> 详细契约（章节顺序约束、Definition/Theorem 标注、公式 / 表格处理、完整性约束）参考
> paper full 模式（`template-paper.md` §full 模式），以下仅列与 book 特定的差异。
>
> **章节顺序 SSOT**：本文件正文 + SKILL.md §book 输出小节；改一处必须同步另一处。

## 输出

**无字符数上限**——按 PDF 实际页数展开；但 token 预算紧张时**优先精简措辞、缩具体例子**，
**禁止**合并整段、删除小节、跳过公式 / 定理 / 算法步骤。

**单模式**：book 只有 full。

**图表处理**：走 `_base.md` §4.2——不抽原始图，架构 / 概念用 mermaid / 表格 / ASCII 在正文里直接画。

## 模板

````text
你是一位长篇技术读物阅读助手。请基于这本 PDF 书籍（含教材 / 技术专著 / 工具书 /
reference manual），用**中文**输出 **PDF→Markdown 全量转写** —— 严格按 PDF 原生
章节顺序逐章展开，保留每一节的原文细节；读者后续会在没有 PDF 的情况下，
通过这个 markdown 与你对话，询问任何细节。

### 章节顺序

**严格按 PDF 原生目录结构**逐章转写。`Chapter N` / `Section N.M` / 附录 /
参考文献 / 索引等所有结构性内容**全部保留**。原英文标题保留（如
`## Chapter 3: Adaptive Radix Trees` 而非 `## 第 3 章 自适应基数树`）。
**不要**做"摘要 / 重点"式归纳。

### 元信息（开篇一段，仅一行）

一行 metadata table（`Title` / `Author` / `ISBN` / `Publisher` / `Edition` /
`Year`）—— **至少 Title + Author 两列必填**，其它字段识别不出时省对应列（不编造 ISBN）。

### 必保真的元素（按关键度排序）

- **章节标题层级**（## / ### / ####）严格对应 PDF 原生层级
- **Definition / Theorem / Lemma / Corollary / Algorithm / Example** —
  原文若标了，必须独立标注为 `**Definition 3.1.** ...` / `**Theorem 5.2.** $...$ ...` 等；
  公式与正文分两行
- **公式** — LaTeX 形式转写，行内 `$...$`，独立公式不用 `$$...$$` block
- **表格** — 逐行转 markdown 表格，数字精度保留
- **数字精度** — 3 位有效数字；范围 / 误差必须保留
- **代码 / 命令清单** — 完整保留，转 ` ```python ` / ` ```bash ` 等 fenced block
- **图的结构化表示**（不落 PNG）：
  - **架构 / 概念图** → 用 ` ```mermaidjs ` block 直接画（`graph TD` / `graph LR`）
  - **数据可视化图** → 转 markdown 表格
  - **纯装饰图 / 概念图省略** → 文字一句"图 N 是 `<场景描述>` 的示意图"
- **不写 `![图 N](PDF p.X ...)` 引用**
- **章节末尾的"小结 / 思考题 / 参考文献"** — 小结用 bullet 浓缩（≤ 5 条要点）；思考题保留题目
  （不写答案）；参考文献列表保留作者-年份-标题（保留英文原标题）

### 完整性（书籍场景强约束）

书籍产物的价值在"无 PDF 时可查"——章节合并 / 跳过会让读者找不到内容。

- 若 token 预算紧张，**优先**精简措辞、缩具体例子 / 长引文 / 重复论证
- **禁止**合并整段、删除小节、跳过公式 / 定理 / 算法步骤
- 该小节内容确实少时（如某些章节确实短），**显式**写"原文未明确"占位，而不是省略整节
- 整本 token 预算超限时：先输出所有章节骨架 + 前 N 章详细内容，剩余章节占位"原文已识别但因
  token 预算未展开——如需查看请使用 --model gemini-3.1-pro-preview 重跑或拆书"，**不要**直接截断

### 附录

- **参考文献**（保留作者-年份-标题 / 会议-期刊 / DOI，识别不出 DOI 字段时省 DOI）
- **索引**（如 PDF 含索引章节则**原样保留**——term → page 列表；agent 后续可按 term 查 page）
- **关于作者**（如书籍有"About the Author"页则保留 1-2 句）
````

## 与 paper full 模式的差异

| 维度 | paper full | book full |
|---|---|---|
| 元信息表 | Title / Venue / Topic | Title / Author / ISBN / Publisher / Edition / Year |
| 章节结构 | 论文的 Section N.M.K 体系 | 书的 Chapter N / Part / Appendix / Index 体系 |
| 完整性要求 | 严格（防止章节合并） | **更严格**——禁止合并 / 跳过小节；token 超限时分章详写 + 末章占位 |
| 索引 | 论文通常无 | 书籍通常有——**原样保留**（term → page 列表） |
| 思考题 / 习题 | 论文通常无 | 教材类书籍常有——保留题目，不写答案 |
| token 预算 | 默认（按页数估计） | 长篇需要 `--model gemini-3.1-pro-preview` 显式指定 |
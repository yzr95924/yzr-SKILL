# Markdown 风格约定（仓库统一基线 · 详细规则）

> 本文件是 `assets/_base.md` §风格约定 + SKILL.md §核心原则 #9 的下放层。SKILL.md 只
> 保留一段索引 + 1-2 行关键 must，完整规则在本文件查。**SSOT 在仓库 `.markdownlint.jsonc`**
> （MD013 行宽、MD041 first-line-heading 关闭），脚本与本文件**不重写**这些数字配置。
>
> 规则来源：仓库内通用基线（与 outline-wiki-upload / llm-wiki-management 等共享），不是
> 本 skill 独有。本 skill 的特殊之处只在"全文级转写产物本身就是 markdown 产物"——所以下面
> 规则同时约束**生成产物**和**skill 自身的 md 文件**。

## 1. bullet / 高亮

- **bullet marker**: 一律用 `*`，**不要**用 `-` 或 `+`
  - 为什么：仓库基线统一；`-` 是 outline-wiki 渲染的横线列表，视觉混淆
- **高亮术语**: 关键概念 / 参数 / 状态用 `==text==`（默认色）
  - Markdown 无法写彩色高亮，**不要**硬造颜色语法（如 `<span style="color:red">`）
- **列表项嵌套**: 二级 bullet 缩进 2 空格，三级 4 空格；不要超过 3 层（再深用 `####` heading）

## 2. Mermaid 块（架构 / 概念 / 流程）

- **块名统一用 `mermaid`**：标准 Markdown 渲染器、outline-wiki、Obsidian 都直接兼容
- **仅用 `graph` 系列**（`graph TD` / `graph LR` / `graph BT`）
- **仓库内**不用 `sequenceDiagram` / `classDiagram` / `stateDiagram` / `erDiagram`
  - 为什么：仓库 `.markdownlint.jsonc` 不配 mermaid 复杂类型 lint；agent 消费 mermaid
    复杂类型时支持参差，统一 graph 系列降低阅读风险
- **block-level**：` ```mermaid ` 放在 bullet **之外**，不要嵌在 bullet 子项内
  - 为什么：内嵌 mermaid 在 outline-wiki 渲染时偶发丢 block，外置稳定

## 3. 代码块

- **语言必填**：` ```bash ` / ` ```python ` / ` ```json ` / ` ```yaml ` 等，**不要**写空语言 ` ``` `
- **多语言示例**：用 4-backtick fence ` ````text ` 包裹（避免内层 ``` 与外层冲突）；
  `_load_prompt_for_type` 用正则抽该 fence 内容作为 Gemini prompt
- **代码块 vs bullet**：跨行代码片段用 fence，单行命令 / flag 可用行内 `` `code` ``

## 4. 表格

- **数据示例 / 概念对比 / 字段定义**：用 markdown 表格
- **其他场景优先 bullet**：表格用于"行结构同质 + 列对齐"的场景，不要把不规则叙述塞表
- **对齐符**：用 `:---` / `:---:` / `---:` 表示左 / 中 / 右对齐；默认左对齐即可

## 5. 引用 / 分隔

- **引用块** 行首 `>` 加空格：**仅在引用原始资料原话时**使用，**不要**当"美化容器"
- **分割线** `---`：仅在章节级别切换时使用，**不要**当段落分隔（段落间用空行即可）
- **加粗 vs 高亮**：状态 / 类别用 `==高亮==`（仓库基线），强调某个关键短语用 `**bold**`

## 6. 章节标题 / 文档结构

- **章节标题用 `##`**：每个章节标题一律 `##`（二级），**不要**降级成 `###` 起步
- **正文不写 H1（`#`）**：标题由文件名 / 上层目录 / Outline 文档 title 字段承载
  - 仓库 `.markdownlint.jsonc` MD041 已关闭 first-line-heading 检查 = 本约定自动化对齐
- **章节顺序 SSOT 在各模板头部**（`assets/template-*.md`）：改章节骨架先改模板，SKILL.md
  §输出 + references/output-skeletons-and-examples.md 同步

## 7. 行宽 / 空白

- **行宽 ≤ 120 字符**（与 `.markdownlint.jsonc` MD013 对齐）
  - **例外**：代码块 / 表格 / URL / 不可拆的长字符串不受 MD013 约束（config 已配）
- **段落间空 1 行**：不要连续空 2 行
- **中英混排**：英文术语 / 模型名 / 库名**直接保留英文**（详见 SKILL.md §核心原则 #4），
  中文前后不强行补空格（`训练使用 LoRA` 而不是 `训练 使用 LoRA`）

## 8. 私造语法禁用清单

**不要**在 markdown 里出现以下私造语法（outline-wiki / 标准渲染器不兼容）：

- `!!! warning` / `!!! note`（mkdocs Material admonition，outline 不支持）
- `:::tip` / `:::warning`（自定义 directive，GitHub 不支持）
- `<mark>` / `<details>` / `<summary>`（HTML 内联标签，markdown lint 不通过）
- 装饰性 emoji 占位（🎉🎉🎉 / ⚡️✨ / 🚀🔥）：可在**标题**适度用 1-2 个，
  **不要**在 bullet / paragraph 里堆 emoji 当 emphasis 替代

## 9. 数学 / 范围 / 公式

- **禁用 MathJax**：`$...$` / `$$...$$` outline-wiki 不渲染
  - 改纯文本 / Unicode：范围 `[1, 2^64)`、上标 `2^64` / `2⁶⁴`、运算 `≥` `≤` `×` `→` `≈`
- **例外（仅 book 模板）**：book 模板的全文级转写产物可保留 `$...$` 行内公式——
  agent Q&A 场景可消费 LaTeX，且 book 通常不在 outline-wiki 直接渲染
- **paper full 产物**：保真 Definition / Theorem / Algorithm 标注 + 行内公式
  （按 SKILL.md §输出 段）

## 10. 何时来查本文件

- **新写 / 改 SKILL.md / references/*.md**：跑 `markdownlint --config .markdownlint.jsonc` 前查
- **生成产物 markdown**（paper / manual / whitepaper / book）：prompt 强约束已写在
  `assets/template-*.md`；产出自检走 `self_check_full_content` 6 项检查
- **写 4-backtick ```` ``` ```` prompt 模板**：注意 §3 的 fence 嵌套规则

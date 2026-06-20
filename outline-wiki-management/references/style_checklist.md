# Outline Wiki 文档风格 Checklist

每次向 Outline Wiki **写新文档** / **大幅改写**前，按这份 checklist
跑一遍。任意一项不过 → 改 Markdown，不通过就硬卡住别发。这不是完整
风格指南——完整规则见
[`doc_style.md`](doc_style.md)，本 checklist 是"最后一道防线"。

## 1. 标题与结构

- [ ] 标题字段（`title` 参数）**单独传**，正文不要 H1——避免与 title 重复
- [ ] 顶部走 `# Reference`（A 变体，最常见）/ `## Reference`（B 变体）/
      直接进主题（C 变体，仅在"文档本身就是平台对比清单"时合理）
      中的某一种；**同一篇文档内不要混用** A/B/C
- [ ] 标题层级 `#` / `##` / `###` 体现逻辑层级，不跳级

## 2. Markdown 基础

- [ ] bullet marker 用 `*`（**不要**用 `-` 或 `+`）
- [ ] 代码块语言**必填**（`bash` / `python` / `json` / `yaml` / ...），
      **不要**写空语言 ` ``` `
- [ ] Shell 提示符统一 `$>` 后接一个空格（仓库自创约定）
- [ ] Mermaid 标识符用 `` ```mermaidjs ``（**不是** `` ```mermaid ``）
- [ ] Mermaid 代码块放在 bullet **之外**（block-level），不要嵌在 bullet
      子项内
- [ ] Mermaid 只用 `graph` 系列（TD / LR），仓库内未观察到
      `sequenceDiagram` / `classDiagram` / `stateDiagram` / `erDiagram`

## 3. 关键术语与高亮

- [ ] 关键术语 / 参数 / 状态用 `==text==`（默认色）
- [ ] **不要**期望 `==text==` 出现彩色高亮——Markdown 写不出来
- [ ] 需要彩色高亮 → 走 Outline UI 工具栏，或调 REST API 时附
      `proseMirrorDoc` 参数；不要在 Markdown 里硬造

## 4. 富文本能力（写之前先确认）

- [ ] **图片**：先 MCP `create_attachment` → curl multipart 上传 →
      Markdown 引用 `![alt](/api/attachments.redirect?id=...)`；**不要**
      直接引用本地路径（破图）
- [ ] **@mention**：先 MCP `list_users` 拿 user ID，再写
      `@[Name](mention://user/<id>)`；**不要**凭印象编 user ID
- [ ] **彩色高亮**：`create_document` / `update_document` **不支持**
      写入 ProseMirror 节点；本 skill 范围内无法解决彩色高亮
- [ ] 富文本能力是否可用 → 先调 MCP `tools/list` 核实 server 实际
      暴露的工具集

## 5. 行宽与 lint

- [ ] 行宽 ≤ 120 字符（`.markdownlint.jsonc` MD013）
- [ ] 整篇跑 `markdownlint <file>` 0 错误
- [ ] 不引入仓库 `.markdownlint.jsonc` 禁掉的语法（`!!!`、HTML、
      MathJax、`:::tip` 等）

## 6. 私造语法与装饰

- [ ] 不引入 `!!! warning` / `:::tip` / MathJax / `<mark>` / `<details>`
      等非 Outline 支持的语法
- [ ] 不写纯装饰性 emoji 占位（如 `🎉🎉🎉`）
- [ ] fenced code block 之外**不**用 HTML 标签
- [ ] 不写新文档用 `<image: ...>` 占位符（已停用，应改 attachment 引用）

## 7. 段落组织

- [ ] 大段内容拆成 bullet 嵌套（3-4 层缩进常见）；仓库内**极少**
      用纯段落
- [ ] 需要行-列对齐才用 table；其他场景优先 bullet（维护成本更低）
- [ ] 引用块 `> text` 仅在引用原始资料原话时使用，**不要**当
      "blockquote 容器"用

## 8. MCP 调用前置

- [ ] 调 MCP `tools/list` 确认 server 暴露的工具集（核心 4 个 + 扩展 N 个）
- [ ] 调用前先 `search` 查重，避免创建重复文档
- [ ] 涉及"编辑"前先 `read` 当前正文，找到精确的 `findText` 锚点；
      用 `editMode: "patch"` + `findText` 精准替换可在不动其他内容
      （注释 / 高亮 / 表格宽度）的前提下改写局部

## 用法

```text
1. 写完新文档 / 改完旧文档
2. 对照 checklist 逐项勾选
3. 不通过的项 → 改 Markdown → 再勾一遍
4. 全部通过 → 调用 create_document / update_document
```

> **意图**：checklist 是写**之前**的快速核对工具，**不**是写作时的
> 风格规范。要查"为什么这样写" / "映射到 ProseMirror 是什么节点"
> → 翻 [`doc_style.md`](doc_style.md)。

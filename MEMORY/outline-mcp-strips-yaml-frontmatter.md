---
name: outline-mcp-strips-yaml-frontmatter
description: Outline 的 MCP create/update_document 把 Markdown 解析成 ProseMirror 再序列化，正文顶部的 ---...--- YAML frontmatter 过不了往返——--- 被吃掉、YAML 键值泄漏成可见正文（title: 还会和 Outline title 字段重复）。OKF 元数据在 Outline 侧必须走正文首块 ```yaml 围栏代码块（存成 code_block 逐字保留），不能用标准 ---...---。2026-07-01 实测确认。
metadata:
  type: project
---

# Outline MCP 吃掉 --- frontmatter → OKF 载体用 ```yaml 围栏

**Why：** 2026-07-01 改进 `outline-wiki-upload` 的 OKF 上传格式时，要决定 OKF
元数据的物理载体。OKF 标准（[`llm-wiki-compiler`](https://github.com/atomicstrata/llm-wiki-compiler)
是权威生产 / 消费端）用 `---...---` YAML frontmatter。但 Outline 的 MCP
`create_document` / `update_document` 只收 Markdown 字符串，内部解析成 ProseMirror
节点再序列化——在同一 self-hosted server（`myoutline.ddnsto.com`）上写两篇探针文档
再读回（经 `list_documents` 的 `context` snippet）实测：

- `---...---` 载体：`---` 被吃掉，YAML 键值**泄漏成可见正文**（`type: concept
  title: ... description: ... tags: ...` 全变成正文段落，`title:` 还和 Outline
  title 字段重复）；不是隐藏元数据
- ` ```yaml ` 围栏载体：存成 `code_block` 节点**逐字保留**（行间 `\n` 完整存活），
  与正文干净分离

结论：Outline 侧 OKF 载体 = **正文首块 ` ```yaml ` 围栏**（标准字段 + 适配载体），
**不**用 `---...---`。这是有意的平台适配，非字面 OKF 合规。

**How to apply：**

- 在 Outline 上写带 OKF / 任何 YAML 元数据的文档时，**永远走 ` ```yaml ` 围栏**，
  不要用 `---...---`——后者会被吃掉并污染正文
- `title` 由 Outline 原生 title 字段承载，**不**进 yaml 块（裸写 H1 也会和 title
  重复）；MCP server 自带指令也明示"content must not begin with a top-level heading"
- 字段对齐真 OKF：**`type` 是唯一硬门槛**（消费端宽容模型：缺 `type` 才跳过文档，
  其余容忍）；`description`/`tags`/`created`/`updated` 推荐；`okf_version` 只在
  bundle 根 `index.md` 声明，**单篇文档不写**；Outline 专属溯源放 `x-outline` 块
  （OKF `x-<producer>` 私有键）
- 完整字段表 + 载体选型实测 + 与标准 / wiki 子集关系，见
  [`outline-wiki-upload/references/doc_style.md` → OKF agent 可读基线](../outline-wiki-upload/references/doc_style.md#okf-agent-可读基线上传格式控制)
  （SSOT 已落 skill，本条是跨会话指针，避免重跑实测 / 错误回退到 `---...---`）
- 读 Outline 文档正文：本 server 上 `mcp__outline__fetch` 只回元数据不带 body；
  `mcp__outline__list_documents(query=...)` 的 `context` 字段是 snippets 来源。
  REST `/api/*` 在 ddnsto relay 下全 404（见 [[ddnsto-relay-https-only-quirk]]），
  只有 `/mcp` 通——所以 body 校验走 MCP search snippet，不走 REST

**关联：**

- [[ddnsto-relay-https-only-quirk]] —— 同一 server 的另一类平台坑（HTTP 80 占位）；
  本条的"REST /api 全 404、只 /mcp 通"是其推论
- [[experience-affecting-skill-distribution-goes-to-skill-not-memory]] —— 本 finding
  的 SSOT 已落 skill（doc_style.md），MEMORY 仅作作者跨会话指针，符合该规则

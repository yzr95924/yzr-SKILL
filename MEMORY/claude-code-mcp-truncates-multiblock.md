---
name: claude-code-mcp-truncates-multiblock
description: Claude Code 的 MCP 客户端只呈现 tool result 的首个 text content block、丢弃其后；Outline 的 fetch(document) 服务端返 2 个 block（元数据 + 正文），正文段在 CC 里被截，读正文走 REST POST /api/documents.info 旁路。2026-07-01 curl 直连 /mcp 实测 num_blocks=2 确认。临时，待 CC 完整支持多 block 后撤销。
metadata:
  type: project
---

# Claude Code 截断 MCP 多 content block → outline 读正文走 REST 旁路

**Why：** 2026-07-01 优化 `outline-wiki-search` 时定位"为什么
`mcp__outline__fetch` 只回元数据、读不到正文"。`curl` 直连 `POST /mcp` 发
`tools/call fetch(document)` 绕开 Claude Code harness 实测：server 实际返回
`num_blocks: 2`——block[0] 是 JSON 元数据（~1.4K 字符），block[1] 是完整 markdown
正文（~3.1K 字符）。MCP 规范允许 `content` 数组含多个 block（text / image / …），
但 **Claude Code 的 MCP 客户端只采纳首个 text content block、丢弃其后所有 block**——
所以 CC 里 `fetch` 只看得到 block[0] 元数据。错在 CC 消费侧，**不是** Outline server
问题，也不是 outline-wiki 安装引入的（`.claude.json` 里 outline 是标准
`type: http` 直连 endpoint，无 bridge）。

> **上游归属（重要，别引错）**：CC 这个"只取首个 content block"的行为，社区相关
> tracking 有 `anthropics/claude-code#1804`，但 **#1804 标题 / 正文明确是针对
> `isError: true` 的错误响应**（且 issue 状态 closed）；成功响应多 block 被截是同源
> 表现或关联问题，**未必就是 #1804 本身**。引用时描述"CC 多 content block 处理
> 缺陷"即可，**不要**硬绑"#1804 修复后就好了"。

**How to apply：**

- 读 outline 文档**完整正文**：走 REST `POST <base>/api/documents.info`（body
  `{"id":"<docId>"}`）→ 响应 `data.text`（curl 模板见
  `outline-wiki-search/SKILL.md` §故障排查项 1）。**POST** 是实测可用方法（GET 在
  本 host 上不可靠，曾测出 404，疑似 middlebox / 缺 id 所致——别用 GET）
- token / `<base>` 同 MCP 配置（`~/.claude.json#mcpServers.outline` 或项目级
  `.mcp.json`，看 setup 当时 scope）；与 MCP server 同一把 key
- 元数据仍用 MCP `fetch`（block[0] 在 CC 里正常可见）；`list_documents` 返单 block
  不受影响，其 `context` 是正文片段（短文档接近全文，长文档会截，**别**据此判断
  全文）
- 待 CC 完整支持 MCP 多 content block（成功响应）后，`fetch` 即可直接返正文，
  届时撤销 REST 旁路——本条与 skill 里的旁路一起退役
- SSOT 已落 `outline-wiki-search/SKILL.md`（§核心原则 #5 + §故障排查），本条是
  作者跨会话指针

**关联：**

- [[outline-mcp-strips-yaml-frontmatter]] —— 同 server 的另一类平台坑；其旧版
  "REST /api 全 404、只 /mcp 通"是**错误推论**（GET / 缺 id 误测），本条已纠正：
  REST POST /api/documents.info 可用
- [[ddnsto-relay-https-only-quirk]] —— HTTP 80 占位空响应；与"REST 能否用"无关
  （REST 走 HTTPS 443 正常）

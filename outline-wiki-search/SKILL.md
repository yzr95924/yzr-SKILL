---
name: outline-wiki-search
description: 用户要在 Outline Wiki 工作区里搜文档或读文档时使用——按关键词全文
  搜索匹配文档列表，或按文档 ID 拉 Markdown 原文与元数据。**不**用于写 / 编辑 /
  上传 outline 文档（含图片附件、@mention、评论、Collection 管理、移动 / 删除 /
  归档，走 outline-wiki-upload）；**不**用于配置 outline MCP（走 outline-wiki-setup）；
  **不**用于 Notion / Confluence / Obsidian / GitHub Wiki。'outline' 若指大纲 /
  议程同名词则无关；分享 / 导出 / 权限调整官方 MCP 未列、server 通常也未暴露，
  走 UI 或 REST。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-07-01
---

# Outline Wiki Search

通过 Outline Wiki MCP 的**只读**操作能力（搜索 + 读取），在工作区内定位
文档、拿 Markdown 原文与元数据。本 skill 是 outline-wiki-* 家族中**最小**
的一个——只有核心能力的 1 / 2（search / read），无任何写操作。

写 / 编辑 / 上传相关操作由 `outline-wiki-upload` SKILL.md
负责；MCP 配置由 `outline-wiki-setup` SKILL.md 负责。

## 何时使用 / 不使用

### 使用

- 用户在对话中提到"搜 outline / 找 outline 文档 / 在 outline 工作区搜一下"
- 用户给出文档 ID，要求"读这篇文档 / 取这篇 markdown / 打开这篇 outline"
- 需要按关键词全文搜索匹配文档列表
- 需要拿到某篇文档的 Markdown 原文 + 元数据（创建时间 / 作者 / Collection 等）
- 需要先 search 查重 / 定位，再决定后续动作（无论后续是上传还是编辑）

### 不使用

- **写 / 编辑 / 上传 outline 文档**（含图片附件 / @mention / 评论 /
  Collection 管理 / 移动 / 删除 / 归档）——走
  `outline-wiki-upload` SKILL.md
- **配置 outline MCP**（首次接入 / 重启后看不到 / 401）——走
  `outline-wiki-setup` SKILL.md
- 用户使用其他 wiki / 知识库产品（Notion / Confluence / Obsidian / GitHub Wiki）
- 分享、导出、权限调整（官方 MCP 文档未列、server 通常也未暴露）——
  走 Outline Wiki 自身 UI 或直接调 REST API
- 写操作前"先 read 一下"——这是 outline-wiki-upload 的"读 - 改"流程前置
  步骤，**不是**本 skill 的场景；user 表达"我要改这篇"时直接走 upload

## 输入 / 输出

### 输入

启动时需具备以下**前置条件**——这些由 `outline-wiki-setup` 负责：

- **MCP 已注册**：当前 session 能调 `mcp__outline__*` 系列工具
  （若未注册，**先走 `outline-wiki-setup` SKILL.md**，
  跑完重启后再回来**）
- **用户自然语言指令**：搜索关键词 / 文档 ID

### 输出

- **搜索结果**：匹配的文档列表（含 ID、标题、摘要）
- **文档内容**：元数据（标题 / Collection / 时间 / 作者等）走 MCP `fetch`；
  **Markdown 正文**因 Claude Code 截断 MCP 多 content block（见 §核心原则 #5）
  需走 REST 旁路 `POST /api/documents.info`
- **错误信息**：工具名不匹配 / 文档 ID 无效 / 连接被拒等

## MCP 工具发现（重要）

> **本 skill 不写死任何工具名**——会话开始时必须先调用 MCP 的 `tools/list`
> 端点，核实当前 MCP server 实际暴露的工具名、参数 schema、返回结构，再据此
> 调用。约定：下文出现的"搜索 / 读取"等指**能力**而非具体工具名；调用前先
> `tools/list` 取真实工具名再做映射。

不同 self-hosted 部署工具集可能略有差异；扩展能力（如评论 / 图片附件）
也以 `tools/list` 实际返回为准——但本 skill 只用核心 search / read 两个能力。

## 能力清单

按"工具来源"分两组。**核心能力**对应官方文档明列的 4 个高层操作中的
search / read 两个；**扩展能力**对应官方文档未明列的写操作（不在本 skill
覆盖范围，由 `outline-wiki-upload` 负责）。

### 核心能力

#### 1. Search（搜索）

按关键词在工作区执行全文搜索，返回匹配的文档列表。

典型参数（具体以 `tools/list` 实际返回为准）：

- `query`：搜索关键词（必选）
- `collection_id`（可选）：限定 Collection 范围
- `limit` / `offset`（可选）：分页

#### 2. Read（读取）

按文档 ID 获取**元数据**（标题 / Collection / 时间 / 作者等）。**正文（Markdown
body）在 Claude Code 里读不到**——见下方"正文读取"说明。

典型参数：

- `id`（必选）：文档 ID
- 返回（MCP `fetch` 在 CC 里）：标题 + 元数据，**无 `text` 正文**

> **正文读取（重要）**：Outline MCP `fetch(document)` 服务端**确实返回正文**——
> 响应含 2 个 text content block：block[0] = JSON 元数据、block[1] = 完整 markdown
> 正文（`curl` 直连 `/mcp` 实测 `num_blocks: 2`）。**但 Claude Code 的 MCP 客户端
> 只呈现首个 content block**，block[1] 正文被丢弃，所以 CC 里 `fetch` 只看得到
> 元数据。这是 CC 客户端侧的已知行为（多 content block 处理缺陷），**不是 Outline
> server 问题**。拿正文走 REST `POST /api/documents.info`（curl 见 §故障排查项 1）；
> 待 CC 完整支持多 block 后撤销旁路，`fetch` 直接返正文。

## 执行原则 / 边界

### 核心原则

1. **写前先搜（Read-First 协作）**
   - 本 skill 自己**只读**，但常作为 outline-wiki-upload 的"写前 search"前置
     步骤；agent 在判断"该走 search 还是 upload"时，看用户意图里是否包含写
     动作（"找到后改一下"→ upload；"找到后告诉我内容"→ search）
2. **工具名核实（Tools-First）**
   - 不假定工具名的拼写、是否带前缀（如 `outline_`）
   - 任何操作前先 `tools/list` 拿真实工具清单
3. **不假定工具集**
   - 核心 search / read 通常稳定暴露；但跨 self-hosted 部署仍可能有差异
4. **结果展示**
   - 搜索结果按相关度排序展示，不要凭缓存的 ID 直接 read（文档可能被归档
     / 重命名）
5. **读正文走 REST 旁路（CC 多 content block 截断，2026-07-01 实测）**
   - Outline MCP `fetch(document)` 服务端返 2 个 content block（元数据 +
     正文），**Claude Code 只呈现首个**，正文被丢——CC 客户端侧问题，非 server
   - 拿正文走 REST `POST /api/documents.info`（curl 见 §故障排查项 1）；
     元数据仍用 MCP `fetch`，两条路分工
   - `list_documents` 返单 block 不受影响，其 `context` 是正文片段（短文档接近
     全文，长文档会截，**别**据此判断全文）
   - 待 CC 完整支持多 content block 后撤销 REST 旁路

### 边界

- **不**处理非 Outline Wiki 的知识库
- **不**在 MCP 未启用时尝试操作（先走 `outline-wiki-setup`）
- **不**做任何写操作（创建 / 编辑 / 移动 / 删除 / 归档 / 评论）——
  走 `outline-wiki-upload`
- **不**绕过 `tools/list` 凭"印象"调用工具

## 工作流 / 步骤

### 标准流程

1. **核实配置与工具**：会话开始时——
   - 确认 outline 相关 MCP 工具在当前 session 已注册；若未注册，**先走
     `outline-wiki-setup` SKILL.md**，跑完重启后
     再回来
   - 调 MCP `tools/list` 取 search / read 的实际工具名、参数 schema
2. **理解意图**：把用户的自然语言指令映射到 search 或 read
3. **执行操作**：
   - search → 按关键词 + 可选 collection_id + 分页参数（MCP `list_documents`，
     返元数据 + `context` 摘录片段，正常可用）
   - read 元数据 → MCP `fetch`（resource=document，按文档 ID）
   - read **正文** → MCP `fetch` 在 CC 里拿不到（§核心原则 #5），走 REST
     `POST /api/documents.info`（§故障排查项 1）
4. **验证结果**：检查返回是否成功
5. **报告**：把找到的文档列表 / 读到的 Markdown 原文 / 元数据告诉用户
6. **衔接**（可选）：如果用户后续要写 / 编辑当前找到的文档，明确告知
   "下一步走 `outline-wiki-upload`"

### 故障排查

按以下顺序定位：

1. **`fetch` 只返元数据、读不到正文（最常见）** — Claude Code 截断 MCP 多
   content block 所致（§核心原则 #5），**不是**文档空 / ID 错 / 鉴权问题，别
   往那些方向排查。拿正文走下方 REST 旁路；或 `list_documents(query)` 的
   `context` 拿正文片段（短文档接近全文，长文档会截）
2. **工具名不匹配** — 重新调 `tools/list` 拿当前工具清单；别凭记忆调用
3. **文档 ID 无效** — 用 search 重新定位拿新 ID；别凭缓存 ID 调用（文档可能
   已归档 / 重命名）
4. **认证失败（401 / 403）** — `outline-wiki-setup` 范畴（key 过期 / OAuth
   失效），先重启或重跑配置脚本
5. **MCP 未启用 / 连接被拒** — 走 `outline-wiki-setup` 排查配置

**读正文 REST 旁路**（故障项 1 展开）—— token / `<base>` 同 MCP 配置（与 MCP
server 同一把 key，setup 时已写好）：

```bash
# <base> = outline MCP url 去掉尾部 /mcp
curl -sS -X POST "<base>/api/documents.info" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"id":"<docId>"}' | jq -r '.data.text'
```

`<token>` 位置看 `outline-wiki-setup` 当时的 scope：

- user → `~/.claude.json#mcpServers.outline.headers.Authorization`
- project → 仓库根 `.mcp.json`
- local → `~/.claude.json#projects.<path>.mcpServers.outline`

## 参考样例

### 样例一：搜索现有文档

**用户指令**："帮我在 Outline Wiki 里搜一下'CI 部署流程'相关的文档"

**执行**：

```text
1. 确认 mcp__outline__* 工具已在 session 注册（否则先走 outline-wiki-setup）
2. 调用 tools/list 拿到 search 工具的实际名称
3. 调用 search 工具，query="CI 部署流程"，limit=10
4. 整理返回的文档列表，按相关度展示给用户
5. 若用户要打开某篇，再用 read 工具拉取正文
```

### 样例二：按文档 ID 读取

**用户指令**："把 doc_abc123 这篇文档的 Markdown 原文给我看一下"

**执行**：

```text
1. 调用 tools/list 拿到 read 工具的实际名称
2. MCP fetch(resource=document, id="doc_abc123") → 标题 + 元数据
   （Collection / 时间 / 作者）；正文因 CC 截断多 block 拿不到（§核心原则 #5）
3. 拿正文走 REST：POST /api/documents.info {"id":"doc_abc123"} → data.text
4. 把标题 + 元数据 + Markdown 正文一并展示
5. 若用户后续要"改这篇"，明确告知下一步走 outline-wiki-upload
```

### 样例三：search 查重（与 upload 协作）

**用户指令**："我要在 '后端' Collection 下新建一篇'缓存策略'文档，
先帮我查一下有没有重名的"

**执行**：

```text
1. 调用 search 工具，query="缓存策略"，collection_id=<后端 Collection ID>
2. 列出已有同名 / 相似标题文档
3. 若无 → 提示用户可走 outline-wiki-upload 创建
4. 若有 → 提示用户走 outline-wiki-upload 的"编辑已有文档"流程（不新建重复）
```

## 相关参考

- `outline-wiki-setup` SKILL.md — 配套：MCP 配置与首次接入
- `outline-wiki-upload` SKILL.md — 配套：写 / 编辑 outline 文档
- **不在本 skill 范围内**：
  - 文档风格（`outline-wiki-upload/references/doc_style.md`）—— 写时参考
  - 风格 checklist（`outline-wiki-upload/references/style_checklist.md`）—— 写时核对

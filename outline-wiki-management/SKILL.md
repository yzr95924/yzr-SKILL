---
name: outline-wiki-management
description: 通过 Outline Wiki 内置 MCP（*.getoutline.com/mcp 或自托管
  /mcp 端点；OAuth 或 API Key）管理工作区文档——核心能力：搜 / 读 / 创
  建 / 编辑；扩展能力（server 实际暴露但官方文档未明列）：图片附件、
  @mention、评论、Collection 管理、移动 / 删除文档。配套：把 Outline
  Wiki MCP 接入 Claude Code（收集 endpoint + 鉴权材料后调
  scripts/configure_mcp.py 写 ~/.claude.json，再让用户重启会话）。所有
  读写走 MCP 工具，不直连 REST。触发词：'Outline Wiki'、'outline 工作区
  / 文档 / MCP'、含 '/mcp' 的 endpoint URL、'配置 / 接入 outline MCP'。
  不用于 Notion / Confluence / Obsidian / GitHub Wiki；'outline = 大纲 /
  议程'同名词；分享 / 导出 / 权限调整（官方 MCP 文档未列且 server 通常
  也未暴露，走 UI 或 REST）。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-20
---

# Outline Wiki Management

通过 Outline Wiki 提供的内置 MCP 服务（Model Context Protocol），在对话中
直接对其工作区内的文档进行**搜索、读取、创建、编辑**，以及配套的扩展
能力（图片 / 文件附件、@mention、评论、Collection 管理、移动 / 删除等）。
本 skill 按"工具来源"把能力分为两组：

- **核心能力**（[Outline 官方 MCP 文档](https://docs.getoutline.com/s/guide/doc/mcp-6j9jtENNKL)
  列出的 4 个）：search / read / create / edit
- **扩展能力**（server 实际暴露但官方文档未明列）：image attachment、
  @mention、comment、Collection 管理、move / delete

官方文档未列出的扩展能力，使用前应通过 `tools/list` 核实 server 是否
暴露对应工具；不同 self-hosted 部署工具集可能略有差异。

## 何时使用 / 不使用

### 使用

- 用户在对话中明确提到 Outline Wiki
- 需要在 Outline Wiki 工作区中按关键词搜索文档
- 需要读取某篇文档的 Markdown 原文与元数据
- 需要在指定 Collection 下创建新文档
- 需要更新已有文档的标题或 Markdown 正文
- 客户端是 Claude Code / Claude Desktop / Cursor / 其他支持 Streamable HTTP
  传输的 MCP 客户端

### 不使用

- 用户使用其他 wiki / 知识库产品（Notion / Confluence / GitHub Wiki /
  本地 Markdown 文件夹 / Obsidian 等）
- 分享、导出、权限调整（官方 MCP 文档未列、server 通常也未暴露）——
  走 Outline Wiki 自身 UI 或直接调 REST API
- 需要**彩色高亮**等 Markdown 表达不出来的富文本特性（`create_document`
  / `update_document` 不接收原始 ProseMirror 节点）——走 UI 或直接调
  REST API 并附 `proseMirrorDoc` 参数
- Outline Wiki 实例未启用 MCP（提示用户到工作区 **Settings → AI** 开启）
- 需要访问 Outline Wiki 之外的资源（外部网页、二进制附件等）

## 输入 / 输出

### 输入

启动时需具备以下信息：

- **MCP 端点**（必选）：
  - 官方云服务：`https://<your-subdomain>.getoutline.com/mcp`
  - 自托管实例：`https://<your-domain>/mcp`（替换为自己的域名，路径固定为 `/mcp`）
- **认证方式**（二选一）：
  - **OAuth（默认）**：在支持的客户端添加端点后自动弹出登录窗口
  - **API Key**：在 Outline Wiki 设置中生成，配 `Authorization: Bearer <key>` 头
- **用户自然语言指令**：搜索关键词 / 文档 ID / 创建 / 编辑等

客户端接入的具体命令与 JSON 模板见 `references/auth.md`。

### 输出

- **搜索结果**：匹配的文档列表（含 ID、标题、摘要）
- **文档内容**：Markdown 原文 + 元数据（创建时间、作者、Collection 等）
- **操作结果**：创建 / 编辑文档的返回值（通常含新文档 ID 与 URL）
- **错误信息**：401 / 403 / 连接被拒 / 文档 ID 无效等，需进入故障排查流程

## 设计决策

> **重启 Claude Code 是硬约束**。Outline Wiki MCP server 必须在
> `~/.claude.json#mcpServers` 中注册，且 Claude Code CLI 在 session
> 启动时一次性读入；mid-session 改文件不会被重读，也没有
> `claude mcp reload` 这类子命令。`/mcp` 斜杠命令能 reconnect 已注册
> 的 server，但**不会**加载新 server。
>
> 因此：使用本 skill 前，**如果 outline 相关 MCP 工具尚未在当前
> session 注册**，必须先走 [`references/onboarding.md`](references/onboarding.md)
> 跑配置脚本，**然后重启当前会话**（推荐 `claude --continue` 续接历史）。
> 完整流程、"为什么必须重启"以及重启后验证清单见该附录。

## MCP 工具发现（重要）

**官方 MCP 文档列出 4 个核心能力（search / read / create / edit），
并未枚举具体工具名**；实际接入的 server 通常还暴露了图片附件、
@mention、评论、Collection 管理、移动 / 删除等扩展工具。本 skill 因
此**不写死**任何工具名——会话开始时必须先调用 MCP 的 `tools/list`
端点，核实当前 MCP server 实际暴露的工具名、参数 schema、返回结构，
再据此调用。

约定：下文出现的"搜索 / 读取 / 创建 / 编辑"等指**能力**而非具体工
具名；调用前先 `tools/list` 取真实工具名再做映射。扩展能力是否可用
也以 `tools/list` 的实际返回为准。

## 能力清单

按"工具来源"分两组。**核心能力**对应官方文档明列的 4 个高层操作；
**扩展能力**对应官方文档未明列但本会话实测可用、且在不同 self-hosted
部署里通常也暴露的工具。扩展能力**强烈建议**先用 `tools/list` 确认
目标 server 是否暴露对应工具，再做调用。

### 核心能力

#### 1. Search（搜索）

按关键词在工作区执行全文搜索，返回匹配的文档列表。

典型参数（具体以 `tools/list` 实际返回为准）：

- `query`：搜索关键词（必选）
- `collection_id`（可选）：限定 Collection 范围
- `limit` / `offset`（可选）：分页

#### 2. Read（读取）

按文档 ID 获取 Markdown 原文与元数据。

典型参数：

- `id`（必选）：文档 ID
- 返回：标题、Markdown 原文、Collection、创建 / 修改时间、作者等

#### 3. Create（创建）

在指定 Collection 下新建文档；如需嵌套子页需传入父文档 ID。

典型参数：

- `title`（必选）
- `content`（必选）：Markdown 原文
- `collection_id`（必选）：目标 Collection
- `parent_document_id`（可选）：父文档 ID（创建子页时设置）

#### 4. Edit（编辑）

修改已有文档的标题或 Markdown 正文。

典型参数：

- `id`（必选）：目标文档 ID
- `title`（可选）
- `content`（可选）
- `editMode`（可选）：`replace`（全量替换，默认）/ `append` / `prepend`
  / `patch`（精准局部替换，配合 `findText`）

> 注：编辑操作可能要求传完整正文，也可能支持局部替换，**以 `tools/list`
> 实际返回的参数 schema 为准**。

### 扩展能力

> 以下工具官方 MCP 文档未明列，但是当前 server（及大多数 self-hosted
> 部署）实际暴露的能力；本 skill 收录并以正式流程对待。使用前
> `tools/list` 确认即可。

#### 5. Image / 文件附件（create_attachment + fetch attachment）

MCP `create_document` / `update_document` 只接受 Markdown 字符串，**不
接收文件二进制**。要把图片或文件嵌进文档，必须先走 attachment 通道，
再在 Markdown 里引用。3 步流程详见下文"文档风格 / 图片与文件附件"。

#### 6. @mention 用户（list_users）

`list_users` 按关键字（名字 / email）查工作区成员；配合 Markdown 语法
`@[Display Name](mention://user/<userId>)` 即可在文档里 @ 到具体用户，
Outline UI 会渲染成可点击链接。详见下文"文档风格 / @mention 用户"。

#### 7. 评论（create_comment / list_comments / update_comment / delete_comment）

在指定文档（或顶层 / 内联）下创建 / 列出 / 修改 / 删除评论；支持嵌套
回复（`parentCommentId`）。`update_comment` 还能 resolve / unresolve
顶层评论（`status: resolved` / `unresolved`）。对他人文档建议先
`list_comments` 看现有讨论再决定新建还是回复。

#### 8. Collection 管理

- `list_collections`：列出工作区可见的 Collection
- `list_collection_documents`：返回 Collection 的完整文档树（含嵌套子文档）
- `create_collection` / `update_collection`：新建 / 修改 Collection
  （name / description / icon / color）
- `delete_collection`：删除 Collection；可设置 `archive=true` 走归档

> 注意：删除 Collection 会**级联删除**其下未归档的文档；批量移动前
> 先用 `list_collection_documents` 看清楚结构。

#### 9. Move / Delete 文档

- `move_document`：把文档移到别的 Collection 或父文档下，可指定 `index`
  控制同级排序
- `delete_document`：删除文档（默认进 trash，30 天内可在 trash 中恢复）；
  可设 `archive=true` 直接归档而**不进** trash

## 文档风格

向 Outline Wiki 写入新文档时，应**对齐工作区现有风格**——避免引入风格
漂移。本节列基线与几个常被踩坑的能力（图片 / @mention / 彩色高亮）；
完整的 Markdown ↔ ProseMirror 节点映射、彩色高亮等 Markdown 写不出
来的特性如何处理，见 [`references/doc_style.md`](references/doc_style.md)。

### 原则：按 ProseMirror JSON 的"投影"写 Markdown

Outline 后端持久化的是 **ProseMirror 节点树**，MCP 工具的 `create_document` /
`update_document` 只接受 Markdown 字符串作为输入。因此：

- **写之前**先想清楚这条 Markdown 会被解析成哪个 ProseMirror 节点
- **不要**使用 Markdown 表面能写、但 ProseMirror schema 不接受的语法
- **不要**使用 Markdown 表面写不出来、必须靠 UI 才能表达的语法（如
  指定 highlight 颜色）；这类需求走"进阶"路径

### 风格基线

| 元素 | 仓库约定 | 说明 |
| --- | --- | --- |
| 顶部结构 | `# Reference` 段开头，列外部资料 | 仓库内事实标准 |
| 标题层级 | `#` / `##` / `###` 表达逻辑层级；**正文不要 H1**（title 单独传） | 标准 + MCP 约束 |
| Bullet marker | `*`（不用 `-` / `+`） | 仓库统一 |
| 高亮 | `==text==` 标记关键术语 / 参数 / 状态 | 仓库指纹（默认色） |
| 代码块语言 | 必填（`bash` / `python` / ...） | 习惯 |
| Shell 提示符 | `$>` 后接一个空格 | 仓库自创约定 |
| 图片 | `![alt](/api/attachments.redirect?id=... "=WxH")` | attachment 引用 |
| @mention | `@[Name](mention://user/<userId>)` | server 扩展语法 |
| 语言 | 中文叙述 + 英文术语混排 | 习惯 |
| 行宽 | ≤ 120 字符 | `.markdownlint.jsonc` 规定 |

### 关键 Markdown ↔ ProseMirror 节点映射

| 风格 | Markdown | ProseMirror 节点 / mark |
| --- | --- | --- |
| 标题 | `# text` | `heading` + `attrs.level` |
| Bullet | `* item` | `bullet_list` + `list_item` |
| 高亮 | `==text==` | `highlight` mark（**Markdown 无法指定颜色**） |
| 加粗 | `**text**` | `strong` mark |
| 斜体 | `*text*` | `em` mark |
| 行内代码 | `` `code` `` | `code` mark |
| 链接 | `[t](u)` | `link` mark + `attrs.href` |
| @mention | `@[N](mention://user/<id>)` | `mention` mark |
| 代码块 | ` ```bash ` | `code_block` + `attrs.language` |
| 图片 | `![a](u "=WxH")` | `image` + `attrs.src/alt/title` |

### 图片与文件附件

图片走 attachment 通道，3 步：

1. **预签名上传 URL**：调 `create_attachment(name, contentType, size)`，
   拿到 `uploadUrl`（multipart 接收端点）+ 一组表单字段
2. **上传二进制**：用 `curl` 或任意 HTTP multipart 客户端把本地文件
   POST 到 `uploadUrl`，其他表单字段作为额外 part 一并提交。响应通常
   返回 `{success: true, ...}` + attachment 元数据
3. **插入引用**：在 Markdown 里写 `![alt](<attachment.url> "=WxH")`，
   其中 `attachment.url` 形如 `/api/attachments.redirect?id=<uuid>`；
   `=宽x高` 给出渲染尺寸，非图片可省略

**读取附件**：`fetch(resource="attachment", id=<id 或完整 redirect URL>)`
返回 short-lived 签名 URL，可直接下载。

**注意事项**：

- `create_document` / `update_document` **不**自动上传本地图片——
  引用一个未上传的本地路径只会在 UI 里渲染成破图
- attachment URL 是 auth-gated：未登录用户访问返回 403，登录 session
  返回 302 重定向到实际文件
- 用 `update_document` + `editMode: "patch"` + `findText` 精准替换
  某段时，可在不动其他内容（注释 / 高亮 / 表格宽度）的前提下把
  mermaid / 占位图换成真图

### @mention 用户

1. 调 `list_users(query=<关键字>)` 拿到 user 列表（含 `id` 与 `name`）
2. 在 Markdown 写 `@[张三](mention://user/c9a1b2e3-...)`
3. 在 Outline UI 里渲染成可点击的 @mention，点击跳转该用户

`list_users` 也可用于"按 email / 名字搜索用户做权限查询"等场景。

### 彩色高亮（Markdown 写不出来）

`==text==` 只能表达"默认色"高亮；要表达彩色高亮（如红色标记警告），
必须绕过 Markdown 直接构造 ProseMirror JSON 节点，但
`create_document` / `update_document` **不接受原始 ProseMirror 节点**
（只有 Markdown 字符串入参）。

**当前结论**：彩色高亮无法通过 MCP 写入；如需，必须走 Outline UI
或直接调 REST API `POST /api/documents.update` 时附 `proseMirrorDoc`
参数。详见 `references/doc_style.md` §进阶。

### 反模式

- 用 `-` 或 `+` 起 bullet（破坏统一）
- 正文以 H1 开头（title 已单独传，再加正文 H1 与标题重复）
- 期望 `==text==` 出现彩色高亮（Markdown 写不出来，见上文彩色高亮小节）
- 私造非 Outline 支持的语法（`!!!`、HTML 标签等）
- 引入外部私有扩展（MathJax、`:::tip` 等）
- 大段纯段落不分 bullet（仓库内极少用纯段落）
- 引用未上传的本地图片路径（只会渲染成破图，必须先走 attachment 流程）

完整规则、彩色高亮等 Markdown 写不出来的特性如何构造 JSON，见
[`references/doc_style.md`](references/doc_style.md)。

## 执行原则 / 边界

### 核心原则

1. **写前先搜（Read-First）**
   - 创建新文档前必须先用"搜索"能力查重，确认是否已有同类但内容过期
   - 若已有同类文档，用"编辑"能力更新而不是新建重复
2. **严格 Markdown 格式**
   - Outline Wiki 是 Markdown 优先平台，所有内容必须用合法、纯净的 Markdown
   - 用 `#` / `##` / `###` 体现逻辑层级，自动生成清晰目录
   - 不引入 Outline Wiki 不支持的非标准私有扩展语法
3. **工具名核实（Tools-First）**
   - 不假定工具名的拼写、是否带前缀（如 `outline_`）
   - 任何操作前先 `tools/list` 拿真实工具清单
4. **能力边界分两组处理**
   - **核心能力**（search / read / create / edit）：官方文档明列，直接调用
   - **扩展能力**（图片附件 / @mention / 评论 / Collection 管理 / move /
     delete）：server 实际暴露但官方文档未列；调用前 `tools/list` 确认
     是否暴露
   - 用户要求"分享 / 导出 / 权限调整"等操作时，明确告知这些不在本
     skill 覆盖范围，建议走 Outline Wiki 自身 UI 或直接调 REST API

### 边界

- **不**处理非 Outline Wiki 的知识库
- **不**在 MCP 未启用时尝试操作（提示用户到 **Settings → AI** 开启）
- **不**支持分享 / 导出 / 权限调整（官方 MCP 文档未列、server 通常也
  未暴露）—— 走 Outline UI 或 REST API
- **不**支持彩色高亮（Markdown 写不出来，`create_document` /
  `update_document` 不接收原始 ProseMirror 节点）—— 走 Outline UI 或
  REST API 时附 `proseMirrorDoc` 参数
- **不**绕过 `tools/list` 凭"印象"调用工具；扩展能力是否可用以 server
  实际暴露的工具集为准
- **不**在 server 端生成 / 撤销 API Key（那是 Outline Wiki 用户在
  **Settings → API** 中的操作）
- **不**在 skill 工作流中直接写 `.claude/settings.local.json`；客户端接入
  通过 `scripts/configure_mcp.py` 完成（详见下文"客户端接入"小节）

## 工作流 / 步骤

### 标准流程

1. **核实配置与工具**：会话开始时——
   - 确认 outline 相关 MCP 工具在当前 session 已注册；
     若未注册，说明客户端未接入，**走 [`references/onboarding.md`](references/onboarding.md)**
     让用户跑配置脚本（agent 主动驱动，不要只让用户手动跑）
   - 调 MCP `tools/list` 取实际工具清单（核心能力 + 扩展能力各自对应
     的真实工具名、参数 schema）
2. **理解意图**：把用户的自然语言指令映射到能力清单之一（核心或扩展）
3. **先搜后写**：涉及"创建 / 编辑"前，先 search 查重 / 定位目标文档；
   涉及"图片"前先确认 attachment 通道（`create_attachment`）可用
4. **执行操作**：调用对应工具；图片场景走"create_attachment → curl 上传
   → Markdown 引用 attachment URL"3 步；评论场景先 `list_comments` 看
   现有讨论再决定新建还是回复
5. **验证结果**：检查返回是否成功；失败时按故障排查流程定位
6. **报告**：把做了什么、结果如何、是否需要后续动作告诉用户

### 客户端接入

> **详细内容已抽出到 [`references/onboarding.md`](references/onboarding.md)**，
> 包括快速入口、检测当前状态、引导配置（agent 收集信息的 Q1/Q2 模板）、
> 调用脚本、手动退路、**重启后验证清单**、**设计决策**（为什么必须
> 重启）、常见问题与旧版配置清理。本节只留工作流中需要的骨架。

首次使用本 skill、或 outline 相关 MCP 工具在当前 session 不可用时，
**主动**完成客户端接入（agent 驱动），而不是只让用户手动跑脚本。
脚本的注册目标是 `~/.claude.json` 的
`projects.<projectPath>.mcpServers.outline` 段（**项目级** scope，
`--scope project`），等价于 `claude mcp add --scope project`。该路径
仅在**当前项目**下生效；首次进入项目时 Claude Code 会弹一次 trust
prompt，按提示批准即可，后续不会再弹。

受控的客户端配置入口是 **`scripts/configure_mcp.py`**：agent 收集
endpoint + 鉴权材料后调脚本写入
`~/.claude.json#projects.<projectPath>.mcpServers`。agent **不**直接调
`claude mcp add`、也**不**直接编辑 `~/.claude.json` 或
`.claude/settings.local.json`。

**最常用路径**（API Key 鉴权，agent 走非交互模式时）：

```bash
OUTLINE_MCP_ENDPOINT='https://<your-subdomain>.getoutline.com/mcp' \
OUTLINE_MCP_AUTH_METHOD='apikey' \
OUTLINE_MCP_API_KEY='<key>' \
python3 outline-wiki-management/scripts/configure_mcp.py
```

OAuth 鉴权或希望手动跑：直接 `python3 outline-wiki-management/scripts/configure_mcp.py`
走交互模式。

**配置完成后必须重启 Claude Code 当前会话**（推荐 `claude --continue`
续接历史），新工具才会出现在 `mcp__outline__*` 列表中。完整验证步骤
与"为什么必须重启"见 `references/onboarding.md`。

### 故障排查

按以下顺序定位：

1. **认证失败（401 / 403）**
   - API Key：检查是否过期或被撤销，让用户重新生成
   - OAuth：让用户重新走一次授权流程
2. **MCP 未启用（连接被拒）**
   - 提示用户到 Outline Wiki 工作区 **Settings → AI** 确认 MCP toggle 已开启
   - 自托管实例需管理员在控制台开启
3. **工具名不匹配**
   - 重新调 `tools/list` 拿当前工具清单；不要凭记忆中的名字调用
4. **文档 ID 无效**
   - 用 search 重新定位目标文档，拿到新 ID
   - 不要凭缓存的 ID 直接调用——文档可能已被归档 / 重命名

## 参考样例

### 样例一：搜索现有文档

**用户指令**："帮我在 Outline Wiki 里搜一下'CI 部署流程'相关的文档"

**执行**：

```text
1. 调用 tools/list 拿到 search 工具的实际名称
2. 调用 search 工具，query="CI 部署流程"，limit=10
3. 整理返回的文档列表，按相关度展示给用户
4. 若用户要打开某篇，再用 read 工具拉取正文
```

### 样例二：更新已存在文档

**用户指令**："把 doc_abc123 的'部署步骤'小节加上'回滚方案'一段"

**执行**：

```text
1. tools/list 拿到 read / edit 工具的实际名称
2. read 工具拿当前正文
3. 找到"部署步骤"小节，追加"回滚方案"段落（保持 Markdown 层级）
4. edit 工具更新 content 为新正文
5. 验证返回成功
```

### 样例三：创建新文档

**用户指令**："在 '后端' Collection 下新建一篇'缓存策略'文档"

**执行**：

```text
1. tools/list 拿到 search / create 工具的实际名称
2. search "后端" 找到名为"后端"的 Collection ID（如果该信息在工具参数中必需）
3. 撰写 Markdown 正文
4. create 工具传 title / content / collection_id
5. 验证返回成功，把新文档链接 / ID 告诉用户
```

> 注：Collection ID 在官方文档中**未明示**如何获取；如果 `tools/list` 中
> create 工具的 schema 不要求 collection_id（例如允许按 Collection 名称引用），
> 则按实际 schema 调用。

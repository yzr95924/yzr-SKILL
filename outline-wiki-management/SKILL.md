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
接收文件二进制**。要把图片或文件嵌进文档，必须先走 attachment 通道
（`create_attachment` → `curl` 上传 → Markdown 引用 attachment URL），
3 步流程 + curl 模板详见下方"工作流 / 步骤 / 图片插入 / 文件附件工作流"
小节（line ~395 之后）。

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
漂移。本节只列最关键的基线与反模式；完整的 Markdown ↔ ProseMirror 节
点映射、图片附件上传流程 / @mention / 彩色高亮等 Markdown 写不出来
的特性如何处理，见
[`references/doc_style.md`](references/doc_style.md)。写新文档 / 大幅
改写前的最后一道防线是 [`references/style_checklist.md`](references/style_checklist.md)
的 9 大类 checklist——按顺序勾选一遍能避免 90% 的风格漂移。

### 原则：按 ProseMirror JSON 的"投影"写 Markdown

Outline 后端持久化的是 **ProseMirror 节点树**，MCP 工具的 `create_document` /
`update_document` 只接受 Markdown 字符串作为输入。因此：

- **写之前**先想清楚这条 Markdown 会被解析成哪个 ProseMirror 节点
- **不要**使用 Markdown 表面能写、但 ProseMirror schema 不接受的语法
- **不要**使用 Markdown 表面写不出来、必须靠 UI 才能表达的语法（如
  指定 highlight 颜色）；这类需求走 references 里的"进阶"路径

### 风格基线

| 元素 | 仓库约定 | 说明 |
| --- | --- | --- |
| 顶部结构 | `# Reference` 段开头，列外部资料 | 仓库内事实标准 |
| 标题层级 | `#` / `##` / `###` 表达逻辑层级；**正文不要 H1**（title 单独传） | 标准 + MCP 约束 |
| Bullet marker | `*`（不用 `-` / `+`） | 仓库统一 |
| 高亮 | `==text==` 标记关键术语 / 参数 / 状态 | 仓库指纹（默认色） |
| 代码块语言 | 必填（`bash` / `python` / ...） | 习惯 |
| Shell 提示符 | `$>` 后接一个空格 | 仓库自创约定 |
| 图片 | `![alt](/api/attachments.redirect?id=... "=WxH")` | attachment 引用，详见 references §12 |
| @mention | `@[Name](mention://user/<userId>)` | server 扩展语法，详见 references §13 |
| 语言 | 中文叙述 + 英文术语混排 | 习惯 |
| 行宽 | 遵守 `.markdownlint.jsonc` MD013 | 阈值见 [`doc_style.md`](references/doc_style.md) §3 |

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

### 反模式

- 用 `-` 或 `+` 起 bullet（破坏统一）
- 正文以 H1 开头（title 已单独传，再加正文 H1 与标题重复）
- 期望 `==text==` 出现彩色高亮（Markdown 写不出来，详见 references §进阶）
- 私造非 Outline 支持的语法（`!!!`、HTML 标签等）
- 引入外部私有扩展（MathJax、`:::tip` 等）
- 大段纯段落不分 bullet（仓库内极少用纯段落）
- 引用未上传的本地图片路径（只会渲染成破图，必须先走 attachment 流程，
  详见 references §12）

完整 Markdown ↔ ProseMirror 节点映射、图片附件上传流程 / @mention /
彩色高亮等 Markdown 写不出来的特性如何构造 JSON，见
[`references/doc_style.md`](references/doc_style.md)；写前的最后一道
防线是 [`references/style_checklist.md`](references/style_checklist.md)。

### 论文笔记 / 设计文档：关键架构图 / 示意图默认必须

仓库内 `论文笔记` Collection、`数据结构与算法 → 索引类` 这类
**以展示系统 / 算法设计为核心**的文档（也包括 `design-doc-edit` 的产出），
**关键架构图 / 示意图是默认要求**——而**不是**可选项。理由：

- 图是"组件 + 关系"信息密度最高的载体；纯文字描述会大幅降低扫读效率
- Outline Wiki 通过 attachment 通道原生支持图片（详见
  [`references/doc_style.md`](references/doc_style.md) §12）
- 工作区里已有的论文笔记（`Bigtable-OSDI'06`、`Dynamo-SOSP'07`、
  `Haystack-OSDI'10`、`Lakehouse-CIDR'21` 等）都带图，缺图的新文档会
  与工作区风格脱节

**判定标准**（按优先级）：

1. ==必须上传==：论文 / 设计稿含 1 张或以上可识别的关键架构 / 示意图
   （整体架构、核心模块示意、概念流程图、关键对比示意、状态机）
2. ==可缺省==：原文是**纯理论推导 / 形式化证明 / 全文字实验报告**，
   确实**没有任何**架构 / 流程 / 概念类图（仅含坐标轴 plot、表格、
   实验数据柱状图不算关键图）
3. =="找不到"不算缺省理由==：用 `pdftotext` / 简单 OCR 容易漏掉嵌入
   图元；务必**人工 / 多模态识别**确认无关键图，才标"原文无图"并简述
   检索过程

**操作流程**（每张图严格 3 步）：

1. ==取图==：用 `pdftoppm` / `pymupdf` 从 PDF 抽取对应页面 / bbox
   渲染为 PNG（推荐 144 DPI / 2×），存到本地临时文件；只裁**图本身**，
   不要整页截图，避免把页眉 / 标题框进来
2. ==上传到 Outline==：先 `create_attachment(name, contentType, size)`
   拿预签名 `uploadUrl` → `curl` multipart 上传 → 拿到 `attachment.url`
   （形如 `/api/attachments.redirect?id=<uuid>`）
3. ==嵌入 Markdown==：在合适位置写
   `![图 N：<caption>](<attachment.url> "=WxH")`，title 给宽 × 高提示
   （仓库内 `=WxH` 约定详见 [`references/doc_style.md`](references/doc_style.md) §7）

**反模式**（"装作有图"的常见偷懒写法）：

- 只写 `*（详见原 PDF p.X fig.Y）*` 文字占位 —— Outline 里点不开，
  读者必须自己翻 PDF，违反"原位可读"原则
- 引用未上传的本地路径（只会渲染成破图，详见上节"反模式"）
- 上传整页截图 / 含无关边距 / 头部白边 —— 必须裁到图本身的 bbox
- 把多张图拼成一张大图上传 —— 失去单图可单独引用的能力

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
   → Markdown 引用 attachment URL"3 步（详见下方"图片插入 / 文件附件工作流"
   小节）；评论场景先 `list_comments` 看现有讨论再决定新建还是回复。
   ==写论文笔记 / 设计文档时，**关键架构图默认就要走这 3 步嵌入**，
   不要写文字占位（参见"文档风格 / 论文笔记 / 设计文档"小节）==
5. **验证结果**：检查返回是否成功；失败时按故障排查流程定位
6. **报告**：把做了什么、结果如何、是否需要后续动作告诉用户

### 图片插入 / 文件附件工作流

> **本 skill 的图片能力 = 上传 + 引用**——只解决"把本地文件变成 outline
> 里能渲染的图片"。**不**管图片怎么来：
> - 截图 / 配图 / logo 等任意本地图片：直接走下面 3 步
> - **论文关键架构图**：先走 [`gemini-paper-summary`](../../gemini-paper-summary/SKILL.md)
>   的 `--extract-figures` 抽到本地 `figures/*.png`，**再**走本 skill 的
>   attachment 3 步

**完整 3 步流程**（每张图独立走一遍）：

1. **预签名上传 URL**：调 `create_attachment(name, contentType, size)`
   ```text
   name: <filename>（如 figure-p1-f1.png）
   contentType: image/png（或 image/jpeg / image/webp）
   size: 文件字节数
   ```
   返回 `uploadUrl`（multipart 接收端点）+ 一组表单字段

2. **上传二进制**：用 `curl` 把本地文件 POST 到 `uploadUrl`（即 `/api/files.create`）。
   `attachments.create` 返回的 `form` 字段必须**逐字**回传（`Cache-Control` /
   `Content-Type` / `key` / `acl` / `maxUploadSize` / `_csrf`），再附 `file=@<path>`：
   ```bash
   $> KEY=$(jq -r '.data.form.key' <(curl -sS -X POST \
         -H "Authorization: Bearer $OUTLINE_API_KEY" \
         -H "Content-Type: application/json" \
         -d '{"name":"figure-p1-f1.png","contentType":"image/png","size":12345}' \
         "$OUTLINE_BASE/api/attachments.create"))
   $> curl -X POST "$OUTLINE_BASE/api/files.create" \
        -F 'Cache-Control=max-age=31557600' \
        -F 'Content-Type=image/png' \
        -F "key=$KEY" \
        -F 'acl=private' \
        -F 'maxUploadSize=26214400' \
        -F '_csrf=' \
        -F "file=@<本地文件路径>" \
        -H "Authorization: Bearer $OUTLINE_API_KEY"
   ```
   响应 `{"success":true, ...}` 才算上传成功（仅 metadata 返回但 `success=false`
   仍意味着文件未落盘，必须重试）

> **⚠️ create_attachment 只注册元数据，二进制必须自己 curl**
>
> 上一行 `create_attachment` 成功 ≠ 文件已上传。MCP 工具只接收
> `name / contentType / size` 三个参数，**不会**接收二进制内容。
> 缺了 step 2 的 curl，attachment 记录存在但内容是 0 字节，文档
> 嵌进去后浏览器加载图片失败 → **空白 / 破图**。**特别坑**：当时
> 不报错，事后才发现图都没显示。
>
> **认证**：用 outline MCP 配置里的 API key
> （`<endpoint 域名>/mcp` 对应的 `Authorization: Bearer <key>` 头，
> 已在 `~/.claude.json#mcpServers.outline.headers` 或
> `.claude/settings.local.json` 注册时填入）。**agent 可以直接拿来用**
> —— 跟 MCP server 用同一把 key，curl `/api/attachments.create` 和
> `/api/files.create` 都能过。不需要用户手动抓 cookie。
> **拿 key 的安全姿势**：先看 `tools/list` 里 attachment 工具能用 → 说明
> key 已在 MCP 端生效 → 直接用同一份 key 走 curl。
>
> **API key 拿不到 / curl 401 时的退路**（按优先级）：
> 1. 检查 `.claude/settings.local.json#mcpServers.outline.headers.Authorization`
>    是否真的填了 key；空 key 是 silent failure
> 2. 重跑 `outline-wiki-management/scripts/configure_mcp.py` 重新写 key
> 3. 用户在 Outline UI 拖拽图片进编辑器（编辑器自带 session auth）

3. **插入引用**：在 Markdown 里写
   ```markdown
   ![图 N：<caption>](<attachment.url> "=WxH")
   ```
   - `attachment.url` 形如 `/api/attachments.redirect?id=<uuid>`
   - `=宽x高` 给渲染尺寸（仓库内 `=WxH` 等宽约定，参见 `references/doc_style.md` §7）
   - 非图片附件可省略 `=WxH`

4. **必做验证**：写完 Markdown 引用**必须**核验 attachment 真有内容
   ```text
   mcp__outline__fetch attachment id=<attachment.id>
   → 拿到 signedUrl
   → 用 WebFetch / 浏览器访问 signedUrl
   → 必须返回 200 + 实际图片字节；404 / 0 字节 / HTML 错误页都算失败
   ```
   失败则**不能**写入文档，先解决 upload 再继续

**写入 / 替换方式**（视场景选）：

- **新建文档时**：直接把第 3 步的 `![...](...)` 嵌进 `create_document` 的 `text` 参数
- **替换已有文档中的图引用**：用 `update_document` + `editMode: "patch"` + `findText` 精准替换
  ```text
  findText: ![图 1：xxx](figures/figure-p1-f1.png)
  text: ![图 1：xxx](/api/attachments.redirect?id=<uuid> "=WxH")
  ```
  这样可保留其他内容（评论 / 高亮 / 表格宽度）不被破坏

**整篇重写**（replace 模式 + 大文档）**改用 REST API**（2026-06-21 经验）：

- **踩坑**：`mcp__outline__update_document` 的 `text` 字段在某些场景下会**吞掉换行符**——
  实测 3K 字符 markdown 经 tool 调用后，**首行表格的 3 个 row 之间的 `\n` 全部丢失**，
  三行被压成一行，表格渲染成单行 inline 元素。其他位置（list / 章节标题）换行正常，
  但首行表格三行是**必杀**。patch 模式更糟：`findText` 短匹配会**追加**而不是替换，
  导致 "3 句话总结" list 变成 5 条 1-2-3-4-5。
- **退路**：整篇重写时**不要**用 mcp tool，**改用** `POST /api/documents.update` 走
  curl + API key（key 同 MCP server 配置），payload 用文件传避免命令行转义：
  ```bash
  python3 -c "import json; json.dump({'id': '<doc-id>', 'text': open('summary.md').read()}, open('payload.json', 'w'), ensure_ascii=False)"
  curl -sS -X POST https://<endpoint>/api/documents.update \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <api-key>" \
    --data-binary @payload.json
  ```
  REST API 正确保留所有换行；返回 `{"data": {...}, "status": 200, "ok": true}`。
- **校验必做**：写完立刻 `mcp__outline__fetch` 看返回的 markdown body 是否有损坏
  （首行表格 / 列表 / 章节标题），如发现 → 重发。tool 返回 success 不代表存盘 OK
- **patch 模式坑**：`findText` 一定要**足够长**（至少含相邻 2-3 行），否则会被误追加；
  实测只匹配 1 行 list item 时，patch 行为是"在该 item 后追加"而不是"替换整段"

**反模式**（**别**这么干）：

- 引用未上传的本地路径（`![x](figures/figure-p1-f1.png)` 或 `![x](PDF p.X ...)`）——
  outline 渲染成**破图**，读者看不到
- 把整页 PDF 截图 / 包含页眉 / 段尾段落上传——必须只截**图本身**的 bbox
- 在 `create_document` / `update_document` 的 `text` 参数里**直接传图片二进制**——
  这两个工具**不**接收文件，只接受 Markdown 字符串

**读取已上传附件**：调 `fetch(resource="attachment", id=<id 或完整 redirect URL>)`
返回 short-lived 签名 URL，可直接下载。

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

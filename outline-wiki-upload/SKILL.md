---
name: outline-wiki-upload
description: 通过 Outline Wiki MCP **写** outline 工作区——核心写能力：创建 / 编辑文档；
  扩展写能力（server 实际暴露但官方文档未明列）：图片附件（create_attachment + curl +
  Markdown 引用 attachment URL）、@mention、评论、Collection 管理、移动 / 删除 / 归档文档。
  配套 Markdown 写作风格基线与 ProseMirror 节点映射（`*` bullet / `==高亮==` / `mermaidjs` /
  `=WxH` 图片尺寸等仓库指纹），以及写前必跑的 9 大类风格 checklist。**含图 / 长 markdown**
  走 create_attachment 3 步流程，**整篇重写**走 REST API 绕开 update_document 的换行
  吞字 bug。所有写操作走 MCP 工具（特殊情况除外），不直连 REST。触发词：'上传 outline'、
  '推到 outline'、'publish to outline'、'编辑 / 创建 / 写 outline 文档'、'outline 文档含
  图'、'@mention / 评论 outline'、'移动 / 删除 / 归档 outline 文档'、'outline collection
  管理'。**不**用于搜 / 读 outline 文档（走 outline-wiki-search）；**不**用于配置
  outline MCP（走 outline-wiki-setup）；**不**用于 Notion / Confluence / Obsidian /
  GitHub Wiki；'outline = 大纲 / 议程'同名词；分享 / 导出 / 权限调整（官方 MCP 文档未列
  且 server 通常也未暴露，走 UI 或 REST）。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-29
---

# Outline Wiki Upload

通过 Outline Wiki MCP 的**写**操作能力（创建 + 编辑 + 扩展能力 + 风格基线），
向工作区写入符合仓库指纹的 Markdown 文档。本 skill 是 outline-wiki-* 家族
中**最重**的一个——含核心写能力 2 个 + 扩展写能力 5 项 + 风格映射
（513 行 ProseMirror 节点表）+ 风格 checklist（9 大类）。

读 / 搜由 [`outline-wiki-search`](../outline-wiki-search/SKILL.md) 负责；
MCP 配置由 [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md) 负责。

## 何时使用 / 不使用

### 使用

- 用户说"创建 / 写 / 编辑 / 改 / 更新 / 推 / 上传 / publish / 同步 / 拷贝
  一篇文档到 outline"
- 用户说"outline 文档含图 / 把图传到 outline / 给 outline 文档插图"
- 用户说"@某人 / 评论 / 移动 / 删除 / 归档 / 整理 outline 文档"
- 用户说"管理 outline collection / 新建 collection / 改 collection 描述"
- 写新文档 / 大幅改写已有文档（含图 / 含 mermaid / 含 attachment 引用）
- 跑 gemini-paper-summary / 类似上游工具后，要把生成的本地 markdown + figures
  **推到 outline**——本 skill 是必经之路（attachment 3 步 + Markdown 替换）

### 不使用

- **搜 / 读 outline 文档**——走 [`outline-wiki-search`](../outline-wiki-search/SKILL.md)
- **配置 outline MCP**（首次接入 / 重启后看不到 / 401）——走
  [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md)
- **写前 search 查重 / 定位**——也是 `outline-wiki-search` 范畴（search + read
  是 read-only，与本 skill 的写配合形成"先搜后写"完整流程）
- 用户使用其他 wiki / 知识库产品（Notion / Confluence / Obsidian / GitHub Wiki）
- 分享、导出、权限调整（官方 MCP 文档未列、server 通常也未暴露）——
  走 Outline Wiki 自身 UI 或直接调 REST API
- 需要**彩色高亮**等 Markdown 表达不出来的富文本特性
  （`create_document` / `update_document` 不接收原始 ProseMirror 节点）——
  走 UI 或直接调 REST API 并附 `proseMirrorDoc` 参数

## 输入 / 输出

### 输入

启动时需具备以下**前置条件**——这些由 `outline-wiki-setup` 负责：

- **MCP 已注册**：当前 session 能调 `mcp__outline__*` 系列工具
  （若未注册，**先走 [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md)**，
  跑完重启后再回来）
- **Collection ID**（写文档必传；如 schema 允许按名称引用，按 schema 调用）
- **用户自然语言指令**：新建 / 编辑指令、文档内容、目标 Collection

### 输出

- **创建 / 编辑结果**：新文档 ID + URL；或 patch 后返回的更新版本
- **图片附件 ID**：走完 attachment 3 步后返回的 `/api/attachments.redirect?id=<uuid>`
- **错误信息**：MCP 调用失败 / attachment 0 字节 / Markdown 换行被吞等

## 设计决策（按 ProseMirror JSON 的"投影"写 Markdown）

> Outline 后端持久化的是 **ProseMirror 节点树**，MCP 工具的 `create_document` /
> `update_document` 只接受 Markdown 字符串作为输入。因此：
> - **写之前**先想清楚这条 Markdown 会被解析成哪个 ProseMirror 节点
> - **不要**使用 Markdown 表面能写、但 ProseMirror schema 不接受的语法
> - **不要**使用 Markdown 表面写不出来、必须靠 UI 才能表达的语法（如指定
>   highlight 颜色）；这类需求走 [`references/doc_style.md`](references/doc_style.md)
>   "进阶"路径

详细 Markdown ↔ ProseMirror 节点映射表见
[`references/doc_style.md`](references/doc_style.md)。本 SKILL.md 只列风格速查
表 + 关键反模式，**完整的 §1-§13 映射 + 图片附件上传流程 + @mention 语法 +
彩色高亮写不出来**都在 references 里。

## MCP 工具发现（重要）

**官方 MCP 文档列出 4 个核心能力（search / read / create / edit），并未枚举
具体工具名**；实际接入的 server 通常还暴露了图片附件、@mention、评论、
Collection 管理、移动 / 删除等扩展工具。本 skill 因此**不写死**任何工具名——
会话开始时必须先调用 MCP 的 `tools/list` 端点，核实当前 MCP server 实际
暴露的工具名、参数 schema、返回结构，再据此调用。

约定：下文出现的"创建 / 编辑 / 图片附件 / 评论 / Collection 管理"等指
**能力**而非具体工具名；调用前先 `tools/list` 取真实工具名再做映射。扩展
能力是否可用也以 `tools/list` 的实际返回为准。

## 能力清单

按"工具来源"分两组。**核心能力**对应官方文档明列的 4 个高层操作中的
create / edit 两个（search / read 由 [`outline-wiki-search`](../outline-wiki-search/SKILL.md)
负责）；**扩展能力**对应官方文档未明列但本会话实测可用、且在不同 self-hosted
部署里通常也暴露的工具。扩展能力**强烈建议**先用 `tools/list` 确认目标
server 是否暴露对应工具，再做调用。

### 核心能力

#### 1. Create（创建）

在指定 Collection 下新建文档；如需嵌套子页需传入父文档 ID。

典型参数：

- `title`（必选）
- `content`（必选）：Markdown 原文
- `collection_id`（必选）：目标 Collection
- `parent_document_id`（可选）：父文档 ID（创建子页时设置）

#### 2. Edit（编辑）

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

> 以下工具官方 MCP 文档未明列，但是当前 server（及大多数 self-hosted 部署）
> 实际暴露的能力；本 skill 收录并以正式流程对待。使用前 `tools/list` 确认即可。

#### 3. Image / 文件附件（create_attachment + fetch attachment）

MCP `create_document` / `update_document` 只接受 Markdown 字符串，**不接收
文件二进制**。要把图片或文件嵌进文档，必须先走 attachment 通道
（`create_attachment` → `curl` 上传 → Markdown 引用 attachment URL），3 步
流程 + curl 模板详见下方"工作流 / 步骤 / 图片插入 / 文件附件工作流"小节。

#### 4. @mention 用户（list_users）

`list_users` 按关键字（名字 / email）查工作区成员；配合 Markdown 语法
`@[Display Name](mention://user/<userId>)` 即可在文档里 @ 到具体用户，Outline
UI 会渲染成可点击链接。

#### 5. 评论（create_comment / list_comments / update_comment / delete_comment）

在指定文档（或顶层 / 内联）下创建 / 列出 / 修改 / 删除评论；支持嵌套回复
（`parentCommentId`）。`update_comment` 还能 resolve / unresolve 顶层评论
（`status: resolved` / `unresolved`）。对他人文档建议先 `list_comments` 看现有
讨论再决定新建还是回复。

#### 6. Collection 管理

- `list_collections`：列出工作区可见的 Collection
- `list_collection_documents`：返回 Collection 的完整文档树（含嵌套子文档）
- `create_collection` / `update_collection`：新建 / 修改 Collection
  （name / description / icon / color）
- `delete_collection`：删除 Collection；可设置 `archive=true` 走归档

> 注意：删除 Collection 会**级联删除**其下未归档的文档；批量移动前先用
> `list_collection_documents` 看清楚结构。

#### 7. Move / Delete 文档

- `move_document`：把文档移到别的 Collection 或父文档下，可指定 `index`
  控制同级排序
- `delete_document`：删除文档（默认进 trash，30 天内可在 trash 中恢复）；
  可设 `archive=true` 直接归档而**不进** trash

## 文档风格（仓库指纹速查）

完整 Markdown ↔ ProseMirror 映射、图片附件上传流程、彩色高亮等 Markdown
写不出来的特性如何处理，见 [`references/doc_style.md`](references/doc_style.md)。
写新文档 / 大幅改写前的最后一道防线是
[`references/style_checklist.md`](references/style_checklist.md) 的 9 大类
checklist——按顺序勾选一遍能避免 90% 的风格漂移。

### 风格基线（速查表）

| 元素 | 仓库约定 | 说明 |
| --- | --- | --- |
| 顶部结构 | `# Reference` 段开头，列外部资料 | 仓库内事实标准 |
| 标题层级 | `#` / `##` / `###` 表达逻辑层级；**正文不要 H1**（title 单独传） | 标准 + MCP 约束 |
| Bullet marker | `*`（不用 `-` / `+`） | 仓库统一 |
| 高亮 | `==text==` 标记关键术语 / 参数 / 状态 | 仓库指纹（默认色） |
| 代码块语言 | 必填（`bash` / `python` / ...） | 习惯 |
| Shell 提示符 | `$>` 后接一个空格 | 仓库自创约定 |
| 图片 | `![alt](/api/attachments.redirect?id=... "=WxH")` | attachment 引用，详见 doc_style.md §7 / §12 |
| @mention | `@[Name](mention://user/<userId>)` | server 扩展语法，详见 doc_style.md §13 |
| Mermaid 标识符 | `` ```mermaidjs ``（**不是** `mermaid`） | 仓库指纹 |
| 语言 | 中文叙述 + 英文术语混排 | 习惯 |
| 行宽 | 遵守 `.markdownlint.jsonc` MD013 | 阈值见 doc_style.md §3 |

### 反模式（写之前先看）

- 用 `-` 或 `+` 起 bullet（破坏统一）
- 正文以 H1 开头（title 已单独传，再加正文 H1 与标题重复）
- 期望 `==text==` 出现彩色高亮（Markdown 写不出来，详见 doc_style.md §进阶）
- 私造非 Outline 支持的语法（`!!!`、HTML 标签等）
- 引入外部私有扩展（MathJax、`:::tip` 等）
- 大段纯段落不分 bullet（仓库内极少用纯段落）
- 引用未上传的本地图片路径（只会渲染成破图，必须先走 attachment 流程）

### 论文笔记 / 设计文档：关键架构图 / 示意图默认必须

仓库内 `论文笔记` Collection、`数据结构与算法 → 索引类` 这类**以展示系统
/ 算法设计为核心**的文档（也包括 `design-doc-edit` 的产出），**关键架构图
/ 示意图是默认要求**——而不是可选项。判定标准与完整操作流程见
[`references/style_checklist.md`](references/style_checklist.md) §9。

## 执行原则 / 边界

### 核心原则

1. **写前先搜（Read-First）**
   - 创建新文档前必须先用 `outline-wiki-search` 查重，确认是否已有同类但
     内容过期
   - 若已有同类文档，用 edit 更新而不是 create 重复
2. **严格 Markdown 格式**
   - Outline Wiki 是 Markdown 优先平台，所有内容必须用合法、纯净的 Markdown
   - 用 `#` / `##` / `###` 体现逻辑层级，自动生成清晰目录
   - 不引入 Outline Wiki 不支持的非标准私有扩展语法
3. **工具名核实（Tools-First）**
   - 不假定工具名的拼写、是否带前缀（如 `outline_`）
   - 任何操作前先 `tools/list` 拿真实工具清单
4. **能力边界分两组处理**
   - **核心能力**（create / edit）：官方文档明列，直接调用
   - **扩展能力**（图片附件 / @mention / 评论 / Collection 管理 / move /
     delete）：server 实际暴露但官方文档未列；调用前 `tools/list` 确认是否
     暴露
   - 用户要求"分享 / 导出 / 权限调整"等操作时，明确告知这些不在本 skill
     覆盖范围，建议走 Outline Wiki 自身 UI 或直接调 REST API
5. **破坏性操作先确认**
   - 删除 / 归档他人文档、移动文档、改 Collection 等**破坏性操作**必须先
     在会话内显式确认
   - 对他人文档建议用 `create_comment` 提议而非直接覆盖

### 边界

- **不**处理非 Outline Wiki 的知识库
- **不**在 MCP 未启用时尝试操作（先走 `outline-wiki-setup`）
- **不**支持分享 / 导出 / 权限调整（官方 MCP 文档未列、server 通常也未
  暴露）—— 走 Outline UI 或 REST API
- **不**支持彩色高亮（Markdown 写不出来，`create_document` /
  `update_document` 不接收原始 ProseMirror 节点）—— 走 Outline UI 或 REST API
  时附 `proseMirrorDoc` 参数
- **不**绕过 `tools/list` 凭"印象"调用工具
- **不**在 server 端生成 / 撤销 API Key（那是 Outline Wiki 用户在
  **Settings → API** 中的操作）

## 工作流 / 步骤

### 标准流程

1. **核实配置与工具**：会话开始时——
   - 确认 outline 相关 MCP 工具在当前 session 已注册；若未注册，**先走
     [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md)**，跑完重启后
     再回来
   - 调 MCP `tools/list` 取实际工具清单（核心能力 + 扩展能力各自对应的
     真实工具名、参数 schema）
2. **理解意图**：把用户的自然语言指令映射到能力清单之一（核心或扩展）
3. **先搜后写**（与 `outline-wiki-search` 协作）：涉及"创建 / 编辑"前，
   先 search 查重 / 定位目标文档；涉及"图片"前先确认 attachment 通道
   （`create_attachment`）可用
4. **执行操作**：
   - 调用对应工具
   - 图片场景走"create_attachment → curl 上传 → Markdown 引用 attachment URL"
     3 步（详见下方"图片插入 / 文件附件工作流"）
   - 评论场景先 `list_comments` 看现有讨论再决定新建还是回复
   - **写论文笔记 / 设计文档时，关键架构图默认就要走这 3 步嵌入**，
     不要写文字占位（参见上文"文档风格 / 论文笔记"小节）
   - **破坏性操作**（delete / move_document / delete_collection）先确认
5. **验证结果**：检查返回是否成功；失败时按故障排查流程定位
6. **报告**：把做了什么、结果如何、是否需要后续动作告诉用户

### 图片插入 / 文件附件工作流

> **本 skill 的图片能力 = 上传 + 引用**——只解决"把本地文件变成 outline 里
> 能渲染的图片"。**不**管图片怎么来：
> - 截图 / 配图 / logo 等任意本地图片：直接走下面 3 步
> - **论文关键架构图**：先走 [`gemini-paper-summary`](../../gemini-paper-summary/SKILL.md)
>   的 `--extract-figures` 抽到本地 `figures/*.png`，**再**走本 skill 的
>   attachment 3 步

**完整 3 步流程**（每张图独立走一遍）：

1. **预签名上传 URL**：调 `create_attachment(name, contentType, size)`
   ```text
   name: （如 figure-p1-f1.png）
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
> `name / contentType / size` 三个参数，**不会**接收二进制内容。缺了 step 2
> 的 curl，attachment 记录存在但内容是 0 字节，文档嵌进去后浏览器加载图片
> 失败 → **空白 / 破图**。**特别坑**：当时不报错，事后才发现图都没显示。
>
> **认证**：用 outline MCP 配置里的 API key
> （`<endpoint 域名>/mcp` 对应的 `Authorization: Bearer <key>` 头，
> 已在 `~/.claude.json#mcpServers.outline.headers` 或
> `.claude/settings.local.json` 注册时填入）。**agent 可以直接拿来用**——
> 跟 MCP server 用同一把 key，curl `/api/attachments.create` 和
> `/api/files.create` 都能过。不需要用户手动抓 cookie。
>
> **拿 key 的安全姿势**：先看 `tools/list` 里 attachment 工具能用 → 说明
> key 已在 MCP 端生效 → 直接用同一份 key 走 curl。
>
> **API key 拿不到 / curl 401 时的退路**（按优先级）：
> 1. 检查 `.claude/settings.local.json#mcpServers.outline.headers.Authorization`
>    是否真的填了 key；空 key 是 silent failure
> 2. 重跑 `outline-wiki-setup/scripts/configure_mcp.py` 重新写 key
> 3. 用户在 Outline UI 拖拽图片进编辑器（编辑器自带 session auth）

3. **插入引用**：在 Markdown 里写
   ```markdown
   ![图 N：<caption>](<attachment.url> "=WxH")
   ```
   - `attachment.url` 形如 `/api/attachments.redirect?id=<uuid>`
   - `=宽x高` 给渲染尺寸（仓库内 `=WxH` 等宽约定，参见 doc_style.md §7）
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

- **踩坑**：`mcp__outline__update_document` 的 `text` 字段在某些场景下会**吞掉
  换行符**——实测 3K 字符 markdown 经 tool 调用后，**首行表格的 3 个 row 之间
  的 `\n` 全部丢失**，三行被压成一行，表格渲染成单行 inline 元素。其他位置
  （list / 章节标题）换行正常，但首行表格三行是**必杀**。patch 模式更糟：
  `findText` 短匹配会**追加**而不是替换，导致 "3 句话总结" list 变成 5 条
  1-2-3-4-5。
- **退路**：整篇重写时**不要**用 mcp tool，**改用**
  `POST /api/documents.update` 走 curl + API key（key 同 MCP server 配置），
  payload 用文件传避免命令行转义：
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
- **patch 模式坑**：`findText` 一定要**足够长**（至少含相邻 2-3 行），否则会被
  误追加；实测只匹配 1 行 list item 时，patch 行为是"在该 item 后追加"而不是
  "替换整段"

**反模式**（**别**这么干）：

- 引用未上传的本地路径（`![x](figures/figure-p1-f1.png)` 或 `![x](PDF p.X ...)`）——
  outline 渲染成**破图**，读者看不到
- 把整页 PDF 截图 / 包含页眉 / 段尾段落上传——必须只截**图本身**的 bbox
- 在 `create_document` / `update_document` 的 `text` 参数里**直接传图片二进制**——
  这两个工具**不**接收文件，只接受 Markdown 字符串

**读取已上传附件**：调 `fetch(resource="attachment", id=<id 或完整 redirect URL>)`
返回 short-lived 签名 URL，可直接下载。

### 客户端接入（首次使用）

> **本节只是一句话索引**——首次接入 / 重启验证 / 故障排查的完整流程由
> [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md) 负责。本 skill 假设
> MCP 已注册可用；若不可用先走 setup skill 跑完重启再回来。

### 故障排查

按以下顺序定位：

1. **认证失败（401 / 403）**
   - 这是 `outline-wiki-setup` 的范畴（key 过期 / OAuth 失效），先重启或
     重新跑配置脚本
2. **MCP 未启用（连接被拒）**
   - 走 `outline-wiki-setup` 排查配置
3. **工具名不匹配**
   - 重新调 `tools/list` 拿当前工具清单；不要凭记忆中的名字调用
4. **文档 ID 无效**
   - 用 `outline-wiki-search` 重新定位目标文档，拿到新 ID
   - 不要凭缓存的 ID 直接调用——文档可能已被归档 / 重命名
5. **图片 attachment 0 字节 / 404**
   - 重跑 attachment 3 步（create_attachment → curl 上传 → Markdown 引用）
   - 验证 fetch 返回 signedUrl 能 200 下载到字节
6. **首行表格 `\n` 丢失**
   - 改走 REST API `POST /api/documents.update`（key 同 MCP server 配置）

## 参考样例

### 样例一：创建新文档

**用户指令**："在 '后端' Collection 下新建一篇'缓存策略'文档"

**执行**：

```text
1. 用 outline-wiki-search 查 '后端' Collection ID（若 create schema 要求）
2. 撰写 Markdown 正文（按 doc_style.md 风格基线 + style_checklist.md 9 大类）
3. 调用 create_document 工具传 title / content / collection_id
4. 验证返回成功，把新文档链接 / ID 告诉用户
```

> 注：Collection ID 在官方文档中**未明示**如何获取；如果 `tools/list` 中
> create 工具的 schema 不要求 collection_id（例如允许按 Collection 名称引用），
> 则按实际 schema 调用。

### 样例二：更新已存在文档

**用户指令**："把 doc_abc123 的'部署步骤'小节加上'回滚方案'一段"

**执行**：

```text
1. 用 outline-wiki-search 读 doc_abc123 拿当前正文
2. 找到"部署步骤"小节，追加"回滚方案"段落（保持 Markdown 层级）
3. edit 工具更新 content 为新正文（editMode: "replace"）
4. 验证返回成功
```

### 样例三：从 gemini-paper-summary 推图到 outline

**用户指令**："把 gemini-paper-summary 生成的 `~/out/<slug>/summary.md` + `figures/*.png`
推到 outline 工作区"

**执行**：

```text
1. 用 outline-wiki-search 查目标 Collection + 是否已有同名文档
2. 对每张 figures/*.png 走 attachment 3 步（详见上文"图片插入"）
3. 用 outline-wiki-search 的 read 拿当前 summary.md 中所有
   ![图 N](figures/figure-pX-fN.png) 引用
4. 用 update_document + editMode: "patch" + findText 精准替换每张图为
   ![图 N](/api/attachments.redirect?id=<uuid> "=WxH")
5. 验证 fetch 返回每张图 signedUrl 能 200 下载
6. （可选）删本地 figures/ 目录
```

## 相关参考

- [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md) — 配套：MCP 配置与首次接入
- [`outline-wiki-search`](../outline-wiki-search/SKILL.md) — 配套：搜 / 读 outline 文档
  （本 skill 的"写前 search 查重"协作方）
- [`references/doc_style.md`](references/doc_style.md) — Markdown ↔ ProseMirror
  节点映射（§1-§13）+ 图片附件上传流程（§12）+ @mention（§13）+ 进阶
- [`references/style_checklist.md`](references/style_checklist.md) — 写前必跑的
  9 大类风格 checklist
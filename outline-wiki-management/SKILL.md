---
name: outline-wiki-management
description: 通过 Outline Wiki 内置的 MCP 服务管理知识库：搜索、读取、创建、编辑、评论、归档文档
---

# Outline Wiki Management

通过 Outline Wiki（提供的知识库产品）内置的 MCP 服务，
在对话中直接对其工作区内的文档进行搜索、读取、创建、编辑、评论与归档。
本 skill 的所有读写动作都通过 MCP 工具完成，不直接访问 Outline Wiki 的 REST API
或第三方接入方式。

## 何时使用 / 不使用

### 使用

- 用户在对话中明确提到 Outline Wiki
- 需要在 Outline Wiki 工作区中按关键词搜索、读取、创建、修改、归档文档
- 需要在某篇文档下发表评论或反馈（用于建议改动、提出问题）
- 需要查询工作区的 Collection 结构以决定文档归属

### 不使用

- 用户使用其他 wiki / 知识库产品（Notion / Confluence / GitHub Wiki /
  本地 Markdown 文件夹 / Obsidian 等）
- Outline Wiki 实例未启用 MCP 服务（需用户先去工作区 **Settings → AI** 开启）
- 需要执行破坏性操作（归档 / 删除）但**未获得用户明确确认**
- 需要读取的是 Outline Wiki 之外的资源（链接指向的外部网页、二进制附件等）

## 输入 / 输出

### 输入

启动时需具备以下信息：

- **MCP 端点**（必选）：
  - 自托管 Outline Wiki：`https://<yourdomain>/mcp`
- **认证方式**（二选一）：
  - **OAuth（默认）**：连接时弹出交互式登录窗口
  - **API Key**：在 Outline Wiki 设置中生成，写入 MCP 头
    `Authorization: Bearer <your-api-key>`
- **用户自然语言指令**：搜索关键词 / 文档 ID / 创建 / 编辑 / 评论等

### 可用 MCP 工具

工具名称可能带或不带 `outline_` 前缀——**会话开始时必须先调用
`tools/list` 核实**实际可用的工具名。

#### 发现与搜索

- `search_documents(query, collection_id?, limit?, offset?)`：
  在工作区内执行全文搜索
- `list_collections()`：列出所有有权限的 Collection（根级文件夹）
- `get_collection_structure(collectionId)`：获取 Collection 的文档树层级

#### 文档操作

- `get_document(id)` / `read_document(id)`：获取文档的 Markdown
  原文与元数据
- `create_document(title, content, collectionId, parentDocumentId?)`：
  在指定 Collection 下创建文档，`parentDocumentId` 用于创建子页
- `update_document(id, title?, content?)`：修改标题或 Markdown 正文
- `archive_document(id)`：归档文档（移入 Trash / Archive）

#### 协作

- `list_document_comments(documentId)`：列出某篇文档的所有评论
- `create_comment(documentId, content)`：在某篇文档下发表新评论

### 输出

- **文档内容**（Markdown 原文 + 元数据）
- **搜索结果**（文档 ID 列表 + 摘要）
- **操作结果**（创建 / 更新 / 归档 / 评论的返回值）
- **错误信息**（401 / 403 / 连接失败 / ID 无效等，需进入故障排查流程）

## 执行原则 / 边界

### 核心原则

1. **写前先搜（Read-First）**
   - 创建新文档前必须用 `search_documents` 搜索关键词，确认是否有类似文档
   - 若已有同类但内容过期，用 `update_document` 更新而不是新建重复
2. **严格 Markdown 格式**
   - Outline 是 Markdown 优先的平台，必须用合法、纯净的 Markdown
   - 用 `#` / `##` / `###` 体现逻辑层级，自动生成清晰目录
   - 除非 Outline 明确支持，否则不引入非标准的私有扩展语法
3. **维护结构与层级**
   - 文档**不能孤立创建**，必须挂到合适的 Collection（`collectionId`）
   - 创建嵌套子页前先调用 `get_collection_structure` 拿到当前层级，
     再设置 `parentDocumentId`
4. **安全协作与破坏性操作**
   - 归档 / 删除任何文档**前**必须获得用户在当前会话中的明确确认
   - 对他人撰写的文档提改动建议时，用 `create_comment` 发起讨论，
     **不要**直接 `update_document` 覆盖

### 边界

- **不**处理非 Outline Wiki 的知识库（用对应产品的 skill / 工具）
- **不**在 MCP 未启用时尝试操作（提示用户去 **Settings → AI** 开启）
- **不**擅自归档 / 删除他人撰写的文档
- **不**绕过用户确认直接执行破坏性操作
- **不**修改 MCP 端点配置本身（OAuth / API Key 由用户在 Outline 设置中管理）

## 工作流 / 步骤

### 标准流程

1. **核实工具**：会话开始时调用 `tools/list`，
   确认 `outline_*` 工具（或不带前缀的同名工具）当前可用且名称一致
2. **理解意图**：把用户的自然语言指令映射到具体操作
   （搜索 / 读取 / 创建 / 更新 / 评论 / 归档）
3. **先搜后写**：涉及"创建 / 更新"前，先 `search_documents` 查重
4. **定位层级**：涉及"创建 / 移动"时，
   用 `list_collections` + `get_collection_structure` 拿到正确的 ID
5. **执行操作**：调用对应工具
6. **验证结果**：检查返回是否成功；失败时按故障排查流程定位
7. **报告**：把做了什么、结果如何、是否还需要后续动作告诉用户

### 故障排查

按以下顺序定位：

1. **认证失败（401 / 403）**
   - API Key：检查是否过期或被撤销，让用户重新生成
   - OAuth：让用户重新走一次授权流程
2. **MCP 未启用（连接被拒）**
   - 提示用户到 Outline 工作区 **Settings → AI** 确认 MCP toggle 已开启
   - 自托管实例需管理员在控制台开启
3. **层级引用错误（`create_document` 报 collection / parent 不存在）**
   - 重新调用 `list_collections` 与 `get_collection_structure` 拉取最新 ID
   - 不要凭记忆中的 ID 直接调用——ID 可能已变更

## 参考样例

### 样例一：搜索现有文档

**用户指令**："帮我在 Outline 里搜一下'CI 部署流程'相关的文档"

**执行**：

```text
1. 调用 search_documents(query="CI 部署流程", limit=10)
2. 整理返回的文档列表，按相关度展示给用户
3. 若用户要打开某篇，再用 get_document(id=<选中项>) 拉取正文
```

### 样例二：更新已存在文档

**用户指令**："把 doc_abc123 的'部署步骤'小节加上'回滚方案'一段"

**执行**：

```text
1. 调用 get_document(id="doc_abc123") 拿到当前正文
2. 找到"部署步骤"小节，追加"回滚方案"段落（保持 Markdown 层级）
3. 调用 update_document(id="doc_abc123", content=<新正文>)
4. 验证返回成功
```

### 样例三：创建新文档

**用户指令**："在 '后端' Collection 下新建一篇'缓存策略'文档"

**执行**：

```text
1. 调用 list_collections() 找到名为"后端"的 collectionId
2. 调用 get_collection_structure(collectionId=<id>) 决定是否需要 parentDocumentId
3. 撰写 Markdown 正文
4. 调用 create_document(
     title="缓存策略",
     content=<正文>,
     collectionId=<id>,
     parentDocumentId=<可选>
   )
5. 验证返回成功，把新文档链接 / ID 告诉用户
```

### 样例四：用评论提改动建议

**用户指令**："doc_xyz789 里那段'监控告警'的阈值设置错了，建议改成 5 分钟，
但先别直接改"

**执行**：

```text
1. 调用 list_document_comments(documentId="doc_xyz789")
   查看是否已有相关讨论（避免重复评论）
2. 调用 create_comment(
     documentId="doc_xyz789",
     content="建议把监控告警的阈值从 10 分钟改为 5 分钟，理由：xxx"
   )
3. 告诉用户评论已发出，等待文档作者确认
```

---
name: outline-wiki-management
description: 通过 Outline Wiki 内置的 MCP 服务（端点形如
  https://your-subdomain.getoutline.com/mcp，自托管改为 https://your-domain/mcp；
  OAuth 或 API Key 鉴权）管理工作区文档。严格对齐官方 MCP 文档所列的 4 个
  高层能力：搜索、读取、创建、编辑。所有读写动作都通过 MCP 工具完成，不直连
  REST API。当用户在对话中提到 Outline Wiki、需要按关键词搜文档、读取 / 编辑 /
  新建文档时使用。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-17
---

# Outline Wiki Management

通过 Outline Wiki 提供的内置 MCP 服务（Model Context Protocol），在对话中
直接对其工作区内的文档进行**搜索、读取、创建、编辑**。本 skill 严格对齐
[Outline 官方 MCP 文档](https://docs.getoutline.com/s/guide/doc/mcp-6j9jtENNKL)
所列的 4 个高层能力，不引入官方未明示的操作（如归档、评论、Collection
层级管理、删除、分享、导出、权限调整等）。

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
- 需要执行官方文档**未列出**的操作：归档、评论、Collection 层级浏览、
  删除、分享、导出、权限调整等——这些操作本 skill 不覆盖，应建议用户走
  Outline Wiki 自身 UI 或直接调 REST API
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

**官方 MCP 文档只列了 4 个高层能力（search / read / create / edit），
并未枚举具体工具名**。本 skill 因此**不写死**任何工具名——会话开始时
必须先调用 MCP 的 `tools/list` 端点，核实当前 MCP server 实际暴露的
工具名、参数 schema、返回结构，再据此调用。

约定：下文出现的"搜索 / 读取 / 创建 / 编辑"指的是**能力**而非具体
工具名；调用前先 `tools/list` 取真实工具名再做映射。

## 4 个能力

### 1. Search（搜索）

按关键词在工作区执行全文搜索，返回匹配的文档列表。

典型参数（具体以 `tools/list` 实际返回为准）：

- `query`：搜索关键词（必选）
- `collection_id`（可选）：限定 Collection 范围
- `limit` / `offset`（可选）：分页

### 2. Read（读取）

按文档 ID 获取 Markdown 原文与元数据。

典型参数：

- `id`（必选）：文档 ID
- 返回：标题、Markdown 原文、Collection、创建 / 修改时间、作者等

### 3. Create（创建）

在指定 Collection 下新建文档；如需嵌套子页需传入父文档 ID。

典型参数：

- `title`（必选）
- `content`（必选）：Markdown 原文
- `collection_id`（必选）：目标 Collection
- `parent_document_id`（可选）：父文档 ID（创建子页时设置）

### 4. Edit（编辑）

修改已有文档的标题或 Markdown 正文。

典型参数：

- `id`（必选）：目标文档 ID
- `title`（可选）
- `content`（可选）

> 注：编辑操作可能要求传完整正文，也可能支持局部替换，**以 `tools/list`
> 实际返回的参数 schema 为准**。

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
4. **遵循官方能力边界**
   - 只使用官方文档列出的 4 个能力
   - 用户要求"归档 / 评论 / 删除 / 分享 / 导出"等操作时，明确告知这些
     不在本 skill 覆盖范围，建议走 Outline Wiki 自身 UI 或直接调 REST API

### 边界

- **不**处理非 Outline Wiki 的知识库
- **不**在 MCP 未启用时尝试操作（提示用户到 **Settings → AI** 开启）
- **不**做官方未列出的操作（归档 / 评论 / 集合管理 / 删除 / 分享 / 导出）
- **不**绕过 `tools/list` 凭"印象"调用工具
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
   - 调 MCP `tools/list` 取实际工具名（search / read / create / edit
     各自对应的真实工具名）
2. **理解意图**：把用户的自然语言指令映射到 4 个能力之一
3. **先搜后写**：涉及"创建 / 编辑"前，先 search 查重 / 定位目标文档
4. **执行操作**：调用对应工具
5. **验证结果**：检查返回是否成功；失败时按故障排查流程定位
6. **报告**：把做了什么、结果如何、是否需要后续动作告诉用户

### 客户端接入

> **详细内容已抽出到 [`references/onboarding.md`](references/onboarding.md)**，
> 包括快速入口、检测当前状态、引导配置（agent 收集信息的 Q1/Q2 模板）、
> 调用脚本、手动退路、**重启后验证清单**、**设计决策**（为什么必须
> 重启）、常见问题与旧版配置清理。本节只留工作流中需要的骨架。

首次使用本 skill、或 outline 相关 MCP 工具在当前 session 不可用时，
**主动**完成客户端接入（agent 驱动），而不是只让用户手动跑脚本。
脚本的注册目标是 `~/.claude.json` 的 `mcpServers.outline` 段（**用户级**
scope，`--scope user`），等价于 `claude mcp add --scope user`。该路径
写一次在**所有项目下**生效，规避了项目级 `mcpServers` 需 trust prompt
才生效的问题。

受控的客户端配置入口是 **`scripts/configure_mcp.py`**：agent 收集
endpoint + 鉴权材料后调脚本写入 `~/.claude.json#mcpServers`。agent
**不**直接调 `claude mcp add`、也**不**直接编辑 `~/.claude.json` 或
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

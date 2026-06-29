---
name: outline-wiki-search
description: 通过 Outline Wiki MCP 在工作区内**搜**和**读**文档——按关键词全文
  搜索、按文档 ID 拉 Markdown 原文与元数据。所有读操作走 MCP 工具，不直连 REST。
  触发词：'搜 outline'、'找 outline 文档'、'读 outline 文档'、'outline 里搜
  / 查 / 找'、'outline 工作区搜一下'、'打开 outline 文档 / 取 outline 内容'。
  **不**用于写 / 编辑 / 上传 outline 文档（包含图片附件、@mention、评论、
  Collection 管理、移动 / 删除 / 归档）——那些走 outline-wiki-upload；**不**
  用于配置 outline MCP —— 走 outline-wiki-setup；**不**用于 Notion / Confluence /
  Obsidian / GitHub Wiki；'outline = 大纲 / 议程'同名词；分享 / 导出 / 权限调整
  （官方 MCP 文档未列且 server 通常也未暴露，走 UI 或 REST）。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-29
---

# Outline Wiki Search

通过 Outline Wiki MCP 的**只读**操作能力（搜索 + 读取），在工作区内定位
文档、拿 Markdown 原文与元数据。本 skill 是 outline-wiki-* 家族中**最小**
的一个——只有核心能力的 1 / 2（search / read），无任何写操作。

写 / 编辑 / 上传相关操作由 [`outline-wiki-upload`](../outline-wiki-upload/SKILL.md)
负责；MCP 配置由 [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md) 负责。

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
  [`outline-wiki-upload`](../outline-wiki-upload/SKILL.md)
- **配置 outline MCP**（首次接入 / 重启后看不到 / 401）——走
  [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md)
- 用户使用其他 wiki / 知识库产品（Notion / Confluence / Obsidian / GitHub Wiki）
- 分享、导出、权限调整（官方 MCP 文档未列、server 通常也未暴露）——
  走 Outline Wiki 自身 UI 或直接调 REST API
- 写操作前"先 read 一下"——这是 outline-wiki-upload 的"读 - 改"流程前置
  步骤，**不是**本 skill 的场景；user 表达"我要改这篇"时直接走 upload

## 输入 / 输出

### 输入

启动时需具备以下**前置条件**——这些由 `outline-wiki-setup` 负责：

- **MCP 已注册**：当前 session 能调 `mcp__outline__*` 系列工具
  （若未注册，**先走 [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md)，
  跑完重启后再回来**）
- **用户自然语言指令**：搜索关键词 / 文档 ID

### 输出

- **搜索结果**：匹配的文档列表（含 ID、标题、摘要）
- **文档内容**：Markdown 原文 + 元数据（创建时间、作者、Collection 等）
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

按文档 ID 获取 Markdown 原文与元数据。

典型参数：

- `id`（必选）：文档 ID
- 返回：标题、Markdown 原文、Collection、创建 / 修改时间、作者等

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
     [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md)**，跑完重启后
     再回来
   - 调 MCP `tools/list` 取 search / read 的实际工具名、参数 schema
2. **理解意图**：把用户的自然语言指令映射到 search 或 read
3. **执行操作**：
   - search → 按关键词 + 可选 collection_id + 分页参数
   - read → 按文档 ID
4. **验证结果**：检查返回是否成功
5. **报告**：把找到的文档列表 / 读到的 Markdown 原文 / 元数据告诉用户
6. **衔接**（可选）：如果用户后续要写 / 编辑当前找到的文档，明确告知
   "下一步走 `outline-wiki-upload`"

### 故障排查

按以下顺序定位：

1. **工具名不匹配**
   - 重新调 `tools/list` 拿当前工具清单；不要凭记忆中的名字调用
2. **文档 ID 无效**
   - 用 search 重新定位目标文档，拿到新 ID
   - 不要凭缓存的 ID 直接调用——文档可能已被归档 / 重命名
3. **认证失败（401 / 403）**
   - 这是 `outline-wiki-setup` 的范畴（key 过期 / OAuth 失效），先重启或
     重新跑配置脚本
4. **MCP 未启用 / 连接被拒**
   - 走 `outline-wiki-setup` 排查配置

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
2. 调用 read 工具，id="doc_abc123"
3. 把标题 + Markdown 原文 + 元数据（Collection / 时间 / 作者）一并展示
4. 若用户后续要"改这篇"，明确告知下一步走 outline-wiki-upload
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

- [`outline-wiki-setup`](../outline-wiki-setup/SKILL.md) — 配套：MCP 配置与首次接入
- [`outline-wiki-upload`](../outline-wiki-upload/SKILL.md) — 配套：写 / 编辑 outline 文档
- **不在本 skill 范围内**：
  - 文档风格（`outline-wiki-upload/references/doc_style.md`）—— 写时参考
  - 风格 checklist（`outline-wiki-upload/references/style_checklist.md`）—— 写时核对
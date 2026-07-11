---
name: yzr-llm-workspace-management
description: |
  用本 skill 管理由 yzr-llm-wiki-management 维护的多个本地 wiki：在 workspace 层级扫描所有 wiki、
  生成与维护全局 INDEX.md / STATS.md / LINT.md，做跨 wiki 综合问答（路由 / 合成 / 对比 / 局部），
  维护跨 wiki 交叉引用，做 workspace 级 lint，沉淀跨 wiki agent 私有记忆到 MEMORY/。
  触发场景："总结我所有 wiki 中关于 X 的内容"、"对比 wiki A 和 wiki B 对 Y 的看法"、
  "这个问题该查哪个 wiki"、"扫一下我的 workspace"、"workspace 整体 lint"、
  "记一下：用户偏好按时间线分 wiki"。弥补 workspace CLI 只能管元数据不能感知内容的缺陷——
  CLI 负责确定性操作（init / add / remove / config / enter / model 注册），本 skill
  负责需要 LLM 判断的跨 wiki 决策。不适用：单 wiki 的 ingest / query / lint（走
  yzr-llm-wiki-management）；workspace / wiki 元数据 CRUD（走 workspace CLI 如 llmw）；
  云端协作 wiki（走 outline-wiki-{search,upload,setup}）。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-07-08
  workspace_spec_version: 0.6.1
---

# LLM Workspace Management

按 [`workspace-spec.md`](references/workspace-spec.md) 维护一个**本地**、**多 wiki**
工作区的"全局视图"和跨 wiki 编排能力——单个 wiki 的 ingest / query / lint 仍走
`yzr-llm-wiki-management` SKILL.md skill。本 skill 站在所有 wiki
之上，做需要跨 wiki 判断的事情。

本 skill 提供三块交付物：

- **SKILL.md（本文）**——工作流 + 边界的"宪法"
- **references/workspace-spec.md**——workspace 根 9 类文件的归属 + schema 权威定义
  （CLI 与 skill 都按它落盘 / 维护）
- **scripts/**——把高频 deterministic 任务固化下来（**不**含 `init`——workspace 的
  init 由 workspace CLI 负责）

## 何时使用 / 不使用

### 使用

- 用户在对话中说"总结我所有 wiki 中关于 X 的内容" / "跨 wiki 查一下 X"
- 用户在对话中说"对比 wiki A 和 wiki B 对 Y 的看法"
- 用户在对话中说"这个问题属于哪个 wiki" / "X 应该放到哪个 wiki"
- 用户在对话中说"扫一下 workspace" / "更新 INDEX.md" / "刷新全局视图"
- 用户在对话中说"workspace 整体 lint" / "workspace 健康检查"
- 用户在对话中说"wiki A 的某 entity 在 wiki B 也存在，加跨 wiki 链接"
- 用户指向 `<workspace>/INDEX.md` 或 `<workspace>/STATS.md` 说"这个该更新了"
- 用户首次提到"我有多个 wiki / workspace / 跨 wiki 视角"

### 不使用

- **单个 wiki 的 ingest / query / lint**——走 `yzr-llm-wiki-management` SKILL.md
- **workspace / wiki 元数据 CRUD**（init / add / remove / config / enter / model
  add / remove / set-default）——走 workspace CLI（如 `llmw`）
- **云端协作 wiki**（Notion / Confluence / Outline Wiki / GitHub Wiki）——走
  `yzr-outline-wiki-upload`（写 / 编辑）/ `yzr-outline-wiki-search`（搜 / 读）
- **一次性文档生成**——直接用普通文件写入流程
- **单 wiki 内的 cross-page Q&A**——走 `yzr-llm-wiki-management` 的 query 工作流

## 输入 / 输出

### 启动时需具备的信息

| 信息 | 来源 | 备注 |
| --- | --- | --- |
| Workspace 路径 | `$LLMW_WORKSPACE` 环境变量，或默认 `~/yzr_llm_wiki_workspace`，或交互时问 | workspace CLI 通常在 `enter` 时设好本变量 |
| 操作类型 | 用户自然语言 | `scan` / `query` / `link` / `lint` |
| Query 范围（仅 query） | 用户自然语言或显式指定 wiki 名 | 不指定走全局 INDEX 路由 |

### 操作产物

- **scan** → 写 `<workspace>/INDEX.md`（人类可读概览）+ `<workspace>/STATS.md`（结构化统计），
  按 [spec §4 / §5](references/workspace-spec.md) 落盘
- **query** → 对话中给出答案（带每 wiki 引用）；可选落 `<workspace>/cross_queries/<slug>.md`
  （需用户确认后归档；格式见 [spec §7](references/workspace-spec.md#7-cross_queriesskill-维护可选)）
- **link** → 在涉及跨 wiki 引用的 wiki 各自的 source / entity 页追加跨 wiki 链接（走
  `yzr-llm-wiki-management` 的 ingest 流程，不直接写 wiki 文件）
- **lint** → 写 `<workspace>/LINT.md`（最近一次报告，每次 lint 覆盖；格式见
  [spec §8](references/workspace-spec.md#8-lintmdskill-维护可选)）+ 对话中总结

## 执行原则 / 边界

### 三层职责切分

```text
┌─────────────────────────────────────────────────────────────────┐
│ workspace CLI (如 llmw)                                          │
│   - 确定性元数据操作：init / add / remove / config / enter        │
│   - 写 workspace.toml / workspace_models.toml / .gitignore       │
│   - init 时按模板拷 AGENTS.md(SSOT)+CLAUDE.md(薄壳)            │
│   - 写 <wiki>/wiki_metadata.toml + wiki 仓骨架（按 wiki-spec）   │
│   - init 建 MEMORY/ + 写 MEMORY.md 索引（§9）                    │
│   - 不读不写 INDEX/STATS/LINT/cross_queries + MEMORY/*.md 经验   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ 元数据 / 启动 session
                              │
┌─────────────────────────────────────────────────────────────────┐
│ yzr-llm-workspace-management (本 skill)                              │
│   - 跨 wiki 编排：scan / query (4 模式) / link / lint / memory   │
│   - 写 INDEX/STATS/LINT/cross_queries + MEMORY/*.md（同步索引）  │
│   - 写 <wiki>/wiki/** （通过 yzr-llm-wiki-management 委托）           │
│   - 不写 workspace.toml / workspace_models.toml / .gitignore      │
│   - 不写 <workspace>/AGENTS.md / CLAUDE.md（用户 schema）        │
│   - 不写 <wiki>/raw/                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 单 wiki 内容操作
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ yzr-llm-wiki-management                                              │
│   - 单 wiki ingest / query / lint / memory                       │
│   - 写 <wiki>/wiki/{entities,concepts,sources,...}                │
│   - 不写 <wiki>/AGENTS.md（用户所有）                              │
│   - 不写 <wiki>/raw/                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 与 workspace CLI 的边界

**本 skill 不调 workspace CLI**。原因：

1. workspace CLI 只读 / 写三份元数据 + 启动 session——本 skill 读 workspace.toml /
   wiki_metadata.toml **直接读**比解析 CLI 输出更可靠（CLI 输出是给人看的，文本可能改）
2. 本 skill 不修改 workspace.toml / wiki_metadata.toml——告诉用户跑 `llmw wiki ...`，
   人类执行。CLI 的元数据写入是用户驱动的决策，skill 不越权
3. workspace CLI 已通过 `wiki enter` 把 session 启动好（包含 model overlay）；
   本 skill 在 session 内只做内容层决策，不需要再 `enter`
4. **依赖单向 DAG**：本 skill → workspace-spec.md（权威契约）；workspace CLI →
   workspace-spec.md；本 skill **不**直接依赖 workspace CLI 的代码或二进制

### 与 yzr-llm-wiki-management 的边界

**本 skill 委托单 wiki 操作给 `yzr-llm-wiki-management`**。场景：

| 场景 | 委托方式 |
| --- | --- |
| 在某 wiki 内 ingest 新资料 | 转交 `yzr-llm-wiki-management` 的 ingest 流程 |
| 在某 wiki 内 query | 转交 `yzr-llm-wiki-management` 的 query 流程 |
| 在某 wiki 内 lint | 转交 `yzr-llm-wiki-management` 的 lint 流程 |
| 写跨 wiki 链接到某 wiki 的 source 页 | 走 `yzr-llm-wiki-management` 的 ingest 更新 |

**本 skill 自己在 workspace 层做的**：scan (聚合) / route (路由) / cross-wiki
synthesis / cross-wiki compare / cross-wiki link suggestion / workspace lint。

### 文件归属（不变量，强制）

| 文件 / 目录 | 维护方 | 本 skill 的态度 |
| --- | --- | --- |
| `<workspace>/workspace.toml` | workspace CLI | 只读 |
| `<workspace>/workspace_models.toml` | workspace CLI | 只读（甚至不读；不感知 model 配置） |
| `<workspace>/.gitignore` | workspace CLI | 只读 |
| `<workspace>/AGENTS.md`（SSOT） | 用户（CLI init 时拷 SSOT 模板） | 只读（schema 宪法；改前先与用户确认）；**作用域 = 跨 wiki**，wiki 子目录内不加载（见"加载作用域边界"小节） |
| `<workspace>/CLAUDE.md`（薄壳） | 用户（CLI init 时拷薄壳模板） | 只读；**作用域 = 跨 wiki**，wiki 子目录内不加载（同上） |
| `<workspace>/INDEX.md` | 本 skill | 写 |
| `<workspace>/STATS.md` | 本 skill | 写 |
| `<workspace>/cross_queries/` | 本 skill | 写 |
| `<workspace>/LINT.md` | 本 skill | 写 |
| `<workspace>/MEMORY/` | CLI init 建骨架（目录 + MEMORY.md）+ 本 skill | CLI init 写 MEMORY.md 索引；skill 写 `*.md` 经验 + 同步索引 |
| `<wiki>/wiki_metadata.toml` | workspace CLI | 只读 |
| `<wiki>/wiki/{entities,concepts,sources,...}` | `yzr-llm-wiki-management` | 通过它写 |
| `<wiki>/wiki/MEMORY/` | `yzr-llm-wiki-management` | 通过它写（单 wiki 私有记忆） |
| `<wiki>/AGENTS.md`（SSOT） | 用户（CLI init 时拷 SSOT 模板） | 只读 |
| `<wiki>/CLAUDE.md`（薄壳） | 用户（CLI init 时拷薄壳模板） | 只读 |
| `<wiki>/raw/` | 用户 | 只读 |

完整归属表见 [spec §1](references/workspace-spec.md#1-目录结构)。**违反归属 = bug**：
本 skill 写 `workspace.toml` 属越权；CLI 写 `INDEX.md` 属越权；skill 写
`<workspace>/AGENTS.md` / `CLAUDE.md` 属越权（用户宪法）。**MEMORY 跨边界混淆**：本 skill **禁止**写
`<wiki>/wiki/MEMORY/`，单 wiki 记忆归 `yzr-llm-wiki-management`；同样禁止把跨 wiki 观察
写到单 wiki MEMORY——按 [spec §9 scope 边界](references/workspace-spec.md#9-workspace-memoryskill-维护)。

### 跨 skill 依赖图（DAG，无环）

```text
yzr-llm-workspace-management (本 skill)
  ├─→ references/workspace-spec.md (本 skill 自有)
  ├─→ references/wiki-spec.md (经 yzr-llm-wiki-management SKILL 仓引用)
  └─→ yzr-llm-wiki-management (运行时委托)

workspace CLI (llmw)
  ├─→ references/workspace-spec.md
  └─→ references/wiki-spec.md

yzr-llm-wiki-management
  └─→ references/wiki-spec.md (本 skill 自有)
```

本 skill 不直接调 workspace CLI；workspace CLI 也不依赖本 skill。两边都通过
spec 文件做契约对齐。

## 工作流 / 步骤

### 0. 启动检查

每次进入本 skill 时：

1. 定位 workspace 路径：`$LLMW_WORKSPACE` → 默认 `~/yzr_llm_wiki_workspace` → 交互问
2. 验证 `<workspace>/workspace.toml` 存在——不存在提示用户 "workspace 还没 init，
   跑 `llmw init` 初始化"（**不**替用户跑）
3. **加载跨 wiki MEMORY 索引**：在 workspace 根目录工作时——Claude Code 经薄壳 `<workspace>/CLAUDE.md`
   → `@AGENTS.md` 自动加载 SSOT，`@MEMORY/MEMORY.md` 已把索引内联会话常驻；读 `AGENTS.md` 的其他 agent
   （Qoder / Codex / Gemini CLI 等）原生读 SSOT；非根目录工作时（skill 经 `$LLMW_WORKSPACE`
   读 AGENTS.md，`@` 不自动展开）→ 显式 `Read <$LLMW_WORKSPACE>/MEMORY/MEMORY.md` 补齐索引，
   知晓已有哪些跨 wiki 记忆
4. **加载作用域边界判定**（见下方"加载作用域边界"小节）——若当前 agent cwd 在某
   `<wiki>/` 子目录内、改跑 `yzr-llm-wiki-management`，本 skill 的纪律（含步骤 3 加载到的
   `<workspace>/AGENTS.md` 内容）**不**接管该 agent，改由 `<wiki>/AGENTS.md` 单 wiki 纪律生效
5. **不**自动跑 `scan`——等用户给操作意图

#### 加载作用域边界

`<workspace>/AGENTS.md` 与 `<workspace>/CLAUDE.md` 仅约束**跨 wiki 工作**
（workspace 根目录或外部 cwd 下调用 `yzr-llm-workspace-management`）。当 agent cwd 在
`<wiki>/` 或更深子目录、改调 `yzr-llm-wiki-management` 时，本 skill **不**自动加载
workspace 顶层 AGENTS.md / CLAUDE.md——避免与 `<wiki>/AGENTS.md` 单 wiki 纪律冲突，尤其
MEMORY scope 边界（workspace `MEMORY/` = 跨 wiki；`<wiki>/MEMORY/` = 单 wiki）、
log / ingest 写入归属（wiki 内 ingest 写 `<wiki>/wiki/` 与 `<wiki>/wiki/log.md`，
非 workspace 级 `INDEX.md` / `STATS.md`）。不同 agent 的 `@AGENTS.md` 级联行为各异
（Claude Code / Qoder / Codex / Gemini CLI），本 skill 不替具体 agent 实现判定，统一通过
**"在 wiki 子目录工作时 workspace skill 纪律不接管"**这条边界让 agent 自决；
`<workspace>/AGENTS.md` 模板顶部自含 scope 声明供级联方识别。

### 1. Scan / refresh-index

**触发**："扫一下 workspace" / "更新 INDEX.md" / 用户说"workspace 该刷新了"。

**流程**：

1. 读 `<workspace>/workspace.toml` 拿 `[wikis]` 注册表
2. 对每个 wiki：
   - 读 `<wiki>/wiki_metadata.toml`（CLI 维护，schema v2）
   - 读 `<wiki>/AGENTS.md` §0（拿主题名）+ §一（拿边界）
   - 读 `<wiki>/wiki/index.md`（已有内容 + 段落骨架）
   - 扫 `<wiki>/wiki/{entities,concepts,sources,comparisons,syntheses}/` 拿 page counts
   - 扫 `<wiki>/raw/` 递归拿原始资料数（仅 `find` + 计数，不读内容）
   - 读 `<wiki>/wiki/log.md` 末条拿 last activity
   - 读 `<wiki>/wiki/MEMORY/` 拿 memory files 数（仅文件名）
3. 读 `<workspace>/MEMORY/MEMORY.md` 索引（知晓已有跨 wiki 记忆，供 query 路由 / scan 报告
   引用）；按 wiki name 字母序聚合，写 `<workspace>/INDEX.md`（格式见
   [spec §4](references/workspace-spec.md#4-indexmdskill-维护)）+ `<workspace>/STATS.md`
   （格式见 [spec §5](references/workspace-spec.md#5-statsmdskill-维护)）
4. 原子写（POSIX `tmp + fsync + rename`）
5. 对话中报告："已刷新 INDEX.md / STATS.md，X 个 wiki，Y 个 page，Z 个原始资料"

**何时不做 scan**：用户只想做 query → 先用现有 INDEX.md；INDEX.md 缺失或过期超过 N 天
再提示先 scan。

**为何不调脚本**：v1 阶段聚合逻辑需要 LLM 判断"key entities"和"one-line summary"，
纯脚本搞不定。等沉淀稳定后可以拆出 `scripts/scan_workspace.py`（v2 TODO）。

### 2. Query（跨 wiki Q&A）

**触发**："总结我所有 wiki 中关于 X 的内容" / "对比 A 和 B 对 Y" / "X 该查哪个 wiki"。

**4 种模式**（按用户意图 + 是否指定 wiki 范围自动判定）：

| 模式 | 触发关键词 | 流程 |
| --- | --- | --- |
| **route** | "应该查哪个 wiki" / "属于哪个 wiki" | 读 INDEX.md → 按 topic / tag / description 匹配 → 返回 1–3 个候选 wiki 名 + 理由 |
| **synthesis** | "总结所有" / "综合所有 wiki" / "跨 wiki 总结" | route → 每候选 wiki query → 合并 + 标注每 wiki 来源 |
| **compare** | "对比 A 和 B" / "A 和 B 的区别" | 读 wiki-A 与 wiki-B 的 `wiki/index.md` → query 双侧 → diff 风格对比 |
| **local** | "只看 wiki X" / "在 X 里查 Y" | 走 `yzr-llm-wiki-management` query（单 wiki） |

**判定规则**：

- 用户显式指定 1 个 wiki → **local**
- 用户显式指定 2 个 wiki 且带"对比 / 区别 / 异同" → **compare**
- 用户说"哪个 / 属于哪里 / 应该放哪" → **route**
- 其余 → **synthesis**

**good query 必有"是否归档"环节**——参考 `yzr-llm-wiki-management` query 流程 SKILL.md
的"是否归档"原则。归档位置：

- 答案涉及**单 wiki** → 归档到 `<wiki>/wiki/syntheses/<slug>.md`（走 `yzr-llm-wiki-management`）
- 答案涉及**多 wiki** → 归档到 `<workspace>/cross_queries/<slug>.md`（本 skill 直接写，
  格式见 [spec §7](references/workspace-spec.md#7-cross_queriesskill-维护可选)）

### 3. Link（跨 wiki 交叉引用）

**触发**："wiki A 里的 entity X 在 wiki B 也存在，加链接" / "扫一下跨 wiki 重复 entity"。

**流程**：

1. **扫描**：对每个 wiki 的 `wiki/entities/` + `wiki/concepts/`，提取所有 entity name
   （frontmatter `title` 或文件名 slug）
2. **去重聚合**：跨 wiki 同名 / 近义（用 description 比对）的 entity 收集为候选对
3. **建议**：对话中列出候选对，让用户选哪些要加跨 wiki 链接
4. **写入**：用户确认后，对每个涉及的 wiki，调用 `yzr-llm-wiki-management` 的 ingest
   流程更新对应 entity / concept 页——追加"跨 wiki 引用"段，引用路径用相对 workspace
   根（例 `[huawei_storage wiki 的 storage-architecture](../huawei_storage_wiki/wiki/concepts/storage-architecture.md)`）

**不变量**：本 skill **不直接**编辑 `<wiki>/wiki/**`——一律通过 `yzr-llm-wiki-management`
的 ingest 流程（保持 wiki 内的 log.md 同步、frontmatter 5 必填、不变量等）。

### 4. Lint（workspace 级）

**触发**："workspace lint" / "workspace 健康检查" / 定期（建议每 N 次 scan 后）。

**流程**：

1. **workspace 级 deterministic 检查**（agent 内联 / 后续拆脚本）：
   - 重复 entity 跨 wiki（同名 + 不同 slug 的对）
   - 失效跨 wiki 链接（cross_queries/*.md 的 `sources` 路径不存在；`<wiki>/wiki/**`
     中的 `../<another-wiki>/...` 路径不存在）
   - 未注册的 wiki 子目录（磁盘上有 `<wiki>/AGENTS.md` 但 workspace.toml 没有注册）
   - workspace.toml 注册但磁盘上不存在的 wiki（孤儿注册）
   - STATS.md 与 INDEX.md 的 wiki 列表是否一致
   - MEMORY 索引一致性：扫 `<workspace>/MEMORY/*.md`（排除 `MEMORY.md`），任一文件未在
     `MEMORY/MEMORY.md` 索引列出 → 报 `memory-not-indexed`（severity = info，与 wiki 侧
     lint-checklist §14 对齐）
2. **本 skill 做的半定性检查**：
   - 主题重叠的 wiki 是否需要合并
   - tag 体系是否混乱（同名 tag 含义不同 / 同含义 tag 命名不一）
3. **本 skill 不做的**：单 wiki 内部 lint（重复 entity / 缺 frontmatter / 矛盾主张等）
   ——转交 `yzr-llm-wiki-management`
4. **输出**：写 `<workspace>/LINT.md`（格式见
   [spec §8](references/workspace-spec.md#8-lintmdskill-维护可选)）+ 对话中报告

**何时不做 lint**：用户只问 query → 不 lint；用户说"扫一下" → scan 而非 lint。

### 5. Memory（跨 wiki agent 私有记忆）

**触发**：在 scan / query / link / lint 过程中识别到**跨 wiki**值得沉淀的信息时主动写。
**严格 scope 边界**（参考 [spec §9.3](references/workspace-spec.md#93-何时写--不写)）：

**写**（跨 wiki 视角）：

- 跨 wiki 关联——"X 类主题放 A wiki，Y 类放 B wiki"
- 用户对 workspace 组织的偏好——"我更喜欢按时间线而非主题分 wiki"
- workspace-wide lint 模式——"最近 N 次 lint 都报某类问题"
- 跨 wiki 综合经验——"这类问题需要先 scan 再答"

**不写**（避免越界）：

- 单 wiki 踩坑 → 归 `<wiki>/wiki/MEMORY/`（委托 `yzr-llm-wiki-management`）
- 跨 wiki 综合答案本身 → 归 `<workspace>/cross_queries/`
- 一次性观察 → 直接 chat，不写 MEMORY

**流程**：

1. 识别一个值得沉淀的跨 wiki 观察
2. **scope 自检**——确认是跨 wiki 视角（不只涉及单个 wiki）
3. **判别条目形式**（与仓库根 `MEMORY/` / wiki 侧 MEMORY 同步）：
   - **完整条目**——需要解释"为什么这么做"或"将来怎么用"（含上下文 / 解决步骤 / 未来如何避免）→
     走步骤 4-7 完整格式
   - **短条目**——纯 reminder / 单一偏好 / 无需 why + how → 直接跳到步骤 6 短格式
4. 生成 slug（kebab-case 短标题，例 `user-prefers-time-based-wikis`）——仅完整条目需要
5. 检查目标 MEMORY 文件是否已存在（仅完整条目）：
   - 不存在 → `Write` 新文件（5 必填 frontmatter：`title` / `type`（用 `workspace-memory`） /
     `created` / `updated` / `tags`；推荐 `wikis` 数组 + `description`）
   - 已存在 → `Edit` 更新正文 + `updated` 字段，`created` 保留原值
6. **同步 `MEMORY.md` 索引一行**——格式按条目形式选：
   - 完整条目：`- <slug> — <一句话摘要> → [正文](<slug>.md)`（步骤 5 文件必须存在；
     漏写 = 下次读不到，lint `memory-not-indexed` 兜底）
   - 短条目：`- <一句话事实>`（无链接、无对应 .md 文件；索引被 AGENTS.md `@` import
     常驻即可达未来会话）
7. **不要**追加 `INDEX.md`（MEMORY 是 agent 私有入口，不进 workspace 单一入口；但**必须**在
   `MEMORY.md` 索引列出，见上一步）
8. **不写** log.md（MEMORY 没有 workspace-level log）

**MEMORY 骨架不由 skill 建**：`<workspace>/MEMORY/` 目录 + `MEMORY.md` 索引由 **CLI init** 创建
（[spec §9](references/workspace-spec.md#9-workspace-memoryskill-维护) §9.1）；skill 不重建（已存在即
跳过），只在写跨 wiki 经验时追加 `*.md` + 同步索引。

**MEMORY 与单 wiki MEMORY 的清晰边界**：

| 场景 | 写哪 |
| --- | --- |
| "wiki A 的 ingest 总是失败，因为 raw/ 里有特殊字符" | `<A>/wiki/MEMORY/ingest-special-char-pitfall.md`（单 wiki 经验） |
| "用户偏好把所有 storage 相关放 A wiki，把 LLM 相关放 B wiki" | `<workspace>/MEMORY/user-storage-vs-llm-preference.md`（跨 wiki 偏好） |
| "跨 wiki 综合答案：对比 A 与 B 的性能优化方法" | `<workspace>/cross_queries/perf-compare-a-b.md`（答案本身，不是 memory） |

## 参考样例

### 样例 1：跨 wiki 综合问答

> 用户："我所有 wiki 中关于 RAID 有什么记录？"

1. skill 读 `<workspace>/INDEX.md` → 找到 `huawei_storage_wiki` 的描述含"存储"
2. mode = **synthesis**（用户说"所有 wiki 中"）
3. 转交 `yzr-llm-wiki-management` 给 `huawei_storage_wiki` 做 query："RAID"
4. 拿到答案（带 source 页引用），对话中给用户，附"只涉及 1 个 wiki，是否归档到
   `huawei_storage_wiki/wiki/syntheses/raid-overview.md`？"
5. 用户确认 → 走 `yzr-llm-wiki-management` 写 synthesis 页 + log 条目

### 样例 2：跨 wiki 对比

> 用户："`huawei_storage_wiki` 和 `test` wiki 在性能优化上有什么不同？"

1. skill 读 INDEX.md → 两个 wiki 都在
2. mode = **compare**（两个 wiki + "不同"）
3. 分别转交 `yzr-llm-wiki-management` 给两个 wiki query："性能优化"
4. 对比两份答案，按主题维度 diff（共识 / 分歧 / 一方独有）
5. 询问是否归档为 `<workspace>/cross_queries/storage-vs-test-perf.md`（用户确认后写）

### 样例 3：路由

> 用户："我刚下了一篇 LLM inference 论文，应该放哪个 wiki？"

1. skill 读 INDEX.md + 读每个 wiki 的 description / tags
2. mode = **route**
3. 返回："`huawei_storage_wiki` 主题是存储，不相关；`test` wiki 主题是 test，也不相关；
   建议新建一个 wiki（`llmw wiki --name=llm-inference add ...`）"
4. **不**自动跑 `llmw wiki add`——告诉用户跑 CLI 命令

### 样例 4：scan 触发

> 用户："扫一下我的 workspace"

1. 读 workspace.toml → 2 个 wiki
2. 读每个 wiki 的 metadata + index.md + log.md 末条 + page counts
3. 写 `<workspace>/INDEX.md`（首次创建；非首次覆盖）
4. 写 `<workspace>/STATS.md`（同上）
5. 对话报告："已刷新 INDEX.md / STATS.md——2 wikis，0 pages 全部，2 raw files 全部"

## 参考文件

- **必读**：[`references/workspace-spec.md`](references/workspace-spec.md)——workspace 根
  9 类文件的归属 + schema 权威定义（含 §4 AGENTS.md / CLAUDE.md + §9 MEMORY/）
- **必读**：[`references/workspace-agents-md-template.md`](references/workspace-agents-md-template.md)——
  `<workspace>/AGENTS.md`（SSOT）的 canonical 模板字节金标准（CLI init 时按此拷）；薄壳 `<workspace>/CLAUDE.md`
  见 [`workspace-claude-md-template.md`](references/workspace-claude-md-template.md)
- **必读**：`yzr-llm-wiki-management` SKILL.md 的 `references/wiki-spec.md`——
  单 wiki 内的目录 / frontmatter / 命名约束（本 skill 操作 wiki 时遵循）
- **委托目标**：`yzr-llm-wiki-management` SKILL.md——
  单 wiki ingest / query / lint / memory 工作流（本 skill 的单 wiki 操作委托给它）
- **CLI 文档**：workspace CLI 仓（命令 `llmw`，仓路径由用户在外部维护）——本 skill
  **不直接调**，但用户的 `init / add / remove / config / enter / model ...` 命令参考此处

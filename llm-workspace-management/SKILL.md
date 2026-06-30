---
name: llm-workspace-management
description: |
  用本 skill 管理由 llm-wiki-management 维护的多个本地 wiki：在 workspace 层级扫描所有 wiki、
  生成与维护全局 INDEX.md 与 STATS.md，做跨 wiki 综合问答（路由 / 合成 / 对比 / 局部），
  维护跨 wiki 交叉引用，做 workspace 级 lint。触发场景："总结我所有 wiki 中关于 X 的内容"、
  "对比 wiki A 和 wiki B 对 Y 的看法"、"这个问题该查哪个 wiki"、"扫一下我的 workspace"、
  "workspace 整体 lint"。弥补 workspace CLI 只能管元数据不能感知内容的缺陷——CLI
  负责确定性操作（init / add / remove / config / enter / model 注册），本 skill
  负责需要 LLM 判断的跨 wiki 决策。不适用：单 wiki 的 ingest / query / lint（走
  llm-wiki-management）；workspace / wiki 元数据 CRUD（走 workspace CLI 如 llmw）；
  云端协作 wiki（走 outline-wiki-{search,upload,setup}）。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-30
  workspace_spec_version: 0.1.0
---

# LLM Workspace Management

按 [`workspace-spec.md`](references/workspace-spec.md) 维护一个**本地**、**多 wiki**
工作区的"全局视图"和跨 wiki 编排能力——单个 wiki 的 ingest / query / lint 仍走
[`llm-wiki-management`](../llm-wiki-management/SKILL.md) skill。本 skill 站在所有 wiki
之上，做需要跨 wiki 判断的事情。

本 skill 提供三块交付物：

- **SKILL.md（本文）**——工作流 + 边界的"宪法"
- **references/workspace-spec.md**——workspace 根 6 类文件的归属 + schema 权威定义
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

- **单个 wiki 的 ingest / query / lint**——走 [`llm-wiki-management`](../llm-wiki-management/SKILL.md)
- **workspace / wiki 元数据 CRUD**（init / add / remove / config / enter / model
  add / remove / set-default）——走 workspace CLI（如 `llmw`）
- **云端协作 wiki**（Notion / Confluence / Outline Wiki / GitHub Wiki）——走
  `outline-wiki-upload`（写 / 编辑）/ `outline-wiki-search`（搜 / 读）
- **一次性文档生成**——直接用普通文件写入流程
- **单 wiki 内的 cross-page Q&A**——走 `llm-wiki-management` 的 query 工作流

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
  （需用户确认后归档；格式见 [spec §6](references/workspace-spec.md#6-cross_queriesskill-维护可选)）
- **link** → 在涉及跨 wiki 引用的 wiki 各自的 source / entity 页追加跨 wiki 链接（走
  `llm-wiki-management` 的 ingest 流程，不直接写 wiki 文件）
- **lint** → 写 `<workspace>/LINT.md`（最近一次报告，每次 lint 覆盖；格式见
  [spec §7](references/workspace-spec.md#7-lintmdskill-维护可选)）+ 对话中总结

## 执行原则 / 边界

### 三层职责切分

```
┌─────────────────────────────────────────────────────────────────┐
│ workspace CLI (如 llmw)                                          │
│   - 确定性元数据操作：init / add / remove / config / enter        │
│   - 写 workspace.toml / workspace_models.toml / .gitignore       │
│   - 写 <wiki>/wiki_metadata.toml + wiki 仓骨架（按 wiki-spec）   │
│   - 不读不写 INDEX.md / STATS.md / LINT.md / cross_queries/      │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ 元数据 / 启动 session
                              │
┌─────────────────────────────────────────────────────────────────┐
│ llm-workspace-management (本 skill)                              │
│   - 跨 wiki 编排：scan / query (4 模式) / link / lint            │
│   - 写 INDEX.md / STATS.md / LINT.md / cross_queries/             │
│   - 写 <wiki>/wiki/** （通过 llm-wiki-management 委托）           │
│   - 不写 workspace.toml / workspace_models.toml / .gitignore      │
│   - 不写 <wiki>/raw/                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 单 wiki 内容操作
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ llm-wiki-management                                              │
│   - 单 wiki ingest / query / lint / memory                       │
│   - 写 <wiki>/wiki/{entities,concepts,sources,...}                │
│   - 不写 <wiki>/CLAUDE.md（用户所有）                              │
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

### 与 llm-wiki-management 的边界

**本 skill 委托单 wiki 操作给 `llm-wiki-management`**。场景：

| 场景 | 委托方式 |
| --- | --- |
| 在某 wiki 内 ingest 新资料 | 转交 `llm-wiki-management` 的 ingest 流程 |
| 在某 wiki 内 query | 转交 `llm-wiki-management` 的 query 流程 |
| 在某 wiki 内 lint | 转交 `llm-wiki-management` 的 lint 流程 |
| 写跨 wiki 链接到某 wiki 的 source 页 | 走 `llm-wiki-management` 的 ingest 更新 |

**本 skill 自己在 workspace 层做的**：scan (聚合) / route (路由) / cross-wiki
synthesis / cross-wiki compare / cross-wiki link suggestion / workspace lint。

### 文件归属（不变量，强制）

| 文件 / 目录 | 维护方 | 本 skill 的态度 |
| --- | --- | --- |
| `<workspace>/workspace.toml` | workspace CLI | 只读 |
| `<workspace>/workspace_models.toml` | workspace CLI | 只读（甚至不读；不感知 model 配置） |
| `<workspace>/.gitignore` | workspace CLI | 只读 |
| `<workspace>/INDEX.md` | 本 skill | 写 |
| `<workspace>/STATS.md` | 本 skill | 写 |
| `<workspace>/cross_queries/` | 本 skill | 写 |
| `<workspace>/LINT.md` | 本 skill | 写 |
| `<wiki>/wiki_metadata.toml` | workspace CLI | 只读 |
| `<wiki>/wiki/{entities,concepts,sources,...}` | `llm-wiki-management` | 通过它写 |
| `<wiki>/CLAUDE.md` | 用户（CLI init 时拷模板） | 只读 |
| `<wiki>/raw/` | 用户 | 只读 |

完整归属表见 [spec §1](references/workspace-spec.md#1-目录结构)。**违反归属 = bug**：
本 skill 写 `workspace.toml` 属越权；CLI 写 `INDEX.md` 属越权。

### 跨 skill 依赖图（DAG，无环）

```
llm-workspace-management (本 skill)
  ├─→ references/workspace-spec.md (本 skill 自有)
  ├─→ references/wiki-spec.md (经 llm-wiki-management SKILL 仓引用)
  └─→ llm-wiki-management (运行时委托)

workspace CLI (llmw)
  ├─→ references/workspace-spec.md
  └─→ references/wiki-spec.md

llm-wiki-management
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
3. **不**自动跑 `scan`——等用户给操作意图

### 1. Scan / refresh-index

**触发**："扫一下 workspace" / "更新 INDEX.md" / 用户说"workspace 该刷新了"。

**流程**：

1. 读 `<workspace>/workspace.toml` 拿 `[wikis]` 注册表
2. 对每个 wiki：
   - 读 `<wiki>/wiki_metadata.toml`（CLI 维护，schema v2）
   - 读 `<wiki>/CLAUDE.md` §0（拿主题名）+ §一（拿边界）
   - 读 `<wiki>/wiki/index.md`（已有内容 + 段落骨架）
   - 扫 `<wiki>/wiki/{entities,concepts,sources,comparisons,syntheses}/` 拿 page counts
   - 扫 `<wiki>/raw/` 递归拿原始资料数（仅 `find` + 计数，不读内容）
   - 读 `<wiki>/wiki/log.md` 末条拿 last activity
   - 读 `<wiki>/wiki/MEMORY/` 拿 memory files 数（仅文件名）
3. 按 wiki name 字母序聚合，写 `<workspace>/INDEX.md`（格式见
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
| **synthesis** | "总结所有" / "综合所有 wiki" / "跨 wiki 总结" | route → 对每个候选 wiki 走 `llm-wiki-management` query → 合并 + 标注每 wiki 来源 |
| **compare** | "对比 A 和 B" / "A 和 B 的区别" | 读 wiki-A 与 wiki-B 的 `wiki/index.md` → 走 `llm-wiki-management` query 双侧 → diff 风格对比 |
| **local** | "只看 wiki X" / "在 X 里查 Y" | 走 `llm-wiki-management` query（单 wiki） |

**判定规则**：

- 用户显式指定 1 个 wiki → **local**
- 用户显式指定 2 个 wiki 且带"对比 / 区别 / 异同" → **compare**
- 用户说"哪个 / 属于哪里 / 应该放哪" → **route**
- 其余 → **synthesis**

**good query 必有"是否归档"环节**——参考 [`llm-wiki-management` query 流程](../llm-wiki-management/SKILL.md)
的"是否归档"原则。归档位置：

- 答案涉及**单 wiki** → 归档到 `<wiki>/wiki/syntheses/<slug>.md`（走 `llm-wiki-management`）
- 答案涉及**多 wiki** → 归档到 `<workspace>/cross_queries/<slug>.md`（本 skill 直接写，
  格式见 [spec §6](references/workspace-spec.md#6-cross_queriesskill-维护可选)）

### 3. Link（跨 wiki 交叉引用）

**触发**："wiki A 里的 entity X 在 wiki B 也存在，加链接" / "扫一下跨 wiki 重复 entity"。

**流程**：

1. **扫描**：对每个 wiki 的 `wiki/entities/` + `wiki/concepts/`，提取所有 entity name
   （frontmatter `title` 或文件名 slug）
2. **去重聚合**：跨 wiki 同名 / 近义（用 description 比对）的 entity 收集为候选对
3. **建议**：对话中列出候选对，让用户选哪些要加跨 wiki 链接
4. **写入**：用户确认后，对每个涉及的 wiki，调用 `llm-wiki-management` 的 ingest
   流程更新对应 entity / concept 页——追加"跨 wiki 引用"段，引用路径用相对 workspace
   根（例 `[huawei_storage wiki 的 storage-architecture](../huawei_storage_wiki/wiki/concepts/storage-architecture.md)`）

**不变量**：本 skill **不直接**编辑 `<wiki>/wiki/**`——一律通过 `llm-wiki-management`
的 ingest 流程（保持 wiki 内的 log.md 同步、frontmatter 5 必填、不变量等）。

### 4. Lint（workspace 级）

**触发**："workspace lint" / "workspace 健康检查" / 定期（建议每 N 次 scan 后）。

**流程**：

1. **workspace 级 deterministic 检查**（agent 内联 / 后续拆脚本）：
   - 重复 entity 跨 wiki（同名 + 不同 slug 的对）
   - 失效跨 wiki 链接（cross_queries/*.md 的 `sources` 路径不存在；`<wiki>/wiki/**`
     中的 `../<another-wiki>/...` 路径不存在）
   - 未注册的 wiki 子目录（磁盘上有 `<dir>/CLAUDE.md` 但 workspace.toml 没有注册）
   - workspace.toml 注册但磁盘上不存在的 wiki（孤儿注册）
   - STATS.md 与 INDEX.md 的 wiki 列表是否一致
2. **本 skill 做的半定性检查**：
   - 主题重叠的 wiki 是否需要合并
   - tag 体系是否混乱（同名 tag 含义不同 / 同含义 tag 命名不一）
3. **本 skill 不做的**：单 wiki 内部 lint（重复 entity / 缺 frontmatter / 矛盾主张等）
   ——转交 `llm-wiki-management`
4. **输出**：写 `<workspace>/LINT.md`（格式见
   [spec §7](references/workspace-spec.md#7-lintmdskill-维护可选)）+ 对话中报告

**何时不做 lint**：用户只问 query → 不 lint；用户说"扫一下" → scan 而非 lint。

## 参考样例

### 样例 1：跨 wiki 综合问答

> 用户："我所有 wiki 中关于 RAID 有什么记录？"

1. skill 读 `<workspace>/INDEX.md` → 找到 `huawei_storage_wiki` 的描述含"存储"
2. mode = **synthesis**（用户说"所有 wiki 中"）
3. 转交 `llm-wiki-management` 给 `huawei_storage_wiki` 做 query："RAID"
4. 拿到答案（带 source 页引用），对话中给用户，附"只涉及 1 个 wiki，是否归档到
   `huawei_storage_wiki/wiki/syntheses/raid-overview.md`？"
5. 用户确认 → 走 `llm-wiki-management` 写 synthesis 页 + log 条目

### 样例 2：跨 wiki 对比

> 用户："`huawei_storage_wiki` 和 `test` wiki 在性能优化上有什么不同？"

1. skill 读 INDEX.md → 两个 wiki 都在
2. mode = **compare**（两个 wiki + "不同"）
3. 分别转交 `llm-wiki-management` 给两个 wiki query："性能优化"
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
  6 类文件的归属 + schema 权威定义
- **必读**：[`../llm-wiki-management/references/wiki-spec.md`](../llm-wiki-management/references/wiki-spec.md)——
  单 wiki 内的目录 / frontmatter / 命名约束（本 skill 操作 wiki 时遵循）
- **委托目标**：[`../llm-wiki-management/SKILL.md`](../llm-wiki-management/SKILL.md)——
  单 wiki ingest / query / lint 工作流（本 skill 的单 wiki 操作委托给它）
- **CLI 文档**：workspace CLI 仓（当前为 `~/llm_workspace_cli/`，命令 `llmw`）——本 skill
  **不直接调**，但用户的 `init / add / remove / config / enter / model ...` 命令参考此处
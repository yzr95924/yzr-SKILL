# Workspace Spec（workspace CLI 实现契约）

> 本文档是 **workspace CLI**（如 `llmw`）生成 workspace 仓时的实现契约，同时也是
> [`yzr-llm-workspace-management`](../SKILL.md) skill 操作 workspace 的权威 schema 参考。
> CLI 必须按本文档落盘骨架；skill 必须按本文档约定的归属关系维护内容。
>
> **依赖方向**：`workspace CLI → 本 spec`（CLI 服从 spec；spec 不依赖 CLI 实现）；
> `yzr-llm-workspace-management → 本 spec`（skill 按 spec 操作）。
> 本 spec 变更 → CLI 与 skill 必须同步；CLI / skill 变更不影响本 spec。
>
> **生命周期归属**：本 spec 只规定 workspace 仓的"出生形态" + 持续维护期各文件的归属。
> workspace 出生后的所有成长（cross-wiki Q&A / xref / lint / 跨 wiki 编排 / 跨 wiki memory）
> 由 [`yzr-llm-workspace-management`](../SKILL.md) skill 在会话内负责。CLI 在 workspace
> 生命周期的两个边界点被调用：
>
> - **init**：创建（按本 spec §1–§4 + §10–§11 落盘）
> - **delete**：删除（带备份）
>
> 其他时刻调 CLI 属"误用"，CLI 应拒绝。

## 目录

- [§1 目录结构](#1-目录结构)
- [§2 workspace.toml](#2-workspacetoml)
- [§3 workspace_models.toml](#3-workspace_modelstoml)
- [§4 workspace AGENTS.md（SSOT）+ CLAUDE.md（薄壳）](#4-workspace-agentsmdssot-claudemd薄壳)
- [§5 INDEX.md（skill 维护）](#5-indexmdskill-维护)
- [§6 STATS.md（skill 维护）](#6-statsmdskill-维护)
- [§7 cross_queries/（skill 维护，可选）](#7-cross_queriesskill-维护可选)
- [§8 LINT.md（skill 维护，可选）](#8-lintmdskill-维护可选)
- [§9 workspace MEMORY/（skill 维护）](#9-workspace-memoryskill-维护)
- [§10 .gitignore](#10-gitignore)
- [§11 Git 仓（用户外部创建，CLI 不碰）](#11-git-仓用户外部创建cli-不碰)
- [§12 拒绝条件（强约束）](#12-拒绝条件强约束)
- [§13 Frontmatter 字段约定（skill 写 §5–§9 时用）](#13-frontmatter-字段约定skill-写-59-时用)
- [§14 版本钉死](#14-版本钉死)
- [§15 命名约束](#15-命名约束)
- [§16 不在本 spec 范围内](#16-不在本-spec-范围内)
- [§17 升级迁移（skill 维护）](#17-升级迁移skill-维护)
- [附录 A：CLI 实现自检建议](#附录-acli-实现自检建议)
- [附录 B：版本历史](#附录-b版本历史)

## §1 目录结构

```text
<workspace-root>/
├── .gitignore                      # CLI init 时写（§10）
├── workspace.toml                  # CLI init 时写（§2）
├── workspace_models.toml           # CLI init 时写（§3，gitignored）
├── AGENTS.md                       # CLI init 时按 §4 拷 SSOT 模板；用户所有（工具无关纪律）
├── CLAUDE.md                       # CLI init 时按 §4 拷薄壳模板（@AGENTS.md）；供经薄壳加载的 agent
├── INDEX.md                        # skill scan 时建 + 维护（§5）
├── STATS.md                        # skill scan 时建 + 维护（§6）
├── cross_queries/                  # skill 可选建（§7）
├── LINT.md                         # skill lint 时写（§8）
├── MEMORY/                         # CLI init 建空目录 + 写 MEMORY.md 索引（§9）
└── <wiki-name>/                    # 每个 wiki 一个子目录，遵循 wiki-spec §1 目录结构
```

**workspace 根的 9 类文件 / 目录各自归属**：

| 文件 / 目录 | init 时刻（CLI） | 后续维护方 | 说明 |
| --- | --- | --- | --- |
| `.gitignore` | CLI 写 | CLI（重 init 时覆盖；普通命令不碰） | 排除 `workspace_models.toml` 等敏感文件 |
| `workspace.toml` | CLI 写 | **CLI**（`wiki add / remove / config` 等命令） | wiki 注册表 + 全局默认；skill **不写**（迁移例外见 §17.2） |
| `workspace_models.toml` | CLI 写 | **CLI**（`model add / remove / set-default`） | 模型注册表（API key 等敏感信息）；skill **不写** |
| `AGENTS.md` | CLI 按 §4 拷 SSOT 模板 | **用户**（schema 是用户的宪法，工具无关 SSOT）；skill **只读**（迁移例外见 §17.2） | workspace 的"宪法"——三层职责切分 + 跨 wiki 约定 |
| `CLAUDE.md`（薄壳） | CLI 按 §4 拷薄壳模板（`@AGENTS.md`） | **用户**；skill **只读**（迁移例外见 §17.2） | 仅供经薄壳自动加载的 agent |
| `INDEX.md` | CLI **不写**（留空） | **skill**（scan / refresh-index） | workspace 全局入口文档 |
| `STATS.md` | CLI **不写**（留空） | **skill**（scan 时一并刷新） | workspace 结构化统计 |
| `cross_queries/` | CLI **不写**（留空目录） | **skill**（跨 wiki 综合答案归档） | 类比 wiki 内的 `syntheses/` |
| `LINT.md` | CLI **不写**（留空） | **skill**（lint 时写） | workspace 级 lint 报告（最近一次） |
| `MEMORY/` | CLI 写（init 建空目录 + 写 MEMORY.md 索引） | **skill**（写 `*.md` 经验 + 同步 MEMORY.md 索引） | 跨 wiki agent 私有记忆 |
| `<wiki-name>/` | CLI 写（按 wiki-spec §1 目录结构） | **CLI** 写元数据 + **skill**（或 `yzr-llm-wiki-management`）写内容 | 每个 wiki 是独立子仓 |

> **CLI 的写入范围限制（不变量）**：CLI 只写 `workspace.toml`、`workspace_models.toml`、
> `AGENTS.md`（SSOT 模板拷贝）+ `CLAUDE.md`（薄壳模板拷贝）、`.gitignore` 五份根级文件 + `MEMORY/`（init 建空目录 + 写
> `MEMORY.md` 索引占位，见 §9）+ `<wiki-name>/` 子树（按 wiki-spec）。
> **CLI 绝不写 `INDEX.md` / `STATS.md` / `LINT.md` / `cross_queries/` + `MEMORY/*.md` 经验条目**——
> 这些是 workspace skill 的领地。
>
> **skill 的写入范围限制（不变量）**：skill 只写 `INDEX.md` / `STATS.md` / `LINT.md` /
> `cross_queries/` 四份 workspace 级文件 + `MEMORY/*.md` 经验条目（并同步追加 `MEMORY.md`
> 索引一行；`MEMORY.md` 骨架由 CLI init 写）+ 各 `<wiki-name>/wiki/**`（通过
> `yzr-llm-wiki-management`）。**skill 绝不写 `workspace.toml` / `workspace_models.toml` /
> `.gitignore` / `AGENTS.md` / `CLAUDE.md`**——前 3 份是 CLI 的领地，最后两份是用户的宪法
> （**迁移例外**：spec 升级时按 §17.2 放开 4 处单点写入）。skill 也不写
> `<wiki-name>/raw/`（用户所有）。

## §2 workspace.toml

> **维护方**：CLI 在 init 时刻创建 + 后续 `wiki add / remove / config / model set-default` 等命令维护。
> skill **只读**——若需要修改元数据，告诉用户跑 CLI 命令，**人类执行**。

- 路径：`<workspace-root>/workspace.toml`
- 格式：TOML
- schema_version：`1`（当前）
- 字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | int | 是 | 当前为 `1` |
| `created_at` | string (ISO8601) | 是 | workspace 初始化时间，CLI 自动写 |
| `templates_version` | string | 是 | CLI 引用的 wiki-spec / workspace-spec 模板版本（钉死 spec 版本用） |
| `default_model` | string | 否 | 全局默认 model_id（指向 `workspace_models.toml` 中某条 `model_id`） |
| `[wikis.<name>]` | table | 是（可空 table） | 注册的 wiki 列表，每个含 `path` + `created_at` |

- `[wikis.<name>]` 子字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 是 | 相对 workspace 根的子目录名（与 `<name>` 相同的约定，见 §15） |
| `created_at` | string (ISO8601) | 是 | wiki 注册时间，CLI 自动写 |

- **CLI 写入场景**：`init` / `wiki add` / `wiki remove` / `wiki config set default_model`
  / `config set default_model` / `config unset default_model`
- **skill 写入场景**：**无**——只读

## §3 workspace_models.toml

> **维护方**：CLI 在 init 时刻创建空骨架 + 后续 `model add / remove / set-default / unset-default`
> 维护。skill **不读不写**——skill 做 cross-wiki Q&A 不需要感知具体 model 配置。

- 路径：`<workspace-root>/workspace_models.toml`
- 格式：TOML
- **必须 gitignored**（详见 §10）——含 API key 等敏感信息
- 落盘后 `chmod 600`（POSIX 系统；NFS 等不支持 chmod 的 FS best-effort 跳过）
- schema_version：`2`（当前）
- 字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | int | 是 | 当前为 `2` |
| `created_at` | string (ISO8601) | 是 | registry 创建时间，CLI 自动写 |
| `updated_at` | string (ISO8601) | 是 | 最近一次 `model add / remove / set-default` 的时间，CLI 自动 bump |
| `[[models]]` | array of table | 是（可空数组） | 模型条目 |

- `[[models]]` 子字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `model_id` | string | 是 | slug，CLI 内部引用用，**不是网关模型名**；命名约束见 §15 |
| `name` | string | 是 | 网关模型名（如 `claude-sonnet-4-6`），`wiki enter` 时用作 `ANTHROPIC_MODEL` |
| `base_url` | string | 是 | API base URL |
| `api_key` | string | 是 | API key；list / show / dry-run 输出走 redact（`前3...末4` 或 `***`） |
| `is_default` | bool | 否 | 全局至多 1 条 `true` |

- **CLI 写入场景**：`init` / `model add` / `model remove` / `model set-default` / `model unset-default`
- **skill 写入场景**：**无**——完全无关

## §4 workspace AGENTS.md（SSOT）+ CLAUDE.md（薄壳）

> **agent 中立设计**：workspace 纪律的**单一真源是 `AGENTS.md`**——工具无关。`CLAUDE.md`
> 收敛为薄壳（`@AGENTS.md` + 声明），仅供经薄壳自动加载的 agent 读到 SSOT。原生读 `AGENTS.md` 的
> 其他 agent 直读 SSOT，不依赖薄壳。改纪律请改 `AGENTS.md`，不要改 `CLAUDE.md` 薄壳。
>
> **维护方**：CLI 在 init 时刻按 [`workspace-agents-md-template.md`](workspace-agents-md-template.md)
> （SSOT）+ [`workspace-claude-md-template.md`](workspace-claude-md-template.md)（薄壳）拷两份模板生成。
> 后续修改由 **用户** 完成（AGENTS.md 是 workspace 的 schema，是用户的"宪法"）。
> LLM agent **不得编辑** AGENTS.md / CLAUDE.md；如需变更 schema，**先与用户确认**。
> **唯一例外**：spec 升级迁移时（§17），agent 经用户确认可全量重渲染两份文件。

### AGENTS.md（SSOT）

- 路径：`<workspace-root>/AGENTS.md`
- 内容来源：本仓 `references/workspace-agents-md-template.md`（**权威 canonical 模板**）
- CLI 实现时必须**逐字拷贝**该模板，仅做以下替换：
  - `{{WORKSPACE_DISPLAY_NAME}}` → workspace display name（默认取 `workspace.toml.created_at` 那天
    或人类指定字符串，如 `"LLM Wiki Workspace"`）
  - `{{SETUP_DATE}}` → 当天日期 `YYYY-MM-DD`
  - `{{WORKSPACE_SPEC_VERSION}}` → CLI 当前兼容的 workspace spec 版本号（如 `0.4.0`）
  - `{{CLI_VERSION}}` → CLI 自身版本号
- 4 个占位符全在 H1 + 模板 §六「当前配置」表（0.7.0+ 机读版本钉死，对齐 wiki-spec §八）；
  升级时的模板渲染字节比对见 §17.1
- 模板顶部说明块的"本文件 ... 按 workspace-spec.md §4 拷贝生成"反向引用，CLI **不得修改**
- **不带 frontmatter**——AGENTS.md 是 plain markdown；与 wiki-spec §2 的 `<wiki>/AGENTS.md` 一致

### CLAUDE.md（薄壳）

- 路径：`<workspace-root>/CLAUDE.md`
- 内容来源：本仓 `references/workspace-claude-md-template.md`（薄壳模板，`@AGENTS.md` + 声明，≤ 30 行）
- CLI 实现时**逐字拷贝**该模板，仅替换 `{{WORKSPACE_DISPLAY_NAME}}`（薄壳不持 spec 版本——版本在 AGENTS.md §六）
- 不含纪律正文、不含 `@MEMORY` import（那条在 AGENTS.md 内）；仅 `@AGENTS.md` 一行

### 共同约束

- **CLI 写入场景**：`init`（重 init 时若 `AGENTS.md` / `CLAUDE.md` 已存在，§12 拒绝覆盖）
- **skill 写入场景**：**无**——只读

## §5 INDEX.md（skill 维护）

> **维护方**：CLI 在 init 时刻**不创建**（留空）。skill 在 `scan` / `refresh-index` 时
> 创建 + 持续维护。skill 是 LLM 拥有的"workspace 入口文档"——人类只读。
> CLI 不参与 INDEX.md 的任何写入；skill 不依赖 CLI。

- 路径：`<workspace-root>/INDEX.md`
- frontmatter（**5 必填** + 推荐 `description`）：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 推荐 `"Workspace Index"` |
| `type` | enum | 是 | `workspace-index`（reserved，见 §13） |
| `tags` | array | 是 | 推荐 `[workspace, index]` |
| `created` | date (`YYYY-MM-DD`) | 是 | skill 首次创建时间 |
| `updated` | date (`YYYY-MM-DD`) | 是 | skill 每次刷新时更新为今天 |
| `description` | string | 否 | 一句话概述本 workspace 主题范围 |

- **正文骨架**：

  ```markdown
  # <Workspace Display Name> — Workspace Index

  > workspace 入口文档。每个 wiki 一节，按 wiki name 字母序；同字母序内按 `created_at` 升序。

  ## Wikis

  ### <wiki-name>

  - **display_name**: ...
  - **topic**: ...
  - **description**: ...
  - **tags**: [...]
  - **created**: YYYY-MM-DD
  - **last activity**: YYYY-MM-DD (log entry kind)
  - **page counts**: 0 entities / 0 concepts / 0 sources / 0 comparisons / 0 syntheses
  - **key entities**: [...]
  - **one-line summary**: ...

  ### <another-wiki>

  ... (同上)

  ## Cross-wiki Links

  - <wiki-a> ↔ <wiki-b>: <short description>

  ## Recent Activity (across all wikis)

  - YYYY-MM-DD: <event>
  ```

- **生成流程**（skill `scan`）：
  1. 读 `<workspace>/workspace.toml` 拿 `[wikis]` 注册表
  2. 对每个 wiki，读 `<wiki>/wiki_metadata.toml` + `<wiki>/wiki/index.md` + 末条 `<wiki>/wiki/log.md` 条目
  3. 按 wiki name 字母序聚合写入本文件
  4. 原子写（POSIX `tmp + fsync + rename`）
- **刷新时机**：每次 `scan` / `refresh-index`；大型 workspace 也可 `--quick` 只刷元数据层（不读 wiki/index.md）
- **skill 写入场景**：`scan` / `refresh-index`
- **CLI 写入场景**：**无**

## §6 STATS.md（skill 维护）

> **维护方**：CLI 在 init 时刻**不创建**（留空）。skill 在 `scan` 时一并创建 + 维护。
> 与 INDEX.md 的区别：INDEX.md 给人看（散文 + 列表），STATS.md 给 agent / 脚本看（结构化）。

- 路径：`<workspace-root>/STATS.md`
- frontmatter：同 §5（`type: workspace-stats`）
- **正文骨架**：

  ```markdown
  # <Workspace Display Name> — Workspace Stats

  > 结构化统计。skill scan 时刷新；脚本可解析 frontmatter + 表格。

  ## Overview

  | 指标 | 值 |
  | --- | --- |
  | total_wikis | N |
  | total_pages | M |
  | total_entities | ... |
  | total_concepts | ... |
  | total_sources | ... |
  | total_comparisons | ... |
  | total_syntheses | ... |
  | total_raw_files | ... |
  | cross_wiki_links | K |

  ## Per-wiki

  ### <wiki-name>

  | 指标 | 值 |
  | --- | --- |
  | pages | N |
  | entities | ... |
  | concepts | ... |
  | sources | ... |
  | comparisons | ... |
  | syntheses | ... |
  | raw_files | N |
  | last_log_entry | YYYY-MM-DD (kind) |
  | tags | [...] |
  | memory_files | N |

  ### <another-wiki>

  ... (同上)
  ```

- **生成流程**：同 §5，但输出格式更结构化（表格）
- **skill 写入场景**：`scan`（与 INDEX.md 同一次刷新）
- **CLI 写入场景**：**无**

## §7 cross_queries/（skill 维护，可选）

> **维护方**：CLI 不创建。skill 在 `query` 输出适合归档为 cross-wiki synthesis 时
> 创建 + 写入。是 workspace 级的"synthesis 类比"——`yzr-llm-wiki-management` 把好的
> 单 wiki query 答案归档为 `<wiki>/wiki/syntheses/<slug>.md`，本 skill 把好的
> 跨 wiki query 答案归档为 `<workspace>/cross_queries/<slug>.md`。

- 路径：`<workspace-root>/cross_queries/`
- 文件命名：`<slug>.md`，kebab-case，约束见 §15
- frontmatter（**5 必填** + 推荐 `description`）：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 人类可读标题 |
| `type` | enum | 是 | `cross-query`（reserved，见 §13） |
| `tags` | array | 是 | 推荐 `[workspace, cross-query, <涉及 wiki 的 tag>...]` |
| `created` | date | 是 | skill 写入日期 |
| `updated` | date | 是 | skill 写入日期（首次创建时同 `created`） |
| `description` | string | 否 | 一句话 |
| `sources` | array | 是 | 引用的 wiki 内页路径数组（相对 workspace 根，如 `huawei_storage_wiki/wiki/sources/foo.md`） |
| `wikis` | array | 是 | 涉及的 wiki 名列表 |

- **skill 写入场景**：`query` 输出用户确认归档时
- **CLI 写入场景**：**无**

## §8 LINT.md（skill 维护，可选）

> **维护方**：CLI 不创建。skill 在 `lint` 时写最近一次报告。属于"快照"——历史上多次
> lint 报告不累积，被新一次覆盖。

- 路径：`<workspace-root>/LINT.md`
- frontmatter：同 §5（`type: workspace-lint`）
- **正文骨架**：

  ```markdown
  # <Workspace Display Name> — Lint Report (<YYYY-MM-DD>)

  > 最近一次 workspace lint 结果。skill `lint` 时刷新；CLI 不参与。

  ## Per-wiki Issues

  ### <wiki-name>

  - **跨 wiki 重复实体**: <list>
  - **跨 wiki 失效链接**: <list>
  - **孤立 wiki**: <yes/no + 说明>
  - **本 wiki 内 lint**: 走 wiki-spec §3 / §4 lint 流程——本 skill 不重复

  ## Workspace-level Issues

  - **重复 entity 跨 wiki**: <wiki-a>::<entity-x> ↔ <wiki-b>::<entity-y>
  - **未注册的 wiki 子目录**: <list>（workspace.toml 中没有但磁盘上存在的 wiki 目录）
  - **STATS.md 过期**: <yes/no>（与最近一次 scan 的时间差）
  - **MEMORY 索引一致性**: <list of `memory-not-indexed`>（MEMORY/*.md 未在 MEMORY.md 索引列出）
  - **其他**: ...
  ```

- **skill 写入场景**：`lint`（每次覆盖）
- **CLI 写入场景**：**无**

## §9 workspace MEMORY/（skill 维护）

> **维护方**：CLI 在 init 时刻创建**空目录**并按 §9.1 写入 `MEMORY/MEMORY.md`（索引占位）；
> 后续 `MEMORY/*.md` 经验条目由 **skill** 写入，并**同步追加 MEMORY.md 索引一行**。
> skill 是 LLM agent 的**跨 wiki** 私有记忆——人类**不写** MEMORY 内容。CLI 不参与 MEMORY
> 的后续写入（仅 init 写骨架）。
>
> **scope 严格区分**（**核心不变量**，避免变成 junk drawer）：
>
> - ✅ `<workspace>/MEMORY/` 写**跨 wiki** 的 LLM 经验（用户对 workspace 组织的偏好 /
>   跨 wiki 关联 / lint recurring pattern / 跨 wiki 综合经验）
> - ❌ **不**写单 wiki 观察——单 wiki 的踩坑 / 偏好 / 关联归 `<wiki>/MEMORY/`
>   （由 `yzr-llm-wiki-management` 维护）
> - ❌ **不**写跨 wiki 综合答案本身——归 `<workspace>/cross_queries/`
> - ❌ **不**写一次性观察——直接 chat，不写 MEMORY

- 路径：`<workspace-root>/MEMORY/`
- 目录名 `MEMORY` **大写**，区别于小写 `raw` / `wiki` / `cross_queries` 等目录
- **MEMORY 不在 `INDEX.md` 中强制列出**——它是 agent 私有入口，不需要 workspace 单一入口约束
- **条目形式按事实颗粒度选**（与仓库根 `MEMORY/` / wiki-spec §5 MEMORY/ 同步）：
  - **完整条目**：含上下文 / 解决步骤 / 未来如何避免 → 建 `MEMORY/<slug>.md`（走 §9.2 规则），
    索引行 `- <slug> — 一句话摘要 → [正文](<slug>.md)`
  - **短条目**：一句话提醒 / 单一偏好 / 无需解释"为什么" → 索引行直接 `- 一句话事实`，
    不单独建 `.md` 文件
  - 判别尺度：需要解释"为什么这么做"或"将来怎么用" → 完整；仅作 reminder → 短
  - 短条目与完整条目可在同一 `MEMORY/MEMORY.md` 共存；lint `memory-not-indexed` 只兜底
    "有 .md 但未索引"，不强制反向（短条目无 .md，不进该检查）
- 命名约束：详见 §15

### §9.1 MEMORY/MEMORY.md（索引）

> **维护方**：CLI 在 init 时刻写一次（idempotent：已存在则跳过）。与 wiki-spec §5.1
> `MEMORY/MEMORY.md` 同构——本目录的索引文件。

- 路径：`<workspace-root>/MEMORY/MEMORY.md`
- **无 frontmatter**——它是被 `<workspace>/AGENTS.md` 用 `@MEMORY/MEMORY.md` import 内联的
  索引片段，不是 workspace 内容页（对齐仓库根 `MEMORY/MEMORY.md` / wiki-spec §5.1 形态）。
  lint / scan 把它当索引跳过 frontmatter / type 校验
- **加载机制（agent 中立）**：agent 在 workspace 根目录工作时——经薄壳 `CLAUDE.md` → `@AGENTS.md`
  递归展开自动加载 SSOT，`@MEMORY/MEMORY.md` 随之展开 → 索引常驻；原生读 `AGENTS.md` 的其他 agent
  直读 SSOT；agent 在别处工作（skill 经 `$LLMW_WORKSPACE` 读 AGENTS.md）时，`@` 不自动展开，
  由 AGENTS.md 顶部强制 Read 指令 + SKILL §0 启动检查显式 Read MEMORY.md 补齐
- 正文骨架：顶部 1 段说明（本目录用途 + 何时写 / 命名 / 纪律指向 SKILL §5，**不**重复以免
  口径分裂）+ `## 索引` 段。索引行两种格式共存：
  - **完整条目**：`- <slug> — <一句话摘要> → [正文](<slug>.md)`（指向 §9.2 的 `MEMORY/<slug>.md`）
  - **短条目**：`- <一句话事实>`（无链接，对应无 `.md` 文件的索引行 reminder）
  - 判别尺度见 §9 总段「条目形式按事实颗粒度选」
- lint `memory-not-indexed` 兜底——`MEMORY/*.md`（排除 `MEMORY.md`）未在索引列出时报该项；
  短条目无 `.md` 不进该检查
- **内容来源 / 字面量**：[`references/fixtures/memory-index.txt`](fixtures/memory-index.txt)
  （与 [`references/canonical/memory-index.md`](canonical/memory-index.md) 一致——MEMORY.md 无占位符，
  fixtures 与 canonical 内容相同）。CLI init **逐字拷贝**生成 `<workspace>/MEMORY/MEMORY.md`——与
  wiki-spec §5.1 走相同的 fixtures/canonical 字节金标准模式（无占位符字面量文件进 fixtures/canonical；
  有占位符的 `AGENTS.md` / `CLAUDE.md` 模板仍在 references/ 根，走 §4 内容级验证）。初始索引为空，注释用纯文字
  描述格式，不含真实 `[](...)` 链接以免被未来 lint 当死链

### §9.2 MEMORY/*.md（非 MEMORY.md）

- 路径：`<workspace-root>/MEMORY/<slug>.md`
- 命名约束：kebab-case `^[a-z0-9][a-z0-9-]*$`，见 §15
- frontmatter：**5 必填**（`title` / `type` / `created` / `updated` / `tags`）+ 推荐
  `description` + 推荐 `wikis` 字段（涉及 wiki 名数组）

| `type` 取值 | 含义 |
| --- | --- |
| `entity` / `concept` / `source` / `comparison` / `synthesis` | 复用 wiki-spec §9 的 5 类内容页 enum（按记忆内容性质选） |
| `workspace-memory` | 跨 wiki 关联 / 用户偏好 / lint 模式（**新增 reserved**，见 §13） |

- `wikis` 字段：数组，列涉及的 wiki 名；若该条记忆涉及全 workspace 而非特定 wiki，可省略
- lint 校验：走与 wiki 内容页一致的 5 必填校验（`title` / `type` / `created` / `updated` / `tags`）
- 与 wiki 内容页的区别：
  - **不**强制在 INDEX.md 列出
  - **不**要求有 inbound 链接
  - 正文无长度上限（agent 经验沉淀可以很长）
  - LLM agent **必须**创建（user 不写）
  - **必须**在 `MEMORY/MEMORY.md` 索引列出一行（skill 写 memory 时同步追加；
    lint `memory-not-indexed` 兜底漏列——severity = info，不阻断但提示）
  - 短条目无对应 `.md` 文件，frontmatter 5 必填仅约束完整条目；判别尺度见 §9 总段

### §9.3 何时写 / 不写

**写**（按 [`SKILL.md` §5 memory](../SKILL.md) 触发）：

- 跨 wiki 的关联（"X 类主题放 A wiki，Y 类放 B wiki"）
- 用户对 workspace 组织的偏好（"我更喜欢按时间线而非主题分 wiki"）
- workspace-wide lint 模式（"最近 N 次 lint 总是报某类问题"）
- 跨 wiki 综合经验（"这类问题需要先 scan 再答"）

**不写**：

- 单 wiki 的踩坑 → 归 `<wiki>/MEMORY/`
- 跨 wiki 综合答案本身 → 归 `<workspace>/cross_queries/`
- 一次性观察 → 直接 chat，不写 MEMORY

### §9.4 创建时机

`MEMORY/` 目录 + `MEMORY.md` 索引由 **CLI init 时刻**创建（见 §1 / §9.1）；skill **不重建**
（已存在即跳过）。这与 `INDEX.md` / `STATS.md`（skill scan 时建）区分——MEMORY 骨架是出生
形态的一部分，由 CLI 负责。

skill 在 `lint` / `query` / `link` / `scan` 触发时**不创建** MEMORY 结构；只在真正需要写
跨 wiki 经验时才 Write `MEMORY/<slug>.md` + 同步 `MEMORY.md` 索引一行。

## §10 .gitignore

CLI 必须生成一份最小 `.gitignore`，至少包含以下忽略规则（保留 §2 / §3 涉及的
"gitignored 但不能丢"的标记段）：

```gitignore
# >>> llmw (managed by llmw) >>>
workspace_models.toml
# IDE 项目级 settings（可能含 token）：`**/` 锚定 workspace 根 + 任意深度子目录
# `settings*.json` 同时覆盖 `settings.json` + `settings.local.json` + `settings.<env>.json` 等变体
**/.claude/settings*.json
**/.qoder/settings*.json
# <<< llmw <<<

# OS / 编辑器
.DS_Store
.idea/
.vscode/
*.swp
*.swo

# Obsidian 配置（保留 vault 内容）
.obsidian/workspace*
.obsidian/cache

# 临时文件
*.tmp
*.bak
```

**必须不忽略**：`workspace.toml`、`AGENTS.md`、`CLAUDE.md`、`INDEX.md`、`STATS.md`、`cross_queries/`、
`LINT.md`、`MEMORY/`、`<wiki-name>/`（wiki 仓的内容由 wiki-spec §6 各自的 `.gitignore` 处理）。

`.gitignore` **总是生成**——git 仓由用户外部创建（§11），与是否启用 git 无关；无 git 时无害，便于用户后续随时补 git。

## §11 Git 仓（用户外部创建，CLI 不碰）

> **立场**：workspace **不依赖 git 即可工作**——默认落盘为**纯目录树**。workspace 的 git 仓
> **由用户在外部自行 `git init` / `clone` 创建**，CLI **不碰 git**——不 `git init`、不 `add`、
> 不 `commit`、也不接 `--git`；版本控制是用户在自己机器上决定的事。`workspace_models.toml`
> 在无 git 时靠文件系统权限保护，用户启用 git 后靠 `.gitignore`（§10）排除。

- **init 允许落在用户已建好的空 git 仓上**：若目标目录已是 git 空仓（仅含 `.git` 与/或
  `.gitignore`），CLI 的 `init` 照常在其上继续——CLI 不调 `git init`，只是不把"已有 .git"
  当成拒绝条件（`git init` 本身幂等，CLI 落盘不破坏用户已建的仓）。
- **`.gitignore` 无条件生成**（详见 §10）：与用户是否启用 git 无关——CLI 总是写 `.gitignore`，
  便于用户后续随时 `git init` 时敏感文件已被排除。

## §12 拒绝条件（强约束）

CLI 在以下情况必须拒绝并退出（**非零退出码**）：

| 触发条件 | 错误信息建议 |
| --- | --- |
| `workspace.toml` 已存在且非 CLI 自己写的 | `"workspace.toml 已存在；拒绝覆盖"` |
| `AGENTS.md` 已存在 | `"AGENTS.md 已存在；拒绝覆盖（schema 是用户所有）"` |
| `CLAUDE.md`（薄壳）已存在 | `"CLAUDE.md 已存在；拒绝覆盖（schema 是用户所有，若需更新请手动编辑）"` |
| 试图 `wiki add` 到已存在的子目录 | `"<wiki-name>/ 已存在；拒绝覆盖"` |
| 试图 `wiki add` 时 `wiki-name` 与现存 wiki 重复 | `"wiki <name> 已注册；拒绝重复"` |

**绝不允许覆盖**：workspace CLI 的 idempotency 原则——已存在 + 内容合法 = 跳过；已存在 + 内容非法 = 报错；用户想重新初始化必须先手动备份 + 删除。

> **注意**：CLI **不**触碰 `INDEX.md` / `STATS.md` / `LINT.md` / `cross_queries/` +
> `MEMORY/*.md` 经验条目——这些是 skill 的领地。CLI 仅在 init 时写 `MEMORY/MEMORY.md` 索引
> 占位（见 §9.1）；CLI 不检查 INDEX/STATS/LINT/cross_queries 是否存在，也不拒绝 init 时
> 这些文件已存在的情况（skill 会在首次 `scan` 时按需创建或跳过自己的产物，这是 skill 的
> 幂等约定）。

## §13 Frontmatter 字段约定（skill 写 §5–§9 时用）

### 通用必填字段（5 项）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | string | 人类可读标题，不含扩展名 |
| `type` | enum | 见下方 `type` 取值 |
| `tags` | array | 可空数组 |
| `created` | date | `YYYY-MM-DD` |
| `updated` | date | `YYYY-MM-DD` |

### `type` 取值（5 类 wiki 内容页 + 2 类 wiki reserved + 4 类 workspace reserved + 1 类 workspace-memory）

| `type` | 目录 | 备注 |
| --- | --- | --- |
| `entity` / `concept` / `source` / `comparison` / `synthesis` | 5 类 wiki 内容页 enum（**复用 wiki-spec §9**） | `<workspace>/MEMORY/*.md` 可按记忆内容性质选 |
| `index` / `log` | 2 类 wiki reserved（**复用 wiki-spec §9**） | wiki 内 `wiki/index.md` / `wiki/log.md`（workspace 不直接用） |
| `workspace-index` | `<workspace>/INDEX.md`（唯一） | workspace reserved |
| `workspace-stats` | `<workspace>/STATS.md`（唯一） | workspace reserved |
| `workspace-lint` | `<workspace>/LINT.md`（唯一） | workspace reserved |
| `cross-query` | `<workspace>/cross_queries/<slug>.md` | workspace reserved |
| `workspace-memory` | `<workspace>/MEMORY/*.md`（非 MEMORY.md） | workspace reserved |

> **与 wiki-spec §9 的关系**：workspace-spec 的 `workspace-memory`（`<workspace>/MEMORY/*.md`
> 经验条目）与 wiki 内容页 5 类 enum（`<wiki>/MEMORY/*.md` 可按记忆性质选）location 区分，
> 不冲突。两份 `MEMORY.md` 索引（workspace 与 wiki 各一份）均**无 frontmatter**——与 wiki-spec
> 的 `<wiki>/MEMORY/MEMORY.md` 无 frontmatter 形态对齐。lint 工具需要识别本
> spec 的 `workspace-memory`；若 lint 脚本只跑在 wiki 内，可忽略本节。

### 类型特化字段

| 字段 | 适用 type | 必填 | 含义 |
| --- | --- | --- | --- |
| `sources` | `cross-query` | 是 | 引用的 wiki 内页路径数组（相对 workspace 根） |
| `wikis` | `cross-query` / `workspace-memory` | 是（`cross-query`）/ 推荐（`workspace-memory`） | 涉及的 wiki 名列表 |
| `description` | 所有 5 必填类 | 否 | 一句话 |

## §14 版本钉死

| 占位符 | 替换为 | 来源 |
| --- | --- | --- |
| `{{WORKSPACE_SPEC_VERSION}}` | CLI 当前兼容的 workspace spec 版本（如 `0.2.0`） | CLI 仓硬编码 |
| `{{WIKI_SPEC_VERSION}}` | CLI 当前兼容的 wiki spec 版本 | CLI 仓硬编码（与 yzr-llm-wiki-management SKILL.md metadata.wiki_spec_version 对齐） |
| `{{CLI_VERSION}}` | CLI 自身版本号 | CLI 仓 `__version__` 或 `pyproject.toml` / `package.json` |

CLI 在生成 `<workspace>/workspace.toml` 时把 `templates_version` 字段写为
`workspace_spec = <WORKSPACE_SPEC_VERSION>; wiki_spec = <WIKI_SPEC_VERSION>`（或类似编码）；
CLI 在生成 `<workspace>/AGENTS.md` 时把上述占位符按本表替换（薄壳 CLAUDE.md 仅替换
`{{WORKSPACE_DISPLAY_NAME}}`；`{{WIKI_SPEC_VERSION}}` **不进** AGENTS.md / CLAUDE.md 模板，
仅用于 workspace.toml `templates_version`）。

"当前 spec 版本"的 SSOT 是 [`yzr-llm-workspace-management`](../SKILL.md) SKILL.md
`metadata.workspace_spec_version`（本 spec 不重复钉号，避免双源漂移）。skill 在每次
`scan` 前比对 `workspace.toml.templates_version` 的 workspace_spec 分量与该版本——不一致时
**警告用户**走 §6 Migrate（不阻断；旧 spec 的产物仍可读）。完整检测走
`scripts/check_workspace_fixtures.py`（§17.3）。

## §15 命名约束

| 维度 | 规则 | 适用对象 |
| --- | --- | --- |
| Wiki name | `[a-z0-9][a-z0-9_-]*`，1–64 字符；推荐纯 kebab-case | `[wikis.<name>]` key + `<wiki-name>/` 子目录名 |
| cross_query slug | kebab-case `^[a-z0-9][a-z0-9-]*$` | `cross_queries/<slug>.md` |
| MEMORY 文件名 | kebab-case `^[a-z0-9][a-z0-9-]*$` | `<workspace>/MEMORY/*.md`（MEMORY.md 例外） |
| `model_id` | `[a-z0-9_-]{1,64}` | `workspace_models.toml` |
| frontmatter 字段名 | 严格小写 + 下划线 | 所有 workspace 级 markdown |
| frontmatter `type` 值 | 严格小写 + 连字符（`workspace-index` / `workspace-memory` 等） | 所有 workspace 级 markdown |

## §16 不在本 spec 范围内

以下事项 workspace CLI 与 skill 不必按本 spec 实现（属于"运行时规则"）：

- **cross-wiki Q&A 的工作流**——4 种模式（route / synthesis / compare / local）的
  算法与判定规则属 [`yzr-llm-workspace-management`](../SKILL.md) skill 范畴
- **跨 wiki 交叉引用（xref）建议逻辑**——同上
- **workspace lint 的工作流**——同上
- **workspace MEMORY 的工作流**（何时写 / 不写 / 怎样分类）——同上
- **frontmatter 字段的语义**（如 `description` 推荐写法）——LLM 写作视角，非 spec 视角
- **Obsidian / 编辑器偏好**——skill 假设通用 Markdown
- **INGEST / 单 wiki query / 单 wiki lint**——走 `yzr-llm-wiki-management` skill，
  本 spec 不重复

## §17 升级迁移（skill 维护）

> **维护方**：`yzr-llm-workspace-management` skill 的 migrate 工作流（SKILL.md §6）+
> `scripts/check_workspace_fixtures.py`（探测器）。CLI 不参与升级（§12 拒绝覆盖已存在文件）。

spec 演进时，已存在 workspace 的约定文件（AGENTS.md / CLAUDE.md / .gitignore /
MEMORY/MEMORY.md / workspace.toml `templates_version`）会有意识地保留旧格式——避免一刀切
破坏用户定制。本节定义检测 + 修复机制，让升级后 workspace 与最新模板保持**字节级**一致。

### §17.1 AGENTS.md / CLAUDE.md 模板同步

`AGENTS.md` 的 per-workspace 变量只有 4 个——Workspace 名 / 创建日期 / Workspace Spec
版本 / CLI 版本（全在 H1 + §六「当前配置」表）；正文 §一~§五 是纪律文本，跨 workspace
逐字相同。因此一致性校验**不**做"存在性断言"，做**模板渲染字节比对**：

- `scripts/check_workspace_fixtures.py` 的 `agents-md-template-sync`（error）：从 §六 表
  提取 4 变量（0.7.0- 老格式 fallback H1 + 老 §六 散文行），渲染
  `references/workspace-agents-md-template.md` 后与 workspace 实际 AGENTS.md 字节比对——
  任何不一致（旧版本残留 / 本地改动）都报错。`claude-md-template-sync` 同理（薄壳仅
  `{{WORKSPACE_DISPLAY_NAME}}` 一个变量；缺失文件报 `workspace-fix-claude-md-create`）。
- 修复 = **全量重渲染**（fix `workspace-fix-agents-md-resync` /
  `workspace-fix-claude-md-resync`）：§六 变量保留旧值（`{{WORKSPACE_SPEC_VERSION}}` 用
  迁移目标版本），其余以模板渲染稿为准——**不**做局部 Edit。旧文件中多出的本地定制
  行/段由 agent 逐条列给用户裁定：搬 `MEMORY/`（一行事实写 MEMORY.md 索引短条目；
  含 why 建 `MEMORY/<slug>.md` 完整条目 + 索引行）或丢弃。
- **纪律推论**：本 workspace 特有纪律 / 偏好一律沉淀到 `MEMORY/`（由 AGENTS.md 顶部
  `@MEMORY/MEMORY.md` `@import` 加载，会话常驻），不写进 AGENTS.md——否则下次升级
  重渲染时丢失。
- 与 `agents-version-is-current` 正交：版本行新旧由后者管；本 check 渲染时用
  workspace 自钉版本替换 `{{WORKSPACE_SPEC_VERSION}}`，只比"正文与模板同步"。

### §17.2 迁移例外（所有权开口）

§1 / §4 的"skill 只读 / 不写"纪律在 migrate 工作流内有 4 条例外（前提都是**用户确认**
后在同一会话内执行）：

| 例外 | 范围 |
| --- | --- |
| agent 可 Write 覆盖 `AGENTS.md` | 仅 §17.1 全量重渲染；本地定制已逐条裁定 |
| agent 可 Write 覆盖 / 创建 `CLAUDE.md` | 仅按薄壳模板渲染 |
| agent 可 Edit `.gitignore` | 仅补 §10 骨架段 / llmw 托管块规则；不动用户自定义规则 |
| agent 可 Edit `workspace.toml` 的 `templates_version` 单字段 | migrate 收尾 bump 到目标版本；其余字段不动 |

### §17.3 检测与修复流程

探测器 `scripts/check_workspace_fixtures.py`（6 条 check：
`agents-version-is-current` / `agents-md-template-sync` / `claude-md-template-sync` /
`gitignore-skeleton` / `memory-index-skeleton` / `workspace-toml-templates-version-sync`（warn，
不阻断）；退出码 0 全过 / 1 有 error / 2 运行错误；`--json` 机器可读）。修复由 agent 按
报告 `fix` 动作走 SKILL.md §6——**不落 plan 文件**（修复面恒定 ≤ 4 个结构文件，报告即
清单；检测幂等，中断重跑即可），零中间产物。

---

## 附录 A：CLI 实现自检建议

CLI 在生成完成后，可执行以下验证：

1. **字节级对比**：CLI 渲染的 `workspace.toml` 与本 spec §2 schema 一致；`workspace_models.toml`
   与 §3 schema 一致；`AGENTS.md` 与 §4 SSOT 模板字面一致 + `CLAUDE.md` 与薄壳模板字面一致（占位符替换后）；`MEMORY/MEMORY.md` 与
   `references/canonical/memory-index.md` 字节一致（无占位符，直接 `cmp`，流程同 wiki fixtures）；`.gitignore` 与 §10 一致
2. **结构性自检**：`<workspace>/` 含 §1 列出的所有顶层项（含 `MEMORY/MEMORY.md`）；`<wiki-name>/` 子目录按
   wiki-spec §1 目录结构 落盘
3. **拒绝性自检**：尝试对已存在 workspace 跑 `init`，应非零退出；尝试 `wiki add`
   到已存在目录，应非零退出；尝试 `init` 时 `AGENTS.md` / `CLAUDE.md` 已存在，应非零退出（§12）
4. **gitignored 自检**：`workspace_models.toml` 在 `.gitignore` 中；
   `**/.claude/settings*.json` 与 `**/.qoder/settings*.json` 在 `.gitignore` 中（`**/` 单行覆盖
   workspace 根 + 任意深度子目录；`settings*.json` 通配 `settings.json` / `settings.local.json` /
   `settings.<env>.json` 等所有 settings 变体）
5. **不变量自检**：init 完成后 `<workspace>/INDEX.md` / `STATS.md` / `LINT.md` / `cross_queries/`
   **不存在**（CLI 不会创建它们；skill 在首次 `scan` 时按 §5–§8 约定建）；但 `<workspace>/MEMORY/`
   **存在**且含 `MEMORY.md` 索引、无 `*.md` 经验条目（CLI init 按 §9 建骨架）

## 附录 B：版本历史

完整 spec 演进日志（每版的 spec / SKILL / 模板同步范围）已
拆出到 [`workspace-spec-changelog.md`](workspace-spec-changelog.md)——CLI 不读，agent 追"为什么
这条规则存在"时按需 Read。

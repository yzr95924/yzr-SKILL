# Workspace Spec（workspace CLI 实现契约）

> 本文档是 **workspace CLI**（如 `llmw`）生成 workspace 仓时的实现契约，同时也是
> [`llm-workspace-management`](../SKILL.md) skill 操作 workspace 的权威 schema 参考。
> CLI 必须按本文档落盘骨架；skill 必须按本文档约定的归属关系维护内容。
>
> **依赖方向**：`workspace CLI → 本 spec`（CLI 服从 spec；spec 不依赖 CLI 实现）；
> `llm-workspace-management → 本 spec`（skill 按 spec 操作）。
> 本 spec 变更 → CLI 与 skill 必须同步；CLI / skill 变更不影响本 spec。
>
> **生命周期归属**：本 spec 只规定 workspace 仓的"出生形态" + 持续维护期各文件的归属。
> workspace 出生后的所有成长（cross-wiki Q&A / xref / lint / 跨 wiki 编排）由
> [`llm-workspace-management`](../SKILL.md) skill 在会话内负责。CLI 在 workspace
> 生命周期的两个边界点被调用：
>
> - **init**：创建（按本 spec §1–§7 落盘）
> - **delete**：删除（带备份）
>
> 其他时刻调 CLI 属"误用"，CLI 应拒绝。

## 目录

- [§1 目录结构](#1-目录结构)
- [§2 workspace.toml](#2-workspacetoml)
- [§3 workspace_models.toml](#3-workspace_modelstoml)
- [§4 INDEX.md（skill 维护）](#4-indexmdskill-维护)
- [§5 STATS.md（skill 维护）](#5-statsmdskill-维护)
- [§6 cross_queries/（skill 维护，可选）](#6-cross_queriesskill-维护可选)
- [§7 LINT.md（skill 维护，可选）](#7-lintmdskill-维护可选)
- [§8 .gitignore](#8-gitignore)
- [§9 Git 初始化（opt-in，默认跳过）](#9-git-初始化opt-in默认跳过)
- [§10 拒绝条件（强约束）](#10-拒绝条件强约束)
- [§11 Frontmatter 字段约定（skill 写 INDEX.md / STATS.md / LINT.md / cross_queries 时用）](#11-frontmatter-字段约定skill-写-indexmd--statsmd--lintmd--cross_queries-时用)
- [§12 版本钉死](#12-版本钉死)
- [§13 命名约束](#13-命名约束)
- [§14 不在本 spec 范围内](#14-不在本-spec-范围内)
- [附录 A：CLI 实现自检建议](#附录-acli-实现自检建议)
- [附录 B：版本历史](#附录-b-版本历史)

## §1 目录结构

```
<workspace-root>/
├── .gitignore                      # CLI init 时写（§8）
├── workspace.toml                  # CLI init 时写（§2）
├── workspace_models.toml           # CLI init 时写（§3，gitignored）
├── INDEX.md                        # skill scan 时建 + 维护（§4）
├── STATS.md                        # skill scan 时建 + 维护（§5）
├── cross_queries/                  # skill 可选建（§6）
└── <wiki-name>/                    # 每个 wiki 一个子目录，遵循 [wiki-spec.md §1](wiki-spec.md#1-目录结构)
```

**workspace 根的 6 类文件 / 目录各自归属**：

| 文件 / 目录 | init 时刻（CLI） | 后续维护方 | 说明 |
| --- | --- | --- | --- |
| `.gitignore` | CLI 写 | CLI（重 init 时覆盖；普通命令不碰） | 排除 `workspace_models.toml` 等敏感文件 |
| `workspace.toml` | CLI 写 | **CLI**（`wiki add / remove / config` 等命令） | wiki 注册表 + 全局默认；skill **不写** |
| `workspace_models.toml` | CLI 写 | **CLI**（`model add / remove / set-default`） | 模型注册表（API key 等敏感信息）；skill **不写** |
| `INDEX.md` | CLI **不写**（留空） | **skill**（scan / refresh-index） | workspace 全局入口文档 |
| `STATS.md` | CLI **不写**（留空） | **skill**（scan 时一并刷新） | workspace 结构化统计 |
| `cross_queries/` | CLI **不写**（留空目录） | **skill**（跨 wiki 综合答案归档） | 类比 wiki 内的 `syntheses/` |
| `LINT.md` | CLI **不写**（留空） | **skill**（lint 时写） | workspace 级 lint 报告（最近一次） |
| `<wiki-name>/` | CLI 写（按 [wiki-spec §1](wiki-spec.md#1-目录结构)） | **CLI** 写元数据 + **skill**（或 `llm-wiki-management`）写内容 | 每个 wiki 是独立子仓 |

> **CLI 的写入范围限制（不变量）**：CLI 只写 `workspace.toml`、`workspace_models.toml`、
> `.gitignore` 三份根级文件 + `<wiki-name>/` 子树（按 wiki-spec）。**CLI 绝不写
> `INDEX.md` / `STATS.md` / `LINT.md` / `cross_queries/`**——这四份是 workspace
> skill 的领地。

> **skill 的写入范围限制（不变量）**：skill 只写 `INDEX.md` / `STATS.md` / `LINT.md` /
> `cross_queries/` 四份 workspace 级文件 + 各 `<wiki-name>/wiki/**`（通过
> `llm-wiki-management`）。**skill 绝不写 `workspace.toml` / `workspace_models.toml` /
> `.gitignore`**——这些是 CLI 的领地。skill 也不写 `<wiki-name>/raw/`（用户所有）。

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
| `path` | string | 是 | 相对 workspace 根的子目录名（与 `<name>` 相同的约定，见 §13） |
| `created_at` | string (ISO8601) | 是 | wiki 注册时间，CLI 自动写 |

- **CLI 写入场景**：`init` / `wiki add` / `wiki remove` / `wiki config set default_model`
  / `config set default_model` / `config unset default_model`
- **skill 写入场景**：**无**——只读

## §3 workspace_models.toml

> **维护方**：CLI 在 init 时刻创建空骨架 + 后续 `model add / remove / set-default / unset-default`
> 维护。skill **不读不写**——skill 做 cross-wiki Q&A 不需要感知具体 model 配置。

- 路径：`<workspace-root>/workspace_models.toml`
- 格式：TOML
- **必须 gitignored**（详见 §8）——含 API key 等敏感信息
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
| `model_id` | string | 是 | slug，CLI 内部引用用，**不是网关模型名**；命名约束见 §13 |
| `name` | string | 是 | 网关模型名（如 `claude-sonnet-4-6`），`wiki enter` 时用作 `ANTHROPIC_MODEL` |
| `base_url` | string | 是 | API base URL |
| `api_key` | string | 是 | API key；list / show / dry-run 输出走 redact（`前3...末4` 或 `***`） |
| `is_default` | bool | 否 | 全局至多 1 条 `true` |

- **CLI 写入场景**：`init` / `model add` / `model remove` / `model set-default` / `model unset-default`
- **skill 写入场景**：**无**——完全无关

## §4 INDEX.md（skill 维护）

> **维护方**：CLI 在 init 时刻**不创建**（留空）。skill 在 `scan` / `refresh-index` 时
> 创建 + 持续维护。skill 是 LLM 拥有的"workspace 入口文档"——人类只读。
> CLI 不参与 INDEX.md 的任何写入；skill 不依赖 CLI。

- 路径：`<workspace-root>/INDEX.md`
- frontmatter（**5 必填** + 推荐 `description`）：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 推荐 `"Workspace Index"` |
| `type` | enum | 是 | `workspace-index`（reserved，见 §11） |
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

## §5 STATS.md（skill 维护）

> **维护方**：CLI 在 init 时刻**不创建**（留空）。skill 在 `scan` 时一并创建 + 维护。
> 与 INDEX.md 的区别：INDEX.md 给人看（散文 + 列表），STATS.md 给 agent / 脚本看（结构化）。

- 路径：`<workspace-root>/STATS.md`
- frontmatter：同 §4（`type: workspace-stats`）
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

- **生成流程**：同 §4，但输出格式更结构化（表格）
- **skill 写入场景**：`scan`（与 INDEX.md 同一次刷新）
- **CLI 写入场景**：**无**

## §6 cross_queries/（skill 维护，可选）

> **维护方**：CLI 不创建。skill 在 `query` 输出适合归档为 cross-wiki synthesis 时
> 创建 + 写入。是 workspace 级的"synthesis 类比"——`llm-wiki-management` 把好的
> 单 wiki query 答案归档为 `<wiki>/wiki/syntheses/<slug>.md`，本 skill 把好的
> 跨 wiki query 答案归档为 `<workspace>/cross_queries/<slug>.md`。

- 路径：`<workspace-root>/cross_queries/`
- 文件命名：`<slug>.md`，kebab-case，约束见 §13
- frontmatter（**5 必填** + 推荐 `description`）：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 人类可读标题 |
| `type` | enum | 是 | `cross-query`（reserved，见 §11） |
| `tags` | array | 是 | 推荐 `[workspace, cross-query, <涉及 wiki 的 tag>...]` |
| `created` | date | 是 | skill 写入日期 |
| `updated` | date | 是 | skill 写入日期（首次创建时同 `created`） |
| `description` | string | 否 | 一句话 |
| `sources` | array | 是 | 引用的 wiki 内页路径数组（相对 workspace 根，如 `huawei_storage_wiki/wiki/sources/foo.md`） |
| `wikis` | array | 是 | 涉及的 wiki 名列表 |

- **skill 写入场景**：`query` 输出用户确认归档时
- **CLI 写入场景**：**无**

## §7 LINT.md（skill 维护，可选）

> **维护方**：CLI 不创建。skill 在 `lint` 时写最近一次报告。属于"快照"——历史上多次
> lint 报告不累积，被新一次覆盖。

- 路径：`<workspace-root>/LINT.md`
- frontmatter：同 §4（`type: workspace-lint`）
- **正文骨架**：

  ```markdown
  # <Workspace Display Name> — Lint Report (<YYYY-MM-DD>)

  > 最近一次 workspace lint 结果。skill `lint` 时刷新；CLI 不参与。

  ## Per-wiki Issues

  ### <wiki-name>

  - **跨 wiki 重复实体**: <list>
  - **跨 wiki 失效链接**: <list>
  - **孤立 wiki**: <yes/no + 说明>
  - **本 wiki 内 lint**: 走 [wiki-spec §3 / §4 lint 流程](wiki-spec.md)——本 skill 不重复

  ## Workspace-level Issues

  - **重复 entity 跨 wiki**: <wiki-a>::<entity-x> ↔ <wiki-b>::<entity-y>
  - **未注册的 wiki 子目录**: <list>（workspace.toml 中没有但磁盘上存在的 wiki 目录）
  - **STATS.md 过期**: <yes/no>（与最近一次 scan 的时间差）
  - **其他**: ...
  ```

- **skill 写入场景**：`lint`（每次覆盖）
- **CLI 写入场景**：**无**

## §8 .gitignore

CLI 必须生成一份最小 `.gitignore`，至少包含以下忽略规则（保留 §1 / §2 / §3 涉及的
"gitignored 但不能丢"的标记段）：

```gitignore
# >>> llmw (managed by llmw) >>>
workspace_models.toml
*/.claude/settings.local.json
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

**必须不忽略**：`workspace.toml`、`INDEX.md`、`STATS.md`、`cross_queries/`、`LINT.md`、
`<wiki-name>/`（wiki 仓的内容由 wiki-spec §6 各自的 `.gitignore` 处理）。

`.gitignore` **无论是否 opt-in git 都生成**——无 git 时是无害的空操作，且便于后续补 git。

## §9 Git 初始化（opt-in，默认跳过）

> **立场**：workspace **不依赖 git 即可工作**——默认落盘为**纯目录树**。git 仅在用户
> 显式 opt-in 时启用，用于版本控制 / history / diff。`workspace_models.toml` 在
> 无 git 时靠文件系统权限保护；有 git 时靠 `.gitignore` 排除。

- **默认（无 `--git`）**：CLI **完全不碰 git**——不 init、不 add、不 commit。
- **opt-in（`--git`）**：CLI 在 workspace 根执行：
  1. `git init`
  2. `git symbolic-ref HEAD refs/heads/main`（默认 main 分支）
  3. 检查全局 `git config user.email` / `user.name`，未配则 local 配占位值
  4. 为 `cross_queries/`（若已建）等空目录放 `.gitkeep` 让其能被 `git add`
  5. `git add .`
  6. `git commit -m "Initial workspace scaffold"`
- **不得**对已存在的 git 仓误调 `git init`。

## §10 拒绝条件（强约束）

CLI 在以下情况必须拒绝并退出（**非零退出码**）：

| 触发条件 | 错误信息建议 |
| --- | --- |
| `workspace.toml` 已存在且非 CLI 自己写的 | `"workspace.toml 已存在；拒绝覆盖"` |
| 试图 `wiki add` 到已存在的子目录 | `"<wiki-name>/ 已存在；拒绝覆盖"` |
| 试图 `wiki add` 时 `wiki-name` 与现存 wiki 重复 | `"wiki <name> 已注册；拒绝重复"` |

**绝不允许覆盖**：workspace CLI 的 idempotency 原则——已存在 + 内容合法 = 跳过；已存在 + 内容非法 = 报错；用户想重新初始化必须先手动备份 + 删除。

> **注意**：CLI **不**触碰 `INDEX.md` / `STATS.md` / `LINT.md` / `cross_queries/`——
> 这些是 skill 的领地，CLI 不检查它们是否存在，也不拒绝 init 时这些文件已存在的情况
> （skill 会在首次 `scan` 时创建或覆盖自己的 INDEX.md，这是 skill 的幂等约定）。

## §11 Frontmatter 字段约定（skill 写 INDEX.md / STATS.md / LINT.md / cross_queries 时用）

### 通用必填字段（5 项）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | string | 人类可读标题，不含扩展名 |
| `type` | enum | 见下方 `type` 取值 |
| `tags` | array | 可空数组 |
| `created` | date | `YYYY-MM-DD` |
| `updated` | date | `YYYY-MM-DD` |

### `type` 取值（新增 4 类 reserved）

| `type` | 目录 | 备注 |
| --- | --- | --- |
| `workspace-index` | `<workspace>/INDEX.md`（唯一） | reserved，仅标记用 |
| `workspace-stats` | `<workspace>/STATS.md`（唯一） | reserved，仅标记用 |
| `workspace-lint` | `<workspace>/LINT.md`（唯一） | reserved，仅标记用 |
| `cross-query` | `<workspace>/cross_queries/<slug>.md` | 类比 wiki 内的 `synthesis` |

> **与 wiki-spec §9 的关系**：本 spec 新增的 4 类 reserved 与 wiki-spec §9 的
> 5 类内容页（`entity` / `concept` / `source` / `comparison` / `synthesis`）+
> 3 类 wiki reserved（`index` / `log` / `memory`）**不冲突也不重复**——命名空间分开
> （`workspace-*` / `cross-query` vs wiki 内 5+3 类）。lint 工具需要识别本 spec
> 新增的 4 类；若 lint 脚本只跑在 wiki 内，可忽略本节。

### 类型特化字段

| 字段 | 适用 type | 必填 | 含义 |
| --- | --- | --- | --- |
| `sources` | `cross-query` | 是 | 引用的 wiki 内页路径数组（相对 workspace 根） |
| `wikis` | `cross-query` | 是 | 涉及的 wiki 名列表 |
| `description` | 所有 4 类 | 否 | 一句话 |

## §12 版本钉死

| 占位符 | 替换为 | 来源 |
| --- | --- | --- |
| `{{WORKSPACE_SPEC_VERSION}}` | CLI 当前兼容的 workspace spec 版本（如 `0.1.0`） | CLI 仓硬编码 |
| `{{WIKI_SPEC_VERSION}}` | CLI 当前兼容的 wiki spec 版本 | CLI 仓硬编码（与 llm-wiki-management SKILL.md metadata.wiki_spec_version 对齐） |
| `{{CLI_VERSION}}` | CLI 自身版本号 | CLI 仓 `__version__` 或 `pyproject.toml` / `package.json` |

CLI 在生成 `<workspace>/workspace.toml` 时把 `templates_version` 字段写为
`workspace_spec = <WORKSPACE_SPEC_VERSION>; wiki_spec = <WIKI_SPEC_VERSION>`（或类似编码）。

skill 在每次 `scan` 前比对 `workspace.toml.templates_version` 与本 spec 顶部声明的
当前版本——不一致时**警告用户**（不阻断；旧 spec 的产物仍可读）。

## §13 命名约束

| 维度 | 规则 | 适用对象 |
| --- | --- | --- |
| Wiki name | `[a-z0-9][a-z0-9_-]*`，1–64 字符；推荐纯 kebab-case | `[wikis.<name>]` key + `<wiki-name>/` 子目录名 |
| cross_query slug | kebab-case `^[a-z0-9][a-z0-9-]*$` | `cross_queries/<slug>.md` |
| `model_id` | `[a-z0-9_-]{1,64}` | `workspace_models.toml` |
| frontmatter 字段名 | 严格小写 + 下划线 | 所有 workspace 级 markdown |
| frontmatter `type` 值 | 严格小写 + 连字符（`workspace-index` 等） | 所有 workspace 级 markdown |

## §14 不在本 spec 范围内

以下事项 workspace CLI 与 skill 不必按本 spec 实现（属于"运行时规则"）：

- **cross-wiki Q&A 的工作流**——4 种模式（route / synthesis / compare / local）的
  算法与判定规则属 [`llm-workspace-management`](../SKILL.md) skill 范畴
- **跨 wiki 交叉引用（xref）建议逻辑**——同上
- **workspace lint 的工作流**——同上
- **frontmatter 字段的语义**（如 `description` 推荐写法）——LLM 写作视角，非 spec 视角
- **Obsidian / 编辑器偏好**——skill 假设通用 Markdown
- **INGEST / 单 wiki query / 单 wiki lint**——走 [`llm-wiki-management`](wiki-spec.md) skill，
  本 spec 不重复

---

## 附录 A：CLI 实现自检建议

CLI 在生成完成后，可执行以下验证：

1. **字节级对比**：CLI 渲染的 `workspace.toml` 与本 spec §2 schema 一致；`workspace_models.toml`
   与 §3 schema 一致；`.gitignore` 与 §8 一致
2. **结构性自检**：`<workspace>/` 含 §1 列出的所有顶层项；`<wiki-name>/` 子目录按
   [wiki-spec §1](wiki-spec.md#1-目录结构) 落盘
3. **拒绝性自检**：尝试对已存在 workspace 跑 `init`，应非零退出；尝试 `wiki add`
   到已存在目录，应非零退出
4. **gitignored 自检**：`workspace_models.toml` 在 `.gitignore` 中；`*/.claude/settings.local.json` 在 `.gitignore` 中
5. **不变量自检**：init 完成后 `<workspace>/INDEX.md` / `STATS.md` / `LINT.md` / `cross_queries/`
   **不存在**（CLI 不会创建它们；skill 在首次 `scan` 时建）

## 附录 B：版本历史

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| 0.1.0 | 2026-06-30 | 初始版本：定义 workspace 根 6 类文件归属、INDEX.md / STATS.md / LINT.md / cross_queries/ schema、CLI 与 skill 边界（CLI 写 workspace.toml / models / .gitignore；skill 写 INDEX.md / STATS.md / LINT.md / cross_queries/）+ 4 类 reserved frontmatter type |
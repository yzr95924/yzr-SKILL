# Wiki Spec（CLI 实现契约）

> 本文档是 **workspace CLI** 生成 wiki 仓时的实现契约。
> CLI 必须按本文档落盘；SKILL 仓的 SKILL.md / references/ 规则以本文档定义的产物为前提。
>
> **依赖方向**：`workspace CLI → 本 spec`（CLI 服从 spec；spec 不依赖 CLI 实现）。
> 本 spec 变更 → CLI 必须同步；CLI 变更不影响本 spec。
>
> **生命周期归属**：本 spec 只规定 wiki 仓的"出生形态"。
> wiki 出生后的所有成长（ingest / query / lint / 重写）由 **LLM agent** 维护，遵循
> SKILL 仓的 SKILL.md / references/ 规则。CLI 在 wiki 生命周期的两个边界点被调用：
>
> - **init**：创建（按本 spec 落盘）
> - **delete**：删除（带备份）
>
> 其他时刻调 CLI 属"误用"，CLI 应拒绝。
>
> **AGENTS.md / CLAUDE.md（薄壳） / index.md / log.md / MEMORY/ 的归属**：
>
> | 文件 / 目录 | init 时刻（CLI） | 后续所有变更 |
> | --- | --- | --- |
> | `<wiki-root>/AGENTS.md` | CLI 按 §2 拷贝 SSOT 模板 | 用户（schema 是用户宪法，工具无关 SSOT） |
>
| `<wiki-root>/CLAUDE.md`（薄壳） | CLI 按 §2 拷贝薄壳模板（`@AGENTS.md`） | 用户（仅供 Claude Code 自动加载） |
> | `wiki/index.md` | CLI 按 §3 写入初始骨架 | **LLM agent**（ingest / 重写 / 归档时同步） |
> | `wiki/log.md` | CLI 按 §4 写入首条 setup 条目 | **LLM agent**（只 append，不删改） |
> | `MEMORY/` | CLI 按 §5 创建空目录 + 写 MEMORY.md（索引） | **LLM agent**（append 经验条目 + 同步 MEMORY.md 索引） |
> | `scripts/`（0.9.0+） | CLI 按 §14 创建空目录 + 写 SCRIPTS.md（索引） | **用户 + LLM agent**（添加 / 修改脚本与同步 SCRIPTS.md 段是原子动作） |
>
> CLI **不**参与 index.md / log.md / MEMORY / scripts 的后续追加；无 "add log entry" /
> "add memory" / "add script" / "sync index" 类命令。

## 目录

- [§1 目录结构](#1-目录结构)
- [§2 AGENTS.md（SSOT）+ CLAUDE.md（薄壳）](#2-agentsmdssot-claudemd薄壳)
- [§3 wiki/index.md](#3-wikiindexmd)
- [§4 wiki/log.md](#4-wikilogmd)
- [§5 MEMORY/](#5-memory)
  - [§5.1 MEMORY/MEMORY.md（索引）](#51-memorymemorymd索引)
  - [§5.2 MEMORY/*.md（非 MEMORY.md）](#52-memorymd非-memorymd)
- [§6 .gitignore](#6-gitignore)
- [§7 Git 初始化（opt-in，默认跳过）](#7-git-初始化opt-in默认跳过)
- [§8 拒绝条件（强约束）](#8-拒绝条件强约束)
- [§9 Frontmatter 字段全集（CLI 引用，非生成内容页）](#9-frontmatter-字段全集cli-引用非生成内容页)
- [§10 版本钉死](#10-版本钉死)
- [§11 命名约束（影响 CLI 生成的产物）](#11-命名约束影响-cli-生成的产物)
- [§12 不在本 spec 范围内](#12-不在本-spec-范围内)
- [§13 raw/external/——外部代码仓接入](#13-rawexternal外部代码仓接入可选)
- [§14 scripts/——本 wiki 仓扩展脚本目录（0.9.0+）](#14-scripts本-wiki-仓扩展脚本目录090)
- [附录 A：CLI 实现自检建议](#附录-acli-实现自检建议)
- [附录 B：版本历史](#附录-b版本历史)

## §1 目录结构

```text
<wiki-root>/
├── .gitignore
├── AGENTS.md                  # 0.11.0+：工具无关纪律 SSOT（详 §2）
├── CLAUDE.md                  # 0.11.0+：薄壳（@AGENTS.md，供 Claude Code 自动加载）
├── MEMORY/                    # 0.10.0+：agent 持久化记忆目录（详 §5）
│   └── MEMORY.md              # MEMORY 索引；AGENTS.md 用 @MEMORY/MEMORY.md import 会话常驻
├── raw/
│   ├── articles/
│   └── assets/
├── scripts/                   # 0.9.0+：本 wiki 自维护脚本目录（详 §14）
│   └── SCRIPTS.md             # scripts/ 索引；被 AGENTS.md 用 @scripts/SCRIPTS.md import
└── wiki/
    ├── comparisons/
    ├── concepts/
    ├── entities/
    ├── index.md
    ├── log.md
    ├── sources/
    ├── syntheses/
    └── tags.md                # 0.8.0+：tag 白名单（LLM 拥有；详 §9）
```

- 5 个内容页子目录名固定，**字母序**（`comparisons` → `concepts` → `entities` → `sources` → `syntheses`），
  CLI 必须按此顺序创建（利于阅读、diff 稳定、跨工具兼容）
- **`MEMORY/` 是 wiki 仓的"agent 持久化记忆"目录**（0.10.0+ 起与 `wiki/` **平级**，
  不再嵌在 `wiki/` 下）——LLM agent 写入，用于沉淀跨 ingest / query / lint 的工作经验、
  踩坑记录、用户偏好；走 §5.2 的 frontmatter **1 必填（`title`）+ optional 字段**规则
  （MEMORY 是 agent 私有，不与 wiki 内容页共享 5 必填；详见 §5）。
  其中 `MEMORY.md` 是索引，被 `<wiki-root>/AGENTS.md` 用 `@MEMORY/MEMORY.md` import
  会话常驻——避免 MEMORY 沦为只写不读的死库。**为什么移到 `<wiki-root>/MEMORY/`**：
  对应 §四层架构第 3 层（独立于 wiki/ 内容，物理位置跟逻辑分层对齐）；未来 publish 时
  MEMORY 自然留作私有层不外传
- **`wiki/tags.md` 是 wiki 仓的"tag 白名单"（0.8.0+）**——LLM agent 拥有，存放本 wiki
  允许使用的 tag 集合；裸 bullet 列表，**无 frontmatter**（与 MEMORY.md 同——元数据不是
  wiki 内容页）；不在 `wiki/index.md` 强制列出；CLI init 时刻按 `references/fixtures/`
  生成空白模板，LLM 与用户共同确认主题分类后填充。详见 §9「§9.1 tag 白名单来源」
- `raw/articles/` 与 `raw/assets/` 是默认占位；用户在 wiki 仓内可自由新增其他子目录
  （如 `podcasts/` / `papers/` / `clippings/` / `external/`——后者语义见 §13），CLI 不必预创建
- `index.md` / `log.md` 是 `wiki/` 下的文件（不是子目录）；`MEMORY/MEMORY.md` 在 `<wiki-root>/MEMORY/`
  下（0.10.0+ 起与 `wiki/` 平级），不是 `wiki/` 下的文件
- `comparisons/` 等 5 个内容页子目录在初始化时为空目录——空目录对纯目录树 wiki 无副作用；
  仅当用户 `--git` opt-in 时，CLI 在每个空子目录放 `.gitkeep` 让其能被 `git add`（见 §7）
- **`scripts/` 是 wiki 仓的本机扩展脚本目录（0.9.0+）**——CLI init 时刻**始终创建**
  （与 `raw/articles/` 同：默认占位），用户 / agent 后续填入项目级 ingest 扩展、
  外部 CLI 胶水脚本、自动化钩子等。`scripts/SCRIPTS.md` 是这个目录的索引，被
  `<wiki-root>/AGENTS.md` 用 `@scripts/SCRIPTS.md` import 会话常驻——避免脚本沦为
  "有脚本但 agent 不知道" 的死库。scripts/ **不**走 §9 5 必填、**不**参与 lint
  内容页扫描（**代码而非内容页**）。详见 §14。

## §2 AGENTS.md（SSOT）+ CLAUDE.md（薄壳）

> **agent 中立设计**（0.11.0+）：wiki 纪律的**单一真源是 `AGENTS.md`**——工具无关。`CLAUDE.md`
> 收敛为薄壳（`@AGENTS.md` + 声明），仅供 Claude Code 经自动加载约定读到 SSOT。读 `AGENTS.md` 的其他
> agent（Qoder / Codex / Gemini CLI 等）原生直读 SSOT，不依赖薄壳。改纪律请改 `AGENTS.md`，不要改 `CLAUDE.md` 薄壳。
>
> **维护方**：CLI 在 init 时刻按本节模板拷贝两份；后续修改由 **用户** 完成（AGENTS.md 是 wiki 的
> schema，是用户的"宪法"）。LLM agent 不得编辑 AGENTS.md / CLAUDE.md；如需变更 schema，**先与用户确认**。
>
> **0.11.0+**：`CLAUDE.md`（SSOT）→ 拆为 `AGENTS.md`（SSOT，工具无关）+ `CLAUDE.md`（薄壳）。
> `@MEMORY/MEMORY.md` / `@scripts/SCRIPTS.md` 两行 import 从原 CLAUDE.md 顶部移入 AGENTS.md 顶部
> （@import 写在 SSOT 内，两边都能加载：Claude Code 经薄壳 CLAUDE.md → @AGENTS.md 递归展开加载；
> Qoder / Codex 等读 `AGENTS.md` 的 agent 原生读，@import 能否展开取决于实现，最坏由 orient ritual
> 显式 Read 兜底）。老 wiki（CLAUDE.md 仍是 SSOT 形态）由 `lint_wiki.py --check-version --apply`
> 的 `claudemd-to-agents-md-split` action 迁移。
>
> **0.8.0+**：SSOT 模板的 `### Tag Taxonomy` 段已被移除——tag 白名单现归
> [`wiki/tags.md`](#91-tag-白名单来源080) 维护；CLI init 不再向 AGENTS.md 写入
> tag 字典。老 wiki 仍含此段时由 `lint_wiki.py --check-version --apply` 自动迁移。
>
> **0.9.0+**：SSOT 模板含 `### Wiki-local scripts` 段，引用
> [`scripts/SCRIPTS.md`](#14-scripts本-wiki-仓扩展脚本目录090) 索引；CLI init 必须
> 同时在 AGENTS.md 顶部插入 `@scripts/SCRIPTS.md` import 行。
> 老 wiki 迁移仅由 workspace CLI 处理（`lint_wiki.py --check-version --apply` 不为此
> 出 legacy pattern——`scripts/` 是 opt-in 扩展，不存在不算违规）。

### AGENTS.md（SSOT）

- 路径：`<wiki-root>/AGENTS.md`
- 内容来源：本仓 `references/agents-md-template.md`（**权威 canonical 模板**）
- CLI 实现时必须**逐字拷贝**该模板，仅做以下替换：
  - `{{TOPIC_NAME}}` → 用户传入的主题名（人类可读字符串，如 `"LLM Systems"`、`"Distributed Systems"`）
  - `{{SETUP_DATE}}` → 当天日期 `YYYY-MM-DD`
  - `{{WIKI_SPEC_VERSION}}` → CLI 实现兼容的 wiki spec 版本号（语义化版本，如 `0.11.0`）
  - `{{CLI_VERSION}}` → CLI 自身版本号
- 模板顶部说明块的"本文件 ... 按 wiki-spec.md §2 拷贝生成"反向引用，CLI **不得修改**

### CLAUDE.md（薄壳）

- 路径：`<wiki-root>/CLAUDE.md`
- 内容来源：本仓 `references/claude-md-template.md`（薄壳模板，`@AGENTS.md` + 声明，≤ 30 行）
- CLI 实现时**逐字拷贝**该模板，仅替换 `{{TOPIC_NAME}}`（占主题名；不持 spec 版本——版本在 AGENTS.md §八）
- 不含纪律正文、不含 `@MEMORY` / `@scripts` import（那些在 AGENTS.md 内）；仅 `@AGENTS.md` 一行

## §3 wiki/index.md

> **维护方**：CLI 在 init 时刻按本节模板创建**初始骨架**；
> 后续所有条目变更由 **LLM agent** 在 ingest / 重写 / 归档时维护。
> CLI 不参与 index.md 的后续更新。

- 路径：`<wiki-root>/wiki/index.md`
- frontmatter（**4 字段必填**）：

| 字段 | 值 |
|---|---|
| `title` | `"<TOPIC_NAME> Index"`（带双引号） |
| `type` | `index`（无引号） |
| `okf_version` | `"0.1"`（OKF 规范版本） |
| `tags` | `[index]` |
| `created` | `YYYY-MM-DD`（= today） |
| `updated` | `YYYY-MM-DD`（= today） |

- 正文骨架：5 个空类别段（按字母序），各带一句"暂无内容"占位
- **字面量见 fixtures**：`references/fixtures/index.md.txt`

## §4 wiki/log.md

> **维护方**：CLI 在 init 时刻写入首条 setup 条目；
> 后续所有 ingest / query / lint 条目由 **LLM agent** 追加，**只 append**。
> CLI 不参与 log.md 的后续追加。

- 路径：`<wiki-root>/wiki/log.md`
- frontmatter（**4 字段必填**，同 §3 但 `type=log`、`okf_version` 不出现）：

| 字段 | 值 |
|---|---|
| `title` | `"<TOPIC_NAME> Log"`（带双引号） |
| `type` | `log` |
| `tags` | `[log]` |
| `created` | `YYYY-MM-DD`（= today） |
| `updated` | `YYYY-MM-DD`（= today） |

- 首条 log 条目（**CLI init 时刻写**）：

  ```text
  ## [<SETUP_DATE>] setup | Initial scaffold by llm-wiki-management
  ```

- **log 条目格式权威正则**（CLI 自检用，未来 lint 也用同一份）：

  ```regex
  ^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|setup) \| .+$
  ```

- 后续条目由 LLM 在 ingest / query / lint 时按相同格式追加，CLI 不必写
- **字面量见 fixtures**：`references/fixtures/log.md.txt`

### §4.1 Log rotation（防 log.md 无限增长）

> **维护方**：**LLM agent** 在 lint / 主动观察时触发；**CLI 不参与**（一次性行为，
> 无 CLI 命令语义）。本节不是"必须自动 rotate"的硬规则，是"鼓励按需 rotate"的指引。

- **触发条件**：`log.md` 条目数 ≥ `LOG_ROTATION_THRESHOLD`（按正则 `^## \[\d{4}-\d{2}-\d{2}\]` 计，不含
  frontmatter 与空白行）——此时 log 越长越难读，索引 / grep 也开始吃力
- **rotate 流程**（agent 手动）：
  1. 重命名 `wiki/log.md` → `wiki/log-YYYY.md`（YYYY = 当前年，如 `log-2026.md`）
  2. 新建 `wiki/log.md`，frontmatter 与 §4 一致；`updated` 改为今天；`created` 保留
     首次创建日不变（frontmatter 历史不被擦除）
  3. 新 `log.md` 写首条：`## [<today>] setup | Log rotation: archive → log-YYYY.md (<N> entries)`
     ——op 用 `setup`（结构事件），不动正则；title 把来源归档说清
  4. 启用 git 时走 `git mv` 重命名 + commit；未启用 git 用普通 `mv`，跳过 commit
- **保留规则**：
  - `log-YYYY.md` 一旦生成不被改写（只读归档）
  - 跨年归档可叠加（log-2025.md、log-2026.md、…）
  - 多次同年内 rotate 不重命名已归档的 `log-YYYY.md`——直接覆盖当次 `log.md`
- **lint 行为**：`lint_wiki.py` 当前**未**实现 log-rotation 自动检测；agent 在 lint
  报告末尾补一条手动建议（"log.md 已 N 条目，建议 rotate"），或后续扩展 lint 实现

## §5 MEMORY/

> **维护方**：CLI 在 init 时刻创建**空目录**并按 §5.1 写入 `MEMORY/MEMORY.md`（索引）；
> 后续 MEMORY 下的经验条目 `*.md` 由 **LLM agent** 写入，并**同步追加 MEMORY.md 索引一行**。
> 用户**不**直接编辑 MEMORY——它是 agent 私有记录。
> CLI 不参与 MEMORY 的后续写入。

- 路径：`<wiki-root>/MEMORY/`
- 目录名 `MEMORY` **大写**，区别于 `raw/` `wiki/` `wiki/index.md` 等小写目录/文件——这是为了
  在文件浏览器里一眼区分"agent 私有记忆"与"wiki 内容"
- **`MEMORY/MEMORY.md`（索引）——CLI init 时刻写入**（fixtures 字面量见
  `references/fixtures/memory-index.txt`）；被 `<wiki-root>/AGENTS.md` 用
  `@MEMORY/MEMORY.md` import，会话常驻。详见 §5.1
- 其余 `*.md` 经验条目由 LLM 在工作中追加，**文件命名与 wiki 内容页一致**；
  frontmatter 走 §5.2 的 **1 必填（`title`）+ optional 字段**规则（与 wiki 内容页 5 必填
  解耦——MEMORY 是 agent 私有，frontmatter 是可选 decoration）
  （lint 校验实现见 SKILL 仓 `scripts/lint_wiki.py`，不归本 spec）
- **MEMORY 不在 `wiki/index.md` 中强制列出**——它是 agent 私有入口，不需要 wiki 单一入口约束；
  但每条 `*.md` **必须**在 `MEMORY/MEMORY.md` 索引中列出一行（lint `memory-not-indexed` 兜底漏列）
- **条目形式按事实颗粒度选**（与仓库根 `MEMORY/MEMORY.md` 同步——见项目 `AGENTS.md` 工具规则段）：
  - **完整条目**：含上下文 / 解决步骤 / 未来如何避免 → 建 `MEMORY/<slug>.md`（走 §5.2 规则）
    - 索引行 `- <slug> — 一句话 → [正文](<slug>.md)`
  - **短条目**：一句话提醒 / 单一偏好 / 无需解释"为什么" → 索引行直接 `- 一句话事实`，
    不单独建 `.md` 文件
  - 判别尺度：需要解释"为什么这么做"或"将来怎么用" → 完整；仅作 reminder → 短
  - 短条目与完整条目可在同一 `MEMORY/MEMORY.md` 共存；lint `memory-not-indexed` 只兜底
    "有 .md 但未索引"，不强制反向（短条目无 .md，不进该检查）

### §5.1 MEMORY/MEMORY.md（索引）

- 路径：`<wiki-root>/MEMORY/MEMORY.md`
- **无 frontmatter**——它是被 `AGENTS.md` 用 `@MEMORY/MEMORY.md` import 内联的索引片段，
  不是 wiki 内容页（对齐仓库根 `MEMORY/MEMORY.md` 形态）。lint 把它当 reserved 跳过 frontmatter /
  tag / 命名校验
- 正文骨架：顶部 1 段说明（本目录用途 + 何时写 / 命名 / 纪律指向 SKILL §4，**不**重复以免口径分裂）+
  `## 索引` 段。索引行两种格式共存：
  - **完整条目**：`- <slug> — <一句话摘要> → [正文](<slug>.md)`（指向 §5.2 的 `MEMORY/<slug>.md`）
  - **短条目**：`- <一句话事实>`（无链接，对应无 `.md` 文件的索引行 reminder）
  - 判别尺度见 §5 总段「条目形式按事实颗粒度选」
- **加载机制（agent 中立）**：agent 在 wiki 根目录工作时——Claude Code 经薄壳 `CLAUDE.md` → `@AGENTS.md`
  递归展开自动加载 SSOT，`@MEMORY/MEMORY.md` 随之展开 → 索引常驻；读 `AGENTS.md` 的其他 agent
  （Qoder / Codex / Gemini CLI 等）原生读 SSOT，能否展开 `@import` 取决于实现。agent 在别处工作
  （skill 经 `$LLM_WIKI_ROOT` 读 AGENTS.md）时，`@` 不自动展开，由 SKILL 的 orient ritual 显式
  Read MEMORY.md 补齐
- **字面量见 fixtures**：`references/fixtures/memory-index.txt`（与 `references/canonical/memory-index.md`
  一致——MEMORY.md 无占位符，fixtures 与 canonical 内容相同）

### §5.2 MEMORY/*.md（非 MEMORY.md）

- 路径：`<wiki-root>/MEMORY/<slug>.md`
- 命名约束：与 wiki 内容页一致，kebab-case `^[a-z0-9][a-z0-9-]*$`
- frontmatter：**1 必填**（`title`），其余 5 字段（`type` / `created` / `updated` / `tags` /
  `description`）全 optional
  - 理由：MEMORY 是 agent 私有记忆，frontmatter 是可选 decoration——与仓库根
    `MEMORY/MEMORY.md`「短条目 1 行索引行」形态对齐；5 必填的 rationale（description
    进 index 摘要、tags 走 wiki taxonomy、updated 触发 stale 判定等）对 MEMORY
    多半不成立（见 spec §5「agent 私有」定位 + §5.2「与 wiki 内容页的区别」）
  - 若 frontmatter 含 `type`，取值需合法：5 类内容页枚举（`entity` / `concept` / `source` /
    `comparison` / `synthesis`），或 memory 扩展类型（`memory` / `memory-entry`，见下）
- `type` 取值新增 2 类 memory 扩展（与 spec §9 的「5 类内容页 + 2 类 reserved」并列）：
  - `memory`——MEMORY/*.md 自用语义，区别于 wiki 5 类内容页
  - `memory-entry`——`memory` 同义别名（lint-checklist §5.1 历史 hint 指向此名；
    兼容老 MEMORY 写法）
- lint 校验（实现见 SKILL 仓 `scripts/lint_wiki.py`）：
  - **仅 `title` 必填**；其余 5 字段全 optional
  - `type` 若取则必须合法（含 `memory` / `memory-entry`）
  - `tags` 若取则必须是 list
  - **不**走 tag 白名单校验（§9.1 taxonomy 仅约束 wiki 内容页，不渗透到 agent 私有记忆）
  - **不**走 reviewed / pending-review 校验（MEMORY 无「人工 review」语义角色）
  - `MEMORY/MEMORY.md`（索引）**不**参与此校验——本身无 frontmatter，是 AGENTS.md `@import` 的内联片段
- 与 wiki 内容页的区别：
  - **不**强制在 `wiki/index.md` 列出
  - **不**要求有 inbound 链接
  - 正文无长度上限（agent 经验沉淀可以很长）
  - LLM agent **必须**创建（user 不写）
  - **必须**在 `MEMORY/MEMORY.md` 索引列出一行（新增；lint `memory-not-indexed` 兜底）

## §6 .gitignore

CLI 必须生成一份最小 `.gitignore`，至少包含以下忽略规则：

```gitignore
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

# 外部代码仓 symlink（详见 §13）
raw/external/*
!raw/external/**/.symlink-anchor.json
```

**必须不**忽略：`wiki/`、`raw/`（除上方的 `raw/external/*` 例外）、`CLAUDE.md`、`.gitignore` 自身。

- `.gitignore` **无论是否 opt-in git 都生成**：无 git 时它是无害的空操作，且便于后续补 git；
  不因"未启用 git"而省略本文件。

## §7 Git 初始化（opt-in，默认跳过）

> **立场**：wiki **不依赖 git 即可工作**——默认落盘为**纯目录树**。git 仅在用户显式 opt-in
> （`--git`）时启用，用于版本控制 / history / diff。即便不启用 git，后续所有 ingest / query /
> lint 仍正常运行（lint 的 raw/ 不可变性检查在无 git 时自动跳过——没有 git 就没有"未提交改动"概念）。

- **默认（无 `--git`）**：CLI **完全不碰 git**——不 init、不 add、不 commit。wiki 作为纯目录树落盘。
- **opt-in（`--git`）**：CLI **同样不碰 git**——0.16.0+ 起，CLI init 仅落盘文件结构 + 打印用户侧 hint。
  **所有 git 操作由用户自行触发**（红线——CLI/agent 流程不主动操作 git）。
- **CLI 必须做的工作（init 时刻）**：
  1. 落盘目录结构（`raw/{articles,assets}/` + 5 个 wiki 内容子目录 + `MEMORY/` + `scripts/` 等）——见 §1
  2. 拷贝 SSOT 模板到 `<wiki-root>/AGENTS.md` / `CLAUDE.md` / `wiki/index.md` /
     `wiki/log.md` / `MEMORY/MEMORY.md` / `scripts/SCRIPTS.md` / `.gitignore`
  3. 在以下空目录放 `.gitkeep` 占位文件（让用户后续 `git add .` 时能跟踪到目录）：
     - **5 个 wiki 内容页子目录**（`comparisons/` `concepts/` `entities/` `sources/` `syntheses/`）——见 §1
     - **raw/articles/** 与 **raw/assets/**（CLI 默认建的 raw 子目录；见 §1）——0.15.0+ 起加入；
       此前版本未放导致 raw/ 0 tracked，`raw-modified` lint 永远 0 命中
     - **不**为用户后续自建的 raw 子目录（如 `podcasts/` `clippings/` `papers/` 等）放 .gitkeep——
       避免 CLI 预设用户没要求的目录；用户自己加（spec §6 不排除 raw/，git 能正常跟踪）

- **CLI 必须打印的 hint**（让用户知道后续 git 操作该怎么做）：

  ```text
  [INFO] wiki 已落盘为纯目录树（<wiki-root>）。
  [INFO] 若需 git 版本控制，请手动执行：
         cd <wiki-root>
         git init && git symbolic-ref HEAD refs/heads/main
         git add . && git commit -m "Initial wiki scaffold"
  [INFO] .gitkeep 占位文件已放入空目录；后续 raw/ 真实文件由你 `git add` 后纳入跟踪。
  ```

- **不得**对已存在的 git 仓误调 `git init`（与 0.16.0 前同样适用——CLI 不主动 git init，所以这一条"不得"在新流程下不再有触发机会，但保留作为反向边界）。
- **破坏性变更（0.16.0）**：CLI 不再自动 `git init` / `git symbolic-ref HEAD refs/heads/main` /
  `git config user.email` 占位值 / `git add .` / `git commit`——
  老 CLI 升级到 0.16.0+ 后，新 wiki 仓将以"纯目录树"形态落盘，用户需自行决定是否 init git。
  老 wiki 仓（CLI 0.16.0 之前 init 的）不受影响——git 仓已存在，CLI 不再主动 add/commit 不会破坏现有 history。

## §8 拒绝条件（强约束）

CLI 在以下情况必须拒绝并退出（**非零退出码**）：

| 触发条件 | 错误信息建议 |
|---|---|
| `<wiki-root>/AGENTS.md` 已存在 | `"<wiki-root>/AGENTS.md 已存在；拒绝覆盖（schema 是用户所有）..."` |
| `<wiki-root>/CLAUDE.md`（薄壳）已存在 | `"<wiki-root>/CLAUDE.md 已存在；拒绝覆盖..."` |
| `<wiki-root>/wiki/index.md` 已存在 | `"<wiki-root>/wiki/index.md 已存在；拒绝覆盖。..."` |

**绝不允许覆盖已有 wiki**。用户想重新初始化必须先手动备份 + 删除。

## §9 Frontmatter 字段全集（CLI 引用，非生成内容页）

CLI **不**生成 `wiki/{entities,concepts,sources,comparisons,syntheses}/` 下的内容页（由 LLM 在 ingest 时写）。
但 spec 必须明确字段全集，CLI 在做合规性自检（如 `init --verify`）时引用：

> **为什么是这 5 个**：5 字段是 OKF §9「字段齐全性」与 lint 校验一致性的最小交集——
> `title`（人/grep 找页）、`type`（决定子目录 + lint 校验路径）、`created` / `updated`（stale / orphan 判定）、
> `tags`（taxonomy 过滤）。少于 5 字段会让"抓腐烂"判定失效；多于 5 字段 OK 但不强制。
> 推荐 `description`（一句话摘要，`index.md` 条目摘要从它来——OKF §4.1）。

### 通用必填字段（5 项）

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | string | 人类可读标题，不含扩展名 |
| `type` | enum | 见下方 `type` 取值 |
| `tags` | array | 可空数组 |
| `created` | date | `YYYY-MM-DD`，lint 解析用 |
| `updated` | date | `YYYY-MM-DD`，lint 解析用 |

### `type` 取值（5 类内容页 + 2 类 reserved）

| `type` | 目录 | 备注 |
|---|---|---|
| `entity` | `entities/` | 实体页 |
| `concept` | `concepts/` | 概念页 |
| `source` | `sources/` | 资料页 |
| `comparison` | `comparisons/` | 对比页 |
| `synthesis` | `syntheses/` | 综合页 |
| `index` | `wiki/index.md`（唯一） | reserved，仅标记用，lint 跳过 |
| `log` | `wiki/log.md`（唯一） | reserved，仅标记用，lint 跳过 |

字母序约束与目录同：`comparison` → `concept` → `entity` → `source` → `synthesis`。

### §9.1 tag 白名单来源（0.8.0+）

`tags` 字段允许的取值集合**不在**本页规定的 type / sources 等字段里——它来自另一个非
内容页文件，避免 wiki 内容页 schema 与 tag 字典混在一起：

- **主流位置（0.8.0+）**：`<wiki-root>/wiki/tags.md`——LLM agent 拥有，**裸 bullet 列表，
  无 frontmatter**；CLI init 时刻按 `references/fixtures/` 生成空白模板，agent 在
  ingest / query 过程中自动追加新 tag
- **过渡 fallback（仅用于跨 spec 迁移期）**：`<wiki-root>/AGENTS.md` 的 `### Tag Taxonomy`
  段（0.11.0 前为 `CLAUDE.md`）——0.8.0 之前 wiki 仍可能含此段；运行 `lint_wiki.py --check-version --apply` 自动
  迁移到 `wiki/tags.md` 并删除 SSOT 中的对应段
- 解析规则、bullet 格式约束、`tag-not-in-taxonomy` lint 行为权威定义在
  [`agents-md-template.md`](agents-md-template.md)「Tag Taxonomy」段；
  SKILL 仓 `scripts/lint_wiki.py` 是实现 SSOT

**为什么从 CLAUDE.md 拆出来**：

1. 纪律 SSOT（`AGENTS.md`，0.11.0 前为 `CLAUDE.md`）是用户写的 schema "宪法"，LLM 不应编辑（见 `wiki-spec.md` §2）；tag 白名单
   是内容元数据，LLM 拥有 + 随 ingest 自动扩更合理
2. tag 字典漂移不应触发 schema 漂移告警；拆出来后 spec bump 不会因为 tag bullet 增减
   而误判老 wiki 与新 SKILL spec 不兼容
3. 与 `MEMORY/MEMORY.md`（无 frontmatter、agent 私有记忆）形态对齐——元数据不归类到
   wiki 内容页

### 类型特化字段（LLM 写内容页时使用）

| 字段 | 适用 type | 必填 | 含义 |
|---|---|---|---|
| `sources` | `source` / `synthesis` | 是 | source 页是 `raw/` 下路径数组；synthesis 页是 wiki 内其它页路径数组（**wiki 根相对**，如 `concepts/transformer.md`） |
| `aliases` | `entity` | 否 | 别名数组，方便搜索 |
| `related` | `concept` | 否 | 相关概念路径数组（**wiki 根相对**，见下方路径格式约定） |
| `compared` | `comparison` | 否 | 被对比对象路径数组（**wiki 根相对**，见下方路径格式约定） |
| `threads` | `synthesis` | 否 | 线索标题数组 |

#### 路径格式约定（0.22.0+）

frontmatter 内的路径字段（`sources` / `related` / `compared` 等指 wiki 内其它页的字段）
统一使用 **wiki 根相对路径**——以 `<wiki-root>/` 为基准的 POSIX 风格路径，不带前导
`./`、不带 `../` 跨目录引用。例：

```yaml
# wiki/concepts/self-attention.md frontmatter
related:
  - concepts/transformer.md
  - concepts/multi-head-attention.md
  - concepts/scaled-dot-product-attention.md
```

```yaml
# wiki/comparisons/transformer-vs-mamba.md frontmatter
compared:
  - concepts/transformer.md
  - concepts/mamba.md
```

裸文件名（`transformer.md`）和文件相对路径（`../concepts/transformer.md`）都**不**再
被 lint 接受——前者跨目录引用时信息不完整、lint 无法定位目标；后者与正文 Markdown 链接
约定（`AGENTS.md` §三.5，文件相对）混淆，跨目录改动时易断裂。

**为什么 frontmatter 用 wiki 根相对、与正文链接形成两层约定**：

- **frontmatter 路径字段**（`related` / `compared` / `sources` 等）——机器消费为主
  （lint 校验、cross-page 综合）；统一 wiki 根相对，**LLM 写时一次声明、跨子目录生效**，
  移动页面不会因相对路径断裂
- **正文 Markdown 链接**（`[text](path)`）——人读为主，in-context 局部引用；保持
  文件相对，**让单页可视化阅读时不依赖 wiki 根位置**

**lint 兜底**：0.22.0+ 新增 `related-broken-link`（warn 级）——校验 `related` /
`compared` 字段每条元素是否能在 wiki 根下解析到现存文件；详见
[`lint-checklist.md` §二.15](lint-checklist.md#15-related--compared-路径引用完整性0220)。

### 可选可信度与认知质量字段（LLM 按需写，全部可选）

> 语义权威定义在 SKILL 仓 [`page-templates.md`](page-templates.md) §一「可选：可信度与认知质量信号」；
> 本表只列 CLI 自检用的字段类型，不重复语义。CLI 自检不要求这些字段存在——
> `reviewed` / `reviewed_at` 是人工审核背书信号，`contested` / `contradictions` 是
> 认知冲突未裁定告警；两类正交。

| 字段 | 适用 type | 必填 | 含义 |
|---|---|---|---|
| `reviewed` | 任意内容页 | 否 | 仅 `true` 时写；人工已审核该页的可信度背书 |
| `reviewed_at` | 任意内容页 | 否 | `YYYY-MM-DD`；与 `reviewed: true` 成对出现 |
| `contested` | 任意内容页 | 否 | 仅 `true` 时写；本页含未解决的矛盾主张，需复审 |
| `contradictions` | 任意内容页 | 否 | wiki 页路径数组；与本页主张冲突的页面（双向标注） |

**生命周期规则**（LLM 必读，CLI 不强制但 CLI `--verify` 可加 `reviewed-stale` 检查）：

- LLM 创建新页不写 `reviewed` / `reviewed_at`
- 人标记已审核 → 写 `reviewed: true` + `reviewed_at: <今天>`
- LLM 修改页面正文 → **必须删除**这两个字段（戳过期，回到默认未审核）
- lint `reviewed-stale` 兜底：`reviewed: true` 存在且 `updated > reviewed_at` 时给 warn

完整 frontmatter 写法约束与 YAML 子集要求，**不在本 spec 范围内**——见 SKILL 仓的
[`page-templates.md`](page-templates.md)（LLM 写作视角，非 CLI 视角）。

**字段退役记录**：`confidence`（0.5.0 引入，0.7.0 退役）已被 `reviewed` + `reviewed_at`
替代。CLI `--verify` 在 0.7.0+ 见到 `confidence:` 字段给 `legacy-confidence-field` warn
（迁移脚本由 SKILL 仓 `lint_wiki.py --migrate-confidence` 提供）。

## §10 版本钉死

CLI 在生成 `<wiki-root>/AGENTS.md` 时，必须替换 SSOT 模板 §八 的版本占位符（薄壳 CLAUDE.md 不持版本）：

| 占位符 | 替换为 | 来源 |
|---|---|---|
| `{{WIKI_SPEC_VERSION}}` | CLI 当前兼容的 wiki spec 版本（如 `0.1.0`） | CLI 实现时 bundled copy spec 时硬编码，或运行时 fetch SKILL 仓 `metadata.wiki_spec_version` |
| `{{CLI_VERSION}}` | CLI 自身版本号 | CLI 仓 `__version__` 或 `pyproject.toml` / `package.json` 的 version 字段 |

spec 版本号约定在 SKILL 仓 `SKILL.md` 的 `metadata.wiki_spec_version` 字段声明（如 `0.1.0`）。
CLI 仓与 spec 版本对齐是 CLI 仓的责任；spec 变更时 SKILL 仓升 `wiki_spec_version`，
CLI 仓跟随升级。

**LLM 在每次操作前比对** AGENTS.md §八（老 wiki 无 AGENTS.md 时 fallback CLAUDE.md §八）的 "Wiki Spec 版本" 与 SKILL.md
`metadata.wiki_spec_version`；不一致时**警告用户**（不阻断——CLI 可能支持多个 spec 版本）。

## §11 命名约束（影响 CLI 生成的产物）

| 维度 | 规则 | 适用对象 |
|---|---|---|
| 文件名 kebab-case | `^[a-z0-9][a-z0-9-]*$` | `wiki/{entities,concepts,sources,comparisons,syntheses}/*.md` + `MEMORY/*.md`（index/log/tags/MEMORY.md 除外） |
| 子目录名 | 固定字母序（§1） | 5 个内容页子目录 |
| 特殊目录名 `MEMORY` | **大写**（区别于小写 `raw` / `wiki` 等）；与 `wiki/` 平级（不再嵌在 `wiki/` 下） | `<wiki-root>/MEMORY/` |
| 元数据文件 tags.md（0.8.0+） | 与 index.md / log.md 同——**无** frontmatter，裸 Markdown；lint 不走 frontmatter 校验（按 `MEMORY.md` 同形态） | `wiki/tags.md` |
| 索引文件 SCRIPTS.md（0.9.0+） | 与 tags.md / MEMORY/MEMORY.md 同——**无** frontmatter，裸 Markdown；AGENTS.md `@` import 目标 | `scripts/SCRIPTS.md` |
| frontmatter 字段名 | 严格小写 + 下划线（`okf_version`、`created`、`updated`） | 所有 frontmatter |
| frontmatter `type` 值 | 严格小写（5 类内容页 + 2 类 reserved：`index`/`log`） | 所有 wiki 页 |

CLI 生成的产物必须满足以上规则；否则后续 lint 会立即报错。

## §12 不在本 spec 范围内

以下事项 CLI 实现不必关心（属于 SKILL 仓的"运行时规则"，不在落盘契约里）：

- raw/ 是否 LLM 只读、用户可改的纪律
- ingest / query / lint 的工作流
- frontmatter 字段的语义（如 `description` 推荐写法）
- 类型特化字段的内容（如 `aliases` 写什么）
- 跨页交叉引用的语义
- 半定性 lint（矛盾、缺失交叉引用等）
- 是否使用 Obsidian / 编辑器偏好

## §13 raw/external/——外部代码仓接入（可选）

> **维护方**：**用户**。CLI 不创建也不管理；用户通过 LLM agent 协助或自行用
> `ln -s` + 手写/追加 `.symlink-anchor.toml` 接入。
>
> **0.17.0 变更（破坏性）**：anchor 从「每仓一份 `<source-name>/.symlink-anchor.json`
> （JSON object）」改为「单文件 `external/.symlink-anchor.toml`（TOML
> array-of-tables）」。老的 `<source-name>/` 子目录层已废弃——见 §13.6 迁移指南。

外部代码仓（如 Linux kernel、Ray 源码）作为原始语料纳入 wiki 时，**不**做仓库内嵌
拷贝（避免占用空间 + 失去 commit 锚点），而是走 **symlink + 锚定元数据**：

### §13.1 路径约定（0.17.0+）

```text
<wiki-root>/raw/external/
├── .symlink-anchor.toml           # 必填：TOML，[[entry]] 数组描述所有外部仓
├── linux-kernel                     # symlink → ~/src/linux-kernel
├── ray                              # symlink → ~/src/ray
└── ...
```

- **扁平结构**：所有外部仓的 symlink 直接放在 `raw/external/` 下，**不再**用
  `<source-name>/` 子目录分组。anchor 文件**单文件**记录所有 entries。
- **symlink 命名**：必须 kebab-case `^[a-z0-9][a-z0-9-]*$`（与 wiki 内容页命名一致）
- **anchor 文件位置**：固定 `<wiki-root>/raw/external/.symlink-anchor.toml`
- **anchor ↔ symlink 关联**：每个 `[[entry]]` 的 `symlink` 字段对应 `raw/external/`
  下同名的 symlink 文件；该 symlink 缺失 → lint 报 `external-symlink-missing`；
  反之 anchor 中没记录该 symlink → lint 报 `external-anchor-orphan`
- 同一 target 的多个 subpath：直接创建多个 symlink（每个 symlink 一行 entry），
  不需要再用 `subpath` 字段间接表达（`subpath` 在 0.17.0 已废弃）

### §13.2 `.symlink-anchor.toml` Schema（必填 + git 仓扩展字段）

**顶层 `schema_version`（可选，推荐）**：`schema_version = 1`——为未来 schema 演进留口子。

**顶层 `[[entry]]` 数组**——每个元素描述一个外部仓：

```toml
schema_version = 1

# linux-kernel 仓
[[entry]]
symlink = "linux-kernel"           # 对应 raw/external/linux-kernel symlink
target = "~/src/linux-kernel"      # 推荐 ~/... home-relative（0.14.0+）
captured_at = "2026-07-07"         # 接入当天
kind = "external-repo"             # 当前唯一支持的 kind
remote_url = "https://github.com/torvalds/linux.git"  # git 仓必填
commit = "f1f2f3f4f5f6"            # git 仓必填，完整 SHA
branch = "master"                  # git 仓必填

# ray 仓
[[entry]]
symlink = "ray"
target = "~/src/ray"
captured_at = "2026-07-05"
kind = "external-repo"
remote_url = "https://github.com/ray-project/ray.git"
commit = "a1b2c3d4e5f6"
branch = "master"

# notes 字段可选
[[entry]]
symlink = "my-til"
target = "~/src/my-til"
captured_at = "2026-07-01"
kind = "external-repo"
notes = "个人 TIL 仓库，按需重 ingest"
```

**每 entry 最小必填 4 字段**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `symlink` | kebab-case string | 是 | 对应 `raw/external/` 下同名的 symlink 文件名 |
| `target` | string（绝对路径 **或** `~/...` home-relative 形式） | 是 | 推荐 `~/src/<name>` 形式以跨主机可移植；**也接受** `readlink -f <symlink>` 输出的绝对路径（兼容 0.14.0 前的 anchor）。lint 在判定前统一 `Path(target).expanduser()` 展开——绝对路径展开后不变，`~/...` 展开为 `$HOME/...` |
| `captured_at` | date `YYYY-MM-DD` | 是 | 用户接入当天；用于提示"target 路径多久前定锚" |
| `kind` | enum | 是 | 当前仅支持 `"external-repo"`；预留给以后扩展（`"snapshot"` 等） |

**git 仓扩展字段**（当 `target` 指向 git 仓时**强制**——见 §13.5）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `remote_url` | string | git 仓时必填 | `git -C <target> remote get-url origin` 输出；用于跨主机重建时 `git clone` |
| `commit` | string（完整 SHA） | git 仓时必填 | `git -C <target> rev-parse HEAD` 输出；用于 `git checkout` 到具体版本 |
| `branch` | string | git 仓时必填 | `git -C <target> rev-parse --abbrev-ref HEAD` 输出；辅助识别漂移 |

**可选字段**（任何场景都不强制）：`tag`（如果 `commit` 是某个 tag 而非分支头）、
`notes`（自由文本，记录接入原因）。**`subpath` 已废弃**（0.17.0+）——直接创建多
symlink 表达即可。

> **为什么 target 字段允许 `~/...` 而不是硬要求绝对路径**（0.14.0+）：`target` 字段
> 进 git，但**不**必须是机器相关绝对路径——推荐写 `~/src/<name>` 形式
> 让同 home 布局的多机共享同一 anchor；`~/...` 跨 home 布局失效时降级到
> `remote_url` / `commit` / `branch` 三字段重建（详见 `external-repo-rebuild.md`）。
> lint 端用 `Path(target).expanduser()` 统一展开，**不**关心 anchor 写哪种形式。
>
> **为什么选 TOML 而不是 JSON**（0.17.0+）：① 支持 `# ...` 注释——LLM / 用户
> 手写时易读、易解释每段含义；② `[[entry]]` array-of-tables 是表达「多 entry」的
> 原生 TOML 语法，比 JSON array + 每个 entry 重复字段名更紧凑；③ 与项目既有
> `workspace.toml` / `wiki_metadata.toml` 风格一致；④ Python 3.11+ `tomllib` 解析，
> 零运行时依赖。

### §13.3 责任切分（用户 + LLM 共有）

**用户责任**：

- 决定**接入哪些**外部代码仓（意图层面）
- symlink target 的存活——target 被删除 / 改名 / 移动后 anchor 仍记录
  旧路径，lint 报 `external-target-dead` 让用户感知
- 更新 anchor 的时机：当用户主动 `git pull` / 切换 commit / 重命名分支后，
  LLM 会在 lint 报 `external-git-anchor-stale`，用户确认后由 LLM 重写 anchor

**LLM agent 责任**（首次接入 + 漂移刷新）：

- **创建 symlink + 追加 entry**——当用户说"把 X 仓纳入 wiki"时，LLM 主导：
  1. 与用户确认 symlink 名（如 `linux-kernel`）+ target 路径
  2. 验证 target 是 git 仓（`git -C <target> rev-parse --is-inside-work-tree`）
  3. 读 `remote_url` / `commit` / `branch` 三个值（git 命令）
  4. `mkdir -p raw/external && ln -s <target> raw/external/<symlink>`（**扁平**，
     不要在 `external/<source-name>/` 下再开子目录）
  5. **读**现有 `.symlink-anchor.toml`（如有）；**追加**新 `[[entry]]` 块；
     **写回**整个文件；首次创建则写完整文件含 `schema_version = 1` 顶层字段
- **更新 entry 的 `target` 字段**（重建到新主机时——见 `external-repo-rebuild.md`）
- **不**修改 target 本身（外部仓是用户所有；LLM 不在仓内跑 `git pull` 之类）
- **不**编辑 `raw/external/` 之外的 `raw/` 子树（articles / papers / assets /
  clippings 等仍走"LLM 只读"纪律）
- lint 报 `external-anchor-missing` / `external-anchor-corrupt` /
  `external-anchor-orphan` / `external-symlink-missing` 时由 LLM 引导用户重写
- **`sources:` 元素类型（0.20 澄清）**——`raw/external/<symlink>/...` 形式的
  sources 可指向**文件或目录**：symlink 目标本身是 git 仓（即目录），可用作整仓
  语料（`raw/external/<symlink>`）；也可指向仓内子路径（文件或子目录）。lint
  仅校验可访问性（`sp.exists()`），不做 file-only 约束。普通 raw 路径（非
  `raw/external/`）的 sources 仍要求指向**文件**（lint 用 `is_file()` 校验）——
  raw 子树语义是"已 ingest 的文档"，目录型 raw 来源暂无用例

> **为什么改"LLM 不写"为"LLM 主导接入"**：外部代码仓接入是结构化操作
> （固定 schema + 固定 git 命令序列），由 LLM 主导可避免用户手动跑
> `ln -s` + 手写 anchor 时出错；范围**仅**限 `raw/external/`，其他
> `raw/` 子树仍只读。

### §13.4 .gitignore 增强

`.gitignore` 在 §6 的基础上追加以下规则（CLI init 时一并生成）：

```gitignore
# 外部代码仓 symlink 接入（不跟踪 symlink 本身，但保留 anchor 元数据）
raw/external/*
!raw/external/.symlink-anchor.toml
```

> **理由**：symlink 会被 git 当成 symlink 记录（指向一个不可解析的 target，在另一台
> 机器 clone 时毫无意义），但 `.symlink-anchor.toml` 是真实文件、记录"接入意图"——
> `!` 否定号让 anchor 文件被跟踪。跨机器 clone 后：
>
> - **同 home 布局**（`target: "~/src/..."` 形式，0.14.0+ 推荐）：lint 把 `target`
>   展开为当前 `$HOME/src/...`，symlink 重新创建后即可用；lint 不报 `external-target-dead`
> - **跨 home 布局**（如 macOS `/Users/foo` vs Linux `/home/foo`）：lint 报
>   `external-target-dead`，LLM 读 anchor 的 `remote_url` / `commit` 重建
>   （见 `external-repo-rebuild.md`）
> - **老 wiki 兼容**：0.14.0 之前的 anchor 写的是绝对路径，跨机器时
>   `expanduser` 展开后不变，仍会 `external-target-dead`，走重建协议

### §13.5 git 仓锚定要求（lint 强制）

当某个 entry 的 `target` 字段经 `Path(target).expanduser()` 展开后**在 git 仓内**
（`git -C <expanded-target> rev-parse --is-inside-work-tree` 返回 `true`）时：

- 该 entry **必须**含 `remote_url` / `commit` / `branch` 三字段（缺一即
  `external-git-anchor-incomplete`，lint 报 **error**）
- lint 跑 `git -C <expanded-target> remote get-url origin` / `rev-parse HEAD` /
  `rev-parse --abbrev-ref HEAD`，与 anchor 同名字段对比，**任一不一致**即
  报 `external-git-anchor-stale`（**warn** 级，提醒用户刷新 anchor）
- `target` 不在 git 仓内（如手动下载的源码包、未初始化的目录）时，三字段
  全部可选，lint 跳过 git 校验

> **为什么 git 仓必须强制 3 字段**：anchor 是 wiki 重建外部源代码的**唯一**
> 信息源——symlink 不进 git、target 路径（无论绝对或 `~/...`）在跨 home 布局的
> 机器上仍可能失效——若三字段缺失，跨机器 clone 后无法重建出"用户接入瞬间"
> 的精确 commit。lint 实时校验防止 anchor 因用户日常 `git pull` 漂移而失去
> 重建能力。

### §13.6 从 0.16.0 迁移到 0.17.0（破坏性变更）

`lint_wiki.py --check-version --apply` **不**自动迁移——迁移需 LLM agent 主动跑
（结构差异太大，自动迁移易出错）。规则：

**老结构**（0.16.0-）：

```text
raw/external/
└── <source-name>/
    ├── .symlink-anchor.json    # 单 JSON object: target / captured_at / kind / git 字段
    └── <symlink> → <target>
```

**新结构**（0.17.0+）：

```text
raw/external/
├── .symlink-anchor.toml        # 顶层 [[entry]] 数组
├── <symlink>                   # symlink → <target>
└── ...
```

**迁移步骤**（LLM agent 跑）：

1. 扫 `raw/external/<source-name>/` 子目录；对每个子目录：
   - 读 `<source-name>/.symlink-anchor.json` 拿到 `{target, captured_at, kind, ...}`
   - 找出 `<source-name>/` 下所有 symlink（每个 symlink 都对应一条 entry）
   - 对每个 symlink `<name>`：
     - `mv <source-name>/<name> <name>`（移 symlink 到 `external/` 顶层；如新位置已有同名
       symlink / 文件冲突，提示用户改名后再迁）
     - 把 anchor 数据 + 新 `symlink = "<name>"` 字段塞进 `[[entry]]` 块
   - 删除 `<source-name>/` 目录 + 旧 `.symlink-anchor.json`
2. 写新 `raw/external/.symlink-anchor.toml`（含 `schema_version = 1` + 所有 entry 块；
   按 symlink 名字典序排版，便于 git diff 阅读）
3. Edit `<wiki-root>/AGENTS.md` §八「Wiki Spec 版本」行改为 `0.17.0`
4. **不**追加 log 条目（迁移是脚本运行，不是 wiki 操作事件）
5. 重跑 `lint_wiki.py` 验证（不应再报 `external-anchor-missing` 等 0.16.0 形态的 finding）

迁移期间无新工具支持——LLM agent 按上述规则手工 Edit / 落盘即可。

---

## §14 scripts/——本 wiki 仓扩展脚本目录（0.9.0+）

> **维护方**：CLI 在 init 时刻**始终创建** `scripts/` 目录 + 拷贝空 `SCRIPTS.md`
> 骨架（参考 `references/fixtures/scripts.md.txt`）；后续**用户 + LLM agent 共有**
> ——用户可手写 / LLM agent 可补——只要维持 `SCRIPTS.md` 索引同步。

### §14.1 设计动机

- skill 自带脚本（`scripts/lint_wiki.py` / `ingest_diff.py` / `log_format.py`）
  满足**通用**wiki 工作流；本 wiki 个性化的扩展（批量 PDF prep、特定主题的
  ingest 模板、外部 CLI 胶水、自动 hook）**不**适合 ship 进 skill 仓
- 走**用户/项目级别**就地维护——既享受 git tracking 又不被 skill 版本约束

### §14.2 路径约定

```text
<wiki-root>/scripts/
├── SCRIPTS.md                  # 必填：索引；AGENTS.md 用 @scripts/SCRIPTS.md import
└── <user scripts>              # 任意文件名 / 嵌套子目录（按工具性质自组织）
```

- **路径**:顶层 `<wiki-root>/scripts/`,与 `raw/` `wiki/` 同级
- **不**为 scripts/ 预创建空 `.gitkeep`——目录由 CLI 必须创建(避免"目录存在但空"
  的歧义;若用户 opt-in git,`SCRIPTS.md` 是真实文件足以让目录被 git 跟踪)
- 子目录 / 文件命名**不限**(`foo.py` / `pdf-prep.sh` / `hooks/pre-commit.sh`
  / `batch/N-papers/main.py` 都可)——scripts/ 不是 wiki 内容页,不走 §11 kebab-case 约束

### §14.3 索引 `SCRIPTS.md`(AGENTS.md `@` import 目标)

- **文件名**:`SCRIPTS.md`(大写,镜像 `MEMORY/MEMORY.md` "目录专属索引" 命名模式)
- **路径**:`<wiki-root>/scripts/SCRIPTS.md`
- **形态**:**无 frontmatter**(与 `MEMORY/MEMORY.md` 同),纯 Markdown
- **骨架**(CLI init 时刻拷贝):

  ```markdown
  # Scripts

  > 本目录存放本 wiki 自维护的脚本（项目级 ingest 扩展 / 外部 CLI 胶水 / 自动化 hook）。
  > 索引文件被 `<wiki-root>/AGENTS.md` 用 `@scripts/SCRIPTS.md` import 会话常驻;
  > 新增 / 修改 / 删除脚本必须同步更新本索引段，否则 agent 视为不可见。
  >
  > 何时写 / 编排纪律见 SKILL §核心原则 §12（本文件不重复，避免口径分裂）。

  ## 索引

  <!-- 每工具一段：## <name> — <short label> + 使用场景 + 调用约定 + 作用 -->
  （暂无脚本 —— 在此追加 ## <name> — <label> 段）
  ```

- 字面量模板进 `references/fixtures/scripts.md.txt`(CLI init 拷贝)
- **无**占位符——SCRIPTS.md 是 AGENTS.md 上下文里的"内部索引",与 `MEMORY/MEMORY.md`
  / `wiki/tags.md` 同族(均无 frontmatter、wiki 名由 AGENTS.md §1 承载,SCRIPTS.md
  不重复)

### §14.4 每工具一段的契约(LLM / 用户共同维护)

每条 `## <name> — <label>` 段必含 4 个要素(顺序任意;lint 不解析但风格一致):

| 要素 | 例子 | 用途 |
| --- | --- | --- |
| **使用场景** | "用户给出 N 个 PDF 想一次摄取; 或 `ingest_diff.py` 返回 ≥ 3 个 untracked" | agent 触发条件(口吻匹配"何时该调") |
| **调用约定** | `python3 scripts/<name>.py "$LLM_WIKI_ROOT" [args]` | 一行可粘贴,假设 `$LLM_WIKI_ROOT` 在调用环境 |
| **作用** | "本脚本做一次聚合 ingest:per-N 调一次 ingest,完成后用 `--bulk-rebuild-index` 一次性更新" | 解释做什么、产出什么、副作用范围 |
| **前置依赖**(可选) | "需 `pip install pypdf`;需环境变量 `PAPERS_DIR`" | 显式声明非标依赖,避免 agent 误跑 |

### §14.5 纪律(硬化约束)

- **git**:默认跟踪(显式 opt-in `--git` 时 commit;不 opt-in 时跟 wiki 同走纯目录树);
  §6 `.gitignore` 模板**不**额外排 `scripts/` ——不写例外规则
- **frontmatter**:**不**写——scripts/ 是代码,非 wiki 内容页(`scripts/*.py` 走 PEP 723
  inline metadata 或 shebang,不由本 spec 规定)
- **lint**:scripts/ **不**参与 `lint_wiki.py` 扫描(`find_md_files` 自然不递归
  `scripts/`,且 §9 5 必填只对 `wiki/{entities,concepts,sources,comparisons,syntheses}/*.md`
  与 `<wiki-root>/MEMORY/*.md`（0.10.0+ 移到 wiki/ 外）走）——脚本的代码质量由用户 / agent 自行负责,
  不在 SKILL 范围内
- **可执行权限**:`.sh` 必须 `chmod +x`(CLI 不批量 chmod,免得给用户跑陌生 binary
  留通道);`.py` 走 `python3 scripts/<name>.py` 不依赖 +x
- **不安全默认**:agent **不会自动遍历** `scripts/` 跑任何东西——必须先 `Read` SCRIPTS.md
  找到对应段,再显式调用。SCRIPTS.md 是唯一的"我知道有谁"通道,**防止意外执行**
- **SCRIPTS.md 更新纪律**:"添加 / 修改 / 删除脚本文件" 与 "同步更新 SCRIPTS.md" 是
  原子动作——stub 段先写还是脚本文件先写由维护者决定,但**完成时两者必须同时一致**

### §14.6 与已有索引模式对照

| | `MEMORY/MEMORY.md` | `wiki/tags.md` | `scripts/SCRIPTS.md` (本) |
| --- | --- | --- | --- |
| import 方式 | `@MEMORY/MEMORY.md` | `@wiki/tags.md` | `@scripts/SCRIPTS.md` |
| 形态 | 无 frontmatter | 无 frontmatter | 无 frontmatter |
| 维护方 | LLM agent | LLM agent(用户审计) | 用户 + LLM agent |
| 何时引入 | §5 (0.2.0) | §9.1 (0.8.0) | §14 (0.9.0) |
| 列举对象 | 一行一条 MEMORY 条目 | 一行一条 tag | 一段一条工具 |
| 类别 | 知识 | 标签白名单 | 代码索引 |

### §14.7 老 wiki 迁移(对照 §10 升级路径)

升级至 0.9.0 后 CLI 需补的动作(由 workspace CLI 负责,**不**属本 skill 范围):

1. 创建 `scripts/` 目录
2. 拷贝 `references/fixtures/scripts.md.txt` 到 `scripts/SCRIPTS.md`（无占位符,直接落盘）
3. 在 `<wiki-root>/AGENTS.md` 顶部加入 `@scripts/SCRIPTS.md` import 行（0.11.0+：import 归属 AGENTS.md）
   (参考 §2 模板 `### Wiki-local scripts` 段)
4. **不**对老 wiki 自动创任何脚本文件(避免污染用户目录)

`lint_wiki.py --check-version --apply` 不为此出 legacy pattern——scripts/ 是 opt-in
扩展,**不**存在不算违规。

---

## 附录 A：CLI 实现自检建议

CLI 在生成完成后，可执行以下验证：

1. **字节级对比(渲染后)**:CLI 用锚点 mapping (`TOPIC_NAME="Test"`, `SETUP_DATE="2026-06-28"`) 渲染,
   产物与本仓 `references/canonical/` 下对应文件**逐字一致**。
   canonical/ 目录由本仓在每次 fixture 变更时手工生成(SKILL 仓 owner 操作)。
2. **正则自检**：生成的 `wiki/log.md` 首条条目匹配 §4 正则
3. **frontmatter 解析**：生成的 `wiki/index.md` / `wiki/log.md` 能被
   `scripts/ingest_diff.py` 的 `parse_frontmatter_simple()` 正确解析（MEMORY.md 无 frontmatter，不在此列）
4. **结构自检**：5 个内容页子目录 + `MEMORY/` 全部存在；MEMORY 目录含 MEMORY.md
5. **lint 跑通**：生成的 wiki 仓跑 `scripts/lint_wiki.py` 应返回 exit code 0

## 附录 B：版本历史

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| 0.22.0 | 2026-07-11 | **related / compared frontmatter 路径格式约定（wiki 根相对）+ 新增 `related-broken-link` lint check（warn）**——`wiki-spec.md §9`「类型特化字段」表 `related` / `compared` 行明确路径格式约定：**wiki 根相对路径**（如 `concepts/transformer.md`），裸文件名（`transformer.md`）与文件相对路径（`../concepts/transformer.md`）均不再被接受。新增 `§9 路径格式约定`段说明两层约定区分——frontmatter 路径字段（机器消费为主，wiki 根相对、跨子目录不丢信息）vs 正文 markdown 链接（人读为主，文件相对、in-context 局部）。`scripts/lint_wiki.py` 新增 `check_related_links()` 扫 `related` / `compared` 字段每条元素，按 wiki 根相对解析，`is_file()` 判定；不命中 → 报 `related-broken-link`（warn）——与正文 `broken-link`（error）严重性区分开（frontmatter 是机器消费、非人直接阅读内容）。`references/lint-checklist.md` 新增 §二.15 段；`severity_of()` 加 `related-broken-link → warn` 映射。`references/page-templates.md` concept / comparison 模板示例同步更新为 wiki 根相对路径。**非破坏性**：`related` / `compared` 字段为可选（spec §9「必填」列均为否），缺字段的 wiki 升级零影响；已有的裸文件名 / 文件相对路径 wiki 升级后会一次性报出所有 `related-broken-link` warn，由用户批量改写为 wiki 根相对形式。`contradictions` 字段按 spec §9 既有约定**保留**文件相对解析（与 `related` / `compared` 两层区分是有意保留），不在本检查范围。SKILL.md `metadata.wiki_spec_version` + `scripts/lint_wiki.py` `CURRENT_WIKI_SPEC` 升至 0.22.0 |
| 0.21.0 | 2026-07-11 | **raw/external/ sources 允许指向目录（bug fix）**——`scripts/lint_wiki.py` `check_sources_field` external 分支（第 657 行）由 `sp.is_file()` 改为 `sp.exists()`：external repo 本身是 git 仓（即目录），`sources: [raw/external/<symlink>]` 语义合法；原 `is_file()` 对目录返回 `False` 导致误报 `sources-missing`。finding 消息由「文件不可访问」改为「路径不可访问」。普通 raw 路径（非 `raw/external/`）的 sources 仍要求指向**文件**——raw 子树语义是「已 ingest 的文档」，目录型 raw 来源暂无用例。spec §13.3「LLM agent 责任」补 `sources:` 元素类型澄清（文件或目录皆可，仅 external 分支）；`references/lint-checklist.md` §二.3 step 4 措辞同步。**非破坏性**：合规 0.20.0 wiki 升级 = bump AGENTS.md §八版本号即可，无内容改动；之前因 external sources 指向整仓而误报 `sources-missing` 的页面升级后自动消失。SKILL.md `metadata.wiki_spec_version` + `scripts/lint_wiki.py` `CURRENT_WIKI_SPEC` 升至 0.21.0 |
| 0.20.0 | 2026-07-08 | **fixtures 字段级骨架比对 + 常规 lint 版本检查 + 升级末尾清理**——`check_wiki_fixtures.py` 从 11 条扩到 **18 条** check：新增 7 条骨架字段比对（`gitignore-init-rules-complete` / `index-md-frontmatter-complete` / `index-md-skeleton` / `log-md-frontmatter-complete` / `memory-index-skeleton` / `scripts-md-skeleton` / `tags-md-skeleton`），读 `references/canonical/` + `references/fixtures/gitignore.txt` 作 **SSOT** 做字段级骨架比对（改 fixtures → check 自动跟随）：纯骨架件（.gitignore / tags.md / SCRIPTS.md / MEMORY.md）全字段骨架比对，成长件（index.md / log.md）只比结构必填（frontmatter 键 + H1 + 说明块），**不动成长内容**。`build_migration_plan()` 新增 `fixtures-fix-skeleton` 通用 action 类型（匹配 `*-skeleton` / `*-frontmatter-complete` / `*-init-rules-complete` cid，`to_action` 引用 expected 缺失项）。常规 lint 新增 `check_spec_version()`——每次 lint 查 AGENTS.md §八版本与 `CURRENT_WIKI_SPEC` 一致性，落后 / 领先给 warn 提示走 `--check-version` 升级（finding `wiki-spec-version-stale` / `-ahead` / `-unparsed`）。升级流程末尾新增「清理临时文件」步（删 `.migration-plan.json` + `*.bak`）。`fixtures/gitignore.txt` 加 `.migration-plan.json`（升级中间产物，用完即删 + 不进 git）。**纯检测覆盖增量，无文件格式变更**：合规的 0.19.0 wiki 升级 = bump AGENTS.md §八版本号即可，无内容改动；缺骨架字段的老 wiki 才首次收到 `fixtures-fix-skeleton` action。SKILL.md `metadata.wiki_spec_version` + `scripts/lint_wiki.py` `CURRENT_WIKI_SPEC` 升至 0.20.0；`SKILL.md` §0.18.0+ 段 + §5 Migrate + `references/migrate-workflow.md`（新增「fixtures 字段更新清单」节 + step 8 清理）+ `references/lint-checklist.md`（§二前置版本检查 + §八边界）+ `scripts/check_wiki_fixtures.py` docstring 同步 |
| 0.19.0 | 2026-07-08 | **MEMORY frontmatter 解耦 + raw/external/ sources 例外**——`scripts/lint_wiki.py` `check_frontmatter` 拆分为两段：wiki 5 类内容页保留 5 必填（`title`/`type`/`created`/`updated`/`tags`），**MEMORY/*.md 改为仅 `title` 必填**（其余 5 字段全 optional——spec §5「agent 私有」定位 + 与短条目「1 行索引行」形态对齐）。`VALID_TYPES` 扩展 `memory` / `memory-entry` 两类（spec §5.2 + §9）；`check_reviewed_signals` 与 `check_tag_taxonomy` 的 `target_pages` 不再含 MEMORY 桶（MEMORY 是 agent 私有，不走 wiki 用户面 reviewed 校验 + 不共享 tag taxonomy）。`check_sources_field` 加 `raw/external/<symlink>/...` 例外分支（spec §13.3）：`.resolve()` 后落 wiki 根外是 symlink 预期行为，改为校验 anchor + symlink 存在 + 文件可访问；新增 finding `sources-external-anchor-missing` / `sources-external-symlink-missing` / `sources-malformed`。**破坏性**：`type: memory` / `type: memory-entry` 在 MEMORY/*.md 上从「非法」变「合法」（无需迁）；5 必填 MEMORY 老页面继续合法（不强制减字段）；wiki 5 类内容页规则不变。SKILL.md `metadata.wiki_spec_version` + `scripts/lint_wiki.py` `CURRENT_WIKI_SPEC` 升至 0.19.0；`references/lint-checklist.md` §5.1 / §二.2 / §二.3 / §二.11 / §二.13 / §九.1 + `references/page-templates.md` §一 + `references/wiki-spec.md` §5.2 全部同步重写对齐新口径 |
| 0.18.0 | 2026-07-07 | **fixtures 一致性检查能力增量**——`--check-version` 自动调一次 `scripts/check_wiki_fixtures.py`，扫 wiki 约定文件（AGENTS.md §八版本行 / .gitignore / wiki/index.md / wiki/log.md / wiki/tags.md / MEMORY/MEMORY.md / scripts/SCRIPTS.md / raw/external/.symlink-anchor.toml）是否满足当前 wiki spec 的字节合规，并入 report["fixtures_check"]；`build_migration_plan()` 新增 `fixtures_actions[]` 数组（与 legacy `actions[]` 平行；type 前缀 `fixtures-fix-*`，含 `expected`/`actual`），落 `.migration-plan.json` 供 agent 走 Edit/Write 修约定文件。**11 条** check：agents-version-is-current / gitignore-external-track-toml / symlink-anchor-toml-schema / symlink-anchor-toml-symlink-matches / symlink-anchor-flat-not-legacy / index-md-categories-stable / memory-index-no-frontmatter / memory-entries-indexed / log-md-format-strict / scripts-md-no-frontmatter / tags-md-no-frontmatter。`fixtures-fix-anchor-merge / -anchor-schema / -anchor-symlink-matches` 三条按 `lint-checklist.md` §五.3 五步迁移（不是单 Edit）——其余可单 Edit 落。**语义合并规则**落到 `references/lint-checklist.md` §五（frontmatter 合并 / index 重复条目 / 0.16.0 → 0.17.0 anchor 多 entry 归并 / MEMORY supersede 等），由 LLM 按该规则人工合并——scripts/ 不替代语义判断（脚本只产 plan）。SKILL.md `metadata.wiki_spec_version` 升至 0.18.0；`SKILL.md` §1 交付物 + §5 Migrate + 「输入 / 输出」 + 「四个核心操作」段加 fixtures-check 描述；`scripts/lint_wiki.py` `CURRENT_WIKI_SPEC` 升至 0.18.0 + `_run_fixtures_check()` 新增（subprocess 调 check_wiki_fixtures.py + 解析 JSON）+ `build_migration_plan()` 新增 `fixtures_actions` 落盘 + `_print_fixtures_check()` 新增 |
| 0.17.0 | 2026-07-07 | **§13 raw/external/ 扁平化 + anchor 改 TOML**：anchor 从「每仓一份 `<source-name>/.symlink-anchor.json`（JSON object）」改为「单文件 `external/.symlink-anchor.toml`（TOML array-of-tables，支持注释）」——所有外部仓的 symlink 直接放在 `raw/external/` 下、共享一份 anchor。`[[entry]]` 数组每元素含 `symlink` / `target` / `captured_at` / `kind` 必填 + git 扩展字段（git 仓时必填）+ `tag` / `notes` 可选；顶层 `schema_version = 1` 可选。**破坏性变更**：0.16.0- 老 wiki 跑 `lint_wiki.py` 会报 `external-anchor-missing`（旧 `<source-name>/.symlink-anchor.json` 不再被识别）——LLM agent 按 §13.6 迁移指南手工 Edit/Write 升级（`--check-version --apply` 不为此自动迁移，结构差异太大）。SKILL.md `metadata.wiki_spec_version` 升至 0.17.0；`scripts/lint_wiki.py` `check_external_symlinks` + `_parse_anchor` + `_check_git_anchor` 全部重写——`tomllib`（py3.11+）解析、entry 级 git 字段校验、新增 finding `external-anchor-orphan`（warn：symlink 存在但 anchor 无 entry）/ `external-symlink-missing`（error：anchor 有 entry 但 symlink 不在 `external/` 顶层）/ `external-source-name-invalid`（error：symlink 命名不合 `^[a-z0-9][a-z0-9-]*$`）。`agents-md-template.md` §一 / `external-repo-rebuild.md` / `lint-checklist.md` / `SKILL.md` §1.bulk + 核心原则 + 边界 + 反模式 / `references/fixtures/gitignore.txt`（`**/.symlink-anchor.json` → `.symlink-anchor.toml`）同步对齐扁平形态。`subpath` 字段退役——直接创建多 symlink 表达 |
| 0.16.0 | 2026-07-07 | **红线贯彻：CLI 撤掉全部 git 操作**——§7 重写。CLI init 仅落盘目录结构 + touch .gitkeep + 打印 hint，**完全不碰 git**（不 `git init` / `git symbolic-ref` / `git config` / `git add` / `git commit`）。**根因**：0.16.0 前 CLI 在 `--git` opt-in 时自动跑 `git init` + `git symbolic-ref HEAD refs/heads/main` + `git config user.email` 占位 + `git add .` + `git commit`，违反"所有 git 操作由用户触发"红线。CLI 主动 git init 还会让 raw/ 整体 0 tracked 等问题被"假提交"掩盖（init 时仓是空的，commit 后 raw/articles/ + raw/assets/ 仍是空目录、靠 0.15.0 的 `.gitkeep` 占位才进 git，但前提是 CLI 真做了 git add）。CLI 退回纯落盘后，**用户**看到 wiki 落盘后**自己决定**是否 init + add + commit——所有 git 操作都可追溯到用户意图。**破坏性**：CLI 0.16.0+ 升级后，老用户（CLI 0.16.0 之前 init 过 git 的 wiki）**不受影响**——git 仓已存在、history 已写，新 CLI 不再主动 add/commit 不会破坏 history；新用户（首次 init）需手动 `cd <wiki-root> && git init && git add . && git commit -m "..."`。**包含 0.15.0 设计的 raw/.gitkeep 占位**——CLI 仍 touch `raw/articles/.gitkeep` + `raw/assets/.gitkeep`，但**不**自动 `git add`；用户首次 `git add .` 时由 git 自然纳入（前提是用户 init git，否则纯目录树）。SKILL.md `metadata.wiki_spec_version` 升至 0.16.0；`lint-checklist.md` §二.1 raw-modified 措辞更新（前提改为"wiki 仓在 git 内 + raw/ 有 tracked 文件"——CLI 不再保证 git init，"未启用 git"是更常见的状态）；`agents-md-template.md` §一 加"git 由用户触发"纪律 |
| 0.14.0 | 2026-07-07 | §13.2 `target` 字段类型放宽为「绝对路径 **或** `~/...` home-relative 形式（推荐后者）」——同 home 布局的多机可共享同一 anchor 不需重写；`scripts/lint_wiki.py` 在 §13.5 校验前已 `Path(target).expanduser()` 统一展开，**不**需新增 finding（绝对路径展开后不变，`~/...` 展开为 `$HOME/...`）。SKILL.md `metadata.wiki_spec_version` 升至 0.14.0；`SKILL.md` §1.bulk / `agents-md-template.md` / `external-repo-rebuild.md` / `lint-checklist.md` §二.3 措辞同步对齐"允许 `~/...`"。**老 wiki 兼容**：0.13.0 及更早的 anchor 写的是绝对路径，`expanduser` 展开后等价不变，lint 行为不变；新接入/重写 anchor 时推荐改用 `~/...` 形式（用户主动改） |

> **更早版本**（0.13.0 → 0.1.0）摘要：`sources-absolute-path` finding（0.13.0）/ `raw/external/`
> schema + git 锚定（0.12.0）/ AGENTS.md SSOT + CLAUDE.md 薄壳拆分（0.11.0）/ MEMORY/ 平级
> 目录（0.10.0）/ `scripts/` + `SCRIPTS.md`（0.9.0）/ `wiki/tags.md` tag 白名单（0.8.0）/
> `reviewed` / `reviewed_at` 二态替代 `confidence`（0.7.0）/ MEMORY 索引改名 MEMORY.md
> （0.6.0）/ `contested` / `contradictions` 字段（0.5.0）/ `raw/external/` 首次引入（0.4.0）/
> git 初始化 opt-in（0.3.0）/ MEMORY 目录首次引入（0.2.0）/ 初始版本（0.1.0）。详细 changelog
> 见 git log / 老 wiki 的 spec 历史 tag。

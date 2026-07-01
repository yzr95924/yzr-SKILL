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
> **CLAUDE.md / index.md / log.md / MEMORY/ 的归属**：
>
> | 文件 / 目录 | init 时刻（CLI） | 后续所有变更 |
> | --- | --- | --- |
> | `<wiki-root>/CLAUDE.md` | CLI 按 §2 拷贝模板 | 用户（schema 是用户宪法） |
> | `wiki/index.md` | CLI 按 §3 写入初始骨架 | **LLM agent**（ingest / 重写 / 归档时同步） |
> | `wiki/log.md` | CLI 按 §4 写入首条 setup 条目 | **LLM agent**（只 append，不删改） |
> | `wiki/MEMORY/` | CLI 按 §5 创建空目录 + 写 MEMORY.md（索引） | **LLM agent**（append 经验条目 + 同步 MEMORY.md 索引） |
>
> CLI **不**参与 index.md / log.md / MEMORY 的后续追加；无 "add log entry" / "add memory" /
> "sync index" 类命令。

## 目录

- [§1 目录结构](#1-目录结构)
- [§2 CLAUDE.md](#2-claudemd)
- [§3 wiki/index.md](#3-wikiindexmd)
- [§4 wiki/log.md](#4-wikilogmd)
- [§5 wiki/MEMORY/](#5-wikimemory)
  - [§5.1 MEMORY/MEMORY.md（索引）](#51-memorymemorymd索引)
  - [§5.2 MEMORY/*.md（非 MEMORY.md）](#52-memorymd-非-memorymd)
- [§6 .gitignore](#6-gitignore)
- [§7 Git 初始化（opt-in，默认跳过）](#7-git-初始化opt-in默认跳过)
- [§8 拒绝条件（强约束）](#8-拒绝条件强约束)
- [§9 Frontmatter 字段全集（CLI 引用，非生成内容页）](#9-frontmatter-字段全集cli-引用非生成内容页)
- [§10 版本钉死](#10-版本钉死)
- [§11 命名约束（影响 CLI 生成的产物）](#11-命名约束影响-cli-生成的产物)
- [§12 不在本 spec 范围内](#12-不在本-spec-范围内)
- [§13 raw/external/——外部代码仓接入](#13-rawexternal外部代码仓接入可选)
- [附录 A：CLI 实现自检建议](#附录-a-cli-实现自检建议)
- [附录 B：版本历史](#附录-b-版本历史)

## §1 目录结构

```
<wiki-root>/
├── .gitignore
├── CLAUDE.md
├── raw/
│   ├── articles/
│   └── assets/
└── wiki/
    ├── MEMORY/
    │   └── MEMORY.md
    ├── comparisons/
    ├── concepts/
    ├── entities/
    ├── index.md
    ├── log.md
    ├── sources/
    └── syntheses/
```

- 5 个内容页子目录名固定，**字母序**（`comparisons` → `concepts` → `entities` → `sources` → `syntheses`），
  CLI 必须按此顺序创建（利于阅读、diff 稳定、跨工具兼容）
- **`wiki/MEMORY/` 是 wiki 仓的"agent 持久化记忆"目录**——LLM agent 写入，用于沉淀跨
  ingest / query / lint 的工作经验、踩坑记录、用户偏好；与 `wiki/` 下 5 个内容页子目录并列，
  走相同的 frontmatter 5 必填 lint（详见 §5）。其中 `MEMORY.md` 是索引，被
  `<wiki-root>/CLAUDE.md` 用 `@wiki/MEMORY/MEMORY.md` import 会话常驻——避免 MEMORY 沦为
  只写不读的死库
- `raw/articles/` 与 `raw/assets/` 是默认占位；用户在 wiki 仓内可自由新增其他子目录
  （如 `podcasts/` / `papers/` / `clippings/` / `external/`——后者语义见 §13），CLI 不必预创建
- `index.md` / `log.md` / `MEMORY/MEMORY.md` 是 `wiki/` 下的文件，不是子目录
- `comparisons/` 等 5 个内容页子目录在初始化时为空目录——空目录对纯目录树 wiki 无副作用；
  仅当用户 `--git` opt-in 时，CLI 在每个空子目录放 `.gitkeep` 让其能被 `git add`（见 §7）

## §2 CLAUDE.md

> **维护方**：CLI 在 init 时刻按本节模板拷贝；
> 后续修改由 **用户** 完成（CLAUDE.md 是 wiki 的 schema，是用户的"宪法"）。
> LLM agent 不得编辑 CLAUDE.md；如需变更 schema，**先与用户确认**。

- 路径：`<wiki-root>/CLAUDE.md`
- 内容来源：本仓 `references/claude-md-template.md`（**权威 canonical 模板**）
- CLI 实现时必须**逐字拷贝**该模板，仅做以下替换：
  - `{{TOPIC_NAME}}` → 用户传入的主题名（人类可读字符串，如 `"LLM Systems"`、`"Distributed Systems"`）
  - `{{SETUP_DATE}}` → 当天日期 `YYYY-MM-DD`
  - `{{WIKI_SPEC_VERSION}}` → CLI 实现兼容的 wiki spec 版本号（语义化版本，如 `0.1.0`）
  - `{{CLI_VERSION}}` → CLI 自身版本号
- 模板顶部第 8 行（"本文件由 ... 初始化时生成"）的反向引用，CLI **不得修改**

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

- **触发条件**：`log.md` 条目数 ≥ 500（按正则 `^## \[\d{4}-\d{2}-\d{2}\]` 计，不含
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

## §5 wiki/MEMORY/

> **维护方**：CLI 在 init 时刻创建**空目录**并按 §5.1 写入 `MEMORY/MEMORY.md`（索引）；
> 后续 MEMORY 下的经验条目 `*.md` 由 **LLM agent** 写入，并**同步追加 MEMORY.md 索引一行**。
> 用户**不**直接编辑 MEMORY——它是 agent 私有记录。
> CLI 不参与 MEMORY 的后续写入。

- 路径：`<wiki-root>/wiki/MEMORY/`
- 目录名 `MEMORY` **大写**，区别于 `raw/` `wiki/` `wiki/index.md` 等小写目录/文件——这是为了
  在文件浏览器里一眼区分"agent 私有记忆"与"wiki 内容"
- **`MEMORY/MEMORY.md`（索引）——CLI init 时刻写入**（fixtures 字面量见
  `references/fixtures/memory-index.txt`）；被 `<wiki-root>/CLAUDE.md` 用
  `@wiki/MEMORY/MEMORY.md` import，会话常驻。详见 §5.1
- 其余 `*.md` 经验条目由 LLM 在工作中追加，**文件命名 + frontmatter 5 必填 与 wiki 内容页规则一致**
  （lint 校验实现见 SKILL 仓 `scripts/lint_wiki.py`，不归本 spec）
- **MEMORY 不在 `wiki/index.md` 中强制列出**——它是 agent 私有入口，不需要 wiki 单一入口约束；
  但每条 `*.md` **必须**在 `MEMORY/MEMORY.md` 索引中列出一行（lint `memory-not-indexed` 兜底漏列）

### §5.1 MEMORY/MEMORY.md（索引）

- 路径：`<wiki-root>/wiki/MEMORY/MEMORY.md`
- **无 frontmatter**——它是被 `CLAUDE.md` 用 `@wiki/MEMORY/MEMORY.md` import 内联的索引片段，
  不是 wiki 内容页（对齐仓库根 `MEMORY/MEMORY.md` 形态）。lint 把它当 reserved 跳过 frontmatter /
  tag / 命名校验
- 正文骨架：顶部 1 段说明（本目录用途 + 何时写 / 命名 / 纪律指向 SKILL §4，**不**重复以免口径分裂）+
  `## 索引` 段；每条一行：`- <slug> — <一句话摘要> → [正文](<slug>.md)`
- **加载机制**：agent 在 wiki 根目录工作时，Claude Code 自动加载根 `CLAUDE.md`，
  `@wiki/MEMORY/MEMORY.md` 随之展开 → 索引常驻；agent 在别处工作（skill 经 `$LLM_WIKI_ROOT`
  读 CLAUDE.md）时，`@` 不自动展开，由 SKILL 的 orient ritual 显式 Read MEMORY.md 补齐
- **字面量见 fixtures**：`references/fixtures/memory-index.txt`（与 `references/canonical/memory-index.md`
  一致——MEMORY.md 无占位符，fixtures 与 canonical 内容相同）

### §5.2 MEMORY/*.md（非 MEMORY.md）

- 路径：`<wiki-root>/wiki/MEMORY/<slug>.md`
- 命名约束：与 wiki 内容页一致，kebab-case `^[a-z0-9][a-z0-9-]*$`
- frontmatter：**5 必填**（`title` / `type` / `created` / `updated` / `tags`）+ 推荐 `description`
- `type` 取值：与 5 类内容页枚举相同（`entity` / `concept` / `source` / `comparison` / `synthesis`），
  或新的 memory 类型（按需扩展，本 spec 不限制）
- lint 校验：走与 wiki 内容页一致的 5 必填校验（实现见 SKILL 仓 `scripts/lint_wiki.py`）
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
- **opt-in（`--git`）**：CLI 先做前置检查，**任一**不满足即**跳过 git 并打印提示（不报错，不阻断落盘）**：
  1. `git` 二进制可用——不可用时提示"未找到 git，已跳过；wiki 仍可用"
  2. `<wiki-root>` **不在**已有 git 仓内——已在仓内时提示"已在 git 仓内，跳过 init；如需提交请自行 add+commit"
- 前置检查通过后，CLI 顺序执行：
  1. `git init`
  2. `git symbolic-ref HEAD refs/heads/main`（默认 main 分支）
  3. 检查全局 `git config user.email` / `user.name`，未配则 local 配占位值（`wiki@local` / `LLM Wiki`）
  4. 为 5 个空内容页子目录放 `.gitkeep`（空目录才能被 `git add`，见 §1）
  5. `git add .`
  6. `git commit -m "Initial wiki scaffold"`
- **不得**对已存在的 git 仓误调 `git init`。

## §8 拒绝条件（强约束）

CLI 在以下情况必须拒绝并退出（**非零退出码**）：

| 触发条件 | 错误信息建议 |
|---|---|
| `<wiki-root>/CLAUDE.md` 已存在 | `"<wiki-root>/CLAUDE.md 已存在；拒绝覆盖。..."` |
| `<wiki-root>/wiki/index.md` 已存在 | `"<wiki-root>/wiki/index.md 已存在；拒绝覆盖。..."` |

**绝不允许覆盖已有 wiki**。用户想重新初始化必须先手动备份 + 删除。

## §9 Frontmatter 字段全集（CLI 引用，非生成内容页）

CLI **不**生成 `wiki/{entities,concepts,sources,comparisons,syntheses}/` 下的内容页（由 LLM 在 ingest 时写）。
但 spec 必须明确字段全集，CLI 在做合规性自检（如 `init --verify`）时引用：

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

### 类型特化字段（LLM 写内容页时使用）

| 字段 | 适用 type | 必填 | 含义 |
|---|---|---|---|
| `sources` | `source` / `synthesis` | 是 | source 页是 `raw/` 下路径数组；synthesis 页是 wiki 内其它页路径数组 |
| `aliases` | `entity` | 否 | 别名数组，方便搜索 |
| `related` | `concept` | 否 | 相关概念路径数组 |
| `compared` | `comparison` | 否 | 被对比对象路径数组 |
| `threads` | `synthesis` | 否 | 线索标题数组 |

### 可选认知质量字段（LLM 按需写，全部可选）

> 语义权威定义在 SKILL 仓 [`page-templates.md`](page-templates.md) §一「可选：认知质量信号」；
> 本表只列 CLI 自检用的字段类型，不重复语义。CLI 自检不要求这些字段存在——它们是
> LLM 摄入争议 / 单源 / fast-moving 内容时按需标注的"弱主张警示"。

| 字段 | 适用 type | 必填 | 含义 |
|---|---|---|---|
| `confidence` | 任意内容页 | 否 | `high` / `medium` / `low`；主张可信支撑度；省略 = 不评 |
| `contested` | 任意内容页 | 否 | 仅 `true` 时写；本页含未解决的矛盾主张，需复审 |
| `contradictions` | 任意内容页 | 否 | wiki 页路径数组；与本页主张冲突的页面（双向标注） |

完整 frontmatter 写法约束与 YAML 子集要求，**不在本 spec 范围内**——见 SKILL 仓的
[`page-templates.md`](page-templates.md)（LLM 写作视角，非 CLI 视角）。

## §10 版本钉死

CLI 在生成 `<wiki-root>/CLAUDE.md` 时，必须替换模板 §八 的两个版本占位符：

| 占位符 | 替换为 | 来源 |
|---|---|---|
| `{{WIKI_SPEC_VERSION}}` | CLI 当前兼容的 wiki spec 版本（如 `0.1.0`） | CLI 实现时 bundled copy spec 时硬编码，或运行时 fetch SKILL 仓 `metadata.wiki_spec_version` |
| `{{CLI_VERSION}}` | CLI 自身版本号 | CLI 仓 `__version__` 或 `pyproject.toml` / `package.json` 的 version 字段 |

spec 版本号约定在 SKILL 仓 `SKILL.md` 的 `metadata.wiki_spec_version` 字段声明（如 `0.1.0`）。
CLI 仓与 spec 版本对齐是 CLI 仓的责任；spec 变更时 SKILL 仓升 `wiki_spec_version`，
CLI 仓跟随升级。

**LLM 在每次操作前比对** CLAUDE.md §八 的 "Wiki Spec 版本" 与 SKILL.md
`metadata.wiki_spec_version`；不一致时**警告用户**（不阻断——CLI 可能支持多个 spec 版本）。

## §11 命名约束（影响 CLI 生成的产物）

| 维度 | 规则 | 适用对象 |
|---|---|---|
| 文件名 kebab-case | `^[a-z0-9][a-z0-9-]*$` | `wiki/{entities,concepts,sources,comparisons,syntheses,MEMORY}/*.md`（index/log 除外；MEMORY/MEMORY.md 不在此约束） |
| 子目录名 | 固定字母序（§1） | 5 个内容页子目录 |
| 特殊目录名 `MEMORY` | **大写**（区别于小写 `raw` / `wiki` 等） | `wiki/MEMORY/` |
| frontmatter 字段名 | 严格小写 + 下划线（`okf_version`、`created`、`updated`） | 所有 frontmatter |
| frontmatter `type` 值 | 严格小写（5 类内容页 + 3 类 reserved） | 所有 wiki 页 |

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
> `ln -s` + 手写 `.symlink-anchor.json` 接入。

外部代码仓（如 Linux kernel、Ray 源码）作为原始语料纳入 wiki 时，**不**做仓库内嵌
拷贝（避免占用空间 + 失去 commit 锚点），而是走 **symlink + 锚定元数据**：

### §13.1 路径约定

```text
<wiki-root>/raw/external/<source-name>/
├── .symlink-anchor.json           # 必填：解析后的绝对路径 + 捕获日
├── <symlink or 子目录/文件>          # 用户的 symlink 目标，可继续嵌套
```

- `<source-name>` 必须匹配 `^[a-z0-9][a-z0-9-]*$`（与 wiki 内容页命名一致）
- symlink 既可以是单个文件也可以是整个目录；`.symlink-anchor.json` 永远与 symlink 同目录
- 多个 symlink 嵌套时**每个 symlink**都需自己的 `.symlink-anchor.json`

### §13.2 `.symlink-anchor.json` Schema（最小必填）

```json
{
  "target": "/absolute/path/resolved/by/readlink",
  "captured_at": "YYYY-MM-DD",
  "kind": "external-repo"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `target` | string（绝对路径） | 是 | `readlink -f <symlink>` 的输出；记录"锚定瞬间" 的真实位置 |
| `captured_at` | date `YYYY-MM-DD` | 是 | 用户接入当天；用于提示"target 路径多久前定锚" |
| `kind` | enum | 是 | 当前仅支持 `"external-repo"`；预留给以后扩展（`"snapshot"` 等） |

**字段扩展**：可加 `commit`、`tag`、`subpath` 等**可选**字段描述对接入到仓的哪个版本/
哪个子目录——CLAUDE.md §一记录的纪律不强制 SKILL 解析，但 lint 不报错。

### §13.3 用户责任（CLIs 不强制）

- 用户负责创建 symlink（用 `ln -s` 或 IDE 拖拽）
- 用户负责就地写 `.symlink-anchor.json`——**没有 anchor 的 symlink = lint 报
  `external-anchor-missing`**
- 用户负责 symlink target 的存活——target 被删除 / 改名 / 移动后 anchor 仍记录
  旧路径，lint 报 `external-target-dead` 让用户感知
- LLM agent **不**写、不删、不修改 `raw/external/` 下任何文件（与 raw/ 纪律一致）

### §13.4 .gitignore 增强

`.gitignore` 在 §6 的基础上追加以下规则（CLI init 时一并生成）：

```gitignore
# 外部代码仓 symlink 接入（不跟踪 symlink 本身，但保留 anchor 元数据）
raw/external/*
!raw/external/**/.symlink-anchor.json
```

> **理由**：symlink 会被 git 当成 symlink 记录（指向一个不可解析的 target，在另一台
> 机器 clone 时毫无意义），但 `.symlink-anchor.json` 是真实文件、记录"接入意图"——
> `!` 否定号让 anchor 文件被跟踪。这样跨机器 clone 时 lint 会立刻发现
> `external-target-dead`（因为 target 路径不存在），提醒用户重新锚定。

---

## 附录 A：CLI 实现自检建议

CLI 在生成完成后，可执行以下验证：

1. **字节级对比(渲染后)**:CLI 用锚点 mapping (`TOPIC_NAME="Test"`, `SETUP_DATE="2026-06-28"`) 渲染,
   产物与本仓 `references/canonical/` 下对应文件**逐字一致**。
   canonical/ 目录由本仓在每次 fixture 变更时手工生成(SKILL 仓 owner 操作)。
2. **正则自检**：生成的 `wiki/log.md` 首条条目匹配 §4 正则
3. **frontmatter 解析**：生成的 `wiki/index.md` / `wiki/log.md` 能被
   `scripts/ingest_diff.py` 的 `parse_frontmatter_simple()` 正确解析（MEMORY.md 无 frontmatter，不在此列）
4. **结构自检**：5 个内容页子目录 + `wiki/MEMORY/` 全部存在；MEMORY 目录含 MEMORY.md
5. **lint 跑通**：生成的 wiki 仓跑 `scripts/lint_wiki.py` 应返回 exit code 0

## 附录 B：版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.6.0 | 2026-07-01 | §5 重构：`MEMORY/README.md`（type:memory reserved）→ `MEMORY/MEMORY.md`（无 frontmatter 索引，被 `<wiki-root>/CLAUDE.md` 用 `@wiki/MEMORY/MEMORY.md` import 会话常驻，避免 MEMORY 沦为只写不读死库）；§9 删 reserved `memory`（只剩 index/log）；§5.2 要求每条 `*.md` 在 MEMORY.md 索引列一行；lint 新增 `memory-not-indexed`（info）。**老 wiki 迁移**：删 `MEMORY/README.md` + 新建 `MEMORY/MEMORY.md` 索引并把现有 `*.md` 各补一行 |
| 0.5.0 | 2026-07-01 | §9 新增「可选认知质量字段」`confidence` / `contested` / `contradictions`（全部可选，LLM 按需标注弱主张）；字段语义权威在 SKILL 仓 page-templates.md §一，spec 仅列 CLI 自检用的字段类型 |
| 0.4.0 | 2026-07-01 | 新增 §13 `raw/external/` 外部代码仓 symlink 接入：`.symlink-anchor.json` schema + 用户责任 + `.gitignore` 例外规则；§6 `.gitignore` 模板加 `raw/external/*` 排除 |
| 0.3.0 | 2026-06-29 | git 初始化改为 opt-in（§7）：默认落盘纯目录树，仅 `--git` 时才 init + commit；§1 空目录 `.gitkeep` 仅 opt-in 时放；§6 `.gitignore` 无条件生成 |
| 0.2.0 | 2026-06-28 | 新增 §5 `wiki/MEMORY/` 目录（agent 持久化记忆）；type 取值新增 reserved `memory`；fixtures 新增 `memory-readme.txt` |
| 0.1.0 | 2026-06-28 | 初始版本：原 `setup_wiki.py` 行为字面量化为 spec |

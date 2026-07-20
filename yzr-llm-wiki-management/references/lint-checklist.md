# Lint 详细 Checklist

Lint 让 wiki **不腐烂**。Karpathy 原话："The tedious part of maintaining a knowledge
base is not the reading or the thinking — it's the bookkeeping." Lint 把 bookkeeping
的一部分自动化。

## 目录

- [一、调用方式](#一调用方式)
- [二、Deterministic 检查清单（脚本执行）](#二deterministic-检查清单脚本执行)
  - [前置：wiki 版本一致性](#前置wiki-版本一致性)
  - [1. `raw/` 不可变性](#1-raw-不可变性)
  - [2. frontmatter 完整性](#2-frontmatter-完整性)
  - [3. frontmatter 来源（source / synthesis 页）](#3-frontmatter-来源source--synthesis-页)
  - [4. 路径引用完整性](#4-路径引用完整性)
  - [5. index.md 覆盖](#5-indexmd-覆盖)
  - [6. log.md 格式](#6-logmd-格式)
  - [7. 过期摘要](#7-过期摘要)
  - [8. 文件名规范](#8-文件名规范)
  - [9. 重复标题](#9-重复标题)
  - [10. log.md 条目数（log-truncation）](#10-logmd-条目数log-truncation)
  - [11. Tag Taxonomy 校验](#11-tag-taxonomy-校验)
  - [12. 页面体量](#12-页面体量)
  - [13. 可信度与认知质量信号（reviewed / contested / contradictions）](#13-可信度与认知质量信号reviewed--contested--contradictions)
  - [14. MEMORY.md 索引一致性](#14-memorymd-索引一致性)
  - [15. related / compared 路径引用完整性](#15-related--compared-路径引用完整性)
- [三、半定性检查（agent 执行）](#三半定性检查agent-执行)
  - [17. 矛盾主张](#17-矛盾主张)
  - [18. 缺失交叉引用](#18-缺失交叉引用)
  - [19. 缺失 entity / concept 页](#19-缺失-entity--concept-页)
  - [20. 调查方向建议](#20-调查方向建议)
  - [21. 资料投放口是否堆积](#21-资料投放口是否堆积)
- [四、报告格式](#四报告格式)
- [五、Semantic-merge 规则](#五semantic-merge-规则)
- [六、lint 之后](#六lint-之后)
- [七、lint 频率](#七lint-频率)
- [八、lint 的边界](#八lint-的边界)

Lint 分**两层**：

1. **Deterministic**（脚本检查，可程序化）——`scripts/lint_wiki.py`
2. **Semi-qualitative**（agent 检查，需理解语义）——本文件"半定性检查"段

## 一、调用方式

```bash
python3 yzr-llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT"
# 或带严重性过滤
python3 yzr-llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT" --severity error
```

退出码：0 = 干净；1 = 有问题（看输出）。

### 子命令 `--migrate-confidence`（仅供旧用法兼容）

老 wiki 中 `confidence: high/medium/low` 字段（已退役）一次性迁移到
新 `reviewed` + `reviewed_at`：

```bash
python3 yzr-llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT" --migrate-confidence
```

行为：

- `confidence: high` → 写 `reviewed: true` + `reviewed_at: <今天>`，移除 `confidence`
- `confidence: medium` / `confidence: low` → 仅移除 `confidence`（默认未审核）
- 遇到冲突（页面同时已有 `reviewed` 字段）→ `migration-conflict`，跳过该页
- 输出报告：`<N> migrated, <M> removed, <K> skipped (conflicts)`
- **不**写 log 条目（迁移是脚本运行，不是 wiki 操作事件）

**与正常 lint 的关系**：

- 不带 `--migrate-confidence` 时：见到 `confidence:` 字段给 `legacy-confidence-field` warn（§二.13.C）
- 带 `--migrate-confidence` 时：**不**做常规 lint 检查，**只**做迁移（互斥模式）

**与 `--check-version` 的关系**：`--migrate-confidence` 是单点硬编码迁移；
新流程一律走 `--check-version --apply`（覆盖其功能 + 范围更广）。保留 `--migrate-confidence`
仅供旧脚本/CI 调用兼容；详见 SKILL.md §5 Migrate。

### 子命令 `--check-version`

扫当前 wiki 的 spec 版本（解析 `<wiki-root>/AGENTS.md` §八；老 wiki fallback `<wiki-root>/CLAUDE.md` §八）与已知
legacy 老格式现场：

```bash
python3 yzr-llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT" --check-version
# 加 --json 输出机器可读 JSON（agent 程序化消费）
python3 yzr-llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT" --check-version --json
# 加 --apply 输出 migration plan（stdout JSON，不落盘）供 agent 按 wiki-spec-changelog.md 走 Edit/Write 修复
python3 yzr-llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT" --check-version --apply --json
```

行为：

- 默认 **dry-run**——只打印人读报告，不动任何文件
- 解析 AGENTS.md §八 → 抽 `current_spec`；与 SKILL 仓 `metadata.wiki_spec_version`
  比对（脚本常量 `CURRENT_WIKI_SPEC`）
- 扫已知 legacy pattern：`confidence-field`（已退役字段）+ `type-memory-value`
  （规则仅对 wiki 5 类内容页误用 reserved `type: memory` 报错；MEMORY/*.md 上
  `type: memory` / `type: memory-entry` 合法——见下文"类型误用 / reserved
  `type: memory`"段）
- 标记冲突页（同时含老字段与新字段）→ `conflicts[]`，agent 跳过 + 转人工
- `--apply` 以 stdout JSON 输出 migration plan（不落盘）——含 `actions[]` / `skipped_conflicts[]`
  / `agent_rules[]`；agent 内存持有，无"plan 已存在"覆盖问题
- **不**做常规 lint 检查（互斥模式）
- **不**写 log 条目（迁移是脚本运行，不是 wiki 操作事件）

完整 agent 修复路径、边界、与 lint 检查的协同见 [SKILL.md §5 Migrate](../SKILL.md#5-migrate升级-wiki-spec)。
规则 SSOT 见 [`wiki-spec-changelog.md`](wiki-spec-changelog.md)。

## 二、Deterministic 检查清单（脚本执行）

### 前置：wiki 版本一致性

- 每次常规 lint（不带 `--check-version`）都查 `<wiki-root>/AGENTS.md` §八「Wiki Spec 版本」
  与 SKILL 仓 `CURRENT_WIKI_SPEC` 是否一致——让用户日常 lint 就能感知版本漂移，不必显式
  跑 `--check-version` 才发现。实现：`check_spec_version()`（复用 `parse_spec_version` +
  `_compare_semver`，与 `--check-version` 同源）
- **finding 名 / 严重性：warn**——不阻断，仅提示：
  - `wiki-spec-version-stale`：AGENTS.md 版本**落后** SKILL——跑 `lint_wiki.py --check-version --apply` 走升级流程（SKILL.md §5 Migrate）
  - `wiki-spec-version-ahead`：AGENTS.md 版本**领先** SKILL——升级 SKILL 仓（`lint_wiki.py`）对齐
  - `wiki-spec-version-unparsed`：§八版本行无法解析（缺 AGENTS.md / CLAUDE.md 或表格格式破坏）——跑 `--check-version` 诊断
- **与 `--check-version` 的区别**：常规 lint 只报 warn 提示（不产 plan、不动 wiki）；
  `--check-version` 才输出 migration plan（stdout JSON）+ 跑 fixtures-check + 产修复 action
- 版本一致（equal）→ 无 finding

### 1. `raw/` 不可变性

- 在 `<wiki-root>/` 跑 `git status raw/`；有 tracked 文件改动 → 报告
- **严重性：error**——任何 raw/ tracked 文件改动都是违反 skill 纪律
- **前提**：脚本**自动检测** wiki 根目录是否在 git 仓内（`.git/` 子目录存在与否）：
  - `.git/` 不存在 → 跳过 + 输出顶部 `[NOTES] raw-immutable-skipped: 未启用 git（无 .git/）`
    ——这是默认状态（CLI 不自动 git init），不需要警告
  - `.git/` 存在但 `raw/` 未纳入 git 跟踪（untracked）→ 跳过 + `[NOTES] raw-immutable-skipped: raw/ 未纳入 git 跟踪`
    ——untracked raw 文件**不在** `raw-modified` 检查范围（用户未提交，自然不在 raw-modified 语义下）
  - 真 git 仓 + raw 里有 tracked file 被 modified → 报 `raw-modified` finding
- 强制跳过：传 `--no-git` 时完全静默跳过（不打 note）——给 CI / 裸仓场景
- **不要**在裸目录树 wiki 上"强假设 git"——`wiki-spec.md §7` 默认就是裸目录树，
  "未启用 git"是默认状态而非异常
- **untracked raw 文件**——CLI init 不自动 `git add .`，用户后续 `git add raw/foo.md` 前该文件
  是 untracked；untracked 不在 `raw-modified` 范围（raw-modified 只针对 tracked file 被 modified）

### 2. frontmatter 完整性

- 扫 `wiki/**` 下所有 `.md`（排除 `index.md` / `log.md`）**+** 扫 `<wiki-root>/MEMORY/*.md`
  （与 `wiki/` 平级、单独子树扫；排除 `MEMORY.md` 本身——索引无 frontmatter）
- 校验口径分两类（spec §5.2 vs §9）：
  - **wiki 5 类内容页**（entities / concepts / sources / comparisons / syntheses）：
    每页**必须**含 `title` / `type` / `created` / `updated` / `tags` 字段
    （字段定义见 [page-templates.md §一](page-templates.md#一共有-frontmatter-段)）
  - **MEMORY/*.md**：仅 `title` 必填；其余 5 字段（`type` / `created` / `updated` / `tags` /
    `description`）全 optional——MEMORY 是 agent 私有记忆，frontmatter 是可选 decoration
    （与「短条目 1 行索引行」形态对齐；spec §5.2）
- `type` 取值合法性：
  - wiki 5 类内容页：`entity` / `concept` / `source` / `comparison` / `synthesis` 之一
  - MEMORY/*.md：以上 5 类均可，或 memory 扩展类型 `memory` / `memory-entry`
- **类型误用 / reserved `type: memory`（legacy `type-memory-value`）**：
  - **范围**：仅对 wiki 5 类内容页（entities/concepts/sources/comparisons/syntheses）
    误用 reserved `type: memory` 报错。MEMORY/*.md 上 `type: memory` /
    `type: memory-entry` 是 spec §5.2 合法值，**不**触发本规则。
  - **迁移目标**：wiki 内容页改为对应 5 类之一（entity/concept/source/comparison/
    synthesis）；不要改为 `memory-entry`（那是 MEMORY 桶扩展值）。
- **finding 名**：`missing-frontmatter`（error，缺必填字段）/ `invalid-type`（error，`type` 取值非法）
- **严重性：error**——缺字段或 type 非法

### 3. frontmatter 来源（source / synthesis 页）

- `type: source` 的页面，`sources` 字段必须非空，且每个值是 `raw/` 下的现存路径
- `type: synthesis` 的页面，`sources` 字段必须非空（可以指 wiki 内其它页）
- **严重性：error**——断链
- **`sources-absolute-path`（仅 source 页）**——`type: source` 的 `sources:` 数组任一元素
  以**绝对路径**形式出现即报。检测 3 种形式：
  - Unix 绝对：以 `/` 起始（如 `/Users/foo/articles/llama-3.md`）
  - Windows 盘符：`C:\` / `C:/` 起始（兼容正反斜杠）
  - Windows UNC：`\\server\share` 起始
  - 跨平台正则自写——不走 `Path.is_absolute()`（它在 Linux / Windows 上对同一字符串
    判定结果不同），lint 必须在 POSIX 主机上跑也能正确报 Windows 绝对路径
  - 命中后 `continue` 跳过后续 `sources-out-of-root` / `sources-missing`——同一根因不重复报错
  - **为什么是 error**：`raw/` 路径是 wiki 内 source 页的"永久引用"（[§一 纪律 SSOT](wiki-spec.md)），
    绝对路径会破坏跨机器可移植性（A 机上的 `/Users/foo/...` 在 B 机上无意义），与"raw 与 wiki
    矛盾以 raw 为准"的纪律同级
  - **与 anchor 字段的对比**：`raw/external/.symlink-anchor.toml` 的 `[[entry]].target`
    字段允许**绝对路径**或 **`~/...` home-relative 形式**（推荐后者）——
    lint 在判定前 `Path(target).expanduser()` 统一展开，**不**关心 anchor 写哪种形式。
    本检查**不**触及 anchor 文件
- **`raw/external/<symlink>/...` 例外（spec §13.3）**——`sources:` 元素以 `raw/external/`
  起始时**不**走 `sources-out-of-root` 检查（symlink 跟随 `.resolve()` 会落到 wiki 根外，但
  这正是 spec §13 的预期用法）。改为：
  1. 解析 `<symlink>` 段（`Path(s).parts[2]`），段数 < 3 → 报 `sources-malformed`
  2. 校验 `raw/external/.symlink-anchor.toml` 存在 → 缺则报 `sources-external-anchor-missing`
  3. 校验 symlink 文件本身存在 → 缺则报 `sources-external-symlink-missing`
  4. 校验路径跟随 symlink 后可访问（文件或目录皆可——external repo 本身是 git 仓即
     目录）→ 不可访问报 `sources-missing`（复用原 finding）；用 `sp.exists()` 而非
     `sp.is_file()`（spec §13.3 LLM 责任澄清：external source 可指向整仓）
  全部合法才放过。**不要**回退本例外——任何 lint 仓 merge / 升级时若发现此例外被回退，
  立刻把它补回去；下游所有用 `raw/external/` 的 wiki 都退化到 12 error 误报
- **不在本检查范围**：`type: synthesis` 的 `sources:`（指向 wiki 内其它页如 `concepts/...`，
  字段语义不同——见 §一 SSOT）；如有需要后续单独加 finding

### 4. 路径引用完整性

- 扫所有 `wiki/**/*.md` 的 Markdown 链接 `[text](path)` 和图片 `![alt](path)`
- 相对路径解析后必须指向现存文件（在 wiki 范围内）
- 外部 URL（http/https）跳过
- **严重性：error**——断链影响阅读

### 5. index.md 覆盖

- 读 `wiki/index.md`
- 提取所有相对路径引用
- `wiki/**/*.md` 减去 `index.md` / `log.md` 后，每个文件**必须**被 index 引用
- **finding 名**：`index-missing`（error，`wiki/index.md` 不存在）/ `orphan-page`（error，未被 index 引用）
- **严重性：error**——孤儿页失去单一入口的意义

### 6. log.md 格式

- 每行匹配正则（见 [page-templates.md §7](page-templates.md#7-logmdlog)）
- **finding 名**：`log-missing`（error，`wiki/log.md` 不存在）/ `log-format`（warning，正则不匹配）
- **严重性：warning**——格式错乱会破坏 `grep "^## \[" log.md` 的可用性

### 7. 过期摘要

- `type: source` 且 `updated` 距今 > `STALE_SUMMARY_DAYS` 天 → 报告
- **finding 名**：`stale-summary`（warning）
- **严重性：warning**——不是 error，但建议复查

### 8. 文件名规范

- 所有 `wiki/**/*.md` 文件名必须是 kebab-case（小写 + `-`）
- 避免空格、大写、下划线
- **严重性：warning**

### 9. 重复标题

- 同一 `title` 出现在多个 wiki 页 → 报告
- **严重性：warning**——可能是合并候选

### 10. log.md 条目数（log-truncation）

- `wiki/log.md` 条目数 > 滚动窗口上限（默认 `LOG_RETENTION_LIMIT` = 50）→ 报告 `log-truncation-recommended`
- 上限由 `scripts/lint_wiki.py` 顶部 `LOG_RETENTION_LIMIT` 常量控制
- **不**自动截断——lint 只建议；agent 用 Edit 删最旧条目保最近 50 条（详见 [wiki-spec §4.1](wiki-spec.md#41-log-retention滚动窗口)）
- 完整历史靠 git（`git log -p -- wiki/log.md`）；存量 `log-YYYY.md`（若有）为只读遗留，不计入
- **严重性：warning**——超过上限不是错误，但长期不截断会让 `grep "^## ["` 噪声变大

### 11. Tag Taxonomy 校验

- 解析 `<wiki-root>/wiki/tags.md`（**主流位置**）的裸 bullet 列表，提取允许的 tag 集合；
  若不存在则 fallback 解析 SSOT（`<wiki-root>/AGENTS.md`；老 wiki `<wiki-root>/CLAUDE.md`）的 `### Tag Taxonomy` 段（**仅过渡期**，
  老 wiki 跨 spec 迁移用；详见 `wiki-spec.md` §9.1）
- 文件 / 段必须是**裸 bullet**（每行 `- ...`），不能包在 code block / HTML comment 里——
  包了就解析不出 0 个 tag，lint 静默跳过（视为未启用约束）
- 格式兼容：`- category：tag1 / tag2 / tag3`（中文 / 英文分隔符都支持；
  多 tag 用 `/` `，` `,` 任一字符分隔）
- 对每个**内容页**（仅 5 类 wiki 内容页：**不含 MEMORY/*.md**）的 `frontmatter.tags` 元素做包含校验
- **MEMORY agent 私有**：MEMORY 是 agent 私有记忆，私有 tag（`lint` / `external-repo` /
  `symlink` 等）是 LLM 工作上下文分类，**不**应跟 wiki 用户面共享 taxonomy（spec §5 + §9.1）
- **`wiki/tags.md` 自身不参与此校验**——它是无 frontmatter 的元数据文件，不是 wiki 内容页
- 找不到任何 tag 源 / 解析出 0 个 tag → 静默跳过（避免新 setup 的
  wiki 必报错）
- 严格匹配的 tag 名 = 严格小写 + kebab-case（`^[a-z0-9][a-z0-9-]*$`），与文件名命名一致
- **严重性：info**——tag 漂移不会立刻让 wiki 失能，但放任几个月后 index 噪音变大
- **审计循环**（与本节协同）：用户可在 `wiki/tags.md` 中**直接删除**误判的 bullet；下次 lint 把
  `tag-not-in-taxonomy`（info）报到所有还引用已删 tag 的页面，由用户裁定二选一：
  重新加回 / 从页面删除 tag。`tag-not-in-taxonomy` 含义因此覆盖：(a) 用户审计删除后的
  残留引用；(b) 用户手工编辑 page 时漏注册；(c) LLM auto-extend 失败 — 详见
  [`page-templates.md`](page-templates.md) §一「tags」段

### 12. 页面体量

- 5 类内容页（entities / concepts / sources / comparisons / syntheses）正文**非空行数** >
  阈值（SSOT = `scripts/lint_wiki.py` 的 `PAGE_SIZE_THRESHOLD`）→ 报 `oversized-page`
- 阈值与 AGENTS.md「Page Thresholds」段的「拆分页」行对齐（`agents-md-template.md` 也引用此 SSOT）
- `MEMORY/*` agent 私有——按 wiki-spec §5.2「正文无长度上限」（agent 经验沉淀可长）
- 计**非空行**（纯空行不计），避免空行撑大计数
- **严重性：warning**——不是 error，但单页过长 = 主题过散，建议拆成子主题页 + cross-link

### 13. 可信度与认知质量信号（reviewed / contested / contradictions）

- 把作者主动标注的"人工审核背书"与"认知冲突警示"拎出来供复审——防止单源弱断言无声固化成
  "wiki 事实"，同时让"已审核"在 query / lint / index.md 三处可见
- 字段语义见 [page-templates.md §一「可选：可信度与认知质量信号」](page-templates.md#可选可信度与认知质量信号)
- 子检查（字段全部可选；省略 = 不评，不报）：

#### A. 可信度信号 reviewed

- `pending-review`（**info**）：非 log/index 页**未**含 `reviewed: true`——新常态，仅提示
  - **MEMORY/*.md agent 私有**：MEMORY 是 agent 私有记忆（spec §5 + §5.2），
    无「人工 review」的语义角色；不进 reviewed 校验
- `reviewed-stale`（**warn**）：`reviewed: true` 存在但 `updated > reviewed_at`——LLM 修改后漏清戳
- `invalid-reviewed-value`（**warn**）：`reviewed` 取值非严格 `true`（如 `"true"` 字符串、`yes`、`1`、`false`）
- `reviewed-at-missing`（**warn**）：`reviewed: true` 存在但缺 `reviewed_at`
- `reviewed-at-orphan`（**warn**）：`reviewed_at` 存在但缺 `reviewed: true`
- `index-review-badge-drift`（**warn**）：`wiki/index.md` 条目上的 ✓/✗ 标识与被链页 frontmatter
  不一致（缺漏 / 多余 / 日期错）

#### B. 认知质量信号 contested / contradictions

- `contested-page`（warn）：`contested: true` 的页——含未解决矛盾，需裁定后移除标记
- `contradiction-target-missing`（warn）：`contradictions` 指向不存在的页
- `contradiction-asymmetric`（warn）：A 把 B 列入 `contradictions` 但 B 未反向标注 A
  （字段语义要求**双向标注**）

#### C. 迁移期检测

- `legacy-confidence-field`（warn）：出现已退役的 `confidence:` 字段——请运行
  `lint_wiki.py --migrate-confidence`（见 §一 调用方式）
- **什么时候下线**：建议保留 ≥ 1 个迁移周期（半年），期间未触发可移除

- **为什么是 deterministic 而非半定性**：这里只读作者**已写**的 frontmatter 信号并拎出来；
  判定"某页是否真的经过认真审核 / 某主张到底是否矛盾"是 §三 半定性工作，lint 不替人/agent 决定
- **严重性**：见上各子项——`reviewed-stale` / 断链类为 warn（需行动），`pending-review` 为 info（新常态）

### 14. MEMORY.md 索引一致性

- `MEMORY/MEMORY.md` 是轻量索引（无 frontmatter），由 `<wiki-root>/AGENTS.md` 顶部单行
  `@MEMORY/MEMORY.md` `@import` 加载全文——自动展开 `@import` 的 agent 透明拿到索引；
  不展开 `@import` 的 agent 由 AGENTS.md 顶部强制 Read 指令兜底（直接 `Read MEMORY/MEMORY.md`）。
  MEMORY.md 是单一真源、AGENTS.md 不持有副本——让所有读 `AGENTS.md` 的 agent 都能看到 MEMORY 里
  有哪些条目，避免 MEMORY 沦为只写不读的死库
- 扫 `<wiki-root>/MEMORY/*.md`（排除 `MEMORY.md` 本身）；任一经验条目 `<slug>.md` **未在 MEMORY.md 索引中
  列出** → 报 `memory-not-indexed`
- **反向**（索引列了某 `<slug>.md` 但文件不存在）由 §二.4 路径引用完整性的 `broken-link` 覆盖
  （MEMORY.md 的 markdown 链接会被扫）——本项不重复检查
- `MEMORY.md` 不存在 → **静默跳过**（老 wiki 迁移期未补索引，不报错）
- `check_wiki_fixtures.py` 的 `agents-md-template-sync`（error）对 AGENTS.md 整文做
  模板渲染字节比对——顶部 `@MEMORY/MEMORY.md` import 行 / 强制 Read 指令 blockquote 等全部
  结构要素由字节比对一次性覆盖。不一致 → 按 wiki-spec §10.1 全量重渲染，
  本地定制逐条与用户裁定搬 `MEMORY/` 或丢弃
- **严重性：info**——MEMORY 是轻量索引非强制入口（区别于 §二.5 `index.md` 覆盖率是 error），
  漏列不阻断但提示 agent 补索引

### 15. related / compared 路径引用完整性

- 校验 wiki 内容页 frontmatter 的 `related`（concept 页使用）与 `compared`
  （comparison 页使用）字段中每条路径对应文件是否存在
- **路径格式约定**（[wiki-spec §9 类型特化字段](wiki-spec.md#类型特化字段llm-写内容页时使用)）：
  **wiki 根相对路径**（如 `concepts/transformer.md`），不带前导 `./`、不带 `../` 跨目录
- 与正文 markdown 链接（约定用文件相对路径）的两层约定：
  - **frontmatter 路径字段**（`related` / `compared` / `sources` 等）——机器消费为主
    （lint / cross-page 综合），统一 wiki 根相对
  - **正文 markdown 链接**（`[text](path)`）——人读为主，in-context 局部引用，
    保持文件相对
- 校验逻辑：每条元素以 `<wiki-root>/<item>` 直接解析（不 `.resolve()`，避免跟随
  不存在的目录时静默吞错）；`is_file()` 判定
- **finding 名**：`related-broken-link`（warn）
- **严重性：warning**——frontmatter 路径字段是机器消费而非人直接阅读内容，与正文
  `broken-link`（error）严重性区分；不阻断但提示用户修正
- **不在本检查范围**：`contradictions` 字段——按 spec §9 既有约定走文件相对
  （`resolve_link(p, c)` 解析），由 §二.13 既有逻辑处理；与 `related` / `compared`
  的两层区分是有意保留

## 三、半定性检查（agent 执行）

跑完 deterministic 检查后，agent 应当再做以下检查（**仅在 wiki 规模 < 200 页
时人工做**——更大规模需 LLM-based 自动检查）：

### 17. 矛盾主张

- 同一概念 / 实体在 ≥ 2 个页里被以**矛盾方式**描述（**内容层**矛盾，区别于 §二 13 的
  frontmatter `contested` 信号——后者是作者已标注、本项是 agent 主动发现未标注的）
- 例：`concepts/context-window.md` 说 "Llama 3 支持 200K tokens"，
  `sources/llama-2.md` 说 "128K tokens"（可能是不同版本，但未注明）
- 检查方法：grep 概念关键词 + 读周围上下文；发现后建议双方补 `contested: true` +
  `contradictions` 互指（让 §二 13 后续能持续追踪）
- **严重性：warning**——可能需要更深入调研

### 18. 缺失交叉引用

- 概念 X 出现在页面 A 的正文里，但 A 没有链接到 `concepts/x.md`
- 例：`sources/foo.md` 提到 "self-attention" 但没链到 `concepts/self-attention.md`
- 检查方法：grep 概念名 + 看是否生成了 link
- **严重性：info**——是 lint 的最高频 finding

### 19. 缺失 entity / concept 页

- 重要概念（出现在 ≥ 3 个 source 页）但没有独立 entity / concept 页
- 检查方法：grep 候选关键词 + 统计出现次数
- **严重性：info**

### 20. 调查方向建议

- 哪些主题"很热门"（多个 source 涉及）但 wiki 内的综合 / 对比页没有
- 例：5 篇 source 提到 RAG，但 `syntheses/rag-evolution.md` 不存在
- **严重性：info**——这是"建议新摄取 / 新合成"的机会

### 21. 资料投放口是否堆积

- `raw/articles/` 是否有大量未摄取文件（跑 `ingest_diff.py` 即可知）
- **严重性：info**——堆积太久会让 ingest 时信息过载

## 四、报告格式

脚本 + agent 一起输出统一格式：

```text
[ERROR] raw-modified: raw/articles/foo.md has uncommitted changes
[ERROR] missing-frontmatter: wiki/concepts/bar.md missing 'sources' field
[ERROR] broken-link: wiki/sources/baz.md links to 'concepts/missing.md' which doesn't exist
[ERROR] orphan-page: wiki/concepts/qux.md is not listed in wiki/index.md
[WARN] stale-summary: wiki/sources/quux.md type=source updated=2024-01-01 (>90 days)
[WARN] log-format: wiki/log.md line 23: '## [bad] ingest | foo' doesn't match expected format
[WARN] reviewed-stale: wiki/concepts/transformer.md reviewed=true reviewed_at=2026-06-15 但 updated=2026-07-01 — LLM 修改后未清 reviewed，建议重新审核
[WARN] index-review-badge-drift: wiki/index.md 条目 'Transformer' 标识为 ✓ reviewed 2026-06-15 但被链页 reviewed=true reviewed_at=2026-06-30 — 日期错
[WARN] legacy-confidence-field: wiki/sources/llama-2.md 含已退役 confidence 字段——请运行 --migrate-confidence
[ERROR] sources-absolute-path: wiki/sources/linux-kernel.md sources 含绝对路径 '/home/user/src/linux/net/ipv4/tcp.c'；必须用相对 wiki 根的路径（如 raw/articles/... 或 raw/external/<symlink>/...），与 lint-checklist §二.3 一致
[ERROR] external-anchor-missing: raw/external/ 下有 symlink ['linux-kernel', 'ray'] 但缺 '.symlink-anchor.toml'（spec §13 必填）
[ERROR] external-anchor-corrupt: raw/external/.symlink-anchor.toml 解析失败或 0 个有效 entry
[ERROR] external-source-name-invalid: raw/external/linux-kernel/ 是子目录，但 raw/external/ 为扁平布局——symlink + anchor 应直接 in external/，不要开 <source-name>/ 子目录
[ERROR] external-symlink-missing: anchor [[entry]] symlink='ray' target='~/src/ray' 但 raw/external/ray symlink 不存在（spec §13 必填关联）
[WARN] external-anchor-orphan: raw/external/my-snapshot 是 symlink 但 anchor 无对应 [[entry]]（spec §13 必填关联）
[WARN] external-target-drift: raw/external/linux-kernel 当前 symlink 解析为 '/home/foo/src/linux-kernel'，但 anchor 记录 '/apsarapangu/disk10/src/linux-kernel'（展开后 '/home/foo/src/linux-kernel'）；anchor 需更新
[WARN] external-git-anchor-stale: raw/external/linux-kernel 的 anchor 与 target git 状态不一致，需刷新；差异：commit anchor='abc1234' git='def5678'
[INFO] missing-xref: wiki/sources/abc.md mentions 'self-attention' but doesn't link to concepts/self-attention.md
[INFO] missing-entity: 'rotary-position-embedding' appears in 4 source pages but has no entity page
[INFO] memory-not-indexed: MEMORY/ocr-tips.md 未在 MEMORY.md 索引中列出
[INFO] pending-review: wiki/concepts/flash-attention.md 未审核 — 待人工复审后置 reviewed: true
[WARN] related-broken-link: wiki/concepts/self-attention.md related[1]='concepts/multi-head-attention.md' 按 wiki 根相对解析为 concepts/multi-head-attention.md，但文件不存在
```

每条带：**严重性** + **类别** + **文件:行** + **描述**。

## 五、Semantic-merge 规则

> 语义合并规则（agent 走 migration plan 时的合并依据）已并入
> [`references/migrate-workflow.md` §六](migrate-workflow.md#六语义合并规则)——
> 含 frontmatter 字段合并 / index 条目合并 / anchor TOML 迁移 5 步 / MEMORY 经验合并 /
> log 严格保留 / 决策树。本节只留指针。

## 六、lint 之后

跑完 lint 后，agent 应当：

1. 整理报告（按严重性排序：error > warn > info）
2. **询问用户先修哪些**——不要一次全修（容易回退或引入新问题）
3. 修完后**重新跑 lint 验证**——不要带着 fix 没验过的状态前进
4. 若启用 git，重大修复 commit 时建议加 `lint: <summary>` 前缀；裸目录树 wiki 跳过 commit 步骤
5. **若跑 fixtures-check**——按 §五 Decision tree 区分脚本 vs LLM 修；
   `fixtures-fix-*` 系列可通过 Edit 落，`fixtures-fix-anchor-merge/-schema/-symlink-matches`
   三条要走 §5.3 五步迁移（不是单 Edit）

## 七、lint 频率

- **小 wiki（< 50 页）**——每月 1 次足够
- **中 wiki（50-200 页）**——每 2 周 1 次
- **大 wiki（> 200 页）**——每周 1 次；可考虑写 cron
- **重大 ingest 后**——建议跑一次（可能引入新 entity / 断链）
- **跨 spec 升级后**——首次跑 fixtures-check 验证约定文件已切到新 spec 字节形态

## 八、lint 的边界

- **不**自动修——只报告；修由用户 / agent 决定
- **不**评估内容质量（不是 fact-checker）——只看结构和纪律
- **不**评估 frontmatter 的语义是否合理（只检查字段存在性 + 类型合法）
- **不**取代 schema（`AGENTS.md`）——schema 是源头，lint 是脚本化检查
- **fixtures 边界**——`check_wiki_fixtures.py` 扫「约定文件」
  （AGENTS.md / CLAUDE.md / .gitignore / wiki/index.md / wiki/log.md / wiki/tags.md /
  MEMORY/MEMORY.md / scripts/SCRIPTS.md / raw/external/.symlink-anchor.toml）的合规性：
  **`metadata.fixtures_check_count` 条** check（11 条结构探测 + 9 条骨架字段比对，后者读 `references/canonical/` +
  `references/fixtures/gitignore.txt` 作 SSOT）；语义合并走 §五由 LLM 判断——脚本不替代人。
  常规 lint 另跑 `check_spec_version`（§二前置）报版本漂移 warn

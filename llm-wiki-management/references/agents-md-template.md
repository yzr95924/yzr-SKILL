# {{TOPIC_NAME}} Wiki — LLM 维护守则

> 这是本 wiki 的**纪律配置**——给维护本 wiki 的 LLM 看的"工作守则"。你（即 LLM）
> 必须在每次操作前先读这份文件；任何对 wiki 的写入都必须符合这里规定的边界。
>
> **本文件（`AGENTS.md`）是本 wiki 纪律的单一真源（SSOT）**——工具无关。由 workspace CLI 在初始化时按
> [`wiki-spec.md`](wiki-spec.md) §2 拷贝生成；后续可由用户编辑，**但**任何与本 skill 的核心原则冲突的修改
> 都视为"非标准配置"，skill 行为不再保证一致。
>
> **读取机制（agent 中立）**：维护本 wiki 的 agent 应在每次操作前读本文件。在 wiki 根目录内工作时——
> **Claude Code** 经同目录薄壳 `CLAUDE.md`（`@AGENTS.md` 递归展开）自动加载本文件；**读 `AGENTS.md` 的其他
> agent**（Qoder / Codex / Gemini CLI 等）原生直读本文件。在别处工作时，由 skill 经 `$LLM_WIKI_ROOT` 按需读取——
> **不依赖 symlink**，多 wiki / 跨项目都能用。（薄壳 `CLAUDE.md` 仅服务于 Claude Code 自动加载约定，无独立纪律。）

<!-- @import 写在 SSOT 内（两边都能加载）：Claude Code 下经薄壳 CLAUDE.md → @AGENTS.md 递归展开后会话常驻；
     其他 agent 能否展开 @import 取决于实现（多未文档化），最坏由 orient ritual 显式 Read 兜底。
     agent 写 memory 时同步更新本索引。 -->
@MEMORY/MEMORY.md

<!-- 同上加载语义。agent 添加/修改/删除脚本时同步更新本索引。详见 `wiki-spec.md` §14 -->
@scripts/SCRIPTS.md

## 一、本 wiki 的边界

### `raw/` —— 真相之源（**LLM 只读，用户可改**）

- 路径：`<wiki-root>/raw/{articles,assets,...}/`（子目录可自由扩展，见下文 `external/`）
- 性质：用户策划的原始资料（论文、剪藏、PDF、图片、播客转写、手写笔记等）
- 纪律：
  - **LLM 在任何情况下不写 / 删除 / 移动 raw/ 下文件**——只读
  - **用户可随时新增 / 更新 raw/**（重新剪藏、重存 PDF 都算）；这是用户的权限，
    不是违反纪律
  - raw 文件一旦被更新（同路径新内容），**由 ingest 重新消化**：更新对应 source
    页的正文 + `updated` 字段，并在 `log.md` 追加一条 ingest。`ingest_diff.py
    --check-stale` 会按 mtime vs source 页 `updated` 标记这类待重新摄取的文件
  - raw 文件路径是 wiki 内 source 页的 `sources` 字段的"永久引用"——改名会断链
  - raw/ 的内容是真相之源；wiki 摘要如与 raw 矛盾，**以 raw 为准**

#### `raw/external/` —— 外部代码仓接入（symlink）

- 路径：`<wiki-root>/raw/external/<source-name>/`
- 用途：把本地已有的外部代码仓（Linux kernel、Ray 源码、papers-with-code 项目等）
  作语料纳入 wiki；**不**内嵌拷贝（占空间 + 失去 commit 锚点），走 symlink +
  锚定元数据
- 一个 `<source-name>/` 下放 symlink + 同目录 `.symlink-anchor.json`：

  ```
  raw/external/linux-kernel/
  ├── .symlink-anchor.json         # {"target": "/home/me/src/linux", "captured_at": "2026-07-01", ...}
  └── linux                       # symlink → /home/me/src/linux
  ```

- **纪律（用户责任，LLM 不代办）**：
  - symlink 由用户用 `ln -s` 或编辑器创建；**没有 anchor 的 symlink = lint 报错**
  - `.symlink-anchor.json` 含 `target`（绝对路径，`readlink -f` 结果）+
    `captured_at`（接入当天）+ `kind: "external-repo"`
  - target 路径被改 / 删除后，anchor 仍记旧值——lint 立刻报 `external-target-dead`
    让用户感知（不静默漏掉）
  - LLM agent **不写、不删、不改** symlink / anchor——延续 `raw/` 的"LLM 只读"
- `.gitignore` 配置：在 §0 已排好 `raw/external/*` 但保留 `**/.symlink-anchor.json`——
  跨机器 clone 时通过 anchor 立即知道"这本来指着哪"

### `wiki/` —— LLM 拥有的复利资产

- 路径：`<wiki-root>/wiki/{entities,concepts,sources,comparisons,syntheses}/`
- 性质：LLM 生成的相互链接的 Markdown 文件
- 纪律：
  - 用户**不写** wiki 页面（编辑 AGENTS.md 除外）
  - 任何 wiki 页面**必须**含 YAML frontmatter（见下）
  - 任何 wiki 页面**必须**在 `wiki/index.md` 中有对应条目
  - 任何 wiki 页面**必须**有 ≥ 1 条 inbound 链接（index 或其它页）

### `log.md` —— 仅追加操作时间线

- 路径：`<wiki-root>/wiki/log.md`
- 纪律：
  - 每次 ingest / query / lint 后**必须**追加一条
  - 格式严格：`## [YYYY-MM-DD] <op> | <title>`（op ∈ {`ingest`, `query`, `lint`, `setup`}；
    `setup` 由 workspace CLI 在初始化时按 `wiki-spec.md` §4 写入首条；
    权威正则见 `page-templates.md` §7）
  - 标题简洁、不超过一行；URL / 详细摘要写在对应页面里
  - **不删不改**——只 append

### `index.md` —— wiki 单一入口

- 路径：`<wiki-root>/wiki/index.md`
- 纪律：
  - 按类别分组列出所有非 log 页面（entities / concepts / sources / comparisons / syntheses）
  - 每条带链接 + 一句话摘要
  - 每次 wiki 内容变更后**必须**同步（宁可多改）

### `MEMORY/` —— LLM agent 的持久化记忆

- 路径：`<wiki-root>/MEMORY/`
- 性质：LLM agent 在 ingest / query / lint 过程中沉淀的**经验、踩坑、用户偏好**——
  不是 wiki 内容、不是操作时间线，而是 agent 私有记忆；对应 SKILL §四层架构第 3 层

> **本段 SSOT 反指**：MEMORY 条目形式（完整 vs 短）的权威定义在仓库根
> `MEMORY/MEMORY.md`「规则」段；本文件是 wiki 仓自带模板（workspace CLI init 时拷贝到目标
> wiki 根，跨仓引不到 SKILL.md / 仓库根 MEMORY.md），必须自包含。与 SSOT 措辞故意保持一致，
> 改 SSOT 时同步改本段。

- **条目形式按事实颗粒度选**（与项目根 `CLAUDE.md` 同步）：
  - **完整条目**——需要解释"为什么这么做"或"将来怎么用"（含上下文 / 解决步骤 / 未来如何避免）→
    建 `MEMORY/<slug>.md`（frontmatter 5 必填 + 正文）+ 索引行 `- <slug> — 一句话 → [正文](<slug>.md)`
  - **短条目**——纯 reminder / 单一偏好 / 无需 why + how → 索引行直接 `- 一句话事实`，
    不单独建 `.md` 文件
  - 两种格式可在同一 `MEMORY/MEMORY.md` 共存；lint `memory-not-indexed` 只兜底"有 .md 但未索引"
- 纪律：
  - 用户**不**直接编辑 MEMORY/（这是 agent 私有记录）
  - 任何 `MEMORY/*.md`（**仅完整条目**）**必须**含 frontmatter 5 必填
    （title / type / created / updated / tags），与 wiki 内容页规则一致
  - **`MEMORY/MEMORY.md` 是索引、无 frontmatter**——被本文件顶部的 `@MEMORY/MEMORY.md`
    import 内联、会话常驻；写每条时**同步追加索引一行**（按上"条目形式"选格式），
    否则下次会话读不到
  - **不**强制在 `wiki/index.md` 列出（不在 wiki 单一入口约束范围内）
  - **不**要求 inbound 链接
  - 目录结构与契约详见 `wiki-spec.md` §5

### `scripts/` —— 本 wiki 仓的自维护脚本目录（0.9.0+）

- 路径：`<wiki-root>/scripts/`
- 性质：**用户 + LLM agent 共有**的项目级脚本目录——放置项目专属的 ingest 扩展（批量 PDF prep、
  主题模板预处理等）、外部 CLI 胶水（pdf 抽图 / obsidian 同步等）、自动化 hook（pre-commit 校验、
  ingest 前清洗等）。**不**放置 llm-wiki-management skill 自带脚本（那些 SSOT 在
  `llm-wiki-management/scripts/`）
- 索引文件：`scripts/SCRIPTS.md`（无 frontmatter，与 `MEMORY/MEMORY.md` 同形态）——
  被本文件顶部 `@scripts/SCRIPTS.md` import 会话常驻。**每条工具必须列一段**：
  - 使用场景（agent 触发条件）
  - 调用约定（一行可粘贴）
  - 作用（做什么 / 产出什么 / 副作用）
  - 前置依赖（可选，`.sh` 需 `chmod +x`；`.py` 走 `python3`）
- 纪律：
  - **添加 / 修改 / 删除脚本文件**与**同步更新 `SCRIPTS.md` 段**是原子动作——完成时两者必须一致
  - **不**写 frontmatter（scripts/ 是代码，不是 wiki 内容页）
  - **`scripts/` 不参与 `lint_wiki.py` 扫描**——脚本代码质量由维护者自行负责
  - **agent 不自动遍历 `scripts/` 跑任何东西**——必须先 `Read SCRIPTS.md` 找到对应段，
    再按段中的调用约定显式执行；防止意外 execute
  - git 跟踪策略：默认跟踪；启用 git 时跟 wiki 一起 commit；未启用 git 时跟 wiki 走纯目录树
- 不适用：llm-wiki-management skill 自带的 `lint_wiki.py` / `ingest_diff.py` / `log_format.py`
  ——这些脚本版本由 skill 仓管，**不**复制进 `scripts/`（避免版本漂移）
- 完整契约与设计动机见 `wiki-spec.md` §14

## 二、页面类型与 frontmatter 约定

> **权威定义在 `page-templates.md` §二（页面模板 + 字段定义）**——
> 本表只是 setup 后在 wiki 内的速查。顺序与该处保持字母序一致（comparison → concept →
> entity → source → synthesis）。

| 类型 | 目录 | `type` 字段 | 关键字段 |
| --- | --- | --- | --- |
| 对比页 | `comparisons/` | `comparison` | `compared`（被对比对象路径数组） |
| 概念页 | `concepts/` | `concept` | `related`（相关概念路径数组） |
| 实体页 | `entities/` | `entity` | `aliases`（别名数组，方便搜索） |
| 资料页 | `sources/` | `source` | `sources`（必填，raw/ 路径） |
| 综合页 | `syntheses/` | `synthesis` | `threads`（线索标题数组）+ `sources`（必填，wiki 内其它页路径） |

**所有页面共有 frontmatter**（完整定义 + 类型特化字段见 `page-templates.md` §一）：

```yaml
---
title: <页面标题>
description: <一句话摘要>  # 推荐；index.md 摘要来源（OKF §4.1）
type: <entity|concept|source|comparison|synthesis>
tags: [<标签>]
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [<raw 相对路径数组>]  # source / synthesis 必填；entity / concept 可选
---
```

### Tag Taxonomy（防 tag 漂移）

> **本段 SSOT 反指**：tag 白名单规则的权威定义在 `wiki-spec.md` §9.1「tag 白名单来源」；
> 本文件是 wiki 仓自带模板（workspace CLI init 时拷贝到目标 wiki 根，跨仓引不到 SKILL.md），必须自包含。
> 与 SSOT 措辞故意保持一致，改 SSOT 时同步改本段。

`tags` 字段是 wiki 索引和过滤的入口；不约束会随 ingest 漂移成噪声。本 wiki 的 tag
白名单放在 [`wiki/tags.md`](wiki/tags.md)（**0.8.0+ 起从此处迁出，原先嵌在本纪律文件
（0.11.0 前为 `CLAUDE.md`）的 `### Tag Taxonomy` 段，由 `--check-version --apply` 自动迁移）；本 wiki 创建时由
workspace CLI 生成空白 wiki/tags.md，由 LLM 与用户共同确认主题分类（**10-20 个一级 tag 是建议值，
非权威阈值**——具体数量由用户/agent 共同裁定，按主题复杂度伸缩）。

**规则**：

- agent 在 ingest / query 时遇到新 tag → **直接追加**到 `wiki/tags.md`（无需询问用户），保持字典随 wiki 生长
- 单页 `tags` 建议 3-7 个；过多说明页面主题过散，考虑拆分或聚焦
- tag 取值严格小写 + kebab-case，与文件名命名一致
- **审计循环**：用户可在 `wiki/tags.md` 中**直接删除**误判的 bullet；下次 lint 把
  `tag-not-in-taxonomy`（info）报到所有还引用已删 tag 的页面，由用户裁定二选一：
  重新加回 / 从页面删除 tag
- `lint_wiki.py` 对 `tags` 中**不**在 wiki/tags.md 白名单的值报
  `tag-not-in-taxonomy`（info 级，不阻断）

> **格式约束（影响 lint 解析）**：`wiki/tags.md` 的 tag 列表必须是**裸 bullet**
> （每行 `- ...`），不能包在 code block / HTML comment 里——`parse_tag_taxonomy` 只读裸文本。
> 格式示例：`- 模型：model / architecture`（中文 / 英文分隔符都支持）。
> 多个 tag 用 `/` `，` `,` 任意一种分隔。`lint_wiki.py` 找不到任何 tag 来源或
> 解析出 0 个 tag 时**静默跳过**（不报错），避免新 setup 的 wiki 必报错。

### Page Thresholds（建页/追加/归档决策）

不是每个 entity / concept 都值得独立成页——没阈值 wiki 会被名词堆爆，几个月后 index 翻不到底。

| 动作 | 触发条件 |
| --- | --- |
| **新建 entity / concept 页** | 该 entity / concept 在 ≥ 2 个 source 页中被提到 **或** 是某 source 页的中心主题 |
| **追加到已有页** | source 页提到一个已被覆盖的 entity / concept——追加"参考来源"段即可（不重写） |
| **不创建页** | 路过提及（脚注 / 一次出现的名字）、领域外的细节、与本 wiki 主题无关 |
| **拆分页** | 单页正文超过阈值（SSOT = `scripts/lint_wiki.py` 的 `PAGE_SIZE_THRESHOLD`）——拆成子主题 + cross-link，避免单页过于庞杂 |
| **归档页** | 内容被完全取代 / 主题域变化——加 `archived: true`、从 `index.md` 移除（log 走 `ingest` 或 `lint` op，记一条说明性条目） |

> **为什么有阈值**：宁可错过一个 entity 也不要堆十个空页。"克制"是 wiki 长期可用性的具体化——
> 一次放过一个小 entity 几乎无成本；堆一千个空 entity 后 lint 报告会被噪声淹没。

### 认知质量信号（可选，防"弱主张固化成事实"）

> 字段语义权威定义在 `page-templates.md` §一「可选：可信度与认知质量信号」；
> 本节是 wiki 内的速查 + 何时标的指引。四个字段**全部可选**，互不依赖。

四个可选 frontmatter 字段：

| 字段 | 取值 | 何时标 |
| --- | --- | --- |
| `reviewed` | `true`（仅在为 true 时写） | 人工**已审核该页**——写 `reviewed: true` + `reviewed_at: <今天>` |
| `reviewed_at` | `YYYY-MM-DD` | 与 `reviewed: true` 成对出现 |
| `contested` | `true`（仅在为 true 时写） | 本页含**尚未裁定**的矛盾主张——搭配 `contradictions` 指向对端 |
| `contradictions` | wiki 页路径数组 | 与本页主张冲突的页面（**双向标注**：A 标 B，B 也标 A） |

`lint_wiki.py`（§二 13）会把 `contested: true` / 非对称 `contradictions` 拎出来供复审，
未审核页面会标 `pending-review`（info，新常态）。**核心理念**：单源弱断言一旦写进 wiki
不加标注，时间一长会被当成"既成事实"——这是比断链更隐蔽的腐烂，这些字段让它显性化。

**生命周期规则（LLM 必读）**：`reviewed: true` 是"我对这一刻的内容背书"的快照，**不是永久标签**。
任何对页面正文的 LLM 修改都会让戳失效——必须**删除** `reviewed` + `reviewed_at` 回到默认未审核状态，
由人重新审。`lint_wiki.py` 用 `reviewed-stale` 兜底：`reviewed: true` 存在且
`updated > reviewed_at` 时给 warn，把漏清戳的页面拎出来。

> **本段 SSOT 反指**：reviewed 戳生命周期的权威定义在仓库 `page-templates.md` §一
> 「生命周期规则」；本文件是 wiki 仓自带模板（workspace CLI init 时拷贝到目标 wiki 根，
> 跨仓引不到 SKILL.md），必须自包含。与 SSOT 措辞故意保持一致，改 SSOT 时同步改本段。

### 矛盾处理 Update Policy（ingest 遇到"新资料与已有页冲突"时）

ingest 时新资料与已有页主张冲突，**不要静默覆盖**，按以下顺序处理：

1. **先看日期**——更新的来源一般覆盖旧的；但若旧来源更权威（如官方技术报告 vs 博客），
   保留两者并进入第 2 步
2. **判定是否真矛盾**——版本差异（Llama 3.0 vs 3.1 的 context window）、上下文差异
   （不同评测条件）不算矛盾，加注明即可；确属矛盾进入第 3 步
3. **显式记录两种说法**——在页面正文写出 A 说 X（来源 + 日期）、B 说 Y（来源 + 日期），
   不要"和稀泥"挑一个；双方 frontmatter 都设 `contested: true` + `contradictions` 互指
4. **等 lint 复审**——下次 lint 会把 `contested` 页拎出来（§二 13）；与用户一起裁定后，
   移除 `contested`（**不再保留 `confidence` 字段**——0.7.0 起已退役；如该页此前已审核，
   按"生命周期规则"判断是否需要重新审）

### Index 扩容（防 index.md 翻不到底）

`index.md` 是 wiki 的单一入口，但条目无限增长后同样会腐烂——给它两条护栏：

| 触发条件 | 动作 |
| --- | --- |
| 单个类别（如 `## Sources`）> 50 条 | 按首字母或子域拆成小段（如 `### A-F` / `### G-M`） |
| `index.md` 总条目 > 200 | 新建 `wiki/_meta/topic-map.md` 按主题聚合页面（index 仍按 type 列，topic-map 按主题导航） |

> 这是"建页阈值"在入口侧的对偶——建页克制控制"有多少页"，扩容规则控制"index 还好不好翻"。
> lint 目前**不**自动检测 index 条目数（与 log-rotation 同理：报告而非强制）；agent 在
> lint 半定性环节（§三）观察 index 体积，超阈值时建议用户拆段 / 建 topic-map。

## 三、写入纪律

1. **写前必搜**——创建新页面前先 grep / search `wiki/` 确认是否已有同名或近义页
2. **写后必同步**——新增 / 改 / 删页面后必须同步：
   - `index.md`（条目增减）
   - 相关的 entity / concept 页（追加"参考来源"段，**不重写**）
   - `log.md`（追加操作条目）
3. **改写而非新建**——若已有同类页，**编辑它**而不是建新的副本
4. **重写时保留 frontmatter**——不要因为改写丢失 `type` / `tags` / `sources` 字段
5. **交叉引用走相对路径**——`[link](../concepts/transformer.md)`，**不要**用 wikilink
   `[[transformer]]`、**不要**用绝对路径
6. **路径稳定**——文件名一旦确定就是永久 ID；想改名时重命名文件 + 更新所有引用（启用
   git 时用 `git mv` 保留 history；未启用 git 时用普通 `mv` + 全量更新引用）

## 四、阅读纪律

1. **读 raw 优先**——source 页的引用若与 raw 矛盾，回到 raw 复核
2. **读 index 起手**——找相关页面前先看 `index.md` 分类
3. **不读 log 内容**做证据——log 是时间线，证据在源页里
4. **跨页综合走 query 操作**——读多页 + 综合 + 给引用，不要拼接

## 五、Query 纪律

1. **先看 index，再读相关页**——不要直接全量 grep
2. **答案带引用**——每条事实带 `(来源: <page path>)`
3. **矛盾显式标注**——不要"和稀泥"
4. **好答案问归档**——对比 / 综合 / 发现新联系 → 询问用户是否写回 wiki

## 六、Lint 纪律

1. **脚本检查 deterministic 部分**——raw/ 不可变性、frontmatter、index 覆盖、断链、log 格式
2. **agent 检查半定性部分**——矛盾、缺失交叉引用、过期主张
3. **修 lint 不要回退 schema**——若 lint 报告与本文件冲突，**先讨论用户**再决定

## 七、本文件本身的纪律

- 本文件是 schema，**不是 wiki 内容**——不要往里塞 wiki 主题相关的笔记
- 改本文件 = 改 skill 行为 = 大事；先和用户确认
- 若 wiki 启用 git，每次改建议 commit 并加清晰的 commit message；未启用 git 跳过此步

## 八、当前配置

| 字段 | 值 |
| --- | --- |
| 主题 | {{TOPIC_NAME}} |
| 创建日期 | {{SETUP_DATE}} |
| Wiki 根 | <由 LLM_WIKI_ROOT 环境变量或 init 时确定> |
| Wiki Spec 版本 | {{WIKI_SPEC_VERSION}} |
| CLI 版本 | {{CLI_VERSION}} |

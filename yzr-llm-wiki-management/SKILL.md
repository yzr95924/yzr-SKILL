---
name: yzr-llm-wiki-management
description: 当用户和本地、单用户、复利型 Markdown 个人 wiki（Karpathy 'LLM owns wiki' 模式）
  打交道时使用本 skill —— 覆盖：初始搭建、批量摄取 raw/ 资料（论文 / 文章 / 剪藏 /
  外部代码仓 symlink 接入）、跨页综合 / 对比 / 矛盾协调 / 答案归档回 wiki、
  矛盾 / 孤儿 / 过期摘要 lint、spec 升级迁移。坚持 raw/ 用户掌控 + wiki/ LLM 拥有 +
  AGENTS.md 单一真源 四层纪律。不用于云端 / 团队协作 wiki（Notion / Confluence / Outline / GitHub Wiki）
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-07-11
  wiki_spec_version: 0.24.0
  fixtures_check_count: 18
---

# LLM Wiki Management

按 Karpathy [LLM Wiki 设计哲学](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
维护一个**本地**、**复利累积**的知识库：用户只管读 + 提供资料 + 提问题，LLM 负责摘要、
交叉引用、归档、簿记这些"无聊的部分"。和 `yzr-outline-wiki-upload` 等云端 skill 的关键区别是
**本地文件 + 三层纪律**——vs 云端 MCP 单层文档。

本 skill 提供三块交付物：

- **SKILL.md（本文）**——工作流 + 纪律的"宪法"
- **scripts/**——ingest_diff.py / lint_wiki.py / log_format.py + **check_wiki_fixtures.py**
  （fixtures 一致性检查；`lint_wiki.py --check-version` 自动调一次）。把高频
  deterministic 任务固化下来（**不**含 setup_wiki——wiki 仓的创建由外部 workspace CLI
  负责）。当前检查项数见 `metadata.fixtures_check_count`（详见
  [`references/migrate-workflow.md`](references/migrate-workflow.md) + §五 Migrate）。
- **references/**——按需加载：AGENTS.md schema 模板 + CLAUDE.md 薄壳模板、各操作详细流程、页面模板、
  wiki-spec.md（CLI 实现契约）、fixtures（CLI 字节级比对金标准）、migrate-workflow.md §六
  (语义合并规则，agent 走 .migration-plan.json 时的合并依据)

## 何时使用 / 不使用

### 使用

- 用户在对话中说"摄取/归档到 wiki / ingest to wiki / 把这篇文章整理进 wiki"
- 用户在对话中说"wiki 里有 X 吗 / 在 wiki 里搜一下 / 总结 wiki 中关于 Y 的内容"
- 用户在对话中说"lint wiki / wiki 健康检查 / 找矛盾 / 找孤儿页"
- 用户在对话中说"升级 wiki / 迁移到最新 spec / 检查 wiki 版本 / 老格式 / reformat"——
  走 §5 Migrate
- 用户指向 `<wiki-root>/raw/` 里新出现 / 未归档的文件
- 用户首次提到"我想搭一个 wiki 用来管理 X 的研究 / 读书笔记 / 项目"
- 用户提到"AGENTS.md 怎么写 / raw/ 和 wiki/ 的边界"
- 用户想把外部代码仓（Linux kernel / Ray 源码等）作为语料纳入 wiki——走
  `raw/external/` 扁平的 symlink + `.symlink-anchor.toml` 路径（详见
  [wiki-spec §13](references/wiki-spec.md#13-rawexternal外部代码仓接入可选)）

### 不使用

- **云端协作 wiki**（Notion / Confluence / Outline Wiki / GitHub Wiki）——走
  `yzr-outline-wiki-upload`（写 / 编辑）/ `yzr-outline-wiki-search`（搜 / 读）
- **一次性文档生成**（不是累积型）——直接用普通文件写入流程
- **没有 raw/ 资料 + 没有累积需求**——skill 的价值在"复利"，一次性整理用不上
- **需强结构化数据库**（带 schema / SQL / 全文检索后端）——wiki 规模 ≤ 数百页时
  index.md 足够；超过该规模再考虑迁移到专用工具
- **多人实时协作**——本 skill 假设单人使用（多账号实时协同走云端 wiki）

## 输入 / 输出

### 启动时需具备的信息

| 信息 | 来源 | 备注 |
| --- | --- | --- |
| Wiki 根目录 | `LLM_WIKI_ROOT` 环境变量，或交互时问 | 例 `~/wiki/llm-systems` |
| 主题名 | setup 时一次性指定，写入 `AGENTS.md` | 例 "LLM Systems" |
| 操作类型 | 用户自然语言 | ingest / query / lint / migrate / setup |
| 触发资料 | ingest 时给文件路径或目录 | 必须在 `raw/` 内 |

### 操作产物

- **setup** → 由外部 workspace CLI 完成（按 [`references/wiki-spec.md`](references/wiki-spec.md) 落盘），
  本 skill 不实现创建逻辑；产物形态为目录结构 + AGENTS.md（SSOT）+ CLAUDE.md（薄壳）+
  wiki/index.md + wiki/log.md + MEMORY/MEMORY.md + .gitignore
- **ingest** → 新增 / 更新 `wiki/sources/<slug>.md` + 同步实体 / 概念页 + 追加
  `log.md` 条目 + 更新 `index.md`
- **query** → 对话中给出答案（带引用），**可选**把答案归档为 `wiki/comparisons/`
  或 `wiki/syntheses/<slug>.md`
- **lint** → `log` 中报告：raw/ 是否被改、孤儿页、断裂交叉引用、过期摘要、缺
  frontmatter、log.md 格式
- **migrate** → 跑 `scripts/lint_wiki.py --check-version` 输出 spec 版本 + legacy 现场
  报告；`--apply` 落盘 `<wiki-root>/.migration-plan.json` 供 agent 按 `wiki-spec.md`
  附录 B 走 Edit/Write 修复；详见 §5 Migrate

## 设计决策

### 四层架构——为什么是四层

参考 Karpathy gist 的核心论断：**"Knowledge 的累加依赖纪律，不依赖意志力"**。
四层各自承担一个责任，互相制衡：

1. **`raw/` 真相之源**——用户只管策划原始资料（论文、剪藏、PDF、笔记、播客转写），
   对 LLM 只读。**唯一例外**：`raw/external/` 顶层（**扁平布局，0.17.0+**）下 LLM **可**创建 symlink +
   写 `.symlink-anchor.toml` 的 `[[entry]]` 块（首次接入 + 漂移刷新）——详见
   [wiki-spec §13.3](references/wiki-spec.md#13-责任切分用户--llm-共有)
   - [wiki-spec §13.5](references/wiki-spec.md#135-git-仓锚定要求lint-强制)；其余 `raw/` 子树
   （articles / papers / assets / clippings / podcasts 等）LLM 仍只读。
   **纪律完整定义**（含 LLM 不写 / 用户可改 / 改名会断链 / wiki 与 raw 矛盾以
   raw 为准 4 条）见 `<wiki-root>/AGENTS.md` §一（由 workspace CLI 在 init 时拷到每个 wiki，
   模板见 [`references/agents-md-template.md`](references/agents-md-template.md)）。
   `raw/` 下子目录自由组织——CLI 默认建 `articles/` + `assets/`，但 `podcasts/` /
   `clippings/` / `papers/` / `external/` 等自定义子目录同样可用；`ingest_diff.py` 递归扫整棵 `raw/`。
2. **`wiki/` 复利资产**——LLM 拥有这一层（5 个内容页子目录 + index.md）。人类**不写**
   wiki 内容，只读 + 提问题。每次摄入新资料或回答新问题，wiki 都变得**更厚**而不是更乱。
3. **`MEMORY/` agent 持久化记忆（与 `wiki/` 平级）**——LLM agent 在工作中沉淀的经验、踩坑、用户偏好，
   物理上位于 `<wiki-root>/MEMORY/`（与 `wiki/` 同级、不嵌在 `wiki/` 下），与 wiki 内容页
   同归属（LLM 写、用户不写）但**不**走单一入口约束、不被 lint 当 wiki 内容页扫。`MEMORY.md`
   是单一真源（无 frontmatter），AGENTS.md 顶部一行 `@MEMORY/MEMORY.md` `@import` 加载——
   agent 自动展开拿到 MEMORY 全文（详见 [`references/agents-md-template.md`](references/agents-md-template.md)
   顶部 L2 索引段 + HTML 注释 Read 指引）。改 MEMORY 只改 `MEMORY.md` 这一处、
   `@import` 引用同步指向全文，无副本漂移。
   为什么搬到 `<wiki-root>/MEMORY/`：对应 §四层架构第 3 层（独立于 wiki/ 内容）、将来 publish 时
   MEMORY 自然留作私有层不外传。详细规则见 spec §5。
4. **`AGENTS.md` 纪律配置（SSOT）+ `CLAUDE.md` 薄壳**——把"wiki 怎么写 / 写什么 / 不写什么"的约定
   集中到 `AGENTS.md`（工具无关单一真源），是维护本 wiki 的 agent 的"宪法"。`CLAUDE.md` 是
   `@AGENTS.md` 薄壳，仅供 Claude Code 经自动加载约定读到 SSOT；读 `AGENTS.md` 的其他 agent
   （Qoder / Codex / Gemini CLI 等）原生直读。**L2 索引走 `@import` 收口**：
   AGENTS.md 顶部单行 `@MEMORY/MEMORY.md` + 单行 `@scripts/SCRIPTS.md` ——agent 自动展开
   拿到 L2 索引（详见 spec §5.1 + §14.3；Codex 不展开 `@import`，由
   [`references/agents-md-template.md`](references/agents-md-template.md) 顶部 HTML 注释
   Read 指引直接 Read，两处不重复实现）。
   没有它，LLM 会退化成普通聊天机器人；有它，LLM 是"纪律严明的 wiki 维护者"。**为什么 AGENTS.md
   作 SSOT + CLAUDE.md 薄壳**（套用 `yzr-multi-agent-context` 方法）：一套真源、
   Claude Code / Qoder / Codex 多 agent 兼容（详见 `yzr-multi-agent-context/SKILL.md`「设计
   与原理」段）。

### 四个核心操作——为什么是四个

| 操作 | 输入 | 输出 | 价值 |
| --- | --- | --- | --- |
| **ingest** | `raw/` 新文件 | 摘要页 + 交叉引用 + log 条目 | 把原始资料变成可查询的结构 |
| **query** | 自然语言问题 | 综合答案（带引用）+ 可选归档 | 复用 + 复利：好答案不回聊天记录 |
| **lint** | 整个 wiki | 报告矛盾 / 孤儿 / 过期 | 防止知识库腐烂 |
| **migrate** | 含 §八 的 wiki | legacy + `.migration-plan.json` +<br>agent 修复后的最新 spec 兼容 wiki | spec 演进时不破坏老 wiki 沉淀 |

每个操作都**双向回报**：ingest 让 query 更好用；query 让 wiki 更厚；lint 让 ingest
不会越积越乱；migrate 让长跑 1-2 年的 wiki 在 spec 演进时不掉队。**单独跑任一个都亏**——
这就是"复利"的本质。migrate 与其他三个不同——它是**周期触发**而非每次 wiki 操作触发
（spec 升版本时才跑），但缺了它老 wiki 会**腐烂在格式层**而不是内容层，更难察觉。

### 为什么不用云端

`yzr-outline-wiki-upload` / `yzr-outline-wiki-search` 走云端 MCP（Outline Wiki），适合团队协作、外部分享、
权限管理。本 skill 走**本地文件**（git 为可选 opt-in），原因：

- **隐私**——研究 / 读书 / 个人思考不需要上云
- **可移植**——纯 Markdown + 文件，不绑任何平台
- **无外部依赖**——不需要 OAuth / API key / 网络
- **版本控制可选**——git（setup 时 `--git` 启用）提供 history / diff；不启用也不影响
  ingest / query / lint（详见 [`wiki-spec.md` §7](references/wiki-spec.md)）

> **立场**：wiki **不依赖 git 即可工作**——默认落盘为纯目录树，git 仅在 setup 时
> 用户显式 opt-in（`--git`）才启用。

两套 skill **不冲突**：本地研究沉淀 → 云端分享，方向是单向的。

## 执行原则 / 边界

### 核心原则

> **操作前置（orient ritual，所有操作通用）**：每次 ingest / query / lint 启动前，**不依赖 symlink**
> ——按以下顺序读完四件套再动手：
>
> 1. `Read <$LLM_WIKI_ROOT>/AGENTS.md`——拿到本 wiki 的主题名、边界配置、
>    Page Thresholds（纪律 SSOT 是 `AGENTS.md`；`CLAUDE.md` 是 `@AGENTS.md` 薄壳，不持纪律）。
>    AGENTS.md 不再含 tag 白名单（迁出到 `wiki/tags.md`——见本节 §核心原则 §11）。AGENTS.md
>    顶部一行 `@MEMORY/MEMORY.md` + 一行 `@scripts/SCRIPTS.md` `@import`——agent 自动展开
>    拿到 MEMORY / scripts 全文（详见 [`references/agents-md-template.md`](references/agents-md-template.md)
>    顶部 HTML 注释 Read 指引）。**别处由 skill 按需读 AGENTS.md 时** 也走相同的 `@import` 链路，
>    **不**需要单独 `Read MEMORY.md` 补齐索引（除非要看各 `<slug>.md` 正文）。
> 2. `Read <$LLM_WIKI_ROOT>/wiki/index.md`——知道有哪些页、分布在哪些类别，避免重复创建 / 漏交叉引用
> 3. `Read <$LLM_WIKI_ROOT>/wiki/log.md`（最近 ~30 行即可）——看清最近活动，避免重复
>    ingest / 漏归档旧工作
> 4. **`Read <$LLM_WIKI_ROOT>/scripts/SCRIPTS.md`**（按需）——确认本 wiki 是否有
>    项目级扩展脚本的**完整分节契约**（使用场景 / 调用约定 / 作用 / 前置依赖）；不强制（wiki 可无
>    scripts/），但**触发非标工作流前**必须先查（AGENTS.md 顶部的 `@scripts/SCRIPTS.md` import
>    已加载全文，详细契约随读出）
>
> 四件套任一未读完不写任何 wiki 内容。100+ 页的 wiki 还应在 `wiki/` 全域
> `Grep "<topic>"` 补一次——单看 index.md 可能漏掉 entity/concept 页之间的引用关系。

1. **raw/ 由用户掌控，LLM 只读**（schema 见 `<wiki-root>/AGENTS.md` §一）——LLM 从不写/删/移 `raw/` 下文件；
   用户可随时新增/更新 raw/（重新剪藏、重存 PDF 都算），改动由 ingest 重新消化（更新对应 source 页正文 +
   `updated`，`ingest_diff.py --check-stale` 按 mtime vs source `updated` 标记待重新摄取项）
   **唯一例外**：`raw/external/` 顶层（**扁平布局**）下 LLM 可主导创建 symlink +
   写 anchor 的 `[[entry]]` 块（详 §1 批处理摄取外部代码仓子节 + wiki-spec §13.3）
2. **wiki/ 由 LLM 撰写**——用户从不手写 wiki 页面（编辑 AGENTS.md 除外，那是 schema）
3. **AGENTS.md 是 schema，不是文档**——它是给 LLM 看的"工作守则"，不要往里塞内容
4. **每次写入必更 log.md**——格式严格，权威定义在 `<wiki-root>/AGENTS.md` §一（正则见
   [`references/page-templates.md`](references/page-templates.md) §7；脚本以
   `scripts/lint_wiki.py` 为准）
5. **每页必带 YAML frontmatter**——5 必填（`title` / `type` / `created` /
   `updated` / `tags`）+ 推荐 `description`（`index.md` 条目摘要从它来）。
   **为什么是这 5 个**见 [wiki-spec.md §9](references/wiki-spec.md)（OKF 字段齐全性 × lint
   一致性的最小交集；少于 5 字段会让"抓腐烂"判定失效）。
   **例外**：
   - `wiki/index.md` / `wiki/log.md` = **4 字段必填**（省 `description`）
   - `MEMORY/MEMORY.md` / `wiki/tags.md` = **无 frontmatter**（索引片段 + tag 白名单）
   - `MEMORY/*.md` = **仅 `title` 必填**（其余 5 字段全 optional——MEMORY 是 agent
     私有记忆，frontmatter 是可选 decoration）；`type` 若取扩到 7 类（5 内容页 + `memory` /
     `memory-entry`）；`tags` 若取**不**走 `wiki/tags.md` 白名单；`reviewed` / `reviewed_at`
     不进 lint 兜底（MEMORY 无"人工 review"语义角色）
   **权威定义**（`type` 取值 / reserved 规则 / `sources` 字段特化 / 可信度信号
   `reviewed` / `contested` / `contradictions`）见 [`references/page-templates.md`](references/page-templates.md) §一
   ——本条不重抄，lint 阈值同步以该处为准。**`tags` 管理见 §核心原则 §11**。
6. **交叉引用走相对路径**——`[link](sources/bigtable.md)`，不用绝对路径，不用 wikilink
7. **index.md 是 wiki 内容页的单一入口**——所有非 log / 非 MEMORY 的页面必须在 `wiki/index.md` 中出现
8. **query 的好答案必问"是否归档"**——能写回 wiki 的不要浪费在聊天里
9. **`MEMORY/` 是 LLM agent 的私有记忆**——遇到踩坑、发现用户偏好、跨 ingest 关联
   时主动追加；frontmatter **仅 `title` 必填**（其余 5 字段全 optional，与 wiki 内容页
   的 5 必填规则解耦——spec §5.2），**不在 index.md 强制列出**，**但每条
   必须在 `MEMORY/MEMORY.md` 索引列一行**——AGENTS.md 顶部 `@MEMORY/MEMORY.md` `@import`
   自动加载全文，**不**需要单独同步 AGENTS.md。lint `memory-not-indexed` 兜底漏列。
   MEMORY 沉淀只改 `MEMORY.md` 这一份，AGENTS.md `@import` 单行引用同步指向全文，
   **无**双写漂移，索引走 `@import` 不占 L1 词数。详见 spec §5 +
   [`wiki-spec.md`](references/wiki-spec.md#5-memory) + §四层架构第 3 点
10. **LLM 修改已审核页必须清 `reviewed` 戳**——任何对页面正文的 LLM 修改（ingest 重摄取 /
   query 归档 / refine / 任何 Edit/Write）让戳失效；**必须删 `reviewed` + `reviewed_at` 两字段**
   回到默认未审核态，由人重新审。`lint_wiki.py` 用 `reviewed-stale`（`reviewed: true` 存在且
   `updated > reviewed_at`）兜底。SSOT：[`page-templates.md` §一](references/page-templates.md#生命周期规则llm-必读)。

    > **注**：同样的规则也会出现在
    > [`references/agents-md-template.md`](references/agents-md-template.md)
    > §二「认知质量信号」末段——那里是 wiki 自带的 AGENTS.md 模板必须自包含（跨仓引不到 SKILL.md）；
    > 两处措辞故意保持一致。SSOT 是 `page-templates.md` §一。

11. **tag 白名单在 `wiki/tags.md`**（详
   [wiki-spec.md §9.1](references/wiki-spec.md#91-tag-白名单来源080)）——LLM auto-extend bullet +
   用户审计循环（删 bullet → 下次 lint 报 `tag-not-in-taxonomy` 由用户裁定）；`wiki/tags.md` 无
   frontmatter，与 `MEMORY/MEMORY.md` 同形态。跨 spec 升级走 `lint_wiki.py --check-version --apply`。
   `agents-md-template.md`「Tag Taxonomy」段自包含同样规则（必须——wiki 仓自带模板跨仓引不到 SKILL.md）。

12. **本 wiki 自维护脚本走 `<wiki-root>/scripts/` + `SCRIPTS.md` 索引**（详
   [wiki-spec.md §14](references/wiki-spec.md#14-scripts本-wiki-仓扩展脚本目录)）——`SCRIPTS.md`
   单段形态：每脚本以 `` - `<name>` — <一句话用途> `` one-liner 起头 + `### <name> — <label>`
   子节含 4 要素契约（使用场景 / 调用约定 / 作用 / 可选前置依赖）。AGENTS.md 顶部
   `@scripts/SCRIPTS.md` `@import` 自动加载全文——agent **必须**先看该索引行知道有哪些脚本，
   再按需 `Read scripts/SCRIPTS.md` 取完整契约（`@import` 展开后即见），按"调用约定"显式执行，
   **不**自动遍历 `scripts/`；改脚本只改 `SCRIPTS.md` 这一份。`scripts/` 不走 §9 5 必填、
   不参与 `lint_wiki.py` 扫描、不复制 skill 自带脚本（版本漂移风险）。
   `agents-md-template.md`「Wiki-local scripts」段自包含同样规则。

### 边界

- **不**编辑 `raw/` 下任何文件——LLM 只读；用户可改，改后由 ingest 重新消化
  **唯一例外**：`raw/external/` 顶层（**扁平布局**）下 LLM 可创建 symlink +
  写 `.symlink-anchor.toml` 的 `[[entry]]` 块（首次接入 + 漂移刷新；spec §13.3）
- **不**删除 `wiki/` 下的页面——用 `archived: true` 标记 + 从 index 移除；想真删直接删文件（启用 git 时用 `git rm`，未启用时用普通 `rm`）
- **不**绕过 `AGENTS.md` 自创约定——若 AGENTS.md 没说的，**先问用户**再写
- **不**在 query 时偷偷归档——必须先展示答案 + 询问用户
- **不**忽略 lint 报告——长期不 lint 的 wiki 一定会腐烂
- **不**用 git 操作破坏 raw/ 不可变性——`git clean` / `git checkout -- raw/` 仅在启用 git
  时适用；未启用 git 时没有"未提交改动"概念（lint 自动跳过此项）
- **不**对 wiki 内文件用 Read 之外的工具做"自动"修改——所有修改走 Edit / Write 并
  走 schema 约定
- **不**在 LLM 修改页面后保留 `reviewed: true` 戳——戳即过期，回到默认未审核（详见核心原则 §10）
- **不**忽略 `scripts/SCRIPTS.md` 索引直接遍历 `scripts/` 跑脚本——必须先 `Read` 索引定位工具
  - 按段中调用约定执行（详见核心原则 §12）

### 反模式（绝对禁止）

- 在 wiki 页面里手写"先写一段话再贴图"等散文式总结（散弹式散落口径冲突的根源）
- 把同一个概念分散在多个 entities/ 文件里（必须先 search 是否已有同名页）
- 不写 log 条目就改 wiki（无法审计 + 无法 ingest_diff 识别新文件）
- 跨 wiki 互引但不更新对端 index（两套 wiki 同步是用户的责任）
- 用 Obsidian-only 语法（`[[wikilink]]`、`![[embed]]`）——本 skill 假设通用 Markdown
- 把 yzr-llm-wiki-management skill 自带脚本（lint_wiki.py / ingest_diff.py / log_format.py）
  复制进 `<wiki-root>/scripts/`——SSOT 在 skill 仓；本 wiki 自维护脚本必须同时更新 `SCRIPTS.md` 索引段
- 把外部代码仓接入走 `cp -r` 内嵌到 `raw/` 而非 `raw/external/` symlink——失去
  commit 锚点 + 占用空间 + 违反 spec §13 纪律
- 修改 anchor 的 `remote_url` / `commit` / `branch` 三字段——这三字段是接入意图，
  不是机器状态（详见 [`references/external-repo-rebuild.md`](references/external-repo-rebuild.md)）
- 绕过 anchor 直接 `ln -s`——没有对应 `[[entry]]` 的 symlink = lint 报
  `external-anchor-orphan`
- 在 `raw/external/` 下开 `<source-name>/` 子目录（0.17.0+ 已废弃）——扁平布局，
  所有 symlink 直接 in `external/`；老 wiki 残留会被 lint 报 `external-source-name-invalid`

### 反合理化三件套（纪律型 skill 必带）

> 本 skill 含 14+ 行"必须 / 禁止 / 不"+"**不**" 起始段 = 纪律型。纪律型禁令在
> LLM 压力下会被以各种合理化借口绕开——三件套只堵一类：**已被合理化的违反**。
> 未被合理化的违反（直接忽略规则）= 缺 §反模式 清单本身，与三件套无关。

#### Rationalization Table（仅占位 — Iron Law baseline 后替换为真实 transcript）

| 常见借口 | 为什么是错的 | 应改做什么 |
| --- | --- | --- |
| "用户没明说要我做这一步" | 本 skill 的纪律点（log / lint / reviewed 戳 / 等）触发条件是**事**而非**人**——写了 wiki 页就是触发 lint，写了 source 就是清 reviewed 戳——用户没说 = 沉默 ≠ 豁免 | 先按 §执行原则走完纪律，再决定是否省略；省略要写明理由进 log 条目 |
| "这次是单页 ingest，跳过 entity/concept 同步更快" | 知识孤岛 = wiki 复利亏空——单页也一样要 cross-link；"更快"是把当前 case 凌驾于复利结构之上 | 哪怕只挂 1 个 entity 页也要同步；交叉引用是 wiki 的 ROI 核心 |
| "我把 source `cp` 进 raw/ 比走 `Write` + 创建 page 更直接" | raw/ 不可变 + raw/external/ 唯一例外是 symlink 不是 cp——`cp` 进 raw/ 触发 `raw-external-anchor-mismatch` 一连串 finding | 用 `Edit/Write` 写 wiki/sources/`<slug>`.md；raw 是用户私有 |
| "`reviewed: true` 是一周前人标的，我没改多少内容，留着就行" | `reviewed: true` 是"这一刻内容背书"快照，**任何** LLM 对正文的修改都让它失效（包括 typos / 字段补全）——留戳 = 假装审过 | 任何 Edit/Write 后**必须**删 `reviewed` + `reviewed_at` 两字段，回到默认未审核态 |
| "外部代码仓我 cp -r 进 raw/ 也算接入，symlink 没必要" | cp -r 失去 commit 锚点 + 占用 wiki 仓磁盘 + 违反 spec §13——"也算"是把"接入意图"和"接入手段"混淆 | 走 `ln -s` 创建 symlink + 写 `.symlink-anchor.toml` 的 `[[entry]]` 块 |
| "这个 wiki 没 git，不写 log 也行" | log.md 是**审计 + 时间线 + ingest_diff 识别新文件**的输入，不是 git 历史替代品——git 缺位时 log 更重要 | 任何 wiki 改动**必须**追加 log 条目（哪怕 wiki 无 git） |

> **占位声明**：上表 6 条是基于本 skill §反模式 / §边界 段"反推"出的 LLM 嫌疑借口，**未**经过
> 实跑 baseline transcript 验证。Red Flags 同样如此。下次 Iron Law 跑出真实借口后，**只替换 /
> 不追加**——保持"只收录 agent 实际说过的"原则（预写 = 噪声 + 信号干扰）。

#### 违反字面 = 违反精神

任何对 §核心原则 / §边界 / §反模式 三段禁令的"看起来不同但效果一致"绕法都算违反——本 skill 常见绕法前三：

- 把 `Edit` / `Write` 改为 `Read` + 手动生成新内容再 `Write`——**不算**绕开"用 Read 之外工具做自动修改"禁令，操作工具是 Write 一样算
- 把"不删除 wiki 页"解释为"先把内容拷出去再 `rm` 然后写回"——**不算**绕开不删禁令，状态效果完全等同
- 把"raw/ 由用户掌控，LLM 只读"解释为"我`cp` 进 raw/ 后立即再`rm`，窗口里我读到了内容 = 等价于只读"——**不算**，写入发生在第一步

**禁止**用"严格按字面 / 严格按精神"二选一措辞给 agent 留退路——任何"看起来不同但效果等价"都是违反。

#### Red Flags（念头清单 — 出现即停）

念头出现 ≠ 已违反；念头 = 警告 = 重读 §核心原则 / §边界 / §反模式 三段。

- "我觉得这一步对当前 case 不必要"
- "用户没明说要我做这步"
- "这样更快 / 更省 token / 更高效"
- "spec 没禁止"
- "我已经做了等价的事" / "效果一样不算违反"
- "先这样留着，回头再补"
- "我自己生成字段比 frontmatter 严格写更灵活"
- "log 条目这次先跳过，反正是 wiki 不是 git"
- "raw 反正用户也天天改，我帮一下忙"
- "lint 报了一堆，反正都是 warn 不算错"

> 没有"念头清单 = 已违反"的递进——念头出现是**信号**，再走下去才成**行动**。
> 但**念头后仍继续** = 默认承担违反精神的责任。

## 工作流 / 步骤

### 0. 一次性 setup（首次使用）—— 由 workspace CLI 完成

> **职责边界**：本 skill 只负责 wiki 的**成长阶段**（ingest / query / lint）。
> wiki 仓的**创建与删除**由外部 workspace CLI 负责——CLI 命令名与参数
> 见 CLI 仓的文档，本 skill 不绑死任何 CLI 实现。
> wiki 仓的"出生形态"契约见 [`references/wiki-spec.md`](references/wiki-spec.md)——
> CLI 实现与 SKILL 之间的接口。

**基本流程**：

```bash
# 1. 调 workspace CLI 创建 wiki 仓（具体命令以 CLI 文档为准）
workspace wiki init "LLM Systems"
# CLI 按 wiki-spec.md 落盘：目录结构 + AGENTS.md（SSOT）+ CLAUDE.md（薄壳）+
# wiki/index.md + wiki/log.md + .gitignore + scripts/SCRIPTS.md +
# git 默认跳过（用户 --git opt-in 时才 init）。完整产物清单见 wiki-spec.md §1-§7。

# 2. 把原始资料放进 raw/（用户手动 / Obsidian Web Clipper / 浏览器下载）
cp ~/Downloads/some-article.md ~/wiki/<topic-name>/raw/articles/
```

**LLM agent 接管后做什么**：

1. 验证 CLI 落盘——读 `<wiki-root>/AGENTS.md` 确认主题名 + 日期替换正确；
   `wiki/index.md` / `wiki/log.md` 存在且 frontmatter 完整；`<wiki-root>/CLAUDE.md` 是薄壳
2. 跑 orient ritual（见 §执行原则 / 边界 顶部引用块）
3. 询问用户是否做首次 ingest——若是，把第一份资料路径给 agent

**为什么 setup 与日常分两层**：CLI = 出生/死亡（一次性，结构稳定），LLM = 成长（高频交互）。
最大收益是 **wiki schema 与 LLM 工作流解耦**——CLI 可独立升级实现（Python → Rust），
SKILL 不动。

### 1. Ingest（摄取新资料）

**触发**："把这篇摄取到 wiki" / `raw/` 有新文件 / 跑 `ingest_diff.py` 发现未摄取项。

**流程摘要**（agent 驱动；详细 7 步 + 批处理 + 外部代码仓 5 步见
[`references/ingest-workflow.md`](references/ingest-workflow.md)）：

1. 跑 `scripts/ingest_diff.py <wiki-root>`（日常加 `--check-stale`）找出未摄取/待重摄文件清单
2. **单篇对一下要点**——仅交互式单篇或少量场景：确认主题方向 / 重点交叉的 entity / 用户判断要保留
3. 对每个文件：Read 全文 → 提取元数据 → 写 `wiki/sources/<slug>.md`(stale-raw 走 **Edit**,**不**Write 覆盖)
   → 同步 entity/concept(只 append "Sources" 段) → 更新 `wiki/index.md` → 追加 `log.md`
4. **commit**（仅启用 git 时）：节奏由用户/agent 决定，**不**自动 commit

### 批处理摄取（≥ 3 份 raw 同时摄入）

走批处理路径而非逐份。**一次聚合、一次写入、一次索引**——避免 N 次重复 search / N 次
index 更新 / N 条 log。5 步流程 + 为什么批处理 + log 标题前缀 `Bulk:` 的细节见
[`references/ingest-workflow.md`](references/ingest-workflow.md)「批处理」节。

**外部代码仓作为语料**——若用户说"把 X 仓库纳入 wiki"：**不**内嵌拷仓，走
[`wiki-spec §13`](references/wiki-spec.md#13-rawexternal外部代码仓接入可选) 的 symlink 路径
（`raw/` 总纪律的**唯一例外**——LLM 主导）。5 步接入（确认 symlink/target → LLM 验证 → 读
git 扩展字段 → 创建 symlink + 写 anchor → 后续 `ingest_diff` 扫描）+ 漂移刷新 + 跨主机
重建见 [`references/external-repo-rebuild.md`](references/external-repo-rebuild.md)。

### 2. Query（跨页综合）

**触发**："wiki 里有 X 吗" / "总结 wiki 中关于 Y 的内容" / "对比 A 和 B"。

**流程**：

1. **先看 index.md**——按关键词 / 类别找候选页
2. **读相关页**（不读 raw——raw 已经在 source 页里消化过）
3. **跨页综合**——用引用形式带 source 链接；矛盾处显式标注："A 说 X（来源：...），
   B 说 Y（来源：...），需要更深入调研"
4. **展示答案 + 询问归档**——如果答案有"对比 / 综合 / 发现联系"的性质，询问用户：
   "这段答案适合归档回 wiki 作为 comparisons/`<slug>`.md 吗？"
5. **用户同意后归档**——走 references/page-templates.md 的 `comparison` 或
   `synthesis` 模板 + 追加 log 条目

详细 query 流程与判定规则见 [`references/query-workflow.md`](references/query-workflow.md)。

### 3. Lint（健康检查）

**触发**："lint wiki" / 定期（频率阈值见 [lint-checklist.md §六](references/lint-checklist.md#六lint-频率)）/ 大型 wiki 主动建议。

**流程**：

1. 跑 `scripts/lint_wiki.py <wiki-root>` 做 deterministic 检查
2. 脚本覆盖（10 大类，详见 [`references/lint-checklist.md`](references/lint-checklist.md)）：
   raw 不可变性 / frontmatter 字段 / 孤儿页 / 断链 / log.md 格式 / 过期摘要 / 页面体量
   / 认知质量与可信度信号（`reviewed` / `contested` / `contradictions`）/ `raw/external/`
   symlink ↔ anchor 关联（spec §13）/ fixtures 一致性（见下文「fixtures 一致性检查」段）
3. 脚本输出后 **agent 还要做半定性检查**：矛盾主张 / 缺失交叉引用 / 建议新摄取方向
4. 报告 + 询问用户哪些修

详细 checklist 见 [`references/lint-checklist.md`](references/lint-checklist.md)。

### 4. Memory（写入 LLM agent 持久化记忆）

**触发**：在 ingest / query / lint 过程中识别到值得沉淀的信息——踩坑、用户偏好、跨文档关联。

**何时写**：

- 遇到踩坑（例：raw/ PDF 频繁 OCR 错误，下次让用户先转格式）
- 发现用户偏好（例：用户偏好表格化对比、不喜散文式总结）
- 跨 ingest 关联（两 source 页指向同一论文不同章节）
- lint 报告的 recurring pattern（每次 lint 都报某 type 缺字段）

**流程摘要**（agent 主动；完整 8 步 + frontmatter 字段 + 索引同步规则 +
完整/短条目判定见 [`references/migrate-workflow.md`](references/migrate-workflow.md)
MEMORY 节——该文件含 MEMORY 写入细节；或仓库根 `MEMORY/MEMORY.md` 索引自身的写法）：

1. 决定是否值得写——能否让未来 agent 工作更顺？
2. 判别条目形式：**完整**（含 why+how 上下文）→ 走 3-6；**短**（纯 reminder）→ 直跳 5
3. 在 `MEMORY/<slug>.md` 创建文件（kebab-case 按主题归类，**不**按时间归档）
4. 写 frontmatter（**仅 `title` 必填**；其余 5 字段全 optional——spec §5.2；短条目可仅 1 行 `title:`）
5. 写正文——记录具体经验，含上下文 / 解决步骤 / 未来如何避免
6. 同步追加 `MEMORY/MEMORY.md` 索引一行（**漏写 = 下次读不到，lint `memory-not-indexed` 兜底**）
7. **不**追加 log 条目 / **不**在 wiki/index.md 列出（MEMORY 不走单一入口约束）

**纪律**：

- 不删除任何 MEMORY 文件——踩坑记录沉淀下来
- 写新文件时保留原 `created` 字段；只更新 `updated`
- 用户**不**直接编辑 MEMORY/——若用户想补充，先转告 agent 由 agent 写入

### 5. Migrate（升级 wiki spec）

**触发**：用户说"升级 wiki / 迁移 / 检查 wiki 版本 / 老格式 / spec 升级 / 是否需要
reformat"；或 `lint_wiki.py` 报告 `legacy-confidence-field` 等迁移期 warn。

**职责切分**（避免与 ingest / lint 混淆）：

- **脚本**（`scripts/lint_wiki.py --check-version`，**含**自动调 `check_wiki_fixtures.py`
  扫约定文件）= 探测器，只扫不修，输出报告 / 落盘 `.migration-plan.json`
- **agent** = 修复者，按 `.migration-plan.json` + [`wiki-spec-changelog.md`](references/wiki-spec-changelog.md)
  用 Edit/Write 改
  frontmatter / 移文件 / 补索引 / 改 AGENTS.md §八；走 plan.fixtures_actions[] 修约定文件；
  语义合并按 [`references/migrate-workflow.md` §六](references/migrate-workflow.md#六语义合并规则0180-从-references-semantic-merge-md-并入) 走
- **[`wiki-spec-changelog.md`](references/wiki-spec-changelog.md)** = SSOT（迁移依据每行写在那边）；fixtures-check 的语义合并
  走 migrate-workflow.md §六（与 §三 字节合规分离）
- **不**追加 log 条目（迁移是脚本运行，不是 wiki 操作事件）

**fixtures 一致性检查**——`--check-version` 自动调 `scripts/check_wiki_fixtures.py`
扫 wiki 仓 9 类约定文件（AGENTS.md §八 / .gitignore / index.md / log.md / tags.md /
MEMORY/MEMORY.md / SCRIPTS.md / .symlink-anchor.toml），finding 并入 `.migration-plan.json` 的
`fixtures_actions[]`（与 legacy `actions[]` 平行）。当前检查项数同 `metadata.fixtures_check_count`，
覆盖 11 条结构探测 + 骨架字段比对两类（`agents-md-has-at-imports` 断言 `@import` 两行均在、
`agents-md-codex-read-hint` 断言 Codex HTML Read 指引注释在位）。**简要流程** + 9 步详细 +
字段清单见 [`references/migrate-workflow.md`](references/migrate-workflow.md)。

## 参考样例

> 本节原为独立文件 `references/examples.md`（按需 Read 指针）——已下沉到本段。
> 5 个完整交互样例（setup / ingest / query / lint / migrate）按序展开，
> 来源文件已删除。

### 样例一：setup 一个 LLM Systems 主题的 wiki

**用户指令**："我想搭一个 wiki 用来跟踪 LLM Systems 主题的研究资料"

**执行**：

```text
1. 告知用户：本 skill 不直接创建 wiki 仓；wiki 创建由 workspace CLI 负责
   → 推荐路径建议在 ~/wiki/llm-systems
2. 用户调 workspace CLI（具体命令以 CLI 文档为准）：
   workspace wiki init "LLM Systems" --root ~/wiki/llm-systems
   → CLI 按 wiki-spec.md 落盘目录 + AGENTS.md（SSOT）+ CLAUDE.md（薄壳）+ index.md + log.md + .gitignore
   → CLI 默认不建 git（用户 --git opt-in 时才 init + commit）
3. LLM agent 接管后：
   → 读 ~/wiki/llm-systems/AGENTS.md 确认主题名替换正确（CLAUDE.md 是薄壳，行数 ≤ 30）
   → 验证 wiki/index.md / wiki/log.md 存在且 frontmatter 完整
   → 提示用户：raw/articles/ 作为"资料投放口"，可放剪藏 / PDF / 笔记
4. 提示用户：wiki 根目录内的 AGENTS.md 在 Claude Code 下经薄壳 CLAUDE.md 自动加载、
   在其他 agent（Codex / Gemini CLI 等）下原生直读；别处工作时 skill 经 $LLM_WIKI_ROOT 按需读取，不必 symlink
```

### 样例二：ingest 一篇论文摘要

**用户指令**："raw/articles/ 里有一篇 'attention-is-all-you-need.md'，把它摄取到 wiki"

**执行**：

```text
1. ingest_diff.py 确认这是未摄取文件
2. Read raw/articles/attention-is-all-you-need.md 全文
3. 在 wiki/sources/attention-is-all-you-need.md 写摘要页：
   - frontmatter: type=source, sources=[raw/articles/...md], tags=[transformer, attention]
   - 正文：摘要 + 关键贡献 + 架构要点 + 与其他论文的关系
4. 检查 concepts/transformer.md, concepts/self-attention.md 是否已存在
   - 不存在：创建并把本次贡献写进
   - 存在：追加"参考来源"段
5. 更新 wiki/index.md：sources/ 段加一条；concepts/ 段同步
6. 追加 log.md：## [2026-06-24] ingest | Attention Is All You Need
7. 若启用 git，建议 commit；裸目录树 wiki 跳过此步
```

### 样例三：query 一个跨实体问题

**用户指令**："wiki 里 Transformer 和 Mamba 的对比是什么样的？"

**执行**：

```text
1. 读 wiki/index.md，找到 concepts/transformer.md 和 concepts/mamba.md
2. 读两个 concept 页
3. 综合答案，引用形式：
   "Transformer 用 self-attention 捕获长依赖（来源 sources/attention-is-all-you-need.md）；
   Mamba 用 state space model 线性复杂度推理（来源 sources/mamba.md）..."
4. 询问用户："这段对比适合归档为 wiki/comparisons/transformer-vs-mamba.md 吗？"
5. 用户同意后：
   - 用 references/page-templates.md#comparison 模板
   - 写 wiki/comparisons/transformer-vs-mamba.md
   - 更新 index.md
   - 追加 log.md：## [2026-06-24] query | Transformer vs Mamba
```

### 样例四：lint 发现腐烂迹象

**用户指令**："lint 一下这个 wiki"

**执行**：

```text
1. python3 yzr-llm-wiki-management/scripts/lint_wiki.py ~/wiki/llm-systems
2. 脚本报告：
   - raw/ 干净（启用 git 时 git status clean；未启用时此项自动跳过 + 输出顶部
     `[NOTES] raw-immutable-skipped: 未启用 git（无 .git/）` 提示）
   - 3 个页面缺 updated 字段
   - 1 个失效引用：concepts/transformer.md 链到 sources/bigtable.md 但后者不存在
   - 5 个 source 页 updated 超过 stale 阈值（阈值见 [lint-checklist §二.7](references/lint-checklist.md#7-过期摘要)），建议复查
   - 1 个孤儿页：concepts/scaling-laws.md 没有任何 inbound link
   - 1 个 `contested-page`：sources/llama-3.md 与 sources/llama-2.md 对 context window
     说法冲突、已双向标注 `contested: true`——需与用户裁定后移除标记
   - 7 个 `pending-review`：默认未审核页面（新常态，info）
   - 1 个 `reviewed-stale`：sources/llama-2.md reviewed=true reviewed_at=2026-06-01 但
     updated=2026-06-25——LLM 修改后漏清 reviewed 戳，建议重新审核
3. agent 补充半定性观察：
   - sources/llama-3.md 与 sources/llama-2.md 对 "context window" 的描述不一致
4. 整理成结构化报告，问用户先修哪些
```

### 样例五：检查 wiki 是否需要升级到最新 spec

**用户指令**："我这个 wiki 是去年搭的，老格式了，能不能升级到最新 spec"

**执行**：

```text
1. 跑操作前置：Read ~/wiki/llm-systems/AGENTS.md (看到 §八 Wiki Spec 版本 = 0.5.0；老 wiki 版本在 CLAUDE.md §八) +
   wiki/index.md + wiki/log.md 最近 30 行
2. 跑探测：
   python3 yzr-llm-wiki-management/scripts/lint_wiki.py ~/wiki/llm-systems --check-version
   脚本报告：
     current_spec : 0.5.0
     skill_spec   : 0.7.0
     comparison   : older
     needs_migration: true
     [LEGACY] 共 12 处老格式现场
       - confidence-field (12) → wiki-spec-changelog.md#附录-b-0-7-0
           wiki/sources/llama-2.md  [CONFLICT] ← 同时有 reviewed，需人工裁定
           wiki/sources/llama-3.md
           ...
     [CONFLICTS] 1 处冲突页——agent 不自动覆盖
       - wiki/sources/llama-2.md: 同时含 legacy confidence 字段与 reviewed 字段
     [HINT] 加 --apply 落盘 .migration-plan.json 供 agent 走 Edit/Write 修复
3. agent 把报告转成对话式清单 + 询问用户:
   "应用全部（除 1 处冲突转人工）/ 部分应用 / 仅看清单?"
   用户: "应用全部"
4. 生成 plan：
   python3 yzr-llm-wiki-management/scripts/lint_wiki.py ~/wiki/llm-systems --check-version --apply
   → 落盘 ~/wiki/llm-systems/.migration-plan.json
5. agent 读 plan.actions[] 逐项 Edit/Write 修复:
   - 12 处 frontmatter-rename（其中 11 处直接改，1 处冲突跳过转人工）
   - 0 处其它（`type-memory-value` 已退役，老 wiki 中 `type: memory` 由 lint `invalid-type` 单独报）
6. Edit 改 ~/wiki/llm-systems/AGENTS.md §八 "Wiki Spec 版本" 0.5.0 → 0.7.0
7. 重跑 lint_wiki.py --check-version 验证:
     needs_migration: false ✓ 完成
     报告残留: wiki/sources/llama-2.md [CONFLICT] 等待用户裁定
8. 告诉用户完成 + 1 处冲突转人工
```

## 与其他 skill 的边界

`yzr-outline-wiki-upload` / `yzr-outline-wiki-search` 走云端 Outline——团队协作、外部分享。
`design-doc-edit` 走单篇 Markdown 写作。`gemini-paper-summary` 抽 PDF 摘要；本 skill
负责 ingest 归档。Paper 域细节见 [`references/paper-wiki-profile.md`](references/paper-wiki-profile.md)。

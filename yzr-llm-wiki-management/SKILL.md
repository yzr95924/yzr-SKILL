---
name: yzr-llm-wiki-management
description: 用户在搭建或维护本地、单用户的复利型个人 wiki
  （Karpathy "LLM owns wiki, humans only read" 模式）时使用本 skill
  ——把原始资料（论文 / 文章 / 剪藏 / 笔记）持续摄入本地 wiki、做跨页综合查询、
  跑矛盾 / 孤儿 / 过期摘要 lint、围绕新主题接入新 wiki 并引导首次 ingest；
  支持以 symlink + .symlink-anchor.toml 路径接入外部代码仓（Linux kernel / Ray 源码等）
  作语料无需内嵌拷贝，按 git 可选 opt-in 的纯目录树 + Markdown 工作流维护。
  0.23.0+ 起 wiki 真正 multi-agent 兼容：AGENTS.md 把 MEMORY / scripts 索引**内联**进正文
  （之前用 `@import` 只 Claude Code 展开，Codex / Qoder / Gemini CLI 看不到）。
  不用于云端协作 wiki（Notion / Confluence / Outline Wiki / GitHub Wiki）——
  那些走 yzr-outline-wiki-upload（写 / 编辑）/ yzr-outline-wiki-search（搜 / 读）；
  不用于一次性文档生成、强结构化数据库、多人实时协作。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-07-11
  wiki_spec_version: 0.23.0
  fixtures_check_count: 20
---

# LLM Wiki Management

按 Karpathy [LLM Wiki 设计哲学](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
维护一个**本地**、**复利累积**的知识库：用户只管读 + 提供资料 + 提问题，LLM 负责摘要、
交叉引用、归档、簿记这些"无聊的部分"。和 `yzr-outline-wiki-upload` 等云端 skill 的关键区别是
**本地文件 + 三层纪律**——vs 云端 MCP 单层文档。

本 skill 提供三块交付物：

- **SKILL.md（本文）**——工作流 + 纪律的"宪法"
- **scripts/**——ingest_diff.py / lint_wiki.py / log_format.py + 0.18.0+ 新增
  **check_wiki_fixtures.py**（fixtures 一致性检查；`lint_wiki.py --check-version`
  自动调一次），把高频 deterministic 任务固化下来（**不**含 setup_wiki——wiki
  仓的创建由外部 workspace CLI 负责）。**0.23.0+** 起 11 条结构探测 + 9 条
  0.20.0+ 骨架字段比对（含 2 条 0.23.0+ 新增：`agents-md-inline-index-sections`
  warn + `agents-md-no-at-imports` error），`fixtures_check_count = 20`；**0.23.0+**
  起 `lint_wiki.py` 新增 `inlined-memory-index-bloating` warn（`scripts/lint_wiki.py`
  顶部 `INLINED_INDEX_MAX = 50`），守"AGENTS.md §一 内联 MEMORY 索引条数"护栏——避免
  渐进加载 L1 膨胀
- **references/**——按需加载：AGENTS.md schema 模板 + CLAUDE.md 薄壳模板、各操作详细流程、页面模板、
  wiki-spec.md（CLI 实现契约）、fixtures（CLI 字节级比对金标准）、lint-checklist §五
  (semantic-merge 规则，agent 走 .migration-plan.json 时的合并依据)

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
  本 skill 不实现创建逻辑；产物形态为目录结构 + AGENTS.md（SSOT）+ CLAUDE.md（薄壳）+ wiki/index.md + wiki/log.md + MEMORY/MEMORY.md + .gitignore
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
   写 `.symlink-anchor.toml` 的 `[[entry]]` 块（首次接入 + 漂移刷新）——详见 [wiki-spec §13.3](references/wiki-spec.md#13-责任切分用户--llm-共有)
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
   是索引（无 frontmatter），其 `## 索引` 段下的全部条目**内联**进 `AGENTS.md` §一
   `#### 跨会话记忆（索引）` 段（0.23.0+ 改；之前用 `@MEMORY/MEMORY.md` import——但 `@import`
   递归展开只 Claude Code 支持，Codex / Qoder / Gemini CLI 不展开 → 整个 `MEMORY/` 对它们不可见。
   内联后所有 agent 一视同仁）——避免 MEMORY 沦为只写不读的死库。**AGENTS.md 内联段是 MEMORY.md
   的"投影"，改一处须同步另一处**（lint `memory-not-indexed` 0.23.0+ 双轨扫兜底）。
   为什么搬到 `<wiki-root>/MEMORY/`：对应 §四层架构第 3 层（独立于 wiki/ 内容）、将来 publish 时
   MEMORY 自然留作私有层不外传。详细规则见 spec §5。
4. **`AGENTS.md` 纪律配置（SSOT）+ `CLAUDE.md` 薄壳**——把"wiki 怎么写 / 写什么 / 不写什么"的约定
   集中到 `AGENTS.md`（工具无关单一真源），是维护本 wiki 的 agent 的"宪法"。`CLAUDE.md` 是
   `@AGENTS.md` 薄壳，仅供 Claude Code 经自动加载约定读到 SSOT；读 `AGENTS.md` 的其他 agent
   （Qoder / Codex / Gemini CLI 等）原生直读。**L2 索引内联（0.23.0+）**：
   AGENTS.md 正文自带 `#### 跨会话记忆（索引）` 与 `#### Wiki-local scripts（索引）` 两段，
   让所有读 `AGENTS.md` 的 agent 都能立即看到 MEMORY / scripts 有哪些条目——之前用 `@import`
   只 Claude Code 展开，Codex / Qoder / Gemini CLI 看不到（详见 §四层架构第 3 点的内联注）。
   没有它，LLM 会退化成普通聊天机器人；有它，LLM 是"纪律严明的 wiki 维护者"。**为什么 AGENTS.md
   作 SSOT + CLAUDE.md 薄壳**（套用 `yzr-multi-agent-context` 方法）：一套真源、Claude Code /
   Qoder / Codex / Gemini CLI 多 agent 一视同仁——`@import` 写在 SSOT 内**已经不够**，
   必须内联才能跨 agent（详见 `yzr-multi-agent-context/SKILL.md`「L2 陷阱段」）。

### 四个核心操作——为什么是四个

| 操作 | 输入 | 输出 | 价值 |
| --- | --- | --- | --- |
| **ingest** | `raw/` 新文件 | 摘要页 + 交叉引用 + log 条目 | 把原始资料变成可查询的结构 |
| **query** | 自然语言问题 | 综合答案（带引用）+ 可选归档 | 复用 + 复利：好答案不回聊天记录 |
| **lint** | 整个 wiki | 报告矛盾 / 孤儿 / 过期 | 防止知识库腐烂 |
| **migrate** | 整个 wiki（含 AGENTS.md §八） | legacy 报告 + `.migration-plan.json` + agent 修复后的最新 spec 兼容 wiki | spec 演进时不破坏老 wiki 沉淀 |

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
>    Page Thresholds（0.11.0+: 纪律 SSOT 是 `AGENTS.md`；`CLAUDE.md` 是 `@AGENTS.md` 薄壳，不持纪律）。
>    AGENTS.md 不再含 tag 白名单（0.8.0+ 迁出到 `wiki/tags.md`——见本节 §核心原则 §11）。**0.23.0+ 起**
>    AGENTS.md 正文自带 `#### 跨会话记忆（索引）` 与 `#### Wiki-local scripts（索引）` 两段（**内联** MEMORY /
>    scripts 索引，让所有读 AGENTS.md 的 agent 立即看到有哪些条目；之前用 `@MEMORY/MEMORY.md` +
>    `@scripts/SCRIPTS.md` import 只 Claude Code 展开）。在 wiki 根目录内工作时——Claude Code 经薄壳
>    `CLAUDE.md` → `@AGENTS.md` 自动加载 SSOT（含内联索引段）；读 `AGENTS.md` 的其他 agent
>    （Qoder / Codex / Gemini CLI 等）原生读 SSOT，同样看到内联段。**别处由 skill 按需读 AGENTS.md 时**
>    也直接读 AGENTS.md（含内联段），**不**再需额外 `Read MEMORY.md` 补齐索引（除非要看各 `<slug>.md` 正文）
> 2. `Read <$LLM_WIKI_ROOT>/wiki/index.md`——知道有哪些页、分布在哪些类别，避免重复创建 / 漏交叉引用
> 3. `Read <$LLM_WIKI_ROOT>/wiki/log.md`（最近 ~30 行即可）——看清最近活动，避免重复
>    ingest / 漏归档旧工作
> 4. **0.9.0+：** `Read <$LLM_WIKI_ROOT>/scripts/SCRIPTS.md`（按需）——确认本 wiki 是否有
>    项目级扩展脚本的**完整分节契约**（使用场景 / 调用约定 / 作用 / 前置依赖）；不强制（wiki 可无
>    scripts/），但**触发非标工作流前**必须先查（AGENTS.md 顶部的 `#### Wiki-local scripts（索引）`
>    段只列脚本名 + 一句话用途，详细契约仍在本文件）
>
> 四件套任一未读完不写任何 wiki 内容。100+ 页的 wiki 还应在 `wiki/` 全域
> `Grep "<topic>"` 补一次——单看 index.md 可能漏掉 entity/concept 页之间的引用关系。

1. **raw/ 由用户掌控，LLM 只读**（schema 见 `<wiki-root>/AGENTS.md` §一）——LLM 从不写/删/移 `raw/` 下文件；
   用户可随时新增/更新 raw/（重新剪藏、重存 PDF 都算），改动由 ingest 重新消化（更新对应 source 页正文 +
   `updated`，`ingest_diff.py --check-stale` 按 mtime vs source `updated` 标记待重新摄取项）
   **唯一例外**：`raw/external/` 顶层（**扁平布局，0.17.0+**）下 LLM 可主导创建 symlink +
   写 anchor 的 `[[entry]]` 块（详 §1.bulk 外部代码仓子节 + wiki-spec §13.3）
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
   - `MEMORY/*.md`（0.19.0+）= **仅 `title` 必填**（其余 5 字段全 optional——MEMORY 是 agent
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
   必须在 `MEMORY/MEMORY.md` 索引 + AGENTS.md `#### 跨会话记忆（索引）` 段 双处列一行**
   （0.23.0+ 双轨；改一处须同步另一处，lint `memory-not-indexed` 双轨兜底，否则下次
   读不到）。**AGENTS.md 内联索引条数受 `INLINED_INDEX_MAX = 50` 阈值护栏**——
   `AGENTS.md` 是 progressive disclosure L1 的 SSOT，不应无限膨胀；
   超阈 lint 报 `inlined-memory-index-bloating` warn（**仅护 AGENTS.md 投影**，
   `MEMORY.md` 本体可自由增长），agent 选一：(a) 短条目化（索引行改 `- <slug> — 一句话`
   不带链接）；(b) 分类摘要；(c) 低频条目迁回 `MEMORY.md`「完整条目」段。详见 spec §5 +
   [`wiki-spec.md`](references/wiki-spec.md#5-memory) + [lint-checklist §二.15](references/lint-checklist.md#15-agentsmd-内联-memory-索引条数阈值)
10. **LLM 修改已审核页必须清 `reviewed` 戳**——任何对页面正文的 LLM 修改（ingest 重摄取 /
   query 归档 / refine / 任何 Edit/Write）让戳失效；**必须删 `reviewed` + `reviewed_at` 两字段**
   回到默认未审核态，由人重新审。`lint_wiki.py` 用 `reviewed-stale`（`reviewed: true` 存在且
   `updated > reviewed_at`）兜底。SSOT：[`page-templates.md` §一](references/page-templates.md#生命周期规则llm-必读)。

    > **注**：同样的规则也会出现在
    > [`references/agents-md-template.md`](references/agents-md-template.md)
    > §二「认知质量信号」末段——那里是 wiki 自带的 AGENTS.md 模板必须自包含（跨仓引不到 SKILL.md）；
    > 两处措辞故意保持一致。SSOT 是 `page-templates.md` §一。

11. **tag 白名单在 `wiki/tags.md`**（0.8.0+ 起，详
   [wiki-spec.md §9.1](references/wiki-spec.md#91-tag-白名单来源080)）——LLM auto-extend bullet +
   用户审计循环（删 bullet → 下次 lint 报 `tag-not-in-taxonomy` 由用户裁定）；`wiki/tags.md` 无
   frontmatter，与 `MEMORY/MEMORY.md` 同形态。跨 spec 升级走 `lint_wiki.py --check-version --apply`。
   `agents-md-template.md`「Tag Taxonomy」段自包含同样规则（必须——wiki 仓自带模板跨仓引不到 SKILL.md）。

12. **本 wiki 自维护脚本走 `<wiki-root>/scripts/` + `SCRIPTS.md` 索引**（0.9.0+ 起，详
   [wiki-spec.md §14](references/wiki-spec.md#14-scripts本-wiki-仓扩展脚本目录090)）——`SCRIPTS.md`
   含 `## 索引`（紧凑 one-liner，给 AGENTS.md 投影）+ `## 分节契约（详细）`（每脚本完整契约）双段。
   **AGENTS.md `#### Wiki-local scripts（索引）` 段（0.23.0+ 内联）**含 one-liner 列表；agent **必须**先
   看该索引段知道有哪些脚本，再按需 `Read scripts/SCRIPTS.md` 取完整契约，再按"调用约定"显式执行，
   **不**自动遍历 `scripts/`；AGENTS.md 索引行与 SCRIPTS.md 分节段修改是**原子动作**。
   `scripts/` 不走 §9 5 必填、不参与 `lint_wiki.py` 扫描、不复制 skill 自带脚本
   （版本漂移风险）。`agents-md-template.md`「Wiki-local scripts」段自包含同样规则。

### 边界

- **不**编辑 `raw/` 下任何文件——LLM 只读；用户可改，改后由 ingest 重新消化
  **唯一例外**：`raw/external/` 顶层（**扁平布局，0.17.0+**）下 LLM 可创建 symlink +
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
# wiki/index.md + wiki/log.md + .gitignore + scripts/SCRIPTS.md（0.9.0+）+
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

### 1.bulk 批处理摄取（≥ 3 份 raw 同时摄入）

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
   symlink ↔ anchor 关联（spec §13）/ fixtures 一致性（0.18.0+，见 §0.18.0+ 段）
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

- **脚本**（`scripts/lint_wiki.py --check-version`，**含**自动调 0.18.0+ `check_wiki_fixtures.py`
  扫约定文件）= 探测器，只扫不修，输出报告 / 落盘 `.migration-plan.json`
- **agent** = 修复者，按 `.migration-plan.json` + `wiki-spec.md` 附录 B 用 Edit/Write 改
  frontmatter / 移文件 / 补索引 / 改 AGENTS.md §八；走 plan.fixtures_actions[] 修约定文件；
  语义合并按 [`references/lint-checklist.md` §五](references/lint-checklist.md#五-semantic-merge-规则) 走
- **`wiki-spec.md` 附录 B** = SSOT（迁移依据每行写在那边）；fixtures-check 的语义合并
  走 lint-checklist §五（与 §三 字节合规分离）
- **不**追加 log 条目（迁移是脚本运行，不是 wiki 操作事件）

### 0.18.0+ 新能力：fixtures 一致性检查（0.20.0+ 升级为字段级骨架比对；0.23.0+ 扩到 20 条）

`--check-version` 自动调 `scripts/check_wiki_fixtures.py` 扫 wiki 仓的 9 类约定文件，
finding 并入 `.migration-plan.json` 的 `fixtures_actions[]`（与 legacy `actions[]` 平行）。
**`metadata.fixtures_check_count` 条 check**——11 条结构探测 + 9 条 0.20.0+ 骨架字段比对
（0.23.0+ 在原 7 条上新增 `agents-md-inline-index-sections` warn + `agents-md-no-at-imports`
error 两条）；骨架 check 读 `references/canonical/` + `references/fixtures/gitignore.txt` 作 SSOT
（改 fixtures → check 自动跟随），纯骨架件全字段比对、成长件只比结构必填，**不动成长内容**。
**0.23.0+ 新增 2 条**：
- `agents-md-inline-index-sections`（warn）——AGENTS.md 含 `#### 跨会话记忆（索引）` +
  `#### Wiki-local scripts（索引）` 两段（迁移期兜底，避免老 wiki 漏加内联段）
- `agents-md-no-at-imports`（error）——AGENTS.md 不含 `@MEMORY` / `@scripts` / `@wiki` 等
  `@import` 行（0.23.0+ 改内联——Codex / Qoder / Gemini CLI 不展开 `@import`，残留即 multi-agent 不达标）
字段清单（升级时每个约定文件对齐什么）见
[`references/migrate-workflow.md`](references/migrate-workflow.md)「fixtures 字段更新清单」节。

**简要流程**（agent 驱动；详细 8 步 + 边界 + 与 lint 协同见
[`references/migrate-workflow.md`](references/migrate-workflow.md)）：

1. orient ritual（AGENTS.md + `wiki/index.md` + `wiki/log.md` 最近 ~30 行）
2. 跑 `scripts/lint_wiki.py "$LLM_WIKI_ROOT" --check-version`——dry-run 报告 + legacy
   pattern 分组 + 冲突页标红 + fixtures-check 段（每条 failed 含 expected/actual）；
   也可单独 `scripts/check_wiki_fixtures.py <wiki-root> [--json]` 跑约定文件扫描
3. 询问用户"应用全部 / 部分 / 仅看清单"
4. 用户同意 → `scripts/lint_wiki.py ... --check-version --apply` 落盘 `.migration-plan.json`
   （含 legacy `actions[]` + fixtures `fixtures_actions[]`，已存在则拒绝覆盖）
5. agent 按顺序修：先 `fixtures_actions[]`（约定文件）→ 再 `actions[]`（内容页 frontmatter）
   → 跳过 `skipped_conflicts[]`（永不自动覆盖人工决策）；语义合并按 lint-checklist §五走
6. Edit 改 `<wiki-root>/AGENTS.md` §八 "Wiki Spec 版本" 为 `to_version`
7. 重跑 `lint_wiki.py --check-version` 验证；`needs_migration == false` 即完成
8. **清理临时文件**：删 `<wiki-root>/.migration-plan.json` + 升级产出的 `*.bak`（保证 wiki
   干净；详见 [`references/migrate-workflow.md`](references/migrate-workflow.md) step 8）
9. **不**追加 log 条目 / **不**触发 ingest / query / lint

**完整样例**：[`references/examples.md`](references/examples.md) §五（"检查 wiki 是否需要升级到最新 spec"）。

## 参考样例

5 个完整样例（setup / ingest / query / lint / migrate）下放到
[`references/examples.md`](references/examples.md)——按需 Read。

## 与 OKF（Open Knowledge Format）的关系

本 skill 的输出（`wiki/` 下 markdown + YAML frontmatter + `index.md`/`log.md`）刻意贴近
[OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)——
"markdown + frontmatter、人 / agent 都能读"的知识格式。它是 OKF 的**实用子集**，非逐字合规。

**已对齐**：

- 每个概念页都有可解析的 YAML frontmatter（OKF §9 ①）
- 每页 frontmatter 含非空 `type`（OKF §9 ②）
- 采用 OKF 推荐字段 `description`——`index.md` 条目摘要从它来，不在 index 里手写第二份（OKF §4.1）
- bundle 根 `index.md` 声明 `okf_version: "0.1"`（OKF §11）

**已知分歧（有意保留）**——本地单用户 wiki 优先"抓腐烂 + grep 友好"，而非跨工具互换：

| 维度 | 本 skill | OKF v0.1 | 保留理由 |
| --- | --- | --- | --- |
| `index.md`/`log.md` 带 frontmatter | 有 | §6 index 无 frontmatter | 本地解析 / grep 方便 |
| `log.md` 条目 | `## [date] op \| title` 单行 | §7 `## date` + `* **Update**` 列表 | 保留 op 维度，`grep "^## \["` 可用 |
| 交叉链接 | 相对 `../concepts/x.md` | §5 推荐 bundle 绝对 `/concepts/x.md` | 全 skill / lint 解析建在相对路径，迁移成本高 |
| 断链 | lint 报 **error** | §5.3 消费者须容忍断链 | 生产端主动抓腐烂才是 lint 价值 |
| `type` 取值 | 固定 5 类 [^1] | §4.1 开放（生产者自定义） | OKF 开放集的子集 |

[^1]: 5 类指 entity / concept / source / comparison / synthesis；另有 2 类 reserved（`type: index` / `type: log`）仅作文件标记用，详见 [wiki-spec.md §8](references/wiki-spec.md#8-frontmatter-字段全集cli-引用非生成内容页)。

本 wiki 可被任意 OKF 消费端"尽力读取"（§9 的宽容消费模型要求不得因上述分歧拒收），但不声称
100% 合规。要跨组织交换 bundle 时，再按"完全合规"档收敛（去掉 index/log frontmatter、log 改
`## date` + 列表、相对链接换 bundle 绝对）。

## 与其他 skill 的边界

| Skill | 场景 | 介质 |
| --- | --- | --- |
| **本 skill（yzr-llm-wiki-management）** | 个人 / 研究的本地复利型知识库 | 本地 Markdown（git 可选 opt-in） |
| `yzr-outline-wiki-upload` | 团队 / 协作：写 / 编辑 / 推图到 Outline | Outline Wiki MCP |
| `yzr-outline-wiki-search` | 团队 / 协作：搜 / 读 Outline 文档 | Outline Wiki MCP |
| `design-doc-edit` | 单篇设计文档写作（含强制章节骨架） | 单文件 Markdown |
| `gemini-paper-summary` | 单篇论文的结构化摘要（含视觉抽图） | 单文件 Markdown + 图片 |

可串行：**gemini-paper-summary** 抽图 → 本 skill **ingest** 归档到 wiki →（未来独立 publish skill）→ `yzr-outline-wiki-upload` 分享对外

### Paper 域：论文主题 wiki 的本地工作流

> **本 skill 永远不推远端**。本节只规定**本地**的论文域约定；把论文发布到云端
> / Outline 走**未来独立的 publish skill**（与本 skill 解耦，跨 skill 编排胶水
> 不归本 skill 负责）。

**触发条件**：用户想把一批论文沉淀到本地 wiki——`gemini-paper-summary` 抽 PDF
是上游、本 skill 做归档 + 多轮蒸馏；不愿入 wiki 的临时读论文不适用本节。

**权威定义**：[`references/paper-wiki-profile.md`](references/paper-wiki-profile.md)——
含 raw 身份（gemini "全量抽取"，非 PDF / 非压缩 summary）、source 页生命周期
（quick 初稿 → 多轮 refine 成熟）、新增 `refine` log op、与 `gemini-paper-summary`
的职责切分、若干反模式。**本节不重抄**——profile 是 SSOT，profile 变时 SKILL.md
同步引链接即可。

**为什么单独成 profile 不污染通用 SKILL.md**：论文域的"raw = 全量抽取（贵读
一次、文本层反复榨取）"是 Karpathy "复利"在单篇论文内部的重演，不该绑到通用
wiki 规则上；profile 在通用规则上做变体，SSOT 仍干净。

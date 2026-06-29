---
name: llm-wiki-management
description: 用本 skill 维护本地、单用户的复利型知识库（遵循 Karpathy
  "LLM 拥有 wiki、人类只读" 模式）。触发场景：把参考资料摄入个人 wiki、对已
  摄入资料做跨页综合查询、对 wiki 做矛盾 / 孤儿 lint、或围绕一个新主题搭建
  wiki。知识越用越厚，不越用越乱。不用于云端协作 wiki（Notion / Confluence
  / Outline / GitHub Wiki）—— 那些场景走 outline-wiki-upload（写）/ outline-wiki-search（搜读）。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-29
  wiki_spec_version: 0.3.0
---

# LLM Wiki Management

按 Karpathy [LLM Wiki 设计哲学](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
维护一个**本地**、**复利累积**的知识库：用户只管读 + 提供资料 + 提问题，LLM 负责摘要、
交叉引用、归档、簿记这些"无聊的部分"。和 `outline-wiki-upload` 等云端 skill 的关键区别是
**本地文件 + 三层纪律**——vs 云端 MCP 单层文档。

本 skill 提供三块交付物：

- **SKILL.md（本文）**——工作流 + 纪律的"宪法"
- **scripts/**——ingest_diff.py / lint_wiki.py / log_format.py，把高频 deterministic
  任务固化下来（**不**含 setup_wiki——wiki 仓的创建由外部 workspace CLI 负责）
- **references/**——按需加载：CLAUDE.md schema 模板、各操作详细流程、页面模板、
  wiki-spec.md（CLI 实现契约）、fixtures（CLI 字节级比对金标准）

## 何时使用 / 不使用

### 使用

- 用户在对话中说"摄取/归档到 wiki / ingest to wiki / 把这篇文章整理进 wiki"
- 用户在对话中说"wiki 里有 X 吗 / 在 wiki 里搜一下 / 总结 wiki 中关于 Y 的内容"
- 用户在对话中说"lint wiki / wiki 健康检查 / 找矛盾 / 找孤儿页"
- 用户指向 `<wiki-root>/raw/` 里新出现 / 未归档的文件
- 用户首次提到"我想搭一个 wiki 用来管理 X 的研究 / 读书笔记 / 项目"
- 用户提到"CLAUDE.md 怎么写 / raw/ 和 wiki/ 的边界"

### 不使用

- **云端协作 wiki**（Notion / Confluence / Outline Wiki / GitHub Wiki）——走
  `outline-wiki-upload`（写 / 编辑）/ `outline-wiki-search`（搜 / 读）
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
| 主题名 | setup 时一次性指定，写入 `CLAUDE.md` | 例 "LLM Systems" |
| 操作类型 | 用户自然语言 | ingest / query / lint / setup |
| 触发资料 | ingest 时给文件路径或目录 | 必须在 `raw/` 内 |

### 操作产物

- **setup** → 由外部 workspace CLI 完成（按 [`references/wiki-spec.md`](references/wiki-spec.md) 落盘），
  本 skill 不实现创建逻辑；产物形态为目录结构 + CLAUDE.md + wiki/index.md + wiki/log.md + .gitignore
- **ingest** → 新增 / 更新 `wiki/sources/<slug>.md` + 同步实体 / 概念页 + 追加
  `log.md` 条目 + 更新 `index.md`
- **query** → 对话中给出答案（带引用），**可选**把答案归档为 `wiki/comparisons/`
  或 `wiki/syntheses/<slug>.md`
- **lint** → `log` 中报告：raw/ 是否被改、孤儿页、断裂交叉引用、过期摘要、缺
  frontmatter、log.md 格式

## 设计决策

### 四层架构——为什么是四层

参考 Karpathy gist 的核心论断：**"Knowledge 的累加依赖纪律，不依赖意志力"**。
四层各自承担一个责任，互相制衡：

1. **`raw/` 真相之源**——用户只管策划原始资料（论文、剪藏、PDF、笔记、播客转写），
   对 LLM 只读。**纪律完整定义**（含 LLM 不写 / 用户可改 / 改名会断链 / wiki 与 raw 矛盾以
   raw 为准 4 条）见 `<wiki-root>/CLAUDE.md` §一（由 workspace CLI 在 init 时拷到每个 wiki，
   模板见 [`references/claude-md-template.md`](references/claude-md-template.md)）。
   `raw/` 下子目录自由组织——CLI 默认建 `articles/` + `assets/`，但 `podcasts/` /
   `clippings/` / `papers/` 等自定义子目录同样可用；`ingest_diff.py` 递归扫整棵 `raw/`。
2. **`wiki/` 复利资产**——LLM 拥有这一层（5 个内容页子目录 + index.md）。人类**不写**
   wiki 内容，只读 + 提问题。每次摄入新资料或回答新问题，wiki 都变得**更厚**而不是更乱。
3. **`wiki/MEMORY/` agent 持久化记忆**——LLM agent 在工作中沉淀的经验、踩坑、用户偏好，
   与 wiki/ 同归属（LLM 写、用户不写）但**不**走单一入口约束。详细规则见 spec §5。
4. **`CLAUDE.md` 纪律配置**——把"wiki 怎么写 / 写什么 / 不写什么"的约定集中到
   一处，是 LLM 维护 wiki 的"宪法"。没有它，LLM 会退化成普通聊天机器人；有它，
   LLM 是"纪律严明的 wiki 维护者"。

### 三个核心操作——为什么是三个

| 操作 | 输入 | 输出 | 价值 |
| --- | --- | --- | --- |
| **ingest** | `raw/` 新文件 | 摘要页 + 交叉引用 + log 条目 | 把原始资料变成可查询的结构 |
| **query** | 自然语言问题 | 综合答案（带引用）+ 可选归档 | 复用 + 复利：好答案不回聊天记录 |
| **lint** | 整个 wiki | 报告矛盾 / 孤儿 / 过期 | 防止知识库腐烂 |

每个操作都**双向回报**：ingest 让 query 更好用；query 让 wiki 更厚；lint 让 ingest
不会越积越乱。**单独跑任一个都亏**——这就是"复利"的本质。

### 为什么不用云端

`outline-wiki-upload` / `outline-wiki-search` 走云端 MCP（Outline Wiki），适合团队协作、外部分享、
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

> **操作前置（所有操作通用）**：每次 ingest / query / lint 启动前，先
> `Read <$LLM_WIKI_ROOT>/CLAUDE.md` 拿到本 wiki 的主题名与边界配置。在 wiki 根目录内
> 工作时它会被 Claude Code 自动加载；别处由 skill 按需读取——**不依赖 symlink**。

1. **raw/ 由用户掌控，LLM 只读**（schema 见 `<wiki-root>/CLAUDE.md` §一）——LLM 从不写/删/移 `raw/` 下文件；
   用户可随时新增/更新 raw/（重新剪藏、重存 PDF 都算），改动由 ingest 重新消化（更新对应 source 页正文 +
   `updated`，`ingest_diff.py --check-stale` 按 mtime vs source `updated` 标记待重新摄取项）
2. **wiki/ 由 LLM 撰写**——用户从不手写 wiki 页面（编辑 CLAUDE.md 除外，那是 schema）
3. **CLAUDE.md 是 schema，不是文档**——它是给 LLM 看的"工作守则"，不要往里塞内容
4. **每次写入必更 log.md**——格式严格，权威定义在 `<wiki-root>/CLAUDE.md` §一（正则见
   [`references/page-templates.md`](references/page-templates.md) §7；脚本以
   `scripts/lint_wiki.py` 为准）
5. **每页必带 YAML frontmatter**——共有必填 5 字段（`title` / `type` / `created` /
   `updated` / `tags`），推荐 `description`（一句话，`index.md` 条目摘要从它来）。
   **5 字段是 OKF §9 "字段齐全性" 与 lint 校验一致性的最小交集**——少于 5 字段会让
   "抓腐烂"判定（stale / orphan）失效，多于 5 字段 OK 但不强制。
   **例外**：`wiki/index.md` / `wiki/log.md` / `wiki/MEMORY/README.md` 是 **4 字段必填**
   （省 `description`）——权威定义见 [spec §3 / §4 / §5.1](references/wiki-spec.md)。
   **字段权威定义**（含 `type` 取值 / `index.md` & `log.md` reserved 规则 / `sources` 类型特化字段）
   见 [`references/page-templates.md`](references/page-templates.md) §一——本条不重抄，lint 阈值
   同步以该处为准。
6. **交叉引用走相对路径**——`[link](sources/bigtable.md)`，不用绝对路径，不用 wikilink
7. **index.md 是 wiki 内容页的单一入口**——所有非 log / 非 MEMORY 的页面必须在 `wiki/index.md` 中出现
8. **query 的好答案必问"是否归档"**——能写回 wiki 的不要浪费在聊天里
9. **`wiki/MEMORY/` 是 LLM agent 的私有记忆**——遇到踩坑、发现用户偏好、跨 ingest 关联
   时主动追加；frontmatter 5 必填与 wiki 内容页一致，**但不在 index.md 强制列出**。
   详见 spec §5 + [`wiki-spec.md`](references/wiki-spec.md#5-wikimemory)

### 边界

- **不**编辑 `raw/` 下任何文件（LLM 只读；用户可改，改后由 ingest 重新消化）
- **不**删除 `wiki/` 下的页面——用 `archived: true` 标记 + 从 index 移除；想真删直接删文件（启用 git 时用 `git rm`，未启用时用普通 `rm`）
- **不**绕过 `CLAUDE.md` 自创约定——若 CLAUDE.md 没说的，**先问用户**再写
- **不**在 query 时偷偷归档——必须先展示答案 + 询问用户
- **不**忽略 lint 报告——长期不 lint 的 wiki 一定会腐烂
- **不**用 git 操作破坏 raw/ 不可变性——`git clean` / `git checkout -- raw/` 仅在启用 git
  时适用；未启用 git 时没有"未提交改动"概念（lint 自动跳过此项）
- **不**对 wiki 内文件用 Read 之外的工具做"自动"修改——所有修改走 Edit / Write 并
  走 schema 约定

### 反模式（绝对禁止）

- 在 wiki 页面里手写"先写一段话再贴图"等散文式总结（散弹式散落口径冲突的根源）
- 把同一个概念分散在多个 entities/ 文件里（必须先 search 是否已有同名页）
- 不写 log 条目就改 wiki（无法审计 + 无法 ingest_diff 识别新文件）
- 跨 wiki 互引但不更新对端 index（两套 wiki 同步是用户的责任）
- 用 Obsidian-only 语法（`[[wikilink]]`、`![[embed]]`）——本 skill 假设通用 Markdown

## 工作流 / 步骤

### 0. 一次性 setup（首次使用）—— 由 workspace CLI 完成

> **职责边界**：本 skill 只负责 wiki 的**成长阶段**（ingest / query / lint）。
> wiki 仓的**创建与删除**由外部 workspace CLI 负责——CLI 命令名与参数
> 见 CLI 仓的文档，本 skill 不绑死任何 CLI 实现。
>
> wiki 仓的"出生形态"契约见 [`references/wiki-spec.md`](references/wiki-spec.md)——
> 这是 CLI 实现与 SKILL 之间的接口。

**基本流程**：

```bash
# 1. 调 workspace CLI 创建 wiki 仓（具体命令以 CLI 文档为准）
workspace wiki init "LLM Systems"

# CLI 按 wiki-spec.md 落盘：
#   - 目录结构（raw/{articles,assets}/ + wiki/{entities,concepts,sources,comparisons,syntheses}/）
#   - <wiki-root>/CLAUDE.md（按 references/claude-md-template.md 模板）
#   - wiki/index.md（5 段空类别占位 + okf_version: "0.1"）
#   - wiki/log.md（首条 setup 条目）
#   - .gitignore（忽略 OS / Obsidian / 临时文件）
#   - git：默认跳过；用户 --git opt-in 时才 git init + 首次 commit（见 wiki-spec §7）
#   - 拒绝已存在的 wiki 仓（防误覆盖）

# 2. 把原始资料放进 raw/（用户手动 / Obsidian Web Clipper / 浏览器下载）
# 例：
cp ~/Downloads/some-article.md ~/wiki/<topic-name>/raw/articles/
```

**LLM agent 接管后做什么**：

1. 验证 CLI 落盘——读 `<wiki-root>/CLAUDE.md` 确认主题名 + 日期替换正确；`wiki/index.md` /
   `wiki/log.md` 存在且 frontmatter 完整
2. **理解 schema**——`<wiki-root>/CLAUDE.md` 是本 wiki 的"宪法"：
   - 在 wiki 根目录内工作时，Claude Code 会自动加载它
   - 在别处工作时由 skill 经 `$LLM_WIKI_ROOT` 按需读取
   - **不依赖 symlink**
3. 询问用户是否做首次 ingest——若是，把第一份资料路径给 agent

**为什么 setup 与日常分两层**：

- **CLI = 出生/死亡**——一次性 init + 偶尔 delete，结构稳定、变更少
- **LLM = 成长**——每次 ingest / query / lint 都可能触发，需要与用户高频交互

分两层的最大收益是：**wiki 仓的 schema（CLI 产物）独立于 LLM 工作流（SKILL 描述）**——
CLI 可以独立升级实现（如从 Python 改 Rust），SKILL 描述的工作流不需要任何改动。

### 1. Ingest（摄取新资料）

**触发**："把这篇摄取到 wiki" / `raw/` 有新文件 / 跑 `ingest_diff.py` 发现未摄取项。

**流程**（agent 驱动）：

1. 跑 `scripts/ingest_diff.py <wiki-root>`（日常加 `--check-stale`）找出需要摄取的文件
   清单——含全新文件（untracked）与 raw 被更新过的已归档文件（stale-raw）
2. 对每个文件：
   - **必读** raw 资料全文（含 PDF / 图片需先 OCR / 视觉识别）
   - 提取关键信息：标题、作者 / 来源、主题、关键论点、引用关系、可链接的实体 / 概念
   - 在 `wiki/sources/<slug>.md` 写**摘要页**（frontmatter + 摘要 + 关键引用 + 跨链）；
     若是 stale-raw（该页已存在），走 **Edit** 更新正文 + `updated`，**不要** Write 覆盖
   - 同步相关 `entities/` / `concepts/` 页面（追加"参考资料"段，不重写）
   - 同步 `wiki/index.md`（追加 source 条目 + 视情况更新 entity/concept 条目）
   - 追加 `log.md` 条目：`## [YYYY-MM-DD] ingest | <source title>`
3. **commit**（建议但非必须）——仅当 wiki 启用了 git 时；未启用 git 跳过此步
   （裸目录树无版本控制，由用户自行决定是否后续手动 init / 回填）。commit 节奏由
   用户 / agent 决定

详细模板与 frontmatter 字段见 [`references/ingest-workflow.md`](references/ingest-workflow.md)
+ [`references/page-templates.md`](references/page-templates.md)。

### 2. Query（跨页综合）

**触发**："wiki 里有 X 吗" / "总结 wiki 中关于 Y 的内容" / "对比 A 和 B"。

**流程**：

1. **先看 index.md**——按关键词 / 类别找候选页
2. **读相关页**（不读 raw——raw 已经在 source 页里消化过）
3. **跨页综合**——用引用形式带 source 链接；矛盾处显式标注："A 说 X（来源：...），
   B 说 Y（来源：...），需要更深入调研"
4. **展示答案 + 询问归档**——如果答案有"对比 / 综合 / 发现联系"的性质，询问用户：
   "这段答案适合归档回 wiki 作为 comparisons/<slug>.md 吗？"
5. **用户同意后归档**——走 references/page-templates.md 的 `comparison` 或
   `synthesis` 模板 + 追加 log 条目

详细 query 流程与判定规则见 [`references/query-workflow.md`](references/query-workflow.md)。

### 3. Lint（健康检查）

**触发**："lint wiki" / 定期（频率阈值见 [lint-checklist.md §六](references/lint-checklist.md#六lint-频率)）/ 大型 wiki 主动建议。

**流程**：

1. 跑 `scripts/lint_wiki.py <wiki-root>` 做 deterministic 检查
2. 脚本覆盖（详见 [`references/lint-checklist.md`](references/lint-checklist.md)）：
   - `raw/` 是否被改（脚本**自动检测** wiki 根目录是否在 git 仓内：
     - `.git/` 不存在 → 跳过 + 在输出顶部 `[NOTES]` 提示"未启用 git"
     - `.git/` 存在但 `raw/` 未纳入 git → 跳过 + 提示"raw/ 未纳入 git"
     - 真 git 仓 + raw 被改 → 报 `raw-modified`
     强制 `--no-git` 则完全静默跳过，不打 note）
   - 缺 frontmatter 的页面
   - 缺 `type` / `sources` / `updated` 字段的页面
   - `wiki/index.md` 没列出的非 log 页面（孤儿）
   - 失效的相对路径引用（`[link](sources/missing.md)` 之类的断链）
   - `log.md` 条目格式不合规（不符合 `## [YYYY-MM-DD] <op> | <title>`；权威正则见 [page-templates.md §7](references/page-templates.md#7-logmdlog)）
   - 过期摘要（`type: source` 且 `updated` 距今超过阈值；阈值见 [lint-checklist.md §二.7](references/lint-checklist.md#7-过期摘要)）
3. 脚本输出报告后，**agent 还要做半定性检查**：
   - 矛盾主张（同一概念在两个 page 中说法冲突）
   - 缺失的交叉引用（页 A 提到 B 概念但没链到 `concepts/b.md`）
   - 建议新摄取 / 新调查方向
4. 报告 + 询问用户哪些修

详细 checklist 见 [`references/lint-checklist.md`](references/lint-checklist.md)。

### 4. Memory（写入 LLM agent 持久化记忆）

**触发**：在 ingest / query / lint 过程中识别到值得沉淀的信息——踩坑、用户偏好、跨文档关联。

**何时写**（参见 `wiki/MEMORY/README.md`）：

- **遇到踩坑**——raw/ 里的 PDF 经常有 OCR 错误，下次让用户先转换格式
- **发现用户偏好**——用户偏好表格化的对比、不喜欢散文式总结
- **跨 ingest 的关联**——两个 source 页指向同一篇会议论文的不同章节
- **lint 报告的 recurring pattern**——每次 lint 都报某个特定 type 缺字段

**流程**（agent 主动）：

1. 决定是否值得写——是否能让未来的自己 / 未来的 agent 工作更顺？
2. 在 `wiki/MEMORY/<slug>.md` 创建文件（kebab-case 命名按主题归类，**不**按时间归档）
3. 写 frontmatter（5 必填：title / type / created / updated / tags；推荐 description）
4. 写正文——记录具体经验，含上下文（什么时候遇到、怎么解决的、未来如何避免）
5. **不**追加 log 条目——MEMORY 不是操作时间线
6. **不**在 wiki/index.md 列出——MEMORY 不走单一入口约束

**纪律**：

- 不删除任何 MEMORY 文件——踩坑记录沉淀下来，未来回顾有价值
- 写新文件时**保留**原文件的 `created` 字段；只更新 `updated`
- 用户**不**直接编辑 MEMORY/——若用户想补充，先转告 agent 由 agent 写入

## 参考样例

### 样例一：setup 一个 LLM Systems 主题的 wiki

**用户指令**："我想搭一个 wiki 用来跟踪 LLM Systems 主题的研究资料"

**执行**：

```text
1. 告知用户：本 skill 不直接创建 wiki 仓；wiki 创建由 workspace CLI 负责
   → 推荐路径建议在 ~/wiki/llm-systems
2. 用户调 workspace CLI（具体命令以 CLI 文档为准）：
   workspace wiki init "LLM Systems" --root ~/wiki/llm-systems
   → CLI 按 wiki-spec.md 落盘目录 + CLAUDE.md + index.md + log.md + .gitignore
   → CLI 默认不建 git（用户 --git opt-in 时才 init + commit）
3. LLM agent 接管后：
   → 读 ~/wiki/llm-systems/CLAUDE.md 确认主题名替换正确
   → 验证 wiki/index.md / wiki/log.md 存在且 frontmatter 完整
   → 提示用户：raw/articles/ 作为"资料投放口"，可放剪藏 / PDF / 笔记
4. 提示用户：wiki 根目录内的 CLAUDE.md 会被 Claude Code 自动加载；
   别处工作时 skill 经 $LLM_WIKI_ROOT 按需读取，不必 symlink
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
1. python3 llm-wiki-management/scripts/lint_wiki.py ~/wiki/llm-systems
2. 脚本报告：
   - raw/ 干净（启用 git 时 git status clean；未启用时此项自动跳过 + 输出顶部
     `[NOTES] raw-immutable-skipped: 未启用 git（无 .git/）` 提示）
   - 3 个页面缺 updated 字段
   - 1 个失效引用：concepts/transformer.md 链到 sources/bigtable.md 但后者不存在
   - 5 个 source 页 updated 超过 stale 阈值（阈值见 [lint-checklist §二.7](references/lint-checklist.md#7-过期摘要)），建议复查
   - 1 个孤儿页：concepts/scaling-laws.md 没有任何 inbound link
3. agent 补充半定性观察：
   - sources/llama-3.md 与 sources/llama-2.md 对 "context window" 的描述不一致
4. 整理成结构化报告，问用户先修哪些
```

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
| **本 skill（llm-wiki-management）** | 个人 / 研究的本地复利型知识库 | 本地 Markdown（git 可选 opt-in） |
| `outline-wiki-upload` | 团队 / 协作：写 / 编辑 / 推图到 Outline | Outline Wiki MCP |
| `outline-wiki-search` | 团队 / 协作：搜 / 读 Outline 文档 | Outline Wiki MCP |
| `design-doc-edit` | 单篇设计文档写作（含强制章节骨架） | 单文件 Markdown |
| `gemini-paper-summary` | 单篇论文的结构化摘要（含视觉抽图） | 单文件 Markdown + 图片 |

可串行：**gemini-paper-summary** 抽图 → 本 skill **ingest** 归档到 wiki →（未来独立 publish skill）→ `outline-wiki-upload` 分享对外

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

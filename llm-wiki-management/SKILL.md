---
name: llm-wiki-management
description: 在独立的本地 git 仓中维护 LLM 驱动的个人知识库——遵循 Karpathy
  "LLM 拥有 wiki、人类只读" 的模式：三层架构（raw/ 不可变原始资料 + wiki/
  LLM 生成的相互链接 Markdown + CLAUDE.md schema 宪法）、三核心操作（ingest 摄取
  资料并写摘要页 / query 跨页综合出可归档的答案 / lint 健康检查找矛盾与孤儿页）、
  与 index.md 目录 + log.md 时间线双轨。触发词：'摄取/归档到 wiki'、'wiki 里有...'、
  'lint wiki / wiki 健康检查'、'把 X 整理成 wiki'、提到 raw/ 与 wiki/ 双目录
  结构、维护 CLAUDE.md schema。**不用于**云端协作 wiki（Notion / Confluence /
  Outline / GitHub Wiki）；云端场景走 outline-wiki-management skill。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-25
---

# LLM Wiki Management

按 Karpathy [LLM Wiki 设计哲学](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
维护一个**本地**、**复利累积**的知识库：用户只管读 + 提供资料 + 提问题，LLM 负责摘要、
交叉引用、归档、簿记这些"无聊的部分"。和 `outline-wiki-management` 的关键区别是
**本地文件 + 三层纪律**——vs 云端 MCP 单层文档。

本 skill 提供三块交付物：

- **SKILL.md（本文）**——工作流 + 纪律的"宪法"
- **scripts/**——setup_wiki.py / ingest_diff.py / lint_wiki.py，把高频 deterministic
  任务固化下来
- **references/**——按需加载：CLAUDE.md schema 模板、各操作详细流程、页面模板

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
  `outline-wiki-management` skill
- **一次性文档生成**（不是累积型）——直接用普通文件写入流程
- **没有 raw/ 资料 + 没有累积需求**——skill 的价值在"复利"，一次性整理用不上
- **需强结构化数据库**（带 schema / SQL / 全文检索后端）——wiki 规模 ≤ 数百页时
  index.md 足够；超过该规模再考虑迁移到专用工具
- **多人实时协作**——本 skill 假设单人使用（git commit 节奏就是节奏）

## 输入 / 输出

### 启动时需具备的信息

| 信息 | 来源 | 备注 |
| --- | --- | --- |
| Wiki 根目录 | `LLM_WIKI_ROOT` 环境变量，或交互时问 | 例 `~/wiki/llm-systems` |
| 主题名 | setup 时一次性指定，写入 `CLAUDE.md` | 例 "LLM Systems" |
| 操作类型 | 用户自然语言 | ingest / query / lint / setup |
| 触发资料 | ingest 时给文件路径或目录 | 必须在 `raw/` 内 |

### 操作产物

- **setup** → `raw/` + `wiki/` 子目录、`wiki/index.md`、`wiki/log.md`、`<wiki-root>/CLAUDE.md`（从
  `references/claude-md-template.md` 拷贝并填入主题名）
- **ingest** → 新增 / 更新 `wiki/sources/<slug>.md` + 同步实体 / 概念页 + 追加
  `log.md` 条目 + 更新 `index.md`
- **query** → 对话中给出答案（带引用），**可选**把答案归档为 `wiki/comparisons/`
  或 `wiki/syntheses/<slug>.md`
- **lint** → `log` 中报告：raw/ 是否被改、孤儿页、断裂交叉引用、过期摘要、缺
  frontmatter、log.md 格式

## 设计决策

### 三层架构——为什么是三层

参考 Karpathy gist 的核心论断：**"Knowledge 的累加依赖纪律，不依赖意志力"**。
三层各自承担一个责任，互相制衡：

1. **`raw/` 真相之源**——用户只管策划原始资料（论文、剪藏、PDF、笔记、播客转写），
   对 LLM 只读。`raw/` 下子目录自由组织——setup 脚本默认建 `articles/` + `assets/`，但
   `podcasts/` / `clippings/` / `papers/` 等自定义子目录同样可用；`ingest_diff.py` 递归扫整棵
   `raw/`。所有 wiki 内容都从 raw 推导而来；raw 被用户更新后，在重新 ingest 之前
   wiki 会与真相暂时脱节（`ingest_diff.py --check-stale` 负责发现这种情况）。
2. **`wiki/` 复利资产**——LLM 拥有这一层。人类**不写** wiki，只读 + 提问题。每次
   摄入新资料或回答新问题，wiki 都变得**更厚**而不是更乱。
3. **`CLAUDE.md` 纪律配置**——把"wiki 怎么写 / 写什么 / 不写什么"的约定集中到
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

`outline-wiki-management` 走云端 MCP（Outline Wiki），适合团队协作、外部分享、
权限管理。本 skill 走**本地 + git**，原因：

- **隐私**——研究 / 读书 / 个人思考不需要上云
- **版本控制**——git 自带 history、diff、branch
- **可移植**——纯 Markdown + 文件，不绑任何平台
- **无外部依赖**——不需要 OAuth / API key / 网络

两套 skill **不冲突**：本地研究沉淀 → 云端分享，方向是单向的。

## 执行原则 / 边界

### 核心原则

> **操作前置（所有操作通用）**：每次 ingest / query / lint 启动前，先
> `Read <$LLM_WIKI_ROOT>/CLAUDE.md` 拿到本 wiki 的主题名与边界配置。在 wiki 根目录内
> 工作时它会被 Claude Code 自动加载；别处由 skill 按需读取——**不依赖 symlink**。

1. **raw/ 由用户掌控，LLM 只读**——LLM 从不写/删/移 `raw/` 下文件；用户可随时新增/更新
   raw/（重新剪藏、重存 PDF 都算），改动由 ingest 重新消化（更新对应 source 页正文 +
   `updated`，`ingest_diff.py --check-stale` 按 mtime vs source `updated` 标记待重新摄取项）
2. **wiki/ 由 LLM 撰写**——用户从不手写 wiki 页面（编辑 CLAUDE.md 除外，那是 schema）
3. **CLAUDE.md 是 schema，不是文档**——它是给 LLM 看的"工作守则"，不要往里塞内容
4. **每次写入必更 log.md**——格式 `## [YYYY-MM-DD] <op> | <title>`，op 取值四选一：
   `ingest` / `query` / `lint` / `setup`（`scripts/lint_wiki.py:34` 与 `scripts/setup_wiki.py:81` 以
   此为准；其它取值会被 lint 报格式错乱）
5. **每页必带 YAML frontmatter**——共有必填 `type` / `title` / `created` / `updated` /
   `tags`；推荐 `description`（一句话，`index.md` 条目摘要从它来）。`type` 取值仅 5 类内容页
   （`entity` / `concept` / `source` / `comparison` / `synthesis`）；`index.md` / `log.md` 是
   reserved 文件，自带 `type: index` / `type: log`，lint 跳过它们——不算概念页 `type`。
   `sources`（raw/ 路径）**非共有**：`source` / `synthesis` 必填、`entity` / `concept` 可选、
   `comparison` 不用。字段权威清单见 [`references/page-templates.md`](references/page-templates.md)
   （与 `lint_wiki.py` 同步）
6. **交叉引用走相对路径**——`[link](sources/bigtable.md)`，不用绝对路径，不用 wikilink
7. **index.md 是 wiki 单一入口**——所有非 log 页必须在 `wiki/index.md` 中出现
8. **query 的好答案必问"是否归档"**——能写回 wiki 的不要浪费在聊天里

### 边界

- **不**编辑 `raw/` 下任何文件（LLM 只读；用户可改，改后由 ingest 重新消化）
- **不**删除 `wiki/` 下的页面——用 `archived: true` 标记 + 从 index 移除；想真删走 git
- **不**绕过 `CLAUDE.md` 自创约定——若 CLAUDE.md 没说的，**先问用户**再写
- **不**在 query 时偷偷归档——必须先展示答案 + 询问用户
- **不**忽略 lint 报告——长期不 lint 的 wiki 一定会腐烂
- **不**用 git 操作破坏 raw/ 不可变性（不要 `git clean` / `git checkout -- raw/`）
- **不**对 wiki 内文件用 Read 之外的工具做"自动"修改——所有修改走 Edit / Write 并
  走 schema 约定

### 反模式（绝对禁止）

- 在 wiki 页面里手写"先写一段话再贴图"等散文式总结（散弹式散落口径冲突的根源）
- 把同一个概念分散在多个 entities/ 文件里（必须先 search 是否已有同名页）
- 不写 log 条目就改 wiki（无法审计 + 无法 ingest_diff 识别新文件）
- 跨 wiki 互引但不更新对端 index（两套 wiki 同步是用户的责任）
- 用 Obsidian-only 语法（`[[wikilink]]`、`![[embed]]`）——本 skill 假设通用 Markdown

## 工作流 / 步骤

### 0. 一次性 setup（首次使用）

详见 [`references/operations/setup.md`](references/operations/setup.md)。概要：

```bash
# 1. 创建独立 git 仓
mkdir -p ~/wiki/<topic-name> && cd ~/wiki/<topic-name> && git init

# 2. 把原始资料放进 raw/（用户手动 / Obsidian Web Clipper / 浏览器下载）
# 例：
cp ~/Downloads/some-article.md raw/articles/

# 3. 调 setup 脚本（agent 驱动）
LLM_WIKI_ROOT=~/wiki/<topic-name> \
python3 llm-wiki-management/scripts/setup_wiki.py <topic-name>
```

setup 脚本做的事：
- 建 `raw/articles/`、`raw/assets/`、`wiki/{entities,concepts,sources,comparisons,syntheses}/`
- 拷 `references/claude-md-template.md` 到 `<wiki-root>/CLAUDE.md`，填入主题名
- 建 `wiki/index.md`（带 frontmatter + 类别分组的空目录）
- 建 `wiki/log.md`（带 frontmatter 的空日志）
- 提示用户：`<wiki-root>/CLAUDE.md` 是本 wiki 的 schema——在 wiki 根目录内工作时
  Claude Code 会自动加载它；在别处工作由 skill 经 `$LLM_WIKI_ROOT` 按需读取，**无需 symlink**

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
3. **commit**（建议但非必须）——用户 / agent 决定 commit 节奏

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

### 3. Lint（健康检查）

**触发**："lint wiki" / 定期（如每月一次）/ wiki 规模超过 ~50 页时主动建议。

**流程**：

1. 跑 `scripts/lint_wiki.py <wiki-root>` 做 deterministic 检查
2. 脚本覆盖（详见 [`references/lint-checklist.md`](references/lint-checklist.md)）：
   - `raw/` 是否被改（`git status raw/`）
   - 缺 frontmatter 的页面
   - 缺 `type` / `sources` / `updated` 字段的页面
   - `wiki/index.md` 没列出的非 log 页面（孤儿）
   - 失效的相对路径引用（`[link](sources/missing.md)` 之类的断链）
   - `log.md` 条目格式不合规（不符合 `## [YYYY-MM-DD] <op> | <title>`）
   - 过期摘要（`updated` 距今 > 90 天且 `type: source`）
3. 脚本输出报告后，**agent 还要做半定性检查**：
   - 矛盾主张（同一概念在两个 page 中说法冲突）
   - 缺失的交叉引用（页 A 提到 B 概念但没链到 `concepts/b.md`）
   - 建议新摄取 / 新调查方向
4. 报告 + 询问用户哪些修

详细 checklist 见 [`references/lint-checklist.md`](references/lint-checklist.md)。

## 参考样例

### 样例一：setup 一个 LLM Systems 主题的 wiki

**用户指令**："我想搭一个 wiki 用来跟踪 LLM Systems 主题的研究资料"

**执行**：

```text
1. 问用户 wiki 根目录（建议 ~/wiki/llm-systems）
2. mkdir ~/wiki/llm-systems && cd ~/wiki/llm-systems && git init
3. 调 setup_wiki.py "LLM Systems"
   → 自动建 raw/articles/, raw/assets/, wiki/{entities,concepts,...}
   → 拷 CLAUDE.md schema 模板（主题名 = "LLM Systems"）
   → 建 wiki/index.md, wiki/log.md
4. 提示用户：把 raw/articles/ 作为"资料投放口"，可以放剪藏 / PDF / 笔记
5. 提示用户：wiki 根目录内的 CLAUDE.md 会被 Claude Code 自动加载；别处工作时 skill
   经 LLM_WIKI_ROOT 按需读取，不必 symlink
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
7. 建议 git commit
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
   - raw/ 干净（git status clean）
   - 3 个页面缺 updated 字段
   - 1 个失效引用：concepts/transformer.md 链到 sources/bigtable.md 但后者不存在
   - 5 个 source 页 updated > 90 天，建议复查
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
| `type` 取值 | 固定 5 类 | §4.1 开放（生产者自定义） | OKF 开放集的子集 |

本 wiki 可被任意 OKF 消费端"尽力读取"（§9 的宽容消费模型要求不得因上述分歧拒收），但不声称
100% 合规。要跨组织交换 bundle 时，再按"完全合规"档收敛（去掉 index/log frontmatter、log 改
`## date` + 列表、相对链接换 bundle 绝对）。

## 与其他 skill 的边界

| Skill | 场景 | 介质 |
| --- | --- | --- |
| **本 skill（llm-wiki-management）** | 个人 / 研究的本地复利型知识库 | 本地 Markdown + git |
| `outline-wiki-management` | 团队 / 协作 / 外部分享的云端 wiki | Outline Wiki MCP |
| `design-doc-edit` | 单篇设计文档写作（含强制章节骨架） | 单文件 Markdown |
| `gemini-paper-summary` | 单篇论文的结构化摘要（含视觉抽图） | 单文件 Markdown + 图片 |

可串行：**gemini-paper-summary** 抽图 → 本 skill **ingest** 归档到 wiki → `outline-wiki-management` 分享对外

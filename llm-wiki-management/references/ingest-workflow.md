# Ingest 详细流程

Ingest 把 `raw/` 里的原始资料变成 wiki 内的**摘要页** + 同步相关 entity / concept
页 + 更新 index + 追加 log。一份资料通常涉及 **1 source 页 + 0~N entity / concept
页 + 1 index 更新 + 1 log 条目**。

## 一、为什么 ingest 是 wiki 的"主循环"

Karpathy 设计的核心论断：**"Most people's experience with LLMs and documents looks
like RAG... There's no accumulation."** Ingest 是把 RAG（每次查询时重抽片段）变成
"复利积累"的关键——同一份资料被消化一次，永久可查；后续 query 自动受益。

## 二、入口与触发

**主动触发**：用户说"摄取 X 到 wiki" / "把 raw/articles/foo.md ingest" /
"raw/articles/ 里这批都摄取一下"。

**被动触发**：用户跑 `ingest_diff.py` 发现未摄取项，问"这些是不是要 ingest"。

**定期触发**：用户设 cron / 习惯——每周一次把 `raw/articles/` 新增的全部 ingest。

## 三、流程详解

### Step 1：识别需要摄取的文件

```bash
# 日常：同时找全新文件 + raw 被更新过的已归档文件
python3 llm-wiki-management/scripts/ingest_diff.py "$LLM_WIKI_ROOT" --check-stale
```

- 扫 `raw/` 递归，对照所有 `wiki/sources/*.md` 的 `frontmatter.sources` 建立 raw 路径 → source 页映射
- 输出需要关注的文件清单（plain text 或 `--json`），按 reason 分三类：
  - `untracked`——从未摄取的全新文件
  - `stale-raw`（仅 `--check-stale`）——已有 source 页，但 raw 文件 mtime 晚于 source
    页 `updated`，说明 raw 被用户更新过，需**重新摄取**
  - `log-only-no-source-page`——log 有 ingest 记录但 source 页缺失，需重建
- 退出码：0 = 无需关注；1 = 有需要处理的项

**注意**：判定"已摄取"的依据是**对应 source 页存在且 frontmatter.sources 含此路径**。
仅在 log.md 里有引用但 source 页被删的视为**未摄取**——这种情况需要重建 source 页。

### Step 2：评估规模

如果未摄取文件 < 5 → 一次性处理；5~20 → 建议分批但可接受；> 20 → 强烈建议
分批 + 询问用户"是否先处理这 5 个"。

**分批策略**：按主题聚类（同一论文 / 同一作者 / 同一时间段优先），不要按文件
名随机排序。

### Step 3：写 source 页

对每个待摄取文件（untracked 或 stale-raw）。**stale-raw 的关键差异**：对应 source 页已
存在 → 用 **Edit** 更新正文 + 把 `updated` 改今天（`created` 保留原值），**不要** Write
覆盖、不要重建 entity / concept 的"参考来源"段（只追加新来源）：

> **若重摄发现新内容与已有 entity / concept 页主张矛盾**——不要静默覆盖旧说法，走
> CLAUDE.md「矛盾处理 Update Policy」（双方设 `contested: true` + `contradictions` 互指、
> 正文显式记录两种说法）。这是 `contested` 信号最常见的产生时机。

1. **完整读取 raw 资料**——若是 PDF / 图片，先做 OCR / 视觉识别
2. **提取元数据**：标题、作者 / 来源、发布时间、URL（若有）、关键标签
3. **生成 slug**——kebab-case 短标题（例 `attention-is-all-you-need`），文件名
   `<slug>.md`
4. **写 `wiki/sources/<slug>.md`**，使用 source 模板（见 `page-templates.md#source`）：
   - frontmatter：title / description（一句话摘要，index 摘要从它来）/ type=source /
     tags / sources=[raw 路径] / updated=today（`created`：全新文件设 today；stale-raw 保留原值）
   - 正文：
     - 摘要（200-500 字）——核心论点 / 关键数据 / 与本 wiki 其他资料的关系
     - 关键引用——可独立成段的引文 / 数字 / 结论
     - 链接出去的 cross-refs——相关 entity / concept / source 页
   - **认知质量信号（可选）**：fast-moving / 争议 / 单一弱来源的 source 页，建议在 frontmatter
     标 `confidence: medium` 或 `low`（字段语义见 [page-templates.md §一](page-templates.md#可选认知质量信号防弱主张固化成事实)）。
     多源印证且稳定的页可标 `high` 或省略。这让弱主张"自带警示"，lint 会把 `low` 拎出来提醒
5. **决策点：是否需要新建 entity / concept 页**
   - 例：raw 资料里反复提到"self-attention"，但 `concepts/self-attention.md` 不存在
   - → 新建 `concepts/self-attention.md`（首次出现 + 值得沉淀的概念）
   - → 反例：raw 资料里偶然提到一次"GPU" → 不必新建（看主题粒度）

### Step 4：同步 entity / concept 页

**若已有相关 entity / concept 页**：

- **不重写**——只追加"## 参考来源 / Sources"段
- 每条新 source 写一行：`* [Source Title](../sources/<slug>.md) — 一句话关联点`
- **保持顺序**：新追加的放最前面或最后面，整个文件**只追加**不重排
- 同时把对应 raw 路径加到该 entity / concept 页 frontmatter 的 `sources` 数组

**若新建 entity / concept 页**：

- 走 `page-templates.md#entity` 或 `#concept` 模板
- frontmatter 含 `created=updated=today`
- 正文含：定义 / 关键属性 / 已知出现于（指向 source 页列表）

### Step 5：更新 `wiki/index.md`

- 在对应类别（sources / entities / concepts）追加条目
- 格式：`* [<title>](<relative-path>) — 一句话摘要`；**摘要直接复制该页 frontmatter 的
  `description`**，不要在 index 里重写第二份（避免漂移）
- 同一类别下按 created 倒序还是字母序？**选字母序**——稳定 + 视觉清晰
- 若新建了 entity / concept 页：同时**反向检查**——之前 source 页是否该有指向新页的
  cross-ref？没有就加（这是"维护交叉引用"的一部分）

### Step 6：追加 `log.md`

- 格式严格：`## [YYYY-MM-DD] ingest | <short title>`
- title 用 source 页的 `title` 字段，不要重写
- 一行结束，不要续行
- 一次 ingest 多个文件 → **写多条 log 条目**，每条对应一个 source 页

### Step 7：建议 commit（启用 git 时）

> **前提**：本步仅在 wiki 启用了 git 时执行；裸目录树 wiki 直接跳过（无版本控制，
> 由用户决定是否后续手动 `git init` + 回填 history）。

- 不是必须，但强烈建议——wiki 改动可追溯
- commit message 格式：`ingest: <title>` 或 `ingest: <N> files from raw/articles/`
- agent 应提示用户："wiki 已更新，建议 commit。message 草稿：`<msg>`，要我帮你
  commit 吗？"

## 四、frontmatter 字段参考（source 页）

> **权威定义在 [`page-templates.md §一`](page-templates.md#一共有-frontmatter-段) +
> [`§二.3`](page-templates.md#3-source资料页)**——本节只列 source 页的特化字段注意事项，
> 不重抄字段全集。

**source 页特有字段**：

- `sources` 必填——`raw/` 下相对路径数组，至少 1 条
- 推荐 `authors` / `published` / `url` / `venue`——便于 index 摘要 + 反向溯源

**示例**（完整字段定义见 page-templates.md §二.3）：

```yaml
---
title: "Attention Is All You Need"
description: "提出 Transformer——完全基于 attention、抛弃 RNN/CNN 的序列建模。"
type: source
tags: [transformer, attention, paper-2017]
created: 2026-06-24
updated: 2026-06-24
sources:
  - raw/articles/attention-is-all-you-need.md
authors: [Vaswani, Shazeer, Parmar, et al.]
published: 2017-06-12
venue: NeurIPS 2017
url: https://arxiv.org/abs/1706.03762
---
```

## 五、判定"是否新建 entity / concept 页"的启发

- **新建**条件（任一满足）：
  - raw 资料用了 ≥ 3 次该概念
  - raw 资料明确将其作为核心论点之一
  - 用户后续 query 时可能直接搜这个概念
- **不新建**条件（任一满足）：
  - raw 资料里只是路过 / 类比 / 背景提及
  - 该概念在 wiki 中粒度过细（例：每次会议人名都建 entity 就太碎了）
  - 已经有同名 / 近义页

## 六、Ingest 失败的常见原因

- **raw 文件不可读**（PDF 加密、图片 OCR 失败）——提示用户处理源文件
- **已存在同名 source 页**——用 Edit 更新而不是 Write 覆盖
- **wiki/index.md 缺类别段**——可能是 setup 没跑完整；先调 setup 修复
- **log.md 格式错乱**——append 前先确认上一行有换行结束

## 七、反模式

- ❌ 一份资料写 5 个 source 页（粒度过细）——按"主题"分，不是按"raw 文件 1:1"
- ❌ source 页只复制 raw 内容——必须消化、提炼、加 cross-refs
- ❌ entity / concept 页"重写式更新"——只 append "Sources" 段
- ❌ 跳过 log.md——失去审计能力 + ingest_diff.py 失效
- ❌ 跳过 index.md 更新——wiki 失去单一入口
- ❌ 跨主题的 entity 混在一起——本 skill 假设一个 wiki 一个主题；跨主题用不同的 wiki

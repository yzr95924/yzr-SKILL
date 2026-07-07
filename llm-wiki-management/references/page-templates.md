# 页面模板

按 `type` 分 5 种。**所有页面**共有 frontmatter 段（见下）+ 类型特定字段 + 自由正文。

> **本章顺序说明**：下面按**教学序**列出（基础 → 综合：entity → concept → source
> → comparison → synthesis）。spec 强制**字母序**用于目录结构与 `type` 取值表——
> 见 [wiki-spec.md §1 / §9](wiki-spec.md)。

## 目录

- [一、共有 frontmatter 段](#一共有-frontmatter-段)
- [二、各类型模板](#二各类型模板)
  - [1. `entity`（实体页）](#1-entity实体页)
  - [2. `concept`（概念页）](#2-concept概念页)
  - [3. `source`（资料页）](#3-source资料页)
  - [4. `comparison`（对比页）](#4-comparison对比页)
  - [5. `synthesis`（综合页）](#5-synthesis综合页)
  - [6. `index`（index.md）](#6-indexindexmd)
  - [7. `log.md`（log）](#7-logmdlog)
- [三、模板使用规则](#三模板使用规则)

> **frontmatter 写法约束**（与 `scripts/ingest_diff.py` 的轻量 YAML 解析器对齐）：仅支持单行
> `key: value`、inline 数组 `[a, b, c]`、`- item` 列表项三种形式。**不要**使用多行折叠 `>` /
> `|`、YAML 锚点 `&` / `*`、嵌套 map——脚本会静默解析失败、返回空 dict、后续 ingest 与 lint
> 行为未定义。

## 一、共有 frontmatter 段

```yaml
---
title: <string, 必填>
description: <一句话摘要, 推荐>  # 推荐（OKF v0.1 推荐字段）；index.md 条目摘要从它来，避免漂移
type: <entity|concept|source|comparison|synthesis, 必填>  # 5 类内容页；index/log 是 reserved（见 §6 / §7）
tags: [<string array>, 必填但可空数组]
created: <YYYY-MM-DD, 必填>
updated: <YYYY-MM-DD, 必填>
# —— 以下为可选「可信度与认知质量信号」（见下方同名段）——
reviewed: <true, 可选>            # 仅在为 true 时写：人工已审核该页
reviewed_at: <YYYY-MM-DD, 可选>   # 审核日期；与 reviewed: true 成对出现
contested: <true, 可选>           # 仅在为 true 时写：本页含未解决的矛盾主张
contradictions: [<wiki 页路径数组>, 可选]  # 与本页主张冲突的页面（双向标注：A 标 B，B 也标 A）
---
```

**字段说明**：

- `title`——人类可读标题，不要带文件扩展名
- `description`——**推荐**（OKF v0.1 推荐字段）。一句话总结本页；`index.md` 条目摘要从它来，
  避免在 index 里手写第二份、与正文漂移（lint 抓不到这种不一致）
- `type`——驱动 lint 校验 + index 分组；合法值仅上述 5 种（`lint_wiki.py` 强制）。`index.md` /
  `log.md` 是 **reserved 文件**（结构见 §6 / §7），自带 frontmatter，其中 `type: index` /
  `type: log` 仅作标记、lint 跳过它们——不算概念页 type
- `tags`——用于跨页搜索 + 未来可能的 dataview 查询。**取值必须严格在
  [`wiki/tags.md`](wiki-spec.md#91-tag-白名单来源080) 白名单内**——agent 在 ingest /
  query 遇到新 tag 时**直接追加**到 `wiki/tags.md`（无需询问用户），保持字典随 wiki 生长；
  用户可随时打开 `wiki/tags.md` **直接删除**误判的 bullet，下次 lint 把残留引用以
  `tag-not-in-taxonomy`（info）报回来再裁定。详 lint 语义见
  [`lint-checklist.md`](lint-checklist.md#11-tag-taxonomy-校验080)
- `created` / `updated`——**严格** `YYYY-MM-DD` 格式（lint 解析用）
- 类型特定字段（`sources` / `compared` / `threads`）见各模板
- `reviewed` / `reviewed_at` / `contested` / `contradictions`——**可选**可信度与认知质量信号，见下

### 可选：可信度与认知质量信号

> **为什么需要**：wiki 的复利价值依赖"已沉淀的主张可被信任"。但 LLM 自动写入的页面——
> 尤其是凭单篇弱来源的断言——一旦写进 wiki 不再标注，时间一长会被当成"既成事实"，这是**认知腐烂**，
> 比断链 / 孤儿更隐蔽。本段两类信号把腐烂显性化：
>
> - **`reviewed` / `reviewed_at`** —— 人工**审核背书**："我读过了，愿意为它背书"。
>   query 阶段 agent 据此优先采信；lint 报告 `pending-review` 清单；`index.md` 上以 ✓ / ✗ 标记。
> - **`contested` / `contradictions`** —— **认知冲突未裁定**的告警："这里有两个说法打架，等人复审"。
>   与可信度正交：一个页面可以既 `reviewed: true` 又 `contested: true`（"我审核过，确实有矛盾待裁定"）。

四个字段（**全部可选**；`reviewed` 与 `reviewed_at` 应成对出现，`contested` 与 `contradictions` 同）：

- `reviewed: true`——**仅**在为 `true` 时写。人工**已审核该页**的可信度背书。
  - 缺省 = 未审核（lint 报 `pending-review` info，新常态，不算腐烂）
  - lint 校验：`reviewed` 取值必须严格为 `true`（裸 token，不是 `"true"` 字符串、`yes`、`1`、`false`）
  - 与 `reviewed_at` 必须成对出现，单独写任一字段给 `reviewed-at-missing` / `reviewed-at-orphan` warn
- `reviewed_at: <YYYY-MM-DD>`——审核日期。与 `reviewed: true` 配套。
  - lint 校验：`updated > reviewed_at` 时给 `reviewed-stale` warn（LLM 修改后未清 reviewed，戳过期）
- `contested: true`——**仅**在为 `true` 时写。表示本页存在**尚未裁定**的矛盾主张
  （搭配 `contradictions` 指向对端）。lint 把所有 `contested: true` 的页集中拎出供用户复审，
  避免悬而未决的冲突被后续 ingest 静默继承
- `contradictions: [path-a, path-b]`——与本页主张**冲突**的 wiki 页路径数组（相对路径，
  与交叉引用同写法）。**双向标注**：A 把 B 列进 `contradictions`，B 也应把 A 列进来；
  lint 检查这种对称性（单向 = `contradiction-asymmetric` warn）

#### 生命周期规则（LLM 必读）

`reviewed: true` 是"我对这一刻的内容背书"的快照，**不是永久标签**。任何对页面正文的
LLM 修改都会让戳失效。纪律：

| 事件 | 对 `reviewed` / `reviewed_at` 的操作 |
| --- | --- |
| LLM 创建新页 | 不写（默认未审核） |
| 人标记已审核 | 写 `reviewed: true` + `reviewed_at: <今天>` |
| LLM 修改页（含 ingest 重摄取、query 归档、refine、任何 Edit/Write） | **必须删除这两个字段**（回到默认未审核） |
| LLM 仅改 `updated` 字段（无正文变化） | 不动（meta 操作，不算内容变更） |

**两道闸门**：

1. **纪律闸门**——本节是唯一权威；其它文件（SKILL.md / agents-md-template.md / ingest-workflow.md /
   wiki-spec.md）只引用、不重抄（例外：`agents-md-template.md` 必须自包含完整纪律——它是 wiki
   自带的 AGENTS.md 模板，会被拷到每个 wiki 仓，不能跨仓引 SKILL.md）
2. **lint 兜底**——`reviewed-stale` 触发条件：`reviewed: true` 存在 **且** `updated > reviewed_at`，
   把 LLM 漏清戳的页面拎出来提示人复审

**何时设 `reviewed: true`**：

- 人读完页面所有正文 + 交叉引用 + 关键 raw 资料，确认主张站得住 → 写 `reviewed: true` + `reviewed_at: <今天>`
- 不是看完了就一定审——遇到 `contested: true` 或 `contradictions` 非空时**不**应盲目标 reviewed，
  应先裁定冲突再标
- 已审过的页被 LLM 修改后，回到默认未审核状态，等人再次复审

**矛盾处理的完整 Update Policy**（ingest 时遇到"新资料与已有页冲突"怎么做）见
[`agents-md-template.md`](agents-md-template.md)「矛盾处理 Update Policy」段——本节只定义字段语义。

## 二、各类型模板

### 1. `entity`（实体页）

路径：`wiki/entities/<slug>.md`

```yaml
---
title: "Llama 3"
description: "Meta 于 2024-04 发布的大语言模型系列。"
type: entity
tags: [model, llama, meta]
created: 2026-06-24
updated: 2026-06-24
aliases: [Llama-3, Llama 3.1, Meta-Llama-3]  # 字段值，不受 §8 kebab-case 文件名规则约束
---
```

正文结构：

```markdown
# Llama 3

## 简述

Meta 于 2024-04 发布的大语言模型系列（来源：[..](../sources/llama-3-release.md)）。

## 关键属性

- **发布方**：Meta
- **参数规模**：8B / 70B / 405B
- **context window**：128K（部分版本 200K）
- **许可证**：Llama 3 Community License

## 已知变体

- Llama 3.0（2024-04）
- Llama 3.1（2024-07，新增 405B）
- Llama 3.2（2024-09，多模态）

## 参考来源 / Sources

* [Llama 3 Release Notes](../sources/llama-3-release.md) — 原始发布
* [Llama 3.1 Technical Report](../sources/llama-3-1-tech-report.md) — 405B 详细规格
```

### 2. `concept`（概念页）

路径：`wiki/concepts/<slug>.md`

```yaml
---
title: "Self-Attention"
description: "让序列内每个位置直接 attend 所有其他位置的注意力机制。"
type: concept
tags: [attention, transformer, mechanism]
created: 2026-06-24
updated: 2026-06-24
related: [transformer.md, multi-head-attention.md, scaled-dot-product-attention.md]
---
```

正文结构：

```markdown
# Self-Attention

## 定义

Self-attention 是一种让序列内每个位置都直接 attend 到所有其他位置的机制
（来源：[..](../sources/attention-is-all-you-need.md)）。

## 数学形式

给定 query Q、key K、value V：

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

## 关键性质

- **计算复杂度**：O(n² · d)
- **并行化**：相比 RNN 无序列依赖
- **长程依赖**：任意两个位置直接相连

## 变体

- Multi-head attention（来源：[..](../sources/...md)）
- Sparse attention（来源：[..](../sources/...md)）

## 相关概念

- [Transformer](transformer.md)
- [Multi-Head Attention](multi-head-attention.md)

## 参考来源 / Sources

* [Attention Is All You Need](../sources/attention-is-all-you-need.md) — 原始论文
* [Flash Attention](../sources/flash-attention.md) — 高效实现
```

### 3. `source`（资料页）

路径：`wiki/sources/<slug>.md`

```yaml
---
title: "Attention Is All You Need"
description: "提出 Transformer——完全基于 attention、抛弃 RNN/CNN 的序列建模。"
type: source
tags: [transformer, paper-2017, nips]
created: 2026-06-24
updated: 2026-06-24
sources:
  - raw/articles/attention-is-all-you-need.md
authors: [Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin]
published: 2017-06-12
url: https://arxiv.org/abs/1706.03762
venue: NeurIPS 2017
---
```

正文结构：

```markdown
# Attention Is All You Need

**作者**：Vaswani et al. (2017)
**来源**：[raw/articles/attention-is-all-you-need.md](../raw/articles/attention-is-all-you-need.md)

## 摘要

提出 Transformer 架构——完全基于 attention mechanism，**抛弃 RNN / CNN**。
在机器翻译任务上达到 SOTA，且训练时间显著缩短。

## 关键贡献

1. **完全基于 attention 的序列建模**——首次在 encoder-decoder 框架中证明可行
2. **Multi-head attention**——并行学习不同子空间的 attention
3. **Positional encoding**——用 sin/cos 函数编码位置信息

## 关键数字

- WMT 2014 EN-DE：28.4 BLEU（来源：raw）
- 训练时间：12 小时 8 P100 GPU

## 与本 wiki 其它资料的关系

- 启发了 [BERT](../sources/bert.md)、[GPT](../sources/gpt-2.md) 等后续工作
- 核心概念见 [Self-Attention](../concepts/self-attention.md)、
  [Transformer](../concepts/transformer.md)

## 引文（可独立成段）

> "We propose a new simple network architecture, the Transformer, based solely on
> attention mechanisms, dispensing with recurrence and convolutions entirely."
> —— 原文 Abstract
```

### 4. `comparison`（对比页）

路径：`wiki/comparisons/<slug>.md`

```yaml
---
title: "Transformer vs Mamba"
description: "Self-attention 与 state space model 两条长上下文路线的对比。"
type: comparison
tags: [comparison, transformer, mamba, long-context]
created: 2026-06-24
updated: 2026-06-24
compared: [../concepts/transformer.md, ../concepts/mamba.md]
---
```

正文结构：

```markdown
# Transformer vs Mamba

## 对比对象

- [Transformer](../concepts/transformer.md) — Self-attention 路线
- [Mamba](../concepts/mamba.md) — State space model 路线

## 维度对比

| 维度 | Transformer | Mamba |
| --- | --- | --- |
| 核心机制 | Self-attention | Selective state space |
| 推理复杂度 | O(n²) | O(n) |
| 长上下文性能 | 平方下降 | 线性 (来源: [...](../sources/mamba-eval.md)) |
| 训练稳定性 | 成熟，attention 收敛稳定 | 较新，需要 careful init |
| 生态成熟度 | 极高 (BERT/GPT/LLaMA) | 新兴，2024 起热度上升 |
| 推理吞吐 | 优化路径多 (FlashAttn, KV cache) | 早期，工程化不足 |

## 适用场景

- **短上下文（< 4K）+ 任务多样** → Transformer
- **长上下文（> 32K）+ 任务相对单一** → Mamba
- **混合架构（hybrid）** → Jamba / Zamba 等正在探索

## 参考来源 / Sources

* [Attention Is All You Need](../sources/attention-is-all-you-need.md)
* [Mamba: Linear-Time Sequence Modeling](../sources/mamba.md)
* [Mamba 评估报告](../sources/mamba-eval.md)
```

### 5. `synthesis`（综合页）

路径：`wiki/syntheses/<slug>.md`

```yaml
---
title: "Long-Context 方法演进"
description: "围绕长上下文建模的 sparse attention 与 linear/SSM 两条路线的演进综合。"
type: synthesis
tags: [long-context, evolution, attention, ssm]
created: 2026-06-24
updated: 2026-06-24
threads: [sparse-attention, linear-attention, state-space-model, hybrid-architectures]
sources:
  - ../sources/attention-is-all-you-need.md
  - ../sources/sparse-transformer.md
  - ../sources/linear-attention.md
  - ../sources/mamba.md
---
```

正文结构：

```markdown
# Long-Context 方法演进

## 主线

围绕"如何让序列模型处理长上下文（> 8K tokens）"形成了两条主要技术路线。

## 线索一：sparse attention

保持 attention 形式但**减少 attend 数量**：

- 2019 — [Sparse Transformer](../sources/sparse-transformer.md) — 固定 stride pattern
- 2020 — [Longformer](../sources/longformer.md) — 局部 + 全局 attention 组合
- 2020 — [BigBird](../sources/bigbird.md) — 随机 + window + global

复杂度 O(n√n) 或 O(n log n)，相比标准 attention 显著降低。

## 线索二：linear attention / SSM

**替换** attention 为线性复杂度的机制：

- 2020 — [Linear Attention](../sources/linear-attention.md) — 重新设计 kernel
- 2023 — [RetNet](../sources/retnet.md) — 保留 + 门控
- 2023 — [Mamba](../sources/mamba.md) — Selective state space model

复杂度 O(n)，在长序列上推理优势显著。

## 交叉与综合

- 2024 — [Jamba](../sources/jamba.md) — Mamba + Attention 混合（SSM 层 + 偶数层 attention）
- 2024 — [Zamba](../sources/zamba.md) — 类似的混合思路

## 观察

1. **稀疏化** 与 **线性化** 是两条平行路径，长期共存
2. **混合架构**（hybrid）正在成为新趋势——纯 attention 或纯 SSM 都有边界
3. **工程化挑战**：Mamba 等新机制的 kernel 优化仍不成熟，吞吐暂时不如成熟 attention

## 待研究

- 长上下文评测 benchmark 的可靠性（needle-in-haystack 等）
- 长上下文中"有效记忆"vs"理论上能 attend"的差距
- 训练数据配比对长上下文能力的影响

## 参考来源 / Sources

* 列在 frontmatter `sources` 字段
```

> **逐段溯源（synthesis 专属）**：synthesis 页通常综合 ≥ 3 个 source，主张散落在不同段落、
> 各自从不同来源得出。仅靠 frontmatter `sources` 只能定位"本页引用了哪些来源"，**无法**
> 追溯"某句具体主张来自哪篇"。因此 synthesis 正文对**来源可分的断言**用标准 Markdown 脚注
> `[^n]` 标注，文末给出 `[^n]: ...` 指向 source 页——让每个可被引用的论点都能不重读 raw 就回溯：
>
> ```markdown
> Linear attention 把复杂度降到 O(n) [^linear]，但长序列精度普遍不及 sparse attention [^sparse]。
>
> [^linear]: [Linear Attention](../sources/linear-attention.md) — kernel 重设计
> [^sparse]: [Sparse Transformer](../sources/sparse-transformer.md) — 固定 stride pattern
> ```
>
> 用标准脚注 `[^n]`（**不要**用 pandoc 的行内 `^[...]`，与本 skill "通用 Markdown" 立场一致，
> 且不依赖 Obsidian / 特定渲染器）。单段纯推论 / 综合判断无需脚注；只对**可追溯到具体来源**
> 的断言标。comparison 页若同样综合多源、断言来源可分，也照此办理。

### 6. `index`（index.md）

路径：`wiki/index.md`（**唯一一份**，不允许新建）

```yaml
---
title: "<Topic> Index"
type: index
okf_version: "0.1"
tags: [index]
created: 2026-06-24
updated: 2026-06-24
---
```

正文结构：

```markdown
# <Topic> Wiki

> 本 wiki 由 LLM 维护，用户只读 + 提供 raw 资料 + 提问题。
> Schema 见 [`../AGENTS.md`](../AGENTS.md)。

## Entities

- [Llama 3](entities/llama-3.md) — Meta 发布的大语言模型系列
- [GPT-4](entities/gpt-4.md) — OpenAI 的大语言模型

## Concepts

- [Self-Attention](concepts/self-attention.md) — 让序列内每个位置 attend 所有位置的机制
- [State Space Model](concepts/ssm.md) — 线性复杂度的序列建模

## Sources

- [Attention Is All You Need](sources/attention-is-all-you-need.md) — Transformer 原始论文
- [Mamba](sources/mamba.md) — SSM 路线的代表工作

## Comparisons

- [Transformer vs Mamba](comparisons/transformer-vs-mamba.md) — 两条技术路线对比

## Syntheses

- [Long-Context 演进](syntheses/long-context-evolution.md) — 跨多篇资料的综合分析
```

**lint 检查**：

- 每个非 log / index 的 wiki 页**必须**在对应类别里出现
- 类别标题固定（Entities / Concepts / Sources / Comparisons / Syntheses）
- 条目格式：`* [<title>](<relative-path>) — <一句话摘要>`；**摘要应取自被链接页 frontmatter 的
  `description`**，不要在 index 里手写第二份（避免漂移）

### 7. `log.md`（log）

路径：`wiki/log.md`（**唯一一份**）

```yaml
---
title: "<Topic> Log"
type: log
tags: [log]
created: 2026-06-24
updated: 2026-06-24
---
```

正文：

```markdown
## [2026-06-24] setup | Initial scaffold by llm-wiki-management
## [2026-06-24] ingest | Attention Is All You Need
## [2026-06-24] ingest | Flash Attention
## [2026-06-24] query | Transformer vs Mamba
## [2026-06-24] lint | First health check
```

**lint 检查**：

- 每行匹配 `^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|setup) \| .+$`
- 不允许删除 / 修改历史条目

## 三、模板使用规则

1. **首次创建**——用对应模板填充 frontmatter
2. **修改时**——保留 frontmatter 全部字段；`updated` 改当天日期
3. **重写时**——若 `type` / `sources` 等关键字段需要变，**先和用户确认**
4. **归档 query 答案**——根据答案性质选 `comparison`（对比）或 `synthesis`（综合）

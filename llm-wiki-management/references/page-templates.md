# 页面模板

按 `type` 分 5 种。**所有页面**共有 frontmatter 段（见下）+ 类型特定字段 + 自由正文。

## 一、共有 frontmatter 段

```yaml
---
title: <string, 必填>
description: <一句话摘要, 推荐>
type: <entity|concept|source|comparison|synthesis, 必填>
tags: [<string array>, 必填但可空数组]
created: <YYYY-MM-DD, 必填>
updated: <YYYY-MM-DD, 必填>
---
```

**字段说明**：

- `title`——人类可读标题，不要带文件扩展名
- `description`——**推荐**（OKF v0.1 推荐字段）。一句话总结本页；`index.md` 条目摘要从它来，
  避免在 index 里手写第二份、与正文漂移（lint 抓不到这种不一致）
- `type`——驱动 lint 校验 + index 分组；合法值仅上述 5 种（`lint_wiki.py` 强制）。`index.md` /
  `log.md` 是 **reserved 文件**（结构见 §6 / §7），自带 frontmatter，其中 `type: index` /
  `type: log` 仅作标记、lint 跳过它们——不算概念页 type
- `tags`——用于跨页搜索 + 未来可能的 dataview 查询
- `created` / `updated`——**严格** `YYYY-MM-DD` 格式（lint 解析用）
- 类型特定字段（`sources` / `compared` / `threads`）见各模板

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
aliases: [Llama-3, Llama 3.1, Meta-Llama-3]
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
related: [transformer, multi-head-attention, scaled-dot-product-attention]
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
**来源**：[raw/articles/attention-is-all-you-need.md](../../raw/articles/attention-is-all-you-need.md)

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
> Schema 见 [`../CLAUDE.md`](../CLAUDE.md)。

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

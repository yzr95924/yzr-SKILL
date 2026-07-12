---
name: paper-wiki-integration-design
description: paper-wiki 整合：yzr-llm-wiki-management 只管本地复利、远端发布独立成 skill；耦合方向 = consumer → producer；producer 不假设 consumer；raw/papers 全量抽取当只读底座。
metadata:
  type: project
---

# paper-wiki 与 yzr-llm-wiki-management 的整合设计（2026-06-29 重写）

> MEMORY 索引：见 [`MEMORY.md`](./MEMORY.md)。本文记录 2026-06-29「yzr-llm-wiki-management 管理
> paper-wiki + 参考 gemini-paper-summary」分析会话沉淀的设计决策。decoupling refactor 后
> 已按新单向口径重写——producer（gemini-paper-summary）不假设有 consumer，consumer
> （yzr-llm-wiki-management）在自己的 SKILL.md / paper-wiki-profile.md §7 拥有完整集成契约。
> 核心立场保持不变；耦合方向归零。

## 核心边界（已拍板，firm）

**yzr-llm-wiki-management 只负责本地，不负责推远端。** 远端发布（outline）后面用**独立 skill**。

**Why：**

- yzr-llm-wiki-management 的 description 白纸黑字写着"**不用于**云端协作 wiki…走
  yzr-outline-wiki-upload / yzr-outline-wiki-search"。把发布塞进它 = 违反它自己的触发声明（description 是触发判定唯一信号），
  糊掉"本地复利"身份。
- 发布是跨 skill 的编排胶水（读本地页 + 驱动 outline MCP + 跟 outline_id + 图上传），不是任一现有
  skill 的本职；图的 attachment 3 步上传正是"跨用例重复 → 该捆绑"的信号。
- 通用：读书 wiki / 项目 wiki 哪天想推 outline 逻辑一样，不该埋进 paper-wiki profile。

## paper-wiki 整合架构（已落地，2026-06-29 decoupling refactor）

三 skill 流水线（**耦合方向 = consumer → producer**）：

```text
yzr-llm-wiki-management
   ├── 调 gemini-paper-summary --full → 产 raw/papers/<slug>.{quick,full}.md + raw/assets/<slug>/
   │       （producer 不假设有 yzr-llm-wiki-management；layout 沿用 Karpathy LLM Wiki 约定）
   ├── ingest_diff.py → 写 wiki/sources/<slug>.md（distill_state: draft）
   ├── 后续多轮对话 → refine op（Edit 追加 / 修订）→ distill_state: refining
   └──（未来 publish skill）→ outline-wiki
```

**为什么 consumer → producer 方向**：每个 skill 的 description 是其触发判定唯一信号；
让 producer 在自己的 description / SKILL.md 里点名 consumer 会污染 producer 的触发语义，
且违反"skill 可独立安装"原则。consumer 在自家 profile §7 写"如何调用 producer +
产物长什么样"即可。

**三层信息（一篇论文）：**

| 层 | 位置 | 性质 |
| --- | --- | --- |
| PDF 原文 | wiki 外 / 仅 URL | 终极真相 |
| 全量抽取 | `raw/papers/<slug>.full.md` + `raw/assets/<slug>/*.png` | producer 读懂后的**完整结构化转储（不压缩）**，只读底座 |
| 蒸馏总结 | `wiki/sources/<slug>.md` | 多轮对话**沉淀出**的总结，靠对话成熟 |

**关键判断：raw 放"全量抽取"，不放 PDF、也不放压缩 summary。** 全量抽取 = 贵的多模态读只付一次，
之后所有提问都在廉价文本层反复榨取——这是 Karpathy"复利"在**单篇论文内部**的重演。

**两阶段：**

1. **处理 PDF**（一次性 / 贵 / 多模态）：producer 同时产 quick summary（现有能力）+ 全量抽取（新）。
   quick summary → (a) outline 早期发布拿 outline_id，(b) `wiki/sources/` 初稿。全量抽取 → `raw/`。
2. **多轮蒸馏**（廉价 / 纯文本 / 反复）：在 `.full.md` 上反复 query，好答案 Edit 进 source 页
   （bump updated）。用户判定"彻底 ready"后，回写 outline（同一 outline_id，update）。

## 各 skill 的职责（按新单向口径）

- **gemini-paper-summary**（独立 skill，本 profile **不**直接编写其代码）：
  - 提供 `--full` 模式产出全量抽取（沿用 Karpathy LLM Wiki raw 端约定）
  - 提供单次 quick summary 模式（默认 / single summary）
  - **不**假设有 yzr-llm-wiki-management；consumer 在 profile §7 描述如何调用
- **yzr-llm-wiki-management**（本 skill）：
  - 维护 `references/paper-wiki-profile.md` §7 权威集成契约（含 7.1 raw 端契约 /
    7.2 推荐实现 / 7.3 职责切分 / 7.4 失败兜底）
  - ingest_diff.py 收窄 ingest 单元到 `*.md` 或排除 `raw/assets/`，否则 figure png 全报 untracked
    （`collect_raw_files` 用 `rglob("*")` 收所有文件）
  - 新增 `refine` log op（在 profile §5 + page-templates.md §7 + log_format.py 三处同步）
  - **不**碰远端
- **publish skill（未来）**：编排本地→outline，跟踪 `outline_id`（source 页 frontmatter opaque
  字段），拥有图上传。**别现在建**——先让发布流程以散文活在 paper-wiki profile 里跑稳几篇，看到
  重复再抽 skill。

## 已决（2026-06-29 refactor 后落地）

- gemini 的 full 与 quick 产出关系：单次多模态调用出两份（保视觉接地、不重读 PDF）——见
  [`gemini-paper-summary-full-mode-design.md`](./gemini-paper-summary-full-mode-design.md) §D1。
- publish skill 何时从 profile 手工流程抽出来（看重复度）——未决。
- source 页发布态 frontmatter 字段（`outline_id` + 可选 `distill_state: draft|refining|final`）——
  由 publish skill 拥有，yzr-llm-wiki-management 不解释。

## 关联

- [[skill-source-vs-runtime-vendor]]——后续真改 skill 时改源别改 vendor
- [[memory-synced-to-skill-source]]——这些设计落地时必须写进 SKILL 源，不只留 MEMORY（npx 分发不带 MEMORY）
- [[gemini-paper-summary-full-mode-design]] — producer 侧 SSOT；本文 consumer 侧 SSOT 的对端
- [`../yzr-llm-wiki-management/references/paper-wiki-profile.md` §7](../yzr-llm-wiki-management/references/paper-wiki-profile.md#7-与上游抽-pdf-工具的边界与集成gemini-paper-summary-是推荐实现) — 集成契约 SSOT（consumer 拥有）
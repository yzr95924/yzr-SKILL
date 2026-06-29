# paper-wiki 与 llm-wiki-management 的整合设计（未落地）

> MEMORY 索引：见 [`MEMORY.md`](./MEMORY.md)。本文记录 2026-06-29「llm-wiki-management 管理
> paper-wiki + 参考 gemini-paper-summary」分析会话沉淀的设计决策。**尚未落地成代码 / 文档**——
> 后续真要动手时先读这里，避免从头推导。

## 核心边界（已拍板，firm）

**llm-wiki-management 只负责本地，不负责推远端。** 远端发布（outline）后面用**独立 skill**。

**Why：**

- llm-wiki-management 的 description 白纸黑字写着"**不用于**云端协作 wiki…走
  outline-wiki-management"。把发布塞进它 = 违反它自己的触发声明（description 是触发判定唯一信号），
  糊掉"本地复利"身份。
- 发布是跨 skill 的编排胶水（读本地页 + 驱动 outline MCP + 跟 outline_id + 图上传），不是任一现有
  skill 的本职；图的 attachment 3 步上传正是"跨用例重复 → 该捆绑"的信号。
- 通用：读书 wiki / 项目 wiki 哪天想推 outline 逻辑一样，不该埋进 paper-wiki profile。

## paper-wiki 整合架构（plan，方向已定、细节待建）

三 skill 流水线：`gemini-paper-summary 产出 → llm-wiki-management 本地精炼 →（未来 publish skill）→ outline`

**三层信息（一篇论文）：**

| 层 | 位置 | 性质 |
| --- | --- | --- |
| PDF 原文 | wiki 外 / 仅 URL | 终极真相 |
| 全量抽取 | `raw/papers/<slug>.full.md` + `raw/assets/<slug>/*.png` | gemini 读懂后的**完整结构化转储（不压缩）**，只读底座 |
| 蒸馏总结 | `wiki/sources/<slug>.md` | 多轮对话**沉淀出**的总结，靠对话成熟 |

**关键判断：raw 放"全量抽取"，不放 PDF、也不放压缩 summary。** 全量抽取 = 贵的多模态读只付一次，
之后所有提问都在廉价文本层反复榨取——这是 Karpathy"复利"在**单篇论文内部**的重演。

**两阶段：**

1. **处理 PDF**（一次性 / 贵 / 多模态）：gemini 同时产 quick summary（现有能力）+ 全量抽取（新）。
   quick summary → (a) outline 早期发布拿 outline_id，(b) `wiki/sources/` 初稿。全量抽取 → `raw/`。
2. **多轮蒸馏**（廉价 / 纯文本 / 反复）：在 `.full.md` 上反复 query，好答案 Edit 进 source 页
   （bump updated）。用户判定"彻底 ready"后，回写 outline（同一 outline_id，update）。

## 各 skill 待做的工作

- **gemini-paper-summary**：扩 `--full` 模式（复用其图片抽取机制 / Stage 2 bbox，**去**字数压缩）；
  现有 summary 模式保留给"速读"。它当前是反全量的（prompt-template 写死 ≤2500 字、精炼优先），
  所以全量是**新能力**。
- **llm-wiki-management**：新增 `references/paper-wiki-profile.md`（raw=全量抽取、source=蒸馏成熟、
  extract→interrogate→distill、log `refine` op）；小改 `ingest_diff.py`——收窄 ingest 单元到
  `*.md` 或排除 `raw/assets/`，否则 figure png 全报 untracked（`collect_raw_files` 用 `rglob("*")`
  收所有文件）。**不**碰远端。
- **publish skill（未来）**：编排本地→outline，跟踪 `outline_id`（source 页 frontmatter opaque
  字段），拥有图上传。**别现在建**——先让发布流程以散文活在 paper-wiki profile 里跑稳几篇，看到
  重复再抽 skill。

## 未决

- gemini 的 full 与 quick 产出关系：一次多模态调用出两份（保视觉接地、不重读 PDF，**倾向**）vs
  full 为主、quick 从 full 派生（天然一致，但丢视觉接地 + 要重构 PDF→summary 直连）。
- publish skill 何时从 profile 手工流程抽出来（看重复度）。
- source 页发布态 frontmatter 字段（`outline_id` + 可选 `distill_state: draft|refining|final`）——
  由 publish skill 拥有，llm-wiki-management 不解释。

## 关联

- [[skill-source-vs-runtime-vendor]]——后续真改 skill 时改源别改 vendor
- [[memory-synced-to-skill-source]]——这些设计落地时必须写进 SKILL 源，不只留 MEMORY（npx 分发不带 MEMORY）

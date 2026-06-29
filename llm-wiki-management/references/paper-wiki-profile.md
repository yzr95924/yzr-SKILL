# Paper-Wiki Profile（论文域的本地工作流变体）

> 本文档是 `llm-wiki-management` 在"论文（paper）"主题域下的**本地工作流**约定——
> 在通用 wiki 规则上的领域变体，**不**修改 `wiki-spec.md` / `page-templates.md` 等
> SSOT，而是把它们与论文域的特殊性拼起来。
>
> **本 profile 永远不推远端**。论文发布到云端 / Outline 走**未来独立的 publish skill**；
> 跨 skill 编排（本地 → outline）属于那边的职责，本 skill 与本 profile 都**不**实现。

## 1. 适用 / 不适用

**适用：**

- 你想沉淀一批论文到本地复利型知识库——论文内容随对话成熟，跨论文概念自然交叉
- 你已经（或愿意）用 `gemini-paper-summary` 把 PDF 抽成结构化文本
- 你希望"贵的一次性多模态读"只付一次，之后所有提问都走廉价文本层

**不适用：**

- 单次临时性读论文——用 `gemini-paper-summary` 出 quick summary 即可，**不必**入 wiki
- 直接把 PDF 原文 / 整本扫描书当 raw——raw 应当是**已结构化的文本**（gemini 抽取后），
  不是二进制 PDF；PDF 仅作"外部真相"被引用
- 把 wiki 内容推云端分享——那是未来 publish skill 的事（与本 skill 解耦）

## 2. 三层信息（每篇论文）

| 层 | 位置 | 性质 | 谁写 |
| --- | --- | --- | --- |
| **PDF 原文** | wiki 外 / 仅 URL 或本地引用 | 终极真相 | 用户 |
| **全量抽取（raw）** | `raw/papers/<slug>.full.md` + `raw/assets/<slug>/*.png` | gemini 多模态读懂后<br>**完整结构化转储（不压缩）** | gemini-paper-summary（user-driven） |
| **蒸馏总结（wiki）** | `wiki/sources/<slug>.md` | 跨多轮对话沉淀出的**成熟**总结；首页时是 quick summary 占位 | LLM（agent 写） |

**关键判断：raw 放"全量抽取"，不放 PDF、也不放压缩 summary。** 全量抽取 = 贵
的多模态读只付一次，之后所有提问都在廉价文本层反复榨取——这是 Karpathy
"复利"在**单篇论文内部**的重演。

> raw/ 的 LLM 只读纪律**保持不变**（见 `wiki-spec.md` §一 + `claude-md-template.md` §一）。
> 本 profile 不破坏这条——gemini 输出的全量抽取仍由 LLM 视为只读底座。

## 3. 命名约定

| 文件 / 目录 | 命名规则 | 例子 |
| --- | --- | --- |
| `raw/papers/<slug>.full.md` | kebab-case `<slug>.full.md` | `attention-is-all-you-need.full.md` |
| `raw/assets/<slug>/` | 抽出的图，PNG 原样存，编号 `-01` `-02` ... | `raw/assets/attention-is-all-you-need/fig-01.png` |
| `raw/articles/<slug>.md` | 同一论文若有 markdown 摘录版，存这里<br>（与 .full.md 共存，sources 字段可同时引用） | `raw/articles/attention-is-all-you-need.md` |
| `wiki/sources/<slug>.md` | 蒸馏总结；slug 与 raw 同名 | `wiki/sources/attention-is-all-you-need.md` |
| `wiki/concepts/<concept>.md` | 跨论文概念，**不**带论文后缀 | `wiki/concepts/self-attention.md` |

`slug` 一旦确定就是永久 ID（与 wiki 通则一致）——重命名走 `git rename`（启用 git
时保留 history）或普通 `mv`（裸目录树）+ 全量更新所有引用，包括 raw / wiki / log。

## 4. 两阶段工作流

### 阶段 1：处理 PDF（一次性 / 贵 / 多模态）

**触发：** 用户拿一篇新 PDF。

**流程：**

1. 调 `gemini-paper-summary` 一次性产出**两份**产物：
   - **quick summary**（其现有能力，精炼 ≤2500 字）—— 用作：
     - (a) `wiki/sources/<slug>.md` 的**初稿**（source 页是"占位 + 后续 refine"，首版就是 quick summary）
     - (b) 早期远端发布的输入（**此动作属未来 publish skill，本 skill 不做**）
   - **全量抽取**（`raw/papers/<slug>.full.md` + `raw/assets/<slug>/*.png`）—— 落 raw/，LLM 视为只读底座
2. 本 skill 的 **ingest 操作**：在 `wiki/sources/<slug>.md` 写**初版**（frontmatter `sources` 指向
   `raw/papers/<slug>.full.md` + `raw/articles/<slug>.md` 如有 + raw 内的图）；
   同步相关 `concepts/` 页（若新概念则新建，若已存在则追加"参考来源"段，**不重写**）；
   追加 `log.md` `ingest` 条目
3. 同步 `wiki/index.md`（sources 段 + concepts 段）

> **当前限制**：gemini-paper-summary 是否原生支持"一次调用出两份"取决于它的实现——
> 若它只产 quick summary，全量抽取要用户**额外调一次**它（或其 `--full` 模式，**如该
> skill 后续支持**）。本 profile 不绑死具体实现，只规定"必须有 raw 层的全量抽取"。

### 阶段 2：多轮蒸馏（廉价 / 纯文本 / 反复）

**触发：** 用户在对话中对某篇论文提新问题（基于其 .full.md）。

**流程：**

1. LLM **不**重新读 PDF、**不**重新跑多模态——只读 `raw/papers/<slug>.full.md`（文本层）
2. 回答用户问题，引用形式带 `.full.md` 内的章节
3. **若答案对 source 页有补全价值**（新事实 / 新角度 / 修正旧描述）—— 询问用户
   "是否把这段写进 `wiki/sources/<slug>.md`？" 用户同意后用 **Edit** 更新 source 页：
   - 在合适小节追加 / 修订
   - 必更 `frontmatter.updated`
   - 追加 `log.md` `refine` 条目（**新增 op**，见 §5）
   - 若新增 / 改动了概念，**同步** `concepts/` 页 + `index.md`
4. 用户判定"彻底 ready"后，**回写** quick summary（若是首次发布则新 publish，若是更新则 update）——
   **此动作属未来 publish skill，本 skill 不做**。本 profile 不解释 `outline_id` 等远端字段。

**关键纪律：**

- **不 Write 覆盖**——refine 阶段永远用 Edit，保留前序对话沉淀
- **不**把每轮问答都塞进 source 页——只有"对源页有补全价值的"才写
- **不**丢失 frontmatter——重写时必须保留 `title` / `type` / `sources` / `created`（只 bump `updated`）
- **跨论文的概念**必须走 `concepts/`，**不**在 source 页里散开定义

## 5. log op 扩展（`refine`）

当前 log op 集合（见 `wiki-spec.md` §4）：`ingest` / `query` / `lint` / `setup`。

**paper-wiki 域扩展新增：`refine`** —— 表示在已存在的 source / concept / synthesis
页上做 Edit 追加 / 修订，**不**等同于 ingest（ingest 是首次摄取）。`log_format.py`
与 `page-templates.md` §7 的权威正则**未**覆盖本 op；扩展时同步改两处：

| 位置 | 改动 |
| --- | --- |
| `references/page-templates.md` §7 权威正则 | 允许 `refine` 出现在 op 集合 |
| `scripts/log_format.py` `LOG_INGEST_RE` 风格正则 | 单独定义 `LOG_REFINE_RE`（与 ingest 并列） |
| `scripts/lint_wiki.py` 格式校验 | 用同一份正则 |

> **实施时机**：在 profile 第一次真实 refine 之后**再**改 SSOT——避免"为虚构需求改通用规则"。

格式样例：

```text
## [2026-07-15] refine | Attention Is All You Need: 补全 decoder-only 实验对照
## [2026-07-18] refine | self-attention: 加上 Mamba 章节的交叉引用
```

## 6. source 页的 frontmatter 增项（建议）

在 `references/page-templates.md` §二 source 页 5 必填 + 推荐项**之外**，本 profile
建议在 paper 域 source 页上额外写：

| 字段 | 类型 | 含义 | 何时写 |
| --- | --- | --- | --- |
| `distill_state` | enum `draft` / `refining` / `final` | 蒸馏成熟度 | 阶段 1 写 `draft`；每次 refine 后 bump 到 `refining`<br>用户明确"彻底 ready"后 bump 到 `final` |
| `paper_slug` | string | raw 路径的稳定 ID；与 `<slug>.full.md` 对齐 | 首次 ingest 写定后不改 |

> **本 profile 不解释** `outline_id` / `outline_url` 等远端字段——**那是未来 publish
> skill 的 frontmatter 增项**，本 skill 与本 profile 都**不**关心。publish skill 可以
> 在 source 页的 frontmatter 上加自己的字段，本 profile 不阻挡也不解析。

## 7. 与 gemini-paper-summary 的边界

| 职责 | 谁做 | 备注 |
| --- | --- | --- |
| 读 PDF + 抽图 | `gemini-paper-summary` | 多模态；调用 Gemini API |
| 出 quick summary | `gemini-paper-summary` | 精炼压缩；可走"早期远端发布"路径 |
| 出全量抽取 | `gemini-paper-summary`（若支持 `--full`，或独立脚本） | 现阶段 gemini-paper-summary **不**原生支持全量抽取——这属于**待补能力** |
| 归档到 `raw/` 与 `wiki/sources/` | `llm-wiki-management` ingest | **本 profile** |
| 跨多轮对话蒸馏 | `llm-wiki-management` refine | **本 profile**（新增 op） |
| 推送到 outline-wiki | **未来 publish skill** | **本 skill 与本 profile 都不做** |

> gemini-paper-summary 的具体 prompt / 输出模板**不在本 profile 引用**——
> 它是独立 skill（`gemini-paper-summary/SKILL.md` 自身权威），不在 npx 分发包内
> 重复维护。**本 profile 只规定 wiki 端的契约**：raw 文件长什么样、source 页
> 怎么写、log 怎么记。

## 8. 反模式（paper 域特别禁忌）

- **不要**把 PDF 原文直接放进 `raw/`——raw 是文本结构化底座；二进制 PDF 留在 wiki
  外（路径 / URL 引用）
- **不要**在 `wiki/sources/<slug>.md` 里只贴 quick summary 然后**永远不 refine**——
  source 页的设计意图是"随对话成熟"，停留在 draft 等于浪费
- **不要**在 refine 阶段重新读 PDF / 重新跑多模态——贵、慢、且答案不会有变化；
  一律读 `raw/papers/<slug>.full.md`
- **不要**让"加几个图"绕过 publish skill 直接写到 wiki——图本来就在 `raw/assets/<slug>/`
  里被 source 页相对引用，**不**需要 publish 介入
- **不要**为虚构需求改 wiki-spec.md / page-templates.md / log_format.py
  等 SSOT——refine op 这类扩展等真实发生再改；过早抽象 = 跟实际漂移
- **不要**在 paper-wiki profile 里塞云端 / outline / publish 相关字段——

  本 profile 的存在目的是把"本地论文复利"讲清楚；远端胶水属于未来 publish skill。

## 9. 关联

- [`wiki-spec.md`](wiki-spec.md) — 通用 wiki 仓契约（SSOT，本 profile 在其之上变体）
- [`page-templates.md`](page-templates.md) — frontmatter 与 page 模板权威定义
- [`claude-md-template.md`](claude-md-template.md) — wiki 宪法（`raw/` LLM 只读等纪律的本源）
- [`../SKILL.md`](../SKILL.md) — skill 主入口；本 profile 由其"与其他 skill 的边界"段引用
- `../gemini-paper-summary/SKILL.md` — 上游抽 PDF 工具（**独立 skill**，本 profile 不复刻其内容）

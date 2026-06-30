# gemini-paper-summary --full 模式设计说明（新口径，2026-06-29 重写）

> MEMORY 索引:见 [`MEMORY.md`](./MEMORY.md)。本文是 producer 侧的设计 SSOT——
> 解释 `--full` 模式的技术决策（D1-D4）以及为什么采用 Karpathy LLM Wiki raw
> 端约定。**producer 不假设有具体消费 skill**；消费方的集成契约见
> [`llm-wiki-management/references/paper-wiki-profile.md`](../llm-wiki-management/references/paper-wiki-profile.md) §7。
>
> **重写背景**：2026-06-29 decoupling refactor 之前，本文 §2 / §3 / §4 / §7 多处
> 把 `llm-wiki-management` 当作 `--full` 模式的设计驱动；重构后改为"基于可识别的
> Karpathy 模式惯例"——producer 描述 layout，消费方在自己的 SKILL.md 里点名
> producer。这是单向依赖的标准做法。

## 0. 一句话

`--full` = "一份 PDF → 两份产物":`(a) quick summary ≤2500 字符`(existing 默认模板,
含 `![图 N]` 引用 + 落 PNG,服务于人类用户快速浏览 + 未来 publish 消费)
`(b) PDF→Markdown 全量转写 = 严格按 PDF 原文章节顺序 + 元信息 + 保真所有
Definition/Theorem/Algorithm/公式/表格/数字精度 + 图转 mermaid/ASCII**(2026-06-30
第二轮翻面)**——产物落 `raw/papers/{slug}.full.md` 自包含,**full 不再写
`raw/assets/{slug}/fig-NN.png`**,该目录仅由 quick 模式或 `--extract-figures`
单跑产生。quick 与 full 在产品定位上彻底分家。

## 1. 完整 4 个设计决策

| # | 决策 | 选择 | 替代方案(为什么不要) |
| --- | --- | --- | --- |
| D1 | 与 default 关系 | 单次调用**两份产物**(quick summary + full) | (a) 只产 full: 消费端必须调两次凑齐两份（要么两次 prompt 不一致、要么两份独立提交流程）；(b) 互斥模板:`--template academic\|lite\|full` 三选一——与现有 `--focus` / `--template academic` flag 风格不统一，"一次成型"卖点丢失 |
| D2 | 产物 layout(2026-06-30 第二轮翻面) | **full 自包含 / quick + extract-figures 落 PNG**: `--output <root>` → `<root>/raw/papers/<slug>.full.md`(自包含,无 PNG) + `<root>/raw/papers/<slug>.quick.md`(含 `![图 N]` 引用 + 落 PNG) + `<root>/raw/assets/<slug>/fig-NN.png`(仅由 quick 模式或 `--extract-figures` 单跑产生,full 不写) | (a) full 也落 PNG:agent 多模态能力不可假设,PNG 对纯文本 agent 是死数据;(b) 加 `--layout raw\|standard`:多一个 flag + 两条路径,YAGNI |
| D3 | full 模式结构(2026-06-30 重新定位) | **PDF→Markdown 全量转写,严格按 PDF 原文章节顺序** —— 开篇 metadata table + 按 `Section 1` / `Section 2` / ... 顺序逐章展开,每个 `Section X.Y` / `Section X.Y.Z` 对应 `###` / `####`;**不做 6 类问题归纳**,**不写**三句话总结 / 业务启示 / 局限与未来工作(summary 视角)。沿用 academic 模板的保真规则:Definition/Theorem/Algorithm 标注、公式 `$$...$$`、表格行级转写、数字精度 3 位有效数字 | (a) 沿用 academic 6 H2 骨架:full 模板强制 summary 视角归纳,丢失 PDF 原生章节顺序,后续 agent Q&A "论文第 4.3 节讲什么" 答不出;(b) 单文件两份结构(上半 quick + 下半 full):文件长 3-5×、两套逻辑绑一个文件;后续要把 quick summary 与 full 解耦(未来 publish 类消费)代价大 |
| D4 | 是否带 Stage 2 视觉定位(2026-06-30 第二轮翻面) | **quick 模式必须带**;**full 模式不再跑**(2026-06-30 翻面后) | 原决策基于 raw 端 `fig-NN.png` 是下游反复引用的产物,需要精确 bbox;第二轮翻面后 full 不再落 PNG,Stage 2 在 full 模式无意义。quick 模式仍隐式开 Stage 2,`--refine-figures` 仅作用于 quick + `--extract-figures` |
| D5 | full 模式的图表示(2026-06-30 第二轮翻面) | **mermaid / ASCII / 表格转写**:架构/概念图直接 mermaid 画在 markdown 里(` ```mermaidjs ` block`),数据可视化图转 markdown 表格,装饰图省略 + 文字一句。Prompt 强约束;`_run_full_mode` 整段图提取分支删除 | (a) PNG 落盘 + Stage 2:agent 多模态不可假设,~50% agent 不能用 PNG;mermaid 100% agent 可读;(b) 链接到 base64 内嵌图:markdown 文件膨胀,信息密度低于 mermaid;(c) SVG inline:Markdown 渲染器兼容性参差不齐 |

## 2. 为什么 D1 选"两份都产"

**Why:** 单次 prompt 内并行两份产物符合 producer 的"一次成型"产品形态——
quick + full 共享同一份 PDF 多模态读，避免重复 token 开销；消费方拿到两份
**对齐**的产物（quick 与 full 在同一文件族里），不需要做额外的"两份对齐"
工作。把"出两份"拆成两次调用，等于把这个意图压成"分两次跑"——用户每次都
得自己协调两次的产物对齐，也把"raw 端就绪"的判断点推迟到第二次调用之后。

**How to apply:** 任何后续要把 --full 与 quick 拆分的诉求（性能 / 成本 / 重试）
应走**单次 prompt 内并行两份**，而非"分两次调用"——除非 Gemini API 计费模型
出现颠覆性变化。

## 3. 为什么 D2 选 Karpathy LLM Wiki raw 端约定

**Why:** `raw/papers/<slug>.full.md` + `raw/assets/<slug>/fig-NN.png` 是
[Karpathy LLM Wiki 设计哲学](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
的可识别模式——任何按 Karpathy 哲学实现本地复利型知识库的工具（不限于
llm-wiki-management）都会采用这个 layout。producer 描述这个 layout 时不
假设存在具体消费 skill；消费方在自己的 SKILL.md 里点名 producer 作为推荐
实现。

**不是 Karpathy 约定时会发生什么:** 走 `<dir>/summary.md + <dir>/papers/ + <dir>/assets/`
时，用户跑完命令还要手动 `(cd $root && mkdir -p raw && mv <dir>/papers raw/ && mv <dir>/assets raw/)`——
这一句 mv 是错的源头（忘记 `mkdir -p` / 覆盖已有 raw 目录 / 部分文件冲突）。

**How to apply:**
- `--output <path>` 在 `--full` 模式下语义是 **raw 根**（默认写到 `<root>/raw/`)
- 不开 `--full` 时,`--output` 仍是任意输出目录（向后兼容；`--extract-figures` 也走任意目录）
- 冲突检测:若 `<root>/raw/papers/<slug>.full.md` 已存在，**默认拒绝覆盖**（退出非零），
  需要 `--force-full` 显式覆盖；理由:full 抽取是"贵读一次"的产物，意外重写会丢消费方
  已经多次引用的 raw

## 4. 为什么 D3 选 PDF 原生章节顺序(2026-06-30 翻面)

**背景:** 旧 D3 选择"沿用 academic 的 6 H2 骨架"——理由是"quick summary 的
6 类问题骨架已经被仓库内多个 skill 共识接受,full 沿用让 quick→full 跨文件
跳读时能定位对应 H2"。

**翻面原因(2026-06-30):** full 模式的真实下游场景是**无 PDF 多轮问答底座**。
Agent 拿到 full.md 后,所有 Q&A 都从这里查——典型问题是"论文第 4.3 节具体
怎么实现 / Theorem 1 的证明思路 / 论文中最差空间消耗怎么证明 / Node48 索引
数组多大 / ART vs FAST 关键差异"。这类问题**按 PDF 章节定位**才能精确答出:

- 用户说"4.3 节"——agent 直接查 `## Section 4` 下的 `### Section 4.3`
- 用户说"Theorem 1"——agent 直接查 `**Theorem 1.**` 标注
- 用户说"实验用了哪些 baseline"——agent 直接查 `## Section 5` 的表格

如果 full.md 仍是 6 H2 归纳视角,以上问题都需要 agent 做一次"分类归纳 →
反推回 PDF 章节"的额外推理——信息丢失 + 推理成本翻倍,且容易答错(摘要归纳
会合并多节,反推不出"具体哪一节")。

**新口径:** full 模板的章节顺序必须严格对齐 PDF 原生章节,不做 6 类归纳;
summary 视角的"3 句话总结 / 业务启示 / 局限"是 noise(agent 不会问"作者对
未来工作有什么展望"这类 meta 问题,会直接问"论文自陈了什么局限 / Section 7
怎么写")。**删除这三个 summary 段**。

**quick.md 不受本翻面影响:** quick 仍是 academic 模板 + 三句话总结,
服务于"快速浏览 + 未来 publish skill 消费",6 H2 骨架是其合理设计。

**How to apply:**

- 修改 full 模板时,只动章节骨架的"顺序"和"段落名称",不破坏保真规则
- 不要把"开篇 metadata table"也删了——agent 仍需"作者是谁 / 什么会议"
  这类元信息查询
- 不要把"团队/机构"行也删了——同上
- 强保真清单(2026-06-30 更新):章节标题(英文原文) > Definition/Theorem/
  Lemma/Algorithm 标注 > 公式(`$$...$$`) > 表格(markdown 行级) > 数字
  精度(3 位有效数字) > 英文小节标题 > 图引用

## 5. 为什么 full 模式不落 PNG(2026-06-30 第二轮翻面)

**Why:** full 模式的真实下游场景是**无 PDF 多轮问答底座**——agent 拿到
full.md 后,所有 Q&A 都从这里查。Agent 的多模态能力**不可假设**:

- 部分 agent(纯文本 LLM、IDE 内嵌 agent、batch pipeline)完全没有 vision
  encoder——PNG 字节对它们而言是死数据,读不到图里内容
- 多数 agent 通过 inline image embedding 间接看图(markdown → HTML →
  image extraction → base64 → vision call),这条路径 token 成本高、延迟
  大、且**信息密度低于 mermaid/ASCII**(mermaid 是结构化重写,信息精确)

mermaid / ASCII / markdown 表格 是 100% agent 可消费的文本形式;PNG 仅
~50% agent 可消费。**mermaid 胜在通用性**。

**How to apply:**
- full 模式 prompt 强约束:Gemini 把架构/概念图转 ` ```mermaidjs ` block`
  画在 markdown 里,数据可视化图转 markdown 表格,装饰图省略 + 文字一句
- full 模式脚本侧 `_run_full_mode` 整段图提取分支删除(line 1629-1637 段),
  不调 Stage 2、不创建 `assets_dir`、不写 `![图 N]` 引用
- 想看 PNG 的用户:跑 quick 模式(默认,含 `![图 N]` + 落 PNG)或单独
  `--extract-figures`;full 是 agent 专用底座,**与人类看图解耦**
- 旧 D4 决策(2026-06-29 落地的"必须带 Stage 2")翻面为 quick-only 约束;
  full 模式不再继承

## 5.1 旧 D4 决策的考古(2026-06-29 → 2026-06-30 翻面)

旧决策"`--full` 隐含 `--refine-figures` 默认开"基于 raw 端 `fig-NN.png` 是
下游消费方反复引用的产物,需要精确 bbox。第二轮翻面后这个前提不再成立——
full.md 没有 PNG 产物,Stage 2 无意义。**quick 模式仍隐式开 Stage 2**,仅
full 关闭。

## 6. 公式 / 表格的转写约定（全量抽取才需关心）

quick summary 因为 ≤2500 字符，公式通常只写"参见公式 X"，full 模式要保真。具体约定
在 prompt 模板里写；这里先记"为什么":

- **公式**:PDF 渲染公式在 Gemini 多模态看图时是**看得见的**——prompt 要求逐公式保留，
  形式 = Unicode（`2^64` / `≥` / `√`）或 `$$...$$`（outline-wiki 不渲染 MathJax，
  详见 `MEMORY/prompt-length-unit-character.md` §一 + `prompt-template.md` 风格约定 #9）
- **表格**:论文实验结果 / hyperparameter 表是文本信息，**不**应仅留图引用；
  prompt 要求逐行转 markdown 表格，数字精度保留（`95.2 ± 0.3` 这种）

## 7. --full 模式的产出清单(2026-06-30 第二轮翻面)

用户跑 `gemini_paper_summary.py --pdf attn.pdf --output ~/root/ --full`，产物**全部**都在
`--output` 指定的 raw 根下：

```text
<root>/raw/
├── papers/
│   ├── <slug>.full.md       # full 抽取(自包含,无 PNG 配套;mermaid/ASCII 在 markdown 里)
│   └── <slug>.quick.md      # quick summary(含 ![图 N] 引用 + 落 PNG,精炼版,供后续可选 publish 流程消费)
└── assets/<slug>/           # 仅由 quick 模式或 --extract-figures 单跑产生,full 不创建
    ├── fig-01.png           # Stage 2 视觉裁剪(quick 模式产物)
    ├── fig-02.png
    └── ...
```

> **full 模式不创建 `assets/<slug>/` 目录**——full.md 自包含,无 PNG 配套。
> 任何"占位 source 页"或后续蒸馏由消费方 skill 处理。

**Quick summary 的产出位置:** `<root>/raw/papers/<slug>.quick.md`（与 .full.md 同目录，
加 `.quick` 后缀区分）；**不是** `wiki/sources/<slug>.md`——理由：避免
"raw 是只读的 / wiki 是可写的"两条 linter 规则 `claude-md-template.md` §一 出现
不必要的责任划分。

## 8. 已知边界 / 不在本次实施范围

- **不改 quick summary 模板**:原本 ≤2500 字符 academic 模板是稳定 SSOT，full 模式只是加新变体
- **不引入新 pip 依赖**:复用现有 `pymupdf` + `google-genai`
- **不重写 Stage 2**:Stage 2 视觉定位逻辑（`call_gemini_for_visual_bbox` 等）不动,
  `--full` 模式下不再调用(--full 不落 PNG),quick 模式仍默认开启
- **不重命名产物**:`<slug>.full.md` / `<slug>.quick.md` 后缀约定与 Karpathy LLM Wiki
  raw 端约定一致
- **不写 ingest 操作**:`--full` 跑完 = raw 端就绪；ingest 是消费方的职责
- **不做"已抽取则跳过"**:用户已经 `raw/papers/<slug>.full.md` 存在，跑 --full 时**默认拒绝覆盖**
  （退出 1，提示用 --force-full）；理由与 §3 一致
- **full 模板不含 summary 段落(2026-06-30)**:不再输出 "3 句话总结 / 业务启示 & 价值 /
  局限与未来工作"。若用户需求里有这些,跑 academic 模板(默认)即可。full 与 quick
  在产品定位上彻底分家——quick 仍走 6 H2 骨架服务于快速浏览 + 未来 publish,
  full 改为 PDF→Markdown 全量转写服务于无 PDF 多轮问答底座。
- **与未来 publish skill 的边界**:quick summary 留给 publish 类消费方使用；本 skill **不**做
  attachment 上传 / Outline API 调用——`SKILL.md` §A' 既有端到端示例依然有效，
  只是把"quick summary 直接走 outline"那段示例从本 skill 文档抽到 publish skill
- **full 模式不落 PNG / 不跑 Stage 2 / 不创建 assets/(2026-06-30 第二轮翻面)**:
  `--full` 是 agent Q&A 底座,产物自包含;架构/概念图直接 mermaid 画在
  markdown 里,数据图转表格。quick 模式 + `--extract-figures` 仍落 PNG。
- **旧 `naming_scheme="raw"` + fig-NN.png 契约(2026-06-30 第一轮加固)已
  翻面**:full 模式不再触发该路径;契约仍适用于 quick 模式 + `--extract-figures`
  单跑。MEMORY §7 + eval/evals.json test #1 同步更新

## 9. 实施优先级（后续 task 编排）

按 yzr-skill-creator 入口 2 改进循环:

1. **MEMORY 同步**（本文） ✅
2. **`prompt-template.md` 加 ## 全文级抽取模板 (full) 变体** ✅
3. **`gemini_paper_summary.py` argparse + 双产物分支 + raw 端约定 layout** ✅
4. **`SKILL.md` 加 `--full` 行为 + 产出契约** ✅
5. **vendor 同步**（派生操作） ✅ （本机无 vendor 安装, N/A）
6. **`evals/evals.json` 起草 3 个测试 prompt** + 跑 with-skill / baseline 迭代

## 10. 关联

- [[paper-wiki-integration-design]] — 本决策的上游（profile 的定位 → producer 落 raw 约定）
- [[gemini-paper-summary-figure-extraction-edges]] — Stage 2 视觉定位的为什么（D4 引用 §1）
- [[python-36-compat]] — 脚本侧的 3.6 兼容约束（本 skill 的 `.py` 必须遵守）
- [[repo-conventions]] — 行宽 120、Markdown 行宽（SSOT）
- `gemini-paper-summary/SKILL.md` §A' / §B（端到端示例 + 批量速读）— 引用本文 §7 / §8 解释 --full 与现有工作流的边界
- `llm-wiki-management/references/paper-wiki-profile.md` §7 — **消费方侧的集成契约 SSOT**（本文 producer 侧 SSOT 的对端）
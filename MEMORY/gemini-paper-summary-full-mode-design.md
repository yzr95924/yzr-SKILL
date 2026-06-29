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

`--full` = "一份 PDF → 两份产物":`(a) quick summary ≤2500 字符`(existing 默认模板)
`(b) 全量结构化转储 = 沿用同 H2 骨架 + 解除字符数约束 + 每 H2 下按论文原生
`Section X.Y` 逐小节展开`——落到 **Karpathy LLM Wiki raw 端约定 layout**:
`raw/papers/<slug>.full.md` + `raw/papers/<slug>.quick.md` +
`raw/assets/<slug>/fig-NN.png`。

## 1. 完整 4 个设计决策

| # | 决策 | 选择 | 替代方案(为什么不要) |
| --- | --- | --- | --- |
| D1 | 与 default 关系 | 单次调用**两份产物**(quick summary + full) | (a) 只产 full: 消费端必须调两次凑齐两份（要么两次 prompt 不一致、要么两份独立提交流程）；(b) 互斥模板:`--template academic\|lite\|full` 三选一——与现有 `--focus` / `--template academic` flag 风格不统一，"一次成型"卖点丢失 |
| D2 | 产物 layout | **Karpathy LLM Wiki raw 端约定**: `--output <root>` → `<root>/raw/papers/<slug>.full.md` + `<root>/raw/papers/<slug>.quick.md` + `<root>/raw/assets/<slug>/fig-NN.png` | (a) 同款 `--extract-figures` layout(`<dir>/summary.md + <dir>/papers/ + <dir>/assets/`):--full 后还得手动 `mv` 进 `raw/`——破坏"一次调用结束 raw 端就绪"的卖点;(b) 加 `--layout raw\|standard`:多一个 flag + 两条路径都需测;当前**只在 --full 模式**下生效,YAGNI |
| D3 | full 模式结构 | **沿用同 H2 骨架**(开篇表 / 3 句话总结 / 背景与动机 / 方法设计 / 代表性实验结果 / 业务启示 & 价值 / 局限) + **解除 ≤2500 字符**约束 + 每 H2 下按 PDF `Section X.Y` / `Section X.Y.Z` 逐小节展开(`###` 与 `####`) | (a) 完全照 PDF 章节顺序:跨论文结构不可比,quick → full 跳读时找不到对应;(b) 单文件两份结构(上半 quick + 下半 full):文件长 3-5×、两套逻辑绑一个文件;后续要把 quick summary 与 full 解耦(未来 publish 类消费)代价大 |
| D4 | 是否带 Stage 2 视觉定位 | **必须带**:`--full` 隐含 `--refine-figures` 默认开 | raw 端约定要求图存 `raw/assets/<slug>/fig-NN.png`,意味着图被消费方反复引用;用 Stage 2 才能拿到精确 bbox,防止旧 caption locator fallback 留白(top header 框入) |

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

## 4. 为什么 D3 选"同骨架 + 不压缩"

**Why:** quick summary 的 H2 骨架（`## 3 句话总结` / `## 背景与动机` / `## 方法设计` /
`## 代表性实验结果` / `## 业务启示 & 价值` / `## 局限与未来工作`）对应"读者想知道的
6 类问题"，已经被仓库内多个 skill 共识接受。full 模式既然要把 raw 端做满，产物也应当
满足这 6 类问题——否则"quick summary 在 A 段，full 在 B 段，跨文件交叉看很累"。

**关于"全文级展开":** quick summary 当前受 ≤2500 字符的"精炼优先"约束，full 模式把
这条去掉，改为"按 PDF 的 `Section X.Y` / `Section X.Y.Z` 逐小节展开"——
- 这是"不压缩"的硬约束:每个小节都得到篇幅，不能再"因 2500 字符限制砍 4.3 节"
- `### Section X.Y: Title`（原文标题保留英文）+ `#### Section X.Y.Z` 嵌套，跨论文
  比较时仍是"同一类问题在那一节"（如 attention mechanism 都在 §3.x）

**反模式（不该这样）:** "同骨架"不是说"headings 一致"就行，**headings 下的内容也必须**:
- 保留**原文标题**（英文，即使 quick summary 是中文）
- 保留**所有数字**（精度 / 量级 / batch size / GPU 数）
- 保留**所有公式**（LaTeX 形式转 Unicode 或 `$$...$$`——提示词层面约束，见 §6）
- 保留**所有实验表格**（可以转 markdown 表格；图截不下来就转表）

"## 方法设计"下空"Section 3.1 / 3.2 / 3.3" 三个空标题就是**违反**本条——这等于
"还是 quick summary，只是变长了"，full 模式不是这个意思。

**How to apply:** prompt 模板（`prompt-template.md` 的 `## 全文级抽取模板 (full)` 变体）
里**显式列出硬约束**:
- "**禁止**因字符数限制合并小节；每个 `Section X.Y` 必须出现，缺数据写'原文未明确'"
- "**禁止**把 `Section 4.2` 的表格合到 `Section 4.1`；表格转 markdown"
- "**禁止**改写英文小节标题；原文是 '3.1 Model Architecture' 就保持 '### 3.1 Model Architecture'"

## 5. 为什么 D4 选"必须带 Stage 2"

**Why:** Stage 2 视觉定位（`--refine-figures`）解决 caption locator fallback 在
"figure 上方只有 annotation / label" 情形退到 page 顶、把 page header 全框进来的老问题。
详见 `MEMORY/gemini-paper-summary-figure-extraction-edges.md` §1、§4.2。

raw 端产出的图会被消费方在后续多次对话里反复引用——bbox 不准一次 = 后续
多次引用的图都不准。Stage 2 多花的 token 是值得的。

**反模式（不该这样）:** "full 模式太慢，加 `--no-refine-figures` 跳过 Stage 2"——
这是把"图不准的代价"转嫁给下游多次引用；Stage 2 的代价上限是 ~5-15s/页 × 引用页数，
单论文 + Stage 2 全跑 ≈ 1-3 分钟；这个量级在"贵读一次"的语境下不算贵。

**How to apply:**
- `--full` 模式默认开 Stage 2（隐式 `--refine-figures`）；若用户执意要关，允许
  `--no-refine-figures` 但 stderr INFO 提醒"raw 端图可能不准 bbox"
- Stage 2 失败的 page 走 caption locator fallback（与现有逻辑一致）；**不**因为
  full 模式就强制重试到死

## 6. 公式 / 表格的转写约定（全量抽取才需关心）

quick summary 因为 ≤2500 字符，公式通常只写"参见公式 X"，full 模式要保真。具体约定
在 prompt 模板里写；这里先记"为什么":

- **公式**:PDF 渲染公式在 Gemini 多模态看图时是**看得见的**——prompt 要求逐公式保留，
  形式 = Unicode（`2^64` / `≥` / `√`）或 `$$...$$`（outline-wiki 不渲染 MathJax，
  详见 `MEMORY/prompt-length-unit-character.md` §一 + `prompt-template.md` 风格约定 #9）
- **表格**:论文实验结果 / hyperparameter 表是文本信息，**不**应仅留图引用；
  prompt 要求逐行转 markdown 表格，数字精度保留（`95.2 ± 0.3` 这种）

## 7. --full 模式的产出清单

用户跑 `gemini_paper_summary.py --pdf attn.pdf --output ~/root/ --full`，产物**全部**都在
`--output` 指定的 raw 根下：

```text
<root>/raw/
├── papers/
│   ├── <slug>.full.md       # full 抽取
│   └── <slug>.quick.md      # quick summary（精炼版,供后续可选 publish 流程消费）
└── assets/<slug>/
    ├── fig-01.png           # Stage 2 视觉裁剪
    ├── fig-02.png
    └── ...
```

> **本 skill 不直接写 `wiki/sources/<slug>.md`**。raw 端的 quick + full 是
> 本 skill 的唯一产物；任何"占位 source 页"或后续蒸馏由消费方 skill 处理。

**Quick summary 的产出位置:** `<root>/raw/papers/<slug>.quick.md`（与 .full.md 同目录，
加 `.quick` 后缀区分）；**不是** `wiki/sources/<slug>.md`——理由：避免
"raw 是只读的 / wiki 是可写的"两条 linter 规则 `claude-md-template.md` §一 出现
不必要的责任划分。

## 8. 已知边界 / 不在本次实施范围

- **不改 quick summary 模板**:原本 ≤2500 字符 academic 模板是稳定 SSOT，full 模式只是加新变体
- **不引入新 pip 依赖**:复用现有 `pymupdf` + `google-genai`
- **不重写 Stage 2**:Stage 2 视觉定位逻辑（`call_gemini_for_visual_bbox` 等）不动，
  --full 只是默认开启
- **不重命名产物**:`<slug>.full.md` / `<slug>.quick.md` 后缀约定与 Karpathy LLM Wiki
  raw 端约定一致
- **不写 ingest 操作**:`--full` 跑完 = raw 端就绪；ingest 是消费方的职责
- **不做"已抽取则跳过"**:用户已经 `raw/papers/<slug>.full.md` 存在，跑 --full 时**默认拒绝覆盖**
  （退出 1，提示用 --force-full）；理由与 §3 一致
- **与未来 publish skill 的边界**:quick summary 留给 publish 类消费方使用；本 skill **不**做
  attachment 上传 / Outline API 调用——`SKILL.md` §A' 既有端到端示例依然有效，
  只是把"quick summary 直接走 outline"那段示例从本 skill 文档抽到 publish skill

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
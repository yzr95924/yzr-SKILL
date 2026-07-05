# `--full` 全文级抽取模式契约

> **设计决策 SSOT**：本文档是 `--full` 模式边界 / 调用契约的权威实现规范（npx 分发后唯一可见的设计文档）。
> SKILL.md 只讲"agent 在哪一步怎么做"，决策 why 在本文档正文内嵌——不依赖任何外部 MEMORY 文件。
>
> **产物 layout SSOT**：`raw/papers/<slug>.{quick,full}.md` 是 paper `--full` 模式**唯一**的产物布局；
> 与 `scripts/gemini_pdf_summary.py::slug_from_path` + `_run_full_mode` 同源——改布局改脚本即可，
> 本文档是描述镜像。manual / whitepaper / book 走**目录**形式（`raw/<type>/<slug>/summary.md` 或 `raw/<type>/<slug>/<slug>.md`），
> 不走本文档描述的 layout。

## 目录

- [接口约定核心](#接口约定核心)
- [调用形式](#调用形式)
- [产物 layout](#产物-layout)
- [关键纪律](#关键纪律)
- [关键行为护栏](#关键行为护栏)（2026-06-30 第二轮翻面：full 不落 PNG）
- [反模式](#反模式)
- [专属故障排查](#专属故障排查)

---

## 接口约定核心

单次调用同时产 **quick summary** + **PDF→Markdown 全量转写** 两份产物；产物 layout **强制 raw-compatible**——`--output` 视为 wiki 仓根，
直接落到 `<wiki_root>/raw/papers/<slug>.{quick,full}.md`。**不要**用 `--full` 把产物落
任意目录——那是 `--extract-figures` 的职责。

**2026-06-30 第二轮翻面**：`raw/assets/<slug>/fig-NN.png` 仅由 quick 模式或
`--extract-figures` 单跑产生，**full 模式不落 PNG**（自包含，mermaid/ASCII 在
markdown 里）。full 模式也不再跑 Stage 2；Stage 2 仍是 quick 模式隐式行为，
`--refine-figures` 仅作用于 quick 模式 + `--extract-figures`。

## 调用形式

```bash
# 推荐（默认从 PDF 文件名推断 slug；这里是 "attention-is-all-you-need"）
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/Attention\ Is\ All\ You\ Need.pdf \
  --output ~/wiki/llm/ \
  --full

# 显式 slug（不依赖文件名）
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attn.pdf \
  --output ~/wiki/llm/ \
  --full --slug attention-is-all-you-need

# 覆盖已存在 raw（默认拒绝）
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attn.pdf --output ~/wiki/llm/ --full --force-full
```

## 产物 layout

一次调用结束 raw 端就绪（2026-06-30 第二轮翻面后，full 不落 PNG）：

```text
<wiki_root>/raw/
├── papers/
│   ├── attention-is-all-you-need.quick.md   # academic 模板（含 ![图 N] 引用 + 落 PNG，精炼速读；字符数 SSOT 见 assets/prompt-template.md §基础要求 #4）
│   └── attention-is-all-you-need.full.md    # full 模板（自包含，无 PNG 配套；mermaid/ASCII 在 markdown 里；全文级 PDF→Markdown 转写）
└── assets/
    └── attention-is-all-you-need/           # 仅由 quick 模式或 --extract-figures 单跑产生，full 不写
        ├── fig-01.png                       # Stage 2 视觉裁剪（quick 模式产物）
        ├── fig-02.png
        └── ...
```

`wiki/sources/<slug>.md` **不是本 skill 的产物**——raw 端的 quick + full
抽取只到 `<root>/raw/...`；任何"占位 source 页"或后续蒸馏由消费端 skill
自行处理，本 skill 不碰 `wiki/` 目录。

**Raw 端就绪后**——本 skill 退出。任何后续 ingest / refine / publish 编排
属于消费端的工作流；本 skill 不引用、不编排、不假设存在具体消费 skill。
详见上文产物 layout 目录契约（`raw/papers/<slug>.quick.md` + `.full.md` +
`raw/assets/<slug>/fig-NN.png`）。

## 关键纪律

- **不要**用 `--full` 模式只产 full —— 即使只要 raw 端，本 skill 也**必须**
  一次调用两份产物（quick summary 作为后续可选 publish 流程的输入，full
  作为后续多轮文本层 query / 蒸馏的输入；本 skill 不规定下游消费方）；
  拆两次调用反而破坏单次成型的产品形态
- **`raw/papers/<slug>.full.md` 不重写**：默认拒绝覆盖；下游已多次引用 full 抽取，
  意外重写会丢下游状态。若要重新抽取，先 `rm <wiki-root>/raw/papers/<slug>.full.md`
  再跑
- **`--full` 与图导出（quick 默认带图）职责不同**：full 模式产物自包含无图、layout 是
  raw-compatible，不消费 `--extract-figures` / `--no-figures`（这些仅 quick 模式生效）；
  full 模式同时另产一份 quick summary（带图，落 `raw/assets/<slug>/`）
- **Stage 2 / `--refine-figures` 在 full 模式是哑**：full 不跑 Stage 2、不写
  `![图 N](...)` 引用、要 PNG 走 quick 模式或 `--extract-figures`

## 关键行为护栏

（2026-06-30 第二轮翻面：full 不落 PNG）

- **产物定位**：full 模式产物是 agent 的**多轮问答底座**，无 PDF 时所有问题从
  `.full.md` 查。**禁止** summary 视角（三句话总结 / 业务启示 / 局限），prompt
  直接做 PDF→Markdown 全量转写
- **章节顺序**：严格按 PDF 原文章节顺序，每个 `Section X.Y` / `Section X.Y.Z`
  必须出现对应 `###` / `####`。**不要**做 6 类问题归纳
- **保真元素**（按关键度排序）：章节标题（英文原文）> Definition/Theorem/Lemma/
  Algorithm 标注 > 公式（`$$...$$`）> 表格（markdown 行级）> 数字精度（3 位有效
  数字）> 英文小节标题
- **不落 PNG**（2026-06-30 第二轮翻面）：full 模式不创建 `raw/assets/<slug>/`、
  不跑 Stage 2、不写 `![图 N](...)` 引用。架构/概念图直接 ```mermaidjs```
  block 画、数据可视化图转 markdown 表格、装饰图省略 + 文字一句。若想看 PNG
  跑 quick 模式（默认）或 `--extract-figures`
- **mermaid 块语法**：` ```mermaidjs `（不是 ` ```mermaid `）——与 academic 模板
  风格约定一致；SSOT 见 `assets/prompt-template.md` 基础要求段（line 192-193）
- **Output token 上限**：`FULL_MAX_OUTPUT_TOKENS` 模块常量（`scripts/gemini_paper_summary.py`）。
  `_run_full_mode` 第二次调用显式传该常量。quick summary 走默认 token 上限
- **后置内容自检**：`_run_full_mode` 写完 `.full.md` 后跑 `self_check_full_content`，
  校验 6 项（H2 ≥ 3 / `### Section X.Y` ≥ 5 / Definition+Theorem+Lemma+Algorithm
  标注数 / `$$...$$` block 数 / **字符下限 `min_chars`** / **"原文未明确"占位比例
  `placeholder_ratio_warn`**）——前两个阈值与 6 个参数默认值的 SSOT 都在
  `scripts/gemini_paper_summary.py:self_check_full_content` 函数签名
  （`min_h2=3` / `min_sections=5` / `min_chars=8000` / `placeholder_ratio_warn=0.5`）。
  任一失败 stderr WARN/FAIL，**不阻塞**（非阻塞是设计选择，
  见 SKILL.md §核心原则 #8）
- **`--refine-figures` / `--thumbnail` 在 full 模式是哑参数**（2026-06-30）：
  full 不消费这些 flag；quick 模式默认带图时生效（`--no-figures` 关闭则都不跑）。
  脚本 stderr INFO 提示
- **`--focus` 在 full 模式走 FOCUS_INJECTION_FULL**（2026-06-30 重新定位后）：
  full 没有 summary 段，focus 不能追加到末尾——而是**注入到对应的 PDF 原生章节下**，
  形式为 `### 用户关注点: <focus>` 子节（或等价的 focus 子段）。比如
  focus="gating 路由的稀疏性 + 辅助负载均衡损失" 时，该子节会出现在
  `## Section 3` 的 `### Section 3.2 Gating` 子节下，而不是全文末尾。quick 模式
  仍走 FOCUS_INJECTION（末尾追加 "## 启发 / 追问" 段）。脚本实现见
  `scripts/gemini_paper_summary.py` 的 `FOCUS_INJECTION_FULL` 常量
  以及 `build_prompt` 的 template 切换；
  契约测试见 `eval/evals.json` test #2 assertion 2

## 反模式

**别**这么干：

- 跑 `--full` 但希望产物落 `<dir>/papers/<slug>.full.md`——**不会发生**，`--full`
  强制 raw-compatible；想落任意目录就**不**加 `--full`，直接跑 quick 默认（就带图）
- 跑两次 `--full` 然后手动把两份产物拼一起——要"一次调两份"是设计本意；
  拆两次会因 quick summary 与 full 模板的 prompt 不一致导致两份对不上
- 在本 skill 里写"占位 source 页" —— 写 `wiki/sources/<slug>.md` 属消费端职责；
  本 skill 只到 raw 端为止
- **`--full` 写 `![图 N](PDF p.X ...)` 引用**（2026-06-30 第二轮翻面后
  **禁用**）——full 模式不落 PNG，引用会断图。架构/概念图直接 mermaid /
  ASCII 画在 markdown 里，数据图转 markdown 表格，装饰图省略。**不要**写
  `![图 N]` 引用——这是 full 与 quick 在图处理上的硬边界

## 专属故障排查

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `ERROR: .../raw/papers/<slug>.full.md 已存在;full 抽取默认拒绝覆盖` | 之前跑过 `--full` 该 PDF | 先 `rm <wiki_root>/raw/papers/<slug>.full.md` 再跑；或加 `--force-full` 显式覆盖 |
| `--full` 跑完后 quick summary 字符数超出预期 | academic 模板的精炼约束 prompt 是"目标不是上限"，Gemini 偶尔溢出 | 降 temperature 到 0.1；或后处理截断（具体字符数 SSOT 见 `assets/prompt-template.md` §基础要求 #4） |
| `ERROR: 无法推断论文 slug` | PDF 文件名含 unicode 私造字符或全部为非 kebab-case | 加 `--slug <kebab-case-slug>` 显式指定 |
| `full.md` 缺尾部章节（业务启示 & 价值 / 局限与未来工作） | 旧版 prompt 残留；**2026-06-30 重新定位后这是预期行为** | full 模式已改为 PDF→Markdown 全量转写，**不再输出**三句话总结 / 业务启示 / 局限等 summary 段；若需要 summary 段，跑 academic 模板（默认）即可 |
| `full.md` 的"原文未明确"占位超过 `### Section` 数一半 | 模型偷懒（应"原文未明确"但实际有内容） | 改 prompt 重跑（不写 `--focus` 让模型聚焦到具体小节）；或换更精确的模型（见 SKILL.md §模型选型） |
| `full.md` 缺 Definition/Theorem/Algorithm 标注 | 原文无此类标注 **或** 模型未保真标注 | 若是算法 / 数学类论文，自检会 WARN；检查 prompt 是否完整加载 |
| `full.md` 缺 `$$...$$` 公式 block | 原文无独立公式 **或** 模型未用 `$$...$$` 转写 | 若是数学 / 物理类论文，自检会 WARN；检查 prompt 是否完整加载 |
| `full.md` 缺 mermaid 块，但 PDF 明显有架构图 | 模型未按 prompt 转 mermaid（可能 PDF 视觉读不出） | 检查 prompt 是否完整加载；或换更精确模型；若该图是性能柱状图等数据图，转 markdown 表格亦可 |
| `full.md` 的 `--focus` 注入位置不对（跑到末尾而非对应 PDF 章节下） | 误用了 academic 的 FOCUS_INJECTION（末尾追加 "启发 / 追问" 段） | full 模式 focus 必须走 FOCUS_INJECTION_FULL：在对应 PDF 原生章节下追加 `### 用户关注点: <focus>` 子节，不是末尾。脚本自动按 `template="full"` 切换；若产物错了，检查 `build_prompt` 调用是否传了 `template="full"`（见 `build_prompt` 的 template 分支） |
| `INFO: --full 模式已不再落 PNG,--refine-figures / --thumbnail 在 full 模式是哑参数` | `--refine-figures` 或 `--thumbnail` 在 full 模式不生效 | 期望行为：full 模式不消费这两个 flag。要 PNG 跑 quick 模式或 `--extract-figures` |

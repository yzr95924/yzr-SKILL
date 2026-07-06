# 全文级 (full 风格) 抽取模式契约

> **设计决策 SSOT**：本文档是 full 风格（按 PDF 原生章节顺序全文级转写）边界 / 调用契约的权威实现规范。
> SKILL.md 只讲"agent 在哪一步怎么做"，决策 why 在本文档正文内嵌——不依赖任何外部 MEMORY 文件。
>
> **适用范围**：4 类文档中**所有走 full 风格**的类型——
>
> - **paper full**（`--type paper --full`，2026-06-30 第二轮翻面后）
> - **manual**（`--type manual`，单模板即 full）
> - **whitepaper**（`--type whitepaper`，单模板即 full）
> - **book**（`--type book`，单 full 模式）
>
> **不在本文档范围**：**paper quick**（`--type paper` 默认，精炼速读带图）——见 SKILL.md §C paper quick。

## 目录

- [接口约定核心](#接口约定核心)
- [调用形式](#调用形式)
- [产物 layout](#产物-layout)
- [by-chapter 模式（`--by-chapter`，4 类通用，默认 L1）](#by-chapter-模式--by-chapter4-类通用默认-l1)
- [关键纪律](#关键纪律)
- [关键行为护栏](#关键行为护栏)
- [反模式](#反模式)
- [专属故障排查](#专属故障排查)

---

## 接口约定核心

按 `--type` 分两类产物策略：

### paper `--full`（双产物）

单次调用同时产 **quick summary** + **PDF→Markdown 全量转写** 两份产物；产物 layout **强制 raw-compatible**——
`--output` 视为 wiki 仓根，直接落到 `<wiki_root>/raw/papers/<slug>.{quick,full}.md`。
**不要**用 `--full` 把产物落任意目录——那是 `--extract-figures` 的职责。

**2026-06-30 第二轮翻面**：`raw/assets/<slug>/fig-NN.png` 仅由 quick 模式或
`--extract-figures` 单跑产生，**full 模式不落 PNG**（自包含，mermaid/ASCII 在
markdown 里）。full 模式也不再跑 Stage 2；Stage 2 仍是 quick 模式隐式行为，
`--refine-figures` 仅作用于 quick 模式 + `--extract-figures`。

### manual / whitepaper / book（单产物）

单次调用产一份 PDF→Markdown 全量转写产物；产物 layout 是 `<output>/summary.md`
（用户传 `--output <dir>` 时）或 `<output>/<slug>.md`（book 类型自动用 slug）——
**单文件，无 .quick / .full 后缀**。脚本已硬编码 `prompt_mode = "full"` for these
types，无需用户传 `--full`。

**manual / whitepaper / book 默认全程不抽原始 PNG**（脚本自动启用 `--no-figures`）；
架构 / 概念 / 数据图全部走 mermaid block / markdown 表格 / ASCII 在产物内直接画。

---

## 调用形式

### paper `--full`

```bash
# 推荐（默认从 PDF 文件名推断 slug；这里是 "attention-is-all-you-need"）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/papers/Attention\ Is\ All\ You\ Need.pdf \
  --output ~/wiki/llm/ \
  --full

# 显式 slug（不依赖文件名）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/papers/attn.pdf \
  --output ~/wiki/llm/ \
  --full --slug attention-is-all-you-need

# 覆盖已存在 raw（默认拒绝）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/papers/attn.pdf --output ~/wiki/llm/ --full --force-full
```

### manual / whitepaper / book

```bash
# manual（产品手册 / datasheet / 用户手册）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/h100-sxm-datasheet.pdf \
  --type manual \
  --output ~/wiki/llm-systems/raw/manuals/h100-sxm/
# 产物：<dir>/summary.md（按 PDF 原生目录结构全文级转写）

# whitepaper（行业 / 技术 / vendor 白皮书）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/gartner-ai-infra-2026.pdf \
  --type whitepaper \
  --output ~/wiki/industry/raw/whitepapers/ai-infra-2026/
# 产物：<dir>/summary.md（按 PDF 原生目录结构全文级转写；元信息段标注发布立场）

# book（书籍 / 长篇技术文档；默认已走 pro-preview，长篇不需额外传 model）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/books/crafting-interpreters.pdf \
  --type book \
  --output ~/wiki/llm-systems/raw/books/crafting-interpreters/
# 产物：<dir>/<slug>.md（按 Chapter / Part / Appendix / Index 顺序全量转写）
```

---

## 产物 layout

按类型分流：

| 类型 | layout | 是否带 PNG | 调用方式 |
| --- | --- | --- | --- |
| **paper `--full`** | `<wiki_root>/raw/papers/<slug>.quick.md` + `<slug>.full.md` | 否（full 自包含；quick 模式另产 PNG 到 `raw/assets/<slug>/`） | 显式 `--full`；默认拒绝覆盖，加 `--force-full` |
| **manual** | `<output>/summary.md`（单文件） | 否（mermaid / 表格 / ASCII 内画） | `--type manual`；产物直接落 `--output` 目录 |
| **whitepaper** | `<output>/summary.md`（单文件） | 否 | `--type whitepaper`；同上 |
| **book** | `<output>/<slug>.md`（单文件） | 否 | `--type book`（脚本自动启用 full）；默认 pro-preview，长篇不需额外传 `--model` |

`wiki/sources/<slug>.md` **不是本 skill 的产物**——full 风格抽取只到 `<output>/` 即可；
任何"占位 source 页"或后续蒸馏由消费端 skill（`llm-wiki-management`）自行处理，
本 skill 不碰 `wiki/` 目录。

---

## by-chapter 模式（`--by-chapter`，4 类通用，默认 L1）

> **设计动机（2026-07-06 翻面）**：当用户希望按章节粒度拥有独立 .md 文件、便于
> llm-wiki 多次 ingest 与逐章 Q&A 时使用。**默认走 L1 模式**：PyMuPDF 读 PDF TOC
> → 按 L1 章 N 次独立 API 调用 → L2 子节合并进 L1 文件，**自带 File API 缓存**
> （PDF > 20MB 时上传 1 次 + N 次 `Part.from_uri()` 引用，节省 N-1 次 PDF 上传 token）。
>
> 适用 4 类文档（paper / manual / whitepaper / book）；**与 `--full` 互斥**
> （`--by-chapter` 已隐含全文级转写）。详细决策背景见 SKILL.md §A Step 1b +
> §输出 by-chapter 段。
>
> **历史背景**：原 L1 翻面前的"单次 API + JSON"模式已重命名为 `--granularity auto`，
> 保留供 ≤ 50 页短 PDF 使用；长 PDF 走 pre-flight 拦截并推荐 L1（决策依据：
> 98 页华为 OceanDisk 白皮书单次调用 → 35%+ 章节截断，详见
> /root/gemini-white-paper-err.md）。

### by-chapter 接口约定核心（L1 默认）

| 维度 | 约定 |
| --- | --- |
| 拆法（`--granularity`） | **`L1`（默认）** / `auto`（旧单次调用） |
| L1 模式调用次数 | **N_L1 次**（每个 L1 章 1 次 API 调用，与 L1 章数同） |
| L1 模式 File API 缓存 | PDF > 20MB → 预上传 1 次 → 后续 N-1 次调用复用 `file_part` |
| L1 模式页范围 | 按 L1 章边界自动切（`[start, next_L1_start - 1]`）；无需 `--pages` |
| auto 模式调用次数 | **1 次**（不拆段、不并行；同旧行为） |
| API 调用方式 | Gemini `response_mime_type="application/json"` + `response_schema` 强制 JSON 结构 |
| 输出形态 | `{"chapters": [{"title": "...", "level": N, "content": "完整 markdown"}, ...]}` |
| 拆文件 | L1 模式：N_L1 个 .md（每个 L1 合并其下 L2 子节）；auto 模式：N 个 .md（每个 chapter 1 个） + 1 个 `00-index.md` TOC |
| token 上限 | L1 模式每章 ≤ 50 页，撞 65536 上限概率近 0；auto 模式仍受 65536 上限约束 |
| 适用 PDF 长度 | L1 模式：**任意长度**（按 L1 拆每章 < 50 页）；auto 模式：**≤ 50 页**（> 50 页 pre-flight 拒绝） |
| 产物 layout | `<output>/00-index.md`（N_L1 / N 行 TOC）+ `<output>/NN-<slug>.md` |
| 与 `--full` 关系 | **互斥**——`--by-chapter` 已隐含全文级转写；`--full` 是 paper 双产物路径 |
| 与 `--pages` 关系 | L1 模式：传了报错（L1 按章自动切页）；auto 模式：可用 `--pages` 拆段 |

### by-chapter 调用形式

```bash
# === L1 模式（默认，2026-07-06 起，长 PDF 首选）===
# manual / whitepaper / book
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/huawei-oceandisk-1600-wp.pdf \
  --type whitepaper \
  --by-chapter \
  --granularity L1 \
  --output ~/wiki/llm-systems/raw/whitepapers/oceandisk-1600/
# 产物：00-index.md + 14 个 <NN>-<L1-slug>.md（含 L2 子节合并）

# product datasheet
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/Downloads/h100-sxm-datasheet.pdf \
  --type manual \
  --by-chapter \
  --output ~/wiki/llm-systems/raw/manuals/h100-sxm/
# 产物：00-index.md + N_L1 个 <NN>-<L1-slug>.md

# paper 也可走 by-chapter（与 --full 互斥；走 by-chapter 时不产 quick summary）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/papers/attention.pdf \
  --type paper \
  --by-chapter \
  --output ~/wiki/llm/raw/papers/attention/

# === auto 模式（旧行为，保留供短 PDF + 习惯用）===
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf ~/papers/short.pdf \
  --type manual \
  --by-chapter \
  --granularity auto \
  --output out/auto/

# auto + --pages 拆段（超长 PDF 不推荐；走 L1 即可）
python3 gemini-pdf-summary/scripts/gemini_pdf_summary.py \
  --pdf big.pdf --type book --by-chapter --granularity auto --pages 1-50 \
  --output out/seg1/
```

### by-chapter 产物 layout

**L1 模式**（默认）：

```text
<output>/
├── 00-index.md              # TOC：N_L1 行，每行 [- [L1 标题（p.X）](NN-slug.md)]
├── 01-<L1-slug>.md          # 第 1 个 L1 章：## L1.title + ### L2 子节 + content
├── 02-<L1-slug>.md          # 第 2 个 L1 章
├── ...
├── NN-<L1-slug>.md          # 第 N 个 L1 章
└── NN-FAILED-<L1-slug>.md   # 某 L1 章调用失败时（写占位 + 继续后续 L1）
```

**auto 模式**（旧行为，≤ 50 页短 PDF 用）：

```text
<output>/
├── 00-index.md              # TOC：按 level 缩进 + 章节链接
├── 01-<chapter-slug>.md     # 第 1 章 markdown
├── 02-<chapter-slug>.md     # 第 2 章 markdown
├── ...
└── NN-<chapter-slug>.md     # 第 N 章 markdown
```

典型产物（98 页华为 OceanDisk whitepaper，L1 模式，gemini-3.1-pro-preview 默认）：

```text
/tmp/by-chapter-test/
├── 00-index.md                 (N_L1 行 TOC)
├── 01-摘要.md                  (~2 KB)
├── 02-简介.md                  (~3 KB)
├── 03-硬件架构.md              (~20 KB，含 8 张表 + 1 mermaid block；L2 子节合并在 ### 下)
├── 04-软件架构.md              (~12 KB)
├── ...
└── 14-缩略语.md                (~2 KB)
```

总产物 ≈ 50-80 KB（N_L1 个文件），L2 子节自动合并到对应 L1，无 1B 空文件（脚本自动清理），N 次 API 调用复用同一 File API upload。

### by-chapter 关键纪律

- **L1 模式不抽原始 PNG**：与 manual / whitepaper / book full 风格一致——架构图直接 ```mermaid block```、数据图转 markdown 表格、装饰图省略 + 文字一句
- **L1 章内容合并**：每个 L1 .md = `## <L1.title>` + 各 L2/L3 子节 content（首个子章节的 H1/H2 标题行被剥掉避免重复）
- **章节拆分贴合 PDF 原生层级**（Chapter / Section / Subsection / Appendix / Index），**不要**把整本塞进一个对象
- **不写 H1**：每个章节的 `title` 字段承载标题，`content` 字段从 `##` 或 `###` 起步（与 full 风格一致，H1 由文件名 / outline 字段承载）
- **章节末尾特色内容原样保留**：manual 故障排查 / FAQ / 更新日志；whitepaper Conclusion /
  Key Takeaways / Recommendations；book 小结 / 思考题 / 参考文献 / 索引 term → page
- **不输出 summary / TLDR / 整体归纳段**：每个章节 content 是该章节的完整转写，**不**做跨章节归纳
- **关键数字精度保留**：不要"约""大约"模糊化（如 `160 万 IOPS` `4 GB/s` `≤ 2 ms`）
- **L1 模式与 `--pages` 互斥**：L1 按 L1 章边界自动切页；传 `--pages` 报错（"L1 模式无需 --pages"）。auto 模式可与 `--pages` 组合拆段
- **Stub 清理**：`< 100B` 的 .md 视为模型放弃的章节，脚本自动 `os.remove` + stderr WARN 数字

### 与现有 4 类 full 模式的差异

| 维度 | manual / whitepaper / book full | paper `--full` | **by-chapter L1**（默认） | **by-chapter auto**（旧） |
| --- | --- | --- | --- | --- |
| 调用次数 | 1 | 2（quick + full） | **N_L1** | 1 |
| 产物形态 | 1 个 .md | 2 个 .md（quick + full） | **N_L1 + 1 个 .md**（N 个 L1 + 1 个 TOC） | **N + 1 个 .md**（N 章 + 1 个 TOC） |
| 章节粒度 | 全文级单文件 | 全文级双文件 | **逐 L1 文件 + L2 合并** | **逐章独立文件** |
| 适用场景 | 普通全文转写 | paper 双产物路径 | **llm-wiki 多次 ingest / 逐章 Q&A（长 PDF）** | **短 PDF 单次过** |
| token 上限 | `FULL_MAX_OUTPUT_TOKENS` | `FULL_MAX_OUTPUT_TOKENS`（full 那次） | **每章 < 50 页几乎不撞** | **`FULL_MAX_OUTPUT_TOKENS`（更紧：JSON 格式增加 ~3% 开销）** |
| 与 `--pages` 组合 | N/A | N/A | **不支持**（按章自动切） | **支持（拆超长 PDF）** |
| File API 缓存 | 单调用（按需） | 单调用（按需） | **N-1 次调用复用**（节省 85% 输入 token） | N/A（单调用） |

### L1 模式失败处理（2026-07-06 新增）

| 失败场景 | 处置 |
| --- | --- |
| PyMuPDF 缺 | 报错退出（"L1 模式需要 pymupdf"）；agent 可改 `--granularity auto` |
| PDF 无 TOC（无 bookmarks / outline） | stderr WARN + 自动 fallback `auto` 模式 |
| File API 上传失败 | 报错退出（**不**静默退 inline——inline 无法跨调用复用）；agent 可改 `auto` 或重试 |
| 单个 L1 章 API 调用失败 | 写 `<idx>-FAILED-<slug>.md` 占位 + 继续后续 L1；00-index.md 标 ⚠FAILED |
| 单个 L1 章页范围切割失败 | 写 `<idx>-FAILED-<slug>.md` 占位 + 继续 |

### 截断检测 + 处置

by-chapter 模式受 `FULL_MAX_OUTPUT_TOKENS`（65536）上限约束。脚本内置两层检测：

1. **API 层**：`call_gemini_structured` 读 `response.usage_metadata.candidates_token_count`，
   若 ≥ 65530 写 stderr WARN，建议用 `--pages` 拆段（默认已走 pro-preview）
2. **末位章节层**：`_looks_truncated_chapter` 启发式检测 content 末尾未正常闭合
   （末字符不在 `.。!！？\`)]>|*#` 等闭合符集合内 + 未闭合代码块 / 表格行），
   标记 ⚠ 在 `00-index.md` 末尾追加"截断告警"段

**L1 模式**（默认）：每章 ≤ 50 页 → 撞 65536 token 上限概率近 0；如有截断，WARN
指向失败 L1 章 + 建议 `--pages <失败页范围> --granularity auto` 单独重跑。

**auto 模式**（旧）：单次调用撞限概率与 PDF 长度正相关，> 50 页必截断；pre-flight
会主动拦截并推荐 L1。

**典型处置策略**：

```bash
# 1. 默认已走 pro-preview；auto 单次调用撞上限 → 按页拆段（每段内按章节拆）
python3 gemini_pdf_summary.py --pdf big.pdf --type book --by-chapter --granularity auto --pages 1-200 --output out/p1/
python3 gemini_pdf_summary.py --pdf big.pdf --type book --by-chapter --granularity auto --pages 201-400 --output out/p2/
# 产物：out/p1/00-index.md + N 章 .md + out/p2/00-index.md + M 章 .md
# 跨段拼接（如需合并成一份大目录）由消费端 skill 处理

# 2. L1 模式某章截断 → 用 --pages 单独重跑该章范围（auto 模式调用），保留前段结果
python3 gemini_pdf_summary.py --pdf big.pdf --type whitepaper --by-chapter --granularity auto \
  --pages 35-50 --output /tmp/refill/  # 跑出 <NN>-<L2-slug>.md
# 手动合并进原 L1 文件（纯本地操作，详见 SKILL.md §A Step 3 失败处理）

# 3. 末位章节确实截断 → 用 --pages 单独重跑末段，保留前段结果
#    （脚本默认不覆盖已存在文件，与 --full 不冲突；by-chapter 无内置覆盖保护，需要手动 rm 后重跑）
```

---

## 关键纪律

### 通用纪律（4 类 full 都遵守）

- **不落 PNG**：full 模式产物自包含无图、layout 是 raw-compatible（或单文件 `<output>/`），
  不消费 `--extract-figures` / `--no-figures`（这些仅 paper quick 模式生效）；
  manual / whitepaper / book 默认就全程不抽 PNG
- **Stage 2 / `--refine-figures` 在 full 模式是哑参数**：full 不跑 Stage 2、不写
  `![图 N](...)` 引用、要 PNG 走 paper quick 模式或 `--extract-figures`
- **不写 `![图 N](PDF p.X ...)` 引用**：full 风格全部不落 PNG，引用会断图。
  架构 / 概念图直接 mermaid / ASCII 画在 markdown 里，数据图转 markdown 表格，
  装饰图省略 + 文字一句。这是 full 与 quick 在图处理上的硬边界
- **mermaid 块语法**：` ```mermaid `(不是 ` ```mermaid `)——与 academic 模板风格约定一致
- **`--focus` 走 FOCUS_INJECTION_FULL**：full 没有 summary 段，focus 不能追加到末尾——
  而是**注入到对应的 PDF 原生章节下**，形式为 `### 用户关注点: <focus>` 子节。
  4 类 full 都遵守。脚本实现见 `scripts/gemini_pdf_summary.py` 的 `FOCUS_INJECTION_FULL` 常量
- **完整性 > 篇幅**：token 预算紧张时**优先精简措辞、缩具体例子 / 长引文 / 重复论证**；
  **禁止**合并整段、删除小节、跳过该类型必保真的元素

### paper `--full` 专属纪律

- **不要**用 `--full` 模式只产 full —— 即使只要 raw 端，本 skill 也**必须**
  一次调用两份产物（quick summary 作为后续可选 publish 流程的输入，full
  作为后续多轮文本层 query / 蒸馏的输入；本 skill 不规定下游消费方）；
  拆两次调用反而破坏单次成型的产品形态
- **`raw/papers/<slug>.full.md` 不重写**：默认拒绝覆盖；下游已多次引用 full 抽取，
  意外重写会丢下游状态。若要重新抽取，先 `rm <wiki-root>/raw/papers/<slug>.full.md`
  再跑

### manual / whitepaper / book 专属纪律

- **单产物**：`--type manual` / `--type whitepaper` / `--type book` **不产**两份——只产一份
  full 风格单文件；不要期望落 `<dir>/papers/<slug>.full.md`
- **无覆盖保护**：manual / whitepaper / book 当前**没有**像 paper full 那样"默认拒绝覆盖"
  的保护（脚本不调 `_run_full_mode`，产物走 `_write_output`）；如需保护产物，
  跑前手动 `rm` 或在外层 git 管理

---

## 关键行为护栏

### 通用护栏

- **产物定位**：full 模式产物是 agent 的**多轮问答底座**，无 PDF 时所有问题从
  对应 markdown 查。**禁止** summary 视角（三句话总结 / 业务启示 / 局限 / 精炼总结），prompt
  直接做 PDF→Markdown 全量转写
- **章节顺序**：严格按 PDF 原生章节顺序（每个 `Section X.Y` / `Chapter X` /
  `Appendix` 必须出现对应 `##` / `###` / `####`）。**不要**做固定段归纳（5 / 6 H2 骨架）
- **不落 PNG**：架构 / 概念图直接 ```mermaid``` block 画、数据可视化图转 markdown 表格、
  装饰图省略 + 文字一句。若想看 PNG 跑 paper quick 模式（默认）或 `--extract-figures`
- **Output token 上限**：`FULL_MAX_OUTPUT_TOKENS` 模块常量（`scripts/gemini_pdf_summary.py`）。
  4 类 full 都传该值。quick summary（仅 paper `--full` 走 quick summary 路径）走默认 token 上限
- **`--focus` 注入位置**：注入到对应 PDF 原生章节下，形式为 `### 用户关注点: <focus>` 子节，
  不是全文末尾
- **`--refine-figures` / `--thumbnail` 在 full 模式是哑参数**：full 不消费这些 flag；
  paper quick 模式默认带图时生效（`--no-figures` 关闭则都不跑）。脚本 stderr INFO 提示

### 类型专属保真元素

| 元素 | paper full | manual full | whitepaper full | book full |
| --- | --- | --- | --- | --- |
| **章节标题** | 原英文保留（`## Section N: ...`） | 原英文保留（`## Hardware Specifications`） | 原英文保留（`## Executive Summary`） | 原英文保留（`## Chapter N: ...`） |
| **Definition / Theorem / Lemma / Corollary / Algorithm** | **必保真**（数学 / 算法类论文） | 通常无 | 通常无 | **必保真**（教材 / 技术专著） |
| **公式** | 行内 `$...$`；自检看 `$$...$$` block | 通常无独立公式（参数公式少） | 通常无 | 行内 `$...$` |
| **命令清单 / API endpoint** | 偶尔（论文伪代码块） | **必保真**（` ```bash ` / ` ```yaml ` / ` ```json `） | 偶尔（snippet） | **必保真**（` ```python ` / ` ```bash `） |
| **表格** | **必保真**（实验结果 / hyperparameter 表） | **必保真**（参数表 / 接口表 / 错误码表） | **必保真**（行业数据表 / 对比表 / 客户案例表） | **必保真** |
| **数字精度** | 3 位有效数字；范围 / 误差必保留 | 3 位有效数字；范围 / 误差必保留 | 3 位有效数字；范围 / 误差必保留 | 3 位有效数字 |
| **章节末尾特色内容** | N/A | **故障排查 / FAQ / 更新日志要点**原样保留 | **Conclusion / Key Takeaways / Recommendations**原样保留 | **小结 / 思考题 / 参考文献**原样保留 |
| **索引 term → page** | 论文通常无 | 通常无 | 通常无 | **原样保留**（书籍索引页） |
| **mermaid 块数（典型）** | 多（架构 / 概念图） | 中（系统架构 / 模块关系） | 中（架构 / 价值链 / 流程） | 中（架构 / 概念） |
| **立场甄别** | N/A | N/A | **必填**（vendor 自家方案 / 行业中立 / 学术 / 政策 / 咨询） | N/A |

### 后置内容自检

调用 `self_check_full_content`（`scripts/gemini_pdf_summary.py`）跑内容完整性校验——目前脚本对
**paper full** 显式调（`_run_full_mode` 末尾）；manual / whitepaper / book 当前**未跑**
该自检（设计上 full 风格已保证基础完整性，运行时未引入该校验是历史遗留）。

`self_check_full_content` 现有 6 项校验（**paper full 专属正则**）：

| # | 项 | 默认阈值 | FAIL / WARN |
| --- | --- | --- | --- |
| 1 | H2 章节数（通用 `^##` 正则） | `min_h2=3` | **FAIL** |
| 2 | `### Section X.Y` 子节数 | `min_sections=5` | **WARN**（paper 命名专属，manual / whitepaper / book 不适用） |
| 3 | Definition/Theorem/Lemma/Corollary/Algorithm 标注数 | ≥ 1（0 时 WARN） | **WARN** |
| 4 | `$$...$$` 公式 block 数 | ≥ 1（0 时 WARN） | **WARN** |
| 5 | 字符下限 | `min_chars=8000`（paper full） | **WARN** |
| 6 | "原文未明确"占位比例 | `placeholder_ratio_warn=0.5`（超 50% 时 WARN） | **WARN** |

manual / whitepaper / book 的自检**待拆分**——若启用，应按各类型调整正则（如 manual 用
通用 `^###\s+` 计数 + 命令清单代码块数；whitepaper 加 mermaid block 数；book 用
`## Chapter N` 计数）。

---

## 反模式

**别**这么干：

### 通用反模式（4 类 full 都适用）

- **在产物里写 `![图 N](PDF p.X ...)` 引用**——4 类 full 都不落 PNG，引用会断图。
  架构 / 概念图直接 mermaid / ASCII 画在 markdown 里，数据图转 markdown 表格，装饰图省略
- **在本 skill 里写"占位 source 页"** —— 写 `wiki/sources/<slug>.md` 属消费端职责；
  本 skill 只到 `<output>/` 为止
- **加私造 Markdown 语法**（`!!! warning` / `:::tip` / `<mark>` / 装饰性 emoji 占位）——
  仓库 `.markdownlint.jsonc` 拒，outline-wiki 不渲染

### paper `--full` 专属反模式

- 跑 `--full` 但希望产物落 `<dir>/papers/<slug>.full.md` 而非 `raw/papers/...`——**不会发生**，
  `--full` 强制 raw-compatible；想落任意目录就**不**加 `--full`，直接跑 paper quick 默认（就带图）
- 跑两次 `--full` 然后手动把两份产物拼一起——要"一次调两份"是设计本意；
  拆两次会因 quick summary 与 full 模板的 prompt 不一致导致两份对不上

### manual / whitepaper / book 专属反模式

- 试图用 `--type manual` 加 `--quick` 强制走 quick 风格——**没有 quick 风格**；
  manual / whitepaper / book 是 full 风格（按 PDF 原生章节顺序），不接受"压缩总结"模式
- 跑 manual / whitepaper 后期望产物是 quick 风格（≤ 3000 / ≤ 3500 字符 + 5 / 6 H2 骨架）——
  **历史产物**（在 manual / whitepaper 改 full 风格之前）才有这行为；当前产物是 full 风格全文级
- 把 manual / whitepaper 产物直接给人看——manual / whitepaper 是给 LLM 消费的下游产物；
  人看请跑 paper quick（如果是论文）或读原文 PDF

---

## 专属故障排查

### 通用故障

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| 产物里出现 `![图 N](PDF p.X ...)` 引用 | 4 类 full 都不落 PNG | 期望行为：脚本 `strip_pdf_figure_refs` 在 main 末尾清理；如出现说明 prompt 漏改 |
| 跑出来字符数远超 prompt 里声明的目标 | Gemini 不严格遵守 prompt 字符数约束 | 调 prompt 字符目标 / `--focus`；后处理裁剪；不要靠 prompt 单点约束 |
| 整本 token 预算超限导致尾部截断 | 模型撞 `FULL_MAX_OUTPUT_TOKENS` 上限 | 默认已是 pro-preview，**改用 `--pages` 拆段**（manual / whitepaper 通常不需要） |
| `503 UNAVAILABLE` / `429 RESOURCE_EXHAUSTED` 重试 3 次后仍失败 | 主模型暂时不可用 / 限流 | **端到端不降级**——脚本直接抛错（含 model 名 + status + 三步建议）；**agent 收到此错不得自行换模型重跑**，须如实报给用户、由用户决定是否 `--model` 显式重试 |

### paper `--full` 专属故障

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `ERROR: .../raw/papers/<slug>.full.md 已存在;full 抽取默认拒绝覆盖` | 之前跑过 `--full` 该 PDF | 先 `rm <wiki_root>/raw/papers/<slug>.full.md` 再跑；或加 `--force-full` 显式覆盖 |
| `--full` 跑完后 quick summary 字符数超出预期 | academic 模板的精炼约束 prompt 是"目标不是上限"，Gemini 偶尔溢出 | 降 temperature 到 0.1；或后处理截断 |
| `ERROR: 无法推断论文 slug` | PDF 文件名含 unicode 私造字符或全部为非 kebab-case | 加 `--slug <kebab-case-slug>` 显式指定 |
| full.md 缺 Definition/Theorem/Algorithm 标注 | 原文无此类标注 **或** 模型未保真标注 | 若是算法 / 数学类论文，自检会 WARN；检查 prompt 是否完整加载 |
| full.md 缺 `$$...$$` 公式 block | 原文无独立公式 **或** 模型未用 `$$...$$` 转写 | 若是数学 / 物理类论文，自检会 WARN；检查 prompt 是否完整加载 |

### manual / whitepaper / book 专属故障

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `manual / whitepaper / book 类型仅支持 full 风格` | 试图用 quick 风格的硬约束（如 ≤ 3000 / ≤ 3500）期待产物 | full 风格无字符数上限；产物比 quick 风格长 5-10 倍是预期行为 |
| manual 产物里漏掉命令清单 / 错误码表 | prompt 未明确标注 manual 必保真元素 | 检查 `assets/template-manual.md` 是否完整加载（`fence_match` 成功）；如 prompt 漏改，补充后重跑 |
| whitepaper 产物里"发布立场"为"原文未明确" | PDF 元信息确实无立场信息 | 预期行为；不要自行补全立场 |
| whitepaper 产物里 vendor 立场未显式标注 | prompt 漏改 / 模型未遵守 | 检查 prompt 是否明确要求"vendor 自家方案白皮书必须显式标注立场" |
| book 产物缺章节末尾的"小结 / 思考题 / 参考文献" | PDF 原本就无这些章节 **或** 模型未保留 | 若是教材类书籍应自检 WARN；检查 prompt 是否完整加载 |
| book 产物缺索引 term → page 列表 | PDF 无索引章节 **或** 模型未保留 | 预期行为（如 PDF 无索引）；检查 prompt 是否完整加载 |
| INFO: `--refine-figures` / `--thumbnail` 在 full 模式是哑参数 | 期望行为 | full 模式不消费这两个 flag。要 PNG 跑 paper quick 模式或 `--extract-figures` |

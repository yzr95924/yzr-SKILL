---
name: gemini-paper-summary
description: 用 Gemini 多模态读 PDF 论文并按 6 段 ## + 3 段 ### 学术结构化模板输出中文 Markdown 总结（一句话速览/研究动机/方法/关键结果/贡献与开源与局限/高频引用），默认中文主语、必要时保留英文术语避免歧义。在用户给出一篇本地 PDF 论文想要快速生成结构化总结、需要在多篇论文里批量过稿、或想用 Gemini 读论文（不抽 OCR）时使用。不适用：非 PDF 来源、要求逐字翻译全文、仅做关键词抽取等。
metadata:
  author: Zuoru YANG
  modify time: 2026-06-14
  category: paper-reading
---

# Gemini Paper Summary

用 Gemini 多模态长上下文直接"读懂"PDF 论文（含图表、公式），按固定的 6 段 ## + 3 段 ### 学术
结构化模板输出**中文 Markdown 总结**。agent 可以直接调用本 skill 的脚本做单篇
或批量总结，也可以按 `references/api-quickstart.md` 在会话内自行调用 SDK。

> 依赖：Python ≥ 3.6、`google-genai`（`pip install -U google-genai`）、
> 环境变量 `GEMINI_API_KEY`（在 [Google AI Studio](https://aistudio.google.com/apikey) 创建）。
> 详细的依赖与失败排查见文末"前置条件"。

## 何时使用 / 不使用

### 使用

- 用户给出一篇**本地 PDF 论文**，要一份中文结构化总结
- 用户要在多篇论文里**批量过稿**，每篇 600–1200 字的速读
- 论文含大量图表 / 公式，纯文本抽取（pdftotext / PyPDF2）会丢信息
- 用户希望用 Gemini 直接读 PDF，而不是先 OCR

### 不使用

- 论文不是 PDF（网页、Markdown、纯文本）——先转 PDF 或改用其他 skill
- 需要**逐字翻译 / 复刻全文**（本 skill 是"总结"，不是翻译）
- 需要**对比多篇论文**——本 skill 一次一篇，多篇请调用多次再人工拼接
- 只想抽关键句、抽取式摘要——本 skill 是生成式结构化总结
- 用户不愿或不能提供 `GEMINI_API_KEY`

## 输入 / 输出

### 输入

| 字段 | 必选 | 说明 |
| --- | --- | --- |
| PDF 路径 | ✓ | 本地 `.pdf` 文件，绝对或相对路径均可 |
| `GEMINI_API_KEY` | ✓ | 环境变量 |
| 模型 ID | ✗ | 默认 `gemini-3.5-flash`；可传 `--model` 覆盖 |
| 关注点 | ✗ | `--focus "重点关注实验部分"` 之类，会追加到 prompt |
| 输出路径 | ✗ | `--output` 写文件；不传则打印到 stdout |
| 模板 | ✗ | `--template academic`（默认） |
| 提取图片 | ✗ | `--extract-figures` 把关键图截成图片嵌入 Markdown；详见下文 A' |
| 渲染倍率 | ✗ | `--figure-dpi 2.0`（默认 2.0 = 144 DPI），仅 `--extract-figures` 启用时生效 |
| 图片格式 | ✗ | `--figure-format {png,webp,jpeg}`，默认 png；webp/jpeg 时可用 `--figure-quality` 压缩 |
| 压缩质量 | ✗ | `--figure-quality 1-100`，默认 85；仅 webp/jpeg 生效 |
| 像素上限 | ✗ | `--max-width N`，渲染后等比缩放到 ≤ N px 宽；None 不限制 |
| 体积上限 | ✗ | `--max-size-kb N`，超 N KB 自动降级（quality → format → scale）；None 不限制 |
| 缩略图 | ✗ | `--thumbnail` 额外生成缩略图；`--thumbnail-width`（默认 400px）控制宽度 |
| Stage 2 视觉定位 | ✗ | `--refine-figures / --no-refine-figures`（默认 True），详见下文 A' §Stage 2 |
| Stage 2 渲染倍率 | ✗ | `--refine-dpi 2.0`，仅 `--refine-figures` 启用时生效 |

### 输出

固定 **6 段 ## 级 + 3 段 ### 级子小节** 的 Markdown，**600–1500 字**。
"贡献与创新点 / 开源实现 / 局限与未来工作"已合并到 `## 贡献、开源与局限` 下面，
用 ### 子小节呈现。**默认中文**（标题、叙述、连接词），但术语、模型名、产品名、库名等
必要时**直接保留英文**（详见下文核心原则 #4）：

```markdown
# <论文标题> - 阅读总结

## 一句话速览
...

## 研究问题 / 动机
...

## 方法
...
**关键架构图 / 示意图**：（若论文含关键图，参见核心原则 #5）
- ![图 N：<图标题>](PDF p.<页码>) — <1-2 句说明>

## 关键结果
...

## 贡献、开源与局限
### 贡献与创新点
...
### 开源实现            （若无任何链接则整个 ### 子小节省略；参见核心原则 #7）
...
### 局限与未来工作
...

## 高频引用 / Take-aways
（若引言 / 相关工作存在，参见核心原则 #6；以表格形式给出 3-8 条）

## 启发 / 追问
（无关注点时省略）
```

完整模板见 `assets/prompt-template.md`。

## 执行原则 / 边界

### 核心原则

1. **PDF 原文直接喂 Gemini，不要先抽文本**
   - 用 `Part.from_bytes(data=<bytes>, mime_type="application/pdf")` 走多模态
   - 不用 pdftotext / PyPDF2 / pdfplumber 之类先抽纯文本（会丢图表、公式）
2. **结构化总结，不是复述**
   - 6 段 ## + 3 段 ### 的固定骨架，每篇 600–1500 字
   - 关键数据 / 数值必须保留，避免泛泛而谈
3. **忠于原文，不脑补**
   - 论文没说就标"原文未明确"
   - 引用结论时点明出处（如"见 4.2 实验部分"）
4. **不强制全中文：英文该留就留**
   - 输出主语言仍是中文，但以下五类**直接保留英文**，不要硬译：
     - 学术专有名词 / 方法名：Transformer、RLHF、LoRA、Mixture-of-Experts、Beam Search
     - 模型 / 产品 / 工具名：Gemini、GPT-4、Claude、PyTorch、vLLM、Hugging Face
     - 库 / API / 文件名：`transformers`、`pip`、`requirements.txt`、`<config>` 字段名
     - 算法 / 协议 / 标准名：Top-p、TCP、gRPC、REST、IEEE 802.11ax
     - 度量 / 缩写 / 专有指标：BLEU、ROUGE、ACL、GPU、FLOPS、perplexity
   - **判定标准**：翻译反而引发歧义、丢失语义、或该英文已是该领域标准用法时，
     无条件保留。中英混排是常态（如"训练使用 LoRA（低秩适配）"）
   - 列表 / 表格中若一项本身就是英文术语，整项保持英文
5. **关键架构图 / 概念示意图：用 (page, fig_num, bbox) 引用插入到 Markdown**
   - 在"方法"小节末尾追加 **关键架构图 / 示意图** 子列表
   - 格式：`![图 N：<图标题或一句话描述>](PDF p.<页码> fig.<N> [bbox=<x0,y0,x1,y1>]) — <1-2 句说明>`
   - `fig.N` 是论文里的 Figure 编号，与 alt 文本中的"图 N"对应
   - `bbox=<x0,y0,x1,y1>`（可选，**强烈建议给**）是图在 PDF 中的边界框，
     单位 PDF point（1 point = 1/72 inch），原点在左上角；A4 ≈ 595×842，Letter ≈ 612×792
   - 启用 `--extract-figures` 时，**脚本会用 bbox 精确截取该图本身**（不是整页！）
   - 若不写 bbox：脚本会在该页按 `Figure N:` caption 自动定位，截取 caption 上方区域
   - 只收录**关键图**：整体架构、核心模块示意、概念流程图、关键对比示意
   - **跳过**纯装饰、坐标轴标注、表格截图、附录图、补充材料中的非核心图
   - 页码以 PDF 实际页码为准（论文首页为 p.1），不要写 "图 1 在第 3 页附近"
   - 正文叙述里要呼应这些图（如"如图 1 所示，..."）
6. **高频引用：抽取 Take-aways 表格**
   - 在"局限与未来工作"与"启发 / 追问"之间追加 **高频引用 / Take-aways** 表格
   - 表格列：`#` / 引用次数（估算）/ 论文（作者-年份 + 标题 + 会议/期刊）/ 一句话核心观点 / 论文中位置
   - 排序按"对本文重要性"或"引用频次"降序，**3-8 条**
   - 重点收录：奠基性工作、近期 SOTA、本文方法的直接前身
   - 剔除一次性提及、自引、与本文方法无直接关系的工作
   - 会议/期刊用领域惯用缩写（NeurIPS / ICML / SIGMOD / VLDB / ICDE / OSDI / TODS / VLDBJ 等），
     不确定时按论文 PDF 中参考文献列表里的写法
   - 论文没有引言 / 相关工作章节时（如短文、纯实验报告），整段省略
7. **开源实现：抽取 prototype / 数据集 / demo 链接**
   - 在"贡献与创新点"之后、"局限与未来工作"之前追加 **开源实现** 小节
   - 链接**只从论文正文 / 脚注 / 参考列表里提取**，绝不编造
   - 格式：`- **代码仓库**：<URL>（简述：实现语言 / 仓库活跃度）`、`- **数据集**：...`、`- **在线 Demo**：...`
   - 链接类型不明确时（如脚注里的 project page）归到"代码仓库"那行
   - 若有多个相关链接，可加多行（如 paper-website、video、slides）
   - 论文**完全未提**任何 prototype 链接时，**整段省略**（不要写"无开源"或占位文本）
8. **模型选择**
   - 默认 `gemini-3.5-flash`（2026-05 稳定版，质量与成本平衡，支持 PDF + 1M 上下文）
   - 复杂论文可换 `gemini-3.1-pro-preview`（preview，质量更高但成本高）
   - 速览批量过稿可换 `gemini-3.1-flash-lite`（更便宜）
   - 实际可用模型以当前 Gemini 文档为准：用 `gemini-api-docs-mcp` 的 `get_current_model` 核实

### 边界

- 只处理本地 PDF；非 PDF 一律先转 PDF
- 不做全文翻译；不做多篇对比
- 一次一篇论文
- 单 PDF 大小建议 ≤ 50 MB（File API 硬上限）

## 工作流 / 步骤

### A. agent 在会话中调用（推荐流程）

```text
1. 确认 PDF 存在且可读
2. 确认 GEMINI_API_KEY 已设置；未设置则提示用户去 aistudio.google.com/apikey 申请
3. 确认 google-genai 已安装：python3 -c "import google.genai" 或 pip install -U google-genai
4. 调用 scripts/gemini_paper_summary.py：
   python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
     --pdf <path> \
     --output <path-to-md>  # 可省，省略则打印到 stdout
5. 把生成的 Markdown 总结呈现给用户
6. 标注所用模型与论文文件名
```

也可以直接在会话里调 SDK（API 细节见 `references/api-quickstart.md`）。

### A'. 导出关键架构图（推荐做法）

启用 `--extract-figures` 后，脚本会用 pymupdf **只截取 figure 本身的矩形区域**（而非整页），
并把 Markdown 里的 `(PDF p.X fig.N [bbox=...])` 替换为 `figures/figure-pX-fN.png`。
该模式下 `--output` 视作目录路径，目录结构：

```text
<--output 指定的目录>/
├── summary.md              # 自动写到这里
└── figures/
    ├── figure-p1-f1.png    # Figure 1 在第 1 页
    ├── figure-p4-f4.png    # Figure 4 在第 4 页
    ├── figure-p4-f5.png    # Figure 5 在第 4 页（同页多图各自一张）
    └── figure-p5-f6.png    # Figure 6 在第 5 页
```

`summary.md` 中的图引用形如：

```markdown
- ![图 1：自适应基数树节点](figures/figure-p1-f1.png) — 展示了 ART 如何...
- ![图 4：传统基数树对比](figures/figure-p4-f4.png) — ...
```

**截取逻辑**（按优先级，从高到低）：

1. **Stage 2 Gemini 视觉定位**（仅在 `--refine-figures` 启用时）：把页面渲染成 PNG 送给 Gemini
   多模态，让它**用视觉方式**给出每个 figure 的紧致 bbox + 完整 caption + 是否关键图。
   精度最高，且能自动跳过装饰图/logo/坐标轴/表格。详见下文 §Stage 2。
2. **caption 定位**（本地算法，多策略 fallback）：在该页按 `Figure N:` caption 反向推断 figure 区域——
   - 双栏布局下，根据 caption 的 x 中心判断 figure 所在栏（左 / 右）
   - figure 顶部检测按以下三策略按顺序尝试：
     1. **正文段落底部**：caption 上方最近的"宽+多行"正文段落底部（≥2 行 + 宽度 ≥ 栏宽 60%）。
        处理 figure 上方紧跟正文的常见情形。
     2. **annotation 顶部**：caption 上方同一栏所有"非正文"文本块（figure annotation / label /
        节点编号等"窄+单行"块）的最上 y0。**专门解决 figure 上方只有 annotation 没有正文**
        的情形（如 ART-ICDE'13 第 5 页的 Figure 6，caption 上方全是 B/F/A/O/R/O 节点 label +
        path compression / lazy expansion 标注），避免旧版退到 page 顶把 header 全框进来。
     3. **page 顶兜底**：以上都失败时退到 page 顶（保证 figure 一定被框入，但可能含 page header）
3. **Stage 1 Gemini bbox hint**（仅作最后兜底，精度差）：脚本直接用 Stage 1 prompt 嵌入的
   `bbox=x0,y0,x1,y1` 区域裁剪，不做 caption 校验
4. **定位失败**：跳过该图并在 stderr 打印 WARN；Markdown 里的引用保持原样

**已知边界**（无 Stage 2 时，caption 定位 fallback 兜底）：

- 单栏 PDF：caption 定位工作得很好
- 双栏 PDF：每栏各自裁剪，不会跨栏"吃"另一栏的图
- 同一栏上下相邻多张图：上方那张的 caption 会被识别成"正文段落"（策略 1 命中），
  但如果上方那张**没有正文段落**，策略 2 会用 annotation 顶部避免切错
- 图在页顶（如 page 1 标题下方）：caption 上方通常有正文段落，策略 1 命中；
  完全没正文时策略 2 仍可能框到 page header，需要 Stage 2 精修

> **推荐始终启用 `--refine-figures`**（默认开）：Stage 2 用 Gemini 看图直接给精确 bbox，
> 上述三个边界问题基本消失；唯一代价是每张引用页多一次 Gemini 调用 + ~5-15s 延迟。

#### Stage 2: Gemini 视觉定位精修（默认开启）

Stage 1 拿到 `PDF p.X fig.N` 引用后,Stage 2 把对应页面渲染成 PNG 送给 Gemini,**用视觉方式**
给出每个 figure 的精确边界 + 完整 caption,直接从源头解决三个老问题:

| 老问题 | Stage 2 怎么解决 |
| --- | --- |
| 边界不准确 | Gemini 看渲染图直接给归一化 0-1000 bbox,按图像像素精确定位,不再是基于 PDF 内容的估算 |
| 图片标题残缺 | Gemini 直接读出图片下方完整 caption(含多行),覆盖 Stage 1 LLM 生成的残缺 alt |
| 上方留白过多 | Gemini 自动判断 figure 顶部边界,不会把页眉/标题/作者框进来 |

**Stage 2 流程**：

```text
Stage 1 输出: "见 PDF p.3 fig.1 / PDF p.4 fig.2 ..."
   ↓
1) 把 p.3 / p.4 渲染成 PNG(默认 2x DPI;改用 --refine-dpi 调整)
   ↓
2) 每页一次 Gemini 调用,prompt 要求返回 JSON:
   { "page": 3, "figures": [
       { "fig_num": 1, "bbox_2d": [ymin,xmin,ymax,xmax],
         "full_caption": "Figure 1: ...",
         "is_key_figure": true }, ...
   ]}
   ↓
3) 把 Gemini 返回的 0-1000 bbox 换算为 PDF point:
   x_pt = x_norm * page.rect.width / 1000
   ↓
4) 用 Stage 2 bbox 替换 Stage 1 提示词里的 bbox hint,再做后续裁剪
5) 把 Stage 2 读出的完整 caption 覆盖 Markdown 里残缺的 alt 文本
```

**坐标约定**(Gemini 官方 `gemini-robotics-er-1.6-preview` 同款):

- `bbox_2d = [ymin, xmin, ymax, xmax]`(y 在前)
- 归一化 0-1000 整数
- 原点在图像左上角
- 渲染图未做宽高变形 → 1000 ↔ 页面 PDF point 的宽/高

**Stage 2 参数**:

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--refine-figures` / `--no-refine-figures` | `True` | 是否启用 Stage 2。关闭后回到 Stage 1 bbox hint + 本地 caption 定位 |
| `--refine-dpi` | `2.0` | Stage 2 渲染页面的 DPI 倍率。增大可提升定位精度但增加 token 成本 |

**Stage 2 失败行为**(单页失败不影响其他页):

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `INFO: Stage 2 第 X 页 第 N/3 次失败,2s 后重试...` | 临时错误 (503/429/500/502/504) | 自动退避重试 2s / 4s,最多 3 次 |
| `WARN: Stage 2 第 X 页 Gemini 调用失败` | 重试 3 次仍失败 / 永久错误 (400/401/403/404) | 该页退回 caption 定位(策略 1/2/3 自动选最优),其他页继续 |
| `WARN: Stage 2 第 X 页 Gemini 返回为空` | 模型无输出 | 同上 |
| `INFO: Stage 2 第 X 页 Figure N 标记为非关键图,跳过` | Gemini 判断为装饰/logo/表格 | 该 fig 不裁剪,沿用 Stage 1 流程 |
| `WARN: 第 X 页 Figure Y 未找到 caption/visual bbox` | Stage 2 失败 + caption 三策略都未命中 | 走 Stage 1 bbox hint 兜底 |

**Stage 2 重试机制**(临时错误自愈):

- 默认 3 次尝试,指数退避 (2s, 4s)
- 临时错误 (`429 / 500 / 502 / 503 / 504`) 触发重试
- 永久错误 (`400 / 401 / 403 / 404`) 立即放弃(重试也没用)
- 网络异常 / 超时也走重试路径(无 `status_code` 时一律重试)

**Stage 2 成本**:

- 多 N 次 Gemini 调用(N = 引用 figure 的页面去重数,通常 2-5 页)
- 每页输入 ~1k token(image + prompt)+ 输出 ~200 token
- 延迟:每页 ~5-15s(串行)
- 用 `--no-refine-figures` 可完全跳过

#### 大小 / 格式 / 缩略图控制（仅在 `--extract-figures` 启用时生效）

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--figure-format` | `{png,webp,jpeg}` | `png` | 输出格式。WebP/JPEG 有损压缩，体积更小 |
| `--figure-quality` | int 1-100 | `85` | WebP/JPEG 质量（pymupdf 内部用 `jpg_quality`），PNG 无效 |
| `--max-width` | int | None | 最大宽度（像素）。超过则等比缩放；None 不限制 |
| `--max-size-kb` | int | None | 最大体积（KB）。超限自动降级：先降 quality → 再换格式（PNG→WebP）→ 再降 scale |
| `--thumbnail` | flag | 关 | 同时生成缩略图，Markdown 引用缩略图、点击跳原图 |
| `--thumbnail-width` | int | `400` | 缩略图宽度（像素） |

**自动 fallback**：

- `--figure-format=jpeg` 但图含 alpha 通道（`pix.alpha=1`）→ 自动改用 WebP 并 stderr 提示
- `--max-size-kb` 降级到最低规格仍超限 → 保留当前结果，stderr 打 WARN（不无限循环）

**缩略图目录结构**：

```text
<--output 指定的目录>/
├── summary.md
└── figures/
    ├── figure-p1-f1.png         # 原图（与 --figure-format 对应）
    ├── figure-p1-f1.thumb.png   # 缩略图
    └── ...
```

注意：缩略图**不**走 `figures/thumbnails/` 子目录，而是与原图并列 + `.thumb` 后缀，
方便一对图片保持目录一致。缩略图**不**应用 `--max-width`（`thumbnail-width` 自带尺寸上限），
但仍受 `--max-size-kb` 约束（缩略图也可能意外偏大）。

**Markdown 引用形式**：

- 默认模式：`![图 1：xxx](figures/figure-p1-f1.png)`
- 缩略图模式：`[![图 1：xxx](figures/figure-p1-f1.thumb.png)](figures/figure-p1-f1.png)`

完整调用：

```bash
# 1) 先装 pymupdf（一次性）
pip install --user --break-system-packages pymupdf

# 2) 一次性跑通：Stage 1 总结 + Stage 2 视觉定位 + 裁剪 + 路径替换 + 写文件
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf \
  --output ~/papers/summaries/attention \
  --extract-figures
# --refine-figures 默认开启;想完全跳过 Stage 2 加 --no-refine-figures
```

`--figure-dpi` 可改最终输出图的渲染倍率（默认 2.0 = 144 DPI；想要更清晰用 3.0 / 4.0）；
`--refine-dpi` 单独控制 Stage 2 喂给 Gemini 看的渲染倍率（同样默认 2.0）。

> 总结里没有 `PDF p.X fig.N` 引用时，`--extract-figures` 不会报错，只是不导出图。

#### Stage 2 对照实验

把 Stage 2 关闭,与开启的产物做视觉对比:

```bash
# 开启 Stage 2(默认)
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf --output ~/out_with_stage2 \
  --extract-figures

# 关闭 Stage 2
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf --output ~/out_without_stage2 \
  --extract-figures --no-refine-figures

# 对比每张图
ls -la ~/out_with_stage2/figures/ ~/out_without_stage2/figures/
```

### B. 批量速览

```text
1. 列出目录下所有 *.pdf
2. 对每篇并行（或限流并发）调用 gemini_paper_summary.py
3. 每篇输出文件名 <paper-stem>.summary.md，放在同目录
4. 结束时汇总哪些论文成功 / 失败
```

### C. 故障排查

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `ModuleNotFoundError: google.genai` | SDK 未装 | `pip install --user --break-system-packages google-genai` |
| `--extract-figures` 报 "需要 pymupdf" | pymupdf 未装 | `pip install --user --break-system-packages pymupdf` |
| `DefaultCredentialsError` / `api_key not set` | 缺 `GEMINI_API_KEY` | `export GEMINI_API_KEY=...` 或 `.env` + `direnv` |
| `400 INVALID_ARGUMENT` + `mime type` 报错 | PDF 损坏 / 加密 / 非 PDF 头 | 用 `file <pdf>` 核实；解密或重新下载 |
| `413 REQUEST_TOO_LARGE` | PDF 超 50 MB | 走 File API 上传（见 `references/api-quickstart.md` §超大 PDF） |
| 模型 404 | 模型名拼错或已下线 | 用 `gemini-api-docs-mcp` 的 `get_current_model` 查当前可用模型 |
| 输出空 / 截断 | 输出 token 上限（默认 65k）撞顶 | 减小 `max_output_tokens` 不会影响——缩短 prompt 或换模型 |

## 参考样例

### 样例一：单篇总结

**用户**："帮我把 `~/papers/attention_is_all_you_need.pdf` 总结成中文"

**执行**：

```bash
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention_is_all_you_need.pdf \
  --output ~/papers/attention_is_all_you_need.summary.md
```

把生成的 `.summary.md` 内容呈现给用户，注明 `模型=gemini-3.5-flash`。

### 样例二：带关注点

**用户**："总结 `~/papers/diffusion.pdf`，重点看数学推导和采样效率"

**执行**：

```bash
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/diffusion.pdf \
  --focus "重点关注数学推导的关键步骤和采样效率优化" \
  --output ~/papers/diffusion.summary.md
```

生成的总结会在"方法 / 关键结果"小节侧重，并在末尾补"启发 / 追问"小节。

### 样例三：批量速览

**用户**："~/papers/ 下面有 20 篇 PDF，帮我每篇 300 字速读一下"

**执行**：

```bash
for pdf in ~/papers/*.pdf; do
  python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
    --pdf "$pdf" \
    --model gemini-3.1-flash-lite \
    --focus "300 字内的速览版" \
    --output "${pdf%.pdf}.summary.md"
done
```

### 样例四：导出关键架构图（让 Markdown 预览能直接看到图）

**用户**："总结 `~/papers/attention.pdf`,关键架构图要能直接看到"

**执行**：

```bash
# 一次性：Gemini 总结 + 渲染关键页为 PNG + 替换 Markdown 引用 + 写文件
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf ~/papers/attention.pdf \
  --output ~/papers/summaries/attention \
  --extract-figures
```

产出：

```text
~/papers/summaries/attention/
├── summary.md
└── figures/
    ├── figure-01-p1.png
    ├── figure-02-p3.png
    └── figure-03-p5.png
```

`summary.md` 中的图引用全部变为相对路径（`figures/figure-01-p1.png`），
在 VS Code / Obsidian / GitHub 等任何 Markdown 预览器里都能直接看到图。

## 前置条件

- **Python ≥ 3.6**（脚本遵循仓库 3.6 兼容规范）
- **`google-genai` Python SDK**（旧 `google-generativeai` 已弃用，请用新包）：
  `pip install -U google-genai`（Debian/WSL 系统 Python 加 `--break-system-packages`）
- **`pymupdf`**（**软依赖**，仅启用 `--extract-figures` 时需要）：
  `pip install --user --break-system-packages pymupdf`
- **`GEMINI_API_KEY`**：
  在 [Google AI Studio](https://aistudio.google.com/apikey) 创建后
  `export GEMINI_API_KEY="你的 key"`
- **可读 PDF 文件**：单文件 ≤ 50 MB；如需处理更大文件改用 File API
  （`references/api-quickstart.md` §超大 PDF）

## 参考文档

- [Gemini API 文档](https://ai.google.dev/gemini-api/docs)
- [google-genai Python SDK](https://github.com/googleapis/python-genai)
- 仓库内 `yzr-skill-creator/`（skill 写作规范）
- 仓库内 `design-doc-edit/`（Markdown 写作规范同源，行宽 ≤ 120）

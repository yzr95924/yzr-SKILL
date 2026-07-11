# Figure 引用与导出规范

> 本文是 `SKILL.md` §输入/输出 + §执行原则 #5 + §工作流 A' 的深度规范。
> 聚焦 **算法原理、边界情况、引用形态对照表**——不重复 SKILL.md 已有的"截取逻辑三优先级"决策树与"何时启用 `--extract-figures`"工作流。
> 详细 Stage 2 / 大小格式 / 缩略图参数见 [`references/figure-processing.md`](./figure-processing.md)。

## 1. 三阶段定位原理

> **本节是 Stage 编号 + bbox 阈值的唯一真源（SSOT）**。SKILL.md §工作流 A' / §边界 / §执行原则 #5 引用本节。
> 按精度从高到低，脚本 `render_figures_to_pngs` 的 fallback 链——三个名字在文档全文统一：
> **Stage 2** (Gemini 视觉定位) / **caption locator** / **bbox hint fallback**。

### Stage 2（默认开启）：Gemini 视觉定位

- 把 p.X 渲染成 PNG（默认 `--refine-dpi 2.0`）送 Gemini 多模态
- 返回归一化 0-1000 bbox `[ymin, xmin, ymax, xmax]`，换算到 PDF point
- 同时返回 `is_key_figure`（过滤 logo/表格/装饰图）
- 临时错误 `429/500/502/503/504` 走指数退避（2s/4s，最多 3 次）
- 永久错误 `400/401/403/404` 立即放弃，退 caption locator

### caption locator（本地算法，三策略 fallback）

- 双栏布局按 caption 中心 x 判断 figure 所在栏（左 / 右）
- figure 顶部三策略按顺序尝试：
  1. **正文段落底部**：caption 上方最近的"宽+多行"正文段落底部（≥ 2 行 + 宽度 ≥ 栏宽 60%）
  2. **annotation 顶部**：caption 上方同一栏所有"非正文"文本块（figure annotation / label /
     节点编号等"窄+单行"块）的最上 y0。**专门解决 figure 上方只有 annotation 没有正文**的情形
     （如 ART-ICDE'13 第 5 页的 Figure 6，caption 上方全是 B/F/A/O/R/O 节点 label +
     path compression / lazy expansion 标注），避免旧版退到 page 顶把 header 全框进来
  3. **page 顶兜底**：以上都失败时退到 page 顶（保证 figure 一定被框入，但可能含 page header）

### bbox hint fallback（精度差，最后兜底）

- 直接用 Stage 1 prompt 嵌入的 `bbox=x0,y0,x1,y1` 区域裁剪，不做 caption 校验
- **bbox sanity check**（2026-06-21，**SSOT**）：Stage 1 Gemini 自由发挥写 `bbox=...` 时
  容易把 figure 下面紧跟的整段正文都框进去（典型 case：p.11 Fig 16，hint 高 ~375pt，
  实际图只有 ~150pt）。`render_figures_to_pngs` 在走 bbox hint fallback 前先检查高度：
  超过 **250pt** 且 caption locator 能算出更紧的 bbox（**≥ 50pt**）时，用 caption locator 替掉 hint

### 三层全失败的处置

- 整张图从 markdown 删除 + 剥掉前一句"如图 N 所示"/"见图 N"/"Figure N 展示了..."等独立呼应句的图编号引用（保留描述文字）
- **不**保留 `![图 N: ...](PDF p.X fig.N ...)` 这种没替换的 PDF reference 字符串——outline 渲染会成**破图**（`![]()` 协议 outline 不识别）
- 脚本日志：`INFO: 跳过 N 张图（Stage 2 + caption locator + bbox hint 三层均失败），已从 markdown 删除对应行 + 呼应句`

## 2. caption 甄别 vs 正文引用

正文常出现 `Figure 16 shows that...` 这类引用，line 文本以 `Figure N` 开头。
原 `find_figure_caption` 简单正则会被这种正文引用命中，返回正文 block 的 bbox（而非真 caption），导致 caption locator 把整段正文当成 figure 区域。

**判定规则**：line 文本必须以 `Figure N[.:]` + 描述形式才算 caption（`Figure 16 shows...` 中数字后是空格+动词，会被过滤掉）。
**辅助判定**：line 长度 ≤ 120 字符。

## 3. alt 字段写法（v3.2 终版）

**图片不包含 caption**（v3.2 终版）：caption 写到 markdown image 的 alt 字段——

```markdown
![图 N: <中文翻译+总结>](<url> "=WxH")
```

是 outline UI 唯一渲染为图片下方 caption 文字的通道。

`=WxH` 由脚本 `embed_figure_refs` 在 `render_figures_to_pngs` 拿到精确像素尺寸后自动注入。

## 4. 三阶段 image 引用形态对照

同一 image 引用在 3 个阶段的不同形态：

| 阶段 | 形态 |
| --- | --- |
| Gemini 输出 | `![图 N: <中文翻译+总结>](PDF p.<页> fig.<N> bbox=<x0,y0,x1,y1>)` |
| 脚本 `--extract-figures` 处理后 | `![图 N: <中文翻译+总结>](figures/figure-pX-fN.png "=WxH")` |
| 推到 outline 后 | `![图 N: <中文翻译+总结>](/api/attachments.redirect?id=<uuid> "=WxH")` |

`fig.N` 是论文里的 Figure 编号，与 alt 文本中的"图 N"对应。

## 5. bbox 单位约定

- `bbox=x0,y0,x1,y1` 单位 PDF point（1 point = 1/72 inch）
- 原点在 PDF 左上角
- A4 ≈ 595×842，Letter ≈ 612×792
- 页码以 PDF 实际页码为准（论文首页为 p.1），不要写"图 1 在第 3 页附近"

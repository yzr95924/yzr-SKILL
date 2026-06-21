# Figure 处理细节（Stage 2 / 大小格式 / 缩略图）

> 本文是 `SKILL.md` §工作流 A' 的深度规范。
> 读 SKILL.md 触发 `Stage 2` / `--figure-format` / `--thumbnail` 相关决策时来读本文。
> 算法原理、caption 甄别、bbox sanity check 见 [`references/figure-extraction.md`](./figure-extraction.md)。

## 1. Stage 2: Gemini 视觉定位精修（默认开启）

Stage 1 拿到 `PDF p.X fig.N` 引用后，Stage 2 把对应页面渲染成 PNG 送给 Gemini，**用视觉方式**给出每个 figure 的精确边界 + 完整 caption，直接从源头解决三个老问题：

| 老问题 | Stage 2 怎么解决 |
| --- | --- |
| 边界不准确 | Gemini 看渲染图直接给归一化 0-1000 bbox，按图像像素精确定位，不再是基于 PDF 内容的估算 |
| 图片标题残缺 | Gemini 直接读出图片下方完整 caption（含多行），覆盖 Stage 1 LLM 生成的残缺 alt |
| 上方留白过多 | Gemini 自动判断 figure 顶部边界，不会把页眉/标题/作者框进来 |

### Stage 2 流程

```text
Stage 1 输出: "见 PDF p.3 fig.1 / PDF p.4 fig.2 ..."
   ↓
1) 把 p.3 / p.4 渲染成 PNG（默认 2x DPI；改用 --refine-dpi 调整）
   ↓
2) 每页一次 Gemini 调用，prompt 要求返回 JSON：
   { "page": 3, "figures": [
       { "fig_num": 1, "bbox_2d": [ymin, xmin, ymax, xmax],
         "full_caption": "Figure 1: ...",
         "is_key_figure": true }, ...
   ]}
   ↓
3) 把 Gemini 返回的 0-1000 bbox 换算为 PDF point：
   x_pt = x_norm * page.rect.width / 1000
   ↓
4) 用 Stage 2 bbox 替换 Stage 1 提示词里的 bbox hint，再做后续裁剪
5) 把 Stage 2 读出的完整 caption 覆盖 Markdown 里残缺的 alt 文本
```

### 坐标约定（Gemini 官方 `gemini-robotics-er-1.6-preview` 同款）

- `bbox_2d = [ymin, xmin, ymax, xmax]`（y 在前）
- 归一化 0-1000 整数
- 原点在图像左上角
- 渲染图未做宽高变形 → 1000 ↔ 页面 PDF point 的宽/高

### Stage 2 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--refine-figures` / `--no-refine-figures` | `True` | 是否启用 Stage 2。关闭后回到 Stage 1 bbox hint + 本地 caption 定位 |
| `--refine-dpi` | `2.0` | Stage 2 渲染页面的 DPI 倍率（脚本 argparse 默认值见 `scripts/gemini_paper_summary.py:1191`）。增大可提升定位精度但增加 token 成本 |

### Stage 2 失败行为（单页失败不影响其他页）

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `INFO: Stage 2 第 X 页 第 N/3 次失败，2s 后重试...` | 临时错误 (503/429/500/502/504) | 自动退避重试 2s / 4s，最多 3 次 |
| `WARN: Stage 2 第 X 页 Gemini 调用失败` | 重试 3 次仍失败 / 永久错误 (400/401/403/404) | 该页退回 caption 定位（策略 1/2/3 自动选最优），其他页继续 |
| `WARN: Stage 2 第 X 页 Gemini 返回为空` | 模型无输出 | 同上 |
| `INFO: Stage 2 第 X 页 Figure N 标记为非关键图，跳过` | Gemini 判断为装饰/logo/表格 | 该 fig 不裁剪，沿用 Stage 1 流程 |
| `WARN: 第 X 页 Figure Y 未找到 caption/visual bbox` | Stage 2 失败 + caption 三策略都未命中 | 走 Stage 1 bbox hint 兜底 |

### Stage 2 重试机制（临时错误自愈）

- 默认 3 次尝试，指数退避（2s, 4s）
- 临时错误（`429 / 500 / 502 / 503 / 504`）触发重试
- 永久错误（`400 / 401 / 403 / 404`）立即放弃（重试也没用）
- 网络异常 / 超时也走重试路径（无 `status_code` 时一律重试）

### Stage 2 成本

- 多 N 次 Gemini 调用（N = 引用 figure 的页面去重数，通常 2-5 页）
- 每页输入 ~1k token（image + prompt）+ 输出 ~200 token
- 延迟：每页 ~5-15s（串行）
- 用 `--no-refine-figures` 可完全跳过

> **推荐始终启用 `--refine-figures`**（默认开）：Stage 2 用 Gemini 看图直接给精确 bbox，上述三个边界问题基本消失；唯一代价是每张引用页多一次 Gemini 调用 + ~5-15s 延迟。

## 2. 大小 / 格式 / 缩略图控制（仅在 `--extract-figures` 启用时生效）

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--figure-format` | `{png,webp,jpeg}` | `png`（脚本 `line 1146`） | 输出格式。WebP/JPEG 有损压缩，体积更小 |
| `--figure-quality` | int 1-100 | `85`（脚本 `line 1152`） | WebP/JPEG 质量（pymupdf 内部用 `jpg_quality`），PNG 无效 |
| `--max-width` | int | None | 最大宽度（像素）。超过则等比缩放；None 不限制 |
| `--max-size-kb` | int | None | 最大体积（KB）。超限自动降级：先降 quality → 再换格式（PNG→WebP）→ 再降 scale |
| `--thumbnail` | flag | 关 | 同时生成缩略图，Markdown 引用缩略图、点击跳原图 |
| `--thumbnail-width` | int | `400`（脚本 `line 1175`） | 缩略图宽度（像素） |
| `--figure-dpi` | float | `2.0`（脚本 `line 1140`） | 最终输出图的渲染倍率（`2.0 = 144 DPI`；想要更清晰用 `3.0 / 4.0`） |

### 自动 fallback

- `--figure-format=jpeg` 但图含 alpha 通道（`pix.alpha=1`）→ 自动改用 WebP 并 stderr 提示
- `--max-size-kb` 降级到最低规格仍超限 → 保留当前结果，stderr 打 WARN（不无限循环）

### 缩略图目录结构

```text
<--output 指定的目录>/
├── summary.md
└── figures/
    ├── figure-p1-f1.png         # 原图（与 --figure-format 对应）
    ├── figure-p1-f1.thumb.png   # 缩略图
    └── ...
```

注意：缩略图**不**走 `figures/thumbnails/` 子目录，而是与原图并列 + `.thumb` 后缀，方便一对图片保持目录一致。缩略图**不**应用 `--max-width`（`thumbnail-width` 自带尺寸上限），但仍受 `--max-size-kb` 约束（缩略图也可能意外偏大）。

### Markdown 引用形式

- 默认模式：`![图 1：xxx](figures/figure-p1-f1.png)`
- 缩略图模式：`[![图 1：xxx](figures/figure-p1-f1.thumb.png)](figures/figure-p1-f1.png)`

> 总结里没有 `PDF p.X fig.N` 引用时，`--extract-figures` 不会报错，只是不导出图。

## 3. Stage 2 对照实验

把 Stage 2 关闭，与开启的产物做视觉对比：

```bash
# 开启 Stage 2（默认）
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
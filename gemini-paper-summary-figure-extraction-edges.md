# gemini-paper-summary 图片提取边界与设计决策

> MEMORY 索引:见 `MEMORY.md`。本文是正文,记录 2026-06-15 「优化 PDF 图片提取」会话沉淀下来的
> 「为什么 + 边界规则」。代码在 `gemini-paper-summary/scripts/gemini_paper_summary.py`,文档在
> `gemini-paper-summary/SKILL.md`。

## 1. 为什么需要 Stage 2 Gemini 视觉定位

**Why:** Stage 1 让 Gemini 直接读 PDF 原内容时给出的 bbox 是**基于语义估算的**(Gemini 看不到真实
像素坐标),精度差;本地 caption 定位的旧启发式("≥2 行 + 宽度 ≥ 栏宽 60%"的"正文段落")在
**figure 上方只有 annotation / label**(没有正文段落)时会**退到 page 顶**,把 page header 全
框进来,造成大量上方留白(典型 case: ART-ICDE'13 第 5 页的 Figure 6)。

Gemini **看渲染图时视觉定位能力才强**(类似 grounded detection),必须把页面渲染成 PNG 送过去
它才能精确给 bbox。

**How to apply:** 任何对 PDF 图片提取的优化,优先考虑让多模态模型**看渲染图**,而不是让它从
PDF 文本流估算像素位置。

## 2. Stage 2 坐标约定:归一化 0-1000

**Why:** Gemini 官方(`gemini-robotics-er-1.6-preview` 文档)约定的 bbox 格式是
`[ymin, xmin, ymax, xmax]` + 归一化 0-1000 整数 + 原点左上。仓库 PDF 场景需要把归一化坐标
换算为 PDF point 才能喂给 pymupdf。

**关键洞察:** 页面渲染图(pymupdf 按 2x DPI 渲染)未做宽高变形,因此归一化 0-1000 直接映射到
页面的 PDF point 宽/高。**换算与 dpi_scale 无关**(放大是等比的,归一化抵消了 scale)。

```python
x0_pt = xmin_norm * page.rect.width / 1000.0
y0_pt = ymin_norm * page.rect.height / 1000.0
```

**How to apply:** 任何"图像 bbox → PDF 坐标"的换算,只要渲染图未做宽高变形(标准
pymupdf 渲染就是),归一化 0-1000 ↔ PDF point 是最简洁的桥梁。

## 3. 为什么 Stage 2 需要重试机制

**Why:** Gemini API 经常返回**临时错误**(`503 UNAVAILABLE` 高并发、`429 RESOURCE_EXHAUSTED`
限流、`500 INTERNAL`),这些重试大概率成功。但永久错误(`400/401/403/404`)重试毫无意义。

**How to apply:**

- 默认 3 次尝试,指数退避 2s / 4s
- 临时错误 (`429/500/502/503/504`) 走重试
- 永久错误 (`400/401/403/404`) 立即抛出不重试
- 无 `status_code` 的异常(网络超时等)也走重试

实现位置:`gemini-paper-summary/scripts/gemini_paper_summary.py` 的 `_call_gemini_with_retry`。

## 4. 为什么 caption 定位 fallback 必须分多策略

**Why:** 单一启发式("宽+多行正文段落")覆盖不全。论文里 figure 上方有几种情形:

| figure 上方有什么 | 旧启发式行为 | 新策略行为 |
| --- | --- | --- |
| 紧跟一段正文 | ✓ 命中 | ✓ 策略 1 命中 |
| 只有 figure annotation / label | ✗ 退到 page 顶 | ✓ 策略 2 命中(annotation 顶部) |
| 完全没内容(图紧贴 caption) | ✗ 退到 page 顶 | ✓ 策略 2 用 caption 上方块的 y0 |

**典型 case:** ART-ICDE'13 第 5 页 Figure 6,caption 上方全是 B/F/A/O/R/O 节点 label +
"path compression / lazy expansion / merge one-way node" 等 annotation(全部"窄 + 单行"),
**没有宽+多行的正文段落**,旧算法退到 y=0 把整页 header 全框进来;新策略 2 命中 annotation
顶部 y=70.7,边界精确。

**How to apply:**

- 策略 1(正文段落底部):用于最常见情形,优先尝试
- 策略 2(annotation 顶部):兜底,只要 caption 上方同栏有任意文本块就用其最上 y0
- 策略 3(page 顶):最后兜底,保证图被框入但可能有 header

实现位置:`gemini-paper-summary/scripts/gemini_paper_summary.py` 的 `find_figure_bbox_by_caption`。

## 5. 为什么让 Gemini 同时判断 `is_key_figure`

**Why:** Stage 1 prompt 已经要求 LLM "跳过装饰图",但 LLM 不一定守约,经常会列 logo /
坐标轴 / 表格截图。让 Gemini 在 Stage 2 **看图**判断"是否关键图",能直接剪掉无意义的裁剪。

**How to apply:** Stage 2 返回的 JSON schema 必含 `is_key_figure: bool`,裁剪前过滤掉 `false`
的项,stderr INFO 告知用户。

## 6. Stage 2 输出的 caption 覆盖 Markdown alt 文本

**Why:** Stage 1 LLM 生成的 alt 文本常是 LLM 自己脑补的"图标题"(可能残缺或与原 caption
不符)。Stage 2 Gemini **看图直接读出**真实 caption,更准。覆盖时**保留**"— <Stage 1 的
1-2 句说明>"后段(这是 Stage 1 的语义信息,Stage 2 没替代品),只替换"图 N:"之后的部分。

**How to apply:** 见 `replace_alt_with_full_caption` 实现。注意保护" — "分隔符后的 role 描述
部分,不要被 Gemini caption 覆盖掉。

## 7. 已知边界 / 不在本次范围

- **不上 Gemini Robotics-ER**:该模型官方支持 bbox 但当前 3.5-flash 在 prompt 引导下也能
  输出 bbox(实测稳定),先用 prompt 方案,后续若不稳再切
- **不做 Stage 2 并发**:每次一页,串行即可;并发是 future work(可能引入复杂限流处理)
- **不改 Stage 1 prompt**:6 段 ## + 3 段 ### 结构化模板已稳定
- **不引入新 pip 依赖**:Stage 2 复用现有 `pymupdf` + `google-genai`
- **双栏 / 单栏通用**:caption x 中心判断栏,只在该栏内做边界检测,避免跨栏"吃"另一栏的图

## 8. 验证方法(端到端 smoke test)

```bash
export GEMINI_API_KEY="..."
# 用 ART-ICDE'13.pdf 做样本(同时含 page 5 figure 6 这个 fallback 边界 case)
python3 gemini-paper-summary/scripts/gemini_paper_summary.py \
  --pdf "./ART-ICDE'13.pdf" \
  --output ./art_icde13_summary \
  --extract-figures
```

预期:

- Stage 2 视觉定位 2-5 页
- figure-p5-f6.png 顶部紧贴 annotation(无 page header 留白)
- 3/3 张图 alt 文本被 Gemini 完整 caption 覆盖
- summary.md 4216-4500 字符

## 9. 关联

- `[[python-36-compat]]`(见 MEMORY.md 同名小节):3.6 兼容约束也适用于本脚本
- `[[repo-conventions]]`(CLAUDE.md 顶层):row width 120,Markdown 行宽检查
- `gemini-paper-summary/SKILL.md` §A':用户面向的文档,本文件是设计决策的内部记忆
# gemini-paper-summary 图片提取边界与设计决策

> MEMORY 索引:见 [`MEMORY.md`](./MEMORY.md)。本文是正文,记录 2026-06-15 「优化 PDF 图片提取」会话沉淀下来的
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

### 4.1 caption 跨 span 时的 bbox union(2026-06-21 修复)

**Why:** pymupdf 会把视觉上同一行的 caption 拆成多个 line(典型:"Fig. 10." 一个
line、"Single-threaded lookup throughput..." 另一个 line,span 之间有 x 间隔
pymupdf 不合并)。`find_figure_caption` 旧实现只返回首个匹配 line 的 bbox——
`cap_x_center` 反映的是 "Fig. 10." 那个 ~25pt 宽的小 bbox,不是真实 caption 横向
跨度。这会导致 `find_figure_bbox_by_caption` 的"按 cap_x_center 判断单/双栏"
逻辑误判:跨双栏的 figure(如 3 subplot 并排占满页宽)会被当成单栏图,只裁左/右半。

**典型 case:** ART-ICDE'13 第 9 页 Figure 10 是 3 subplot 并排的宽图,caption
"Fig. 10. Single-threaded lookup throughput..." 横跨 page_mid_x(x: 157 → 455)。
旧实现 cap_x_center=170("Fig. 10." 的中心),被判为左栏图,clip 被裁到只含
左侧 65K subplot + 半个 16M subplot(550×344px,半截图)。新实现 union 后
cap_x_center=306 ≈ page_mid_x,被识别为跨双栏 figure,clip 用整页文本区宽
度裁剪(1080×324px,3 subplot + 完整 caption 全在)。

**How to apply:**

- `find_figure_caption` 找到首个匹配 line 后,**同 block 内** union 所有 y 相同
  (±3pt)的 line;3pt 覆盖 pymupdf line 分组的微小 y 偏移,不会跨 y 跨到下段正文
- **只在 block 内 union**,不会跨 block 误吞另一栏的 Fig.N(实测 p5 Fig.6 的
  "Fig. 6." 在 block[21] line[0],续行 "Illustration..." 在 block[21] line[1];
  同页 Fig.7 的 "Fig. 7. Search algorithm." 在 block[39],不同 block,安全)

### 4.2 跨双栏 figure 识别(2026-06-21 修复)

**Why:** 4.1 修复让 caption bbox 反映真实横向跨度后,还要在 `find_figure_bbox_by_caption`
里识别"caption 跨 page_mid_x → figure 必跨双栏",把裁剪宽度从单栏 (~265pt) 扩到
整页文本区 (~540pt)。否则 4.1 的 union 修了 cap_x_center,但 column decision 仍
按 cap_x_center < page_mid_x 走单栏逻辑(300pt+ 的 caption 中心在 page_mid_x 附近
时被分到某一栏)。

**判据:** `cap_bbox[0] < page_mid_x and cap_bbox[2] > page_mid_x`(caption
横向跨度本身横跨页面中线)→ 视为跨双栏 figure,col_left=page_x0+36、
col_right=page_x1-36。

**典型 case:** 仍以 ART-ICDE'13 p9 Fig.10 为代表。修复后 clip 宽度
540pt(vs 旧 265pt 单栏),1080×324 px,3 subplot + 完整 caption "Fig. 10.
Single-threaded lookup throughput in an index with 65K, 16M, and 256M keys." 全在。

**How to apply:** 实现位置同上 — `find_figure_bbox_by_caption` 的 column
decision 段。**注意:** 这是 caption-only 路径的 fallback;Stage 2 视觉定位
默认开启时会优先用 Gemini 视觉 bbox,不受本逻辑影响。Stage 2 失败的 page 才
会落到这里。

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

## 8. 图片 caption 写到 markdown image 的 alt 字段(中文翻译+总结,2026-06-21 最终, v3.2)

> **演进历程**:本节经过 6 个版本的迭代才到最终设计。前 5 版都已弃用,留作
> "为什么是这样"的设计决策上下文:
>
> | 版本 | 阶段 | caption 怎么承载 | 问题 |
> | --- | --- | --- | --- |
> | v1 | 上午 | 塞进图片内 | 图片里文字不可搜索 / 复制 |
> | v2 | 中午 | markdown body `**图 N**:...` 行,图片行 + 单 `\n` | outline-wiki 把单 `\n` 渲染成软空格,caption 视觉紧贴图片底部 |
> | v3 | 中午再试 | v2 + 图片行 + `\n\n` 分段 | markdown body 与 attachment name 都显示 caption,**重复** |
> | v4 | 下午(已弃) | 仅 attachment `name` 字段,markdown body 完全不写 | **outline UI 实际用 markdown alt 渲染 caption,不用 attachment.name**;name 字段只当文件名,UI 看不到 caption 文字 |
> | v3.1 | 晚(已弃) | markdown image alt = **论文英文 caption 原文** | caption 是面向中文读者的,英文原文含术语细节(partial key 0/2/3/255)不好懂;且 inline element 配 ` — <role>` 后段撑成"长句" |
> | **v3.2** | **最终** | **markdown image alt = 中文翻译+总结**," — <role>" 后段删除 | **中文读者扫读快,inline element 短而独立,无重复** |
>
> **关键事实**:
> - outline-wiki `attachments.list` 返回字段只有 `id / name / url / contentType / size / userId / documentId`,**没有 caption / alt / description 字段**
> - `attachments.update` / `attachments.get` / `attachments.view` / `attachments.info` 全部 404 或 `{}`
> - outline UI 实际渲染 caption 文字的来源 = markdown image 的 alt 文本(`![alt](url)`)
> - 唯一改 caption 的途径 = 改 markdown body(attachment 端改不了,只能改 body)
>
> 以下是 v3.2 详细 How to apply:**

**Why:** 旧设计把 "Fig. 10. Single-threaded lookup throughput..." 这类 caption 文字
截进图片。caption 是文本信息,**图片里的文字搜不到 / 不能复制 / 不能翻译 / 不能
被 outline-wiki 索引**。同时图片偏大(多 30-50pt 高度纯文本),扫读时还要"先看
图再读 caption",与论文"图在上、caption 在下"的物理排版相反。

新设计:图片只裁 figure 主体(不含 caption),**caption 写成"中文翻译+总结"形式
写到 markdown image 的 alt 字段**——这是 outline UI 实际渲染为图片下方 caption
文字的通道。
`![图 N: <中文翻译+总结>](<url> "=WxH")`,alt = 中文翻译+总结(含 `图 N: ` 前缀,
冒号允许保留),**不再带 ` — <role>` 后段**——信息全收进 alt,inline element
保持短而独立。
caption 文字**可被搜索 / 复制 / 翻译 / 索引**;中文翻译+总结比英文原文更易扫读。

**How to apply:**

- 裁剪边界 `y1`:`y1 = min(y1, cap_bbox[1] - 2)`(caption 顶上方 2pt 安全边距),
  **y1 不再加 padding**——否则会把 caption 顶重新框进来(实测 +2pt padding 会
  把 caption 顶部 1-2px 的笔画重新框进来,看到 "Fig. N." 的残影)
- markdown image 行格式 (v3.2):
  `![图 N: <中文翻译+总结>](<url> "=WxH")`
  - alt 字段 = **中文**翻译+总结(不是英文原文)
  - alt **必须**以 `图 N: ` 开头(中文版,不是 v3.1 的 `Figure N: `)
  - **不要** ` — <role>` 后段——信息全收进 alt,inline element 短而独立
  - 中文 caption 通常 ≤ 100 字符;如个别仍超 120,markdown 链接不能拆行,**接受超长**
  - 实测示例 (ART-ICDE'13 doc 900f3b2b rev 34):
    - `![图 5: ART 四种内部节点的数据结构（以 partial key 0/2/3/255 → 子树 a/b/c/d 为例）](...)`
    - `![图 6: 延迟扩展（Lazy Expansion）与路径压缩（Path Compression）示意图](...)`
    - `![图 10: 单线程下 ART 在 65K / 16M / 256M 键规模上的查找吞吐量](...)`
- prompt 模板**不要**再要求 Gemini 写 `**图 N**:...` 段落行(独立 caption 段会
  与 alt 渲染重复)
- 脚本侧:`insert_caption_after_figure` 已退化为 no-op + 清理旧 caption 段落行
  的函数(**新代码不应再调用**);**Stage 2 `full_caption`(英文)→ Stage 3 译成中文 → 写到 image alt**——
  v3.2 新增的 Stage 3 翻译步骤,可以是 Gemini 再次调用,或规则化中英术语对照
- **修已发布的 outline doc 改 alt**:用 `mcp__outline__update_document` 的
  `editMode: "patch"`,**逐行 patch 单个 image 行**——image 行之间被 `### 二级标题`
  隔开,**不能**多行一起 patch 整段(实测 "text not found" 失败)
- 行宽 120 限制(`.markdownlint.jsonc` MD013):中文版通常不超 120;英文版 v3.1
  可能超长(如 Figure 5 的 205 字符)——**接受超长**(markdown 链接不能拆行,
  换行会断 URL 解析);本地 `ART-ICDE'13.v4/summary.md` 不在仓库 lint 范围
- **attachment `name` 字段**建议仍设为**英文 caption 原文**(虽然 UI 不显示,
  纯文件名;但同一图附件在 outline 其他 doc 复用时,从 attachment 浏览器能保留
  原始论文语义信息;中文版留给 alt 字段,因为 alt 是用户面向的展示)
- 实测: ART-ICDE'13 p4 f5 (506×548,4 节点全在)、p5 f6 (464×247,path compression +
  lazy expansion 全在)、p9 f10 (1023×310,3 subplot + "(GPT and CSB crashed)" 标注全在,
  caption 文字已剥离);doc 900f3b2b rev 34 = 3 个 image alt = 中文翻译+总结,
  body 0 个独立 caption 段落行

## 10. [已弃用] outline-wiki 分段：图片与 caption 之间必须空行(2026-06-21,被 v3.2 反转)

> **本节已被 §8 v3.2 设计取代**——v3.2 把 caption 写到 markdown image alt
> 字段(单 inline element,无独立段落),本节的"图片行 + caption 行之间用
> `\n\n` 分段"规则**不再适用**。本节保留作为演进历史(避免重蹈覆辙)。

**Why (历史):** 本地 markdown 用单个 `\n` 换行没问题,但 outline-wiki 把单个 `\n`
渲染成**软空格**(同段落内换行),只有 `\n\n` 才会切到新段落(ProseMirror 切
paragraph node)。v2 / v3 设计的 `insert_caption_after_figure` 输出
`![图 N](...) — <role>\n**图 N**:<caption>`(图片行 + 单换行 + caption 行)推到
outline-wiki 后,**图片行与 caption 行在同一段落**,caption 视觉紧贴图片底部,
扫读时像"只有图 5 这个标签,没有原文 caption 文字"——这就是用户当时反馈"图片
标题只有图 5"的真正原因。v3 临时加 `\n\n` 修复,但又引入"body 与 attachment
name 重复显示 caption"的新问题,所以最终推翻到 v3.1。

**How to apply (历史,已不再用):**

- v3 输出模板:`\n\n` 分段(本地规则 `\n`,推送 outline-wiki 规则 `\n\n`):
  ```python
  block = "![图 N](...) — <role>\n\n**图 N**:<caption>"
  ```
- v3 的本地实测: ART-ICDE'13 doc 900f3b2b-... rev 24 用此规则,3 张图 + 3 段
  caption 全部独立成段,outline-wiki 渲染正常。但 v3.1 推翻了此设计。

**为何被 v3.1 取代**:v3 仍把 caption 写在 markdown body 独立段落,会和
outline UI 用 markdown alt 渲染的 caption **重复显示**;v3.1 直接把 caption
塞到 image alt 字段(单 inline element,不构成独立段落),body 不再写
` **图N**:... ` 行,根本消除了重复与分段问题。

## 11. outline-wiki attachment 能力边界(2026-06-21 实测)

**Why:** v3.1 设计需要知道 outline 端 attachment 字段的真实情况,避免凭
"印象"反复试错(前面 v4 误判就是凭印象)。

**实测清单**(基于 `https://myoutline.ddnsto.com` 实例,2026-06-21):

| 端点 / 字段 | 是否暴露 | 备注 |
| --- | --- | --- |
| `attachments.list` `GET/POST` | ✓ | 返 `{id, name, url, contentType, size, userId, documentId}`——**无 caption / alt / description 字段** |
| `attachments.list` `documentId` 字段 | 部分 | **只对"其它 doc 引用的 attachment" 返回 docId**;当前 doc 引用的 attachment 返 `null`(不能用于判 orphan) |
| `attachments.list` `limit` | 上限 100 | 超过返 `400 Pagination limit is too large (max 100)`,需分页 |
| `attachments.create` | ✓ | 接 `name` / `contentType` / `size`(MCP `create_attachment` 工具暴露的就是这 3 个);二进制走 `curl /api/files.create` |
| `attachments.info` | ✗ | 返 `{}`(端点不存在) |
| `attachments.get` | ✗ | 404 |
| `attachments.view` | ✗ | 404 |
| `attachments.update` | ✗ | 404;**不能改 attachment 的 name / contentType**——只能删除重建(但 delete 也 404) |
| `attachments.delete` | ✗ | 404;**orphan attachment 无法通过 API 清理**,只能在 outline UI 手动删 |
| `attachments.redirect` | ✓ | `curl /api/attachments.redirect?id=<id>` 拿二进制,需带 API key |

**How to apply:**

- 改 attachment 的 name / contentType:删不掉、改不了,只能重新 `create_attachment` + 重新 `curl /api/files.create`——但旧 attachment 会**永远 orphan**(`attachments.delete` 404,没法清理)
- 改 doc body 里图片的 caption:用 `mcp__outline__update_document` 的 `editMode: "patch"`,**逐行 patch 单个 image 行**(image 行之间被 `### 二级标题` 隔开,**不能**多行一起 patch 整段)
- 判 attachment 是否 orphan:不要信 `attachments.list` 的 `documentId` 字段(对当前 doc 永远返 null);只能**信 doc body 里的 markdown 引用**——脚本用 `grep '/api/attachments.redirect?id=<id>' <doc-text>` 倒推 in-use 集合
- 想看 attachment 关联 doc:实测 `attachments.list` 拿不到完整信息,可能要走 outline DB 直接查(超出本 skill 范围)

## 9. 验证方法(端到端 smoke test)

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

- `[[python-min-3-7]]`(见 [`MEMORY.md`](./MEMORY.md) "Python 最低 3.7" 小节):Python 版本兼容约束也适用于本脚本
- `[[repo-conventions]]`(CLAUDE.md 顶层):row width 120,Markdown 行宽检查
- `gemini-paper-summary/SKILL.md` §A':用户面向的文档,本文件是设计决策的内部记忆

## 12. quick 模式默认带图（2026-07-01 产品决策）

**Why:** quick 模式的产物是给**人看**的（快速浏览论文），图是论文理解的关键部分；
纯文字 Markdown 残留 `![图 N](PDF p.X fig.N bbox=...)` 这种任何渲染器都显示不了
的破图引用，比"没图"更糟（误导用户以为图坏了）。full 模式则是给 agent 多轮查询用
的纯文本底座，不需要图（mermaid/ASCII/表格替代）。两个模式的图策略彻底分家：
**quick 默认带图 + Stage 2 精修保质量；full 不带图**。

**关键变更（main() 重构）：**

- 产图不再由 `--extract-figures`（默认 False）显式触发，而是 quick 模式**默认行为**
  （`want_figures = not args.no_figures`）
- `--extract-figures` 降级为**向后兼容冗余 flag**（传了等价默认 + INFO），不破坏
  yzr-outline-wiki-upload 等下游既有调用
- 新增 `--no-figures` 关闭图导出（批量速读 / 纯文字速览场景）
- Stage 2（`--refine-figures` 默认 True）与默认带图绑定，保证图质量（Gemini 视觉
  定位精修 bbox + 完整 caption + 过滤装饰图）

**边界清理（strip_pdf_figure_refs）：** 当 `--no-figures` / 缺 pymupdf / stdout 模式
导致不导出图时，调用新增的 `strip_pdf_figure_refs(md_text)`（复用 `embed_figure_refs`
里提取出的 `_strip_failed_figure_lines` 同源清理逻辑）把**所有** `![...](PDF p.X
fig.N ...)` 破图引用整行删 + 剥"如图 N 所示"呼应句，保证产物绝不残留破图。各边界
打明确 WARN/INFO 告知用户为何没图。

**`--output` 语义随是否带图切换：** 带图成功时视作目录（summary.md + figures/）；
否则视作 .md 文件路径；不传则 stdout（清破图、不导出）。

**关联：** 端到端不降级（agent 收到 503 RuntimeError 也不自行换模型）见
`gemini-paper-summary/SKILL.md` §核心原则 #8（2026-07-01 同期加固，是这次改动的
姊妹修复——脚本侧早已零降级，补的是 agent 行为盲区）。

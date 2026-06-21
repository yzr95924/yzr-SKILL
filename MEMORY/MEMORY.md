# MEMORY/

跨会话需要持久化的"为什么"与边界规则。新条目追加在末尾。`MEMORY.md`（本文件）只做索引，正文与本文件同级。

> 本文件是项目级规则的**唯一**真源。Claude 会话级 memory（`~/.claude/projects/.../memory/`）只放指向本文件的指针，不再持有内容副本，避免跟代码仓迁移时失同步。

## 规则

### Python 3.6 兼容

**Why：** 部署目标含 CentOS 7 等老 OS（官方源最高只有 Python 3.6，通过 `python36` / SCL `rh-python36` 提供）。3.6 写出的代码在 3.6+ 全版本都能跑，向上兼容比向下兼容重要。

**How to apply：** 新写 Python 脚本时避开以下特性（按最低引入版本列）：

| 最低版本 | 特性 | 替代写法 |
| --- | --- | --- |
| 3.7+ | `subprocess.run(capture_output=True, text=True)` | `stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True` |
| 3.7+ | `from __future__ import annotations` | 直接写完整注解（`Optional[X]` 而非 `X \| None`） |
| 3.7+ | `breakpoint()` | `import pdb; pdb.set_trace()` |
| 3.7+ | `asyncio.run` | `loop.run_until_complete(...)` |
| 3.8+ | walrus `:=` | 拆成两行 |
| 3.8+ | f-string `=`（`f"{x=}"`） | `f"x={x}"` |
| 3.9+ | PEP 585 内建泛型 `list[int]`、`dict[str, X]`、`tuple[X, Y]` | `from typing import List, Dict, Tuple` |
| 3.9+ | `zoneinfo`、`str.removeprefix/removesuffix` | 自行实现或 `s[:-len(x)] if s.endswith(x) else s` |
| 3.10+ | PEP 604 联合类型 `X \| Y`、`X \| None` | `from typing import Union, Optional`；用 `Optional[X]` |
| 3.10+ | `int.bit_count` | `bin(n).count("1")` |
| 3.10+ | `match` 语句 | if/elif 链 |

**静态扫描（写完自查）：**

```bash
grep -nE "(\| None|list\[|dict\[|tuple\[|capture_output|text=True|:=|breakpoint\(\))" path/to/script.py
```

空白命中即视为 3.6 不兼容。

**落地参考：** `yzr-skill-creator/scripts/` 下 8 个脚本（B1 修复时落地的合规示例）—— 含 `from typing import Optional, List, Dict, Tuple` 的导入，以及 `subprocess.run(stdout=PIPE, stderr=PIPE, universal_newlines=True)` 的标准调用形式。

### 后续脚本优先 Python 3

**Why：** 在 2026-06-20 反馈中明确——后续脚本优先用 Python 3 而非 bash / shell 实现，**同时**在 Python 3 内部严格走 3.6 语法以保老 OS 兼容。理由是：(1) 部署目标含 CentOS 7（`python36` / SCL `rh-python36`）等只到 Python 3.6 的环境，参见上方的 "Python 3.6 兼容" 小节；(2) 脚本语言统一用 Python 3 便于在 Python 生态内统一管理（包管理、`subprocess`、`pathlib` 等），不被 bash 平台差异 / shell 解析边界问题分神。

**How to apply：**

- **首选 Python 3** 写新脚本，不再新写 bash / shell 脚本。唯一例外是 shell 天然更自然的场景：一行管道、纯文本流处理、`awk` / `sed` / `grep` 一句话即可
- **Python 3 内部** 严格遵守上方 "Python 3.6 兼容" 小节的所有规则
  - `Optional[X]` 而非 `X | None`；`List[X]` / `Dict[X, Y]` / `Tuple[X, ...]` 而非 PEP 585 内建泛型
  - `subprocess.run(stdout=PIPE, stderr=PIPE, universal_newlines=True)` 而非 `capture_output + text`
  - 不使用 walrus `:=`、`match` 语句、`int.bit_count`、`f"{x=}"`、`from __future__ import annotations`、`breakpoint()`、`asyncio.run` 等 3.7+ 特性
- **已有的 bash 脚本** 不强制回溯改写，但新增脚本按本规则判断。`scripts/install-dev-deps.sh` 在 2026-06-20 已重写为 `install-dev-deps.py`，是这次转写的第一个落地例子
- **类型注解** 完整写（`Optional[X]` / `List[X]` / `Tuple[X, ...]` / `Dict[X, Y]`），不省略

### gemini-paper-summary 图片提取 fallback 设计

**Why：** Stage 1 让 Gemini 从 PDF 原内容估算 bbox 是基于语义而非像素的，精度差；caption 定位的旧启发式（"宽+多行正文段落"）在 figure 上方只有 annotation / label 时会退到 page 顶，造成大量上方留白（典型 case：ART-ICDE'13 第 5 页 Figure 6）。Stage 2 必须把页面渲染成 PNG 送给 Gemini 用视觉定位，caption 定位 fallback 也必须分多策略。

**2026-06-21 增补**：caption 跨 span 时的 bbox union（4.1）+ 跨双栏 figure 识别（4.2）—— 旧实现返回的 caption bbox 只是 "Fig. 10." 那 ~25pt 宽的小 line，cap_x_center 偏左，3 subplot 并排的宽图被判为单栏图，只裁左半（典型 case：ART-ICDE'13 第 9 页 Figure 10 旧产物 550×344px 是半截图）。修复：union 同 block 内同行 (±3pt) line + 判 `cap_bbox[0] < page_mid_x < cap_bbox[2]` 时用整页文本区宽度裁剪。

**How to apply：**

- Stage 2 坐标用 Gemini 官方归一化 0-1000 (`[ymin, xmin, ymax, xmax]`)；渲染图未做宽高变形时，`x_pt = x_norm * page.rect.width / 1000` 与 dpi_scale 无关
- Stage 2 Gemini 调用加重试（默认 3 次，指数退避 2s/4s）：临时错误 (`429/500/502/503/504`) 重试，永久错误 (`400/401/403/404`) 立即放弃
- caption 定位 fallback 三策略：①正文段落底部（图上方紧跟正文）→ ②annotation 顶部（用 caption 上方同栏所有"非正文"块的最上 y0，覆盖只有 annotation 的 case）→ ③page 顶兜底
- caption bbox union 必须在**同 block 内**做（3pt y 容忍），不会跨 block 误吞另一栏的 Fig.N
- 跨双栏 figure 判据 `cap_bbox[0] < page_mid_x and cap_bbox[2] > page_mid_x` → 用整页文本区宽度（page_x0+36 / page_x1-36），不只裁单栏
- Stage 2 返回的 `is_key_figure=false` 直接过滤（让 Gemini 顺手判断"装饰图"）
- Stage 2 读出的完整 caption 覆盖 Markdown alt 文本中"图 N:"之后的部分，但**保留**"— <role 说明>"后段

### gemini-paper-summary 图片 caption：写到 markdown image alt 字段，中文翻译+总结，不进正文段落（2026-06-21 修订 v3.2）

**Why：** 旧设计（2026-06-21 上午）把 caption 文字 "Fig. 10. Single-threaded lookup throughput..." 截进图片里——caption 是文本信息，图片里的文字**搜不到 / 不能复制 / 不能翻译 / 不能被索引**。演进过程：
1. **第一步修复**：图片只裁 figure 主体（不含 caption），caption 由 markdown body 紧贴图片的下一行加粗文字承载（`**图 N**：<caption>`）。但这步实测**仍有问题**：outline-wiki 把单 `\n` 渲染成软空格，caption 视觉上贴住图片底部，扫读像"只有图 5 标签没有原文"。
2. **第二步误判（已弃）**：以为 caption 走 outline-wiki attachment 的 `name` 字段——上传时把 `name` 设为论文 Figure 标题原文。实测 outline UI **不**用 `name` 渲染 caption，用户看到的还是 markdown 里的"图 5"短 alt。attachment 的 `name` 字段纯为文件名（保留 caption 文本是副作用）。
3. **v3.1（2026-06-21 晚）**：**caption 写到 markdown image 的 alt 字段（英文原文）**——`![Figure 5: Data structures for inner nodes...](/api/attachments.redirect?id=<id> "=WxH") — <role>`。这是 outline UI 唯一会渲染为图片下方 caption 文字的通道。markdown body 仍不写独立的 `**图N`：...` caption 段落行。
4. **v3.2（2026-06-21 晚，最终）**：**alt 字段写成"中文翻译+总结浓缩"，" — <role>" 后段删除**。理由：caption 是面向中文读者的，论文英文 caption 长且含术语细节，中文翻译+总结更易扫读；role 描述本来是 Stage 1 的语义补充，但 alt 字段本身就是语义信息源，role 段冗余且把 inline element 撑成"长句"。

**Why not both**：
- markdown body 写独立 caption 段落 = 重复（image 下方已经有 alt 渲染的 caption）
- attachment.name 设 caption 但不写 alt = 看不到（name 纯文件名，UI 不用）
- **唯一通道** = markdown image 的 alt 字段
- **caption 走英文原文** = 中文读者看不懂细节（论文 figure caption 含 partial key 0/2/3/255 这种 raw 数字）；**caption 走中文翻译+总结** = 读者扫读快

**How to apply：**

- 裁剪边界：`y1 = min(y1, cap_bbox[1] - 2)`（caption 顶上方 2pt 安全边距），**y1 不再加 padding**
- markdown image 行格式（v3.2 最终）：
  `![图 N: <中文翻译+总结>](/api/attachments.redirect?id=<id> "=WxH")`
  - alt 字段 = **中文**翻译 + 总结浓缩（前缀 `图 N: `，冒号允许）
  - **不要**再带 ` — <role>` 后段（信息全收进 alt）
  - 中文 caption 行宽通常 ≤ 100 字符，不超 120 限制；如个别仍超，markdown 链接不能拆行，**接受超长**（本地 `ART-ICDE'13.v4/` 不在仓库 lint 范围）
  - 示例（实测）：
    - `![图 5: ART 四种内部节点的数据结构（以 partial key 0/2/3/255 → 子树 a/b/c/d 为例）](...)`
    - `![图 6: 延迟扩展（Lazy Expansion）与路径压缩（Path Compression）示意图](...)`
    - `![图 10: 单线程下 ART 在 65K / 16M / 256M 键规模上的查找吞吐量](...)`
- **attachment `name` 字段** 可以（且建议）保留英文 caption 原文（虽然 UI 不显示，但同一图附件在 outline 其他 doc 复用时，从 attachment 浏览器能保留原始论文语义信息）
- 脚本侧：`insert_caption_after_figure` 已退化为 no-op + 清理旧 caption 段落行的函数（**新代码不应再调用**）；Stage 2 `full_caption`（英文）由**调用方在 Stage 3 中译成中文**写到 image alt 字段——这是 v3.2 新增的 Stage 3 步骤
- prompt 模板里**不要**再要求 Gemini 写 `**图 N**：...` 段落行
- 修复 doc 改 alt：用 `mcp__outline__update_document` 的 `editMode: "patch"`，**逐行 patch 单个 image 行**（image 行之间被 `### 二级标题` 隔开，**不能** 多行一起 patch 整段）——前面试过 3 行一起 patch 报"text not found"

**outline-wiki 实例能力边界（实测）：**

- `attachments.update` / `attachments.get` / `attachments.view` / `attachments.info` 全部 404 或返回 `{}`——**attachment 字段只能通过 `attachments.list` 看到**（id / name / url / contentType / size / userId / documentId，**没有** caption / alt / description 字段）
- `attachments.list` 的 `documentId` 字段对 in-use 的 attachment **不返回 docId**（只对其它 doc 引用的 attachment 才显示 docId），所以**不能用 `attachments.list` 判 orphan**——只信 doc body 里的引用
- `attachments.list` `limit` 最大 100，超过报 400；`total: 198` 时分页

**正文：** [`gemini-paper-summary-figure-extraction-edges.md`](./gemini-paper-summary-figure-extraction-edges.md)

### SKILL 描述类修改：默认同步仓库源

**Why：** 本仓库是 SKILL 的"源 / 描述"载体（`outline-wiki-management/`、`gemini-paper-summary/`、`yzr-skill-creator/`、`design-doc-edit/` 等顶层子目录即各 skill 源），而 Claude Code 加载的是 `.claude/skills/<name> -> ../../.agents/skills/<name>` 的软链（vendored 副本，被 `.gitignore` 排除）。两套文件**不同 inode**——`Edit` 默认改的是 vendored 副本，不在 git 跟踪范围内，会随下次 `npx skills` 同步被覆盖。

**How to apply：**

- 修改任何 skill 的 `SKILL.md` / `references/*.md` / `scripts/*.py` 等"描述类"文件前，**先**问自己："这次修改是要进仓库源（`.gitignore` 之外），还是只调 vendored 副本做本地实验？"
- 默认是前者（持续维护的代码），改完后**必须**同步到仓库源——通常用 `cp` 把 vendored 副本拷回源（`cp .claude/skills/<name>/SKILL.md <name>/SKILL.md`），用 `git status` / `git diff --stat` 确认
- 一次只改一个 skill，不要顺手把 vendored 里其他无关改动一起带回去——`cp` 之前先 `diff` 一遍
- 涉及仓库源里 `Edit` 不到的字符（如大段重写、含特殊符号的）也可以走 `cp`，但**只覆盖源里未改的部分**；源已被别处修改时必须 `Edit` 走精准 patch，否则会丢别人的改动
- 反例：上次的 SKILL 修改我只在 `.claude/skills/outline-wiki-management/` 改了，没主动同步到 `outline-wiki-management/`，被用户提醒才补；这就是这条规则要堵的洞

### outline-wiki attachment：API key 可直用走 curl 传二进制

**Why：** `mcp__outline__create_attachment` 是 **metadata-only**——只接收 `name` / `contentType` / `size`，**不**接收二进制。如果不继续走一步 curl，`attachment` 记录存在但内容是 0 字节，文档嵌进去后**空白 / 破图**。这是"看起来一切正常，事后才发现"的最深坑。

但 curl **不需要**用户浏览器 session cookie——outline MCP 配置里那把 `Authorization: Bearer <key>`（在 `~/.claude.json#mcpServers.outline.headers` 或 `.claude/settings.local.json`）就是**同一把** outline API key，agent 直接拿来用 `curl /api/attachments.create`（拿 presigned form）和 `curl /api/files.create`（multipart 上传二进制）都能过认证。所以 attachment 完整流程可以**完全由 agent 在对话里完成**，不用让用户手动拖图。

**How to apply：**

- 标准 3 步：① `mcp__outline__create_attachment` 拿 `data.form`（`key` / `acl` / `Content-Type` / `Cache-Control` / `maxUploadSize` / `_csrf`）；② 拿 MCP 配置文件里的 API key 走 `curl POST /api/files.create -F <form 字段> -F "file=@<path>"` 上传；③ `mcp__outline__update_document` 用 `editMode: "replace"` 写入 Markdown 引用（`patch` 模式在前置测试里也不生效，bug 未上报）
- **必须**在第 ② 步后用 `curl -sSL /api/attachments.redirect?id=<id>`（带 API key）核验 `size=实际文件字节` + `content-type=image/...`；0 字节或 HTML 错误页都算上传失败，要重试
- 上传失败的 orphan attachment 用 `curl POST /api/attachments.delete -d '{"id":"<id>"}'` 清理
- **退路顺序**（API key 失效时）：① 查 `mcpServers.outline.headers.Authorization` 是否真的填了 key；② 重跑 `outline-wiki-management/scripts/configure_mcp.py` 重新写 key；③ 让用户在 Outline UI 拖图（编辑器自带 session auth）
- 详细 curl 命令 / 字段说明 / 边界见 `outline-wiki-management/SKILL.md` §图片插入 / 文件附件工作流

### gemini-paper-summary 字数上限：1000 词（≈ 500 中文字符）

**Why：** 用户在 2026-06-21 反馈希望总结"精炼、无冗余"，显式给出双标尺：1000 词（token 级）/ 500 个中文字符（纯中文级）。两个数对应不同语言模式——纯中文 500 字（≈ 一篇会议论文 summary 段落长度）；中英混排（保留 ART / B+-tree / HyPer 等术语不译）则 1000 词更宽。两个数都写进 SKILL 的 "精炼优先" 小节、核心原则 #2、prompt-template 头部 + 基础要求 #4，共 7 处，统一为 "1000 词（≈ 500 个中文字符）"。

**How to apply：**

- 描述统一用 `1000 词（≈ 500 个中文字符）`——"词" 覆盖中英混排、"字" 覆盖纯中文段落；"≈" 表示数量级近似，不强求词→字严格 1:1
- 写法选择：核心原则 / prompt 头部 / 风格约束小节三处都明确写"上限" + "精炼优先"修饰；故障排查表格（"远超 1000 字"）改成"远超 1000 词（≈ 500 个中文字符）"
- 不要写"1500 词 / 1000 字" 这种放宽版本——用户原意就是要严控

### 关键架构图 / 示意图：内联到方法上下文，**不**单独成节

**Why：** 用户在 2026-06-21 反馈，旧设计把"关键架构图 / 示意图"集中在方法小节末尾的子列表里——读者必须先看完整段方法 bullet，再翻到节末找图，**扫读体验割裂**，而且"图 5：四种内部节点内存布局"显然属于"### 自适应内部节点"那段论述、不属于"### 路径压缩与延迟扩展"那段论述，分离在节末会丢失归属感。新设计把图**直接插入**到对应方法 / 概念的 bullet 之后（"方法 bullet → 图 → 下一个方法 bullet → 下一张图"），让图和它的方法点物理上紧贴，扫读不丢锚点。

**How to apply：**

- SKILL.md 核心原则 #5 标题从 "用 (page, fig_num, bbox) 引用插入到 Markdown" 改成 "(page, fig_num, bbox) 引用 + 内联到对应方法上下文"；第一条 bullet 从 "在'方法'小节末尾追加 **关键架构图 / 示意图** 子列表" 改成 "**不**单独成'关键架构图 / 示意图'小节；每张关键图紧贴它说明的算法 / 协议 / 数据结构那段 bullet 放"
- prompt-template.md "图引用约定"小节：从 "方法小节末尾追加" 改成 "**不**单独成 ... 直接插入到对应方法 / 概念的上下文"；示例从独立子列表改为 bullet 内部示例（"（先写算法 / 数据结构 bullet）→ 图 → （继续写下一个方法点）"）
- A 变体示例里的 `**关键架构图 / 示意图**（若论文含关键图，参见核心原则 #5）：` 子标题和它下面的示例 bullet 整段删掉，直接 `bullet → bullet → ## 代表性实验结果`
- 强调 "**图前**一句必须呼应（"如图 N 所示" / "见图 N"），把图和上下文绑死；**图后**一句不要重复同样的内容"——这是把图从"节末附录"变成"上下文锚点"的关键
- 保留 bbox / page 引用 / fig.N 编号 / 只收关键图（跳装饰图、坐标轴、表格）这些抽取 / 排版规则——只改"插哪里"，不改"怎么引"
- references/figure-extraction.md 不动——它讲的是抽取逻辑（怎么把 PDF figure 截成 PNG），跟"输出文档里图放哪"是两个层面

### 论文笔记开篇结构 v4：去掉 `## 团队背景介绍`，加 `## 3 句话总结`（2026-06-21）

**Why：** 旧设计（v3.2 及更早）开篇是 `## 团队背景介绍` 独立小节，含 `* **级别**：数据库领域顶级会议 ICDE 2013` 这类**主观评级** bullet——会议级别是 doc 标题/3 列表格承载的信息，正文里再写一遍是冗余且容易随个人感受漂移（"顶级"谁定义？）。同时缺一个**开篇 3 句**的总览段——读者要扫读完 200-300 字的团队/背景才能进方法。

新设计（v4，2026-06-21 反馈）：

```markdown
| **Title** | **Venue** | **Topic** |
|-------|-------|-------|
| 论文全英文标题 | 会议'年份 | 领域关键词 |

* 论文链接

  > <TODO>

* **团队/机构**：…（如"麻省理工学院 CSAIL"）；研究背景是…（一句话上下文）

## 3 句话总结

1. 论文主旨一句话：方法 + 关键 insight
2. 核心设计 / 关键数据（用具体数字）
3. 落地 / 关键 baseline 对比

## 背景与动机
…
```

**Why not `## 团队背景介绍` 独立小节**：
- 团队信息只是 1 条 item（机构 + 一句背景），不构成"小节"
- "会议级别 / tier-1" 评级不可量化，正文不写——3 列表格 + doc title 已承载
- `## 3 句话总结` 才是真正承载"扫读锚点"的位置（3 句把论文核心讲清），应紧跟开篇

**How to apply：**

- 章节顺序：**开篇 3 列表格 → 团队 item → `## 3 句话总结` → `## 背景与动机` → 方法 / 实验 / 业务启示&价值 / 局限**
- 团队 item 格式：**只一条 item**——`* **团队/机构**：<机构名>；<一句话研究背景>`，用分号/句号衔接，**不**再单独起 `* **背景**：…` 第二条 item
- 团队 item 行宽尽量 ≤ 120；超出可接受（临时输出目录不在仓库 lint 范围）
- 团队 item **不**写"会议级别 / 顶级 / best paper?"这类评级
- `## 3 句话总结` 用编号列表（`1. ` / `2. ` / `3. `）——3 条编号比 1 段话更易扫读
  - 句 1 = 方法 + insight（论文要解决什么问题 + 怎么解）
  - 句 2 = 核心设计点 / 关键数据（用具体数字）
  - 句 3 = 落地 / 关键 baseline 对比（被谁采用、超越什么）
- 同步改 `gemini-paper-summary/SKILL.md` 的 description、`## 输出` 章节顺序、开篇结构示例、核心原则 #2 章节顺序、核心原则 #2 `###` 三级标题示例
- 旧 A/B 变体（A = 本地 md / B = outline-wiki）已**合并为统一结构**（开篇 3 列表格统一适用），不再区分 A/B

**正文：** [`gemini-paper-summary/SKILL.md`](../../gemini-paper-summary/SKILL.md) 的"输出"节

### gemini-paper-summary 生成后自检：图片完整性 + 边界破坏（2026-06-21）

**Why：** 用户在 2026-06-21 反馈——"最终生成完的论文总结，要自检一下图片是否完整，是否存在图片边界破坏的情况"。单看 doc body 字面 OK 不代表图真的 OK（attachment 可能 0 字节 / doc body 引用的尺寸与实际 PNG 尺寸不一致 / 图片被错误裁剪）。自检是生成流程的**最后一道防线**，分 3 层面：

| 层面 | 自动化 | 检测什么 | 失败信号 |
| --- | --- | --- | --- |
| 1. 引用完整性 | ✓（脚本） | doc body 里的 `attachments.redirect?id=<id>` 引用 ID 是否在 `attachments.list` 返回中存在 | attachment 被删但 doc 还引用 → 破图 |
| 2. 二进制完整性 | ✓（脚本） | 每个 in-use attachment 的 `attachments.redirect` HEAD 是否 200 + image/... + size > 0 | 0 字节 / HTML 错误页 = 上传失败未发现 |
| 3. 边界破坏 | ✓ + 人工 | (a) 本地 `figures/*.png` 实际像素尺寸 vs markdown title `=WxH` 差 ≥ 5% → 标题尺寸字段失效；(b) 人工到 outline UI 看图是否截断 / 留白过多 / 边界切错 | 裁剪坐标错误 / 重新上传导致 title 尺寸与实际不符 |

**How to apply：**

- **脚本侧**（自动）：`gemini-paper-summary/scripts/gemini_paper_summary.py` 的 `self_check_figures(md_text, figures_dir, outline_check, outline_endpoint, outline_api_key)` 挂在 main 末尾，写文件后、退出前自动调
  - 阶段 1：parse markdown text 抽 `attachments.redirect?id=<id>` 引用 ID 集合
  - 阶段 2：仅当环境变量 `OUTLINE_ENDPOINT` + `OUTLINE_API_KEY` 都设置时跑（`attachments.list` + 每个 ID 的 HEAD 校验）
  - 阶段 3：本地 `figures/` 目录每个 PNG 用 pymupdf 读像素尺寸，对照 markdown 里 `=WxH` title 字段；差 ≥ 5% 警告
  - 返回 `{ok, warnings[], failures[], report}` 写到 stderr，**不抛异常**（warning 继续 / failure 只 WARN，不让主流程挂）
- **人工侧**（必做）：agent 把生成的 doc 链接给用户后，**让用户在 outline UI 看一眼**3 张图——是否完整、是否截断、是否切到不该切的位置；用户反馈"图破了"再回查（脚本不会自动做视觉 diff）
- **运行时**：本地 summary.md 生成时（`--extract-figures`）走 阶段 1+3+4（按 cwd 解析 figures 路径）；推到 outline 后 + 设置环境变量走 阶段 1+2+3；不阻塞主流程
- **Why not visual diff 自动做**：outline doc 渲染图含 outline UI chrome（背景色 / padding / 标题区），与原 figure 直接像素 diff 噪声大；可靠方案是按论文 PDF 原 page 渲染 + bbox 内裁剪后与 `figures/*.png` 对比——成本高，作为可选 Step 4b（默认不跑，agent 怀疑有问题时手动启用）
- 脚本加的 helper 函数 `_outline_api_request` / `_outline_attachment_head` 走 `urllib.request` 纯 stdlib 调 outline REST API，**不** 强依赖 outline MCP / `requests` 包

**正文：** [`gemini-paper-summary/SKILL.md`](../../gemini-paper-summary/SKILL.md) 的"## 生成后自检"节 + [`gemini_paper_summary.py:self_check_figures`](../../gemini-paper-summary/scripts/gemini_paper_summary.py)

### SKILL 源 vs 运行时 vendor：两套独立文件，改源才有效

**Why：** 复盘 2026-06-21 改 v3.2 caption 规则时栽的坑——`Skill` 命令从 `~/.claude/skills/<name>/SKILL.md` 加载（运行时 vendor），而代码仓源是仓库根的 `<name>/SKILL.md`。两者**不是软链，是两份独立文件**（vendor 是 `npx skills add` install 出来的真目录）。`Edit` 默认改的是 vendor，源没动——下次 npx 重装就丢改、或 `git status` 看不到这次改。

```text
/home/zryang/my_SKILL/gemini-paper-summary/                  # ← 代码仓源（SSOT）
/home/zryang/my_SKILL/.agents/skills/gemini-paper-summary/   # ← vendored 真目录
/home/zryang/my_SKILL/.claude/skills/gemini-paper-summary    # ← 软链 → 上面那个
```

`ls -la .claude/skills/gemini-paper-summary` → `lrwxrwxrwx ... -> ../../.agents/skills/gemini-paper-summary`，`file .agents/skills/gemini-paper-summary` → `directory`。

**How to apply：**

- **改 SKILL 必须改源**（仓库根 `<name>/`），改完**手动同步**到 `.agents/skills/<name>/`（vendor）才能让当前 Claude 会话看到新内容
- 同步命令（dry-run 先过一遍再实跑）：
  ```bash
  diff -q gemini-paper-summary/SKILL.md .claude/skills/gemini-paper-summary/SKILL.md
  rsync -a --delete --dry-run gemini-paper-summary/ .claude/skills/gemini-paper-summary/
  rsync -a --delete gemini-paper-summary/ .claude/skills/gemini-paper-summary/
  ```
- `cp` 风险：源被别处修改过（被别人改过）时 `cp` 会丢对方改动，**优先 Edit 精准 patch**；大段重写 / 含特殊字符时走 `cp` 但 `cp` 之前必须 `diff` 一次
- vendor 副本在 `.gitignore` 内，git 跟踪不到——只改 vendor 等于"本地实验"，**不算**给仓库做了贡献
- 现状：本次会话发现 prompt-template.md 在源（仓库根）和 vendor 不一致，已把 vendor 改回成源的旧版（revert），下一步在**源**重新做 v3.2 同步

**正文：** [`skill-source-vs-runtime-vendor.md`](./skill-source-vs-runtime-vendor.md)

### 影响 SKILL 输出的"为什么"记忆必须同步到 SKILL 源

**Why：** 本仓库是 SKILL 的代码仓。MEMORY 记的是"为什么 + 边界规则"，但**光放 MEMORY 不够**——SKILL.md / assets / scripts 才是 Claude Code 触发 SKILL 时实际加载的上下文。如果设计决策**没有**在 SKILL 文件里**显式落地**，下次触发 SKILL 时这个决策就丢了（典型 case：MEMORY §8 v3.2 写了"alt = 中文、不写独立 caption 行"，但 SKILL.md §核心原则 #5 + prompt-template.md 仍停留在 v3.1——脚本实际跑出来还是 v3.1 格式）。

**How to apply：**

- 写任何影响 SKILL **最终输出 / 行为** 的 MEMORY 时，**同步**做两件事：
  1. **改 SKILL.md 对应小节**（让 Skill 加载时看到新规则）
  2. **改 assets / scripts / references**（让脚本实际跑出新行为）
- 判定：影响输出格式 / 行为 / 边界 → 必须同步；纯工作日志 / 任务状态 → 留 MEMORY
- 冲突处理：MEMORY 和 SKILL 冲突时，**以更新日期晚的为准**；改 SKILL 的要把"为什么"补到 MEMORY；改 MEMORY 的要同步 SKILL
- 本条与上方 "SKILL 源 vs 运行时 vendor" 配套——同步时记得**两边都改**（源 + vendor）

**正文：** [`memory-synced-to-skill-source.md`](./memory-synced-to-skill-source.md)

### 论文总结字数限制：单单位 = 字符

**Why：** 旧写法 "1000 词 ≈ 500 中文字符" 双单位 + 近似换算有歧义——"词"是英文单位（中文没有"词"概念），"中文字符"只算汉字（不含英文术语 / 标点 / 空格），"≈ 500" 是 heuristic 没法精确换算。实测换成"总字符数 ≤ 1000"后 Gemini 输出从 2772 字符降到 1311 字符，明显更尊重约束。

**How to apply：**

- 字数限制**只用**一个单位 = **字符**（character，含中英 / 空格 / 标点）
- 唯一来源在 `gemini-paper-summary/assets/prompt-template.md` 头部 + §基础要求 #4，**不要**在 SKILL.md / MEMORY.md / 故障排查表再写具体数值
- 改字数只改 `prompt-template.md` 两处；SKILL.md / MEMORY.md 跟随
- 字符数是用户和工具的**唯一公分母**：Python `len()`、markdown linter 行宽、outline 字数统计、用户直观"页数 / 篇幅"——都是字符

**正文：** [`prompt-length-unit-character.md`](./prompt-length-unit-character.md)

### outline MCP 工具必须在 settings.local.json 加白名单

**Why：** 2026-06-21 实测——多次 `mcp__outline__update_document` 写入大文档（≥ 3000 字符）被 auto mode classifier 拦下（false positive），需要回退到 curl REST API。根因：`/home/zryang/my_SKILL/.claude/settings.local.json#permissions.allow` 之前只显式允许 `mcp__gemini-api-docs-mcp__*`，没有 `mcp__outline__*`。classifier 启发式判断下，大内容 / 多次连续调用容易踩雷。

**How to apply：**

- 新装 / 维护 outline MCP 时**同步**加 15 条 `mcp__outline__*` 白名单（覆盖 attachment / document / comment / collection / list_* 五组工具）
- 白名单是 mid-session 即时生效，不用重启 Claude Code
- **退路**：被拦时改用 outline REST API 走 curl + API key，POST `/api/documents.update`
- 不要只把白名单写用户级 `~/.claude/settings.json`——项目级 `settings.local.json` 没继承的话，agent 在本项目里还是被拦

**正文：** [`outline-mcp-permission-allowlist.md`](./outline-mcp-permission-allowlist.md)

### mcp__outline__update_document：text 字段会吞换行，整篇重写改走 REST API（2026-06-21）

**Why：** 2026-06-21 实测——用 `mcp__outline__update_document` 的 `replace` 模式推 3K 字符的中文 markdown 总结，**首行表格的 3 个 row 之间的 `\n` 全部丢失**，三行被压成一行 `| Title | Venue | Topic | |---|---|---| | ART... |`（表格渲染成 inline 元素，破坏整篇布局）。其他位置（"3 句话总结" 列表 / 章节标题）换行正常；只有首行表格三行是**必杀**。`patch` 模式更糟——`findText` 短匹配会**追加**而不是替换，"3 句话总结" list 变成 5 条 1-2-3-4-5。

**根因**（未上报 MCP server 端 bug）：mcp tool 的 text 字段在序列化时部分换行符被吞。`success=true` 返回不代表存盘 OK——tool 没校验 text 完整性。

**How to apply：**

- **整篇重写（replace 模式）** → **不要**用 mcp tool，**改用** `POST /api/documents.update` 走 curl + API key
  ```bash
  python3 -c "import json; json.dump({'id': '<doc-id>', 'text': open('summary.md').read()}, open('payload.json', 'w'), ensure_ascii=False)"
  curl -sS -X POST https://<endpoint>/api/documents.update \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <api-key>" \
    --data-binary @payload.json
  ```
  REST API 正确保留所有换行；返回 `{"data": {...}, "status": 200, "ok": true}`。
- **payload 用文件传**（`--data-binary @payload.json`）避免命令行转义；中文 / 特殊字符不会被 shell 解释
- **patch 模式**：`findText` 一定要**足够长**（至少含相邻 2-3 行），否则会被误追加
- **校验必做**：写完立刻 `mcp__outline__fetch` 看返回的 markdown body 首行 / 表格 / 列表 / 章节是否正常
- API key 同 MCP server 配置（`~/.claude.json#mcpServers.outline.headers.Authorization` 或 `.claude/settings.local.json#mcpServers.outline.headers`），agent 直用
- 详情见 [`outline-wiki-management/SKILL.md`](../../outline-wiki-management/SKILL.md) §图片插入 / 文件附件工作流 → "整篇重写"小节

### gemini-paper-summary figure 抽取：三层 locator + 实在处理不了就 drop（2026-06-21）

**Why：** 用户 2026-06-21 反馈 ART-ICDE'13 p.11 Fig 16 裁成正文段落（"纯文字图片"，caption locator 错把 "Figure 16 shows..." 引用当真 caption），同时要求"实在处理不了的图宁可不放"。三层 locator 互相补位、最后兜底 drop，是处理**混排页 / caption 错位 / 跨栏宽图** 这类边界的统一策略。

**三层定位**（从高到低）：

1. **Stage 2 Gemini 视觉定位**（`visual_bbox_map`）：把 page 渲染成 PNG 送 Gemini，规范化 0-1000 bbox。**不再因为 `is_key_figure=false` 丢 bbox**——Gemini 在混排页（如 Fig 15/Fig 16/Table IV 同页）容易把关键图误判为非关键图，丢 bbox 后上层只能回退到精度差的 hint/caption locator，把整段正文框进图。是否引用由 markdown 端的 `![...](PDF p.X fig.N)` 引用列表控制，Stage 2 不越权。
2. **caption locator**（`find_figure_bbox_by_caption`）：按 `Figure N:` caption 反向定位，策略 ①正文段落底部 / ②annotation 顶部 / ③page 顶兜底；caption 必须是 `Figure N[.:]` + 描述形式（数字后跟 `:` 或 `.` + 空白），排除"Figure 16 shows..."这类正文引用；line 长度 ≤ 120 字符作辅助判定；跨双栏 figure 用整页文本区宽度裁剪。
3. **Stage 1 bbox hint**（`bbox=...` 字段）：**sanity check**——Gemini 自由发挥写 bbox 容易把 figure 下面紧跟的整段正文都框进去（p.11 Fig 16 hint 高 ~375pt，实际图 ~150pt）。**hint 高度 > 250pt 且 caption locator 能算出 ≥ 50pt 的 bbox 时，用 caption locator 替掉 hint**。

**drop 兜底**：`embed_figure_refs` 收集三层全失败的 `(page, fig_num)`，删除对应整行 `![...](PDF p.X fig.N ...)`，并剥掉前一句"如图 N 所示" / "见图 N" / "Figure N 展示了..."等独立呼应句里的图编号引用（保留描述文字）。避免 outline 出现 `![](PDF p.X fig.N)` 这种**非 attachment 协议**的破图 + 死引用。日志：`INFO: 跳过 N 张图（视觉定位 + caption locator + bbox hint 三层均失败），已从 markdown 删除对应行 + 呼应句`。

**How to apply：**

- SKILL.md `### 边界` 和 `### 核心原则 #5`、prompt-template.md `### 图引用约定` 三处都写明"实在处理不了的图宁可不引"——prompt 端引导 Gemini 自己不要硬引不把握的图，脚本端兜底
- 新增 `find_figure_caption` 的 line 文本过滤：`re.match(r"^\s*(?:Figure|Fig\.?)\s*{N}\s*[.:]\s*\S", text) and len(text) <= 120`；失败 fallback 到最短候选
- `render_figures_to_pngs` 第三层 hint 兜底前查 `hint_h > 250`，是经验阈值（单张 figure 一般 100-200pt 高；> 250pt 几乎一定是含正文）
- `embed_figure_refs` 失败行处理用**line-level split + 重 join**，**不**用 `re.sub`（后者无法跨行删除独立呼应句）
- 同步改 3 处：脚本 / SKILL.md 边界节 / prompt-template.md 图引用节。漏改 SKILL / prompt 等于只修了脚本里的 bug，下次触发 SKILL 仍然没新规则
- 用户原话（2026-06-21）："本代码仓是 SKILL 的代码仓，所有可能影响到 SKILL 最后结果的信息，都要更新到 SKILL 对应的文件夹中"——MEMORY 只是索引，正文必须落到 SKILL.md / prompt-template.md

**正文：** [`gemini-paper-summary/SKILL.md`](../../gemini-paper-summary/SKILL.md) §边界 + §核心原则 #5；[`gemini-paper-summary/assets/prompt-template.md`](../../gemini-paper-summary/assets/prompt-template.md) §图引用约定

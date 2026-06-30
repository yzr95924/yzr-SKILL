# Outline Wiki 文档风格与 ProseMirror JSON 映射

向 Outline Wiki 写入新文档时，写什么 Markdown、怎么写，应**对齐工作区已有
风格**——本附录集中描述这些约定，并给出 Markdown ↔ ProseMirror JSON 的
映射表，方便理解"为什么这么写"以及"什么写不出来"。

## 目录

- [核心原则](#核心原则)
- [风格速查](#风格速查)
- [Markdown ↔ ProseMirror 节点映射](#markdown--prosemirror-节点映射)
  - §1-§11 节点映射
  - [§12 图片附件与上传流程](#12-图片附件与上传流程)
  - [§13 @mention 用户](#13-mention-用户)
- [OKF agent 可读基线（上传格式控制）](#okf-agent-可读基线上传格式控制)
- [反模式](#反模式)
- [进阶：Markdown 写不出的特性](#进阶markdown-写不出的特性)
- [参考样例](#参考样例)

## 核心原则

### 1. 现有数据 = 风格基线

本仓库内现有约 22 个 collection、200+ 文档，已经沉淀出一套"事实标准"：
以 `list_collections` 拿到的 collection description 为样本，从 `fetch document`
的 `text` 字段读取 Markdown，从原始 ProseMirror JSON（如果返回）的
`marks` 字段读取富文本信息——三处对照即可还原整套规则。

新文档应与这套标准对齐，避免在同一个工作区出现风格漂移。

### 2. 原则：按 ProseMirror JSON 的"投影"写 Markdown

Outline 后端持久化的是 **ProseMirror 节点树**，MCP 工具的 `create_document` /
`update_document` 只接受 `text`（Markdown 字符串）作为输入。

"什么样的 Markdown 写出来最自然"取决于 ProseMirror schema 支持的节点 / mark。
因此：

- 写之前**先想清楚**这条 Markdown 会被解析成哪个 ProseMirror 节点
- **不要**使用 Markdown 表面能写、但 ProseMirror schema 不接受的语法
- **不要**使用 Markdown 表面写不出来、必须靠 UI 才能表达的语法（如指定
  highlight 颜色）；这类需求请走"进阶"小节

### 3. 行宽与 lint

仓库根目录 `.markdownlint.jsonc` 把 MD013 放宽到 120 字符，**新文档
必须遵守**——过长的行用列表嵌套 / 代码块切分，不要硬超。

## 风格速查

| 元素 | 本仓库约定 | 是否独家 |
| --- | --- | --- |
| 顶部结构 | 多数 `# Reference` / `## Reference` 开头，少数无 Reference 直接进主题 | 仓库内事实标准（**不严格统一**） |
| 一级标题 | `#` | 标准 |
| 二级标题 | `##` | 标准 |
| 三级标题 | `###` | 标准 |
| Bullet marker | `*`（不用 `-` / `+`） | 仓库统一 |
| 嵌套层级 | 常用 3–4 层缩进 | 风格偏好 |
| 关键术语高亮 | `==text==`（默认色） | **是**（仓库指纹） |
| 斜体 + 高亮 | `*==text==*` | 复合 |
| 加粗 | `**text**`（少量混用） | 标准 |
| 斜体 | `*text*` | 标准 |
| 行内代码 | `` `code` `` | 标准 |
| 代码块语言 | 必填（`bash` / `json` / `yaml` / `lua` / `nginx` / `java` / ...） | 习惯 |
| Mermaid 标识符 | `` ```mermaidjs ``（**不是** `mermaid`） | **是**（仓库指纹） |
| Mermaid 类型 | 只用 `graph`（TD / LR），未用其他类型 | 仓库习惯 |
| Mermaid 位置 | block-level，**不**嵌在 bullet 子项内 | 与普通代码块相反 |
| Shell 提示符 | `$>` 后接一个空格 | **是** |
| 图片 | `![alt](/api/attachments.redirect?id=...)` | Outline 限定 |
| 图片尺寸 | title 写 `=WxH` 等宽 | 仓库统一 |
| 引用块 | `>` 后接一个空格，偶尔用 | 标准 |
| 表格 | 仅在需要行-列对齐时用 | 偶尔 |
| 删除线 | `~~text~~` 偶尔用（标记已废案 / 旧版本） | 习惯 |
| HTML 标签 | **不**用（除 fenced code block） | 习惯 |
| 自动链接 | `<https://...>` 偶尔用 | 习惯 |
| `<image: ...>` 占位符 | 旧版用法，**已停用**（用 `![alt](/api/attachments.redirect?id=...)`） | 历史遗留 |
| 语言 | 中文叙述 + 英文术语 | 习惯 |
| 行宽 | 遵守 `.markdownlint.jsonc` MD013（见 §3） | 仓库规定 |

## Markdown ↔ ProseMirror 节点映射

### 1. 标题（heading）

| Markdown | ProseMirror 节点 |
| --- | --- |
| `# text` | `{type: "heading", attrs: {level: 1}, content: [{type: "text", text: "text"}]}` |
| `## text` | `{type: "heading", attrs: {level: 2}, content: [...]}` |
| `### text` | `{type: "heading", attrs: {level: 3}, content: [...]}` |

**注意（顶部 H1 起始有 3 种变体）**：

- Outline 推荐**标题**放 `title` 字段，正文不应再以 H1 起笔（避免与
  title 重复）
- 仓库内存量文档**并不统一**——`list_documents` 返回的 30+ 文档里
  至少观察到 3 种顶部结构：

  | 变体 | 例子 | 文档数 |
  | --- | --- | --- |
  | A. `# Reference` 起笔，再进入 `# 主题A` | VPS搭建、DDIA ch8、git 技巧、termux 配置、nvim 管理、Token 获取方式（主体）、Skills 实践 | 多数 |
  | B. `## Reference`（H2） | bazel | 少数 |
  | C. 无 Reference 段，直接进 `# 平台A` / `# 平台B` | Token 获取方式子平台分块（`# 阿里云百炼` / `# GLM`） | 少数 |

- **新建时建议**：优先选 A（与多数存量一致）；选 B 略偏紧凑；选 C
  仅在"文档本身就是平台对比清单"时合理
- 同一篇文档内**不要混用** A/B/C

**H1 内允许嵌套其他 mark**：

```markdown
# **Gemini**
# ==重点== 章节
```

仓库内 `Token 获取方式` 用了 `# **Gemini**`，即 H1 标题内嵌套 strong mark。

### 2. 段落（paragraph）

| Markdown | ProseMirror 节点 |
| --- | --- |
| 普通段落 | `{type: "paragraph", content: [{type: "text", text: "..."}]}` |

仓库内**很少**用纯段落，绝大多数内容通过 bullet 列表承载。

### 3. Bullet 列表（bullet_list）

| Markdown | ProseMirror 节点 |
| --- | --- |
| `* item` | `{type: "bullet_list", content: [{type: "list_item", content: [{type: "paragraph", ...}, ...]}]}` |
| `* item` + 嵌套 | 外层 `list_item` 内含子 `bullet_list` |

- 仓库统一用 `*`（不用 `-` / `+` / `1.`）
- 列表可嵌套任意深度，3–4 层常见
- `list_item` 内**首节点**必须是 `paragraph`（这是 ProseMirror 强约束）

### 4. 高亮（highlight）—— 仓库"指纹" ⭐

| Markdown | ProseMirror mark |
| --- | --- |
| `==text==` | `{type: "highlight", attrs: {color: "<default>"}}` |

- `==...==` 是 Outline 特有的高亮语法
- **Markdown 写法**只能产生**默认色**（典型为黄色 `#FDE68A` 一类）
- 默认色由 Outline 调色板决定，不同版本可能微调
- **彩色高亮**（红 / 橙 / 绿 / 蓝 / 紫等）只能通过 UI 工具栏的色板，或
  直接构造 ProseMirror JSON 实现（见下文"进阶"）

### 5. 其他 mark

| Markdown | ProseMirror mark | 备注 |
| --- | --- | --- |
| `**bold**` | `{type: "strong"}` | 仓库内**少用**，`==...==` 优先 |
| `*italic*` | `{type: "em"}` | 因 `*` 也是 bullet marker，italic 只能出现在文本行内 |
| `` `code` `` | `{type: "code"}` | 行内代码、命令、参数、文件路径 |
| `[text](url)` | `{type: "link", attrs: {href: "url"}}` | 外部资料、API 文档、GitHub |

`==...==` 与 `*...*` 可复合：`*==text==*` 表示「斜体+高亮」，渲染为
italic + 默认色 highlight。

### 6. 代码块（code_block）

| Markdown | ProseMirror 节点 |
| --- | --- |
| ` ```bash ` 开头、` ``` ` 结尾 | `{type: "code_block", attrs: {language: "bash"}, content: [{type: "text", text: "..."}]}` |

- `language` 字段**必填**（仓库约定），用小写
- 命令行提示符统一用 `$>` 后接一个空格（自创约定）
- 命令输出（log、状态、表格）原样粘到代码块内
- **普通代码块**经常嵌在 bullet 列表项内部（保持缩进对齐）
- **mermaid 代码块例外**：必须放在 bullet 之外（block-level），见 §11

**仓库内已观察到的语言标识符**（基于 17 篇文档样本）：

| 语言 | 用途 | 频率 |
| --- | --- | --- |
| `bash` | shell 命令（带 `$>` 提示符） | **最频繁** |
| `json` | Claude Code / OpenCode / API 配置 | 高 |
| `yaml` | Docker Compose | 偶尔 |
| `lua` | Neovim 配置 | 偶尔 |
| `nginx` | Nginx 反向代理配置 | 偶尔 |
| `java` | Java 代码示例 | 各 1-2 例 |
| `python` / `cpp` / `go` | 代码示例 | 各 1-2 例 |
| `mermaidjs` | 流程图（**不是** `mermaid`） | 6 张 |
| `text` | 引用样例（reference 文档用） | 1 例 |

**反例**（仓库内未观察到、应避免）：

- ` ```shell ` / ` ```console ` —— 不存在，统一用 `bash`
- ` ```mermaid ` —— 不存在，统一用 `mermaidjs`
- 空语言 ` ``` ` —— 违反"语言必填"约定

### 7. 图片（image）

| Markdown | ProseMirror 节点 |
| --- | --- |
| `![alt](/api/attachments.redirect?id=<uuid> "=WxH")` | `{type: "image", attrs: {src: "url", alt: "alt", title: "=WxH"}}` |

- `src` 必须走 Outline 自己的 attachment API（`/api/attachments.redirect?id=...`）
- `title` 字段约定写**等宽尺寸** `=WxH`（如 `=600x364`），便于 UI 预览
- 图片通常紧邻对应文字说明，嵌在 bullet 项下

### 8. 引用块（blockquote）

| Markdown | ProseMirror 节点 |
| --- | --- |
| `> text` | `{type: "blockquote", content: [{type: "paragraph", ...}]}` |

仓库内**偶尔**使用，典型场景是引用原始资料原话（如 DDIA 闰秒解释）。

### 9. 表格（table）

Markdown 标准语法：第一行 `| col | col |`，第二行 `|---|---|`，
第三行起为数据行 `| a | b |`。

对应的 ProseMirror 节点：

```text
{type: "table", content: [
  {type: "table_row", content: [
    {type: "table_cell", ...},
    {type: "table_cell", ...}
  ]},
  ...
]}
```

仓库内**仅在需要行-列对齐**的场景使用（如子章节完成日期追踪）。
其他场景仍以 bullet 列表为主——bullet 维护成本更低。

### 10. 有序列表（ordered_list）

| Markdown | ProseMirror 节点 |
| --- | --- |
| `1. item` | `{type: "ordered_list", attrs: {start: 1}, content: [{type: "list_item", ...}]}` |

仓库内**仅在枚举并列项**时使用（如 3 个 clock 异常点）。

### 11. Mermaid 流程图（code_block 变体）

仓库内**实测**（3 篇使用 mermaid 的文档：基本编程语法概念、软路由、存储管理）：

**关键约定**：

- 代码块语言标识符**必须**用 `` ```mermaidjs ``，**不是** `` ```mermaid ``
  - 这是 Outline Wiki 当前的固定写法（与 Mermaid 官方推荐不同）
  - 用 `mermaid` 可能被识别成普通代码块、不渲染为图
- 仓库**只使用** `graph` 系列，**未观察到** `sequenceDiagram` /
  `classDiagram` / `stateDiagram` / `erDiagram` / `gantt` / `pie`
- **block-level 放置**：mermaid 代码块放在 bullet list 之外（独立行），
  **不**嵌在 bullet 子项内——与普通代码块相反

**写法速查**：

| 元素 | 推荐写法 | 例子 |
| --- | --- | --- |
| 方向 | `graph TD`（top-down） / `graph LR;`（left-right，带分号） | `graph TD` |
| 节点 - 矩形 | `A[Label]` | `JDK["Java Development Kit (JDK)"]` |
| 节点 - 圆角 | `B(Label)` | `B(OpenWrt)` / `B(物理卷 PV1)` |
| 节点内换行 | `A[Line1\nLine2]` | `A[Hello.java\nsource code]` |
| 子图 | `subgraph <id>["<label>"]` | `subgraph n1["Java EE: Enterprise Edition"]` |
| 子图显示名 | 直接用中文 | `subgraph 物理磁盘` |
| 边 | `A --> B` | `JDK --> JRE` |
| 带标签的边 | `A -->\|label\| B` | `JDK -->\|包含\| JRE` |
| 多源汇合 | `F & G & H -->\|label\| I` | `F & G & H -->\|lvcreate\| I(逻辑卷 LV1)` |

**完整样例**（取自"存储管理"）：

```mermaidjs
graph TD
    subgraph 物理磁盘
        A[物理磁盘1 /dev/sda] -->|pvcreate| B(物理卷 PV1)
        C[物理磁盘2 /dev/sdb] -->|pvcreate| D(物理卷 PV2)
    end

    subgraph 卷组 VG
        B --> E[卷组 VG1]
        D --> E
        E --> F[物理区域 PE1]
        E --> G[物理区域 PE2]
        E --> H[...]
    end

    subgraph 逻辑卷 LV
        F & G & H -->|lvcreate| I(逻辑卷 LV1)
        F & G & H -->|lvcreate| J(逻辑卷 LV2)
    end

    I --> K[文件系统 XFS/EXT4]
    J --> L[文件系统 EXT4/NTFS]
```

**典型语境**：

- 系统组件关系（Java EE/SE/ME 嵌套、OpenWrt 网络拓扑、Spark 组件）
- 概念分层（Java 三个版本、JDK ↔ JRE ↔ JVM）
- 数据流（Java 参数传递、Java 编译过程、LVM 物理 → 卷组 → 逻辑卷）

**没有观察到的 mermaid 类型**：

- `sequenceDiagram`（时序图）→ 仓库内用**文字描述 + bullet 列表**代替
- `classDiagram`（类图）→ 未见
- `stateDiagram`（状态图）→ 未见
- `erDiagram`（ER 图）→ 未见

如果新文档需要时序图之类的，先确认 Outline 是否支持
`mermaidjs` 对应的图类型，不要直接套用——可能识别失败而显示为代码
块。

### 12. 图片附件与上传流程

图片走 attachment 通道：MCP `create_document` / `update_document` **不
接收文件二进制**，只接受 Markdown 字符串。要把图片或文件嵌进文档，
必须先上传到 Outline attachment API，再在 Markdown 里引用（§7 是
Markdown 语法本身，本节是上传流程）。

**完整上传流程**（3 步）：

1. **预签名上传 URL**：调 MCP `create_attachment(name, contentType, size)`
   拿到 `uploadUrl`（multipart 接收端点）+ 一组表单字段
2. **上传二进制**：用 `curl` 或任意 HTTP multipart 客户端把本地文件
   POST 到 `uploadUrl`，其他表单字段作为额外 part 一并提交。响应通常
   返回 `{success: true, ...}` + attachment 元数据
3. **插入引用**：在 Markdown 里写 `![alt](<attachment.url> "=WxH")`，
   其中 `attachment.url` 形如 `/api/attachments.redirect?id=<uuid>`；
   `=宽x高` 给出渲染尺寸，非图片可省略

**读取附件**：调 MCP `fetch(resource="attachment", id=<id 或完整 redirect URL>)`
返回 short-lived 签名 URL，可直接下载。

**注意事项**：

- `create_document` / `update_document` **不**自动上传本地图片——
  引用一个未上传的本地路径只会在 UI 里渲染成破图
- attachment URL 是 auth-gated：未登录用户访问返回 403，登录 session
  返回 302 重定向到实际文件
- 用 `update_document` + `editMode: "patch"` + `findText` 精准替换
  某段时，可在不动其他内容（注释 / 高亮 / 表格宽度）的前提下把
  mermaid / 占位图换成真图

### 13. @mention 用户

MCP server 暴露 `list_users`，配合 Markdown 语法即可在正文里 @ 到
具体用户。

**用法**：

1. 调 `list_users(query=<关键字>)` 拿到 user 列表（含 `id` 与 `name`）
2. 在 Markdown 写 `@[张三](mention://user/c9a1b2e3-...)`
3. 在 Outline UI 里渲染成可点击的 @mention，点击跳转该用户

| Markdown | ProseMirror mark |
| --- | --- |
| `@[Display Name](mention://user/<userId>)` | `{type: "mention", attrs: {type: "user", id: "<userId>", label: "<name>"}}` |

`list_users` 也可用于"按 email / 名字搜索用户做权限查询"等场景。
注意：**MCP 工具名以 `tools/list` 实际返回为准**——本节描述基于当前
server 暴露的工具集，不同 self-hosted 部署可能略有差异。

## OKF agent 可读基线（上传格式控制）

> **目的**：推到 Outline 的文档要能被 agent 稳定**读回理解**——
> `outline-wiki-search` 读回 markdown body、外部 OKF 消费端解析、未来检索
> 分块，都依赖一个可机读的元数据头 + 可预测的正文结构。OKF =
> [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
> （"markdown + frontmatter、人 / agent 都能读"）。权威实现见
> [`llm-wiki-compiler`](https://github.com/atomicstrata/llm-wiki-compiler)（OKF
> 生产端 + 消费端）；本仓库 [`llm-wiki-management`](../../llm-wiki-management/SKILL.md)
> 落地了 v0.1 子集，**Outline 侧沿用同一定义**，只为 Outline 的硬约束做载体适配。

### 载体选型（实测，2026-07-01）

OKF 标准载体是 `---...---` YAML frontmatter。但 Outline 的 MCP
`create_document` / `update_document` 把 Markdown 解析成 **ProseMirror** 节点
再序列化，`---...---` 过不了往返——实测在同一 server 上写两篇探针文档读回：

- `---...---` frontmatter：`---` 被吃掉，YAML 键值**泄漏成可见正文**（`title:
  …` 还会和 Outline title 字段重复），不是隐藏元数据
- ` ```yaml ` 围栏代码块：存成 `code_block` 节点**逐字保留**（行间 `\n` 完整存活），

因此 Outline 侧的 OKF 载体 = **正文首块 ` ```yaml ` 围栏**（标准字段，适配载体），
而**不是** `---...---`。这是有意的平台适配，非字面合规——见末尾"与标准的关系"。

### 两个 Outline 适配点

1. **title 外置**：OKF 的 `title` 由 Outline **原生 title 字段**承载，**不**写进
   正文块（正文裸写 H1 会与 title 重复；裸写 `---...---` 又会泄漏，见上）。
2. **元数据载体 = 正文首块 ` ```yaml ` 围栏**：其余 OKF 字段放正文**第一个**块的
   yaml 围栏代码块。ProseMirror 存成 `code_block` 原样保留；读回时这块在最前，
   agent 一眼可解析。

### OKF 元数据块字段（正文首块 yaml 围栏）

> **硬门槛只有 `type`**：OKF 消费端的宽容模型（见 `llm-wiki-compiler`
> `okf-read.ts`）是"frontmatter 解析失败或缺 `type` 才跳过该文档，其余一律
> 容忍"。所以 agent 能否读回，**只取决于 `type` 是否非空**；其余字段都是
> 推荐项，提升检索 / 摘要 / 时效质量，但不卡读回。

| 字段 | 级别 | 值 / 约束 |
| --- | --- | --- |
| `type` | **必填**（唯一硬门槛） | 非空；见下方 type 枚举 |
| `description` | 推荐 | 一句话摘要；agent 检索 / 索引摘要从它来 |
| `tags` | 推荐 | 数组，≥ 1 个，如 `[llm, systems]` |
| `created` | 推荐 | `YYYY-MM-DD`（内容首次成稿日） |
| `updated` | 推荐 | `YYYY-MM-DD`；每次大改写同步 |
| `x-outline` | 可选 | Outline 专属溯源（见下），生产者命名空间块 |
| `okf_version` | **不放本块** | 标准只在 bundle 根 `index.md` 声明；单篇 Outline 文档无 bundle，故不写 |
| `title` | —— | **不写进块**——由 Outline title 字段承载（= OKF `title`） |

> **`x-outline` 扩展块**（OKF 允许 `x-<producer>` 私有键，消费端保留不动）：
> 放 Outline 特有、标准字段表达不了的溯源信息，例如 `collection`（所属
> Collection）、`docId`、`source-skill`（产出该文的 skill）。标准字段能表达的
> 不要塞进这里。
>
> **时间戳与标准的分歧**：真 OKF 用单个 `timestamp`；本仓库 wiki 子集刻意用
> `created` + `updated`（双字段，便于 lint 抓腐烂）。Outline 侧**沿用 wiki 的
> `created`/`updated`** 保持跨 skill 一致，不单独切回 `timestamp`。注意它们是
> **写入方维护的内容版本时间戳**，与 Outline 系统自动维护的 `createdAt` /
> `updatedAt` 不是一回事，不要用后者替代。

### type 枚举

- **知识页类**（同 wiki，跨 skill 一致）：
  - `entity`——具体系统 / 产品 / 团队的事实页
  - `concept`——概念 / 术语 / 原理
  - `source`——单一外部资料（论文 / 博客 / spec）的摘要
  - `comparison`——多对象横向对比
  - `synthesis`——跨来源综合
- **Outline 专属扩展**：
  - `design-doc`——设计文档（`design-doc-edit` 的产出）
  - `paper-note`——论文笔记（`gemini-paper-summary` 推上来的）
  - `runbook`——操作手册 / SOP / 故障处理
  - `reference`——速查 / API / 配置清单
  - `guide`——教程 / how-to

`type` 优先取上表枚举值；确实不属于任何一类时可自定义 kebab-case 值（OKF §4.1
本就是开放集），但要在 `description` 里说清这是什么类型。

### 正文结构纪律（让 agent 能分块导航）

yaml 块之后的正文按以下规则写——这些不是装饰，是 agent 检索 / 分块能
工作的前提：

1. yaml 块是正文**第一个**块，前面无任何内容（含空 Reference 段）。
2. 正文标题从 `##` 起（H1 = title 已外置），**不跳级**；**同级标题文字不
   重复**——agent 用标题文本做锚点 / 分块单元，重名标题会撞锚。
3. **一篇一主题**：一个主题一篇文档，不把多个不相关主题塞进一篇——
   agent 的检索粒度 = 文档。
4. 链接用 Outline 文档链接或绝对 URL，**不**裸写本地相对路径（agent 解析
   不到，渲染也是死链）。
5. 富文本降级照旧：彩色高亮等 Markdown 写不出来的特性走"进阶"小节，
   **不**在 yaml 块里塞渲染指令。

### 最小骨架示例

Outline title 字段填 `"LLaMA-3 架构要点"`；正文：

````markdown
```yaml
type: paper-note
description: LLaMA-3 的注意力 / 位置编码 / 训练数据要点速记
tags: [llm, architecture, meta]
created: 2026-07-01
updated: 2026-07-01
x-outline:
  collection: 论文笔记
  source-skill: gemini-paper-summary
```

## 背景

* ...
````

> 改写已有文档时，用 `update_document` + `editMode: "patch"` + `findText`
> 精准替换 yaml 块（`findText` 取整块含围栏行），并把 `updated` 改成当天，
> 不动正文其他部分。

### 与标准的关系

本格式是 OKF v0.1 的 **Outline 适配子集**：字段语义对齐标准（`type` 硬门槛、
`x-<producer>` 扩展块、宽容消费模型），但载体用 ` ```yaml ` 围栏而非 `---...---`
（Outline 往返实测不支持，见"载体选型"）。任何 OKF 消费端能"尽力读取"这种文档
（`type` 在、字段名标准），但**不**声称字面合规。要把一批 Outline 文档导成
完全合规的 OKF bundle，需另写转换（围栏→`---...---`、补 bundle 根 `index.md`
声明 `okf_version`），不在本 skill 范围。

## 反模式

以下写法**应避免**，会导致工作区风格漂移或渲染异常：

- 用 `-` 或 `+` 起 bullet（破坏统一）
- 期望 `==text==` 出现彩色高亮（Markdown 写不出来）
- 私造非 Outline 支持的语法（如 `!!! warning`、`{% hint %}`）
- 用 HTML 标签强行实现富文本（`<mark>`、`<details>` 等）；fenced code
  block 内的 HTML 标签例外
- 标题字段与正文一级 H1 完全重复
- 引入外部私有扩展（如 `:::tip`、MathJax 等）
- 表格内嵌代码块（Markdown 不允许，可改用 bullet + 子代码块）
- 写纯空白或装饰性 emoji 占位（如 `🎉🎉🎉`）
- 在 bullet 列表中放裸反斜杠 `* \` 当分隔符（仓库内偶有出现但语义不清，
  应改用空行或新章节）
- 同一篇文档里混用 `# Reference` / `## Reference` / 无 Reference 三种
  顶部结构
- Mermaid 标识符用 `mermaid` 而非 `mermaidjs`（仓库内 100% 用
  `mermaidjs`，用 `mermaid` 可能不被识别为图）
- Mermaid 代码块嵌在 bullet 子项内（应放在 bullet 之外，block-level）
- 写新文档时用 `<image: ...>` 占位符（已停用，应改为
  `![alt](/api/attachments.redirect?id=...)`）
- 正文裸写 `---...---` YAML frontmatter——Outline 往返会**吃掉 `---`**、把
  YAML 泄漏成可见正文（`title:` 还会和 Outline 字段重复），不是隐藏元数据
  （2026-07-01 实测确认）；OKF 元数据只走正文首块 ```yaml 围栏
- 把 OKF `title` 既写进 Outline title 字段又写进 yaml 块（重复）——title
  只外置，yaml 块内不出现 `title`
- 在单篇文档的 yaml 块写 `okf_version`——标准只在 bundle 根 `index.md` 声明，
  单篇 Outline 文档无 bundle，写了反而背离标准
- OKF 元数据块不放在正文首块（前面垫了 Reference 段 / 空段）——agent
  读回时拿不到"开头即元数据"，分块失效

### 偶尔可见但**不推荐**的写法

- `~~删除线~~` 偶尔用于标记"已废案 / 旧版本"内容（如
  `* ~~版本选择~~` + `* ~~当前选择==0.86.1==~~`），渲染为横线文本
  - 适用：明确已下线的方案
  - **不推荐**：作为"视觉强调"使用（应改用 `==...==`）
- `<https://...>` 自动链接偶尔用，但与 `[text](url)` 混用会显得风格
  不统一——同一篇内只选一种

## 进阶：Markdown 写不出的特性

以下 ProseMirror 节点在 Markdown 层面**无法直接表达**，必须直接构造
ProseMirror JSON：

### 彩色高亮

仓库内**实测**（截至 2026-06-20，14 文档 + 22 collection 抽样）：

| 抽样范围 | 非默认色 highlight | 备注 |
| --- | --- | --- |
| 文档正文（14 篇） | **0 例** | 全部 `==text==` 渲染为默认色 |
| Collection description（22 个） | 1 例 | "读书笔记" collection 的 `#FA551E`（orange） |

**结论**：仓库内**几乎没有使用彩色高亮**——文档正文只用默认黄色，
唯一一处橙色高亮出现在 collection description 文本里。因此：

- 默认 `==text==` 完全够用，与存量 99% 一致
- **不建议**为追求"颜色区分"而改用 JSON 注入彩色
- 走 UI 工具栏选色的场景极少

**如确实需要彩色**，对应的 ProseMirror JSON 结构：

```json
{
  "type": "text",
  "text": "笔记还是尽量尝试用中文描述",
  "marks": [
    { "type": "highlight", "attrs": { "color": "#FA551E" } }
  ]
}
```

**可用色值**（Outline 调色板，约 6 色，具体以版本为准）：

| 色 | hex（推测） |
| --- | --- |
| 🟡 Yellow（默认） | `#FDE68A` |
| 🟠 Orange | `#FDBA74` |
| 🔴 Red | `#FCA5A5` |
| 🟢 Green | `#86EFAC` |
| 🔵 Blue | `#93C5FD` |
| 🟣 Purple | `#C4B5FD` |

**写入路径**：

1. 在 Outline UI 里选中文字 → highlight 工具栏 → 选色（最简单）
2. 通过 REST API 写 ProseMirror JSON（绕开 MCP）——超出本 skill 覆盖范围
3. 在 MCP `update_document` 走"非 markdown 模式"——**目前官方 MCP 文档
   未列此能力**，不建议尝试

**当前 MCP 写入结论（2026-06 复测）**：

- `create_document` / `update_document` 只接受 Markdown 字符串入参，
  **不接受原始 ProseMirror JSON**
- Markdown `==text==` 只能产生默认色高亮，无法指定颜色
- 因此彩色高亮**无法通过 MCP 写入**——如需，走 Outline UI 工具栏，
  或直接调 REST API `POST /api/documents.update` 时附 `proseMirrorDoc`
  参数

**实操建议**：保持 `==text==` 默认色一致；如确实需要颜色区分语义层级，
**优先用 emoji**（⚠️ 🔑 ✅ ❌）或 `**bold**`，不依赖颜色。

### 其他 Markdown 不支持但 ProseMirror 支持的特性

- 任务列表（task list）`{type: "checkbox_list"}` —— Outline 支持，
  Markdown 不支持
- 嵌入文件（attachment）`{type: "attachment"}` —— 通常通过图片插入
- 数学公式（math）`{type: "math"}` —— Outline 不内置支持
- 折叠块（details）`{type: "details"}` —— Outline 不支持

写入这些节点同样需要直接构造 ProseMirror JSON，**走 MCP Markdown 输入
无法实现**。

## 参考样例

### 良好样例（与现有风格一致）

```markdown
# Reference

* [The Adaptive Radix Tree: ARTful Indexing for Main-Memory Databases - ICDE'13](https://...)

# 概述

* 核心思想：将 trie 节点压缩为 path-compressed 形式，降低空间开销
  * 节点分为 4 类：Node4 / Node16 / Node48 / Node256
    * 根据子节点数量动态选择最合适的节点类型

# 实现细节

* 节点扩容 / 收缩
  * Node4 → Node16：插入导致子节点数超过 4

    ```bash
    $> ./configure --disable-optimizations
    ```
  * 扩容触发 lazy expansion（惰性展开）

# 适用场景

* ==In-memory== 数据库索引
  * 树高通常 ≤ 8 → 单次查找 ≤ 8 次 cache miss
```

### 反例（破坏风格）

```markdown
# Adaptive Radix Tree             ← 与 title 字段重复
- Reference                       ← 用 `-` 起 bullet，破坏统一
  - [paper](url)
## 概述
论文提出了ART索引……                  ← 大段纯段落，不分 bullet
```

> **判断方法**：写完一段，先问自己"这段会被 ProseMirror 解析成什么
> 节点？"——如果答案是"paragraph"，而仓库内同类文档用的是
> `bullet_list`，就拆成 bullet。

## 参考

- [Outline 编辑器支持的 ProseMirror 节点类型](https://github.com/outline/outline/tree/main/shared/editor/nodes)
- [Outline 编辑器支持的 mark 类型](https://github.com/outline/outline/tree/main/shared/editor/marks)
- 仓库根目录 `.markdownlint.jsonc`（行宽等 lint 规则）
- 本 skill 主页 [SKILL.md](../SKILL.md)

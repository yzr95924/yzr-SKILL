---
name: yzr-md-to-html
description: |
  把本地 Markdown 文件或目录转成自包含 HTML：深色主题、侧边栏目录、代码高亮内联，
  公式按需 KaTeX 渲染，Mermaid 图默认转 ASCII 离线，双击即开。
  当用户想把 md / Markdown 转成 HTML、导出成能直接打开 / 双击的网页、批量转换
  笔记目录、把转换产物发给别人或上传分享、要自定义模板或样式时使用。
  不适用：从零写网页或前端页面、搭静态站点与部署发布、HTML 反向转 Markdown、
  转 PDF、实时预览与在线编辑、Outline 上传。
---

## 输入与输出

- **输入**：一个 `.md` 文件，或一个目录（批量转目录下 `*.md`）
- **输出**：同名 `.html`，单文件自包含、双击即开；目录输入就地逐篇生成
- **参数**：以 `python3 tools/md_to_html.py --help` 为单一来源（argparse 定义，此处不重抄）；
  脚本按自身路径定位资产，任意 cwd 可调用
- **前置**：Python ≥ 3.7，无需 pandoc；依赖清单以脚本 `DEPENDENCIES` 常量为准，缺依赖时
  脚本打印 pip 安装命令；文档含 Mermaid 时另需 Node + beautiful-mermaid（版本 SSOT 在
  `tools/mermaid_to_ascii.mjs` 常量，缺时打印 npm 安装命令）；不含 Mermaid 的文档不需要 Node
- **模板变量**（`--template` 传入的 Jinja2 模板里用，不在 `--help` 范围内）：`content` 正文、
  `toc` 目录、`styles` 主题 CSS、`pygments_css` 高亮 CSS、`title`、`lang`，及布尔开关
  `has_math` / `has_mermaid` / `has_toc`（控制挂对应 CDN 与侧边栏）

## 执行原则

- **统一入口**：转换一律跑 `tools/md_to_html.py`，不现场手拼 HTML、不用 md 库自建管线——
  裸跑取证里三次隔离会话对同一任务产出三种互不相容的产物（主题浅 / 深 / 自适应各一，同输入
  体积差 248 倍）。脚本消灭的是方差、重复劳动与离线可靠性风险，不是"agent 写不对"
- **离线优先**：文档含公式才挂 KaTeX；Mermaid 默认转 ASCII，转换失败或不支持的块（gantt /
  mindmap 等）才回退挂 CDN——产物承诺双击离线可开，普通 README 不该背公式图表的网络请求
- **不乱改**：主题、目录、内容结构以脚本默认值为准；新增原文没有的元素（导航、索引页）或
  改写标题是改内容不是转换。换风格走 `--template` / `--style`，去目录走 `--no-toc`
- **通知口径不复述**：公式联网、Mermaid 回退、缺依赖这些通知由脚本自行检测打印（含哪个文件
  哪个块与原因），正文与转述都不另立口径

## 工作流

1. 跑 `python3 tools/md_to_html.py <文件或目录>`（输出路径、标题、模板等参数见 `--help`）
2. 缺依赖：把脚本打印的 pip / npm 安装命令转呈用户确认，不自行猜版本安装
3. 汇报产物 `.html` 路径（双击即开）；目录输入报转换数量；单篇失败（如目录下没有 `.md`，
   脚本会报错）如实转报不静默跳过；脚本打印的公式 / 回退通知原样转达
4. 用户要多篇合成一个 HTML：不做跨文档合并，请用户先拼成单个 `.md` 再转
5. 用户要上传分享：已配置 `agent-html-drop` MCP 时调用其上传工具推 `.html`；未配置就把
   本地路径交给用户，不提供其他上传方式（不 rsync 推 server、不写部署配置）

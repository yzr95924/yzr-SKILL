---
name: yzr-md-to-html
description: |
  当用户想把一份本地 Markdown 文件 / 目录（README / 技术文档 / 笔记 / 论文草稿）转成
  自包含、双击即可在浏览器打开的 HTML 时使用本 skill：深色阅读主题 + 侧边栏目录 + 代码
  高亮，公式和 Mermaid 图表都能正常呈现，可自定义模板。
  触发："把这个 README 转成好看的 HTML 发给同事" / "这份设计文档有公式和流程图，导出成能直接
  打开看的网页" / "把 notes/ 目录下的 .md 批量转成 html" / "转成 html 后用 agent-html-drop
  上传分享"。只要用户明确要"本地 .md → 自包含 HTML 文件"的单向转换——即使没提 skill 名，
  也务必使用本 skill。
  不适用：从零写网页 / 前端页面、文档站 / 静态站点生成与部署发布（要托管上线
  的在线网页）、Markdown → PDF 或其它格式、HTML → Markdown 反向、实时预览 / 在线编辑器、
  上传到 Outline Wiki
metadata:
  author: Zuoru YANG
  modify time: 2026-09-23
  category: document-conversion
---

# yzr-md-to-html

把本地 Markdown 转成**自包含、双击即可浏览**的 HTML：深色阅读主题 + 侧边栏目录 + 离线代码高亮，
公式 / Mermaid 按需才联网（完整口径见执行原则 2）

## 输入与输出

- **输入**：一个 `.md` 文件，或一个目录（批量转该目录下所有 `*.md`）
- **输出**：单个自包含 `.html`（CSS 与 Pygments 高亮全部内联，公式 / 图表按需渲染）
- **参数与默认值以 `python3 tools/md_to_html.py --help` 为单一来源**（argparse 定义，此处不
  重抄）；脚本按自身路径定位 assets / wrapper，任意 cwd 可调用。文件输入默认生成同名 `.html`；
  目录输入默认就地生成，`--title` 默认取首个 `#`
  一级标题再退回文件名
- **前置条件**：Python ≥ 3.7，无需 pandoc；依赖清单以 `tools/md_to_html.py` 的 `DEPENDENCIES`
  常量为准，缺依赖时脚本打印 `pip install` 命令。含 Mermaid 且未加 `--no-mermaid-ascii` 时另需
  Node + `beautiful-mermaid`（缺时 wrapper 打印含版本号的 npm 安装命令，版本 SSOT：
  `tools/mermaid_to_ascii.mjs` 的 `BEAUTIFUL_MERMAID_VERSION`）；不含 Mermaid 的文档不需要 Node

**自定义模板可用变量**（`--template` 传入的 Jinja2 模板里用，不在 `--help` 范围内）：
`{{ content }}`（正文 HTML）、`{{ toc }}`（目录 HTML）、`{{ styles }}`（默认主题 CSS）、
`{{ pygments_css }}`（代码高亮 CSS）、`{{ title }}`、`{{ lang }}`，
以及布尔开关 `{{ has_math }}` / `{{ has_mermaid }}` / `{{ has_toc }}`（控制是否挂对应 CDN / 侧边栏）

## 执行原则

1. **直接跑脚本，不自创 HTML**：转换逻辑、主题、CDN 挂载都在 `tools/md_to_html.py`，
   agent 不要现场拼 HTML 或现写 markdown 库调用——保证产物一致、主题统一、扩展行为可预期
2. **按需挂 CDN**：脚本检测到 `$` 才挂 KaTeX CDN；Mermaid 默认转 ASCII（离线），只有
   转换失败 / 不支持的图类型（gantt / mindmap 等）才回退挂 Mermaid CDN；
   不要无脑给所有文档挂全套 CDN（普通 README 不该背公式 / 图表的网络请求与加载耗时）
3. **深色主题默认**：默认 GitHub-dark 纯深色；
   要彻底换风格走 `--template` / `--style`
4. **一次一份或一次一目录**：不做跨文档合并；多份想合成一个 HTML 请先拼成一个 `.md`
5. **ASCII 转换可关**：不想转 ASCII 时用 `--no-mermaid-ascii` 强制走 Mermaid CDN

## 工作流

```text
1. 确认输入 .md 路径（或目录）；首次使用确认依赖已装（见「输入与输出」）
2. 跑脚本：
     python3 tools/md_to_html.py <input.md> [-o <output.html>]
   批量：把 <input.md> 换成目录路径即可
3. 把生成的 .html 路径告诉用户（双击即可浏览）
4. 脚本输出含公式 / Mermaid 回退需联网的通知时，原样转达用户（通知由脚本自己检测打印，不必复述口径）
5. 上传 / 分享（可选）：产物本是本地自包含文件、不需要上传；用户要分享且 agent 已配置
   `agent-html-drop` MCP 时，调用其上传工具推 `.html` 即可——不提供其他上传方式（不经
   rsync 推 server、不写部署配置）；未配置就把本地路径交给用户
```

## 参考样例

### 样例一：单篇技术文档（最常见）

```bash
python3 tools/md_to_html.py docs/design.md
# → 生成 docs/design.html：深色主题 + 侧边栏目录 + 代码高亮
```

### 样例二：批量转换整个目录

```bash
python3 tools/md_to_html.py notes/
# → notes/ 下每个 .md 就地生成同名 .html
```

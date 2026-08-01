---
name: yzr-md-to-html
description: 用户给一份本地 Markdown（README / 技术文档 / 笔记 / 设计文档 / 论文草稿），想转成一个自包含、双击即可在浏览器浏览的 HTML 文件时使用本 skill。默认套深色阅读主题（GitHub-dark 风格，附右上角明暗切换），自带侧边栏目录 TOC 与离线代码语法高亮（Pygments），并按需自动启用数学公式（KaTeX）与 Mermaid 图表——只有源文件里真出现 `$` 或 mermaid 代码块才会挂对应 CDN，普通文档零额外网络请求。支持 `--template` 传入自定义 HTML 模板覆盖默认主题；可选 `--deploy` 经 rsync+SSH 把产物推到 server web 目录并给出访问 URL（命名 target 配置，推送即公开发布、需先确认）。不适用场景：上传到 Outline Wiki（走 yzr-outline-wiki-upload）、PDF 转 Markdown（走 yzr-gemini-pdf-summary）、HTML 反向转 Markdown、实时预览编辑器。常见触发："把这个 README 转成好看的 HTML 发给同事" / "这份设计文档有公式和流程图，导出成能直接看的网页" / "把 notes/ 目录下的笔记批量转成 html" / "把这个 md 转成 html 推到我 server 上发个链接"。
metadata:
  author: Zuoru YANG
  modify time: 2026-08-01
  category: document-conversion
---

把一份本地 Markdown 转成**自包含、双击即可在浏览器浏览**的 HTML 文件。默认套一套
**深色阅读主题**（GitHub-dark 风格，附明暗切换按钮），自带侧边栏目录 TOC、离线代码
语法高亮（Pygments），并**按需**自动启用数学公式（KaTeX）与 Mermaid 图表——只有源文件
里真出现 `$` 或 mermaid 代码块才会挂对应 CDN，普通文档零额外网络请求。

> 依赖：Python ≥ 3.7；Python 包清单（单一来源）见 `scripts/md_to_html.py` 的 `DEPENDENCIES`
> 常量——直接跑脚本即可，缺包时脚本报错并给出 `pip install` 命令。无需 pandoc、无需 Node。

## 何时使用 / 不使用

### 使用

- 用户给一份本地 `.md`（README / 技术文档 / 笔记 / 设计文档 / 论文草稿），想要一个能直接打开看的 HTML
- 文档含代码块 / 公式 / 流程图，希望它们在产物里被正确渲染
- 想批量把一个目录下的 `.md` 全转成 HTML

### 不使用

- **上传到 Outline Wiki** → 走 `yzr-outline-wiki-upload`（产物形态是 wiki 文档，不是本地 HTML）
- **PDF → Markdown** → 走 `yzr-gemini-pdf-summary`
- **HTML → Markdown**（反向）→ 本 skill 不做
- 想要实时预览 / 在线编辑器 → 本 skill 是一次性导出，不是编辑器

## 输入 / 输出

| 字段 | 必选 | 说明 |
| --- | --- | --- |
| 输入路径 | ✓ | 一个 `.md` 文件，或一个目录（批量转该目录下所有 `*.md`） |
| `-o` / `--output` | ✗ | 文件输入：输出 `.html` 路径（默认同名 `.html`）；目录输入：输出目录（默认就地生成） |
| `--title` | ✗ | `<title>` 与浏览器标签名；默认取首个 `#` 一级标题，再退回文件名 |
| `--template` | ✗ | 自定义 Jinja2 HTML 模板路径，覆盖默认主题（可用变量见下） |
| `--style` | ✗ | 自定义 CSS 路径，覆盖默认深色主题 |
| `--no-toc` | ✗ | 关闭侧边栏目录 |
| `--lang` | ✗ | `<html lang>`，默认 `zh-CN` |
| `--deploy <target>` | ✗ | 转换后 rsync+SSH 推送到配置里的命名 target，打印访问 URL（发布即公开，推送前确认） |
| `--deploy-config <path>` | ✗ | 部署配置 JSON 路径（默认 `./.md2html-deploy.json` → `~/.config/md2html/deploy.json`） |
| `-y` / `--yes` | ✗ | 跳过推送前确认（agent / 脚本用；推送即公开发布） |

输出：单个自包含 `.html`（CSS 与 Pygments 高亮全部内联；KaTeX / Mermaid 按需走 CDN）。

**自定义模板可用变量**（`--template` 传入的 Jinja2 模板里用）：
`{{ content }}`（正文 HTML）、`{{ toc }}`（目录 HTML）、`{{ styles }}`（默认主题 CSS）、
`{{ pygments_css }}`（代码高亮 CSS）、`{{ title }}`、`{{ lang }}`，
以及布尔开关 `{{ has_math }}` / `{{ has_mermaid }}` / `{{ has_toc }}`（控制是否挂对应 CDN / 侧边栏）。

## 执行原则 / 边界

1. **直接跑脚本，不自创 HTML**：转换逻辑、主题、CDN 挂载都在 `scripts/md_to_html.py`，
   agent 不要现场拼 HTML 或现写 markdown 库调用——保证产物一致、主题统一、扩展行为可预期
2. **按需挂 CDN**：脚本检测到 `$` 才挂 KaTeX、检测到 mermaid 代码块才挂 mermaid.js；
   不要无脑给所有文档挂全套 CDN（普通 README 不该背公式 / 图表的网络请求与加载耗时）
3. **深色主题默认**：默认 GitHub-dark，附右上角明暗切换按钮（`localStorage` 记忆偏好）；
   要彻底换风格走 `--template` / `--style`
4. **一次一份或一次一目录**：不做跨文档合并；多份想合成一个 HTML 请先拼成一个 `.md`

## 工作流 / 步骤

```text
1. 确认输入 .md 路径（或目录）；首次使用确认依赖已装（见前置条件）
2. 跑脚本：
     python3 yzr-md-to-html/scripts/md_to_html.py <input.md> [-o <output.html>]
   批量：把 <input.md> 换成目录路径即可
3. 把生成的 .html 路径告诉用户（双击即可浏览）
4. 若源文档含公式 / Mermaid，提醒用户首次打开需联网加载 CDN（离线则这两类不渲染，
   代码高亮与基础排版仍正常——Pygments 是离线的）
```

## 部署到 server（--deploy）

转换后可经 **rsync over SSH** 把产物推到 server 的 web 目录，直接拼出可访问 URL。server 信息
（host / path / base_url）写在 JSON 配置里，按命名 target 复用。

**配置文件**（默认 `./.md2html-deploy.json`，其次 `~/.config/md2html/deploy.json`；完整样例见
`assets/deploy-config.example.json`）：

```json
{
  "targets": {
    "prod": {
      "host": "user@example.com",
      "path": "/var/www/notes",
      "base_url": "https://notes.example.com"
    }
  }
}
```

每个 target 必填 `host` / `path` / `base_url`；可选 `port`（SSH 端口，默认 22）、
`rsync_flags`（额外 rsync 参数，如 `--delete` 做整站同步）。

**安全模型**（重要）：

- 只走 **SSH key 认证**——靠本机 ssh agent / `~/.ssh/config`，skill **不碰私钥或密码**；连不上
  让用户查自己的 SSH 配置，不要把密码塞进配置或命令行
- **发布即公开**：推送会把内容公开到 `base_url`。**agent 推送前必须先向用户确认 target 与将生效
  的 URL**，确认后再带 `-y` 执行；交互命令行会问 y/n，非交互环境（agent / 管道）不传 `-y` 直接拒绝
- 默认**不删远端文件**（无 `--delete`）；目录批量部署只排除 `.md` 源，其余（含图片 / 资源）一并发布

**依赖**：本机装 `rsync`（macOS 自带；Debian/Ubuntu `apt install rsync`）+ SSH 可达 target host。

## 参考样例

### 样例一：单篇技术文档（最常见）

```bash
python3 yzr-md-to-html/scripts/md_to_html.py docs/design.md
# → 生成 docs/design.html：深色主题 + 侧边栏目录 + 代码高亮
```

### 样例二：带公式和流程图的论文草稿

```bash
python3 yzr-md-to-html/scripts/md_to_html.py draft.md -o draft.html
# draft.md 含 $E=mc^2$ 与 mermaid 块 → 产物自动挂 KaTeX + Mermaid CDN
```

### 样例三：批量转换整个目录

```bash
python3 yzr-md-to-html/scripts/md_to_html.py notes/
# → notes/ 下每个 .md 就地生成同名 .html
```

### 样例四：转换并推送到 server

```bash
python3 yzr-md-to-html/scripts/md_to_html.py draft.md --deploy prod -y
# → 生成 draft.html → rsync 推到 prod target → 打印 https://notes.example.com/draft.html
# -y 跳过确认；agent 推送前须先向用户确认 target 与 URL
```

## 前置条件

- Python ≥ 3.7
- Python 依赖清单的**单一来源**：`scripts/md_to_html.py` 的 `DEPENDENCIES` 常量
- 直接跑脚本即可；缺包时脚本报错并列出 `pip install` 命令（不抛裸 ImportError 栈）
- （仅 `--deploy` 用）本机 `rsync` + SSH 可达 target host（认证走你自己的 ssh key，skill 不碰密钥）
- （仅 `--deploy` 用）一份 `.md2html-deploy.json` 配置（样例见 `assets/deploy-config.example.json`）

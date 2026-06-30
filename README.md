# My SKILLs

这个仓库主要为个人常用的自定义 SKILL 合集，本身也是一个生成个人常用的 skills 的仓库

## 快速开始（开发环境）

首次使用本仓库前，建议跑一次依赖安装脚本，把以下工具链备齐：

| 工具 | 用途 | 来源 |
| --- | --- | --- |
| `pyyaml` | 跑 `yzr-skill-creator/scripts/quick_validate.py` 校验 SKILL.md frontmatter | pip |
| `ruff` | Python 格式化 + lint（`pyproject.toml` 配 py37 + 120 行宽） | pip |
| `markdownlint-cli` | Markdown 行宽与 lint（`.markdownlint.jsonc` 配 MD013 ≤ 120） | npm |

```bash
python3 scripts/install-dev-deps.py
```

脚本特点：

- **幂等**：重复跑不会重复安装
- **跨平台**：macOS / Debian / WSL 都能跑；PEP 668 保护的环境自动加
  `--break-system-packages`
- **自检**：装完逐个 `verify` 并打印版本号；若某个工具不在 PATH，会用
  `python3 -m <tool>` 回退检测并提示

可选环境变量：

- `PYTHON=python3.11` 指定 Python 解释器
- `SKIP_NPM=1` 跳过 npm 包（只装 Python 工具）
- `SKIP_PIP=1` 跳过 pip 包（只装 npm 工具）

> 提示：Homebrew Python 3.12+ 默认启用 PEP 668。脚本自动加
> `--break-system-packages`，把工具装到 `~/Library/Python/<ver>/bin/`。
> 若 `ruff` / `markdownlint` 不在 PATH，可加：
> `export PATH="$HOME/Library/Python/3.14/bin:$PATH"` 到 `~/.zshrc`。

## 设计原则
- 主要参考
  - [Claude 官方指导](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
  - [Claude 官方生成 skill 的 skill](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
- 具体的实现原则，参考 `./yzr-skill-creator`

## SKILLs 分类

> 每个子目录即一个独立 skill。完整名单与简介见 [CLAUDE.md](./CLAUDE.md) 顶层结构。

按职责分三类：

- **知识库**（本地 / 私有，复利累积型）：
  - `llm-wiki-management` —— 单 wiki 内 ingest / query / lint / memory
  - `llm-workspace-management` —— 多个 wiki 之上的全局视图（INDEX.md / STATS.md / MEMORY/）+ 跨 wiki Q&A / xref / lint
- **写作**：
  - `design-doc-edit` —— 设计文档写作（强制骨架 + 场景/方案分析）
- **元 skill**：
  - `yzr-skill-creator` —— 创建 / 改进 / 评估 skill 本体

外部 skill（依赖项，非本仓所有）：`outline-wiki-{setup,search,upload}` / `gemini-paper-summary` 等按需 `npx skills add` 接入。

## 代码仓规范

- 所有 SKILL 名字与起对应的文件夹名字保持一致，对应的文件夹下必须包含 `SKILL.md` 文件，其他目录结构可以先创建，后面再扩展；
- 所以 Markdown 文件需要进行格式化和 lint 操作，确保格式统一；
- 所有 Python 文件统一走 `ruff`（配置见根目录 `pyproject.toml`），`ruff format` + `ruff check` 双管齐下，target 锁在 `py37` 以保住 3.6 风格的类型注解；
- 一些经验可以持久化到 [`MEMORY/`](./MEMORY/)（`MEMORY.md` 是索引，正文与索引同级）

## 依赖的 MCP 和外部的 Skills
### 依赖的 MCP
- 需要依赖 Gemini 文档的 MCP 服务：Gemini Docs MCP

### 依赖的 Skills
- 有的 skills 涉及调用 Gemini 相关的 API，需要安装 Gemini API 的 skills
```shell
$> npx skills add google-gemini/gemini-skills --skill gemini-api-dev
$> npx skills add google-gemini/gemini-skills --skill gemini-live-api-dev
$> npx skills add google-gemini/gemini-skills --skill gemini-interactions-api
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库定位

个人自定义 Claude Skills 合集。仓库本身既是 skills 的消费载体（每个子目录是一个独立 skill），也是一个用于"造 skill"的元仓库。设计原则与 skill 写作规范详见 `README.md` 与 `./yzr-skill-creator/SKILL.md`。

## 仓库规约（来源：README.md）

- 每个 skill 目录名（kebab-case）必须与 `SKILL.md` frontmatter 的 `name` 一致。
- 每个 skill 目录**必须**包含 `SKILL.md`；可选 `scripts/`、`references/`、`assets/`、`eval/` 子目录。
- 全部 Markdown 文件需经格式化 + lint，行宽 ≤ 120 字符（`.markdownlint.jsonc`，MD013 已放宽）。
- 跨会话需要持久化的"为什么"与边界规则写入根目录 `MEMORY/`（`MEMORY.md` 是索引，正文与索引同级）。
- frontmatter `quick_validate.py` 的 `ALLOWED_PROPERTIES = {name, description, license, allowed-tools, metadata, compatibility}`。`dependencies` 字段曾被 `paper-summary` 试用过，但与 allowlist 冲突；该 skill 已被整体删除。

## 常用命令

### 校验 skill

`yzr-skill-creator/scripts/` 下的脚本顶部都注入了 `sys.path` 引导，**两种调用形式都可用**：

```bash
# 形式 A：独立脚本（README 的原写法）
python3 yzr-skill-creator/scripts/quick_validate.py <skill-dir>

# 形式 B：作为模块（cwd 必须在 yzr-skill-creator/）
cd yzr-skill-creator && python3 -m scripts.quick_validate <skill-dir>

# 评估 / 描述优化 等其他脚本同理
python3 yzr-skill-creator/scripts/run_eval.py --eval-set ... --skill-path ...
python3 yzr-skill-creator/scripts/run_loop.py --eval-set ... --skill-path ... --model <id>
```

- 全部脚本已对齐到 **Python 3.6 语法**（`Optional` / `List` / `Dict` / `Tuple` 而非 PEP 604 / 585；`stdout=PIPE + universal_newlines=True` 而非 `capture_output + text`）。

### Markdown 格式 / lint

仓库内未配置 npm 工具链。本地 lint 走全局 `markdownlint-cli` 即可（未在仓库内固定）：

```bash
markdownlint '**/*.md'  # 遵守 .markdownlint.jsonc
```

### Python 格式 / lint

仓库根目录 `pyproject.toml` 配置了 ruff（formatter + linter 一体），覆盖 `yzr-skill-creator/scripts/*.py`。本机首次使用按以下方式安装（Debian/WSL 系统 Python 受 PEP 668 保护，必须显式开 `--break-system-packages` 才能装到用户目录）：

```bash
python3 -m pip install --user --break-system-packages ruff
```

常用命令（从仓库根运行）：

```bash
ruff format yzr-skill-creator           # 应用格式化
ruff format --check --diff yzr-skill-creator   # 只看 diff，不写文件
ruff check yzr-skill-creator            # 跑 lint
ruff check --fix yzr-skill-creator      # 跑 lint 并应用 safe 修复
```

关键约束：
- `target-version = "py37"`：ruff 的最低支持版本，等价保住 `Optional` / `List` / `Tuple` 注解（PEP 604/585 在 py37 下仍被 UP 规则禁用）。
- `UP021` / `UP022` 在 `ignore` 列表里——`subprocess.run` 的 `universal_newlines=True` 与 `stdout/stderr=PIPE` 写法是为了保 3.6 兼容，**不要**被自动改成 `text=True` / `capture_output=True`。
- 行宽 120，与 `.markdownlint.jsonc` MD013 对齐。

### Gemini 相关依赖（首次接入时按需执行）

`README.md` 列出了依赖的外部 skills，按需安装：

```bash
npx skills add google-gemini/gemini-skills --skill gemini-api-dev
npx skills add google-gemini/gemini-skills --skill gemini-live-api-dev
npx skills add google-gemini/gemini-skills --skill gemini-interactions-api
```

（`google-genai` Python SDK 之前随 `paper-summary` 引入；该 skill 已删除，目前仓库内没有直接调用 Gemini API 的代码。需要时按 `pip install -U google-genai` 自行安装，并准备 `GEMINI_API_KEY`。）

## 高层结构

入库文件（24 个）：

```
.
├── README.md              # 设计原则 / 依赖 / SKILLs 分类占位
├── MEMORY/                # 跨会话"为什么 + 边界"目录（MEMORY.md 是索引，正文同级）
├── .markdownlint.jsonc    # MD013 放宽到 120
├── design-doc-edit/       # 设计文档写作 skill（强制骨架 + 场景/方案分析）
├── outline-wiki-setup/    # Outline Wiki MCP 接入 + 重启验证（一次性配置）
├── outline-wiki-search/   # Outline Wiki 搜 / 读文档（核心 2 个能力）
├── outline-wiki-upload/   # Outline Wiki 写 / 编辑 + 图片附件 + @mention + 评论 + Collection + 移动 / 删除
└── yzr-skill-creator/     # 元 skill：创建 / 改进 / 评估 skill 本身
    ├── SKILL.md           # skill 创作循环 + 描述优化 + 实操评估章节
    ├── scripts/           # quick_validate / run_loop / generate_review / improve_description …
    ├── references/        # schemas.md（evals/history 等 JSON 结构）+ agents/{grader,comparator,analyzer}.md
    └── assets/eval_review.html  # 描述优化的查询评审页模板
```

`.gitignore` 覆盖、不入库的部分（详见根目录 `.gitignore`）：

- 外部工具产物：`package-lock.json`、`skills-lock.json`
- 用户级配置：`.claude/`（含 `settings.local.json`、commands 缓存）、`.agents/`（npx skills install 出来的 vendored 副本，软链到 `.claude/skills/`）
- Python 构建产物：`__pycache__/`、`*.pyc|pyo|pyd`、`*.egg-info/`
- 本地环境 / 密钥：`.env*`、`*.local`（保留 `!.env.example`）
- 编辑器 / 系统垃圾：`.DS_Store`、`.vscode/`、`.idea/`、swap 文件等
- 通用构建目录：`dist/`、`build/`

### Skill 写作骨架（来自 `yzr-skill-creator/SKILL.md`）

每个 `SKILL.md` 都遵循三级渐进加载：

1. **frontmatter**：`name` + `description`（≤ 1024 字符，触发判定的唯一信号）—— 始终在上下文。
2. **正文**：触发时加载，控制在 5000 词以内。
3. **捆绑资源**：`scripts/` 可执行、`references/` 按需阅读、`assets/` 模板/图标、`eval/` 评估集。

正文应包含的小节：`何时使用 / 不使用`、`输入 / 输出`、`执行原则 / 边界`、`工作流 / 步骤`、可选 `参考样例`。描述写得"主动"，把"何时使用"全部塞进 `description` 而不是正文里。

### yzr-skill-creator 内部脚本

| 脚本 | 作用 |
| --- | --- |
| `scripts/quick_validate.py` | frontmatter 合法性校验（可单独调用） |
| `scripts/run_eval.py` / `aggregate_benchmark.py` / `generate_report.py` | 跑评估用例、聚合结果、生成报告 |
| `scripts/run_loop.py` | 描述优化的后台循环（60% 训练 / 40% 保留评估） |
| `scripts/improve_description.py` | 单轮描述优化 |
| `scripts/generate_review.py` | 渲染 `assets/eval_review.html` 供用户人工评审触发评估集 |

`references/agents/{grader,comparator,analyzer}.md` 定义了三个子 agent 指令；`references/schemas.md` 给出 `evals.json` / `history.json` / `grading.json` 的字段约定。

### 跨 skill 协作约定

- `outline-wiki-*` 三个 skill（`outline-wiki-setup` / `outline-wiki-search` / `outline-wiki-upload`）共同维护 Outline Wiki MCP 接入与使用——`setup` 一次性写 `~/.claude.json` + 重启验证；`search` 只读 search / read；`upload` 写 / 编辑 + 图片附件 3 步 + 扩展能力（@mention / 评论 / Collection 管理 / 移动 / 删除）。三者均完全依赖 MCP 工具（不直连 REST，唯一例外是 `upload` 在大文档整篇重写时走 REST API 绕开 update_document 的换行吞字 bug）。破坏性操作（移动 / 删除 / 归档）由 `outline-wiki-upload` 承担，必须先在会话内显式确认；对他人文档用 `create_comment` 提议而非直接覆盖。
- `design-doc-edit` 输出**有强制章节骨架**（概述 → 场景分析 → 方案选择 → 核心设计 → 文件归属），章节可增删但顺序不可打乱；行宽同样受 `.markdownlint.jsonc` MD013 约束。
- `yzr-skill-creator` 内部的"运行与评估测试用例"章节要求 workspace 与 skill 同级（`<skill-name>-workspace/`），按 `iteration-N/eval-N/` 嵌套；with-skill 与 baseline 必须在同一轮并行启动，不要串行。

## 注意事项

- `.claude/settings.local.json` 已预批准一组 MCP / Bash 权限（Gemini Docs MCP、`pip install *`、`python3 *` 等），新增依赖工具时若需新权限需走 `update-config` skill。该文件本身已被 `.gitignore` 覆盖，仅本机生效。
- 新增 skill 时优先复用 `yzr-skill-creator/scripts/quick_validate.py` 做预检，再决定是否走评估 / 描述优化流程。
- `yzr-skill-creator` 内部的 `run_eval` / `improve_description` 会调用 `claude` CLI（`claude -p` 子进程），需要本机已安装并登录 Claude Code。

# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

> **关键**：本文件里凡 `@path/to/file` 形式的引用（如 `@MEMORY/MEMORY.md`），都用 Read 工具按需
> 读取——它们与你**当前任务**直接相关。不自动展开 `@import` 的 agent 尤须手动执行，否则漏上下文。

## 项目定位

个人自定义 AI skills 合集。仓库本身既是 skills 的消费载体（每个子目录是一个独立 skill），
也是一个用于"造 skill"的元仓库。设计原则与 skill 写作规范详见 `README.md` 与
`./yzr-skill-creator/SKILL.md`。

## 仓库规约（来源：README.md）

- 每个 skill 目录名（kebab-case）必须与 `SKILL.md` frontmatter 的 `name` 一致。
- 每个 skill 目录**必须**包含 `SKILL.md`；可选 `scripts/`、`tests/`、`references/`、`assets/`、
  `eval/` 子目录（`tests/` 为开发期测试专用，运行时 agent 不读——定位见
  yzr-skill-creator/references/skill-template-guide.md）。
- 全部 Markdown 文件需经格式化 + lint，行宽 ≤ 120 字符（`.markdownlint.jsonc`，MD013 已放宽）。
- 跨会话需要持久化的"为什么"与边界规则写入根目录 `MEMORY/`（`MEMORY.md` 是索引）。
  两种条目形式按事实颗粒度选：
  - **完整 memory**：含设计决策 / 工作流约束 / 跨文件关系 → 建 `MEMORY/<slug>.md`（**YAML
    frontmatter 起手：`name` + `description` + `metadata.type` 三件套**，正文 H1 + body），
    `MEMORY.md` 加 `[Title](slug.md)` 指针。**禁止**直接 `# 起手 / **Why:** / **How to apply:**`
    等无 frontmatter 写法（recall 阶段无法用 description 字段做 relevance 判定）。
    frontmatter 三件套字段要求：
    - `name`：kebab-case slug，必须等于文件名 `<slug>.md` 的 slug
    - `description`：一行 ≤ 200 字符的事实摘要，用于机器 relevance 召回
    - `metadata.type`：四选一 `user | feedback | project | reference`
  - **短 memory**：一句话能讲清的纯事实 / 单一偏好 / 无需 why+how 的提醒——直接以
    `- 一行事实` 索引行承载，不单独建 `<slug>.md`
  - 判别尺度交给事实本身：需要解释"为什么这么做"或"将来怎么用" → 完整；仅作 reminder → 短
  - **MEMORY 重复 → 直接删**（不要留 thin pointer）：MEMORY 条目内容已落
    SKILL 源（`<skill-name>/SKILL.md` / `scripts/` / `references/`）→ **直接删**
    MEMORY 条目 + `MEMORY.md` 索引指针。反模式：留 pointer = 死代码 + 漂移风险
    （详见 `skill-source-priority-over-memory-vendor.md` "反模式"段）。
    **MEMORY 只记 SKILL 源不涵盖的跨会话 meta**——SKILL 开发配置相关（python /
    skill workflow / wiki-spec 耦合等）才进 MEMORY；具体 SKILL 用法问题（具体
    skill 踩到的坑 / 经验）必须随 SKILL 文件夹分发，不进 MEMORY。
- frontmatter `quick_validate.py` 的 `ALLOWED_PROPERTIES = {name, description, license,
  allowed-tools, metadata, compatibility}`。`dependencies` 字段曾被 `paper-summary`
  试用过，但与 allowlist 冲突；该 skill 已被整体删除。

## 常用命令

### 校验 skill

`yzr-skill-creator/scripts/` 下的脚本顶部都注入了 `sys.path` 引导，**两种调用形式都可用**：

日常只要一条命令（全套检查，含 markdownlint / ruff）：

```bash
python3 yzr-skill-creator/scripts/verify.py --repo-root .      # 全部 skill
python3 yzr-skill-creator/scripts/verify.py <skill-dir> --tier meta
```

单独跑某一项时用下面的脚本：

```bash
# 形式 A：独立脚本（README 的原写法）
python3 yzr-skill-creator/scripts/quick_validate.py <skill-dir>

# 形式 B：作为模块（cwd 必须在 yzr-skill-creator/）
cd yzr-skill-creator && python3 -m scripts.quick_validate <skill-dir>

# 评估 / 描述优化 等其他脚本同理
python3 yzr-skill-creator/scripts/optimize_description.py --eval-set ... --skill-path ... --model <id>
```

### Markdown 格式 / lint

仓库内未配置 npm 工具链。本地 lint 走全局 `markdownlint-cli` 即可（未在仓库内固定）：

```bash
markdownlint '**/*.md'  # 遵守 .markdownlint.jsonc
```

**必须在仓库根跑**（或用 `-c .markdownlint.jsonc` 显式指定）——否则配置找不到，行宽退回默认值，
正常行被成批误报 MD013。判回归只看有无**新错误类别**，不计 lint 计数
绝对值。日常别手打这条：`yzr-skill-creator/scripts/verify.py` 已把 cwd 与 config 路径钉死
（坑的完整说明在该脚本 docstring）。

### Python 格式 / lint

仓库根目录 `pyproject.toml` 配置了 ruff（formatter + linter 一体），覆盖
`yzr-skill-creator/scripts/*.py`。本机首次使用按以下方式安装（Debian/WSL 系统 Python
受 PEP 668 保护，必须显式开 `--break-system-packages` 才能装到用户目录）：

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

- `target-version = "py37"`：仓库脚本的最低支持版本（Python 3.7）；PEP 604/585 在 py37 下
  被 UP 规则禁用，故注解走 `Optional` / `List` / `Tuple`。
- `UP021` / `UP022` 在 `ignore` 列表里——仓库脚本沿用 `subprocess.run` 的
  `universal_newlines=True` 与 `stdout/stderr=PIPE` 写法（既有风格），**不要**被自动改成
  `text=True` / `capture_output=True`。
- 行宽 120，与 `.markdownlint.jsonc` MD013 对齐。

### Gemini 相关依赖（首次接入时按需执行）

`README.md` 列出了依赖的外部 skills，按需安装：

```bash
npx skills add google-gemini/gemini-skills --skill gemini-api-dev
npx skills add google-gemini/gemini-skills --skill gemini-live-api-dev
npx skills add google-gemini/gemini-skills --skill gemini-interactions-api
```

（`google-genai` Python SDK 之前随 `paper-summary` 引入；该 skill 已删除，目前仓库内没有
直接调用 Gemini API 的代码。需要时按 `pip install -U google-genai` 自行安装，并准备
`GEMINI_API_KEY`。）

## 高层结构

入库文件（18 个）：

```text
.
├── README.md              # 设计原则 / 依赖 / SKILLs 分类占位
├── AGENTS.md              # 工具无关项目上下文（SSOT；agent 原生直读，部分 agent 经
│                          # 薄壳 CLAUDE.md 的 @AGENTS.md 引入）
├── CLAUDE.md              # 部分 agent 的薄壳：仅含 @AGENTS.md + Claude 专属逃生舱
├── MEMORY/                # 跨会话"为什么 + 边界"目录（MEMORY.md 是索引；完整条目正文
│                          # 同级，短条目直接索引行）
├── .markdownlint.jsonc    # MD013 放宽到 120
├── yzr-multi-agent-context/       # CLAUDE.md → AGENTS.md 单源 + CLAUDE.md 薄壳改造（元 skill）
├── yzr-coding-review/           # 交互式代码 review（合理性审视 + 重构场景 catalog；
│                                # 语言中立；默认对话式结论，可出分级报告 / 逐条过，不主动改文件）
├── yzr-writing-review/          # 文档内容 review（逻辑 / 结构 / 冗余 / AI 腔 / 风格语气 /
│                                # 跨文档 SSOT；默认对话式结论，可出分级报告 / 逐条过；
│                                # 确认后承接改写，规则库 references/）
├── yzr-sys-design-doc/          # 正式系统设计文档写作：full/lite 两档路由（需求层/方案层/
│                                # 落地层 + DFX），full 档配套独立实施任务书
│                                # （执行期活文档，进度/问题/设计变更循环）
└── yzr-skill-creator/           # 元 skill：创建 / 改进 / 评估 skill 本身
    ├── SKILL.md           # skill 创作循环 + 描述优化 + 实操评估章节
    ├── scripts/           # verify（全套入口）/ quick_validate / check_* / audit_prose / …
    ├── tests/             # smoke_test_*（打桩冒烟，开发期 / CI 专用，运行时不读）
    ├── references/        # schemas.md（evals.json / grading.json JSON 结构）+ agents/grader.md
    └── assets/skill-template.md   # 可拷贝的 SKILL.md 正文骨架
```

`.gitignore` 覆盖、不入库的部分（详见根目录 `.gitignore`）：

- 外部工具产物：`package-lock.json`、`skills-lock.json`
- 用户级配置：agent 特定配置目录（含 `settings.local.json`、commands 缓存等；路径因 agent
  而异，详见各自文档）与 `.agents/`（npx skills install 出来的 vendored 副本，软链到
  agent skills 目录）
- Python 构建产物：`__pycache__/`、`*.pyc|pyo|pyd`、`*.egg-info/`
- 本地环境 / 密钥：`.env*`、`*.local`（保留 `!.env.example`）
- 编辑器 / 系统垃圾：`.DS_Store`、`.vscode/`、`.idea/`、swap 文件等
- 通用构建目录：`dist/`、`build/`

### Skill 写作骨架（来自 `yzr-skill-creator/SKILL.md`）

每个 `SKILL.md` 都遵循三级渐进加载：

1. **frontmatter**：`name` + `description`（≤ `utils.py::DESCRIPTION_MAX_CHARS` 字符，触发判定的唯一信号）—— 始终在上下文。
2. **正文**：触发时加载，控制在 `utils.py::BODY_WORD_LIMIT` 词以内（数值只在该常量处给）。
3. **捆绑资源**：`scripts/` 可执行、`references/` 按需阅读、`assets/` 模板/图标、`eval/`
   评估集。

正文规范 H2 节名 / 顺序 / 各类型豁免的 SSOT 在
`yzr-skill-creator/scripts/utils.py::CANONICAL_BODY_SECTIONS`，可拷贝骨架在
`yzr-skill-creator/assets/skill-template.md`——此处与其它 prose 不重抄节名列表。
描述写得"主动"，把"何时使用"全部塞进 `description` 而不是正文里。

### yzr-skill-creator 内部脚本

| 脚本 | 作用 |
| --- | --- |
| `scripts/verify.py` | **一条命令跑全套**（下面各检查 + markdownlint + ruff；cwd/config 陷阱在脚本内钉死；`--repo-root` 自动枚举全部 skill；工具状态 OK/FAIL/SKIP/MISSING 结构化，`--strict-tools` 只把 MISSING 变 error；`--json`） |
| `scripts/quick_validate.py` | frontmatter 合法性 + 正文结构 + description 格式标记 + 手写目录（TOC）禁令 + 已废除的「何时不使用」节 + 正文长度（`--tier <default\|reference\|meta>`；除 frontmatter 外 WARN 不 fail；`--json`） |
| `scripts/check_skill_dependencies.py` | 跨 skill 双向依赖筛查（仓库级；列出互相提及的 skill 对 + 证据，方向人工判） |
| `scripts/check_anchor_health.py` | 引用存活检查——markdown 链接锚点 + 反引号路径（含逃逸出 skill 根的跨 skill 相对路径）+ 「节名」指针（单 skill 或 `--repo-root` 全扫；`--json` 机器可读） |
| `scripts/audit_prose.py` | 两条启发式扫描（BARE-METRIC 指标散落 / VERSION-HISTORY-INLINE 版本演进史内联）；INFO 级候选，判定归 agent |
| `scripts/optimize_description.py` | 描述优化（触发评估 + 改进循环）；输出 results.json + 终端摘要，无 HTML 报告；`--apply`（配 `--dry-run`）负责写回 frontmatter |
| `scripts/eval_report.py` | 一次 eval iteration 的 grading.json 契约校验（字段名 / summary 算术 / 断言漏评）+ with_skill vs baseline 对比表；也供 verify 校验 evals.json |
| `scripts/eval_init.py` | eval 迭代工作区初始化（目录树 + 逐迭代旧版快照 + 子 agent prompt 拼装）；与 eval_report 构成 writer/reader round-trip，冒烟钉死 |
| `tests/smoke_test_*.py` | 打桩冒烟（判定 / 计分逻辑的正反两向钉死），改 `scripts/` 后手跑，CI glob 全跑 |

`references/agents/grader.md` 定义了评分子 agent 指令；
`references/schemas.md` 给出 `evals.json` / `grading.json` 字段约定。

### 跨 skill 协作约定

- `yzr-skill-creator` 内部的"运行与评估测试用例"章节要求 workspace 与 skill 同级
  （`<skill-name>-workspace/`），按 `iteration-N/eval-N/` 嵌套；with-skill 与 baseline 必须
  在同一轮并行启动，不要串行。

## 跨会话记忆（索引）

@MEMORY/MEMORY.md

## 注意事项

- agent 配置文件已预批准一组 MCP / Bash 权限（Gemini Docs MCP、`pip install *`、
  `python3 *` 等），新增依赖工具时若需新权限需走 `update-config` skill。具体路径与权限
  清单见各自 agent 配置文件（路径因 agent 而异，本文件不展开）。
- 新增 skill 时优先复用 `yzr-skill-creator/scripts/verify.py` 做预检（它内含 quick_validate /
  引用存活 / 启发式扫描 / markdownlint / ruff），再决定是否走评估 / 描述优化流程。
- 本仓 CI（`.github/workflows/ci.yml`）= `verify.py --repo-root . --strict-tools` + 仓库级
  markdownlint + `tests/smoke_test_*.py` glob 循环；新增 skill 与新增冒烟都不必改 CI。
- `yzr-skill-creator` 内部的 `optimize_description` 会调用 agent CLI 子进程
  （具体 CLI 因 agent 而异，见各自 agent 的逃生舱）。

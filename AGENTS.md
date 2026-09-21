# AGENTS.md

> **关键**：本文件里凡 `@path/to/file` 形式的引用（如 `@MEMORY/MEMORY.md`），都用 Read 工具按需
> 读取——它们与你**当前任务**直接相关。不自动展开 `@import` 的 agent 尤须手动执行，否则漏上下文。

## 项目定位

个人自定义 AI skills 合集：每个 `yzr-*/` 子目录是一个独立 skill，经 npx 分发；本仓同时是"造 skill"
的元仓。六个 skill：

- `yzr-skill-creator`（元）：创建 / 改进 / 评估 / 校验 skill 本身
- `yzr-coding-review`：代码 review（合理性审视 + 重构场景，语言中立，默认不改文件）
- `yzr-writing-review`：文档 review（逻辑 / 结构 / 冗余 / AI 腔 / SSOT；确认后承接改写）
- `yzr-multi-agent-context`：`CLAUDE.md` → `AGENTS.md` 单源 + 薄壳改造
- `yzr-md-to-html`：本地 md 转自包含 HTML（深色主题 + 侧边栏 + 公式 / mermaid）
- `yzr-sys-design-doc`：系统设计文档写作（full / lite 两档 + 实施任务书）

## 仓库规约

- 每个 skill 必备 `SKILL.md`，frontmatter `name` = 目录名（kebab-case）；可选子目录
  `ref/` `tools/` `tests/` `assets/` `eval/`。新标准名 `ref/` + `tools/`；存量 skill 仍是
  `references/` + `scripts/`，工具双兼容（verify 的 ruff 扫 scripts / tools / tests 三者），
  不要为统一而迁移存量目录。
- 正文节名 / 顺序 / 可选性 SSOT：`yzr-skill-creator/tools/utils.py::CANONICAL_BODY_SECTIONS`；
  可拷贝骨架 `yzr-skill-creator/assets/skill-template.md`；数值常量（DESCRIPTION_MAX_CHARS /
  BODY_WORD_LIMIT）在 utils.py 顶部，别处不抄数值。
- 改 skill 一律改仓库源；vendor 副本（`~/.agents/skills/` 等）是 npx 派生物，会被覆盖，
  不读、不改、不对比。
- Python：唯一工具链配置在根 `pyproject.toml`，target py37（注解用 Optional / List / Tuple，
  禁 PEP 604/585）、行宽 120、规则族 E/W/F/I/B/UP。UP021/UP022 在 ignore 里——subprocess 的
  `universal_newlines=True` / `stdout=PIPE` 旧写法是刻意的，别"修正"。
- docstring 政策（`yzr-skill-creator/tools/`）：函数 / 类全挂一行中文 docstring，模块 docstring
  一行；行内注释只写代码表达不了的坑与契约，不复述代码。
- Markdown：行宽 ≤ 120（`.markdownlint.jsonc`，代码块 / 表格豁免）；跨文件 / 跨节引用一律
  markdown 链接（旧节名指针机制已退役）。frontmatter 解析唯一实现
  `yzr-skill-creator/tools/utils.py::frontmatter_span`，别再写解析器。
- `tests/` 仅供开发期 / CI，运行时 agent 不读；eval 工作区 `<skill>-workspace/` 与 skill 同级
  且已 gitignore。

<!-- ↓ 默认启用：repo-local 记忆管理（让多 agent 共用同一份 MEMORY/，而非各自私有 memory）。
     记忆跟 repo 走——本注释 + 以下规约 + 下方“跨会话记忆（索引）”段一律保留（R6）。 -->
- 跨会话需持久化的"为什么 / 边界规则"写入根目录 `MEMORY/`（`MEMORY.md` 是索引），**禁写** agent
  私有 memory（如 `~/.claude/...`）——私有路径不随仓迁移 / 不进 git / 多 agent 分裂。
  - 完整 memory（设计决策 / 工作流约束）→ `MEMORY/<slug>.md`，带 frontmatter 三件套：
    `name`(=文件 slug) + `description`(≤200 字符事实摘要) + `metadata.type`(user|feedback|project|reference)
  - 短 memory（一句话事实）→ 直接写 `MEMORY.md` 索引行，不单独建文件
  - MEMORY 只收跨会话 meta；具体 skill 的用法与踩坑随该 skill 源分发，不进 MEMORY

## 常用命令

首次备齐工具链：`python3 scripts/install-dev-deps.py`（幂等；装 pyyaml + ruff + markdownlint-cli）。

### 校验 skill

```bash
# 全仓总入口（= CI 第 1 步）：frontmatter / 结构 / 锚点存活 / 启发式 / markdownlint / ruff
python3 yzr-skill-creator/tools/verify.py --repo-root . --strict-tools

# 单 skill
python3 yzr-skill-creator/tools/verify.py <skill-dir>

# 冒烟（= CI 第 3 步；每个在各自 skill 目录下跑）
for t in */tests/smoke_test_*.py; do d=${t%/tests/*}; (cd "$d" && python3 "tests/$(basename "$t")") || exit 1; done
```

- 判据是 **0 ERROR / 0 gate failure**，不是"与上次输出一致"；WARN / INFO 不挂 CI。
- `--strict-tools` 下工具 MISSING 直接判失败；CI 装的是 unpinned 最新版（ruff / markdownlint-cli），
  本地旧版绿不算数。
- 新增 skill / 新增冒烟都不用改 CI（verify 自动枚举 + glob 循环）。

### Markdown lint

```bash
markdownlint 'README.md' 'AGENTS.md' 'CLAUDE.md' 'MEMORY/**/*.md'   # 仓库级文档（= CI 第 2 步）
markdownlint '**/*.md'                                              # 全仓
```

必须在仓库根跑（或 `-c .markdownlint.jsonc`）——否则配置找不到、行宽退回默认 80 成批误报；
verify 内部已钉死 cwd 与 config。中文行"超限部分无空格"会被 markdownlint 默认豁免，但别依赖
豁免，一律折到 120 内（工具版本漂移翻过车）。

### Python lint

```bash
ruff format <skill-dir>          # 应用格式化
ruff check <skill-dir>           # lint（--fix 应用 safe 修复）
```

verify 已自动跑 `ruff check` + `ruff format --check`，配置见根 `pyproject.toml`。

## 高层结构

```text
.
├── AGENTS.md / CLAUDE.md        # 项目上下文 SSOT + Claude 薄壳（@AGENTS.md + 逃生舱）
├── MEMORY/                      # 跨会话"为什么 + 边界"（MEMORY.md 索引，条目正文同级）
├── README.md                    # 设计原则 / 依赖 / skill 分类
├── pyproject.toml               # ruff 唯一配置（py37 + 120 列）
├── .markdownlint.jsonc          # MD013 放宽到 120；MD041 / MD060 关闭
├── scripts/install-dev-deps.py  # 开发依赖安装（pyyaml / ruff / markdownlint-cli）
├── .github/workflows/ci.yml     # CI = verify --strict-tools + 仓库级 markdownlint + 冒烟循环
└── yzr-*/                       # 六个 skill；yzr-skill-creator 内部：
    ├── SKILL.md                 #   入口表（4 个入口）
    ├── tools/                   #   verify / quick_validate / check_* / audit_prose / eval_* / optimize_description
    ├── tests/                   #   smoke_test_*（打桩冒烟）+ _fixtures.py（共享夹具）
    ├── ref/                     #   {create,improve,description,audit}-workflow.md + schemas.md + agents/grader.md
    └── assets/skill-template.md #   可拷贝的 SKILL.md 正文骨架
```

## 跨会话记忆（索引）

@MEMORY/MEMORY.md

## 注意事项

- verify 对 `yzr-skill-creator` 报的 `BODY-SECTION-MISSING` WARN 是已知债（节名变体），
  别为消 WARN 改节名。
- `yzr-skill-creator/tools/optimize_description.py` 按标题抽取 `ref/description-workflow.md` 的
  「## description 优化原则」正文——该标题不得改。它调 `opencode run` 子进程跑评估
  （judge / improve）：需本机 opencode 可用且已配置 provider；judge 走全 deny 工具权限的内联
  agent（`OPENCODE_CONFIG_CONTENT`），不加载工具。
- 创建 / 改进 / 描述优化 / 审计的执行细节在
  `yzr-skill-creator/ref/{create,improve,description,audit}-workflow.md`，`SKILL.md` 入口表负责指路。
- 冒烟风格：failures 列表收尾 exit 1，不用裸 assert（`python -O` 会吞）；每个冒烟头部注明 cwd
  与跑法。skill-creator 脚本两种入口都行（文件内 sys.path 引导）：
  `python3 yzr-skill-creator/tools/x.py` 或 `cd yzr-skill-creator && python3 -m tools.x`。

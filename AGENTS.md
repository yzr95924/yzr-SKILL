# AGENTS.md

> **关键**：本文件里凡 `@path/to/file` 形式的引用（如 `@MEMORY/MEMORY.md`），都用 Read 工具按需
> 读取——它们与你**当前任务**直接相关。不自动展开 `@import` 的 agent 尤须手动执行，否则漏上下文。

## 项目定位

个人自定义 AI skills 合集：每个 `yzr-*/` 子目录是一个独立 skill，经 npx 分发；本仓同时是"造 skill"
的元仓。skill 名单与简介见 [README.md](./README.md)，此处不另立副本。

## 仓库规约

- 正文节名 / 顺序 / 可选性标准：`yzr-skill-creator/assets/skill-template.md`（可拷贝骨架，agent 与检查器都只认它）。
  共享数值常量统一在 `yzr-skill-creator/tools/utils.py` 顶部定义，utils.py 已有的数值别处不重抄（文件局部常量允许定义在所在文件）。
- 改 skill 一律改仓库源；vendor 副本（`~/.agents/skills/` 等）是 npx 派生物，会被覆盖，
  不读、不改、不对比。
- Python：唯一工具链配置在根 `pyproject.toml`。UP021/UP022 在 ignore 里——subprocess 的
  `universal_newlines=True` / `stdout=PIPE` 旧写法是刻意的，别"修正"。
- 注释只写代码表达不了的坑与契约，不复述代码。
- Markdown：跨文件 / 跨节引用一律 markdown 链接。frontmatter 解析唯一实现
  `yzr-skill-creator/tools/utils.py::frontmatter_span`，别再写解析器——该唯一性约束
  skill-creator 工具链内部；独立分发的 skill 不能跨 skill import，自带轻量 frontmatter
  解析属豁免（如 `yzr-memory-management/tools/memory_lint.py`）
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
# 全仓总入口（= CI 第 1 步）
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
├── README.md                    # 门面入口：定位 / SKILLs 名单 / 快速开始 / 设计原则
├── pyproject.toml               # ruff 唯一配置（py37 + 120 列）
├── .markdownlint.jsonc          # MD013 放宽到 120；MD041 / MD060 关闭
├── scripts/install-dev-deps.py  # 开发依赖安装（pyyaml / ruff / markdownlint-cli）
├── .github/workflows/ci.yml     # CI = verify --strict-tools + 仓库级 markdownlint + 冒烟循环
└── yzr-*/                       # 各 skill 目录；yzr-skill-creator 内部：
    ├── SKILL.md                 #   入口表（4 个入口）
    ├── tools/                   #   verify / quick_validate / check_* / audit_prose / eval_* / optimize_description
    ├── tests/                   #   smoke_test_*（打桩冒烟）+ _fixtures.py（共享夹具）
    ├── ref/                     #   {create,improve,description,audit}-workflow.md + schemas.md + agents/grader.md
    └── assets/skill-template.md #   可拷贝的 SKILL.md 正文骨架
```

## 跨会话记忆（索引）

@MEMORY/MEMORY.md

## 注意事项

- `yzr-skill-creator/tools/optimize_description.py` 按标题抽取 `ref/description-workflow.md` 的
  "## description 优化原则"正文——该标题不得改。它调 `opencode run` 子进程跑评估
  （judge / improve）：需本机 opencode 可用且已配置 provider；judge 走全 deny 工具权限的
  markdown agent（专用 cwd 内 `.opencode/agent/`），不加载工具；`opencode run` 的 flag 与
  agent 注入机制按本机 CLI 能力探测降级（v2.0.16 无 `--pure` / `--dir` / JSON agent 键）。
- 创建 / 改进 / 描述优化 / 审计的执行细节在
  `yzr-skill-creator/ref/{create,improve,description,audit}-workflow.md`，`SKILL.md` 入口表负责指路。
- skill-creator 脚本两种入口都行（文件内 sys.path 引导）：
  `python3 yzr-skill-creator/tools/x.py` 或 `cd yzr-skill-creator && python3 -m tools.x`。

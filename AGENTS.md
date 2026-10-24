# AGENTS.md

## 项目定位

个人自定义 AI skills 合集：每个 `yzr-*/` 子目录是一个独立 skill，经 npx 分发；本仓同时是“造 skill”
的元仓。skill 名单与简介见 [README.md](./README.md)，此处不另立副本。

## 仓库规约

- 正文节名 / 顺序 / 可选性标准：`yzr-skill-management/assets/skill-template.md`（可拷贝骨架，agent 与检查器都只认它）。
- 改 skill 一律改仓库源；vendor 副本（`~/.agents/skills/` 等）是 npx 派生物，会被覆盖，
  不读、不改、不对比。
- Python：唯一工具链配置在根 `pyproject.toml`。UP021/UP022 在 ignore 里——subprocess 的
  `universal_newlines=True` / `stdout=PIPE` 旧写法是刻意的，别“修正”。
- 注释只写代码表达不了的坑与契约，不复述代码。
- Markdown：跨文件 / 跨节引用一律 markdown 链接。独立分发的 skill 不能跨 skill import，
  自带轻量 frontmatter 解析属豁免（如 `yzr-memory-management/tools/memory_lint.py`）
- `tests/` 仅供开发期 / CI，运行时 agent 不读；eval 工作区 `<skill>-workspace/` 与 skill 同级
  且已 gitignore。

## 常用命令

首次备齐工具链：`python3 scripts/install-dev-deps.py`（幂等；装 pyyaml + ruff + markdownlint-cli）。

### 校验 skill

```bash
# 全仓总入口
python3 yzr-skill-management/tools/skeleton.py check

# 单 skill
python3 yzr-skill-management/tools/skeleton.py check <skill-dir>

# 冒烟（tests/ 为存量位置，tools/tests/ 为新约定，两处都跑；各自 skill 目录下执行）
for t in */tests/smoke_test_*.py; do d=${t%/tests/*}; (cd "$d" && python3 "tests/$(basename "$t")") || exit 1; done
for t in */tools/tests/smoke_test_*.py; do d=${t%/tools/tests/*}; (cd "$d" && python3 "tools/tests/$(basename "$t")") || exit 1; done
```

- 判据是 **0 finding**，不是“与上次输出一致”。
- 存量债务：sys-design-doc 带旧标准形状（metadata 键、多余 H2），过不了新 check，修形或放宽检查器待定；
  ruff 暂无 CI 覆盖。

### Markdown lint

```bash
markdownlint 'README.md' 'AGENTS.md' 'CLAUDE.md' 'MEMORY/**/*.md'   # 仓库级文档（= CI 第 2 步）
markdownlint '**/*.md'                                              # 全仓
```

必须在仓库根跑（或 `-c .markdownlint.jsonc`）——否则配置找不到、行宽退回默认 80 成批误报。
中文行“超限部分无空格”会被 markdownlint 默认豁免，但别依赖豁免，一律折到 120 内
（工具版本漂移翻过车）。

### Python lint

```bash
ruff format <skill-dir>          # 应用格式化
ruff check <skill-dir>           # lint（--fix 应用 safe 修复）
```

配置见根 `pyproject.toml`。

## 高层结构

```text
.
├── AGENTS.md / CLAUDE.md        # 项目上下文 SSOT + Claude 薄壳（@AGENTS.md + 逃生舱）
├── MEMORY/                      # 跨会话"为什么 + 边界"（MEMORY.md 索引，条目正文同级）
├── README.md                    # 门面入口：定位 / SKILLs 名单 / 提示词模板 / 快速开始 / 设计原则
├── prompts/                     # 提示词模板：网页平台即贴即用（围栏代码块整段复制）
├── pyproject.toml               # ruff 唯一配置（py37 + 120 列）
├── .markdownlint.jsonc          # MD013 放宽到 120；MD041 / MD060 关闭
├── scripts/install-dev-deps.py  # 开发依赖安装（pyyaml / ruff / markdownlint-cli）
├── .github/workflows/ci.yml     # CI = 仓库级 markdownlint + 冒烟循环（骨架检查步随 verify.py 删除，待重建）
└── yzr-*/                       # 各 skill 目录；yzr-skill-management（元）内部：
    ├── SKILL.md                 #   执行原则（设计 / 写作两小节）+ 工作流（改进 / 审计 + 共享末步）
    ├── tools/                   #   skeleton.py（new 生成骨架 / check 比对漂移）+ tools/tests/ 冒烟
    ├── ref/                     #   create.md（创建工作流）+ qualitative-loop.md（定性测试循环协议）
    ├── assets/skill-template.md #   可拷贝的 SKILL.md 正文骨架
    └── eval/                    #   evals.json（行为用例）+ trigger_eval.json（触发正负例）+ fixtures/（用例固定输入）
```

## 跨会话记忆（索引）

@MEMORY/MEMORY.md

## 注意事项

- 定性测试的 judge 与行为性改进 subagent 一律由编排 agent 用 harness subagent 会话内发起，
  不起 `opencode run` 之类 CLI 子进程，也没有 A/B 数值管线（选型依据见 MEMORY/llm-worker-subagent.md）。
- 创建 / 改进 / 审计的流程写在 `yzr-skill-management/SKILL.md` 工作流节；定性测试循环协议在其
  `ref/qualitative-loop.md`。
- 骨架脚本两种入口都行：`python3 yzr-skill-management/tools/skeleton.py …` 或
  `cd yzr-skill-management && python3 -m tools.skeleton …`。

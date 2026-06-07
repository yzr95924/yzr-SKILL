# MEMORY.md

跨会话需要持久化的"为什么"与边界规则。新条目追加在末尾。

## skills 仓是独立 submodule，不要跨界读父目录

- **事实**：`/home/zryang/yzr_ws/skills/` 是独立代码仓
  （远程 `my_SKILL`），按 git submodule 形态被外部仓库消费；
  父目录 `yzr_ws/` 是另一个工程（`yzrws` 工具源码），与本仓无关。
- **Why**：`/init` 操作时本 session 曾默认向上读 `../CLAUDE.md` /
  `../MEMORY.md`，被用户当场制止（"不要越界访问上级目录，
  当前目录是作为一个独立的代码仓"）。Submodule 形态下，
  消费者只会把本目录作为顶层 clone，看不到父 `yzr_ws/`
  ——任何隐含依赖父目录的约定都会失配。
- **How to apply**：
  - 禁止 `Read` / `Bash ls` / `Grep` 以 `..` / `../` /
    `/home/zryang/yzr_ws/`（去掉 `skills/` 后缀）开头的路径
  - 信息源只取本目录：`README.md` / `SKILL_template.md` /
    `MEMORY.md` / `LICENSE` / `<skill-name>/SKILL.md` 等
  - 缺信息先问用户，不自动去父目录找
  - 本仓 lint 按自身 README 走（`markdownlint-cli2`），
    **没有** wrapper 脚本，不要和父 `yzr_ws/` 的 `lint.sh` 关联
  - 撰写文档时只用相对路径或本仓内绝对路径，不带 `../` 上级引用
- **验真信号**：`.git` 是 gitfile（指向 `../.git/modules/skills`），
  而不是目录——这是 git submodule 的标准形态

## 写新 SKILL.md 时不要参考 design-doc-edit

- **事实**：`design-doc-edit/SKILL.md` 是为"撰写项目技术设计文档"
  设计的 skill，核心是"场景分析 / 方案选择 / 视觉规范 / 硬性内容规则"
  等设计文档方法论；它**不是**通用 SKILL 的模板。
- **Why**：在 `outline-wiki-management` 任务中，本 session 曾错误地
  把 design-doc-edit 的 9-12 段结构（"核心模型 / 支持的操作 / 链接规范
  / 硬性内容规则" 等额外 h2）套到新 SKILL.md 上，被用户当场纠正：
  "不是 design-doc-edit 中的设计原则，而是 README.md 和 CLAUDE.md
  约束的设计原则"。两个 skill 的领域不同，结构也不同：
  - **design-doc-edit**：写技术设计文档——核心是场景分析 / 方案选择
    等方法论，h2 多、章节厚
  - **通用 SKILL.md**：写 agent 行为指令——按 `README.md` +
    本仓 `CLAUDE.md` 约束的 5 段骨架
    （`# 标题 / 何时使用 / 输入输出 / 执行原则 / 工作流 / 参考样例`），
    h2 固定 5 段
- **How to apply**：
  - 撰写新 `SKILL.md` 时**不读** `design-doc-edit/SKILL.md` 当模板
  - 模板源只用 `SKILL_template.md`（5 段骨架）
  - 写新 SKLL 不确定章节写法时，参考其他通用 SKILL 的样例
    （如 `outline-wiki-management/SKILL.md`），**不**参考 design-doc-edit
  - design-doc-edit 仅在用户**明确**要求"按设计文档流程做事"时由
    agent 自动调用——与"写新 SKILL.md"是两件事
- **验真信号**：`SKILL_template.md` 的 5 段骨架存在即说明它是本仓
  通用 SKILL 的事实标准；design-doc-edit 是个例外

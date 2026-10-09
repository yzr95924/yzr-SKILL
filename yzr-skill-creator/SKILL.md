---
name: yzr-skill-creator
description: |
  当用户处于 skill 生命周期时使用本 skill：从工作流 / 模板 / 流程 / 决策模式创建新 skill、
  改进现有 skill、独立优化某个 skill 的触发 description、或拿写作原则审计 skill 合规性。
  触发："我想 / 帮我 做一个 X 的 skill" / "从零做一个 skill 处理 X" / "把 XX 流程沉淀成
  skill" / "以后能用 / 新人也能用 / 按这个走"；改进 / 修改 / 评估 / 迭代 XX skill
  （修改含单点编辑：修 typo 等）、给 XX skill 增加 / 扩展功能；检查 / 审查 XX skill
  全文（内容体检、合规审查）；用户反馈触发不准或行为不对；想跑触发评估。
  不适用：单步问询；问 skill 机制原理；排查 / 调试 skill 的脚本 / 代码问题但不改 skill 内容；
  写普通代码 / 改普通文档 / 不涉及 skill 生命周期的事
metadata:
  author: Zuoru YANG
  modify time: 2026-10-10
  tier: meta
---
# yzr-skill-creator

## 入口

先归类，再动手，执行流程见[章节](#工作流)

1. **创建一个 skill**：从零做
2. **改进 skill**：先分**单点**（正文措辞 / typo / 指称 / 注释）与**行为性**（规则 / 流程 / 脚本行为 / 新增功能）
3. **`description` 优化**：凡改动触及 frontmatter 的 `description`，一律走本入口
4. **原则校验**：审计合规性（只报告）

分流：用户说"优化描述"而对象不明时，默认泛指（正文措辞与结构）走入口 2，点名 frontmatter 才走入口 3；
一次请求同时涉及正文与 `description` 时，先 2 后 3

## 输入与输出

- **输入**：目标 skill 目录 + 用户诉求；创建场景为待沉淀的工作流素材（访谈补齐其余）
- **输出**：各入口的交付见[章节](#工作流)

## 执行原则

写作规则与审计清单是同一份清单，逐条对照：

1. **归位**：路由节只装分类判据与指针；正文只装判断、路由、闸门、调用契约与"为什么"；何时用 /
   何时不用只写 frontmatter `description`，闸门 / 纪律句在执行点的重述不算违反。执行细节超一屏、
   被多处共读、或被脚本按节抽取，三者居其一才独立 `ref/` 文件，否则留在对应工作流节
2. **每行自证**：改动触及的每段问"删掉它，称职 agent 会做错吗"，不会则删或下放；新增纪律须有实录
   失败支撑（裸跑记录 / 用户反馈归纳成类后写入），并经用户点头；不凭精读断言对错——没把握先查溯源
   （自体声明的动机 / git 历史 / 测试记录），查无实证标注"未经验证"；自身演进史归 git，
   正文最多一句路标
3. **机械归脚本**：能机械判定"违反 / 通过"的归脚本，误报频繁的、实现比规则本身重的除外。机制靠
   代码自描述（命名 / 结构 / `--help`），md 只给全调用契约（何时调、怎么调）——"跑 X 命令"
   调用行与"以 `--help` 为准"算契约已给全
4. **单一来源**：一件事只在一个地方描述（权威源），其他地方最多是引用；相同概念全程同一个名称；
   `eval/` 断言里复述正文阈值不算散落（断言须自足可判定）
5. **依赖单向**：skill 间依赖必须单向（DAG），真实功能依赖显式声明；指称停在对方 skill 名，不指
   其内部路径 / 节名（会因对方重构无声断裂），确需指针只用纯文本"X 侧规范 N 节"式
6. **agent 中立**：内容默认泛指具体 agent（如 "AI coding agent"；点名缩窄触发面、降低寿命）；
   仅为该 agent 特有机制设计时可点名，正文须讲清为什么
7. **交付纪律**：门禁全绿只证形式，不证内容正确；任何入口的改动面都是整个 skill 文件夹，不只
   `SKILL.md`。一批改动（触及多节 / 多文件 / 同措辞多处）交付前主动提议对目标 skill 全文审计
   （入口 4），用户点头才执行；单点编辑豁免

## 工作流

### 创建一个 skill

先 Read `ref/create-workflow.md` 再动手（访谈、裸跑、起草、测试用例、定性测试），交付收敛后的完整 skill 目录

### 改进 skill

单点：直接改 → `python3 -m tools.verify <skill-dir>` 全绿（动过 `tools/` 加跑
`for t in tests/smoke_test_*.py; do python3 "$t" || exit 1; done`）→ 汇报分类与一句理由

行为性改动走定性测试循环。授权闸门：先问用户跑不跑测试 prompt（subagent 成本），不静默跑、
不静默省；目标 skill 没有 `eval/evals.json` 时，先按 `ref/create-workflow.md`"第 4 步：测试用例"
补 prompt（先给用户确认）再进循环。每轮：

1. 备 `<skill-name>-workspace/test-N/eval-<id>/outputs/`，从 `eval/evals.json` 取该用例 prompt 拼任务，
   加一句"产物只写该 outputs/ 目录，不读不加载任何其他 skill；你处于 headless 测试，没有用户可回答
   问题，流程期待用户确认处，把本应展示给用户的内容原样存入 outputs/ 并停在那里"；每用例 spawn 一个
   harness subagent（一条消息并行发起，长任务用后台模式），编排者把最终回复原样存为该用例
   `transcript.txt`（从 harness 会话记录提取，勿手抄）
2. 读各用例 `outputs/` 与 `transcript.txt`，对照 `expectations` 逐条定性判断，结论 + 证据 + 自己的
   判断一起给用户请反馈；本轮新出现的 agent 借口**原样**摘抄，改写时写进对应禁令
3. 按反馈改写 skill，发现明显弱断言（错误输出也会过的）同步修订 `evals.json`，跑 `test-N+1`；
   循环至用户满意或反馈为空。收敛后把 evals 扩到 5–10 条
   （更广意图类别 + 相邻负例）再跑一轮防过拟合

### `description` 优化

授权闸门：用户确认后才写回；无触发回归才写回。先 Read `ref/description-workflow.md` 再动手

### 原则校验

`python3 -m tools.verify <skill-dir>` 覆盖机械项。逐文件（含 `assets/` 模板与 `eval/`）全量精读，
对照执行原则、`ref/create-workflow.md`"标点基线"与 `ref/description-workflow.md`"description
优化原则"逐条给结论（文件 + 原文引用为证据），只报不修。精读后跨文件 grep 取证一轮：同一
`<数字><单位>` 指标散落多文件、跨 skill 互提对（互提 ≠ 互依，方向读正文判）、同概念名称漂移——
这三类单文件精读不可见。报告三小节：违反项（附修法建议）/ 待删候选 / 已转交层——md 散文质量转
yzr-writing-review、`tools/` 代码转 yzr-coding-review、`description` 触发质量转入口 3，
未处置不得收工；修复由用户点头转入口 2

---
name: yzr-skill-creator
description: |
  当用户处于 skill 生命周期时使用本 skill：从工作流 / 模板 / 流程 / 决策模式创建新 skill、
  通过 eval-and-iterate 改进现有 skill、独立优化某个 skill 的触发
  description、或拿写作原则审计 skill 合规性（只报告、不改写）。
  触发："我想 / 帮我 做一个 X 的 skill" / "从零做一个 skill 处理 X" / "把 XX 流程沉淀成
  skill" / "以后能用 / 新人也能用 / 按这个走"；改进 / 修改 / 评估 / 迭代 XX skill
  （修改含单点编辑：修 typo 等）、给 XX skill 增加 / 扩展功能；检查 / 审查 XX skill
  全文（内容体检、合规审查）；用户反馈触发
  不准或行为不对；想跑评估。
  不适用：单步问询；问 skill 机制原理；排查 / 调试 skill 的脚本 / 代码问题但不改 skill 内容；
  写普通代码 / 改普通文档 / 不涉及 skill 生命周期的事。
metadata:
  author: Zuoru YANG
  modify time: 2026-09-20
---
# yzr skill creator

这是一个用于创建、改进 skill、独立优化 skill 触发描述，并能校验 skill 写作原则符合度的 skill

## 入口

先归类到四种入口之一再介入。

1. **创建新 skill**：从零做一个，见[章节](#创建一个-skill)。
2. **改进现有 skill**：已有 skill 要改（改动面 = 整个 skill 文件夹，不只 SKILL.md）。先分
   **单点 / 行为性**：改的是说法（措辞 / typo / 指称 / 注释）还是规矩（规则 / 流程 /
   脚本行为 / 新增功能），流程见[章节](#改进-skill)。
3. **优化 skill 的 description**：只调触发准确率、不动正文，见[章节](#描述优化)。
4. **校验写作原则**：拿原则当 checklist 审计，见[章节](#原则校验)。

## 输入 / 输出

| 入口 | skill 交付 |
| --- | --- |
| 1. 创建 | 收敛后的完整 skill 目录（评估可按用户指示跳过，跳过则无 `eval/`） |
| 2. 改进 | 单点：改后文件 + verify 全绿 + 分类汇报；行为性：+ workspace 评估产物（见 [章节](ref/eval-pipeline.md#第-0-步初始化工作区)） |
| 3. 描述优化 | 用户确认后写回的新 `description`（附 before/after 触发分数） |
| 4. 原则校验 | 对话内 pass/fail 结论 + 证据 + 建议修法；不建文件、不动手改 |

## 执行原则 / 边界

无论走哪个入口，下面这些原则贯穿全程，不是单独某一步的规则，而是 agent 在用本 skill 时应保持的判断基线：

- **元 skill 的"元"特征**：本 skill 的产物是"让 agent 在某类任务上更靠谱"的载体，不是用户最终要的文件；写每段 prose 前先问"下游 agent 读到这里会怎么想"
- **过拟合红线**：用户给的反馈只覆盖少数 prompt；要让 skill 在一百万次调用里都成立，必须从反馈归纳"意图类别"而非把 case 逐条抄进 SKILL.md
- **必须跑评估**（行为性改动；单点编辑豁免，见入口 2）：写完不跑 eval = 在赌运气
  （哪怕 1 个 case 也能暴露"skill 让模型做了无效工作"）；改进时先留旧版快照做 baseline
  （`scripts.eval_init` 自动做），否则"是否更好"无法量化
- **交付门禁**：一批 prose 改动（触及 ≥2 个 H2 节，或同一措辞跨节改）交付前，主动提议
  对目标 skill 跑全文审计，散文层转 yzr-writing-review“指令文档”组（跨节冗余与
  frontmatter 双写是 diff 视野的盲区，必须全文比对），机制层跑 verify + 审计速查表；
  用户点头才执行，单节单点修改免除
- **用户说"优化描述"是泛指**：默认包括 frontmatter `description` + 标题 + 章节 +
  when-to-use 措辞 + 操作步骤，不默认专指 frontmatter；用户要细分会用精确措辞
  （"只改 frontmatter" / "只动 description 字段"）。维度分清：frontmatter 只决定
  "何时调"、正文决定"怎么用"。入口 3 只动前者，入口 1/2 才动正文
- **writer 与 grader 分离**：跑评估的子 agent 跟打分的子 agent 不要合并，否则 grader
  会偏向自己刚写的版本（grader 盲评约定见 `ref/agents/grader.md`）
- **指标单一来源**：脚本里有 `CONST = value` 的，prose 用 `` `CONST` `` 引用，禁止写字面量
  （原则见 `ref/skill-writing-principles.md`；本 skill 的常量定义在 `scripts/utils.py`
  与 `scripts/optimize_description.py` 顶部）
- **与用户沟通**：skill 使用者编程背景差异大，术语（eval / holdout / baseline 等）先给
  一句人话解释

## 工作流 / 步骤

创建 / 改进一个 skill 的主要流程如下（入口 3 / 4 的流程见本节尾部两个小节）：

1. 明确这个 skill 要做什么、大致如何实现
2. **RED 阶段**：不带 skill 跑典型 prompt 观察失败（细节与条数见
   “创建一个 skill · baseline 演练（RED 阶段）”，此处不重抄）
3. 起草 skill（改进场景 = 编辑现有版），**针对 RED 观察到的具体违规做最小封堵**，
   不预堵"可能存在的"漏洞
4. 设计几个测试 prompt 让 agent 跑一遍（细节见[章节](#测试用例)）
5. 协助用户定性 + 定量评估结果（细节见[章节](#运行与评估测试用例)）→ 按反馈改写 → 重复直到满意
6. **收敛后扩量再验证（防过拟合最后一道闸）**：测试集扩到 5–10 条（覆盖更广意图类别 +
   相邻负例）再跑一轮完整评估，小样本收敛 ≠ 大样本成立

用户说“不跑评估，直接头脑风暴”时照做。

### 创建一个 skill

#### 意图识别与访谈

先理解用户的意图。当前对话可能已包含用户希望捕获的工作流（如"把这段流程沉淀成 skill"）。
若是，先从对话历史抽取答案：用到了哪些工具、步骤顺序、用户做了哪些修正、观察到的
输入/输出格式。再主动补齐缺口，梳理清楚之前先不写测试 prompt，需要确认的：

1. 这个 skill 应该让 agent 能做什么？
2. 应该在什么时机触发？（什么样的用户表述/上下文）
3. 期望的输出格式是什么？
4. 是否需要设置测试用例来验证 skill 是否可用？（文件转换、数据
   抽取、代码生成、固定工作流步骤等可客观验证输出的 skill，测试用例有益）
5. 边界情况、示例文件、成功标准、依赖项等
6. 流程里哪些步骤是**机械操作**（零判断、可枚举）？逐条标“判断 / 机械”，机械的默认进
   `scripts/` 规划，留 md 要给理由（闸门与豁免口径见
   [机械操作脚本化](ref/skill-writing-principles.md#归属与下放)）

调研：检查可用的 MCP，对调研有帮助（搜索文档、查找类似 skill、查阅最佳实践）且支持
子 agent 时并行调研，否则直接内联进行。

#### baseline 演练（RED 阶段）

> 原则见 [Iron Law](ref/skill-writing-principles.md#方法论写前--形式)。

不写 skill，先用旧版 skill（改进场景）或完全不带 skill（创建场景）跑 2–3 个典型 prompt：

- **创建场景**：完全不带 skill 跑 prompt，让 agent 用基础能力自由发挥，记录它**怎么违反**（哪些规则被跳 / 哪些步骤被漏 / 用了什么借口逐字摘抄）。
- **改进场景**：用当前版本的 skill 跑 prompt，记录**还错在哪**（旧 skill 没堵住的口子 / agent 找出的新借口）。

这些 transcript 作为起草 skill 的**输入**。skill 不是凭空设计，是**针对观察到的违规做最小封堵**。
后续 Rationalization Table + Red Flags 的素材都来自这里。**纯参考资料型 skill 跳过**。

#### 起草 SKILL.md

基于用户访谈的结果，按 `assets/skill-template.md` 的 frontmatter 占位符填充。
`description` 三组件格式与写法原则的 SSOT 在
[章节](ref/skill-writing-principles.md#description-优化原则)，不在此重抄。

后面为 skill 的正文：**骨架从 `assets/skill-template.md` 拷贝**，逐节填充（规范节名 / 顺序 /
各类型豁免的 SSOT 在 `scripts/utils.py::CANONICAL_BODY_SECTIONS`，变体规则见
[章节](ref/skill-template-guide.md#变体各类型的骨架适配)）。先填全骨架再删节，不要"想到哪写到哪"，
SKILL.md 格式统一靠的就是这份骨架。

起草正文前先落 `scripts/` 清单：访谈第 6 问标出的机械操作逐条进 `scripts/`（留 md 的记录
理由），正文只写判断引导与"跑 X 命令"调用行。

起草完成后先跑预检再进入测试用例：`python -m scripts.verify <skill-dir> --tier <type>`。

写作风格与语言原则见
[章节](ref/skill-writing-principles.md#正文写作原则)，不在此重抄 agent 通识。

#### 测试用例

写完 skill 草稿后，设计几个测试 prompt（条数与 [章节](#baseline-演练red-阶段) 同量级，
用真实用户会说的话），先跟用户确认："这是我准备跑的几个测试用例，你看这样 OK 吗？
要不要再补几个？"再跑起来

测试用例存到 `eval/evals.json`（结构见 `ref/schemas.md`）。先不写断言，只写
prompt，等下一步再起草断言。

### 运行与评估测试用例

本节是连续流程，不要中途停下来。

- 工作区目录树 / 旧版快照 / 子 agent prompt：`python3 -m scripts.eval_init
  --workspace <skill-name>-workspace --iteration <N> --skill-path <skill-dir>
  --baseline without_skill|old_skill` 一次备好（创建场景 `without_skill`，改进场景
  `old_skill`）
- 同轮并行启动 / 起草断言 / 评分 / 对话展示的判断性纪律见
  `ref/eval-pipeline.md`

### 改进 skill

**单点改动**直接做：对照 `ref/skill-writing-principles.md` 自查 +
`python -m scripts.verify <skill-dir>` 全绿（动 `scripts/` 加跑
`tests/smoke_test_*.py`），汇报声明分类 + 一句理由。**行为性改动**走
[迭代循环](#迭代循环)。

跑过测试用例、用户评审过结果后，根据反馈迭代，迭代原则（从反馈归纳泛化而非逐 case 抄写 /
找重复工作进 `scripts/`）见 [Iron Law](ref/skill-writing-principles.md#方法论写前--形式)+
[章节](ref/skill-writing-principles.md#归属与下放)，逐段精简按下述 Concision review 执行。

#### 迭代循环

**先问用户是否跑 eval 循环：不点头不跑、不静默降级。**完成改进后：(1) 先跑 `scripts.eval_init` 备好 `iteration-<N+1>/`，改进场景必须
**先于应用改动**跑（快照的是跑时的当前版 = 上一轮迭代结果，先改后跑会把新版快照成
baseline，对比失去意义）→ (2) 应用改动 → (3) 同轮并行启动两组子 agent（prompt 用
eval_init 打印的）→ (4) 在对话里展示本轮对比（含上一轮对比）、请用户反馈 →
(5) 按反馈继续循环。

#### 堵 loophole（REFACTOR 阶段）

> 原则见 [Iron Law](ref/skill-writing-principles.md#方法论写前--形式)+“反合理化”。

每次迭代结束 + 读 transcript 后：(1) 识别新合理化（agent 又用什么借口绕禁令）；
(2) 加进 Rationalization Table（**只**补 agent 实际说过的，预写"可能存在"借口是反模式）；
(3) 对应红旗征兆若有缺则补 Red Flags；(4) agent 是否用看似不同但效果一致的手法绕禁令
→ 在"违反字面 = 违反精神"里加新案例；(5) 重测同批 prompt，新借口应不再出现；
仍出现 = 回 GREEN 重写。

#### Concision review（每轮迭代必做）

下轮改动前对每段问**删掉它，称职 agent 会做错吗**，不会 → 删或下放，处理顺序按“修法
优先级”（[章节](ref/skill-writing-principles.md#归属与下放)）；细则判据与典型噪音场景卡见
yzr-writing-review“指令文档”组。

停止条件：用户满意 / 反馈全空 / 看不到有意义的进展。

### 描述优化

> 优化原则见 [章节](ref/skill-writing-principles.md#description-优化原则)
> （`optimize_description.py` 运行时也读这一节）。

直接优化某个已有 skill 的 description，提升触发准确率。

#### 第 1 步：生成触发评估查询

生成评估查询（数量 / should-trigger 配比 / 写作指南见 `ref/trigger-eval-guide.md`），
存为 JSON。

#### 第 2 步：与用户过一遍

把评估集在对话里呈现给用户审阅（should-trigger / should-not-trigger 分组列出，
请用户确认或增删改），确认后存为 JSON。

#### 第 3 步：运行优化循环

告诉用户：这一步会花一些时间，我会在后台跑优化循环，并定期检查进度。
把评估集存到 workspace，然后后台运行（用 `setsid` + 重定向 + `< /dev/null` 脱离进程组，
否则 agent shell 工具超时会连坐杀掉跑到一半的循环）:

```bash
setsid python3 -m scripts.optimize_description \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --max-iterations 5 --verbose \
  > /tmp/desc-eval-results.json 2> /tmp/desc-eval.log < /dev/null &
```

跑的过程中定期 tail 输出，告知用户当前在第几轮、分数长什么样。

#### 第 4 步：应用结果

向用户展示 before/after 并汇报分数；**用户确认后**才写回（触发措辞属行为性改动，不先斩后奏）。
写回是零判断的字节操作（frontmatter 块标量的缩进 / 折行手改容易破 YAML），交给脚本：

```bash
python3 -m scripts.optimize_description --skill-path <path-to-skill> \
  --apply /tmp/desc-eval-results.json --dry-run   # 先看 diff，确认后去掉 --dry-run 落盘
```

### 原则校验

拿写作原则当 checklist，审计某个已有 skill 的**机制合规**，违反哪些，产出 pass/fail 报告。
**只审计、不改写**；散文质量不在本入口审，转交 yzr-writing-review“指令文档”组、
`scripts/*.py` 转交 yzr-coding-review（分工口径见 principles 末尾“审查分工”）。
要修让用户点头再动或转入口 2。

#### 怎么校验

1. **机械项一条命令跑完**：`python -m scripts.verify <skill-dir> --tier <default\|reference\|meta>`
   （覆盖清单、单项排查用哪个脚本见 `scripts/verify.py` docstring；`--json` 机器可读）。
2. 把 `ref/skill-writing-principles.md` 当 checklist（三段：
   [description 优化原则](ref/skill-writing-principles.md#description-优化原则)、
   [正文写作原则](ref/skill-writing-principles.md#正文写作原则)、末尾
   [审计速查](ref/skill-writing-principles.md#审计速查)表），读目标 skill 的 `SKILL.md`
   （必要时连带 `ref/`（存量为 `references/`）/ `scripts/`）逐条核对 → 通过 / 违反（附证据：文件:行 + 具体内容）。
   是否违规照速查表每行
   判定口径由 agent 判；表里的纯手工行（Iron Law 证据 / 反合理化三件套 / agent 中立 /
   机械操作脚本化的语义部分）逐条跑 grep 执行。
3. 产出报告（**只审计、不改写**）：每条 pass / fail + 建议修法；报告只活在对话里，
   不建归档文件（口径见 [章节](ref/skill-writing-principles.md#审查深度标准入口-4-默认口径)的报告条）。

#### 审查深度标准（入口 4 默认口径）

入口 4 默认按深度标准执行（全量精读每个文件，不只跑速查表机械检查）；散文层转交与人工行
判据细则见 [章节](ref/skill-writing-principles.md#审查深度标准入口-4-默认口径)。

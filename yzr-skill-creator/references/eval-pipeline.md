# 评估测试用例的执行细节

> 本文件承载 yzr-skill-creator「运行与评估测试用例」章节的机械细节——workspace 布局、
> 子 agent prompt 模板、JSON 约定。SKILL.md 主文件只列原则性指针。

## 工作区布局

结果放在 `<skill-name>-workspace/`，与 skill 目录同级（**不要**放在 skill 目录内）。
workspace 内按迭代（`iteration-1/`、`iteration-2/` 等）组织，每个迭代内每个测试用例
单独成目录（`eval-0/`、`eval-1/` 等）。目录边做边建，不要一次建完。

子运行目录按 baseline 类型分流（创建 `without_skill/outputs/` / 改进 `old_skill/outputs/`，
细节见「第 1 步」Baseline 配置）；`grading.json` 落在 `outputs/` 同级（grader 产物，见「第 3 步」）。

## 第 1 步：在同一轮并行启动 with-skill 与 baseline

对每个测试用例，在**同一轮**启动两个子 agent——一个带 skill、一个不带。
**重要**：不要先启动 with-skill、再串行启动 baseline；并发启动让它们大致同时完成。

**没有子 agent 的环境（降级路径）**：改为**串行**执行——对每个测试用例，自己读该
skill 的 SKILL.md 并按其指令完成任务（**跳过 baseline**：你写的 skill 你自己跑，
独立性的损失由人工评审环节补偿），评估结果直接在对话里展示。

**With-skill prompt 模板：**

```text
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files if any, or "none">
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- Outputs to save: <what the user cares about — e.g., "the .docx file", "the final CSV">
```

**Baseline 配置**：

- **创建新 skill**：完全不用 skill，同样的 prompt，不传 skill path，输出存到
  `without_skill/outputs/`
- **改进现有 skill**：用旧版——编辑前先快照 skill（`cp -r <skill-path> <workspace>/skill-snapshot/`），
  然后让 baseline 子 agent 指向那份快照，输出存到 `old_skill/outputs/`

## 第 2 步：在运行进行中起草断言

不要只是等运行结束——边跑边起草定量断言。如果 `eval/evals.json` 已有断言，
审视一遍并向用户解释它们检查什么。

好的断言应当：**客观可验证**、**名字描述性**，让瞥一眼结果的人立刻明白每个断言在
检查什么。偏主观的 skill（写作风格、设计质量）更适合定性评估，不要给需要人为判断的
事强行套断言。

断言定稿后，更新 `eval/evals.json`。

## 第 3 步：评分 + 对话展示

1. **为每次运行打分**：启动 grader 子 agent（或内联打分），它读
   `references/agents/grader.md`，逐条核对断言与输出。评分存到
   `<run>/grading.json`（字段约定见 `references/schemas.md`「grading.json」——
   `expectations` 数组用字段 `text` / `passed` / `evidence`）。
   可编程检查的断言写脚本跑，不要肉眼判断——脚本更快、可跨迭代复用。
2. **汇总展示**：读全部 `grading.json` + 关键输出，在对话里给用户对比——
   每个用例的 with_skill vs baseline 通过情况 + 值得看的输出差异，请用户反馈。
3. **迭代循环**：按用户反馈（以及对比暴露出的明显缺陷）改写 skill → 跑新
   `iteration-<N+1>/`（**含** baseline，baseline 取值：创建场景始终
   `without_skill`；改进场景：用户最初版本 or 上一轮迭代，由你判）。

## 何时去读本文件

执行 入口 1 / 2（创建 / 改进 skill）需要落地测试用例时 `Read`。

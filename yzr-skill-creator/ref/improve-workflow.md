# 改进 skill 的完整流程

> 本文件承载[章节](../SKILL.md#改进-skill)的执行细节：单点与行为性两条路线；行为性路线的评估循环机制也供创建流程复用（见[章节](create-workflow.md#第-5-步评估循环与扩集)）

## 单点

直接改；改完对照[章节](../SKILL.md#执行原则)自查，再 `python3 -m tools.verify <skill-dir>` 全绿
（动过 `tools/` 加跑 `for t in tests/smoke_test_*.py; do python3 "$t" || exit 1; done`）；最后汇报分类与一句理由

## 评估循环

行为性改动走本循环；改进场景 `--baseline old_skill`，创建场景 `--baseline without_skill`。每轮：

### 第 0 步：初始化工作区并应用改动

```bash
python3 -m tools.eval_init --workspace <skill-name>-workspace --iteration <N> \
  --skill-path <skill-dir> --baseline without_skill|old_skill
```

备好整轮迭代：`old_skill` 场景的**逐迭代**旧版快照（快照 = 跑 init 时的当前版，即上一轮迭代
结果）；先改后跑会把新版快照成 baseline、对比失去意义；init 成功后把本轮改动落到 `<skill-dir>`，再进第 1 步

### 第 1 步：独立子 agent 运行

`python3 -m tools.eval_prep --iteration <ws>/iteration-<N> --skill-path <skill-dir>`：每用例的 with_skill 与
对照侧（`without_skill` / `old_skill`）各建好沙箱与 prompt.txt，stdout 打印 PENDING 清单。前置同 `description`
优化（harness subagent 能力，[章节](description-workflow.md#命令流程)）。按清单**一条消息并行发起该用例的两侧**
subagent（长任务用后台模式），prompt 逐字交付该侧 prompt.txt 内容，
编排者把每侧最终回复原样存为该侧 `transcript.txt`（从 harness 会话记录提取，勿手抄——漂移有实录）。两侧并发让任务大致同时完成，串行会放大其间的时空漂移、
污染对比。会嵌套再跑循环的用例（如 `description` 优化的评估循环）是墙钟大头，单独 `--eval` 挑出先跑

**harness 无 subagent 能力（降级路径）**：改为**串行**执行：对每个测试用例，自己读该 skill 的 `SKILL.md` 并按其指令完成任务。
**跳过 baseline**：你写的 skill 你自己跑，独立性的损失由人工评审环节补偿。评估结果直接在对话里展示；第 3 步随之不跑 `eval_report` 双侧对比，逐条判断言只出 with_skill 单侧分

### 第 2 步：运行进行中起草断言

如果 `eval/evals.json` 已有断言，审视一遍并向用户解释它们检查什么

好的断言应当：**客观可验证**、**表述描述性**（瞥一眼即知在查什么）。偏主观的 skill（写作风格、设计质量）更适合定性评估，不要给需要人为判断的事强行套断言

断言定稿后，更新 `eval/evals.json`

### 第 3 步：评分、展示、借口记录

1. **为每次运行打分**：启动 grader 子 agent（或内联打分），它读 `ref/agents/grader.md`，逐条核对断言与输出。评分存到
   `<run>/grading.json`（字段约定见[章节](schemas.md#gradingjson)）。可编程检查的断言写脚本跑，不要肉眼判断，
   脚本更快、可跨迭代复用
2. **汇总 + 校验**：`python3 -m tools.eval_report <workspace>/iteration-<N> --evals <skill>/eval/evals.json` 出每个用例的
   `with_skill` vs `baseline` 对比（校验范围见[章节](schemas.md#gradingjson)）。**输出文件的实际差异与"这版好不好"的
   结论仍由 agent 读文件判**，把数字 + 差异 + 自己的判断一起给用户，请反馈
3. **借口记录**：本轮新出现的 agent 借口**原样**摘抄（只记实际说过的，不预写假想借口），改写时写进对应禁令

按用户反馈（以及对比暴露出的明显缺陷）改写 skill，再跑新 `iteration-<N+1>/`（`--baseline old_skill`）。循环至用户满意或反馈为空

# 改进 skill 的完整流程

> 本文件承载[入口 2](../SKILL.md#改进-skill)的执行细节：单点与行为性两条路线；行为性路线的评估循环机制也供入口 1 创建流程复用（见[章节](create-workflow.md#第-5-步评估循环与扩集)）

## 单点（正文措辞 / typo / 指称 / 注释）

直接改 → 改完对照[章节](../SKILL.md#执行原则)自查 → `python -m tools.verify <skill-dir>` 全绿
（动过 `tools/` 加跑 `python3 tests/smoke_test_*.py`）→ 汇报分类与一句理由

## 评估循环

行为性改动（规则 / 流程 / 脚本行为 / 新增功能）走本循环；改进场景 `--baseline old_skill`，创建场景 `--baseline without_skill`。每轮：

### 第 0 步：初始化工作区（必须先于应用改动）

```bash
python -m tools.eval_init --workspace <skill-name>-workspace --iteration <N> \
  --skill-path <skill-dir> --baseline without_skill|old_skill
```

一条命令备好整轮迭代：`iteration-<N>/eval-<id>/{with_skill,<baseline>}/outputs/` 目录树、`old_skill` 场景的**逐迭代**
旧版快照（快照 = 跑 init 时的当前版，即上一轮迭代结果，**必须先于应用本轮改动跑**，先改后跑会把新版快照成
baseline，对比失去意义）

### 第 1 步：应用改动

### 第 2 步：独立子 agent 运行

`python -m tools.eval_run --iteration <ws>/iteration-<N> --skill-path <skill-dir>`：每用例的 with_skill 与
对照侧（`without_skill` / `old_skill`）各起一个独立 `opencode run` 子 agent，开关以 `--help` 为准。两侧并发让
任务大致同时完成，串行会放大其间的时空漂移、污染对比。前置同入口 3。
会嵌套再跑循环的用例（如入口 3 的评估循环）是墙钟大头，单独 `--eval` 跑并配大 `--timeout`

**没有子 agent 的环境（降级路径）**：改为**串行**执行：对每个测试用例，自己读该 skill 的 `SKILL.md` 并按其指令完成任务（**跳过 baseline**：
你写的 skill 你自己跑，独立性的损失由人工评审环节补偿），评估结果直接在对话里展示

### 第 3 步：运行进行中起草断言

不要只是等运行结束，边跑边起草定量断言。如果 `eval/evals.json` 已有断言，审视一遍并向用户解释它们检查什么

好的断言应当：**客观可验证**、**名字描述性**（瞥一眼即知在查什么）。偏主观的 skill（写作风格、设计质量）更适合定性评估，不要给需要人为判断的事强行套断言

断言定稿后，更新 `eval/evals.json`

### 第 4 步：评分、展示、借口记录

1. **为每次运行打分**：启动 grader 子 agent（或内联打分），它读 `ref/agents/grader.md`，逐条核对断言与输出。评分存到
   `<run>/grading.json`（字段约定见[章节](schemas.md#gradingjson)）。可编程检查的断言写脚本跑，不要肉眼判断，
   脚本更快、可跨迭代复用
2. **汇总 + 校验**：`python -m tools.eval_report <workspace>/iteration-<N> --evals <skill>/eval/evals.json` 出每个用例的
   `with_skill` vs `baseline` 对比（校验范围见[章节](schemas.md#gradingjson)）。**输出文件的实际差异与"这版好不好"的
   结论仍由 agent 读文件判**，把数字 + 差异 + 自己的判断一起给用户，请反馈
3. **借口记录**：本轮新出现的 agent 借口**原样**摘抄（只记实际说过的，不预写假想借口），改写时写进对应禁令

按用户反馈（以及对比暴露出的明显缺陷）改写 skill → 跑新 `iteration-<N+1>/`（`--baseline old_skill`）。循环至用户满意或反馈为空

# 评估测试用例的执行细节

> 本文件承载本入口（[章节](../SKILL.md#运行与评估测试用例)）的**判断性纪律**：并行启动、
> 断言起草、评分与对话展示。机械细节（目录树 / 旧版快照 / 子 agent prompt 拼装）固化在
> `scripts/eval_init.py`，SKILL.md 主文件只列原则性指针。

## 第 0 步：初始化工作区

```bash
python3 -m scripts.eval_init --workspace <skill-name>-workspace --iteration <N> \
  --skill-path <skill-dir> --baseline without_skill|old_skill
```

一条命令备好整轮迭代：`iteration-<N>/eval-<id>/{with_skill,<baseline>}/outputs/` 目录树
（即 `scripts/eval_report.py` 读回的布局契约，round-trip 由
`tests/smoke_test_eval_init.py` 钉死）、`old_skill` 场景的**逐迭代**旧版快照
（快照 = 跑 init 时的当前版，即上一轮迭代结果，**必须先于应用本轮改动跑**，先改后跑
会把新版快照成 baseline，对比失去意义）、以及逐用例填好路径的
子 agent prompt（模板 SSOT 在脚本）。已存在的 iteration 目录拒绝覆盖，重跑换新编号。

## 第 1 步：同轮并行启动两个子 agent

对 eval_init 打印的每段 prompt，在**同一轮**启动两个子 agent：一个带 skill、
一个不带。**重要**：不要先启动 with-skill、再串行启动 baseline；并发启动让它们
大致同时完成。

**没有子 agent 的环境（降级路径）**：改为**串行**执行：对每个测试用例，自己读该
skill 的 SKILL.md 并按其指令完成任务（**跳过 baseline**：你写的 skill 你自己跑，
独立性的损失由人工评审环节补偿），评估结果直接在对话里展示。

## 第 2 步：在运行进行中起草断言

不要只是等运行结束，边跑边起草定量断言。如果 `eval/evals.json` 已有断言，
审视一遍并向用户解释它们检查什么。

好的断言应当：**客观可验证**、**名字描述性**，让瞥一眼结果的人立刻明白每个断言在
检查什么。偏主观的 skill（写作风格、设计质量）更适合定性评估，不要给需要人为判断的
事强行套断言。

断言定稿后，更新 `eval/evals.json`。

## 第 3 步：评分 + 对话展示

1. **为每次运行打分**：启动 grader 子 agent（或内联打分），它读
   `ref/agents/grader.md`，逐条核对断言与输出。评分存到
   `<run>/grading.json`（字段约定见 [章节](schemas.md#gradingjson)）。
   可编程检查的断言写脚本跑，不要肉眼判断，脚本更快、可跨迭代复用。
2. **汇总 + 校验**：`python -m scripts.eval_report <workspace>/iteration-<N> --evals <skill>/eval/evals.json`
   出每个用例的 with_skill vs baseline 对比（校验范围与输出格式见
   `scripts/eval_report.py` docstring）。**输出文件的实际差异与"这版好不好"的结论仍由
   agent 读文件判**，把数字 + 差异 + 自己的判断一起给用户，请反馈。
3. **迭代循环**：按用户反馈（以及对比暴露出的明显缺陷）改写 skill → 跑新
   `iteration-<N+1>/`（baseline 取值规则见 [章节](../SKILL.md#迭代循环)）。

## 何时去读本文件

执行 入口 1 / 2（创建 / 改进 skill）需要落地测试用例时 `Read`。

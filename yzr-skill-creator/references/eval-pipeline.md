# 评估测试用例的执行细节

> 本文件承载 yzr-skill-creator「运行与评估测试用例」章节的机械细节——workspace 布局、
> 子 agent prompt 模板、JSON schema、命令清单。SKILL.md 主文件只列原则性指针，
> 避免把"目录约定 + 命令清单 + json 模板"塞进 SKILL.md 抬 token。

## 工作区布局

结果放在 `<skill-name>-workspace/`，与 skill 目录同级（**不要**放在 skill 目录内）。
workspace 内按迭代（`iteration-1/`、`iteration-2/` 等）组织，每个迭代内每个测试用例
单独成目录（`eval-0/`、`eval-1/` 等）。目录边做边建，不要一次建完。

子运行目录按 baseline 类型分流：

- **创建新 skill**：`without_skill/outputs/`——完全不带 skill 的 baseline
- **改进现有 skill**：`old_skill/outputs/`——用快照（`cp -r <skill-path> <workspace>/skill-snapshot/`）
  后的旧版

> **不要**混用 `/skill-test` 或其它评估框架：它们有各自的目录约定，会让本 skill 的
> `iteration-N/eval-N/{with_skill|baseline}` benchmark 数据无法跨迭代对比。

## 第 1 步：在同一轮并行启动 with-skill 与 baseline

对每个测试用例，在**同一轮**启动两个子 agent——一个带 skill、一个不带。
**重要**：不要先启动 with-skill、再串行启动 baseline；并发启动让它们大致同时完成。

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

### `eval_metadata.json` 模板

为每个测试用例写一个（断言可以先留空）：

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

- 取一个**描述性**名字（不要只是 "eval-0"）；目录名也用这个
- 新 eval 目录的元数据**不**从上一迭代继承——本迭代用了新 prompt / 改过 prompt
  时必须新建

## 第 2 步：在运行进行中起草断言

不要只是等运行结束——边跑边起草定量断言。如果 `eval/evals.json` 已有断言，
审视一遍并向用户解释它们检查什么。

好的断言应当：**客观可验证**、**名字描述性**（在 benchmark viewer 里一目了然），
让瞥一眼结果的人立刻明白每个断言在检查什么。偏主观的 skill（写作风格、设计质量）
更适合定性评估，不要给需要人为判断的事强行套断言。

断言定稿后，更新 `eval_metadata.json` 和 `eval/evals.json`。同时向用户说明
viewer 里会看到什么——既包括定性输出，也包括定量基准。

## 第 3 步：跑完时采集时序数据

每个子 agent 任务结束时，会收到一个通知，其中含 `total_tokens` 和 `duration_ms`。
**立即**（不等批量）存到该运行目录下的 `timing.json`：

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

> 这是采集这份数据的**唯一机会**——它从任务通知里来，不会持久化到别处。

## 第 4 步：评分 + 聚合 + 启动 viewer

1. **为每次运行打分**：启动 grader 子 agent（或内联打分），它读
   `references/agents/grader.md`，逐条核对断言与输出。评分存到
   `<run>/grading.json`。
   - `grading.json` 的 `expectations` 数组**必须**用字段 `text` / `passed` / `evidence`
     （不要 `name` / `met` / `details` 变体）——viewer 依赖这些确切字段名
   - 可编程检查的断言写脚本跑，不要肉眼判断——脚本更快、可跨迭代复用

2. **聚合成 benchmark**：

```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
```

生成 `benchmark.json` + `benchmark.md`：含每种配置的 `pass_rate` / `time` / `tokens`，
及均值 ± 标准差与差值。**`with_skill` 必须在它对应 baseline 之前**。
手动生成时参 `references/schemas.md` 的精确 schema。

- **分析基准**：读 `references/agents/analyzer.md`「分析基准结果」节。
  关注点：无论是否使用 skill 都始终通过的断言（= 用例没鉴别力）、高方差 eval、
  时间 / Token 取舍等。聚合统计常掩盖模式。

- **启动 viewer**（同时展示定性输出 + 定量数据）：

```bash
nohup python <skill-creator-path>/scripts/generate_review.py \
  <workspace>/iteration-N \
  --skill-name "my-skill" \
  --benchmark <workspace>/iteration-N/benchmark.json \
  > /dev/null 2>&1 &
VIEWER_PID=$!
```

第 2 轮及之后的迭代，再传 `--previous-workspace <workspace>/iteration-<N-1>`。
`webbrowser.open()` 不可用或无显示器时，改用 `--static <output_path>` 生成独立 HTML。

- **告知用户**："我已经在浏览器里打开结果界面——两个 tab，Outputs 让你逐个查看每个
   测试用例并留反馈，'Benchmark' 显示定量对比。看完了告诉我一声。"

用户点"Submit All Reviews"后，反馈会作为 `feedback.json` 文件下载；拷到 workspace
目录，供下一迭代使用。**用 `scripts/generate_review.py` 生成 viewer，不要自己写 HTML**。

## 第 5 步：读取反馈

用户告知"看完了"时读 `feedback.json`：

```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "the chart is missing axis labels", "timestamp": "..."},
    {"run_id": "eval-1-with_skill", "feedback": "", "timestamp": "..."},
    {"run_id": "eval-2-with_skill", "feedback": "perfect, love this", "timestamp": "..."}
  ],
  "status": "complete"
}
```

空反馈 = 用户觉得该 eval 没问题——把精力集中在有具体意见的测试用例上。
viewer 用完后杀掉：

```bash
kill $VIEWER_PID 2>/dev/null
```

## Viewer 输出口径

**Outputs tab** 一次展示一个测试用例：

- **Prompt**：给出的任务
- **Output**：skill 产出的文件，能内联展示就内联
- **Previous Output**（第 2 轮及以后）：折叠区域，展示上一轮输出
- **Formal Grades**（跑了评分时）：折叠区域，断言通过 / 失败详情
- **Feedback**：文本框，边输入边自动保存
- **Previous Feedback**（第 2 轮及以后）：上一轮评论

**Benchmark tab**：每种配置的通过率、时序、Token 消耗、单 eval 拆解、分析观察。
通过上下页按钮或方向键浏览；点"Submit All Reviews"把所有反馈存到 `feedback.json`。

## 何时去读本文件

执行 入口 1 / 2（创建 / 改进 skill）需要落地测试用例时 `Read`。`/skill-test` 等
其它评估框架不接此约定；混用 = benchmark 不可比。

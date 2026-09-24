# JSON schema 契约

> 本文件是两份 JSON 的**唯一完整示例来源**：`ref/agents/*.md` 只放骨架，字段精确值一律以本文件为准
> （启动子 agent 时把对应节的路径附进 prompt）。字段名是契约：错名 / 缺名会被下游读成"0 通过"，
> `tools/eval_report.py` 在出任何数字前先报 ERROR
>
> 描述优化（入口 3）不在本文件范围：其 results.json 由 `tools/optimize_description.py` 直接输出（stdout），
> 供 `--apply` 写回

---

## evals.json

一个 skill 的评估集，存 skill 目录内 `eval/evals.json`

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "用户会说的任务原话",
      "expected_output": "这轮成功长什么样（给人读）",
      "files": ["eval/files/sample1.pdf"],
      "expectations": [
        "输出里包含 X",
        "用到了脚本 Y"
      ]
    }
  ]
}
```

**字段**（标注 = 机器是否读它；"校验" = 缺或错在出数前报 ERROR）：

- `skill_name`（校验）：须等于该 skill frontmatter 的 `name`；改名要同步，否则 grader 与产出对不上
- `evals[].id`（校验）：整数且全文件唯一，决定 `eval-<id>/` 目录名
- `evals[].prompt`（校验）：非空，交给执行 agent 的任务原话
- `evals[].files`（校验，可选）：输入文件路径，相对 skill 根；列了就必须真实存在
- `evals[].expectations`（grader 消费 + 覆盖率校验）：可核验断言列表；创建阶段可先空，评估循环里补
- `evals[].expected_output`（机器不读）：给人看的成功描述

---

## grading.json

grader 子 agent 的产出，存 `<run-dir>/grading.json`（与 `outputs/` 同级）

```json
{
  "expectations": [
    {
      "text": "输出里包含姓名 '张三'",
      "passed": true,
      "evidence": "transcript 第 3 步：'提取到的姓名：张三、李四'"
    },
    {
      "text": "表格 B10 单元格是 SUM 公式",
      "passed": false,
      "evidence": "没有生成表格，输出是纯文本文件"
    }
  ],
  "summary": {"passed": 1, "failed": 1, "total": 2, "pass_rate": 0.5},
  "claims": [
    {
      "claim": "表单有 12 个可填字段",
      "type": "factual",
      "verified": true,
      "evidence": "在 field_info.json 里数到 12 个"
    },
    {
      "claim": "所有必填字段都已填",
      "type": "quality",
      "verified": false,
      "evidence": "参考资料那一节是空的，尽管数据可得"
    }
  ],
  "user_notes_summary": {
    "uncertainties": ["用的是 2023 年数据，可能过期"],
    "needs_review": [],
    "workarounds": ["不可填字段改用文字覆盖"]
  },
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "输出里包含姓名 '张三'",
        "reason": "凭空编的文档只要提到这个名字也能过；建议改查它是否作为主联系人出现，并与输入里的电话、邮箱对得上"
      }
    ],
    "overall": "断言只查了有没有出现，没查对不对；建议补内容核验"
  }
}
```

**字段**（标注口径同上）：

- `expectations[]`（校验）：逐条判定，每条须齐 `text`（断言原文）/ `passed`（布尔）/ `evidence`（可核对
  的证据）
- `summary`（校验）：`passed` / `failed` / `total` / `pass_rate` 四项齐全，算术须与 `expectations` 数组
  对得上（`pass_rate = passed / total`）；给了 `--evals` 时另查覆盖率：evals.json 里每条断言都得判过，
  漏判按 ERROR 处理
- `claims`（机器不读）：从输出里提取并核验的隐含声明；`type` 取 `factual` / `process` / `quality`
- `user_notes_summary`（机器不读）：执行 agent 自标的不确定 / 需复核 / 变通
- `eval_feedback`（机器不读，可选）：对 evals 本身的批判，判据见 [grader 规范](agents/grader.md) 第 4 步

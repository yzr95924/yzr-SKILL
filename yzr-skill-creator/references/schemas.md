# JSON Schemas

This document defines the JSON schemas used by yzr-skill-creator.

> 本文件是 JSON schema **唯一完整示例来源**——`references/agents/*.md` 只含骨架，字段精确值
> 一律以本文件为准（spawn 子 agent 时把对应节的路径附进 prompt）。

## 目录

- [evals.json](#evalsjson) — 评估集
- [grading.json](#gradingjson) — 单次运行的断言评分

> 描述优化（入口 3）没有独立 JSON schema——`scripts/optimize_description.py` 直接输出
> results.json（含 history 数组），字段以该脚本 docstring 为准。

---

## evals.json

Defines the evals for a skill. Located at `eval/evals.json` within the skill directory.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's example prompt",
      "expected_output": "Description of expected result",
      "files": ["eval/files/sample1.pdf"],
      "expectations": [
        "The output includes X",
        "The skill used script Y"
      ]
    }
  ]
}
```

**Fields:**

- `skill_name`: Name matching the skill's frontmatter
- `evals[].id`: Unique integer identifier
- `evals[].prompt`: The task to execute
- `evals[].expected_output`: Human-readable description of success
- `evals[].files`: Optional list of input file paths (relative to skill root)
- `evals[].expectations`: List of verifiable statements

---

## grading.json

Output from the grader agent. Located at `<run-dir>/grading.json`（与 `outputs/` 同级）。

```json
{
  "expectations": [
    {
      "text": "The output includes the name 'John Smith'",
      "passed": true,
      "evidence": "Found in transcript Step 3: 'Extracted names: John Smith, Sarah Johnson'"
    },
    {
      "text": "The spreadsheet has a SUM formula in cell B10",
      "passed": false,
      "evidence": "No spreadsheet was created. The output was a text file."
    }
  ],
  "summary": {
    "passed": 1,
    "failed": 1,
    "total": 2,
    "pass_rate": 0.5
  },
  "claims": [
    {
      "claim": "The form has 12 fillable fields",
      "type": "factual",
      "verified": true,
      "evidence": "Counted 12 fields in field_info.json"
    },
    {
      "claim": "All required fields were populated",
      "type": "quality",
      "verified": false,
      "evidence": "Reference section was left blank despite data being available"
    }
  ],
  "user_notes_summary": {
    "uncertainties": ["Used 2023 data, may be stale"],
    "needs_review": [],
    "workarounds": ["Fell back to text overlay for non-fillable fields"]
  },
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "The output includes the name 'John Smith'",
        "reason": "A hallucinated document that mentions the name would also pass — consider checking it appears as the primary contact with matching phone and email from the input"
      }
    ],
    "overall": "Assertions check presence but not correctness. Consider adding content verification."
  }
}
```

**Fields:**

- `expectations[]`: Graded expectations with evidence
- `summary`: Aggregate pass/fail counts
- `claims`: Extracted and verified claims from the output
- `user_notes_summary`: Issues flagged by the executor
- `eval_feedback`: (optional) Improvement suggestions for the evals, only present when the grader identifies issues
  worth raising

"""trigger_score.py 冒烟：对账规则的六类行为。

契约点（破哪条挂哪条）：
- 全对 → 退出 0，输出含正确率
- verdict 与标注不符 → 1，含"误判"
- 标注有而判定无 / 判定有而标注无 → 1，含"缺判" / "多判"
- verdict 非法取值 → 1，含"非法"
- 标注形状坏（缺 should_trigger）→ 1，含"形状不对"
- JSON 损坏 → 2

Run: python3 tools/tests/smoke_test_trigger_score.py  (from yzr-skill-management/)
Exit 0 = all green, 1 = regression.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "trigger_score.py"

LABELS = [
    {"query": "q1", "should_trigger": True},
    {"query": "q2", "should_trigger": False},
]


def run(score_args):
    p = subprocess.run([sys.executable, str(SCRIPT)] + score_args, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def case(tmp, name, labels, verdicts):
    d = tmp / name
    (d / "eval").mkdir(parents=True)
    (d / "eval" / "trigger_eval.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    v = d / "verdicts.json"
    v.write_text(json.dumps(verdicts, ensure_ascii=False), encoding="utf-8")
    return run([str(d), str(v)])


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        code, out = case(
            tmp,
            "all-ok",
            LABELS,
            [
                {"query": "q1", "verdict": "触发"},
                {"query": "q2", "verdict": "不触发"},
            ],
        )
        if code != 0 or "100%" not in out:
            failures.append(f"all-ok: exit={code} out={out}")

        code, out = case(
            tmp,
            "mismatch",
            LABELS,
            [
                {"query": "q1", "verdict": "不触发"},
                {"query": "q2", "verdict": "不触发"},
            ],
        )
        if code != 1 or "误判" not in out:
            failures.append(f"mismatch: exit={code} out={out}")

        code, out = case(tmp, "missing", LABELS, [{"query": "q1", "verdict": "触发"}])
        if code != 1 or "缺判" not in out:
            failures.append(f"missing: exit={code} out={out}")

        code, out = case(
            tmp,
            "extra",
            LABELS,
            [
                {"query": "q1", "verdict": "触发"},
                {"query": "q2", "verdict": "不触发"},
                {"query": "q3", "verdict": "触发"},
            ],
        )
        if code != 1 or "多判" not in out:
            failures.append(f"extra: exit={code} out={out}")

        code, out = case(tmp, "bad-verdict", LABELS, [{"query": "q1", "verdict": "trigger"}])
        if code != 1 or "非法" not in out:
            failures.append(f"bad-verdict: exit={code} out={out}")

        code, out = case(tmp, "bad-shape", [{"query": "q1"}], [])
        if code != 1 or "形状不对" not in out:
            failures.append(f"bad-shape: exit={code} out={out}")

        d = tmp / "broken"
        (d / "eval").mkdir(parents=True)
        (d / "eval" / "trigger_eval.json").write_text("{not json", encoding="utf-8")
        v = d / "verdicts.json"
        v.write_text("[]", encoding="utf-8")
        code, out = run([str(d), str(v)])
        if code != 2:
            failures.append(f"broken-json: exit={code} out={out}")

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("trigger_score smoke: all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Fixture smoke test for eval_init's workspace scaffolding.

The class of bug this pins: the writer half drifting from the reader half —
eval_init creates a layout eval_report cannot read back, or the old-skill
snapshot silently missing (a missing baseline reads as "no comparison" and
kills quantification). Every case has both directions — the broken path must
refuse, the good path must produce the exact tree + prompts. The final case
pins the round-trip: init -> synthetic grading.json -> eval_report green.

Run: python3 tests/smoke_test_eval_init.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_tmp_dir  # noqa: E402

from tools import (
    eval_init,  # noqa: E402
    eval_report,  # noqa: E402
)

FAILURES: List[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def make_skill(root: Path, evals: List[Dict]) -> Path:
    skill = root / "demo-skill"
    (skill / "eval").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo-skill\ndescription: |\n  stub\n---\n# demo\n", encoding="utf-8")
    (skill / "eval" / "evals.json").write_text(
        json.dumps({"skill_name": "demo-skill", "evals": evals}), encoding="utf-8"
    )
    return skill


EVALS = [
    {"id": 1, "prompt": "把 A 转成 B", "files": ["eval/files/a.pdf"]},
    {"id": 2, "prompt": "summarize C", "expectations": ["mentions X"]},
]


def case_old_skill_snapshot(tmp: Path) -> None:
    print("[case] old_skill: tree + per-iteration snapshot + prompts")
    skill = make_skill(tmp / "s1", EVALS)
    ws = tmp / "s1" / "demo-skill-workspace"
    rc = eval_init.main(
        ["--workspace", str(ws), "--iteration", "1", "--skill-path", str(skill), "--baseline", "old_skill"]
    )
    check("exit 0", rc == 0, f"rc={rc}")
    it = ws / "iteration-1"
    ok_tree = all(
        (it / f"eval-{eid}" / side / "outputs").is_dir() for eid in (1, 2) for side in ("with_skill", "old_skill")
    )
    check("tree matches eval_report layout (eval-*/side/outputs)", ok_tree)
    snap = it / "skill-snapshot"
    check("snapshot exists inside iteration dir", (snap / "SKILL.md").is_file())
    check("snapshot is a copy, not the live skill", snap.resolve() != skill.resolve())


def case_without_skill_and_prompts(tmp: Path) -> None:
    print("[case] without_skill: no snapshot; prompts carry paths + tasks")
    skill = make_skill(tmp / "s2", EVALS)
    ws = tmp / "s2" / "demo-skill-workspace"
    rc = eval_init.main(
        ["--workspace", str(ws), "--iteration", "1", "--skill-path", str(skill), "--baseline", "without_skill"]
    )
    check("exit 0", rc == 0, f"rc={rc}")
    it = ws / "iteration-1"
    check("no snapshot for without_skill", not (it / "skill-snapshot").exists())
    check("without_skill outputs dir exists", (it / "eval-1" / "without_skill" / "outputs").is_dir())

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        eval_init.main(
            [
                "--workspace",
                str(tmp / "s2" / "demo-skill-workspace-w"),
                "--iteration",
                "2",
                "--skill-path",
                str(skill),
                "--baseline",
                "old_skill",
            ]
        )
    out = buf.getvalue()
    check(
        "prompt has with_skill section pointing at live skill",
        f"Skill path: {skill.resolve()}" in out and "[with_skill]" in out,
    )
    check(
        "prompt has old_skill section pointing at snapshot",
        "iteration-2/skill-snapshot" in out.replace("\\", "/") and "[old_skill]" in out,
    )
    check("prompt carries the task text and files", "把 A 转成 B" in out and "a.pdf" in out)
    check("prompt carries the parallel-start discipline", "同一轮并行" in out)


def case_refusals(tmp: Path) -> None:
    print("[case] refusals: existing iteration / malformed evals / bad paths")
    skill = make_skill(tmp / "s3", EVALS)
    ws = tmp / "s3" / "demo-skill-workspace"
    rc = eval_init.main(
        ["--workspace", str(ws), "--iteration", "1", "--skill-path", str(skill), "--baseline", "without_skill"]
    )
    check("first init succeeds", rc == 0, f"rc={rc}")
    rc = eval_init.main(
        ["--workspace", str(ws), "--iteration", "1", "--skill-path", str(skill), "--baseline", "without_skill"]
    )
    check("re-init same iteration refused (exit 2)", rc == 2, f"rc={rc}")

    broken = tmp / "s3b" / "skill"
    (broken / "eval").mkdir(parents=True)
    (broken / "SKILL.md").write_text("---\nname: x\ndescription: |\n  y\n---\n", encoding="utf-8")
    (broken / "eval" / "evals.json").write_text('{"evals": [{"id": 1}]}', encoding="utf-8")
    rc = eval_init.main(
        [
            "--workspace",
            str(tmp / "s3b" / "ws"),
            "--iteration",
            "1",
            "--skill-path",
            str(broken),
            "--baseline",
            "without_skill",
        ]
    )
    check("eval missing prompt refused (exit 2, nothing created)", rc == 2 and not (tmp / "s3b" / "ws").exists())

    rc = eval_init.main(
        [
            "--workspace",
            str(tmp / "s3c-ws"),
            "--iteration",
            "1",
            "--skill-path",
            str(tmp / "no-such-skill"),
            "--baseline",
            "without_skill",
        ]
    )
    check("non-skill path refused", rc == 2, f"rc={rc}")


def case_round_trip(tmp: Path) -> None:
    print("[case] round-trip: init layout -> synthetic grading.json -> eval_report green")
    skill = make_skill(tmp / "s4", EVALS)
    ws = tmp / "s4" / "demo-skill-workspace"
    eval_init.main(
        ["--workspace", str(ws), "--iteration", "1", "--skill-path", str(skill), "--baseline", "without_skill"]
    )
    good = {
        "expectations": [{"text": "把 A 转成 B", "passed": True, "evidence": "step 1"}],
        "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
    }
    for eid in (1, 2):
        for side in ("with_skill", "without_skill"):
            target = ws / "iteration-1" / f"eval-{eid}" / side
            (target / "grading.json").write_text(json.dumps(good), encoding="utf-8")
    findings = eval_report.collect(ws / "iteration-1")[1]
    check("eval_report reads init's layout with zero findings", findings == [], str(findings))


def main() -> int:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    case_old_skill_snapshot(tmp)
    case_without_skill_and_prompts(tmp)
    case_refusals(tmp)
    case_round_trip(tmp)
    if FAILURES:
        print(f"SMOKE FAIL: {len(FAILURES)} regression(s): {FAILURES}")
        return 1
    print("SMOKE OK: eval_init tree/snapshot/refusal/round-trip pinned (dirty + clean directions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

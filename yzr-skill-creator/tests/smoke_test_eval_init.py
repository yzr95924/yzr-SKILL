#!/usr/bin/env python3
"""Fixture smoke test for eval_init's workspace scaffolding.

The class of bug this pins: the writer half drifting from the reader half —
eval_init creates a layout eval_report cannot read back, or the old-skill
snapshot silently missing (a missing baseline reads as "no comparison" and
kills quantification). Every case has both directions — the broken path must
refuse, the good path must produce the exact tree. The final case pins the
round-trip: init -> synthetic grading.json -> eval_report green.

Run: python3 tests/smoke_test_eval_init.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_tmp_dir, run_cases  # noqa: E402

from tools import (
    eval_init,  # noqa: E402
    eval_report,  # noqa: E402
)

EVALS = [
    {"id": 1, "prompt": "把 A 转成 B", "files": ["eval/files/a.pdf"]},
    {"id": 2, "prompt": "summarize C", "expectations": ["mentions X"]},
]


def check(name: str, ok: bool, detail: str = "") -> None:
    """条件不成立时抛 AssertionError（带检查名，runner 收集）。"""
    if not ok:
        raise AssertionError(name + (f" — {detail}" if detail else ""))


def make_skill(root: Path, evals: List[Dict]) -> Path:
    """在 root 下建 demo-skill（含 eval/evals.json）。"""
    skill = root / "demo-skill"
    (skill / "eval").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo-skill\ndescription: |\n  stub\n---\n# demo\n", encoding="utf-8")
    (skill / "eval" / "evals.json").write_text(
        json.dumps({"skill_name": "demo-skill", "evals": evals}), encoding="utf-8"
    )
    return skill


def init(ws: Path, skill: Path, baseline: str) -> int:
    """跑 eval_init.main，吞掉进度输出。"""
    argv = ["--workspace", str(ws), "--iteration", "1", "--skill-path", str(skill), "--baseline", baseline]
    with contextlib.redirect_stdout(io.StringIO()):
        return eval_init.main(argv)


def case_old_skill_snapshot() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s1", EVALS)
    (skill / "node_modules" / "dep").mkdir(parents=True)
    (skill / "node_modules" / "dep" / "index.js").write_text("// vendor junk\n", encoding="utf-8")
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    ws = tmp / "s1" / "demo-skill-workspace"
    rc = init(ws, skill, "old_skill")
    check("exit 0", rc == 0, f"rc={rc}")
    it = ws / "iteration-1"
    ok_tree = all(
        (it / f"eval-{eid}" / side / "outputs").is_dir() for eid in (1, 2) for side in ("with_skill", "old_skill")
    )
    check("tree matches eval_report layout (eval-*/side/outputs)", ok_tree)
    snap = it / "skill-snapshot"
    check("snapshot exists inside iteration dir", (snap / "SKILL.md").is_file())
    check("snapshot is a copy, not the live skill", snap.resolve() != skill.resolve())
    check(
        "snapshot skips node_modules / __pycache__",
        not (snap / "node_modules").exists() and not (snap / "__pycache__").exists(),
    )


def case_without_skill_tree() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s2", EVALS)
    ws = tmp / "s2" / "demo-skill-workspace"
    rc = init(ws, skill, "without_skill")
    check("exit 0", rc == 0, f"rc={rc}")
    it = ws / "iteration-1"
    check("no snapshot for without_skill", not (it / "skill-snapshot").exists())
    check("with_skill outputs dir exists", (it / "eval-1" / "with_skill" / "outputs").is_dir())
    check("without_skill outputs dir exists", (it / "eval-1" / "without_skill" / "outputs").is_dir())


def case_refusals() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s3", EVALS)
    ws = tmp / "s3" / "demo-skill-workspace"
    rc = init(ws, skill, "without_skill")
    check("first init succeeds", rc == 0, f"rc={rc}")
    rc = init(ws, skill, "without_skill")
    check("re-init same iteration refused (exit 2)", rc == 2, f"rc={rc}")

    broken = tmp / "s3b" / "skill"
    (broken / "eval").mkdir(parents=True)
    (broken / "SKILL.md").write_text("---\nname: x\ndescription: |\n  y\n---\n", encoding="utf-8")
    (broken / "eval" / "evals.json").write_text('{"evals": [{"id": 1}]}', encoding="utf-8")
    rc = init(tmp / "s3b" / "ws", broken, "without_skill")
    check("eval missing prompt refused (exit 2, nothing created)", rc == 2 and not (tmp / "s3b" / "ws").exists())

    rc = init(tmp / "s3c-ws", tmp / "no-such-skill", "without_skill")
    check("non-skill path refused", rc == 2, f"rc={rc}")


def case_duplicate_id() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    dup = [{"id": 1, "prompt": "a"}, {"id": 1, "prompt": "b"}]
    skill = make_skill(tmp / "s5", dup)
    ws = tmp / "s5" / "demo-skill-workspace"
    rc = init(ws, skill, "without_skill")
    check("duplicate id refused (exit 2, nothing created)", rc == 2 and not ws.exists(), f"rc={rc}")


def case_round_trip() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s4", EVALS)
    ws = tmp / "s4" / "demo-skill-workspace"
    init(ws, skill, "without_skill")
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


if __name__ == "__main__":
    sys.exit(
        run_cases(
            [
                case_old_skill_snapshot,
                case_without_skill_tree,
                case_refusals,
                case_duplicate_id,
                case_round_trip,
            ]
        )
    )

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

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import expect, make_tmp_dir, run_cases, run_cli  # noqa: E402

from tools import (
    eval_init,  # noqa: E402
    eval_report,  # noqa: E402
)

EVALS = [
    {"id": 1, "prompt": "把 A 转成 B", "files": ["eval/files/a.pdf"], "expectations": ["把 A 转成 B"]},
    {"id": 2, "prompt": "summarize C", "expectations": ["mentions X"]},
]


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
    """跑 eval_init.main，吞掉全部输出，返回退出码。"""
    argv = ["--workspace", str(ws), "--iteration", "1", "--skill-path", str(skill), "--baseline", baseline]
    return run_cli(eval_init.main, argv)[0]


def case_old_skill_snapshot() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s1", EVALS)
    (skill / "node_modules" / "dep").mkdir(parents=True)
    (skill / "node_modules" / "dep" / "index.js").write_text("// vendor junk\n", encoding="utf-8")
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    ws = tmp / "s1" / "demo-skill-workspace"
    rc = init(ws, skill, "old_skill")
    expect(rc == 0, f"exit 0 — rc={rc}")
    it = ws / "iteration-1"
    ok_tree = all(
        (it / f"eval-{eid}" / side / "outputs").is_dir() for eid in (1, 2) for side in ("with_skill", "old_skill")
    )
    expect(ok_tree, "tree matches eval_report layout (eval-*/side/outputs)")
    snap = it / "skill-snapshot"
    expect((snap / "SKILL.md").is_file(), "snapshot exists inside iteration dir")
    expect(snap.resolve() != skill.resolve(), "snapshot is a copy, not the live skill")
    expect(
        not (snap / "node_modules").exists() and not (snap / "__pycache__").exists(),
        "snapshot skips node_modules / __pycache__",
    )


def case_without_skill_tree() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s2", EVALS)
    ws = tmp / "s2" / "demo-skill-workspace"
    rc = init(ws, skill, "without_skill")
    expect(rc == 0, f"exit 0 — rc={rc}")
    it = ws / "iteration-1"
    expect(not (it / "skill-snapshot").exists(), "no snapshot for without_skill")
    expect((it / "eval-1" / "with_skill" / "outputs").is_dir(), "with_skill outputs dir exists")
    expect((it / "eval-1" / "without_skill" / "outputs").is_dir(), "without_skill outputs dir exists")


def case_refusals() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s3", EVALS)
    ws = tmp / "s3" / "demo-skill-workspace"
    rc = init(ws, skill, "without_skill")
    expect(rc == 0, f"first init succeeds — rc={rc}")
    rc = init(ws, skill, "without_skill")
    expect(rc == 2, f"re-init same iteration refused (exit 2) — rc={rc}")

    broken = tmp / "s3b" / "skill"
    (broken / "eval").mkdir(parents=True)
    (broken / "SKILL.md").write_text("---\nname: x\ndescription: |\n  y\n---\n", encoding="utf-8")
    (broken / "eval" / "evals.json").write_text('{"evals": [{"id": 1}]}', encoding="utf-8")
    rc = init(tmp / "s3b" / "ws", broken, "without_skill")
    expect(rc == 2 and not (tmp / "s3b" / "ws").exists(), "eval missing prompt refused (exit 2, nothing created)")

    rc = init(tmp / "s3c-ws", tmp / "no-such-skill", "without_skill")
    expect(rc == 2, f"non-skill path refused — rc={rc}")


def case_duplicate_id() -> None:
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    dup = [{"id": 1, "prompt": "a", "expectations": ["x"]}, {"id": 1, "prompt": "b", "expectations": ["y"]}]
    skill = make_skill(tmp / "s5", dup)
    ws = tmp / "s5" / "demo-skill-workspace"
    rc = init(ws, skill, "without_skill")
    expect(rc == 2 and not ws.exists(), f"duplicate id refused (exit 2, nothing created) — rc={rc}")


def case_missing_expectations() -> None:
    """公共契约收紧：只够 init 拼任务、不够 report 对照的 evals.json 必须在建工作区前被拒。"""
    tmp = make_tmp_dir(prefix="eval-init-smoke-")
    skill = make_skill(tmp / "s6", [{"id": 1, "prompt": "a"}])
    ws = tmp / "s6" / "demo-skill-workspace"
    rc = init(ws, skill, "without_skill")
    expect(rc == 2 and not ws.exists(), f"evals missing expectations refused (exit 2, nothing created) — rc={rc}")


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
    expect(findings == [], f"eval_report reads init's layout with zero findings — {findings}")


if __name__ == "__main__":
    sys.exit(run_cases())

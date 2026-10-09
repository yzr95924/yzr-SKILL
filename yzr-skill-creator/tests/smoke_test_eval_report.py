"""Fixture smoke test for eval_report's grading.json validation.

The class of bug this pins: a grader writes the wrong field name or skips an
assertion, and the tabulation step reads the hole as "0 passed" and reports a
confident wrong score. Every case below has both directions — the broken fixture
must produce the named ERROR, the good fixture must produce none — because an
always-failing validator passes the same test as a correct one.

Run: python3 tests/smoke_test_eval_report.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import expect, make_skill_dir, make_tmp_dir, run_cases  # noqa: E402

from tools.eval_report import _cross_check_evals, check_evals, check_grading, collect, evals_by_id  # noqa: E402

ASSERTIONS = ["产出含 X", "使用了脚本 Y", "正文不含 Z"]


def good_grading(passed: List[str]) -> Dict:
    """构造覆盖 ASSERTIONS 的合法 grading.json。"""
    return {
        "expectations": [
            {"text": text, "passed": text in passed, "evidence": "transcript step 2" if text in passed else "未找到"}
            for text in ASSERTIONS
        ],
        "summary": {
            "passed": len(passed),
            "failed": len(ASSERTIONS) - len(passed),
            "total": len(ASSERTIONS),
            "pass_rate": len(passed) / len(ASSERTIONS),
        },
    }


def rules(findings: List, level: str = "ERROR") -> List[str]:
    """取指定等级的 rule id 列表。"""
    return [f.rule for f in findings if f.level == level]


def write_run(root: Path, eval_id: int, side: str, payload) -> None:
    """把一个 run 的 grading.json 写进 eval-<id>/<side>/。"""
    target = root / f"eval-{eval_id}" / side
    target.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        (target / "grading.json").write_text(payload)
    else:
        (target / "grading.json").write_text(json.dumps(payload, ensure_ascii=False))


def case_good() -> None:
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", good_grading(ASSERTIONS))
    write_run(root, 0, "old_skill", good_grading(ASSERTIONS[:1]))
    runs, findings = collect(root)
    expect(not rules(findings), f"good run produced {rules(findings)}")
    warns = [f.rule for f in findings if f.level == "WARN"]
    expect(not warns, f"good run produced WARN {warns}")
    sides = runs[0]
    expect(set(sides) == {"with_skill", "old_skill"}, f"good run: unexpected sides {sorted(sides)}")
    expect(sum(sides["with_skill"].values()) == 3, "good run: with_skill should score 3/3")


def case_field_typo() -> None:
    """`pass` instead of `passed` must be an ERROR, not a silent 0."""
    broken = {
        "expectations": [{"text": ASSERTIONS[0], "pass": True, "evidence": "x"}],
        "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
    }
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", broken)
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    expect("GRADING-SCHEMA" in rules(findings), "field typo: not reported as GRADING-SCHEMA ERROR")


def case_arithmetic() -> None:
    bad_summary = good_grading(ASSERTIONS[:1])
    bad_summary["summary"] = {"passed": 3, "failed": 0, "total": 3, "pass_rate": 1.0}
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", bad_summary)
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    got = rules(findings)
    expect("GRADING-ARITHMETIC" in got, f"summary mismatch: expected GRADING-ARITHMETIC, got {got}")


def case_malformed_types() -> None:
    """Wrong types (string pass_rate / non-int id) must be findings, not tracebacks."""
    bad_rate = good_grading(ASSERTIONS[:1])
    bad_rate["summary"]["pass_rate"] = "50%"
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", bad_rate)
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    expect("GRADING-SCHEMA" in rules(findings), f"string pass_rate: expected GRADING-SCHEMA, got {rules(findings)}")

    _by_id, findings = evals_by_id({"evals": [{"id": "one", "prompt": "p", "expectations": ASSERTIONS}]}, "evals.json")
    expect("EVALS-SCHEMA" in rules(findings), f"non-int id: expected EVALS-SCHEMA, got {rules(findings)}")


def case_unreadable() -> None:
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", '{"expectations": [')
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    expect("GRADING-SCHEMA" in rules(findings), "truncated JSON: not reported")


def case_missing_grading() -> None:
    root = make_tmp_dir(prefix="er-smoke-")
    (root / "eval-0" / "with_skill" / "outputs").mkdir(parents=True)
    _runs, findings = collect(root)
    expect("WORKSPACE-LAYOUT" in [f.rule for f in findings], "no grading.json: layout not flagged")


def case_coverage() -> None:
    """--evals cross-check: a grading.json that skips assertions must be a
    GRADING-COVERAGE ERROR (the headline bug this script exists for); a
    fully-covered run must stay silent."""
    evals, _ = evals_by_id({"evals": [{"id": 0, "prompt": "p", "expectations": ASSERTIONS}]}, "evals.json")

    # Grades only the first assertion — a grader that silently skipped the rest.
    partial = {
        "expectations": [{"text": ASSERTIONS[0], "passed": True, "evidence": "x"}],
        "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
    }
    partial_root = make_tmp_dir(prefix="er-smoke-")
    write_run(partial_root, 0, "with_skill", partial)
    runs, _ = collect(partial_root)
    got = [f.rule for f in _cross_check_evals(runs, evals, Path("evals.json")) if f.level == "ERROR"]
    expect("GRADING-COVERAGE" in got, f"coverage: skipped assertions not reported as GRADING-COVERAGE ERROR, got {got}")

    full_root = make_tmp_dir(prefix="er-smoke-")
    write_run(full_root, 0, "with_skill", good_grading(ASSERTIONS))
    runs_full, _ = collect(full_root)
    loud = [f for f in _cross_check_evals(runs_full, evals, Path("evals.json")) if f.level == "ERROR"]
    expect(not loud, f"coverage: fully-covered run produced {[(f.rule, f.level) for f in loud]}")


def case_evals_set() -> None:
    """eval/evals.json drift: stale skill_name / duplicate id / missing input file."""

    def make_skill(payload: dict) -> Path:
        """写一个带 evals.json 的临时 demo-skill 目录。"""
        return make_skill_dir(
            {
                "SKILL.md": "---\nname: demo-skill\ndescription: 触发：a。不适用：b。\n---\n# t\n",
                "eval/evals.json": json.dumps(payload, ensure_ascii=False),
            },
            prefix="er-smoke-",
            name="demo-skill",
        )

    good = make_skill(
        {"skill_name": "demo-skill", "evals": [{"id": 0, "prompt": "p", "expectations": ["x"], "files": []}]}
    )
    got = check_evals(good)
    expect(not got, f"check_evals: clean set reported {got}")
    for label, payload, want in (
        (
            "stale skill_name",
            {"skill_name": "old-name", "evals": [{"id": 0, "prompt": "p", "expectations": ["x"]}]},
            "EVALS-SCHEMA",
        ),
        (
            "duplicate id",
            {
                "skill_name": "demo-skill",
                "evals": [
                    {"id": 0, "prompt": "p", "expectations": ["x"]},
                    {"id": 0, "prompt": "q", "expectations": ["y"]},
                ],
            },
            "EVALS-SCHEMA",
        ),
        (
            "missing input file",
            {
                "skill_name": "demo-skill",
                "evals": [{"id": 0, "prompt": "p", "expectations": ["x"], "files": ["eval/files/gone.csv"]}],
            },
            "EVALS-INPUT-MISSING",
        ),
    ):
        got = [f.rule for f in check_evals(make_skill(payload)) if f.level == "ERROR"]
        expect(want in got, f"check_evals {label}: expected {want}, got {got}")


def case_multi_baseline() -> None:
    """三个侧并存：对照表只取第一个 baseline，且必须 WARN，不许靠 dict 序静默默选。"""
    root = make_tmp_dir(prefix="er-smoke-")
    for side in ("with_skill", "without_skill", "old_skill"):
        write_run(root, 0, side, good_grading(ASSERTIONS))
    _runs, findings = collect(root)
    warns = [f for f in findings if f.rule == "WORKSPACE-LAYOUT" and f.level == "WARN"]
    expect(len(warns) == 1, f"multi baseline should WARN once, got {warns}")
    expect(not rules(findings), f"multi baseline WARN should not escalate to ERROR: {rules(findings)}")


if __name__ == "__main__":
    sys.exit(run_cases())

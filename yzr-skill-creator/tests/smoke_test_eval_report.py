#!/usr/bin/env python3
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

from _fixtures import make_skill_dir, make_tmp_dir  # noqa: E402

from tools.eval_report import _cross_check_evals, check_evals, check_grading, collect, evals_by_id  # noqa: E402

ASSERTIONS = ["产出含 X", "使用了脚本 Y", "正文不含 Z"]


def good_grading(passed: List[str]) -> Dict:
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


def rules(findings, level="ERROR") -> List[str]:
    return [f.rule for f in findings if f.level == level]


def write_run(root: Path, eval_id: int, side: str, payload) -> None:
    target = root / f"eval-{eval_id}" / side
    target.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        (target / "grading.json").write_text(payload)
    else:
        (target / "grading.json").write_text(json.dumps(payload, ensure_ascii=False))


def check_good(failures: List[str], root: Path) -> None:
    write_run(root, 0, "with_skill", good_grading(ASSERTIONS))
    write_run(root, 0, "old_skill", good_grading(ASSERTIONS[:1]))
    runs, findings = collect(root)
    if rules(findings):
        failures.append(f"good run produced {rules(findings)}")
    warns = [f.rule for f in findings if f.level == "WARN"]
    if warns:
        failures.append(f"good run produced WARN {warns}")
    sides = runs[0]
    if set(sides) != {"with_skill", "old_skill"}:
        failures.append(f"good run: unexpected sides {sorted(sides)}")
    if sum(sides["with_skill"].values()) != 3:
        failures.append("good run: with_skill should score 3/3")


def check_field_typo(failures: List[str]) -> None:
    """`pass` instead of `passed` must be an ERROR, not a silent 0."""
    broken = {
        "expectations": [{"text": ASSERTIONS[0], "pass": True, "evidence": "x"}],
        "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
    }
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", broken)
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    if "GRADING-SCHEMA" not in rules(findings):
        failures.append("field typo: not reported as GRADING-SCHEMA ERROR")


def check_arithmetic(failures: List[str]) -> None:
    bad_summary = good_grading(ASSERTIONS[:1])
    bad_summary["summary"] = {"passed": 3, "failed": 0, "total": 3, "pass_rate": 1.0}
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", bad_summary)
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    got = rules(findings)
    if "GRADING-ARITHMETIC" not in got:
        failures.append(f"summary mismatch: expected GRADING-ARITHMETIC, got {got}")


def check_malformed_types(failures: List[str]) -> None:
    """Wrong types (string pass_rate / non-int id) must be findings, not tracebacks."""
    bad_rate = good_grading(ASSERTIONS[:1])
    bad_rate["summary"]["pass_rate"] = "50%"
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", bad_rate)
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    if "GRADING-SCHEMA" not in rules(findings):
        failures.append(f"string pass_rate: expected GRADING-SCHEMA, got {rules(findings)}")

    _by_id, findings = evals_by_id({"evals": [{"id": "one", "prompt": "p", "expectations": ASSERTIONS}]}, "evals.json")
    if "EVALS-SCHEMA" not in rules(findings):
        failures.append(f"non-int id: expected EVALS-SCHEMA, got {rules(findings)}")


def check_unreadable(failures: List[str]) -> None:
    root = make_tmp_dir(prefix="er-smoke-")
    write_run(root, 0, "with_skill", '{"expectations": [')
    findings, _results = check_grading(root / "eval-0" / "with_skill" / "grading.json", "eval-0")
    if "GRADING-SCHEMA" not in rules(findings):
        failures.append("truncated JSON: not reported")


def check_missing_grading(failures: List[str]) -> None:
    root = make_tmp_dir(prefix="er-smoke-")
    (root / "eval-0" / "with_skill" / "outputs").mkdir(parents=True)
    _runs, findings = collect(root)
    if "WORKSPACE-LAYOUT" not in [f.rule for f in findings]:
        failures.append("no grading.json: layout not flagged")


def check_coverage(failures: List[str]) -> None:
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
    if "GRADING-COVERAGE" not in got:
        failures.append(f"coverage: skipped assertions not reported as GRADING-COVERAGE ERROR, got {got}")

    full_root = make_tmp_dir(prefix="er-smoke-")
    write_run(full_root, 0, "with_skill", good_grading(ASSERTIONS))
    runs_full, _ = collect(full_root)
    loud = [f for f in _cross_check_evals(runs_full, evals, Path("evals.json")) if f.level == "ERROR"]
    if loud:
        failures.append(f"coverage: fully-covered run produced {[(f.rule, f.level) for f in loud]}")


def check_evals_set(failures: List[str]) -> None:
    """eval/evals.json drift: stale skill_name / duplicate id / missing input file."""

    def make_skill(payload) -> Path:
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
    if got:
        failures.append(f"check_evals: clean set reported {got}")
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
        if want not in got:
            failures.append(f"check_evals {label}: expected {want}, got {got}")


def main() -> int:
    failures: List[str] = []
    root = make_tmp_dir(prefix="er-smoke-")
    check_good(failures, root)
    check_field_typo(failures)
    check_arithmetic(failures)
    check_malformed_types(failures)
    check_unreadable(failures)
    check_missing_grading(failures)
    check_coverage(failures)
    check_evals_set(failures)
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print("SMOKE OK: eval_report good/broken directions pinned (schema, arithmetic, coverage, layout)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

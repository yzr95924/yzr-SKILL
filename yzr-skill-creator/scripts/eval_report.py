#!/usr/bin/env python3
"""Summarise one eval iteration — and reject malformed grading.json.

Two jobs, in this order:

1. **Schema check.** The grader writes ``<run>/grading.json`` by hand (or by an
   LLM), and the field names are a contract: ``expectations[].text / passed /
   evidence`` + ``summary.{passed,failed,total,pass_rate}``. A typo in a field
   name used to be invisible — whoever tabulated it read a missing key as "0
   passed" and reported a confident wrong number. Here it is an ERROR before any
   number is shown. Also checked: summary arithmetic (it must match the
   expectations array), and — when ``--evals`` is given — that every assertion
   in ``eval/evals.json`` actually got graded (a grader that silently skips
   assertions is the same class of bug).
2. **Comparison table.** with_skill vs baseline (``without_skill`` for a new
   skill, ``old_skill`` for an improvement) per eval case, plus the assertions
   that flipped between the two sides. That is the whole tabulation step of
   references/eval-pipeline.md「第 3 步」; reading outputs and judging quality
   stays with the agent.

Numbers here are not a gate: exit 1 means "the data is malformed", never
"your skill scored badly".

Usage:
    python3 -m scripts.eval_report <workspace>/iteration-1 [--evals <skill>/eval/evals.json] [--json]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap so `from scripts.utils import ...` works both as a standalone
# script and as `python -m scripts.eval_report`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import Finding  # noqa: E402

# Side directories, in display order. A run has one baseline side; both are
# listed so either layout validates.
SIDES = ("with_skill", "without_skill", "old_skill")

_EXPECTATION_KEYS = ("text", "passed", "evidence")
_SUMMARY_KEYS = ("passed", "failed", "total", "pass_rate")

# pass_rate is recomputed from the array; tolerate rounding, nothing more.
_RATE_TOLERANCE = 0.01
_EVIDENCE_PREVIEW = 60


def _load_json(path: Path) -> Tuple[Optional[Dict], List[Finding]]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return None, [_schema_finding("GRADING-SCHEMA", f"cannot read JSON: {e}", str(path))]
    if not isinstance(data, dict):
        return None, [_schema_finding("GRADING-SCHEMA", "grading.json is not a JSON object", str(path))]
    return data, []


def _schema_finding(rule: str, message: str, where: str, line: str = "", fix: str = "") -> Finding:
    """ERROR-level schema finding — most call sites here share this shape."""
    return Finding(rule=rule, level="ERROR", evidence=message, file=where, line=line, fix=fix)


def _check_expectations(expectations: List, rel: str) -> Tuple[List[Finding], Dict[str, Dict[str, bool]]]:
    """Per-assertion field check. Returns (findings, {assertion text: passed}).

    An expectation missing a contract field is dropped from the results rather
    than counted as failed: a wrong field name must not silently become a 0.
    """
    findings: List[Finding] = []
    results: Dict[str, Dict[str, bool]] = {}
    for i, item in enumerate(expectations):
        if not isinstance(item, dict):
            findings.append(_schema_finding("GRADING-SCHEMA", f"expectations[{i}] is not an object", rel, str(i)))
            continue
        missing = [k for k in _EXPECTATION_KEYS if k not in item]
        if missing:
            findings.append(
                _schema_finding(
                    "GRADING-SCHEMA",
                    f"expectations[{i}] 缺字段 {missing}——字段名是契约，缺了会被读成 0 通过",
                    rel,
                    str(i),
                    "按 references/schemas.md「grading.json」补字段",
                )
            )
            continue
        if not isinstance(item["passed"], bool):
            findings.append(
                _schema_finding("GRADING-SCHEMA", f"expectations[{i}].passed must be true/false", rel, str(i))
            )
            continue
        text = str(item["text"])
        if text in results:
            findings.append(
                Finding(
                    rule="GRADING-SCHEMA", level="WARN", evidence=f"重复的断言原文：{text[:40]}", file=rel, line=str(i)
                )
            )
        results[text] = {"passed": bool(item["passed"])}
        if not str(item.get("evidence", "")).strip():
            findings.append(
                Finding(
                    rule="GRADING-EVIDENCE",
                    level="WARN",
                    evidence=f"断言无证据：{text[:_EVIDENCE_PREVIEW]}",
                    file=rel,
                    line=str(i),
                    fix="PASS 也要可核对的证据（grader.md 的判定标准）",
                )
            )
    return findings, results


def _check_summary(summary, rel: str, results: Dict[str, Dict[str, bool]]) -> List[Finding]:
    """The summary block must be arithmetic the expectations array supports."""
    counts = {
        name: sum(1 for r in results.values() if r["passed"] == want)
        for name, want in (("passed", True), ("failed", False))
    }
    total = len(results)
    if not isinstance(summary, dict) or any(k not in summary for k in _SUMMARY_KEYS):
        missing = [k for k in _SUMMARY_KEYS if k not in (summary or {})]
        return [
            _schema_finding(
                "GRADING-SCHEMA",
                f"summary 缺字段 {missing}",
                rel,
                "summary",
                "按 references/schemas.md「grading.json」补齐",
            )
        ]
    findings: List[Finding] = []
    if (summary["passed"], summary["failed"], summary["total"]) != (counts["passed"], counts["failed"], total):
        findings.append(
            _schema_finding(
                "GRADING-ARITHMETIC",
                f"summary 与 expectations 数组不符：summary=({summary['passed']},{summary['failed']},{summary['total']}) "
                f"实算=({counts['passed']},{counts['failed']},{total})",
                rel,
                "summary",
                "以 expectations 为准重算，或补回漏掉的逐条判定",
            )
        )
    expected_rate = (counts["passed"] / total) if total else 0.0
    if abs(float(summary.get("pass_rate", -1)) - expected_rate) > _RATE_TOLERANCE:
        findings.append(
            _schema_finding(
                "GRADING-ARITHMETIC",
                f"pass_rate={summary.get('pass_rate')} 与 passed/total={expected_rate:.4f} 不符",
                rel,
                "summary",
                "pass_rate = passed / total",
            )
        )
    return findings


def check_grading(path: Path, rel: str) -> Tuple[List[Finding], Optional[Dict[str, Dict[str, bool]]]]:
    """Validate one grading.json. Returns (findings, {assertion text: passed})."""
    data, findings = _load_json(path)
    if data is None:
        return findings, None
    expectations = data.get("expectations")
    if not isinstance(expectations, list) or not expectations:
        return findings + [_schema_finding("GRADING-SCHEMA", "missing or empty `expectations` array", rel)], None
    exp_findings, results = _check_expectations(expectations, rel)
    return findings + exp_findings + _check_summary(data.get("summary"), rel, results), results


def evals_by_id(data: Dict, where: str) -> Tuple[Dict[int, List[str]], List[Finding]]:
    """{eval id: [assertion texts]} from an evals.json document, with findings.

    Takes the parsed dict (not a path) because check_evals() inspects the same
    document for other things and must not parse it twice.
    """
    by_id: Dict[int, List[str]] = {}
    findings: List[Finding] = []
    if not isinstance(data.get("evals"), list):
        findings.append(_schema_finding("EVALS-SCHEMA", "missing `evals` array", where))
        return by_id, findings
    for i, item in enumerate(data["evals"]):
        if not isinstance(item, dict) or "id" not in item or not isinstance(item.get("expectations"), list):
            findings.append(_schema_finding("EVALS-SCHEMA", f"evals[{i}] 缺 id 或 expectations 数组", where, str(i)))
            continue
        by_id[int(item["id"])] = [str(e) for e in item["expectations"]]
    return by_id, findings


def collect(iteration_dir: Path) -> Tuple[Dict[int, Dict[str, Dict[str, bool]]], List[Finding]]:
    """{eval_id: {side: {assertion: {"passed": bool}}}} plus schema findings."""
    runs: Dict[int, Dict[str, Dict[str, bool]]] = {}
    findings: List[Finding] = []
    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        if not eval_dir.is_dir():
            continue
        try:
            eval_id = int(eval_dir.name.split("-", 1)[1])
        except ValueError:
            findings.append(
                Finding(
                    rule="WORKSPACE-LAYOUT",
                    level="ERROR",
                    evidence=f"用例目录名不合规范：{eval_dir.name}",
                    file=str(eval_dir),
                    fix=f"目录名应为 eval-<id>（id 取自 {'evals.json'})",
                )
            )
            continue
        sides: Dict[str, Dict[str, bool]] = {}
        for side in SIDES:
            grading = eval_dir / side / "grading.json"
            if not grading.is_file():
                continue
            side_findings, results = check_grading(grading, str(grading.relative_to(iteration_dir)))
            findings += side_findings
            if results is not None:
                sides[side] = results
        if not sides:
            findings.append(
                Finding(
                    rule="WORKSPACE-LAYOUT",
                    level="WARN",
                    evidence=f"该用例下没有可读的 grading.json（{', '.join(SIDES)} 均缺）",
                    file=str(eval_dir),
                )
            )
        runs[eval_id] = sides
    return runs, findings


def _cross_check_evals(runs, evals: Dict[int, List[str]], evals_path: Path) -> List[Finding]:
    findings = []
    for eval_id, sides in sorted(runs.items()):
        want = evals.get(eval_id)
        if want is None:
            findings.append(
                Finding(
                    rule="EVALS-SCHEMA",
                    level="WARN",
                    evidence=f"iteration 里有 eval-{eval_id}，{evals_path.name} 里没有",
                    file=str(evals_path),
                )
            )
            continue
        for side, results in sorted(sides.items()):
            got = set(results)
            for text in want:
                if text not in got:
                    findings.append(
                        Finding(
                            rule="GRADING-COVERAGE",
                            level="ERROR",
                            evidence=f"断言未被评分（漏评 = 分母虚小）：{text[:_EVIDENCE_PREVIEW]}",
                            file=f"eval-{eval_id}/{side}",
                            line="",
                            fix="让 grader 逐条判完，或按 evals.json 修断言原文",
                        )
                    )
            extra = got - set(want)
            for text in sorted(extra):
                findings.append(
                    Finding(
                        rule="GRADING-COVERAGE",
                        level="WARN",
                        evidence=f"评分里出现 evals.json 没有的断言：{text[:_EVIDENCE_PREVIEW]}",
                        file=f"eval-{eval_id}/{side}",
                    )
                )
    return findings


def compare(runs) -> List[Dict]:
    """One row per eval case: with_skill vs whichever baseline side exists."""
    rows = []
    for eval_id, sides in sorted(runs.items()):
        baseline = next((s for s in sides if s != "with_skill"), None)
        with_skill = sides.get("with_skill")
        row = {
            "eval": eval_id,
            "with_skill": None,
            "baseline": baseline,
            "baseline_pass": None,
            "flips_to_with_skill": [],
            "flips_to_baseline": [],
        }
        if with_skill is not None:
            row["with_skill"] = f"{sum(r['passed'] for r in with_skill.values())}/{len(with_skill)}"
        if baseline is not None and with_skill is not None:
            base = sides[baseline]
            row["baseline_pass"] = f"{sum(r['passed'] for r in base.values())}/{len(base)}"
            for text, res in with_skill.items():
                if res["passed"] and not base.get(text, {}).get("passed"):
                    row["flips_to_with_skill"].append(text)
            for text, res in base.items():
                if res["passed"] and not with_skill.get(text, {}).get("passed"):
                    row["flips_to_baseline"].append(text)
        rows.append(row)
    return rows


def _evals_from_file(path: Path) -> Tuple[Dict[int, List[str]], List[Finding]]:
    data, findings = _load_json(path)
    if data is None:
        return {}, findings
    return evals_by_id(data, str(path))


def _check_evals_identity(data: Dict, skill_dir: Path, where: str) -> List[Finding]:
    """The set must declare the skill it belongs to, or it drifts silently after
    a rename (the grader and the outputs stop matching)."""
    from scripts.utils import parse_skill_md

    try:
        name = parse_skill_md(skill_dir)[0]
    except (ValueError, OSError):
        return []  # frontmatter is quick_validate's problem, not ours
    if data.get("skill_name") == name:
        return []
    return [
        _schema_finding(
            "EVALS-SCHEMA",
            f"skill_name={data.get('skill_name')!r} 与 frontmatter name={name!r} 不符",
            where,
            "",
            "改名要同步评估集，否则 grader 与产出对不上",
        )
    ]


def _check_eval_items(data: Dict, skill_dir: Path, where: str) -> List[Finding]:
    """Per-case checks: duplicate ``id`` (the workspace ``eval-<id>`` dirs would
    overwrite each other) and declared input files that no longer exist."""
    findings: List[Finding] = []
    seen = set()
    for item in data.get("evals", []):
        if not isinstance(item, dict):
            continue
        eval_id = item.get("id")
        if eval_id in seen:
            findings.append(
                _schema_finding(
                    "EVALS-SCHEMA",
                    f"id={eval_id} 重复（workspace 的 eval-<id> 目录会互相覆盖）",
                    where,
                    str(eval_id),
                )
            )
        seen.add(eval_id)
        for rel in item.get("files", []) or []:
            if (skill_dir / str(rel)).exists():
                continue
            findings.append(
                Finding(
                    rule="EVALS-INPUT-MISSING",
                    level="ERROR",
                    evidence=f"声明的输入文件不存在：{rel}",
                    file=where,
                    line=str(eval_id),
                    fix="补文件 / 改相对路径，或从 files 里删掉",
                )
            )
    return findings


def check_evals(skill_dir: Path) -> List[Finding]:
    """Static checks on ``<skill>/eval/evals.json`` (run by verify.py).

    An eval set is the contract for "is this skill better?" — a stale
    ``skill_name``, a duplicated ``id``, or an input file that no longer exists
    all quietly invalidate a round of evaluation.
    """
    path = skill_dir / "eval" / "evals.json"
    if not path.is_file():
        return []
    data, findings = _load_json(path)
    if data is None:
        return findings
    where = "eval/evals.json"
    return findings + _check_evals_identity(data, skill_dir, where) + _check_eval_items(data, skill_dir, where)


def _render_text(iteration_dir: Path, rows: List[Dict], findings: List[Finding], errors: List[Finding]) -> None:
    print(f"== {iteration_dir.name} ==")
    if not rows:
        print("  （没有用例产物）")
    else:
        print(f"{'eval':>5}  {'with_skill':>10}  {'baseline':>12}")
        for row in rows:
            baseline = f"{row['baseline_pass']} ({row['baseline']})" if row["baseline"] else str(row["baseline_pass"])
            print(f"{row['eval']:>5}  {str(row['with_skill']):>10}  {baseline:>12}")
            for text in row["flips_to_with_skill"]:
                print(f"        + 仅 with_skill 通过：{text[: _EVIDENCE_PREVIEW * 2]}")
            for text in row["flips_to_baseline"]:
                print(f"        - 仅 baseline 通过：{text[: _EVIDENCE_PREVIEW * 2]}")
    if findings:
        print("\n-- 校验 --")
        for f in findings:
            loc = f"{f.file}:{f.line}  " if f.file else ""
            print(f"  {f.level}: {f.rule}  {loc}{f.evidence}")
    else:
        print("\n  校验：全部通过")
    print(f"\n{len(rows)} case(s), {len(errors)} ERROR — {'FAIL' if errors else 'PASS'}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate grading.json files and tabulate one eval iteration.")
    parser.add_argument("iteration_dir", help="path to <skill>-workspace/iteration-N/")
    parser.add_argument("--evals", default=None, help="eval/evals.json to cross-check assertion coverage")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args(argv)

    iteration_dir = Path(args.iteration_dir).resolve()
    if not iteration_dir.is_dir():
        print(f"error: not a directory: {iteration_dir}", file=sys.stderr)
        return 2
    runs, findings = collect(iteration_dir)
    if args.evals:
        evals, eval_findings = _evals_from_file(Path(args.evals))
        findings += eval_findings
        findings += _cross_check_evals(runs, evals, Path(args.evals))
    rows = compare(runs)
    errors = [f for f in findings if f.level == "ERROR"]

    if args.json:
        print(
            json.dumps(
                {
                    "iteration_dir": str(iteration_dir),
                    "cases": rows,
                    "findings": [f.to_dict() for f in findings],
                    "ok": not errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _render_text(iteration_dir, rows, findings, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

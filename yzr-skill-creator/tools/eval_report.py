#!/usr/bin/env python3
"""Summarise one eval iteration and reject malformed grading.json."""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import SIDES, WITH_SKILL, Finding, parse_skill_md  # noqa: E402

_EXPECTATION_KEYS = ("text", "passed", "evidence")
_SUMMARY_KEYS = ("passed", "failed", "total", "pass_rate")

_RATE_TOLERANCE = 0.01
_EVIDENCE_PREVIEW = 60


def _load_json(path: Path) -> Tuple[Optional[Dict], List[Finding]]:
    """读 JSON 对象；失败返回 (None, Finding)。"""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return None, [_schema_finding("GRADING-SCHEMA", f"cannot read JSON: {e}", str(path))]
    if not isinstance(data, dict):
        return None, [_schema_finding("GRADING-SCHEMA", "grading.json is not a JSON object", str(path))]
    return data, []


def _schema_finding(rule: str, message: str, where: str, line: str = "", fix: str = "") -> Finding:
    """构造 ERROR 级 schema Finding。"""
    return Finding(rule=rule, level="ERROR", evidence=message, file=where, line=line, fix=fix)


def _check_expectations(expectations: List, rel: str) -> Tuple[List[Finding], Dict[str, bool]]:
    """逐条校验 expectations 的字段与证据，返回 (Findings, 断言原文到是否通过的映射)。"""
    findings: List[Finding] = []
    results: Dict[str, bool] = {}
    for i, item in enumerate(expectations):
        if not isinstance(item, dict):
            findings.append(_schema_finding("GRADING-SCHEMA", f"expectations[{i}] is not an object", rel, str(i)))
            continue
        missing = [k for k in _EXPECTATION_KEYS if k not in item]
        if missing:
            findings.append(
                _schema_finding(
                    "GRADING-SCHEMA",
                    f"expectations[{i}] 缺字段 {missing}，字段名是契约，缺了会被读成 0 通过",
                    rel,
                    str(i),
                    "按 ref/schemas.md 的\u201cgrading.json\u201d补字段",
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
                    rule="GRADING-SCHEMA",
                    level="WARN",
                    evidence=f"重复的断言原文：{text[:_EVIDENCE_PREVIEW]}",
                    file=rel,
                    line=str(i),
                )
            )
        results[text] = item["passed"]
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


def _check_summary(summary, rel: str, results: Dict[str, bool]) -> List[Finding]:
    """校验 summary 计数与 pass_rate 跟逐条结果一致。"""
    n_passed = sum(1 for r in results.values() if r)
    counts = {"passed": n_passed, "failed": len(results) - n_passed}
    total = len(results)
    if not isinstance(summary, dict) or any(k not in summary for k in _SUMMARY_KEYS):
        missing = [k for k in _SUMMARY_KEYS if k not in (summary or {})]
        return [
            _schema_finding(
                "GRADING-SCHEMA",
                f"summary 缺字段 {missing}",
                rel,
                "summary",
                "按 ref/schemas.md 的\u201cgrading.json\u201d补齐",
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


def check_grading(path: Path, rel: str) -> Tuple[List[Finding], Optional[Dict[str, bool]]]:
    """校验一份 grading.json，返回 (Findings, 逐条是否通过)。"""
    data, findings = _load_json(path)
    if data is None:
        return findings, None
    expectations = data.get("expectations")
    if not isinstance(expectations, list) or not expectations:
        return findings + [_schema_finding("GRADING-SCHEMA", "missing or empty `expectations` array", rel)], None
    exp_findings, results = _check_expectations(expectations, rel)
    return findings + exp_findings + _check_summary(data.get("summary"), rel, results), results


def evals_by_id(data: Dict, where: str) -> Tuple[Dict[int, List[str]], List[Finding]]:
    """从 evals.json 数据提取 id 到断言原文列表的映射。"""
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
    """汇总一个 iteration 下全部用例与侧别的评分结果。"""
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
                    fix="目录名应为 eval-<id>（id 取自 evals.json）",
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
    """交叉核对评分与 evals.json：漏评、多评、缺用例。"""
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
    """生成 with_skill 与 baseline 的对照行（含翻转断言）。"""
    rows = []
    for eval_id, sides in sorted(runs.items()):
        baseline = next((s for s in sides if s != WITH_SKILL), None)
        with_skill = sides.get(WITH_SKILL)
        row = {
            "eval": eval_id,
            "with_skill": None,
            "baseline": baseline,
            "baseline_pass": None,
            "flips_to_with_skill": [],
            "flips_to_baseline": [],
        }
        if with_skill is not None:
            row["with_skill"] = f"{sum(with_skill.values())}/{len(with_skill)}"
        if baseline is not None and with_skill is not None:
            base = sides[baseline]
            row["baseline_pass"] = f"{sum(base.values())}/{len(base)}"
            for text, res in with_skill.items():
                if res and not base.get(text, False):
                    row["flips_to_with_skill"].append(text)
            for text, res in base.items():
                if res and not with_skill.get(text, False):
                    row["flips_to_baseline"].append(text)
        rows.append(row)
    return rows


def _evals_from_file(path: Path) -> Tuple[Dict[int, List[str]], List[Finding]]:
    """读 evals.json 文件并提取 id 到断言列表的映射。"""
    data, findings = _load_json(path)
    if data is None:
        return {}, findings
    return evals_by_id(data, str(path))


def _check_evals_identity(data: Dict, skill_dir: Path, where: str) -> List[Finding]:
    """校验 evals.json 的 skill_name 与 frontmatter 一致。"""
    try:
        name = parse_skill_md(skill_dir)[0]
    except (ValueError, OSError):
        return []
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
    """校验用例 id 唯一、声明的输入文件存在。"""
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
    """校验 skill 的 eval/evals.json（存在才查）。"""
    path = skill_dir / "eval" / "evals.json"
    if not path.is_file():
        return []
    data, findings = _load_json(path)
    if data is None:
        return findings
    where = "eval/evals.json"
    return findings + _check_evals_identity(data, skill_dir, where) + _check_eval_items(data, skill_dir, where)


def _render_text(iteration_dir: Path, rows: List[Dict], findings: List[Finding], errors: List[Finding]) -> None:
    """打印人类可读的对照表与校验结果。"""
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
    """CLI 入口：校验 grading.json 并汇总一个 iteration。"""
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

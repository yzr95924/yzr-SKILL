#!/usr/bin/env python3
"""One command for "is this skill still healthy".

Why this exists: after any edit to a skill the agent has to run a fixed
sequence — quick_validate, check_anchor_health, markdownlint, ruff — and each
tool has a placement trap that silently changes the result. The one that bites
is markdownlint: run from inside a skill directory it never finds the repo root
`.markdownlint.jsonc`, falls back to line_length 80, and floods MD013 on
perfectly fine lines. That trap used to live only in the repo's MEMORY/, which is
not part of the npx-distributed skill — so a fresh install hit it again. Here the
config path and the working directory are pinned, so the trap cannot recur.

Checks run (in this order):

  1. quick_validate — frontmatter legality + body structure + description format
                      + TOC ban + retired 「何时不使用」 section + body length
  2. check_anchor_health — link anchors, backticked paths, 「节名」 pointers
  3. audit_prose — heuristic prose screens (INFO only)
  4. eval_report.check_evals — eval/evals.json drift (stale skill_name / duplicate
     id / declared input file missing)
  5. check_skill_dependencies — repo mode only; mutual-mention candidates,
                                advisory (互提 ≠ 互依, direction is a human call)
  6. markdownlint — skipped when the tool or the repo config is absent
  7. ruff check + format — only when the skill has scripts/ and/or tests/

Gating: exit 1 on any ERROR. WARN / INFO never fail a run — they are advice for
the agent to weigh. A bad invocation or unreadable target is exit 2 (UsageError). Each external tool reports a structured state (see
ToolResult): OK, FAIL (it ran and complained), SKIP (not applicable, e.g. a skill
without scripts/), MISSING (the tool / its config / the skill's placement made it
impossible to run). `--strict-tools` turns MISSING into an ERROR, for
environments where the tools are guaranteed present. Nothing about that decision
is inferred from human-readable text — rewording a message must not be able to
silently disarm the gate.

Distribution note: a vendored single-skill install has no repo root above it, so
checks 4–7 report MISSING/SKIP with a reason instead of failing. Point
`--repo-root` at a checkout when you want the full run.

Usage:
    python3 -m scripts.verify <skill-dir> [<skill-dir> ...]
    python3 -m scripts.verify --repo-root [<repo-root>]      # every skill in a repo
    python3 -m scripts.verify <skill-dir> --json
"""

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# Bootstrap so `from scripts.X import Y` works both as a standalone
# script and as `python -m scripts.verify`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import (  # noqa: E402
    audit_prose,
    check_anchor_health,
    check_skill_dependencies,
    eval_report,
    quick_validate,
)
from scripts.utils import FINDING_LEVELS, Finding, discover_skill_dirs, format_findings  # noqa: E402

# Anchor drift blocks: a dead pointer is a real defect, and CI has always
# treated check_anchor_health's exit code as a gate.
_ANCHOR_LEVEL = "ERROR"
# markdownlint / ruff failures, and a tool that could not run under --strict-tools.
_TOOL_LEVEL = "ERROR"
# check_skill_dependencies is a screen, not a verdict → never gates. But a screen
# that produced no output at all is an ERROR: reporting "clean" off an empty
# payload would hand out a green light for a measurement that never happened.
_ADVISORY_LEVEL = "INFO"

_CONFIG_FILE = ".markdownlint.jsonc"

# Tool states. Enumerated rather than inferred from message text.
TOOL_OK = "OK"
TOOL_FAIL = "FAIL"
TOOL_SKIP = "SKIP"  # not applicable to this skill
TOOL_MISSING = "MISSING"  # should have run, could not


class ToolResult(NamedTuple):
    """Outcome of one external tool invocation for one skill."""

    skill: str
    tool: str
    state: str
    detail: str = ""

    def render(self) -> str:
        return f"{self.skill}: {self.tool}: {self.state}" + (f" ({self.detail})" if self.detail else "")

    def to_dict(self) -> Dict[str, str]:
        return {"skill": self.skill, "tool": self.tool, "state": self.state, "detail": self.detail}


class Run(NamedTuple):
    """Everything one verify pass produced, before rendering."""

    per_skill: List[Tuple[Path, List[Finding]]]
    tools: List[ToolResult]
    advisory: List[Finding]

    @property
    def findings(self) -> List[Finding]:
        return [f for _, fs in self.per_skill for f in fs] + self.advisory


class UsageError(Exception):
    """Bad invocation or unreadable target; main turns it into exit code 2."""


def _repo_root(start: Path) -> Optional[Path]:
    """Nearest ancestor holding the repo's markdownlint config.

    That marker is what makes "run markdownlint from the right place" checkable
    without hardcoding a depth: the skill sits at ``<repo>/yzr-skill-creator/``
    in a checkout but at ``~/.agents/skills/yzr-skill-creator/`` when vendored.
    """
    for candidate in [start, *start.parents]:
        if (candidate / _CONFIG_FILE).is_file():
            return candidate
    return None


def _relative_to_root(path: Path, repo_root: Optional[Path]) -> Optional[str]:
    """*path* as seen from *repo_root* (tools are run with cwd=repo_root), or
    None when there is no repo root or the skill does not live under it."""
    if repo_root is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root))
    except ValueError:
        return None


def _capture_json(fn, argv: List[str]) -> Tuple[int, Optional[Dict]]:
    """Run a check script's ``main(argv)`` and parse what it printed as JSON.

    Returns None (not an empty dict) when the output was not JSON — "the screen
    ran and saw nothing" and "the screen broke" must stay distinguishable.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = fn(argv)
    try:
        return rc, json.loads(buffer.getvalue())
    except ValueError:
        return rc, None


def _quick_validate_findings(skill_dir: Path, tier: str) -> List[Finding]:
    valid, message = quick_validate.validate_skill(skill_dir)
    if not valid:
        return [Finding(rule="FRONTMATTER", level="ERROR", evidence=message, file="SKILL.md")]
    findings = quick_validate.check_body_structure(skill_dir, tier=tier)
    findings += quick_validate.check_no_when_not_section(skill_dir)
    findings += quick_validate.check_description_format(skill_dir)
    findings += quick_validate.check_no_toc(skill_dir)
    findings += quick_validate.check_body_length(skill_dir, tier=tier)
    return findings


def _anchor_findings(skill_dir: Path) -> List[Finding]:
    _files, _links, _paths, _sections, _skipped, issues = check_anchor_health.scan_skill(skill_dir)
    return [
        Finding(
            rule=issue.get("status", "ANCHOR"),
            level=_ANCHOR_LEVEL,
            evidence=issue.get("reason", ""),
            file=issue.get("file", ""),
            line=issue.get("line", ""),
            fix="修引用或补齐目标节（机制见 scripts/check_anchor_health.py docstring）",
        )
        for issue in issues
    ]


def _dependency_findings(repo_root: Path) -> List[Finding]:
    rc, payload = _capture_json(check_skill_dependencies.main, [str(repo_root), "--json"])
    broken = payload is None or not all(key in payload for key in ("pairs", "one_way"))
    if broken:
        return [
            Finding(
                rule="CROSS-SKILL-MENTION",
                level="ERROR",
                evidence=f"依赖筛查未产出可解析的结果（rc={rc}），测量通道断了，这轮不给结论",
                fix=f"单跑看报错：python3 -m scripts.check_skill_dependencies {repo_root}",
            )
        ]
    pairs, one_way = payload["pairs"], payload["one_way"]
    if not pairs and not one_way:
        return [Finding(rule="CROSS-SKILL-MENTION", level=_ADVISORY_LEVEL, evidence="跨 skill 提及：零")]
    lines = []
    if pairs:
        lines.append(f"{len(pairs)} 组互提候选对（" + "、".join(f"{p['a']}<->{p['b']}" for p in pairs) + "）")
    if one_way:
        lines.append(f"{len(one_way)} 条单向提及")
    return [
        Finding(
            rule="CROSS-SKILL-MENTION",
            level=_ADVISORY_LEVEL,
            evidence="；".join(lines) + "；互提 ≠ 互依，方向需读正文判",
            fix=f"逐条证据：python3 -m scripts.check_skill_dependencies {repo_root}",
        )
    ]


def _run_tool(cmd: List[str], cwd: Path) -> Tuple[int, str]:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        cwd=str(cwd),
    )
    return result.returncode, result.stdout


def _issue_lines(output: str) -> List[str]:
    return [line for line in output.splitlines() if line.strip()]


def _tool_output_finding(rule: str, summary: str, body: str, fix: str) -> Finding:
    """One finding per tool run: the tool's own report is the evidence, and
    splitting it into N findings only inflates the error count."""
    return Finding(
        rule=rule,
        level=_TOOL_LEVEL,
        evidence=summary + "\n" + "\n".join(body),
        fix=fix,
    )


def _markdownlint(skill_dir: Path, repo_root: Optional[Path]) -> Tuple[List[Finding], ToolResult]:
    name = skill_dir.name
    binary = shutil.which("markdownlint")
    if binary is None:
        return [], ToolResult(name, "markdownlint", TOOL_MISSING, "not installed")
    if repo_root is None:
        return [], ToolResult(name, "markdownlint", TOOL_MISSING, f"no {_CONFIG_FILE} above {skill_dir}")
    rel = _relative_to_root(skill_dir, repo_root)
    if rel is None:
        return [], ToolResult(name, "markdownlint", TOOL_MISSING, f"{skill_dir} is not under {repo_root}")
    # cwd + explicit -c are the whole point: without them markdownlint-cli stops
    # searching upward for the repo config and reverts to line_length 80.
    rc, output = _run_tool([binary, "-c", str(repo_root / _CONFIG_FILE), rel], repo_root)
    if rc == 0:
        return [], ToolResult(name, "markdownlint", TOOL_OK)
    lines = _issue_lines(output)
    finding = _tool_output_finding(
        "MARKDOWNLINT",
        f"markdownlint 报 {len(lines)} 处（config: {repo_root / _CONFIG_FILE}，cwd: {repo_root}）:",
        lines,
        "按输出修文",
    )
    return [finding], ToolResult(name, "markdownlint", TOOL_FAIL, f"{len(lines)} issue(s)")


def _ruff_run(
    skill: str, binary: str, args: List[str], rels: List[str], repo_root: Path
) -> Tuple[List[Finding], ToolResult]:
    label = "ruff " + " ".join(args)
    rc, output = _run_tool([binary] + args + rels, repo_root)
    if rc == 0:
        return [], ToolResult(skill, label, TOOL_OK)
    lines = _issue_lines(output)
    finding = _tool_output_finding(
        "RUFF", f"{label} 失败（{' '.join(rels)}）:", lines, "ruff check --fix / ruff format"
    )
    return [finding], ToolResult(skill, label, TOOL_FAIL, f"{len(lines)} line(s)")


def _ruff(skill_dir: Path, repo_root: Optional[Path]) -> Tuple[List[Finding], List[ToolResult]]:
    name = skill_dir.name
    # Runtime scripts and dev-time tests are linted together: scripts/ holds what
    # the skill executes at runtime, tests/ (smoke tests) what CI/developers run.
    sub_dirs = [skill_dir / sub for sub in ("scripts", "tests") if (skill_dir / sub).is_dir()]
    if not sub_dirs:
        return [], [ToolResult(name, "ruff", TOOL_SKIP, "skill has no scripts/ or tests/")]
    binary = shutil.which("ruff")
    if binary is None:
        return [], [ToolResult(name, "ruff", TOOL_MISSING, "not installed")]
    if repo_root is None:
        return [], [ToolResult(name, "ruff", TOOL_MISSING, "no repo root — pyproject.toml config unreachable")]
    rels: List[str] = []
    for sub_dir in sub_dirs:
        rel = _relative_to_root(sub_dir, repo_root)
        if rel is None:
            return [], [ToolResult(name, "ruff", TOOL_MISSING, f"{skill_dir} is not under {repo_root}")]
        rels.append(rel)
    findings: List[Finding] = []
    results: List[ToolResult] = []
    for args in (["check"], ["format", "--check"]):
        sub_findings, result = _ruff_run(name, binary, args, rels, repo_root)
        findings += sub_findings
        results.append(result)
    return findings, results


def verify_skill(skill_dir: Path, tier: str, repo_root: Optional[Path]) -> Tuple[List[Finding], List[ToolResult]]:
    """Every check for one skill. Returns (findings, tool results)."""
    findings = _quick_validate_findings(skill_dir, tier)
    findings += _anchor_findings(skill_dir)
    findings += audit_prose.scan_skill(skill_dir)
    findings += eval_report.check_evals(skill_dir)
    md_findings, md_result = _markdownlint(skill_dir, repo_root)
    ruff_findings, ruff_results = _ruff(skill_dir, repo_root)
    return findings + md_findings + ruff_findings, [md_result] + ruff_results


def _parse_args(argv: Optional[List[str]]):
    """Parse CLI args. Raises UsageError when no target was given (argparse only
    knows about flags, not about this either/or), so main can render it as exit 2."""
    parser = argparse.ArgumentParser(description="Run every skill health check in one command.")
    parser.add_argument("skill_dirs", nargs="*", help="skill directories to verify")
    parser.add_argument(
        "--repo-root",
        nargs="?",
        const="",
        default=None,
        help="verify every skill under a repo root (default: auto-detected above this script)",
    )
    parser.add_argument(
        "--tier",
        choices=quick_validate.SKILL_TIERS,
        default="default",
        help="skill tier for structure / length checks (default: %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="emit a single JSON document")
    parser.add_argument("--strict-tools", action="store_true", help="turn MISSING tool states into errors")
    args = parser.parse_args(argv)
    if args.repo_root is None and not args.skill_dirs:
        raise UsageError("give skill dirs or --repo-root")
    return args


def _resolve_targets(args) -> Tuple[List[Path], Optional[Path], bool]:
    """(skill dirs, repo root, repo-mode) from parsed args.

    In repo mode the root is also the scan boundary; in explicit-dirs mode it is
    only used to place the external tools, and may legitimately be None.
    """
    if args.repo_root is not None:
        root = Path(args.repo_root) if args.repo_root else _repo_root(Path(__file__).resolve().parent)
        if root is None:
            raise UsageError("no repo root above this script; pass one explicitly")
        root = root.resolve()
        targets = discover_skill_dirs(root)
        if not targets:
            raise UsageError(f"no skill directories under {root}")
        return targets, root, True
    first = Path(args.skill_dirs[0]).resolve()
    targets = [Path(p).resolve() for p in args.skill_dirs]
    for skill_dir in targets:
        if not (skill_dir / "SKILL.md").is_file():
            raise UsageError(f"no SKILL.md under {skill_dir}")
    return targets, _repo_root(first), False


def _run_checks(targets: List[Path], tier: str, root: Optional[Path], repo_mode: bool) -> Run:
    per_skill: List[Tuple[Path, List[Finding]]] = []
    tools: List[ToolResult] = []
    for skill_dir in targets:
        findings, tool_results = verify_skill(skill_dir, tier, root)
        per_skill.append((skill_dir, findings))
        tools += tool_results
    advisory = _dependency_findings(root) if repo_mode and root is not None else []
    return Run(per_skill=per_skill, tools=tools, advisory=advisory)


def _gate(run: Run, strict_tools: bool) -> List[Finding]:
    """Findings that fail the run: ERROR-level findings, plus MISSING tools when
    the caller promised the toolchain is present."""
    errors = [f for f in run.findings if f.level == "ERROR"]
    if strict_tools:
        errors += [
            Finding(
                rule="TOOL-MISSING",
                level="ERROR",
                evidence=result.render(),
                fix="python3 scripts/install-dev-deps.py",
            )
            for result in run.tools
            if result.state == TOOL_MISSING
        ]
    return errors


def _counts(findings: List[Finding]) -> Dict[str, int]:
    return {lvl: sum(1 for f in findings if f.level == lvl) for lvl in FINDING_LEVELS}


def _render_json(run: Run, root: Optional[Path], repo_mode: bool, errors: List[Finding]) -> None:
    print(
        json.dumps(
            {
                "repo_root": str(root) if repo_mode else None,
                "skills": [str(skill_dir) for skill_dir, _ in run.per_skill],
                "findings": [f.to_dict() for _, fs in run.per_skill for f in fs],
                "advisory": [f.to_dict() for f in run.advisory],
                "tools": [r.to_dict() for r in run.tools],
                "summary": _counts(run.findings),
                "error_count": len(errors),
                "ok": not errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _render_text(run: Run, errors: List[Finding]) -> None:
    for skill_dir, findings in run.per_skill:
        print(f"== {skill_dir} ==")
        print("\n".join(format_findings(findings)) if findings else "  clean")
    for line in run.advisory:
        print(format_findings([line])[0])
    print("== tools ==")
    for result in run.tools:
        print(f"  {result.render()}")
    counts = _counts(run.findings)
    print(
        f"\n{len(run.per_skill)} skill(s): {counts['ERROR']} ERROR, {counts['WARN']} WARN, "
        f"{counts['INFO']} INFO, {len(errors)} gate failure(s) — {'FAIL' if errors else 'PASS'}"
    )


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        targets, root, repo_mode = _resolve_targets(args)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    run = _run_checks(targets, args.tier, root, repo_mode)
    errors = _gate(run, args.strict_tools)
    if args.json:
        _render_json(run, root, repo_mode, errors)
    else:
        _render_text(run, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

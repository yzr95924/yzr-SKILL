#!/usr/bin/env python3
"""Fixture smoke test for verify.py's own gating logic.

verify.py hands out the green light that CI reads, so its two failure modes are
worse than the bugs it hunts:

  - a screen that produced no parseable output must not be reported as "clean"
    (a broken measurement channel reading as zero findings);
  - the MISSING-vs-SKIP decision must come from structured state, never from
    substring-matching a human-readable message (rewording a message would then
    silently disarm --strict-tools).

Both directions are pinned: the missing-tool case must gate under
``--strict-tools`` and must not gate on SKIP; the broken channel must be ERROR
while a genuinely empty result stays INFO.

Run: python3 tests/smoke_test_verify.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_skill_dir, make_tmp_dir  # noqa: E402

from tools import verify  # noqa: E402

SKILL_BODY = "---\nname: probe-skill\ndescription: 场景。触发：x。不适用：y。\n---\n# t\n\n## 输入与输出\n\n正文。\n"


def make_skill(name: str = "probe-skill") -> Path:
    """本测试的夹具：建一个带固定正文的临时 skill 目录。"""
    return make_skill_dir({"SKILL.md": SKILL_BODY}, prefix="verify-smoke-", name=name)


def fake_dependency_main(payload, garbage: bool = False):
    """Stand in for check_skill_dependencies.main: prints JSON, or junk."""

    def run(_argv: List[str]) -> int:
        print(json.dumps(payload) if not garbage else "Traceback (most recent call last): ...")
        return 1 if payload and payload.get("pairs") else 0

    return run


def with_dependencies(payload=None, garbage=False, scope=None):
    """Call verify._dependency_findings against a stubbed screen."""
    original = verify.check_skill_dependencies.main
    verify.check_skill_dependencies.main = fake_dependency_main(payload, garbage)
    try:
        return verify._dependency_findings(Path("/tmp"), scope)
    finally:
        verify.check_skill_dependencies.main = original


def check_dependency_channel(failures: List[str]) -> None:
    empty = {"pairs": [], "one_way": [], "skill_count": 3, "repo_root": "/tmp"}
    findings = with_dependencies(empty)
    levels = [(f.rule, f.level) for f in findings]
    if levels != [("CROSS-SKILL-MENTION", "INFO")]:
        failures.append(f"clean dependency screen: expected one INFO, got {levels}")
    if "零" not in findings[0].evidence:
        failures.append("clean dependency screen: evidence should say 零提及")

    for label, result in (
        ("unparseable output", with_dependencies(garbage=True)),
        ("missing keys", with_dependencies({"pairs": []})),
    ):
        levels = [(f.rule, f.level) for f in result]
        if levels != [("CROSS-SKILL-MENTION", "ERROR")]:
            failures.append(f"broken channel ({label}): expected ERROR, got {levels}")
        elif "零" in result[0].evidence:
            failures.append(f"broken channel ({label}): reported 零提及 from a dead channel")


def check_tool_states(failures: List[str]) -> None:
    skill = make_skill()
    run = verify.Run(
        per_skill=[(skill, [])], tools=[verify.ToolResult("s", "markdownlint", verify.TOOL_MISSING)], advisory=[]
    )
    if not verify._gate(run, strict_tools=True):
        failures.append("strict-tools did not gate a MISSING tool")
    if verify._gate(run, strict_tools=False):
        failures.append("non-strict run gated a MISSING tool")

    # The decision must not depend on message text (that was the old bug).
    mute = verify.Run(
        per_skill=[(skill, [])],
        tools=[verify.ToolResult("s", "markdownlint", verify.TOOL_MISSING, "")],
        advisory=[],
    )
    if not verify._gate(mute, strict_tools=True):
        failures.append("gate is reading message text: empty detail disarmed it")

    skip = verify.Run(
        per_skill=[(skill, [])],
        tools=[verify.ToolResult("s", "ruff", verify.TOOL_SKIP, "skill has no scripts/")],
        advisory=[],
    )
    if verify._gate(skip, strict_tools=True):
        failures.append("SKIP (not applicable) was gated as if the tool were missing")

    rendered = skip.tools[0].render()
    if not rendered.startswith("s: ruff: SKIP"):
        failures.append(f"ToolResult.render() format changed: {rendered!r}")


def check_markdownlint_placement(failures: List[str]) -> None:
    """A skill outside the repo root is a MISSING state, not a traceback."""
    skill = make_skill()
    other_root = make_tmp_dir(prefix="verify-smoke-") / "elsewhere"
    other_root.mkdir()
    try:
        _findings, result = verify._markdownlint(skill, other_root)
    except Exception as e:  # the old behaviour: ValueError escapes
        failures.append(f"_markdownlint raised {type(e).__name__} instead of reporting MISSING")
        return
    if result.state != verify.TOOL_MISSING:
        failures.append(f"skill outside repo root: expected MISSING, got {result.state}")
    if _findings:
        failures.append("a tool that never ran produced findings")


def check_usage_errors(failures: List[str]) -> None:
    try:
        verify._resolve_targets(verify._parse_args([]))
        failures.append("no targets: expected UsageError")
    except verify.UsageError:
        pass
    bad = make_skill()
    (bad / "SKILL.md").unlink()
    try:
        verify._resolve_targets(verify._parse_args([str(bad)]))
        failures.append("skill without SKILL.md: expected UsageError")
    except verify.UsageError:
        pass


def check_end_to_end(failures: List[str]) -> None:
    """main() still exits 0 on a healthy skill and 2 on a bad invocation."""
    skill = make_skill()
    buffer, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(err):
        rc_ok = verify.main([str(skill)])
        rc_usage = verify.main(["/nonexistent-dir"])
    if rc_usage != 2:
        failures.append(f"usage error: exit {rc_usage} != 2")
    if rc_ok not in (0, 1):
        failures.append(f"healthy run: unexpected exit {rc_ok}")
    if "skill(s):" not in buffer.getvalue():
        failures.append("human render missing its summary line")


def check_run_tool_exec_guard(failures: List[str]) -> None:
    """_run_tool survives exec failure (vanishing binary / broken shebang) instead of Traceback."""
    rc, out = verify._run_tool(["definitely-missing-tool-xyz"], Path.cwd())
    if rc != 127 or "definitely-missing-tool-xyz" not in out:
        failures.append(f"exec guard: rc={rc} out={out!r}")


def check_dependency_screen_in_single_skill_mode(failures: List[str]) -> None:
    """Single-skill mode carries the dependency advisory scoped to the target; repo mode unscoped; no root -> no screen."""
    skill = make_skill()
    calls = []

    def fake_dep(root, scope=None):
        calls.append((root, scope))
        return []

    def fake_checks(skill_dir, tier, root):
        return [], []

    original_dep = verify._dependency_findings
    original_checks = verify.verify_skill
    verify._dependency_findings = fake_dep
    verify.verify_skill = fake_checks
    try:
        verify._run_checks([skill], "default", Path("/tmp"), False)
        if calls != [(Path("/tmp"), frozenset({"probe-skill"}))]:
            failures.append(f"single-skill mode screen call/scope wrong: {calls}")
        calls.clear()
        verify._run_checks([skill], "default", Path("/tmp"), True)
        if calls != [(Path("/tmp"), None)]:
            failures.append(f"repo mode must not scope the screen: {calls}")
        calls.clear()
        verify._run_checks([skill], "default", None, False)
        if calls:
            failures.append("dependency screen ran without a repo root")
    finally:
        verify._dependency_findings = original_dep
        verify.verify_skill = original_checks


def check_dependency_scope_filter(failures: List[str]) -> None:
    """Scoped screen keeps only edges touching the target; unscoped keeps all."""
    payload = {
        "pairs": [{"a": "other-a", "b": "other-b", "a_mentions_b": [], "b_mentions_a": []}],
        "one_way": [
            {"a": "probe-skill", "b": "other-a", "a_mentions_b": []},
            {"a": "other-b", "b": "other-a", "a_mentions_b": []},
        ],
        "skill_count": 3,
        "repo_root": "/tmp",
    }
    scoped = with_dependencies(payload, scope=frozenset({"probe-skill"}))
    evidence = scoped[0].evidence if scoped else ""
    if "1 条单向提及" not in evidence or "互提候选对" in evidence:
        failures.append(f"scoped screen did not filter to the target edge: {evidence!r}")
    if "仅目标 skill 相关" not in evidence:
        failures.append(f"scoped screen evidence lacks the scope marker: {evidence!r}")
    full = with_dependencies(payload)
    evidence = full[0].evidence if full else ""
    if "1 组互提候选对" not in evidence or "2 条单向提及" not in evidence:
        failures.append(f"unscoped screen must keep every edge: {evidence!r}")


def main() -> int:
    failures: List[str] = []
    check_dependency_channel(failures)
    check_tool_states(failures)
    check_markdownlint_placement(failures)
    check_usage_errors(failures)
    check_end_to_end(failures)
    check_run_tool_exec_guard(failures)
    check_dependency_screen_in_single_skill_mode(failures)
    check_dependency_scope_filter(failures)
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print("SMOKE OK: verify gate — dead channel = ERROR, MISSING vs SKIP split, text-independent gating")
    return 0


if __name__ == "__main__":
    sys.exit(main())

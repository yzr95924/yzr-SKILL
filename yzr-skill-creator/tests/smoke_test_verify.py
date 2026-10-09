"""Fixture smoke test for verify.py's own gating logic.

verify.py hands out the green light that CI reads, so the modes pinned here are
the ones where a broken verifier is worse than the bugs it hunts:

  - the MISSING-vs-SKIP decision must come from structured state, never from
    substring-matching a human-readable message (rewording a message would then
    silently disarm --strict-tools);
  - the --audit md list must come from the shared enumerator (assets walked,
    templates kept, and only under --audit);
  - the dependency advisory must stay scoped to the target in single-skill
    mode and unscoped in repo mode.

Run: python3 tests/smoke_test_verify.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import expect, make_skill_dir, make_tmp_dir, run_cases, run_cli  # noqa: E402

from tools import verify  # noqa: E402

SKILL_BODY = "---\nname: probe-skill\ndescription: 场景。触发：x。不适用：y\n---\n# t\n\n## 输入与输出\n\n正文\n"


def make_skill(name: str = "probe-skill") -> Path:
    """本测试的夹具：建一个带固定正文的临时 skill 目录。"""
    return make_skill_dir({"SKILL.md": SKILL_BODY}, prefix="verify-smoke-", name=name)


def with_dependencies(payload: dict, scope=None) -> List:
    """Call verify._dependency_findings against a stubbed in-process scan."""
    original = verify.check_skill_dependencies.scan
    verify.check_skill_dependencies.scan = lambda root: payload
    try:
        return verify._dependency_findings(Path("/tmp"), scope)
    finally:
        verify.check_skill_dependencies.scan = original


def case_dependency_advisory() -> None:
    """A clean screen yields one INFO saying 零提及; never ERROR."""
    empty = {"pairs": [], "one_way": [], "skill_count": 3, "repo_root": "/tmp"}
    findings = with_dependencies(empty)
    levels = [(f.rule, f.level) for f in findings]
    expect(levels == [("CROSS-SKILL-MENTION", "INFO")], f"clean dependency screen: expected one INFO, got {levels}")
    expect("零" in findings[0].evidence, "clean dependency screen: evidence should say 零提及")


def case_tool_states() -> None:
    skill = make_skill()
    run = verify.Run(
        per_skill=[(skill, [])], tools=[verify.ToolResult("s", "markdownlint", verify.TOOL_MISSING)], advisory=[]
    )
    expect(bool(verify._gate(run, strict_tools=True)), "strict-tools did not gate a MISSING tool")
    expect(not verify._gate(run, strict_tools=False), "non-strict run gated a MISSING tool")

    # The decision must not depend on message text (that was the old bug).
    mute = verify.Run(
        per_skill=[(skill, [])],
        tools=[verify.ToolResult("s", "markdownlint", verify.TOOL_MISSING, "")],
        advisory=[],
    )
    expect(bool(verify._gate(mute, strict_tools=True)), "gate is reading message text: empty detail disarmed it")

    skip = verify.Run(
        per_skill=[(skill, [])],
        tools=[verify.ToolResult("s", "ruff", verify.TOOL_SKIP, "skill has no tools/ tests/")],
        advisory=[],
    )
    expect(not verify._gate(skip, strict_tools=True), "SKIP (not applicable) was gated as if the tool were missing")

    rendered = skip.tools[0].render()
    expect(rendered.startswith("s: ruff: SKIP"), f"ToolResult.render() format changed: {rendered!r}")


def case_markdownlint_placement() -> None:
    """A skill outside the repo root is a MISSING state, not a traceback."""
    skill = make_skill()
    other_root = make_tmp_dir(prefix="verify-smoke-") / "elsewhere"
    other_root.mkdir()
    _findings, result = verify._markdownlint(skill, other_root)
    expect(result.state == verify.TOOL_MISSING, f"skill outside repo root: expected MISSING, got {result.state}")
    expect(not _findings, "a tool that never ran produced findings")


def case_usage_errors() -> None:
    try:
        verify._resolve_targets(verify._parse_args([]))
        expect(False, "no targets: expected UsageError")
    except verify.UsageError:
        pass
    bad = make_skill()
    (bad / "SKILL.md").unlink()
    try:
        verify._resolve_targets(verify._parse_args([str(bad)]))
        expect(False, "skill without SKILL.md: expected UsageError")
    except verify.UsageError:
        pass


def case_end_to_end() -> None:
    """main() still exits 0 on a healthy skill and 2 on a bad invocation."""
    skill = make_skill()
    rc_ok, stdout = run_cli(verify.main, [str(skill)])
    rc_usage, _ = run_cli(verify.main, ["/nonexistent-dir"])
    expect(rc_usage == 2, f"usage error: exit {rc_usage} != 2")
    expect(rc_ok in (0, 1), f"healthy run: unexpected exit {rc_ok}")
    expect("skill(s):" in stdout, "human render missing its summary line")


def case_run_tool_exec_guard() -> None:
    """_run_tool survives exec failure (vanishing binary / broken shebang) instead of Traceback."""
    rc, out = verify._run_tool(["definitely-missing-tool-xyz"], Path.cwd())
    expect(rc == 127 and "definitely-missing-tool-xyz" in out, f"exec guard: rc={rc} out={out!r}")


def case_dependency_screen_in_single_skill_mode() -> None:
    """Single-skill mode carries the dependency advisory scoped to the target; repo mode unscoped; no root -> no screen."""
    skill = make_skill()
    calls = []

    def fake_dep(root, scope=None):
        """记录调用参数的 _dependency_findings 替身。"""
        calls.append((root, scope))
        return []

    def fake_checks(skill_dir, tier, root):
        """空检查替身。"""
        return [], []

    original_dep = verify._dependency_findings
    original_checks = verify.verify_skill
    verify._dependency_findings = fake_dep
    verify.verify_skill = fake_checks
    try:
        verify._run_checks([skill], "default", Path("/tmp"), False)
        expect(
            calls == [(Path("/tmp"), frozenset({"probe-skill"}))], f"single-skill mode screen call/scope wrong: {calls}"
        )
        calls.clear()
        verify._run_checks([skill], "default", Path("/tmp"), True)
        expect(calls == [(Path("/tmp"), None)], f"repo mode must not scope the screen: {calls}")
        calls.clear()
        verify._run_checks([skill], "default", None, False)
        expect(not calls, "dependency screen ran without a repo root")
    finally:
        verify._dependency_findings = original_dep
        verify.verify_skill = original_checks


def case_dependency_scope_filter() -> None:
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
    expect(
        "1 条单向提及" in evidence and "互提候选对" not in evidence,
        f"scoped screen did not filter to the target edge: {evidence!r}",
    )
    expect("仅目标 skill 相关" in evidence, f"scoped screen evidence lacks the scope marker: {evidence!r}")
    full = with_dependencies(payload)
    evidence = full[0].evidence if full else ""
    expect(
        "1 组互提候选对" in evidence and "2 条单向提及" in evidence,
        f"unscoped screen must keep every edge: {evidence!r}",
    )


def case_audit_scope_channel() -> None:
    """--audit lists every shipped md (assets walked, templates kept); and only then."""
    skill = make_skill()
    (skill / "ref").mkdir()
    (skill / "ref" / "guide.md").write_text("# g\n\n正文\n", encoding="utf-8")
    (skill / "ref" / "skeleton-template.md").write_text("# t\n\n正文\n", encoding="utf-8")
    (skill / "assets").mkdir()
    (skill / "assets" / "skill-template.md").write_text("# s\n\n正文\n", encoding="utf-8")

    def audit_evidence(skill_dir: Path, *extra: str) -> str:
        """跑 verify.main --json，取 AUDIT-SCOPE 的 evidence。"""
        _, stdout = run_cli(verify.main, [str(skill_dir), "--json", *extra])
        payload = json.loads(stdout)
        return next((f["evidence"] for f in payload["findings"] if f["rule"] == "AUDIT-SCOPE"), "")

    evidence = audit_evidence(skill, "--audit")
    expect(bool(evidence), "--audit did not emit AUDIT-SCOPE")
    for rel in ("SKILL.md", "ref/guide.md", "ref/skeleton-template.md", "assets/skill-template.md"):
        expect(rel in evidence, f"audit list missing {rel}: {evidence!r}")
    expect(not audit_evidence(skill), "AUDIT-SCOPE leaked without --audit")


if __name__ == "__main__":
    sys.exit(run_cases())

"""Fixture smoke test for verify.py's own gating logic.

verify.py hands out the green light that CI reads, so the modes pinned here are
the ones where a broken verifier is worse than the bugs it hunts:

  - the MISSING-vs-SKIP decision must come from structured state, never from
    substring-matching a human-readable message (rewording a message would then
    silently disarm --strict-tools);
  - the template-sync check must fire only on drift against the canonical
    section list (it gates the skeleton every new skill copies);
  - the evals-skeleton check must fire on a desynced skill_name or a vanished
    input file (silent rot: renames break eval assets without any consumer
    noticing until a test run does).

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

TEMPLATE_MATCHING = "# t\n\n## 输入与输出\n\n## 执行原则\n\n## 工作流\n\n## 参考样例\n"


def make_skill(name: str = "probe-skill") -> Path:
    """本测试的夹具：建一个带固定正文的临时 skill 目录。"""
    return make_skill_dir({"SKILL.md": SKILL_BODY}, prefix="verify-smoke-", name=name)


def error_rules(argv: List[str]) -> List[str]:
    """跑 verify.main --json，返回 ERROR 级 findings 的 rule 列表。"""
    rc, stdout = run_cli(verify.main, [*argv, "--json"])
    payload = json.loads(stdout)
    return [f["rule"] for f in payload["findings"] if f["level"] == "ERROR"]


def case_tool_states() -> None:
    skill = make_skill()
    run = verify.Run(per_skill=[(skill, [])], tools=[verify.ToolResult("s", "markdownlint", verify.TOOL_MISSING)])
    expect(bool(verify._gate(run, strict_tools=True)), "strict-tools did not gate a MISSING tool")
    expect(not verify._gate(run, strict_tools=False), "non-strict run gated a MISSING tool")

    # The decision must not depend on message text (that was the old bug).
    mute = verify.Run(per_skill=[(skill, [])], tools=[verify.ToolResult("s", "markdownlint", verify.TOOL_MISSING, "")])
    expect(bool(verify._gate(mute, strict_tools=True)), "gate is reading message text: empty detail disarmed it")

    skip = verify.Run(
        per_skill=[(skill, [])],
        tools=[verify.ToolResult("s", "ruff", verify.TOOL_SKIP, "skill has no tools/ tests/")],
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


def case_template_sync() -> None:
    """Matching template is clean; a drifted one is a single TEMPLATE-SECTION-DRIFT ERROR."""
    skill = make_skill()
    (skill / "assets").mkdir()
    tpl = skill / "assets" / "skill-template.md"
    tpl.write_text(TEMPLATE_MATCHING, encoding="utf-8")
    expect(not verify._template_sync_findings(skill), "matching template reported drift")
    tpl.write_text("# t\n\n## 输入与输出\n\n## 执行原则\n\n", encoding="utf-8")
    findings = verify._template_sync_findings(skill)
    expect(
        len(findings) == 1 and findings[0].rule == "TEMPLATE-SECTION-DRIFT" and findings[0].level == "ERROR",
        f"drifted template: expected one TEMPLATE-SECTION-DRIFT ERROR, got {findings!r}",
    )
    expect(
        "参考样例" in findings[0].evidence, f"drift evidence should name the missing section: {findings[0].evidence}"
    )


def case_evals_skeleton() -> None:
    """evals.json: wrong skill_name and missing input file each raise ERROR; a healthy set stays clean."""
    skill = make_skill()
    eval_dir = skill / "eval"
    eval_dir.mkdir()

    def rules() -> List[str]:
        return [r for r in error_rules([str(skill)]) if r.startswith("EVALS")]

    (eval_dir / "evals.json").write_text(
        json.dumps(
            {"skill_name": "wrong-name", "evals": [{"id": 1, "prompt": "p", "expectations": ["e"]}]}, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    expect(rules() == ["EVALS-JSON"], f"desynced skill_name: expected EVALS-JSON only, got {rules()}")

    (eval_dir / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "probe-skill",
                "evals": [{"id": 1, "prompt": "p", "files": ["eval/none.pdf"], "expectations": ["e"]}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    expect(rules() == ["EVALS-INPUT-MISSING"], f"vanished input file: expected EVALS-INPUT-MISSING, got {rules()}")

    (eval_dir / "evals.json").write_text(
        json.dumps(
            {"skill_name": "probe-skill", "evals": [{"id": 1, "prompt": "p", "expectations": ["e"]}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    expect(rules() == [], f"healthy evals.json produced findings: {rules()}")
    (eval_dir / "evals.json").write_text("{not json", encoding="utf-8")
    expect(rules() == ["EVALS-JSON"], f"unparseable evals.json: expected EVALS-JSON, got {rules()}")


if __name__ == "__main__":
    sys.exit(run_cases())

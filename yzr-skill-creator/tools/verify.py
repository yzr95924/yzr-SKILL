"""Run every skill health check in one command."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import (  # noqa: E402
    audit_prose,
    check_anchor_health,
    check_python_style,
    check_skill_dependencies,
    eval_report,
    quick_validate,
)
from tools.utils import (  # noqa: E402
    CANONICAL_BODY_SECTIONS,
    ERROR,
    FINDING_LEVELS,
    INFO,
    SKILL_TIERS,
    Finding,
    discover_skill_dirs,
    format_findings,
    h2_headings,
    json_text,
    parse_skill_md,
    skill_markdown_files,
)

_ADVISORY_LEVEL = INFO

_CONFIG_FILE = ".markdownlint.jsonc"


TOOL_OK = "OK"
TOOL_FAIL = "FAIL"
TOOL_SKIP = "SKIP"
TOOL_MISSING = "MISSING"


class ToolResult(NamedTuple):
    """一个工具步骤的运行结果（状态加细节）。"""

    skill: str
    tool: str
    state: str
    detail: str = ""

    def render(self) -> str:
        """渲染成一行人类可读文本。"""
        return f"{self.skill}: {self.tool}: {self.state}" + (f" ({self.detail})" if self.detail else "")

    def to_dict(self) -> Dict[str, str]:
        """转成 JSON 友好 dict。"""
        return {"skill": self.skill, "tool": self.tool, "state": self.state, "detail": self.detail}


class Run(NamedTuple):
    """一轮 verify 的全部产出（逐 skill findings、工具状态、跨 skill 建议）。"""

    per_skill: List[Tuple[Path, List[Finding]]]
    tools: List[ToolResult]
    advisory: List[Finding]

    @property
    def findings(self) -> List[Finding]:
        """拉平全部 findings（逐 skill 加 advisory）。"""
        return [f for _, fs in self.per_skill for f in fs] + self.advisory


class UsageError(Exception):
    """CLI 用法错误（参数缺失或路径不合法）。"""

    pass


def _repo_root(start: Path) -> Optional[Path]:
    """向上找含 .markdownlint.jsonc 的目录作 repo 根。"""
    for candidate in [start, *start.parents]:
        if (candidate / _CONFIG_FILE).is_file():
            return candidate
    return None


def _relative_to_root(path: Path, repo_root: Optional[Path]) -> Optional[str]:
    """返回相对 repo 根的路径；不在其下返回 None。"""
    if repo_root is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root))
    except ValueError:
        return None


def _template_sync_findings(skill_dir: Path) -> List[Finding]:
    """带 assets 模板的 skill：模板节名须与 CANONICAL_BODY_SECTIONS 一致（漂移会误导每个新 skill）。"""
    tpl = skill_dir / "assets" / "skill-template.md"
    if not tpl.is_file():
        return []
    norm = quick_validate.normalize_heading
    want = {norm(h) for h, _ in CANONICAL_BODY_SECTIONS}
    have = {norm(h) for h in h2_headings(tpl.read_text(encoding="utf-8"))}
    if want == have:
        return []
    missing = "、".join(f"## {h}" for h, _ in CANONICAL_BODY_SECTIONS if norm(h) not in have) or "无"
    extra = "、".join(f"`## {h}`" for h in sorted(have - want)) or "无"
    return [
        Finding(
            rule="TEMPLATE-SECTION-DRIFT",
            level=ERROR,
            evidence=f"assets/skill-template.md 与节名清单不一致：模板缺 {missing}，模板多出 {extra}",
            fix="以 assets/skill-template.md 为准对齐，检查器清单同步",
        )
    ]


def _dependency_findings(repo_root: Path, scope: Optional[FrozenSet[str]] = None) -> List[Finding]:
    """跑跨 skill 提及筛查（进程内直调 scan），产出建议级 Finding；scope 非空时只保留涉及这些 skill 的提及边。"""
    payload = check_skill_dependencies.scan(repo_root)
    pairs, one_way = payload["pairs"], payload["one_way"]
    if scope is not None:
        pairs = [p for p in pairs if p["a"] in scope or p["b"] in scope]
        one_way = [e for e in one_way if e["a"] in scope or e["b"] in scope]
    if not pairs and not one_way:
        label = "目标 skill 跨 skill 提及：零" if scope is not None else "跨 skill 提及：零"
        return [Finding(rule="CROSS-SKILL-MENTION", level=_ADVISORY_LEVEL, evidence=label)]
    lines = []
    if pairs:
        lines.append(f"{len(pairs)} 组互提候选对（" + "、".join(f"{p['a']}<->{p['b']}" for p in pairs) + "）")
    if one_way:
        lines.append(f"{len(one_way)} 条单向提及")
    evidence = "；".join(lines) + "；互提 ≠ 互依，方向需读正文判"
    if scope is not None:
        evidence = "（仅目标 skill 相关）" + evidence
    return [
        Finding(
            rule="CROSS-SKILL-MENTION",
            level=_ADVISORY_LEVEL,
            evidence=evidence,
            fix=f"逐条证据：python3 -m tools.check_skill_dependencies {repo_root}",
        )
    ]


def _run_tool(cmd: List[str], cwd: Path) -> Tuple[int, str]:
    """跑外部命令，返回 (退出码, stdout 与 stderr 合并输出)；exec 失败按 127 报告不抛 Traceback。"""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=str(cwd),
        )
    except FileNotFoundError as e:
        # which() 之后二进制消失、或绝对路径 shebang 的解释器缺失：报 127 交上层降级为 FAIL 行
        return 127, f"FileNotFoundError: {cmd[0]!r} (vanishing binary or missing shebang interpreter: {e})"
    return result.returncode, result.stdout


def _issue_lines(output: str) -> List[str]:
    """取输出中的非空行。"""
    return [line for line in output.splitlines() if line.strip()]


def _tool_output_finding(rule: str, summary: str, body: str, fix: str) -> Finding:
    """把工具报错行包成 ERROR 级 Finding。"""
    return Finding(
        rule=rule,
        level=ERROR,
        evidence=summary + "\n" + "\n".join(body),
        fix=fix,
    )


def _markdownlint(skill_dir: Path, repo_root: Optional[Path]) -> Tuple[List[Finding], ToolResult]:
    """对一个 skill 跑 markdownlint（显式 -c 与 cwd）。"""
    name = skill_dir.name
    binary = shutil.which("markdownlint")
    if binary is None:
        return [], ToolResult(name, "markdownlint", TOOL_MISSING, "not installed")
    if repo_root is None:
        return [], ToolResult(name, "markdownlint", TOOL_MISSING, f"no {_CONFIG_FILE} above {skill_dir}")
    rel = _relative_to_root(skill_dir, repo_root)
    if rel is None:
        return [], ToolResult(name, "markdownlint", TOOL_MISSING, f"{skill_dir} is not under {repo_root}")

    # 必须显式 -c + cwd：否则 markdownlint 向上找不到仓库配置，回退 80 列
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
    """跑一条 ruff 命令并包装结果。"""
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
    """对 skill 的 tools/tests 跑 ruff check 与 format --check。"""
    name = skill_dir.name

    sub_dirs = [skill_dir / sub for sub in ("tools", "tests") if (skill_dir / sub).is_dir()]
    if not sub_dirs:
        return [], [ToolResult(name, "ruff", TOOL_SKIP, "skill has no tools/ tests/")]
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


_AUDIT_MD_SCOPE = "audit"  # 宣告清单与 links 审计口径有意不同：审计者要精读模板与 tools/eval 下 md


def _audit_scope_findings(skill_dir: Path) -> List[Finding]:
    """--audit 模式：由统一枚举器实时产出参与审计的 md 清单。"""
    files = "、".join(str(p.relative_to(skill_dir)) for p in skill_markdown_files(skill_dir, _AUDIT_MD_SCOPE))
    return [
        Finding(
            rule="AUDIT-SCOPE",
            level=_ADVISORY_LEVEL,
            evidence=f"参与审计的 md 清单：{files}",
        )
    ]


def verify_skill(
    skill_dir: Path, tier: Optional[str], repo_root: Optional[Path]
) -> Tuple[List[Finding], List[ToolResult]]:
    """跑一个 skill 的全部检查，返回 (findings, 工具状态)。"""
    findings = quick_validate.collect_findings(skill_dir, tier)
    findings += _template_sync_findings(skill_dir)
    findings += check_anchor_health.scan_skill(skill_dir)
    findings += audit_prose.scan_skill(skill_dir)
    findings += check_python_style.scan_skill(skill_dir)
    findings += eval_report.check_evals(skill_dir)
    md_findings, md_result = _markdownlint(skill_dir, repo_root)
    ruff_findings, ruff_results = _ruff(skill_dir, repo_root)
    return findings + md_findings + ruff_findings, [md_result] + ruff_results


def _parse_args(argv: Optional[List[str]]):
    """解析 CLI 参数；缺目标时抛 UsageError。"""
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
        choices=SKILL_TIERS,
        default=None,
        help="Override every target's frontmatter metadata.tier (default: per-skill metadata.tier, fallback 'default')",
    )
    parser.add_argument("--json", action="store_true", help="emit a single JSON document")
    parser.add_argument("--strict-tools", action="store_true", help="turn MISSING tool states into errors")
    parser.add_argument(
        "--audit", action="store_true", help="add each target's audited markdown file list (audit workflow)"
    )
    args = parser.parse_args(argv)
    if args.repo_root is not None and args.skill_dirs:
        raise UsageError("--repo-root scans the whole repo; give it instead of positional skill dirs, not with them")
    if args.repo_root is None and not args.skill_dirs:
        raise UsageError("give skill dirs or --repo-root")
    return args


def _resolve_targets(args) -> Tuple[List[Path], Optional[Path], bool]:
    """解析出目标 skill 列表、repo 根与是否 repo 模式。"""
    if args.repo_root is not None:
        root = Path(args.repo_root) if args.repo_root else _repo_root(Path(__file__).resolve().parent)
        if root is None:
            raise UsageError("no repo root above this script; pass one explicitly")
        root = root.resolve()
        targets = discover_skill_dirs(root)
        if not targets:
            raise UsageError(f"no skill directories under {root}")
        return targets, root, True
    targets = [Path(p).resolve() for p in args.skill_dirs]
    for skill_dir in targets:
        if not (skill_dir / "SKILL.md").is_file():
            raise UsageError(f"no SKILL.md under {skill_dir}")
    return targets, _repo_root(targets[0]), False


def _target_name(skill_dir: Path) -> str:
    """目标 skill 的筛查名：frontmatter name，解析失败回落目录名。"""
    try:
        name = parse_skill_md(skill_dir)[0]
    except (ValueError, OSError):
        name = ""
    return name or skill_dir.name


def _run_checks(
    targets: List[Path], tier: Optional[str], root: Optional[Path], repo_mode: bool, audit: bool = False
) -> Run:
    """依次跑目标 skill 的检查并汇总成 Run；依赖筛查有仓根时总是附带，单 skill 模式过滤到目标。"""
    per_skill: List[Tuple[Path, List[Finding]]] = []
    tools: List[ToolResult] = []
    for skill_dir in targets:
        findings, tool_results = verify_skill(skill_dir, tier, root)
        if audit:
            findings = findings + _audit_scope_findings(skill_dir)
        per_skill.append((skill_dir, findings))
        tools += tool_results
    advisory: List[Finding] = []
    if root is not None:
        scope = None if repo_mode else frozenset(_target_name(skill_dir) for skill_dir in targets)
        advisory = _dependency_findings(root, scope)
    return Run(per_skill=per_skill, tools=tools, advisory=advisory)


def _gate(run: Run, strict_tools: bool) -> List[Finding]:
    """收集 ERROR 级 findings；strict 模式下工具 MISSING 也算失败。"""
    errors = [f for f in run.findings if f.level == ERROR]
    if strict_tools:
        errors += [
            Finding(
                rule="TOOL-MISSING",
                level=ERROR,
                evidence=result.render(),
                fix="python3 scripts/install-dev-deps.py",
            )
            for result in run.tools
            if result.state == TOOL_MISSING
        ]
    return errors


def _counts(findings: List[Finding]) -> Dict[str, int]:
    """按等级统计数量。"""
    return {lvl: sum(1 for f in findings if f.level == lvl) for lvl in FINDING_LEVELS}


def _render_json(run: Run, root: Optional[Path], repo_mode: bool, errors: List[Finding]) -> None:
    """输出整份 JSON 报告。"""
    print(
        json_text(
            {
                "repo_root": str(root) if repo_mode else None,
                "skills": [str(skill_dir) for skill_dir, _ in run.per_skill],
                "findings": [f.to_dict() for _, fs in run.per_skill for f in fs],
                "advisory": [f.to_dict() for f in run.advisory],
                "tools": [r.to_dict() for r in run.tools],
                "summary": _counts(run.findings),
                "error_count": len(errors),
                "ok": not errors,
            }
        )
    )


def _render_text(run: Run, errors: List[Finding]) -> None:
    """输出人类可读报告。"""
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
    """CLI 入口：解析目标、跑检查、渲染报告，返回退出码。"""
    try:
        args = _parse_args(argv)
        targets, root, repo_mode = _resolve_targets(args)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    run = _run_checks(targets, args.tier, root, repo_mode, args.audit)
    errors = _gate(run, args.strict_tools)
    if args.json:
        _render_json(run, root, repo_mode, errors)
    else:
        _render_text(run, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

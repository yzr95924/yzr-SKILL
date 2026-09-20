#!/usr/bin/env python3
"""Prose-level heuristic screens for skill audits (入口 4 · 审计速查).

Scope discipline — read this before adding a rule. Scripts take over a check
only when the *mechanical* part is genuinely hard to type correctly by hand; the
judgement stays with the agent. Two of the audit table's rows qualify:

  - 指标单一来源 (BARE-METRIC): needs cross-file grouping, no single grep does it.
  - 时间性信息不内联 (VERSION-HISTORY): a hairy BRE that has already been
    mistyped once in this repo's history (commit "修复审计 grep 语法").

Deliberately NOT here (they stay grep rows in
references/skill-writing-principles.md「审计速查」, because a one-line alternation
is not worth a rule + its exemption list):

  - agent 中立 (品牌词 grep) — trivial pattern, verdict is 100% human.
  - Iron Law 证据 / workspace 粗筛 — trivial keyword alternation.
  - 反合理化三件套 — two simple greps + a "is this a discipline skill?" call
    that a word-density proxy gets wrong (measured: the repo's doc-writing skill
    trips density, the discipline skill does not).
  - Semantic restatement / 口径漂移 — verdict moved to yzr-writing-review (its catalog
    X group + 「指令文档」组 judgment notes); no grep row lives here anymore.

Every finding is INFO: these are candidate screens, never verdicts. Output shape
is scripts.utils.Finding, same as quick_validate, so verify.py can merge them.

Usage:
    python3 -m scripts.audit_prose <skill-dir> [--json]
    python3 -m scripts.audit_prose --repo-root <repo-root> [--json]

Exit code: 0 = no findings; 1 = at least one finding (all findings are INFO —
gating on this exit code is a policy choice, not a verdict); 2 = setup error.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap so `from scripts.utils import ...` works both as a standalone
# script and as `python -m scripts.audit_prose`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import (  # noqa: E402
    Finding,
    discover_skill_dirs,
    find_code_spans,
    format_findings,
    iter_unfenced_lines,
)

# A number written next to a counting unit is a candidate metric. What makes it
# a *violation* is not the number itself but the same (number, unit) token
# recurring across files of one skill — then it is a metric with no single
# source and every edit must remember to sync all copies.
#
# The range is part of the token on purpose: "5–40 行" and "8–40 行" are two
# different budgets, and collapsing them to "40行" is a false positive this rule
# cannot argue away later.
METRIC_RE = re.compile(r"(?<![\w.])(?:\d+\s*[–—-]\s*)?\d+(?:\.\d+)?\s*(词|行|条|轮|次|秒|天)\b")

# An occurrence that names its authority on the same line ("（对齐 rubric）" /
# "以 X 为准" / "SSOT") is a declared copy, not drift — that exemption is part of
# the principles checked here (「指标单一来源」/「自包含例外」require self-aware SSOT
# notes; restatement verdicts belong to yzr-writing-review), so the rule must
# apply it rather than leaving the agent to re-derive it per hit.
DECLARED_SOURCE_RE = re.compile(r"对齐|以.{0,16}为准|直取|SSOT|同.{0,8}口径|见\s*`?[a-z0-9-]+\.md")

# Version + a change verb = the sentence is narrating this project's own
# evolution, which belongs in a commit message (rule now lives in the
# yzr-writing-review catalog, 「指令文档」组 I4).
VERSION_HISTORY_RE = re.compile(r"v?[0-9]+\.[0-9]+(?:\.[0-9]+)?\s*(?:起|开始|之后|以来|废止|引入|新增|删除)")

# Quoted material is definitional or illustrative text — the principle file
# quoting its own counter-example ("0.6.0 起删了 X") is not itself a violation,
# and neither is a grep pattern shown in backticks. This exemption is what keeps
# both rules at zero false positives on this repo's 18 markdown files.
_QUOTE_PAIRS = (('"', '"'), ("“", "”"), ("「", "」"), ("‘", "’"))


def _quote_spans(line: str) -> List[Tuple[int, int]]:
    spans = [tuple(s) for s in find_code_spans(line)]
    for opener, closer in _QUOTE_PAIRS:
        for match in re.finditer(re.escape(opener) + r"[^" + re.escape(closer) + r"\n]*" + re.escape(closer), line):
            spans.append(match.span())
    return spans


def _is_quoted(line: str, start: int, end: int) -> bool:
    return any(a <= start and end <= b for a, b in _quote_spans(line))


def _markdown_files(skill_dir: Path) -> List[Path]:
    """Prose files of one skill: SKILL.md + references/ + assets/ (recursive).

    scripts/*.py is excluded — a constant there is the *source* of truth, not a
    stray literal. scripts/*.md / eval/*.json likewise.
    """
    files: List[Path] = []
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        files.append(skill_md)
    for sub in ("references", "assets"):
        sub_root = skill_dir / sub
        if sub_root.is_dir():
            files.extend(sorted(p for p in sub_root.rglob("*.md") if p.is_file()))
    return files


def check_version_history(skill_dir: Path) -> List[Finding]:
    """VERSION-HISTORY: "vX.Y 起 / 引入 / 删除 …" narrative inside the skill's own
    spec documents.

    A version *constraint* ("Python ≥ 3.7") carries no change verb and is legal;
    quoted examples are exempt (see _QUOTE_PAIRS).
    """
    findings = []
    for md in _markdown_files(skill_dir):
        rel = str(md.relative_to(skill_dir))
        for lineno, line in iter_unfenced_lines(md.read_text()):
            for match in VERSION_HISTORY_RE.finditer(line):
                if _is_quoted(line, match.start(), match.end()):
                    continue
                findings.append(
                    Finding(
                        rule="VERSION-HISTORY-INLINE",
                        level="INFO",
                        evidence=f"自身版本演进史内联：{match.group(0)!r}；{line.strip()[:70]}",
                        file=rel,
                        line=str(lineno),
                        fix="演进叙事挪 git commit message，正文最多留一句路标"
                        "（见 references/skill-writing-principles.md「时间性信息不内联」；外部依赖版本约束合法）",
                    )
                )
    return findings


def check_bare_metrics(skill_dir: Path) -> List[Finding]:
    """BARE-METRIC: the same ``<number><unit>`` token in ≥ 2 files of one skill.

    Cross-skill coincidences are *not* reported — separate packages evolve
    independently, and "50 行" meaning two different things in two skills is
    noise, not drift. Occurrences that declare their authority on the same line
    are exempt (see DECLARED_SOURCE_RE), so what survives is a number copied
    around with no stated source. One finding per token, listing every real
    occurrence, so the agent has the full picture to judge which copy rules.
    """
    occurrences: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for md in _markdown_files(skill_dir):
        rel = str(md.relative_to(skill_dir))
        for lineno, line in iter_unfenced_lines(md.read_text()):
            if DECLARED_SOURCE_RE.search(line):
                continue
            for match in METRIC_RE.finditer(line):
                token = re.sub(r"\s+", "", match.group(0))
                if _is_quoted(line, match.start(), match.end()):
                    continue
                occurrences[token].append((rel, str(lineno)))

    findings = []
    for token in sorted(occurrences):
        hits = occurrences[token]
        files = {f for f, _ in hits}
        if len(files) < 2:
            continue
        where = "、".join(f"{f}:{ln}" for f, ln in hits)
        findings.append(
            Finding(
                rule="BARE-METRIC",
                level="INFO",
                evidence=f"指标 `{token}` 散落在 {len(files)} 个文件（{where}）",
                file="",
                line="",
                fix="确认权威出处后：脚本常量则 prose 改 `` `CONST` `` 引用，prose 则留一处其余改指针"
                "（见 references/skill-writing-principles.md「指标单一来源」）",
            )
        )
    return findings


def scan_skill(skill_dir: Path) -> List[Finding]:
    """Run every prose heuristic over one skill directory."""
    findings = check_version_history(skill_dir)
    findings += check_bare_metrics(skill_dir)
    return findings


def _collect_targets(args, parser) -> Tuple[List[Path], int]:
    """(skill dirs, exit code). A non-zero code means the target set was invalid.

    The repo sweep reuses scripts.utils.discover_skill_dirs so "what counts as a
    skill" stays a single rule across every checker in this skill.
    """
    if args.repo_root:
        root = Path(args.repo_root).resolve()
        if not root.is_dir():
            print(f"error: repo root not found: {root}", file=sys.stderr)
            return [], 2
        return discover_skill_dirs(root), 0
    if args.skill_dir:
        skill_dir = Path(args.skill_dir).resolve()
        if not (skill_dir / "SKILL.md").is_file():
            print(f"error: no SKILL.md under: {skill_dir}", file=sys.stderr)
            return [], 2
        return [skill_dir], 0
    # parser.error raises SystemExit(2); nothing below it runs.
    parser.error("give a skill dir or --repo-root")


def scan_all(targets: List[Path]) -> List[Finding]:
    """Screens over several skills, each finding tagged with its skill."""
    findings: List[Finding] = []
    for skill_dir in targets:
        for finding in scan_skill(skill_dir):
            if len(targets) > 1:
                finding = finding._replace(evidence=f"[{skill_dir.name}] {finding.evidence}")
            findings.append(finding)
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Heuristic prose screens for skill audits (candidate list, not verdicts)."
    )
    parser.add_argument("skill_dir", nargs="?", default=None, help="path to one skill directory")
    parser.add_argument("--repo-root", default=None, help="scan every skill dir under this repo root")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human-readable lines")
    args = parser.parse_args(argv)

    targets, code = _collect_targets(args, parser)
    if code:
        return code
    findings = scan_all(targets)

    if args.json:
        print(
            json.dumps(
                {
                    "targets": [str(t) for t in targets],
                    "finding_count": len(findings),
                    "findings": [f.to_dict() for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for line in format_findings(findings):
            print(line)
        print(
            f"\nScanned {len(targets)} skill(s); {len(findings)} candidate finding(s) — "
            "INFO level: screens, not verdicts; the agent confirms 违规 / 豁免 per row."
        )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

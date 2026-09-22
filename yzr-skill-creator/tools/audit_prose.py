#!/usr/bin/env python3
"""Prose-level heuristic screens for skill audits."""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import (  # noqa: E402
    Finding,
    discover_skill_dirs,
    find_code_spans,
    format_findings,
    iter_unfenced_lines,
)

METRIC_RE = re.compile(r"(?<![\w.])(?:\d+\s*[–—-]\s*)?\d+(?:\.\d+)?\s*(词|字|行|条|轮|次|秒|天)\b")


DECLARED_SOURCE_RE = re.compile(r"对齐|以.{0,16}为准|直取|SSOT|单一来源|同.{0,8}口径|见\s*`?[a-z0-9-]+\.md")


VERSION_HISTORY_RE = re.compile(r"v?[0-9]+\.[0-9]+(?:\.[0-9]+)?\s*(?:起|开始|之后|以来|废止|引入|新增|删除)")


_QUOTE_PAIRS = (('"', '"'), ("“", "”"), ("‘", "’"))


def _quote_spans(line: str) -> List[Tuple[int, int]]:
    """返回行内被引号或代码段覆盖的偏移区间。"""
    spans = [tuple(s) for s in find_code_spans(line)]
    for opener, closer in _QUOTE_PAIRS:
        for match in re.finditer(re.escape(opener) + r"[^" + re.escape(closer) + r"\n]*" + re.escape(closer), line):
            spans.append(match.span())
    return spans


def _is_quoted(line: str, start: int, end: int) -> bool:
    """判断给定偏移区间是否落在引号或代码段内。"""
    return any(a <= start and end <= b for a, b in _quote_spans(line))


def _markdown_files(skill_dir: Path) -> List[Path]:
    """列出要扫的 md：SKILL.md 加 ref/assets 下的文件。"""
    files: List[Path] = []
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        files.append(skill_md)
    for sub in ("ref", "assets"):
        sub_root = skill_dir / sub
        if sub_root.is_dir():
            files.extend(sorted(p for p in sub_root.rglob("*.md") if p.is_file()))
    return files


_EVIDENCE_SNIPPET = 70


def check_version_history(skill_dir: Path) -> List[Finding]:
    """筛内联的自身版本演进史（引号或代码段内的除外）。"""
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
                        evidence=f"自身版本演进史内联：{match.group(0)!r}；{line.strip()[:_EVIDENCE_SNIPPET]}",
                        file=rel,
                        line=str(lineno),
                        fix="演进叙事挪 git commit message，正文最多留一句路标"
                        "（见 ref/audit-workflow.md“判定清单”；外部依赖版本约束合法）",
                    )
                )
    return findings


def check_bare_metrics(skill_dir: Path) -> List[Finding]:
    """筛散落在两个以上文件的裸指标（行内已声明出处的除外）。"""
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
                fix="确认权威出处后：脚本常量则散文改 `` `CONST` `` 引用，散文则留一处其余改指针"
                "（见 ref/audit-workflow.md“判定清单”）",
            )
        )
    return findings


AGENT_NAME_RE = re.compile(r"\b(?:Claude(?:\s+Code)?|Qoder|Cursor|Windsurf|Copilot)\b")

# 本行豁免说明：筛查定义自身含被点名的 agent 名，扫自己会自引用误报
_SELF_EXEMPT_RE = re.compile(r"^(AGENT_NAME_RE|_SELF_EXEMPT_RE)\s*=")


def check_agent_names_in_code(skill_dir: Path) -> List[Finding]:
    """筛 tools/ 脚本里点名具体 agent 的字符串（判定清单"agent 中立"的脚本侧；例外由人判）。"""
    findings = []
    sub_root = skill_dir / "tools"
    if not sub_root.is_dir():
        return findings
    for py in sorted(p for p in sub_root.rglob("*.py") if p.is_file()):
        rel = str(py.relative_to(skill_dir))
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            if _SELF_EXEMPT_RE.match(line.strip()):
                continue
            match = AGENT_NAME_RE.search(line)
            if match:
                findings.append(
                    Finding(
                        rule="AGENT-NAME-CODE",
                        level="INFO",
                        evidence=f"脚本点名 agent：{match.group(0)!r}；{line.strip()[:_EVIDENCE_SNIPPET]}",
                        file=rel,
                        line=str(lineno),
                        fix="可泛化改泛指（"
                        '"AI coding agent"）；针对该 agent 特有机制设计的可保留（口径见 ref/audit-workflow.md“判定清单”）',
                    )
                )
    return findings


def scan_skill(skill_dir: Path) -> List[Finding]:
    """跑一个 skill 的全部散文启发式筛查。"""
    findings = check_version_history(skill_dir)
    findings += check_bare_metrics(skill_dir)
    findings += check_agent_names_in_code(skill_dir)
    return findings


def _collect_targets(args, parser) -> Tuple[List[Path], int]:
    """解析扫描目标，返回 (目标列表, 退出码)。"""
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

    # parser.error 抛 SystemExit(2)，下面不会执行
    parser.error("give a skill dir or --repo-root")


def scan_all(targets: List[Path]) -> List[Finding]:
    """多目标时给每条 Finding 加 skill 名前缀。"""
    findings: List[Finding] = []
    for skill_dir in targets:
        for finding in scan_skill(skill_dir):
            if len(targets) > 1:
                finding = finding._replace(evidence=f"[{skill_dir.name}] {finding.evidence}")
            findings.append(finding)
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：输出启发式候选清单；有候选时退出码 1。"""
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
            "INFO level: screens, not verdicts; the agent confirms 违反 / 豁免 per row."
        )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

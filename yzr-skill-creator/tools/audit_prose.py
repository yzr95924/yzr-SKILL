#!/usr/bin/env python3
"""Prose-level heuristic screens for skill audits."""

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import (  # noqa: E402
    Finding,
    find_code_spans,
    iter_unfenced_lines,
    run_screen,
    skill_markdown_files,
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


_EVIDENCE_SNIPPET = 70


def check_version_history(skill_dir: Path) -> List[Finding]:
    """筛内联的自身版本演进史（引号或代码段内的除外）。"""
    findings = []
    for md in skill_markdown_files(skill_dir):
        rel = str(md.relative_to(skill_dir))
        for lineno, line in iter_unfenced_lines(md.read_text(encoding="utf-8")):
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
    for md in skill_markdown_files(skill_dir):
        rel = str(md.relative_to(skill_dir))
        for lineno, line in iter_unfenced_lines(md.read_text(encoding="utf-8")):
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


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：输出启发式候选清单；有候选时退出码 1。"""
    return run_screen(
        "Heuristic prose screens for skill audits (candidate list, not verdicts).",
        scan_skill,
        argv,
        "candidate finding(s) — INFO level: screens, not verdicts; the agent confirms 违反 / 豁免 per row.",
    )


if __name__ == "__main__":
    sys.exit(main())

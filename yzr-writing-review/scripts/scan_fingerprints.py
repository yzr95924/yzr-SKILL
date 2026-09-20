#!/usr/bin/env python3
"""Scan markdown for enumerable AI-style fingerprints (literal matches only).

Findings are INFO candidates: detection is mechanical, the fix is reviewer
judgment (quote / meta-mention exemptions stay human).

Extension contract for PATTERNS: literal or regex only (no judgment),
near-zero false positives on the real corpus, positive + negative fixtures in
tests/smoke_test_scan_fingerprints.py, rule text stays in
references/catalog.md.

Usage: python3 scripts/scan_fingerprints.py <file-or-dir> [--json]
A directory scans **/*.md. Fence blocks and inline code spans are skipped;
meta-mentions are deliberately reported. Exit code is always 0.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional

DASH = "\u2014\u2014"  # 中文双破折号「——」


class Pattern(NamedTuple):
    pid: str
    literal: str
    rule: str


PATTERNS = [
    Pattern("DASH", DASH, "catalog 第六组 标点与排版指纹「破折号」行"),
]

FENCE = re.compile(r"^\s*```")
# inline code spans: double-backtick first, then single-backtick
CODE_SPANS = (re.compile(r"``[^`\n]+``"), re.compile(r"`[^`\n]*`"))


class Hit(NamedTuple):
    file: str
    line: int
    pid: str
    count: int
    evidence: str
    rule: str


def mask_code_spans(line: str) -> str:
    for span in CODE_SPANS:
        line = span.sub(lambda m: " " * len(m.group(0)), line)
    return line


def scan_text(text: str, rel: str) -> List[Hit]:
    """Scan markdown text; returns candidate hits. Fence and inline code are skipped."""
    hits: List[Hit] = []
    in_fence = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        hay = mask_code_spans(raw)
        for pat in PATTERNS:
            count = hay.count(pat.literal)
            if count:
                snippet = raw.strip()
                if len(snippet) > 80:
                    snippet = snippet[:80] + "…"
                hits.append(Hit(rel, lineno, pat.pid, count, snippet, pat.rule))
    return hits


def iter_targets(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    return sorted(root.rglob("*.md"))


def run(paths: List[str], cwd: Optional[Path] = None) -> List[Hit]:
    cwd = cwd or Path.cwd()
    hits: List[Hit] = []
    for p in paths:
        target = Path(p)
        for md in iter_targets(target):
            text = md.read_text(encoding="utf-8")
            try:
                rel = str(md.resolve().relative_to(cwd))
            except ValueError:
                rel = str(md)
            hits.extend(scan_text(text, rel))
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", help="markdown file(s) or directory to scan")
    parser.add_argument("--json", action="store_true", dest="as_json", help="machine-readable output")
    args = parser.parse_args(argv)
    hits = run(args.paths)
    if args.as_json:
        print(json.dumps([h._asdict() for h in hits], ensure_ascii=False, indent=1))
    else:
        for h in hits:
            print(f"INFO: {h.file}:{h.line} {h.pid} {h.evidence}")
        print(f"scanned: {len(hits)} candidate(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

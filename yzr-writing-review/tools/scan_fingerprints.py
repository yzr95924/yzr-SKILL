#!/usr/bin/env python3
"""扫描 Markdown 里的 AI 腔指纹，输出 INFO 候选（仅字面 / 正则命中）。"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional

DASH = "\u2014\u2014"  # 中文双破折号"——"
CORNER_QUOTE = "\u300c"  # 中文左角引号"「"（成对符号，开侧计一次）
SECTION_SIGN = "\u00a7"  # 章节符号"§"
ARROW = "\u2192"  # 箭头"→"
# 段落开头的装饰性 emoji；✓ ✗ ★ ⚠ 表格中的 ✅ 等是技术文档正当用法，靠行首锚定排除
EMOJI_RE = r"^\s*(?:[-*+]\s+)?[\U0001F300-\U0001FAFF\u2728\u26A1\u274C\u2705\u2757\u2764]"

# 扩展契约：PATTERNS 只收字面 / 正则命中（不做判断），新增模式须配正反夹具
# （tests/smoke_test_scan_fingerprints.py），规则文案归 ref/catalog.md；
# 元提及（讨论符号本身的行）有意上报，由 reviewer 豁免。


class Pattern(NamedTuple):
    """一条指纹模式：pid / 字面 / catalog 规则文案，regex 置位时按正则计数。"""

    pid: str
    literal: str
    rule: str
    regex: Optional[str] = None  # 置位时按正则计数，literal 留空


PATTERNS = [
    Pattern("DASH", DASH, "catalog AI 腔指纹“破折号”行"),
    Pattern("CORNER-QUOTE", CORNER_QUOTE, "catalog AI 腔指纹“CJK 角引号”行"),
    Pattern("SECTION-SIGN", SECTION_SIGN, "catalog AI 腔指纹“§ 章节符号”行"),
    Pattern("ARROW", ARROW, "catalog AI 腔指纹“→ 箭头”行"),
    Pattern("EMOJI", "", "catalog AI 腔指纹“emoji 点缀”行", EMOJI_RE),
]

FENCE = re.compile(r"^\s*```")
# inline code spans: double-backtick first, then single-backtick
CODE_SPANS = (re.compile(r"``[^`\n]+``"), re.compile(r"`[^`\n]*`"))


class Hit(NamedTuple):
    """一条候选命中：文件 / 行 / 指纹 / 计数 / 证据片段 / 规则文案。"""

    file: str
    line: int
    pid: str
    count: int
    evidence: str
    rule: str


def mask_code_spans(line: str) -> str:
    """把行内代码段替换为等长空格，避免代码内容计入命中。"""
    for span in CODE_SPANS:
        line = span.sub(lambda m: " " * len(m.group(0)), line)
    return line


def scan_text(text: str, rel: str) -> List[Hit]:
    """扫描一段 Markdown，返回候选命中；围栏与行内代码跳过。"""
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
            count = len(re.findall(pat.regex, hay)) if pat.regex else hay.count(pat.literal)
            if count:
                snippet = raw.strip()
                if len(snippet) > 80:
                    snippet = snippet[:80] + "…"
                hits.append(Hit(rel, lineno, pat.pid, count, snippet, pat.rule))
    return hits


def iter_targets(root: Path) -> List[Path]:
    """文件直接返回，目录则递归列出全部 md。"""
    if root.is_file():
        return [root]
    return sorted(root.rglob("*.md"))


def run(paths: List[str], cwd: Optional[Path] = None) -> List[Hit]:
    """对多个路径跑扫描，rel 相对 cwd 计算（失败时用原路径）。"""
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
    """CLI 入口：打印候选（--json 机器可读）；始终退出 0（候选不是门禁）。"""
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

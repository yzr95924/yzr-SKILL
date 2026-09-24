#!/usr/bin/env python3
"""语言中立重复块扫描：归一化代码行后滑窗匹配，输出候选重复组（不做判定，始终退出 0）。"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

DEFAULT_EXTS = (
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".lua",
    ".m",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
)
# 整行注释 / 块注释边界行按行首前缀跳过；行尾注释不剥离（复制粘贴通常连同注释一起带走）
COMMENT_PREFIXES = ("#", "//", "*", "/*", "*/")

STR_RE = re.compile(r'"(?:[^"\\]|\\.)*"' + r"|'(?:[^'\\]|\\.)*'")
NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
ID_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


class Occurrence(NamedTuple):
    """一次出现：文件 / 起止行（1-based，含端点）。"""

    file: str
    start: int
    end: int


class Group(NamedTuple):
    """一个候选重复组：出现列表（按文件行号排序）+ 最长匹配行数。"""

    occurrences: List[Occurrence]
    lines: int


def normalize_line(text: str, fuzzy: bool) -> str:
    """折叠空白；fuzzy 模式把字符串 / 数字 / 标识符各自归一到单个非词字符。"""
    text = " ".join(text.split())
    if fuzzy:
        text = STR_RE.sub("§", text)
        text = NUM_RE.sub("¥", text)
        text = ID_RE.sub("¤", text)
    return text


def load_code_lines(path: Path, fuzzy: bool) -> List[Tuple[int, str]]:
    """读文件为 (行号, 归一化行) 序列，跳过空行与整行注释。"""
    kept: List[Tuple[int, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIXES):
            continue
        kept.append((lineno, normalize_line(raw, fuzzy)))
    return kept


def iter_code_files(paths: Sequence[str], exts: Sequence[str]) -> List[Path]:
    """显式文件不查扩展名；目录递归按扩展名过滤。"""
    found: List[Path] = []
    for p in paths:
        target = Path(p)
        if target.is_file():
            found.append(target)
        else:
            found.extend(f for f in target.rglob("*") if f.is_file() and f.suffix in exts)
    return sorted(set(found))


def _maximal_run(
    seqs: List[List[Tuple[int, str]]], p1: Tuple[int, int], p2: Tuple[int, int], min_lines: int
) -> Optional[Tuple[int, int, int, int, int]]:
    """两个窗口起点向两侧延伸出最长公共行段；同文件自比截断重叠区。"""
    (f1, i1), (f2, i2) = p1, p2
    n1, n2 = len(seqs[f1]), len(seqs[f2])
    while i1 > 0 and i2 > 0 and seqs[f1][i1 - 1][1] == seqs[f2][i2 - 1][1]:
        i1 -= 1
        i2 -= 1
    length = 0
    while i1 + length < n1 and i2 + length < n2 and seqs[f1][i1 + length][1] == seqs[f2][i2 + length][1]:
        length += 1
    if (f1, i1) > (f2, i2):
        f1, i1, f2, i2 = f2, i2, f1, i1
    if f1 == f2 and i1 + length > i2:
        length = i2 - i1
    if length < min_lines:
        return None
    return (f1, i1, f2, i2, length)


def _covers(outer: Tuple[int, int, int, int, int], inner: Tuple[int, int, int, int, int]) -> bool:
    """同一文件对的匹配段，outer 是否完整包住 inner。"""
    o1, s1, o2, s2, olen = outer
    i1, t1, i2, t2, ilen = inner
    if (o1, o2) != (i1, i2):
        return False
    return s1 <= t1 and t1 + ilen <= s1 + olen and s2 <= t2 and t2 + ilen <= s2 + olen


def _group_runs(
    keys: List[str],
    seqs: List[List[Tuple[int, str]]],
    runs: List[Tuple[int, int, int, int, int]],
) -> List[Group]:
    """互相衔接的匹配段并成组件，输出各组在各文件内的出现区间。"""
    parent: Dict[Tuple[int, int], Tuple[int, int]] = {}

    def find(x: Tuple[int, int]) -> Tuple[int, int]:
        """找根并路径减半。"""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: Tuple[int, int], b: Tuple[int, int]) -> None:
        """按根合并两个出现位置。"""
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for f1, i1, f2, i2, _ in runs:
        for pos in ((f1, i1), (f2, i2)):
            parent.setdefault(pos, pos)
        union((f1, i1), (f2, i2))

    components: Dict[Tuple[int, int], List[Tuple[int, int, int, int, int]]] = {}
    for run in runs:
        components.setdefault(find((run[0], run[1])), []).append(run)

    groups: List[Group] = []
    for group_runs in components.values():
        spans: Dict[int, List[Tuple[int, int]]] = {}
        for f1, i1, f2, i2, length in group_runs:
            spans.setdefault(f1, []).append((i1, i1 + length))
            spans.setdefault(f2, []).append((i2, i2 + length))
        occurrences: List[Occurrence] = []
        for fi, file_spans in spans.items():
            kept_spans: List[Tuple[int, int]] = []
            for s, e in sorted(file_spans, key=lambda sp: (sp[0] - sp[1], sp[0])):
                if any(ks <= s and e <= ke for ks, ke in kept_spans):
                    continue
                kept_spans.append((s, e))
            kept_spans.sort()
            merged: List[Tuple[int, int]] = []
            for s, e in kept_spans:
                if merged and s < merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))
            seq = seqs[fi]
            for s, e in merged:
                occurrences.append(Occurrence(keys[fi], seq[s][0], seq[min(e - 1, len(seq) - 1)][0]))
        if len(occurrences) < 2:
            continue
        occurrences.sort(key=lambda o: (o.file, o.start))
        groups.append(Group(occurrences, max(run[4] for run in group_runs)))
    groups.sort(key=lambda g: (g.occurrences[0].file, g.occurrences[0].start))
    return groups


def find_groups(kept: Dict[str, List[Tuple[int, str]]], min_lines: int) -> List[Group]:
    """滑窗找重复候选并合并为组；kept 为文件 -> (行号, 归一化行) 序列。"""
    keys = list(kept)
    seqs = [kept[k] for k in keys]
    windows: Dict[Tuple[str, ...], List[Tuple[int, int]]] = {}
    for fi, seq in enumerate(seqs):
        for si in range(len(seq) - min_lines + 1):
            windows.setdefault(tuple(norm for _, norm in seq[si : si + min_lines]), []).append((fi, si))
    seen = set()
    runs: List[Tuple[int, int, int, int, int]] = []
    for positions in windows.values():
        if len(positions) < 2:
            continue
        for a in range(len(positions)):
            for b in range(a + 1, len(positions)):
                run = _maximal_run(seqs, positions[a], positions[b], min_lines)
                if run is not None and run not in seen:
                    seen.add(run)
                    runs.append(run)
    maximal: List[Tuple[int, int, int, int, int]] = []
    for run in sorted(runs, key=lambda r: (-r[4], r[0], r[1], r[2], r[3])):
        if not any(_covers(k, run) for k in maximal):
            maximal.append(run)
    return _group_runs(keys, seqs, maximal)


def scan(paths: Sequence[str], exts: Sequence[str], min_lines: int, fuzzy: bool) -> Tuple[List[Path], List[Group]]:
    """扫描路径，返回 (收进扫描的文件, 重复候选组)。"""
    files = iter_code_files(paths, exts)
    kept: Dict[str, List[Tuple[int, str]]] = {}
    for f in files:
        lines = load_code_lines(f, fuzzy)
        if len(lines) >= min_lines:
            kept[str(f)] = lines
    return files, find_groups(kept, min_lines)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：打印候选组（--max-groups 截断）；始终退出 0（候选不是门禁）。"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", help="code file(s) or directory to scan")
    parser.add_argument("--min-lines", type=int, default=5, help="duplicate block size threshold (default 5)")
    parser.add_argument(
        "--fuzzy", action="store_true", help="treat blocks differing only in literals / identifiers as duplicates"
    )
    parser.add_argument(
        "--ext", default=",".join(DEFAULT_EXTS), help="comma-separated extensions used for directory scan"
    )
    parser.add_argument("--max-groups", type=int, default=50, help="cap printed groups, 0 = unlimited")
    args = parser.parse_args(argv)
    exts = tuple(e if e.startswith(".") else "." + e for e in args.ext.split(",") if e)
    files, groups = scan(args.paths, exts, args.min_lines, args.fuzzy)
    shown = groups if args.max_groups <= 0 else groups[: args.max_groups]
    for idx, g in enumerate(shown, 1):
        print(f"INFO: dup group {idx}: {len(g.occurrences)} occurrence(s), {g.lines} line(s)")
        for occ in g.occurrences:
            span = str(occ.start) if occ.start == occ.end else f"{occ.start}-{occ.end}"
            print(f"  {occ.file}:{span}")
    if len(groups) > len(shown):
        print(f"... and {len(groups) - len(shown)} more group(s)", file=sys.stderr)
    print(f"scanned: {len(files)} file(s) -> {len(groups)} group(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

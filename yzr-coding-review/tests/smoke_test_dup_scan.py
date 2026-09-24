#!/usr/bin/env python3
"""Fixture smoke test for dup_scan.

The class of bug this pins: a matcher that reports everything (noise) or
nothing (missed duplication) passes a naive "it found a dup" check. Every
fixture below has both directions, plus the behaviors the catalog relies on:
comment / blank insulation, exact vs fuzzy split, one group per region (no
per-window spam), and same-file occurrences listed separately.

Run: python3 tests/smoke_test_dup_scan.py  (from yzr-coding-review/)
Exit 0 = all green, 1 = regression.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.dup_scan import find_groups, iter_code_files, load_code_lines, normalize_line, scan  # noqa: E402

CASES: List = []

BLOCK = [
    "def calc(items):",
    "    total = 0",
    "    for it in items:",
    "        total += it.price * it.qty",
    "    tax = total * 0.1",
    "    return total + tax",
]


def expect(cond, msg="") -> None:
    """条件不成立时抛 AssertionError；显式 raise 替代 assert（python -O 不吞）。"""
    if not cond:
        raise AssertionError(msg)


def case(fn):
    CASES.append(fn)
    return fn


def build(tmp: str, files: Dict[str, str], fuzzy: bool = False, min_lines: int = 5):
    kept: Dict[str, List[Tuple[int, str]]] = {}
    for name, text in files.items():
        p = Path(tmp) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        lines = load_code_lines(p, fuzzy)
        if len(lines) >= min_lines:
            kept[str(p)] = lines
    return find_groups(kept, min_lines)


@case
def positive_exact_dup_across_files():
    with tempfile.TemporaryDirectory() as td:
        groups = build(td, {"a.py": "\n".join(BLOCK) + "\n", "b.py": "// header\n\n" + "\n".join(BLOCK) + "\nx = 1\n"})
    expect(len(groups) == 1, groups)
    expect(len(groups[0].occurrences) == 2 and groups[0].lines == 6, groups)
    expect(sorted(o.file for o in groups[0].occurrences)[0].endswith("a.py"), groups)


@case
def negative_unrelated_files():
    with tempfile.TemporaryDirectory() as td:
        groups = build(
            td, {"a.py": "x = 1\ny = 2\nz = 3\nw = 4\nv = 5\n", "b.py": "a = 9\nb = 8\nc = 7\nd = 6\ne = 5\n"}
        )
    expect(groups == [], groups)


@case
def negative_short_dup_below_min_lines():
    dup3 = "alpha = 1\nbeta = 2\ngamma = 3\n"
    with tempfile.TemporaryDirectory() as td:
        groups = build(td, {"a.py": dup3 + "only_a = 1\nonly_a2 = 2\n", "b.py": dup3 + "only_b = 1\nonly_b2 = 2\n"})
    expect(groups == [], groups)


@case
def fuzzy_renamed_and_retuned():
    a = "\n".join(BLOCK) + "\n"
    b = "def settle(rows):\n    acc = 0\n    for row in rows:\n        acc += row.cost * row.count\n    vat = acc * 0.2\n    return acc + vat\n"
    with tempfile.TemporaryDirectory() as td:
        exact = build(td, {"a.py": a, "b.py": b}, fuzzy=False)
        fuzzy = build(td, {"a.py": a, "b.py": b}, fuzzy=True)
    expect(exact == [], exact)
    expect(len(fuzzy) == 1 and len(fuzzy[0].occurrences) == 2 and fuzzy[0].lines == 6, fuzzy)


@case
def positive_comment_and_blank_insulation():
    b = "\n".join(BLOCK[:3]) + "\n# explain the tax rate\n\n" + "\n".join(BLOCK[3:]) + "\n"
    with tempfile.TemporaryDirectory() as td:
        groups = build(td, {"a.py": "\n".join(BLOCK) + "\n", "b.py": b})
    expect(len(groups) == 1 and len(groups[0].occurrences) == 2, groups)


@case
def positive_three_way_one_group():
    text = "\n".join(BLOCK) + "\n"
    with tempfile.TemporaryDirectory() as td:
        groups = build(td, {"a.py": text, "b.py": text, "c.py": text})
    expect(len(groups) == 1 and len(groups[0].occurrences) == 3, groups)


@case
def positive_self_dup_two_occurrences():
    body = "\n".join(BLOCK) + "\n"
    with tempfile.TemporaryDirectory() as td:
        groups = build(td, {"a.py": body + "separator = 1\nseparator2 = 2\n" + body})
    expect(len(groups) == 1, groups)
    occ = groups[0].occurrences
    expect(len(occ) == 2 and occ[0].file == occ[1].file and occ[0].start < occ[1].start, occ)


@case
def positive_overlapping_spans_merged():
    long7 = [f"l{i} = {i} + 1" for i in range(7)]
    short5 = long7[:5]
    with tempfile.TemporaryDirectory() as td:
        groups = build(
            td,
            {
                "f.py": "\n".join(long7) + "\nmarker_f = 1\n",
                "g.py": "\n".join(short5) + "\nmarker_g = 2\n",
                "h.py": "\n".join(long7) + "\nmarker_h = 3\n",
            },
        )
    expect(len(groups) == 1, groups)
    occ = groups[0].occurrences
    expect(len(occ) == 3, occ)  # one span per file, overlapping duplicates merged
    by_name = {o.file.rsplit("/", 1)[-1]: o for o in occ}
    expect(by_name["f.py"].start == 1 and by_name["f.py"].end == 7, occ)
    expect(by_name["h.py"].start == 1 and by_name["h.py"].end == 7, occ)
    expect(by_name["g.py"].start == 1 and by_name["g.py"].end == 5, occ)


@case
def positive_no_per_window_spam():
    block = [f"line{i} = f({i})" for i in range(12)]
    text = "\n".join(block) + "\n"
    with tempfile.TemporaryDirectory() as td:
        groups = build(td, {"a.py": text, "b.py": text})
    expect(len(groups) == 1 and groups[0].lines == 12, groups)
    expect(len(groups[0].occurrences) == 2, groups)


@case
def directory_scan_filters_by_extension():
    text = "\n".join(BLOCK) + "\n"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.md").write_text(text, encoding="utf-8")
        (Path(td) / "b.md").write_text(text, encoding="utf-8")
        expect(iter_code_files([td], (".py",)) == [], "md must not enter directory scan")
        _, groups = scan([td], (".py",), 5, False)
    expect(groups == [], groups)


@case
def explicit_file_ignores_extension():
    text = "\n".join(BLOCK) + "\n"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.txt").write_text(text, encoding="utf-8")
        (Path(td) / "b.txt").write_text(text, encoding="utf-8")
        _, groups = scan([str(Path(td) / "a.txt"), str(Path(td) / "b.txt")], (".py",), 5, False)
    expect(len(groups) == 1 and len(groups[0].occurrences) == 2, groups)


@case
def normalize_line_contract():
    expect(normalize_line("  x   =  foo(1)  ", False) == "x = foo(1)", "exact collapse")
    expect(normalize_line("total = compute(items)", True) == normalize_line("sum = derive(rows)", True), "fuzzy ids")
    expect(normalize_line('name = "a b"', True) == normalize_line("name = 'x y'", True), "fuzzy strings")


@case
def cli_contract():
    script = Path(__file__).resolve().parent.parent / "tools" / "dup_scan.py"
    text = "\n".join(BLOCK) + "\n"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text(text, encoding="utf-8")
        (Path(td) / "b.py").write_text(text, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(script), td], capture_output=True, text=True)
        expect(proc.returncode == 0, proc)  # candidates, never a gate
        expect("dup group 1" in proc.stdout and "a.py" in proc.stdout, proc.stdout)
        expect("scanned: 2 file(s)" in proc.stderr, proc.stderr)
        proc2 = subprocess.run([sys.executable, str(script), td, "--max-groups", "0"], capture_output=True, text=True)
        expect(proc2.returncode == 0, proc2)


def main() -> int:
    failures = []
    for fn in CASES:
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{fn.__name__}: {exc}")
    for name in failures:
        print("FAIL", name)
    print(f"{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

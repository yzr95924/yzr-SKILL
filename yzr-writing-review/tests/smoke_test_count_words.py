#!/usr/bin/env python3
"""count_words.py 冒烟：中文非空白字符 / 英文词数口径、目录展开、缺路径大声失败。

Run: python3 tests/smoke_test_count_words.py（cwd: skill 根）
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_ROOT / "tools" / "count_words.py"

failures = []
CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def expect(cond, msg):
    if not cond:
        failures.append(msg)


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        universal_newlines=True,
    )


@case
def cjk_chars_exclude_whitespace_and_english_words():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.md"
        f.write_text("你好 世界\n\nabc def\n", encoding="utf-8")
        proc = run(str(f))
        expect(proc.returncode == 0, proc)
        expect("chars=10" in proc.stdout and "words=4" in proc.stdout, proc.stdout)


@case
def directory_expands_to_one_line_per_file():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a.md").write_text("甲乙", encoding="utf-8")
        (d / "b.md").write_text("丙丁", encoding="utf-8")
        proc = run(str(d))
        expect(proc.returncode == 0, proc)
        expect(proc.stdout.count("chars=") == 2, proc.stdout)
        expect("a.md" in proc.stdout and "b.md" in proc.stdout, proc.stdout)


@case
def missing_path_fails_loudly():
    proc = run("/nonexistent/nope.md")
    expect(proc.returncode != 0, proc)
    expect("ERROR" in proc.stderr, proc)


def main() -> int:
    for fn in CASES:
        fn()
    print(f"{len(CASES) - len(failures)}/{len(CASES)} passed")
    for f in failures:
        print(f"FAIL: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

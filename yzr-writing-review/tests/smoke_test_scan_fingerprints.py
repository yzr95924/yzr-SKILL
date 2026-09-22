#!/usr/bin/env python3
"""Fixture smoke test for scan_fingerprints.

The class of bug this pins: an always-reporting or never-reporting scanner
passes a naive "it finds dashes" check. So every fixture below has both
directions: prose hits must produce the named finding, and code fences /
inline code / clean text must produce none. Meta-mention reporting is also
pinned in the positive direction: it is deliberate (the reviewer exempts),
not a bug to "fix" by suppression.

Run: python3 tests/smoke_test_scan_fingerprints.py  (from yzr-writing-review/)
Exit 0 = all green, 1 = regression.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scan_fingerprints import DASH, scan_text  # noqa: E402

CASES: List = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def positive_prose_hit():
    text = "先判断用户属于哪一种——再介入。\n"
    hits = scan_text(text, "a.md")
    assert len(hits) == 1 and hits[0].line == 1 and hits[0].pid == "DASH", hits


@case
def positive_multiple_on_one_line():
    text = "A——B——C\n"
    hits = scan_text(text, "a.md")
    assert len(hits) == 1 and hits[0].count == 2, hits


@case
def negative_single_em_dash_not_matched():
    text = "范围 1—10 之间。\n"
    assert scan_text(text, "a.md") == []


@case
def negative_inline_code_span():
    text = "输出格式 `LEVEL: 文件:行 证据 —— 修法` 是契约。\n"
    assert scan_text(text, "a.md") == []


@case
def negative_double_backtick_span():
    text = "示例 ``" + DASH + "`` 属字面串。\n"
    assert scan_text(text, "a.md") == []


@case
def negative_inside_fence():
    text = "```bash\ngrep foo —— bar\n```\n"
    assert scan_text(text, "a.md") == []


@case
def positive_after_fence_resumes():
    text = "```python\n# " + DASH + "\n```\n" + "正文" + DASH + "继续。\n"
    hits = scan_text(text, "a.md")
    assert len(hits) == 1 and hits[0].line == 4, hits


@case
def positive_meta_mention_reported():
    # fingerprint row talking about the symbol itself: deliberately a candidate
    text = "- **破折号" + chr(0x201C) + DASH + chr(0x201D) + "/ em-dash**：默认一律换常规标点\n"
    hits = scan_text(text, "a.md")
    assert len(hits) == 1, hits


@case
def positive_clean_text_zero():
    text = "正常句子，用逗号：冒号、括号（如这些）。\n\n另一段。\n"
    assert scan_text(text, "a.md") == []


@case
def corner_quote_positive_prose_hit():
    text = "别的入口用「按该节执行」式指针复用。\n"
    hits = scan_text(text, "a.md")
    assert len(hits) == 1 and hits[0].pid == "CORNER-QUOTE" and hits[0].count == 1, hits


@case
def corner_quote_negative_inline_code():
    text = "参数 `--tier「default」` 照抄。\n"
    assert scan_text(text, "a.md") == []


@case
def corner_quote_negative_inside_fence():
    text = "```md\n「引用块」\n```\n"
    assert scan_text(text, "a.md") == []


@case
def section_sign_positive_prose_hit():
    text = "配置细节详见 §3.2 的说明。\n"
    hits = scan_text(text, "a.md")
    assert len(hits) == 1 and hits[0].pid == "SECTION-SIGN" and hits[0].count == 1, hits


@case
def section_sign_negative_inline_code():
    text = "参数 `§3.2` 照抄。\n"
    assert scan_text(text, "a.md") == []


@case
def section_sign_negative_inside_fence():
    text = "```md\n§ 引用块\n```\n"
    assert scan_text(text, "a.md") == []


@case
def arrow_positive_prose_hit():
    text = "引入缓存 → 延迟下降。\n"
    hits = scan_text(text, "a.md")
    assert len(hits) == 1 and hits[0].pid == "ARROW" and hits[0].count == 1, hits


@case
def arrow_negative_inline_code():
    text = "写法 `现象 → 修法` 是旧格式。\n"
    assert scan_text(text, "a.md") == []


@case
def arrow_negative_inside_fence():
    text = "```md\nA → B\n```\n"
    assert scan_text(text, "a.md") == []


@case
def cli_contract():
    with tempfile.TemporaryDirectory() as td:
        md = Path(td) / "doc.md"
        md.write_text("句子" + DASH + "尾巴。\n", encoding="utf-8")
        script = Path(__file__).resolve().parent.parent / "tools" / "scan_fingerprints.py"
        for extra, check in ((["--json"], "DASH"), ([], "INFO")):
            proc = subprocess.run(
                [sys.executable, str(script), str(md)] + extra,
                capture_output=True,
                text=True,
                universal_newlines=True,
            )
            assert proc.returncode == 0, proc  # candidates, never a gate
            assert check in proc.stdout, (extra, proc.stdout)
        proc = subprocess.run([sys.executable, str(script), str(md), "--json"], capture_output=True, text=True)
        data = json.loads(proc.stdout)
        assert data[0]["file"] == str(md) and data[0]["count"] == 1, data


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

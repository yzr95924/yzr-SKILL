#!/usr/bin/env python3
"""Fixture smoke test for check_anchor_health.

Run: python3 tests/smoke_test_anchor_health.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import sys
import tempfile
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import check_anchor_health  # noqa: E402

CASES: List = []


def case(fn):
    CASES.append(fn)
    return fn


def slug(text: str) -> str:
    return check_anchor_health.slugify_heading(text)


@case
def slug_ascii_and_cjk():
    assert slug("Foo Bar") == "foo-bar"
    assert slug("Quick Start") == "quick-start"


@case
def slug_cjk_punctuation_gap_double_hyphen():
    # " / " survives punctuation-stripping as a two-space gap -> two hyphens
    assert slug("工作流 / 步骤") == "工作流--步骤"


@case
def slug_fullwidth_colon_and_parens_removed():
    assert slug("Step 4: 形态路由") == "step-4-形态路由"
    assert slug("Step 1：快照 + 源提取（按路径分支）") == "step-1快照--源提取按路径分支"


@case
def slug_backticks_stripped():
    assert slug("运行 `verify.py` 校验") == "运行-verifypy-校验"


def make_skill(files: dict) -> Path:
    root = Path(tempfile.mkdtemp(prefix="anchor-smoke-"))
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def statuses(root: Path) -> List[str]:
    *_, issues = check_anchor_health.scan_skill(root)
    return [i["status"] for i in issues]


@case
def same_file_anchor_positive_negative():
    body = "## 目标节\n\n见好 [x](#目标节) 和坏 [y](#不存在)。\n"
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    assert got.count("ANCHOR-DRIFT") == 1, got
    assert "DEAD-LINK" not in got, got


@case
def cross_file_anchor_positive_negative():
    root = make_skill(
        {
            "SKILL.md": "---\nname: s\ndescription: d\n---\n\n"
            "好 [a](references/r.md#深层节) 坏 [b](references/r.md#gone) 缺 [c](references/none.md)。\n",
            "references/r.md": "## 深层节\n",
        }
    )
    got = statuses(root)
    assert got.count("ANCHOR-DRIFT") == 1, got
    assert got.count("DEAD-LINK") == 1, got


@case
def backtick_path_resolves_from_skill_root():
    # operational ref inside a references/ file, written skill-root-relative
    root = make_skill(
        {
            "SKILL.md": "---\nname: s\ndescription: d\n---\n\nsee [r](references/r.md)\n",
            "references/r.md": "跑 `scripts/x.py`。\n",
            "scripts/x.py": "",
        }
    )
    assert statuses(root) == [], statuses(root)


@case
def backtick_path_missing_reports():
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n`scripts/gone.py`\n"})
    assert statuses(root) == ["PATH-MISSING"], statuses(root)


@case
def explicit_anchor_accepted():
    body = '<a id="stable"></a>\n\n## 任意标题\n\n[t](#stable) [u](#nope-missing)\n'
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    assert got == ["ANCHOR-DRIFT"], got  # only #nope-missing is drift


@case
def fenced_and_externals_ignored():
    body = "```\n[dead](nope.md#x)\n```\n\n[ext](https://example.com/a#b) `[code-illustration](nope2.md)`\n"
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    assert statuses(root) == [], statuses(root)


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

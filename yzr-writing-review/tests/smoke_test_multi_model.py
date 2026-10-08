#!/usr/bin/env python3
"""Fixture smoke test for multi-model review doc invariants.

The subagent-era pipeline has no build script copying files around: its SSOTs are
plain text, so drift between them is silent. Pins the roster table in
ref/multi-model.md mirrored into the eval id-3 expectations (the roster/eval
divergence really happened: an uncommitted roster edit left the script-era list
at two models while the eval demanded three), and the 评审立场 block plus the
复述 core phrase duplicated across SKILL.md / ref/reviewer.md staying identical
(reviewers read only reviewer.md, so drift ships divergent reviewer guidance).

Run: python3 tests/smoke_test_multi_model.py  (from yzr-writing-review/)
Exit 0 = all green, 1 = regression.
"""

import json
import re
import sys
from pathlib import Path
from typing import List

SKILL_ROOT = Path(__file__).resolve().parent.parent
CASES: List = []


def case(fn):
    CASES.append(fn)
    return fn


def expect(cond, msg="") -> None:
    if not cond:
        raise AssertionError(msg)


@case
def roster_table_mirrored_in_evals():
    md = (SKILL_ROOT / "ref" / "multi-model.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\|\s*([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)\s*\|$", md, re.M)
    expect(len(ids) == 3, f"roster table must list exactly 3 model IDs, got {ids}")
    evals_blob = json.dumps(
        json.loads((SKILL_ROOT / "eval" / "evals.json").read_text(encoding="utf-8")), ensure_ascii=False
    )
    for model_id in ids:
        expect(model_id in evals_blob, f"roster id {model_id} not mirrored in eval expectations")


@case
def reviewer_stance_synced_with_skill_md():
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reviewer_md = (SKILL_ROOT / "ref" / "reviewer.md").read_text(encoding="utf-8")
    for label, text in (("SKILL.md", skill_md), ("ref/reviewer.md", reviewer_md)):
        expect("- **资深架构师视角**" in text, f"stance block start missing in {label}")
        expect("不靠多轮往返补齐发现" in text, f"stance block end missing in {label}")
    start = skill_md.index("- **资深架构师视角**")
    end = skill_md.index("不靠多轮往返补齐发现", start) + len("不靠多轮往返补齐发现")
    expect(reviewer_md.count(skill_md[start:end]) == 1, "评审立场 drifted between SKILL.md and ref/reviewer.md")


@case
def reviewer_paraphrase_synced_with_skill_md():
    # 复述口径两文各有交互/存疑的尾句差异，钉住共同的核心成分防漂移
    phrase = "**在说什么**（核心主张）与**逻辑怎么走**（论证链条）"
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reviewer_md = (SKILL_ROOT / "ref" / "reviewer.md").read_text(encoding="utf-8")
    for label, text in (("SKILL.md", skill_md), ("ref/reviewer.md", reviewer_md)):
        expect("2-4 句" in text, f"{label} missing 2-4 句")
        expect(phrase in text, f"复述口径 drifted in {label}")


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

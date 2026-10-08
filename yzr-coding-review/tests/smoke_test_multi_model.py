#!/usr/bin/env python3
"""多模型评审文档不变量的夹具冒烟。

subagent 时代的编排没有构建脚本：SSOT 回到纯文本，漂移不再有任何构建期告警。钉住
ref/multi-model.md 的名单表镜像进 eval id-23 expectations（两者脱钩即静默失效），并钉住
SKILL.md / ref/reviewer.md 各自的复述口径共享核心句（评审立场已单源到 catalog.md，无双写
无需钉；评审员只读 reviewer.md，复述句漂移即发出分叉的评审指引）。

Run: python3 tests/smoke_test_multi_model.py  (from yzr-coding-review/)
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
def reviewer_paraphrase_synced_with_skill_md():
    # 复述口径两文各有交互/存疑的尾句差异，钉住共同的核心成分防漂移
    phrase = "**在做什么**（功能意图）与**怎么做到的**（结构 / 控制流）"
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

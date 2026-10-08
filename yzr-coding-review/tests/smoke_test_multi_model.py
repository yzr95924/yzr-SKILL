#!/usr/bin/env python3
"""多模型评审文档不变量的夹具冒烟。

subagent 时代的编排没有构建脚本：SSOT 回到纯文本，漂移不再有任何构建期告警。钉住
ref/multi-model.md 的名单表镜像进 eval id-23 expectations（两者脱钩即静默失效）。

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

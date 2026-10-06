#!/usr/bin/env python3
"""Fixture smoke test for build_review_packet.

The class of bug this pins: a packet builder whose manifest hash disagrees
with `sha256sum`, or whose BRIEF template drifts from what the merge step
(ref/multi-model.md) consumes, silently breaks every multi-model review. So
fixtures check: hashes match an independent hashlib run, the BRIEF stays
session-data-only (reviewer role and contract live in ref/reviewer.md, and
the BRIEF must not duplicate skill content), the default roster stays
mirrored in the eval expectations, and missing paths fail loudly.

Run: python3 tests/smoke_test_build_packet.py  (from yzr-writing-review/)
Exit 0 = all green, 1 = regression.
"""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SKILL_ROOT = Path(__file__).resolve().parent.parent
CASES: List = []


def expect(cond, msg="") -> None:
    if not cond:
        raise AssertionError(msg)


def case(fn):
    CASES.append(fn)
    return fn


def make_packet(tmp: Path, extra_args: List[str] = ()) -> subprocess.CompletedProcess:
    doc = tmp / "doc.md"
    doc.write_text("先看延迟, 再看成本——结论如下。\n", encoding="utf-8")
    ref = tmp / "ref.md"
    ref.write_text("回滚 SOP 说明。\n", encoding="utf-8")
    script = SKILL_ROOT / "tools" / "build_review_packet.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--target",
            str(doc),
            "--ref",
            str(ref),
            "--out",
            str(tmp / "packet"),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        universal_newlines=True,
    )
    return proc


@case
def packet_brief_is_session_data_only():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proc = make_packet(tmp)
        expect(proc.returncode == 0, proc.stderr)
        brief = (tmp / "packet" / "BRIEF.md").read_text(encoding="utf-8")
        for anchor in ("sha256", "被审内容清单", "参照输入", "机械扫描候选", "reviewer.md"):
            expect(anchor in brief, anchor)
        expect("WIDTH-MIX" in brief and "DASH" in brief, "scan hits must be embedded")
        for duplicated in ("## 立场", "## 输出契约", "资深架构师视角"):
            expect(duplicated not in brief, f"BRIEF must not duplicate skill content: {duplicated}")
        reviewer_md = (SKILL_ROOT / "ref" / "reviewer.md").read_text(encoding="utf-8")
        for anchor in ("sha256sum", "评审员模式", "` | `"):
            expect(anchor in reviewer_md, f"reviewer.md missing {anchor}")


@case
def manifest_hash_matches_independent_sha256():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        make_packet(tmp)
        brief = (tmp / "packet" / "BRIEF.md").read_text(encoding="utf-8")
        for name in ("doc.md", "ref.md"):
            real = hashlib.sha256((tmp / name).read_bytes()).hexdigest()[:8]
            row = re.search(rf"\| `{re.escape(str(tmp / name))}` \| ([0-9a-f]+) \|", brief)
            expect(row is not None, name)
            expect(row.group(1) == real, (name, row.group(1), real))


@case
def cli_reports_packet_and_brief_paths():
    with tempfile.TemporaryDirectory() as td:
        proc = make_packet(Path(td))
        expect("packet:" in proc.stdout and "brief:" in proc.stdout, proc.stdout)


@case
def missing_target_path_fails():
    with tempfile.TemporaryDirectory() as td:
        script = SKILL_ROOT / "tools" / "build_review_packet.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--target", str(Path(td) / "nope.md"), "--out", str(Path(td) / "p")],
            capture_output=True,
            text=True,
            universal_newlines=True,
        )
        expect(proc.returncode != 0, proc)
        expect("ERROR" in proc.stderr or "ERROR" in proc.stdout, proc)


@case
def default_roster_synced_with_evals():
    ref_md = (SKILL_ROOT / "ref" / "multi-model.md").read_text(encoding="utf-8")
    expect("## 默认名单" in ref_md, "ref must keep the 默认名单 section for this sync check")
    ids = re.findall(r"^- `(yzr-dashscope/[^`]+)`", ref_md, re.M)
    expect(len(ids) == 3, ids)
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

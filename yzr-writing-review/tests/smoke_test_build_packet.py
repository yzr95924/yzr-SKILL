#!/usr/bin/env python3
"""Fixture smoke test for build_review_packet.

The class of bug this pins: a packet whose inlined target text or contract
appendices drift from the live skill files — every reviewer would read a stale
or different volume, silently breaking every multi-model review. The
harness-subagent era's "session-data-only" pin is inverted on purpose: text-only
workers get their contract through the packet, so fixtures now pin byte-level
equality of the appended SKILL.md / reviewer.md / catalog.md against their
sources, verbatim inlining of targets and references, that the sha-fingerprint
mechanism stayed removed, and that the roster in run_multi_review.py stays
mirrored in the eval expectations.

Run: python3 tests/smoke_test_build_packet.py  (from yzr-writing-review/)
Exit 0 = all green, 1 = regression.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

SKILL_ROOT = Path(__file__).resolve().parent.parent
CASES: List = []


def expect(cond, msg="") -> None:
    if not cond:
        raise AssertionError(msg)


def case(fn):
    CASES.append(fn)
    return fn


def make_packet(tmp: Path) -> subprocess.CompletedProcess:
    doc = tmp / "doc.md"
    doc.write_text("先看延迟, 再看成本——结论如下。\n", encoding="utf-8")
    ref = tmp / "ref.md"
    ref.write_text("回滚 SOP 说明。\n", encoding="utf-8")
    script = SKILL_ROOT / "tools" / "build_review_packet.py"
    return subprocess.run(
        [sys.executable, str(script), "--target", str(doc), "--ref", str(ref), "--out", str(tmp / "packet")],
        capture_output=True,
        text=True,
        universal_newlines=True,
    )


def read_packet(tmp: Path) -> str:
    return (tmp / "packet" / "PACKET.md").read_text(encoding="utf-8")


@case
def packet_inlines_targets_and_refs_verbatim():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proc = make_packet(tmp)
        expect(proc.returncode == 0, proc.stderr)
        packet = read_packet(tmp)
        for anchor in ("被审内容清单", "参照输入", "机械扫描候选", "被审与参照全文", "契约附章"):
            expect(anchor in packet, anchor)
        expect("先看延迟, 再看成本——结论如下。" in packet, "target content must be inlined verbatim")
        expect("回滚 SOP 说明。" in packet, "reference content must be inlined verbatim")
        expect("WIDTH-MIX" in packet and "DASH" in packet, "scan hits must be embedded")


@case
def contract_appendices_match_source_files():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        make_packet(tmp)
        packet = read_packet(tmp)
        for rel in ("ref/reviewer.md", "ref/catalog.md"):
            source = (SKILL_ROOT / rel).read_text(encoding="utf-8").rstrip()
            expect(source in packet, f"appendix drift: {rel}")
            expect(f"### {rel}" in packet, f"appendix header missing: {rel}")
        expect("### SKILL.md" not in packet, "SKILL.md must not ride to text-only reviewers (command bait)")


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


@case
def fingerprint_mechanism_stays_removed():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        make_packet(tmp)
        packet = read_packet(tmp)
        expect("sha256" not in packet, "fingerprint mechanism should be gone from the packet")
        reviewer_md = (SKILL_ROOT / "ref" / "reviewer.md").read_text(encoding="utf-8")
        expect("sha256sum" not in reviewer_md, "reviewer contract must not ask for self-run hashing")
        for anchor in ("评审员契约", "` | `"):
            expect(anchor in reviewer_md, f"reviewer.md missing {anchor}")


@case
def manifest_rows_have_counts():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        make_packet(tmp)
        packet = read_packet(tmp)
        for name in ("doc.md", "ref.md"):
            row = re.search(rf"\| `{re.escape(str(tmp / name))}` \| (\d+) \| (\d+) \|", packet)
            expect(row is not None, name)


@case
def cli_reports_packet_paths():
    with tempfile.TemporaryDirectory() as td:
        proc = make_packet(Path(td))
        expect("packet:" in proc.stdout and "file:" in proc.stdout, proc.stdout)


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
    src = (SKILL_ROOT / "tools" / "run_multi_review.py").read_text(encoding="utf-8")
    match = re.search(r"DEFAULT_ROSTER = \[(.*?)\]", src, re.S)
    expect(match is not None, "run_multi_review.py must keep DEFAULT_ROSTER for this sync check")
    ids = re.findall(r'"([^"]+)"', match.group(1))
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

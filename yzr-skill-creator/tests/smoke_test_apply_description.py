#!/usr/bin/env python3
"""Round-trip smoke test for the description write-back (--apply).

The write-back is the only place in this skill where a script edits a source
file, so it is pinned from both sides: the value must come back out of the
rewritten YAML byte-for-byte once whitespace is normalised, and a rejected
candidate must leave the file exactly as it was. A corrupted block scalar is the
silent kind of failure — the skill still looks present, but its description (and
therefore its triggering) is quietly broken.

Run: python3 tests/smoke_test_apply_description.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.optimize_description import DESCRIPTION_WRAP_WIDTH, apply_description  # noqa: E402
from scripts.utils import parse_skill_md  # noqa: E402

FM_TAIL = "metadata:\n  author: smoke\n  modify time: 2026-01-01\n"
BODY = "\n# t\n\n## 输入 / 输出\n\n正文。\n"

LONG_DESCRIPTION = (
    "当用户处于 skill 生命周期时使用本 skill：从工作流 / 模板 / 流程创建新 skill、通过 eval-and-iterate 改进现有 skill、"
    "独立优化某个 skill 的触发 description、或拿写作原则审计 skill 合规性（只报告、不改写）。"
    "触发：「帮我做一个 X 的 skill」/「改进 XX 这个 skill」/「评估 / 迭代 XX skill」/「检查 XX skill 全文」；"
    "用户反馈触发不准或行为不对；想跑评估。不适用：单步问询；问 skill 机制原理；写普通代码。"
)


def make_skill(description_line: str) -> Path:
    """A throwaway skill whose frontmatter carries *description_line*."""
    root = Path(tempfile.mkdtemp(prefix="apply-smoke-")) / "s"
    root.mkdir()
    (root / "SKILL.md").write_text("---\nname: s\n" + description_line + FM_TAIL + "---" + BODY)
    return root


def apply(root: Path, description: str, dry_run: bool = False) -> int:
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer), contextlib.redirect_stdout(buffer):
        return apply_description(root, description, dry_run=dry_run)


def check_round_trip(failures):
    root = make_skill("description: |\n  旧描述。\n  折了两行。\n")
    rc = apply(root, LONG_DESCRIPTION)
    if rc != 0:
        failures.append(f"round-trip: apply returned {rc}")
        return
    _, got, content = parse_skill_md(root)
    if " ".join(LONG_DESCRIPTION.split()) != got:
        failures.append("round-trip: description came back different")
    if not content.startswith("---\nname: s\ndescription: |\n"):
        failures.append("round-trip: block-scalar style not preserved")
    if "author: smoke" not in content or "modify time: 2026-01-01" not in content:
        failures.append("round-trip: sibling frontmatter keys lost")
    if "## 输入 / 输出" not in content or "旧描述" in content:
        failures.append("round-trip: body / old value mismatch")
    for line in content.split("\n"):
        if line.startswith("  ") and len(line) > DESCRIPTION_WRAP_WIDTH + 2:
            failures.append(f"round-trip: wrapped line exceeds {DESCRIPTION_WRAP_WIDTH}+2 chars ({len(line)})")
            break
    # Second apply is a no-op.
    before = content
    rc = apply(root, LONG_DESCRIPTION)
    if rc != 0 or parse_skill_md(root)[2] != before:
        failures.append("idempotency: re-applying the same description mutated the file")


def check_from_single_line(failures):
    """A skill written with an inline description is normalised to a block."""
    root = make_skill('description: "旧的一句话。"\n')
    if apply(root, LONG_DESCRIPTION) != 0:
        failures.append("single-line source: apply failed")
        return
    if parse_skill_md(root)[1] != " ".join(LONG_DESCRIPTION.split()):
        failures.append("single-line source: value mismatch")


def check_rejections(failures):
    for label, value in (
        ("angle brackets", "触发：做 <placeholder> 的事。不适用：其它。"),
        ("over-long", "触发：a。不适用：b。" + "很长的描述" * 300),
    ):
        root = make_skill("description: |\n  原描述。触发：x。不适用：y。\n")
        before = (root / "SKILL.md").read_text()
        rc = apply(root, value)
        if rc == 0:
            failures.append(f"reject {label}: accepted an invalid description")
        if (root / "SKILL.md").read_text() != before:
            failures.append(f"reject {label}: file was modified anyway")
    # Same for dry-run: nothing is written even on the happy path.
    root = make_skill("description: |\n  原描述。触发：x。不适用：y。\n")
    before = (root / "SKILL.md").read_text()
    if apply(root, LONG_DESCRIPTION, dry_run=True) != 0:
        failures.append("dry-run: non-zero exit")
    if (root / "SKILL.md").read_text() != before:
        failures.append("dry-run: wrote the file")


def check_missing_key(failures):
    root = Path(tempfile.mkdtemp(prefix="apply-smoke-")) / "s"
    root.mkdir()
    (root / "SKILL.md").write_text("---\nname: s\n" + FM_TAIL + "---" + BODY)
    if apply(root, "触发：a。不适用：b。") == 0:
        failures.append("missing key: reported success without a description block")


def main() -> int:
    failures = []
    check_round_trip(failures)
    check_from_single_line(failures)
    check_rejections(failures)
    check_missing_key(failures)
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print("SMOKE OK: apply_description round-trip + idempotency + 3 rejection paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())

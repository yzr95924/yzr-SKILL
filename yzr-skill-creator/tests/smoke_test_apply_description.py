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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import BODY, expect, make_skill_dir, run_cases  # noqa: E402

from tools.desc_eval import DESCRIPTION_WRAP_WIDTH, apply_description  # noqa: E402
from tools.utils import parse_skill_md  # noqa: E402

FM_TAIL = "metadata:\n  author: smoke\n  modify time: 2026-01-01\n"

LONG_DESCRIPTION = (
    "当用户处于 skill 生命周期时使用本 skill：从工作流 / 模板 / 流程创建新 skill、通过 eval-and-iterate 改进现有 skill、"
    "独立优化某个 skill 的触发 description、或拿写作原则审计 skill 合规性（只报告、不改写）。"
    "触发：“帮我做一个 X 的 skill”/“改进 XX 这个 skill”/“评估 / 迭代 XX skill”/“检查 XX skill 全文”；"
    "用户反馈触发不准或行为不对；想跑评估。不适用：单步问询；问 skill 机制原理；写普通代码"
)


def make_skill(description_line: str) -> Path:
    """本测试的夹具：建一个 frontmatter 带 *description_line* 的临时 skill 目录。"""
    skill_md = "---\nname: smoke-target\n" + description_line + FM_TAIL + "---" + BODY
    return make_skill_dir({"SKILL.md": skill_md}, prefix="apply-smoke-")


def apply(root: Path, description: str, dry_run: bool = False) -> int:
    """吞掉输出跑 apply_description。"""
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer), contextlib.redirect_stdout(buffer):
        return apply_description(root, description, dry_run=dry_run)


def case_round_trip() -> None:
    root = make_skill("description: |\n  旧描述。\n  折了两行。\n")
    expect(apply(root, LONG_DESCRIPTION) == 0, "round-trip: apply failed")
    _, got, content = parse_skill_md(root)
    expect(" ".join(LONG_DESCRIPTION.split()) == got, "round-trip: description came back different")
    expect(
        content.startswith("---\nname: smoke-target\ndescription: |\n"), "round-trip: block-scalar style not preserved"
    )
    expect(
        "author: smoke" in content and "modify time: 2026-01-01" in content, "round-trip: sibling frontmatter keys lost"
    )
    expect("## 输入与输出" in content and "旧描述" not in content, "round-trip: body / old value mismatch")
    for line in content.split("\n"):
        if line.startswith("  ") and len(line) > DESCRIPTION_WRAP_WIDTH + 2:
            expect(False, f"round-trip: wrapped line exceeds {DESCRIPTION_WRAP_WIDTH}+2 chars ({len(line)})")
    # Second apply is a no-op.
    before = content
    rc = apply(root, LONG_DESCRIPTION)
    expect(
        rc == 0 and parse_skill_md(root)[2] == before, "idempotency: re-applying the same description mutated the file"
    )


def case_from_single_line() -> None:
    """A skill written with an inline description is normalised to a block."""
    root = make_skill('description: "旧的一句话。"\n')
    expect(apply(root, LONG_DESCRIPTION) == 0, "single-line source: apply failed")
    expect(parse_skill_md(root)[1] == " ".join(LONG_DESCRIPTION.split()), "single-line source: value mismatch")


def case_rejections() -> None:
    for label, value in (
        ("angle brackets", "触发：做 <placeholder> 的事。不适用：其它。"),
        ("over-long", "触发：a。不适用：b。" + "很长的描述" * 300),
        ("trailing period", "触发：a。不适用：b。"),
    ):
        root = make_skill("description: |\n  原描述。触发：x。不适用：y。\n")
        before = (root / "SKILL.md").read_text()
        expect(apply(root, value) != 0, f"reject {label}: accepted an invalid description")
        expect((root / "SKILL.md").read_text() == before, f"reject {label}: file was modified anyway")
    # Same for dry-run: nothing is written even on the happy path.
    root = make_skill("description: |\n  原描述。触发：x。不适用：y。\n")
    before = (root / "SKILL.md").read_text()
    expect(apply(root, LONG_DESCRIPTION, dry_run=True) == 0, "dry-run: non-zero exit")
    expect((root / "SKILL.md").read_text() == before, "dry-run: wrote the file")


def case_missing_key() -> None:
    root = make_skill("")
    expect(apply(root, "触发：a。不适用：b。") != 0, "missing key: reported success without a description block")


def case_multiline_no_stray_blanks() -> None:
    """已折行的多行描述写回时不得行间插空行（块标量空行是字面内容，往返失真即触发率失真）。"""
    candidate = "当用户要审文字时使用本 skill；也可编排多个模型交叉评审。\n触发：多模型 review / 交叉评审；\n不适用：翻译、代码 review"
    root = make_skill("description: |\n  旧描述。\n")
    expect(apply(root, candidate) == 0, "multiline source: apply failed")
    content = (root / "SKILL.md").read_text(encoding="utf-8")
    stray = sum(1 for line in content.split("\n") if line == "  ")
    expect(stray == 0, f"multiline source: {stray} stray blank line(s) inserted between wrapped lines")
    _, got, _ = parse_skill_md(root)
    expect(" ".join(candidate.split()) == got, "multiline source: value mismatch after round-trip")


def case_paragraph_blank_preserved() -> None:
    """真段落分隔（输入空行）写回后须保留恰好一行。"""
    candidate = "第一段内容不带换行\n\n第二段内容不带换行"
    root = make_skill("description: |\n  旧描述。\n")
    expect(apply(root, candidate) == 0, "paragraph split: apply failed")
    content = (root / "SKILL.md").read_text(encoding="utf-8")
    fm = content.split("---")[1]
    blanks = sum(1 for line in fm.split("\n") if line == "  ")
    expect(blanks == 1, f"paragraph split: expected exactly 1 blank separator, got {blanks}")


if __name__ == "__main__":
    sys.exit(run_cases())

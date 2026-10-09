"""Round-trip smoke test for the shared frontmatter reader + word estimator.

Why this exists: every script that touches a skill reads its frontmatter through
tools.utils, so a parse regression silently truncates the description fed to
the trigger judge (this happened historically with a hand-rolled parser that cut
off at a blank line inside a ``|`` block) and a bad word estimate turns into a
bogus length finding. Cases below pin the exact shapes that broke before.

Run: python3 tests/smoke_test_frontmatter.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import BODY, expect, make_skill_dir, run_cases  # noqa: E402

from tools.utils import (  # noqa: E402
    BODY_WORD_LIMIT,
    estimate_body_words,
    load_frontmatter,
    parse_skill_md,
    skill_tier,
)

# Malformed-frontmatter fixtures must raise, never return a half-parsed dict.
ERROR_CASES = (
    ("no-frontmatter", "# t\n\n正文。\n"),
    ("no-closing", "---\nname: x\ndescription: y\n# t\n"),
    ("not-a-mapping", "---\n- just\n- a\n- list\n---\n# t\n"),
)


def write_skill(fm_lines) -> Path:
    """本测试的夹具：建一个 frontmatter 为 *fm_lines* 的临时 skill 目录。"""
    text = "---\n" + "\n".join(fm_lines) + "\n---\n" + BODY
    return make_skill_dir({"SKILL.md": text}, prefix="fm-smoke-")


def cases():
    """(label, frontmatter lines, expected name, expected normalized description)."""
    return [
        (
            "single-line",
            ["name: s1", "description: 一句话场景。触发：a。不适用：b"],
            "s1",
            "一句话场景。触发：a。不适用：b",
        ),
        (
            "literal-block",
            ["name: s2", "description: |", "  场景一句，", "  折行两行。", "  触发：x"],
            "s2",
            "场景一句， 折行两行。 触发：x",
        ),
        (
            "block-with-blank-line",  # the historical truncation trap
            ["name: s3", "description: |", "  第一段。", "", "  第二段带触发：y。", "metadata:", "  author: me"],
            "s3",
            "第一段。 第二段带触发：y。",
        ),
        (
            "folded-strip",
            ["name: s4", "description: >-", "  场景。", "  触发：z。", "  不适用：w。"],
            "s4",
            "场景。 触发：z。 不适用：w。",
        ),
        (
            "double-quoted",
            ["name: s5", 'description: "场景一句。触发：q。不适用：r。"'],
            "s5",
            "场景一句。触发：q。不适用：r。",
        ),
        (
            "bare-key-implicit-plain",
            ["name: s6", "description:", "  场景一句。", "  触发：v。", "license: MIT"],
            "s6",
            "场景一句。 触发：v。",
        ),
        (
            "empty-description",
            ["name: s7", "description: "],
            "s7",
            "",
        ),
    ]


def case_parse_cases() -> None:
    for label, fm_lines, want_name, want_desc in cases():
        path = write_skill(fm_lines)
        name, description, content = parse_skill_md(path)  # a parse blow-up raises: itself the failure
        expect(name == want_name, f"parse {label}: name {name!r} != {want_name!r}")
        expect(description == want_desc, f"parse {label}: desc {description!r} != {want_desc!r}")
        expect(content.startswith("---"), f"parse {label}: full content not returned")


def case_error_cases() -> None:
    """Malformed frontmatter must raise, never return a half-parsed dict."""
    for label, text in ERROR_CASES:
        path = make_skill_dir({"SKILL.md": text}, prefix="fm-smoke-err-")
        raised = None
        try:
            parse_skill_md(path)
        except Exception as e:  # noqa: BLE001 - 区分 ValueError 与其他异常本身就是被测点
            raised = e
        expect(isinstance(raised, ValueError), f"error {label}: expected ValueError, got {raised!r}")


def run_load_frontmatter_cases() -> None:
    """load_frontmatter hands back the raw mapping — sibling keys (metadata /
    license) must survive intact, since other scripts read them from there."""
    path = write_skill(["name: k", "description: 一句话。", "metadata:", "  author: me", "  modify time: 2026-01-01"])
    data = load_frontmatter(path)
    expect(
        data.get("name") == "k" and data.get("metadata", {}).get("author") == "me",
        f"load_frontmatter: unexpected mapping {data!r}",
    )


def case_estimate_cases() -> None:
    """CJK and ASCII must be counted on their own bases.

    The naive "total chars / 1.7" formula the audit table carried reads an
    English body as ~3.5x its real word count — enough to fake a hard-limit
    violation, which is exactly what these pins prevent.
    """
    cjk = "一" * 17
    ascii_words = "one two three four five"
    fence = "```\n" + ("code word " * 200) + "\n```\n"
    checks = [
        ("cjk-17-chars", cjk, 10),
        ("ascii-5-words", ascii_words, 5),
        ("fence-excluded", fence, 0),
        ("mixed", cjk + " " + ascii_words, 15),
    ]
    for label, body, expected in checks:
        got = estimate_body_words(body)
        expect(got == expected, f"estimate {label}: {got} != {expected}")
    over = estimate_body_words("词" * 10000)
    expect(over > BODY_WORD_LIMIT, f"estimate hard-limit-over: {over} should exceed {BODY_WORD_LIMIT}")


def run_skill_tier_cases() -> None:
    """skill_tier precedence: override > metadata.tier > default; invalid falls back to default."""
    tier_cases = [
        ("override-wins", ["name: t", "description: d", "metadata:", "  tier: meta"], "reference", "reference"),
        ("metadata-read", ["name: t", "description: d", "metadata:", "  tier: meta"], None, "meta"),
        ("default-fallback", ["name: t", "description: d"], None, "default"),
        ("invalid-fallback", ["name: t", "description: d", "metadata:", "  tier: metta"], None, "default"),
    ]
    for label, fm_lines, override, want in tier_cases:
        got = skill_tier(write_skill(fm_lines), override)
        expect(got == want, f"skill_tier {label}: {got!r} != {want!r}")


if __name__ == "__main__":
    sys.exit(run_cases())

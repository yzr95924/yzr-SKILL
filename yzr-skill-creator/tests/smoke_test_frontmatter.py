#!/usr/bin/env python3
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

from _fixtures import make_skill_dir  # noqa: E402

from tools.utils import (  # noqa: E402
    BODY_WORD_LIMIT,
    estimate_body_words,
    load_frontmatter,
    parse_skill_md,
)

BODY = "\n# t\n\n## 输入与输出\n\n正文。\n"

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


def run_parse_cases(failures):
    for label, fm_lines, want_name, want_desc in cases():
        path = write_skill(fm_lines)
        try:
            name, description, content = parse_skill_md(path)
        except Exception as e:  # a parse blow-up is itself the failure
            failures.append(f"parse {label}: raised {type(e).__name__}: {e}")
            continue
        if name != want_name:
            failures.append(f"parse {label}: name {name!r} != {want_name!r}")
        if description != want_desc:
            failures.append(f"parse {label}: desc {description!r} != {want_desc!r}")
        if not content.startswith("---"):
            failures.append(f"parse {label}: full content not returned")


def run_error_cases(failures):
    """Malformed frontmatter must raise, never return a half-parsed dict."""
    for label, text in ERROR_CASES:
        path = make_skill_dir({"SKILL.md": text}, prefix="fm-smoke-err-")
        try:
            parse_skill_md(path)
            failures.append(f"error {label}: expected ValueError, got none")
        except ValueError:
            pass
        except Exception as e:
            failures.append(f"error {label}: expected ValueError, got {type(e).__name__}: {e}")


def run_load_frontmatter_cases(failures) -> None:
    """load_frontmatter hands back the raw mapping — sibling keys (metadata /
    license) must survive intact, since other scripts read them from there."""
    path = write_skill(["name: k", "description: 一句话。", "metadata:", "  author: me", "  modify time: 2026-01-01"])
    try:
        data = load_frontmatter(path)
    except Exception as e:
        failures.append(f"load_frontmatter: raised {type(e).__name__}: {e}")
        return
    if data.get("name") != "k" or data.get("metadata", {}).get("author") != "me":
        failures.append(f"load_frontmatter: unexpected mapping {data!r}")


def run_estimate_cases(failures) -> int:
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
        if got != expected:
            failures.append(f"estimate {label}: {got} != {expected}")
    over = estimate_body_words("词" * 10000)
    if over <= BODY_WORD_LIMIT:
        failures.append(f"estimate hard-limit-over: {over} should exceed {BODY_WORD_LIMIT}")
    return len(checks) + 1  # + the hard-limit-over pin


def main():
    failures = []
    run_parse_cases(failures)
    run_error_cases(failures)
    run_load_frontmatter_cases(failures)
    est_pins = run_estimate_cases(failures)
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print(
        f"SMOKE OK: frontmatter {len(cases())} shapes + {len(ERROR_CASES)} error paths"
        f" + raw mapping + {est_pins} estimator pins"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

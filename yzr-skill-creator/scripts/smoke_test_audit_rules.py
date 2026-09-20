#!/usr/bin/env python3
"""Fixture smoke test for the mechanical audit rules added to this skill.

Covers the checks that replaced hand-typed grep rows: quick_validate's
「何时不使用」 / length / TOC rules, check_anchor_health's CROSS-SKILL-PATH, and
audit_prose's two heuristic screens. Each case pins both directions — the dirty
fixture must fire the rule id, the clean fixture must stay silent — because an
audit rule that only ever reports is as useless as one that never does.

Run: python3 scripts/smoke_test_audit_rules.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import sys
import tempfile
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import audit_prose, quick_validate, verify  # noqa: E402

CLEAN_SKILL = """---
name: smoke-target
description: |
  场景一句。触发：做 X。不适用：做 Y。
---
# smoke-target

## 输入 / 输出

| 方向 | 内容 |
| --- | --- |
| 输入 | a |
| 输出 | b |

## 执行原则 / 边界

- 一条边界。

## 工作流 / 步骤

1. 做 X。
"""


_KEEP = []


def make_skill(files: Dict[str, str]) -> Path:
    """Write a throwaway skill dir from {relative path: content}."""
    tmp = tempfile.TemporaryDirectory(prefix="audit-smoke-")
    root = Path(tmp.name) / "smoke-target"
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    # Kept alive for the process lifetime; the fixtures are a few KB each.
    _KEEP.append(tmp)
    return root


def rules(findings) -> List[str]:
    return [f.rule for f in findings]


def check_when_not_section(failures: List[str]) -> None:
    dirty = make_skill(
        {"SKILL.md": CLEAN_SKILL.replace("## 输入 / 输出", "## 何时不使用\n\n不该用本 skill。\n\n## 输入 / 输出")}
    )
    clean = make_skill({"SKILL.md": CLEAN_SKILL})
    if "WHEN-NOT-SECTION" not in rules(quick_validate.check_no_when_not_section(dirty)):
        failures.append("WHEN-NOT-SECTION: dirty fixture not reported")
    if "WHEN-NOT-SECTION" in rules(quick_validate.check_no_when_not_section(clean)):
        failures.append("WHEN-NOT-SECTION: clean fixture reported")


def check_body_length(failures: List[str]) -> None:
    long_body = "字" * 9000  # ~5300 estimated words: past BODY_WORD_LIMIT
    mid_body = "字" * 3600  # ~2100 estimated words: past the default soft target only
    for label, body, tier, expect in (
        ("over-hard", long_body, "meta", "WARN"),
        ("over-soft", mid_body, "default", "WARN"),
        ("meta-exempt", mid_body, "meta", None),
        ("clean", "字" * 300, "default", None),
    ):
        skill = make_skill({"SKILL.md": CLEAN_SKILL + "\n" + body + "\n"})
        findings = [f for f in quick_validate.check_body_length(skill, tier=tier) if f.rule == "BODY-LENGTH"]
        got = findings[0].level if findings else None
        if got != expect:
            failures.append(f"BODY-LENGTH {label}: level {got!r} != {expect!r}")


def check_toc_still_works(failures: List[str]) -> None:
    body = CLEAN_SKILL + "\n## 目录\n\n- [一](#一)\n- [二](#二)\n- [三](#三)\n"
    skill = make_skill({"SKILL.md": body})
    if "HAND-TOC" not in rules(quick_validate.check_no_toc(skill)):
        failures.append("HAND-TOC: anchor-list TOC not reported")


def check_desc_format(failures: List[str]) -> None:
    both_missing = make_skill({"SKILL.md": CLEAN_SKILL.replace("触发：做 X。不适用：做 Y。", "泛泛而谈。")})
    got = rules(quick_validate.check_description_format(both_missing))
    if len(got) != 2:
        failures.append(f"DESC-FORMAT: expected 2 findings (触发 / 不适用), got {got}")
    one_missing = make_skill({"SKILL.md": CLEAN_SKILL.replace("不适用：做 Y。", "")})
    got = rules(quick_validate.check_description_format(one_missing))
    if len(got) != 1:
        failures.append(f"DESC-FORMAT: expected 1 finding, got {got}")
    if rules(quick_validate.check_description_format(make_skill({"SKILL.md": CLEAN_SKILL}))):
        failures.append("DESC-FORMAT: clean fixture reported")


def check_cross_skill_path(failures: List[str]) -> None:
    dirty = make_skill({"SKILL.md": CLEAN_SKILL + "\n见 `../../sibling/references/x.md`。\n"})
    findings = verify._anchor_findings(dirty)
    if "CROSS-SKILL-PATH" not in rules(findings):
        failures.append("CROSS-SKILL-PATH: escaping backticked path not reported")
    hit = [f for f in findings if f.rule == "CROSS-SKILL-PATH"]
    if hit and hit[0].level != "ERROR":
        failures.append("CROSS-SKILL-PATH: level is not ERROR, so it would never gate")
    # The legal forms must stay silent: a skill-root-relative path that resolves,
    # and a cross-skill *name* (topic mention, not a path).
    legit = make_skill({"SKILL.md": CLEAN_SKILL + "\n见 `references/guide.md`。\n", "references/guide.md": "# g\n"})
    if "CROSS-SKILL-PATH" in rules(verify._anchor_findings(legit)):
        failures.append("CROSS-SKILL-PATH: legit in-skill path reported")


def check_bare_metric(failures: List[str]) -> None:
    spread = CLEAN_SKILL + "\n阈值 40 行。\n"
    skill = make_skill(
        {
            "SKILL.md": spread,
            "references/a.md": "# a\n\n上限 40 行。\n",
        }
    )
    if "BARE-METRIC" not in rules(audit_prose.check_bare_metrics(skill)):
        failures.append("BARE-METRIC: same token across 2 files not reported")
    single = make_skill({"SKILL.md": spread})
    if "BARE-METRIC" in rules(audit_prose.check_bare_metrics(single)):
        failures.append("BARE-METRIC: single-file occurrence reported (should be silent)")
    quoted = make_skill(
        {
            "SKILL.md": spread,
            "references/a.md": '# a\n\n例："上限 40 行" 只是示例。\n',
        }
    )
    if "BARE-METRIC" in rules(audit_prose.check_bare_metrics(quoted)):
        failures.append("BARE-METRIC: quoted example not exempted")
    # A copy that names its authority on the same line is a declared copy, not
    # drift (the exemption is part of 「正文描述一致性」, not an ad-hoc whitelist).
    annotated = make_skill(
        {
            "SKILL.md": CLEAN_SKILL,
            "references/a.md": "# a\n\n上限 40 行(对齐 rubric)。\n",
            "references/rubric.md": "# rubric\n\n- 上限 40 行\n",  # 唯一权威源，无标注
        }
    )
    if "BARE-METRIC" in rules(audit_prose.check_bare_metrics(annotated)):
        failures.append("BARE-METRIC: 已标注出处的副本仍被报")
    unannotated_second = make_skill(
        {
            "SKILL.md": CLEAN_SKILL + "\n上限 40 行。\n",
            "references/rubric.md": "# rubric\n\n- 上限 40 行\n",
        }
    )
    if "BARE-METRIC" not in rules(audit_prose.check_bare_metrics(unannotated_second)):
        failures.append("BARE-METRIC: 第二个未标注副本被豁免漏掉")
    # Two different ranges are two different budgets, not one stray metric.
    ranges = make_skill(
        {
            "SKILL.md": CLEAN_SKILL + "\n测试集 5–40 行。\n",
            "references/a.md": "# a\n\n查询 8–40 行。\n",
        }
    )
    if "BARE-METRIC" in rules(audit_prose.check_bare_metrics(ranges)):
        failures.append("BARE-METRIC: 5–40 与 8–40 被当成同一个指标")


def check_version_history(failures: List[str]) -> None:
    skill = make_skill({"SKILL.md": CLEAN_SKILL + "\nv0.6.0 起删了旧接口。\n"})
    if "VERSION-HISTORY-INLINE" not in rules(audit_prose.check_version_history(skill)):
        failures.append("VERSION-HISTORY-INLINE: narrative not reported")
    exempt = make_skill(
        {"SKILL.md": CLEAN_SKILL + '\n例："v0.6.0 起删了旧接口" 属定义引语。\nPython ≥ 3.7 是外部约束。\n'}
    )
    if rules(audit_prose.check_version_history(exempt)):
        failures.append("VERSION-HISTORY-INLINE: quoted example / version constraint reported")


def check_clean_skill_is_quiet(failures: List[str]) -> None:
    """The reference fixture must produce no ERROR and no WARN.

    Without this direction the suite would pass even if every rule fired on
    everything.
    """
    skill = make_skill({"SKILL.md": CLEAN_SKILL, "references/guide.md": "# guide\n\n正文。\n"})
    findings = quick_validate.check_body_structure(skill) + quick_validate.check_no_when_not_section(skill)
    findings += quick_validate.check_description_format(skill) + quick_validate.check_no_toc(skill)
    findings += audit_prose.scan_skill(skill) + verify._anchor_findings(skill)
    loud = [f for f in findings if f.level in ("ERROR", "WARN")]
    if loud:
        failures.append("clean fixture produced " + "、".join(f"{f.rule}({f.level})" for f in loud))


def main() -> int:
    failures: List[str] = []
    for check in (
        check_when_not_section,
        check_body_length,
        check_toc_still_works,
        check_desc_format,
        check_cross_skill_path,
        check_bare_metric,
        check_version_history,
        check_clean_skill_is_quiet,
    ):
        check(failures)
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print("SMOKE OK: 8 rule groups, dirty + clean directions pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())

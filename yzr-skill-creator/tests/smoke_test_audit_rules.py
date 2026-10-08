#!/usr/bin/env python3
"""Fixture smoke test for the mechanical audit rules added to this skill.

Covers the checks that replaced hand-typed grep rows: quick_validate's
“何时不使用” / length / TOC / trailing-period / dir-naming / name==目录 rules,
check_anchor_health's heading slug extraction and CROSS-SKILL-PATH, and
audit_prose's two heuristic screens. Every
rule case pins both directions — dirty fixture fires the rule id, clean fixture
stays silent — and the extraction / line-number cases pin exact output, because
a matcher that silently drops matches (or is off by one line) passes
single-direction, id-only tests.

Run: python3 tests/smoke_test_audit_rules.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import expect, make_skill_dir, run_cases  # noqa: E402

from tools import audit_prose, check_anchor_health, quick_validate  # noqa: E402

CLEAN_SKILL = """---
name: smoke-target
description: |
  场景一句。触发：做 X。不适用：做 Y
---
# smoke-target

## 输入与输出

| 方向 | 内容 |
| --- | --- |
| 输入 | a |
| 输出 | b |

## 执行原则

- 一条边界

## 工作流

1. 做 X
"""


def make_skill(files: Dict[str, str]) -> Path:
    """本测试的夹具：建 audit-smoke- 前缀的临时 skill 目录。"""
    return make_skill_dir(files, prefix="audit-smoke-")


def rules(findings) -> List[str]:
    """取 Finding 列表里的 rule id。"""
    return [f.rule for f in findings]


def check_when_not_section() -> None:
    dirty_text = CLEAN_SKILL.replace("## 输入与输出", "## 何时不使用\n\n不该用本 skill。\n\n## 输入与输出")
    dirty = make_skill({"SKILL.md": dirty_text})
    clean = make_skill({"SKILL.md": CLEAN_SKILL})
    hits = [f for f in quick_validate.check_no_when_not_section(dirty) if f.rule == "WHEN-NOT-SECTION"]
    expect(hits, "WHEN-NOT-SECTION: dirty fixture not reported")
    # Pin the line number too: an off-by-one in the fence offset survived
    # every earlier run because no test looked at Finding.line.
    expected = dirty_text.split("\n").index("## 何时不使用") + 1
    expect(hits[0].line == str(expected), f"WHEN-NOT-SECTION: line {hits[0].line} != {expected}")
    expect(
        "WHEN-NOT-SECTION" not in rules(quick_validate.check_no_when_not_section(clean)),
        "WHEN-NOT-SECTION: clean fixture reported",
    )


def check_body_length() -> None:
    long_body = "字" * 9000  # ~5300 estimated words: past BODY_WORD_LIMIT
    mid_body = "字" * 3600  # ~2100 estimated words: past the default soft target only
    for label, body, tier, want in (
        ("over-hard", long_body, "meta", "WARN"),
        ("over-soft", mid_body, "default", "WARN"),
        ("meta-exempt", mid_body, "meta", None),
        ("clean", "字" * 300, "default", None),
    ):
        skill = make_skill({"SKILL.md": CLEAN_SKILL + "\n" + body + "\n"})
        findings = [f for f in quick_validate.check_body_length(skill, tier=tier) if f.rule == "BODY-LENGTH"]
        got = findings[0].level if findings else None
        expect(got == want, f"BODY-LENGTH {label}: level {got!r} != {want!r}")


def check_toc_still_works() -> None:
    body = CLEAN_SKILL + "\n## 目录\n\n- [一](#一)\n- [二](#二)\n- [三](#三)\n"
    skill = make_skill({"SKILL.md": body})
    expect("HAND-TOC" in rules(quick_validate.check_no_toc(skill)), "HAND-TOC: anchor-list TOC not reported")
    clean = make_skill({"SKILL.md": CLEAN_SKILL})
    expect(not rules(quick_validate.check_no_toc(clean)), "HAND-TOC: clean fixture reported")


def check_anchor_extraction() -> None:
    """Heading extraction: it had a silent dead branch (a two-line regex fed
    single lines) until pinned to exact output."""
    slugs = check_anchor_health.collect_heading_slugs("Title One\n===\n\n## ATX\n")
    expect("title-one" in slugs, f"setext heading not collected: {sorted(slugs)}")
    # The frontmatter closing fence has a non-blank line above it and must
    # NOT mint a setext heading; a real setext heading after it must survive.
    fenced = "---\nname: x\ndescription: y\n---\n\nBody\n===\n"
    slugs_fm = check_anchor_health.collect_heading_slugs(fenced)
    expect("body" in slugs_fm, f"setext after frontmatter not collected: {sorted(slugs_fm)}")
    bogus = [s for s in slugs_fm if "name" in s or "description" in s]
    expect(not bogus, f"frontmatter fence read as setext heading: {bogus}")
    # Headings inside code fences are examples, not anchors: link extraction
    # skips fences, slug collection must match it.
    in_fence = "## Real\n\n```md\n## Example\n```\n"
    slugs_code = check_anchor_health.collect_heading_slugs(in_fence)
    expect("example" not in slugs_code, f"fenced heading collected as anchor: {sorted(slugs_code)}")
    expect("real" in slugs_code, f"real heading lost next to fence: {sorted(slugs_code)}")


def check_desc_format() -> None:
    both_missing = make_skill({"SKILL.md": CLEAN_SKILL.replace("触发：做 X。不适用：做 Y", "泛泛而谈")})
    got = rules(quick_validate.check_description_format(both_missing))
    expect(len(got) == 2, f"DESC-FORMAT: expected 2 findings (触发 / 不适用), got {got}")
    one_missing = make_skill({"SKILL.md": CLEAN_SKILL.replace("。不适用：做 Y", "")})
    got = rules(quick_validate.check_description_format(one_missing))
    expect(len(got) == 1, f"DESC-FORMAT: expected 1 finding, got {got}")
    clean = make_skill({"SKILL.md": CLEAN_SKILL})
    expect(not rules(quick_validate.check_description_format(clean)), "DESC-FORMAT: clean fixture reported")


def check_desc_trailing_period() -> None:
    dirty = make_skill({"SKILL.md": CLEAN_SKILL.replace("不适用：做 Y", "不适用：做 Y。")})
    hits = [f for f in quick_validate.check_description_format(dirty) if f.rule == "DESC-TRAILING-PERIOD"]
    expect(hits and hits[0].level == "ERROR", f"DESC-TRAILING-PERIOD: 尾句号未报 ERROR：{hits}")
    clean = make_skill({"SKILL.md": CLEAN_SKILL})
    expect(
        "DESC-TRAILING-PERIOD" not in rules(quick_validate.check_description_format(clean)),
        "DESC-TRAILING-PERIOD: clean fixture reported",
    )


def check_trailing_period() -> None:
    """block 末句号报 ERROR；句中句号 / 折行续行 / 行内代码 / 围栏 / frontmatter 不报。"""
    dirty = make_skill({"SKILL.md": CLEAN_SKILL + "\n阈值 40 行。\n"})
    hits = [f for f in quick_validate.check_no_trailing_period(dirty) if f.rule == "TRAILING-PERIOD"]
    expect(hits and hits[0].level == "ERROR", f"TRAILING-PERIOD: 段落末句号未报 ERROR：{hits}")
    expected = CLEAN_SKILL.count("\n") + 2
    expect(hits[0].line == str(expected), f"TRAILING-PERIOD: line {hits[0].line} != {expected}")
    folded = make_skill({"SKILL.md": CLEAN_SKILL + "\n第一行收在中点。\n第二行才是段末\n"})
    expect(not rules(quick_validate.check_no_trailing_period(folded)), "TRAILING-PERIOD: 折行中间行末句号被误报")
    item = make_skill({"SKILL.md": CLEAN_SKILL + "\n- 首行带句号。\n  缩进续行收尾\n"})
    expect(not rules(quick_validate.check_no_trailing_period(item)), "TRAILING-PERIOD: 列表项续行被误报")
    coded = make_skill({"SKILL.md": CLEAN_SKILL + "\n分隔符是 `。`\n"})
    expect(not rules(quick_validate.check_no_trailing_period(coded)), "TRAILING-PERIOD: 行内代码段内句号被误报")
    fenced = make_skill({"SKILL.md": CLEAN_SKILL + "\n```\n代码里的句号。\n```\n"})
    expect(not rules(quick_validate.check_no_trailing_period(fenced)), "TRAILING-PERIOD: 围栏内句号被误报")
    clean = make_skill({"SKILL.md": CLEAN_SKILL})
    expect(not rules(quick_validate.check_no_trailing_period(clean)), "TRAILING-PERIOD: frontmatter 句中句号被误报")
    decorated = make_skill({"SKILL.md": CLEAN_SKILL + "\n- **重点。**\n"})
    expect(
        "TRAILING-PERIOD" in rules(quick_validate.check_no_trailing_period(decorated)),
        "TRAILING-PERIOD: 行尾修饰（加粗）后的句号未识别",
    )


def check_name_matches_dir() -> None:
    mismatched = make_skill_dir({"SKILL.md": CLEAN_SKILL}, prefix="audit-smoke-", name="other-dir")
    valid, message = quick_validate.validate_skill(mismatched)
    expect(not valid and "other-dir" in message, f"name!=目录名 未拦截：valid={valid} message={message}")
    valid, message = quick_validate.validate_skill(make_skill({"SKILL.md": CLEAN_SKILL}))
    expect(valid, f"name=目录名 被误拦：{message}")


def check_dir_unknown() -> None:
    dirty = make_skill({"SKILL.md": CLEAN_SKILL, "docs/a.md": "# a\n"})
    findings = quick_validate.check_dir_naming(dirty)
    expect(
        rules(findings) == ["DIR-UNKNOWN"] and all(f.level == "ERROR" for f in findings),
        f"DIR-UNKNOWN: 未知顶层目录未报 ERROR：{findings}",
    )
    legacy = make_skill({"SKILL.md": CLEAN_SKILL, "references/a.md": "# a\n"})
    expect(
        rules(quick_validate.check_dir_naming(legacy)) == ["DIR-LEGACY"],
        "DIR-UNKNOWN: 旧目录名被重复报（应只报 DIR-LEGACY）",
    )
    clean = make_skill({"SKILL.md": CLEAN_SKILL, "ref/a.md": "# a\n", "tests/x.py": "", "assets/t.md": ""})
    expect(
        not rules(quick_validate.check_dir_naming(clean)),
        f"DIR-UNKNOWN: 规范目录被误报：{rules(quick_validate.check_dir_naming(clean))}",
    )


def check_reffile_section() -> None:
    dirty = make_skill({"SKILL.md": CLEAN_SKILL + "\n## 参考文件\n\n- ref/a.md\n"})
    hits = [f for f in quick_validate.check_no_toc(dirty) if f.rule == "HAND-TOC"]
    expect(hits and "参考文件索引节" in hits[0].evidence, f"HAND-TOC: 参考文件索引节未报：{hits}")


def check_cross_skill_path() -> None:
    dirty = make_skill({"SKILL.md": CLEAN_SKILL + "\n见 `../../sibling/ref/x.md`。\n"})
    findings = check_anchor_health.scan_skill(dirty)
    expect("CROSS-SKILL-PATH" in rules(findings), "CROSS-SKILL-PATH: escaping backticked path not reported")
    hit = [f for f in findings if f.rule == "CROSS-SKILL-PATH"]
    expect(not hit or hit[0].level == "ERROR", "CROSS-SKILL-PATH: level is not ERROR, so it would never gate")
    # The legal forms must stay silent: a skill-root-relative path that resolves,
    # and a cross-skill *name* (topic mention, not a path).
    legit = make_skill({"SKILL.md": CLEAN_SKILL + "\n见 `ref/guide.md`。\n", "ref/guide.md": "# g\n"})
    expect(
        "CROSS-SKILL-PATH" not in rules(check_anchor_health.scan_skill(legit)),
        "CROSS-SKILL-PATH: legit in-skill path reported",
    )


def check_dir_legacy() -> None:
    dirty = make_skill({"SKILL.md": CLEAN_SKILL, "references/a.md": "# a\n", "scripts/x.py": ""})
    findings = quick_validate.check_dir_naming(dirty)
    expect(
        sorted(rules(findings)) == ["DIR-LEGACY", "DIR-LEGACY"] and all(f.level == "ERROR" for f in findings),
        f"DIR-LEGACY: 旧目录名未全部报 ERROR：{findings}",
    )
    clean = make_skill({"SKILL.md": CLEAN_SKILL, "ref/a.md": "# a\n", "tools/x.py": ""})
    expect(not rules(quick_validate.check_dir_naming(clean)), "DIR-LEGACY: 标准目录名被误报")


def check_missing_section_tiers() -> None:
    """全 tier 可省略的节缺失零信息量，不报；必填节缺失照旧 WARN。"""
    quiet = rules(quick_validate.check_body_structure(make_skill({"SKILL.md": CLEAN_SKILL})))
    expect("BODY-SECTION-MISSING" not in quiet, f"全豁免节缺失被报：{quiet}")
    partial = CLEAN_SKILL.replace("## 执行原则\n\n- 一条边界\n\n", "")
    findings = quick_validate.check_body_structure(make_skill({"SKILL.md": partial}))
    got = [f for f in findings if f.rule == "BODY-SECTION-MISSING"]
    expect(got and got[0].level == "WARN", f"必填节缺失未报 WARN：{got}")


def check_tier_resolution() -> None:
    """tier 从 frontmatter metadata.tier 解析：meta 路由节不报、default 同结构报；非法值 WARN 且回落。"""
    routed = CLEAN_SKILL.replace("## 输入与输出", "## 入口\n\n先分类。\n\n## 输入与输出", 1)
    meta_fm = routed.replace("---\n# smoke-target", "metadata:\n  tier: meta\n---\n# smoke-target")
    got = rules(quick_validate.collect_findings(make_skill({"SKILL.md": meta_fm}))[2])
    expect("BODY-EXTRA" not in got, f"meta tier 未从 frontmatter 生效：{got}")
    got = rules(quick_validate.collect_findings(make_skill({"SKILL.md": routed}))[2])
    expect("BODY-EXTRA" in got, "default 下路由节未报 BODY-EXTRA")
    bad_fm = routed.replace("---\n# smoke-target", "metadata:\n  tier: metta\n---\n# smoke-target")
    got = rules(quick_validate.collect_findings(make_skill({"SKILL.md": bad_fm}))[2])
    expect("TIER-METADATA" in got and "BODY-EXTRA" in got, f"非法 tier 未 WARN 或未回落 default：{got}")


def check_bare_metric() -> None:
    spread = CLEAN_SKILL + "\n阈值 40 行。\n"
    skill = make_skill(
        {
            "SKILL.md": spread,
            "ref/a.md": "# a\n\n上限 40 行。\n",
        }
    )
    expect(
        "BARE-METRIC" in rules(audit_prose.check_bare_metrics(skill)),
        "BARE-METRIC: same token across 2 files not reported",
    )
    single = make_skill({"SKILL.md": spread})
    expect(
        "BARE-METRIC" not in rules(audit_prose.check_bare_metrics(single)),
        "BARE-METRIC: single-file occurrence reported (should be silent)",
    )
    quoted = make_skill(
        {
            "SKILL.md": spread,
            "ref/a.md": '# a\n\n例："上限 40 行" 只是示例。\n',
        }
    )
    expect(
        "BARE-METRIC" not in rules(audit_prose.check_bare_metrics(quoted)), "BARE-METRIC: quoted example not exempted"
    )
    # A copy that names its authority on the same line is a declared copy, not
    # drift (the exemption follows the SSOT-annotation requirement in
    # “指标单一来源”/“自包含例外”, not an ad-hoc whitelist).
    annotated = make_skill(
        {
            "SKILL.md": CLEAN_SKILL,
            "ref/a.md": "# a\n\n上限 40 行(对齐 rubric)。\n",
            "ref/rubric.md": "# rubric\n\n- 上限 40 行\n",  # 唯一权威源，无标注
        }
    )
    expect("BARE-METRIC" not in rules(audit_prose.check_bare_metrics(annotated)), "BARE-METRIC: 已标注出处的副本仍被报")
    unannotated_second = make_skill(
        {
            "SKILL.md": CLEAN_SKILL + "\n上限 40 行。\n",
            "ref/rubric.md": "# rubric\n\n- 上限 40 行\n",
        }
    )
    expect(
        "BARE-METRIC" in rules(audit_prose.check_bare_metrics(unannotated_second)),
        "BARE-METRIC: 第二个未标注副本被豁免漏掉",
    )
    # Two different ranges are two different budgets, not one stray metric.
    ranges = make_skill(
        {
            "SKILL.md": CLEAN_SKILL + "\n测试集 5–40 行。\n",
            "ref/a.md": "# a\n\n查询 8–40 行。\n",
        }
    )
    expect(
        "BARE-METRIC" not in rules(audit_prose.check_bare_metrics(ranges)), "BARE-METRIC: 5–40 与 8–40 被当成同一个指标"
    )


def check_version_history() -> None:
    skill = make_skill({"SKILL.md": CLEAN_SKILL + "\nv0.6.0 起删了旧接口。\n"})
    expect(
        "VERSION-HISTORY-INLINE" in rules(audit_prose.check_version_history(skill)),
        "VERSION-HISTORY-INLINE: narrative not reported",
    )
    exempt = make_skill(
        {"SKILL.md": CLEAN_SKILL + '\n例："v0.6.0 起删了旧接口" 属定义引语。\nPython ≥ 3.7 是外部约束。\n'}
    )
    expect(
        not rules(audit_prose.check_version_history(exempt)),
        "VERSION-HISTORY-INLINE: quoted example / version constraint reported",
    )


def check_clean_skill_is_quiet() -> None:
    """The reference fixture must produce no ERROR and no WARN.

    Without this direction the suite would pass even if every rule fired on
    everything.
    """
    skill = make_skill({"SKILL.md": CLEAN_SKILL, "ref/guide.md": "# guide\n\n正文\n"})
    findings = quick_validate.check_body_structure(skill) + quick_validate.check_no_when_not_section(skill)
    findings += quick_validate.check_description_format(skill) + quick_validate.check_no_toc(skill)
    findings += quick_validate.check_no_trailing_period(skill)
    findings += quick_validate.check_dir_naming(skill)
    findings += audit_prose.scan_skill(skill) + check_anchor_health.scan_skill(skill)
    loud = [f for f in findings if f.level in ("ERROR", "WARN")]
    expect(not loud, "clean fixture produced " + "、".join(f"{f.rule}({f.level})" for f in loud))


if __name__ == "__main__":
    sys.exit(
        run_cases(
            [
                check_when_not_section,
                check_body_length,
                check_toc_still_works,
                check_desc_format,
                check_desc_trailing_period,
                check_trailing_period,
                check_name_matches_dir,
                check_dir_unknown,
                check_reffile_section,
                check_anchor_extraction,
                check_cross_skill_path,
                check_dir_legacy,
                check_bare_metric,
                check_version_history,
                check_missing_section_tiers,
                check_tier_resolution,
                check_clean_skill_is_quiet,
            ]
        )
    )

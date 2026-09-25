#!/usr/bin/env python3
"""Fixture smoke test for check_anchor_health.

Run: python3 tests/smoke_test_anchor_health.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_skill_dir  # noqa: E402

from tools import check_anchor_health  # noqa: E402


def make_skill(files: Dict[str, str]) -> Path:
    """本测试的夹具：建 anchor-smoke- 前缀的临时 skill 目录。"""
    return make_skill_dir(files, prefix="anchor-smoke-")


def slug(text: str) -> str:
    return check_anchor_health.slugify_heading(text)


def statuses(root: Path) -> List[str]:
    _totals, issues = check_anchor_health.scan_skill(root)
    return [i["status"] for i in issues]


def case_slug_ascii_and_cjk(failures: List[str]) -> None:
    if slug("Foo Bar") != "foo-bar":
        failures.append(f"slug ascii: {slug('Foo Bar')!r}")
    if slug("Quick Start") != "quick-start":
        failures.append(f"slug ascii 2: {slug('Quick Start')!r}")


def case_slug_cjk_punctuation_gap_double_hyphen(failures: List[str]) -> None:
    # " / " survives punctuation-stripping as a two-space gap -> two hyphens
    got = slug("工作流 / 步骤")
    if got != "工作流--步骤":
        failures.append(f"slug cjk gap: {got!r}")


def case_slug_fullwidth_colon_and_parens_removed(failures: List[str]) -> None:
    got = slug("Step 4: 形态路由")
    if got != "step-4-形态路由":
        failures.append(f"slug fullwidth colon: {got!r}")
    got = slug("Step 1：快照 + 源提取（按路径分支）")
    if got != "step-1快照--源提取按路径分支":
        failures.append(f"slug parens: {got!r}")


def case_slug_backticks_stripped(failures: List[str]) -> None:
    got = slug("运行 `verify.py` 校验")
    if got != "运行-verifypy-校验":
        failures.append(f"slug backticks: {got!r}")


def case_same_file_anchor_positive_negative(failures: List[str]) -> None:
    body = "## 目标节\n\n见好 [章节](#目标节) 和坏 [章节](#不存在)。\n"
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    if got.count("ANCHOR-DRIFT") != 1 or "DEAD-LINK" in got:
        failures.append(f"same-file anchors: {got}")


def case_cross_file_anchor_positive_negative(failures: List[str]) -> None:
    root = make_skill(
        {
            "SKILL.md": "---\nname: s\ndescription: d\n---\n\n"
            "好 [章节](ref/r.md#深层节) 坏 [章节](ref/r.md#gone) 缺 [章节](ref/none.md)。\n",
            "ref/r.md": "## 深层节\n",
        }
    )
    got = statuses(root)
    if got.count("ANCHOR-DRIFT") != 1 or got.count("DEAD-LINK") != 1:
        failures.append(f"cross-file anchors: {got}")


def case_anchor_link_label_unified(failures: List[str]) -> None:
    body = "## 目标节\n\n好 [章节](#目标节) 坏 [x](#目标节)\n"
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    if got != ["LINK-LABEL"]:
        failures.append(f"link label: {got}")


def case_backtick_path_resolves_from_skill_root(failures: List[str]) -> None:
    # operational ref inside a ref/ file, written skill-root-relative
    root = make_skill(
        {
            "SKILL.md": "---\nname: s\ndescription: d\n---\n\nsee [r](ref/r.md)\n",
            "ref/r.md": "跑 `tools/x.py`。\n",
            "tools/x.py": "",
        }
    )
    got = statuses(root)
    if got:
        failures.append(f"skill-root path: {got}")


def case_backtick_path_missing_reports(failures: List[str]) -> None:
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n`tools/gone.py`\n"})
    got = statuses(root)
    if got != ["PATH-MISSING"]:
        failures.append(f"missing path: {got}")


def case_ref_root_drift_still_reports(failures: List[str]) -> None:
    # 内容子目录（ref/assets/tools）根下的分发物路径：漂移仍必须报
    root = make_skill(
        {
            "SKILL.md": "---\nname: s\ndescription: d\n---\n\n好 `ref/r.md` 坏 `ref/gone.md`\n",
            "ref/r.md": "# r\n",
        }
    )
    got = statuses(root)
    if got != ["PATH-MISSING"]:
        failures.append(f"ref root drift: {got}")


def case_instance_paths_exempt(failures: List[str]) -> None:
    # 实例路径（首段非内容子目录）不做存在性校验：wiki/workspace 类 skill 的误报根因
    body = (
        "见 `wiki/log.md`、`scripts/SCRIPTS.md`、`concepts/x.md`、"
        "`huawei_storage_wiki/wiki/syntheses/raid-overview.md`。\n"
    )
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    if got:
        failures.append(f"instance paths: {got}")


def case_bare_filenames_exempt(failures: List[str]) -> None:
    # 裸文件名无法区分实例产物（STATS.md / index.md）与同目录引用，一律不查
    body = "产出 `STATS.md` 与 `index.md`，参考 `catalog.md`。\n"
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    if got:
        failures.append(f"bare filenames: {got}")


def case_explicit_anchor_accepted(failures: List[str]) -> None:
    body = '<a id="stable"></a>\n\n## 任意标题\n\n[章节](#stable) [章节](#nope-missing)\n'
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    if got != ["ANCHOR-DRIFT"]:  # only #nope-missing is drift
        failures.append(f"explicit anchor: {got}")


def case_fenced_and_externals_ignored(failures: List[str]) -> None:
    body = "```\n[dead](nope.md#x)\n```\n\n[ext](https://example.com/a#b) `[code-illustration](nope2.md)`\n"
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n" + body})
    got = statuses(root)
    if got:
        failures.append(f"fenced/external: {got}")


def case_yzr_prefix_exempt_for_bare_name_only(failures: List[str]) -> None:
    # 裸 `yzr-x` 是题材提及豁免；`yzr-x/y.md` 是跨 skill 路径，必须仍进检查（曾整前缀豁免留兜底空洞）
    if check_anchor_health._is_checkable_path("yzr-md-to-html"):
        failures.append("bare yzr- name should stay exempt")
    if not check_anchor_health._is_checkable_path("yzr-md-to-html/SKILL.md"):
        failures.append("yzr- prefixed path should be checkable")
    root = make_skill({"SKILL.md": "---\nname: s\ndescription: d\n---\n\n见 `yzr-md-to-html/SKILL.md`\n"})
    got = statuses(root)
    if got != ["PATH-MISSING"]:
        failures.append(f"yzr- prefixed path scan: {got}")


def main() -> int:
    failures: List[str] = []
    checks = (
        case_slug_ascii_and_cjk,
        case_slug_cjk_punctuation_gap_double_hyphen,
        case_slug_fullwidth_colon_and_parens_removed,
        case_slug_backticks_stripped,
        case_same_file_anchor_positive_negative,
        case_cross_file_anchor_positive_negative,
        case_anchor_link_label_unified,
        case_backtick_path_resolves_from_skill_root,
        case_backtick_path_missing_reports,
        case_ref_root_drift_still_reports,
        case_instance_paths_exempt,
        case_bare_filenames_exempt,
        case_explicit_anchor_accepted,
        case_fenced_and_externals_ignored,
        case_yzr_prefix_exempt_for_bare_name_only,
    )
    for check in checks:
        check(failures)
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print(f"{len(checks)}/{len(checks)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

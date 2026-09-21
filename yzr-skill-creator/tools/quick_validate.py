#!/usr/bin/env python3
"""Validate a skill's frontmatter and SKILL.md body."""

import re
import sys
from pathlib import Path

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import (  # noqa: E402
    BODY_WORD_LIMIT,
    CANONICAL_BODY_SECTIONS,
    DESCRIPTION_MAX_CHARS,
    SKILL_TIERS,
    SOFT_WORD_TARGETS,
    Finding,
    estimate_body_words,
    format_findings,
    frontmatter_span,
    load_frontmatter,
)

WHEN_NOT_SECTION_RE = re.compile(r"^##\s+何时不使用")

ALLOWED_PROPERTIES = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def normalize_heading(text):
    """归一化标题用于比较：删掉全部空白。"""
    return re.sub(r"\s+", "", text)


def _body(skill_path):
    """返回 frontmatter 之后的正文；无完整 frontmatter 时返回 None。"""
    content = (Path(skill_path) / "SKILL.md").read_text()
    span = frontmatter_span(content)
    if span is None:
        return None
    return "\n".join(content.split("\n")[span[1] + 1 :])


def _frontmatter_line_offset(skill_path):
    """返回正文起始行号（1-based），供 Finding 行号换算。"""
    span = frontmatter_span((skill_path / "SKILL.md").read_text())
    return span[1] + 1 if span else 0


def check_body_structure(skill_path, tier="default"):
    """检查正文 H2 节：缺失、顺序、额外节，返回 Finding 列表。"""
    skill_path = Path(skill_path)
    if not (skill_path / "SKILL.md").exists():
        return [Finding(rule="BODY-STRUCTURE", level="ERROR", evidence="SKILL.md not found", file="SKILL.md")]

    body = _body(skill_path)
    if body is None:
        return [
            Finding(
                rule="BODY-STRUCTURE",
                level="ERROR",
                evidence="Cannot parse frontmatter; body structure check skipped",
                file="SKILL.md",
            )
        ]

    headings = re.findall(r"^##\s+(.+)$", body, re.MULTILINE)
    found = {normalize_heading(h): h for h in headings}
    canonical = [(normalize_heading(h[3:]), h, t) for h, t in CANONICAL_BODY_SECTIONS]
    canonical_found = [norm for norm, _, _ in canonical if norm in found]
    findings = _missing_section_findings(canonical, found, tier)
    findings += _order_findings(headings, canonical, canonical_found)
    findings += _extra_section_findings(headings, tier)
    return findings


def _missing_section_findings(canonical, found, tier):
    """为缺失的规范节生成 Finding（该 tier 可省略的降为 INFO）。"""
    findings = []
    for norm, heading, exempt_tiers in canonical:
        if norm in found:
            continue
        if tier in exempt_tiers:
            findings.append(
                Finding(
                    rule="BODY-SECTION-MISSING",
                    level="INFO",
                    evidence=f"正文缺少可选节 `{heading}`（{tier} 型可省略，参考 assets/skill-template.md）",
                    file="SKILL.md",
                )
            )
        else:
            findings.append(
                Finding(
                    rule="BODY-SECTION-MISSING",
                    level="WARN",
                    evidence=f"正文缺少规范节 `{heading}`，参照 assets/skill-template.md 补齐"
                    "（节名 SSOT 在 tools/utils.py::CANONICAL_BODY_SECTIONS）",
                    file="SKILL.md",
                )
            )
    return findings


def _order_findings(headings, canonical, canonical_found):
    """检查已出现的规范节是否按 canonical 顺序排列。"""
    present_in_order = [h for h in headings if normalize_heading(h) in set(canonical_found)]
    if [normalize_heading(h) for h in present_in_order] == canonical_found:
        return []
    expected = " → ".join(f"`{h}`" for norm, h, _ in canonical if norm in set(canonical_found))
    actual = " → ".join(f"`{h}`" for h in present_in_order)
    return [
        Finding(
            rule="BODY-ORDER",
            level="WARN",
            evidence=f"规范节顺序不符：应为 {expected}，实际 {actual}",
            file="SKILL.md",
        )
    ]


def _extra_section_findings(headings, tier):
    """报告规范节之外的 H2；meta 型放行首个规范节前的路由节。"""
    canonical_norms = {normalize_heading(h[3:]) for h, _ in CANONICAL_BODY_SECTIONS}
    extras = [h for h in headings if normalize_heading(h) not in canonical_norms]
    if tier == "meta":
        # meta 型允许第一个规范节前放路由节；之后的额外节仍报（用 enumerate 而非 index()：重复节名下 index() 会取错位置）
        first_canonical_idx = next(
            (i for i, h in enumerate(headings) if normalize_heading(h) in canonical_norms),
            None,
        )
        if first_canonical_idx is not None:
            extras = [
                h
                for i, h in enumerate(headings)
                if normalize_heading(h) not in canonical_norms and i > first_canonical_idx
            ]
        else:
            extras = []
    if not extras:
        return []
    listed = "、".join(f"`{h}`" for h in extras)
    return [
        Finding(
            rule="BODY-EXTRA",
            level="INFO",
            evidence=f"额外 H2 节：{listed}"
            "，规范节之外的节应尽量收进 ref/，或按 assets/skill-template.md 注释（变体）放路由位置",
            file="SKILL.md",
        )
    ]


def check_no_when_not_section(skill_path):
    """检出已废除的 `## 何时不使用` 节。"""
    skill_path = Path(skill_path)
    body = _body(skill_path)
    if body is None:
        return []
    offset = _frontmatter_line_offset(skill_path)
    findings = []
    for index, line in enumerate(body.split("\n"), start=1):
        if not WHEN_NOT_SECTION_RE.match(line):
            continue
        findings.append(
            Finding(
                rule="WHEN-NOT-SECTION",
                level="WARN",
                evidence="正文含已废除的 `## 何时不使用` 节，selection 负例归 frontmatter description 的“不适用”槽"
                "（口径见 ../SKILL.md“执行原则”（归位 / 机械操作归脚本））",
                file="SKILL.md",
                line=str(offset + index),
            )
        )
    return findings


def check_description_format(skill_path):
    """检查 description 是否含“触发：”与“不适用：”两个标记。"""
    try:
        frontmatter = load_frontmatter(Path(skill_path))
    except (ValueError, OSError):
        return []
    description = " ".join(str(frontmatter.get("description", "") or "").split())
    if not description:
        return []

    findings = []
    for marker, label in ((re.compile(r"触发[：:]"), "触发："), (re.compile(r"不适用[：:]"), "不适用：")):
        if not marker.search(description):
            findings.append(
                Finding(
                    rule="DESC-FORMAT",
                    level="WARN",
                    evidence=f"description 缺 `{label}` 标记，固定格式（场景一句 + 触发： + 不适用：）"
                    "见 ref/description-workflow.md“description 优化原则”",
                    file="SKILL.md",
                )
            )
    return findings


def check_no_toc(skill_path):
    """扫描全部 md：手写目录节与连续页内锚点列表。"""
    skill_path = Path(skill_path)
    ssot = "ref/audit-workflow.md“判定清单”的“参考文件禁手写目录”"
    heading_re = re.compile(r"^##\s+(?:TOC|目录)\s*$")
    anchor_re = re.compile(r"^\s*[-*]\s+\[[^\]]+\]\(#")
    findings = []

    def flag(rel, line_no, text):
        """构造一条 HAND-TOC Finding。"""
        return Finding(rule="HAND-TOC", level="WARN", evidence=text, file=rel, line=str(line_no))

    for md_file in sorted(skill_path.rglob("*.md")):
        rel = str(md_file.relative_to(skill_path))
        run_start = None
        run_len = 0
        for lineno, line in enumerate(md_file.read_text().splitlines(), start=1):
            if heading_re.match(line):
                findings.append(flag(rel, lineno, f"手写目录节 `{line.strip()}`，{ssot}"))
            if anchor_re.match(line):
                if run_start is None:
                    run_start = lineno
                run_len += 1
            elif run_len:
                if run_len >= 3:
                    findings.append(flag(rel, run_start, f"疑似手写目录（{run_len} 行连续页内锚点列表），{ssot}"))
                run_start = None
                run_len = 0
        if run_len >= 3:
            findings.append(flag(rel, run_start, f"疑似手写目录（{run_len} 行连续页内锚点列表），{ssot}"))
    return findings


def check_body_length(skill_path, tier="default"):
    """正文词数超软目标或硬上限时报 Finding。"""
    body = _body(skill_path)
    if body is None:
        return []
    words = estimate_body_words(body)
    soft = SOFT_WORD_TARGETS.get(tier)
    if words > BODY_WORD_LIMIT:
        return [
            Finding(
                rule="BODY-LENGTH",
                level="WARN",
                evidence=f"正文约 {words} 词（CJK/1.7 + ASCII token 估算），超硬上限 {BODY_WORD_LIMIT}"
                "，按 ../SKILL.md“执行原则”（归位）查根因再抽层",
                file="SKILL.md",
            )
        ]
    if soft is not None and words > soft:
        return [
            Finding(
                rule="BODY-LENGTH",
                level="WARN",
                evidence=f"正文约 {words} 词（估算），超 {tier} 型软目标 {soft}，按“正文超长根因诊断”"
                "查根因处置（重抄→删重留指针 / 未下放→抽 ref/；软目标不取代硬上限，仅供参考）",
                file="SKILL.md",
            )
        ]
    return []


def _check_name(frontmatter):
    """校验 name 字段，返回错误描述或 None。"""
    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if not name:
        return "Name must not be empty"
    if not re.match(r"^[a-z0-9-]+$", name):
        return f"Name '{name}' should be kebab-case (lowercase letters, digits, and hyphens only)"
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
    if len(name) > 64:
        return f"Name is too long ({len(name)} characters). Maximum is 64 characters."
    return None


def _check_description(frontmatter):
    """校验 description 字段（类型、尖括号、长度），返回错误描述或 None。"""
    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if not description:
        return None
    if "<" in description or ">" in description:
        return "Description cannot contain angle brackets (< or >)"
    if len(description) > DESCRIPTION_MAX_CHARS:
        return (
            f"Description is too long ({len(description)} characters). Maximum is {DESCRIPTION_MAX_CHARS} characters."
        )
    return None


def _check_compatibility(frontmatter):
    """校验 compatibility 字段（类型、长度），返回错误描述或 None。"""
    compatibility = frontmatter.get("compatibility", "")
    if not compatibility:
        return None
    if not isinstance(compatibility, str):
        return f"Compatibility must be a string, got {type(compatibility).__name__}"
    if len(compatibility) > 500:
        return f"Compatibility is too long ({len(compatibility)} characters). Maximum is 500 characters."
    return None


def validate_skill(skill_path):
    """校验 frontmatter，返回 (是否通过, 消息)。"""
    skill_path = Path(skill_path)

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    try:
        frontmatter = load_frontmatter(skill_path)
    except OSError as e:
        return False, f"Cannot read SKILL.md: {e}"
    except ValueError as e:
        return False, str(e)

    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            f"Allowed properties are: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    for check in (_check_name, _check_description, _check_compatibility):
        error = check(frontmatter)
        if error:
            return False, error
    return True, "Skill is valid!"


def _collect_findings(skill_dir, tier):
    """汇总一个 skill 的全部结构类 Finding。"""
    valid, message = validate_skill(skill_dir)
    if not valid:
        return valid, message, [Finding(rule="FRONTMATTER", level="ERROR", evidence=message, file="SKILL.md")]
    findings = check_body_structure(skill_dir, tier=tier)
    findings += check_no_when_not_section(skill_dir)
    findings += check_description_format(skill_dir)
    findings += check_no_toc(skill_dir)
    findings += check_body_length(skill_dir, tier=tier)
    return valid, message, findings


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Validate a skill's frontmatter, body structure, description format, TOC ban, and length"
    )
    parser.add_argument("skill_dir", help="Path to the skill directory")
    parser.add_argument(
        "--tier",
        choices=SKILL_TIERS,
        default="default",
        help="Skill tier for the body-structure and length checks (default: %(default)s)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human-readable lines")
    args = parser.parse_args()

    valid, message, findings = _collect_findings(args.skill_dir, args.tier)

    if args.json:
        print(
            json.dumps(
                {
                    "skill_dir": str(args.skill_dir),
                    "tier": args.tier,
                    "valid": valid,
                    "message": message,
                    "findings": [f.to_dict() for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(message)
        for line in format_findings(findings):
            print(line)

    has_error = any(f.level == "ERROR" for f in findings)
    sys.exit(0 if valid and not has_error else 1)

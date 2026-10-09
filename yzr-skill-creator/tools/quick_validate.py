#!/usr/bin/env python3
"""Validate a skill's frontmatter, directory naming, body structure, and bundled eval set."""

import json
import re
import sys
from pathlib import Path

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import (  # noqa: E402
    BODY_WORD_LIMIT,
    CANONICAL_BODY_SECTIONS,
    DESCRIPTION_MAX_CHARS,
    ERROR,
    INFO,
    KEBAB_NAME_RE,
    SKILL_SUBDIRS,
    SKILL_TIERS,
    SOFT_WORD_TARGETS,
    WARN,
    Finding,
    estimate_body_words,
    format_findings,
    frontmatter_span,
    h2_headings,
    iter_skill_texts,
    iter_unfenced_lines,
    json_text,
    load_frontmatter,
    parse_skill_md,
    skill_tier,
)

ALLOWED_PROPERTIES = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}

# frontmatter 字段硬上限（数值口径归这里，消息用 f-string 引用）
NAME_MAX_CHARS = 64
COMPATIBILITY_MAX_CHARS = 500


def normalize_heading(text):
    """归一化标题用于比较：删掉全部空白。"""
    return re.sub(r"\s+", "", text)


def _body(skill_path):
    """返回 (frontmatter 之后的正文, 正文起始行号 1-based)；无完整 frontmatter 时返回 (None, 0)。"""
    content = (Path(skill_path) / "SKILL.md").read_text(encoding="utf-8")
    span = frontmatter_span(content)
    if span is None:
        return None, 0
    return "\n".join(content.split("\n")[span[1] + 1 :]), span[1] + 1


def check_body_structure(skill_path, tier="default"):
    skill_path = Path(skill_path)
    if not (skill_path / "SKILL.md").exists():
        return [Finding(rule="BODY-STRUCTURE", level=ERROR, evidence="SKILL.md not found", file="SKILL.md")]

    body, _offset = _body(skill_path)
    if body is None:
        return [
            Finding(
                rule="BODY-STRUCTURE",
                level=ERROR,
                evidence="Cannot parse frontmatter; body structure check skipped",
                file="SKILL.md",
            )
        ]

    headings = h2_headings(body)
    found = {normalize_heading(h): h for h in headings}
    canonical = [(normalize_heading(h), f"## {h}", t) for h, t in CANONICAL_BODY_SECTIONS]
    canonical_found = [norm for norm, _, _ in canonical if norm in found]
    findings = _missing_section_findings(canonical, found, tier)
    findings += _order_findings(headings, canonical, canonical_found)
    findings += _extra_section_findings(headings, tier)
    return findings


def _missing_section_findings(canonical, found, tier):
    """为缺失的规范节生成 Finding（该 tier 可省略的降为 INFO；全 tier 可省略的不报）。"""
    findings = []
    for norm, heading, exempt_tiers in canonical:
        if norm in found:
            continue
        if exempt_tiers >= set(SKILL_TIERS):
            continue
        if tier in exempt_tiers:
            findings.append(
                Finding(
                    rule="BODY-SECTION-MISSING",
                    level=INFO,
                    evidence=f"正文缺少可选节 `{heading}`（{tier} 型可省略，参考 assets/skill-template.md）",
                    file="SKILL.md",
                )
            )
        else:
            findings.append(
                Finding(
                    rule="BODY-SECTION-MISSING",
                    level=WARN,
                    evidence=f"正文缺少规范节 `{heading}`，参照 assets/skill-template.md 补齐",
                    file="SKILL.md",
                )
            )
    return findings


def _order_findings(headings, canonical, canonical_found):
    present_in_order = [h for h in headings if normalize_heading(h) in set(canonical_found)]
    if [normalize_heading(h) for h in present_in_order] == canonical_found:
        return []
    expected = " → ".join(f"`{h}`" for norm, h, _ in canonical if norm in set(canonical_found))
    actual = " → ".join(f"`{h}`" for h in present_in_order)
    return [
        Finding(
            rule="BODY-ORDER",
            level=WARN,
            evidence=f"规范节顺序不符：应为 {expected}，实际 {actual}",
            file="SKILL.md",
        )
    ]


def _extra_section_findings(headings, tier):
    """报告规范节之外的 H2；meta 型放行首个规范节前的路由节。"""
    canonical_norms = {normalize_heading(h) for h, _ in CANONICAL_BODY_SECTIONS}
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
            level=INFO,
            evidence=f"额外 H2 节：{listed}"
            "，规范节之外的节应尽量收进 ref/，或按 assets/skill-template.md 注释（变体）放路由位置",
            file="SKILL.md",
        )
    ]


def check_description_format(skill_path):
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
                    level=WARN,
                    evidence=f"description 缺 `{label}` 标记，固定格式（场景一句 + 触发： + 不适用：）"
                    "见 ref/description-workflow.md“description 优化原则”",
                    file="SKILL.md",
                )
            )
    if description.endswith("。"):
        findings.append(
            Finding(
                rule="DESC-TRAILING-PERIOD",
                level=ERROR,
                evidence="description 以「。」收尾",
                file="SKILL.md",
                fix="删去末尾句号（与正文 block 末统一不加句号）",
            )
        )
    return findings


def check_no_toc(skill_path):
    skill_path = Path(skill_path)
    ssot = "agent 全量读入参考文件，手写目录只喂上下文"
    heading_re = re.compile(r"^##\s+(?:TOC|目录|参考文件)\s*$")
    anchor_re = re.compile(r"^\s*[-*]\s+\[[^\]]+\]\(#")
    findings = []

    def flag(rel, line_no, text):
        return Finding(rule="HAND-TOC", level=WARN, evidence=text, file=rel, line=str(line_no))

    def run_finding(rel, run_start, run_len):
        """连续 ≥ 3 行页内锚点列表按疑似手写目录报告，否则 None。"""
        if run_len < 3:
            return None
        return flag(rel, run_start, f"疑似手写目录（{run_len} 行连续页内锚点列表），{ssot}")

    for _md, rel, text in iter_skill_texts(skill_path, "toc"):
        run_start = None
        run_len = 0
        for lineno, line in iter_unfenced_lines(text):
            if heading_re.match(line):
                label = "参考文件索引节" if "参考文件" in line else "手写目录节"
                findings.append(flag(rel, lineno, f"{label} `{line.strip()}`，{ssot}"))
            if anchor_re.match(line):
                if run_start is None:
                    run_start = lineno
                run_len += 1
            elif run_len:
                finding = run_finding(rel, run_start, run_len)
                if finding:
                    findings.append(finding)
                run_start = None
                run_len = 0
        finding = run_finding(rel, run_start, run_len)
        if finding:
            findings.append(finding)
    return findings


def check_body_length(skill_path, tier="default"):
    body, _offset = _body(skill_path)
    if body is None:
        return []
    words = estimate_body_words(body)
    soft = SOFT_WORD_TARGETS.get(tier)
    if words > BODY_WORD_LIMIT:
        return [
            Finding(
                rule="BODY-LENGTH",
                level=WARN,
                evidence=f"正文约 {words} 词（估算），超硬上限 {BODY_WORD_LIMIT}"
                "，按 SKILL.md“执行原则”（归位）查根因再抽层",
                file="SKILL.md",
            )
        ]
    if soft is not None and words > soft:
        return [
            Finding(
                rule="BODY-LENGTH",
                level=WARN,
                evidence=f"正文约 {words} 词（估算），超 {tier} 型软目标 {soft}，按 SKILL.md“执行原则”（归位）"
                "查根因处置（重抄→删重留指针 / 未下放→抽 ref/；软目标仅供参考，不取代硬上限）",
                file="SKILL.md",
            )
        ]
    return []


def check_evals_json(skill_path):
    """eval/evals.json 骨架检查（存在才查）：可解析、skill_name 与 frontmatter 一致、声明的输入文件存在。"""
    skill_path = Path(skill_path)
    path = skill_path / "eval" / "evals.json"
    if not path.is_file():
        return []
    where = "eval/evals.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [Finding(rule="EVALS-JSON", level=ERROR, evidence=f"无法解析：{e}", file=where)]
    if not isinstance(data, dict) or not isinstance(data.get("evals"), list) or not data["evals"]:
        return [
            Finding(
                rule="EVALS-JSON",
                level=ERROR,
                evidence="须为含非空 `evals` 数组的 JSON 对象",
                file=where,
            )
        ]
    findings = []
    try:
        name = parse_skill_md(skill_path)[0]
    except (ValueError, OSError):
        name = ""
    if name and data.get("skill_name") != name:
        findings.append(
            Finding(
                rule="EVALS-JSON",
                level=ERROR,
                evidence=f"skill_name={data.get('skill_name')!r} 与 frontmatter name={name!r} 不符",
                file=where,
                fix="改名要同步评估集，否则测试 prompt 与产出对不上",
            )
        )
    for item in data["evals"]:
        if not isinstance(item, dict):
            continue
        for rel in item.get("files") or []:
            if (skill_path / str(rel)).exists():
                continue
            findings.append(
                Finding(
                    rule="EVALS-INPUT-MISSING",
                    level=ERROR,
                    evidence=f"声明的输入文件不存在：{rel}",
                    file=where,
                    line=str(item.get("id", "")),
                    fix="补文件 / 改相对路径，或从 files 里删掉",
                )
            )
    return findings


def _check_name(frontmatter):
    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if not name:
        return "Name must not be empty"
    if not KEBAB_NAME_RE.match(name):
        return f"Name '{name}' should be kebab-case (lowercase letters, digits, and hyphens only)"
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
    if len(name) > NAME_MAX_CHARS:
        return f"Name is too long ({len(name)} characters). Maximum is {NAME_MAX_CHARS} characters."
    return None


def _check_description(frontmatter):
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
    compatibility = frontmatter.get("compatibility", "")
    if not compatibility:
        return None
    if not isinstance(compatibility, str):
        return f"Compatibility must be a string, got {type(compatibility).__name__}"
    if len(compatibility) > COMPATIBILITY_MAX_CHARS:
        return (
            f"Compatibility is too long ({len(compatibility)} characters). "
            f"Maximum is {COMPATIBILITY_MAX_CHARS} characters."
        )
    return None


def validate_skill(skill_path):
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
    name = str(frontmatter.get("name", "")).strip()
    if name != skill_path.name:
        return False, f"Name '{name}' must match the skill directory name '{skill_path.name}'"
    return True, "Skill is valid!"


def check_tier_metadata(skill_path):
    """metadata.tier 存在但非法时报 WARN（将回落 default，防 typo 静默）。"""
    try:
        metadata = load_frontmatter(Path(skill_path)).get("metadata") or {}
    except (ValueError, OSError):
        return []
    if not isinstance(metadata, dict):
        return []
    tier = metadata.get("tier")
    if tier is None or tier in SKILL_TIERS:
        return []
    return [
        Finding(
            rule="TIER-METADATA",
            level=WARN,
            evidence=f"metadata.tier={tier!r} 不在 {SKILL_TIERS}，已回落 default",
            file="SKILL.md",
            fix="改成合法 tier 或删掉该键",
        )
    ]


def check_dir_naming(skill_path):
    skill_path = Path(skill_path)
    findings = []
    for child in sorted(skill_path.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name == "node_modules":
            continue
        if child.name in SKILL_SUBDIRS:
            continue
        findings.append(
            Finding(
                rule="DIR-UNKNOWN",
                level=ERROR,
                evidence=f"目录 `{child.name}/` 不在规范子目录（{'、'.join(SKILL_SUBDIRS)}）中",
                file=f"{child.name}/",
                fix="改用规范子目录或移出 skill 目录",
            )
        )
    return findings


def collect_findings(skill_dir, tier=None):
    """汇总一个 skill 的全部结构类 Finding（tier=None = 读 frontmatter metadata.tier，缺省 default）；frontmatter 坏时仅此一条 FRONTMATTER ERROR。"""
    valid, message = validate_skill(skill_dir)
    if not valid:
        return [Finding(rule="FRONTMATTER", level=ERROR, evidence=message, file="SKILL.md")]
    resolved = skill_tier(Path(skill_dir), tier)
    findings = check_tier_metadata(skill_dir)
    findings += check_dir_naming(skill_dir)
    findings += check_body_structure(skill_dir, tier=resolved)
    findings += check_description_format(skill_dir)
    findings += check_no_toc(skill_dir)
    findings += check_body_length(skill_dir, tier=resolved)
    findings += check_evals_json(skill_dir)
    return findings


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate a skill's frontmatter, directory naming, body structure, description format, TOC ban, length, and eval set skeleton"
    )
    parser.add_argument("skill_dir", help="Path to the skill directory")
    parser.add_argument(
        "--tier",
        choices=SKILL_TIERS,
        default=None,
        help="Override the skill's frontmatter metadata.tier (default: read from SKILL.md, fallback 'default')",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human-readable lines")
    args = parser.parse_args(argv=None)

    findings = collect_findings(args.skill_dir, args.tier)
    fatal = next((f for f in findings if f.rule == "FRONTMATTER"), None)
    valid = fatal is None
    message = fatal.evidence if fatal else "Skill is valid!"

    if args.json:
        print(
            json_text(
                {
                    "skill_dir": str(args.skill_dir),
                    "tier": skill_tier(Path(args.skill_dir), args.tier),
                    "valid": valid,
                    "message": message,
                    "findings": [f.to_dict() for f in findings],
                }
            )
        )
    else:
        print(message)
        for line in format_findings(findings):
            print(line)

    has_error = any(f.level == ERROR for f in findings)
    sys.exit(0 if valid and not has_error else 1)

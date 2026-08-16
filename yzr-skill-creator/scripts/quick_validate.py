#!/usr/bin/env python3
"""
Quick validation script for skills - minimal version
"""

import re
import sys
from pathlib import Path

# Bootstrap sys.path so `from scripts.X import Y` works under both
# `python3 scripts/quick_validate.py` (standalone) and
# `python3 -m scripts.quick_validate` (from yzr-skill-creator/). Resolves B1.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from scripts.utils import CANONICAL_BODY_SECTIONS, DESCRIPTION_MAX_CHARS, SKILL_TIERS, parse_skill_md


def normalize_heading(text):
    """Normalize a heading for comparison: strip all whitespace so
    `执行原则 / 边界` == `执行原则/边界` == `执行原则  /  边界`."""
    return re.sub(r"\s+", "", text)


def check_body_structure(skill_path, tier="default"):
    """Check SKILL.md body against CANONICAL_BODY_SECTIONS (utils.py).

    WARN-level only — never blocks (frontmatter failures do). Returns a list of
    (level, message) findings: missing required sections / out-of-order canonical
    sections are WARN; sections the given tier may omit and extra H2 sections
    are INFO.
    """
    skill_path = Path(skill_path)
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return [("ERROR", "SKILL.md not found")]

    content = skill_md.read_text()
    match = re.match(r"^---\n.*?\n---\n(.*)$", content, re.DOTALL)
    if not match:
        return [("ERROR", "Cannot parse frontmatter; body structure check skipped")]

    body = match.group(1)
    headings = re.findall(r"^##\s+(.+)$", body, re.MULTILINE)
    found = {normalize_heading(h): h for h in headings}

    # Canonical entries carry the "## " prefix; normalize to bare heading text
    # so both sides compare on the same basis.
    canonical = [(normalize_heading(h[3:]), h, t) for h, t in CANONICAL_BODY_SECTIONS]

    findings = []
    canonical_found = []
    for norm, heading, exempt_tiers in canonical:
        if norm in found:
            canonical_found.append(norm)
            continue
        if tier in exempt_tiers:
            findings.append(
                (
                    "INFO",
                    f"正文缺少可选节 `{heading}`（{tier} 型可省略，参考 assets/skill-template.md）",
                )
            )
        else:
            findings.append(
                (
                    "WARN",
                    f"正文缺少规范节 `{heading}`——参照 assets/skill-template.md 补齐（节名 SSOT 在 scripts/utils.py::CANONICAL_BODY_SECTIONS）",
                )
            )

    present_in_order = [h for h in headings if normalize_heading(h) in set(canonical_found)]
    if [normalize_heading(h) for h in present_in_order] != canonical_found:
        expected = " → ".join(f"`{h}`" for norm, h, _ in canonical if norm in set(canonical_found))
        actual = " → ".join(f"`{h}`" for h in present_in_order)
        findings.append(("WARN", f"规范节顺序不符——应为 {expected}，实际 {actual}"))

    canonical_norms = {norm for norm, _, _ in canonical}
    extras = [h for h in headings if normalize_heading(h) not in canonical_norms]
    if extras:
        findings.append(
            (
                "INFO",
                "额外 H2 节："
                + "、".join(f"`{h}`" for h in extras)
                + "——规范节之外的节应尽量收进 references/，或按 skill-template-guide.md「变体」放路由位置",
            )
        )

    return findings


def check_description_format(skill_path):
    """Check description for the fixed 3-component format markers (WARN-only).

    硬性约定 SSOT 在 references/skill-writing-principles.md「description 优化原则」
    （固定格式）：场景一句（中文 lead）+ 触发： + 不适用：，槽内措辞自由。
    WARN 不 fail——描述触发准确性由 run_loop 优化，这里只防结构漂移。
    """
    try:
        _, description, _ = parse_skill_md(Path(skill_path))
    except (ValueError, OSError):
        return []

    findings = []
    for marker, label in ((re.compile(r"触发[：:]"), "触发："), (re.compile(r"不适用[：:]"), "不适用：")):
        if not marker.search(description):
            findings.append(
                (
                    "WARN",
                    f"description 缺 `{label}` 标记——固定格式（场景一句 + 触发： + 不适用：）"
                    "见 references/skill-writing-principles.md「description 优化原则」",
                )
            )
    return findings


def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    content = skill_md.read_text()
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"

    # Extract frontmatter
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}"

    # Define allowed properties
    ALLOWED_PROPERTIES = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            f"Allowed properties are: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    # Check required fields
    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    # Extract name for validation
    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        # Check naming convention (kebab-case: lowercase with hyphens)
        if not re.match(r"^[a-z0-9-]+$", name):
            return False, f"Name '{name}' should be kebab-case (lowercase letters, digits, and hyphens only)"
        if name.startswith("-") or name.endswith("-") or "--" in name:
            return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
        # Check name length (max 64 characters per spec)
        if len(name) > 64:
            return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters."

    # Extract and validate description
    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        # Check for angle brackets
        if "<" in description or ">" in description:
            return False, "Description cannot contain angle brackets (< or >)"
        # Check description length (limit defined once in utils.DESCRIPTION_MAX_CHARS)
        if len(description) > DESCRIPTION_MAX_CHARS:
            return (
                False,
                f"Description is too long ({len(description)} characters). Maximum is {DESCRIPTION_MAX_CHARS} characters.",
            )

    # Validate compatibility field if present (optional)
    compatibility = frontmatter.get("compatibility", "")
    if compatibility:
        if not isinstance(compatibility, str):
            return False, f"Compatibility must be a string, got {type(compatibility).__name__}"
        if len(compatibility) > 500:
            return False, f"Compatibility is too long ({len(compatibility)} characters). Maximum is 500 characters."

    return True, "Skill is valid!"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate a skill's frontmatter and body structure")
    parser.add_argument("skill_dir", help="Path to the skill directory")
    parser.add_argument(
        "--tier",
        choices=SKILL_TIERS,
        default="default",
        help="Skill tier for the body-structure check (default: %(default)s)",
    )
    args = parser.parse_args()

    valid, message = validate_skill(args.skill_dir)
    print(message)

    findings = check_body_structure(args.skill_dir, tier=args.tier)
    findings += check_description_format(args.skill_dir)
    for level, msg in findings:
        print(f"{level}: {msg}")

    has_error = any(level == "ERROR" for level, _ in findings)
    sys.exit(0 if valid and not has_error else 1)

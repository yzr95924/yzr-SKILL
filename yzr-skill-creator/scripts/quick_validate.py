#!/usr/bin/env python3
"""
Quick validation script for skills - minimal version

Checks a skill directory's SKILL.md for: frontmatter legality, canonical body
structure, description format markers, hand-written TOC ban, the retired
「何时不使用」 section, and body length. Frontmatter problems and an
unparseable body are ERROR (they block); the rest are WARN / INFO advisories
that never fail the run — this is a drift tripwire, not a gate on judgement
calls.

Output: human lines ``LEVEL: file:line  evidence —— fix`` (stable format; prose
quotes the messages), or ``--json`` for machine use.
"""

import re
import sys
from pathlib import Path

# Bootstrap sys.path so `from scripts.X import Y` works under both
# `python3 scripts/quick_validate.py` (standalone) and
# `python3 -m scripts.quick_validate` (from yzr-skill-creator/). Resolves B1.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import (  # noqa: E402
    BODY_WORD_LIMIT,
    CANONICAL_BODY_SECTIONS,
    DESCRIPTION_MAX_CHARS,
    SKILL_TIERS,
    SOFT_WORD_TARGETS,
    Finding,
    estimate_body_words,
    format_findings,
    load_frontmatter,
)

# Selection-layer negatives belong in the frontmatter description's 「不适用」 slot
# (references/skill-writing-principles.md「结构与加载」); a body section saying the
# same thing is a second copy that silently rots after the next description edit.
WHEN_NOT_SECTION_RE = re.compile(r"^##\s+何时不使用")


def normalize_heading(text):
    """Normalize a heading for comparison: strip all whitespace so
    `执行原则 / 边界` == `执行原则/边界` == `执行原则  /  边界`."""
    return re.sub(r"\s+", "", text)


def _body(skill_path):
    """Return the SKILL.md body (frontmatter stripped), or None if unparseable.

    Fence tolerance deliberately matches utils.load_frontmatter
    (``line.strip() == "---"``): a closing fence with trailing whitespace is
    legal frontmatter, and the two readers disagreeing once made
    validate_skill pass while check_body_structure errored on the same file.
    """
    lines = (Path(skill_path) / "SKILL.md").read_text().split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1 :])
    return None


def _frontmatter_line_offset(skill_path):
    """1-based line number of the frontmatter closing ``---`` (body checks
    number their findings relative to it)."""
    lines = (skill_path / "SKILL.md").read_text().split("\n")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return i + 1
    return 0


def check_body_structure(skill_path, tier="default"):
    """Check SKILL.md body against CANONICAL_BODY_SECTIONS (utils.py).

    WARN-level only — never blocks (frontmatter failures do). Findings: missing
    required sections / out-of-order canonical sections are WARN; sections the
    given tier may omit and extra H2 sections are INFO.
    """
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
                    evidence=f"正文缺少规范节 `{heading}`——参照 assets/skill-template.md 补齐"
                    "（节名 SSOT 在 scripts/utils.py::CANONICAL_BODY_SECTIONS）",
                    file="SKILL.md",
                )
            )

    present_in_order = [h for h in headings if normalize_heading(h) in set(canonical_found)]
    if [normalize_heading(h) for h in present_in_order] != canonical_found:
        expected = " → ".join(f"`{h}`" for norm, h, _ in canonical if norm in set(canonical_found))
        actual = " → ".join(f"`{h}`" for h in present_in_order)
        findings.append(
            Finding(
                rule="BODY-ORDER",
                level="WARN",
                evidence=f"规范节顺序不符——应为 {expected}，实际 {actual}",
                file="SKILL.md",
            )
        )

    canonical_norms = {norm for norm, _, _ in canonical}
    extras = [h for h in headings if normalize_heading(h) not in canonical_norms]
    if tier == "meta":
        # meta 型允许在第一个规范节前放路由节（见 utils.py::CANONICAL_BODY_SECTIONS
        # 注释），路由节不报 INFO；规范节之后的额外节仍报。从 enumerate(headings)
        # 构建，避免 headings.index() 在重复额外节名下取错位置。
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
    if extras:
        listed = "、".join(f"`{h}`" for h in extras)
        findings.append(
            Finding(
                rule="BODY-EXTRA",
                level="INFO",
                evidence=f"额外 H2 节：{listed}"
                "——规范节之外的节应尽量收进 references/，或按 skill-template-guide.md「变体」放路由位置",
                file="SKILL.md",
            )
        )

    return findings


def check_no_when_not_section(skill_path):
    """WARN on a retired ``## 何时不使用`` section (deterministic).

    It used to surface only as a generic "额外 H2 节" INFO, which reads as
    optional tidy-up — but the section is an explicit convention retirement with
    a defined migration (selection negatives go to the description's 「不适用」
    slot), so it gets its own rule and a WARN.
    """
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
                evidence="正文含已废除的 `## 何时不使用` 节——selection 负例归 frontmatter description 的「不适用」槽"
                "（口径见 references/skill-writing-principles.md「结构与加载」）",
                file="SKILL.md",
                line=str(offset + index),
            )
        )
    return findings


def check_description_format(skill_path):
    """Check description for the fixed 3-component format markers (WARN-only).

    硬性约定 SSOT 在 references/skill-writing-principles.md「description 优化原则」
    （固定格式）：场景一句（中文 lead）+ 触发： + 不适用：，槽内措辞自由。
    WARN 不 fail——描述触发准确性由 optimize_description 优化，这里只防结构漂移。
    """
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
                    evidence=f"description 缺 `{label}` 标记——固定格式（场景一句 + 触发： + 不适用：）"
                    "见 references/skill-writing-principles.md「description 优化原则」",
                    file="SKILL.md",
                )
            )
    return findings


def check_no_toc(skill_path):
    """Detect hand-written TOC sections in a skill's markdown (WARN-only).

    目录禁令 SSOT 在 references/skill-writing-principles.md「正文写作原则」的
    「结构与加载」：reference 一律不手写目录（TOC）——agent 全量读入正文不看
    TOC，目录只对浏览器 / 编辑器有效。两类信号：`## TOC` / `## 目录` 节头；
    连续 ≥ 3 行页内锚点列表（无节头形态的目录）。WARN 不 fail——与正文结构
    检查同级，只防回潮；不做 fence 感知，代码块内示例可能误报。
    """
    skill_path = Path(skill_path)
    ssot = "references/skill-writing-principles.md「结构与加载」目录禁令"
    heading_re = re.compile(r"^##\s+(?:TOC|目录)\s*$")
    anchor_re = re.compile(r"^\s*[-*]\s+\[[^\]]+\]\(#")
    findings = []

    def flag(rel, line_no, text):
        return Finding(rule="HAND-TOC", level="WARN", evidence=text, file=rel, line=str(line_no))

    for md_file in sorted(skill_path.rglob("*.md")):
        rel = str(md_file.relative_to(skill_path))
        run_start = None
        run_len = 0
        for lineno, line in enumerate(md_file.read_text().splitlines(), start=1):
            if heading_re.match(line):
                findings.append(flag(rel, lineno, f"手写目录节 `{line.strip()}`——{ssot}"))
            if anchor_re.match(line):
                if run_start is None:
                    run_start = lineno
                run_len += 1
            elif run_len:
                if run_len >= 3:
                    findings.append(flag(rel, run_start, f"疑似手写目录（{run_len} 行连续页内锚点列表）——{ssot}"))
                run_start = None
                run_len = 0
        if run_len >= 3:
            findings.append(flag(rel, run_start, f"疑似手写目录（{run_len} 行连续页内锚点列表）——{ssot}"))
    return findings


def check_body_length(skill_path, tier="default"):
    """Estimate body words and compare against BODY_WORD_LIMIT / SOFT_WORD_TARGETS.

    Why a script and not the audit table's ``wc -w`` row: ``wc -w`` reads a
    Chinese paragraph as one word, so the prose row added a "chars / 1.7"
    conversion that miscounts ASCII-heavy bodies by ~3x — measured against this
    very skill it reports ~5400 "words" where the real estimate is ~2300, i.e. a
    false violation of the hard limit. utils.estimate_body_words counts CJK and
    ASCII separately. Levels stay advisory: the estimate is a proxy for what the
    loader bills, so exceeding it is a WARN rather than a hard failure.
    """
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
                "——按 references/skill-writing-principles.md「正文超长根因诊断」查根因再抽层",
                file="SKILL.md",
            )
        ]
    if soft is not None and words > soft:
        return [
            Finding(
                rule="BODY-LENGTH",
                level="WARN",
                evidence=f"正文约 {words} 词（估算），超 {tier} 型软目标 {soft}——按「精简与粒度约束」三问逐段删，"
                "或抽一层到 references/（软目标不取代硬上限，仅供参考）",
                file="SKILL.md",
            )
        ]
    return []


def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Parse frontmatter through the single shared reader (utils.load_frontmatter)
    try:
        frontmatter = load_frontmatter(skill_path)
    except OSError as e:
        return False, f"Cannot read SKILL.md: {e}"
    except ValueError as e:
        return False, str(e)
    except Exception as e:  # yaml errors surface as ValueError above; this is a last-resort net
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
    if not name:
        # An empty name passed every check here while discover_skill_dirs
        # (require_parseable=True) rejected it — the two must agree.
        return False, "Name must not be empty"
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
                f"Description is too long ({len(description)} characters). "
                f"Maximum is {DESCRIPTION_MAX_CHARS} characters.",
            )

    # Validate compatibility field if present (optional)
    compatibility = frontmatter.get("compatibility", "")
    if compatibility:
        if not isinstance(compatibility, str):
            return False, f"Compatibility must be a string, got {type(compatibility).__name__}"
        if len(compatibility) > 500:
            return False, f"Compatibility is too long ({len(compatibility)} characters). Maximum is 500 characters."

    return True, "Skill is valid!"


def _collect_findings(skill_dir, tier):
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

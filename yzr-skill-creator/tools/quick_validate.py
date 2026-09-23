#!/usr/bin/env python3
"""Validate a skill's frontmatter, directory naming, body, and bundled-doc prose."""

import re
import sys
from pathlib import Path

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import (  # noqa: E402
    BODY_WORD_LIMIT,
    CANONICAL_BODY_SECTIONS,
    DESCRIPTION_MAX_CHARS,
    KEBAB_NAME_RE,
    LEGACY_SUBDIR_RENAMES,
    SKILL_SUBDIRS,
    SKILL_TIERS,
    SOFT_WORD_TARGETS,
    Finding,
    estimate_body_words,
    find_code_spans,
    format_findings,
    frontmatter_span,
    iter_unfenced_lines,
    load_frontmatter,
    skill_markdown_files,
    skill_tier,
)

WHEN_NOT_SECTION_RE = re.compile(r"^##\s+何时不使用")

H2_RE = re.compile(r"^##\s+(.+)$")

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

    headings = []
    for _, line in iter_unfenced_lines(body):
        m = H2_RE.match(line)
        if m:
            headings.append(m.group(1).strip())
    found = {normalize_heading(h): h for h in headings}
    canonical = [(normalize_heading(h[3:]), h, t) for h, t in CANONICAL_BODY_SECTIONS]
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
                    evidence=f"正文缺少规范节 `{heading}`，参照 assets/skill-template.md 补齐",
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
    for index, line in iter_unfenced_lines(body):
        if not WHEN_NOT_SECTION_RE.match(line):
            continue
        findings.append(
            Finding(
                rule="WHEN-NOT-SECTION",
                level="WARN",
                evidence="正文含已废除的 `## 何时不使用` 节，selection 负例归 frontmatter description 的“不适用”槽"
                "（口径见 ref/audit-workflow.md“判定清单”的“触发语不回正文”）",
                file="SKILL.md",
                line=str(offset + index),
            )
        )
    return findings


def check_description_format(skill_path):
    """检查 description：含“触发：”与“不适用：”标记，且不以句号收尾。"""
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
    if description.endswith("。"):
        findings.append(
            Finding(
                rule="DESC-TRAILING-PERIOD",
                level="ERROR",
                evidence="description 以「。」收尾",
                file="SKILL.md",
                fix="删去末尾句号（与正文 block 末统一不加句号）",
            )
        )
    return findings


_EVIDENCE_SNIPPET = 70

_BLANK, _HEADING, _TABLE, _LIST, _QUOTE, _TEXT = range(6)

_HEADING_LINE_RE = re.compile(r"^ {0,3}#{1,6}\s")
_TABLE_LINE_RE = re.compile(r"^\s*\|")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
_QUOTE_LINE_RE = re.compile(r"^\s*>")

# block 末行判定用；句号后只允许行尾修饰（粗体 / 引号 / 括号 / 反引号）
_TRAILING_PERIOD_RE = re.compile(r"。[\s*_`\"'）)\]】”’]*$")


def _line_kind(line):
    """把 md 行粗分成 block 边界类型，供 block 末行判定。"""
    stripped = line.strip()
    if not stripped:
        return _BLANK
    if _HEADING_LINE_RE.match(line):
        return _HEADING
    if _TABLE_LINE_RE.match(line):
        return _TABLE
    if _LIST_ITEM_RE.match(line):
        return _LIST
    if _QUOTE_LINE_RE.match(line):
        return _QUOTE
    return _TEXT


def _block_final_lines(pairs):
    """返回 block 末行行号：段落 / 列表项 / 引用块的最后一行；标题与表格行自成 block。"""
    finals = []
    last = None
    prev_kind = _BLANK
    for lineno, line in pairs:
        kind = _line_kind(line)
        if kind == _BLANK:
            if last is not None:
                finals.append(last)
                last = None
        elif kind in (_HEADING, _TABLE):
            if last is not None:
                finals.append(last)
                last = None
            finals.append(lineno)
        elif kind == _LIST:
            if last is not None:
                finals.append(last)
            last = lineno
        elif kind == _QUOTE:
            if last is not None and prev_kind != _QUOTE:
                finals.append(last)
            last = lineno
        else:
            indented = line[:1] in (" ", "\t")
            if last is not None and not indented and prev_kind != _TEXT:
                finals.append(last)
            last = lineno
        prev_kind = kind
    if last is not None:
        finals.append(last)
    return finals


def check_no_trailing_period(skill_dir):
    """扫 SKILL.md / ref/ / assets/：block 末行以「。」收尾报 ERROR（句中句号与折行续行不报）。"""
    skill_dir = Path(skill_dir)
    findings = []
    for md in skill_markdown_files(skill_dir):
        rel = str(md.relative_to(skill_dir))
        text = md.read_text(encoding="utf-8")
        span = frontmatter_span(text)
        cutoff = span[1] + 1 if span else 0
        pairs = [(lineno, line) for lineno, line in iter_unfenced_lines(text) if lineno > cutoff]
        finals = set(_block_final_lines(pairs))
        for lineno, line in pairs:
            if lineno not in finals:
                continue
            match = _TRAILING_PERIOD_RE.search(line)
            if not match or any(start <= match.start() < end for start, end in find_code_spans(line)):
                continue
            findings.append(
                Finding(
                    rule="TRAILING-PERIOD",
                    level="ERROR",
                    evidence=f"block 末句号：{line.strip()[:_EVIDENCE_SNIPPET]}",
                    file=rel,
                    line=str(lineno),
                    fix="删去行末「。」；句中句号与折行续行保留",
                )
            )
    return findings


def check_no_toc(skill_path):
    """扫描全部 md：手写目录节与连续页内锚点列表。"""
    skill_path = Path(skill_path)
    ssot = "ref/audit-workflow.md“判定清单”的“参考文件禁手写目录”"
    heading_re = re.compile(r"^##\s+(?:TOC|目录|参考文件)\s*$")
    anchor_re = re.compile(r"^\s*[-*]\s+\[[^\]]+\]\(#")
    findings = []

    def flag(rel, line_no, text):
        """构造一条 HAND-TOC Finding。"""
        return Finding(rule="HAND-TOC", level="WARN", evidence=text, file=rel, line=str(line_no))

    def run_finding(rel, run_start, run_len):
        """连续 ≥ 3 行页内锚点列表按疑似手写目录报告，否则 None。"""
        if run_len < 3:
            return None
        return flag(rel, run_start, f"疑似手写目录（{run_len} 行连续页内锚点列表），{ssot}")

    for md_file in sorted(skill_path.rglob("*.md")):
        rel = str(md_file.relative_to(skill_path))
        run_start = None
        run_len = 0
        for lineno, line in iter_unfenced_lines(md_file.read_text(encoding="utf-8")):
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
                evidence=f"正文约 {words} 词（估算），超硬上限 {BODY_WORD_LIMIT}"
                "，按 SKILL.md“执行原则”（归位）查根因再抽层",
                file="SKILL.md",
            )
        ]
    if soft is not None and words > soft:
        return [
            Finding(
                rule="BODY-LENGTH",
                level="WARN",
                evidence=f"正文约 {words} 词（估算），超 {tier} 型软目标 {soft}，按 SKILL.md“执行原则”（归位）"
                "查根因处置（重抄→删重留指针 / 未下放→抽 ref/；软目标仅供参考，不取代硬上限）",
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
    if not KEBAB_NAME_RE.match(name):
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
            level="WARN",
            evidence=f"metadata.tier={tier!r} 不在 {SKILL_TIERS}，已回落 default",
            file="SKILL.md",
            fix="改成合法 tier 或删掉该键",
        )
    ]


def check_dir_naming(skill_path):
    """检出旧目录名（references/ / scripts/）与非规范顶层子目录，返回 Finding 列表。"""
    skill_path = Path(skill_path)
    findings = []
    for legacy, standard in LEGACY_SUBDIR_RENAMES.items():
        if (skill_path / legacy).is_dir():
            findings.append(
                Finding(
                    rule="DIR-LEGACY",
                    level="ERROR",
                    evidence=f"目录 `{legacy}/` 不受支持，标准名为 `{standard}/`",
                    file=f"{legacy}/",
                    fix=f"重命名 {legacy}/ → {standard}/，并同步更新引用路径",
                )
            )
    for child in sorted(skill_path.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name == "node_modules":
            continue
        if child.name in LEGACY_SUBDIR_RENAMES or child.name in SKILL_SUBDIRS:
            continue
        findings.append(
            Finding(
                rule="DIR-UNKNOWN",
                level="ERROR",
                evidence=f"目录 `{child.name}/` 不在规范子目录（{'、'.join(SKILL_SUBDIRS)}）中",
                file=f"{child.name}/",
                fix="改用规范子目录或移出 skill 目录",
            )
        )
    return findings


def collect_findings(skill_dir, tier=None):
    """汇总一个 skill 的全部结构类 Finding（tier=None = 读 frontmatter metadata.tier，缺省 default）。"""
    valid, message = validate_skill(skill_dir)
    if not valid:
        return valid, message, [Finding(rule="FRONTMATTER", level="ERROR", evidence=message, file="SKILL.md")]
    resolved = skill_tier(Path(skill_dir), tier)
    findings = check_tier_metadata(skill_dir)
    findings += check_dir_naming(skill_dir)
    findings += check_body_structure(skill_dir, tier=resolved)
    findings += check_no_when_not_section(skill_dir)
    findings += check_description_format(skill_dir)
    findings += check_no_toc(skill_dir)
    findings += check_no_trailing_period(skill_dir)
    findings += check_body_length(skill_dir, tier=resolved)
    return valid, message, findings


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Validate a skill's frontmatter, directory naming, body structure, description format, TOC ban, length, and trailing periods"
    )
    parser.add_argument("skill_dir", help="Path to the skill directory")
    parser.add_argument(
        "--tier",
        choices=SKILL_TIERS,
        default=None,
        help="Override the skill's frontmatter metadata.tier (default: read from SKILL.md, fallback 'default')",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human-readable lines")
    args = parser.parse_args()

    valid, message, findings = collect_findings(args.skill_dir, args.tier)

    if args.json:
        print(
            json.dumps(
                {
                    "skill_dir": str(args.skill_dir),
                    "tier": skill_tier(Path(args.skill_dir), args.tier),
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

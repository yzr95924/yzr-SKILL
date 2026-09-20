"""Shared utilities for skill-creator scripts.

Everything here is a pure helper: constants that prose refers to by name, the
frontmatter reader shared by every script, the fence-aware line iterator, and
the Finding record that check scripts emit. No check *logic* lives here — a rule
belongs to the script that enforces it (see
references/skill-writing-principles.md“机械操作脚本化”推论: mechanism detail
stays in the script, prose keeps only the口径).
"""

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# Description length hard limit, in characters. Single source of truth for this metric:
# quick_validate.py enforces it, optimize_description.py rewrites over-long descriptions
# against it. The human-facing statement lives in references/skill-writing-principles.md
# ("指标单一来源" 原则) — change the limit here and code updates everywhere.
DESCRIPTION_MAX_CHARS = 1024

# SKILL.md body hard limit, in words. Prose refers to this constant instead of
# writing the number (指标单一来源). Enforced by quick_validate.check_body_length.
BODY_WORD_LIMIT = 5000

# Soft (advisory) word targets per skill tier — WARN below the hard limit, so an
# over-long-but-under-hard skill still gets flagged. ``meta`` = no target: a
# multi-entry / methodology skill legitimately carries more prose. The 高频触发
# tightening mentioned in prose is an author's voluntary choice and deliberately
# gets no tier / flag of its own (an extra knob for a one-off preference is
# maintenance surface we refuse).
SOFT_WORD_TARGETS: Dict[str, Optional[int]] = {"default": 2000, "reference": 300, "meta": None}

# Body word estimate: Chinese prose has no spaces, so ``wc -w`` reads a whole
# paragraph as one word. Count CJK characters at CJK_CHARS_PER_WORD chars/word
# and add a plain ASCII token count. Fenced code blocks are excluded — command
# examples are not prose. This is an estimator, not a tokeniser: it only ever
# feeds WARN/INFO level checks.
CJK_CHARS_PER_WORD = 1.7
# CJK ideographs: Extension A + URO + Compatibility Ideographs (re parses \\u in patterns).
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_`.'\-/]+")


def estimate_body_words(body: str) -> int:
    """Estimate the word count of SKILL.md prose (fenced code excluded).

    Splitting CJK from ASCII matters: applying the CJK divisor to English text
    overestimates by ~3.5x (an English word averages ~6 characters, not 1.7),
    which would false-positive every ASCII-heavy skill against BODY_WORD_LIMIT.
    """
    prose = "\n".join(line for _, line in iter_unfenced_lines(body))
    cjk_chars = len(_CJK_RE.findall(prose))
    ascii_tokens = len(_ASCII_TOKEN_RE.findall(_CJK_RE.sub(" ", prose)))
    return int(round(cjk_chars / CJK_CHARS_PER_WORD + ascii_tokens))


# ---------------------------------------------------------------------------
# Fence-aware line iteration (shared: quick_validate, check_anchor_health,
# audit_prose all need "prose lines only" and must agree on what a fence is)
# ---------------------------------------------------------------------------

# Fenced code block opening: 3+ backticks or 3+ tildes, ≤ 3 leading spaces
# (CommonMark). We capture the full run so a 4-backtick fence (````) can
# contain 3-backtick (```) lines as *content* — matching the opener's run
# length is what tells content-closers apart from real closers. The info
# string after the fence (e.g. ```` ```yaml ````) is ignored.
_FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})")


def find_code_spans(line: str) -> List[Tuple[int, int]]:
    """Half-open ``[start, end)`` spans of inline code in *line*.

    A span is a pair of matching *single* backticks; CommonMark's run-length
    matching is deliberately not modelled. Known consequence: text wrapped in
    double backticks (e.g. a `` ``[x](a.md#y)`` `` link illustration) is not
    recognised as one code span, so an example inside it can still be scanned.
    Accepted because upgrading the matcher would change which live references
    each checker sees — a bigger behaviour change than the illustration case
    is worth, and prose can dodge it by putting such illustrations in fenced code.
    """
    spans: List[Tuple[int, int]] = []
    i = 0
    while i < len(line):
        if line[i] == "`":
            close = line.find("`", i + 1)
            if close == -1:
                break
            spans.append((i, close + 1))
            i = close + 1
        else:
            i += 1
    return spans


def iter_unfenced_lines(text: str):
    """Yield ``(lineno, line)`` for lines outside fenced code blocks.

    Line numbers are 1-based and preserve the original numbering, so findings
    point at the real source line even when fences are skipped.
    """
    fence: Optional[str] = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _FENCE_RE.match(line)
        if match:
            marker = match.group(2)
            if fence is None:
                fence = marker
                continue
            if marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
                continue
        if fence is None:
            yield lineno, line


# ---------------------------------------------------------------------------
# Findings: one record shape for every check script
# ---------------------------------------------------------------------------

# Severity vocabulary is reused from quick_validate (ERROR blocks, WARN advises,
# INFO observes) rather than inventing a second scale — the P1–P4 grading in
# references/skill-writing-principles.md“审查深度标准” is the agent's *report*
# layer and is derived from (level, rule), not stored here.
FINDING_LEVELS = ("ERROR", "WARN", "INFO")


class Finding(NamedTuple):
    """One audit finding. *rule* is a stable machine id (e.g. ``BODY-LENGTH``)
    so CI and agents can filter; *evidence* is the human-readable line; *fix*
    is the suggested remedy ("" when the finding is self-explanatory).

    Call sites pass every field by keyword: all six fields are ``str``, so a
    positional slip is invisible to a linter and silently lands in the wrong
    slot (this happened once while writing these scripts)."""

    rule: str
    level: str
    evidence: str
    file: str = ""
    line: str = ""
    fix: str = ""

    def location(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}  "
        if self.file:
            return f"{self.file}  "
        return ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "rule": self.rule,
            "level": self.level,
            "file": self.file,
            "line": self.line,
            "evidence": self.evidence,
            "fix": self.fix,
        }


def format_findings(findings: List[Finding]) -> List[str]:
    """Render findings as ``LEVEL: file:line  evidence —— fix`` lines."""
    out = []
    for f in findings:
        text = f"{f.level}: {f.location()}{f.evidence}"
        if f.fix:
            text += f" —— {f.fix}"
        out.append(text)
    return out


_KEBAB_NAME_RE = re.compile(r"^[a-z0-9-]+$")


def discover_skill_dirs(repo_root: Path, require_parseable: bool = False) -> List[Path]:
    """Direct sub-dirs of *repo_root* that count as a skill — one rule for every
    script that sweeps a repo, because three slightly different answers to "is
    this a skill?" means a half-broken directory is audited by one checker and
    silently skipped by another.

    ``require_parseable=False`` (default): SKILL.md merely exists. verify wants
    to *report* on a broken skill, not omit it from the report.
    ``True``: the frontmatter must parse and name itself a kebab-case slug — the
    cross-skill screens key their graph on that name.
    """
    dirs: List[Path] = []
    if not repo_root.is_dir():
        return dirs
    for child in sorted(repo_root.iterdir()):
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        if require_parseable:
            try:
                name = parse_skill_md(child)[0]
            except (ValueError, OSError):
                continue
            if not _KEBAB_NAME_RE.match(name):
                continue
        dirs.append(child)
    return dirs


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def load_frontmatter(skill_path: Path) -> Dict:
    """Parse SKILL.md's YAML frontmatter into a dict.

    The single frontmatter reader for every script in this skill — PyYAML is
    already a dependency (quick_validate imported it directly), so there is no
    reason to keep a second, hand-rolled parser whose block-scalar edge cases
    would then have to be maintained in two places.

    Raises ValueError for a missing / malformed fence or a non-mapping document;
    yaml.YAMLError for invalid YAML.
    """
    content = (skill_path / "SKILL.md").read_text()
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")
    # Imported here rather than at module top: PyYAML is only needed by the
    # frontmatter reader, and keeping it local means stdlib-only tooling (the
    # fixture / text checks) still runs on a bare interpreter.
    import yaml

    try:
        data = yaml.safe_load("\n".join(lines[1:end_idx]))
    except yaml.YAMLError as e:
        # Normalised to ValueError: callers sweep directories and catch
        # (ValueError, OSError) to skip an unparseable skill — a raw
        # ScannerError would abort the whole scan over one bad file.
        raise ValueError(f"invalid YAML frontmatter: {e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Frontmatter must be a YAML dictionary")
    return data


def parse_skill_md(skill_path: Path) -> Tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content).

    The description is whitespace-normalised (frontmatter is routinely written
    as a ``|`` block scalar whose line breaks are prose wrapping, not content),
    so callers can compare / measure it as a single line.
    """
    frontmatter = load_frontmatter(skill_path)
    name = str(frontmatter.get("name", "") or "").strip()
    description = " ".join(str(frontmatter.get("description", "") or "").split())
    content = (skill_path / "SKILL.md").read_text()
    return name, description, content


# Canonical SKILL.md body sections (H2 headings), in canonical order. Single source
# of truth for the body skeleton: quick_validate.py checks skills against it,
# assets/skill-template.md and references/skill-template-guide.md reference it by
# name — prose must NOT re-list the headings (指标单一来源 原则).
#
# Each entry: (heading, exempt_tiers) where exempt_tiers is the set of skill tiers
# allowed to omit the section. Tiers:
#   default   — 普通 workflow skill（缺省）
#   reference — 纯参考资料型（只聚合信息、不改变 agent 行为，可省行为类节）
#   meta      — 元 skill / 多入口 skill（允许在第一个规范节前加路由节）
# Empty exempt set = required for every tier. 参考样例 is recommended for all
# tiers, so it exempts every tier (missing it = INFO, not WARN). There is
# deliberately NO canonical "参考文件" index section: the agent reaches every
# bundled file through inline "何时去读" pointers at the step that uses it; a
# terminal listing is double-writing at best (see skill-writing-principles.md
# “正文超长根因诊断”'s restatement smell). Enumeration-as-routing needs (e.g.
# multi-domain skills) belong inline at the dispatch step as a routing table.
CANONICAL_BODY_SECTIONS = (
    ("## 输入 / 输出", frozenset()),
    ("## 执行原则 / 边界", frozenset({"reference"})),
    ("## 工作流 / 步骤", frozenset({"reference"})),
    ("## 参考样例", frozenset({"default", "reference", "meta"})),
)

# Allowed --tier values for quick_validate.py's body-structure check.
SKILL_TIERS = ("default", "reference", "meta")

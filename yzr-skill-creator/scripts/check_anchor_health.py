#!/usr/bin/env python3
"""Audit a skill's markdown cross-references: link targets, heading anchors,
backticked paths. Existence only, never semantics.

Checks run over SKILL.md + top-level / references/ / scripts/ *.md:
- `[text](target)`: target must resolve inside the skill (DEAD-LINK); with
  `#anchor`, anchor must match a heading slug (see slugify_heading) or an
  explicit <a id> (ANCHOR-DRIFT).
- backticked `x.md` / `x.py` tokens: resolve via containing file, then skill
  root, then basename search (PATH-MISSING; paths escaping the skill root are
  CROSS-SKILL-PATH). Fenced code, externals, and placeholder / topic-name
  exemptions: see is_placeholder_path, is_placeholder_target, _TOPIC_FILENAMES.

Reference convention SSOT: references/skill-writing-principles.md "引用约定".
Does not audit vendored copies (per [[skill-source-priority-over-memory-vendor]]).

Usage:
    python3 -m scripts.check_anchor_health <skill-dir>
    python3 -m scripts.check_anchor_health --repo-root <repo-root>
        [--json] [--include-templates]   # *-template.md skipped unless asked

Exit code: 0 clean, 1 issues, 2 setup error.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap so `from scripts.utils import ...` works both as a standalone
# script and as `python -m scripts.check_anchor_health`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import discover_skill_dirs, find_code_spans, iter_unfenced_lines  # noqa: E402

# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------

# Match [text](target). Greedy until first balanced `)`. Inside the target we
# allow anything except `)`, whitespace, `<`, `>` — same as CommonMark.
# Anchor detection is done separately by splitting on `#` after the target.
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")

# GitHub honors <a id> / <a name> as anchor targets besides heading slugs.
_EXPLICIT_ANCHOR_RE = re.compile(r"""<a\b[^>]*\b(?:id|name)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

# Heading line: ATX-style (# ... ######). Indent ≤ 3 spaces, then 1-6 '#',
# then a space, then the heading text. Setext (text line + ===/--- underline)
# is rare in this repo; it is detected per-line via _setext_heading_text.
_ATX_HEADING_RE = re.compile(r"^( {0,3})(#{1,6})\s+(.*?)\s*#*\s*$")
# Setext underline: 3-space indent max, a run of = or -, optional trailing
# whitespace. The heading text is whatever eligible line precedes it — the old
# two-line regex was only ever fed single lines, so setext headings silently
# never matched (pinned in smoke_test_audit_rules).
_SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")


def _frontmatter_end_index(lines: List[str]) -> int:
    """0-based index of the line *after* the frontmatter closing fence
    (0 = no frontmatter).

    Setext detection must not fire on frontmatter fences: the closing
    ``---`` always has a non-blank frontmatter line above it and would
    otherwise read as a setext underline, minting bogus headings out of
    frontmatter keys.
    """
    if not lines or lines[0].strip() != "---":
        return 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i + 1
    return 0


def _setext_heading_text(lines: List[str], i: int, frontmatter_end: int) -> Optional[str]:
    """Heading text when *lines[i]* is a setext underline, else None.

    CommonMark shape: a non-blank paragraph line (not itself an ATX heading)
    directly above an ===/--- underline. A ``---`` after a blank line is a
    thematic break, not an underline; frontmatter fences are excluded via
    *frontmatter_end*.
    """
    if i <= frontmatter_end:
        return None
    if not _SETEXT_UNDERLINE_RE.match(lines[i]):
        return None
    prev = lines[i - 1]
    if not prev.strip() or _ATX_HEADING_RE.match(prev):
        return None
    return prev.strip()


# Fence detection + inline-code spans (the two "is this prose or example?"
# primitives) come from scripts.utils so every checker in this skill agrees on
# what a fence is; do not re-implement them here.


def extract_links(text: str) -> List[Tuple[int, str, str]]:
    """Yield (line_number_1indexed, link_text, target_with_anchor) for
    every markdown link in *text*. Skips:

    - Lines inside fenced code blocks (```` ``` ```` / `~~~`) — those are
      illustrative code samples, not real cross-references.
    - Links whose **target** (the `(...)` part) is inside an inline-code
      span — markdown like `` `[link](foo.md)` `` demonstrates link
      syntax, it doesn't actually link. We only filter by target, not
      by link text, because real links often have `` `code` `` inside
      the text portion (e.g. `` [`migrate-workflow.md` §六](migrate.md#六) ``)
      and we don't want to lose those.
    """
    hits: List[Tuple[int, str, str]] = []
    for lineno, line in iter_unfenced_lines(text):
        code_spans = find_code_spans(line)
        for match in _LINK_RE.finditer(line):
            target_start, target_end = match.span(2)
            if any(c_start <= target_start and target_end <= c_end for c_start, c_end in code_spans):
                continue
            hits.append((lineno, match.group(1), match.group(2)))
    return hits


def split_target(target: str) -> Tuple[str, str]:
    """Split a markdown link target into (path, anchor). For target
    'foo.md#section-1' returns ('foo.md', 'section-1'). For 'foo.md'
    returns ('foo.md', ''). For '#section' (same-file anchor) returns
    ('', 'section').
    """
    hash_idx = target.find("#")
    if hash_idx == -1:
        return target, ""
    return target[:hash_idx], target[hash_idx + 1 :]


# ---------------------------------------------------------------------------
# Heading slug
# ---------------------------------------------------------------------------


def slugify_heading(text: str) -> str:
    """Compute the GitHub-style heading anchor slug for *text*.

    Mirrors github's slug algorithm closely enough for our checks:

    - Strip surrounding whitespace.
    - Strip backticks (for `` `code` `` spans inside headings).
    - Lowercase ASCII letters (preserve CJK and other scripts as-is).
    - Remove punctuation except word characters, whitespace, and hyphen.
    - Replace each whitespace char with a single hyphen (one-to-one,
      not collapsing runs). This matters: a stripped punctuation char
      between two spaces (e.g. `source / synthesis` → `source
      synthesis`) produces `source--synthesis`, not
      `source-synthesis`. Collapsing runs here would mis-align
      anchors whose originals have punctuation gaps.
    - Trim leading/trailing hyphens.

    We do NOT emulate github's duplicate-heading disambiguation
    (-1, -2 suffix). For our "does it exist?" check, that doesn't matter:
    a duplicated heading is still reachable by the bare slug.
    """
    text = text.strip()
    # Strip backticks (markdown code spans inside headings).
    text = text.replace("`", "")
    # Lowercase ASCII alpha; leave other scripts unchanged so e.g.
    # Chinese characters survive intact.
    lowered = []
    for ch in text:
        if ch.isascii() and ch.isalpha():
            lowered.append(ch.lower())
        else:
            lowered.append(ch)
    text = "".join(lowered)
    # Remove punctuation (anything not word char, whitespace, hyphen).
    # \w with default re.UNICODE matches Unicode letters/digits/underscore,
    # so CJK / kana / etc. survive.
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    # Replace each whitespace char with a single hyphen. Using \s+ here
    # would be WRONG: it collapses runs (e.g. `source  synthesis`
    # after `/` is stripped) into one hyphen, when GitHub's actual
    # behavior is one hyphen per whitespace char (= two hyphens for a
    # two-space gap). \s matches one char at a time, so each becomes
    # its own hyphen. We deliberately do NOT collapse consecutive
    # hyphens afterwards — see docstring.
    text = re.sub(r"\s", "-", text)
    return text.strip("-")


def collect_heading_slugs(text: str) -> Dict[str, int]:
    """Return {slug: line_number} for every heading in *text*. Setext
    headings (===/---) are also picked up. Collisions keep the first
    occurrence's line number — the anchor still works on the first
    heading regardless, so this is fine for "does it exist?" checks.
    """
    slugs: Dict[str, int] = {}
    lines = text.splitlines()
    fm_end = _frontmatter_end_index(lines)
    for i, line in enumerate(lines):
        atx_match = _ATX_HEADING_RE.match(line)
        if atx_match:
            heading = atx_match.group(3)
            slug = slugify_heading(heading)
            if slug and slug not in slugs:
                slugs[slug] = i + 1
            continue
        # Setext: a non-blank line followed by an ===/--- underline. The
        # heading text is on the previous line.
        setext_text = _setext_heading_text(lines, i, fm_end)
        if setext_text is not None:
            slug = slugify_heading(setext_text)
            if slug and slug not in slugs:
                slugs[slug] = i  # 1-indexed: the underline line is i+1, heading is i
    return slugs


def collect_explicit_anchor_ids(text: str) -> set:
    """Return the set of explicit anchor IDs declared in *text* via
    `<a id="...">` / `<a name="...">` HTML tags. GitHub honors these as
    navigation targets independent of heading slugs, so a TOC that points
    at `#foo` resolves if the file contains `<a id="foo">` even when no
    heading slug matches. We read the raw text (these tags are inline
    HTML, not rendered by our heading scan)."""
    return {m.group(1) for m in _EXPLICIT_ANCHOR_RE.finditer(text)}


# ---------------------------------------------------------------------------
# File resolution + scan
# ---------------------------------------------------------------------------


def is_external(target: str) -> bool:
    """True for absolute URLs / known custom protocols we should not try
    to resolve as file paths. Includes ``mention:`` (Outline's @mention
    protocol) — every occurrence is illustrative prose, not a real file ref."""
    scheme_match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)
    if not scheme_match:
        return False
    scheme = scheme_match.group(0).lower()
    return scheme in ("http:", "https:", "mailto:", "ftp:", "mention:")


# Targets that are clearly illustrative placeholders in markdown prose,
# not real file references. Skip silently — false positives on these are
# noise; missing real drift on them is impossible (they can't be real).
_PLACEHOLDER_LITERALS = frozenset({"...", "path", "url", "Path", "URL"})


def is_placeholder_target(target: str) -> bool:
    """True if *target* is a placeholder pattern that can never be a real
    file reference. Catches ``<slug>.md``, ``<userId>``, ``...``,
    ``/api/...id=...``, etc. — the visual signatures authors use to
    denote "this is an example, not a real link"."""
    # Any literal '<' = template substitution marker.
    if "<" in target:
        return True
    # Any literal '...' = ellipsis placeholder.
    if "..." in target:
        return True
    # Exact-match denylist of variable names that authors use to talk
    # about URLs/paths in the abstract (e.g. "see [link](path) for ...").
    if target in _PLACEHOLDER_LITERALS:
        return True
    return False


def resolve_target(containing_file: Path, target_path: str, skill_root: Path) -> Optional[Path]:
    """Resolve *target_path* (relative to *containing_file*'s directory) to
    an absolute path. Returns None if the target is empty, or if the
    resolved path escapes *skill_root* (we don't follow cross-skill links
    into sibling skills, only into the skill being audited).

    Cross-skill refs like `../other-skill/foo.md` are followed only if they
    land inside *skill_root* (rare in this repo — discouraged per AGENTS.md
    "跨 skill 协作约定").
    """
    if not target_path:
        return None
    base = containing_file.parent
    # Pure relative path; resolve against base, then ensure result is
    # under skill_root (no escape).
    try:
        resolved = (base / target_path).resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(skill_root.resolve())
    except ValueError:
        # Resolved outside skill_root — refuse. Cross-skill links fall
        # here; we don't audit them (other skill's anchor health is that
        # other skill's problem).
        return None
    return resolved


# ---------------------------------------------------------------------------
# Backticked path refs
# ---------------------------------------------------------------------------

# A backticked token that can carry a concrete file reference: path
# charset only, ending in a source / doc extension. Commands with spaces,
# template placeholders and globs never match.
_PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./-]+\.(?:md|py)$")

# ``scripts/utils.py::SYMBOL`` — the file part is a real ref, the symbol
# suffix is not; strip it before resolving.
_SYMBOL_SUFFIX_RE = re.compile(r"::[A-Za-z0-9_.]+$")

# File *kinds* discussed as topics (the target project's AGENTS.md, a
# skill's CHANGELOG.md sidecar, ...), not pointers into this skill. Bare
# occurrences are skipped; directory-qualified occurrences still checked.
# SKILL.md is deliberately absent — it resolves locally in every skill.
_TOPIC_FILENAMES = frozenset({"AGENTS.md", "CLAUDE.md", "MEMORY.md", "README.md", "CHANGELOG.md"})

# Teaching-example naming (same spirit as the code-fence exemption):
# single letters / foo-bar names used to illustrate a naming rule.
_PLACEHOLDER_STEMS = frozenset({"a", "b", "foo", "bar", "baz"})


def extract_backtick_paths(text: str) -> List[Tuple[int, str]]:
    """Yield (line_number, path_token) for inline-code spans that look
    like concrete file paths (see _PATH_TOKEN_RE). Fenced blocks are
    skipped: their paths are command examples with cwd-relative meaning."""
    hits: List[Tuple[int, str]] = []
    for lineno, line in iter_unfenced_lines(text):
        for start, end in find_code_spans(line):
            content = _SYMBOL_SUFFIX_RE.sub("", line[start + 1 : end - 1].strip())
            if _PATH_TOKEN_RE.match(content):
                hits.append((lineno, content))
    return hits


def is_placeholder_path(path: str) -> bool:
    """True for sample / template naming that can never be a real ref:
    `<...>` markers, globs, ellipses, single-letter / foo-bar sample
    stems, iteration-N placeholders."""
    if any(ch in path for ch in "<>*") or "..." in path:
        return True
    for segment in path.split("/"):
        stem = segment.rsplit(".", 1)[0]
        if stem in _PLACEHOLDER_STEMS or segment.endswith("-N"):
            return True
    return False


def scan_file(md_path: Path, skill_root: Path) -> List[Dict[str, str]]:
    """Audit a single markdown file. Returns a list of issue dicts; empty
    if the file is clean.
    """
    issues: List[Dict[str, str]] = []
    text = md_path.read_text()
    links = extract_links(text)
    for lineno, link_text, raw_target in links:
        # External URL → skip (we don't fetch the web).
        if is_external(raw_target):
            continue
        # Illustrative placeholder target → skip (see is_placeholder_target).
        if is_placeholder_target(raw_target):
            continue
        target_path, anchor = split_target(raw_target)
        # Empty target `[text]()` with no anchor — malformed, skip silently.
        # Bare anchor `[text](#anchor)` — same-file reference.
        if not target_path and not anchor:
            continue
        resolved: Optional[Path]
        if not target_path:
            # Same-file anchor; resolve against containing file.
            resolved = md_path
        else:
            resolved = resolve_target(md_path, target_path, skill_root)
        if resolved is None:
            issues.append(
                {
                    "file": str(md_path.relative_to(skill_root)),
                    "line": str(lineno),
                    "link_text": link_text,
                    "target": raw_target,
                    "anchor": anchor,
                    "status": "DEAD-LINK",
                    "reason": "target file does not exist or escapes skill root",
                }
            )
            continue
        if not resolved.exists():
            issues.append(
                {
                    "file": str(md_path.relative_to(skill_root)),
                    "line": str(lineno),
                    "link_text": link_text,
                    "target": raw_target,
                    "anchor": anchor,
                    "status": "DEAD-LINK",
                    "reason": f"target file not found: {resolved}",
                }
            )
            continue
        if anchor:
            target_text = resolved.read_text()
            slugs = collect_heading_slugs(target_text)
            explicit_ids = collect_explicit_anchor_ids(target_text)
            # Valid if the anchor matches a heading slug OR an explicit
            # <a id>/<a name> anchor (GitHub honors both).
            if anchor in slugs or anchor in explicit_ids:
                continue
            # Suggest close matches: any slug containing the anchor as
            # substring, or with low edit distance. Simple substring
            # filter is good enough — gives a hint without false
            # positives from aggressive Levenshtein.
            candidates = [s for s in slugs if anchor[:5] in s or s[:5] in anchor]
            hint = f"; similar slugs: {candidates[:5]}" if candidates else ""
            issues.append(
                {
                    "file": str(md_path.relative_to(skill_root)),
                    "line": str(lineno),
                    "link_text": link_text,
                    "target": raw_target,
                    "anchor": anchor,
                    "status": "ANCHOR-DRIFT",
                    "reason": (
                        f"anchor #{anchor} not found in {resolved.name}"
                        f" ({len(slugs)} heading slug(s), {len(explicit_ids)} explicit anchor(s))" + hint
                    ),
                }
            )
    _scan_backtick_paths(md_path, skill_root, text, issues)
    return issues


def _resolve_skill_root_ref(skill_root: Path, token: str) -> Optional[Path]:
    """Fallback resolution for refs written from the skill root rather
    than the containing file's directory — operational refs in this repo
    routinely say `references/x.md` inside a references/ file. Also
    serves bare basenames found anywhere in the skill (``x.py`` for
    scripts/x.py). Returns an existing path or None."""
    if "/" in token:
        candidate = skill_root / token
        try:
            candidate = candidate.resolve()
            candidate.relative_to(skill_root.resolve())
        except (OSError, ValueError):
            return None
        return candidate if candidate.exists() else None
    for match in sorted(skill_root.rglob(token)):
        if match.is_file():
            return match
    return None


def _escapes_skill_root(md_path: Path, token: str, skill_root: Path) -> Optional[bool]:
    """``True``: *token* (resolved against the containing file) lands outside
    *skill_root*, i.e. it reaches into a sibling skill. ``None``: unresolvable
    (filesystem error) — a distinct answer, because reporting an unreadable path
    as a cross-skill violation sends the reader to fix the wrong thing."""
    try:
        resolved = (md_path.parent / token).resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(skill_root.resolve())
    except ValueError:
        return True
    return False


def _scan_backtick_paths(md_path: Path, skill_root: Path, text: str, issues: List[Dict[str, str]]) -> None:
    """PATH-MISSING: every backticked ``x.md`` / ``x.py`` reference must
    resolve — relative to the containing file first, then to the skill
    root (operational refs), then as a skill-wide basename search.

    CROSS-SKILL-PATH: a relative path that leaves the skill root is a
    violation in itself (see references/skill-writing-principles.md
    "相对路径引用禁止") — it resolves only as long as the sibling skill
    keeps its current directory name and layout, and breaks silently once
    skills are distributed independently.
    """
    for lineno, token in extract_backtick_paths(text):
        if "/" not in token and token in _TOPIC_FILENAMES:
            continue
        if token.startswith("MEMORY/") or token.startswith("yzr-"):
            # Managed-project memory file / sibling-skill path — topic
            # mentions, never local refs (cross-skill is out of scope).
            continue
        if is_placeholder_path(token):
            continue
        resolved = resolve_target(md_path, token, skill_root)
        if resolved is None:
            if _escapes_skill_root(md_path, token, skill_root) is True:
                issues.append(
                    {
                        "file": str(md_path.relative_to(skill_root)),
                        "line": str(lineno),
                        "link_text": "",
                        "target": token,
                        "anchor": "",
                        "status": "CROSS-SKILL-PATH",
                        "reason": f"relative path escapes the skill root: {token}",
                    }
                )
            continue
        if resolved.exists():
            continue
        if _resolve_skill_root_ref(skill_root, token):
            continue
        issues.append(
            {
                "file": str(md_path.relative_to(skill_root)),
                "line": str(lineno),
                "link_text": "",
                "target": token,
                "anchor": "",
                "status": "PATH-MISSING",
                "reason": f"backticked path not found: {token}",
            }
        )


def find_markdown_files(skill_root: Path, include_templates: bool = False) -> List[Path]:
    """Markdown files to audit: SKILL.md + references/*.md + scripts/*.md.

    Files whose name ends in ``-template.md`` are skipped by default —
    they are skeleton files that get copied into the wiki root, where
    relative paths like ``AGENTS.md`` / ``wiki/tags.md`` are valid. From
    the skill source dir they always look like dead links. Pass
    ``include_templates=True`` to audit them anyway.

    assets/*.md is excluded by convention (assets/ holds templates, not
    prose with cross-references). Top-level *.md aside from SKILL.md is
    rare; if present it's typically a README that should also be audited
    — include it.
    """
    files: List[Path] = []
    skill_md = skill_root / "SKILL.md"
    if skill_md.is_file():
        files.append(skill_md)
    # Top-level *.md besides SKILL.md (rare; typically a README) ships with
    # the skill and its links drift like any other file — audit it.
    for p in sorted(skill_root.glob("*.md")):
        if not p.is_file() or p == skill_md:
            continue
        if not include_templates and p.stem.endswith("-template"):
            continue
        files.append(p)
    for sub in ("references", "scripts"):
        sub_root = skill_root / sub
        if sub_root.is_dir():
            # rglob: references/ may nest (e.g. references/agents/grader.md);
            # scripts/ is flat in practice but rglob is harmless there.
            for p in sorted(sub_root.rglob("*.md")):
                if not p.is_file():
                    continue
                if not include_templates and p.stem.endswith("-template"):
                    continue
                files.append(p)
    return files


def count_skipped_templates(skill_root: Path) -> int:
    """Count ``*-template.md`` files that would be skipped (for the
    summary line)."""
    skill_md = skill_root / "SKILL.md"
    n = sum(1 for p in skill_root.glob("*.md") if p.is_file() and p != skill_md and p.stem.endswith("-template"))
    for sub in ("references", "scripts"):
        sub_root = skill_root / sub
        if sub_root.is_dir():
            n += sum(1 for p in sub_root.rglob("*.md") if p.stem.endswith("-template"))
    return n


def scan_skill(
    skill_root: Path, include_templates: bool = False
) -> Tuple[int, int, int, int, int, List[Dict[str, str]]]:
    """Scan one skill directory. Returns (files_scanned, links_checked,
    paths_checked, templates_skipped, issues)."""
    files = find_markdown_files(skill_root, include_templates=include_templates)
    all_issues: List[Dict[str, str]] = []
    links_checked = 0
    paths_checked = 0
    for f in files:
        text = f.read_text()
        links = extract_links(text)
        # Count only links the scanner will actually check (skip externals,
        # placeholders, and bare-empty).
        checkable = [
            (ln, lt, tgt)
            for (ln, lt, tgt) in links
            if not is_external(tgt)
            and not is_placeholder_target(tgt)
            and (split_target(tgt)[0] or split_target(tgt)[1])
        ]
        links_checked += len(checkable)
        paths_checked += sum(
            1
            for _, token in extract_backtick_paths(text)
            if not ("/" not in token and token in _TOPIC_FILENAMES)
            and not token.startswith("MEMORY/")
            and not token.startswith("yzr-")
            and not is_placeholder_path(token)
        )
        all_issues.extend(scan_file(f, skill_root))
    templates_skipped = 0 if include_templates else count_skipped_templates(skill_root)
    return len(files), links_checked, paths_checked, templates_skipped, all_issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def discover_skills(repo_root: Path) -> List[Path]:
    """Absolute skill dirs under *repo_root* — the shared rule in
    scripts.utils.discover_skill_dirs, with the parseable frontmatter the
    cross-skill screens also require."""
    return [path.resolve() for path in discover_skill_dirs(repo_root, require_parseable=True)]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit markdown link anchors inside a skill — catches silent drift between SKILL.md / references/*.md cross-references and the headings they point at."
    )
    parser.add_argument(
        "skill_dir",
        nargs="?",
        default=None,
        help="skill directory to audit (default with --repo-root: scan all skills under repo)",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="audit every skill under this repo root (overrides positional skill_dir)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    parser.add_argument(
        "--include-templates",
        action="store_true",
        help="audit *-template.md files too (default: skip — those are skeleton files copied into wikis, where their relative paths resolve differently)",
    )
    args = parser.parse_args(argv)

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
        if not repo_root.is_dir():
            print(f"error: repo root not found: {repo_root}", file=sys.stderr)
            return 2
        skill_dirs = discover_skills(repo_root)
        if not skill_dirs:
            print(f"error: no skills found under {repo_root}", file=sys.stderr)
            return 2
    elif args.skill_dir:
        skill_dir = Path(args.skill_dir).resolve()
        if not skill_dir.is_dir():
            print(f"error: skill dir not found: {skill_dir}", file=sys.stderr)
            return 2
        skill_dirs = [skill_dir]
    else:
        parser.error("either skill_dir or --repo-root is required")

    overall_files = 0
    overall_links = 0
    overall_paths = 0
    overall_templates = 0
    overall_issues: List[Dict[str, object]] = []
    for skill_dir in skill_dirs:
        files_scanned, links_checked, paths_checked, templates_skipped, issues = scan_skill(
            skill_dir, include_templates=args.include_templates
        )
        overall_files += files_scanned
        overall_links += links_checked
        overall_paths += paths_checked
        overall_templates += templates_skipped
        for issue in issues:
            overall_issues.append({"skill": skill_dir.name, **issue})

    if args.json:
        payload = {
            "files_scanned": overall_files,
            "links_checked": overall_links,
            "paths_checked": overall_paths,
            "templates_skipped": overall_templates,
            "issue_count": len(overall_issues),
            "issues": overall_issues,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        suffix = (
            f", skipped {overall_templates} template file(s) (--include-templates to audit)"
            if overall_templates and not args.include_templates
            else ""
        )
        print(
            f"Scanned {overall_files} file(s), {overall_links} link(s), "
            f"{overall_paths} path ref(s){suffix}; {len(overall_issues)} issue(s) found."
        )
        if overall_issues:
            print("")
            for issue in overall_issues:
                skill = issue["skill"]
                file = issue["file"]
                line = issue["line"]
                target = issue["target"]
                status = issue["status"]
                reason = issue["reason"]
                print(f"[{status}] {skill}/{file}:{line}  [{target}]")
                print(f"    {reason}")
            print("")
            print("Hint: re-run with --json for machine-readable output.")

    return 1 if overall_issues else 0


if __name__ == "__main__":
    sys.exit(main())

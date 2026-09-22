#!/usr/bin/env python3
"""Audit markdown cross-references: link targets, anchors, backticked paths."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import discover_skill_dirs, find_code_spans, frontmatter_span, iter_unfenced_lines  # noqa: E402

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


_EXPLICIT_ANCHOR_RE = re.compile(r"""<a\b[^>]*\b(?:id|name)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


_ATX_HEADING_RE = re.compile(r"^( {0,3})(#{1,6})\s+(.*?)\s*#*\s*$")


_SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")


def _setext_heading_text(lines: List[str], i: int, frontmatter_end: int) -> Optional[str]:
    """若第 i 行是 setext 下划线，返回其标题文本，否则 None。"""
    if i <= frontmatter_end:
        return None
    if not _SETEXT_UNDERLINE_RE.match(lines[i]):
        return None
    prev = lines[i - 1]
    if not prev.strip() or _ATX_HEADING_RE.match(prev):
        return None
    return prev.strip()


def extract_links(text: str) -> List[Tuple[int, str, str]]:
    """提取 markdown 行内链接 (行号, 链接文本, 目标)，跳过代码段内的。"""
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
    """把链接目标拆成 (路径, 锚点)。"""
    hash_idx = target.find("#")
    if hash_idx == -1:
        return target, ""
    return target[:hash_idx], target[hash_idx + 1 :]


def slugify_heading(text: str) -> str:
    """按 GitHub 规则生成标题锚点（小写、去标点、空格转连字符）。"""
    text = text.strip()

    text = text.replace("`", "")

    lowered = []
    for ch in text:
        if ch.isascii() and ch.isalpha():
            lowered.append(ch.lower())
        else:
            lowered.append(ch)
    text = "".join(lowered)

    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)

    text = re.sub(r"\s", "-", text)
    return text.strip("-")


def collect_heading_slugs(text: str) -> Dict[str, int]:
    """收集全文标题 slug 到行号（同名取首个）。"""
    slugs: Dict[str, int] = {}
    lines = text.splitlines()
    span = frontmatter_span(text)
    fm_end = span[1] + 1 if span else 0
    for i, line in enumerate(lines):
        atx_match = _ATX_HEADING_RE.match(line)
        if atx_match:
            heading = atx_match.group(3)
            slug = slugify_heading(heading)
            if slug and slug not in slugs:
                slugs[slug] = i + 1
            continue

        setext_text = _setext_heading_text(lines, i, fm_end)
        if setext_text is not None:
            slug = slugify_heading(setext_text)
            if slug and slug not in slugs:
                slugs[slug] = i
    return slugs


def collect_explicit_anchor_ids(text: str) -> set:
    """收集 `<a id=...>` / `<a name=...>` 显式锚点。"""
    return {m.group(1) for m in _EXPLICIT_ANCHOR_RE.finditer(text)}


def is_external(target: str) -> bool:
    """判断链接目标是否为外部协议（http/https/mailto/ftp/mention）。"""
    scheme_match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)
    if not scheme_match:
        return False
    scheme = scheme_match.group(0).lower()
    return scheme in ("http:", "https:", "mailto:", "ftp:", "mention:")


_PLACEHOLDER_LITERALS = frozenset({"...", "path", "url", "Path", "URL"})


def is_placeholder_target(target: str) -> bool:
    """判断链接目标是否为占位符（含尖括号、省略号或字面量 path/url）。"""
    if "<" in target:
        return True

    if "..." in target:
        return True

    if target in _PLACEHOLDER_LITERALS:
        return True
    return False


def resolve_target(containing_file: Path, target_path: str, skill_root: Path) -> Optional[Path]:
    """解析相对路径并限制在 skill 根内；越界或失败返回 None。"""
    if not target_path:
        return None
    base = containing_file.parent

    try:
        resolved = (base / target_path).resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(skill_root.resolve())
    except ValueError:
        return None
    return resolved


_PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./-]+\.(?:md|py)$")


_SYMBOL_SUFFIX_RE = re.compile(r"::[A-Za-z0-9_.]+$")


_TOPIC_FILENAMES = frozenset({"AGENTS.md", "CLAUDE.md", "MEMORY.md", "README.md", "CHANGELOG.md"})


_PLACEHOLDER_STEMS = frozenset({"a", "b", "foo", "bar", "baz"})


def extract_backtick_paths(text: str) -> List[Tuple[int, str]]:
    """提取反引号内像文件路径的 token（去掉 ::symbol 后缀）。"""
    hits: List[Tuple[int, str]] = []
    for lineno, line in iter_unfenced_lines(text):
        for start, end in find_code_spans(line):
            content = _SYMBOL_SUFFIX_RE.sub("", line[start + 1 : end - 1].strip())
            if _PATH_TOKEN_RE.match(content):
                hits.append((lineno, content))
    return hits


def is_placeholder_path(path: str) -> bool:
    """判断路径是否为占位符（通配符、省略号、a-b-foo 段或 -N 结尾）。"""
    if any(ch in path for ch in "<>*") or "..." in path:
        return True
    for segment in path.split("/"):
        stem = segment.rsplit(".", 1)[0]
        if stem in _PLACEHOLDER_STEMS or segment.endswith("-N"):
            return True
    return False


def _is_checkable_link(target: str) -> bool:
    """该链接目标是否需要检查（排除外部协议与占位符，且路径与锚点不能都为空）。"""
    if is_external(target) or is_placeholder_target(target):
        return False
    target_path, anchor = split_target(target)
    return bool(target_path or anchor)


def _is_checkable_path(token: str) -> bool:
    """该反引号 token 是否需要按路径检查（排除主题文件名、跨 skill 裸名提及与占位符）。"""
    if "/" not in token and token in _TOPIC_FILENAMES:
        return False
    if token.startswith("MEMORY/"):
        return False
    if "/" not in token and token.startswith("yzr-"):
        return False
    return not is_placeholder_path(token)


_ANCHOR_PREFIX_MATCH = 5
_CANDIDATE_DISPLAY_LIMIT = 5
_MD_SCAN_SUBDIRS = ("references", "ref", "scripts", "tools")


def _anchor_drift_reason(target: Path, anchor: str) -> Optional[str]:
    """锚点在目标文件中不存在时返回带候选提示的原因，存在返回 None。"""
    text = target.read_text()
    slugs = collect_heading_slugs(text)
    explicit_ids = collect_explicit_anchor_ids(text)
    if anchor in slugs or anchor in explicit_ids:
        return None
    candidates = [s for s in slugs if anchor[:_ANCHOR_PREFIX_MATCH] in s or s[:_ANCHOR_PREFIX_MATCH] in anchor]
    hint = f"; similar slugs: {candidates[:_CANDIDATE_DISPLAY_LIMIT]}" if candidates else ""
    return (
        f"anchor #{anchor} not found in {target.name}"
        f" ({len(slugs)} heading slug(s), {len(explicit_ids)} explicit anchor(s))" + hint
    )


def _scan_links(md_path: Path, skill_root: Path, text: str, issues: List[Dict[str, str]]) -> None:
    """把链接问题（死链 / 锚点漂移）追加进 issues。"""
    for lineno, link_text, raw_target in extract_links(text):
        if not _is_checkable_link(raw_target):
            continue
        target_path, anchor = split_target(raw_target)
        resolved = md_path if not target_path else resolve_target(md_path, target_path, skill_root)
        status = ""
        reason = ""
        if resolved is None:
            status, reason = "DEAD-LINK", "target file does not exist or escapes skill root"
        elif not resolved.exists():
            status, reason = "DEAD-LINK", f"target file not found: {resolved}"
        elif anchor:
            reason = _anchor_drift_reason(resolved, anchor) or ""
            status = "ANCHOR-DRIFT" if reason else ""
        if not status:
            continue
        issues.append(
            {
                "file": str(md_path.relative_to(skill_root)),
                "line": str(lineno),
                "link_text": link_text,
                "target": raw_target,
                "anchor": anchor,
                "status": status,
                "reason": reason,
            }
        )


def scan_file(md_path: Path, skill_root: Path) -> List[Dict[str, str]]:
    """扫单个 md：死链、锚点漂移、反引号路径问题。"""
    issues: List[Dict[str, str]] = []
    text = md_path.read_text()
    _scan_links(md_path, skill_root, text, issues)
    _scan_backtick_paths(md_path, skill_root, text, issues)
    return issues


def _resolve_skill_root_ref(skill_root: Path, token: str) -> Optional[Path]:
    """按 skill 根解析裸文件名 token；找不到返回 None。"""
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
    """判断相对路径是否逃出 skill 根；无法解析返回 None。"""
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
    """把反引号路径问题追加进 issues（CROSS-SKILL-PATH / PATH-MISSING）。"""
    for lineno, token in extract_backtick_paths(text):
        if not _is_checkable_path(token):
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
    """列出要审计的 md（默认跳过 *-template.md）。"""
    files: List[Path] = []
    skill_md = skill_root / "SKILL.md"
    if skill_md.is_file():
        files.append(skill_md)

    for p in sorted(skill_root.glob("*.md")):
        if not p.is_file() or p == skill_md:
            continue
        if not include_templates and p.stem.endswith("-template"):
            continue
        files.append(p)
    for sub in _MD_SCAN_SUBDIRS:
        sub_root = skill_root / sub
        if sub_root.is_dir():
            for p in sorted(sub_root.rglob("*.md")):
                if not p.is_file():
                    continue
                if not include_templates and p.stem.endswith("-template"):
                    continue
                files.append(p)
    return files


def count_skipped_templates(skill_root: Path) -> int:
    """统计被跳过的 *-template.md 数量。"""
    skill_md = skill_root / "SKILL.md"
    n = sum(1 for p in skill_root.glob("*.md") if p.is_file() and p != skill_md and p.stem.endswith("-template"))
    for sub in _MD_SCAN_SUBDIRS:
        sub_root = skill_root / sub
        if sub_root.is_dir():
            n += sum(1 for p in sub_root.rglob("*.md") if p.stem.endswith("-template"))
    return n


class ScanTotals(NamedTuple):
    """一次扫描的计数汇总。"""

    files: int
    links: int
    paths: int
    templates_skipped: int


def scan_skill(skill_root: Path, include_templates: bool = False) -> Tuple[ScanTotals, List[Dict[str, str]]]:
    """扫一个 skill，返回 (计数汇总, issues)。"""
    files = find_markdown_files(skill_root, include_templates=include_templates)
    all_issues: List[Dict[str, str]] = []
    links_checked = 0
    paths_checked = 0
    for md_file in files:
        text = md_file.read_text()
        links_checked += sum(1 for _, _, target in extract_links(text) if _is_checkable_link(target))
        paths_checked += sum(1 for _, token in extract_backtick_paths(text) if _is_checkable_path(token))
        all_issues.extend(scan_file(md_file, skill_root))
    totals = ScanTotals(
        files=len(files),
        links=links_checked,
        paths=paths_checked,
        templates_skipped=0 if include_templates else count_skipped_templates(skill_root),
    )
    return totals, all_issues


def discover_skills(repo_root: Path) -> List[Path]:
    """列出 repo 下可解析 skill 的绝对路径。"""
    return [path.resolve() for path in discover_skill_dirs(repo_root, require_parseable=True)]


def _resolve_skill_dirs(args, parser) -> Optional[List[Path]]:
    """解析审计目标；路径问题打印错误返回 None，用法问题走 parser.error 退出。"""
    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
        if not repo_root.is_dir():
            print(f"error: repo root not found: {repo_root}", file=sys.stderr)
            return None
        skill_dirs = discover_skills(repo_root)
        if not skill_dirs:
            print(f"error: no skills found under {repo_root}", file=sys.stderr)
            return None
        return skill_dirs
    if args.skill_dir:
        skill_dir = Path(args.skill_dir).resolve()
        if not skill_dir.is_dir():
            print(f"error: skill dir not found: {skill_dir}", file=sys.stderr)
            return None
        return [skill_dir]
    parser.error("either skill_dir or --repo-root is required")


def _scan_all(skill_dirs: List[Path], include_templates: bool) -> Tuple[ScanTotals, List[Dict[str, object]]]:
    """扫全部目标 skill，合并计数与 issues（issues 带 skill 名）。"""
    totals = ScanTotals(files=0, links=0, paths=0, templates_skipped=0)
    issues: List[Dict[str, object]] = []
    for skill_dir in skill_dirs:
        skill_totals, skill_issues = scan_skill(skill_dir, include_templates=include_templates)
        totals = ScanTotals(
            files=totals.files + skill_totals.files,
            links=totals.links + skill_totals.links,
            paths=totals.paths + skill_totals.paths,
            templates_skipped=totals.templates_skipped + skill_totals.templates_skipped,
        )
        issues.extend({"skill": skill_dir.name, **issue} for issue in skill_issues)
    return totals, issues


def _render_json(totals: ScanTotals, issues: List[Dict[str, object]]) -> None:
    """输出整份 JSON 报告。"""
    payload = {
        "files_scanned": totals.files,
        "links_checked": totals.links,
        "paths_checked": totals.paths,
        "templates_skipped": totals.templates_skipped,
        "issue_count": len(issues),
        "issues": issues,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _render_text(totals: ScanTotals, issues: List[Dict[str, object]], include_templates: bool) -> None:
    """输出人类可读报告。"""
    suffix = (
        f", skipped {totals.templates_skipped} template file(s) (--include-templates to audit)"
        if totals.templates_skipped and not include_templates
        else ""
    )
    print(
        f"Scanned {totals.files} file(s), {totals.links} link(s), "
        f"{totals.paths} path ref(s){suffix}; {len(issues)} issue(s) found."
    )
    if issues:
        print("")
        for issue in issues:
            print(f"[{issue['status']}] {issue['skill']}/{issue['file']}:{issue['line']}  [{issue['target']}]")
            print(f"    {issue['reason']}")
        print("")
        print("Hint: re-run with --json for machine-readable output.")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：审计链接、锚点、反引号路径；有问题时退出码 1。"""
    parser = argparse.ArgumentParser(
        description="Audit markdown link anchors inside a skill — catches silent drift between SKILL.md / bundled-doc cross-references and the headings they point at."
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
        help="audit *-template.md files too (default: skip — those are skeleton files copied into new skill folders, where their relative paths resolve differently)",
    )
    args = parser.parse_args(argv)

    skill_dirs = _resolve_skill_dirs(args, parser)
    if skill_dirs is None:
        return 2
    totals, issues = _scan_all(skill_dirs, include_templates=args.include_templates)
    if args.json:
        _render_json(totals, issues)
    else:
        _render_text(totals, issues, args.include_templates)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())

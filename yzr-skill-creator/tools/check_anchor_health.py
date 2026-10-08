#!/usr/bin/env python3
"""Audit markdown cross-references: link targets, anchors, link labels, backticked paths."""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import (  # noqa: E402
    SKILL_SOURCE_SUBDIRS,
    Finding,
    find_code_spans,
    frontmatter_span,
    iter_unfenced_lines,
    run_screen,
    skill_markdown_files,
)

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
    """收集全文标题 slug 到行号（同名取首个；跳过围栏代码块，与链接提取口径一致）。"""
    slugs: Dict[str, int] = {}
    lines = text.splitlines()
    span = frontmatter_span(text)
    fm_end = span[1] + 1 if span else 0
    for lineno, line in iter_unfenced_lines(text):
        atx_match = _ATX_HEADING_RE.match(line)
        if atx_match:
            heading, line_no = atx_match.group(3), lineno
        else:
            heading = _setext_heading_text(lines, lineno - 1, fm_end)
            if heading is None:
                continue
            line_no = lineno - 1
        slug = slugify_heading(heading)
        if slug and slug not in slugs:
            slugs[slug] = line_no
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


def _resolve_within(containing_file: Path, target_path: str, skill_root: Path) -> Tuple[Optional[Path], bool]:
    """解析相对路径，返回 (结果或 None, 是否逃出 skill 根)；空目标 / 解析失败返回 (None, False)。"""
    if not target_path:
        return None, False
    try:
        resolved = (containing_file.parent / target_path).resolve()
    except OSError:
        return None, False
    try:
        resolved.relative_to(skill_root.resolve())
    except ValueError:
        return resolved, True
    return resolved, False


_PATH_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./-]+\.(?:md|py)$")


_SYMBOL_SUFFIX_RE = re.compile(r"::[A-Za-z0-9_.]+$")


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
    """判断路径是否为占位符（通配符、省略号、尖括号或 -N 结尾）。"""
    if any(ch in path for ch in "<>*") or "..." in path:
        return True
    return any(segment.endswith("-N") for segment in path.split("/"))


def _is_checkable_link(target: str) -> bool:
    """该链接目标是否需要检查（排除外部协议与占位符，且路径与锚点不能都为空）。"""
    if is_external(target) or is_placeholder_target(target):
        return False
    target_path, anchor = split_target(target)
    return bool(target_path or anchor)


def _is_checkable_path(token: str) -> bool:
    """该反引号 token 是否需要按路径检查：仅内容子目录（ref/assets/tools）根、越界路径与 yzr- 跨 skill 引用可校验；实例路径与裸文件名无法与运行时产物区分，不查。"""
    if is_placeholder_path(token):
        return False
    if "/" not in token:
        return False
    first = token.split("/", 1)[0]
    if first in (".", ".."):
        return True
    if token.startswith("yzr-"):
        return True
    return first in SKILL_SOURCE_SUBDIRS


_ANCHOR_PREFIX_MATCH = 5
_CANDIDATE_DISPLAY_LIMIT = 5
_LINK_LABEL = "章节"

_DEFAULT_FIX = "修链接 / 路径或补齐目标标题（脚本：tools/check_anchor_health.py）"
_LINK_LABEL_FIX = "锚点链接文字统一为「章节」（脚本：tools/check_anchor_health.py）"


def _finding(md_path: Path, skill_root: Path, lineno: int, rule: str, evidence: str) -> Finding:
    """构造一条链接审计 Finding（file 为相对 skill 根路径）。"""
    return Finding(
        rule=rule,
        level="ERROR",
        evidence=evidence,
        file=str(md_path.relative_to(skill_root)),
        line=str(lineno),
        fix=_LINK_LABEL_FIX if rule == "LINK-LABEL" else _DEFAULT_FIX,
    )


def _anchor_drift_reason(target: Path, anchor: str) -> Optional[str]:
    """锚点在目标文件中不存在时返回带候选提示的原因，存在返回 None。"""
    text = target.read_text(encoding="utf-8")
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


def _scan_links(md_path: Path, skill_root: Path, text: str) -> List[Finding]:
    """该文件的链接问题（死链 / 锚点漂移 / 标签不符）。"""
    findings: List[Finding] = []
    for lineno, link_text, raw_target in extract_links(text):
        if not _is_checkable_link(raw_target):
            continue
        target_path, anchor = split_target(raw_target)
        resolved = md_path if not target_path else _resolve_within(md_path, target_path, skill_root)[0]
        if resolved is None:
            findings.append(
                _finding(md_path, skill_root, lineno, "DEAD-LINK", "target file does not exist or escapes skill root")
            )
            continue
        if not resolved.exists():
            findings.append(_finding(md_path, skill_root, lineno, "DEAD-LINK", f"target file not found: {resolved}"))
            continue
        if not anchor:
            continue
        reason = _anchor_drift_reason(resolved, anchor)
        if reason:
            findings.append(_finding(md_path, skill_root, lineno, "ANCHOR-DRIFT", reason))
        elif link_text != _LINK_LABEL:
            findings.append(
                _finding(
                    md_path,
                    skill_root,
                    lineno,
                    "LINK-LABEL",
                    f'anchor link text must be "{_LINK_LABEL}", got "{link_text}"',
                )
            )
    return findings


def _skill_root_candidate(skill_root: Path, token: str) -> Optional[Path]:
    """按 skill 根解析 token（md 相对解析未命中时的第二落点）；越界或不存在返回 None。"""
    try:
        resolved = (skill_root / token).resolve()
        resolved.relative_to(skill_root.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.exists() else None


def _scan_backtick_paths(md_path: Path, skill_root: Path, text: str) -> List[Finding]:
    """该文件的反引号路径问题（CROSS-SKILL-PATH / PATH-MISSING）。"""
    findings: List[Finding] = []
    for lineno, token in extract_backtick_paths(text):
        if not _is_checkable_path(token):
            continue
        resolved, escaped = _resolve_within(md_path, token, skill_root)
        if escaped:
            findings.append(
                _finding(
                    md_path, skill_root, lineno, "CROSS-SKILL-PATH", f"relative path escapes the skill root: {token}"
                )
            )
        elif resolved is not None and not resolved.exists() and _skill_root_candidate(skill_root, token) is None:
            findings.append(
                _finding(md_path, skill_root, lineno, "PATH-MISSING", f"backticked path not found: {token}")
            )
    return findings


def scan_skill(skill_root: Path) -> List[Finding]:
    """扫一个 skill 的链接、锚点与反引号路径（每个 md 只读一遍，产出 Finding 列表）。"""
    skill_root = Path(skill_root)
    findings: List[Finding] = []
    for md in skill_markdown_files(skill_root, "links"):
        text = md.read_text(encoding="utf-8")
        findings += _scan_links(md, skill_root, text)
        findings += _scan_backtick_paths(md, skill_root, text)
    return findings


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：审计链接、锚点、反引号路径；有问题时退出码 1。"""
    return run_screen(
        "Audit markdown link anchors inside a skill — catches silent drift between SKILL.md / "
        "bundled-doc cross-references and the headings they point at.",
        scan_skill,
        argv,
        "issue(s) found.",
    )


if __name__ == "__main__":
    sys.exit(main())

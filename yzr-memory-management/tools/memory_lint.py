#!/usr/bin/env python3
"""检查项目 MEMORY/：索引一致性、frontmatter、预算水位、敏感串；只报告不改写。"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

MEMORY_DIR = "MEMORY"
INDEX_NAME = "MEMORY.md"

# 预算与阈值的机器面；md 侧 SSOT 在 assets/memory-{index,entry}-template.md
INDEX_MAX_LINES = 200
INDEX_MAX_BYTES = 25600
BUDGET_HIGH_RATIO = 0.8
ENTRY_MAX_LINES = 120
DESCRIPTION_MAX_CHARS = 200
VALID_TYPES = ("user", "feedback", "project", "reference")
STALE_INFO_DAYS = 180

ENTRY_LINK_RE = re.compile(r"^\s*-\s+\[(?P<title>[^\]]+)\]\((?P<slug>[^)\s/]+\.md)\)：")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MODIFIED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SENSITIVE_RES = (
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
)


class Finding(NamedTuple):
    """一条检查发现；渲染与 JSON 输出共用六个字段"""

    rule: str
    level: str
    evidence: str
    file: str = ""
    line: str = ""

    def to_dict(self) -> Dict[str, str]:
        """转 JSON 友好 dict"""
        return {
            "rule": self.rule,
            "level": self.level,
            "file": self.file,
            "line": self.line,
            "evidence": self.evidence,
        }


class Stats(NamedTuple):
    """体检报告的机械数字面：索引水位与条目数，免人工计数"""

    index_lines: int
    index_budget_lines: int
    entry_count: int

    def to_dict(self) -> Dict[str, int]:
        """转 JSON 友好 dict"""
        return self._asdict()


class Snapshot(NamedTuple):
    """MEMORY/ 一次性读取快照；entries 值为 None 即读取失败（已计入 read_errors），slug 契约单层故按文件名配对"""

    index_text: Optional[str]
    entries: Dict[str, Optional[str]]
    read_errors: List[Finding]


def snapshot_memory(memory_root: Path) -> Snapshot:
    """一次遍历读齐 MEMORY/；读失败记 READ-ERROR、其余文件继续"""
    entries: Dict[str, Optional[str]] = {}
    read_errors: List[Finding] = []
    index_text: Optional[str] = None
    for path in sorted((memory_root / MEMORY_DIR).glob("*.md")):
        rel = f"{MEMORY_DIR}/{path.name}"
        try:
            text: Optional[str] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            text = None
            read_errors.append(Finding("READ-ERROR", "ERROR", f"无法读取 {rel}: {exc}", file=rel))
        if path.name == INDEX_NAME:
            index_text = text
        else:
            entries[path.name] = text
    return Snapshot(index_text=index_text, entries=entries, read_errors=read_errors)


def parse_frontmatter(text: str) -> Optional[Dict]:
    """轻量解析 --- 围栏的 frontmatter：顶层 key: value，metadata 下挂一层嵌套；多行值不折叠"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    closing = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing = i
            break
    if closing is None:
        return None
    data: Dict = {}
    parent: Optional[str] = None
    for raw in lines[1:closing]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if raw[:1] not in (" ", "\t"):
            if value:
                data[key] = value
            parent = key if not value else None
        elif parent is not None:
            nested = data.setdefault(parent, {})
            if isinstance(nested, dict):
                nested[key] = value
    return data


def discover_memory_root(start: Path) -> Optional[Path]:
    """从 start 向上找含 MEMORY/ 的最近目录；start 本身是 MEMORY/ 时返回其父"""
    for candidate in [start, *start.parents]:
        if (candidate / MEMORY_DIR).is_dir():
            return candidate
        if candidate.name == MEMORY_DIR and candidate.is_dir():
            return candidate.parent
    return None


def _index_findings(rel: str, text: str) -> Tuple[List[Finding], List[Tuple[int, str]]]:
    """检查索引：预算水位、重复链接；返回 (findings, [(行号, slug)])"""
    findings: List[Finding] = []
    line_count = len(text.splitlines())
    if line_count > INDEX_MAX_LINES:
        findings.append(
            Finding(
                "INDEX-BUDGET",
                "ERROR",
                f"索引 {line_count} 行，超上限 {INDEX_MAX_LINES} 行——先精简再写入（合并摘要 / 升格文件条目 / 复核最旧条目）",
                file=rel,
            )
        )
    elif line_count >= int(INDEX_MAX_LINES * BUDGET_HIGH_RATIO):
        findings.append(
            Finding(
                "INDEX-BUDGET-HIGH",
                "WARN",
                f"索引 {line_count} 行，已达上限 {INDEX_MAX_LINES} 行的八成——写入前先备精简案",
                file=rel,
            )
        )
    byte_size = len(text.encode("utf-8"))
    if byte_size > INDEX_MAX_BYTES:
        findings.append(
            Finding(
                "INDEX-BUDGET",
                "ERROR",
                f"索引 {byte_size} 字节，超上限 {INDEX_MAX_BYTES} 字节（25KB）",
                file=rel,
            )
        )
    slugs: List[Tuple[int, str]] = []
    seen: Dict[str, int] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        match = ENTRY_LINK_RE.match(line)
        if match is None:
            continue
        slug = match.group("slug")
        slugs.append((lineno, slug))
        if slug in seen:
            findings.append(
                Finding(
                    "DUP-INDEX-LINE",
                    "WARN",
                    f"索引重复链接同一条目：{slug}（首见第 {seen[slug]} 行）——同主题应合并为一条",
                    file=rel,
                    line=str(lineno),
                )
            )
        else:
            seen[slug] = lineno
    return findings, slugs


def _entry_findings(rel: str, name: str, text: str, linked: bool) -> List[Finding]:
    """检查条目文件本体：slug 命名、孤儿、正文长度，再转 frontmatter"""
    findings: List[Finding] = []
    stem = Path(name).stem
    if not KEBAB_RE.match(stem):
        findings.append(
            Finding(
                "SLUG-FORMAT",
                "ERROR",
                f"条目文件名 {name} 不是 kebab-case（小写字母 / 数字 / 连字符）",
                file=rel,
            )
        )
    if not linked:
        findings.append(
            Finding(
                "ORPHAN",
                "WARN",
                "条目存在但索引没有指向它的链接——补索引行，或确认后删除本文件",
                file=rel,
            )
        )
    entry_lines = len(text.splitlines())
    if entry_lines > ENTRY_MAX_LINES:
        findings.append(
            Finding(
                "ENTRY-LONG",
                "WARN",
                f"条目 {entry_lines} 行，超 {ENTRY_MAX_LINES}——压缩或吸收进 docs / AGENTS.md 留指针（超长多为路由错误）",
                file=rel,
            )
        )
    fm = parse_frontmatter(text)
    if fm is None:
        findings.append(
            Finding(
                "FRONTMATTER-MISSING",
                "ERROR",
                "条目缺 --- 围栏的 frontmatter（三件套：name / description / metadata.type）",
                file=rel,
            )
        )
        return findings
    findings += _frontmatter_findings(rel, stem, fm)
    return findings


def _frontmatter_findings(rel: str, stem: str, fm: Dict) -> List[Finding]:
    """检查 frontmatter 字段：name / description / type / scope / modified"""
    findings: List[Finding] = []
    name = str(fm.get("name", "") or "")
    if not name:
        findings.append(Finding("NAME-MISSING", "ERROR", "缺 name 字段", file=rel))
    elif name != stem:
        findings.append(Finding("NAME-MISMATCH", "ERROR", f"name={name!r} 与文件名 slug {stem!r} 不一致", file=rel))
    description = str(fm.get("description", "") or "")
    if not description:
        findings.append(Finding("DESC-MISSING", "ERROR", "缺 description 字段", file=rel))
    elif len(description) > DESCRIPTION_MAX_CHARS:
        findings.append(
            Finding(
                "DESC-LONG",
                "WARN",
                f"description {len(description)} 字符，超 {DESCRIPTION_MAX_CHARS}——摘要该压缩了",
                file=rel,
            )
        )
    metadata = fm.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    entry_type = str(metadata.get("type", "") or "")
    if not entry_type:
        findings.append(
            Finding("TYPE-MISSING", "ERROR", f"缺 metadata.type（四选一：{' / '.join(VALID_TYPES)}）", file=rel)
        )
    elif entry_type not in VALID_TYPES:
        findings.append(
            Finding("TYPE-INVALID", "ERROR", f"metadata.type={entry_type!r} 不在 {' / '.join(VALID_TYPES)}", file=rel)
        )
    if not str(metadata.get("scope", "") or ""):
        findings.append(
            Finding(
                "SCOPE-MISSING",
                "WARN",
                "缺 metadata.scope——事件驱动复核（scope × git 变更匹配）会漏掉本条",
                file=rel,
            )
        )
    findings += _modified_findings(rel, str(metadata.get("modified", "") or ""))
    return findings


def _modified_findings(rel: str, modified: str) -> List[Finding]:
    """检查 modified 的格式与新鲜度；STALE 只是参考信号，不作陈旧判决依据"""
    if not modified:
        return []
    if not MODIFIED_RE.match(modified):
        return [Finding("MODIFIED-FORMAT", "WARN", f"modified={modified!r} 不是 YYYY-MM-DD", file=rel)]
    try:
        age = (date.today() - date.fromisoformat(modified)).days
    except ValueError:
        return []
    if age > STALE_INFO_DAYS:
        return [
            Finding(
                "STALE",
                "INFO",
                f"modified 距今 {age} 天——仅参考信号，是否复核由事件驱动判据定",
                file=rel,
            )
        ]
    return []


def _sensitive_findings(files: List[Tuple[str, str]]) -> List[Finding]:
    """扫索引与条目里的疑似密钥 / token 字样（只报需人工复核，不判死刑）"""
    findings: List[Finding] = []
    for rel, text in files:
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in SENSITIVE_RES):
                findings.append(
                    Finding(
                        "SENSITIVE",
                        "WARN",
                        f"疑似密钥 / token 字样：{line.strip()[:60]}——密钥永不入记忆，人工复核后删除",
                        file=rel,
                        line=str(lineno),
                    )
                )
    return findings


def collect_findings(memory_root: Path, snap: Optional[Snapshot] = None) -> List[Finding]:
    """跑全部检查；memory_root 须含 MEMORY/ 目录；snap 可传入已读快照避免重复读"""
    snap = snap or snapshot_memory(memory_root)
    findings = list(snap.read_errors)
    index_path = memory_root / MEMORY_DIR / INDEX_NAME
    if snap.index_text is None:
        # 索引读取失败已记 READ-ERROR，不冒充 INDEX-MISSING
        if index_path.parent.is_dir() and not index_path.is_file():
            findings.append(
                Finding(
                    "INDEX-MISSING",
                    "ERROR",
                    f"{MEMORY_DIR}/ 存在但缺索引 {INDEX_NAME}",
                    file=f"{MEMORY_DIR}/{INDEX_NAME}",
                )
            )
        return findings
    index_rel = f"{MEMORY_DIR}/{INDEX_NAME}"
    index_findings, slugs = _index_findings(index_rel, snap.index_text)
    findings += index_findings
    linked = {slug for _, slug in slugs}
    for lineno, slug in slugs:
        if slug not in snap.entries:
            findings.append(
                Finding("DEAD-LINK", "ERROR", f"索引指向的条目不存在：{slug}", file=index_rel, line=str(lineno))
            )
    for name, text in snap.entries.items():
        if text is not None:
            findings += _entry_findings(f"{MEMORY_DIR}/{name}", name, text, name in linked)
    md_texts = [(index_rel, snap.index_text)] + [
        (f"{MEMORY_DIR}/{n}", t) for n, t in snap.entries.items() if t is not None
    ]
    findings += _sensitive_findings(md_texts)
    return findings


def memory_stats(snap: Snapshot) -> Stats:
    """从快照汇总体检数字：索引行数（缺索引记 0）与条目数"""
    index_lines = len(snap.index_text.splitlines()) if snap.index_text is not None else 0
    return Stats(index_lines=index_lines, index_budget_lines=INDEX_MAX_LINES, entry_count=len(snap.entries))


def _render_text(memory_root: Path, findings: List[Finding], stats: Stats) -> None:
    """输出人类可读报告"""
    print(f"== MEMORY root: {memory_root} ==")
    if findings:
        for f in findings:
            loc = f"{f.file}:{f.line}  " if f.file else ""
            print(f"{f.level}: {f.rule}  {loc}{f.evidence}")
    else:
        print("  clean")
    print(f"STATS 索引 {stats.index_lines} / {stats.index_budget_lines} 行 · 条目 {stats.entry_count} 个")
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in ("ERROR", "WARN", "INFO")}
    errors = counts["ERROR"]
    print(f"\n{counts['ERROR']} ERROR, {counts['WARN']} WARN, {counts['INFO']} INFO — {'FAIL' if errors else 'PASS'}")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：定位 MEMORY/、读快照、跑检查、渲染、按 ERROR 定退出码"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="从该路径向上找 MEMORY/（默认 cwd）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非文本")
    args = parser.parse_args(argv)

    start = Path(args.root).resolve()
    memory_root = discover_memory_root(start)
    if memory_root is None:
        info = Finding(
            rule="NO-MEMORY",
            level="INFO",
            evidence="未发现 MEMORY/ 目录——需要建立记忆体系时走 init 入口",
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "memory_root": None,
                        "findings": [info.to_dict()],
                        "stats": None,
                        "error_count": 0,
                        "ok": True,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"INFO: {info.rule}  {info.evidence}")
        return 0

    snap = snapshot_memory(memory_root)
    findings = collect_findings(memory_root, snap)
    errors = sum(1 for f in findings if f.level == "ERROR")
    if args.json:
        print(
            json.dumps(
                {
                    "memory_root": str(memory_root),
                    "findings": [f.to_dict() for f in findings],
                    "stats": memory_stats(snap).to_dict(),
                    "error_count": errors,
                    "ok": errors == 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _render_text(memory_root, findings, memory_stats(snap))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

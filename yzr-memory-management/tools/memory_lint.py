#!/usr/bin/env python3
"""检查项目 MEMORY/：索引一致性、条目 scope、索引用量、敏感串、悬空声明；只报告不改写。"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

MEMORY_DIR = "MEMORY"
INDEX_NAME = "MEMORY.md"
AGENTS_NAME = "AGENTS.md"

# 上限与阈值的具体数值；md 侧以 assets/memory-{index,entry}-template.md 为准
INDEX_MAX_LINES = 200
INDEX_MAX_BYTES = 25600
BUDGET_HIGH_RATIO = 0.8
ENTRY_MAX_LINES = 120

ENTRY_LINK_RE = re.compile(r"^\s*-\s+\[(?P<title>[^\]]+)\]\((?P<slug>[^)\s/]+\.md)\)：")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# 契约：初始化引用段模板自带的 <!-- 包裹注释行含 @MEMORY/MEMORY.md 字样，刻意不算声明
MEMORY_REF_RE = re.compile(r"^@MEMORY/MEMORY\.md\b")
SENSITIVE_RES = (
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
)


class Finding(NamedTuple):
    """一条检查发现"""

    rule: str
    level: str
    evidence: str
    file: str = ""
    line: str = ""


class Stats(NamedTuple):
    """检查结果里的统计数字：索引用量与条目数，免人工计数"""

    index_lines: int
    index_budget_lines: int
    entry_count: int


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


def declares_memory(agents_path: Path) -> bool:
    """AGENTS.md 是否存在 @MEMORY/MEMORY.md 声明行；读不动按无声明处理，不为壳文件损坏另立判据"""
    try:
        text = agents_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return any(MEMORY_REF_RE.match(line.strip()) for line in text.splitlines())


def _index_findings(rel: str, text: str) -> Tuple[List[Finding], List[Tuple[int, str]]]:
    """检查索引：用量、头部残留、重复链接；返回 (findings, [(行号, slug)])"""
    findings: List[Finding] = []
    line_count = len(text.splitlines())
    if line_count > INDEX_MAX_LINES:
        findings.append(
            Finding(
                "INDEX-BUDGET",
                "ERROR",
                f"索引 {line_count} 行，超上限 {INDEX_MAX_LINES} 行——先精简再写入（合并摘要 / 短条目改写成文件条目 / 复查最旧条目）",
                file=rel,
            )
        )
    elif line_count >= int(INDEX_MAX_LINES * BUDGET_HIGH_RATIO):
        findings.append(
            Finding(
                "INDEX-BUDGET-HIGH",
                "WARN",
                f"索引 {line_count} 行，已达上限 {INDEX_MAX_LINES} 行的八成——写入前先备精简方案",
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
    head_open = True
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if head_open and stripped and not stripped.startswith("#"):
            head_open = False
            if not stripped.startswith("-"):
                findings.append(
                    Finding(
                        "INDEX-HEAD",
                        "WARN",
                        f"索引头部只允许标题与 ## 组名行，发现说明文字 / 模板残留：{stripped[:40]}"
                        "（格式规格在 skill 侧模板，项目不持副本）",
                        file=rel,
                        line=str(lineno),
                    )
                )
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
                f"条目 {entry_lines} 行，超 {ENTRY_MAX_LINES}——压缩或写进 docs / AGENTS.md、摘要里写明去处（超长多半是放错了位置）",
                file=rel,
            )
        )
    fm = parse_frontmatter(text) or {}
    findings += _frontmatter_findings(rel, fm)
    return findings


def _frontmatter_findings(rel: str, fm: Dict) -> List[Finding]:
    """检查条目 scope：变更检查（scope × git 变更匹配）的预筛字段"""
    # scope 兼容旧条目的 metadata.scope 嵌套写法，旧格式条目在新检查下保持零 finding
    metadata = fm.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    scope = str(fm.get("scope", "") or "") or str(metadata.get("scope", "") or "")
    if not scope:
        return [
            Finding(
                "SCOPE-MISSING",
                "WARN",
                "缺 scope（--- 围栏 frontmatter 内）——变更检查会漏掉本条",
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
    # 判据是全文无有效字符；骨架零条目是合法首批（init 允许空着起步），不报
    if not snap.index_text.strip():
        findings.append(
            Finding(
                "INDEX-EMPTY",
                "WARN",
                f"{index_rel} 为空白文件——可从 assets/memory-index-template.md 重建（git 可恢复）",
                file=index_rel,
            )
        )
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
    """从快照汇总统计数字：索引行数（缺索引记 0）与条目数"""
    index_lines = len(snap.index_text.splitlines()) if snap.index_text is not None else 0
    return Stats(index_lines=index_lines, index_budget_lines=INDEX_MAX_LINES, entry_count=len(snap.entries))


def _print_finding(finding: Finding) -> None:
    """单条 finding 的一行渲染，两分支共用"""
    loc = f"{finding.file}:{finding.line}  " if finding.file else ""
    print(f"{finding.level}: {finding.rule}  {loc}{finding.evidence}")


def _render_text(memory_root: Path, findings: List[Finding], stats: Stats) -> None:
    """输出人类可读报告"""
    print(f"== MEMORY root: {memory_root} ==")
    if findings:
        for f in findings:
            _print_finding(f)
    else:
        print("  clean")
    print(f"STATS 索引 {stats.index_lines} / {stats.index_budget_lines} 行 · 条目 {stats.entry_count} 个")
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in ("ERROR", "WARN", "INFO")}
    errors = counts["ERROR"]
    print(f"\n{counts['ERROR']} ERROR, {counts['WARN']} WARN, {counts['INFO']} INFO — {'FAIL' if errors else 'PASS'}")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：定位 MEMORY/、读快照、跑检查、渲染、按 ERROR 定退出码"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="检查该目录下的 MEMORY/（默认当前目录）")
    args = parser.parse_args(argv)

    start = Path(args.root).resolve()
    memory_root = start if (start / MEMORY_DIR).is_dir() else None
    snap: Optional[Snapshot] = None
    if memory_root is None:
        findings = [Finding("NO-MEMORY", "INFO", "未发现 MEMORY/ 目录——需要建立记忆体系时走初始化入口")]
        agents_path = start / AGENTS_NAME
        if agents_path.is_file() and declares_memory(agents_path):
            findings.append(
                Finding(
                    "DANGLING-REF",
                    "ERROR",
                    f"{AGENTS_NAME} 声明了 @MEMORY/MEMORY.md 但 MEMORY/ 不存在——走初始化入口建骨架"
                    "（AGENTS.md 引用段已存在，按初始化跳过条件免改）",
                    file=AGENTS_NAME,
                )
            )
    else:
        snap = snapshot_memory(memory_root)
        findings = collect_findings(memory_root, snap)
    errors = sum(1 for f in findings if f.level == "ERROR")
    stats = memory_stats(snap) if snap is not None else None
    if memory_root is None:
        for f in findings:
            _print_finding(f)
    else:
        _render_text(memory_root, findings, stats)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

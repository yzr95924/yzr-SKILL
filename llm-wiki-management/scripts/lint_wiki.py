#!/usr/bin/env python3
"""
lint_wiki.py — deterministic 健康检查

跑 references/lint-checklist.md 的 §二（1-9 项）。
半定性检查（§三 10-14）由 agent 现场做。

用法：
  python3 lint_wiki.py [<WIKI_ROOT>] [--severity <LEVEL>] [--no-git]

--severity 过滤：error | warn | info | all（默认 all）
--no-git 跳过 raw/ 的 git status 检查（CI 或裸仓场景）

退出码：
- 0 = 全部指定严重性级别内无 finding
- 1 = 有 finding
- 2 = 运行错误
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

# 复用 ingest_diff 的轻量 frontmatter 解析
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_diff import parse_frontmatter_simple  # noqa: E402
from log_format import LOG_LINE_RE  # noqa: E402

VALID_TYPES = {"entity", "concept", "source", "comparison", "synthesis"}
WIKI_SUBDIRS = ("entities", "concepts", "sources", "comparisons", "syntheses")
MEMORY_SUBDIR = "MEMORY"
MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
EXTERNAL_URL_RE = re.compile(r"^(https?:|mailto:|//)")

# 严重性等级
SEV_RANK = {"error": 0, "warn": 1, "info": 2}


def is_external_url(url: str) -> bool:
    return bool(EXTERNAL_URL_RE.match(url.strip()))


def find_md_files(wiki_root: Path) -> Dict[str, List[Path]]:
    """收集所有 wiki/**/*.md，按 type 分类（用子目录名判定）

    MEMORY 子目录扫到独立的 'memory' 桶：走 frontmatter 校验但**不**强制 index 覆盖。
    """
    out = {
        "index": [],  # type: List[Path]
        "log": [],
        "entities": [],
        "concepts": [],
        "sources": [],
        "comparisons": [],
        "syntheses": [],
        "memory": [],
    }  # type: Dict[str, List[Path]]
    wiki_dir = wiki_root / "wiki"
    if not wiki_dir.is_dir():
        return out
    for sub in WIKI_SUBDIRS:
        d = wiki_dir / sub
        if d.is_dir():
            for p in sorted(d.glob("*.md")):
                out[sub].append(p)
    # MEMORY/ 单独扫：含 README.md + 其它 .md
    mem_dir = wiki_dir / MEMORY_SUBDIR
    if mem_dir.is_dir():
        for p in sorted(mem_dir.glob("*.md")):
            out["memory"].append(p)
    out["index"].append(wiki_dir / "index.md")
    out["log"].append(wiki_dir / "log.md")
    return out


def check_raw_immutable(wiki_root: Path, use_git: bool) -> List[str]:
    """1. raw/ 是否被改"""
    if not use_git:
        return []
    raw_dir = wiki_root / "raw"
    if not raw_dir.is_dir():
        return []
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "raw/"],
            cwd=str(wiki_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    if result.returncode != 0:
        # 不是 git 仓 / 没 raw/ 在 git 里——跳过
        return []
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not lines:
        return []
    return [f"raw-modified: raw/ 有 {len(lines)} 处未提交改动：{lines[0]}{' ...' if len(lines) > 1 else ''}"]


def check_frontmatter(wiki_root: Path) -> List[str]:
    """2. frontmatter 完整性 + 3. source/synthesis 的 sources 字段"""
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    # 合并所有非 index / log / MEMORY/README.md 页（MEMORY/README.md 是 reserved，不走 5 字段校验）
    content_pages = []
    for sub in WIKI_SUBDIRS:
        content_pages.extend(pages[sub])
    for p in pages["memory"]:
        # 跳过 MEMORY/README.md（reserved；只校验 type=memory 即可，字段不全不报错）
        if p.name == "README.md" and p.parent.name == MEMORY_SUBDIR:
            continue
        content_pages.append(p)
    # 跳过不存在的 index / log
    for p in content_pages:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter_simple(text)
        rel = p.relative_to(wiki_root).as_posix()
        # 必填字段
        for field in ("title", "type", "created", "updated", "tags"):
            if field not in fm:
                findings.append(f"missing-frontmatter: {rel} 缺 '{field}' 字段")
        # type 合法
        t = fm.get("type")
        if t is not None and t not in VALID_TYPES:
            findings.append(f"invalid-type: {rel} type='{t}' 非法；应为 {sorted(VALID_TYPES)} 之一")
        # source / synthesis 的 sources 必填且非空
        if t in ("source", "synthesis"):
            srcs = fm.get("sources", [])
            if not isinstance(srcs, list) or not srcs:
                findings.append(f"missing-sources: {rel} type={t} 缺 'sources' 字段或为空")
            else:
                # 对 source 页：每个 src 必须是 raw/ 下现存路径
                if t == "source":
                    for s in srcs:
                        if not isinstance(s, str):
                            continue
                        sp = (wiki_root / s).resolve()
                        try:
                            sp.relative_to(wiki_root.resolve())
                        except ValueError:
                            findings.append(f"sources-out-of-root: {rel} sources[0]='{s}'不在 wiki 根下")
                            continue
                        if not sp.is_file():
                            findings.append(f"sources-missing: {rel} sources[0]='{s}'但文件不存在")
    return findings


def resolve_link(base: Path, link: str) -> Optional[Path]:
    """把 Markdown 链接解析为绝对路径；外部 URL / 锚点返回 None"""
    link = link.strip()
    # 去掉锚点
    link = link.split("#", 1)[0]
    # 去掉 query
    link = link.split("?", 1)[0]
    if not link:
        return None
    if is_external_url(link):
        return None
    # 相对路径
    target = (base.parent / link).resolve()
    return target


def check_link_integrity(wiki_root: Path) -> List[str]:
    """4. 路径引用完整性"""
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    all_pages = []
    for sub in WIKI_SUBDIRS + ("index", "log", "memory"):
        all_pages.extend(pages[sub])
    for p in all_pages:
        if not p.is_file():
            continue
        rel = p.relative_to(wiki_root).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in MD_LINK_RE.finditer(text):
            url = m.group(2)
            target = resolve_link(p, url)
            if target is None:
                continue
            # 只检查 wiki 范围内的链接（raw/ 下的图不在范围）
            try:
                target.relative_to(wiki_root.resolve() / "wiki")
            except ValueError:
                continue
            if not target.is_file():
                findings.append(
                    f"broken-link: {rel} 引用 '{url}' 解析为 {target.relative_to(wiki_root).as_posix()}，但文件不存在"
                )
    return findings


def check_index_coverage(wiki_root: Path) -> List[str]:
    """5. index.md 覆盖"""
    findings = []  # type: List[str]
    index_path = wiki_root / "wiki" / "index.md"
    if not index_path.is_file():
        return ["index-missing: wiki/index.md 不存在"]
    index_text = index_path.read_text(encoding="utf-8", errors="replace")
    # 收集 index 引用的所有相对路径
    indexed = set()  # type: Set[str]
    for m in MD_LINK_RE.finditer(index_text):
        url = m.group(2)
        target = resolve_link(index_path, url)
        if target is None:
            continue
        try:
            rel = target.relative_to(wiki_root).as_posix()
        except ValueError:
            continue
        indexed.add(rel)
    # 找所有非 index / log 的页面
    pages = find_md_files(wiki_root)
    for sub in WIKI_SUBDIRS:
        for p in pages[sub]:
            if not p.is_file():
                continue
            rel = p.relative_to(wiki_root).as_posix()
            if rel not in indexed:
                findings.append(f"orphan-page: {rel} 未在 wiki/index.md 中列出")
    return findings


def check_log_format(wiki_root: Path) -> List[str]:
    """6. log.md 格式"""
    findings = []  # type: List[str]
    log_path = wiki_root / "wiki" / "log.md"
    if not log_path.is_file():
        return ["log-missing: wiki/log.md 不存在"]
    text = log_path.read_text(encoding="utf-8", errors="replace")
    # 跳过 frontmatter
    body_start = 0
    if text.startswith("---"):
        m = re.match(r"^---\n.*?\n---\n?", text, re.DOTALL)
        if m:
            body_start = m.end()
    body = text[body_start:]
    for i, line in enumerate(body.splitlines(), start=1):
        if not line.strip():
            continue
        if line.startswith("## "):
            if not LOG_LINE_RE.match(line):
                findings.append(
                    f"log-format: wiki/log.md 第 {i} 行格式不合规：'{line[:60]}{'...' if len(line) > 60 else ''}'"
                )
    return findings


def check_stale_summaries(wiki_root: Path, threshold_days: int = 90) -> List[str]:
    """7. 过期摘要"""
    findings = []  # type: List[str]
    sources_dir = wiki_root / "wiki" / "sources"
    if not sources_dir.is_dir():
        return findings
    today = date.today()
    for p in sources_dir.glob("*.md"):
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter_simple(text)
        updated = fm.get("updated")
        if not isinstance(updated, str):
            continue
        try:
            upd_date = date.fromisoformat(updated)
        except ValueError:
            continue
        age = (today - upd_date).days
        if age > threshold_days:
            rel = p.relative_to(wiki_root).as_posix()
            findings.append(
                f"stale-summary: {rel} type=source updated={updated} ({age} 天前，超过 {threshold_days} 天阈值)"
            )
    return findings


def check_filename_kebab(wiki_root: Path) -> List[str]:
    """8. 文件名 kebab-case 规范"""
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    for sub in WIKI_SUBDIRS + ("index", "log"):
        for p in pages[sub]:
            stem = p.stem
            if not re.match(r"^[a-z0-9][a-z0-9-]*$", stem):
                rel = p.relative_to(wiki_root).as_posix()
                findings.append(
                    f"filename-not-kebab: {rel} 文件名 '{p.name}' 应使用 kebab-case（小写字母 + 数字 + 短横线）"
                )
    # MEMORY/* 走同一规则，但排除 README.md（reserved，大写不报错）
    for p in pages["memory"]:
        if p.name == "README.md" and p.parent.name == MEMORY_SUBDIR:
            continue
        stem = p.stem
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", stem):
            rel = p.relative_to(wiki_root).as_posix()
            findings.append(
                f"filename-not-kebab: {rel} 文件名 '{p.name}' 应使用 kebab-case（小写字母 + 数字 + 短横线）"
            )
    return findings


def check_duplicate_titles(wiki_root: Path) -> List[str]:
    """9. 重复标题"""
    findings = []  # type: List[str]
    title_to_files = {}  # type: Dict[str, List[str]]
    pages = find_md_files(wiki_root)
    for sub in WIKI_SUBDIRS:
        for p in pages[sub]:
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter_simple(text)
            title = fm.get("title")
            if not isinstance(title, str):
                continue
            rel = p.relative_to(wiki_root).as_posix()
            title_to_files.setdefault(title, []).append(rel)
    for title, files in title_to_files.items():
        if len(files) > 1:
            findings.append(f"duplicate-title: '{title}' 出现在 {len(files)} 个页面：{', '.join(files)}")
    return findings


def severity_of(finding: str) -> str:
    """从 finding 的类别前缀推断严重性"""
    if finding.startswith(
        (
            "raw-modified",
            "missing-frontmatter",
            "invalid-type",
            "sources-missing",
            "sources-out-of-root",
            "broken-link",
            "orphan-page",
            "index-missing",
            "log-missing",
        )
    ):
        return "error"
    if finding.startswith(("stale-summary", "log-format", "filename-not-kebab", "duplicate-title")):
        return "warn"
    return "info"


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic health check for a local LLM wiki.")
    parser.add_argument("wiki_root", nargs="?", help="wiki 根目录；默认从 $LLM_WIKI_ROOT 读")
    parser.add_argument(
        "--severity", choices=["error", "warn", "info", "all"], default="all", help="过滤输出严重性（默认 all）"
    )
    parser.add_argument("--no-git", action="store_true", help="跳过 raw/ 的 git status 检查")
    args = parser.parse_args()

    if args.wiki_root:
        wiki_root = Path(args.wiki_root).expanduser().resolve()
    elif os.environ.get("LLM_WIKI_ROOT"):
        wiki_root = Path(os.environ["LLM_WIKI_ROOT"]).expanduser().resolve()
    else:
        print("ERROR: 需提供 wiki_root 参数或设置 $LLM_WIKI_ROOT", file=sys.stderr)
        return 2

    if not (wiki_root / "wiki").is_dir():
        print(f"ERROR: {wiki_root}/wiki 不存在（wiki 还没 setup？）", file=sys.stderr)
        return 2

    # 跑所有检查
    all_findings = []  # type: List[str]
    all_findings.extend(check_raw_immutable(wiki_root, not args.no_git))
    all_findings.extend(check_frontmatter(wiki_root))
    all_findings.extend(check_link_integrity(wiki_root))
    all_findings.extend(check_index_coverage(wiki_root))
    all_findings.extend(check_log_format(wiki_root))
    all_findings.extend(check_stale_summaries(wiki_root))
    all_findings.extend(check_filename_kebab(wiki_root))
    all_findings.extend(check_duplicate_titles(wiki_root))

    # 过滤
    if args.severity != "all":
        threshold = SEV_RANK[args.severity]
        all_findings = [f for f in all_findings if SEV_RANK[severity_of(f)] <= threshold]

    # 输出
    if not all_findings:
        print("No issues found. ✓")
        return 0

    # 按严重性分组
    by_sev = {"error": [], "warn": [], "info": []}  # type: Dict[str, List[str]]
    for f in all_findings:
        by_sev[severity_of(f)].append(f)

    for sev in ("error", "warn", "info"):
        if by_sev[sev]:
            print(f"\n[{sev.upper()}] ({len(by_sev[sev])})")
            for f in by_sev[sev]:
                print(f"  {f}")

    print()
    print(f"Total: {len(all_findings)} finding(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())

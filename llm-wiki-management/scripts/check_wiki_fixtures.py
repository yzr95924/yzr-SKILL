#!/usr/bin/env python3
"""check_wiki_fixtures.py — 0.18.0+ fixtures 一致性检查（升级时专用）

按 wiki-spec §三 + lint-checklist §五的 fixture 视角，校验一个已存在 wiki 的"约定文件"
（AGENTS.md / CLAUDE.md / .gitignore / wiki/index.md / wiki/log.md / wiki/tags.md /
MEMORY/MEMORY.md / scripts/SCRIPTS.md / raw/external/.symlink-anchor.toml）是否满足
当前 wiki spec 的结构要求。本脚本只校验**结构性字节合规**；语义合并（frontmatter 字段
升级 / index 重复条目 / 多 MEMORY 条目归并等）由 lint-checklist §五 + LLM agent 走
migration plan 时的语义合并规则处理——本脚本不替代。

用法:
  python3 check_wiki_fixtures.py [<WIKI_ROOT>] [--json] [--target-spec <semver>]

缺省 --target-spec 时读 SKILL.md metadata.wiki_spec_version 作为"目标 spec"。
standalone（不依赖 lint_wiki.py）；自身合法 TOML 解析，不依赖 tomli/tomllib。

退出码:
  0 = 全部 check pass (或仅 skip)
  1 = 至少一条 check fail
  2 = 运行错误（路径 / 参数 / 文件 IO）

设计权衡:
- 该脚本不写文件，也不进 .migration-plan.json（那是 lint_wiki.py --check-version
  落盘并 call 它的活）；standalone 调用方只能看到 stdout/JSON 报告。
- 10 条 check 一次性写完，下一个 wiki spec 升级只需新增 register 条目。
- 复用 lint_wiki 的 WIKI_SUBDIRS / MEMORY_SUBDIR / EXTERNAL_SUBDIR 常量名（SSOT
  在 lint_wiki.py；本脚本硬编码确保 vendored 副本仍能跑）。
"""
from __future__ import absolute_import

import argparse
import json
import os
import re
import subprocess  # noqa: F401 — 仅在 _git_inside_work_tree / _git_field 里用
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# -- 复用 lint_wiki.py 常量名（保持 SSOT 一致；standalone 不依赖 lint_wiki.py import）--
WIKI_SUBDIRS = ("entities", "concepts", "sources", "comparisons", "syntheses")
MEMORY_SUBDIR = "MEMORY"
EXTERNAL_SUBDIR = "external"
ANCHOR_FILENAME = ".symlink-anchor.toml"  # 0.17.0+ TOML

# -- 公开 check 注册表（顺序 = 输出顺序）--
# 每条: severity (error/warn)、rule_ref（指向 spec/lint-checklist 段）、desc（人读摘要）
CHECK_REGISTRY = [
    {
        "id": "agents-version-is-current",
        "severity": "error",
        "rule_ref": "wiki-spec.md §10 + lint-checklist.md §三.1",
        "desc": "AGENTS.md §八 Wiki Spec 版本行需与 --target-spec 一致",
    },
    {
        "id": "gitignore-external-track-toml",
        "severity": "error",
        "rule_ref": "wiki-spec.md §13.4 + lint-checklist.md §三.3",
        "desc": ".gitignore 含 `raw/external/*` 排除 + `!raw/external/.symlink-anchor.toml` 跟踪；老 `**/.symlink-anchor.json` 残留即报错",
    },
    {
        "id": "symlink-anchor-toml-schema",
        "severity": "error",
        "rule_ref": "wiki-spec.md §13.2 + lint-checklist.md §三.3",
        "desc": "raw/external/.symlink-anchor.toml（若存在）：合法 TOML + [[entry]] 数组 + 每 entry 必填 4 字段 + git 仓时三扩展字段",
    },
    {
        "id": "symlink-anchor-toml-symlink-matches",
        "severity": "error",
        "rule_ref": "wiki-spec.md §13.1 + lint-checklist.md §三.3",
        "desc": "anchor 每个 [[entry]].symlink 对应 external/ 顶层同名 symlink；anchor 无对应 symlink / orphan symlink 一并检查",
    },
    {
        "id": "symlink-anchor-flat-not-legacy",
        "severity": "error",
        "rule_ref": "wiki-spec.md §13.6 + lint-checklist.md §三.3",
        "desc": "raw/external/ 不存在 <source-name>/ 子目录（0.17.0+ 扁平布局）",
    },
    {
        "id": "index-md-categories-stable",
        "severity": "warn",
        "rule_ref": "wiki-spec.md §3 + lint-checklist.md §三.4",
        "desc": "wiki/index.md 含 5 类别标题 (Entities / Concepts / Sources / Comparisons / Syntheses)",
    },
    {
        "id": "memory-index-no-frontmatter",
        "severity": "error",
        "rule_ref": "wiki-spec.md §5 + lint-checklist.md §三.5",
        "desc": "MEMORY/MEMORY.md（索引）不带 YAML frontmatter（被 AGENTS.md @import）",
    },
    {
        "id": "memory-entries-indexed",
        "severity": "error",
        "rule_ref": "wiki-spec.md §5.1 + lint-checklist.md §三.5",
        "desc": "MEMORY/*.md（除 MEMORY.md）每条都在 MEMORY/MEMORY.md 索引中列出",
    },
    {
        "id": "log-md-format-strict",
        "severity": "error",
        "rule_ref": "wiki-spec.md §4 + lint-checklist.md §三.6",
        "desc": "wiki/log.md 每行匹配 `^## [YYYY-MM-DD] (ingest|query|lint|setup) | .+$`",
    },
    {
        "id": "scripts-md-no-frontmatter",
        "severity": "error",
        "rule_ref": "wiki-spec.md §14 + lint-checklist.md §三.7",
        "desc": "scripts/SCRIPTS.md 不带 YAML frontmatter",
    },
    {
        "id": "tags-md-no-frontmatter",
        "severity": "error",
        "rule_ref": "wiki-spec.md §3 + lint-checklist.md §三.8",
        "desc": "wiki/tags.md 不带 YAML frontmatter",
    },
]

# -- 解析用正则 --
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
LOG_LINE_RE = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|setup) \| .+$")
AGENTS_VERSION_ROW_RE = re.compile(r"^\s*\|\s*Wiki Spec 版本\s*\|\s*([^|]+?)\s*\|")
INDEX_CATEGORY_RE = re.compile(r"^## (.+)$")
SOURCE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
GITIGNORE_TRACK_TOML_RE = re.compile(r"^!\s*raw/external/\.symlink-anchor\.toml\s*(#.*)?$")
GITIGNORE_TRACK_LEGACY_RE = re.compile(r"^!\s*raw/external/\*?/?\.symlink-anchor\.json\s*(#.*)?$")
GITIGNORE_EXCLUDE_EXTERNAL_RE = re.compile(r"^\s*raw/external/?\*?\s*(#.*)?$")
YAML_FRONT_MATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
CL_LLM_WIKI_ROOT = "LLM_WIKI_ROOT"


def _read_text(path: Path) -> Optional[str]:
    """读文件文本；失败返 None（不抛异常；fixture-check 静默容错）。"""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _skill_spec_version() -> Optional[str]:
    """读 SKILL.md metadata.wiki_spec_version（脚本相对路径）。

    找不到 / 解析失败返 None——Standalone 调用方用 --target-spec 显式传；该函数
    只在缺省 --target-spec 时作为 fallback。
    """
    # __file__ -> scripts/check_wiki_fixtures.py → ../SKILL.md
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    if not skill_md.is_file():
        return None
    text = _read_text(skill_md)
    if text is None:
        return None
    m = re.search(r"^[ \t]*wiki_spec_version:[ \t]*(\S+)[ \t]*$", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


def _compare_semver(a: Optional[str], b: Optional[str]) -> str:
    """返 'equal' / 'older' / 'newer' / 'unknown'。"""
    if not a or not b:
        return "unknown"

    def parse(v: str) -> Optional[Tuple[int, int, int]]:
        m = SEMVER_RE.search(v)
        if not m:
            return None
        try:
            return tuple(int(x) for x in m.group(0).split("."))  # type: ignore
        except ValueError:
            return None

    av, bv = parse(a), parse(b)
    if not av or not bv:
        return "unknown"
    if av < bv:
        return "older"
    if av > bv:
        return "newer"
    return "equal"


def _parse_anchor_minimal(anchor_path: Path) -> Optional[List[Dict[str, str]]]:
    """最小 TOML 解析——支持 [[entry]] 表 + key = "value" 双引号。

    与 lint_wiki.py _parse_anchor 同语义，独立以避免脚本间 import。返回 List[Dict]
    或 None（文件缺失 / 解析失败 / 无有效 entry）。
    """
    text = _read_text(anchor_path)
    if text is None:
        return None
    entries = []  # type: List[Dict[str, str]]
    current = None  # type: Optional[Dict[str, str]]
    for raw_line in text.splitlines():
        if "#" in raw_line:
            in_str = False
            cut = -1
            for i, ch in enumerate(raw_line):
                if ch == '"':
                    in_str = not in_str
                elif ch == "#" and not in_str:
                    cut = i
                    break
            if cut >= 0:
                raw_line = raw_line[:cut]
        stripped = raw_line.rstrip().strip()
        if not stripped:
            continue
        m = re.match(r"^\[\[(\w+)\]\]\s*$", stripped)
        if m:
            if current is not None:
                entries.append(current)
            current = {}
            continue
        m = re.match(r'^([a-z_]+)\s*=\s*"((?:[^"\\]|\\.)*)"\s*$', stripped)
        if m:
            key, raw_val = m.group(1), m.group(2)
            val = re.sub(
                r"\\(.)",
                lambda mo: {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    '"': '"',
                    "\\": "\\",
                }.get(mo.group(1), mo.group(1)),
                raw_val,
            )
            if current is not None:
                current[key] = val
            continue
        # 顶层标量（schema_version = 1 等）跳过
        m = re.match(r"^([a-z_]+)\s*=\s*([0-9]+|true|false)\s*$", stripped)
        if m:
            continue
        # 未知行 lenilent 跳过——返回上层按"无有效 entry"判定

    if current is not None:
        entries.append(current)

    valid = [e for e in entries if all(e.get(k) for k in ("symlink", "target", "captured_at")) and e.get("kind") == "external-repo"]
    return valid if valid else None


def _git_inside_work_tree(target_path: Path) -> bool:
    """target 是否在 git 仓内——失败返 False；不抛异常。"""
    try:
        out = subprocess.run(  # noqa: UP021
            ["git", "-C", str(target_path), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # noqa: UP022
            timeout=5,
        )
        return out.returncode == 0 and out.stdout.strip() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return False


def _git_field(target_path: Path, args: List[str]) -> Optional[str]:
    """跑 git -C <target> <args>，返 stdout.strip() 或 None。"""
    try:
        out = subprocess.run(  # noqa: UP021
            ["git", "-C", str(target_path)] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # noqa: UP022
            timeout=5,
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


# ============================================================================
# 各 check 函数定义——每个返 Dict { passed, severity, expected, actual, file, evidence }
# 约定：returned dict 至少有 "passed" (bool)；passed=False 时尽量附 "expected"/"actual"
# ============================================================================


def check_agents_version(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#1: AGENTS.md §八 spec 行与 --target-spec 一致"""
    target_spec = info.get("target_spec") or None
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": "AGENTS.md",
    }
    if target_spec is None:
        out["passed"] = None  # type: ignore
        out["skipped"] = "--target-spec 未提供；跳过版本对齐检查"
        return out

    # 从 AGENTS.md 抓行；若 AGENTS.md 不存在，fallback CLAUDE.md（pre-0.11.0 老 wiki 兼容）
    found_version = None
    source_file = None
    for candidate in ("AGENTS.md", "CLAUDE.md"):
        fpath = wiki_root / candidate
        text = _read_text(fpath)
        if text is None:
            continue
        for line in text.splitlines():
            m = AGENTS_VERSION_ROW_RE.match(line)
            if not m:
                continue
            cell = m.group(1).strip()
            semver = SEMVER_RE.search(cell)
            if semver:
                found_version = semver.group(0)
                source_file = candidate
            break
        if found_version is not None:
            break
    if found_version is None:
        out["passed"] = False  # type: ignore
        out["actual"] = "(无法解析 §八 Wiki Spec 版本行)"
        out["expected"] = target_spec
        return out
    out["file"] = source_file  # type: ignore
    cmp = _compare_semver(found_version, target_spec)
    if cmp != "equal":
        out["passed"] = False  # type: ignore
        out["actual"] = found_version
        out["expected"] = target_spec
        out["comparison"] = cmp  # type: ignore
    return out


def check_gitignore_external_track(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#2: .gitignore 含 raw/external/* 排除 + !raw/external/.symlink-anchor.toml 跟踪"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": ".gitignore",
    }
    text = _read_text(wiki_root / ".gitignore")
    if text is None:
        out["passed"] = None  # type: ignore
        out["skipped"] = ".gitignore 不存在"
        return out

    has_exclude = False
    has_track_toml = False
    has_legacy_json = False
    for line in text.splitlines():
        if GITIGNORE_EXCLUDE_EXTERNAL_RE.match(line):
            has_exclude = True
        if GITIGNORE_TRACK_TOML_RE.match(line):
            has_track_toml = True
        if GITIGNORE_TRACK_LEGACY_RE.match(line):
            has_legacy_json = True

    if has_legacy_json:
        out["passed"] = False  # type: ignore
        out["actual"] = "残留旧 `!raw/external/**/.symlink-anchor.json` 跟踪规则（0.17.0+ 退役）"
        out["expected"] = "!raw/external/.symlink-anchor.toml"
        out["rule_ref"] = "wiki-spec.md §13.6 迁移 + lint-checklist.md §三.3"
        return out
    if not has_exclude:
        out["passed"] = False  # type: ignore
        out["actual"] = "缺 `raw/external/*` 排除规则"
        out["expected"] = "raw/external/*\\n!raw/external/.symlink-anchor.toml"
        return out
    if not has_track_toml:
        out["passed"] = False  # type: ignore
        out["actual"] = "缺 `!raw/external/.symlink-anchor.toml` 跟踪规则"
        out["expected"] = "!raw/external/.symlink-anchor.toml"
        return out
    return out


def check_symlink_anchor_toml_schema(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#3: .symlink-anchor.toml（若存在）合法 + 必填字段齐 + git 仓时三扩展字段"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": f"raw/{EXTERNAL_SUBDIR}/{ANCHOR_FILENAME}",
    }
    anchor_path = wiki_root / "raw" / EXTERNAL_SUBDIR / ANCHOR_FILENAME
    if not anchor_path.exists():
        out["passed"] = None  # type: ignore
        out["skipped"] = "anchor 文件不存在（external/ 无 symlink 时可不建）"
        return out

    entries = _parse_anchor_minimal(anchor_path)
    if entries is None:
        out["passed"] = False  # type: ignore
        out["actual"] = "TOML 解析失败 / 无有效 [[entry]] / 必填字段缺失"
        out["expected"] = "schema_version = 1（顶层）+ 至少 1 个 [[entry]]（每 entry 含 symlink/target/captured_at/kind='external-repo'）"
        return out

    bad_entries = []  # type: List[str]
    missing_git = []  # type: List[str]
    for entry in entries:
        sym = entry.get("symlink", "<no-symlink>")
        target = entry.get("target", "")
        # 必填字段：parse 函数已保证 symlink/target/captured_at 非空 + kind='external-repo'
        # 此处额外核对 symlink 命名规则 + target 非空
        if not SOURCE_NAME_RE.match(sym):
            bad_entries.append(f"{sym}: 不合 kebab-case")
        if not target:
            bad_entries.append(f"{sym}: target 字段空")
        # git 仓时三字段必填
        expanded = Path(os.path.expanduser(target))
        if _git_inside_work_tree(expanded):
            for fld in ("remote_url", "commit", "branch"):
                if not entry.get(fld):
                    missing_git.append(f"{sym}: 缺 {fld}")
    if bad_entries:
        out["passed"] = False  # type: ignore
        out["actual"] = "; ".join(bad_entries)
        out["expected"] = "每 entry symlink 合 `^[a-z0-9][a-z0-9-]*$` + target 非空"
        return out
    if missing_git:
        out["passed"] = False  # type: ignore
        out["actual"] = "; ".join(missing_git)
        out["expected"] = "git 仓时 entry 必含 remote_url/commit/branch 三字段"
        return out
    return out


def check_symlink_anchor_toml_symlink_matches(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#4: anchor entry ↔ external/ 顶层 symlink 双向匹配"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": f"raw/{EXTERNAL_SUBDIR}/",
    }
    anchor_path = wiki_root / "raw" / EXTERNAL_SUBDIR / ANCHOR_FILENAME
    if not anchor_path.exists():
        out["passed"] = None  # type: ignore
        out["skipped"] = "anchor 文件不存在"
        return out

    external_dir = wiki_root / "raw" / EXTERNAL_SUBDIR
    if not external_dir.is_dir():
        out["passed"] = None  # type: ignore
        out["skipped"] = "raw/external/ 目录不存在"
        return out

    entries = _parse_anchor_minimal(anchor_path)
    if entries is None:
        # schema check 已报，此处跳过避免重复（passed=None）
        out["passed"] = None  # type: ignore
        out["skipped"] = "anchor 解析失败（已被 #3 报）"
        return out

    entry_symlinks = {e["symlink"] for e in entries if e.get("symlink")}
    real_symlinks = {p.name for p in external_dir.iterdir() if p.is_symlink()} if external_dir.is_dir() else set()

    orphan_entry = sorted(entry_symlinks - real_symlinks)  # anchor 有 entry 但 symlink 缺
    orphan_symlink = sorted(real_symlinks - entry_symlinks)  # symlink 有但 anchor 无 entry

    if orphan_entry or orphan_symlink:
        out["passed"] = False  # type: ignore
        out["actual"] = (
            f"anchor 缺 symlink: {orphan_entry}; " if orphan_entry else ""
        ) + (f"symlink 缺 entry: {orphan_symlink}" if orphan_symlink else "")
        out["expected"] = "anchor [[entry]].symlink 与 external/ 顶层 symlink 一一对应"
        return out
    return out


def check_symlink_anchor_flat(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#5: external/ 不存在 <source-name>/ 子目录（0.17.0+ 扁平）"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": f"raw/{EXTERNAL_SUBDIR}/",
    }
    external_dir = wiki_root / "raw" / EXTERNAL_SUBDIR
    if not external_dir.is_dir():
        out["passed"] = None  # type: ignore
        out["skipped"] = "raw/external/ 目录不存在"
        return out

    legacy_subdirs = []  # type: List[str]
    legacy_anchor_json = []  # type: List[str]
    for p in sorted(external_dir.iterdir()):
        # 实际子目录（非 symlink 跟随）= legacy 0.16.0- 形态
        if p.is_dir() and not p.is_symlink():
            legacy_subdirs.append(p.name + "/")
            # 子目录内若还有 .symlink-anchor.json，则更明确的标志
            if (p / ".symlink-anchor.json").exists():
                legacy_anchor_json.append(str(p.name) + "/.symlink-anchor.json")
        elif p.name == ".symlink-anchor.json" and not p.is_symlink():
            # 旧 anchor 文件直接放 external/ 顶层（变体，不规范）
            legacy_anchor_json.append(p.name)

    if legacy_subdirs or legacy_anchor_json:
        out["passed"] = False  # type: ignore
        msg_parts = []  # type: List[str]
        if legacy_subdirs:
            msg_parts.append(f"legacy 子目录: {legacy_subdirs}")
        if legacy_anchor_json:
            msg_parts.append(f"legacy anchor 文件: {legacy_anchor_json}")
        out["actual"] = "; ".join(msg_parts)
        out["expected"] = "扁平布局: symlink + .symlink-anchor.toml 直接在 external/ 顶层"
        return out
    return out


def check_index_md_categories(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#6: wiki/index.md 含 5 类别标题（顺序可调）"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "warn",
        "file": "wiki/index.md",
    }
    text = _read_text(wiki_root / "wiki" / "index.md")
    if text is None:
        out["passed"] = None  # type: ignore
        out["skipped"] = "wiki/index.md 不存在"
        return out
    found = set()  # type: Set[str]
    for line in text.splitlines():
        m = INDEX_CATEGORY_RE.match(line)
        if m:
            name = m.group(1).strip()
            if name in ("Entities", "Concepts", "Sources", "Comparisons", "Syntheses"):
                found.add(name)
    expected = {"Entities", "Concepts", "Sources", "Comparisons", "Syntheses"}
    missing = sorted(expected - found)
    if missing:
        out["passed"] = False  # type: ignore
        out["actual"] = f"缺类别: {missing}"
        out["expected"] = "5 类别齐全 (Entities / Concepts / Sources / Comparisons / Syntheses)"
        return out
    return out


def check_memory_index_no_frontmatter(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#7: MEMORY/MEMORY.md 不带 YAML frontmatter"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": f"{MEMORY_SUBDIR}/MEMORY.md",
    }
    text = _read_text(wiki_root / MEMORY_SUBDIR / "MEMORY.md")
    if text is None:
        out["passed"] = None  # type: ignore
        out["skipped"] = "MEMORY/MEMORY.md 不存在"
        return out
    # YAML frontmatter = 文件首行 `---` 紧跟块再以 `---` 闭合
    if YAML_FRONT_MATTER_RE.match(text):
        out["passed"] = False  # type: ignore
        out["actual"] = "文件以 `---` 起始（YAML frontmatter）"
        out["expected"] = "无 frontmatter（索引文件）"
        return out
    return out


def check_memory_entries_indexed(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#8: MEMORY/*.md 每条在 MEMORY.md 索引列出"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": f"{MEMORY_SUBDIR}/",
    }
    mem_dir = wiki_root / MEMORY_SUBDIR
    if not mem_dir.is_dir():
        out["passed"] = None  # type: ignore
        out["skipped"] = "MEMORY/ 目录不存在"
        return out
    memory_md_text = _read_text(mem_dir / "MEMORY.md")
    if memory_md_text is None:
        out["passed"] = None  # type: ignore
        out["skipped"] = "MEMORY/MEMORY.md 不存在"
        return out

    # 收集 MEMORY/ 下除 MEMORY.md 外所有 .md
    memory_entries = [p.name for p in sorted(mem_dir.glob("*.md")) if p.name != "MEMORY.md"]
    if not memory_entries:
        # 无经验条目 → 跳过；纯索引文件不算违规
        out["passed"] = None  # type: ignore
        out["skipped"] = "MEMORY/ 无经验条目"
        return out

    missing = []  # type: List[str]
    for entry in memory_entries:
        # 索引行匹配：以 stem 形式出现即可（链接 / slug / 路径均可）
        stem = entry[: -len(".md")] if entry.endswith(".md") else entry
        if (stem) not in memory_md_text:
            missing.append(entry)
    if missing:
        out["passed"] = False  # type: ignore
        out["actual"] = f"未索引: {missing}"
        out["expected"] = "MEMORY/MEMORY.md 含 `- [slug](slug.md)` 或 slug 字面量"
        return out
    return out


def check_log_md_format(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#9: wiki/log.md 每行匹配严格格式（仅 ## 一级 heading 行）"""
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": "wiki/log.md",
    }
    text = _read_text(wiki_root / "wiki" / "log.md")
    if text is None:
        out["passed"] = None  # type: ignore
        out["skipped"] = "wiki/log.md 不存在"
        return out
    bad_lines = []  # type: List[int]
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        # 仅检查 ## 一级 heading 行；其它行（续段落 / 描述）允许
        if line.lstrip().startswith("#"):
            if not LOG_LINE_RE.match(line):
                bad_lines.append(i)
    if bad_lines:
        out["passed"] = False  # type: ignore
        out["actual"] = f"不合规行: {bad_lines[:5]}{'... (前 5 行)' if len(bad_lines) > 5 else ''}"
        out["expected"] = "每行匹配 `^## [YYYY-MM-DD] (ingest|query|lint|setup) | .+$`"
        return out
    return out


def _check_no_frontmatter(file_path: Path) -> Dict[str, object]:
    """共用：检测文件首部是否存在 YAML frontmatter"""
    rel = file_path.name
    out = {  # type: Dict[str, object]
        "passed": True,
        "severity": "error",
        "file": rel,
    }
    text = _read_text(file_path)
    if text is None:
        out["passed"] = None  # type: ignore
        out["skipped"] = f"{rel} 不存在"
        return out
    if YAML_FRONT_MATTER_RE.match(text):
        out["passed"] = False  # type: ignore
        out["actual"] = "文件以 `---` 起始（YAML frontmatter）"
        out["expected"] = "无 frontmatter"
        return out
    return out


def check_scripts_md_no_frontmatter(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#10: scripts/SCRIPTS.md 不带 YAML frontmatter"""
    result = _check_no_frontmatter(wiki_root / "scripts" / "SCRIPTS.md")
    result["file"] = "scripts/SCRIPTS.md"
    return result


def check_tags_md_no_frontmatter(wiki_root: Path, info: Dict[str, str]) -> Dict[str, object]:
    """0.18.0 check#11: wiki/tags.md 不带 YAML frontmatter"""
    result = _check_no_frontmatter(wiki_root / "wiki" / "tags.md")
    result["file"] = "wiki/tags.md"
    return result


# ============================================================================
# 调度
# ============================================================================

CHECK_FUNCTIONS = [
    ("agents-version-is-current", check_agents_version),
    ("gitignore-external-track-toml", check_gitignore_external_track),
    ("symlink-anchor-toml-schema", check_symlink_anchor_toml_schema),
    ("symlink-anchor-toml-symlink-matches", check_symlink_anchor_toml_symlink_matches),
    ("symlink-anchor-flat-not-legacy", check_symlink_anchor_flat),
    ("index-md-categories-stable", check_index_md_categories),
    ("memory-index-no-frontmatter", check_memory_index_no_frontmatter),
    ("memory-entries-indexed", check_memory_entries_indexed),
    ("log-md-format-strict", check_log_md_format),
    ("scripts-md-no-frontmatter", check_scripts_md_no_frontmatter),
    ("tags-md-no-frontmatter", check_tags_md_no_frontmatter),
]


def run_checks(wiki_root: Path, target_spec: Optional[str]) -> Dict[str, object]:
    """跑全部 check；返 { wiki_root, target_spec, checks: [...], summary: {...} }"""
    info = {"wiki_root": str(wiki_root), "target_spec": target_spec or ""}
    checks_out = []  # type: List[Dict[str, object]]
    summary = {"error": 0, "warn": 0, "info": 0, "pass": 0, "skip": 0}  # type: Dict[str, int]
    for check_id, fn in CHECK_FUNCTIONS:
        reg = next(c for c in CHECK_REGISTRY if c["id"] == check_id)
        result = fn(wiki_root, info)
        # 统一字段 schema
        passed = result.get("passed")  # type: Optional[bool]
        severity = reg["severity"]
        if passed is True:
            summary["pass"] += 1
        elif passed is False:
            if severity == "error":
                summary["error"] += 1
            elif severity == "warn":
                summary["warn"] += 1
            else:
                summary["info"] += 1
        else:
            # passed is None → skipped
            summary["skip"] += 1
        entry = {
            "id": check_id,
            "file": result.get("file", ""),
            "passed": passed,
            "severity": severity,
            "rule_ref": reg["rule_ref"],
            "desc": reg["desc"],
            "expected": result.get("expected", ""),
            "actual": result.get("actual", ""),
            "skipped": result.get("skipped", ""),
            "comparison": result.get("comparison", ""),
        }
        checks_out.append(entry)
    return {
        "wiki_root": str(wiki_root),
        "target_spec": target_spec,
        "checks": checks_out,
        "summary": summary,
    }


def _format_human(report: Dict[str, object]) -> str:
    """人读报告（默认输出）。"""
    lines = []  # type: List[str]
    lines.append("=== Wiki fixtures 一致性检查（0.18.0+）===")
    lines.append(f"  wiki_root     : {report['wiki_root']}")
    lines.append(f"  target_spec   : {report['target_spec'] or '(未指定)'}")
    s = report["summary"]  # type: ignore
    lines.append(
        f"  error={s['error']} warn={s['warn']} info={s['info']} "
        f"pass={s['pass']} skip={s['skip']}"  # type: ignore
    )
    lines.append("")
    for c in report["checks"]:  # type: ignore
        passed = c.get("passed")  # type: ignore
        cid = c["id"]  # type: ignore
        sev = c["severity"].upper()  # type: ignore
        fpath = c["file"]  # type: ignore
        if passed is True:
            tag = "✓"
        elif passed is False:
            tag = "✗"
        else:
            tag = "·"
        lines.append(f"[{tag}] [{sev}] {cid} ({fpath})")
        if c.get("rule_ref"):  # type: ignore
            lines.append(f"        规则: {c['rule_ref']}")  # type: ignore
        if passed is False:
            if c.get("expected"):  # type: ignore
                lines.append(f"        期望: {c['expected']}")  # type: ignore
            if c.get("actual"):  # type: ignore
                lines.append(f"        实际: {c['actual']}")  # type: ignore
        elif passed is None and c.get("skipped"):  # type: ignore
            lines.append(f"        skip: {c['skipped']}")  # type: ignore
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="check_wiki_fixtures",
        description="0.18.0+ 检查已存在 wiki 的 fixtures 一致性（升级检查专用）",
    )
    parser.add_argument("wiki_root", nargs="?", help="wiki 根目录；默认从 $LLM_WIKI_ROOT 读")
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出机器可读 JSON 而不是人读报告",
    )
    parser.add_argument(
        "--target-spec",
        default=None,
        help="目标 wiki spec 版本（缺省读 SKILL.md metadata.wiki_spec_version）",
    )
    args = parser.parse_args()

    if args.wiki_root:
        wiki_root = Path(args.wiki_root).expanduser().resolve()
    elif os.environ.get(CL_LLM_WIKI_ROOT):
        wiki_root = Path(os.environ[CL_LLM_WIKI_ROOT]).expanduser().resolve()
    else:
        print("ERROR: 需提供 wiki_root 参数或设置 $LLM_WIKI_ROOT", file=sys.stderr)
        return 2

    if not wiki_root.is_dir():
        print(f"ERROR: {wiki_root} 不是目录", file=sys.stderr)
        return 2

    target_spec = args.target_spec or _skill_spec_version()

    report = run_checks(wiki_root, target_spec)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_format_human(report))

    # 退出码：error > warn > pass/skip
    s = report["summary"]  # type: ignore
    if s["error"] > 0:  # type: ignore
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

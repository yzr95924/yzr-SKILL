#!/usr/bin/env python3
"""Screen skills for mutual references (candidate cycles)."""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import (  # noqa: E402
    ERROR_REPO_ROOT,
    SKILL_SOURCE_SUBDIRS,
    discover_skill_dirs,
    json_text,
    parse_skill_md,
)


def discover_named_skills(repo_root: Path) -> List[Tuple[str, Path]]:
    """返回 repo 下可解析 skill 的 (name, 目录) 列表。"""
    skills: List[Tuple[str, Path]] = []
    for child in discover_skill_dirs(repo_root, require_parseable=True):
        name = parse_skill_md(child)[0]
        skills.append((name, child))
    return skills


def find_mentions(text: str, target_name: str) -> List[Tuple[int, str]]:
    """找出以词边界出现的 target_name，返回 (行号, 行内容)。"""
    pattern = re.compile(r"(?<![a-z0-9-])" + re.escape(target_name) + r"(?![a-z0-9-])")
    hits: List[Tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            hits.append((lineno, line.strip()))
    return hits


SOURCE_SUFFIXES = (".md", ".py")


def skill_sources(skill_dir: Path) -> List[Tuple[str, str]]:
    """一个 skill 参与提及筛查的全部文本源：(相对路径, 内容) 列表。"""
    # 只读 SKILL.md 会漏掉 ref/ 与脚本里的跨 skill 提及（经脚本消息、文档转交的环测不到）
    files: List[Path] = []
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        files.append(skill_md)
    for sub in SKILL_SOURCE_SUBDIRS:
        sub_root = skill_dir / sub
        if sub_root.is_dir():
            files.extend(sorted(p for p in sub_root.rglob("*") if p.is_file() and p.suffix in SOURCE_SUFFIXES))
    return [(str(p.relative_to(skill_dir)), p.read_text(encoding="utf-8", errors="replace")) for p in files]


def mentions_in(sources: List[Tuple[str, str]], target_name: str) -> List[Tuple[str, str]]:
    """在全部源里找提及，返回 (相对路径:行号, 行内容) 列表。"""
    hits: List[Tuple[str, str]] = []
    for rel, text in sources:
        for lineno, line in find_mentions(text, target_name):
            hits.append((f"{rel}:{lineno}", line))
    return hits


def scan(repo_root: Path) -> Dict:
    """扫互提对与单向提及，返回 JSON 友好 payload（verify 进程内直调，不经 stdout）。"""
    by_name: Dict[str, Path] = {}
    for name, skill_dir in discover_named_skills(repo_root):
        by_name.setdefault(name, skill_dir)
    names = sorted(by_name)
    sources: Dict[str, List[Tuple[str, str]]] = {name: skill_sources(by_name[name]) for name in names}

    edges: Dict[str, List[str]] = {a: [b for b in names if b != a and mentions_in(sources[a], b)] for a in names}
    pairs: List[Tuple[str, str]] = [
        (a, b) for i, a in enumerate(names) for b in names[i + 1 :] if b in edges[a] and a in edges[b]
    ]
    mutual_set = {frozenset((a, b)) for a, b in pairs}
    one_way: List[Tuple[str, str]] = [(a, b) for a in names for b in edges[a] if frozenset((a, b)) not in mutual_set]

    return {
        "repo_root": str(repo_root),
        "skill_count": len(sources),
        "skill_dirs": {name: by_name[name].name for name in names},
        "pairs": [
            {
                "a": a,
                "b": b,
                "a_mentions_b": mentions_in(sources[a], b),
                "b_mentions_a": mentions_in(sources[b], a),
            }
            for a, b in pairs
        ],
        "one_way": [{"a": a, "b": b, "a_mentions_b": mentions_in(sources[a], b)} for a, b in one_way],
    }


def _render_text(payload: Dict) -> None:
    """输出人类可读报告。"""
    pairs, one_way = payload["pairs"], payload["one_way"]
    dirs = payload["skill_dirs"]
    print(f"Scanning {payload['skill_count']} skill(s) under {payload['repo_root']}")
    if not pairs:
        print("No mutual-mention pairs found.")
    else:
        print(
            f"Found {len(pairs)} mutual-mention pair(s) — review whether each "
            "is a real cycle (互提 ≠ 互依；分工转交 / 风格对齐是良性的):\n"
        )
        for edge in pairs:
            a, b = edge["a"], edge["b"]
            print(f"== {a}  <->  {b} ==")
            for src, dst in ((a, b), (b, a)):
                hits = edge["a_mentions_b"] if src == a else edge["b_mentions_a"]
                print(f"  [{src} -> {dst}]")
                for loc, line in hits:
                    print(f"    {dirs[src]}/{loc}: {line}")
            print("")

    if one_way:
        print(
            f"\n{len(one_way)} one-directional mention(s) (info — every mention must justify "
            "itself: real functional dependency = keep explicit; anything else = vague it down "
            "to the skill name or delete; baseline expectation is zero):\n"
        )
        for edge in one_way:
            a, b = edge["a"], edge["b"]
            print(f"  [{a} -> {b}]")
            for loc, line in edge["a_mentions_b"]:
                print(f"    {dirs[a]}/{loc}: {line}")
            print("")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：扫描互提对与单向提及；有互提对时退出码 1。"""
    parser = argparse.ArgumentParser(description="Screen skills for mutual (potentially cyclic) references.")
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=None,
        help="repository root to scan (default: this skill's repo root)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    if not repo_root.is_dir():
        print(f"{ERROR_REPO_ROOT}: {repo_root}", file=sys.stderr)
        return 2

    payload = scan(repo_root)
    if args.json:
        print(json_text(payload))
    else:
        _render_text(payload)
    return 1 if payload["pairs"] else 0


if __name__ == "__main__":
    sys.exit(main())

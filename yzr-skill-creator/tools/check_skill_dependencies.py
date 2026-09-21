#!/usr/bin/env python3
"""Screen skills for mutual references (candidate cycles)."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import discover_skill_dirs, parse_skill_md  # noqa: E402


def discover_skills(repo_root: Path) -> List[Tuple[str, Path]]:
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


def _render_json(
    repo_root: Path, pairs: List[Tuple[str, str]], one_way: List[Tuple[str, str]], texts: Dict[str, str]
) -> None:
    """输出整份 JSON 报告。"""
    payload = {
        "repo_root": str(repo_root),
        "skill_count": len(texts),
        "pairs": [
            {
                "a": a,
                "b": b,
                "a_mentions_b": find_mentions(texts[a], b),
                "b_mentions_a": find_mentions(texts[b], a),
            }
            for a, b in pairs
        ],
        "one_way": [{"a": a, "b": b, "a_mentions_b": find_mentions(texts[a], b)} for a, b in one_way],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _render_text(
    repo_root: Path,
    pairs: List[Tuple[str, str]],
    one_way: List[Tuple[str, str]],
    by_name: Dict[str, Path],
    texts: Dict[str, str],
) -> None:
    """输出人类可读报告。"""
    print(f"Scanning {len(texts)} skill(s) under {repo_root}")
    if not pairs:
        print("No mutual-mention pairs found.")
    else:
        print(
            f"Found {len(pairs)} mutual-mention pair(s) — review whether each "
            "is a real cycle (互提 ≠ 互依；分工转交 / 风格对齐是良性的):\n"
        )
        for a, b in pairs:
            print(f"== {a}  <->  {b} ==")
            print(f"  [{a} -> {b}]")
            for lineno, line in find_mentions(texts[a], b):
                print(f"    {by_name[a].name}/SKILL.md:{lineno}: {line}")
            print(f"  [{b} -> {a}]")
            for lineno, line in find_mentions(texts[b], a):
                print(f"    {by_name[b].name}/SKILL.md:{lineno}: {line}")
            print("")

    if one_way:
        print(
            f"\n{len(one_way)} one-directional mention(s) (info — every mention must justify "
            "itself: real functional dependency = keep explicit; anything else = blur to XX "
            "or delete; baseline expectation is zero):\n"
        )
        for a, b in one_way:
            print(f"  [{a} -> {b}]")
            for lineno, line in find_mentions(texts[a], b):
                print(f"    {by_name[a].name}/SKILL.md:{lineno}: {line}")
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
        print(f"error: repo root not found: {repo_root}", file=sys.stderr)
        return 2

    by_name: Dict[str, Path] = {}
    for name, skill_dir in discover_skills(repo_root):
        by_name.setdefault(name, skill_dir)
    names = sorted(by_name)
    texts: Dict[str, str] = {name: (by_name[name] / "SKILL.md").read_text() for name in names}

    edges: Dict[str, List[str]] = {a: [b for b in names if b != a and find_mentions(texts[a], b)] for a in names}
    pairs: List[Tuple[str, str]] = [
        (a, b) for i, a in enumerate(names) for b in names[i + 1 :] if b in edges[a] and a in edges[b]
    ]
    mutual_set = {frozenset((a, b)) for a, b in pairs}
    one_way: List[Tuple[str, str]] = [(a, b) for a in names for b in edges[a] if frozenset((a, b)) not in mutual_set]

    if args.json:
        _render_json(repo_root, pairs, one_way, texts)
    else:
        _render_text(repo_root, pairs, one_way, by_name, texts)
    return 1 if pairs else 0


if __name__ == "__main__":
    sys.exit(main())

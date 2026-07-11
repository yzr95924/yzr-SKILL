#!/usr/bin/env python3
"""
Detect mutual references between skills — a candidate screen for
bidirectional (cyclic) dependencies.

A skill "mentions" another when the other skill's frontmatter `name` appears
anywhere in its SKILL.md (the description counts too — division-of-labor
handoffs often live there). Two skills that mention each other are flagged as
a *candidate* pair. Whether a pair is a real dependency cycle or benign
division of labor (e.g. the yzr-outline-wiki-setup/search/upload trio handing
work off to each other) is a semantic call this script does NOT make — it only
narrows the search to candidate pairs and prints the evidence lines, so a
human can judge direction.

Why a screen and not a verdict: skills in this repo declare dependencies
through prose (there is no frontmatter `dependencies` field — it was tried and
removed). Prose direction is hard to detect mechanically, but "who mentions
whom" is cheap and exact, and any real cycle must surface as a mutual mention.
High recall, human precision.

Usage:
    python3 check_skill_dependencies.py [<repo-root>] [--json]

Exit code: 0 = no mutual-mention pairs; 1 = at least one pair found.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap so `from scripts.utils import ...` works both as a standalone
# script and as `python -m scripts.check_skill_dependencies`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import parse_skill_md  # noqa: E402


def discover_skills(repo_root: Path) -> List[Tuple[str, Path]]:
    """Return [(name, skill_dir)] for each direct subdir of repo_root whose
    SKILL.md parses to a non-empty kebab-case name."""
    skills: List[Tuple[str, Path]] = []
    for child in sorted(repo_root.iterdir()):
        skill_md = child / "SKILL.md"
        if not child.is_dir() or not skill_md.is_file():
            continue
        try:
            name, _desc, _content = parse_skill_md(child)
        except (ValueError, OSError):
            continue
        name = name.strip()
        # kebab-case sanity — skip dirs that aren't real skills
        if not re.match(r"^[a-z0-9-]+$", name):
            continue
        skills.append((name, child))
    return skills


def find_mentions(text: str, target_name: str) -> List[Tuple[int, str]]:
    """Lines (1-based number, stripped text) where target_name appears as a
    whole token — not a substring of a longer kebab-case identifier."""
    # name chars are [a-z0-9-]; a real mention is bounded by non-name chars on
    # both sides, so "yzr-outline-wiki-search" won't match inside
    # "yzr-outline-wiki-searchable".
    pattern = re.compile(r"(?<![a-z0-9-])" + re.escape(target_name) + r"(?![a-z0-9-])")
    hits: List[Tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            hits.append((lineno, line.strip()))
    return hits


def main(argv: Optional[List[str]] = None) -> int:
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

    # Dedupe by frontmatter name (dir name vs name can mismatch); keep first.
    by_name: Dict[str, Path] = {}
    for name, skill_dir in discover_skills(repo_root):
        by_name.setdefault(name, skill_dir)
    names = sorted(by_name)
    texts: Dict[str, str] = {name: (by_name[name] / "SKILL.md").read_text() for name in names}

    # Directed mention edges: edges[A] = [B, ...] that A's text mentions.
    edges: Dict[str, List[str]] = {a: [b for b in names if b != a and find_mentions(texts[a], b)] for a in names}

    # Mutual pairs (A mentions B and B mentions A); a < b avoids duplicates.
    pairs: List[Tuple[str, str]] = [
        (a, b) for i, a in enumerate(names) for b in names[i + 1 :] if b in edges[a] and a in edges[b]
    ]

    if args.json:
        payload = {
            "repo_root": str(repo_root),
            "skill_count": len(names),
            "pairs": [
                {
                    "a": a,
                    "b": b,
                    "a_mentions_b": find_mentions(texts[a], b),
                    "b_mentions_a": find_mentions(texts[b], a),
                }
                for a, b in pairs
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Scanning {len(names)} skill(s) under {repo_root}")
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

    return 1 if pairs else 0


if __name__ == "__main__":
    sys.exit(main())

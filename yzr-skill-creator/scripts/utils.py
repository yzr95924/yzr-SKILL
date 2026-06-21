"""Shared utilities for skill-creator scripts."""

from pathlib import Path
from typing import List, Tuple

# Description length hard limit, in characters. Single source of truth for this metric:
# quick_validate.py enforces it, improve_description.py rewrites over-long descriptions
# against it. The human-facing statement lives in references/skill-writing-principles.md
# ("指标单一来源" 原则) — change the limit here and code updates everywhere.
DESCRIPTION_MAX_CHARS = 1024


def parse_skill_md(skill_path: Path) -> Tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text()
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:") :].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:") :].strip()
            # 续行场景：显式 YAML 块标量指示符（>, |, >-, |-）
            # 或裸 `description:`（无值）后接缩进续行（隐式 plain 多行）。
            # 两种形式都把后续缩进行收集起来，拼成单行描述。
            if value in ("", ">", "|", ">-", "|-"):
                continuation_lines: List[str] = []
                i += 1
                while i < len(frontmatter_lines) and (
                    frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")
                ):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content

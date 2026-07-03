#!/usr/bin/env python3
"""
Step 0 前置检查：报告一个 Claude Code 项目是否就绪可重构成「AGENTS.md 单一真源 + CLAUDE.md
薄壳共存」结构。

用法：
    python3 scripts/precheck.py [project-root]     # 默认 cwd

退出码：
    0  CLAUDE.md 就绪（即使有需用户确认的项也算通过——本脚只报告、不拦阻）
    1  硬阻塞（CLAUDE.md 缺失或为空，没有源可迁）
"""

import sys
from pathlib import Path
from typing import List, Tuple

# Bootstrap sys.path so `python3 -m scripts.precheck` (从 skill 根) 也能跑，
# 与 `python3 scripts/precheck.py`（独立）行为一致。本脚本无包内 import，
# bootstrap 仅保持调用形式一致。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check_project(root: Path) -> Tuple[List[str], bool]:
    """返回 (报告行列表, 是否就绪)。就绪 = CLAUDE.md 存在且非空。"""
    lines = []
    ready = True

    lines.append(f"项目根：{root}")
    if not root.is_dir():
        lines.append(f"  [硬阻塞] 项目根不是目录：{root}")
        return lines, False

    # 1. CLAUDE.md（硬阻塞）
    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        lines.append("  [硬阻塞] 未找到 CLAUDE.md——没有源可迁。")
        ready = False
    elif claude_md.stat().st_size == 0:
        lines.append("  [硬阻塞] CLAUDE.md 为空——没有源可迁。")
        ready = False
    else:
        lines.append(f"  [OK] CLAUDE.md 存在（{claude_md.stat().st_size} 字节）")

    # 2. MEMORY/（可选；不存在则 Step 4 跳过）
    memory = root / "MEMORY"
    if memory.is_dir():
        n = sum(1 for _ in memory.glob("*.md"))
        lines.append(f"  [OK] MEMORY/ 存在（{n} 个 .md）——Step 4 将一并去品牌化")
    else:
        lines.append("  [INFO] 无 MEMORY/ 目录——Step 4（MEMORY 改写）将跳过")

    # 3. AGENTS.md 已存在？（需用户确认覆盖）
    agents = root / "AGENTS.md"
    if agents.exists():
        lines.append("  [需确认] 已存在 AGENTS.md——Step 2 会覆盖，须先与用户确认")
    else:
        lines.append("  [OK] 无 AGENTS.md——Step 2 将新建")

    # 4. .qoder/rules/ 已存在且非空？（覆盖风险）
    rules = root / ".qoder" / "rules"
    if rules.is_dir():
        existing = list(rules.glob("*.md"))
        if existing:
            lines.append(
                f"  [需确认] .qoder/rules/ 已有 {len(existing)} 个 rule 文件——"
                f"Step 3 会覆盖同名 / 产生重复，须先与用户确认"
            )
        else:
            lines.append("  [OK] .qoder/rules/ 存在但为空")

    # 5. .migration-backup/ 已存在？（可能是上次运行残留）
    backup = root / ".migration-backup"
    if backup.exists():
        lines.append("  [INFO] .migration-backup/ 已存在——可能是上次迁移残留；Step 1 会刷新其中的 CLAUDE.md.original")

    # 6. .gitignore 是否忽略 .qoder/rules（信息性——本地不共享 rule 时需要）
    gitignore = root / ".gitignore"
    if gitignore.exists():
        text = gitignore.read_text(errors="replace")
        ignores_rules = ".qoder/rules" in text
        lines.append(
            "  [INFO] .gitignore 已忽略 .qoder/rules（rule 本地不共享）"
            if ignores_rules
            else "  [INFO] .gitignore 未忽略 .qoder/rules（rule 随 git 共享）"
        )

    return lines, ready


def main() -> int:
    root_str = "." if len(sys.argv) <= 1 else sys.argv[1]
    if len(sys.argv) > 2 or root_str in ("-h", "--help"):
        print("用法: python3 scripts/precheck.py [project-root]")
        return 2
    lines, ready = check_project(Path(root_str).resolve())
    print("\n[precheck] Step 0 前置检查")
    print("-" * 60)
    for ln in lines:
        print(ln)
    print("-" * 60)
    if ready:
        print("结论：可以进入 Step 1。带 [需确认] 的项先与用户确认再继续。")
        return 0
    print("结论：硬阻塞，无法迁移。请先准备 CLAUDE.md。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

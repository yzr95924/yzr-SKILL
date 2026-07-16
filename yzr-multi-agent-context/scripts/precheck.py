#!/usr/bin/env python3
"""
Step 0 前置检查 + 路径判定：报告项目状态并路由到两条归约路径之一（① CLAUDE.md 迁移 /
② 已有 AGENTS.md 规范化），统一收敛到「AGENTS.md 单一真源」。

裸项目（既无 CLAUDE.md 又无 AGENTS.md）不在本 skill 范围——请先用 agent 的 /init 生成初始上下文。

用法：
    python3 scripts/precheck.py [project-root]     # 默认 cwd

退出码：
    0  两条路径之一成立（即使有需用户确认的项也算通过——本脚只报告、不拦阻）
    1  硬阻塞（项目根无效，或既无 CLAUDE.md 又无 AGENTS.md——走 /init）
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Bootstrap sys.path so `python3 -m scripts.precheck` (从 skill 根) 也能跑，
# 与 `python3 scripts/precheck.py`（独立）行为一致。本脚本无包内 import，
# bootstrap 仅保持调用形式一致。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check_project(root: Path) -> Tuple[List[str], bool]:
    """返回 (报告行列表, 是否就绪)。就绪 = 有 CLAUDE.md 或 AGENTS.md 之一（路径 1 / 2 成立）。"""
    lines: List[str] = []
    ready = True

    lines.append(f"项目根：{root}")
    if not root.is_dir():
        lines.append(f"  [硬阻塞] 项目根不是目录：{root}")
        return lines, False

    # 1. 检测上下文文件 → 判定路径（裸项目硬阻塞，指向 /init）
    claude_md = root / "CLAUDE.md"
    agents = root / "AGENTS.md"
    has_claude = claude_md.exists() and claude_md.stat().st_size > 0
    has_agents = agents.exists() and agents.stat().st_size > 0

    if has_agents:
        lines.append(f"  [OK] AGENTS.md 存在（{agents.stat().st_size} 字节）")
        if has_claude:
            lines.append(f"  [OK] CLAUDE.md 并存（{claude_md.stat().st_size} 字节）")
            lines.append("  [路径 2] 已有 AGENTS.md（+CLAUDE.md）→ 规范化 + 合并存 CLAUDE.md，冲突让用户裁定")
        else:
            lines.append("  [路径 2] 已有 AGENTS.md（纯，无 CLAUDE.md）→ 规范化（去品牌残留 / 改记忆段为 @import）")
    elif has_claude:
        lines.append(f"  [OK] CLAUDE.md 存在（{claude_md.stat().st_size} 字节）")
        lines.append("  [路径 1] 有 CLAUDE.md 无 AGENTS.md → 去品牌迁移")
    else:
        lines.append("  [硬阻塞] 无 CLAUDE.md / AGENTS.md——裸项目不在本 skill 范围。")
        lines.append("           请先用 agent 的 /init 生成初始 CLAUDE.md / AGENTS.md，再来归约。")
        return lines, False

    # 2. MEMORY/（可选；不存在则 Step 3 跳过）
    memory = root / "MEMORY"
    if memory.is_dir():
        n = sum(1 for _ in memory.glob("*.md"))
        lines.append(f"  [OK] MEMORY/ 存在（{n} 个 .md）——Step 3 一并去品牌化")
        lines.append("  [INFO] L2 记忆索引走 AGENTS.md 顶部强制 Read 指令 + 单行 @MEMORY/MEMORY.md 引入")
        lines.append("         (自动展开 @import 的 agent 读入全文;不展开的按顶部指令 Read MEMORY/MEMORY.md)")
        # 检出 AGENTS.md 是否已挂记忆段（旧内联方案残留时 Step 2 顺带改）
        memory_index = memory / "MEMORY.md"
        if agents.exists() and memory_index.exists():
            text = agents.read_text(encoding="utf-8", errors="replace")
            if "@MEMORY/MEMORY.md" not in text:
                if re.search(r"^## 跨会话记忆", text, re.MULTILINE):
                    lines.append("  [提示] AGENTS.md 已有记忆段但未用 @MEMORY/MEMORY.md（老内联方案残留）")
                    lines.append("         → Step 2 / 路径 2 诊断会触发规范化（行 2-3）")
                else:
                    lines.append("  [提示] AGENTS.md 缺记忆段——Step 2 会追加 @MEMORY/MEMORY.md + 顶部强制 Read 指令")
    else:
        lines.append("  [INFO] 无 MEMORY/ 目录——Step 3 跳过")

    # 3. .migration-backup/ 已存在？（可能是上次运行残留）
    backup = root / ".migration-backup"
    if backup.exists():
        lines.append("  [INFO] .migration-backup/ 已存在——可能是上次残留；Step 1 会刷新源文件快照")

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
    print("结论：硬阻塞——无 CLAUDE.md / AGENTS.md。裸项目请先用 agent 的 /init 生成初始上下文再来。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""生成多模型评审卷宗：PACKET.md（被审代码全文 + 共享扫描候选 + 契约附章）。"""

import argparse
import datetime
import sys
import tempfile
from pathlib import Path
from typing import List

from dup_scan import DEFAULT_EXTS, Occurrence, iter_code_files, scan

SKILL_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_FILES = ("ref/reviewer.md", "ref/catalog.md")
# 内联的被审正文本身是含 3 反引号围栏的代码，外层用 4 反引号防嵌套碰撞
FENCE = "````"
MIN_LINES = 5
DEFAULT_OUT_ROOT = Path(tempfile.gettempdir())


def expand_paths(paths: List[str], label: str) -> List[Path]:
    """展开为文件列表（目录按代码扩展名递归并在 vendor 目录剪枝），去重保序；路径不存在直接退出。"""
    out: List[Path] = []
    for p in paths:
        t = Path(p)
        if not t.exists():
            sys.exit(f"ERROR: {label} 路径不存在: {p}")
        out.extend(iter_code_files([str(t)], DEFAULT_EXTS))
    seen, uniq = set(), []
    for f in out:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def manifest_row(path: Path) -> str:
    """清单行：绝对路径 + 行数。"""
    text = path.read_bytes().decode("utf-8", errors="replace")
    return f"| `{path}` | {len(text.splitlines())} |"


def format_occurrence(occ: Occurrence) -> str:
    """单个出现位置：file:line 或 file:start-end。"""
    span = str(occ.start) if occ.start == occ.end else f"{occ.start}-{occ.end}"
    return f"{occ.file}:{span}"


def dup_lines(files: List[Path]) -> str:
    """对被审文件跑 exact 与 fuzzy 两模式重复扫描，候选组渲染为共享列表行。"""
    lines: List[str] = []
    modes: List[tuple] = [("exact", False), ("fuzzy", True)]
    for label, fuzzy in modes:
        _, groups = scan([str(f) for f in files], DEFAULT_EXTS, MIN_LINES, fuzzy)
        for idx, g in enumerate(groups, 1):
            occs = "、".join(format_occurrence(o) for o in g.occurrences)
            lines.append(f"- [{label}] 组 {idx}：{len(g.occurrences)} 处出现，{g.lines} 行 —— {occs}")
    return "\n".join(lines) if lines else "- 无命中"


def fenced(text: str) -> str:
    """4 反引号围栏包裹整份正文（附章是 Markdown，被审代码同格式内联）。"""
    return f"{FENCE}markdown\n{text.rstrip()}\n{FENCE}"


def body_sections(files: List[Path]) -> str:
    """被审全文内联：每文件一个围栏块，评审员不再读盘。"""
    blocks = [f"### {f}\n\n{fenced(f.read_text(encoding='utf-8', errors='replace'))}" for f in files]
    return "## 被审代码全文\n\n" + "\n\n".join(blocks)


def contract_sections() -> str:
    """附章运行时现读 reviewer.md / catalog.md 拼接：SSOT 在源文件，卷宗是派生物。"""
    blocks = [f"### {rel}\n\n{fenced((SKILL_ROOT / rel).read_text(encoding='utf-8'))}" for rel in CONTRACT_FILES]
    return "## 契约附章（评审员契约与规则清单，随卷宗送达）\n\n" + "\n\n".join(blocks)


def build_packet(out_dir: Path, targets: List[Path]) -> Path:
    """生成 PACKET.md：全体评审员收到字节级相同的单文件，读盘与核验机制随之取消。"""
    rows = "\n".join(manifest_row(p) for p in targets)
    parts = [
        "# 多模型评审卷宗",
        "本卷宗是单名评审员的唯一输入：被审内容清单、机械扫描候选、被审代码全文、文末契约附章。"
        "评审员角色、评审立场与产物顺序见附章 ref/reviewer.md；评审员没有可用工具，一切以本卷宗为准。"
        "全体评审员收到的本文件字节级相同。",
        "## 被审内容清单",
        "| 路径 | 行数 |\n| --- | --- |\n" + rows,
        "## 机械扫描候选（全体评审员共享，勿重跑扫描）",
        f"dup_scan（连续 ≥ {MIN_LINES} 行归一化相同即入候选，报不报由评审员按规则裁）：\n\n{dup_lines(targets)}",
        body_sections(targets),
        contract_sections(),
    ]
    path = out_dir / "PACKET.md"
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return path


def main(argv: List[str] = None) -> int:
    """CLI 入口：建卷宗目录并生成 PACKET.md，打印两个路径。"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", nargs="+", required=True, help="reviewed code file(s) or dir(s)")
    parser.add_argument("--out", default="", help="packet dir (default: cr-<timestamp> under system temp)")
    args = parser.parse_args(argv)
    targets = expand_paths(args.target, "被审")
    if args.out:
        out_dir = Path(args.out)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        out_dir = Path(DEFAULT_OUT_ROOT) / f"cr-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    packet = build_packet(out_dir, targets)
    print(f"packet: {out_dir}")
    print(f"file: {packet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

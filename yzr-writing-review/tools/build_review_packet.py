#!/usr/bin/env python3
"""生成多模型评审卷宗：PACKET.md（被审全文 + 参照输入 + 共享扫描候选 + 契约附章）。"""

import argparse
import datetime
import sys
import tempfile
from pathlib import Path
from typing import List

from count_words import count_text
from scan_fingerprints import iter_targets, scan_text

SKILL_ROOT = Path(__file__).resolve().parent.parent
# SKILL.md 刻意不入附章：评审员是无工具的纯文本会话，SKILL.md 里编排者的 tools/ 命令曾诱导
# 评审员尝试调用（实测复现）；防线由 smoke_test_build_packet.py 的 SKILL.md 缺席断言钉死
CONTRACT_FILES = ("ref/reviewer.md", "ref/catalog.md")
# 内联的被审 / 附章正文本身是含 3 反引号围栏的 Markdown，外层用 4 反引号防嵌套碰撞
FENCE = "````"
DEFAULT_OUT_ROOT = Path(tempfile.gettempdir())


def expand_paths(paths: List[str], label: str) -> List[Path]:
    """展开为文件列表（目录递归 .md），去重保序；路径不存在直接退出。"""
    out: List[Path] = []
    for p in paths:
        t = Path(p)
        if not t.exists():
            sys.exit(f"ERROR: {label} 路径不存在: {p}")
        out.extend(f.resolve() for f in iter_targets(t))
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def manifest_row(path: Path) -> str:
    """清单行：绝对路径 + 非空白字数 + 行数。"""
    text = path.read_bytes().decode("utf-8", errors="replace")
    nchars, _ = count_text(text)
    return f"| `{path}` | {nchars} | {len(text.splitlines())} |"


def scan_lines(files: List[Path]) -> str:
    """对被审文件跑指纹扫描，命中渲染为共享候选列表行。"""
    lines: List[str] = []
    for f in files:
        text = f.read_bytes().decode("utf-8", errors="replace")
        for h in scan_text(text, str(f)):
            lines.append(f"- {h.file}:{h.line} {h.pid} ×{h.count}（{h.rule}）：{h.evidence}")
    return "\n".join(lines) if lines else "- 无命中"


def fenced(text: str) -> str:
    """4 反引号围栏包裹整份 Markdown 正文。"""
    return f"{FENCE}markdown\n{text.rstrip()}\n{FENCE}"


def body_sections(files: List[Path]) -> str:
    """被审与参照全文内联：每文件一个围栏块，评审员不再读盘。"""
    blocks = [f"### {f}\n\n{fenced(f.read_text(encoding='utf-8', errors='replace'))}" for f in files]
    return "## 被审与参照全文\n\n" + "\n\n".join(blocks)


def contract_sections() -> str:
    """附章运行时现读 SKILL.md / reviewer.md / catalog.md 拼接：SSOT 在源文件，卷宗是派生物。"""
    blocks = [f"### {rel}\n\n{fenced((SKILL_ROOT / rel).read_text(encoding='utf-8'))}" for rel in CONTRACT_FILES]
    return "## 契约附章（评审员契约与规则清单，随卷宗送达）\n\n" + "\n\n".join(blocks)


def build_packet(out_dir: Path, targets: List[Path], refs: List[Path]) -> Path:
    """生成 PACKET.md：全体评审员收到字节级相同的单文件，读盘与核验机制随之取消。"""
    rows = "\n".join(manifest_row(p) for p in targets)
    ref_rows = "\n".join(manifest_row(p) for p in refs) if refs else "未传外部参照（--ref 为空）"
    parts = [
        "# 多模型评审卷宗",
        "本卷宗是单名评审员的唯一输入：被审内容清单、参照输入、机械扫描候选、被审与参照全文、文末契约附章。"
        "评审员角色、评审立场与产物顺序见附章 ref/reviewer.md；评审员没有可用工具，一切以本卷宗为准。"
        "全体评审员收到的本文件字节级相同。",
        "## 被审内容清单",
        "| 路径 | 字数（不含空白） | 行数 |\n| --- | --- | --- |\n" + rows,
        "## 参照输入",
        ref_rows,
        "## 机械扫描候选（全体评审员共享，勿重跑扫描）",
        scan_lines(targets),
        body_sections(targets + refs),
        contract_sections(),
    ]
    path = out_dir / "PACKET.md"
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return path


def main(argv: List[str] = None) -> int:
    """CLI 入口：建卷宗目录并生成 PACKET.md，打印两个路径。"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", nargs="+", required=True, help="reviewed file(s) or dir(s)")
    parser.add_argument("--ref", nargs="+", default=[], help="reference input file(s) for cross-doc SSOT")
    parser.add_argument("--out", default="", help="packet dir (default: wr-<timestamp> under system temp)")
    args = parser.parse_args(argv)
    targets = expand_paths(args.target, "被审")
    refs = expand_paths(args.ref, "参照")
    if args.out:
        out_dir = Path(args.out)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        out_dir = Path(DEFAULT_OUT_ROOT) / f"wr-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    packet = build_packet(out_dir, targets, refs)
    print(f"packet: {out_dir}")
    print(f"file: {packet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

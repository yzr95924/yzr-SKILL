#!/usr/bin/env python3
"""生成多模型评审卷宗：BRIEF.md（会话数据：指纹清单 + 参照输入 + 共享扫描候选）。"""

import argparse
import datetime
import hashlib
import sys
import tempfile
from pathlib import Path
from typing import List

from count_words import count_text
from scan_fingerprints import iter_targets, scan_text

SHA_LEN = 8
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
    """清单行：绝对路径 + sha256 前缀（对字节取哈希，与 sha256sum 一致）+ 非空白字数。"""
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()[:SHA_LEN]
    nchars, _ = count_text(data.decode("utf-8", errors="replace"))
    return f"| `{path}` | {sha} | {nchars} |"


def scan_lines(files: List[Path]) -> str:
    """对被审文件跑指纹扫描，命中渲染为共享候选列表行。"""
    lines: List[str] = []
    for f in files:
        text = f.read_bytes().decode("utf-8", errors="replace")
        for h in scan_text(text, str(f)):
            lines.append(f"- {h.file}:{h.line} {h.pid} ×{h.count}（{h.rule}）：{h.evidence}")
    return "\n".join(lines) if lines else "- 无命中"


def build_brief(out_dir: Path, targets: List[Path], refs: List[Path]) -> Path:
    """按内嵌模板生成 BRIEF.md：只装会话数据，所有评审员读到的内容零差异。"""
    rows = "\n".join(manifest_row(p) for p in targets)
    ref_rows = "\n".join(manifest_row(p) for p in refs) if refs else "无参照输入（只审文档内）"
    scan = scan_lines(targets)
    # 角色与契约归 skill（ref/reviewer.md，评审员经加载 skill 获得）；BRIEF 只装会话数据，不复制 skill 内容
    brief = f"""# 评审卷宗（会话数据）

评审员模式、角色边界与产物要求由 yzr-writing-review skill 的 ref/reviewer.md 定义；本卷宗只含本次评审的会话数据，全体评审员字节级相同。

## 被审内容清单

| 路径 | sha256 前 {SHA_LEN} 位 | 字数（不含空白） |
| --- | --- | --- |
{rows}

参照输入：

{ref_rows}

## 机械扫描候选（全体评审员共享，勿重跑扫描）

{scan}
"""
    path = out_dir / "BRIEF.md"
    path.write_text(brief, encoding="utf-8")
    return path


def main(argv: List[str] = None) -> int:
    """CLI 入口：建卷宗目录并生成 BRIEF.md，打印两个路径。"""
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
    brief = build_brief(out_dir, targets, refs)
    print(f"packet: {out_dir}")
    print(f"brief: {brief}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

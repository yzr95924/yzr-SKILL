#!/usr/bin/env python3
"""数字数（Step 1 分段闸门 / Step 6 压缩率取数）：每文件一行，两种口径都给，agent 按语言取。"""

import argparse
import re
import sys
from pathlib import Path
from typing import List

from scan_fingerprints import iter_targets


def count_text(text: str):
    """数一段文字：返回（非空白字符数, 词数）。"""
    return len(re.sub(r"\s", "", text)), len(text.split())


def main(argv: List[str] = None) -> int:
    """CLI 入口：逐文件打印两种口径计数，供分段闸门与压缩率取数。"""
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="口径：chars=非空白字符数，中文篇幅按它；words=空白分词数，英文篇幅按它。",
    )
    parser.add_argument("paths", nargs="+", help="markdown file(s) or directory to count")
    args = parser.parse_args(argv)
    rc = 0
    for arg in args.paths:
        path = Path(arg)
        if not path.exists():
            print(f"ERROR: {path} 不存在", file=sys.stderr)
            rc = 1
            continue
        for f in iter_targets(path):
            chars, words = count_text(f.read_text(encoding="utf-8"))
            print(f"{f}\tchars={chars}\twords={words}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

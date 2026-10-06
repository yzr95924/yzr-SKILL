#!/usr/bin/env python3
"""为无记忆约定的项目创建 MEMORY/ 骨架；骨架 SSOT 在 assets/memory-index-template.md。"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.memory_lint import INDEX_NAME, MEMORY_DIR  # noqa: E402

TEMPLATE_REL = Path("assets") / "memory-index-template.md"
INDEX_REL = Path(MEMORY_DIR) / INDEX_NAME

SKELETON_RE = re.compile(r"<!-- skeleton:start -->\n(.*?)<!-- skeleton:end -->", re.DOTALL)
FENCE_RE = re.compile(r"```markdown\n(.*?)```", re.DOTALL)


def extract_skeleton(template: Path) -> str:
    """从模板 skeleton 标记段抽项目骨架；冒烟与本函数共享实现，改标记格式即 CI 红"""
    outer = SKELETON_RE.search(template.read_text(encoding="utf-8"))
    if outer is None:
        raise RuntimeError(f"{template} 缺 skeleton 标记段")
    inner = FENCE_RE.search(outer.group(1))
    if inner is None:
        raise RuntimeError(f"{template} skeleton 标记段内应是 markdown 代码块")
    return inner.group(1)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：定位模板、拒绝覆盖、写骨架；MEMORY/MEMORY.md 已存在时退出 1 不动文件"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", help="项目根（默认 cwd）")
    args = parser.parse_args(argv)

    template = Path(__file__).resolve().parent.parent / TEMPLATE_REL
    if not template.is_file():
        print(f"ERROR: 模板不存在：{template}", file=sys.stderr)
        return 1
    try:
        skeleton = extract_skeleton(template)
    except (OSError, UnicodeDecodeError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    index_path = Path(args.root).resolve() / INDEX_REL
    if index_path.is_file():
        print(f"ERROR: {index_path} 已存在——init 只建骨架不覆盖，已有记忆走 audit 入口", file=sys.stderr)
        return 1
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(skeleton, encoding="utf-8")
    print(f"created {index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

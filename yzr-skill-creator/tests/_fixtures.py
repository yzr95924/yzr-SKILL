"""共享 smoke 夹具：把 {相对路径: 内容} 写进一个保活的临时 skill 目录。"""

import tempfile
from pathlib import Path
from typing import Dict

_KEEP = []


def make_tmp_dir(prefix: str = "smoke-") -> Path:
    """建一个保活到进程结束的临时目录，返回其路径。"""
    tmp = tempfile.TemporaryDirectory(prefix=prefix)
    _KEEP.append(tmp)
    return Path(tmp.name)


def make_skill_dir(files: Dict[str, str], prefix: str = "smoke-", name: str = "smoke-target") -> Path:
    """建临时 skill 目录并写入 files；句柄保活到进程结束，返回 skill 根。"""
    root = make_tmp_dir(prefix) / name
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root

"""共享 smoke 夹具：保活临时目录、expect 断言与统一 runner。"""

import tempfile
from pathlib import Path
from typing import Callable, Dict, List

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


def expect(cond, msg: str = "") -> None:
    """条件不成立时抛 AssertionError；显式 raise 替代 assert（python -O 不吞）。"""
    if not cond:
        raise AssertionError(msg)


def run_cases(cases: List[Callable[[], None]]) -> int:
    """统一冒烟 runner：顺序跑 case 函数，AssertionError 与异常都记为失败，末尾汇总退出码。"""
    failures: List[str] = []
    for case in cases:
        try:
            case()
        except AssertionError as exc:
            failures.append(f"{case.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 - 炸穿也算失败，不吞后续用例
            failures.append(f"{case.__name__}: crashed {type(exc).__name__}: {exc}")
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print(f"{len(cases)}/{len(cases)} passed")
    return 0

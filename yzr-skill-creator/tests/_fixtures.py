"""共享 smoke 夹具：保活临时目录、expect 断言、CLI runner 包装与统一 runner。"""

import contextlib
import io
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

_KEEP = []

BODY = "\n# t\n\n## 输入与输出\n\n正文。\n"


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


def run_cli(fn: Callable[[List[str]], int], argv: List[str]) -> Tuple[int, str]:
    """跑 CLI main，返回 (退出码, stdout)；stderr 吞掉。"""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = fn(argv)
    return rc, out.getvalue()


def run_cases(cases: Optional[List[Callable[[], None]]] = None) -> int:
    """统一冒烟 runner：缺省自动收集调用方模块的 case_* 函数（手工列表会让新增用例静默漏跑），AssertionError 与异常都记为失败，末尾汇总退出码。"""
    if cases is None:
        cases = [fn for name, fn in sys._getframe(1).f_globals.items() if name.startswith("case_") and callable(fn)]
        if not cases:
            print("SMOKE FAIL: 调用方模块没有 case_* 函数")
            return 1
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

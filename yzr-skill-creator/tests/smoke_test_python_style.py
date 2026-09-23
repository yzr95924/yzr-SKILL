#!/usr/bin/env python3
"""Fixture smoke test for check_python_style (docstring policy + smoke-test form).

Every case pins both directions: a compliant fixture stays silent, and the
named rule fires exactly where it should. The expect() helper is itself part of
the contract — it replaced bare asserts in the smoke files, so a fixture that
uses it must pass the SMOKE-ASSERT screen.

Run: python3 tests/smoke_test_python_style.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_skill_dir  # noqa: E402

from tools import check_python_style  # noqa: E402

CLEAN_TOOLS = '''"""夹具模块。"""


class Box:
    """一个盒子。"""

    def open(self):
        """打开盒子。"""
        return 1


def helper(x):
    """返回入参。"""
    return x
'''

CLEAN_SMOKE = '''#!/usr/bin/env python3
"""打桩检查夹具。

Run: python3 tests/smoke_test_x.py  (from skill-root/)
"""

import sys


def expect(cond, msg=""):
    """条件不成立时抛 AssertionError。"""
    if not cond:
        raise AssertionError(msg)


def main():
    failures = []
    if failures:
        print("SMOKE FAIL:", *failures)
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def output(files: Dict[str, str]) -> List:
    """把文件集写进临时 skill 并跑 scan_skill。"""
    return check_python_style.scan_skill(make_skill_dir(files, prefix="pystyle-smoke-"))


def rules(findings) -> List[str]:
    return [f.rule for f in findings]


def check_docstrings(failures: List[str]) -> None:
    if rules(output({"tools/mod.py": CLEAN_TOOLS})):
        failures.append(f"DOCSTRING: clean tools fixture reported: {rules(output({'tools/mod.py': CLEAN_TOOLS}))}")
    cases = (
        ("模块缺", "x = 1\n", "模块"),
        ("模块非一行", '"""第一行。\n第二行。"""\n', "非一行"),
        ("函数缺", CLEAN_TOOLS.replace('    """返回入参。"""\n', ""), "函数 helper"),
        ("函数非中文", CLEAN_TOOLS.replace("返回入参。", "Return x."), "无中文"),
        ("类缺", CLEAN_TOOLS.replace('    """一个盒子。"""\n', ""), "类 Box"),
    )
    for label, content, marker in cases:
        findings = output({"tools/mod.py": content})
        hits = [f for f in findings if f.rule == "DOCSTRING"]
        if not hits or hits[0].level != "ERROR" or marker not in hits[0].evidence:
            failures.append(f"DOCSTRING {label}: got {[(f.rule, f.level, f.evidence) for f in findings]}")


def check_smoke_form(failures: List[str]) -> None:
    if rules(output({"tests/smoke_test_x.py": CLEAN_SMOKE})):
        failures.append("SMOKE: clean fixture reported")
    # 裸 assert 报 ERROR（expect 的显式 raise 不报）
    dirty = CLEAN_SMOKE.replace("    failures = []", "    assert True")
    hits = [f for f in output({"tests/smoke_test_x.py": dirty}) if f.rule == "SMOKE-ASSERT"]
    if not hits or hits[0].level != "ERROR":
        failures.append(f"SMOKE-ASSERT: bare assert not reported: {hits}")
    # 缺 sys.exit 报 ERROR
    dirty = CLEAN_SMOKE.replace("    sys.exit(main())\n", "    main()\n")
    hits = [f for f in output({"tests/smoke_test_x.py": dirty}) if f.rule == "SMOKE-EXIT"]
    if not hits or hits[0].level != "ERROR":
        failures.append(f"SMOKE-EXIT: missing sys.exit not reported: {hits}")
    # 头部缺跑法报 WARN
    dirty = CLEAN_SMOKE.replace("Run: python3 tests/smoke_test_x.py  (from skill-root/)", "只是一段说明")
    hits = [f for f in output({"tests/smoke_test_x.py": dirty}) if f.rule == "SMOKE-HEADER"]
    if not hits or hits[0].level != "WARN":
        failures.append(f"SMOKE-HEADER: missing run hint not reported: {hits}")
    # 非 smoke_test_*.py 的 tests 文件不在扫描范围
    unscanned = output({"tests/helpers.py": "assert 1 == 1\n"})
    if rules(unscanned):
        failures.append(f"tests/ 非冒烟文件被误扫：{[(f.rule, f.file) for f in unscanned]}")


def main() -> int:
    failures: List[str] = []
    check_docstrings(failures)
    check_smoke_form(failures)
    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print("SMOKE OK: check_python_style — docstring + smoke 双向用例")
    return 0


if __name__ == "__main__":
    sys.exit(main())

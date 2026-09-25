#!/usr/bin/env python3
"""Fixture smoke test for memory_lint.

The class of bug this pins: a linter that passes everything (silent rot) or
fails on valid structures (blocks legit writes). Fixtures cover both
directions: a canonical clean memory passes with zero findings, and a rotted
one surfaces each rule it should catch (dead link, orphan, frontmatter
violations, budget overflow, sensitive strings), plus the no-MEMORY case,
and the entry-length boundary (120 lines pass, 121 warns without gating).

Run: python3 tests/smoke_test_memory_lint.py  (from yzr-memory-management/)
Exit 0 = all green, 1 = regression.
"""

import contextlib
import io
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.memory_lint import (  # noqa: E402
    ENTRY_MAX_LINES,
    INDEX_MAX_LINES,
    collect_findings,
    discover_memory_root,
    main,
)


def expect(cond, msg="") -> None:
    """条件不成立时抛 AssertionError；显式 raise 替代 assert（python -O 不吞）"""
    if not cond:
        raise AssertionError(msg)


def write(path: Path, text: str) -> None:
    """建父目录并写文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_cli(argv):
    """捕获 stdout 跑 CLI，返回 (退出码, 输出)"""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = main(argv)
    return rc, buffer.getvalue()


def rules_in(output: str, rules) -> str:
    """返回输出里命中的规则名集合描述，供断言消息用"""
    return ", ".join(r for r in rules if r in output)


TODAY = date.today().isoformat()

CLEAN_INDEX = """# MEMORY/

## 规则

- [包管理用 uv](pkg-tool.md)：本仓装依赖走 uv，禁 npm / pip 直装
- 金额一律 Decimal：结算相关计算禁 float
"""

CLEAN_ENTRY = f"""---
name: pkg-tool
description: 本仓包管理用 uv，禁 npm/pip 直装。
metadata:
  type: feedback
  scope: 全仓依赖安装
  modified: {TODAY}
---

# 包管理用 uv

- 装依赖一律 uv，npm / pip 直装会被用户纠正

## 关键证据

2026-09 用户纠正过一次 npm install 的用法
"""

ROTTED_INDEX_HEAD = """# MEMORY/

## 规则

- [包管理用 uv](pkg-tool.md)：本仓装依赖走 uv
- [旧规则](old-rule.md)：已被文档吸收但索引还挂着
- 包管理用 uv：与第一条同主题，短条目重复
"""


def build_rotted(root: Path) -> None:
    """造一个各坏一处的 MEMORY/：死链、孤儿、name 不符、type 非法、缺 scope、敏感串、超预算"""
    body = [ROTTED_INDEX_HEAD] + [f"- 填充条目 {i}：占位事实" for i in range(210)]
    write(root / "MEMORY" / "MEMORY.md", "\n".join(body) + "\n")
    write(
        root / "MEMORY" / "pkg-tool.md",
        (
            "---\n"
            "name: other-name\n"
            "description: name 与文件名不一致。\n"
            "metadata:\n"
            "  type: diary\n"
            f"  modified: {TODAY}\n"
            "---\n\n# 条目\n\n- 正文\n\n```\n"
            "password: abc123def456ghi789jkl\n"
            "```\n"
        ),
    )
    write(root / "MEMORY" / "unlinked.md", CLEAN_ENTRY)


def main_test() -> None:
    """三组用例：干净、腐化、无 MEMORY/"""
    with tempfile.TemporaryDirectory() as tmp:
        clean_root = Path(tmp) / "clean"
        write(clean_root / "MEMORY" / "MEMORY.md", CLEAN_INDEX)
        write(clean_root / "MEMORY" / "pkg-tool.md", CLEAN_ENTRY)

        expect(discover_memory_root(clean_root) == clean_root.resolve(), "发现层应定位到含 MEMORY/ 的目录")
        findings = collect_findings(clean_root.resolve())
        expect(findings == [], f"干净夹具应零 finding，实际: {findings}")
        rc, out = run_cli([str(clean_root)])
        expect(rc == 0, f"干净夹具应退出 0，实际 {rc}")
        expect("PASS" in out, "干净夹具应输出 PASS")
        expect(
            f"STATS 索引 {len(CLEAN_INDEX.splitlines())} / {INDEX_MAX_LINES} 行 · 条目 1 个" in out,
            "文本模式应输出 STATS 体检数字",
        )

        sub = clean_root / "sub" / "dir"
        sub.mkdir(parents=True, exist_ok=True)
        rc, out = run_cli([str(sub)])
        expect(rc == 0 and "MEMORY root" in out, "从子目录跑应向上定位到 MEMORY/")

    with tempfile.TemporaryDirectory() as tmp:
        rotted_root = Path(tmp) / "rotted"
        build_rotted(rotted_root)
        rc, out = run_cli([str(rotted_root)])
        expect(rc == 1, f"腐化夹具应退出 1，实际 {rc}")
        want = (
            "DEAD-LINK",
            "ORPHAN",
            "NAME-MISMATCH",
            "TYPE-INVALID",
            "SCOPE-MISSING",
            "INDEX-BUDGET",
            "SENSITIVE",
        )
        hit = rules_in(out, want)
        expect(len(hit.split(", ")) == len(want), f"应命中全部 {len(want)} 条规则，实命中: {hit or '无'}")
        expect("INDEX-BUDGET-HIGH" not in out, "已超上限时不应再报八成水位 WARN")

        rc, out = run_cli([str(rotted_root), "--json"])
        data = json.loads(out)
        expect(rc == 1 and data["ok"] is False, "JSON 模式 ok 应为 False")
        expect(data["stats"]["entry_count"] == 2, f"JSON 模式 stats 条目数应为 2，实际 {data['stats']}")
        expect(
            data["error_count"] == sum(1 for f in data["findings"] if f["level"] == "ERROR"),
            "error_count 应与 findings 一致",
        )

        rules = {f["rule"] for f in data["findings"]}
        expect(
            {"DEAD-LINK", "INDEX-BUDGET", "NAME-MISMATCH", "TYPE-INVALID"} <= rules,
            f"ERROR 级规则应齐全，实际: {rules}",
        )

    with tempfile.TemporaryDirectory() as tmp:
        empty_root = Path(tmp) / "empty"
        empty_root.mkdir(parents=True, exist_ok=True)
        rc, out = run_cli([str(empty_root)])
        expect(rc == 0 and "NO-MEMORY" in out, "无 MEMORY/ 应回 INFO 且退出 0")
        rc, out = run_cli([str(empty_root), "--json"])
        data = json.loads(out)
        expect(data["memory_root"] is None, "JSON 模式 memory_root 应为 null")
        expect(
            "stats" in data and data["stats"] is None and data["error_count"] == 0,
            "无记忆根的 JSON 应与正常分支同键集（stats / error_count）",
        )

    with tempfile.TemporaryDirectory() as tmp:
        broken_root = Path(tmp) / "broken"
        index = (
            CLEAN_INDEX
            + "- [坏文件](gbk.md)：读取失败应转 READ-ERROR\n"
            + "- [越界](../outside.md)：单层 slug 契约外的链接不应被跟进\n"
        )
        write(broken_root / "MEMORY" / "MEMORY.md", index)
        write(broken_root / "MEMORY" / "pkg-tool.md", CLEAN_ENTRY)
        (broken_root / "MEMORY" / "gbk.md").write_bytes(b"\xff\xfe\x01\x02")
        rc, out = run_cli([str(broken_root)])
        expect(rc == 1 and "READ-ERROR" in out, f"读不动的文件应转 READ-ERROR 并退出 1，实际 rc={rc}")
        expect("DEAD-LINK" not in out, "读取失败与越界 slug 都不应误判为死链")
        expect("STATS" in out, "个别文件读坏时其余检查与统计仍应产出")

    with tempfile.TemporaryDirectory() as tmp:
        long_root = Path(tmp) / "long-entry"
        write(long_root / "MEMORY" / "MEMORY.md", CLEAN_INDEX)

        def padded_entry(n_lines: int) -> str:
            """把 CLEAN_ENTRY 填充到精确 n_lines 行（总行数，frontmatter 计入）"""
            base = CLEAN_ENTRY.rstrip("\n")
            pad = max(0, n_lines - len(base.splitlines()))
            return base + "\n" + "\n".join(f"- 填充 {i}" for i in range(pad)) + "\n"

        write(long_root / "MEMORY" / "pkg-tool.md", padded_entry(ENTRY_MAX_LINES))
        findings = collect_findings(long_root.resolve())
        expect(findings == [], f"{ENTRY_MAX_LINES} 行整不应触发 ENTRY-LONG，实际: {findings}")

        write(long_root / "MEMORY" / "pkg-tool.md", padded_entry(ENTRY_MAX_LINES + 1))
        rc, out = run_cli([str(long_root)])
        long_hits = [f for f in collect_findings(long_root.resolve()) if f.rule == "ENTRY-LONG"]
        expect(rc == 0, f"ENTRY-LONG 是 WARN 不应改退出码，实际 {rc}")
        expect(len(long_hits) == 1 and long_hits[0].level == "WARN", f"应恰好一条 WARN，实际: {long_hits}")
        expect("ENTRY-LONG" in out, "文本模式应输出 ENTRY-LONG")

    print("smoke_test_memory_lint: all green")


if __name__ == "__main__":
    try:
        main_test()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)

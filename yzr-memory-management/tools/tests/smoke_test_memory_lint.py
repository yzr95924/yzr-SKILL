#!/usr/bin/env python3
"""Fixture smoke test for memory_lint.

The class of bug this pins: a linter that passes everything (silent rot) or
fails on valid structures (blocks legit writes). Fixtures cover both
directions: a canonical clean memory passes with zero findings, and a rotted
one surfaces each rule it should catch (dead link, orphan, missing scope,
budget overflow, sensitive strings, index-head residue), plus the no-MEMORY case with
and without a dangling AGENTS.md declaration, the empty-index warning, and the
entry-length boundary (120 lines pass, 121 warns without gating). It also pins
the skill's own artifacts against lint: eval/fixtures fixtures must pass with
zero ERROR/WARN, assets template numbers must match lint constants, and the
AGENTS.md sample in ref/init-workflow.md must stay recognizable by
MEMORY_REF_RE (exactly one declaring line). The project skeleton constant
must appear in the template's skeleton block.

Run: python3 tools/tests/smoke_test_memory_lint.py  (from yzr-memory-management/)
Exit 0 = all green, 1 = regression.
"""

import contextlib
import io
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.memory_lint import (  # noqa: E402
    BUDGET_HIGH_RATIO,
    ENTRY_MAX_LINES,
    INDEX_MAX_BYTES,
    INDEX_MAX_LINES,
    MEMORY_REF_RE,
    collect_findings,
    main,
)

AGENTS_MD = "AGENTS.md"


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


SKILL_DIR = Path(__file__).resolve().parents[2]
TEMPLATE = SKILL_DIR / "assets" / "memory-index-template.md"
SKELETON = "# MEMORY/\n\n## 规则\n"
FENCE_RE = re.compile(r"```markdown\n(.*?)```", re.DOTALL)


def skill_file(rel: str) -> str:
    """读 skill 侧文件（assets 模板 / ref 工作流）"""
    return (SKILL_DIR / rel).read_text(encoding="utf-8")


CLEAN_INDEX = """# MEMORY/

## 规则

- [包管理用 uv](pkg-tool.md)：本仓装依赖走 uv，禁 npm / pip 直装
- 金额一律 Decimal：结算相关计算禁 float
"""

CLEAN_ENTRY = """---
scope: 全仓依赖安装
---

# 包管理用 uv

- 装依赖一律 uv，npm / pip 直装会被用户纠正

## 关键证据

2026-09 用户纠正过一次 npm install 的用法
"""

ROTTED_INDEX_HEAD = """# MEMORY/

## 规则

- [包管理用 uv](pkg-tool.md)：本仓装依赖走 uv
- [旧规则](old-rule.md)：已被文档覆盖但索引还挂着
- 包管理用 uv：与第一条同主题，短条目重复
"""


def build_rotted(root: Path) -> None:
    """造一个各坏一处的 MEMORY/：死链、孤儿、缺 scope、敏感串、超上限"""
    body = [ROTTED_INDEX_HEAD] + [f"- 填充条目 {i}：占位事实" for i in range(210)]
    write(root / "MEMORY" / "MEMORY.md", "\n".join(body) + "\n")
    write(
        root / "MEMORY" / "pkg-tool.md",
        ("- 正文没有 frontmatter，scope 缺失\n\n```\npassword: abc123def456ghi789jkl\n```\n"),
    )
    write(root / "MEMORY" / "unlinked.md", CLEAN_ENTRY)


def main_test() -> None:
    """用例组：干净 / 腐化 / 无 MEMORY 与悬空声明 / 空白与骨架 / eval 夹具 / 模板数值 / init 样例"""
    with tempfile.TemporaryDirectory() as tmp:
        clean_root = Path(tmp) / "clean"
        write(clean_root / "MEMORY" / "MEMORY.md", CLEAN_INDEX)
        write(clean_root / "MEMORY" / "pkg-tool.md", CLEAN_ENTRY)

        findings = collect_findings(clean_root.resolve())
        expect(findings == [], f"干净夹具应零 finding，实际: {findings}")
        rc, out = run_cli([str(clean_root)])
        expect(rc == 0, f"干净夹具应退出 0，实际 {rc}")
        expect("PASS" in out, "干净夹具应输出 PASS")
        expect(
            f"STATS 索引 {len(CLEAN_INDEX.splitlines())} / {INDEX_MAX_LINES} 行 · 条目 1 个" in out,
            "文本模式应输出 STATS 统计数字",
        )
        write(clean_root / AGENTS_MD, "## 跨会话记忆（索引）\n\n@MEMORY/MEMORY.md\n")
        findings = collect_findings(clean_root.resolve())
        expect(findings == [], f"干净夹具带 @MEMORY 声明仍应零 finding，实际: {findings}")

        sub = clean_root / "sub" / "dir"
        sub.mkdir(parents=True, exist_ok=True)
        rc, out = run_cli([str(sub)])
        expect(rc == 0 and "NO-MEMORY" in out, "传子目录不向上找，应报 NO-MEMORY")

    with tempfile.TemporaryDirectory() as tmp:
        rotted_root = Path(tmp) / "rotted"
        build_rotted(rotted_root)
        rc, out = run_cli([str(rotted_root)])
        expect(rc == 1, f"腐化夹具应退出 1，实际 {rc}")
        want = (
            "DEAD-LINK",
            "ORPHAN",
            "SCOPE-MISSING",
            "INDEX-BUDGET",
            "SENSITIVE",
        )
        hit = rules_in(out, want)
        expect(len(hit.split(", ")) == len(want), f"应命中全部 {len(want)} 条规则，实命中: {hit or '无'}")
        expect("INDEX-BUDGET-HIGH" not in out, "已超上限时不应再报八成用量 WARN")

        rules = {f.rule for f in collect_findings(rotted_root.resolve()) if f.level == "ERROR"}
        expect({"DEAD-LINK", "INDEX-BUDGET"} <= rules, f"ERROR 级规则应齐全，实际: {rules}")

    with tempfile.TemporaryDirectory() as tmp:
        empty_root = Path(tmp) / "empty"
        empty_root.mkdir(parents=True, exist_ok=True)
        rc, out = run_cli([str(empty_root)])
        expect(rc == 0 and "NO-MEMORY" in out, "无 MEMORY/ 且无声明应回 INFO 且退出 0")
        expect("DANGLING-REF" not in out, "无声明时不应误报悬空声明")

        # 声明悬空：AGENTS.md 有 @MEMORY 行但 MEMORY/ 不存在
        write(empty_root / AGENTS_MD, "## 跨会话记忆（索引）\n\n@MEMORY/MEMORY.md\n")
        rc, out = run_cli([str(empty_root)])
        expect(rc == 1 and "DANGLING-REF" in out, f"声明悬空应报 ERROR 且退出 1，实际 rc={rc}")
        expect("NO-MEMORY" in out, "悬空声明应与 NO-MEMORY INFO 并存")

        write(
            empty_root / AGENTS_MD,
            "<!-- 下方 @引用若未被自动展开（看不到正文），用 Read 工具读取 -->\n@ MEMORY/MEMORY.md\n",
        )
        rc, out = run_cli([str(empty_root)])
        expect(rc == 0 and "DANGLING-REF" not in out, f"注释式 / 变形引用不应判为声明，实际 rc={rc}: {out}")

    with tempfile.TemporaryDirectory() as tmp:
        blank_root = Path(tmp) / "blank"
        write(blank_root / "MEMORY" / "MEMORY.md", "   \n\t\n")
        rc, out = run_cli([str(blank_root)])
        expect(rc == 0 and "INDEX-EMPTY" in out, f"空白索引应 WARN 且不改退出码，实际 rc={rc}")
        write(blank_root / "MEMORY" / "MEMORY.md", SKELETON)
        rc, out = run_cli([str(blank_root)])
        expect(rc == 0 and "INDEX-EMPTY" not in out, f"骨架零条目是合法首批，不应报 INDEX-EMPTY，实际: {out}")
        findings = collect_findings(blank_root.resolve())
        expect(findings == [], f"极简骨架本身应零 finding，实际: {findings}")

    with tempfile.TemporaryDirectory() as tmp:
        head_root = Path(tmp) / "head"
        write(
            head_root / "MEMORY" / "MEMORY.md",
            "# MEMORY/\n\n上限 ≤ 200 行，达八成先精简再写入。\n\n## 规则\n\n- 短条目：事实\n",
        )
        rc, out = run_cli([str(head_root)])
        expect(rc == 0 and "INDEX-HEAD" in out, f"头部规格抄件应报 INDEX-HEAD WARN 且不改退出码，实际 rc={rc}: {out}")
        head_hits = [f for f in collect_findings(head_root.resolve()) if f.rule == "INDEX-HEAD"]
        expect(len(head_hits) == 1 and head_hits[0].level == "WARN", f"应恰一条 WARN，实际: {head_hits}")

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

    with tempfile.TemporaryDirectory() as tmp:
        case_dirs = sorted(d for d in (SKILL_DIR / "eval" / "fixtures").iterdir() if d.is_dir())
        expect(len(case_dirs) > 0, "eval/fixtures 下应有用例夹具目录")
        for case_dir in case_dirs:
            root = Path(tmp) / case_dir.name
            if (case_dir / "MEMORY").is_dir():
                shutil.copytree(case_dir, root)
            else:
                entries = sorted(case_dir.glob("*.md"))
                expect(len(entries) > 0, f"{case_dir.name} 下应有 .md 条目夹具")
                (root / "MEMORY").mkdir(parents=True)
                lines = [f"- [{f.stem}]({f.name})：eval 夹具" for f in entries]
                (root / "MEMORY" / "MEMORY.md").write_text(SKELETON + "\n".join(lines) + "\n", encoding="utf-8")
                for f in entries:
                    (root / "MEMORY" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            findings = [f for f in collect_findings(root.resolve()) if f.level in ("ERROR", "WARN")]
            expect(findings == [], f"夹具 {case_dir.name} 须过现行契约（0 ERROR 0 WARN），实际: {findings}")

    index_md = TEMPLATE.read_text(encoding="utf-8")
    entry_md = skill_file("assets/memory-entry-template.md")
    expect(f"≤ {INDEX_MAX_LINES} 行且 ≤ {INDEX_MAX_BYTES // 1024}KB" in index_md, "索引模板上限数值应与 lint 常量一致")
    expect("八成" in index_md and BUDGET_HIGH_RATIO == 0.8, "用量措辞（八成）应与 BUDGET_HIGH_RATIO 一致")
    expect(f"超 {ENTRY_MAX_LINES} 行" in entry_md, "条目模板长度阈值应与 lint 常量一致")
    expect("scope" in entry_md, "条目模板应保留 scope 字段及其用途说明")

    init_md = skill_file("ref/init-workflow.md")
    blocks = FENCE_RE.findall(init_md)
    sample = next((b for b in blocks if "MEMORY/MEMORY.md" in b), None)
    expect(sample is not None, "init-workflow 应含 AGENTS.md 引用段样例（markdown 代码块）")
    declared = [ln for ln in sample.splitlines() if MEMORY_REF_RE.match(ln.strip())]
    expect(len(declared) == 1, f"引用段样例应恰有一行命中 MEMORY_REF_RE（@ 行命中、注释行不命中），实际: {declared}")

    print("smoke_test_memory_lint: all green")


if __name__ == "__main__":
    try:
        main_test()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)

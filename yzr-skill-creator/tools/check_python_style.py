#!/usr/bin/env python3
"""Python shape screens: docstring policy (tools/) and smoke-test form (tests/)."""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import Finding, discover_skill_dirs, format_findings  # noqa: E402

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

_RUN_HINT_RE = re.compile(r"python", re.IGNORECASE)


def _parse(path: Path) -> Optional[ast.Module]:
    """解析 Python 源文件；语法错误返回 None（语法问题归 ruff）。"""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return None


def _docstring_findings(path: Path, rel: str) -> List[Finding]:
    """检查模块与全部函数 / 类的 docstring：模块一行，函数 / 类一行中文。"""
    tree = _parse(path)
    if tree is None:
        return []
    findings: List[Finding] = []

    def check(node, label: str, require_cjk: bool, lineno: int) -> None:
        """按政策检查单个节点的 docstring，违规时追加 Finding。"""
        doc = ast.get_docstring(node)
        if not doc:
            findings.append(
                Finding(
                    rule="DOCSTRING",
                    level="ERROR",
                    evidence=f"{label}：缺 docstring",
                    file=rel,
                    line=str(lineno),
                    fix="补一行中文 docstring",
                )
            )
            return
        if "\n" in doc.strip():
            findings.append(
                Finding(
                    rule="DOCSTRING",
                    level="ERROR",
                    evidence=f"{label}：docstring 非一行",
                    file=rel,
                    line=str(lineno),
                    fix="压成一行",
                )
            )
        if require_cjk and not _CJK_RE.search(doc):
            findings.append(
                Finding(
                    rule="DOCSTRING",
                    level="ERROR",
                    evidence=f"{label}：docstring 无中文",
                    file=rel,
                    line=str(lineno),
                    fix="改成一行中文 docstring",
                )
            )

    check(tree, "模块", False, 1)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            check(node, f"类 {node.name}", True, node.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check(node, f"函数 {node.name}", True, node.lineno)
    return findings


def _is_sys_exit(node: ast.AST) -> bool:
    """判断节点是否为 sys.exit(...) 调用。"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "exit"
        and isinstance(func.value, ast.Name)
        and func.value.id == "sys"
    )


def _smoke_findings(path: Path, rel: str) -> List[Finding]:
    """检查冒烟形态：禁裸 assert、sys.exit 收尾、模块 docstring 注明跑法。"""
    tree = _parse(path)
    if tree is None:
        return []
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            findings.append(
                Finding(
                    rule="SMOKE-ASSERT",
                    level="ERROR",
                    evidence="冒烟含裸 assert（python -O 会吞，失败静默）",
                    file=rel,
                    line=str(node.lineno),
                    fix="改 failures 列表收集或显式 raise，末尾 exit 1",
                )
            )
    if not any(_is_sys_exit(node) for node in ast.walk(tree)):
        findings.append(
            Finding(
                rule="SMOKE-EXIT",
                level="ERROR",
                evidence="冒烟未以 sys.exit 收尾，CI 拿不到失败退出码",
                file=rel,
                fix="结尾 sys.exit(main())",
            )
        )
    doc = ast.get_docstring(tree)
    if not doc or not _RUN_HINT_RE.search(doc):
        findings.append(
            Finding(
                rule="SMOKE-HEADER",
                level="WARN",
                evidence="冒烟头部缺跑法（Run: python3 tests/... 与 cwd）",
                file=rel,
                fix="模块 docstring 注明 cwd 与跑法",
            )
        )
    return findings


def scan_skill(skill_dir: Path) -> List[Finding]:
    """跑一个 skill 的 Python 形态筛查：tools/ 全量 docstring + tests/ 冒烟形态。"""
    skill_dir = Path(skill_dir)
    findings: List[Finding] = []
    tools_dir = skill_dir / "tools"
    if tools_dir.is_dir():
        for py in sorted(p for p in tools_dir.rglob("*.py") if p.is_file()):
            findings += _docstring_findings(py, str(py.relative_to(skill_dir)))
    tests_dir = skill_dir / "tests"
    if tests_dir.is_dir():
        for py in sorted(tests_dir.glob("smoke_test_*.py")):
            findings += _smoke_findings(py, str(py.relative_to(skill_dir)))
    return findings


def _collect_targets(args, parser) -> Tuple[List[Path], int]:
    """解析扫描目标，返回 (目标列表, 退出码)。"""
    if args.repo_root:
        root = Path(args.repo_root).resolve()
        if not root.is_dir():
            print(f"error: repo root not found: {root}", file=sys.stderr)
            return [], 2
        return discover_skill_dirs(root), 0
    if args.skill_dir:
        skill_dir = Path(args.skill_dir).resolve()
        if not (skill_dir / "SKILL.md").is_file():
            print(f"error: no SKILL.md under: {skill_dir}", file=sys.stderr)
            return [], 2
        return [skill_dir], 0
    parser.error("give a skill dir or --repo-root")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：输出 Python 形态 Finding；有命中时退出码 1。"""
    parser = argparse.ArgumentParser(
        description="Python shape screens for a skill: docstring policy (tools/) and smoke-test form (tests/)."
    )
    parser.add_argument("skill_dir", nargs="?", default=None, help="path to one skill directory")
    parser.add_argument("--repo-root", default=None, help="scan every skill dir under this repo root")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human-readable lines")
    args = parser.parse_args(argv)

    targets, code = _collect_targets(args, parser)
    if code:
        return code
    findings: List[Finding] = []
    for skill_dir in targets:
        for finding in scan_skill(skill_dir):
            if len(targets) > 1:
                finding = finding._replace(evidence=f"[{skill_dir.name}] {finding.evidence}")
            findings.append(finding)

    if args.json:
        print(
            json.dumps(
                {
                    "targets": [str(t) for t in targets],
                    "finding_count": len(findings),
                    "findings": [f.to_dict() for f in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for line in format_findings(findings):
            print(line)
        print(f"\nScanned {len(targets)} skill(s); {len(findings)} finding(s).")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

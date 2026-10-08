#!/usr/bin/env python3
"""Fixture smoke test for scan_fingerprints.

钉住的 bug 类型：一直上报或从不上报的扫描器都能通过"能不能查破折号"这类朴素检查，
所以下方夹具全部双向：prose 命中必须产生命中，代码围栏 / 行内代码 / 干净文本必须零命中。
元提及（讨论符号本身的行）有意上报，由 reviewer 豁免，不是需要压掉的 bug。

Run: python3 tests/smoke_test_scan_fingerprints.py  (from yzr-writing-review/)
Exit 0 = all green, 1 = regression.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scan_fingerprints import DASH, PATTERNS, iter_targets, scan_text  # noqa: E402

CASES: List = []


def expect(cond, msg="") -> None:
    """条件不成立时抛 AssertionError；显式 raise 替代 assert（python -O 不吞）。"""
    if not cond:
        raise AssertionError(msg)


def case(fn):
    CASES.append(fn)
    return fn


@case
def positive_prose_hit():
    text = "先判断用户属于哪一种——再介入。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].line == 1 and hits[0].pid == "DASH", hits)


@case
def positive_multiple_on_one_line():
    text = "A——B——C\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].count == 2, hits)


@case
def negative_single_em_dash_not_matched():
    text = "范围 1—10 之间。\n"
    expect(scan_text(text, "a.md") == [])


@case
def negative_inline_code_span():
    text = "输出格式 `LEVEL: 文件:行 证据 —— 修法` 是契约。\n"
    expect(scan_text(text, "a.md") == [])


@case
def negative_double_backtick_span():
    text = "示例 ``" + DASH + "`` 属字面串。\n"
    expect(scan_text(text, "a.md") == [])


@case
def negative_inside_fence():
    text = "```bash\ngrep foo —— bar\n```\n"
    expect(scan_text(text, "a.md") == [])


@case
def positive_after_fence_resumes():
    text = "```python\n# " + DASH + "\n```\n" + "正文" + DASH + "继续。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].line == 4, hits)


@case
def positive_meta_mention_reported():
    # 指纹行在谈符号本身：有意上报的候选
    text = "- **破折号" + chr(0x201C) + DASH + chr(0x201D) + "/ em-dash**：默认一律换常规标点\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1, hits)


@case
def positive_clean_text_zero():
    text = "正常句子，用逗号：冒号、括号（如这些）。\n\n另一段。\n"
    expect(scan_text(text, "a.md") == [])


@case
def corner_quote_positive_prose_hit():
    text = "别的入口用「按该节执行」式指针复用。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "CORNER-QUOTE" and hits[0].count == 1, hits)


@case
def corner_quote_negative_inline_code():
    text = "参数 `--tier「default」` 照抄。\n"
    expect(scan_text(text, "a.md") == [])


@case
def corner_quote_negative_inside_fence():
    text = "```md\n「引用块」\n```\n"
    expect(scan_text(text, "a.md") == [])


@case
def section_sign_positive_prose_hit():
    text = "配置细节详见 §3.2 的说明。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "SECTION-SIGN" and hits[0].count == 1, hits)


@case
def section_sign_negative_inline_code():
    text = "参数 `§3.2` 照抄。\n"
    expect(scan_text(text, "a.md") == [])


@case
def section_sign_negative_inside_fence():
    text = "```md\n§ 引用块\n```\n"
    expect(scan_text(text, "a.md") == [])


@case
def arrow_positive_prose_hit():
    text = "引入缓存 → 延迟下降。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "ARROW" and hits[0].count == 1, hits)


@case
def arrow_negative_inline_code():
    text = "写法 `现象 → 修法` 是旧格式。\n"
    expect(scan_text(text, "a.md") == [])


@case
def arrow_negative_inside_fence():
    text = "```md\nA → B\n```\n"
    expect(scan_text(text, "a.md") == [])


@case
def emoji_positive_prose_hit():
    text = "🚀 快速开始：先跑安装命令。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "EMOJI" and hits[0].count == 1, hits)


@case
def emoji_positive_bullet_lead():
    text = "- ✨ 亮点\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "EMOJI", hits)


@case
def emoji_negative_midline():
    # 规则面（装饰性 emoji）比脚本面（行首锚定）宽：行中装饰 emoji 由 reviewer 补齐，不进候选
    text = "文中提到 🚀 命令。\n"
    expect(scan_text(text, "a.md") == [])


@case
def emoji_negative_table_symbols():
    text = "| a | ✅ |\n跑完 ✓ 检查。\n★ 推荐\n⚠ 注意\n"
    expect(scan_text(text, "a.md") == [])


@case
def emoji_negative_inline_code():
    text = "参数 `--icon 🚀` 照抄。\n"
    expect(scan_text(text, "a.md") == [])


@case
def emoji_negative_inside_fence():
    text = "```md\n🚀 标题\n```\n"
    expect(scan_text(text, "a.md") == [])


@case
def width_mix_positive_comma_adjacent():
    text = "我们先看延迟, 再看成本。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "WIDTH-MIX" and hits[0].count == 1, hits)


@case
def width_mix_positive_paren_contains_cjk():
    text = "部署 Redis(cache 层) 作为缓存。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "WIDTH-MIX" and hits[0].count == 1, hits)


@case
def width_mix_positive_exclamation_after_cjk():
    text = "现在就开始! 完成。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "WIDTH-MIX", hits)


@case
def width_mix_positive_comma_after_latin():
    text = "Runbook 写着 'Roll back first, then investigate', 但我们没有回滚。\n"
    hits = scan_text(text, "a.md")
    expect(len(hits) == 1 and hits[0].pid == "WIDTH-MIX" and hits[0].count == 1, hits)


@case
def width_mix_negative_numeric_and_coords():
    # 豁免清单成反例：时间 / 比例 / file:line / md 链接里的半角合法
    text = "故障 12:30 发生，延迟比 3:1，详见 [手册](redis.conf:42)。\n"
    expect(scan_text(text, "a.md") == [])


@case
def width_mix_negative_english_label_heading():
    # Step 1: 与 file:章节名 式 Latin 后冒号属标签 / 坐标，反向不收（本 skill 自身标题即此风格）
    text = "### Step 1: 收集输入\n详见 file:章节名 式坐标。\n"
    expect(scan_text(text, "a.md") == [])


@case
def width_mix_negative_link_target_anchor():
    # 中文标题锚的链接目标经掩码豁免（链接闭括号后紧跟汉字曾是系统性误报源）
    text = "路由见[章节](#step-3-形态路由)的说明。\n"
    expect(scan_text(text, "a.md") == [])


@case
def width_mix_negative_english_clause_boundary():
    # ! 属英文小句句末，反向邻接不收（反向只收 ,;）
    text = "Run it now! 现在回滚。\n"
    expect(scan_text(text, "a.md") == [])


@case
def width_mix_negative_inline_code():
    text = "参数 `Redis(缓存)` 照抄。\n"
    expect(scan_text(text, "a.md") == [])


@case
def width_mix_negative_inside_fence():
    text = "```\nredis.conf:42, 行内\n```\n"
    expect(scan_text(text, "a.md") == [])


@case
def directory_scan_prunes_vendor_dirs():
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "doc.md"
        doc.write_text("正常句子。\n", encoding="utf-8")
        nm = Path(td) / "node_modules"
        nm.mkdir()
        (nm / "dep.md").write_text("句子" + DASH + "尾巴。\n", encoding="utf-8")
        git = Path(td) / ".git" / "hooks"
        git.mkdir(parents=True)
        (git / "h.md").write_text("句子" + DASH + "尾巴。\n", encoding="utf-8")
        found = iter_targets(Path(td))
        expect([f.name for f in found] == ["doc.md"], found)
        # 显式点名的 vendor 内文件照扫
        expect(iter_targets(nm / "dep.md") == [nm / "dep.md"], found)


@case
def rule_pointers_resolve_in_catalog():
    catalog = (Path(__file__).resolve().parent.parent / "ref" / "catalog.md").read_text(encoding="utf-8")
    for pat in PATTERNS:
        name = pat.rule.split("\u201c")[1].split("\u201d")[0]
        expect("- **" + name in catalog, pat)


@case
def cli_contract():
    with tempfile.TemporaryDirectory() as td:
        md = Path(td) / "doc.md"
        md.write_text("句子" + DASH + "尾巴。\n", encoding="utf-8")
        script = Path(__file__).resolve().parent.parent / "tools" / "scan_fingerprints.py"
        for extra, check in ((["--json"], "DASH"), ([], "INFO")):
            proc = subprocess.run(
                [sys.executable, str(script), str(md)] + extra,
                capture_output=True,
                text=True,
                universal_newlines=True,
            )
            expect(proc.returncode == 0, proc)  # 候选即提示，不是门禁
            expect(check in proc.stdout, (extra, proc.stdout))
        proc = subprocess.run([sys.executable, str(script), str(md), "--json"], capture_output=True, text=True)
        data = json.loads(proc.stdout)
        expect(data[0]["file"] == str(md) and data[0]["count"] == 1, data)


@case
def cli_missing_path_fails_loudly():
    # 缺路径静默退 0 会把"扫了个寂寞"伪装成"零命中"（本 skill 自审时踩过写错路径）
    with tempfile.TemporaryDirectory() as td:
        script = Path(__file__).resolve().parent.parent / "tools" / "scan_fingerprints.py"
        proc = subprocess.run([sys.executable, str(script), str(Path(td) / "nope.md")], capture_output=True, text=True)
        expect(proc.returncode != 0, proc)
        expect("ERROR" in proc.stderr, proc.stderr)


def main() -> int:
    failures = []
    for fn in CASES:
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{fn.__name__}: {exc}")
    for name in failures:
        print("FAIL", name)
    print(f"{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

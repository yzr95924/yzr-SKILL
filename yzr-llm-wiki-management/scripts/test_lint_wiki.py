#!/usr/bin/env python3
"""test_lint_wiki.py — lint_wiki.py 的端到端测试（聚焦 check_related_links）

stdlib unittest + subprocess 调真实脚本（无 mock）：在 tmp 目录搭最小 scratch
wiki，断言 related / compared 字段的路径基准（spec §9「wiki 根相对」= **内容根
`wiki/` 相对**）解析正确——spec 形式 `concepts/X.md` 命中真实文件时不报
`related-broken-link`；真坏链接仍报。

背景：0.22.0 引入 `check_related_links` 时 `target = wiki_root / item` 误把 spec
的内容根相对路径（`concepts/X.md`）当**最外层根相对**解析（缺 `wiki/` 段，因为
`wiki_root` 是 `<wiki>/`，真实文件在 `<wiki>/wiki/concepts/X.md`），导致按 spec
正确写的 related 必被误报 `related-broken-link`。本测试覆盖该基准 bug——改 lint
前 test_spec_form_* / test_compared_field_* 失败，改后全绿。

运行:
  python3 scripts/test_lint_wiki.py        # 在 skill 仓根或 scripts/ 下均可
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "lint_wiki.py"

_INDEX_MD = """\
---
title: Idx
description: d
type: index
tags: []
created: 2026-07-21
updated: 2026-07-21
---
# Idx
"""

_LOG_MD = """\
---
title: Log
description: d
type: log
tags: []
created: 2026-07-21
updated: 2026-07-21
---
# Log

## 2026-07-21 setup
- init
"""


def _page(title, ptype, extra=""):
    """生成一页 markdown：5 必填 frontmatter + 可选 extra 字段行 + 空 H1 正文。"""
    fm = (
        "---\n"
        f"title: {title}\n"
        "description: d\n"
        f"type: {ptype}\n"
        "tags: []\n"
        "created: 2026-07-21\n"
        "updated: 2026-07-21\n"
        f"{extra}"
        "---\n"
    )
    return fm + f"# {title}\n"


def build_minimal_wiki(root):
    """搭最小可跑通的 scratch wiki（wiki/index.md + log.md + raw/）。"""
    root = Path(root)
    (root / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "index.md").write_text(_INDEX_MD, encoding="utf-8")
    (root / "wiki" / "log.md").write_text(_LOG_MD, encoding="utf-8")
    return root


def run_lint(root):
    """跑 lint_wiki.py --no-git，返回 (exit_code, stdout)。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(root), "--no-git"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return proc.returncode, proc.stdout


class RelatedLinksResolutionTest(unittest.TestCase):
    def test_spec_form_concepts_relative_not_reported(self):
        """spec §9 约定的 wiki 根相对形式 concepts/beta.md（基准 = 内容根 wiki/）
        命中真实文件 wiki/concepts/beta.md 时，不应报 related-broken-link。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = build_minimal_wiki(tmp)
            (root / "wiki" / "concepts" / "beta.md").write_text(_page("Beta", "concept"), encoding="utf-8")
            (root / "wiki" / "concepts" / "alpha.md").write_text(
                _page("Alpha", "concept", extra="related: [concepts/beta.md]\n"), encoding="utf-8"
            )
            _, stdout = run_lint(root)
        self.assertNotIn("related-broken-link", stdout, f"spec 形式不应误报：\n{stdout}")

    def test_genuinely_missing_target_still_reported(self):
        """真坏链接（目标确实不存在）仍须报 related-broken-link——确保基准修正没把检查改瞎。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = build_minimal_wiki(tmp)
            (root / "wiki" / "concepts" / "alpha.md").write_text(
                _page("Alpha", "concept", extra="related: [concepts/nonexistent.md]\n"), encoding="utf-8"
            )
            _, stdout = run_lint(root)
        self.assertIn("related-broken-link", stdout, "真坏链接应被报出：\n" + stdout)

    def test_compared_field_same_semantics(self):
        """compared 字段与 related 同语义（spec §9 同基准）——wiki 根相对形式同样不应误报。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = build_minimal_wiki(tmp)
            (root / "wiki" / "comparisons").mkdir(parents=True, exist_ok=True)
            (root / "wiki" / "concepts" / "beta.md").write_text(_page("Beta", "concept"), encoding="utf-8")
            (root / "wiki" / "comparisons" / "cmp.md").write_text(
                _page("Cmp", "comparison", extra="compared: [concepts/beta.md]\n"), encoding="utf-8"
            )
            _, stdout = run_lint(root)
        self.assertNotIn("related-broken-link", stdout, f"compared spec 形式不应误报：\n{stdout}")


if __name__ == "__main__":
    unittest.main()

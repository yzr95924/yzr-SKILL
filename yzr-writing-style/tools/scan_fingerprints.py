#!/usr/bin/env python3
"""扫描 Markdown 里规则集可机械判定的候选（装饰符号 / 标点宽度 / 全角符号，仅字面 / 正则命中）。"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional

DASH = "\u2014\u2014"  # 中文双破折号"——"
CORNER_QUOTE = "\u300c"  # 中文左角引号"「"（成对符号，开侧计一次）
# Unicode 箭头区段；ASCII 的 -> / => 属 Mermaid 与命令行常打，不收
ARROW_RE = r"[\u2190-\u21ff\u2794-\u27be\u27f0-\u27ff\u2900-\u297f\u2b00-\u2b19]"
# 段落开头的装饰性 emoji 与图形符号（★ ● ▶ ▲ 等）；✓ ✗ ⚠ 表格中的 ✅ 等是技术文档正当用法，靠行首锚定排除
EMOJI_RE = r"^\s*(?:[-*+]\s+)?[\U0001F300-\U0001FAFF\u2728\u26A1\u274C\u2705\u2757\u2764\u2605\u25CF\u25B6\u25B2]"
# 标点宽度候选（规则集"标点宽度"）：正向收 CJK 紧邻的半角 ,;:!?；反向只收 ,; 与括号。
# !? 可归英文小句句末、: 反向多为 Latin 标签 / 坐标（Step 1:、file:章节名），收则误报成灾
_CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"  # 独立分发 skill，不跨目录 import 共用正则
WIDTH_MIX_RE = (
    rf"[{_CJK}][,;:!?](?!\d)"  # (?!\d) 放行 file:42、比例等"汉字后冒号 + 数字"的坐标 / 数值语境
    rf"|[,;]\s?[{_CJK}]"
    rf"|[{_CJK}]\(|\)[{_CJK}]"
    rf"|\([^)]*[{_CJK}][^)]*\)"
)
# 全角 ASCII 变体区 U+FF01-FF5E 加全角空格 U+3000，减去合法全角标点白名单
# （！，（）：；？［］｛｝）；白名单外的全角字母 / 数字 / 符号行文一律不用（规则集"全角符号"）
FULLWIDTH_FORM_RE = (
    "[\uff02-\uff07\uff0a-\uff0b\uff0d-\uff19\uff1c-\uff1e"
    "\uff20-\uff3a\uff3c\uff3e-\uff40\uff41-\uff5a\uff5c\uff5e\u3000]"
)
# CJK 邻接的半角双引号：中文行文引号用弯引号“”（U+201C/201D），半角 " 属混用；英文行文的 " 不邻 CJK 不收
QUOTE_MIX_RE = rf"[{_CJK}]\"|\"[{_CJK}]"

# 目录递归在 vendor / 产物目录处剪枝；显式点名的路径（文件或目录本身）不过滤
DEFAULT_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", "site-packages", "venv", ".venv"}

# 扩展契约：PATTERNS 只收字面 / 正则命中（不做判断），新增模式须配正反夹具
# （tools/tests/smoke_test_scan_fingerprints.py），规则文案归 SKILL.md 规则集；
# 元提及（讨论符号本身的行）有意上报，由调用方豁免。


class Pattern(NamedTuple):
    """一条模式：pid / 字面 / 规则集规则文案。"""

    pid: str
    literal: str
    rule: str
    regex: Optional[str] = None  # 置位时按正则计数，literal 留空


PATTERNS = [
    Pattern("DASH", DASH, "规则集\u201c装饰符号\u201d行"),
    Pattern("CORNER-QUOTE", CORNER_QUOTE, "规则集\u201c装饰符号\u201d行"),
    Pattern("ARROW", "", "规则集\u201c装饰符号\u201d行", ARROW_RE),
    Pattern("EMOJI", "", "规则集\u201c装饰符号\u201d行", EMOJI_RE),
    Pattern("WIDTH-MIX", "", "规则集\u201c标点宽度\u201d行", WIDTH_MIX_RE),
    Pattern("QUOTE-MIX", "", "规则集\u201c标点宽度\u201d行", QUOTE_MIX_RE),
    Pattern("FULLWIDTH-FORM", "", "规则集\u201c全角符号\u201d行", FULLWIDTH_FORM_RE),
]

FENCE = re.compile(r"^\s*(?:```|~~~)")
# 行内代码段：先双反引号后单反引号
CODE_SPANS = (re.compile(r"``[^`\n]+``"), re.compile(r"`[^`\n]*`"))
# markdown 链接目标 ](...) 与行内代码同理非行文标点：中文标题锚 / file:line 式坐标不该计入命中
LINK_DEST = re.compile(r"\]\([^)]*\)")


class Hit(NamedTuple):
    """一条候选命中：文件 / 行 / 模式 / 计数 / 证据片段 / 规则文案。"""

    file: str
    line: int
    pid: str
    count: int
    evidence: str
    rule: str


def mask_nonprose(line: str) -> str:
    """把行内代码段与链接目标替换为等长空格，避免非行文内容计入命中。"""
    for span in CODE_SPANS:
        line = span.sub(lambda m: " " * len(m.group(0)), line)
    return LINK_DEST.sub(lambda m: "]" + " " * (len(m.group(0)) - 1), line)


def _match_line(raw: str, rel: str, lineno: int) -> List[Hit]:
    """扫描单行：逐模式收集候选命中；证据取 strip 后前 80 字符。"""
    hay = mask_nonprose(raw)
    snippet = raw.strip()
    if len(snippet) > 80:
        snippet = snippet[:80] + "…"
    hits: List[Hit] = []
    for pat in PATTERNS:
        count = len(re.findall(pat.regex, hay)) if pat.regex else hay.count(pat.literal)
        if count:
            hits.append(Hit(rel, lineno, pat.pid, count, snippet, pat.rule))
    return hits


def scan_text(text: str, rel: str) -> List[Hit]:
    """扫描一段 Markdown，返回候选命中；围栏与非行文内容跳过。"""
    hits: List[Hit] = []
    in_fence = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue
        if not in_fence:
            hits.extend(_match_line(raw, rel, lineno))
    return hits


def iter_targets(root: Path) -> List[Path]:
    """文件直接返回；目录递归列出全部 md，在 vendor 目录处剪枝（不进入其子树）。"""
    if root.is_file():
        return [root]
    found: List[Path] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS)
        found.extend(Path(base) / name for name in files if name.endswith(".md"))
    return sorted(found)


def run(paths: List[str]) -> List[Hit]:
    """对多个路径跑扫描，rel 相对当前工作目录计算（失败时用原路径）。"""
    cwd = Path.cwd()
    hits: List[Hit] = []
    for p in paths:
        target = Path(p)
        for md in iter_targets(target):
            try:
                text = md.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                print(f"WARNING: {md} 非 UTF-8，跳过", file=sys.stderr)
                continue
            try:
                rel = str(md.resolve().relative_to(cwd))
            except ValueError:
                rel = str(md)
            hits.extend(scan_text(text, rel))
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：打印候选（--json 机器可读）。"""
    epilog = (
        "退出码：0 = 扫描完成（命中不是门禁），1 = 路径缺失。\n"
        "输入：markdown 文件或目录；目录递归只收 .md，在 .git / node_modules 等 vendor 目录处剪枝。\n"
        "豁免：代码围栏、行内代码、markdown 链接目标不计命中；非 UTF-8 文件跳过并告警。\n"
        "元提及（讨论符号本身的行）有意上报，由调用方豁免。"
    )
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0], epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="+", help="要扫描的 markdown 文件或目录")
    parser.add_argument("--json", action="store_true", dest="as_json", help="机器可读输出")
    args = parser.parse_args(argv)
    missing = [p for p in args.paths if not Path(p).exists()]
    if missing:
        for p in missing:
            print(f"ERROR: {p} 不存在", file=sys.stderr)
        return 1
    hits = run(args.paths)
    if args.as_json:
        print(json.dumps([h._asdict() for h in hits], ensure_ascii=False, indent=1))
    else:
        for h in hits:
            print(f"INFO: {h.file}:{h.line} {h.pid} {h.evidence}")
        print(f"candidates: {len(hits)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

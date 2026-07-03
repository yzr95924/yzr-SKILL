#!/usr/bin/env python3
"""
Step 5 覆盖率验证：比对原 CLAUDE.md 与迁移后的 AGENTS.md + 薄壳 CLAUDE.md，
逐行检查原文的 ascii 信息点（路径 / 命令 / 标识符）是否在新结构里保留。

原理：迁移会改写中文措辞并去品牌（Claude Code → agent），但**事实性 ascii 标识符**（如
`outline-wiki-upload`、`run_eval.py`、`create_attachment`）应当保留。本脚把每条原文行的高信号
ascii token 拿去新结构里找：找不到 = 该行信息点可能丢失，需人工复核。

用法：
    python3 scripts/coverage.py [project-root] [--threshold 0.5] [--min-tokens 4]

退出码：
    0  源文件可读、比对完成（无论是否 flag——本脚是 advisory）
    1  硬错误（找不到 Step 1 快照的源文件）

局限（诚实声明）：
    - 纯中文 / 无 ascii 的行无法用此法评估，会跳过并计数——这些行需人工确认。
    - flag 不等于丢失：可能是去品牌改写 / 合理下沉到 MEMORY。输出里会给每条 flag
      "最佳匹配位置"，辅助判断。
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap sys.path：保持 `python3 -m scripts.coverage` 与 `python3 scripts/coverage.py` 一致。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 去品牌归一化：原文 "Claude/CC" 在新结构里已改成 "agent"——归一后两者才匹配。
ALIAS: Dict[str, str] = {
    "claude": "agent",
    "cc": "agent",
}

# 极常见英文虚词 / 通用词，信噪比低，不计入比对。
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "was",
    "but",
    "not",
    "you",
    "your",
    "can",
    "will",
    "into",
    "when",
    "then",
    "than",
    "via",
    "per",
    "all",
    "new",
    "use",
    "used",
    "using",
    "its",
    "their",
    "have",
    "has",
    "had",
    "been",
    "they",
    "them",
    "which",
    "what",
    "where",
    "how",
    "who",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """小写 → 抽 ascii 字母数字 run → 去品牌归一 → 去 <3 字符 / 虚词。"""
    out = []
    for tok in TOKEN_RE.findall(text.lower()):
        tok = ALIAS.get(tok, tok)
        if len(tok) < 3 or tok in STOPWORDS:
            continue
        out.append(tok)
    return out


def read_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def collect_targets(root: Path) -> List[Tuple[str, int, str, frozenset]]:
    """返回 [(file_label, lineno, line_text, token_set), ...] 遍历所有目标文件。"""
    targets: List[Tuple[str, int, str, frozenset]] = []
    candidates: List[Tuple[str, Path]] = []
    agents = root / "AGENTS.md"
    if agents.exists():
        candidates.append(("AGENTS.md", agents))
    claude = root / "CLAUDE.md"
    if claude.exists():
        candidates.append(("CLAUDE.md(thin)", claude))
    for label, path in candidates:
        for i, line in enumerate(read_lines(path), 1):
            toks = frozenset(tokenize(line))
            targets.append((label, i, line, toks))
    return targets


def overlap_coeff(a: frozenset, b: frozenset) -> float:
    """Szymkiewicz–Simpson：|A∩B| / min(|A|,|B|)。语义＝"A 的 token 有多少出现在 B"。"""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def coverage(root: Path, threshold: float, min_tokens: int) -> Tuple[List[str], int, int]:
    """返回 (报告行, flag 数, 评估行数)。"""
    src = root / ".migration-backup" / "CLAUDE.md.original"
    lines = []
    if not src.exists():
        lines.append(f"[硬错误] 找不到源文件 {src}——Step 1 应先快照原 CLAUDE.md 到此处。")
        return lines, -1, 0

    targets = collect_targets(root)
    if not targets:
        lines.append("[硬错误] 目标侧无文件：AGENTS.md / CLAUDE.md 都不存在。")
        return lines, -1, 0

    total = 0
    evaluated = 0
    covered = 0
    skipped_no_ascii = 0
    flagged: List[str] = []

    for i, line in enumerate(read_lines(src), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue
        total += 1
        toks = frozenset(tokenize(stripped))
        if len(toks) < min_tokens:
            # 纯中文 / ascii 标识符太少——token 法无法评估，跳过。
            skipped_no_ascii += 1
            continue
        evaluated += 1

        best = 0.0
        best_at: Optional[Tuple[str, int]] = None
        for label, lineno, _tline, ttoks in targets:
            score = overlap_coeff(toks, ttoks)
            if score > best:
                best = score
                best_at = (label, lineno)
        if best >= threshold:
            covered += 1
        else:
            where = f"{best_at[0]}:{best_at[1]}" if best_at else "?"
            flagged.append(f"  L{i} [overlap={best:.2f} @ {where}] tokens={sorted(toks)}\n    {stripped[:100]}")

    pct = (covered / evaluated * 100) if evaluated else 0.0
    lines.append(f"源文件：{src}")
    lines.append("目标：AGENTS.md + 薄壳 CLAUDE.md")
    lines.append(
        f"原文非空行 {total}，参与比对 {evaluated}（ascii token ≥ {min_tokens}），"
        f"跳过 {skipped_no_ascii}（纯中文 / 标识符过少，需人工确认）"
    )
    lines.append(f"覆盖率：{covered}/{evaluated} = {pct:.1f}%  （阈值 {threshold}）")
    lines.append(f"flag（可能丢失 / 需复核）：{len(flagged)}")
    if flagged:
        lines.append("-" * 60)
        lines.extend(flagged[:80])
        if len(flagged) > 80:
            lines.append(f"  … 还有 {len(flagged) - 80} 条，详见源（调整 --threshold 可收紧 / 放宽）")
    return lines, len(flagged), evaluated


def main() -> int:
    ap = argparse.ArgumentParser(description="Step 5 覆盖率验证")
    ap.add_argument("root", nargs="?", default=".", help="项目根（默认 cwd）")
    ap.add_argument("--threshold", type=float, default=0.5, help="overlap 阈值（默认 0.5）")
    ap.add_argument("--min-tokens", type=int, default=4, help="行参与比对的最低 token 数（默认 4）")
    args = ap.parse_args()

    lines, flag_count, evaluated = coverage(Path(args.root).resolve(), args.threshold, args.min_tokens)
    print("\n[coverage] Step 5 覆盖率验证")
    print("-" * 60)
    for ln in lines:
        print(ln)
    print("-" * 60)
    if flag_count < 0:
        print("结论：硬错误，未完成比对。")
        return 1
    if flag_count == 0:
        print("结论：无 flag——参与比对的行全部覆盖。记得人工复核被跳过的纯中文行。")
    else:
        print("结论：有 flag——逐条确认是「真丢失」还是「去品牌改写 / 下沉到 MEMORY」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

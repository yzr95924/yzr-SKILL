#!/usr/bin/env python3
"""
Step 5 覆盖率验证：比对原 CLAUDE.md 与迁移后的 AGENTS.md + 薄壳 CLAUDE.md，
逐行检查原文的 ascii 信息点（路径 / 命令 / 标识符）是否在新结构里保留。

原理：迁移会改写中文措辞并去品牌（Claude Code → agent），但**事实性 ascii 标识符**（如
`yzr-outline-wiki-upload`、`run_eval.py`、`create_attachment`）应当保留。本脚把每条原文行的高信号
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

import yaml

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

# 完整 memory frontmatter 三件套约束（参见本仓库 AGENTS.md「仓库规约」段——禁止无 frontmatter 起手）。
# 与 yzr-skill-creator 的 DESCRIPTION_MAX_CHARS（SKILL description 上限）是两套独立常量，本脚本不复用。
ALLOWED_MEMORY_TYPES = frozenset({"user", "feedback", "project", "reference"})
MEMORY_DESCRIPTION_MAX_CHARS = 200


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


def _extract_preamble(text: str) -> str:
    r"""提取 AGENTS.md 的前导区：首个 H1（`# ...`）之后、首个 `## ` 之前的文本。

    顶部强制 Read 指令必须落在此区（agent 加载 AGENTS.md 第一屏读到）。无 H1 或无 `## ` 时返回
    H1 之后的全部文本（容错）。
    """
    m = re.search(r"^# .+$\n([\s\S]*?)(?=^## )", text, re.MULTILINE)
    return m.group(1) if m else ""


def check_memory_sync(root: Path) -> List[str]:
    r"""校验 R2 记忆 `@import` 收口的几何（R2：AGENTS.md 顶部强制 Read 指令 + @MEMORY/MEMORY.md 单行）。

    检查三件事：
    1. `MEMORY/MEMORY.md` 存在——L2 索引的真源在此，缺则 R2 引用会指向空气。
    2. AGENTS.md 有且仅有一行 `@MEMORY/MEMORY.md`——多行（说明重复挂）或缺失（说明走的是旧方案 /
       已改为内联）都算违反。
    3. AGENTS.md 顶部（H1 后、首个 `##` 前）有强制 Read 指令 blockquote（含 `@` + Read 两特征）——
       通吃所有 agent：自动展开 `@import` 的读了无害，不展开的据此读 `@` 引用。缺则 L2 对不展开的不可见。
    4. AGENTS.md 不再含旧内联形态（一堆 `- [标题](MEMORY/<slug>.md) — …`）——内联 + @import
       两套并存让 L1 词数翻倍，诊断时按旧内联残留处理。

    无 MEMORY/ 或无 AGENTS.md 时返回空（不适用）。返回的报告行前缀沿用旧 [OK]/[不同步]，便于 caller
    grep。
    """
    lines: List[str] = []
    memory = root / "MEMORY"
    agents = root / "AGENTS.md"
    if not memory.is_dir() or not agents.exists():
        return lines

    memory_index = memory / "MEMORY.md"
    text = agents.read_text(encoding="utf-8", errors="replace")

    # 1) MEMORY/MEMORY.md 真源
    if not memory_index.exists():
        lines.append("  [不同步] MEMORY/MEMORY.md 真源缺失——@MEMORY/MEMORY.md 引用会指向空气")
    else:
        lines.append(f"  [OK] MEMORY/MEMORY.md 存在（{memory_index.stat().st_size} 字节）")

    # 2) @MEMORY/MEMORY.md 引用（精确匹配单行，避免误伤 HTML 注释里提到 `@MEMORY/MEMORY.md` 的说明）
    import_hits = [ln for ln in text.splitlines() if ln.strip() == "@MEMORY/MEMORY.md"]
    if not import_hits:
        lines.append("  [不同步] AGENTS.md 缺 `@MEMORY/MEMORY.md` 单行引用——记忆段未走 R2 收口")
    elif len(import_hits) > 1:
        lines.append(f"  [不同步] `@MEMORY/MEMORY.md` 出现 {len(import_hits)} 行——R2 要求单行")
    else:
        lines.append("  [OK] AGENTS.md 含单行 `@MEMORY/MEMORY.md` 引用")

    # 3) 顶部强制 Read 指令（前导区 blockquote，含 `@` + Read 两特征——通吃所有 agent）
    preamble = _extract_preamble(text)
    top_directive = bool(preamble) and bool(
        re.search(r"^>.*@.*$", preamble, re.MULTILINE)
        and re.search(r"^>.*Read", preamble, re.MULTILINE | re.IGNORECASE)
    )
    if not top_directive:
        lines.append("  [不同步] AGENTS.md 缺顶部强制 Read 指令——不展开 @import 的 agent 拿不到 @ 引用")
    else:
        lines.append("  [OK] AGENTS.md 含顶部强制 Read 指令（H1 后 blockquote）")

    # 4) 旧内联形态检测（R2 已废弃；与 @import 同时存在会让 L1 词数翻倍）
    # 判"`- [标题](MEMORY/<slug>.md) — ...`"行 ≥ 2（容忍 1 行示例 / 单条引用）
    legacy_inline = len(re.findall(r"^- \[[^\]]+\]\(MEMORY/[^)]+\.md\)\s*[—–-]", text, re.MULTILINE))
    if legacy_inline >= 2:
        lines.append(
            f"  [不同步] AGENTS.md 含 {legacy_inline} 行旧内联记忆索引——"
            "与 @import 并存会双写 / 词数翻倍，按 R2 迁回 MEMORY.md"
        )
    else:
        lines.append("  [OK] AGENTS.md 不含旧内联记忆索引形态")

    return lines


def parse_memory_frontmatter(text: str) -> Tuple[Optional[dict], Optional[str]]:
    """解析 MEMORY/<slug>.md 开头的 YAML frontmatter。返回 (meta, error_msg)。

    失败情形（首行非 --- / 第二 --- 缺失 / YAML 解析错 / 非映射）→ 返回 (None, 错误描述字符串)。
    成功返回 (dict, None)。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "缺 frontmatter 起手标记 ---（首行必须以 --- 开头）"
    end: Optional[int] = None
    for i, ln in enumerate(lines[1:], 1):
        if ln.strip() == "---":
            end = i
            break
    if end is None:
        return None, "frontmatter 未闭合（缺第二个 ---）"
    yaml_block = "\n".join(lines[1:end])
    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError as e:
        return None, f"YAML 解析失败：{e}"
    if not isinstance(meta, dict):
        return None, "frontmatter 非映射（应为 key: value 形式）"
    return meta, None


def check_memory_frontmatter(root: Path) -> List[str]:
    r"""校验 MEMORY/<slug>.md frontmatter 三件套合法性（AGENTS.md「仓库规约」约定）。

    本仓库的"完整 memory"必须带 YAML frontmatter 三件套——`name`（必须等于文件 slug）/
    `description`（一行 ≤ 200 字符事实摘要，供 recall 阶段 relevance 判定）/
    `metadata.type`（四选一 user / feedback / project / reference）。短 memory 走 MEMORY.md
    索引行（不是单文件），不在本函数范围。

    检查逐文件：
    1. 文件首行 --- 起手 + 第二 --- 闭合——三件套的载体
    2. `name` 字段非空且等于文件 stem（kebab-case slug）
    3. `description` 字段是字符串、非空、**单行**（不含 `\n`）、≤ 200 字符
    4. `metadata.type` ∈ ALLOWED_MEMORY_TYPES

    无 MEMORY/ 或无 <slug>.md 单文件时返回空。报告行前缀 [OK]/[违规] 区分通过与不通过。
    """
    memory = root / "MEMORY"
    if not memory.is_dir():
        return []

    files = sorted(p for p in memory.glob("*.md") if p.name != "MEMORY.md")
    if not files:
        return []

    pass_count = 0
    fail_count = 0
    detail: List[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, err = parse_memory_frontmatter(text)
        issues: List[str] = []

        if err:
            issues.append(err)
        else:
            slug = path.stem
            name = meta.get("name")
            if name != slug:
                issues.append(f"name 字段={name!r} ≠ 文件 slug={slug!r}")

            desc = meta.get("description")
            if not isinstance(desc, str) or not desc.strip():
                issues.append("description 缺 / 非字符串 / 仅空白")
            elif "\n" in desc or len(desc) > MEMORY_DESCRIPTION_MAX_CHARS:
                issues.append(
                    f"description {len(desc)} 字符 / 含换行——AGENTS.md 要求单行（≤ {MEMORY_DESCRIPTION_MAX_CHARS} 字符）"
                )

            metadata = meta.get("metadata") or {}
            if not isinstance(metadata, dict):
                issues.append("metadata 缺 / 非映射")
            else:
                typ = metadata.get("type")
                if typ not in ALLOWED_MEMORY_TYPES:
                    issues.append(f"metadata.type={typ!r} 不在 {sorted(ALLOWED_MEMORY_TYPES)}")

        if issues:
            fail_count += 1
            detail.append(f"  [违规] {path.name}")
            for issue in issues:
                detail.append(f"    - {issue}")
        else:
            pass_count += 1
            detail.append(f"  [OK] {path.name}")

    summary = f"[统计] {pass_count} 合规 / {fail_count} 不合规 （共 {len(files)} 个 MEMORY/<slug>.md 文件）"
    return [summary] + detail


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

    # 记忆索引一致性（R2 @import 收口）：MEMORY.md 存在 / AGENTS.md 单行引用 / 顶部强制 Read 指令 / 无旧内联形态
    mem_sync = check_memory_sync(root)
    if mem_sync:
        lines.append("-" * 60)
        lines.append("记忆索引一致性（R2 @import 收口）：")
        lines.extend(mem_sync)
    return lines, len(flagged), evaluated


def main() -> int:
    ap = argparse.ArgumentParser(description="Step 5 覆盖率验证")
    ap.add_argument("root", nargs="?", default=".", help="项目根（默认 cwd）")
    ap.add_argument("--threshold", type=float, default=0.5, help="overlap 阈值（默认 0.5）")
    ap.add_argument("--min-tokens", type=int, default=4, help="行参与比对的最低 token 数（默认 4）")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    lines, flag_count, evaluated = coverage(root, args.threshold, args.min_tokens)
    print("\n[coverage] Step 5 覆盖率验证")
    print("-" * 60)
    for ln in lines:
        print(ln)
    print("-" * 60)

    # frontmatter 三件套合法性独立打印：不依赖 Step 1 快照存在，
    # 用户哪怕没跑迁移、只想体检 MEMORY 也能用。
    fm_sync = check_memory_frontmatter(root)
    if fm_sync:
        print("-" * 60)
        print("记忆正文 frontmatter 三件套合法性：")
        for ln in fm_sync:
            print(ln)
        print("-" * 60)
        # 三件套有违规时非零退出，让 CI 能挂住（advisory 用可忽略）
        fail_count = sum(1 for ln in fm_sync if "[违规]" in ln)
        if fail_count and flag_count >= 0:
            print(f"结论：frontmatter 违规 {fail_count} 处——补 name/description/metadata.type 后再跑。")
            return 1

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

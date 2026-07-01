#!/usr/bin/env python3
"""
lint_wiki.py — deterministic 健康检查

跑 references/lint-checklist.md 的 §二（deterministic 全部项）+ external symlink 检查。
半定性检查（§三，矛盾主张 / 缺失交叉引用等需理解语义的）由 agent 现场做。

用法：
  python3 lint_wiki.py [<WIKI_ROOT>] [--severity <LEVEL>] [--no-git]

--severity 过滤：error | warn | info | all（默认 all）
--no-git 跳过 raw/ 的 git status 检查（CI 或裸仓场景）。默认**自动检测**：
  仅当 wiki 根目录在 git 仓内且 raw/ 被 git 跟踪时才跑 raw 不可变性检查；
  裸目录树 / 无 git / raw 未纳入 git → 自动跳过并打印提示（不报错，不阻断）。

退出码：
- 0 = 全部指定严重性级别内无 finding
- 1 = 有 finding
- 2 = 运行错误
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set

# 复用 ingest_diff 的轻量 frontmatter 解析
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_diff import parse_frontmatter_simple  # noqa: E402
from log_format import LOG_LINE_RE  # noqa: E402

VALID_TYPES = {"entity", "concept", "source", "comparison", "synthesis"}
WIKI_SUBDIRS = ("entities", "concepts", "sources", "comparisons", "syntheses")
MEMORY_SUBDIR = "MEMORY"
EXTERNAL_SUBDIR = "external"
ANCHOR_FILENAME = ".symlink-anchor.json"
MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
EXTERNAL_URL_RE = re.compile(r"^(https?:|mailto:|//)")
SOURCE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# 严重性等级
SEV_RANK = {"error": 0, "warn": 1, "info": 2}


def is_external_url(url: str) -> bool:
    return bool(EXTERNAL_URL_RE.match(url.strip()))


def find_md_files(wiki_root: Path) -> Dict[str, List[Path]]:
    """收集所有 wiki/**/*.md，按 type 分类（用子目录名判定）

    MEMORY 子目录扫到独立的 'memory' 桶：走 frontmatter 校验但**不**强制 index 覆盖。
    """
    out = {
        "index": [],  # type: List[Path]
        "log": [],
        "entities": [],
        "concepts": [],
        "sources": [],
        "comparisons": [],
        "syntheses": [],
        "memory": [],
    }  # type: Dict[str, List[Path]]
    wiki_dir = wiki_root / "wiki"
    if not wiki_dir.is_dir():
        return out
    for sub in WIKI_SUBDIRS:
        d = wiki_dir / sub
        if d.is_dir():
            for p in sorted(d.glob("*.md")):
                out[sub].append(p)
    # MEMORY/ 单独扫：含 MEMORY.md（索引）+ 其它经验条目 .md
    mem_dir = wiki_dir / MEMORY_SUBDIR
    if mem_dir.is_dir():
        for p in sorted(mem_dir.glob("*.md")):
            out["memory"].append(p)
    out["index"].append(wiki_dir / "index.md")
    out["log"].append(wiki_dir / "log.md")
    return out


def is_git_repo(path: Path) -> bool:
    """判定 path 是否在 git 仓内（`.git/` 子目录存在即可，不依赖 git CLI）。

    wiki 默认是裸目录树，git 仅 setup 时 `--git` opt-in；本函数用于自动跳过
    无 git 场景下的 raw/ 不可变性检查，避免无脑报"raw 已被改"（无 git 时
    本来就没有"未提交改动"概念）。"""
    if not path.is_dir():
        return False
    cur = path.resolve()
    while True:
        if (cur / ".git").exists():
            return True
        parent = cur.parent
        if parent == cur:
            return False
        cur = parent


def check_raw_immutable(wiki_root: Path, use_git: bool) -> List[str]:
    """1. raw/ 是否被改（仅在 wiki 是 git 仓时跑；否则跳过）

    返回元组 (findings, skipped_reason)：
    - findings：原始改动列表（可能为空）
    - skipped_reason：跳过时的提示文本；未跳过时为空字符串。
      调用方决定怎么展示（lint 输出 / 退出码 / 副作用）。
    """
    if not use_git:
        return ([], "")
    raw_dir = wiki_root / "raw"
    if not raw_dir.is_dir():
        return ([], "")
    # 自动检测：不在 git 仓内就直接跳过，不依赖 git CLI；这是"裸目录树
    # wiki 默认支持"的关键路径——强假设 wiki 是 git 仓会让裸目录树误报。
    if not is_git_repo(wiki_root):
        return ([], "raw-immutable-skipped: 未启用 git（无 .git/），跳过 raw/ 不可变性检查")
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "raw/"],
            cwd=str(wiki_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except FileNotFoundError:
        # git CLI 不在 PATH（极少见，.git/ 存在但 git 没装）——同样跳过
        return ([], "raw-immutable-skipped: 未找到 git CLI，跳过 raw/ 不可变性检查")
    if result.returncode != 0:
        # 是 git 仓但 raw/ 没被 git 跟踪（`.gitignore` 忽略或从未 add）——
        # 这种情况没有"未提交改动"概念（git 一无所知），跳过
        return ([], "raw-immutable-skipped: raw/ 未纳入 git 跟踪，跳过 raw/ 不可变性检查")
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not lines:
        return ([], "")
    findings = [f"raw-modified: raw/ 有 {len(lines)} 处未提交改动：{lines[0]}{' ...' if len(lines) > 1 else ''}"]
    return (findings, "")


def _parse_anchor(anchor_path: Path):
    """解析 .symlink-anchor.json；返回 dict 或 None（损坏/缺字段）

    只校验最小必填字段（target / captured_at / kind）——扩展字段静默忽略。
    """
    import json  # 局部 import（函数内按需）

    try:
        data = json.loads(anchor_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    target = data.get("target")
    captured_at = data.get("captured_at")
    kind = data.get("kind")
    if not isinstance(target, str) or not target:
        return None
    if not isinstance(captured_at, str):
        return None
    if kind != "external-repo":
        return None
    return data


def check_external_symlinks(wiki_root: Path) -> List[str]:
    """10. raw/external/<source-name>/ 下 symlink 的健康检查

    触发条件：扫 `raw/external/<source-name>/`，检测两类问题：
    - anchor 缺失：symlink 存在但没 `.symlink-anchor.json`（用户漏配）
    - target 失效：anchor 存在但解析出的 target 路径不存在（已被删/挪）

    返回 finding 列表；该目录不存在/不存在 symlink 时返回空。
    """
    findings = []  # type: List[str]
    external_dir = wiki_root / "raw" / EXTERNAL_SUBDIR
    if not external_dir.is_dir():
        return findings
    # 一层：只看每个 <source-name>/ 顶层 entry（不递归扫描嵌套 symlink——
    # spec §13.1 规定每个 symlink 都需自己的 anchor，但嵌套场景罕见且会让
    # 报错路径膨胀；遇到再说）
    for entry in sorted(external_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        source_dir = external_dir / entry.name
        if not source_dir.is_dir():
            continue
        # 命名规范
        if not SOURCE_NAME_RE.match(entry.name):
            rel = source_dir.relative_to(wiki_root).as_posix()
            findings.append(
                f"external-source-name-invalid: {rel}/ 目录名 '{entry.name}' 不符合 "
                f"^[a-z0-9][a-z0-9-]*$（kebab-case 短名）"
            )
        # 找该目录下所有 symlink（用 lexists 区分；broken symlink 也会被 ls 列）
        try:
            children = list(source_dir.iterdir())
        except OSError:
            continue
        symlinks = [c for c in children if c.name != ANCHOR_FILENAME and c.is_symlink()]
        if not symlinks:
            continue
        for sl in symlinks:
            rel = sl.relative_to(wiki_root).as_posix()
            anchor_path = source_dir / ANCHOR_FILENAME
            if not anchor_path.is_file():
                findings.append(
                    f"external-anchor-missing: {rel} 是 symlink 但同目录缺 "
                    f"'{ANCHOR_FILENAME}'（按 spec §13 没有 anchor 视为未接入）"
                )
                continue
            anchor = _parse_anchor(anchor_path)
            if anchor is None:
                findings.append(
                    f"external-anchor-corrupt: {rel} 的 '{ANCHOR_FILENAME}' 解析失败 "
                    f"或缺 target / captured_at / kind='external-repo' 必填字段"
                )
                continue
            # target 路径必须存在（解析 anchor 的绝对路径）
            target_path = Path(anchor["target"]).expanduser()
            if not target_path.exists():
                findings.append(
                    f"external-target-dead: {rel} 的 anchor target='{anchor['target']}' "
                    f"已不存在（captured_at={anchor.get('captured_at', '?')}）；"
                    f"用户需重新锚定或删除 symlink"
                )
            # target 路径与当前 symlink 解析不一致：target 被迁移了
            else:
                try:
                    current_target = str(sl.resolve())
                except OSError:
                    current_target = ""
                if current_target and anchor["target"] != current_target:
                    findings.append(
                        f"external-target-drift: {rel} 当前 symlink 解析为 "
                        f"'{current_target}'，但 anchor 记录 '{anchor['target']}'；"
                        f"anchor 需更新"
                    )
    return findings


def check_frontmatter(wiki_root: Path) -> List[str]:
    """2. frontmatter 完整性 + 3. source/synthesis 的 sources 字段"""
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    # 合并所有非 index / log / MEMORY/MEMORY.md 页（MEMORY/MEMORY.md 是索引无 frontmatter，不走 5 字段校验）
    content_pages = []
    for sub in WIKI_SUBDIRS:
        content_pages.extend(pages[sub])
    for p in pages["memory"]:
        # 跳过 MEMORY/MEMORY.md（索引，无 frontmatter；不校验字段）
        if p.name == "MEMORY.md" and p.parent.name == MEMORY_SUBDIR:
            continue
        content_pages.append(p)
    # 跳过不存在的 index / log
    for p in content_pages:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter_simple(text)
        rel = p.relative_to(wiki_root).as_posix()
        # 必填字段
        for field in ("title", "type", "created", "updated", "tags"):
            if field not in fm:
                findings.append(f"missing-frontmatter: {rel} 缺 '{field}' 字段")
        # type 合法
        t = fm.get("type")
        if t is not None and t not in VALID_TYPES:
            findings.append(f"invalid-type: {rel} type='{t}' 非法；应为 {sorted(VALID_TYPES)} 之一")
        # source / synthesis 的 sources 必填且非空
        if t in ("source", "synthesis"):
            srcs = fm.get("sources", [])
            if not isinstance(srcs, list) or not srcs:
                findings.append(f"missing-sources: {rel} type={t} 缺 'sources' 字段或为空")
            else:
                # 对 source 页：每个 src 必须是 raw/ 下现存路径
                if t == "source":
                    for s in srcs:
                        if not isinstance(s, str):
                            continue
                        sp = (wiki_root / s).resolve()
                        try:
                            sp.relative_to(wiki_root.resolve())
                        except ValueError:
                            findings.append(f"sources-out-of-root: {rel} sources[0]='{s}'不在 wiki 根下")
                            continue
                        if not sp.is_file():
                            findings.append(f"sources-missing: {rel} sources[0]='{s}'但文件不存在")
    return findings


def resolve_link(base: Path, link: str) -> Optional[Path]:
    """把 Markdown 链接解析为绝对路径；外部 URL / 锚点返回 None"""
    link = link.strip()
    # 去掉锚点
    link = link.split("#", 1)[0]
    # 去掉 query
    link = link.split("?", 1)[0]
    if not link:
        return None
    if is_external_url(link):
        return None
    # 相对路径
    target = (base.parent / link).resolve()
    return target


def check_link_integrity(wiki_root: Path) -> List[str]:
    """4. 路径引用完整性"""
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    all_pages = []
    for sub in WIKI_SUBDIRS + ("index", "log", "memory"):
        all_pages.extend(pages[sub])
    for p in all_pages:
        if not p.is_file():
            continue
        rel = p.relative_to(wiki_root).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in MD_LINK_RE.finditer(text):
            url = m.group(2)
            target = resolve_link(p, url)
            if target is None:
                continue
            # 只检查 wiki 范围内的链接（raw/ 下的图不在范围）
            try:
                target.relative_to(wiki_root.resolve() / "wiki")
            except ValueError:
                continue
            if not target.is_file():
                findings.append(
                    f"broken-link: {rel} 引用 '{url}' 解析为 {target.relative_to(wiki_root).as_posix()}，但文件不存在"
                )
    return findings


def check_index_coverage(wiki_root: Path) -> List[str]:
    """5. index.md 覆盖"""
    findings = []  # type: List[str]
    index_path = wiki_root / "wiki" / "index.md"
    if not index_path.is_file():
        return ["index-missing: wiki/index.md 不存在"]
    index_text = index_path.read_text(encoding="utf-8", errors="replace")
    # 收集 index 引用的所有相对路径
    indexed = set()  # type: Set[str]
    for m in MD_LINK_RE.finditer(index_text):
        url = m.group(2)
        target = resolve_link(index_path, url)
        if target is None:
            continue
        try:
            rel = target.relative_to(wiki_root).as_posix()
        except ValueError:
            continue
        indexed.add(rel)
    # 找所有非 index / log 的页面
    pages = find_md_files(wiki_root)
    for sub in WIKI_SUBDIRS:
        for p in pages[sub]:
            if not p.is_file():
                continue
            rel = p.relative_to(wiki_root).as_posix()
            if rel not in indexed:
                findings.append(f"orphan-page: {rel} 未在 wiki/index.md 中列出")
    return findings


def check_log_format(wiki_root: Path) -> List[str]:
    """6. log.md 格式"""
    findings = []  # type: List[str]
    log_path = wiki_root / "wiki" / "log.md"
    if not log_path.is_file():
        return ["log-missing: wiki/log.md 不存在"]
    text = log_path.read_text(encoding="utf-8", errors="replace")
    # 跳过 frontmatter
    body_start = 0
    if text.startswith("---"):
        m = re.match(r"^---\n.*?\n---\n?", text, re.DOTALL)
        if m:
            body_start = m.end()
    body = text[body_start:]
    for i, line in enumerate(body.splitlines(), start=1):
        if not line.strip():
            continue
        if line.startswith("## "):
            if not LOG_LINE_RE.match(line):
                findings.append(
                    f"log-format: wiki/log.md 第 {i} 行格式不合规：'{line[:60]}{'...' if len(line) > 60 else ''}'"
                )
    return findings


# log.md 条目数阈值——超过则建议 rotate 到 log-YYYY.md（详见 wiki-spec §4.1）
LOG_ROTATION_THRESHOLD = 500


def check_log_rotation(wiki_root: Path) -> List[str]:
    """10. log.md 条目数阈值——超过 LOG_ROTATION_THRESHOLD 建议 rotate

    仅检查 wiki/log.md 当前文件；归档文件 log-YYYY.md 不计入（它们是只读归档，
    不需要再次 rotate）。判定依据：按 LOG_LINE_RE 正则匹配行数。

    不自动 rotate——lint 只报告；rotate 由 agent 或用户按 wiki-spec §4.1 流程手动执行。
    log-missing 已被 check_log_format 报告，这里跳过重复报错。
    """
    findings = []  # type: List[str]
    log_path = wiki_root / "wiki" / "log.md"
    if not log_path.is_file():
        return findings
    text = log_path.read_text(encoding="utf-8", errors="replace")
    body_start = 0
    if text.startswith("---"):
        m = re.match(r"^---\n.*?\n---\n?", text, re.DOTALL)
        if m:
            body_start = m.end()
    body = text[body_start:]
    entry_count = sum(1 for line in body.splitlines() if LOG_LINE_RE.match(line))
    if entry_count > LOG_ROTATION_THRESHOLD:
        findings.append(
            f"log-rotation-recommended: wiki/log.md 含 {entry_count} 条目，超过 {LOG_ROTATION_THRESHOLD} 阈值；"
            f"按 wiki-spec §4.1 rotate 到 log-YYYY.md（当前 log.md 仍正常追加，rotate 是建议而非必须）"
        )
    return findings


def check_stale_summaries(wiki_root: Path, threshold_days: int = 90) -> List[str]:
    """7. 过期摘要"""
    findings = []  # type: List[str]
    sources_dir = wiki_root / "wiki" / "sources"
    if not sources_dir.is_dir():
        return findings
    today = date.today()
    for p in sources_dir.glob("*.md"):
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter_simple(text)
        updated = fm.get("updated")
        if not isinstance(updated, str):
            continue
        try:
            upd_date = date.fromisoformat(updated)
        except ValueError:
            continue
        age = (today - upd_date).days
        if age > threshold_days:
            rel = p.relative_to(wiki_root).as_posix()
            findings.append(
                f"stale-summary: {rel} type=source updated={updated} ({age} 天前，超过 {threshold_days} 天阈值)"
            )
    return findings


# Tag Taxonomy 段在 CLAUDE.md 内的解析常量
TAG_TAXONOMY_HEADER_RE = re.compile(r"^###\s+Tag Taxonomy")
TAXONOMY_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
TAG_KV_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_tag_taxonomy(claude_md_path: Path) -> Set[str]:
    """从 CLAUDE.md 的 Tag Taxonomy 段提取允许的 tag 集合

    解析规则：
    - 找到 `### Tag Taxonomy` 段（到下一个 ### / ## / # 标题结束）
    - 每行形如 `- category：tag1 / tag2 / tag3`（中文 / 英文分隔符都支持）
      或 `- tag`（无分类）
    - 多个 tag 用 `/` `，` `,` 任一字符分隔
    - 跳过 code block fence、HTML comment、空行
    - 只保留 kebab-case（`^[a-z0-9][a-z0-9-]*$`）的 tag
    - 找不到文件 / 段 / 解析出 0 个 tag → 返回空集合（调用方应静默跳过）
    """
    tags = set()  # type: Set[str]
    if not claude_md_path.is_file():
        return tags
    text = claude_md_path.read_text(encoding="utf-8", errors="replace")
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        # 段进入
        if TAG_TAXONOMY_HEADER_RE.match(stripped):
            in_section = True
            continue
        # 段退出（遇到其它标题——但同一标题再次出现仍算段内）
        if in_section and re.match(r"^#{1,4}\s", stripped) and not TAG_TAXONOMY_HEADER_RE.match(stripped):
            break
        if not in_section:
            continue
        # 跳过空行 / 注释 / code block
        if not stripped or stripped.startswith("<!--") or stripped.startswith("```"):
            continue
        # 提取 bullet 内容
        m = TAXONOMY_BULLET_RE.match(stripped)
        if not m:
            continue
        content = m.group(1).strip()
        # 分类形式："category：tag1 / tag2"——第一个 ： 或 : 是分隔符
        sep_match = re.match(r"^([^：:]+)[：:]\s*(.+)$", content)
        if sep_match:
            tag_part = sep_match.group(2)
        else:
            tag_part = content
        # 多 tag 分隔
        for t in re.split(r"[/，,]", tag_part):
            t = t.strip().strip("`").strip("*").strip()
            if t and TAG_KV_RE.match(t):
                tags.add(t)
    return tags


def check_tag_taxonomy(wiki_root: Path) -> List[str]:
    """11. tag 是否在 CLAUDE.md 的 Tag Taxonomy 白名单内

    找不到 CLAUDE.md / Tag Taxonomy 段为空 / 解析出 0 个 tag → 静默跳过
    （避免新 setup 的 wiki 必报错）。启用 taxonomy 后，对每个内容页（5 类 +
    MEMORY 非 MEMORY.md）的 frontmatter.tags 元素做包含校验；不在白名单 → info 级。
    """
    findings = []  # type: List[str]
    allowed = parse_tag_taxonomy(wiki_root / "CLAUDE.md")
    if not allowed:
        return findings
    pages = find_md_files(wiki_root)
    target_pages = []  # type: List[Path]
    for sub in WIKI_SUBDIRS:
        target_pages.extend(pages[sub])
    for p in pages["memory"]:
        # MEMORY/MEMORY.md 是索引无 frontmatter，不校验
        if p.name == "MEMORY.md" and p.parent.name == MEMORY_SUBDIR:
            continue
        target_pages.append(p)
    for p in target_pages:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter_simple(text)
        tags = fm.get("tags", [])
        if not isinstance(tags, list):
            continue
        rel = p.relative_to(wiki_root).as_posix()
        for t in tags:
            if not isinstance(t, str):
                continue
            t = t.strip().strip("\"'")
            if not t:
                continue
            if t not in allowed:
                findings.append(f"tag-not-in-taxonomy: {rel} tags 含 '{t}' 不在 CLAUDE.md 的 Tag Taxonomy 白名单")
    return findings


def check_filename_kebab(wiki_root: Path) -> List[str]:
    """8. 文件名 kebab-case 规范"""
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    for sub in WIKI_SUBDIRS + ("index", "log"):
        for p in pages[sub]:
            stem = p.stem
            if not re.match(r"^[a-z0-9][a-z0-9-]*$", stem):
                rel = p.relative_to(wiki_root).as_posix()
                findings.append(
                    f"filename-not-kebab: {rel} 文件名 '{p.name}' 应使用 kebab-case（小写字母 + 数字 + 短横线）"
                )
    # MEMORY/* 走同一规则，但排除 MEMORY.md（索引，大写不报错）
    for p in pages["memory"]:
        if p.name == "MEMORY.md" and p.parent.name == MEMORY_SUBDIR:
            continue
        stem = p.stem
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", stem):
            rel = p.relative_to(wiki_root).as_posix()
            findings.append(
                f"filename-not-kebab: {rel} 文件名 '{p.name}' 应使用 kebab-case（小写字母 + 数字 + 短横线）"
            )
    return findings


def check_duplicate_titles(wiki_root: Path) -> List[str]:
    """9. 重复标题"""
    findings = []  # type: List[str]
    title_to_files = {}  # type: Dict[str, List[str]]
    pages = find_md_files(wiki_root)
    for sub in WIKI_SUBDIRS:
        for p in pages[sub]:
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter_simple(text)
            title = fm.get("title")
            if not isinstance(title, str):
                continue
            rel = p.relative_to(wiki_root).as_posix()
            title_to_files.setdefault(title, []).append(rel)
    for title, files in title_to_files.items():
        if len(files) > 1:
            findings.append(f"duplicate-title: '{title}' 出现在 {len(files)} 个页面：{', '.join(files)}")
    return findings


# 页面正文行数阈值——超过则建议拆分。
# SSOT：其他文件 prose 提到「单页正文阈值」时，统一引用此常量，避免散弹式散落。
PAGE_SIZE_THRESHOLD = 300

# 认知质量信号字段取值
CONFIDENCE_VALUES = {"high", "medium", "low"}


def _strip_frontmatter_body(text):
    """返回去掉 frontmatter 后的正文（frontmatter 不计入页面体量）"""
    body_start = 0
    if text.startswith("---"):
        m = re.match(r"^---\n.*?\n---\n?", text, re.DOTALL)
        if m:
            body_start = m.end()
    return text[body_start:]


def check_page_size(wiki_root, threshold=PAGE_SIZE_THRESHOLD):
    """12. 页面体量——正文非空行数 > threshold 的内容页建议拆分

    仅检查 5 类内容页（entities/concepts/sources/comparisons/syntheses）——MEMORY/*
    按 wiki-spec §5.2「正文无长度上限」豁免。计非空行（纯空行不计），避免空行撑大计数。
    阈值见模块顶部 PAGE_SIZE_THRESHOLD（SSOT）。
    """
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    for sub in WIKI_SUBDIRS:
        for p in pages[sub]:
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            body = _strip_frontmatter_body(text)
            n = sum(1 for ln in body.splitlines() if ln.strip())
            if n > threshold:
                rel = p.relative_to(wiki_root).as_posix()
                findings.append(
                    f"oversized-page: {rel} 正文 {n} 行（非空），超过 {threshold} 阈值——"
                    f"建议拆成子主题页 + cross-link（CLAUDE.md「Page Thresholds」）"
                )
    return findings


def check_quality_signals(wiki_root):
    """13. 认知质量信号——把 confidence/contested/contradictions 显性化（防"弱主张固化成事实"）

    deterministic 子检查（字段全部可选；省略 = 不评，lint 不报）：
    - contested-page（warn）：contested: true 的页——含未解决矛盾，需用户裁定后移除标记
    - low-confidence（info）：confidence: low 的页——弱支撑主张
    - invalid-confidence（warn）：confidence 取值不在 {high, medium, low}
    - contradiction-target-missing（warn）：contradictions 指向不存在的页
    - contradiction-asymmetric（warn）：A 把 B 列入 contradictions 但 B 未反向标注 A
      （字段语义要求双向标注，见 page-templates.md §一）

    这与"lint 抓腐烂而非评判内容"立场一致——只把作者主动标注的弱信号拎出来，不替作者
    决定"该不该标"。判定"某主张是否弱支撑"是半定性工作，见 lint-checklist.md §三。
    """
    findings = []  # type: List[str]
    pages = find_md_files(wiki_root)
    target_pages = []  # type: List[Path]
    for sub in WIKI_SUBDIRS:
        target_pages.extend(pages[sub])
    for p in pages["memory"]:
        if p.name == "MEMORY.md" and p.parent.name == MEMORY_SUBDIR:
            continue
        target_pages.append(p)

    # contradictions 对端映射：page_rel -> set(已解析且存在的 target wiki 相对路径)
    contra_out = {}  # type: Dict[str, Set[str]]
    for p in target_pages:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter_simple(text)
        rel = p.relative_to(wiki_root).as_posix()
        # contested
        if str(fm.get("contested", "")).strip().strip("\"'").lower() == "true":
            findings.append(f"contested-page: {rel} contested=true — 含未解决矛盾主张，需裁定后移除该标记")
        # confidence
        conf = fm.get("confidence")
        if conf is not None:
            conf_s = str(conf).strip().strip("\"'").lower()
            if conf_s == "low":
                findings.append(f"low-confidence: {rel} confidence=low — 弱支撑主张，引用需谨慎或找印证")
            elif conf_s not in CONFIDENCE_VALUES:
                findings.append(f"invalid-confidence: {rel} confidence='{conf}' 非法；应为 high/medium/low 之一")
        # contradictions（收集对端 + 即时检查 target 存在性）
        contras = fm.get("contradictions", [])
        if isinstance(contras, list) and contras:
            resolved = set()  # type: Set[str]
            for c in contras:
                if not isinstance(c, str):
                    continue
                target = resolve_link(p, c)
                if target is None:
                    continue
                try:
                    target_rel = target.relative_to(wiki_root.resolve()).as_posix()
                except ValueError:
                    continue
                if target.is_file():
                    resolved.add(target_rel)
                else:
                    findings.append(
                        f"contradiction-target-missing: {rel} contradictions 含 '{c}'，但该页不存在（{target_rel}）"
                    )
            if resolved:
                contra_out[rel] = resolved
    # 对称性：A 标 B → B 应标 A
    for src, targets in contra_out.items():
        for tgt in targets:
            back = contra_out.get(tgt)
            if back is None or src not in back:
                findings.append(
                    f"contradiction-asymmetric: {src} 把 {tgt} 标为矛盾对端，"
                    f"但 {tgt} 的 contradictions 未反向标注 {src}（要求双向标注）"
                )
    return findings


def check_memory_index(wiki_root: Path) -> List[str]:
    """14. MEMORY.md 索引一致性——MEMORY/*.md（非 MEMORY.md）必须在 MEMORY.md 索引中列出

    MEMORY.md 是被 CLAUDE.md @import 的轻量索引（无 frontmatter），不走 wiki/index.md
    强制入口；但每条经验条目仍需在 MEMORY.md 列一行，否则下次会话读不到（MEMORY 沦为死库）。
    本检查把"有文件但没进索引"的拎出来。反向（索引列了但文件不存在）已被 check_link_integrity
    的 broken-link 覆盖（MEMORY.md 在 memory 桶，其 markdown 链接被扫）。

    MEMORY.md 不存在时静默跳过（老 wiki 迁移期 / spec <0.6.0，不报错）。
    severity = info（轻量索引非强制入口，类比 tag-not-in-taxonomy）。
    """
    findings = []  # type: List[str]
    mem_dir = wiki_root / "wiki" / MEMORY_SUBDIR
    memory_index = mem_dir / "MEMORY.md"
    if not memory_index.is_file():
        return findings
    # 解析 MEMORY.md 正文里的 markdown 链接 → 已索引的文件名集合
    indexed = set()  # type: Set[str]
    text = memory_index.read_text(encoding="utf-8", errors="replace")
    mem_dir_resolved = mem_dir.resolve()
    for m in MD_LINK_RE.finditer(text):
        target = resolve_link(memory_index, m.group(2))
        if target is None:
            continue
        # 只关心 MEMORY/ 范围内的链接
        try:
            target.relative_to(mem_dir_resolved)
        except ValueError:
            continue
        if target.is_file():
            indexed.add(target.name)
    # 扫 MEMORY/*.md（排除 MEMORY.md 本身）；任一不在 indexed → memory-not-indexed
    if not mem_dir.is_dir():
        return findings
    for p in sorted(mem_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        if p.name not in indexed:
            rel = p.relative_to(wiki_root).as_posix()
            findings.append(
                f"memory-not-indexed: {rel} 未在 wiki/MEMORY/MEMORY.md 索引中列出；"
                f"该条目下次会话读不到（追加一行：- <slug> — <一句话> → [正文](<slug>.md)）"
            )
    return findings


def severity_of(finding: str) -> str:
    """从 finding 的类别前缀推断严重性"""
    if finding.startswith(
        (
            "raw-modified",
            "missing-frontmatter",
            "invalid-type",
            "sources-missing",
            "sources-out-of-root",
            "broken-link",
            "orphan-page",
            "index-missing",
            "log-missing",
            "external-anchor-missing",
            "external-target-dead",
            "external-source-name-invalid",
        )
    ):
        return "error"
    if finding.startswith(("external-anchor-corrupt", "external-target-drift")):
        return "warn"
    if finding.startswith(
        ("stale-summary", "log-format", "filename-not-kebab", "duplicate-title", "log-rotation-recommended")
    ):
        return "warn"
    if finding.startswith(
        (
            "contested-page",
            "invalid-confidence",
            "contradiction-target-missing",
            "contradiction-asymmetric",
            "oversized-page",
        )
    ):
        return "warn"
    if finding.startswith(("tag-not-in-taxonomy", "low-confidence", "memory-not-indexed")):
        return "info"
    return "info"


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic health check for a local LLM wiki.")
    parser.add_argument("wiki_root", nargs="?", help="wiki 根目录；默认从 $LLM_WIKI_ROOT 读")
    parser.add_argument(
        "--severity", choices=["error", "warn", "info", "all"], default="all", help="过滤输出严重性（默认 all）"
    )
    parser.add_argument("--no-git", action="store_true", help="跳过 raw/ 的 git status 检查")
    args = parser.parse_args()

    # `--no-git` 与"自动检测"叠加：传了 `--no-git` 就完全不检测；不传时
    # 脚本自动按 `.git/` 存在与否决定跑 / 跳。两种路径都允许，不强制用户
    # 必须装 git 或必须 init 仓——保留"裸目录树 wiki 默认支持"立场。
    effective_use_git = not args.no_git

    if args.wiki_root:
        wiki_root = Path(args.wiki_root).expanduser().resolve()
    elif os.environ.get("LLM_WIKI_ROOT"):
        wiki_root = Path(os.environ["LLM_WIKI_ROOT"]).expanduser().resolve()
    else:
        print("ERROR: 需提供 wiki_root 参数或设置 $LLM_WIKI_ROOT", file=sys.stderr)
        return 2

    if not (wiki_root / "wiki").is_dir():
        print(f"ERROR: {wiki_root}/wiki 不存在（wiki 还没 setup？）", file=sys.stderr)
        return 2

    # 跑所有检查
    all_findings = []  # type: List[str]
    info_notes = []  # type: List[str]  # 不计入 severity 过滤的"说明性输出"（如 raw-immutable 跳过原因）
    raw_findings, raw_skip = check_raw_immutable(wiki_root, effective_use_git)
    all_findings.extend(raw_findings)
    if raw_skip:
        info_notes.append(raw_skip)
    all_findings.extend(check_frontmatter(wiki_root))
    all_findings.extend(check_link_integrity(wiki_root))
    all_findings.extend(check_index_coverage(wiki_root))
    all_findings.extend(check_log_format(wiki_root))
    all_findings.extend(check_log_rotation(wiki_root))
    all_findings.extend(check_stale_summaries(wiki_root))
    all_findings.extend(check_filename_kebab(wiki_root))
    all_findings.extend(check_duplicate_titles(wiki_root))
    all_findings.extend(check_tag_taxonomy(wiki_root))
    all_findings.extend(check_external_symlinks(wiki_root))
    all_findings.extend(check_page_size(wiki_root))
    all_findings.extend(check_quality_signals(wiki_root))
    all_findings.extend(check_memory_index(wiki_root))

    # 过滤
    if args.severity != "all":
        threshold = SEV_RANK[args.severity]
        all_findings = [f for f in all_findings if SEV_RANK[severity_of(f)] <= threshold]

    # 输出：跳过提示（INFO 级别但不受 --severity 过滤；让用户始终能看到）
    if info_notes:
        print("\n[NOTES]")
        for n in info_notes:
            print(f"  {n}")

    # 输出
    if not all_findings:
        print("No issues found. ✓")
        return 0

    # 按严重性分组
    by_sev = {"error": [], "warn": [], "info": []}  # type: Dict[str, List[str]]
    for f in all_findings:
        by_sev[severity_of(f)].append(f)

    for sev in ("error", "warn", "info"):
        if by_sev[sev]:
            print(f"\n[{sev.upper()}] ({len(by_sev[sev])})")
            for f in by_sev[sev]:
                print(f"  {f}")

    print()
    print(f"Total: {len(all_findings)} finding(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())

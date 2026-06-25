#!/usr/bin/env python3
"""
setup_wiki.py — 一次性脚手架脚本

用法：
  python3 setup_wiki.py <TOPIC_NAME> [<WIKI_ROOT>]

- <TOPIC_NAME>：人类可读的主题名（写入 CLAUDE.md / index / log）
- <WIKI_ROOT>：可选，默认从 LLM_WIKI_ROOT 环境变量读，再回退到 ~/wiki/<slug>

行为：
1. 拒绝在已存在 CLAUDE.md 或 wiki/index.md 的目录里运行（防误覆盖）
2. 创建 raw/{articles,assets}/ 与 wiki/{entities,concepts,sources,comparisons,syntheses}/
3. 拷 llm-wiki-management/references/claude-md-template.md 到 <WIKI_ROOT>/CLAUDE.md
   并替换 {{TOPIC_NAME}} / {{SETUP_DATE}}
4. 写 wiki/index.md 与 wiki/log.md（含 frontmatter）
5. 写 .gitignore（不忽略 wiki/ / raw/ / CLAUDE.md）
6. 若非 git 仓，git init + 首次 commit
7. 打印后续指引
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

# 模板路径（相对脚本自身的 skill 目录）
SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_ROOT / "references" / "claude-md-template.md"


def slugify(name: str) -> str:
    """把主题名转成目录名用的 kebab-case slug"""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "wiki"


def render_index_md(topic: str, today: str) -> str:
    """生成 wiki/index.md 的初始内容"""
    return (
        "---\n"
        f'title: "{topic} Index"\n'
        "type: index\n"
        'okf_version: "0.1"\n'
        "tags: [index]\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        "---\n\n"
        f"# {topic} Wiki\n\n"
        "> 本 wiki 由 LLM 维护，用户只读 + 提供 raw 资料 + 提问题。\n"
        "> Schema 见 [`../CLAUDE.md`](../CLAUDE.md)。\n\n"
        "## Entities\n\n"
        "_（暂无内容）_\n\n"
        "## Concepts\n\n"
        "_（暂无内容）_\n\n"
        "## Sources\n\n"
        "_（暂无内容）_\n\n"
        "## Comparisons\n\n"
        "_（暂无内容）_\n\n"
        "## Syntheses\n\n"
        "_（暂无内容）_\n\n"
    )


def render_log_md(topic: str, today: str) -> str:
    """生成 wiki/log.md 的初始内容（带一条 setup 条目）"""
    return (
        "---\n"
        f'title: "{topic} Log"\n'
        "type: log\n"
        "tags: [log]\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        "---\n\n"
        f"## [{today}] setup | Initial scaffold by llm-wiki-management\n"
    )


def render_gitignore() -> str:
    """生成 .gitignore 内容"""
    return (
        "# OS / 编辑器\n"
        ".DS_Store\n"
        ".idea/\n"
        ".vscode/\n"
        "*.swp\n"
        "*.swo\n"
        "\n"
        "# Obsidian 配置（保留 vault 内容）\n"
        ".obsidian/workspace*\n"
        ".obsidian/cache\n"
        "\n"
        "# 临时文件\n"
        "*.tmp\n"
        "*.bak\n"
    )


def check_safe_target(wiki_root: Path) -> Optional[str]:
    """若目标目录已有 CLAUDE.md 或 wiki/index.md，返回拒绝原因；否则返回 None"""
    if (wiki_root / "CLAUDE.md").exists():
        return f"{wiki_root}/CLAUDE.md 已存在；拒绝覆盖。如需重新 setup，请先备份并删除。"
    if (wiki_root / "wiki" / "index.md").exists():
        return f"{wiki_root}/wiki/index.md 已存在；拒绝覆盖。"
    return None


def ensure_git(wiki_root: Path) -> bool:
    """若 wiki_root 不是 git 仓，git init + add + commit。返回是否新建了仓"""
    is_repo = (wiki_root / ".git").is_dir()
    if is_repo:
        return False

    # 初始化
    subprocess.run(
        ["git", "init"],
        cwd=str(wiki_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    # 默认分支 main
    subprocess.run(
        ["git", "symbolic-ref", "HEAD", "refs/heads/main"],
        cwd=str(wiki_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    # 配置 local user（仅首次 commit 需要；若无全局配置）
    try:
        subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(wiki_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "config", "user.email", "wiki@local"],
            cwd=str(wiki_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    try:
        subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(wiki_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "config", "user.name", "LLM Wiki"],
            cwd=str(wiki_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    subprocess.run(
        ["git", "add", "."],
        cwd=str(wiki_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial wiki scaffold"],
        cwd=str(wiki_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup a new LLM Wiki from scratch (one-time scaffold).")
    parser.add_argument("topic", help="主题名（人类可读，将写入 CLAUDE.md）")
    parser.add_argument(
        "wiki_root", nargs="?", help="wiki 根目录路径；默认从 $LLM_WIKI_ROOT 读，再回退到 ~/wiki/<slug>"
    )
    args = parser.parse_args()

    topic = args.topic.strip()
    if not topic:
        print("ERROR: 主题名不能为空", file=sys.stderr)
        return 2

    # 决定 wiki_root
    if args.wiki_root:
        wiki_root = Path(args.wiki_root).expanduser().resolve()
    elif os.environ.get("LLM_WIKI_ROOT"):
        wiki_root = Path(os.environ["LLM_WIKI_ROOT"]).expanduser().resolve()
    else:
        slug = slugify(topic)
        wiki_root = (Path.home() / "wiki" / slug).resolve()
        print(f"未指定 wiki_root，默认: {wiki_root}")
        print("（可通过 LLM_WIKI_ROOT 环境变量或第二个参数覆盖）")

    # 模板必须存在
    if not TEMPLATE_PATH.is_file():
        print(f"ERROR: 找不到模板 {TEMPLATE_PATH}", file=sys.stderr)
        return 2

    # 安全检查
    reject = check_safe_target(wiki_root)
    if reject:
        print(f"ERROR: {reject}", file=sys.stderr)
        return 1

    # 创建目录
    today = date.today().isoformat()
    print(f"[setup] wiki 根：{wiki_root}")
    print(f"[setup] 主题：{topic}")
    print(f"[setup] 日期：{today}")

    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "raw" / "articles").mkdir(parents=True, exist_ok=True)
    (wiki_root / "raw" / "assets").mkdir(parents=True, exist_ok=True)
    for sub in ("entities", "concepts", "sources", "comparisons", "syntheses"):
        (wiki_root / "wiki" / sub).mkdir(parents=True, exist_ok=True)

    # 写 CLAUDE.md（从模板替换）
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template.replace("{{TOPIC_NAME}}", topic).replace("{{SETUP_DATE}}", today)
    (wiki_root / "CLAUDE.md").write_text(rendered, encoding="utf-8")
    print(f"[setup] 写 {wiki_root}/CLAUDE.md")

    # 写 index.md / log.md
    (wiki_root / "wiki" / "index.md").write_text(render_index_md(topic, today), encoding="utf-8")
    print(f"[setup] 写 {wiki_root}/wiki/index.md")

    (wiki_root / "wiki" / "log.md").write_text(render_log_md(topic, today), encoding="utf-8")
    print(f"[setup] 写 {wiki_root}/wiki/log.md")

    # 写 .gitignore
    (wiki_root / ".gitignore").write_text(render_gitignore(), encoding="utf-8")
    print(f"[setup] 写 {wiki_root}/.gitignore")

    # git init + 首次 commit
    try:
        created = ensure_git(wiki_root)
        if created:
            print("[setup] git init + 首次 commit 完成")
        else:
            print("[setup] 检测到已存在 git 仓，未做 init；请手动 add + commit")
    except subprocess.CalledProcessError as e:
        print(f"WARN: git 操作失败：{e}", file=sys.stderr)
        print("      wiki 内容已落盘，请手动初始化 git", file=sys.stderr)

    # 后续指引
    print()
    print("=" * 60)
    print("Setup 完成！接下来：")
    print(f"  1. 把原始资料放到 {wiki_root}/raw/articles/")
    print("  2. 让 LLM 通过 ingest 操作把资料摄取到 wiki")
    print("  3. 定期跑 lint：")
    print(f"     LLM_WIKI_ROOT={wiki_root} \\")
    print(f"       python3 {SKILL_ROOT}/scripts/lint_wiki.py")
    print()
    print("Schema 读取：本 skill 每次操作会按需读取本仓 CLAUDE.md，无需手动配置。")
    print("（可选）在 wiki 根目录内工作时，Claude Code 会自动加载根目录 CLAUDE.md；")
    print("     在别处工作时由 skill 经 $LLM_WIKI_ROOT 按需读取，不必 symlink。")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

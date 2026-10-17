"""骨架机械层：new 生成骨架 / check 比对漂移。

脚本零定义：形状事实（frontmatter 键、节名、顺序）一律从 assets/skill-template.md 解析；
每节/每目录"装什么"的定义活在 SKILL.md 正文，本文件不携带。

用法：
    python3 tools/skeleton.py new <skill-name> [--root DIR]
    python3 tools/skeleton.py check [skill-dir ...] [--root DIR]   # 不给目录则扫 root 下全部含 SKILL.md 的子目录

check 检查项：frontmatter 键与 H2 序列和模板精确相等；目录名 == name 值；引用名存活——
正文"见/按/对照 + 引号或反引号"引用的名称必须能解析到本文件的节、小节或粗体清单项名（真实文件路径按存在性放行；
反引号内 `-` 开头的 CLI 旗标与含空格的命令片段不算名称引用）；
锚点链接——正文 [文字](#锚点) 的文字固定"章节"、锚点须解析到本文件节 / 小节（内联代码与围栏内的示例不查）。

house 加严备查：frontmatter"精确相等"严于开放规范（规范另有可选字段），放宽路径 = 必需键精确 + 可选键白名单；
跨文件链接 / `<a id>` 显式锚 / 反引号路径存活未实现——无场景无实证，立项先给事故。

Run: python3 tools/skeleton.py --help
Exit: 0 = 绿；1 = 有 finding；2 = 用法/环境错误。
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = SKILL_DIR.parent
TEMPLATE = SKILL_DIR / "assets" / "skill-template.md"

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAME_MAX_LEN = 64  # Agent Skills 开放规范上限
NAME_SLOT_RE = re.compile(r"^name:\s*<skill-name>\s*$")
FM_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")
H2_RE = re.compile(r"^##\s+(.*?)\s*$")
H3_RE = re.compile(r"^###\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
BOLD_ITEM_RE = re.compile(r"^-\s*\*\*(.+?)\*\*")
REF_RE = re.compile(r"(?:见|按照|按|对照)[ \t]*([“\"])([^”\"]{1,40})[”\"]")
REF_TICK_RE = re.compile(r"(?:见|按照|按)[ \t]*`([^`]{1,40})`")
REF_NOISE_RE = re.compile(r"[；，。、：！？;:]")
LINK_RE = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
ANCHOR_LINK_LABEL = "章节"


def is_ref_name(ref: str) -> bool:
    """触发词后引号内不像是引用名的：单字（标点捕获）或含顿逗等中文标点（散文边界）。"""
    return len(ref) >= 2 and not REF_NOISE_RE.search(ref)


def slugify_heading(text: str) -> str:
    """按 GitHub 规则生成标题锚点（ASCII 小写、去标点、空白转连字符）。"""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s", "-", text).strip("-")


def split_frontmatter(lines: List[str]) -> Tuple[List[str], List[str]]:
    """返回 (frontmatter 行, 正文行)；无 frontmatter 返回 ([], lines)，未闭合抛 ValueError。"""
    if not lines or lines[0].strip() != "---":
        return [], lines
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx], lines[idx + 1 :]
    raise ValueError("frontmatter 未闭合")


def parse_fm_keys(fm_lines: Sequence[str]) -> Tuple[List[str], Dict[str, str]]:
    """顶层键（零缩进）按序返回 (键名列表, name 等单行值)。"""
    keys: List[str] = []
    values: Dict[str, str] = {}
    for line in fm_lines:
        m = FM_KEY_RE.match(line)
        if m:
            keys.append(m.group(1))
            values[m.group(1)] = m.group(2).strip()
    return keys, values


def strip_fenced(body_lines: Sequence[str]) -> List[str]:
    """剔除围栏代码块内的行（含围栏行本身）。"""
    out: List[str] = []
    fence: Optional[str] = None
    for line in body_lines:
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            fence = None if fence == marker else fence or marker
            continue
        if not fence:
            out.append(line)
    return out


def _heading_name(line: str) -> Tuple[bool, str]:
    m = H2_RE.match(line) or H3_RE.match(line)
    if not m:
        return False, ""
    return True, re.sub(r"<!--.*?-->", "", m.group(1)).strip()


def parse_headings(body_lines: Sequence[str]) -> Tuple[List[str], List[str]]:
    """返回 (H2 节名序列, H3 小节名序列)。"""
    h2: List[str] = []
    h3: List[str] = []
    for line in strip_fenced(body_lines):
        ok, name = _heading_name(line)
        if ok and line.startswith("## "):
            h2.append(name)
        elif ok:
            h3.append(name)
    return h2, h3


def parse_md(md: Path) -> Tuple[List[str], Dict[str, str], List[str]]:
    lines = md.read_text(encoding="utf-8").splitlines()
    fm_lines, body_lines = split_frontmatter(lines)
    keys, values = parse_fm_keys(fm_lines)
    heads, _ = parse_headings(body_lines)
    return keys, values, heads


def defined_names(md: Path) -> set:
    """本文件的可解析引用目标：节 / 小节 / 粗体清单项名。"""
    lines = md.read_text(encoding="utf-8").splitlines()
    _, body_lines = split_frontmatter(lines)
    h2, h3 = parse_headings(body_lines)
    names = set(h2) | set(h3)
    for line in strip_fenced(body_lines):
        m = BOLD_ITEM_RE.match(line)
        if m:
            names.add(m.group(1))
    return names


def check_ref_liveness(md: Path) -> List[str]:
    """见/按/对照 + 引号|反引号 引用的名称必须存在于 defined_names 或指向 skill 根下的真实文件，否则悬空。"""
    try:
        lines = md.read_text(encoding="utf-8").splitlines()
        _, body_lines = split_frontmatter(lines)
        names = defined_names(md)
    except (ValueError, OSError, UnicodeDecodeError):
        return []
    skill_root = md.parent
    body = "\n".join(body_lines)
    missing = set()
    for m in REF_RE.finditer(body):
        ref = m.group(2)
        if is_ref_name(ref) and ref not in names and not (skill_root / ref).is_file():
            missing.add(ref)
    for m in REF_TICK_RE.finditer(body):
        ref = m.group(1)
        # 反引号里 - 开头是 CLI 旗标、含空格是命令行片段，都不是名称引用
        if ref.startswith("-") or " " in ref:
            continue
        if is_ref_name(ref) and ref not in names and not (skill_root / ref).is_file():
            missing.add(ref)
    return [
        f"引用名 {name!r} 无存活定义（节 / 小节 / 粗体条目中均无此名，亦非 skill 根下真实文件）"
        for name in sorted(missing)
    ]


def check_anchor_links(md: Path) -> List[str]:
    """正文 [文字](#锚点) 链接：文字固定"章节"、锚点须解析到本文件 H2/H3（GitHub slug）；内联代码与围栏内不查。"""
    try:
        lines = md.read_text(encoding="utf-8").splitlines()
        _, body_lines = split_frontmatter(lines)
    except (ValueError, OSError, UnicodeDecodeError):
        return []
    h2, h3 = parse_headings(body_lines)
    slugs = {slugify_heading(x) for x in h2 + h3}
    text = INLINE_CODE_RE.sub("", "\n".join(strip_fenced(body_lines)))
    bad: List[str] = []
    seen = set()
    for m in LINK_RE.finditer(text):
        label, anchor = m.group(1), m.group(2)
        if anchor not in slugs:
            key = ("dead", anchor)
            if key not in seen:
                seen.add(key)
                bad.append(f"死锚点 #{anchor}（本文件节 / 小节的 slug 均不含它）")
        elif label != ANCHOR_LINK_LABEL:
            key = ("label", label, anchor)
            if key not in seen:
                seen.add(key)
                bad.append(f'锚点链接文字须为"{ANCHOR_LINK_LABEL}"，实为"{label}"（目标 #{anchor}）')
    return bad


def discover_skill_dirs(root: Path) -> List[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and (p / "SKILL.md").is_file())


def check_one(skill_dir: Path, want_keys: List[str], want_heads: List[str]) -> List[str]:
    """单个 skill 与模板形状比对 + 引用名 / 锚点存活，返回 finding 列表。"""
    md = skill_dir / "SKILL.md"
    try:
        keys, values, heads = parse_md(md)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        return [f"SKILL.md 解析失败：{exc}"]
    findings: List[str] = []
    if keys != want_keys:
        findings.append(f"frontmatter 键 {keys} ≠ 模板 {want_keys}")
    if heads != want_heads:
        findings.append(f"H2 序列 {heads} ≠ 模板 {want_heads}")
    if values.get("name") != skill_dir.name:
        findings.append(f"目录名 {skill_dir.name!r} ≠ frontmatter name {values.get('name')!r}")
    findings += check_ref_liveness(md)
    findings += check_anchor_links(md)
    return findings


def cmd_check(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="skeleton.py check", description="比对 skill 与模板形状 + 引用名 / 锚点存活")
    parser.add_argument("dirs", nargs="*", type=Path, help="显式 skill 目录；不给则扫 --root")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="扫描根（默认仓库根）")
    args = parser.parse_args(argv)
    if not TEMPLATE.is_file():
        print(f"模板不存在：{TEMPLATE}", file=sys.stderr)
        return 2
    want_keys, _, want_heads = parse_md(TEMPLATE)
    targets = [d.resolve() for d in args.dirs] or discover_skill_dirs(args.root)
    print(f"模板形状：frontmatter={want_keys} 节={want_heads}")
    total = 0
    for skill_dir in targets:
        for finding in check_one(skill_dir, want_keys, want_heads):
            print(f"FAIL {skill_dir}：{finding}")
            total += 1
    print(f"{len(targets)} 个 skill，{total} 处 finding — {'PASS' if total == 0 else 'FAIL'}")
    return 0 if total == 0 else 1


def cmd_new(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="skeleton.py new", description="从模板生成新 skill 骨架")
    parser.add_argument(
        "name", help="kebab-case skill 名（小写字母/数字、连字符分词、≤64 字符，=目录名=frontmatter name）"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="创建位置（默认仓库根）")
    args = parser.parse_args(argv)
    if len(args.name) > NAME_MAX_LEN:
        print(f"非法名 {args.name!r}：超过 {NAME_MAX_LEN} 字符（开放规范上限）", file=sys.stderr)
        return 2
    if not KEBAB_RE.match(args.name):
        print(f"非法名 {args.name!r}：须 kebab-case（小写字母/数字用连字符连接，如 my-skill）", file=sys.stderr)
        return 2
    if not TEMPLATE.is_file():
        print(f"模板不存在：{TEMPLATE}", file=sys.stderr)
        return 2
    target = args.root / args.name
    if target.exists():
        print(f"目录已存在：{target}", file=sys.stderr)
        return 2
    lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    if not any(NAME_SLOT_RE.match(line) for line in lines):
        print("模板缺 name 槽位 `name: <skill-name>`，先同步本脚本", file=sys.stderr)
        return 2
    target.mkdir(parents=True)
    body = [f"name: {args.name}" if NAME_SLOT_RE.match(line) else line for line in lines]
    (target / "SKILL.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    print(target / "SKILL.md")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    handlers = {"new": cmd_new, "check": cmd_check}
    return handlers[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main())

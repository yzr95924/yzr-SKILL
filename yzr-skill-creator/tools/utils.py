"""Shared helpers for the tools scripts."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

DESCRIPTION_MAX_CHARS = 1024


BODY_WORD_LIMIT = 5000


SOFT_WORD_TARGETS: Dict[str, Optional[int]] = {"default": 2000, "meta": None}


CJK_CHARS_PER_WORD = 1.7

EVIDENCE_SNIPPET = 70

ERROR_REPO_ROOT = "error: repo root not found"

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_`.'\-/]+")


def json_text(payload: object) -> str:
    """唯一的 JSON 渲染口径：缩进 2、保留中文。"""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def estimate_body_words(body: str) -> int:
    """估算正文词数：CJK 字符折算加 ASCII token 数（先剔除围栏代码块）。"""
    prose = "\n".join(line for _, line in iter_unfenced_lines(body))
    cjk_chars = len(CJK_RE.findall(prose))
    ascii_tokens = len(_ASCII_TOKEN_RE.findall(CJK_RE.sub(" ", prose)))
    return int(round(cjk_chars / CJK_CHARS_PER_WORD + ascii_tokens))


_FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})")


def find_code_spans(line: str) -> List[Tuple[int, int]]:
    """返回一行内所有成对反引号代码段的 (起点, 终点)；未闭合的反引号忽略。"""
    spans: List[Tuple[int, int]] = []
    i = 0
    while i < len(line):
        if line[i] == "`":
            close = line.find("`", i + 1)
            if close == -1:
                break
            spans.append((i, close + 1))
            i = close + 1
        else:
            i += 1
    return spans


def iter_unfenced_lines(text: str):
    """逐行产出 (行号, 行内容)，跳过围栏代码块内部的行。"""
    fence: Optional[str] = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _FENCE_RE.match(line)
        if match:
            marker = match.group(2)
            if fence is None:
                fence = marker
                continue
            if marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
                continue
        if fence is None:
            yield lineno, line


FINDING_LEVELS = ("ERROR", "WARN", "INFO")


class Finding(NamedTuple):
    """一条审计发现；调用点一律关键字传参（六个字段都是 str，位置传错 linter 看不见）。"""

    rule: str
    level: str
    evidence: str
    file: str = ""
    line: str = ""
    fix: str = ""

    def location(self) -> str:
        """返回 `file:line` 前缀（缺字段则尽量短），供报告行拼接。"""
        if self.file and self.line:
            return f"{self.file}:{self.line}  "
        if self.file:
            return f"{self.file}  "
        return ""

    def to_dict(self) -> Dict[str, str]:
        """转成 JSON 友好的 dict（六个字段齐全）。"""
        return {
            "rule": self.rule,
            "level": self.level,
            "file": self.file,
            "line": self.line,
            "evidence": self.evidence,
            "fix": self.fix,
        }


def format_findings(findings: List[Finding], show_rule: bool = False) -> List[str]:
    """把 Finding 列表渲染成一行一条的人类可读文本；show_rule 时在等级后带 [RULE]。"""
    out = []
    for f in findings:
        head = f"{f.level} [{f.rule}]: " if show_rule else f"{f.level}: "
        text = f"{head}{f.location()}{f.evidence}"
        if f.fix:
            text += f" —— {f.fix}"
        out.append(text)
    return out


KEBAB_NAME_RE = re.compile(r"^[a-z0-9-]+$")


def discover_skill_dirs(repo_root: Path, require_parseable: bool = False) -> List[Path]:
    """列出 repo 根下含 SKILL.md 的目录；require_parseable 时只留 name 可解析且合规的。"""
    dirs: List[Path] = []
    if not repo_root.is_dir():
        return dirs
    for child in sorted(repo_root.iterdir()):
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        if require_parseable:
            try:
                name = parse_skill_md(child)[0]
            except (ValueError, OSError):
                continue
            if not KEBAB_NAME_RE.match(name):
                continue
        dirs.append(child)
    return dirs


def run_screen(description: str, scan_fn, argv: Optional[List[str]], summary_tail: str) -> int:
    """筛查类 CLI 共享骨架：解析目标 → 逐目标跑 scan_fn → JSON/文本渲染 → 有 Finding 退 1。"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("skill_dir", nargs="?", default=None, help="path to one skill directory")
    parser.add_argument("--repo-root", default=None, help="scan every skill dir under this repo root")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human-readable lines")
    args = parser.parse_args(argv)

    if args.repo_root:
        root = Path(args.repo_root).resolve()
        if not root.is_dir():
            print(f"{ERROR_REPO_ROOT}: {root}", file=sys.stderr)
            return 2
        targets = discover_skill_dirs(root)
    elif args.skill_dir:
        skill_dir = Path(args.skill_dir).resolve()
        if not (skill_dir / "SKILL.md").is_file():
            print(f"error: no SKILL.md under: {skill_dir}", file=sys.stderr)
            return 2
        targets = [skill_dir]
    else:
        parser.error("give a skill dir or --repo-root")

    findings: List[Finding] = []
    for target in targets:
        for finding in scan_fn(target):
            if len(targets) > 1:
                finding = finding._replace(evidence=f"[{target.name}] {finding.evidence}")
            findings.append(finding)

    if args.json:
        print(
            json_text(
                {
                    "targets": [str(t) for t in targets],
                    "finding_count": len(findings),
                    "findings": [f.to_dict() for f in findings],
                }
            )
        )
    else:
        for line in format_findings(findings):
            print(line)
        print(f"\nScanned {len(targets)} skill(s); {len(findings)} {summary_tail}")
    return 1 if findings else 0


def frontmatter_span(text: str) -> Optional[Tuple[int, int]]:
    """返回 frontmatter 围栏的 (起始行, 结束行) 索引（0-based）；不以 --- 开头或未闭合时返回 None。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return 0, i
    return None


def load_frontmatter(skill_path: Path) -> Dict:
    """读取 SKILL.md 的 YAML frontmatter；缺失或非法时抛 ValueError。"""
    content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    span = frontmatter_span(content)
    if span is None:
        reason = "no opening ---" if content.split("\n", 1)[0].strip() != "---" else "no closing ---"
        raise ValueError(f"SKILL.md missing frontmatter ({reason})")
    lines = content.split("\n")

    # 局部导入：只有 frontmatter 读取需要 PyYAML，其余检查保持 stdlib 可用
    import yaml

    try:
        data = yaml.safe_load("\n".join(lines[1 : span[1]]))
    except yaml.YAMLError as e:
        raise ValueError(f"invalid YAML frontmatter: {e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Frontmatter must be a YAML dictionary")
    return data


def parse_skill_md(skill_path: Path) -> Tuple[str, str, str]:
    """返回 (name, description, 全文)；description 的空白折叠成单行。"""
    frontmatter = load_frontmatter(skill_path)
    name = str(frontmatter.get("name", "") or "").strip()
    description = " ".join(str(frontmatter.get("description", "") or "").split())
    content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    return name, description, content


# 条目 = (H2 标题（不含 `## ` 前缀）, 允许省略该节的 tier 集）；空集 = 各 tier 必填；assets/skill-template.md 须与此一致（verify 查漂移）
CANONICAL_BODY_SECTIONS = (
    ("输入与输出", frozenset()),
    ("执行原则", frozenset({"reference"})),
    ("工作流", frozenset({"reference"})),
    ("参考样例", frozenset({"default", "reference", "meta"})),
)


SKILL_TIERS = ("default", "reference", "meta")


def skill_tier(skill_path: Path, override: Optional[str] = None) -> str:
    """解析结构 tier：显式 override > frontmatter metadata.tier > default；非法值回落 default。"""
    if override:
        return override
    try:
        metadata = load_frontmatter(skill_path).get("metadata") or {}
    except (ValueError, OSError):
        return "default"
    tier = metadata.get("tier") if isinstance(metadata, dict) else None
    return tier if tier in SKILL_TIERS else "default"


# "哪些 md 属于本 skill"的唯一口径：按用途给枚举子集，消费者的覆盖范围与 --audit 宣告都从这里产出，不手抄清单
# prose = 文风检查（入口 + 参考资料）；links = 链接解析（顶层 md + ref/tools，assets 骨架拷进新目录后相对路径变化，不查）；
# toc = 全树目录扫描；audit = 原则校验精读宣告清单
_MD_SCOPE_SUBDIRS = {
    "prose": ("ref", "assets"),
    "links": ("ref", "tools"),
    "toc": None,
    "audit": ("ref", "tools", "assets", "eval"),
}

# prose 只扫 SKILL.md；links / toc / audit 扫顶层全部 *.md
_MD_SCOPE_TOP_ALL = frozenset({"links", "toc", "audit"})


def skill_markdown_files(skill_dir: Path, scope: str = "prose") -> List[Path]:
    """按用途口径列出 skill 的 md 文件。"""
    subdirs = _MD_SCOPE_SUBDIRS[scope]
    if subdirs is None:
        return sorted(skill_dir.rglob("*.md"))
    if scope in _MD_SCOPE_TOP_ALL:
        files = sorted(skill_dir.glob("*.md"))
    else:
        skill_md = skill_dir / "SKILL.md"
        files = [skill_md] if skill_md.is_file() else []
    for sub in subdirs:
        sub_root = skill_dir / sub
        if sub_root.is_dir():
            files += sorted(p for p in sub_root.rglob("*.md") if p.is_file())
    return files


# skill 内容子目录全集；检查器按用途取子集
SKILL_SOURCE_SUBDIRS = ("ref", "assets", "tools")

# skill 顶层子目录白名单；其余顶层目录报 DIR-UNKNOWN ERROR（见 quick_validate.check_dir_naming）
SKILL_SUBDIRS = ("ref", "tools", "tests", "assets", "eval")

# 旧目录名 → 标准名；出现旧名报 DIR-LEGACY ERROR（见 quick_validate.check_dir_naming）
LEGACY_SUBDIR_RENAMES = {"references": "ref", "scripts": "tools"}

WITH_SKILL = "with_skill"
WITHOUT_SKILL = "without_skill"
OLD_SKILL = "old_skill"
SIDES = (WITH_SKILL, WITHOUT_SKILL, OLD_SKILL)

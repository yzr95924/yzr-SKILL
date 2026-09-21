"""Shared helpers for the tools scripts."""

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

DESCRIPTION_MAX_CHARS = 1024


BODY_WORD_LIMIT = 5000


SOFT_WORD_TARGETS: Dict[str, Optional[int]] = {"default": 2000, "reference": 300, "meta": None}


CJK_CHARS_PER_WORD = 1.7

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_`.'\-/]+")


def estimate_body_words(body: str) -> int:
    """估算正文词数：CJK 字符数 / 1.7 加 ASCII token 数（先剔除围栏代码块）。"""
    prose = "\n".join(line for _, line in iter_unfenced_lines(body))
    cjk_chars = len(_CJK_RE.findall(prose))
    ascii_tokens = len(_ASCII_TOKEN_RE.findall(_CJK_RE.sub(" ", prose)))
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


def format_findings(findings: List[Finding]) -> List[str]:
    """把 Finding 列表渲染成一行一条的人类可读文本。"""
    out = []
    for f in findings:
        text = f"{f.level}: {f.location()}{f.evidence}"
        if f.fix:
            text += f" —— {f.fix}"
        out.append(text)
    return out


_KEBAB_NAME_RE = re.compile(r"^[a-z0-9-]+$")


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
            if not _KEBAB_NAME_RE.match(name):
                continue
        dirs.append(child)
    return dirs


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
    content = (skill_path / "SKILL.md").read_text()
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
    content = (skill_path / "SKILL.md").read_text()
    return name, description, content


# 条目 = (H2 标题, 允许省略该节的 tier 集)；空集 = 各 tier 必填
CANONICAL_BODY_SECTIONS = (
    ("## 输入 / 输出", frozenset()),
    ("## 执行原则 / 边界", frozenset({"reference"})),
    ("## 工作流 / 步骤", frozenset({"reference"})),
    ("## 参考样例", frozenset({"default", "reference", "meta"})),
)


SKILL_TIERS = ("default", "reference", "meta")

SIDES = ("with_skill", "without_skill", "old_skill")

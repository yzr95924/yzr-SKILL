#!/usr/bin/env python3
"""Description 触发评估的机械半区：prep（拼判题批次）/ score（汇总）/ apply（写回），零 LLM、零子进程。"""

import argparse
import difflib
import json
import os
import random
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.quick_validate import check_description_format, validate_skill  # noqa: E402
from tools.utils import frontmatter_span, json_text, parse_skill_md  # noqa: E402

# 路由评估竞争池 = agent 实际可见的已部署集合（npx 分发落点）；与仓维护"vendor 副本不读"约定语境不同：
# 那边管改源只认仓库，这边测的是真实触发面，默认 --skills-dir 可覆盖
SKILLS_DIR = Path.home() / ".agents" / "skills"

DEFAULT_RUNS = 3
DEFAULT_TRIGGER_THRESHOLD = 0.5
DEFAULT_SEED = 42

# 金丝雀哨兵：随每批 judge 题混跑，判"通道坏了"（如判官恒答 null / 恒选第一个）而不是分数差；
# 正向题要求命中假 skill，负向题要求 null，两个方向都探
CANARY_NAME = "_canary_skill"
CANARY_SKILL = {
    "name": CANARY_NAME,
    "description": "当用户提到“量子香蕉”时使用本 skill。触发：量子香蕉。不适用：其它一切。",
}
CANARY_QUERIES: List[Dict] = [
    {"query": "帮我处理一下量子香蕉的排序问题", "expect": CANARY_NAME},
    {"query": "帮我写个 Python 脚本把两个 JSON 合并一下", "expect": None},
]

# markdownlint MD013 限 120 列（含 frontmatter）；90 给 2 空格缩进留余量
DESCRIPTION_WRAP_WIDTH = 90
_DESCRIPTION_KEY_RE = re.compile(r"^description:[ \t]*(.*)$")
_BREAK_AFTER = "。；，、：）】"


def collect_skills(
    skill_name: str, candidate_description: str, skills_dir: Optional[Path] = None
) -> List[Dict[str, str]]:
    """收集 skills 目录下的 name 与 description，目标 skill 用候选描述替换。"""
    root = skills_dir or SKILLS_DIR
    if not root.is_dir():
        raise RuntimeError(f"skills dir not found: {root} (pass --skills-dir to override)")
    skills: List[Dict[str, str]] = []
    for entry in sorted(root.iterdir()):
        if not (entry / "SKILL.md").is_file():
            continue
        try:
            name, desc, _ = parse_skill_md(entry)
        except (ValueError, OSError):
            continue
        if not name or not desc:
            continue
        if name == skill_name:
            desc = candidate_description
        skills.append({"name": name, "description": desc})
    if not any(s["name"] == skill_name for s in skills):
        # 目标尚未装进 skills 目录（新建 skill 的首评）：注入候选，否则判官只能在 decoy 里挑
        skills.append({"name": skill_name, "description": candidate_description})
    return skills


def load_eval_set(path: Path) -> List[Dict]:
    """读入评估集：缺字段或同 query 冲突时抛 ValueError（消息可直接给用户）。"""
    try:
        eval_set = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read eval set {path}: {e}") from e
    if not isinstance(eval_set, list) or not eval_set:
        raise ValueError("eval set must be a non-empty JSON array")
    for i, item in enumerate(eval_set):
        if not isinstance(item, dict) or "query" not in item or "should_trigger" not in item:
            raise ValueError(f"eval set item {i} missing 'query' / 'should_trigger': {item!r}")
    unique: Dict[str, dict] = {}
    for item in eval_set:
        prev = unique.get(item["query"])
        if prev is not None and bool(prev["should_trigger"]) != bool(item["should_trigger"]):
            raise ValueError(f"query appears twice with conflicting should_trigger: {item['query']!r}")
        if prev is None:
            unique[item["query"]] = item
    return list(unique.values())


_JUDGE_PREAMBLE = (
    "You are the routing layer of an AI coding agent. Below is the list of available skills "
    "(name + description) and a list of user queries. For EACH query, decide which one skill "
    "(if any) you would load to handle it.\n"
    "Route ONLY against the skill list below. Ignore any skills installed in your own "
    "environment or session. Do not use any tools or read any files except writing the result "
    "file named at the end. Judge every query independently.\n\n"
)


def build_judge_prompt(skills: List[Dict[str, str]], numbered_queries: List[Tuple[int, str]], result_path: Path) -> str:
    """拼一个 run 的整批判题 prompt（技能清单 + 编号查询 + JSON 数组落盘指令）。"""
    lines = [_JUDGE_PREAMBLE, "Available skills:"]
    for i, s in enumerate(skills, 1):
        lines.append(f"{i}. {s['name']}:\n   {s['description']}")
    lines.append("\nQueries:")
    for qid, text in numbered_queries:
        lines.append(f"[q{qid}] {text}")
    lines.append(
        "\nReply format: a JSON array with one object per query —\n"
        '[{"query_id": <int>, "skill": "<chosen skill name or null>"}, ...]\n\n'
        f"Write that JSON array as the ONLY content of this file: {result_path}\n"
        "Then reply with the single word DONE."
    )
    return "\n".join(lines)


def _read_description_file(path: str) -> str:
    """读候选描述文件；IO 失败抛 ValueError（子命令各自转退出码）。"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"cannot read description file: {e}") from e


def cmd_prep(args: argparse.Namespace) -> int:
    """prep：建 out-dir，写 manifest 与每 run 一个判题 prompt。"""
    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").is_file():
        print(f"error: no SKILL.md under {skill_path}", file=sys.stderr)
        return 2
    try:
        name, current_desc, _ = parse_skill_md(skill_path)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.description_file:
        try:
            candidate = _read_description_file(args.description_file)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    else:
        candidate = current_desc
    candidate = " ".join(candidate.split())
    try:
        eval_set = load_eval_set(Path(args.eval_set))
        skills = collect_skills(name, candidate, args.skills_dir)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        print(f"error: out dir exists and is not empty: {out_dir}", file=sys.stderr)
        return 2
    prompts_dir = out_dir / "prompts"
    results_dir = out_dir / "results"
    prompts_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)

    queries = [
        {"id": i + 1, "query": item["query"], "should_trigger": bool(item["should_trigger"])}
        for i, item in enumerate(eval_set)
    ]
    canary = [
        {"id": len(queries) + j + 1, "query": c["query"], "expect": c["expect"]} for j, c in enumerate(CANARY_QUERIES)
    ]
    all_items = [(q["id"], q["query"]) for q in queries] + [(c["id"], c["query"]) for c in canary]

    for run in range(1, args.runs + 1):
        batch = list(all_items)
        random.Random(args.seed * 100 + run).shuffle(batch)
        result_path = (results_dir / f"run-{run}.json").resolve()
        prompt = build_judge_prompt(skills + [CANARY_SKILL], batch, result_path)
        (prompts_dir / f"run-{run}.txt").write_text(prompt, encoding="utf-8")

    manifest = {
        "skill": name,
        "description": candidate,
        "runs": args.runs,
        "seed": args.seed,
        "queries": queries,
        "canary": canary,
    }
    (out_dir / "manifest.json").write_text(json_text(manifest), encoding="utf-8")

    print(f"prepped {out_dir}: {len(queries)} query(s), {args.runs} run(s) x 1 judge sub-agent")
    print(
        "next: spawn one harness sub-agent per prompts/run-<k>.txt (deliver the file content verbatim), "
        "each judge writes its own results/run-<k>.json"
    )
    return 0


def _normalize_choice(value) -> Optional[str]:
    """判官选择的归一化：null / "null" / 空串都算不选。"""
    if value is None:
        return None
    text = str(value).strip()
    return None if text in ("", "null", "None") else text


def _load_run_choices(result_path: Path, expected_ids: set) -> Dict[int, Optional[str]]:
    """读一个 run 的判官结果文件；非法 / 缺 id 时抛 ValueError。"""
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read judge result {result_path}: {e}") from e
    if not isinstance(data, list):
        raise ValueError(f"judge result {result_path} is not a JSON array")
    choices: Dict[int, Optional[str]] = {}
    for obj in data:
        if not isinstance(obj, dict) or "query_id" not in obj:
            raise ValueError(f"judge result {result_path} has a malformed entry: {obj!r}")
        choices[int(obj["query_id"])] = _normalize_choice(obj.get("skill"))
    missing = expected_ids - set(choices)
    if missing:
        raise ValueError(f"judge result {result_path} missing query_id(s): {sorted(missing)}")
    return choices


def cmd_score(args: argparse.Namespace) -> int:
    """score：金丝雀哨兵校验 + 四象限汇总，stdout 出 results JSON。"""
    out_dir = Path(args.out_dir)
    try:
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"error: cannot read manifest: {e}", file=sys.stderr)
        return 2

    queries, canary = manifest["queries"], manifest["canary"]
    expected_ids = {q["id"] for q in queries} | {c["id"] for c in canary}
    run_choices: List[Dict[int, Optional[str]]] = []
    for run in range(1, manifest["runs"] + 1):
        try:
            run_choices.append(_load_run_choices(out_dir / "results" / f"run-{run}.json", expected_ids))
        except ValueError as e:
            print(f"error: {e} — re-spawn that run's judge sub-agent and score again", file=sys.stderr)
            return 2

    for run, choices in enumerate(run_choices, 1):
        for c in canary:
            got = choices[c["id"]]
            if got != c["expect"]:
                print(
                    f"channel error (run {run}): canary query {c['id']} expected {c['expect']!r} got {got!r} — "
                    "judge channel is broken, refusing to produce numbers",
                    file=sys.stderr,
                )
                return 3

    target = manifest["skill"]
    results = []
    for q in queries:
        triggers = sum(1 for choices in run_choices if choices[q["id"]] == target)
        runs = manifest["runs"]
        should = bool(q["should_trigger"])
        results.append(
            {
                "query": q["query"],
                "query_id": q["id"],
                "should_trigger": should,
                "triggers": triggers,
                "runs": runs,
                "pass": (triggers / runs >= args.trigger_threshold) == should,
            }
        )

    def summarize(subset: List[Dict]) -> Optional[Dict]:
        """把一组 results 汇总成 passed/failed/total；空组返回 None。"""
        if not subset:
            return None
        passed = sum(1 for r in subset if r["pass"])
        return {"passed": passed, "failed": len(subset) - passed, "total": len(subset)}

    payload = {
        "skill": target,
        "description": manifest["description"],
        "runs": manifest["runs"],
        "trigger_threshold": args.trigger_threshold,
        "results": results,
        "summary": summarize(results),
    }
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        print(
            f"  [{status}] rate={r['triggers']}/{r['runs']} expected={r['should_trigger']}: {r['query'][:60]}",
            file=sys.stderr,
        )
    s = payload["summary"]
    print(f"summary: {s['passed']}/{s['total']} correct", file=sys.stderr)
    print(json_text(payload))
    return 0


# ---- apply：description 写回（折行 / 校验 / dry-run 与历史实现一致） ----


def _frontmatter_close(lines: List[str]) -> int:
    """返回 frontmatter 结束行索引；缺失抛 ValueError。"""
    span = frontmatter_span("\n".join(lines))
    if span is None:
        raise ValueError("SKILL.md frontmatter has no closing ---")
    return span[1]


def _description_span(lines: List[str]) -> Tuple[int, int]:
    """定位 description 键的 (起始行, 结束行)。"""
    close = _frontmatter_close(lines)
    for i in range(1, close):
        match = _DESCRIPTION_KEY_RE.match(lines[i])
        if match:
            end = close
            for j in range(i + 1, close):
                if lines[j].strip() and not (lines[j].startswith("  ") or lines[j].startswith("\t")):
                    end = j
                    break
            return i, end
    raise ValueError("SKILL.md frontmatter has no description key")


def wrap_description(description: str, indent: str = "  ", width: int = DESCRIPTION_WRAP_WIDTH) -> List[str]:
    """按标点与空白把描述折行成 YAML 块标量行。"""
    out: List[str] = []
    for paragraph in description.split("\n"):
        # 输入行内换行是折行不是分段：块标量里空行是字面内容，插入会造成往返失真
        pieces: List[str] = []
        current = ""
        for char in paragraph:
            current += char
            if char.isspace() or char in _BREAK_AFTER:
                pieces.append(current)
                current = ""
        if current:
            pieces.append(current)

        line = ""
        for piece in pieces:
            if len(piece) > width:
                if line:
                    out.append(indent + line)
                    line = ""
                for start in range(0, len(piece), width):
                    chunk = piece[start : start + width]
                    if start + width < len(piece):
                        out.append(indent + chunk)
                    else:
                        line = chunk
                continue
            if line and len(line) + len(piece) > width:
                out.append(indent + line.rstrip())
                line = piece
            else:
                line += piece
        out.append(indent + line.rstrip())
    return out


def rewrite_description(text: str, new_description: str) -> str:
    """把 SKILL.md 全文里的 description 块替换为新描述的块标量。"""
    lines = text.split("\n")
    start, end = _description_span(lines)
    block = ["description: |"] + wrap_description(new_description.strip())
    return "\n".join(lines[:start] + block + lines[end:])


def apply_description(skill_path: Path, new_description: str, dry_run: bool = False) -> int:
    """校验后把新描述写回 SKILL.md（dry_run 只打印 diff），返回退出码。"""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.is_file():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        return 1
    original = skill_md.read_text(encoding="utf-8")
    try:
        current = parse_skill_md(skill_path)[1]
    except ValueError as e:
        print(f"Error: 现有 frontmatter 无法解析，先修 SKILL.md：{e}", file=sys.stderr)
        return 1
    if " ".join(new_description.split()) == current:
        print("候选 description 与现有 description 一致，无需改动。", file=sys.stderr)
        return 0

    try:
        updated = rewrite_description(original, new_description)
    except ValueError as e:
        print(f"Error: cannot locate the description block: {e}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="skill-apply-") as tmp:
        # validate_skill 校验 name 与目录名一致，探测目录须沿用原 skill 名
        probe = Path(tmp) / skill_path.name
        probe.mkdir()
        (probe / "SKILL.md").write_text(updated, encoding="utf-8")
        valid, message = validate_skill(probe)
        period_error = None
        if valid:
            period_error = next((f for f in check_description_format(probe) if f.rule == "DESC-TRAILING-PERIOD"), None)
    if not valid:
        print(f"Error: 新 frontmatter 未通过校验，SKILL.md 未改动：{message}", file=sys.stderr)
        return 1
    if period_error is not None:
        print(
            f"Error: 新 description {period_error.evidence}（{period_error.fix}），SKILL.md 未改动",
            file=sys.stderr,
        )
        return 1

    if dry_run:
        diff = difflib.unified_diff(
            original.splitlines(), updated.splitlines(), "a/SKILL.md", "b/SKILL.md", lineterm="", n=2
        )
        print("\n".join(diff))
        print("\n(--dry-run: 未写入)", file=sys.stderr)
        return 0

    tmp_path = skill_md.with_name(skill_md.name + ".tmp-apply")
    tmp_path.write_text(updated, encoding="utf-8")
    os.replace(str(tmp_path), str(skill_md))
    print(f"已写入 {skill_md}（description {len(current)} → {len(new_description.strip())} 字符）", file=sys.stderr)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """apply：从描述文件读候选并写回。"""
    try:
        candidate = _read_description_file(args.description_file)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not candidate.strip():
        print("error: description file is empty", file=sys.stderr)
        return 2
    return apply_description(Path(args.skill_path), candidate, dry_run=args.dry_run)


def _build_parser() -> argparse.ArgumentParser:
    """三段式 CLI：prep / score / apply。"""
    parser = argparse.ArgumentParser(description="Description trigger eval: prep judge batches, score results, apply")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prep", help="write manifest + one judge prompt file per run")
    p.add_argument("--skill-path", required=True, help="skill directory under evaluation")
    p.add_argument("--eval-set", required=True, help="path to eval set JSON")
    p.add_argument("--out-dir", required=True, help="fresh directory for manifest/prompts/results")
    p.add_argument("--description-file", default=None, help="candidate description (default: current frontmatter)")
    p.add_argument(
        "--runs", type=int, default=DEFAULT_RUNS, help="judge sub-agents per evaluation (default: %(default)s)"
    )
    p.add_argument("--seed", type=int, default=DEFAULT_SEED, help="shuffle seed (default: %(default)s)")
    p.add_argument("--skills-dir", type=Path, default=None, help="routing pool (default: ~/.agents/skills)")
    p.set_defaults(func=cmd_prep)

    s = sub.add_parser("score", help="canary check + four-quadrant tally over results/*.json")
    s.add_argument("--out-dir", required=True, help="directory written by prep")
    s.add_argument(
        "--trigger-threshold",
        type=float,
        default=DEFAULT_TRIGGER_THRESHOLD,
        help="trigger-rate threshold (default: %(default)s)",
    )
    s.set_defaults(func=cmd_score)

    a = sub.add_parser("apply", help="write a candidate description back into SKILL.md frontmatter")
    a.add_argument("--skill-path", required=True, help="skill directory")
    a.add_argument("--description-file", required=True, help="file containing the candidate description")
    a.add_argument("--dry-run", action="store_true", help="print a diff, write nothing")
    a.set_defaults(func=cmd_apply)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：分发到子命令。"""
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""为一个 eval 迭代搭建各侧沙箱与 prompt，供编排 agent 用 harness subagent 发起对照侧（零 LLM、零子进程）。"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import eval_init  # noqa: E402
from tools.utils import OLD_SKILL, SIDES, WITHOUT_SKILL  # noqa: E402

SANDBOX_DIRNAME = "run"
TRANSCRIPT_NAME = "transcript.txt"
PROMPT_NAME = "prompt.txt"

_WITH_PREAMBLE = (
    "You MUST follow the skill given under 'Skill path' below: first Read its SKILL.md in full, "
    "then act exactly as it instructs (including any files it tells you to read). An installed "
    "vendor copy of this skill may be outdated — trust only the repo path given. Do not load any "
    "other skill from your available_skills list.\n\n"
)
_WITHOUT_PREAMBLE = (
    "Capability test: do NOT use, read, or load any skill from your available_skills list; "
    "solve this with base tools and general ability only.\n\n"
)
_HEADLESS_NOTE = (
    "\n\nNote: you run headless — no user can answer questions. If the workflow expects user "
    "confirmation somewhere, produce the exact artifact you would have shown the user, save it "
    "under the outputs directory, and stop there.\n"
)


def build_prompt(side: str, item: Dict, out_dir: Path, skill_in_sandbox: Optional[Path]) -> str:
    """按侧别拼 subagent 的完整 prompt（隔离前言 + 任务块 + headless 声明）。"""
    task = eval_init.skill_prompt(skill_in_sandbox if side != WITHOUT_SKILL else None, item, out_dir)
    preamble = _WITHOUT_PREAMBLE if side == WITHOUT_SKILL else _WITH_PREAMBLE
    return preamble + task + _HEADLESS_NOTE


def make_sandbox(repo_root: Path, side_dir: Path) -> Path:
    """把整个仓拷成该侧专属沙箱（排除 git 缓存与 workspace），返回沙箱内的仓目录。"""
    sandbox = side_dir / SANDBOX_DIRNAME
    if sandbox.exists():
        shutil.rmtree(str(sandbox))
    sandbox.mkdir(parents=True)
    target = sandbox / repo_root.name
    shutil.copytree(str(repo_root), str(target), ignore=eval_init.SANDBOX_IGNORE)
    return target


def overlay_snapshot(iteration: Path, skill_in_sandbox: Path) -> None:
    """把 old_skill 侧沙箱里的 skill 换成该轮迭代的旧版快照。"""
    snapshot = iteration / eval_init.SNAPSHOT_DIRNAME
    if not snapshot.is_dir():
        raise FileNotFoundError(f"old_skill baseline needs a snapshot, none at {snapshot}")
    shutil.rmtree(str(skill_in_sandbox))
    shutil.copytree(str(snapshot), str(skill_in_sandbox))


def _eval_id_of(eval_dir: Path) -> Optional[int]:
    """从 eval-<id> 目录名解析 id；不合规范返回 None。"""
    try:
        return int(eval_dir.name.split("-", 1)[1])
    except ValueError:
        return None


def _is_selected(eval_dir: Path, eval_ids: Optional[List[int]]) -> bool:
    """该用例目录是否在 --eval 筛选范围内（目录名不合规范一律不选）。"""
    eval_id = _eval_id_of(eval_dir)
    return eval_id is not None and (not eval_ids or eval_id in eval_ids)


def _sides_of(eval_dir: Path) -> List[Path]:
    """该用例已建好的可跑侧别目录。"""
    return [eval_dir / s for s in SIDES if (eval_dir / s).is_dir()]


def _pending_sides(eval_dir: Path, force: bool) -> List[Path]:
    """该用例待跑的侧：无 transcript 才跑（--force 忽略已有 transcript 全重跑）。"""
    return [s for s in _sides_of(eval_dir) if force or not (s / TRANSCRIPT_NAME).is_file()]


def prep_case(eval_dir: Path, iteration: Path, skill_path: Path, evals: Dict[int, Dict], force: bool) -> List[Path]:
    """备好一个用例的所有待跑侧：沙箱 + prompt.txt，返回待跑侧目录列表。"""
    item = evals.get(_eval_id_of(eval_dir))
    if item is None:
        print(f"  skip {eval_dir.name}: id not in evals.json", file=sys.stderr)
        return []
    pending = _pending_sides(eval_dir, force)
    for s in pending:
        sandbox_repo = make_sandbox(skill_path.parent, s)
        if s.name == OLD_SKILL:
            overlay_snapshot(iteration, sandbox_repo / skill_path.name)
        prompt = build_prompt(s.name, item, s / "outputs", sandbox_repo / skill_path.name)
        (s / PROMPT_NAME).write_text(prompt, encoding="utf-8")
    return pending


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：校验路径、逐侧备沙箱与 prompt、打印待跑清单。"""
    parser = argparse.ArgumentParser(description="Build per-side sandboxes and prompts for one eval iteration")
    parser.add_argument("--iteration", required=True, help="path to <skill>-workspace/iteration-N/")
    parser.add_argument("--skill-path", required=True, help="skill directory under verification")
    parser.add_argument("--eval", type=int, action="append", dest="eval_ids", help="restrict to these eval ids")
    parser.add_argument("--force", action="store_true", help="re-prep sides even if a transcript already exists")
    args = parser.parse_args(argv)

    iteration = Path(args.iteration).resolve()
    skill_path = Path(args.skill_path).resolve()
    if not iteration.is_dir() or not (skill_path / "SKILL.md").is_file():
        print("error: iteration dir or skill path invalid", file=sys.stderr)
        return 2

    try:
        evals = {int(item["id"]): item for item in eval_init.load_evals(skill_path / "eval" / "evals.json")}
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    selected = [d for d in sorted(iteration.glob("eval-*")) if _is_selected(d, args.eval_ids)]
    needs_snapshot = any((d / OLD_SKILL) in _pending_sides(d, args.force) for d in selected)
    if needs_snapshot and not (iteration / eval_init.SNAPSHOT_DIRNAME).is_dir():
        print(
            f"error: old_skill side has no snapshot to overlay: {iteration / eval_init.SNAPSHOT_DIRNAME}",
            file=sys.stderr,
        )
        return 2

    total = 0
    for eval_dir in selected:
        for side_dir in prep_case(eval_dir, iteration, skill_path, evals, args.force):
            total += 1
            print(f"PENDING {eval_dir.name}/{side_dir.name}: {side_dir / PROMPT_NAME}")
    if not total:
        print("nothing to prep (all sides have transcripts; use --force to redo)")
    else:
        print(
            f"\n{total} side(s) prepped — spawn one harness sub-agent per PENDING line, "
            f"prompt = that prompt.txt delivered verbatim; save each final reply to "
            f"<side>/{TRANSCRIPT_NAME} as-is",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

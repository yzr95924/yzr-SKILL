#!/usr/bin/env python3
"""Run eval iterations with independent opencode sub-agents (with_skill vs without_skill / old_skill baseline)."""

import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
import time
from functools import partial
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import eval_init  # noqa: E402
from tools.utils import OLD_SKILL, SIDES, WITHOUT_SKILL, run_supported_flags  # noqa: E402

DEFAULT_TIMEOUT = 600
SANDBOX_DIRNAME = "run"
TRANSCRIPT_NAME = "transcript.txt"

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
    """按侧别拼独立 agent 的完整 prompt（隔离前言 + 任务块 + headless 声明）。"""
    task = eval_init.skill_prompt(skill_in_sandbox if side != WITHOUT_SKILL else None, item, out_dir)
    preamble = _WITHOUT_PREAMBLE if side == WITHOUT_SKILL else _WITH_PREAMBLE
    return preamble + task + _HEADLESS_NOTE


def _to_text(data) -> str:
    """TimeoutExpired.stdout 在文本模式下仍可能是 bytes，统一解码。"""
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data or ""


def make_sandbox(repo_root: Path, side_dir: Path) -> Path:
    """把整个仓拷成该侧专属沙箱（排除 git 缓存与 workspace），返回沙箱内的仓目录。"""
    sandbox = side_dir / SANDBOX_DIRNAME
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)
    target = sandbox / repo_root.name
    shutil.copytree(str(repo_root), str(target), ignore=eval_init.SANDBOX_IGNORE)
    return target


def run_side(side_dir: Path, opencode: str, prompt: str, timeout: int, model: Optional[str]) -> int:
    """起一个独立 `opencode run` 跑该侧，transcript 落盘，返回该次运行的退出码。"""
    transcript = side_dir / TRANSCRIPT_NAME
    sandbox = side_dir / SANDBOX_DIRNAME
    supported = run_supported_flags()
    cmd = [opencode, "run"]
    if "--pure" in supported:
        cmd.append("--pure")
    if "--dir" in supported:
        cmd.extend(["--dir", str(sandbox)])
    cmd.extend(["--title", "eval-run"])
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)
    header = "--- prompt ---\n" + prompt + "\n--- output ---\n"
    t0 = time.time()
    # 坑：subprocess 的 cwd= 不更新 $PWD，opencode 按 $PWD 解析项目目录（skill 发现随之失效）
    env = {**os.environ, "OPENCODE_DISABLE_AUTOUPDATE": "1", "PWD": str(sandbox)}
    try:
        result = subprocess.run(
            cmd,
            cwd=str(sandbox),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=env,
            timeout=timeout,
        )
        rc, out, note = result.returncode, result.stdout, ""
    except subprocess.TimeoutExpired as e:
        rc, out, note = 124, _to_text(e.stdout), f"\n[eval_run] TIMEOUT after {timeout}s\n"
    transcript.write_text(header + out + note, encoding="utf-8")
    print(f"  {side_dir.parent.name}/{side_dir.name}: rc={rc} {time.time() - t0:.0f}s -> {transcript}")
    return rc


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


def overlay_snapshot(iteration: Path, skill_in_sandbox: Path) -> None:
    """把 old_skill 侧沙箱里的 skill 换成该轮迭代的旧版快照。"""
    snapshot = iteration / eval_init.SNAPSHOT_DIRNAME
    if not snapshot.is_dir():
        raise FileNotFoundError(f"old_skill baseline needs a snapshot, none at {snapshot}")
    shutil.rmtree(str(skill_in_sandbox))
    shutil.copytree(str(snapshot), str(skill_in_sandbox))


class RunContext(NamedTuple):
    """一次 eval_run 运行所需的共享上下文。"""

    iteration: Path
    skill_path: Path
    evals: Dict[int, Dict]
    opencode: str
    timeout: int
    model: Optional[str]
    force: bool
    eval_ids: Optional[List[int]]


def run_case(eval_dir: Path, ctx: RunContext) -> None:
    """跑一个用例：建沙箱与 prompt，各侧并发起子 agent。"""
    if not _is_selected(eval_dir, ctx.eval_ids):
        return
    item = ctx.evals.get(_eval_id_of(eval_dir))
    if item is None:
        print(f"  skip {eval_dir.name}: id not in evals.json", file=sys.stderr)
        return
    side_dirs = [s for s in _sides_of(eval_dir) if ctx.force or not (s / TRANSCRIPT_NAME).is_file()]
    if not side_dirs:
        print(f"  skip {eval_dir.name}: nothing to run (use --force to redo)")
        return
    prompts: Dict[Path, str] = {}
    for s in side_dirs:
        sandbox_repo = make_sandbox(ctx.skill_path.parent, s)
        if s.name == OLD_SKILL:
            overlay_snapshot(ctx.iteration, sandbox_repo / ctx.skill_path.name)
        prompts[s] = build_prompt(s.name, item, s / "outputs", sandbox_repo / ctx.skill_path.name)
    print(f"== {eval_dir.name}: {', '.join(s.name for s in side_dirs)} ==")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(side_dirs)) as pool:
        futures = [pool.submit(run_side, s, ctx.opencode, prompts[s], ctx.timeout, ctx.model) for s in side_dirs]
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"  side crashed: {e}", file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：用例按 --jobs 并发，每个用例内的各侧总是并发。"""
    parser = argparse.ArgumentParser(description="Run one eval iteration's sides with independent opencode sub-agents")
    parser.add_argument("--iteration", required=True, help="path to <skill>-workspace/iteration-N/")
    parser.add_argument("--skill-path", required=True, help="skill directory under verification")
    parser.add_argument("--eval", type=int, action="append", dest="eval_ids", help="restrict to these eval ids")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds per sub-agent run")
    parser.add_argument("--jobs", type=int, default=2, help="eval cases to run concurrently (default: %(default)s)")
    parser.add_argument("--model", default=None, help="provider/model for the sub-agents (default: opencode config)")
    parser.add_argument("--force", action="store_true", help="re-run sides even if a transcript already exists")
    args = parser.parse_args(argv)

    iteration = Path(args.iteration).resolve()
    skill_path = Path(args.skill_path).resolve()
    opencode = shutil.which("opencode")
    if opencode is None:
        print("error: opencode CLI not on PATH; run the degraded path instead", file=sys.stderr)
        return 2
    if not iteration.is_dir() or not (skill_path / "SKILL.md").is_file():
        print("error: iteration dir or skill path invalid", file=sys.stderr)
        return 2

    try:
        evals = {int(item["id"]): item for item in eval_init.load_evals(skill_path / "eval" / "evals.json")}
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    snapshot = iteration / eval_init.SNAPSHOT_DIRNAME
    needs_snapshot = [
        d
        for d in sorted(iteration.glob("eval-*"))
        if _is_selected(d, args.eval_ids)
        and (d / OLD_SKILL).is_dir()
        and (args.force or not (d / OLD_SKILL / TRANSCRIPT_NAME).is_file())
    ]
    if needs_snapshot and not snapshot.is_dir():
        print(f"error: old_skill side has no snapshot to overlay: {snapshot}", file=sys.stderr)
        return 2

    ctx = RunContext(
        iteration=iteration,
        skill_path=skill_path,
        evals=evals,
        opencode=opencode,
        timeout=args.timeout,
        model=args.model,
        force=args.force,
        eval_ids=args.eval_ids,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        list(pool.map(partial(run_case, ctx=ctx), sorted(iteration.glob("eval-*"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

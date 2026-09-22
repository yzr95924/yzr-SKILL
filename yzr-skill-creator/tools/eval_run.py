#!/usr/bin/env python3
"""Run eval iterations with independent opencode sub-agents (with_skill vs without_skill baseline)."""

import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import eval_init  # noqa: E402
from tools.utils import WITH_SKILL, WITHOUT_SKILL  # noqa: E402

DEFAULT_TIMEOUT = 600
SANDBOX_DIRNAME = "run"
TRANSCRIPT_NAME = "transcript.txt"

_SANDBOX_IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*-workspace")

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
    task = eval_init.skill_prompt(skill_in_sandbox if side == WITH_SKILL else None, item, out_dir)
    return (_WITH_PREAMBLE if side == WITH_SKILL else _WITHOUT_PREAMBLE) + task + _HEADLESS_NOTE


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
    shutil.copytree(str(repo_root), str(target), ignore=_SANDBOX_IGNORE)
    return target


def run_side(side_dir: Path, opencode: str, prompt: str, timeout: int, model: Optional[str]) -> int:
    """起一个独立 `opencode run` 跑该侧，transcript 落盘，返回该次运行的退出码。"""
    transcript = side_dir / TRANSCRIPT_NAME
    cmd = [opencode, "run", "--pure", "--dir", str(side_dir / SANDBOX_DIRNAME), "--title", "eval-run"]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)
    header = "--- prompt ---\n" + prompt + "\n--- output ---\n"
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env={**os.environ, "OPENCODE_DISABLE_AUTOUPDATE": "1"},
            timeout=timeout,
        )
        rc, out, note = result.returncode, result.stdout, ""
    except subprocess.TimeoutExpired as e:
        rc, out, note = 124, _to_text(e.stdout), f"\n[eval_run] TIMEOUT after {timeout}s\n"
    transcript.write_text(header + out + note, encoding="utf-8")
    print(f"  {side_dir.parent.name}/{side_dir.name}: rc={rc} {time.time() - t0:.0f}s -> {transcript}")
    return rc


def _sides_of(eval_dir: Path) -> List[Path]:
    """该用例已建好的可跑侧别目录。"""
    return [eval_dir / s for s in (WITH_SKILL, WITHOUT_SKILL) if (eval_dir / s).is_dir()]


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：用例按 --jobs 并发，每个用例内 with/without 两侧总是并发。"""
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

    evals = {int(item["id"]): item for item in eval_init.load_evals(skill_path / "eval" / "evals.json")}

    def run_case(eval_dir: Path) -> None:
        """跑一个用例：建沙箱与 prompt，两侧并发起子 agent。"""
        try:
            eval_id = int(eval_dir.name.split("-", 1)[1])
        except ValueError:
            return
        if args.eval_ids and eval_id not in args.eval_ids:
            return
        item = evals.get(eval_id)
        if item is None:
            print(f"  skip {eval_dir.name}: id not in evals.json", file=sys.stderr)
            return
        side_dirs = [s for s in _sides_of(eval_dir) if args.force or not (s / TRANSCRIPT_NAME).is_file()]
        if not side_dirs:
            print(f"  skip {eval_dir.name}: nothing to run (use --force to redo)")
            return
        prompts: Dict[Path, str] = {}
        for s in side_dirs:
            sandbox = make_sandbox(skill_path.parent, s)
            prompts[s] = build_prompt(s.name, item, s / "outputs", sandbox / skill_path.name)
        print(f"== {eval_dir.name}: {', '.join(s.name for s in side_dirs)} ==")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(side_dirs)) as pool:
            futures = [pool.submit(run_side, s, opencode, prompts[s], args.timeout, args.model) for s in side_dirs]
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    print(f"  side crashed: {e}", file=sys.stderr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        list(pool.map(run_case, sorted(iteration.glob("eval-*"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

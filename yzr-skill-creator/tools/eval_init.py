#!/usr/bin/env python3
"""Scaffold one eval iteration's workspace (the writer half of eval_report)."""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import OLD_SKILL, WITH_SKILL, WITHOUT_SKILL  # noqa: E402

SNAPSHOT_DIRNAME = "skill-snapshot"


def _fail(message: str) -> int:
    """打印错误并返回退出码 2。"""
    print(f"eval_init: {message}", file=sys.stderr)
    return 2


def load_evals(evals_path: Path) -> Optional[List[Dict]]:
    """读取并校验 evals.json；失败时打印错误并返回 None。"""
    try:
        data = json.loads(evals_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(f"cannot read evals.json: {exc}")
        return None
    evals = data.get("evals") if isinstance(data, dict) else None
    if not isinstance(evals, list) or not evals:
        _fail("evals.json must be a JSON object with a non-empty `evals` array")
        return None
    for item in evals:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int) or not item.get("prompt"):
            _fail(f"every eval needs integer `id` and non-empty `prompt` (got: {item!r})")
            return None
    return evals


def skill_prompt(skill_path: Path, item: Dict, out_dir: Path) -> str:
    """拼一条子 agent 任务提示（skill 路径、任务、输入文件、产出目录）。"""
    files = item.get("files") or []
    files_line = ", ".join(str(f) for f in files) if files else "none"
    return (
        "Execute this task:\n"
        f"- Skill path: {skill_path}\n"
        f"- Task: {item['prompt']}\n"
        f"- Input files: {files_line}\n"
        f"- Save outputs to: {out_dir}\n"
        '- Outputs to save: <what the user cares about — e.g. "the .docx file", "the final CSV">'
    )


def init(
    workspace: Path,
    iteration: int,
    skill_path: Path,
    evals: List[Dict],
    baseline: str,
) -> Optional[List[str]]:
    """建 iteration 工作区与目录骨架，返回每用例的提示文本；工作区已存在非空时返回 None。"""
    iteration_dir = workspace / f"iteration-{iteration}"
    if iteration_dir.exists() and any(iteration_dir.iterdir()):
        _fail(f"{iteration_dir} already exists and is not empty — use a fresh iteration number")
        return None

    snapshot_dir = iteration_dir / SNAPSHOT_DIRNAME if baseline == OLD_SKILL else None
    if snapshot_dir is not None:
        shutil.copytree(str(skill_path), str(snapshot_dir))

    prompts: List[str] = []
    for item in evals:
        eval_dir = iteration_dir / f"eval-{item['id']}"
        for side in (WITH_SKILL, baseline):
            (eval_dir / side / "outputs").mkdir(parents=True, exist_ok=True)
        lines = [
            f"=== eval-{item['id']}：同一轮并行启动两个子 agent（不要串行）===",
            f"[{WITH_SKILL}]",
            skill_prompt(skill_path, item, eval_dir / WITH_SKILL / "outputs"),
        ]
        if snapshot_dir is not None:
            lines += [
                f"[{OLD_SKILL}]（指向快照，不指当前版）",
                skill_prompt(snapshot_dir, item, eval_dir / OLD_SKILL / "outputs"),
            ]
        else:
            lines += [
                f"[{WITHOUT_SKILL}]",
                f"同 [{WITH_SKILL}]，但删去 Skill path 一行；Save outputs to: {eval_dir / WITHOUT_SKILL / 'outputs'}",
            ]
        prompts.append("\n".join(lines) + "\n")
    return prompts


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：解析参数、校验路径、建工作区并打印提示。"""
    parser = argparse.ArgumentParser(
        description="Scaffold one eval iteration's workspace (the writer half of eval_report)"
    )
    parser.add_argument("--workspace", required=True, help="Workspace root, e.g. <skill-name>-workspace/")
    parser.add_argument("--iteration", required=True, type=int, help="Iteration number (>= 1)")
    parser.add_argument("--skill-path", required=True, help="Skill directory")
    parser.add_argument("--evals", default=None, help="Path to evals.json (default: <skill-path>/eval/evals.json)")
    parser.add_argument(
        "--baseline",
        required=True,
        choices=(WITHOUT_SKILL, OLD_SKILL),
        help="without_skill = creating a new skill; old_skill = improving one",
    )
    args = parser.parse_args(argv)

    if args.iteration < 1:
        return _fail("--iteration must be >= 1")
    skill_path = Path(args.skill_path).resolve()
    if not (skill_path / "SKILL.md").is_file():
        return _fail(f"{skill_path} is not a skill directory (no SKILL.md)")
    evals_path = Path(args.evals).resolve() if args.evals else skill_path / "eval" / "evals.json"
    if not evals_path.is_file():
        return _fail(f"evals.json not found: {evals_path}")

    evals = load_evals(evals_path)
    if evals is None:
        return 2
    prompts = init(Path(args.workspace).resolve(), args.iteration, skill_path, evals, args.baseline)
    if prompts is None:
        return 2

    print(f"workspace ready: iteration-{args.iteration}, {len(evals)} eval(s), baseline={args.baseline}")
    if args.baseline == OLD_SKILL:
        print(f"snapshot: {Path(args.workspace).resolve() / f'iteration-{args.iteration}' / SNAPSHOT_DIRNAME}")
    for prompt in prompts:
        print()
        print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())

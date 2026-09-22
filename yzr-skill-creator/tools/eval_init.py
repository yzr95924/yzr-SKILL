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


def load_evals(evals_path: Path) -> List[Dict]:
    """读取并校验 evals.json；非法时抛 ValueError（消息可直接给用户）。"""
    try:
        data = json.loads(evals_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read evals.json: {exc}") from exc
    evals = data.get("evals") if isinstance(data, dict) else None
    if not isinstance(evals, list) or not evals:
        raise ValueError("evals.json must be a JSON object with a non-empty `evals` array")
    for item in evals:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int) or not item.get("prompt"):
            raise ValueError(f"every eval needs integer `id` and non-empty `prompt` (got: {item!r})")
    return evals


def skill_prompt(skill_path: Optional[Path], item: Dict, out_dir: Path) -> str:
    """拼一条子 agent 任务提示（skill_path 为 None = 不带 skill 侧），含任务、输入文件、产出目录。"""
    files = item.get("files") or []
    files_line = ", ".join(str(f) for f in files) if files else "none"
    lines = ["Execute this task:"]
    if skill_path is not None:
        lines.append(f"- Skill path: {skill_path}")
    lines += [
        f"- Task: {item['prompt']}",
        f"- Input files: {files_line}",
        f"- Save outputs to: {out_dir}",
    ]
    return "\n".join(lines)


def init(
    workspace: Path,
    iteration: int,
    skill_path: Path,
    evals: List[Dict],
    baseline: str,
) -> None:
    """建 iteration 工作区与目录骨架；目标已存在非空时抛 ValueError。"""
    iteration_dir = workspace / f"iteration-{iteration}"
    if iteration_dir.exists() and any(iteration_dir.iterdir()):
        raise ValueError(f"{iteration_dir} already exists and is not empty — use a fresh iteration number")

    snapshot_dir = iteration_dir / SNAPSHOT_DIRNAME if baseline == OLD_SKILL else None
    if snapshot_dir is not None:
        shutil.copytree(str(skill_path), str(snapshot_dir))

    for item in evals:
        eval_dir = iteration_dir / f"eval-{item['id']}"
        for side in (WITH_SKILL, baseline):
            (eval_dir / side / "outputs").mkdir(parents=True, exist_ok=True)


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

    try:
        evals = load_evals(evals_path)
        init(Path(args.workspace).resolve(), args.iteration, skill_path, evals, args.baseline)
    except ValueError as e:
        return _fail(str(e))

    print(f"workspace ready: iteration-{args.iteration}, {len(evals)} eval(s), baseline={args.baseline}")
    if args.baseline == OLD_SKILL:
        print(f"snapshot: {Path(args.workspace).resolve() / f'iteration-{args.iteration}' / SNAPSHOT_DIRNAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

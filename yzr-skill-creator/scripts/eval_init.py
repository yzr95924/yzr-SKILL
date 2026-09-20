#!/usr/bin/env python3
"""
Scaffold one eval iteration's workspace — the writer half of eval_report.

yzr-skill-creator“运行与评估测试用例”的机械细节（目录树 / 旧版快照 / 子 agent
prompt 拼装）固化在此；eval-pipeline.md 只留判断性纪律（同轮并行启动、无子 agent
环境的降级路径）。零判断：不读 skill 内容、不做权衡，输出是输入的纯函数。

What it does:

1. Reads ``--evals <skill>/eval/evals.json`` (schema: "evals.json" in
   references/schemas.md) for eval ids + prompts.
2. Creates ``<workspace>/iteration-<N>/eval-<id>/{with_skill,<baseline>}/outputs/``
   for every eval — exactly the layout ``scripts/eval_report.py`` reads back
   (``eval-*`` dirs, one ``grading.json`` per side at ``eval-<id>/<side>/``);
   the two scripts form a round-trip pair pinned by
   ``tests/smoke_test_eval_init.py``.
3. ``--baseline old_skill`` snapshots the skill at init time
   (``iteration-<N>/skill-snapshot/``, ``cp -r``) — the snapshot is whatever
   the skill tree looks like when init runs, so run init BEFORE applying this
   round's edits (eval-pipeline.md“第 0 步”): snapshot-after-edit would
   baseline the new version against itself. Per-iteration (not per-workspace)
   so each iteration naturally compares against the previous round's result.
   ``without_skill`` needs no snapshot.
4. Prints, per eval, the ready-to-spawn with-skill prompt plus the baseline
   variant's differences — the prompt template SSOT lives here, not in prose.

Refuses to clobber an existing non-empty iteration dir (exit 2) — re-running
an iteration means a fresh number.

Usage:
    python3 -m scripts.eval_init --workspace <skill-name>-workspace \
        --iteration 1 --skill-path <skill-dir> \
        [--evals <skill-dir>/eval/evals.json] --baseline without_skill
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Bootstrap sys.path so `from scripts.X import Y` works under both
# `python3 scripts/eval_init.py` (standalone) and
# `python3 -m scripts.eval_init` (from yzr-skill-creator/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SNAPSHOT_DIRNAME = "skill-snapshot"
SIDES = ("with_skill", "without_skill", "old_skill")


def _fail(message: str) -> int:
    print(f"eval_init: {message}", file=sys.stderr)
    return 2


def load_evals(evals_path: Path) -> Optional[List[Dict]]:
    """Read evals.json and enforce the minimum contract init depends on.

    Prints the error and returns None on any violation (main returns 2);
    never raises, so callers can treat this as a plain value.
    """
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
    """Create the iteration tree (+snapshot). Returns prompts, or None (error, printed)."""
    iteration_dir = workspace / f"iteration-{iteration}"
    if iteration_dir.exists() and any(iteration_dir.iterdir()):
        _fail(f"{iteration_dir} already exists and is not empty — use a fresh iteration number")
        return None

    snapshot_dir = iteration_dir / SNAPSHOT_DIRNAME if baseline == "old_skill" else None
    if snapshot_dir is not None:
        shutil.copytree(str(skill_path), str(snapshot_dir))

    prompts: List[str] = []
    for item in evals:
        eval_dir = iteration_dir / f"eval-{item['id']}"
        for side in ("with_skill", baseline):
            (eval_dir / side / "outputs").mkdir(parents=True, exist_ok=True)
        lines = [
            f"=== eval-{item['id']}：同一轮并行启动两个子 agent（不要串行）===",
            "[with_skill]",
            skill_prompt(skill_path, item, eval_dir / "with_skill" / "outputs"),
        ]
        if snapshot_dir is not None:
            lines += [
                "[old_skill]（指向快照，不指当前版）",
                skill_prompt(snapshot_dir, item, eval_dir / "old_skill" / "outputs"),
            ]
        else:
            lines += [
                "[without_skill]",
                f"同 [with_skill]，但删去 Skill path 一行；Save outputs to: {eval_dir / 'without_skill' / 'outputs'}",
            ]
        prompts.append("\n".join(lines) + "\n")
    return prompts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--workspace", required=True, help="Workspace root, e.g. <skill-name>-workspace/")
    parser.add_argument("--iteration", required=True, type=int, help="Iteration number (>= 1)")
    parser.add_argument("--skill-path", required=True, help="Skill directory")
    parser.add_argument("--evals", default=None, help="Path to evals.json (default: <skill-path>/eval/evals.json)")
    parser.add_argument(
        "--baseline",
        required=True,
        choices=("without_skill", "old_skill"),
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
    if args.baseline == "old_skill":
        print(f"snapshot: {Path(args.workspace).resolve() / f'iteration-{args.iteration}' / SNAPSHOT_DIRNAME}")
    for prompt in prompts:
        print()
        print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())

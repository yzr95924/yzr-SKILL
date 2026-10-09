"""Fixture smoke test for eval_prep (sandbox + prompt assembly only; zero stubs).

Run: python3 tests/smoke_test_eval_prep.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import json
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import expect, make_tmp_dir, run_cases, run_cli  # noqa: E402

from tools import eval_prep  # noqa: E402


def make_repo(tmp: Path, sides=("with_skill", "without_skill"), ids=(1,)) -> Path:
    """最小可跑的仓副本：一个 skill + evals.json + iteration-1 骨架。"""
    root = tmp / "repo"
    skill = root / "s1"
    (skill / "eval").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: s1\ndescription: |\n  LIVE-VERSION\n---\n# s1\n", encoding="utf-8")
    evals = [{"id": i, "prompt": f"做 X{i}", "expectations": [f"断言 X{i}"], "files": []} for i in ids]
    (skill / "eval" / "evals.json").write_text(json.dumps({"skill_name": "s1", "evals": evals}), encoding="utf-8")
    iteration = root / "s1-workspace" / "iteration-1"
    for i in ids:
        for side in sides:
            (iteration / f"eval-{i}" / side / "outputs").mkdir(parents=True)
    return root


def prep(argv: List[str]) -> Tuple[int, str]:
    """跑 eval_prep.main，返回 (退出码, stdout)。"""
    return run_cli(eval_prep.main, argv)


def pending(stdout: str) -> List[str]:
    """从 stdout 抽出 PENDING 行。"""
    return [line for line in stdout.splitlines() if line.startswith("PENDING ")]


def case_happy_sandbox_and_prompts() -> None:
    tmp = make_tmp_dir("evalprep-smoke-")
    root = make_repo(tmp)
    iteration = root / "s1-workspace" / "iteration-1"
    rc, stdout = prep(["--iteration", str(iteration), "--skill-path", str(root / "s1")])
    expect(rc == 0, rc)
    lines = pending(stdout)
    expect(len(lines) == 2, stdout)
    expect(any("eval-1/with_skill" in line for line in lines), stdout)
    expect(any("eval-1/without_skill" in line for line in lines), stdout)
    with_side = iteration / "eval-1" / "with_skill"
    out_side = iteration / "eval-1" / "without_skill"
    with_prompt = (with_side / eval_prep.PROMPT_NAME).read_text()
    out_prompt = (out_side / eval_prep.PROMPT_NAME).read_text()
    expect("You MUST follow" in with_prompt and "Skill path:" in with_prompt, with_prompt[:200])
    expect(str(with_side / eval_prep.SANDBOX_DIRNAME / "repo" / "s1") in with_prompt, "with_skill prompt 未指向沙箱")
    expect("Capability test" in out_prompt and "Skill path:" not in out_prompt, out_prompt[:200])
    expect("headless" in with_prompt and "headless" in out_prompt, "headless 声明缺失")
    sandbox_skill = with_side / eval_prep.SANDBOX_DIRNAME / "repo" / "s1" / "SKILL.md"
    expect(sandbox_skill.is_file(), "沙箱未拷贝仓")
    expect(not (with_side / eval_prep.SANDBOX_DIRNAME / "repo" / ".git").exists(), "沙箱不应含 .git")
    expect(not (with_side / eval_prep.TRANSCRIPT_NAME).exists(), "transcript 应由编排 agent 落盘，不该是 prep 写的")


def case_skip_existing_transcript_and_force() -> None:
    tmp = make_tmp_dir("evalprep-smoke-")
    root = make_repo(tmp)
    iteration = root / "s1-workspace" / "iteration-1"
    argv = ["--iteration", str(iteration), "--skill-path", str(root / "s1")]
    rc1, out1 = prep(argv)
    expect(len(pending(out1)) == 2, out1)
    # 模拟编排 agent 跑完两侧并落 transcript：再 prep 应无待跑
    for side in ("with_skill", "without_skill"):
        (iteration / "eval-1" / side / eval_prep.TRANSCRIPT_NAME).write_text("done", encoding="utf-8")
    rc2, out2 = prep(argv)
    expect(len(pending(out2)) == 0 and "nothing to prep" in out2, out2)
    rc3, out3 = prep(argv + ["--force"])
    expect(len(pending(out3)) == 2, "--force 未重跑")


def case_old_skill_side_gets_snapshot_overlay() -> None:
    tmp = make_tmp_dir("evalprep-smoke-")
    root = make_repo(tmp, sides=("with_skill", "old_skill"))
    iteration = root / "s1-workspace" / "iteration-1"
    snapshot = iteration / "skill-snapshot"
    snapshot.mkdir()
    (snapshot / "SKILL.md").write_text(
        "---\nname: s1\ndescription: |\n  SNAPSHOT-VERSION\n---\n# s1\n", encoding="utf-8"
    )
    rc, stdout = prep(["--iteration", str(iteration), "--skill-path", str(root / "s1")])
    expect(rc == 0, rc)
    old_side = iteration / "eval-1" / "old_skill"
    live_side = iteration / "eval-1" / "with_skill"

    def sandbox_skill(side: Path) -> Path:
        """定位某侧沙箱内的 SKILL.md。"""
        return side / eval_prep.SANDBOX_DIRNAME / "repo" / "s1" / "SKILL.md"

    expect("SNAPSHOT-VERSION" in sandbox_skill(old_side).read_text(), "old_skill 沙箱未覆盖为快照")
    expect("SNAPSHOT-VERSION" not in sandbox_skill(live_side).read_text(), "with_skill 沙箱被快照污染")
    old_prompt = (old_side / eval_prep.PROMPT_NAME).read_text()
    expect("You MUST follow" in old_prompt, old_prompt[:200])
    expect(str(old_side / eval_prep.SANDBOX_DIRNAME / "repo" / "s1") in old_prompt, "prompt 未指向沙箱内快照")


def case_old_skill_missing_snapshot_refused() -> None:
    tmp = make_tmp_dir("evalprep-smoke-")
    root = make_repo(tmp, sides=("with_skill", "old_skill"))
    iteration = root / "s1-workspace" / "iteration-1"
    rc, stdout = prep(["--iteration", str(iteration), "--skill-path", str(root / "s1")])
    expect(rc == 2, rc)
    expect(pending(stdout) == [], stdout)
    expect(not (iteration / "eval-1" / "with_skill" / eval_prep.PROMPT_NAME).exists(), "校验失败前已建 prompt")


def case_invalid_paths_exit_2() -> None:
    tmp = make_tmp_dir("evalprep-smoke-")
    rc, _ = prep(["--iteration", str(tmp / "nope"), "--skill-path", str(tmp / "nope")])
    expect(rc == 2, rc)


def case_eval_filter() -> None:
    tmp = make_tmp_dir("evalprep-smoke-")
    root = make_repo(tmp, ids=(1, 2))
    iteration = root / "s1-workspace" / "iteration-1"
    rc, stdout = prep(["--iteration", str(iteration), "--skill-path", str(root / "s1"), "--eval", "1"])
    expect(rc == 0, rc)
    lines = pending(stdout)
    expect(len(lines) == 2, stdout)
    expect(all("eval-1/" in line for line in lines), stdout)


if __name__ == "__main__":
    sys.exit(run_cases())

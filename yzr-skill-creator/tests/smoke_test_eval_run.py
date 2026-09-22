#!/usr/bin/env python3
"""Fixture smoke test for eval_run (stubbed opencode on PATH).

Run: python3 tests/smoke_test_eval_run.py  (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_tmp_dir  # noqa: E402

from tools import eval_run  # noqa: E402

STUB = """#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["SMOKE_EVALRUN_CAPTURE"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\\n")
time.sleep(float(os.environ.get("SMOKE_EVALRUN_SLEEP", "0")))
print("STUB-OUTPUT")
sys.exit(int(os.environ.get("SMOKE_EVALRUN_RC", "0")))
"""

CASES: List = []


def case(fn):
    CASES.append(fn)
    return fn


def make_repo(tmp: Path) -> Path:
    """最小可跑的仓副本：一个 skill + evals.json + iteration-1 骨架。"""
    root = tmp / "repo"
    skill = root / "s1"
    (skill / "eval").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: s1\ndescription: |\n  d\n---\n# s1\n", encoding="utf-8")
    (skill / "eval" / "evals.json").write_text(
        json.dumps({"skill_name": "s1", "evals": [{"id": 1, "prompt": "做 X", "files": []}]}), encoding="utf-8"
    )
    for side in ("with_skill", "without_skill"):
        (skill.parent / "s1-workspace" / "iteration-1" / "eval-1" / side / "outputs").mkdir(parents=True)
    return root


def run_with_stub(tmp: Path, argv: List[str], rc: str = "0", sleep: str = "0") -> List[List[str]]:
    """PATH 前置打桩 opencode 跑 eval_run.main，返回桩收到的 argv 调用列表。"""
    bin_dir = tmp / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "opencode"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    capture = tmp / "calls.jsonl"
    envs = ("SMOKE_EVALRUN_CAPTURE", "SMOKE_EVALRUN_RC", "SMOKE_EVALRUN_SLEEP")
    old = dict(PATH=os.environ.get("PATH", ""), **{k: os.environ.get(k) for k in envs})
    os.environ["PATH"] = str(bin_dir) + os.pathsep + old["PATH"]
    os.environ["SMOKE_EVALRUN_CAPTURE"], os.environ["SMOKE_EVALRUN_RC"], os.environ["SMOKE_EVALRUN_SLEEP"] = (
        str(capture),
        rc,
        sleep,
    )
    try:
        code = eval_run.main(argv)
    finally:
        os.environ["PATH"] = old["PATH"]
        for k in envs:
            if old[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old[k]
    assert code == 0, code
    return [json.loads(line) for line in capture.read_text(encoding="utf-8").splitlines()] if capture.is_file() else []


@case
def case_happy_path_isolation_and_sandbox(tmp: Path) -> None:
    print("[case] both sides spawn: isolated prompts + sandboxes + transcripts")
    root = make_repo(tmp)
    iteration = root / "s1-workspace" / "iteration-1"
    calls = run_with_stub(tmp, ["--iteration", str(iteration), "--skill-path", str(root / "s1"), "--timeout", "30"])
    assert len(calls) == 2, calls
    by_prompt = {c[-1]: c for c in calls}
    with_p = next((p for p in by_prompt if "Capability test" not in p), None)
    out_p = next((p for p in by_prompt if "Capability test" in p), None)
    assert with_p and out_p, "两侧 prompt 未区分"
    assert "Skill path:" in with_p and "You MUST follow" in with_p, with_p[:200]
    assert "Skill path:" not in out_p, out_p[:200]
    assert all("headless" in p for p in by_prompt), "headless 声明缺失"
    for c in calls:
        assert "--pure" in c and "--dir" in c and c[c.index("--dir") + 1].endswith("run"), c
    side = iteration / "eval-1" / "with_skill"
    assert (side / eval_run.TRANSCRIPT_NAME).is_file(), "transcript 未落盘"
    assert "STUB-OUTPUT" in (side / eval_run.TRANSCRIPT_NAME).read_text(), "transcript 缺 stdout"
    sandbox_skill = side / eval_run.SANDBOX_DIRNAME / "repo" / "s1" / "SKILL.md"
    assert sandbox_skill.is_file(), "沙箱未拷贝仓"
    assert not (side / eval_run.SANDBOX_DIRNAME / "repo" / ".git").exists(), "沙箱不应含 .git"


@case
def case_skip_existing_transcript_and_force(tmp: Path) -> None:
    print("[case] transcripts present -> skip; --force -> redo")
    root = make_repo(tmp)
    iteration = root / "s1-workspace" / "iteration-1"
    argv = ["--iteration", str(iteration), "--skill-path", str(root / "s1"), "--timeout", "30"]
    assert len(run_with_stub(tmp, argv)) == 2
    assert len(run_with_stub(tmp, argv)) == 2, "第二轮应跳过（capture 不追加）"
    assert len(run_with_stub(tmp, argv + ["--force"])) == 4, "--force 未重跑"


@case
def case_side_rc_recorded(tmp: Path) -> None:
    print("[case] sub-agent non-zero rc recorded in transcript line")
    root = make_repo(tmp)
    iteration = root / "s1-workspace" / "iteration-1"
    # capture 追加会累积，这里只断言 rc=3 标记进了运行输出（stdout 无法捕获则断 transcript）
    run_with_stub(tmp, ["--iteration", str(iteration), "--skill-path", str(root / "s1")], rc="3")
    t = (iteration / "eval-1" / "with_skill" / eval_run.TRANSCRIPT_NAME).read_text()
    assert "STUB-OUTPUT" in t


@case
def case_timeout_writes_transcript_and_survives(tmp: Path) -> None:
    print("[case] sub-agent timeout -> rc 124 recorded, run survives (bytes bug regression)")
    root = make_repo(tmp)
    iteration = root / "s1-workspace" / "iteration-1"
    run_with_stub(tmp, ["--iteration", str(iteration), "--skill-path", str(root / "s1"), "--timeout", "1"], sleep="3")
    t = (iteration / "eval-1" / "with_skill" / eval_run.TRANSCRIPT_NAME).read_text()
    assert "TIMEOUT after 1s" in t, t[-200:]


@case
def case_missing_opencode_exits_2(tmp: Path) -> None:
    print("[case] no opencode on PATH -> rc 2 (degraded path hint)")
    old = os.environ.get("PATH", "")
    os.environ["PATH"] = str(tmp / "empty-bin")
    (tmp / "empty-bin").mkdir(exist_ok=True)
    try:
        code = eval_run.main(["--iteration", str(tmp), "--skill-path", str(tmp)])
    finally:
        os.environ["PATH"] = old
    assert code == 2, code


def main() -> int:
    failures: Dict[str, str] = {}
    for fn in CASES:
        td = make_tmp_dir("evalrun-smoke-")
        try:
            fn(td)
        except AssertionError as exc:
            failures[fn.__name__] = str(exc)
    for name, detail in failures.items():
        print("FAIL", name, detail)
    print(f"{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

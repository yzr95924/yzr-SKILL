#!/usr/bin/env python3
"""Four-quadrant + best-selection smoke test for the description-eval scoring.

Catches the class of bug that static checks and the canary can't: pass-judgment
logic (`== should_trigger`), best-selection tie-break, and the `opencode run`
invocation contract. A stubbed `opencode` binary serves controlled judge
responses and a synthetic skills pool stands in for the host's skills dir
(absent on CI runners), so the run is deterministic and needs no model calls.
Exit 0 = all green, 1 = regression.

Run: python3 tests/smoke_test_scoring.py  (from yzr-skill-creator/)
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import make_tmp_dir  # noqa: E402

from tools import optimize_description

TARGET = "smoke-target-skill"

STUB_SRC = """#!/usr/bin/env python3
import json, os, sys
cfg = json.load(open(os.environ["SMOKE_JUDGE_CONFIG"]))
capture = os.environ.get("SMOKE_STUB_CAPTURE")
if capture:
    # per-pid：判官调用并发起多个桩进程，同一文件会被竞争写坏
    json.dump(
        {"argv": sys.argv[1:], "cwd": os.getcwd()},
        open(f"{capture}.{os.getpid()}", "w"),
    )
prompt = " ".join(sys.argv[1:])
for rule in cfg["rules"]:
    if rule["marker"] in prompt:
        print(json.dumps({"skill": rule["choice"]}), flush=True)
        sys.exit(0)
print(json.dumps({"skill": None}), flush=True)
"""

# Four quadrants: should-trigger hit / miss x should-not-trigger hit / miss.
# runs_per_query=1 + threshold=0.5 makes each quadrant a single deterministic call.
QUERIES = [
    {"query": "smoke-trigger-pos 帮我做个 skill", "should_trigger": True},
    {"query": "smoke-trigger-neg 帮我做个 skill", "should_trigger": True},
    {"query": "smoke-no-trigger-pos 写个脚本", "should_trigger": False},
    {"query": "smoke-no-trigger-neg 写个脚本", "should_trigger": False},
]
RULES = [
    {"marker": "smoke-trigger-pos", "choice": TARGET},
    {"marker": "smoke-trigger-neg", "choice": None},
    {"marker": "smoke-no-trigger-pos", "choice": None},
    {"marker": "smoke-no-trigger-neg", "choice": TARGET},
]

EXPECTED = {
    "smoke-trigger-pos": True,
    "smoke-trigger-neg": False,
    "smoke-no-trigger-pos": True,
    "smoke-no-trigger-neg": False,
}


def run_smoke_eval() -> Tuple[dict, dict]:
    """Run the four-quadrant eval with the stubbed judge and a synthetic
    skills pool.

    The pool (decoys + target) stands in for the host's real skills dir
    (absent on CI runners) and is passed explicitly as skills_dir — it also
    makes the judge pick the target out of a list, which is what the real
    routing layer does. Returns (eval result, captured opencode invocation).
    """
    td_path = make_tmp_dir(prefix="skill-smoke-")
    stub = td_path / "opencode"
    stub.write_text(STUB_SRC)
    stub.chmod(0o755)
    config = td_path / "judge-config.json"
    config.write_text(json.dumps({"rules": RULES}))
    capture_path = td_path / "capture.json"
    skills_dir = td_path / "skills"
    for name in (TARGET, "smoke-decoy-a", "smoke-decoy-b"):
        entry = skills_dir / name
        entry.mkdir(parents=True)
        (entry / "SKILL.md").write_text(f"---\nname: {name}\ndescription: |\n  {name} 的描述。\n---\n# {name}\n")

    old_path = os.environ.get("PATH", "")
    old_config = os.environ.get("SMOKE_JUDGE_CONFIG")
    old_capture = os.environ.get("SMOKE_STUB_CAPTURE")
    os.environ["PATH"] = str(td_path) + os.pathsep + old_path
    os.environ["SMOKE_JUDGE_CONFIG"] = str(config)
    os.environ["SMOKE_STUB_CAPTURE"] = str(capture_path)
    try:
        result = optimize_description.run_eval(
            eval_set=QUERIES,
            skill_name=TARGET,
            description="smoke description",
            config=optimize_description.EvalConfig(timeout=60, runs_per_query=1, trigger_threshold=0.5),
            skills_dir=skills_dir,
        )
    finally:
        os.environ["PATH"] = old_path
        for key, old in (("SMOKE_JUDGE_CONFIG", old_config), ("SMOKE_STUB_CAPTURE", old_capture)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
    capture_files = sorted(td_path.glob(capture_path.name + ".*"))
    captures = [json.loads(p.read_text()) for p in capture_files]
    # 过滤到判官调用（--agent 在场）：flag 能力探测等辅助子进程也会留捕获文件，pid 序不可靠
    captured = next((c for c in captures if "--agent" in c.get("argv", [])), captures[0] if captures else {})
    return result, captured


def check_contract(captured: dict) -> List[str]:
    """Pin the opencode invocation contract: prompt via argv, text-only judge agent."""
    issues = []
    argv = captured.get("argv", [])
    if "--agent" not in argv or argv[argv.index("--agent") + 1] != optimize_description._OPENCODE_AGENT:
        issues.append("contract: --agent <judge> missing from opencode argv")
    if not argv or not any(marker in argv[-1] for marker in EXPECTED):
        issues.append("contract: prompt not delivered as the last argv element")
    agent_md = Path(captured.get("cwd", "")) / ".opencode" / "agent" / f"{optimize_description._OPENCODE_AGENT}.md"
    if not agent_md.is_file():
        issues.append(f"contract: judge agent md missing in invocation cwd ({agent_md})")
    elif '"*": deny' not in agent_md.read_text(encoding="utf-8"):
        issues.append("contract: judge agent permission is not deny-all")
    return issues


def run_best_selection() -> dict:
    """Pin the real selection function (not a re-typed copy of its lambda —
    a copy stays green when the tie-break is changed in the source)."""
    history = [
        {"iteration": 1, "test_passed": 8, "test_total": 8, "train_passed": 11, "train_total": 12},
        {"iteration": 2, "test_passed": 8, "test_total": 8, "train_passed": 12, "train_total": 12},
    ]
    best = optimize_description.select_best_iteration(history, has_test_set=True)
    train_only = optimize_description.select_best_iteration(
        [
            {"iteration": 1, "test_passed": None, "train_passed": 3, "train_total": 4},
            {"iteration": 2, "test_passed": None, "train_passed": 5, "train_total": 6},
        ],
        has_test_set=False,
    )
    return {
        "chosen_iteration": best["iteration"],
        "expected_iteration": 2,  # test tie 8=8 → train 12 > 11 breaks it
        "train_only_iteration": train_only["iteration"],
        "expected_train_only": 2,
    }


def main() -> int:
    failures = []

    result, captured = run_smoke_eval()
    for r in result["results"]:
        key = next(marker for marker in EXPECTED if marker in r["query"])
        if r["pass"] != EXPECTED[key]:
            failures.append(f"{key}: pass={r['pass']}, expected={EXPECTED[key]}")
    failures.extend(check_contract(captured))

    selection = run_best_selection()
    if selection["chosen_iteration"] != selection["expected_iteration"]:
        failures.append(
            f"best-selection: chose iteration {selection['chosen_iteration']}, "
            f"expected {selection['expected_iteration']}"
        )
    if selection["train_only_iteration"] != selection["expected_train_only"]:
        failures.append(
            f"best-selection (no holdout): chose iteration {selection['train_only_iteration']}, "
            f"expected {selection['expected_train_only']}"
        )

    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print("SMOKE OK: 4/4 quadrants + best-selection + opencode contract (real function, both modes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

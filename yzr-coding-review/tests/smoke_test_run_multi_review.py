#!/usr/bin/env python3
"""Stub smoke test for run_multi_review.

Pins the spawn contract static checks can't see: the roster gate stops with
near-miss candidates instead of silently swapping models, one `opencode run`
vote per model with --agent + -m + --file (packet inlined into the prompt when
the probed help lacks --file), a failed vote retried exactly once, format
warnings that keep the vote, and exit codes separating all-ok from partial
failure. The stubbed `opencode` on PATH answers `models`, `run --help` and
per-model `run` outcomes from env, so the run is deterministic and needs no
real model calls.

Run: python3 tests/smoke_test_run_multi_review.py  (from yzr-coding-review/)
Exit 0 = all green, 1 = regression.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "tools"))

import run_multi_review  # noqa: E402

ROSTER = run_multi_review.DEFAULT_ROSTER

STUB_SRC = r"""#!/usr/bin/env python3
import json, os, re, sys

argv = sys.argv[1:]
capture = os.environ["SMOKE_OC_CAPTURE"]
json.dump({"argv": argv}, open(f"{capture}.{os.getpid()}", "w"))

if argv[:1] == ["models"]:
    if os.environ.get("SMOKE_OC_MODELS_FAIL"):
        sys.exit(4)
    sys.stdout.write(os.environ.get("SMOKE_OC_MODELS", "") + "\n")
    sys.exit(0)
if argv[:2] == ["run", "--help"]:
    print(os.environ.get("SMOKE_OC_HELP", "--file, -f string\n--agent string\n--model, -m string\n--title string"))
    sys.exit(0)
if argv[:1] == ["run"]:
    model = argv[argv.index("-m") + 1]
    behavior = json.loads(os.environ.get("SMOKE_OC_VOTES", "{}")).get(model, "ok")
    if behavior == "fail":
        sys.exit(3)
    if behavior == "failfirst":
        state = os.path.join(os.path.dirname(capture), "state-" + re.sub(r"\W", "_", model))
        if not os.path.exists(state):
            open(state, "w").close()
            sys.exit(3)
    if behavior == "nofindings":
        print("整体读下来还行，没有发现。")
        sys.exit(0)
    print("复述：读取订单行，校验后累计金额。\n"
          "- parser.py:1 | 函数粒度 | process() 内嵌 3 个语义段 | 抽具名函数\n"
          "- ghost.py:9 | 魔法值 | 引用了卷宗外文件 | 夹具")
    sys.exit(0)
sys.exit(9)
"""


def run_cli(
    tmp: Path, args: List[str], models_text: str, votes: Dict[str, str], help_text: str = ""
) -> Tuple[subprocess.CompletedProcess, List[List[str]]]:
    """在 PATH 头部挂 opencode 桩跑一次 CLI，返回 (进程, 逐票 spawn 的 argv 列表)。"""
    stub = tmp / "opencode"
    stub.write_text(STUB_SRC, encoding="utf-8")
    stub.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{tmp}{os.pathsep}{env.get('PATH', '')}"
    env["SMOKE_OC_CAPTURE"] = str(tmp / "capture.json")
    env["SMOKE_OC_MODELS"] = models_text
    env["SMOKE_OC_VOTES"] = json.dumps(votes)
    if help_text:
        env["SMOKE_OC_HELP"] = help_text
    proc = subprocess.run(
        [sys.executable, str(SKILL_ROOT / "tools" / "run_multi_review.py"), *args],
        capture_output=True,
        text=True,
        env=env,
        universal_newlines=True,
        cwd=str(SKILL_ROOT),
    )
    calls = [json.loads(p.read_text())["argv"] for p in tmp.glob("capture.json.*") if p.suffix != ""]
    spawns = [c for c in calls if c[:1] == ["run"] and "--agent" in c]
    return proc, spawns


def make_code(tmp: Path) -> Path:
    code = tmp / "parser.py"
    code.write_text("def process(order):\n    return order.total * 1.06\n", encoding="utf-8")
    return code


CASES = []


def expect(cond, msg="") -> None:
    if not cond:
        raise AssertionError(msg)


def case(fn):
    CASES.append(fn)
    return fn


@case
def dry_run_announces_roster_without_spawn():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proc, spawns = run_cli(tmp, ["--dry-run"], "\n".join(ROSTER), {})
        expect(proc.returncode == 0, proc.stderr)
        expect("roster:" in proc.stdout, proc.stdout)
        for model in ROSTER:
            expect(model in proc.stdout, model)
        expect("未建卷宗未 spawn" in proc.stdout, proc.stdout)
        expect(not spawns, spawns)


@case
def dead_model_stops_with_candidates():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        available = "\n".join(ROSTER[:-1] + ["opencode-go/qwen3.8-pro"])
        proc, spawns = run_cli(tmp, ["--dry-run", "--models", f"{ROSTER[0]},{ROSTER[-1]}"], available, {})
        expect(proc.returncode == 2, proc)
        expect("不可发现" in proc.stderr, proc.stderr)
        expect(ROSTER[-1] in proc.stderr, proc.stderr)
        expect("qwen3.8-pro" in proc.stderr, proc.stderr)
        expect(not spawns, spawns)


@case
def models_probe_failure_stops():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        stub = tmp / "opencode"
        stub.write_text(STUB_SRC, encoding="utf-8")
        stub.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{tmp}{os.pathsep}{env.get('PATH', '')}"
        env["SMOKE_OC_CAPTURE"] = str(tmp / "capture.json")
        env["SMOKE_OC_MODELS_FAIL"] = "1"
        proc = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "tools" / "run_multi_review.py"), "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
            universal_newlines=True,
            cwd=str(SKILL_ROOT),
        )
        expect(proc.returncode == 2, proc)
        expect("校验通道不可用" in proc.stderr, proc.stderr)


@case
def run_spawns_one_vote_per_model_with_packet():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        code = make_code(tmp)
        proc, spawns = run_cli(tmp, ["--target", str(code), "--out", str(tmp / "packet")], "\n".join(ROSTER), {})
        expect(proc.returncode == 0, proc.stderr)
        expect(len(spawns) == len(ROSTER), spawns)
        packet_path = str(tmp / "packet" / "PACKET.md")
        for model in ROSTER:
            vote = next(c for c in spawns if model in c)
            expect("--file" in vote and packet_path in vote, vote)
        reviews = list((tmp / "packet" / "reviews").glob("*.md"))
        expect(len(reviews) == len(ROSTER), reviews)
        expect(proc.stdout.count("ok ->") == len(ROSTER), proc.stdout)
        expect("WARN" in proc.stdout and "ghost.py" in proc.stdout, proc.stdout)
        expect("无契约格式发现行" not in proc.stdout, proc.stdout)


@case
def failed_vote_retried_once():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        code = make_code(tmp)
        votes = {ROSTER[0]: "failfirst"}
        proc, spawns = run_cli(tmp, ["--target", str(code), "--out", str(tmp / "packet")], "\n".join(ROSTER), votes)
        expect(proc.returncode == 0, proc.stderr)
        expect(len(spawns) == len(ROSTER) + 1, spawns)
        first = [c for c in spawns if ROSTER[0] in c]
        expect(len(first) == 2, first)


@case
def persistent_failure_exits_1_and_keeps_other_votes():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        code = make_code(tmp)
        votes = {ROSTER[1]: "fail"}
        proc, spawns = run_cli(tmp, ["--target", str(code), "--out", str(tmp / "packet")], "\n".join(ROSTER), votes)
        expect(proc.returncode == 1, proc)
        expect("FAILED after retry" in proc.stdout, proc.stdout)
        expect(ROSTER[1] in proc.stdout, proc.stdout)
        expect(len(spawns) == len(ROSTER) + 1, spawns)
        reviews = list((tmp / "packet" / "reviews").glob("*.md"))
        expect(len(reviews) == len(ROSTER) - 1, reviews)


@case
def format_warning_keeps_vote_without_retry():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        code = make_code(tmp)
        votes = {ROSTER[2]: "nofindings"}
        proc, spawns = run_cli(tmp, ["--target", str(code), "--out", str(tmp / "packet")], "\n".join(ROSTER), votes)
        expect(proc.returncode == 0, proc.stderr)
        expect("无契约格式发现行" in proc.stdout, proc.stdout)
        expect(len(spawns) == len(ROSTER), spawns)


@case
def inline_packet_when_file_flag_unsupported():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        code = make_code(tmp)
        proc, spawns = run_cli(
            tmp,
            ["--target", str(code), "--out", str(tmp / "packet")],
            "\n".join(ROSTER),
            {},
            help_text="--agent string\n--model, -m string\n--title string",
        )
        expect(proc.returncode == 0, proc.stderr)
        expect(len(spawns) == len(ROSTER), spawns)
        for vote in spawns:
            expect("--file" not in vote, vote)
            expect(any("以下为卷宗全文" in arg for arg in vote), vote[-1][:120])
        expect("契约附章" in spawns[0][-1], "packet must ride inside the prompt")


def main() -> int:
    failures = []
    for fn in CASES:
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{fn.__name__}: {exc}")
    for name in failures:
        print("FAIL", name)
    print(f"{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

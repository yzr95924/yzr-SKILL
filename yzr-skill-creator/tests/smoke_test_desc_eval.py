#!/usr/bin/env python3
"""Four-quadrant + canary smoke test for desc_eval prep/score (zero stubs, no model calls).

Judge responses are synthesized as results/run-<k>.json — the same file contract
the judge sub-agents write in production. Pins: pass-judgment logic, threshold,
canary channel check, manifest query/canary contract, and the anti-contamination clause in
the judge prompt. Run: python3 tests/smoke_test_desc_eval.py (from yzr-skill-creator/)
Exit 0 = all green, 1 = regression.
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import expect, make_tmp_dir  # noqa: E402

from tools import desc_eval  # noqa: E402

TARGET = "smoke-target-skill"

# 四象限：应触发×命中 / 应触发×漏 / 不应触发×正确 / 不应触发×误中
QUERIES = [
    {"query": "smoke-trigger-pos 帮我做个 skill", "should_trigger": True},
    {"query": "smoke-trigger-neg 帮我做个 skill", "should_trigger": True},
    {"query": "smoke-no-trigger-pos 写个脚本", "should_trigger": False},
    {"query": "smoke-no-trigger-neg 写个脚本", "should_trigger": False},
]
CHOICES = {
    "smoke-trigger-pos 帮我做个 skill": TARGET,
    "smoke-trigger-neg 帮我做个 skill": None,
    "smoke-no-trigger-pos 写个脚本": None,
    "smoke-no-trigger-neg 写个脚本": TARGET,
}
EXPECTED_PASS = {
    "smoke-trigger-pos 帮我做个 skill": True,
    "smoke-trigger-neg 帮我做个 skill": False,
    "smoke-no-trigger-pos 写个脚本": True,
    "smoke-no-trigger-neg 写个脚本": False,
}


def run_cli(argv: List[str]) -> Tuple[int, str]:
    """跑 desc_eval.main，返回 (退出码, stdout)。"""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = desc_eval.main(argv)
    return rc, out.getvalue()


def make_fixture(tmp: Path) -> Tuple[Path, Path, Path]:
    """合成竞争池（target + decoys）与评估集；目标 skill 即池中的那份。"""
    pool = tmp / "skills"
    for name in (TARGET, "smoke-decoy-a", "smoke-decoy-b"):
        entry = pool / name
        entry.mkdir(parents=True)
        (entry / "SKILL.md").write_text(f"---\nname: {name}\ndescription: |\n  {name} 的描述。\n---\n# {name}\n")
    eval_set = tmp / "eval_set.json"
    eval_set.write_text(json.dumps(QUERIES, ensure_ascii=False), encoding="utf-8")
    return pool / TARGET, eval_set, pool


def do_prep(tmp: Path, skill: Path, eval_set: Path, pool: Path, name: str, extra: List[str]) -> Path:
    """prep 到一个带名字的 out-dir，返回其路径。"""
    out_dir = tmp / f"out-{name}"
    argv = [
        "prep",
        "--skill-path",
        str(skill),
        "--eval-set",
        str(eval_set),
        "--out-dir",
        str(out_dir),
        "--runs",
        "1",
        "--skills-dir",
        str(pool),
    ] + extra
    rc, stdout = run_cli(argv)
    expect(rc == 0, f"prep failed rc={rc}: {stdout}")
    return out_dir


def write_results(out_dir: Path, id_choice: List[Tuple[int, Optional[str]]], run: int = 1) -> None:
    """把 (query_id, skill) 列表写成 run-<k>.json。"""
    payload = [{"query_id": qid, "skill": choice} for qid, choice in id_choice]
    (out_dir / "results" / f"run-{run}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def check_prep_contract(out_dir: Path, manifest: dict, failures: List[str]) -> None:
    """断言 1：manifest 查询/金丝雀契约 + prompt 防污染条款 + 候选描述注入。"""
    try:
        expect(manifest["skill"] == TARGET, manifest["skill"])
        expect(len(manifest["queries"]) == 4, manifest["queries"])
        expect(len(manifest["canary"]) == 2, manifest["canary"])
        expect(all("role" not in q for q in manifest["queries"]), "holdout 机制已删，manifest 不应再有 role")
        prompt = (out_dir / "prompts" / "run-1.txt").read_text(encoding="utf-8")
        expect("Ignore any skills installed in your own environment" in prompt, "防污染条款缺失")
        expect(desc_eval.CANARY_NAME in prompt and "量子香蕉" in prompt, "金丝雀未混入批次")
        expect("做个 skill。不适用" in prompt, "候选描述未进竞争池")
        for qid in [q["id"] for q in manifest["queries"]] + [c["id"] for c in manifest["canary"]]:
            expect(f"[q{qid}]" in prompt, f"查询 q{qid} 缺失")
        expect("run-1.json" in prompt, "结果落盘路径指令缺失")
    except AssertionError as exc:
        failures.append(f"prep: {exc}")


def check_score(out_dir: Path, manifest: dict, failures: List[str]) -> List[Tuple[int, Optional[str]]]:
    """断言 2：四象限判定 + summary 数字。返回已用 choice（供金丝雀断言复用）。"""
    id_choice: List[Tuple[int, Optional[str]]] = []
    try:
        for q in manifest["queries"]:
            id_choice.append((q["id"], CHOICES[q["query"]]))
        pos_id, neg_id = manifest["canary"][0]["id"], manifest["canary"][1]["id"]
        id_choice += [(pos_id, desc_eval.CANARY_NAME), (neg_id, None)]
        write_results(out_dir, id_choice)
        rc, stdout = run_cli(["score", "--out-dir", str(out_dir)])
        expect(rc == 0, f"score rc={rc}")
        payload = json.loads(stdout)
        per_pass = {r["query_id"]: r["pass"] for r in payload["results"]}
        for q in manifest["queries"]:
            expect(per_pass[q["id"]] == EXPECTED_PASS[q["query"]], f"{q['query']}: {per_pass[q['id']]}")
        expect(payload["summary"]["total"] == 4, payload["summary"])
        expect(payload["summary"]["passed"] == 2, payload["summary"])
    except AssertionError as exc:
        failures.append(f"score: {exc}")
    return id_choice


def check_canary(
    out_dir: Path, manifest: dict, id_choice: List[Tuple[int, Optional[str]]], failures: List[str]
) -> None:
    """断言 3：金丝雀正题未命中假 skill -> 通道错误 rc 3，不出数字。"""
    try:
        pos_id = manifest["canary"][0]["id"]
        broken = [(qid, None if qid == pos_id else choice) for qid, choice in id_choice]
        write_results(out_dir, broken)
        rc, stdout = run_cli(["score", "--out-dir", str(out_dir)])
        expect(rc == 3, f"canary-broken rc={rc}")
        expect("passed" not in stdout, "通道错误不应产出分数")
    except AssertionError as exc:
        failures.append(f"canary: {exc}")


def check_missing_run(out_dir: Path, id_choice: List[Tuple[int, Optional[str]]], failures: List[str]) -> None:
    """断言 4：缺 run 结果文件 -> rc 2（编排者据此补跑该 run）。"""
    try:
        write_results(out_dir, id_choice)
        (out_dir / "results" / "run-1.json").unlink()
        rc, _ = run_cli(["score", "--out-dir", str(out_dir)])
        expect(rc == 2, f"missing-run rc={rc}")
    except AssertionError as exc:
        failures.append(f"missing-run: {exc}")


def check_guards(tmp: Path, skill: Path, eval_set: Path, pool: Path, failures: List[str]) -> None:
    """断言 5：prep 对非空 out-dir 复用拒绝。"""
    argv = [
        "prep",
        "--skill-path",
        str(skill),
        "--eval-set",
        str(eval_set),
        "--out-dir",
        str(tmp / "out-guard"),
        "--skills-dir",
        str(pool),
    ]
    try:
        rc, _ = run_cli(argv)
        expect(rc == 0, f"fresh prep rc={rc}")
        rc, _ = run_cli(argv)
        expect(rc == 2, f"out-dir reuse should be refused rc={rc}")
    except AssertionError as exc:
        failures.append(f"guards: {exc}")


def main() -> int:
    failures: List[str] = []
    tmp = make_tmp_dir("desc-eval-smoke-")
    skill, eval_set, pool = make_fixture(tmp)
    cand_file = tmp / "candidate.txt"
    cand_file.write_text("当用户要做 skill 时使用本 skill。触发：做个 skill。不适用：其它。", encoding="utf-8")
    out_dir = do_prep(tmp, skill, eval_set, pool, "base", ["--description-file", str(cand_file)])
    manifest: Dict = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

    check_prep_contract(out_dir, manifest, failures)
    id_choice = check_score(out_dir, manifest, failures)
    check_canary(out_dir, manifest, id_choice, failures)
    check_missing_run(out_dir, id_choice, failures)
    check_guards(tmp, skill, eval_set, pool, failures)

    if failures:
        print("SMOKE FAIL:", *failures, sep="\n  ")
        return 1
    print("SMOKE OK: prep contract + 4-quadrant score + canary channel + missing-run + outdir guard")
    return 0


if __name__ == "__main__":
    sys.exit(main())

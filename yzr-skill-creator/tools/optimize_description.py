#!/usr/bin/env python3
"""Optimize a skill description via a routing-judge eval + improve loop."""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# 让直跑与 python -m 两种入口都能 import tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils import DESCRIPTION_MAX_CHARS, frontmatter_span, parse_skill_md

DEFAULT_HOLDOUT_RATIO = 0.4

SKILLS_DIR = Path.home() / ".agents" / "skills"

# judge / improve 走无工具判官 agent：OPENCODE_PERMISSION 通配实测拦不住 read，显式 deny 会挂起，
# 故用 OPENCODE_CONFIG_CONTENT 内联一个全 deny 工具权限的 agent（agent 级 permission 优先级最高）。
_OPENCODE_AGENT = "yzr-skill-judge"
_OPENCODE_CONFIG_CONTENT = json.dumps(
    {
        "agent": {
            _OPENCODE_AGENT: {
                "description": "Text-only eval judge",
                "mode": "primary",
                "permission": {"*": "deny"},
            }
        }
    }
)

CANARY_SKILL = {
    "name": "_canary_skill",
    "description": "当用户提到“量子香蕉”时使用本 skill。触发：量子香蕉。不适用：其它一切。",
}
CANARY_QUERIES = [
    {"query": "帮我处理一下量子香蕉的排序问题", "should_trigger": True},
    {"query": "帮我写个 Python 脚本把两个 JSON 合并一下", "should_trigger": False},
]

_JUDGE_PATTERN = re.compile(r'"skill"\s*:\s*(?:"([^"]*)"|null)')


class EvalConfig(NamedTuple):
    """路由评估的配置：超时 / 每查询重复次数 / 触发阈值 / 模型。"""

    timeout: int = 120
    runs_per_query: int = 3
    trigger_threshold: float = 0.5
    model: Optional[str] = None


class LoopConfig(NamedTuple):
    """优化循环的配置：评估配置 + 轮数上限 / holdout / 输出 / 竞争池。"""

    eval: EvalConfig
    max_iterations: int = 5
    holdout: float = DEFAULT_HOLDOUT_RATIO
    verbose: bool = False
    log_dir: Optional[Path] = None
    skills_dir: Optional[Path] = None


class SkillContext(NamedTuple):
    """优化对象：skill 名 / SKILL.md 全文 / 当前 description。"""

    name: str
    content: str
    description: str


class SplitSets(NamedTuple):
    """train / test 切分结果。"""

    train: List[dict]
    test: List[dict]


def _call_opencode(prompt: str, model: Optional[str], timeout: int = 300) -> str:
    """调一次 `opencode run`（无工具判官 agent），返回 stdout；非零退出抛 RuntimeError。"""
    cmd = ["opencode", "run", "--pure", "--print-logs", "--dir", tempfile.gettempdir(), "--agent", _OPENCODE_AGENT]
    cmd.extend(["--title", "skill-creator-eval"])
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)

    # 其余 env 全传（smoke_test_scoring 靠 PATH 上的 `opencode` 桩接管）
    env = dict(os.environ)
    env["OPENCODE_CONFIG_CONTENT"] = _OPENCODE_CONFIG_CONTENT
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"

    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env,
            cwd=tempfile.gettempdir(),
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise RuntimeError("opencode CLI not found on PATH; install opencode and configure a provider") from e
    except subprocess.TimeoutExpired:
        # 原异常链里嵌着完整 prompt，抑制它避免超时报错刷屏
        raise RuntimeError(f"opencode run timed out after {timeout}s; retry with a larger --timeout") from None
    if result.returncode != 0:
        raise RuntimeError(f"opencode run exited {result.returncode}\nstderr: {result.stderr}")
    return result.stdout


def collect_skills(
    skill_name: str, candidate_description: str, skills_dir: Optional[Path] = None
) -> List[Dict[str, str]]:
    """收集 skills 目录下的 name 与 description，目标 skill 用候选描述替换。"""
    root = skills_dir or SKILLS_DIR
    if not root.is_dir():
        raise RuntimeError(f"skills dir not found: {root} (pass --skills-dir to override)")
    skills: List[Dict[str, str]] = []
    for entry in sorted(root.iterdir()):
        if not (entry / "SKILL.md").is_file():
            continue
        try:
            name, desc, _ = parse_skill_md(entry)
        except (ValueError, OSError):
            continue
        if not name or not desc:
            continue
        if name == skill_name:
            desc = candidate_description
        skills.append({"name": name, "description": desc})
    if not skills:
        raise RuntimeError(f"no skills found under {root}")
    return skills


def _judge_prompt(query: str, skills: List[Dict[str, str]]) -> str:
    """拼路由判定 prompt（技能清单加用户 query）。"""
    lines = []
    for i, s in enumerate(skills, 1):
        lines.append(f"{i}. {s['name']}:\n   {s['description']}")
    return (
        "You are the routing layer of an AI coding agent. Below is the list of "
        "available skills (name + description) and a user query. Decide whether you "
        "would load one of these skills to handle the query.\n"
        "Answer with a JSON object only, no other text:\n"
        '{"skill": "<name>"} or {"skill": null}\n\n'
        "Available skills:\n" + "\n".join(lines) + "\n\nUser query: " + query + "\n\nJSON:"
    )


def judge_query(query: str, skills: List[Dict[str, str]], target_name: str, config: EvalConfig) -> bool:
    """让 judge 选一个 skill，返回是否选中目标；响应不可解析时抛 RuntimeError。"""
    text = _call_opencode(_judge_prompt(query, skills), config.model, config.timeout)
    match = _JUDGE_PATTERN.search(text)
    if not match:
        raise RuntimeError(f"judge returned unparseable response for query: {query[:60]!r}\nresponse: {text[:200]!r}")
    chosen = match.group(1)
    return chosen == target_name


def run_canary(config: EvalConfig) -> None:
    """跑金丝雀用例，判定通道失效就中止（避免产出假数字）。"""
    for q in CANARY_QUERIES:
        got = judge_query(q["query"], [CANARY_SKILL], CANARY_SKILL["name"], config)
        if got != q["should_trigger"]:
            raise RuntimeError(
                f"canary failed: query={q['query']!r} expected_trigger={q['should_trigger']} "
                f"got={got} — judge channel is broken, aborting instead of producing numbers"
            )


def run_eval(
    eval_set: List[dict],
    skill_name: str,
    description: str,
    config: EvalConfig,
    skills_dir: Optional[Path] = None,
) -> dict:
    """对评估集跑一轮路由判定，返回逐条结果与汇总。"""
    skills = collect_skills(skill_name, description, skills_dir)
    results = []
    for item in eval_set:
        query = item["query"]
        should_trigger = bool(item["should_trigger"])
        triggers = 0
        for _ in range(config.runs_per_query):
            if judge_query(query, skills, skill_name, config):
                triggers += 1
        passed = (triggers / config.runs_per_query >= config.trigger_threshold) == should_trigger
        results.append(
            {
                "query": query,
                "should_trigger": should_trigger,
                "triggers": triggers,
                "runs": config.runs_per_query,
                "pass": passed,
            }
        )
    passed_count = sum(1 for r in results if r["pass"])
    return {
        "results": results,
        "summary": {
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "total": len(results),
        },
    }


def _load_description_principles() -> str:
    """从 ref/description-workflow.md 抽出“description 优化原则”正文。"""
    path = Path(__file__).resolve().parent.parent / "ref" / "description-workflow.md"
    text = path.read_text(encoding="utf-8")
    header = "## description 优化原则"
    start = text.find(header)
    if start == -1:
        raise ValueError(
            f"Section '{header}' not found in {path}. Restore the header, or update the "
            f"header match in optimize_description.py to point at the renamed section."
        )
    body_start = text.find("\n", start) + 1
    next_h2 = text.find("\n## ", body_start)
    body = text[body_start:next_h2] if next_h2 != -1 else text[body_start:]
    return body.strip()


def _format_eval_failures(eval_results: dict) -> str:
    """把漏触发与误触发渲染成改进 prompt 的失败清单。"""
    failed = [r for r in eval_results["results"] if r["should_trigger"] and not r["pass"]]
    false = [r for r in eval_results["results"] if not r["should_trigger"] and not r["pass"]]
    out = ""
    if failed:
        out += "FAILED TO TRIGGER (should have triggered but didn't):\n"
        for r in failed:
            out += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        out += "\n"
    if false:
        out += "FALSE TRIGGERS (triggered but shouldn't have):\n"
        for r in false:
            out += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        out += "\n"
    return out


def _format_history(history: List[dict]) -> str:
    """把历史尝试渲染成改进 prompt 的 attempt 段。"""
    if not history:
        return ""
    out = "PREVIOUS ATTEMPTS (do NOT repeat these — try something structurally different):\n\n"
    for h in history:
        train_s = f"{h['train_passed']}/{h['train_total']}"
        test_s = f"{h['test_passed']}/{h['test_total']}" if h.get("test_passed") is not None else None
        score_str = f"train={train_s}" + (f", test={test_s}" if test_s else "")
        out += f"<attempt {score_str}>\n"
        out += f'Description: "{h["description"]}"\n'
        if h.get("train_results"):
            out += "Train results:\n"
            for r in h["train_results"]:
                status = "PASS" if r["pass"] else "FAIL"
                out += f'  [{status}] "{r["query"][:80]}" (triggered {r["triggers"]}/{r["runs"]})\n'
        if h.get("note"):
            out += f"Note: {h['note']}\n"
        out += "</attempt>\n\n"
    return out


def _build_improve_prompt(skill: SkillContext, eval_results: dict, history: List[dict]) -> str:
    """拼改进描述的完整 prompt（现状、失败、历史、原则）。"""
    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    prompt = f"""You are optimizing a skill description for an AI coding agent skill called "{skill.name}". A "skill" is sort of like a prompt, but with progressive disclosure -- there's a title and description that the agent sees when deciding whether to use the skill, and then if it does use the skill, it reads the .md file which has lots more details and potentially links to other resources in the skill folder like helper files and scripts and additional documentation or examples.

The description appears in the agent's "available_skills" list. When a user sends a query, the agent decides whether to invoke the skill based solely on the title and on this description. Your goal is to write a description that triggers for relevant queries, and doesn't trigger for irrelevant ones.

Here's the current description:
<current_description>
"{skill.description}"
</current_description>

Current scores (Train: {train_score}):
<scores_summary>
"""
    prompt += _format_eval_failures(eval_results)
    prompt += _format_history(history)
    prompt += f"""</scores_summary>

Skill content (for context on what the skill does):
<skill_content>
{skill.content}
</skill_content>

<description_principles>
{_load_description_principles()}
</description_principles>

Based on the failures above and these principles, write a new and improved description that is more likely to trigger correctly. Be creative — you'll have multiple attempts and we'll keep the highest-scoring one.

Please respond with only the new description text in <new_description> tags, nothing else."""
    return prompt


def _extract_tagged_description(text: str) -> str:
    """从响应中取出 new_description 标签内容（容错无闭合标签）。"""
    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    if match:
        return match.group(1).strip().strip('"')
    cleaned = re.sub(r"^\s*<new_description>\s*", "", text)
    cleaned = re.sub(r"\s*</new_description>\s*$", "", cleaned)
    return cleaned.strip().strip('"')


def _rewrite_over_limit(prompt: str, description: str, config: LoopConfig) -> Tuple[str, str, str]:
    """对超长描述发起重写，返回 (prompt, 响应, 新描述)。"""
    shorten_prompt = (
        f"{prompt}\n\n"
        f"---\n\n"
        f"A previous attempt produced this description, which at "
        f"{len(description)} characters is over the {DESCRIPTION_MAX_CHARS}-character hard limit:\n\n"
        f'"{description}"\n\n'
        f"Rewrite it to be under {DESCRIPTION_MAX_CHARS} characters while keeping the most "
        f"important trigger words and intent coverage. Respond with only "
        f"the new description in <new_description> tags."
    )
    shorten_text = _call_opencode(shorten_prompt, config.eval.model, config.eval.timeout)
    return shorten_prompt, shorten_text, _extract_tagged_description(shorten_text)


def _write_transcript(log_dir: Path, iteration: Optional[int], transcript: dict) -> None:
    """把一轮改进的完整 transcript 落盘。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"improve_iter_{iteration or 'unknown'}.json").write_text(json.dumps(transcript, indent=2))


def improve_description(
    skill: SkillContext,
    eval_results: dict,
    history: List[dict],
    config: LoopConfig,
    iteration: Optional[int] = None,
) -> str:
    """调 opencode 生成改进描述，超长自动重写，可落 transcript。"""
    prompt = _build_improve_prompt(skill, eval_results, history)
    text = _call_opencode(prompt, config.eval.model, config.eval.timeout)
    description = _extract_tagged_description(text)

    transcript: dict = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "char_count": len(description),
        "over_limit": len(description) > DESCRIPTION_MAX_CHARS,
    }

    if len(description) > DESCRIPTION_MAX_CHARS:
        shorten_prompt, shorten_text, description = _rewrite_over_limit(prompt, description, config)
        transcript["rewrite_prompt"] = shorten_prompt
        transcript["rewrite_response"] = shorten_text
        transcript["rewrite_description"] = description
        transcript["rewrite_char_count"] = len(description)

    transcript["final_description"] = description

    if config.log_dir:
        _write_transcript(config.log_dir, iteration, transcript)

    return description


def split_eval_set(eval_set: List[dict], holdout: float, seed: int = 42) -> Tuple[List[dict], List[dict]]:
    """按正负例分层切分 train/test（固定种子）。"""
    rng = random.Random(seed)

    trigger = [e for e in eval_set if e["should_trigger"]]
    no_trigger = [e for e in eval_set if not e["should_trigger"]]

    rng.shuffle(trigger)
    rng.shuffle(no_trigger)

    n_trigger_test = max(1, int(len(trigger) * holdout))
    n_no_trigger_test = max(1, int(len(no_trigger) * holdout))

    test_set = trigger[:n_trigger_test] + no_trigger[:n_no_trigger_test]
    train_set = trigger[n_trigger_test:] + no_trigger[n_no_trigger_test:]

    return train_set, test_set


def _print_eval_stats(label: str, results: List[dict], elapsed: Optional[float] = None) -> None:
    """向 stderr 打印准确率、精确率、召回率与逐条结果。"""
    pos = [r for r in results if r["should_trigger"]]
    neg = [r for r in results if not r["should_trigger"]]
    tp = sum(r["triggers"] for r in pos)
    pos_runs = sum(r["runs"] for r in pos)
    fn = pos_runs - tp
    fp = sum(r["triggers"] for r in neg)
    neg_runs = sum(r["runs"] for r in neg)
    tn = neg_runs - fp
    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    accuracy = (tp + tn) / total if total > 0 else 0.0
    time_str = f" ({elapsed:.1f}s)" if elapsed is not None else ""
    print(
        f"{label}: {tp + tn}/{total} correct, precision={precision:.0%} recall={recall:.0%} accuracy={accuracy:.0%}{time_str}",
        file=sys.stderr,
    )
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        rate_str = f"{r['triggers']}/{r['runs']}"
        print(
            f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:60]}",
            file=sys.stderr,
        )


def select_best_iteration(history: List[dict], has_test_set: bool) -> dict:
    """选最佳轮：有 test 分数优先 test，其次 train。"""
    if has_test_set:
        return max(history, key=lambda h: (h["test_passed"] or 0, h["train_passed"]))
    return max(history, key=lambda h: h["train_passed"])


def _split_train_test(eval_set: List[dict], config: LoopConfig) -> SplitSets:
    """holdout 大于 0 时切分并打印，否则全量作 train。"""
    if config.holdout > 0:
        train_set, test_set = split_eval_set(eval_set, config.holdout)
        if config.verbose:
            print(f"Split: {len(train_set)} train, {len(test_set)} test (holdout={config.holdout})", file=sys.stderr)
    else:
        train_set, test_set = eval_set, []
    return SplitSets(train=train_set, test=test_set)


def _summarize(results: List[dict]) -> dict:
    """把逐条结果汇总成 {results, summary} 结构。"""
    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    return {"results": results, "summary": {"passed": passed, "failed": total - passed, "total": total}}


def _eval_iteration(
    split: SplitSets, name: str, description: str, config: LoopConfig
) -> Tuple[dict, Optional[dict], float]:
    """跑一轮评估并按 train/test 拆汇总，返回 (train, test, 耗时)。"""
    t0 = time.time()
    all_results = run_eval(
        eval_set=split.train + split.test,
        skill_name=name,
        description=description,
        config=config.eval,
        skills_dir=config.skills_dir,
    )
    elapsed = time.time() - t0
    train_queries = {q["query"] for q in split.train}
    train_results = _summarize([r for r in all_results["results"] if r["query"] in train_queries])
    test_results = (
        _summarize([r for r in all_results["results"] if r["query"] not in train_queries]) if split.test else None
    )
    return train_results, test_results, elapsed


def _history_entry(iteration: int, description: str, train_results: dict, test_results: Optional[dict]) -> dict:
    """把一轮评估整理成历史条目。"""
    test_summary = test_results["summary"] if test_results else None
    return {
        "iteration": iteration,
        "description": description,
        "train_passed": train_results["summary"]["passed"],
        "train_failed": train_results["summary"]["failed"],
        "train_total": train_results["summary"]["total"],
        "train_results": train_results["results"],
        "test_passed": test_summary["passed"] if test_summary else None,
        "test_failed": test_summary["failed"] if test_summary else None,
        "test_total": test_summary["total"] if test_summary else None,
        "test_results": test_results["results"] if test_results else None,
    }


def _stop_reason(iteration: int, train_failed: int, config: LoopConfig) -> Optional[str]:
    """判断是否停止（全过或达上限），返回停止原因或 None。"""
    if train_failed == 0:
        if config.verbose:
            print(f"\nAll train queries passed on iteration {iteration}!", file=sys.stderr)
        return f"all_passed (iteration {iteration})"
    if iteration == config.max_iterations:
        if config.verbose:
            print(f"\nMax iterations reached ({config.max_iterations}).", file=sys.stderr)
        return f"max_iterations ({config.max_iterations})"
    return None


def _print_iteration_header(iteration: int, description: str, config: LoopConfig) -> None:
    """打印一轮的分隔标题。"""
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"Iteration {iteration}/{config.max_iterations}", file=sys.stderr)
    print(f"Description: {description}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)


def _result_payload(
    history: List[dict],
    exit_reason: str,
    original_description: str,
    split: SplitSets,
    config: LoopConfig,
) -> dict:
    """组装最终结果 dict（含最佳描述与分数）。"""
    best = select_best_iteration(history, has_test_set=bool(split.test))
    best_score = (
        f"{best['test_passed']}/{best['test_total']}" if split.test else f"{best['train_passed']}/{best['train_total']}"
    )
    if config.verbose:
        print(f"\nExit reason: {exit_reason}", file=sys.stderr)
        print(f"Best score: {best_score} (iteration {best['iteration']})", file=sys.stderr)
    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "best_train_score": f"{best['train_passed']}/{best['train_total']}",
        "best_test_score": f"{best['test_passed']}/{best['test_total']}" if split.test else None,
        "iterations_run": len(history),
        "holdout": config.holdout,
        "train_size": len(split.train),
        "test_size": len(split.test),
        "history": history,
    }


def _train_only(history: List[dict]) -> List[dict]:
    """剥掉历史条目里的 test_* 字段（改进 prompt 不该看到留出集结果）。"""
    return [{k: v for k, v in h.items() if not k.startswith("test_")} for h in history]


def run_optimize_loop(
    eval_set: List[dict], skill_path: Path, description_override: Optional[str], config: LoopConfig
) -> dict:
    """跑 canary、评估、改进的完整优化循环，返回结果 dict。"""
    name, original_description, content = parse_skill_md(skill_path)
    skill = SkillContext(name=name, content=content, description=description_override or original_description)
    split = _split_train_test(eval_set, config)

    history: List[dict] = []
    exit_reason = "unknown"

    for iteration in range(1, config.max_iterations + 1):
        if config.verbose:
            _print_iteration_header(iteration, skill.description, config)
        run_canary(config.eval)
        train_results, test_results, eval_elapsed = _eval_iteration(split, skill.name, skill.description, config)
        history.append(_history_entry(iteration, skill.description, train_results, test_results))
        if config.verbose:
            _print_eval_stats("Train", train_results["results"], eval_elapsed)
            if test_results:
                _print_eval_stats("Test ", test_results["results"])

        reason = _stop_reason(iteration, train_results["summary"]["failed"], config)
        if reason:
            exit_reason = reason
            break

        if config.verbose:
            print("\nImproving description...", file=sys.stderr)
        t0 = time.time()
        new_description = improve_description(skill, train_results, _train_only(history), config, iteration)
        if config.verbose:
            print(f"Proposed ({time.time() - t0:.1f}s): {new_description}", file=sys.stderr)
        skill = skill._replace(description=new_description)

    return _result_payload(history, exit_reason, original_description, split, config)


def _print_final_summary(output: dict) -> None:
    """向 stderr 打印最终对比摘要。"""
    print(file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"优化完成（exit: {output['exit_reason']}）", file=sys.stderr)
    print(
        f"Best score: {output['best_score']}（train {output['best_train_score']}"
        + (f"，test {output['best_test_score']}" if output["best_test_score"] else "")
        + f"，{output['iterations_run']} 轮）",
        file=sys.stderr,
    )
    print("=" * 60, file=sys.stderr)
    print("Original:", file=sys.stderr)
    print(f"  {output['original_description']}", file=sys.stderr)
    print("Best:", file=sys.stderr)
    print(f"  {output['best_description']}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


# markdownlint MD013 限 120 列（含 frontmatter）；90 给 2 空格缩进留余量
DESCRIPTION_WRAP_WIDTH = 90
_DESCRIPTION_KEY_RE = re.compile(r"^description:[ \t]*(.*)$")
_BREAK_AFTER = "。；，、：）】"


def _frontmatter_close(lines: List[str]) -> int:
    """返回 frontmatter 结束行索引；缺失抛 ValueError。"""
    span = frontmatter_span("\n".join(lines))
    if span is None:
        raise ValueError("SKILL.md frontmatter has no closing ---")
    return span[1]


def _description_span(lines: List[str]) -> Tuple[int, int]:
    """定位 description 键的 (起始行, 结束行)。"""
    close = _frontmatter_close(lines)
    for i in range(1, close):
        match = _DESCRIPTION_KEY_RE.match(lines[i])
        if match:
            end = close
            for j in range(i + 1, close):
                if lines[j].strip() and not (lines[j].startswith("  ") or lines[j].startswith("\t")):
                    end = j
                    break
            return i, end
    raise ValueError("SKILL.md frontmatter has no description key")


def wrap_description(description: str, indent: str = "  ", width: int = DESCRIPTION_WRAP_WIDTH) -> List[str]:
    """按标点与空白把描述折行成 YAML 块标量行。"""
    out: List[str] = []
    for para_index, paragraph in enumerate(description.split("\n")):
        if para_index:
            out.append(indent)
        pieces: List[str] = []
        current = ""
        for char in paragraph:
            current += char
            if char.isspace() or char in _BREAK_AFTER:
                pieces.append(current)
                current = ""
        if current:
            pieces.append(current)

        line = ""
        for piece in pieces:
            if len(piece) > width:
                if line:
                    out.append(indent + line)
                    line = ""
                for start in range(0, len(piece), width):
                    chunk = piece[start : start + width]
                    if start + width < len(piece):
                        out.append(indent + chunk)
                    else:
                        line = chunk
                continue
            if line and len(line) + len(piece) > width:
                out.append(indent + line.rstrip())
                line = piece
            else:
                line += piece
        out.append(indent + line.rstrip())
    return out


def rewrite_description(text: str, new_description: str) -> str:
    """把 SKILL.md 全文里的 description 块替换为新描述的块标量。"""
    lines = text.split("\n")
    start, end = _description_span(lines)
    block = ["description: |"] + wrap_description(new_description.strip())
    return "\n".join(lines[:start] + block + lines[end:])


def apply_description(skill_path: Path, new_description: str, dry_run: bool = False) -> int:
    """校验后把新描述写回 SKILL.md（dry_run 只打印 diff），返回退出码。"""
    import difflib

    from tools.quick_validate import validate_skill

    skill_md = skill_path / "SKILL.md"
    if not skill_md.is_file():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        return 1
    original = skill_md.read_text()
    try:
        current = parse_skill_md(skill_path)[1]
    except ValueError as e:
        print(f"Error: 现有 frontmatter 无法解析，先修 SKILL.md：{e}", file=sys.stderr)
        return 1
    if " ".join(new_description.split()) == current:
        print("best_description 与现有 description 一致，无需改动。", file=sys.stderr)
        return 0

    try:
        updated = rewrite_description(original, new_description)
    except ValueError as e:
        print(f"Error: cannot locate the description block: {e}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="skill-apply-") as tmp:
        (Path(tmp) / "SKILL.md").write_text(updated)
        valid, message = validate_skill(Path(tmp))
    if not valid:
        print(f"Error: 新 frontmatter 未通过校验，SKILL.md 未改动：{message}", file=sys.stderr)
        return 1

    if dry_run:
        diff = difflib.unified_diff(
            original.splitlines(), updated.splitlines(), "a/SKILL.md", "b/SKILL.md", lineterm="", n=2
        )
        print("\n".join(diff))
        print("\n(--dry-run: 未写入)", file=sys.stderr)
        return 0

    tmp_path = skill_md.with_name(skill_md.name + ".tmp-apply")
    tmp_path.write_text(updated)
    os.replace(str(tmp_path), str(skill_md))
    print(f"已写入 {skill_md}（description {len(current)} → {len(new_description.strip())} 字符）", file=sys.stderr)
    return 0


def _load_best_description(path: Path) -> str:
    """从 results.json 读取 best_description；读不到或缺失时抛 ValueError。"""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read results json {path}: {e}") from e
    best = data.get("best_description") if isinstance(data, dict) else None
    if not best:
        raise ValueError(f"no 'best_description' in {path}")
    return str(best)


def _load_eval_set(path: Path) -> List[dict]:
    """读入 eval set：缺字段或同 query 冲突时抛 ValueError（消息可直接给用户）。"""
    try:
        eval_set = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read eval set {path}: {e}") from e
    for i, item in enumerate(eval_set):
        if not isinstance(item, dict) or "query" not in item or "should_trigger" not in item:
            raise ValueError(f"eval set item {i} missing 'query' / 'should_trigger': {item!r}")
    unique: Dict[str, dict] = {}
    for item in eval_set:
        prev = unique.get(item["query"])
        if prev is not None and bool(prev["should_trigger"]) != bool(item["should_trigger"]):
            raise ValueError(f"query appears twice with conflicting should_trigger: {item['query']!r}")
        if prev is None:
            unique[item["query"]] = item
    return list(unique.values())


def _prepare_results_dir(results_dir: Optional[str]) -> Tuple[Optional[Path], Optional[Path]]:
    """建带时间戳的结果目录，返回 (结果目录, transcript 目录)；未指定时返回 (None, None)。"""
    if not results_dir:
        return None, None
    run_dir = Path(results_dir) / time.strftime("%Y-%m-%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, run_dir / "logs"


def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="Run eval + improve loop for a skill description")
    parser.add_argument("--eval-set", default=None, help="Path to eval set JSON file (loop mode)")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override starting description")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per opencode run call in seconds")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max improvement iterations")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument(
        "--holdout",
        type=float,
        default=DEFAULT_HOLDOUT_RATIO,
        help=f"Fraction of eval set to hold out for testing (0 to disable, default: {DEFAULT_HOLDOUT_RATIO})",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model in provider/model form (default: the model opencode is configured with)",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=None,
        help="Skills pool for the routing judge (default: ~/.agents/skills)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Save results.json + improve transcripts to a timestamped subdirectory here",
    )
    parser.add_argument(
        "--apply",
        default=None,
        metavar="RESULTS_JSON",
        help="apply mode: write results.json's best_description into --skill-path's frontmatter "
        "instead of running the loop (run this only after the user approved the candidate)",
    )
    parser.add_argument("--dry-run", action="store_true", help="with --apply: print a diff, write nothing")
    return parser


def main():
    """CLI 入口：loop 模式或 --apply 模式。"""
    parser = _build_parser()
    args = parser.parse_args()

    if args.apply:
        try:
            best = _load_best_description(Path(args.apply))
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(apply_description(Path(args.skill_path), best, dry_run=args.dry_run))

    if not args.eval_set:
        parser.error("--eval-set is required in loop mode (or use --apply)")

    try:
        eval_set = _load_eval_set(Path(args.eval_set))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    results_dir, log_dir = _prepare_results_dir(args.results_dir)
    config = LoopConfig(
        eval=EvalConfig(
            timeout=args.timeout,
            runs_per_query=args.runs_per_query,
            trigger_threshold=args.trigger_threshold,
            model=args.model,
        ),
        max_iterations=args.max_iterations,
        holdout=args.holdout,
        verbose=args.verbose,
        log_dir=log_dir,
        skills_dir=args.skills_dir,
    )
    output = run_optimize_loop(eval_set, skill_path, args.description, config)
    _print_final_summary(output)

    print(json.dumps(output, indent=2))
    if results_dir:
        (results_dir / "results.json").write_text(json.dumps(output, indent=2))
        print(f"Results saved to: {results_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()

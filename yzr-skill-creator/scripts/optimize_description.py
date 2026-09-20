#!/usr/bin/env python3
"""Optimize a skill description via a routing-judge eval + improve loop.

Single entry point for yzr-skill-creator's“描述优化”入口. The loop:
  1. split the eval set into train / holdout (DEFAULT_HOLDOUT_RATIO)
2. eval: for each query, one text-only `claude -p` call acts as the routing
      judge — it sees the available skills list (name + description) and picks
      which skill (if any) it would load. The candidate description stands in
      for the target skill. 触发是概率事件, so each query is probed
      `runs_per_query` times and pass = trigger rate agrees with the query's
      `should_trigger` label (rate >= threshold for should-trigger, rate < threshold
      for should-not-trigger)
  3. canary: control queries against a synthetic skill with a bulletproof
     description run before the eval set — a canary failure means the judge
     channel is broken (model error / CLI error / parse error), and the run
     aborts instead of producing numbers from a broken channel
  4. improve: feed failures + previous attempts + the“description 优化原则”
     section of ref/skill-writing-principles.md to `claude -p`, get a
     new description back
  5. repeat until all train queries pass or max_iterations; pick the best
     iteration by test score (train score if no holdout)

All judge / improve calls run `claude -p` in a neutral cwd (temp dir) with no
tools, so project context (AGENTS.md / MCP servers) cannot bias the result.
No model is pinned by default — `claude -p` uses the user's configured default
(pass `--model` to override); not binding this skill to a specific model is
intentional.
The skills list is parsed in-process from ~/.claude/skills — nothing is cloned,
moved, or written to the skills directory.

Output: results JSON on stdout (machine-readable, carries `best_description`);
a compact human summary on stderr. `--results-dir` saves
results.json + per-round improvement transcripts under logs/. There is no HTML
report — the summary is meant to be relayed by the agent in chat.

`--apply <results.json> --skill-path <dir>` is the write-back half of that last
sentence: it replaces the frontmatter description mechanically (block-scalar
indentation + wrapping included), validates the result with quick_validate
before touching the file, refuses to write on any validation error, reports
"无需改动" and writes nothing when the best description equals the current
one, and prints a diff instead when given `--dry-run`.
Whether to accept a candidate description stays with the user — see
SKILL.md“描述优化 · 第 4 步”.
"""

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
from typing import Dict, List, Optional, Tuple

# Bootstrap sys.path so `from scripts.X import Y` works under both
# `python3 scripts/optimize_description.py` (standalone) and
# `python3 -m scripts.optimize_description` (from yzr-skill-creator/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import DESCRIPTION_MAX_CHARS, parse_skill_md

# SSOT for the train/test split ratio. Prose references this constant instead
# of writing the literal so future tweaks don't drift docs vs. code.
DEFAULT_HOLDOUT_RATIO = 0.4

# Judge candidates are collected from here so the eval list mirrors what a real
# agent sees. The target skill is identified by its own frontmatter name.
# Agent-specific path (Claude Code skills dir; root AGENTS.md notes the CLI
# varies by agent): porting to another agent CLI = repoint this and the
# `claude` binary in _call_claude, nothing else.
SKILLS_DIR = Path.home() / ".claude" / "skills"

# Canary: a synthetic skill whose description contains a unique token, plus
# control queries with known outcomes. A canary failure = broken judge channel
# (model / CLI / parsing), not a bad description — abort loudly.
CANARY_SKILL = {
    "name": "_canary_skill",
    "description": "当用户提到“量子香蕉”时使用本 skill。触发：量子香蕉。不适用：其它一切。",
}
CANARY_QUERIES = [
    {"query": "帮我处理一下量子香蕉的排序问题", "should_trigger": True},
    {"query": "帮我写个 Python 脚本把两个 JSON 合并一下", "should_trigger": False},
]

_JUDGE_PATTERN = re.compile(r'"skill"\s*:\s*(?:"([^"]*)"|null)')


def _call_claude(prompt: str, model: Optional[str], timeout: int = 300) -> str:
    """Run `claude -p` with the prompt on stdin and return the text response.

    Prompt goes over stdin (not argv) because it can embed full skill content.
    Runs in the temp dir so project context cannot bias the answer.
    """
    # Agent-specific binding, deliberately centralised in this one function:
    # every judge / improve call goes through it, so swapping the agent CLI is
    # a one-spot change (see SKILLS_DIR's comment).
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    # CLAUDECODE marks an enclosing Claude Code session; stripping it keeps the
    # child CLI behaving like a top-level invocation. The pass-everything-else
    # policy is also what lets smoke_test_scoring inject its stub via
    # SMOKE_JUDGE_CONFIG — extend the strip list and that stub dies silently.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
        cwd=tempfile.gettempdir(),
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p exited {result.returncode}\nstderr: {result.stderr}")
    return result.stdout


def collect_skills(skill_name: str, candidate_description: str) -> List[Dict[str, str]]:
    """Collect real skills from SKILLS_DIR; the target skill uses the candidate description."""
    if not SKILLS_DIR.is_dir():
        raise RuntimeError(f"skills dir not found: {SKILLS_DIR}")
    skills: List[Dict[str, str]] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
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
        raise RuntimeError(f"no skills found under {SKILLS_DIR}")
    return skills


def _judge_prompt(query: str, skills: List[Dict[str, str]]) -> str:
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


def judge_query(
    query: str,
    skills: List[Dict[str, str]],
    target_name: str,
    model: Optional[str],
    timeout: int,
) -> bool:
    """One routing-judge call: return whether the target skill was chosen."""
    text = _call_claude(_judge_prompt(query, skills), model, timeout)
    match = _JUDGE_PATTERN.search(text)
    if not match:
        raise RuntimeError(f"judge returned unparseable response for query: {query[:60]!r}\nresponse: {text[:200]!r}")
    chosen = match.group(1)
    return chosen == target_name


def run_canary(model: Optional[str], timeout: int) -> None:
    """Verify the judge channel with a synthetic skill; abort on failure."""
    for q in CANARY_QUERIES:
        got = judge_query(q["query"], [CANARY_SKILL], CANARY_SKILL["name"], model, timeout)
        if got != q["should_trigger"]:
            raise RuntimeError(
                f"canary failed: query={q['query']!r} expected_trigger={q['should_trigger']} "
                f"got={got} — judge channel is broken, aborting instead of producing numbers"
            )


def run_eval(
    eval_set: List[dict],
    skill_name: str,
    description: str,
    timeout: int,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: Optional[str] = None,
) -> dict:
    """Run the full eval set through the routing judge and return results."""
    skills = collect_skills(skill_name, description)
    results = []
    for item in eval_set:
        query = item["query"]
        should_trigger = bool(item["should_trigger"])
        triggers = 0
        for _ in range(runs_per_query):
            if judge_query(query, skills, skill_name, model, timeout):
                triggers += 1
        passed = (triggers / runs_per_query >= trigger_threshold) == should_trigger
        results.append(
            {
                "query": query,
                "should_trigger": should_trigger,
                "triggers": triggers,
                "runs": runs_per_query,
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
    """Read description-optimization principles from ref/skill-writing-principles.md.

    The principles live in a single SSOT markdown file so they can be extended
    without touching code. Extracts the section under the `## description 优化
    原则` header (up to the next `## ` header) and injects it into the
    improvement prompt.
    """
    path = Path(__file__).resolve().parent.parent / "ref" / "skill-writing-principles.md"
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


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: List[dict],
    model: Optional[str],
    log_dir: Optional[Path] = None,
    iteration: Optional[int] = None,
    timeout: int = 300,
) -> str:
    """Call Claude to improve the description based on eval results."""
    failed_triggers = [r for r in eval_results["results"] if r["should_trigger"] and not r["pass"]]
    false_triggers = [r for r in eval_results["results"] if not r["should_trigger"] and not r["pass"]]

    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    scores_summary = f"Train: {train_score}"

    prompt = f"""You are optimizing a skill description for a Claude Code skill called "{skill_name}". A "skill" is sort of like a prompt, but with progressive disclosure -- there's a title and description that Claude sees when deciding whether to use the skill, and then if it does use the skill, it reads the .md file which has lots more details and potentially links to other resources in the skill folder like helper files and scripts and additional documentation or examples.

The description appears in Claude's "available_skills" list. When a user sends a query, Claude decides whether to invoke the skill based solely on the title and on this description. Your goal is to write a description that triggers for relevant queries, and doesn't trigger for irrelevant ones.

Here's the current description:
<current_description>
"{current_description}"
</current_description>

Current scores ({scores_summary}):
<scores_summary>
"""
    if failed_triggers:
        prompt += "FAILED TO TRIGGER (should have triggered but didn't):\n"
        for r in failed_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if false_triggers:
        prompt += "FALSE TRIGGERS (triggered but shouldn't have):\n"
        for r in false_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if history:
        prompt += "PREVIOUS ATTEMPTS (do NOT repeat these — try something structurally different):\n\n"
        for h in history:
            train_s = f"{h['train_passed']}/{h['train_total']}"
            test_s = f"{h['test_passed']}/{h['test_total']}" if h.get("test_passed") is not None else None
            score_str = f"train={train_s}" + (f", test={test_s}" if test_s else "")
            prompt += f"<attempt {score_str}>\n"
            prompt += f'Description: "{h["description"]}"\n'
            if h.get("train_results"):
                prompt += "Train results:\n"
                for r in h["train_results"]:
                    status = "PASS" if r["pass"] else "FAIL"
                    prompt += f'  [{status}] "{r["query"][:80]}" (triggered {r["triggers"]}/{r["runs"]})\n'
            if h.get("note"):
                prompt += f"Note: {h['note']}\n"
            prompt += "</attempt>\n\n"

    prompt += f"""</scores_summary>

Skill content (for context on what the skill does):
<skill_content>
{skill_content}
</skill_content>

<description_principles>
{_load_description_principles()}
</description_principles>

Based on the failures above and these principles, write a new and improved description that is more likely to trigger correctly. Be creative — you'll have multiple attempts and we'll keep the highest-scoring one.

Please respond with only the new description text in <new_description> tags, nothing else."""

    text = _call_claude(prompt, model, timeout)

    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    if match:
        description = match.group(1).strip().strip('"')
    else:
        cleaned = re.sub(r"^\s*<new_description>\s*", "", text)
        cleaned = re.sub(r"\s*</new_description>\s*$", "", cleaned)
        description = cleaned.strip().strip('"')

    transcript: dict = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "char_count": len(description),
        "over_limit": len(description) > DESCRIPTION_MAX_CHARS,
    }

    if len(description) > DESCRIPTION_MAX_CHARS:
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
        shorten_text = _call_claude(shorten_prompt, model, timeout)
        match = re.search(r"<new_description>(.*?)</new_description>", shorten_text, re.DOTALL)
        if match:
            shortened = match.group(1).strip().strip('"')
        else:
            cleaned = re.sub(r"^\s*<new_description>\s*", "", shorten_text)
            cleaned = re.sub(r"\s*</new_description>\s*$", "", cleaned)
            shortened = cleaned.strip().strip('"')

        transcript["rewrite_prompt"] = shorten_prompt
        transcript["rewrite_response"] = shorten_text
        transcript["rewrite_description"] = shortened
        transcript["rewrite_char_count"] = len(shortened)
        description = shortened

    transcript["final_description"] = description

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"improve_iter_{iteration or 'unknown'}.json"
        log_file.write_text(json.dumps(transcript, indent=2))

    return description


def split_eval_set(eval_set: List[dict], holdout: float, seed: int = 42) -> Tuple[List[dict], List[dict]]:
    """Split eval set into train and test sets, stratified by should_trigger."""
    # Local RNG: seeding the global one would reset the caller's random
    # sequence when this module is imported as a library.
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
    """Compact per-split stats + per-query status, for human (stderr) output."""
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
    """Best iteration by score: holdout test score first (train as tie-break)
    when a test set exists, else train score alone.

    Importable so the smoke test pins the real selection logic, not a copy
    of its lambda (a copy stayed green when the tie-break was changed).
    """
    if has_test_set:
        return max(history, key=lambda h: (h["test_passed"] or 0, h["train_passed"]))
    return max(history, key=lambda h: h["train_passed"])


def run_optimize_loop(
    eval_set: List[dict],
    skill_path: Path,
    description_override: Optional[str],
    timeout: int,
    max_iterations: int,
    runs_per_query: int,
    trigger_threshold: float,
    holdout: float,
    model: Optional[str],
    verbose: bool,
    log_dir: Optional[Path] = None,
) -> dict:
    """Run the eval + improve loop; return the results dict for results.json."""
    name, original_description, content = parse_skill_md(skill_path)
    current_description = description_override or original_description

    if holdout > 0:
        train_set, test_set = split_eval_set(eval_set, holdout)
        if verbose:
            print(f"Split: {len(train_set)} train, {len(test_set)} test (holdout={holdout})", file=sys.stderr)
    else:
        train_set = eval_set
        test_set = []

    history = []
    exit_reason = "unknown"

    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print(f"Iteration {iteration}/{max_iterations}", file=sys.stderr)
            print(f"Description: {current_description}", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)

        run_canary(model, timeout)

        all_queries = train_set + test_set
        t0 = time.time()
        all_results = run_eval(
            eval_set=all_queries,
            skill_name=name,
            description=current_description,
            timeout=timeout,
            runs_per_query=runs_per_query,
            trigger_threshold=trigger_threshold,
            model=model,
        )
        eval_elapsed = time.time() - t0

        train_queries_set = {q["query"] for q in train_set}
        train_result_list = [r for r in all_results["results"] if r["query"] in train_queries_set]
        test_result_list = [r for r in all_results["results"] if r["query"] not in train_queries_set]

        train_passed = sum(1 for r in train_result_list if r["pass"])
        train_total = len(train_result_list)
        train_summary = {"passed": train_passed, "failed": train_total - train_passed, "total": train_total}
        train_results = {"results": train_result_list, "summary": train_summary}

        if test_set:
            test_passed = sum(1 for r in test_result_list if r["pass"])
            test_total = len(test_result_list)
            test_summary = {"passed": test_passed, "failed": test_total - test_passed, "total": test_total}
            test_results = {"results": test_result_list, "summary": test_summary}
        else:
            test_results = None
            test_summary = None

        history.append(
            {
                "iteration": iteration,
                "description": current_description,
                "train_passed": train_summary["passed"],
                "train_failed": train_summary["failed"],
                "train_total": train_summary["total"],
                "train_results": train_results["results"],
                "test_passed": test_summary["passed"] if test_summary else None,
                "test_failed": test_summary["failed"] if test_summary else None,
                "test_total": test_summary["total"] if test_summary else None,
                "test_results": test_results["results"] if test_results else None,
            }
        )

        if verbose:
            _print_eval_stats("Train", train_results["results"], eval_elapsed)
            if test_summary:
                _print_eval_stats("Test ", test_results["results"])

        if train_summary["failed"] == 0:
            exit_reason = f"all_passed (iteration {iteration})"
            if verbose:
                print(f"\nAll train queries passed on iteration {iteration}!", file=sys.stderr)
            break

        if iteration == max_iterations:
            exit_reason = f"max_iterations ({max_iterations})"
            if verbose:
                print(f"\nMax iterations reached ({max_iterations}).", file=sys.stderr)
            break

        if verbose:
            print("\nImproving description...", file=sys.stderr)

        t0 = time.time()
        blinded_history = [{k: v for k, v in h.items() if not k.startswith("test_")} for h in history]
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=current_description,
            eval_results=train_results,
            history=blinded_history,
            model=model,
            log_dir=log_dir,
            iteration=iteration,
            timeout=timeout,
        )
        improve_elapsed = time.time() - t0

        if verbose:
            print(f"Proposed ({improve_elapsed:.1f}s): {new_description}", file=sys.stderr)

        current_description = new_description

    best = select_best_iteration(history, has_test_set=bool(test_set))
    if test_set:
        best_score = f"{best['test_passed']}/{best['test_total']}"
    else:
        best_score = f"{best['train_passed']}/{best['train_total']}"

    if verbose:
        print(f"\nExit reason: {exit_reason}", file=sys.stderr)
        print(f"Best score: {best_score} (iteration {best['iteration']})", file=sys.stderr)

    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "best_train_score": f"{best['train_passed']}/{best['train_total']}",
        "best_test_score": f"{best['test_passed']}/{best['test_total']}" if test_set else None,
        "iterations_run": len(history),
        "holdout": holdout,
        "train_size": len(train_set),
        "test_size": len(test_set),
        "history": history,
    }


def _print_final_summary(output: dict) -> None:
    """Human-facing end summary on stderr (before/after + best score)."""
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


# --- applying a result back into SKILL.md -----------------------------------

# Wrapping width for the emitted block scalar. markdownlint's MD013 measures
# every line of the file (frontmatter included) against 120, and 90 leaves room
# for the 2-space indent plus future style tweaks.
DESCRIPTION_WRAP_WIDTH = 90
_DESCRIPTION_KEY_RE = re.compile(r"^description:[ \t]*(.*)$")
# Break preferentially after these — CJK prose has no spaces to break on, so a
# hard wrap mid-sentence would read badly in every downstream view.
_BREAK_AFTER = "。；，、：）】"


def _frontmatter_close(lines: List[str]) -> int:
    """Index of the closing ``---`` line."""
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return i
    raise ValueError("SKILL.md frontmatter has no closing ---")


def _description_span(lines: List[str]) -> Tuple[int, int]:
    """``[start, end)`` line indices of the frontmatter ``description`` block."""
    close = _frontmatter_close(lines)
    for i in range(1, close):
        match = _DESCRIPTION_KEY_RE.match(lines[i])
        if match:
            end = close
            for j in range(i + 1, close):
                # A non-empty, non-indented line is the next top-level key.
                if lines[j].strip() and not (lines[j].startswith("  ") or lines[j].startswith("\t")):
                    end = j
                    break
            return i, end
    raise ValueError("SKILL.md frontmatter has no description key")


def wrap_description(description: str, indent: str = "  ", width: int = DESCRIPTION_WRAP_WIDTH) -> List[str]:
    """Fold a description into indented lines of ≤ *width*.

    Break opportunities are whitespace and CJK punctuation (``_BREAK_AFTER``),
    so a Chinese description wraps after a clause marker instead of mid-word;
    only a single unbreakable run longer than the width gets hard-cut. Existing
    newlines become paragraph breaks (one blank indented line each).
    """
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
    """Return SKILL.md text with the frontmatter description replaced.

    Always re-emits as a ``|`` block scalar: the value is multi-line prose, and
    block style is what every existing SKILL.md in this repo uses.
    """
    lines = text.split("\n")
    start, end = _description_span(lines)
    block = ["description: |"] + wrap_description(new_description.strip())
    return "\n".join(lines[:start] + block + lines[end:])


def apply_description(skill_path: Path, new_description: str, dry_run: bool = False) -> int:
    """Write ``best_description`` into the skill's frontmatter, gated on validation.

    The write is mechanical (pure function of the two inputs), so it belongs in a
    script; whether to accept a candidate description stays with the user — this
    function is only reached after they say yes.

    Returns a process exit code. Never leaves a broken SKILL.md behind: the
    candidate is validated in a throwaway copy first, and the real write is an
    atomic rename.
    """
    import difflib

    from scripts.quick_validate import validate_skill

    skill_md = skill_path / "SKILL.md"
    original = skill_md.read_text()
    try:
        current = parse_skill_md(skill_path)[1]
    except ValueError as e:
        # The *existing* file is already unparseable — say so instead of
        # pretending the candidate was at fault.
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

    # Gate on the real validator before touching the file.
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


def main():
    parser = argparse.ArgumentParser(description="Run eval + improve loop for a skill description")
    parser.add_argument("--eval-set", default=None, help="Path to eval set JSON file (loop mode)")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override starting description")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per claude -p call in seconds")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max improvement iterations")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument(
        "--holdout",
        type=float,
        default=DEFAULT_HOLDOUT_RATIO,
        help=f"Fraction of eval set to hold out for testing (0 to disable, default: {DEFAULT_HOLDOUT_RATIO})",
    )
    parser.add_argument("--model", default=None, help="Model to use for claude -p (default: user's configured model)")
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
    args = parser.parse_args()

    if args.apply:
        best = json.loads(Path(args.apply).read_text()).get("best_description")
        if not best:
            print(f"Error: no 'best_description' in {args.apply}", file=sys.stderr)
            sys.exit(1)
        sys.exit(apply_description(Path(args.skill_path), str(best), dry_run=args.dry_run))

    if not args.eval_set:
        parser.error("--eval-set is required in loop mode (or use --apply)")

    eval_set = json.loads(Path(args.eval_set).read_text())
    for i, item in enumerate(eval_set):
        if not isinstance(item, dict) or "query" not in item or "should_trigger" not in item:
            print(f"Error: eval set item {i} missing 'query' / 'should_trigger': {item!r}", file=sys.stderr)
            sys.exit(1)
    # Duplicate query texts would straddle the train/test split (membership is
    # keyed on query text below) and double-count one side; collapse exact
    # duplicates and refuse contradictory labels up front.
    unique: Dict[str, dict] = {}
    for item in eval_set:
        prev = unique.get(item["query"])
        if prev is not None and bool(prev["should_trigger"]) != bool(item["should_trigger"]):
            print(
                f"Error: query appears twice with conflicting should_trigger: {item['query']!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        if prev is None:
            unique[item["query"]] = item
    eval_set = list(unique.values())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    results_dir = None
    log_dir = None
    if args.results_dir:
        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        results_dir = Path(args.results_dir) / timestamp
        results_dir.mkdir(parents=True, exist_ok=True)
        log_dir = results_dir / "logs"

    output = run_optimize_loop(
        eval_set=eval_set,
        skill_path=skill_path,
        description_override=args.description,
        timeout=args.timeout,
        max_iterations=args.max_iterations,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        holdout=args.holdout,
        model=args.model,
        verbose=args.verbose,
        log_dir=log_dir,
    )
    _print_final_summary(output)

    print(json.dumps(output, indent=2))
    if results_dir:
        (results_dir / "results.json").write_text(json.dumps(output, indent=2))
        print(f"Results saved to: {results_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()

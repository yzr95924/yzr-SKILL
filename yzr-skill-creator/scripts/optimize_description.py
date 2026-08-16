#!/usr/bin/env python3
"""Optimize a skill description via an eval + improve loop.

Single entry point for yzr-skill-creator's「描述优化」独立入口. The loop:
  1. split the eval set into train / holdout (DEFAULT_HOLDOUT_RATIO)
  2. eval: for each query, run `claude -p` against a per-query skill clone
     (`_eval_skill_<uuid>` under ~/.claude/skills/) and detect triggering from
     stream events — 触发是概率事件, so each query is probed `runs_per_query`
     times and pass = trigger_rate >= trigger_threshold
  3. improve: feed failures + previous attempts + the「description 优化原则」
     section of references/skill-writing-principles.md to `claude -p`, get a
     new description back
  4. repeat until all train queries pass or max_iterations; pick the best
     iteration by test score (train score if no holdout)

Output: results JSON on stdout (machine-readable, agent applies
`best_description`); a compact human summary on stderr. `--results-dir` saves
results.json + per-round improvement transcripts under logs/. There is no HTML
report — the summary is meant to be relayed by the agent in chat.

`--single-round`: one eval + one improvement without the loop (covers the
old standalone improve_description.py use — pass an eval set you already have).
"""

import argparse
import json
import os
import random
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap sys.path so `from scripts.X import Y` works under both
# `python3 scripts/optimize_description.py` (standalone) and
# `python3 -m scripts.optimize_description` (from yzr-skill-creator/). Resolves B1.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import DESCRIPTION_MAX_CHARS, parse_skill_md

# SSOT for the train/test split ratio. Prose references this constant instead of
# writing the literal 0.4 so future tweaks don't drift docs vs. code.
DEFAULT_HOLDOUT_RATIO = 0.4

# Match any per-query eval clone, not just the one assigned to the current
# query. With ProcessPoolExecutor(10), all in-flight clones coexist in
# ~/.claude/skills/ with identical descriptions, and the model picks one
# arbitrarily — crediting only the specific `clean_name` would register most
# real triggers as misses (recall ~6%). 8 hex chars matches
# `uuid.uuid4().hex[:8]` in run_single_query.
EVAL_SKILL_PATTERN = re.compile(r"_eval_skill_[a-f0-9]{8}")

# Where test skills are placed so the `claude -p` harness auto-discovers them
# into the available_skills list of each spawned subprocess. Tests use a unique
# `_eval_skill_<uuid>` name so multiple in-flight queries never collide, and
# each cleans up its own dir in `finally`.
EVAL_SKILLS_DIR = Path.home() / ".claude" / "skills"


def find_project_root() -> Path:
    """Find the project root by walking up from cwd looking for .claude/.

    Mimics how Claude Code discovers its project root, so the command file
    we create ends up where claude -p will look for it.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def cleanup_stale_eval_skills() -> int:
    """Remove `_eval_skill_*` dirs from prior runs that crashed mid-cleanup.

    Called once at the start of the eval so a previous interrupted run
    doesn't pollute available_skills. Returns count removed.
    """
    if not EVAL_SKILLS_DIR.is_dir():
        return 0
    removed = 0
    for entry in EVAL_SKILLS_DIR.iterdir():
        if entry.is_dir() and entry.name.startswith("_eval_skill_"):
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: Optional[str] = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Writes a SKILL.md clone under ~/.claude/skills/ so it appears in the
    spawned `claude -p` subprocess's available_skills list, then runs the raw
    query. Uses --include-partial-messages to detect triggering early from
    stream events (content_block_start) rather than waiting for the full
    assistant message, which only arrives after tool execution.
    """
    unique_id = uuid.uuid4().hex[:8]
    # Per-query unique name; never matches a real skill so the harness can
    # auto-discover it under ~/.claude/skills/. Original code wrote to
    # .claude/commands/ (a slash-command registry, not a skills registry) so
    # testing config / meta skills consistently measured 0% trigger for a
    # harness reason rather than a description reason.
    clean_name = f"_eval_skill_{unique_id}"
    skill_dir = EVAL_SKILLS_DIR / clean_name
    skill_md = skill_dir / "SKILL.md"

    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        # YAML block scalar keeps multi-line / quoted descriptions safe
        indented_desc = "\n  ".join(skill_description.split("\n"))
        skill_md.write_text(
            f"---\n"
            f"name: {clean_name}\n"
            f"description: |\n"
            f"  {indented_desc}\n"
            f"---\n\n"
            f"# {clean_name}\n\n"
            f"Eval-injected skill for trigger testing.\n"
        )

        cmd = [
            "claude",
            "-p",
            query,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Remove CLAUDECODE env var to allow nesting claude -p inside a
        # Claude Code session. The guard is for interactive terminal conflicts;
        # programmatic subprocess usage is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=project_root,
            env=env,
        )

        triggered = False
        start_time = time.time()
        buffer = ""
        # Track state for stream event detection
        pending_tool_name = None
        accumulated_json = ""

        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if not ready:
                    continue

                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Early detection via stream events
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name in ("Skill", "Read"):
                                    pending_tool_name = tool_name
                                    accumulated_json = ""
                                else:
                                    return False

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if EVAL_SKILL_PATTERN.search(accumulated_json):
                                    return True

                        elif se_type in ("content_block_stop", "message_stop"):
                            if pending_tool_name:
                                return bool(EVAL_SKILL_PATTERN.search(accumulated_json))
                            if se_type == "message_stop":
                                return False

                    # Fallback: full assistant message
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if tool_name == "Skill" and EVAL_SKILL_PATTERN.search(tool_input.get("skill", "")):
                                triggered = True
                            elif tool_name == "Read" and EVAL_SKILL_PATTERN.search(tool_input.get("file_path", "")):
                                triggered = True
                            return triggered

                    elif event.get("type") == "result":
                        return triggered
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            if process.poll() is None:
                process.kill()
                process.wait()

        return triggered
    finally:
        # rmtree the whole skill_dir so the SKILL.md AND any side files drop
        # together; ignore_errors handles "already gone" races from a prior
        # partial cleanup.
        if skill_dir.exists():
            shutil.rmtree(skill_dir, ignore_errors=True)


def run_eval(
    eval_set: List[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: Optional[str] = None,
) -> dict:
    """Run the full eval set and return results."""
    # Sweep any _eval_skill_* leftovers from a previous interrupted run so
    # they don't pollute this run's available_skills list.
    removed = cleanup_stale_eval_skills()
    if removed:
        print(f"Cleaned {removed} stale eval-skill dir(s) from prior run.", file=sys.stderr)

    # The real skill is usually vendored under ~/.claude/skills/ and would
    # shadow the per-query eval clone in the subprocess's available_skills
    # list: the model triggers the real skill, detection sees no
    # `_eval_skill_*` tool call, and recall silently collapses to 0%. Claude
    # Code discovers ANY directory under ~/.claude/skills/ regardless of its
    # name (a `.hidden`-suffixed rename is still listed), so the vendored
    # copy must be MOVED OUT of the skills dir for the duration of the eval,
    # then restored in `finally`.
    real_skill_dir = EVAL_SKILLS_DIR / skill_name
    hidden_path = None
    if real_skill_dir.exists():
        hidden_path = Path(tempfile.mkdtemp(prefix="_skill_eval_hide_")) / skill_name
        try:
            shutil.move(str(real_skill_dir), str(hidden_path))
            print(
                f"Moved vendored skill {skill_name} out of ~/.claude/skills for the duration of the eval.",
                file=sys.stderr,
            )
        except OSError as e:
            hidden_path = None
            print(
                f"Warning: could not hide vendored skill {skill_name} ({e}); eval may measure "
                f"0% recall if the model triggers the real skill instead.",
                file=sys.stderr,
            )

    results = []

    try:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_info = {}
            for item in eval_set:
                for run_idx in range(runs_per_query):
                    future = executor.submit(
                        run_single_query,
                        item["query"],
                        skill_name,
                        description,
                        timeout,
                        str(project_root),
                        model,
                    )
                    future_to_info[future] = (item, run_idx)

            query_triggers: Dict[str, List[bool]] = {}
            query_items: Dict[str, dict] = {}
            for future in as_completed(future_to_info):
                item, _ = future_to_info[future]
                query = item["query"]
                query_items[query] = item
                if query not in query_triggers:
                    query_triggers[query] = []
                try:
                    query_triggers[query].append(future.result())
                except Exception as e:
                    print(f"Warning: query failed: {e}", file=sys.stderr)
                    query_triggers[query].append(False)

    finally:
        if hidden_path is not None and os.path.lexists(str(hidden_path)):
            shutil.move(str(hidden_path), str(real_skill_dir))
            print(f"Restored vendored skill {skill_name}.", file=sys.stderr)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append(
            {
                "query": query,
                "should_trigger": should_trigger,
                "trigger_rate": trigger_rate,
                "triggers": sum(triggers),
                "runs": len(triggers),
                "pass": did_pass,
            }
        )

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def _call_claude(prompt: str, model: Optional[str], timeout: int = 300) -> str:
    """Run `claude -p` with the prompt on stdin and return the text response.

    Prompt goes over stdin (not argv) because it embeds the full SKILL.md
    body and can easily exceed comfortable argv length.
    """
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    # Same CLAUDECODE-strip pattern as run_single_query above.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p exited {result.returncode}\nstderr: {result.stderr}")
    return result.stdout


def _load_description_principles() -> str:
    """Read description-optimization principles from references/skill-writing-principles.md.

    The principles live in a single SSOT markdown file so they can be extended without
    touching code. Extracts the section under the `## description 优化原则` header (up to
    the next `## ` header) and injects it into the improvement prompt.

    Raises if the file or section is missing — the file ships with the skill, so its
    absence means a broken install, not a state to paper over with a hardcoded fallback
    (a fallback would re-duplicate the principles this refactor exists to consolidate).
    """
    path = Path(__file__).resolve().parent.parent / "references" / "skill-writing-principles.md"
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
    test_results: Optional[dict] = None,
    log_dir: Optional[Path] = None,
    iteration: Optional[int] = None,
) -> str:
    """Call Claude to improve the description based on eval results."""
    failed_triggers = [r for r in eval_results["results"] if r["should_trigger"] and not r["pass"]]
    false_triggers = [r for r in eval_results["results"] if not r["should_trigger"] and not r["pass"]]

    # Build scores summary
    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    if test_results:
        test_score = f"{test_results['summary']['passed']}/{test_results['summary']['total']}"
        scores_summary = f"Train: {train_score}, Test: {test_score}"
    else:
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

    text = _call_claude(prompt, model)

    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    if match:
        description = match.group(1).strip().strip('"')
    else:
        # Defensive fallback for when the model forgot the closing tag —
        # without this, a literal `<new_description>` token leaked into the
        # rewritten description (observed 2026-07-12 in yzr-skill-creator
        # iter 3 because the close was missing).
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

    # Safety net: the injected principles state the char hard limit, but if
    # the model blew past it anyway, make one fresh single-turn call that
    # quotes the too-long version and asks for a shorter rewrite. (The old
    # SDK path did this as a true multi-turn; `claude -p` is one-shot, so we
    # inline the prior output into the new prompt instead.)
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
        shorten_text = _call_claude(shorten_prompt, model)
        match = re.search(r"<new_description>(.*?)</new_description>", shorten_text, re.DOTALL)
        if match:
            shortened = match.group(1).strip().strip('"')
        else:
            # Same defensive strip as the primary site (model missed close tag).
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
    random.seed(seed)

    # Separate by should_trigger
    trigger = [e for e in eval_set if e["should_trigger"]]
    no_trigger = [e for e in eval_set if not e["should_trigger"]]

    # Shuffle each group
    random.shuffle(trigger)
    random.shuffle(no_trigger)

    # Calculate split points
    n_trigger_test = max(1, int(len(trigger) * holdout))
    n_no_trigger_test = max(1, int(len(no_trigger) * holdout))

    # Split
    test_set = trigger[:n_trigger_test] + no_trigger[:n_no_trigger_test]
    train_set = trigger[n_trigger_test:] + no_trigger[n_no_trigger_test:]

    return train_set, test_set


def _print_eval_stats(label: str, results: List[dict], elapsed: float) -> None:
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
    print(
        f"{label}: {tp + tn}/{total} correct, precision={precision:.0%} recall={recall:.0%} accuracy={accuracy:.0%} ({elapsed:.1f}s)",
        file=sys.stderr,
    )
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        rate_str = f"{r['triggers']}/{r['runs']}"
        print(
            f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:60]}",
            file=sys.stderr,
        )


def run_optimize_loop(
    eval_set: List[dict],
    skill_path: Path,
    description_override: Optional[str],
    num_workers: int,
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
    project_root = find_project_root()
    name, original_description, content = parse_skill_md(skill_path)
    current_description = description_override or original_description

    # Split into train/test if holdout > 0
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

        # Evaluate train + test together in one batch for parallelism
        all_queries = train_set + test_set
        t0 = time.time()
        all_results = run_eval(
            eval_set=all_queries,
            skill_name=name,
            description=current_description,
            num_workers=num_workers,
            timeout=timeout,
            project_root=project_root,
            runs_per_query=runs_per_query,
            trigger_threshold=trigger_threshold,
            model=model,
        )
        eval_elapsed = time.time() - t0

        # Split results back into train/test by matching queries
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
                _print_eval_stats("Test ", test_results["results"], 0)

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

        # Improve the description based on train results
        if verbose:
            print("\nImproving description...", file=sys.stderr)

        t0 = time.time()
        # Strip test scores from history so improvement model can't see them
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
        )
        improve_elapsed = time.time() - t0

        if verbose:
            print(f"Proposed ({improve_elapsed:.1f}s): {new_description}", file=sys.stderr)

        current_description = new_description

    # Find the best iteration by TEST score (or train if no test set)
    if test_set:
        best = max(history, key=lambda h: h["test_passed"] or 0)
        best_score = f"{best['test_passed']}/{best['test_total']}"
    else:
        best = max(history, key=lambda h: h["train_passed"])
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


def main():
    parser = argparse.ArgumentParser(description="Run eval + improve loop for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override starting description")
    parser.add_argument("--single-round", action="store_true", help="One eval + one improvement, no loop")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument(
        "--max-iterations", type=int, default=5, help="Max improvement iterations (ignored with --single-round)"
    )
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
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description

    results_dir = None
    log_dir = None
    if args.results_dir:
        timestamp = time.strftime("%Y-%m-%d_%H%M%S")
        results_dir = Path(args.results_dir) / timestamp
        results_dir.mkdir(parents=True, exist_ok=True)
        log_dir = results_dir / "logs"

    if args.single_round:
        if args.verbose:
            print(f"Single round — evaluating: {description}", file=sys.stderr)
        eval_output = run_eval(
            eval_set=eval_set,
            skill_name=name,
            description=description,
            num_workers=args.num_workers,
            timeout=args.timeout,
            project_root=find_project_root(),
            runs_per_query=args.runs_per_query,
            trigger_threshold=args.trigger_threshold,
            model=args.model,
        )
        if args.verbose:
            _print_eval_stats(
                "Eval",
                eval_output["results"],
                0,
            )
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=description,
            eval_results=eval_output,
            history=[],
            model=args.model,
            log_dir=log_dir,
            iteration=1,
        )
        output = {
            "mode": "single_round",
            "original_description": description,
            "description": new_description,
        }
        if args.verbose:
            print(f"Improved: {new_description}", file=sys.stderr)
    else:
        output = run_optimize_loop(
            eval_set=eval_set,
            skill_path=skill_path,
            description_override=args.description,
            num_workers=args.num_workers,
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

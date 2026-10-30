"""Eval runner: tasks -> agent -> graders -> results. Standard library only.

    results = run_eval(agent_fn, tasks, num_runs=5, workers=4)   # returns data, prints nothing
    summary = summarize(results)
    print_summary(results)
    save_results(results)
    append_run_log(results, "runs.jsonl", label="baseline", split="dev", model="...")
    print_history("runs.jsonl")
    compare(baseline_results, new_results)                         # flags regressions

``agent_fn(query) -> transcript`` wraps the agent under test without changing it. The transcript is a dict:

    {"final_text": str,
     "tool_calls": [{"name": str, "arguments": dict, "result": str | None}, ...],
     "usage": {"input_tokens": int, "output_tokens": int, "cost_usd": float},   # usage optional
     "turns": int}                                                              # optional

If your agent returns raw Anthropic ``messages``, convert them with ``parse_messages(messages)``.

Two kinds of bad outcome are kept apart everywhere:
  * a failed TASK: the agent finished and a grader said the answer was wrong (status "fail");
  * a failed RUN: the agent crashed, timed out or ran too long (status "error"). The infrastructure
    broke, so no grading happened. Failed runs are excluded from pass rates and reported separately.

Keep ``workers`` below your API rate limits. Threads can't be killed: a timed-out call is abandoned
and may keep running in the background until it returns.
"""

import json
import os
import statistics
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from math import isnan

from graders import GRADER_REGISTRY

REQUIRED_TASK_FIELDS = ("id", "query", "graders")


# --- tasks -------------------------------------------------------------------------------------

def load_tasks(path, split=None):
    """Read a JSONL task file (one task per line). ``split`` filters to "dev" or "holdout"."""
    tasks = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                task = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: not valid JSON ({exc})") from exc
            tasks.append(task)
    validate_tasks(tasks)
    if split:
        tasks = [t for t in tasks if t.get("split", "dev") == split]
    return tasks


def validate_tasks(tasks, registry=None):
    """Raise ValueError listing every problem, before any money is spent."""
    registry = registry or GRADER_REGISTRY
    problems, seen = [], set()
    for i, task in enumerate(tasks):
        where = f"task {i} ({task.get('id', '?')})"
        for field in REQUIRED_TASK_FIELDS:
            if field not in task:
                problems.append(f"{where}: missing {field!r}")
        if task.get("id") in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(task.get("id"))
        if task.get("split", "dev") not in ("dev", "holdout"):
            problems.append(f"{where}: split must be 'dev' or 'holdout'")
        for grader in task.get("graders", []):
            if grader.get("type") not in registry:
                problems.append(f"{where}: unknown grader {grader.get('type')!r}")
            if not grader.get("checks"):
                problems.append(f"{where}: grader {grader.get('type')!r} has no checks")
    if problems:
        raise ValueError("invalid tasks:\n  " + "\n  ".join(problems))


def assign_splits(tasks, holdout_fraction=0.2):
    """Give every task a stable split, so the held-out set doesn't change between runs.

    Tasks are ordered by a hash of their id; the first ``holdout_fraction`` become "holdout".
    Don't look at held-out tasks while fixing the system. Review the split by category afterwards.
    """
    import hashlib

    ordered = sorted(tasks, key=lambda t: hashlib.sha256(t["id"].encode()).hexdigest())
    n_holdout = max(1, round(len(tasks) * holdout_fraction)) if len(tasks) > 1 else 0
    holdout_ids = {t["id"] for t in ordered[:n_holdout]}
    for task in tasks:
        task["split"] = "holdout" if task["id"] in holdout_ids else "dev"
    return tasks


# --- transcripts -------------------------------------------------------------------------------

def parse_messages(messages):
    """Turn an Anthropic-style message list (dicts or SDK blocks) into a transcript dict."""
    final_text, calls = "", []

    def field(block, name, default=None):
        return block.get(name, default) if isinstance(block, dict) else getattr(block, name, default)

    for msg in messages:
        content = msg["content"] if isinstance(msg, dict) else msg.content
        role = msg["role"] if isinstance(msg, dict) else msg.role
        if isinstance(content, str):
            if role == "assistant":
                final_text = content
            continue
        for block in content:
            kind = field(block, "type")
            if role == "assistant" and kind == "text":
                final_text = field(block, "text", "")
            elif role == "assistant" and kind == "tool_use":
                calls.append({"name": field(block, "name"), "arguments": field(block, "input", {}),
                              "id": field(block, "id"), "result": None})
            elif role == "user" and kind == "tool_result":
                for call in calls:
                    if call.get("id") == field(block, "tool_use_id"):
                        call["result"] = field(block, "content")
    turns = sum(1 for m in messages if (m["role"] if isinstance(m, dict) else m.role) == "assistant")
    return {"final_text": final_text, "tool_calls": calls, "turns": turns}


# --- running -----------------------------------------------------------------------------------

def _call_with_timeout(fn, arg, timeout_s):
    box = {}

    def target():
        try:
            box["value"] = fn(arg)
        except BaseException as exc:  # noqa: BLE001 - reported as a failed run
            box["error"] = exc
            box["trace"] = traceback.format_exc()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        raise TimeoutError(f"agent did not finish within {timeout_s}s")
    if "error" in box:
        raise RuntimeError(box["trace"])
    return box["value"]


def run_single_task(agent_fn, task, registry=None, timeout_s=120, retries=2, backoff_s=2.0, max_turns=None):
    """Run one task once. Infrastructure errors are retried, then recorded as status "error"."""
    registry = registry or GRADER_REGISTRY
    base = {"task_id": task["id"], "task_description": task.get("description", ""),
            "query": task["query"], "category": task.get("category", "uncategorized"),
            "split": task.get("split", "dev")}
    start = time.time()
    transcript, last_error = None, None

    for attempt in range(retries + 1):
        try:
            transcript = _call_with_timeout(agent_fn, task["query"], timeout_s)
            last_error = None
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt < retries:
                time.sleep(backoff_s * (2 ** attempt))

    elapsed = round(time.time() - start, 3)
    if last_error is not None:
        return {**base, "status": "error", "passed": None, "error": last_error, "grades": [],
                "metrics": {"time": elapsed}}

    turns = transcript.get("turns")
    if max_turns is not None and turns is not None and turns > max_turns:
        return {**base, "status": "error", "passed": None, "grades": [],
                "error": f"agent used {turns} turns, over the limit of {max_turns}",
                "metrics": {"time": elapsed, "turns": turns}}

    context = {"query": task["query"], "task_id": task["id"]}
    grades = []
    for grader in task["graders"]:
        grader_fn = registry.get(grader["type"])
        for check in grader["checks"]:
            if grader_fn is None:
                grades.append({"type": grader["type"], "check": check, "score": 0,
                               "reason": f"unknown grader {grader['type']!r}"})
                continue
            try:  # a grader that raises fails this check only, never the whole run
                g = grader_fn(transcript, check, context)
                grades.append({"type": grader["type"], "check": check,
                               "score": 1 if g["score"] else 0, "reason": g["reason"]})
            except Exception as exc:  # noqa: BLE001
                grades.append({"type": grader["type"], "check": check, "score": 0,
                               "reason": f"grader error: {type(exc).__name__}: {exc}"})

    passed = bool(grades) and all(g["score"] == 1 for g in grades)
    usage = transcript.get("usage") or {}
    return {**base, "status": "pass" if passed else "fail", "passed": passed, "grades": grades,
            "final_text": transcript.get("final_text", ""),
            "tool_calls": transcript.get("tool_calls", []),
            "metrics": {"time": elapsed, "turns": turns,
                        "tool_calls": len(transcript.get("tool_calls") or []),
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cost_usd": usage.get("cost_usd", 0.0)}}


def run_eval(agent_fn, tasks, num_runs=5, workers=4, registry=None, timeout_s=120, retries=2,
             max_turns=None, model=None):
    """Run every task ``num_runs`` times. Returns data; never prints.

    One run of one task is one unit of work; units run in a thread pool of ``workers``.
    """
    jobs = [(r, t) for r in range(num_runs) for t in tasks]

    def do(job):
        run_idx, task = job
        res = run_single_task(agent_fn, task, registry, timeout_s, retries, max_turns=max_turns)
        res["run"] = run_idx
        return res

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        flat = list(pool.map(do, jobs))

    runs = [[r for r in flat if r["run"] == i] for i in range(num_runs)]
    return {"runs": runs,
            "config": {"model": model, "num_runs": num_runs, "num_tasks": len(tasks),
                       "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}}


# --- summarising -------------------------------------------------------------------------------

def summarize(results):
    """Per-task, per-category and overall numbers. Failed runs are counted apart from failed tasks."""
    flat = [r for run in results["runs"] for r in run]
    by_task = {}
    for r in flat:
        by_task.setdefault(r["task_id"], []).append(r)

    tasks = {}
    for task_id, rs in by_task.items():
        done = [r for r in rs if r["status"] != "error"]
        passes = sum(1 for r in done if r["passed"])
        k = len(done)
        tasks[task_id] = {
            "category": rs[0]["category"], "description": rs[0]["task_description"],
            "runs": len(rs), "failed_runs": len(rs) - k, "passes": passes,
            "pass_rate": passes / k if k else None,
            "pass_at_k": (passes > 0) if k else None,       # passed at least once
            "pass_pow_k": (passes == k) if k else None,     # passed every time
        }

    categories = {}
    for info in tasks.values():
        c = categories.setdefault(info["category"], {"passes": 0, "completed": 0})
        c["passes"] += info["passes"]
        c["completed"] += info["runs"] - info["failed_runs"]
    for c in categories.values():
        c["pass_rate"] = c["passes"] / c["completed"] if c["completed"] else None

    checks = {}
    for r in flat:
        for g in r["grades"]:
            key = f"{g['type']}: {g['check']}"
            c = checks.setdefault(key, [0, 0])
            c[0] += g["score"]
            c[1] += 1

    done = [r for r in flat if r["status"] != "error"]
    times = [r["metrics"]["time"] for r in done]
    n_done = len(done)
    graded = [t for t in tasks.values() if t["pass_rate"] is not None]  # tasks with at least one completed run
    return {
        "tasks": tasks, "categories": categories,
        "checks": {k: v[0] / v[1] for k, v in checks.items()},
        "completed_runs": n_done, "failed_runs": len(flat) - n_done,
        "pass_rate": (sum(1 for r in done if r["passed"]) / n_done) if n_done else None,
        "pass_at_k": (sum(1 for t in graded if t["pass_at_k"]) / len(graded)) if graded else None,
        "pass_pow_k": (sum(1 for t in graded if t["pass_pow_k"]) / len(graded)) if graded else None,
        "cost_usd": round(sum(r["metrics"].get("cost_usd", 0.0) for r in done), 6),
        "p50_s": statistics.median(times) if times else None,
        "k": results["config"]["num_runs"],
    }


def _pct(x):
    return "n/a" if x is None or (isinstance(x, float) and isnan(x)) else f"{x * 100:.0f}%"


def print_summary(results):
    s = summarize(results)
    cfg = results["config"]
    print("=" * 64)
    print(f"EVAL: {cfg['num_tasks']} tasks x {cfg['num_runs']} runs"
          + (f"  |  model {cfg['model']}" if cfg.get("model") else ""))
    print("=" * 64)
    print(f"pass rate     {_pct(s['pass_rate'])}   (over {s['completed_runs']} completed runs)")
    print(f"pass@{s['k']}        {_pct(s['pass_at_k'])}   (tasks that passed at least once)")
    print(f"pass^{s['k']}        {_pct(s['pass_pow_k'])}   (tasks that passed every time)")
    cost = f"${s['cost_usd']:.4f}" if s["cost_usd"] else "n/a"
    p50 = f"{s['p50_s']:.1f}s" if s["p50_s"] is not None else "n/a"
    print(f"cost          {cost}      p50 latency {p50}")
    if s["failed_runs"]:
        print(f"FAILED RUNS   {s['failed_runs']}  (agent crashed or timed out; not counted as wrong answers)")
    if len(s["categories"]) > 1:
        print("\nby category:")
        for name, c in sorted(s["categories"].items()):
            print(f"  {name}: {_pct(c['pass_rate'])}")
    print("\nby task:")
    for task_id, t in s["tasks"].items():
        flaky = " (flaky)" if t["pass_at_k"] and not t["pass_pow_k"] else ""
        err = f"  [{t['failed_runs']} failed run(s)]" if t["failed_runs"] else ""
        print(f"  {task_id}: {t['passes']}/{t['runs'] - t['failed_runs']} passed{flaky}{err}")
    print("\nby check (which part holds the score down):")
    for key, rate in sorted(s["checks"].items(), key=lambda kv: kv[1]):
        print(f"  {_pct(rate):>5}  {key[:90]}")
    shown = set()
    for r in (r for run in results["runs"] for r in run if r["status"] == "error"):
        line = f"run error in {r['task_id']}: {r['error'].strip().splitlines()[-1][:200]}"
        if line not in shown and len(shown) < 3:
            shown.add(line)
            print("\n" + line)


def inspect_task(results, task_id, run_index=0):
    """Print one result in full: grades, tool calls, final answer."""
    r = next((r for r in results["runs"][run_index] if r["task_id"] == task_id), None)
    if r is None:
        print(f"task {task_id!r} not found")
        return
    print(f"[{r['status'].upper()}] {r['task_id']}: {r['task_description']}\nquery: {r['query']}")
    if r["status"] == "error":
        print("run error:\n" + r["error"])
        return
    print(f"answer: {r['final_text']}\n")
    for g in r["grades"]:
        print(f"  {'+' if g['score'] else '-'} {g['type']}: {g['reason']}")
    for c in r["tool_calls"]:
        print(f"  tool {c['name']}({c['arguments']}) -> {str(c.get('result'))[:120]}")


def save_results(results, directory="eval_results", label="eval"):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{label}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    return path


def compare(before, after, min_drop=0.2):
    """Flag tasks whose pass rate fell by at least ``min_drop`` (default 20 points).

    With repeated runs a task "passed before and fails now" shows as a large drop. Returns a list
    of dicts and prints a short report. Tasks present in only one result are listed separately.
    """
    a, b = summarize(before)["tasks"], summarize(after)["tasks"]
    regressions, improvements = [], []
    for task_id in a.keys() & b.keys():
        ra, rb = a[task_id]["pass_rate"], b[task_id]["pass_rate"]
        if ra is None or rb is None:
            continue
        if ra - rb >= min_drop:
            regressions.append({"task_id": task_id, "before": ra, "after": rb})
        elif rb - ra >= min_drop:
            improvements.append({"task_id": task_id, "before": ra, "after": rb})
    print(f"REGRESSIONS ({len(regressions)})")
    for r in sorted(regressions, key=lambda r: r["after"] - r["before"]):
        print(f"  {r['task_id']}: {_pct(r['before'])} -> {_pct(r['after'])}")
    print(f"IMPROVEMENTS ({len(improvements)})")
    for r in improvements:
        print(f"  {r['task_id']}: {_pct(r['before'])} -> {_pct(r['after'])}")
    only = sorted(a.keys() ^ b.keys())
    if only:
        print(f"not in both runs: {only}")
    return regressions


# --- run history -------------------------------------------------------------------------------

def append_run_log(results, path="runs.jsonl", label="", split="dev", model=None, accuracy=None,
                   changed=None, note=""):
    """Append one line in the shared runs.jsonl format. Never rewrites the file."""
    s = summarize(results)
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": label, "model": model or results["config"].get("model"),
        "split": split, "trials": s["k"],
        "pass_rate": None if s["pass_rate"] is None else round(s["pass_rate"], 4),
        "checks": {k: round(v, 4) for k, v in s["checks"].items()},
        "cost_usd": s["cost_usd"],
        "p50_s": None if s["p50_s"] is None else round(s["p50_s"], 2),
        "accuracy": accuracy, "changed": changed or [], "note": note,
    }
    if s["failed_runs"]:
        entry["failed_runs"] = s["failed_runs"]
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def print_history(path="runs.jsonl"):
    """Print the run log so the baseline stays on screen under each new result."""
    if not os.path.exists(path):
        print("(no run history yet)")
        return
    print("\nRUN HISTORY")
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            cost = f"${e['cost_usd']:.2f}" if e.get("cost_usd") else "n/a"
            print(f"  {e.get('ts', '')[:16]}  {e.get('label', ''):<16} {e.get('split', ''):<8} "
                  f"pass {_pct(e.get('pass_rate')):>4}  cost {cost:>7}  {e.get('model') or ''}")

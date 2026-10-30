"""Self-test for the harness templates. No API calls: it uses a stub agent.

Run from this folder:  python selftest.py
"""

import os
import tempfile

import runner
from graders import GRADER_REGISTRY

CATALOG = {"standard plan": 29.0, "add-on": 20.0}


def stub_agent(query):
    """A fake agent: answers price questions from a table, crashes on a magic word."""
    if "CRASH" in query:
        raise ConnectionError("simulated API outage")
    if "total" in query:
        return {"final_text": "The total is $127.00.",
                "tool_calls": [{"name": "get_price", "arguments": {"item": "standard plan"}},
                               {"name": "calculate", "arguments": {"op": "*"}}], "turns": 3,
                "usage": {"input_tokens": 100, "output_tokens": 20, "cost_usd": 0.001}}
    return {"final_text": "The standard plan costs $29.00.",
            "tool_calls": [{"name": "get_price", "arguments": {"item": "standard plan"}}], "turns": 2,
            "usage": {"input_tokens": 80, "output_tokens": 10, "cost_usd": 0.0005}}


TASKS = [
    {"id": "price", "query": "How much is the standard plan?", "category": "lookup",
     "graders": [{"type": "response_contains", "checks": ["29.00"]},
                 {"type": "tool_use", "checks": [{"tool_name": "get_price", "arguments": {"item": "Standard Plan"}}]}]},
    {"id": "total", "query": "What is the total for 3 plans and 2 add-ons?", "category": "multi_step",
     "graders": [{"type": "response_numeric", "checks": [{"value": 127.0, "tolerance": 0.05}]}]},
    {"id": "wrong_expectation", "query": "How much is the standard plan?", "category": "lookup",
     "graders": [{"type": "response_contains", "checks": ["99.00"]}]},
]


def check(name, condition):
    print(("ok   " if condition else "FAIL ") + name)
    if not condition:
        raise SystemExit(1)


def main():
    validate_ok = True
    try:
        runner.validate_tasks(TASKS)
    except ValueError:
        validate_ok = False
    check("valid tasks pass validation", validate_ok)
    try:
        runner.validate_tasks([{"id": "x", "query": "q", "graders": [{"type": "nope", "checks": ["a"]}]}])
        validate_ok = False
    except ValueError:
        pass
    check("unknown grader is rejected before any run", validate_ok)

    results = runner.run_eval(stub_agent, TASKS, num_runs=5, workers=4, retries=0)
    s = runner.summarize(results)
    check("passing tasks pass 5/5", s["tasks"]["price"]["passes"] == 5 and s["tasks"]["total"]["passes"] == 5)
    check("wrong answer is a failed TASK, 0/5", s["tasks"]["wrong_expectation"]["passes"] == 0)
    check("overall pass rate is 2/3", abs(s["pass_rate"] - 2 / 3) < 1e-9)
    check("no failed runs yet", s["failed_runs"] == 0)

    crashing = TASKS + [{"id": "boom", "query": "CRASH now", "category": "infra",
                         "graders": [{"type": "response_contains", "checks": ["x"]}]}]
    results_crash = runner.run_eval(stub_agent, crashing, num_runs=5, workers=4, retries=0)
    s2 = runner.summarize(results_crash)
    check("exception is a failed RUN, not a failed task",
          s2["tasks"]["boom"]["failed_runs"] == 5 and s2["tasks"]["boom"]["pass_rate"] is None)
    check("failed runs are left out of the pass rate", abs(s2["pass_rate"] - 2 / 3) < 1e-9)
    check("failed runs are counted separately", s2["failed_runs"] == 5)

    slow = runner.run_single_task(lambda q: __import__("time").sleep(5), TASKS[0], timeout_s=0.2, retries=0)
    check("timeout is a failed run", slow["status"] == "error")

    over = runner.run_single_task(stub_agent, TASKS[1], max_turns=2, retries=0)
    check("max-turns guard is a failed run", over["status"] == "error")

    def regressed(query):
        out = stub_agent(query)
        if "standard plan" in query:
            out["final_text"] = "I am not sure."
        return out

    worse = runner.run_eval(regressed, TASKS, num_runs=5, workers=4, retries=0)
    flagged = runner.compare(results, worse)
    check("compare flags a task that passed before and fails now", [r["task_id"] for r in flagged] == ["price"])

    def grader_raises(result, check_value, context=None):
        raise RuntimeError("bug in grader")

    registry = dict(GRADER_REGISTRY, broken=grader_raises)
    one = runner.run_single_task(stub_agent, {"id": "g", "query": "How much?", "graders": [
        {"type": "broken", "checks": ["x"]}]}, registry=registry, retries=0)
    check("a raising grader fails one task, not the run", one["status"] == "fail")

    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "runs.jsonl")
        runner.append_run_log(results, log, label="baseline", model="stub")
        runner.append_run_log(worse, log, label="after-change", model="stub", changed=["prompt.txt"])
        with open(log, encoding="utf-8") as f:
            check("run log appends one line per run", len(f.readlines()) == 2)
        runner.print_history(log)
        saved = runner.save_results(results, os.path.join(tmp, "eval_results"))
        check("results are saved", os.path.exists(saved))

    msgs = [{"role": "user", "content": "q"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "get_price", "input": {"item": "a"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "29"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "It is 29."}]}]
    parsed = runner.parse_messages(msgs)
    check("parse_messages extracts text and tool results",
          parsed["final_text"] == "It is 29." and parsed["tool_calls"][0]["result"] == "29" and parsed["turns"] == 2)

    split = runner.assign_splits([{"id": f"t{i}", "query": "q", "graders": []} for i in range(10)])
    check("assign_splits holds out about 20%", sum(t["split"] == "holdout" for t in split) == 2)

    print()
    runner.print_summary(results_crash)
    print("\nall self-tests passed")


if __name__ == "__main__":
    main()

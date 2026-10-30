---
name: build-eval-harness
description: Build and run an evaluation harness for an LLM agent or prompt, with task files, deterministic and LLM-as-judge graders, repeated runs, pass@k and pass^k, a held-out set, and a run history. Use when someone needs a baseline, wants proof that a prompt, tool or model change helped, or asks how to know an AI feature works before shipping.
---

# Build an eval harness

An eval gives you a baseline ("how good is it now?"), a feedback loop ("did this change help, and did it break anything?"), and numbers you can show a client instead of impressions. Models vary from run to run, so every number here comes from repeated runs.

The harness has three parts: **tasks** (what to test), a **runner** (sends each task to the agent and collects what happened), and **graders** (decide whether the agent did the right thing). Templates for all three are in `templates/`. Copy them into the project; don't edit them in place.

## Steps

1. **Wrap the agent, don't change it.** Find its entry point and write `agent_fn(query) -> transcript` around it. The transcript is a dict with `final_text`, `tool_calls` (name, arguments, result) and optional `usage` and `turns`; the header of `templates/runner.py` shows the exact shape, and `parse_messages()` converts a raw Anthropic message list. If the agent only returns text, record the tool calls by wrapping its tool functions, not by editing its logic.

2. **Draft tasks with the user.** Cover: the happy path, edge cases, out-of-scope inputs, and **at least one task for every reported failure**. One task per line in a JSONL file (`templates/tasks.example.jsonl`): `id`, `description`, `query`, `category`, `split`, `graders`. Use `assign_splits()` to hold out about 20% as `holdout`, and don't look at those while fixing. Check the split covers each category.

3. **Choose graders: deterministic first.** Use `response_contains`, `response_numeric` and `tool_use` wherever the answer can be checked by rule. Use `llm_judge` only for open-ended answers. A `tool_use` check proves the answer was grounded in a tool; it should not enforce a fixed call order, because a valid but unexpected path is still correct. See `references/grader-design.md`.

4. **Validate, then estimate spend.** `load_tasks()` validates the file. Before the first run, tell the user how many agent calls you will make (tasks x runs, plus judge calls) and a rough cost, and wait for a yes. Never run paid calls without it.

5. **Run the baseline at 5 or more runs per task.** Report pass rate, pass@k (passed at least once), pass^k (passed every time), cost, p50 latency, and the breakdown by category and by check. A task that passes some of the time is flaky: report it as flaky, not as passing.

6. **Keep infrastructure errors apart from wrong answers.** A crash, timeout or runaway loop is a failed *run*, not a failed *task*; the runner excludes it from pass rates and reports it on its own line. If failed runs are more than a few percent, fix the harness before reading anything into the rates.

7. **Log every run.** `append_run_log()` adds a line to `runs.jsonl` (format in the `diagnose-ai-system` skill's `references/diagnostic-loop.md`), and `print_history()` shows the history under each new result so the baseline stays visible.

8. **Inspect before trusting.** For failures, read the transcript: wrong tool, bad arguments, or a wrong final answer? For passes, ask whether it passed for the right reason. For failures, ask whether the grader is fair. If a grader is wrong, fix the grader deliberately and say so in the notes, then re-run the baseline: the old numbers no longer compare.

## Using the harness for a change

Run the same tasks, the same number of runs, change **one** thing, and run again. `compare(before, after)` flags tasks whose pass rate fell. Done when the target rate holds on the `dev` split and, run once at the end, on the `holdout` split.

The graders and task files are the measuring instrument. The `protect-eval` hook asks for confirmation before they change; don't edit them to move a number.

## Harness hygiene

- Keep `workers` below the API rate limit. Retries use backoff; don't retry in a tight loop.
- The runner takes `timeout_s`, `retries` and `max_turns`; set them to match the agent.
- Don't print API keys, and don't read `.env`. The client comes from the project's own setup.
- Confirm parameter names for structured outputs (used by the judge) with the `claude-api` skill or the API docs; don't rely on memory.

## Files

- `templates/graders.py`: registry and the three deterministic graders.
- `templates/llm_judge.py`: one-criterion-per-call judge with a structured PASS/FAIL verdict.
- `templates/runner.py`: `run_eval`, `summarize`, `print_summary`, `save_results`, `compare`, `append_run_log`, `print_history`, `load_tasks`, `assign_splits`.
- `templates/tasks.example.jsonl`: generic examples; replace them.
- `templates/selftest.py`: runs the templates against a stub agent, no API calls. Run it first (`python selftest.py` from `templates/`) after copying.
- `references/grader-design.md`: choosing graders and writing criteria.

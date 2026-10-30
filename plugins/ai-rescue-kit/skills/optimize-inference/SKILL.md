---
name: optimize-inference
description: Cut the cost and latency of a Claude API workload without losing accuracy. Measures time to first token, total time, output speed and cache-aware cost, then applies round-trip removal, prompt caching, model routing, structured outputs, streaming, parallelism and the Batch API, each gated on an accuracy eval. Use for API spend, slow responses, unit economics or latency SLAs.
---

# Optimize inference

You can't optimize what you can't measure, and you can't bill a client for an improvement you can't prove. Accuracy is the gate: a change that makes the workload faster or cheaper but less accurate isn't an optimization.

This skill owns the **method and the order of levers**. For exact parameter names, model ids and limits, use the `claude-api` skill or the current platform docs; don't restate them from memory.

## 1. Gate first

Confirm an accuracy eval exists for this workload: tasks with known-correct answers, a grader, and a held-out set. If not, hand off to the `build-eval-harness` skill before changing anything. Agree the accuracy threshold with the user (for example, 90% on audited fields) and write it down. Any change that drops accuracy below it is rejected.

## 2. Measure the baseline

Use `templates/benchmark.py` and `templates/cost.py`. Record per unit of work: time to first token (TTFT), total time (TTC), output tokens per second (OTPS), and cost with **all four terms**: plain input, output, cache writes, cache reads. Run enough units to get a median (p50) that isn't one lucky call. Log it in `runs.jsonl` as the baseline.

Spend rule: before any run that makes more than a handful of paid calls, state the number of calls and a rough cost and wait for a yes. A deliberately wasteful baseline can be the most expensive run in the project.

## 3. Audit the code

Read the code that calls the API against the problem list in `references/levers.md`: largest model for everything; a large unchanging prompt re-billed each call; serial calls that could be one; long free-text output; no streaming on user-facing calls; units processed one at a time; interactive and backlog work on the same lane. Write down which apply, with `path:line`. Don't make changes yet.

## 4. Apply in this order, measuring after each

1. Remove unneeded round trips.
2. Cache the unchanging prefix; confirm with `cache_read_input_tokens`.
3. Route by difficulty with a cheap triage pass.
4. Structured output, right-sized `max_tokens`, and effort where the model supports it.
5. Stream user-facing calls.
6. Parallelise, after warming the cache.
7. Move non-interactive volume to the Batch API.

One change at a time, same eval, same units. If accuracy falls under the threshold, revert that change before the next. Finish by running the held-out set once.

## 5. Report

For each lever: what changed, cost per unit, p50, TTFT where relevant, accuracy on dev and holdout, and the run label. Optionally compute the engagement score:

```
if accuracy < threshold: score = 0
else: score = 50 * (baseline_cost / new_cost) + 50 * (baseline_p50 / new_p50)   # baseline indexes at 100
```

Hand the numbers to `client-brief` for anything going to a client. Production cost is the measured cost per unit times a scale factor between your test units and production units; if the scale factor isn't measured, say the annual figures are estimates and print the assumptions.

## Prices

Rates live in one place: `references/pricing.md`, which has a "verified on" date. **Before quoting any figure to a client, re-check the pricing page and update that file.** `templates/cost.py` reads its rates from there, and raises an error for a model that isn't listed rather than guessing.

## Never

- Never optimise without a measured baseline, or report a lever with no before/after.
- Never change the grader, the gold answers or the held-out set to keep accuracy above the threshold. The `protect-eval` hook asks for confirmation if you try.
- Never hard-code your own price table. Never read or print values from `.env`.

## Files

- `references/levers.md`: each lever: when it applies, how to verify, pitfalls.
- `references/pricing.md`: price table with date and source.
- `templates/cost.py`: `calculate_cost(model, usage, batch=False)`; run `python cost.py` for a quick check.
- `templates/benchmark.py`: streaming helper returning TTFT, TTC, OTPS, cost and cache use.

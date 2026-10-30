# Levers, in order

Every lever is gated on the accuracy eval: if accuracy falls below the agreed threshold, the change is rejected however fast or cheap it is. Measure before and after each one and record both in `runs.jsonl`.

For exact parameter names, model ids and limits, consult the `claude-api` skill or the current platform docs. This file owns the method and the order, not the API reference.

## Audit: problems to look for

1. The largest model is used for everything.
2. A large, unchanging prompt (playbook, policy, tool definitions) is paid for in full on every call.
3. Serial calls that could be one (a "summarise first, then extract" step nobody reads).
4. Long free-text output where a structured answer is the deliverable.
5. No streaming on calls a person is waiting for.
6. Units processed one at a time.
7. Interactive and backlog work on the same lane.

## Step 0: delete round trips first

Before you make any call cheaper, remove the ones you don't need. Every serial round trip pays network, input processing and generation time, and chained calls re-pay earlier output as new input. The same applies to tool loops (request, tool call, execute, result, response) and multi-step chains.
- **Applies when:** a step's output only feeds the next step and the next step could do both jobs.
- **Verify:** call count per unit down, accuracy held.
- **Pitfall:** collapsing steps that really do reduce interference (see the prompt-chaining note in `diagnose-ai-system`); check accuracy.

## 1. Prompt caching

Caching is a **prefix match** in the order tools, system, messages. Any change in the prefix invalidates everything after it. Mark the stable block with `cache_control`; the first call pays the write premium, calls inside the lifetime read it back at the discounted rate and skip reprocessing it, which also lowers time to first token.
- **Applies when:** a block of 512+ tokens (check the per-model minimum in `pricing.md`) is identical across calls and calls repeat within the lifetime (5 minutes default; 1 hour is available at a higher write price).
- **Verify:** `usage.cache_read_input_tokens` is non-zero on the second call and cost per call drops. Don't verify by feel.
- **Pitfalls:**
  - Prompts shorter than the model's minimum cacheable prefix silently don't cache.
  - Volatile content (timestamps, request ids, the user's text, the document under review) must come **after** the cached block.
  - A cache entry becomes readable only once the first response starts, so calls fired at the same moment all pay the write price. Warm first, then fan out.
  - Cache-read price is not always 0.1x; take rates from `pricing.md`.
  - If calls are far apart (longer than the lifetime), caching can cost more than it saves because you keep paying write prices.

## 2. Model routing: a portfolio, not one model

Run a cheap triage pass (small model, tiny structured output) and route: routine work to a small or mid model, hard cases to a larger one. Unknown or unparseable triage results should fail safe to the larger path.
- **Applies when:** the workload mixes easy and hard units, and a quality eval can tell them apart.
- **Verify:** accuracy per route on the eval; total cost including the triage call.
- **Pitfall:** the triage rule is itself a prompt: measure how often it misroutes hard cases to the cheap model, since those are the failures you'll never see in an average.

## 3. Output discipline

Output tokens cost several times more than input tokens, and each one adds generation time (TTC is roughly TTFT plus output tokens divided by OTPS).
- Use **structured outputs** so the response is the deliverable: valid JSON from a schema, no preamble, no parsing regex. Put the rubric in the schema's field descriptions so the schema doubles as the spec.
- **Right-size `max_tokens`** to the artifact (a 300-token JSON doesn't need 8,000).
- **Effort setting** trades depth for tokens on models that accept it. It is not accepted on every model: some reject it with an error. Check the docs for the model you use, and don't pass it where unsupported.
- **Pitfall:** a `max_tokens` below the real output length truncates the answer and breaks the JSON. Verify the stop reason.

## 4. Streaming

Stream every user-facing call. TTC is an economics number; TTFT is the experience number. Long outputs also avoid HTTP timeouts when streamed.
- **Verify:** measure TTFT with `templates/benchmark.py`; it should be far below TTC.
- **Pitfall:** streaming doesn't make the whole answer faster, only the first token; don't claim a TTC improvement from it.

## 5. Parallelise, after warming the cache

Independent units can run concurrently. Send one first so the cache is written, then fan out.
- **Verify:** wall-clock for the batch falls, accuracy unchanged, `cache_read_input_tokens` is non-zero on the fan-out calls.
- **Pitfall:** concurrency beyond your rate limit causes retries that cost time; size workers to the limit.

## 6. Two-speed architecture: the Batch API lane

Split by who is waiting. Interactive work (a person watching) stays streamed and fast. Non-interactive volume (backfills, overnight runs) goes to the Batch API at half price in exchange for latency nobody was spending anyway. Most batches complete within an hour.
- **Applies when:** a meaningful share of the work can wait.
- **Verify:** the share that can wait is a client fact, not a guess; record it as an assumption.
- **Pitfalls:** the Batch API is an Anthropic API feature. It isn't available on every cloud platform or through every company gateway; check the platform in use before promising it. Caching in batches is best-effort.

## Reporting each lever

For each lever applied: what changed, accuracy (dev and holdout), p50 latency, TTFT if relevant, cost per unit measured with all four cost terms, and the run label. A lever with no before/after measurement is not reported as an improvement.

## Optional score (from the lab)

```
if accuracy < threshold: score = 0
else: score = 50 * (baseline_cost / new_cost) + 50 * (baseline_p50 / new_p50)   # baseline = 100
```

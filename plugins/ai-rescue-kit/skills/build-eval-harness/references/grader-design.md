# Grader design

## Pick the cheapest grader that can be right

| The answer is… | Use | Check format |
|---|---|---|
| A known string or phrase | `response_contains` | `"29.00"` |
| A number | `response_numeric` | `{"value": 127.0, "tolerance": 0.05}` |
| Grounded in a tool call | `tool_use` | `{"tool_name": "get_price"}` or with `"arguments": {...}` |
| Open-ended: many valid wordings | `llm_judge` | A sentence stating one criterion |

A task passes only if every check of every grader passes.

## Deterministic graders

- **Numbers:** set a tolerance that matches the rounding the agent might use. Check that the number is the *answer*, not just present: a response that lists the inputs can contain the right number by accident.
- **Strings:** pick text that only a correct answer contains. If the check is too loose it passes for the wrong reason (for example, a refusal that repeats the question).
- **`tool_use`:** check the tool name only, unless the argument is what you are testing (for example, whether the agent resolved a synonym to the right key). Never grade a fixed sequence of calls.
- **Negative cases:** to check the agent did *not* do something (invent a price, call a tool it shouldn't), use an `llm_judge` criterion worded as a positive statement ("Response does not state a price for the item"), or add a deterministic grader that you write for it.

## LLM judge

- **One criterion per check.** Don't ask one call to judge several things; list several checks instead. A criterion that contains "and" is probably two.
- **Write criteria the answer can be tested against:** "Response mentions that prices can be looked up" is testable; "Response is helpful" is not.
- **Structured verdict:** an enum (PASS/FAIL) plus a one-sentence reason, so there's no free-text parsing.
- **Calibrate:** grade ten answers by hand, run the judge on the same ten, and read every disagreement. Adjust the criterion, not the answer.
- **Cost:** one call per check per run. Use a small model, and count these calls in the spend estimate.
- Don't let the agent under test grade itself.

## Task design

- Cover the **categories** the system will see, not just the ones you've seen it fail on. Protect the cases that already work; fixes for hard cases often break easy ones.
- Include at least one task for each failure anyone has reported, using the reporter's wording.
- Include out-of-scope inputs where the correct behaviour is to decline or say "not found".
- Keep tasks independent: no task depends on state left by another.
- Write the expected answer from the source of truth (the data, the policy), not from what the agent said.

## Reading results

- **Flaky vs reliably broken:** pass@k high but pass^k low means flaky. Both low means broken. Fix the broken ones first.
- **Spread:** with 5 runs, a change of one run is noise. Treat a change as real when the movement is clearly larger than the spread between repeated baselines; if unsure, run the baseline twice.
- **Overfitting:** a rate that rises on `dev` but not on `holdout` means the fix was tuned to the cases you looked at.

## Going further

Pass@k and pass^k with larger k, confidence intervals, efficiency graders (fewest tool calls), parameter sweeps, caching unchanged tasks, and live progress are all worthwhile when the harness is used often. Established eval frameworks (hosted or open source) may be a better home for a harness that outgrows this one; migrate the task files, not the habits.

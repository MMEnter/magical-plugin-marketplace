---
name: client-brief
description: Turn measured diagnostic or optimization results into a one-page client brief or steering-committee slide, covering what broke in plain language, the fix, before and after numbers, scope, and the "why not just use a bigger model?" objection. Use when writing findings up for a client, an executive, or leadership.
---

# Client brief

Turns what the team measured into something a client's leadership can act on. The brief is only as good as the evidence behind it: every number comes from a recorded run.

## Before writing

Read `rescue-notes.md` and `runs.jsonl` in the project folder. If either is missing, say so and ask where the findings are. Don't write a brief from memory or from the conversation alone.

State the audience in one line ("Written for: the client's VP of Operations") and check it with the user if it isn't clear. A steering committee, a technical lead and a CFO need different amounts of detail.

## Rules

1. **Every number names its run.** Write it as `31% (run: fix-2)`, using the `label` from `runs.jsonl`. If a section needs a number and no run has it, leave a visible gap such as `[GAP: no run measures cost per ticket after the fix; run the dev set with cost logging]` and say what run would fill it. **Never estimate or round into a claim the data doesn't support.**
2. **Plain language for client sections.** No "system prompt", "tool schema", "routing", "tokens" or "cache" without a one-line explanation in everyday words. Describe what the system did wrong, not the component's name.
3. **Answer the objection with the team's own bigger-model run.** "Why not just pay for a better model?" is answered with that run's rate and cost next to the fixed system's. If the log has no bigger-model run, leave the section open and ask for that run; don't argue it from general knowledge.
4. **Credit the diagnosis to the team.** Never write "Claude fixed it" or "the AI found it". The team decided what to look at, judged the evidence and chose the fix.
5. **Before and after use the same measure.** Same tasks, same number of runs, same split. If they differ, say so beside the numbers.
6. **Hold-out results are the proof.** If the log has a `holdout` run, headline that; if not, flag that the fix is not yet shown to generalise.
7. **For slides, print the assumptions** (volume, scale factor, share of interactive vs batch work, fee) next to the numbers they feed. Assumptions the user hasn't given are gaps, not defaults.
8. **Don't include** key values, client data from traces beyond what the client has already seen, or internal tool names that mean nothing to them.

## Steps

1. Read the two files; list the runs you will cite (label, split, rate, cost).
2. Fill `templates/brief.md` section by section. Mark each gap.
3. Read the draft as the client: any term they would have to ask about gets a plain-words explanation.
4. Check every number against `runs.jsonl` and say you did.
5. If the work was about cost or latency, also fill `templates/steering-slide.md`.
6. Finish with a list of gaps and the run that would fill each.

## Narrative order

Problem, diagnosis, fix, proof, prevention. The strongest brief doesn't say "we fixed the prompt and the score went up". It says what structural failure was found, why the chosen technique addresses that failure, and what changed in each failure category.

## Templates

- `templates/brief.md`: one page, fixed sections.
- `templates/steering-slide.md`: before/after table with an assumptions block.

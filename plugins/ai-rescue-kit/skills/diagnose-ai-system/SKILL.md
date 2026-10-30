---
name: diagnose-ai-system
description: Diagnose why an LLM app, prompt, or multi-agent system gives wrong, invented, or incomplete answers, using symptom, hypotheses, line-cited evidence and a scoped fix, proven by re-measuring. Use when an AI feature fails in production, closes tickets it didn't resolve, misroutes, hallucinates fields, or someone asks whether a bigger model would fix it. Not for ordinary code bugs.
---

# Diagnose an AI system

The client usually suspects the model. Most of the time the cause is in the system around it: prompts, tool definitions, routing, context, or the code that wraps the model. Your job is to find the cause with evidence, fix it, and prove the fix by measuring.

Work the loop in order. Do not skip ahead to a fix.

## 1. Mode

Default is **direct**: do the work and report what you find.

Switch to **coaching** when the user asks to be coached, or when a `CLAUDE.md` in the working folder says the folder is a training exercise. In coaching mode, show evidence and ask questions, and let the user name the root cause. Don't hand over the answer. If a `CLAUDE.md` restricts which files may be edited, follow it.

Say which mode you are in, in one line, before you start.

## 2. Symptom

Write the complaint as one sentence in the reporter's own words, before opening any file. Don't reframe it or add your interpretation. Keep who said it and where (email, ticket, chat) so the brief can cite it.

## 3. Hypotheses

Write **at least three** before reading any artifact, and rank them. Naming them first commits you to a position, so the evidence can overturn it. Start from `references/failure-patterns.md`, and add your own.

Each hypothesis is one line: what is wrong, and what you would expect to see in the artifacts if it were true.

## 4. Baseline

Find or build a repeated-run measure of the failure. Never judge from one run: an agent's choices vary from run to run, so read the rate, not any single attempt.

- If a measure exists, run it and record it.
- If none exists, hand off to the `build-eval-harness` skill. If the user has no API budget for runs yet, say so and continue with evidence only, marking every conclusion "not yet measured".

Before any run that calls a paid API more than a handful of times, say how many calls and the rough cost, and wait for a yes. Record every run in `runs.jsonl` using the shared format in `references/diagnostic-loop.md`.

## 5. "Is it the model?"

Offer to run the same eval on a larger model, with nothing else changed. Record the rate and the cost. Whichever way it goes, it is evidence for the client brief: either the bigger model did not fix it (the cause is elsewhere), or it did at a cost that can be compared with the fix.

This run tests the theory. It is never the fix. Do not propose a model change as the remedy unless the user explicitly asks for that option to be costed.

## 6. Evidence

Read in this order, because each one explains the next:

1. Execution traces: what actually happened, step by step.
2. System prompts: what each agent was told to do.
3. Tool definitions: what the model could see, and when it would use each tool.

If the traces or run logs are long, delegate to the `trace-analyst` subagent (see below) instead of reading them in this conversation.

For each hypothesis, quote the exact line that confirms or rules it out, with `path:line`. "The prompt seems off" is not evidence. A hypothesis with no quoted line stays **open**. Mark each one confirmed, ruled out, or open.

Also look at variation: if the same input is handled differently across runs, say which decisions differ and how often.

## 7. Fix

Write each fix as: **file, line, change, the failure it prevents**. If you can't name the file and line, go back to step 6.

- Change one thing at a time, so you know which change moved the number.
- Fixes belong in prompts, tool definitions, routing, and code around the model.
- Never fix by changing the graders, the gold answers, the scoring code or the held-out set. That changes the measurement, not the system. The `protect-eval` hook will ask for confirmation if you try.
- Never fix by changing the model.

## 8. Re-measure

Re-run the same eval after every change, with the same number of runs. If the rate does not move, the theory was wrong or half right: go back to the evidence. Don't pile on a second change.

Done when the target rate holds, run after run, **and** on the held-out set. A fix that only works on the cases you looked at is overfitting. Run the held-out set once, when the fix is final; don't tune against it.

## 9. Record

Append to `rescue-notes.md` using the structure in `references/diagnostic-loop.md`, then offer the `client-brief` skill.

## Delegating long traces

Use the `trace-analyst` subagent when traces, transcripts or run logs are too long to read here. Give it: the symptom sentence, the numbered hypotheses, and the paths to traces, prompts, tool files and run logs. It returns a timeline, a verdict with quotes for each hypothesis, variation across runs, and leads you didn't ask about. It does not propose fixes; deciding the root cause stays with you and the user. Check its quotes against the files for any hypothesis you rely on.

## Reference files

Load only when needed:

- `references/diagnostic-loop.md`: the four steps with question and output of each, the `runs.jsonl` and `rescue-notes.md` formats, and a worked example.
- `references/failure-patterns.md`: starting list of hypotheses, with symptom, where to look and typical fix.
- `references/fix-techniques.md`: which technique fits which failure, and when not to use it.

## Rules

- Every claim about a cause cites `path:line` and quotes the line.
- Never read, print or write values from `.env` or any credentials file. Checking that a variable name exists is fine.
- Give the team credit for the diagnosis in anything written for a client.

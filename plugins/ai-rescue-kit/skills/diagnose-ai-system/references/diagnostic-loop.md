# The diagnostic loop

A repeatable way to diagnose any AI system failure, from one broken prompt to a many-agent pipeline.

| Step | Question | Output |
|------|----------|--------|
| Symptom | What is the reporter actually saying is wrong? | One sentence, their words |
| Hypothesis | What could cause this? (3 minimum, before looking at artifacts) | Ranked list, each with what you'd expect to see |
| Evidence | Which hypothesis does each artifact confirm or rule out? | A quoted line with `path:line` per hypothesis |
| Recommendation | What change, in which file, prevents this failure? | File, line, change, failure prevented |

## Step by step

**Symptom.** Don't reframe it. "Customers say the assistant tells them a refund is on its way when nothing was filed" is a symptom. "The agent hallucinates" is an interpretation.

**Hypothesis.** Commit before you look. The point is to find out where your reflexes are strong or weak, and to avoid reading every artifact until one of them seems to fit. Include at least one hypothesis that is not about the prompt (a tool, routing, context, or code around the model), and one that says the model really is not capable enough, so that it gets tested rather than assumed.

**Evidence.** Traces first, then system prompts, then tool definitions. A trace shows what happened; the prompt shows what the agent was told; the tool definitions show what it could do. Quote each line. If you can't tie a hypothesis to a line, it is not confirmed.

**Recommendation.** "Improve the prompt" is not a recommendation. A recommendation names the file, the line, the change, and the failure it prevents. Then make the change and re-measure. The step isn't done until the rate moves.

## Shared files

All the skills in this plugin read and write two files in the project folder.

### `runs.jsonl`: the run log

One JSON object per run, appended, never rewritten. Create the file if it doesn't exist.

```json
{"ts": "2026-10-30T14:02:11Z", "label": "baseline", "model": "model-id-used",
 "split": "dev", "trials": 5, "pass_rate": 0.2,
 "checks": {"check_a": 0.2, "check_b": 0.2},
 "cost_usd": 0.55, "p50_s": 11.4, "accuracy": null,
 "changed": ["system-prompt.txt"], "note": "first run, no changes"}
```

| Field | Meaning |
|-------|---------|
| `ts` | UTC time, ISO 8601 |
| `label` | Short name for the run: `baseline`, `bigger-model`, `fix-1`, `holdout-final` |
| `model` | The model the system under test used for this run |
| `split` | `dev` or `holdout` |
| `trials` | Runs per task |
| `pass_rate` | Share of trials that passed every check |
| `checks` | Pass rate per named check, so you can see which part holds the score down |
| `cost_usd`, `p50_s` | Total cost of the run; median seconds per unit of work |
| `accuracy` | Share of audited fields correct, when the workload has a gate; otherwise `null` |
| `changed` | Files changed since the previous run |
| `note` | Anything a later reader needs |

If the project already keeps a run log in a different shape, don't rewrite it. Write new entries in this shape to a file with a different name, and say so in `rescue-notes.md`.

### `rescue-notes.md`: the findings file

Headed sections, in this order:

1. **Symptom**: the one sentence, with who said it and where.
2. **Hypotheses**: ranked, each with status (open, confirmed, ruled out).
3. **Evidence**: per hypothesis, the quoted line with `path:line`.
4. **Fixes**: file, line, change, failure prevented, and the run label that proved it.
5. **Open questions**: anything you could not settle, and what run or artifact would settle it.

The client brief reads only this file and the run log, so anything that matters has to be in one of them.

## Worked example (a made-up system)

*A meeting-notes assistant. Participants complain that action items are assigned to the wrong people.*

**Symptom.** "The notes say Dana owns the budget review and she wasn't even in the meeting." (Reported by the programme manager, in a support thread.)

**Hypotheses, written before opening any file:**

1. The prompt asks for an owner for every action item, so when none is stated the model supplies one. *Expect: an instruction to always fill the owner field.*
2. The attendee list is not in the model's context, so it cannot check names. *Expect: the call that builds the prompt leaves out attendees.*
3. A names-extraction step runs separately and its output is dropped before the summary step. *Expect: two prompts, and the second does not receive the first's output.*
4. The model is too weak for this. *Expect: errors that a larger model avoids, with the same prompt.*

**Baseline.** Ten meetings, five runs each; a run passes when every action-item owner appears in that meeting's attendee list. 22% pass.

**Is it the model?** Same eval on a larger model: 26% pass, at about four times the cost. Hypothesis 4 is not supported.

**Evidence.** Trace for meeting 3: the owner for "budget review" is "Dana", and no attendee list appears in the request. Prompt line 14: *"Every action item must have an owner."* Hypotheses 1 and 2 are confirmed; hypothesis 3 is ruled out (one prompt only, line 1).

**Fix 1** (one change): `prompt.txt:14`, replace the line with *"Give an owner only if a participant is named as taking it; otherwise write 'unassigned'."* Re-run: 41% pass. The rate moved, so the theory was right but incomplete.

**Fix 2:** add the attendee list to the request in `build_request()` at `notes.py:52`. Re-run: 88% pass. Hold-out set: 85%.

**Record** both fixes with their run labels in `rescue-notes.md`.

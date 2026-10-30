# ai-rescue-kit

A Claude Code plugin that packages the Partner Basecamp engagement method: **diagnose** a failing AI system, **prove** the fix with an eval, **cut cost and latency** without losing accuracy, and **write it up** for the client.

Version 0.1.0.

## What's in it

| Component | Type | Use it when |
|---|---|---|
| `diagnose-ai-system` | skill | An AI feature gives wrong, invented or incomplete answers, or someone asks "would a bigger model fix it?" |
| `build-eval-harness` | skill | You need a baseline, or proof that a prompt, tool or model change helped |
| `optimize-inference` | skill | API spend, slow responses, unit economics, caching, routing, batch |
| `client-brief` | skill | Writing findings up for a client, executive or steering committee |
| `trace-analyst` | subagent | Called by the diagnose skill (or directly) to read long traces and logs and return line-cited evidence |
| `protect-eval` | hook | Runs on every edit; asks for confirmation before grader, gold, hold-out or scoring files change |

The skills hand off through two files in your project folder: `runs.jsonl` (the run log) and `rescue-notes.md` (findings). Formats are in `skills/diagnose-ai-system/references/diagnostic-loop.md`.

## Install

Try it for one session without installing:

```
claude --plugin-dir ./ai-rescue-kit
```

From the marketplace:

```
claude plugin marketplace add MMEnter/magical-plugin-marketplace
claude plugin install ai-rescue-kit@magical-plugin-marketplace
```

Check the files with `claude plugin validate ./ai-rescue-kit`.

Python 3.10 or newer is needed for the hook and the templates (standard library only; the Anthropic SDK is needed only by `llm_judge.py` and `benchmark.py`, and comes from your project).

## Direct answers or coaching

The skills work **directly** by default: they do the work and report. They switch to **coaching** (show evidence, ask questions, let you name the root cause) when:

- you ask to be coached ("coach me through this"), or
- a `CLAUDE.md` in the working folder says the folder is a training exercise.

## Protecting the eval: `.eval-protected`

The `protect-eval` hook asks for confirmation (it never blocks) when Claude tries to edit a file that matches a protected pattern, because changing a grader changes the measurement, not the system. Confirm only when the grader itself is wrong.

Defaults: `**/*grader*`, `**/*judge*`, `**/gold*`, `**/*holdout*`, `**/tasks*.jsonl`, `**/eval_results/**`, `**/runs.jsonl`, `**/.eval-protected`.

To change them for a project, create `.eval-protected` in the project root: one glob per line, `#` for comments. A line starting with `!` removes a default. `*` stays within a folder name; `**/` spans folders; a pattern also covers everything under a folder it matches.

```
# files that hold graders and tickets alongside the tool code
path/to/scoring_script.py
# this project's judge files are ordinary code
!**/*judge*
```

The hook fails open: if it errors for any reason it logs to stderr and lets the edit through.

**Windows note.** Hook commands run through a POSIX shell where there is one (macOS, Linux, Windows with Git Bash). The shipped command is `python3 … || python …`. On Windows **without** Git Bash, hooks run through PowerShell 5.1, which has no `||`, so the hook errors and does nothing (a non-blocking error), and edits to protected files go through unprompted. Installing Git for Windows (which includes Git Bash) avoids this. See "Known gaps" below.

## Costs

Skills that run an eval or a benchmark state the number of paid API calls and a rough cost first, and wait for a yes. No component reads, prints or writes values from `.env`.

## Prices

`skills/optimize-inference/references/pricing.md` carries a "verified on" date. Re-check the pricing page before quoting any figure to a client.

## Not included

Exercise scenarios, client emails, tickets, contracts and answers from the Basecamp exercises. The plugin reimplements the patterns only. Check with the Basecamp owners before publishing it outside the firm.

## Checks

```
python skills/build-eval-harness/templates/selftest.py     # harness, no API calls (run from templates/)
python -m unittest test_protect_eval -v                    # hook matcher (run from hooks/)
claude plugin eval . --trust-plugin --json results.json    # trigger tests (costs API calls)
```

## Known gaps

- The Windows-without-Git-Bash hook launcher is not settled: exec form (`command` plus `args`) avoids the shell but needs one interpreter name, and the name differs between Windows (`python` or `py`) and macOS (`python3`). Test on a Windows machine without Git Bash, then choose.
- Fixture runs against the exercise folders are a manual release check, not part of the eval suite.

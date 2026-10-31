---
name: eval-plugin
description: Write, run and debug a plugin's `claude plugin eval` suite to the house eval standards - realistic cases, outcome graders, a negative case, eval-config.json - including tuning a skill description that isn't triggering. States the cost before any multi-case run. Use when the user asks to add or fix evals, test a plugin, check whether a skill fires, run the eval gate, or work out why a case fails. Not for reviewing the plugin itself (review-plugin).
metadata:
  version: "0.3.0"
---

# Plugin evals

Follow `${CLAUDE_PLUGIN_ROOT}/references/eval-standards.md`; case and config templates are in `${CLAUDE_PLUGIN_ROOT}/references/scaffold-templates.md`.

## Write a suite

1. Read every skill's description. For each skill, write at least one case whose prompt is something a real user would type, not a copy of the description or a SKILL.md example (HR-E07). Cover at least two different input shapes for the plugin's main skill.
2. Add one negative case: a request close to the plugin's subject that should not fire any of its skills, graded with the negative template (`tool_used`, `min: 0`, `max: 0`, `arm: both`).
3. Give every case an outcome grader: `regex` or `file_exists` when a pattern or created file proves the result, `llm` with concrete checkable claims otherwise. A `tool_used: Skill` trigger grader may sit alongside, never alone.
4. Tools follow graders: if a grader needs a created file, allow `Write` (and `Bash` if a script writes it) in that case and add the tool to `allow_tools` in eval-config.
5. Fixtures that look risky (secrets, malicious archives, broken plugins) are generated at run time by a `scaffold.sh` that the case declares in `case.yaml` (`context.scaffold_script`), never committed. A `scaffold.sh` next to a `prompt.md` never runs. Set `scaffold: true` in eval-config only for suites the marketplace owner wrote.
6. Plan `evals/eval-config.json` from the template with one or two quick smoke cases.
7. Show the user the list of cases (slug, prompt, graders, allowed tools) and the files you will create, and wait for approval before writing anything (HR-P07). Then write them.

Validate the suite before spending anything:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py" "<plugin>"
```

All HR-E findings should be gone.

## Run

Always show the cost first:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/eval_gate.py" "<plugin>" --mode pr --dry-run
```

Tell the user the number of agent runs; each is a billed Claude session. Get a yes, then run without `--dry-run` (add `--yes` so the script doesn't prompt again). Pilot with `--mode pr`; run `--mode full` (with a no-plugin baseline) only when the pilot passes or the user asks.

Pass `--trust` only if the user confirms they trust this plugin's code: the eval loads its skills, hooks and MCP servers on this machine.

## Debug a failing case

1. Open the gate file `evals/results/gate-<ts>.json` and the eval JSON it names. For the failing case, read each grader's `explanation` and open the run's `tracePath`.
2. Classify: the skill didn't fire, it fired but did the wrong thing, the grader is wrong, or the case can't pass with the tools it's allowed.
3. If the skill didn't fire, compare the prompt's wording with the description. Rewrite the description to name what the user said, keeping it under 1024 characters and keeping the "Not for" line accurate so neighbouring skills don't start firing. Re-run only that case.
4. Never loosen a grader just to pass. If a grader is wrong, say why and fix it so it still checks the outcome.

A score that jumps without a matching change in the plugin is suspect: spot-check the transcript before trusting it.

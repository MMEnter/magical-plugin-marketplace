# Eval standards

How a plugin's `claude plugin eval` suite is laid out, what `evals/eval-config.json` holds, and what `eval_gate.py` checks. HR-E rules point here.

## Layout

```
evals/
├── eval-config.json          gate settings (below)
├── <case-slug>/
│   ├── prompt.md             frontmatter: max_turns, timeout_seconds, allowed_tools, runs; body = the user's request
│   └── graders/
│       ├── <outcome>.md      regex, file_exists or llm: checks the result
│       └── <fired>.md        tool_used: display-only trigger check
├── mocks/<server>/<tool>.md  stand-ins for MCP tools the flow calls (never hit real services)
└── results/                  run output, git-ignored (HR-E06)
```

A case that needs starting files must be written as `case.yaml`, because only `case.yaml` can declare a scaffold script (`context.scaffold_script: scaffold.sh`, a bash file in the case folder that runs in the sandbox working folder before the agent starts, and only when eval-config says `scaffold: true`). A `scaffold.sh` that isn't declared never runs. In `case.yaml`, the prompt goes in `execution.prompt`, a regex grader's pattern in `pattern`, and an llm grader's rubric in `criteria`. The validator reads both formats.

## Grader types

| type | Use for | Key frontmatter |
|---|---|---|
| `regex` | text in the last message, the trace, the created-file list, or a created file | `target: last_message \| trace \| files \| {source: file, path}`, `match: contains \| not_contains \| count:N` |
| `file_exists` | a file the run created (pre-existing files never count) | `path: <glob>`, `exists: true \| false` |
| `llm` | anything a pattern can't capture; write the body as concrete checkable claims | `focus`, `weight` |
| `tool_used` | whether a tool or skill fired | `tool`, `input_match`, `min`, `max`, `arm: with-only \| both` |
| `tool_order` | one tool before another | `before`, `after` |

Rules of thumb:

- Every case has at least one outcome grader (`regex`, `file_exists` or `llm`). A `tool_used: Skill` grader is a display-only trigger check under ablation and never moves the score (HR-E03).
- A should-not-fire case uses `tool_used`, `tool: Skill`, `min: 0`, `max: 0`, `arm: both` (HR-E04).
- Tools follow graders: a grader that needs a created file means the case allows `Write` (and `Bash` if a command writes it).
- `regex` graders use JavaScript regular expressions: set `flags: i` for case-insensitive matching; inline `(?i)` makes the grader throw.
- No absolute paths or `~/` in prompts or graders; cases run in a sandbox working folder.
- A grader that checks a script ran should match the Bash command in the trace (`"command"\s*:\s*"(?:[^"\\]|\\.)*script\.py`, which allows the escaped quotes the trace stores), not just the script's name, which also appears in the skill text Claude read.
- Fixtures are synthetic. Generate risky test inputs from a script at scaffold time rather than committing them (HR-E08).

## eval-config.json

```json
{
  "threshold": 0.8,
  "runs_full": 3,
  "smoke_cases": ["review-runs-mechanical-checks"],
  "judge_model": "sonnet",
  "allow_tools": ["Bash", "Write"],
  "scaffold": true,
  "max_cost_usd": 15
}
```

| Key | Meaning |
|---|---|
| `threshold` | Minimum score (0-1] every case must reach in the with-plugin arm. |
| `runs_full` | Runs per case in `--mode full`; at least 3. |
| `smoke_cases` | Case names run in `--mode pr` (one run each, no baseline). |
| `judge_model` | Model for `llm` graders. Never the model under test. |
| `allow_tools` | Operator grants passed as `--allow-tools` (Bash, Write, Edit, WebFetch, mcp__*). |
| `scaffold` | Whether case `scaffold.sh` scripts run. Set true only for suites the marketplace owner wrote. |
| `max_cost_usd` | Hard cost ceiling for one gate run. |

## What the gate checks

`eval_gate.py PLUGIN --mode pr|full`:

1. Runs `validate_plugin.py`; any open critical finding fails the gate before a model call is made.
2. States the expected cost (cases × runs × arms) and asks for confirmation unless `--yes` is passed.
3. Runs `claude plugin eval` with the config's settings: `--mode pr` uses the smoke cases, 1 run, no baseline; `--mode full` uses every case, `runs_full` runs, with a no-plugin baseline arm.
4. Fails if the result is `partial`, if the plugin did not load, if any case is missing from the result, if any run has an error (timeouts and rate limits are reported as such), or if any case scores below `threshold`.
5. Writes `evals/results/gate-<timestamp>.json` (schema in `finding-schema.md`) with the tree hash of the files it tested. `stamp.py write` accepts it only when that hash still matches.

Evals run on the marketplace owner's machine and are billed as real model calls. CI never runs them; it trusts the stamp.

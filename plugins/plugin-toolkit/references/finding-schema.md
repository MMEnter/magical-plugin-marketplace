# Finding schema

Every producer of findings uses this one JSON shape: `validate_plugin.py --json`, each analyst agent, and `finding-synthesizer`. `render_report.py` and `stamp.py` read it. Nobody writes a report by hand (HR-P01, HR-P03).

## Findings file

```json
{
  "schema_version": 1,
  "producer": "validate_plugin | <analyst-name> | finding-synthesizer",
  "mode": "mechanical | review | security",
  "plugin": "exam-podcast",
  "plugin_version": "0.2.0",
  "source": {
    "type": "local | github | zip | marketplace",
    "location": "plugins/exam-podcast or https://github.com/o/r",
    "sha": "40-char commit SHA, or null",
    "tree_hash": "sha256 from stamp.py, or null"
  },
  "generated_at": "2026-10-31T12:00:00Z",
  "findings": [ /* Finding objects, below */ ],
  "summary": { "critical": 0, "major": 2, "minor": 5 }
}
```

`summary` counts only findings whose `status` is `open`.

## Finding

```json
{
  "id": "F-003",
  "rule": "HR-S05",
  "severity": "major",
  "kind": "judgment",
  "analyst": "skill-quality-analyst",
  "status": "open",
  "file": "skills/exam-podcast/SKILL.md",
  "line": 3,
  "title": "Description has no trigger phrases",
  "evidence": "description: 'Podcast generator.' (17 characters, no 'Use when')",
  "fix": "Say what it produces and list the requests that should trigger it.",
  "patch": "--- a/skills/...\n+++ b/skills/...\n@@ ...",
  "escalation": null,
  "dissent": []
}
```

| Field | Rules |
|---|---|
| `id` | `F-` plus 3 digits, unique within the file. The synthesizer renumbers the merged list. |
| `rule` | An ID from `plugin-guidelines.md` or `security-checklist.md`. A finding with no rule is not a finding; raise it as a note to the user instead. |
| `severity` | At least the rule's severity. Raising it needs an `escalation`. |
| `kind` | Copied from the rule. |
| `analyst` | Producer name: `validate_plugin` or the agent name. |
| `status` | `open`, `fixed` (a patch was applied and re-validation passed), `waived` (rule ID is in `waivers.md` and the rule is waivable), or `disputed` (the synthesizer could not reconcile analysts; the user decides). |
| `file`, `line` | Path relative to the plugin root; `line` may be null. |
| `evidence` | The exact text, value or command output that shows the problem. Quote it; don't paraphrase. |
| `fix` | One or two sentences a person could act on. |
| `patch` | A unified diff per `patch-spec.md`, or null when the fix needs a human decision. |
| `escalation` | Null, or `{ "from": "major", "to": "critical", "reason": "..." }`. Used when an analyst re-raises a mechanical finding to escalate it. |
| `dissent` | Analyst names that disagreed with this finding, each with a one-line reason. Kept, never averaged away (HR-P05). |

## Eval gate result

`eval_gate.py` writes `evals/results/gate-<timestamp>.json`:

```json
{
  "schema_version": 1,
  "plugin": "plugin-toolkit",
  "tree_hash": "sha256:...",
  "mode": "pr | full",
  "passed": true,
  "threshold": 0.8,
  "cases": [{ "name": "review-runs-mechanical-checks", "score": 1.0, "baseline": 0.0, "status": "ok" }],
  "problems": [],
  "cost_usd": 1.84,
  "finished_at": "2026-10-31T12:30:00Z"
}
```

`status` per case is `ok`, `error`, `timeout`, `rate_limited` or `missing`. Any status other than `ok` fails the gate, whatever the score.

## Stamp

`stamp.py` writes `.toolkit/stamp.json` inside the plugin (or `.toolkit/pinned/<name>.json` in the repo root for a pinned upstream entry):

```json
{
  "schema_version": 1,
  "plugin": "exam-podcast",
  "version": "0.2.0",
  "origin": "native | vendored | pinned",
  "tree_hash": "sha256:...",
  "upstream": { "repo": "owner/repo", "sha": "..." },
  "review_report": "rv-20261031-1a2b3c4d",
  "security_report": "sc-20261031-5e6f7a8b",
  "open_criticals": 0,
  "eval_gate": { "result": "passed | waived", "mode": "full", "tree_hash": "sha256:...", "finished_at": "..." },
  "waivers": ["HR-P01", "HR-E01"],
  "toolkit_version": "1.0.0",
  "stamped_at": "2026-10-31T13:00:00Z"
}
```

`upstream` is null for native plugins. Report IDs are `rv-` or `sc-` plus the date plus the first 8 hex characters of the SHA-256 of the merged findings file.

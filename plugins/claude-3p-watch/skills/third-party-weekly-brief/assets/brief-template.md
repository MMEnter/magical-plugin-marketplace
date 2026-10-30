# Claude on 3P Inference — Week of {{WEEK_OF}}

**Releases covered:** {{VERSION_RANGE}} · **Docs checked:** {{PAGE_COUNT}} pages · **Generated:** {{DATE}}

## Bottom line

{{One to three sentences. What an administrator needs to know if they read nothing else.
If nothing shipped, say "No 3P changes this week" and delete every section below.}}

## Needs a decision

{{Breaking changes, changed defaults, deprecations, and anything where inaction has a
consequence. Each item: what changed, what it defaults to, what happens if you do nothing.
Delete this section if empty — do not write "none".}}

## New configuration keys

| Key | Default | What it does |
|---|---|---|
| `{{key}}` | `{{default}}` | {{effect}} |

{{Drawn from the configuration changelog diff and the 3P changelog sections. Include the
delivery channel — MDM, bootstrap server, or local config file — when the source states it.}}

## Behavior changes

{{Changes to existing behavior that ship no new key: consent prompts, sign-in flows, hidden
or relocated UI, model picker behavior, default-on/default-off flips.}}

## Documentation changes

{{From the snapshot diff. Report meaning, not patch text. Separate substantive changes from
terminology and formatting. Note new or deleted pages from the docs index diff.}}

## Fixes

{{One compressed list. Only fixes that a 3P administrator would recognize as a problem they
have or had — auth failures, proxy and TLS issues, connector reliability, MDM enforcement.
Skip general UI fixes.}}

## Relevance to our deployment

{{Two or three lines mapping the above to the specific provider, auth path, and MDM setup in
use. This is the section that makes the brief worth reading — everything above it is
available upstream.}}

---

*Sources: Claude Desktop changelog and third-party documentation, fetched {{DATE}}.
Snapshot baseline: {{BASELINE_DATE}}.*

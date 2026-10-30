---
name: third-party-weekly-brief
description: Produce a weekly brief on changes to Claude Desktop on third-party (3P) inference — Amazon Bedrock, Microsoft Foundry, Google Cloud's Agent Platform, and self-hosted gateways. Use this skill whenever the user asks for a 3P update, a Claude Desktop changelog review, a "what changed last week" brief on Claude Desktop / Cowork / Code, a managed-configuration key digest, or when a scheduled task fires asking for the weekly 3P brief. Also use it whenever the user wants to diff Anthropic's third-party documentation pages against a previous snapshot to detect silent doc edits.
---

# Weekly Claude 3P Inference Brief

Produce a dated brief covering everything that changed for Claude Desktop on third-party
inference in the past week, from two independent signals:

1. **The release changelog** — dated entries, parsed by date. Deterministic, needs no history.
2. **Documentation snapshots** — pages that carry no version history, diffed against last
   week's committed copy. This is the only way to catch silent doc edits.

Run both. The changelog tells you what shipped; the doc diff tells you what the guidance
now says, which frequently changes without a release entry.

## Workspace

The workspace is a private git repository reached through the GitHub connector, never through
the git CLI. Read `${CLAUDE_PLUGIN_ROOT}/shared/workspace.md` first — it defines the repo
coordinates, the layout, and the boundary between what belongs in a brief and what may be
published.

Git is not just storage here. It *is* the snapshot baseline: last week's pages are last
week's commit, so the doc diff compares the repo's copies against what this run fetched. There
is no `previous/` directory and nothing to rotate.

On the very first run there are no committed snapshots. The diff script detects this and says
`NO_BASELINE`. When it does, skip the doc-diff section and say so in the brief. Do not
fabricate a baseline, and do not describe that run's pages as additions.

## Procedure

### 0. Confirm connector access

Do this before anything else. Call `mcp__GitHub_MCP__get_me`.

If the GitHub tools are not present at all, this is very likely the known Cowork bug where MCP
connectors fail to initialize in an unattended scheduled session — the tools are simply not
loaded until a human message warms the session. **Delegate the whole run to a subagent** (the
Agent tool, `general-purpose`): a subagent initializes MCP tools correctly even when the parent
session did not. Have it report the brief back.

If the tools are still unavailable after that, run in **degraded mode**:

- Produce the changelog half of the brief. It needs no repository.
- Skip the documentation diff and say plainly, in the brief, that it did not run and why.
- **Write nothing to the repository — above all, do not advance `state.json`.** A degraded run
  that advances state makes next week's changelog window skip everything this run could not
  confirm. Failing loudly is cheap; a silently wrong diff window is not.

### 1. Load the baseline

Create a clean scratch directory for this run:

```bash
rm -rf /tmp/3p-run && mkdir -p /tmp/3p-run/baseline /tmp/3p-run/current
```

Read `state.json` from the repo with `mcp__GitHub_MCP__get_file_contents`. Fields: `last_run`
(ISO date, `null` on a fresh workspace), `last_version_seen` (e.g. `v1.30096.5`, `null` on a
fresh workspace), `tracked_pages`. Nulls or a missing file mean a first run — use a 7-day
lookback window.

List `snapshots/` with the same tool, then read each `<slug>.md` and write it to
`/tmp/3p-run/baseline/<slug>.md`. An empty `snapshots/` directory is the first-run case.

### 2. Pull the changelog

Fetch `https://claude.com/docs/cowork/changelog.md`.

Always append `.md` to a docs URL. It returns clean markdown instead of rendered HTML,
which makes both parsing and diffing far more stable.

Select every `<Update>` block whose `description` date is **after** `last_run`, or whose
`label` version is newer than `last_version_seen`. Prefer the version comparison — dates
can repeat within a day and multiple builds ship on the same date.

From each selected block, take:

- the whole **3P** section (this is the primary payload)
- anything under **General**, **Cowork**, or **Code** that touches managed configuration,
  MDM, sign-in, credentials, proxies, telemetry, egress, plugins, or connectors — these land
  in the wrong section regularly and matter just as much to a 3P administrator

Skip blocks whose 3P section reads "No user-facing changes" unless a General/Cowork/Code
item survived the filter above.

### 3. Snapshot and diff the documentation

Fetch each page listed in `tracked_pages`, resolving slugs to URLs via
`references/sources.md` (relative to this skill), all as `.md`. Write each to
`/tmp/3p-run/current/<slug>.md`.

Validate every fetch before writing. A page that came back empty, truncated, or as an error
document does not get written to `current/` — leave the slug absent so it is reported as not
fetched, and its committed copy stays untouched. Writing an error page here is the one
mistake that corrupts every future run.

Then:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/third-party-weekly-brief/scripts/diff_snapshots.sh" \
  /tmp/3p-run/baseline /tmp/3p-run/current
```

It prints a unified diff per changed page, flags newly tracked and not-fetched pages, and ends
with a summary line. Read the diffs and translate them — report what the change *means for a
deployment*, not the raw patch. A removed sentence in the telemetry page is a policy change;
say so.

For the history of a single page, use `mcp__GitHub_MCP__list_commits` with
`path: snapshots/<slug>.md`, then `mcp__GitHub_MCP__get_commit` on the SHA that interests you.
Useful when a change looks like it may have landed weeks ago.

Two page-specific notes:

- `llms.txt` is the docs index. New or removed lines there mean new or deleted documentation
  pages. A brand-new 3P page is often the earliest signal of a feature.
- `configuration-changelog.md` maps every managed-configuration key to the release it first
  shipped in. Diffing it gives you a clean list of new keys with no parsing at all — treat it
  as the authoritative source for the "New configuration keys" section.

### 4. Write the brief

Use `assets/brief-template.md` (relative to this skill). Write it to
`/tmp/3p-run/3p-brief-YYYY-MM-DD.md` for now; step 5 commits it.

Rules for the writing:

- **Lead with what requires action.** A new key that changes a default, a breaking change, or
  anything marked `(breaking)` goes at the top regardless of where it appeared in the source.
- **Name every configuration key in backticks** and say what it defaults to. An administrator
  reading this needs to know whether inaction is safe.
- **Separate "new capability" from "fix".** Fixes get one compressed list at the end; nobody
  needs a paragraph on each.
- **Flag terminology drift.** Anthropic renames providers in the docs without a changelog
  entry (Azure AI Foundry → Microsoft Foundry, Vertex AI → Google Cloud's Agent Platform).
  Managed configuration keys keep their old names — `inferenceFoundryTenantId`,
  `inferenceVertexBaseUrl` — so a rename is a documentation event, not a config migration.
  Say which it is, every time.
- **Keep it under a page.** If a week is quiet, the brief is three lines. Do not pad.
- If nothing changed in either signal, say exactly that and stop. A no-change week is a
  useful result, not a failed run.

### 5. Commit

One `mcp__GitHub_MCP__push_files` call to `main`, containing everything this run produced:

- **Only the snapshots the diff reported as CHANGED or NEWLY TRACKED.** Unchanged pages
  already have a correct copy in the repo; re-sending them costs a great deal and changes
  nothing. Pages reported as NOT FETCHED must be omitted — that is what preserves the last
  good copy.
- The brief, at `briefs/3p-brief-YYYY-MM-DD.md`.
- `state.json`, with `last_run` set to today, `last_version_seen` set to the newest version
  label seen in the changelog, and any change to `tracked_pages`.

Put all of it in the **same call**. `push_files` writes one commit, so snapshots, brief and
state advance together or not at all. Committing `state.json` separately reintroduces exactly
the failure this design removes.

A run that fetches pages but never commits leaves the next run diffing against a two-week-old
baseline while believing it is one week — the one failure mode that produces confidently wrong
output. If the push fails, say so in the brief and hand the user the brief anyway; do not
retry blindly, and do not claim the baseline advanced.

### 6. Deliver

Keep the **Relevance to our deployment** section internal. It is the reason the companion
`third-party-social-post` skill reads briefs rather than sources — see the publication boundary
in `${CLAUDE_PLUGIN_ROOT}/shared/workspace.md`.

Surface the brief to the user with a file-presentation tool if one is available. If the task
was configured to email or post the brief, do that too. Either way the commit is what makes
next week's diff possible, so it is never optional.

## Failure handling

- **A fetch fails.** Omit that slug from `current/` and from the commit, and note the page as
  unchecked in the brief. Never overwrite a snapshot with an error page — next week then diffs
  against a 404 instead of the last good version.
- **The GitHub connector is unavailable.** Delegate to a subagent first (step 0). If that does
  not recover it, produce the changelog half, state that the doc diff did not run, and write
  nothing to the repo.
- **The push fails.** Report it in the brief. The baseline did not advance, so next week's run
  is still correct — it will simply cover two weeks. Say that explicitly in the brief.
- **The changelog format changed.** Fall back to diffing the whole changelog page against
  its snapshot and report the added lines.
- **A page 404s.** That is itself news — a deleted or moved docs page belongs in the brief.
  Confirm it is genuinely gone upstream rather than a transient failure before saying so, and
  only then remove it from `tracked_pages`.

## Companion skill

`third-party-social-post` turns a finished brief into a short public post. Do not invoke it from
here. If the user wants both in one run, they will ask for both — commit the brief first, then
let the other skill read it from the repository.

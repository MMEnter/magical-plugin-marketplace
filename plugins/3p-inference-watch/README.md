# 3p-inference-watch

Tracks changes to Claude Desktop on third-party inference — Amazon Bedrock, Microsoft Foundry,
Google Cloud's Agent Platform, and self-hosted gateways — and turns them into two outputs: a
weekly administrator brief, and a short public post drawn from it.

## Skills

| Skill | Runs | Input | Output |
|---|---|---|---|
| `third-party-weekly-brief` | Weekly, scheduled | Release changelog + documentation snapshots | `briefs/3p-brief-YYYY-MM-DD.md` |
| `third-party-social-post` | On demand | A finished brief | `social/YYYY-MM-DD-<platform>.md` |

The dependency runs one way. The brief skill writes; the social skill reads. The social skill
never fetches a source and never runs the brief skill — see `shared/workspace.md` for why.

## Why two skills and not one step

The brief and the post have different rules about what may be said. Every brief ends with a
section describing the local deployment, which is exactly the content that must not reach a
public post. Keeping publication in a separate skill, with the boundary written into both,
makes that separation structural rather than a matter of remembering.

They also run on different cadences. The brief is scheduled; the post is a judgment call made
some weeks and not others.

## How the workspace is reached

The workspace is a private GitHub repository, and both skills reach it through the **GitHub
MCP connector** — not the git CLI.

This is not a stylistic choice. A Cowork session runs in an ephemeral cloud container with no
durable disk, and its GitHub access is mediated by a proxy that binds each session to
explicitly attached repositories. Cowork has no way to attach one, so `git clone` and
`git push` fail there regardless of credentials. Connector traffic bypasses that proxy
entirely.

Two consequences worth knowing before you change anything:

- **There is nothing to configure in the environment.** Earlier versions of this plugin read
  `CLAUDE_3P_WATCH_ROOT`, `CLAUDE_3P_WATCH_REMOTE` and `CLAUDE_3P_WATCH_BRANCH`. Those are
  gone — a Cowork session has nowhere to set an environment variable that survives to the next
  run, which is why the plugin appeared to work while never once syncing.
- **The repo coordinates live in `shared/workspace.md`**, and only there.

## Setup

1. **Create a private git repository** for the workspace. Private matters: it holds internal
   briefs.
2. **Install the connector's GitHub App.** In Claude, add GitHub's hosted MCP server as a
   custom connector (Customize → Connectors → Add custom connector →
   `https://api.githubcopilot.com/mcp/`). Then — and this is the step that is easy to miss —
   install the **Claude Github MCP Connector** app at
   `github.com/apps/claude-github-mcp-connector` and grant it access to the workspace repo.
   Authorizing the connector is not the same as installing the app: without the installation
   it can read your public repositories but returns a bare `404` for a private one, which
   looks identical to the repository not existing.

   Note this app is deliberately separate from the **Claude** app used by Claude Code. Having
   one installed does nothing for the other.
3. **Point the plugin at the repo.** Set the repository and branch in `shared/workspace.md`.
4. **Scaffold the repo** with `state.json`, `snapshots/`, `briefs/` and `social/` as laid out
   in `shared/workspace.md`. Set `tracked_pages` to the Tier 1 slugs plus whichever Tier 2
   pages match your deployment.
5. **Run the brief skill once by hand.** This produces the first snapshot commit, which becomes
   the documentation baseline. The changelog half works immediately; the diff half needs one
   prior commit, so the first run reports `NO_BASELINE` and the second is the first real diff.
6. **Schedule the brief weekly.** In Cowork, open a task and type `/schedule`.
7. **Ask for a post** whenever a week is worth one.

### Prerequisites to verify

- **The connector is enabled in the session that runs the task**, not merely connected at the
  account level. Connectors are toggled per conversation.
- **The GitHub App is installed with access to the workspace repo.** See step 2.
- **The repo is reachable**: `mcp__GitHub_MCP__get_file_contents` on the repo root should
  return its contents rather than a 404.

### Known issue: connectors in scheduled runs

MCP connectors currently fail to initialize in unattended scheduled sessions — the run finds no
GitHub tools at all until a human message warms the session. Both skills work around this by
delegating to a subagent, which initializes MCP tools correctly.

If that does not recover it, the brief skill runs in degraded mode: it produces the changelog
half, states that the documentation diff did not run, and writes nothing to the repository. It
specifically does **not** advance `state.json`, so a degraded run costs you one week's diff
rather than silently corrupting the next window.

## Tuning

- **Tracked pages:** `skills/third-party-weekly-brief/references/sources.md` maps slugs to
  URLs; `state.json` in the workspace decides which are actually fetched. Drop the provider
  pages that do not apply to your deployment — each one you keep is diff noise.
- **Brief structure:** `skills/third-party-weekly-brief/assets/brief-template.md`.
- **Post voice and platform rules:** `skills/third-party-social-post/references/`. Edit
  `voice.md` rather than correcting the output every week.

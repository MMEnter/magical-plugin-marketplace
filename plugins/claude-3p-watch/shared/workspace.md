# Shared workspace contract

Both skills in this plugin read and write the same git repository, through the GitHub
connector. Read this file before either skill touches the workspace.

## Where the workspace lives

| Setting | Value |
|---|---|
| Repository | `MMEnter/claude-3p-watch` (private) |
| Branch | `main` |
| Access | GitHub MCP connector (`mcp__GitHub_MCP__*` tools) |

Those coordinates are the single configuration point in this plugin. To move the workspace,
change them here — nothing else hardcodes them.

```
<repo root>/
├── state.json                    # last run date, last changelog version seen, tracked pages
├── snapshots/
│   └── <slug>.md                 # overwritten in place each run; git holds the history
├── briefs/
│   └── 3p-brief-YYYY-MM-DD.md    # written by third-party-weekly-brief
└── social/
    ├── YYYY-MM-DD-<platform>.md  # written by third-party-social-post
    └── posted-log.md             # running record of angles already used
```

## Why the connector, and not git

The session that runs these skills is an ephemeral cloud container. It has no durable disk,
and it cannot reach github.com over git: session GitHub access is mediated by a proxy that
binds each session to explicitly attached repositories, and Cowork sessions have no way to
attach one. `git clone` and `git push` fail there no matter what credentials exist.

Connector traffic does not go through that proxy. So the repository is reached with
`mcp__GitHub_MCP__get_file_contents` and `mcp__GitHub_MCP__push_files`, never with the git
CLI, and no part of this plugin depends on a working copy surviving between runs.

There is nothing to configure in the environment. Earlier versions of this plugin read
`CLAUDE_3P_WATCH_ROOT`, `CLAUDE_3P_WATCH_REMOTE` and `CLAUDE_3P_WATCH_BRANCH`; those are gone,
because a Cowork session has nowhere to set an environment variable that survives to the next
run. Anything that must persist lives in the repository.

## Git is the baseline, not just the backup

Snapshots are overwritten in place. Last week's version of a page is last week's commit, so
the documentation diff compares what the repo holds against what this run fetched. There is no
`previous/` directory, no `archive/`, and no rotation step — those existed to hand-roll
version control, and the repo does it properly.

Two consequences worth internalizing:

- **A run that fetches but never commits is worse than a run that fails.** The next run then
  diffs two weeks of change while believing it is looking at one. Always reach the commit.
- **Never overwrite a snapshot with an error page.** A failed fetch must leave the committed
  copy alone. Otherwise the 404 becomes the baseline and next week reports the real page as a
  large addition. In practice this means: omit that slug from the commit entirely.

One property the connector gives that the old local-git flow did not: `push_files` writes
every path in a single commit. Snapshots, brief and `state.json` advance together or not at
all, so a partial run cannot leave `state.json` claiming a baseline that was never written.
Put `state.json` in the same call as everything else — never commit it separately.

## Direction of dependency

`third-party-weekly-brief` **writes** briefs. `third-party-social-post` **reads** them.

The dependency runs one way and only one way:

- The social skill never fetches a documentation page, never parses the changelog, never
  touches `snapshots/` or `state.json`, and never commits to either. Its input is a finished
  brief file, nothing else.
- The brief skill never writes to `social/` and never considers publication.

If the social skill is invoked and no brief exists for the requested week, it says so and
stops. It does not run the brief skill to fill the gap — that would fetch on a cadence nobody
scheduled and advance `state.json`, corrupting the next week's diff window.

## The publication boundary

Every brief ends with a **Relevance to our deployment** section. That section, and anything
else in a brief that describes the local environment — provider choice, auth path, MDM
posture, internal incidents, help-desk volume — is internal. It never reaches a public post.

The social skill draws only from facts that appear in Anthropic's public documentation. The
test to apply: *could a reader verify this from the public changelog alone?* If no, cut it.

This boundary is the reason the two skills are separate. Reporting and publishing have
different rules about what may be said, and collapsing them into one step makes the internal
section one careless sentence away from a public post.

Note that a private repository does not soften this. The repo holds internal briefs; the
social drafts in `social/` are written for publication. Keeping both in one repository is
fine — treating the repo's privacy as the control is not.

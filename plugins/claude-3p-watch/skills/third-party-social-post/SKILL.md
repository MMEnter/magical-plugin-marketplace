---
name: third-party-social-post
description: Turn a finished weekly Claude 3P inference brief into a short social media post for LinkedIn or X. Use this skill whenever the user asks to post, share, or publish something from the 3P brief, wants a short version or a thread of the weekly update, asks "what's worth posting this week", or wants a draft about a specific Claude Desktop release, managed-configuration key, or third-party inference change. Also use it when the weekly brief has just been generated and the user asks for a public-facing version.
---

# 3P Social Post

Turn one week's brief into one post. The brief is the only input.

Read `${CLAUDE_PLUGIN_ROOT}/shared/workspace.md` before touching the workspace. Two rules from
it govern everything here:

1. **Never fetch sources.** This skill does not open the changelog or any documentation page.
   If a needed fact is not in the brief, the answer is that the post cannot make that claim —
   not that the source should be checked.
2. **Never publish internal content.** The brief's **Relevance to our deployment** section,
   and any other line describing the local environment, is off limits. The test: could a
   reader verify this from Anthropic's public documentation alone? If no, cut it.

## Procedure

### 1. Load the brief

The workspace is reached through the GitHub connector, never the git CLI.

List `briefs/` with `mcp__GitHub_MCP__get_file_contents` and take the newest
`3p-brief-YYYY-MM-DD.md` by filename date, unless the user named a specific week. Read it with
the same tool.

If the GitHub tools are not present, delegate to a subagent (the Agent tool,
`general-purpose`) — connectors routinely fail to initialize in unattended sessions and a
subagent recovers them. If `briefs/` is empty or the requested week has no brief, say so and
stop. Do not generate one: the brief skill fetches sources and advances `state.json`, and
running it off-cadence corrupts the next diff window.

Also read `social/posted-log.md` if it exists, so this week's angle does not repeat a recent
one.

### 2. Pick one angle

This is the whole job. A brief is a list; a post is an argument. Summarizing the brief
produces a changelog paste that nobody reads.

Choose the single item with the strongest *so what*, in this order of preference:

1. **A change that reverses an assumption.** A default that flipped, a setting that used to
   be silent and now prompts, a key that got renamed. These are the posts people thank you
   for.
2. **A fix whose description reveals the bug.** "One malformed entry disabled every
   marketplace" tells an administrator what their unexplained outage was. High value, and
   nobody else writes it up.
3. **A new capability with a real constraint.** Not "X now supports Y" but "X now supports Y,
   and here is the condition under which it actually applies."
4. **A pattern across several weeks.** Only if the archive supports it — read earlier briefs
   from `briefs/` before claiming a trend.

Reject the week if nothing clears the bar. "No post this week" is a valid output and keeps the
feed worth following. Say which items were considered and why they did not make it.

### 3. Draft

Produce the platform the user asked for; produce both if they did not specify.

Read `references/platforms.md` for length, shape, and formatting per platform, and
`references/voice.md` for the rules on tone, claims, and attribution. Both are short — read
them, do not guess.

### 4. Verify before handing it over

Walk this list explicitly and report the result. Every item is a hard gate.

- **Attribution.** Every factual claim traces to a line in the brief. Point at it.
- **Version.** The post names the release version or the week. Undated claims about software
  behavior go stale and become wrong.
- **Boundary.** Nothing from **Relevance to our deployment** survived, in substance or in
  paraphrase. Employer, provider, fleet size, and internal incidents are absent.
- **No implied access.** Nothing suggests private or early information. This is public
  documentation, read carefully — that is the entire value proposition, and claiming more
  undercuts it.
- **Key names exact.** Configuration keys are copied character for character from the brief,
  in the correct case. A post that misspells `trustBootstrapDelivery` is worse than no post.
- **Falsifiable.** A reader can check the claim against the public changelog and find it true.

Verify *before* committing. A draft that fails a gate is rewritten, not committed and fixed
later — the repo is not the place to keep a post that breaches the boundary.

### 5. Commit the draft and log it

One `mcp__GitHub_MCP__push_files` call to `main` containing both:

- the draft, at `social/YYYY-MM-DD-<platform>.md`
- the updated `social/posted-log.md`, with a row appended: date, platform, the angle in one
  line, and the release version

One commit, both files. The log is what stops week six from re-posting week two's point, so a
draft committed without its log entry defeats the mechanism.

## What this skill does not do

- It does not publish. It writes a file and hands it over. If a connector is configured and
  the user explicitly asks to post, that is a separate instruction they give in the moment.
- It does not run the brief skill. See the dependency direction in the shared workspace file.
- It does not write engagement bait, threads padded to a target length, or posts about weeks
  with nothing in them.

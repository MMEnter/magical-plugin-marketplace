---
name: security-review-plugin
description: Run a deeper security review of a Claude plugin through four blind lenses - supply chain, script security, confidentiality, and dependencies and licenses - against the SEC checklist, and report findings with patches. Use when the user asks for a security review, asks whether a plugin is safe to install or import, worries about hooks, scripts, MCP servers, secrets, leaked names or licenses, or before any plugin enters the marketplace. Not for style or house-rule reviews (review-plugin) or applying fixes (fix-plugin).
metadata:
  version: "0.3.0"
---

# Security review of a plugin

Slower and deeper than review-plugin. Every SEC rule in `${CLAUDE_PLUGIN_ROOT}/references/security-checklist.md` is mandatory: a security finding can never be waived.

## 1. Reuse or build the evidence package

If review-plugin already ran in this session on the same plugin, reuse its `<work>/package` when its tree hash still matches:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/stamp.py" hash "<plugin folder>"
```

Compare with `source.tree_hash` in `<work>/package/manifest.json`. If they differ, or there is no package, build one exactly as review-plugin step 2 does, into a new `.toolkit-work/<plugin>-<timestamp>/package`.

## 2. Run the blind security panel

Dispatch these four agents **in parallel**, each with the same message: the package folder path and `${CLAUDE_PLUGIN_ROOT}/references`. Never share one analyst's output with another.

- `supply-chain-analyst`
- `script-security-analyst`
- `confidentiality-analyst`
- `dependency-license-analyst`

Save each final JSON block to `<work>/security/analysts/<agent-name>.json`, retrying an invalid one once as in review-plugin. If agents can't be dispatched here, say so and run the lenses yourself one at a time, writing each lens's JSON before starting the next.

## 3. Merge and render

Dispatch `finding-synthesizer` with mode `security`, the four analyst files, `<work>/package/mechanical.json`, and the references path. Save to `<work>/security/merged.json` and render:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py" "<work>/security/merged.json" --out "<work>/security" --plugin "<plugin folder>" --mode security
```

## 4. Report back

Hand back `report.md` as a `computer://` link in Cowork, otherwise its path. Lead with the verdict in one sentence: **blocked** (any open or disputed critical), **fix first** (majors only), or **clear**. Then list every critical and major finding in one line each, with the lens that found it. Never repeat a secret or a denylisted term; the report already redacts them.

If a secret was found, tell the user to rotate it now: removing it from the files doesn't remove it from git history or from anyone who already cloned the repo.

Offer fix-plugin for findings with patches. For an import, remind the user that security findings block the import until fixed; they cannot be waived.

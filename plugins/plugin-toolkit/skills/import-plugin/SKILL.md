---
name: import-plugin
description: Bring an outside plugin into the marketplace through quarantine - from a .zip, a GitHub repo, an Anthropic or other marketplace entry, a standalone skill folder or an MCP server config - with safety checks, both review panels, approved fixes, waivers, provenance and a vendored-or-pinned choice, then hand off to release-plugin. Use when the user wants to import, add, adopt, vendor or bring in a plugin, skill or MCP server they didn't build here, or uploads a plugin zip. Not for new builds (build-plugin).
metadata:
  version: "1.0.0"
---

# Import a plugin

Every outside plugin enters through here. Read `${CLAUDE_PLUGIN_ROOT}/references/intake-policy.md` for the limits, tiers, waivers and provenance formats.

## 1. Intake into quarantine

Identify the source and run intake from the marketplace repo root: the user's working folder that holds `.claude-plugin/marketplace.json`, never the folder plugin-toolkit itself is installed in. If the current folder isn't a marketplace repo, ask where it is.

| Source | SOURCE argument |
|---|---|
| uploaded or local .zip | the file path |
| GitHub repo or subfolder | `https://github.com/OWNER/REPO` or `.../tree/REF/path` |
| entry in another marketplace | `marketplace:PLUGIN@OWNER/REPO` |
| standalone skill folder | the folder (add `--kind skill`) |
| MCP server config | the `.json` file or folder (add `--kind mcp`) |

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/intake.py" "<SOURCE>" --quarantine .toolkit-quarantine --json
```

Add `--name <kebab-name>` if the user wants a different name, `--ref <tag or sha>` to pin a specific version.

If the status is `rejected`, show every reason and stop. Nothing was unpacked outside quarantine. Do not try to work around a rejection; the user can raise the limit only by changing `intake-policy.md` in a reviewed pull request.

If accepted, tell the user the kind, name, pinned SHA or zip hash, and detected license. A missing or non-allowlisted license blocks the import (SEC-22); ask the user how they want to proceed.

For a wrapped skill or MCP server, ask who the author should be in `plugin.json` (it starts as `upstream`) and fill in the "TO CONFIRM" lines in the README from the upstream source.

## 2. Review in quarantine

Run review-plugin and then security-review-plugin on the `plugin_dir` from the intake result. Both use the quarantine copy; nothing has been executed.

## 3. Sort the findings

Split open findings into:

- **Must fix:** every mandatory rule, including all SEC rules. These block the import.
- **May waive:** waivable rules (mostly HR-P house patterns and HR-E evals).

Ask the user, for each waivable finding: fix it (fix-plugin) or waive it with a reason. Write waivers into `waivers.md` in the plugin folder using the table format in `intake-policy.md`, one row per rule with the user's reason and today's date. Don't invent reasons.

Apply approved fixes with fix-plugin, then re-run both reviews until nothing mandatory is open.

## 4. Storage

Ask: **vendored** (copy into `plugins/<name>/`, the marketplace owns it from now on) or **pinned** (the marketplace points at the upstream commit; no files copied). Pinned is only possible when no fixes were applied, because a pinned plugin can't carry changes. Explain that whichever they choose, bumping the version later is a new import.

- Vendored: check `plugins/<name>` doesn't exist, move the quarantine plugin folder there, and set "Storage" to `vendored` in `PROVENANCE.md`.
- Pinned: keep `PROVENANCE.md` in the quarantine copy for the record; release-plugin writes the stamp to `.toolkit/pinned/<name>.json`.

## 5. Hand off

Hand off to release-plugin with the plugin, storage choice, both report folders, and for pinned imports the upstream repo, SHA and subfolder. After a successful release, delete the quarantine box for this import.

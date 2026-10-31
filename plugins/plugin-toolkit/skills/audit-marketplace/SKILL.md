---
name: audit-marketplace
description: Audit a whole plugin marketplace repo - validate every plugin against the rulebook, reconcile plugins/ with marketplace.json, flag cross-plugin name collisions, and flag plugins with a missing or stale review stamp (edited after review, or merged around the gate). Use when the user asks to audit, health-check or sweep the marketplace, asks what is out of date or unreviewed, or wants to know if anything skipped the gate. Not for reviewing one plugin in depth (review-plugin).
metadata:
  version: "0.3.0"
---

# Audit the marketplace

Read-only. Run from the marketplace repo root (the folder with `.claude-plugin/marketplace.json`). If you're not there, ask for the path.

## 1. Run the three checks

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py" --all . --json --out .toolkit-work/audit-validate.json
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/sync_marketplace.py" . --json
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/stamp.py" verify-repo . --json
```

Each exits non-zero when it finds problems; that's expected, keep going.

## 2. Summarise

Give one table, a row per plugin: open critical / major / minor counts, marketplace sync status, and stamp status (`ok`, `missing`, `stale: edited after review`, or the specific problem). Then list separately:

- **Skipped the gate:** plugins with no stamp or a stale stamp. These were changed without the toolkit, most likely through an admin bypass of branch protection. Name the stamp problem for each.
- **Marketplace drift:** unlisted plugins, entries without folders, version or path mismatches, pinned entries without a SHA or stamp.
- **Name collisions:** skills, agents or commands with the same name in two plugins.

## 3. Offer next steps

For each plugin that needs it, offer review-plugin and security-review-plugin, then release-plugin to re-stamp. Never fix or re-stamp anything during an audit.

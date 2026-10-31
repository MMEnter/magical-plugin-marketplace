---
name: fix-plugin
description: Apply the patches from a plugin-toolkit review or security report after the user approves them, then re-validate and show what is fixed, still open or newly broken. Use when the user says apply the fixes, fix the findings, apply patches F-003 and F-007, or accept the review's suggestions. Not for reviewing (review-plugin, security-review-plugin) or for edits the report didn't propose.
metadata:
  version: "1.0.0"
---

# Apply approved fixes

The only toolkit skill that edits an existing plugin, and only with approval. Follow `${CLAUDE_PLUGIN_ROOT}/references/patch-spec.md`.

## 1. Find the report

Use the report folder from this session (`.toolkit-work/<plugin>-<timestamp>/review` or `/security`), or ask the user for its path. Read its `findings.json`.

Refuse, and say why, when `source.type` is `github`, `zip` or `marketplace` and the plugin folder in `source.location` is a temporary clone: patches applied there would be lost. Point the user to import-plugin (which puts the plugin in quarantine where it can be fixed) or a local checkout.

## 2. Ask for approval

List every open or disputed finding that has a patch, one line each: finding ID, severity, rule, files touched, and whether the patch applies cleanly. Then list findings without a patch and what each needs from the user.

Ask which patches to apply: all, a list of IDs, or none. Wait for the answer. Never apply a patch that conflicts; say it needs a fresh review instead.

## 3. Apply

From the plugin folder, for each approved patch in finding-ID order:

```bash
GIT_CEILING_DIRECTORIES="$(dirname "$PWD")" git apply --check -p1 "<report>/patches/<file>.diff" && \
GIT_CEILING_DIRECTORIES="$(dirname "$PWD")" git apply -p1 "<report>/patches/<file>.diff"
```

Stop at the first failure and report which patches applied. Never edit a patch to make it fit.

For fixes without a patch that the user explicitly tells you how to resolve, make exactly that edit and show the diff.

## 4. Re-validate

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py" "<plugin folder>"
```

Tell the user which mechanical findings are now fixed, which are still open, and any new ones. Judgment findings are only confirmed fixed by a new review.

## 5. Record

For an import (the plugin has `PROVENANCE.md`), add one line per applied fix under "Changes from upstream": `- F-003 (HR-S05): <one-line description>`.

Tell the user the next step: re-run review-plugin and security-review-plugin on the changed plugin. A release needs fresh reports with no open critical findings; the old ones describe files that no longer exist.

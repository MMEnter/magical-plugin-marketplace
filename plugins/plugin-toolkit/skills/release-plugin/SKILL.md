---
name: release-plugin
description: Release a reviewed plugin into the marketplace - bump the version everywhere it appears, write the marketplace entry, run the eval gate, write the review stamp, and open the pull request the plugin-gate check verifies. Blocks on open critical findings or a failing eval gate. Use when the user says release, ship, publish, bump the version, or add a reviewed or imported plugin to the marketplace. The only skill that edits marketplace.json. Not for reviews (review-plugin) or fixes (fix-plugin).
metadata:
  version: "1.0.0"
---

# Release a plugin

Run from the marketplace repo root. This is the last step for build-plugin and import-plugin, and the only way a plugin's marketplace entry changes.

## 1. Check the preconditions

You need a review report and a security report for the plugin's **current** files, each with no open or disputed critical finding. Use the `findings.json` files from this session's `.toolkit-work/` folders. If either is missing, or fix-plugin changed files after the review, run review-plugin and security-review-plugin again first. Stop and say what blocks the release if any judgment critical is open. Mechanical findings are re-checked on the current files in steps 3 and 5, so a first release's "not listed in marketplace.json" (HR-M09) is expected here and cleared in step 3.

Check the repo is on a clean branch: `git status --porcelain` should show only this plugin's changes.

## 2. Version

Ask for the bump: patch (fixes only), minor (new behaviour), or major (breaking). The first release of a new build is `0.1.0`; an import keeps its upstream version for its first release.

Set the version in `.claude-plugin/plugin.json`. Search the plugin for the old version string (`README.md`, `CHANGELOG.md` if present) and update the places that name the plugin's version; leave skill `metadata.version` values alone unless that skill changed.

## 3. Marketplace entry

For a plugin in `plugins/<name>/`:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/sync_marketplace.py" . --update-entry "<name>" --category "<category>"
```

Ask for the category on a first release (for example productivity, development, education). Add or update the plugin's row in the repo `README.md` plugin table.

For a pinned import, use `--update-pinned <name> --repo OWNER/REPO --sha <sha> [--path <subdir>] --description "..." --version <ver>` instead.

Then check nothing drifted and the plugin is clean:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/sync_marketplace.py" .
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py" "plugins/<name>"
```

## 4. Eval gate

The gate runs on the final files, after the version bump, because the stamp checks that the eval result matches them. State the cost first (run with `--dry-run` to see the run count), then:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/eval_gate.py" "plugins/<name>" --mode full
```

Use `--mode pr` only when the user explicitly accepts a smoke-level gate for a patch release. An import with an HR-E01 waiver skips this step. If the gate fails, stop and show why; use eval-plugin to debug.

## 5. Stamp

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/stamp.py" write "plugins/<name>" --review "<review>/findings.json" --security "<security>/findings.json" --eval "plugins/<name>/evals/results/gate-<ts>.json"
```

Use `--eval-waived` instead of `--eval` for an import with an HR-E01 waiver. For a pinned import use `stamp.py write-pinned . <name> --repo ... --sha ...` with the same report flags. Then confirm:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/stamp.py" verify "plugins/<name>"
```

Any edit after this point invalidates the stamp; if you have to change something, go back to step 1.

## 6. Pull request

Show the user the branch name (`release/<name>-<version>`), the files changed, and the PR title and body, and wait for approval before pushing (HR-P07).

Fill the `pr-body.md` template from `${CLAUDE_PLUGIN_ROOT}/references/scaffold-templates.md` with the version, origin, report IDs and open counts, eval gate result and cost, waivers with reasons, and for imports the source and pinned SHA. Don't write the body freehand (HR-P04). Then commit, push the branch and open the PR against `main` through the ~~source control connector, or with `gh pr create --body-file` when no connector is available.

Tell the user the plugin-gate check will run on the PR and that merging requires it to pass. Admins can bypass branch protection; audit-marketplace flags anything that skips the gate.

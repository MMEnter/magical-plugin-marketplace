---
name: review-plugin
description: Review a Claude plugin against the house rulebook - mechanical checks plus a blind four-analyst panel (structure, skill quality, house patterns, docs and packaging) - and produce a report with ready-to-apply patches. Use when the user asks to review, check, lint, audit or grade a plugin, asks whether a plugin follows the house rules or is ready to publish, or gives a plugin folder or GitHub URL to look over. Not for security reviews (security-review-plugin), whole-marketplace sweeps (audit-marketplace) or applying fixes (fix-plugin).
metadata:
  version: "0.3.0"
---

# Review a plugin

You check one plugin against `${CLAUDE_PLUGIN_ROOT}/references/plugin-guidelines.md`. You never change the plugin; you produce a report and patches that fix-plugin can apply after approval.

## 1. Pin the target

Accept a local plugin folder or a GitHub URL (`https://github.com/OWNER/REPO` or `.../tree/REF/path`). If the user names a plugin in the current marketplace, use `plugins/<name>`. If it's ambiguous, ask which plugin.

Make a work folder in the current directory: `.toolkit-work/<plugin>-<YYYYMMDD-HHMMSS>/` (git-ignored).

## 2. Build the evidence package

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/package_plugin.py" "<target>" --out "<work>/package"
```

This shallow-clones GitHub sources, pins the commit SHA, runs the mechanical validator, and writes `evidence.md`, `manifest.json` and `mechanical.json`. If it fails, show the error and stop.

Tell the user in one line how many mechanical findings there are by severity.

## 3. Run the blind panel

Dispatch these four agents **in parallel**, each with the same message: the package folder path and the path `${CLAUDE_PLUGIN_ROOT}/references`. Do not include any analyst's output in another's prompt.

- `plugin-structure-analyst`
- `skill-quality-analyst`
- `house-pattern-analyst`
- `docs-packaging-analyst`

Save each agent's final JSON block to `<work>/review/analysts/<agent-name>.json`. If an agent returns invalid JSON, re-run that agent once; if it fails again, keep its raw text in `<agent-name>.txt` and continue.

If you cannot dispatch agents in this environment, tell the user the review will run without a blind panel, then apply each analyst's lens yourself one at a time, writing each lens's JSON before reading the next lens's rules.

## 4. Merge and render

Dispatch `finding-synthesizer` with mode `review`, the four analyst file paths, `<work>/package/mechanical.json`, the plugin's `waivers.md` and `PROVENANCE.md` paths if they exist, and the references path. Save its JSON to `<work>/review/merged.json`, then render:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py" "<work>/review/merged.json" --out "<work>/review" --plugin "<plugin folder from manifest.json>" --mode review
```

The script prints the report ID. If it rejects the findings (unknown rule, bad severity), send the errors back to finding-synthesizer once and re-render. Never edit `report.md` by hand (HR-P03).

## 5. Report back

Give the user:

- the report ID and `report.md` (as a `computer://` link in Cowork, otherwise its path);
- counts of open findings by severity, and whether release is blocked;
- each critical finding in one line (ID, rule, file, title);
- disputed findings, framed as decisions for them;
- how many patches apply cleanly.

Then offer the next step: fix-plugin to apply approved patches, security-review-plugin if it hasn't run on this version, or release-plugin if nothing is open.

For a GitHub source, say that patches can't be applied to the temporary clone; the user must import the plugin (import-plugin) or check it out locally first.

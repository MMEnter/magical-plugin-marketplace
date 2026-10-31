# Patch spec

Analysts propose fixes as patches. `render_report.py` writes them to disk and checks them; `fix-plugin` applies them only after the user approves.

## Format

- A unified diff with `a/` and `b/` prefixes, paths relative to the **plugin root** (not the repo root): `--- a/skills/foo/SKILL.md`, `+++ b/skills/foo/SKILL.md`.
- New files use `--- /dev/null`. Deleted files use `+++ /dev/null`.
- One patch per finding. A patch touches only what its finding needs; no drive-by reformatting.
- Text files only. A fix to a binary file is described in `fix` with `patch: null`.
- At least 3 lines of context, so `git apply` can locate the hunk.

## Naming

`render_report.py` writes each patch to `patches/<finding-id>-<rule-id>-<slug>.diff`, for example `patches/F-003-hr-s05-add-trigger-phrases.diff`. The slug is the finding title lowercased, kebab-cased and cut to 40 characters.

## The check gate

Before a patch is offered, `render_report.py --plugin <path>` runs:

```
git apply --check -p1 <patch>
```

with the plugin root as the working directory (git 2.31 or later). The plugin does not need to be a git repo of its own; the scripts set `GIT_CEILING_DIRECTORIES` to the plugin's parent folder so `git apply` treats the plugin as plain files with plugin-root-relative paths, even when it sits inside the marketplace checkout. The report marks each patch **applies** or **conflicts**. Conflicting patches are listed but `fix-plugin` will not apply them.

## Applying

`fix-plugin`:

1. Refuses when the findings file's `source.type` is `github`, `zip` or `marketplace` without a local working copy. Patches made against a temporary clone would be lost; the user must check out or import the plugin first.
2. Shows the list of patches with finding ID, rule, severity and the files each touches, and waits for the user to approve all, some or none.
3. Re-runs `git apply --check` on each approved patch, then applies them in finding-ID order with `git apply -p1`.
4. Stops at the first failure and reports which patches applied.
5. Re-runs `validate_plugin.py` and reports findings that are now fixed, still open, or newly introduced.

A patch is never edited by hand to make it apply. If it conflicts, re-run the review on the current files.

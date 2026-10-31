# Intake policy

How a plugin from outside (a .zip, a GitHub repo, an Anthropic marketplace entry, a standalone skill or an MCP server) gets into the marketplace. `import-plugin` follows this file; `intake.py` and `stamp.py` read the machine-readable blocks in it.

## Quarantine

Every import lands in a quarantine folder first: `.toolkit-quarantine/<name>-<timestamp>/` under the current working folder, which is git-ignored. Nothing in quarantine is executed, installed or evaluated until both review panels have run and the user has approved the fixes. Quarantine is deleted after a successful release or when the user abandons the import.

## Archive and clone limits (SEC-20)

```json
{
  "max_archive_bytes": 52428800,
  "max_unpacked_bytes": 209715200,
  "max_files": 5000,
  "max_single_file_bytes": 26214400,
  "max_compression_ratio": 100,
  "allowed_executable_extensions": [".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".ps1"],
  "blocked_extensions": [".exe", ".dll", ".so", ".dylib", ".bin", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".jar", ".com", ".scr", ".bat", ".cmd", ".vbs"]
}
```

`intake.py` rejects an archive before writing anything if any entry has an absolute path, a drive letter, or a `..` component; is a symlink or hard link; would exceed a limit; or has a blocked extension. A file with the executable bit whose extension is not in `allowed_executable_extensions` is rejected too. GitHub sources are shallow-cloned and then put through the same file checks; symlinks in a clone are rejected.

## License allowlist (SEC-22)

```json
{
  "allowed_licenses": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Unlicense", "CC0-1.0", "MPL-2.0"]
}
```

The license is read from `plugin.json` `license`, else detected from the LICENSE file's first lines. Unknown or missing is a critical finding. Anything else needs the user to add it here in a reviewed pull request first.

## Import tiers

Native builds meet every rule. Imports must meet every rule tagged **mandatory** in `plugin-guidelines.md` and `security-checklist.md`; rules tagged **waivable** may be waived. In practice that means security, manifest, install-blocking and licensing rules always apply, and most house patterns (HR-P) and evals (HR-E) can be waived with a reason.

## waivers.md

Lives in the plugin root. Only imports may have one; `stamp.py --verify` fails a native plugin that has waivers.

```markdown
# Waivers

| Rule | Reason | Date |
|---|---|---|
| HR-P01 | Upstream skill writes its report directly; reworking it would fork upstream. | 2026-10-31 |
| HR-E01 | No eval suite upstream; covered by manual smoke test in PROVENANCE.md. | 2026-10-31 |
```

Every row needs all three cells. A waiver for a mandatory rule, an unknown rule or a row with an empty reason makes the stamp invalid.

## PROVENANCE.md

Lives in the plugin root of every import. The upstream LICENSE and NOTICE files stay as they are (SEC-18).

```markdown
# Provenance

| Field | Value |
|---|---|
| Source type | github · zip · marketplace · skill · mcp-server |
| Source | https://github.com/owner/repo/tree/<sha>/path, or the zip file name |
| Pinned SHA or zip SHA-256 | 40-char commit SHA, or sha256:... |
| License | MIT |
| Storage | vendored · pinned |
| Imported | 2026-10-31 |
| Imported by | plugin-toolkit 0.3.0 |

## Changes from upstream

- (each approved fix, by finding ID and rule)
```

## Storage choice

Asked per import:

- **Vendored:** the reviewed copy is committed under `plugins/<name>/`. The marketplace owns it from then on; upstream changes come in only as a new import.
- **Pinned:** nothing is copied. `marketplace.json` points at the upstream repo with a `sha`, and the stamp lives at `.toolkit/pinned/<name>.json` in the repo root. Fixes cannot be applied to a pinned plugin, so a pinned import must pass with no open findings except waived ones. Bumping the SHA is a new import and goes through the gate again.

## Denylist (SEC-23)

`.toolkit/denylist.json` in the marketplace repo root:

```json
{
  "schema_version": 1,
  "normalize": "lowercase word tokens; phrases of up to 3 tokens joined by single spaces",
  "terms": [
    { "sha256": "<hex of the normalized term>", "label": "former-employer-1" }
  ]
}
```

Terms are stored only as hashes so the file never contains the words it bans; `label` is a neutral tag that does not reveal the term. To add a term, run `python3 scripts/stamp.py --hash-term` and type the term at the prompt (it is not echoed or stored), then paste the printed hash into the file. The scan covers file contents and file names.

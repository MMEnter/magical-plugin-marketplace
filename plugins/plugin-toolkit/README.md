# plugin-toolkit

The front gate to this marketplace. Every plugin, built here or imported from outside, is reviewed, security-checked, fixed, eval-gated, stamped and released through this toolkit, against one numbered rulebook. A GitHub Actions check (`plugin-gate`) refuses pull requests whose plugins don't carry a valid review stamp.

## How a plugin gets in

| Source | Skill | First step |
|---|---|---|
| New build | build-plugin | Filled from the house templates |
| .zip | import-plugin | Checked for path traversal, symlinks, size and executables, then unpacked into quarantine |
| GitHub repo, or an entry in another marketplace (such as Anthropic's) | import-plugin | Shallow clone into quarantine, pinned to a commit SHA |
| Standalone skill | import-plugin | Wrapped with a generated plugin.json, README and the upstream LICENSE |
| MCP server config | import-plugin | Wrapped as a plugin with an .mcp.json |

All routes converge: both review panels, approved fixes, the eval gate, then release-plugin writes the stamp and the marketplace entry and opens the pull request.

## Components

**Skills**

- `review-plugin`: mechanical checks plus a blind four-analyst review panel; report and patches.
- `security-review-plugin`: four blind security lenses (supply chain, script security, confidentiality, dependencies and licenses).
- `build-plugin`: new plugin from templates, reviewed, handed to release.
- `import-plugin`: quarantine intake for zips, GitHub repos, marketplace entries, skills and MCP servers; waivers, provenance, vendored or pinned storage.
- `fix-plugin`: applies approved patches and re-validates. The only skill that edits an existing plugin.
- `audit-marketplace`: validates every plugin, reconciles marketplace.json, flags name collisions and missing or stale stamps.
- `release-plugin`: version bump, marketplace entry, eval gate, stamp, pull request. The only skill that edits marketplace.json.
- `eval-plugin`: writes, runs and debugs `claude plugin eval` suites; states cost first.

**Agents** (all read-only: Read, Grep, Glob)

- Review panel: `plugin-structure-analyst`, `skill-quality-analyst`, `house-pattern-analyst`, `docs-packaging-analyst`.
- Security panel: `supply-chain-analyst`, `script-security-analyst`, `confidentiality-analyst`, `dependency-license-analyst`.
- `finding-synthesizer`: merges a panel's blind outputs without averaging away disagreement.

**Scripts** (`scripts/`)

| Script | Job |
|---|---|
| `validate_plugin.py` | Every mechanical rule, read from the rulebook at runtime; findings as JSON |
| `package_plugin.py` | One byte-identical evidence package per review, from a folder or GitHub URL |
| `render_report.py` | Findings JSON to `report.md` plus checked patches |
| `sync_marketplace.py` | Reconciles `plugins/` with `marketplace.json`; writes entries only for release-plugin |
| `eval_gate.py` | Runs `claude plugin eval` in pr or full mode and decides pass or fail |
| `intake.py` | Quarantine intake and wrapping for imports |
| `stamp.py` | Tree hash, review stamp write and verify, denylist term hashing |

**References** (`references/`): `plugin-guidelines.md` (the HR rulebook), `security-checklist.md` (SEC rules), `finding-schema.md`, `patch-spec.md`, `scaffold-templates.md`, `eval-standards.md`, `intake-policy.md`.

**Tests**: `tests/test_toolkit.py` (unit tests, no model calls) and `tests/make_fixtures.py`, which generates synthetic fixtures at run time so the repo never holds files that trip its own scans. `evals/` holds the toolkit's own seven-case eval suite.

This plugin has no hooks and no MCP servers. Its scripts make no network calls except `git clone` and `git fetch` from github.com when you review or import a GitHub source.

## Install

```
/plugin install plugin-toolkit --marketplace MMEnter/magical-plugin-marketplace
```

Or, with the marketplace already added: `/plugin install plugin-toolkit@magical-plugin-marketplace`.

## Requirements

- Python 3.10 or later with PyYAML 6 (`pip install "pyyaml>=6,<7"`).
- git 2.31 or later.
- Claude Code 2.1.269 or later for `claude plugin eval` (eval-plugin and the eval gate) and for `claude plugin validate` (used by the validator when present).
- Linux, macOS or WSL2 for eval suites that grant Bash.
- github.com egress for GitHub imports and for pushing releases. On a Foundry or other third-party deployment, allow it in the egress policy.

## Usage

- "Review plugins/exam-podcast against the house rules."
- "Security-review this plugin before I import it: https://github.com/owner/repo"
- "Import the plugin in this zip." / "Import the skill in incoming/minutes as a plugin."
- "Build a new plugin that turns meeting transcripts into minutes."
- "Audit the marketplace: has anything skipped review?"
- "Release ai-rescue-kit as 0.2.0."

Run the unit tests with `python3 -m unittest discover -s plugins/plugin-toolkit/tests` from the repo root.

## The gate

`.github/workflows/plugin-gate.yml` runs on pull requests to `main` that touch `plugins/`, `.claude-plugin/marketplace.json` or `.toolkit/`. For each changed plugin it runs the validator (fails on any critical finding), checks marketplace sync, verifies the review stamp (tree hash, reports, eval gate, waivers), checks pinned SHAs against their stamps, and scans changed files for secrets and denylisted terms. It runs the toolkit from `main`, so a pull request can't weaken the checks that judge it.

CI never runs model-based reviews or evals: those are billed and run locally, and CI trusts the stamp as proof. A hand-written stamp would pass, so the stamp is an honesty check, not a security boundary. `audit-marketplace` is the second line, and the backstop for admin bypasses of branch protection.

## The denylist

`.toolkit/denylist.json` in the repo root lists terms that must never appear in the marketplace, stored as SHA-256 hashes. Add one with `python3 plugins/plugin-toolkit/scripts/stamp.py --hash-term` (input hidden) and paste the hash in.

## License

MIT. See LICENSE.

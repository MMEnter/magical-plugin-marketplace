# Security checklist (SEC rules)

The security panel reviews a plugin through four lenses. Every SEC rule is **mandatory**: it cannot be waived for a native build or an import. Mechanical SEC rules are checked by `validate_plugin.py` on every review and in CI; judgment rules are checked by the analyst that owns the lens.

Columns mean the same as in `plugin-guidelines.md`.

## Lens owners

| Lens | Rules | Analyst |
|---|---|---|
| Supply chain | SEC-01–05, SEC-20 | supply-chain-analyst |
| Script security | SEC-06–10 | script-security-analyst |
| Confidentiality | SEC-11–15, SEC-21, SEC-23 | confidentiality-analyst |
| Dependencies and licenses | SEC-16–19, SEC-22 | dependency-license-analyst |

## Supply chain

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| SEC-01 | no downloaded script is piped straight into a shell or interpreter (curl or wget output fed to sh, bash or python; PowerShell Invoke-Expression of a web request) in scripts, hooks, commands or skills | mechanical | critical | mandatory |
| SEC-02 | code fetched at runtime is pinned by version and checked by hash, or not fetched at all | judgment | critical | mandatory |
| SEC-03 | git, npm and pip sources are pinned to a tag, version or commit, never a moving branch | mechanical | major | mandatory |
| SEC-04 | no obfuscated execution: `eval`/`exec` of decoded strings, base64-to-shell, packed or minified scripts | mechanical | critical | mandatory |
| SEC-05 | bundled binaries and executables are named in the README with their source and purpose | mechanical | major | mandatory |
| SEC-20 | archives are safe to unpack: no absolute paths or `..` entries, no symlinks or hard links, under the size and file-count limits, and no unexpected executables (limits in `intake-policy.md`) | mechanical | critical | mandatory |

## Script security

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| SEC-06 | no `shell=True`, `os.system` or `os.popen` built from interpolated input | mechanical | major | mandatory |
| SEC-07 | scripts and hooks write only inside the plugin, the user's project or a stated output folder | judgment | critical | mandatory |
| SEC-08 | paths and arguments that come from the user or a file are validated before use (no traversal, no option injection) | judgment | major | mandatory |
| SEC-09 | destructive commands (`rm -rf`, `git push --force`, `git reset --hard`, `DROP TABLE`) only run behind an explicit approval step | mechanical | major | mandatory |
| SEC-10 | every network destination a script, hook or skill contacts is named in the README | judgment | major | mandatory |

## Confidentiality

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| SEC-11 | no real client, customer or employer names, project codenames or engagement details | judgment | critical | mandatory |
| SEC-12 | no internal hostnames, private IP addresses or intranet URLs | mechanical | major | mandatory |
| SEC-13 | no personal data (email addresses, phone numbers) beyond the declared author | judgment | major | mandatory |
| SEC-14 | no prompt or script sends workspace content to an external endpoint the user has not been told about | judgment | critical | mandatory |
| SEC-15 | logs, reports and outputs do not capture secrets or environment variables | judgment | major | mandatory |
| SEC-21 | no secrets: nothing matches the secret scanner (API keys, tokens, private keys, connection strings with passwords) | mechanical | critical | mandatory |
| SEC-23 | no term on the marketplace denylist appears in any file or file name | mechanical | critical | mandatory |

## Dependencies and licenses

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| SEC-16 | every runtime dependency is declared with a version constraint | judgment | major | mandatory |
| SEC-17 | no abandoned, typo-squatted or unvetted packages | judgment | major | mandatory |
| SEC-18 | third-party code keeps its upstream LICENSE and NOTICE files | judgment | critical | mandatory |
| SEC-19 | dependency licenses are compatible with the plugin's license | judgment | major | mandatory |
| SEC-22 | the plugin's license is on the allowlist in `intake-policy.md` | mechanical | critical | mandatory |

## Secret scanner patterns (SEC-21)

`validate_plugin.py` flags any line matching one of these. A match inside `tests/fixtures/` is still reported; fixtures must use obviously fake values that do not match.

- Anthropic, OpenAI and similar keys: `sk-ant-...`, `sk-proj-...`, `sk-` followed by 32+ characters
- GitHub tokens: `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`
- AWS access key IDs: `AKIA` or `ASIA` plus 16 uppercase characters
- Google API keys: `AIza` plus 35 characters
- Slack tokens: `xox[abprs]-`
- Private key blocks: `-----BEGIN ... PRIVATE KEY-----`
- Connection strings that carry a literal password between the user name and the host
- Assignments such as `api_key = "..."`, `password: "..."`, `secret="..."` with a literal value of 12+ characters that is not a `${VAR}` reference or a placeholder like `<your-key>`

## Denylist (SEC-23)

The marketplace keeps its denylist at `.toolkit/denylist.json` in the repo root. Terms are stored as SHA-256 hashes so the list itself never contains the words it bans. Format and how to add a term are in `intake-policy.md`.

# Plugin guidelines (House Rules)

This is the rulebook. Every skill, agent and script in plugin-toolkit points back here, and `validate_plugin.py` reads the rule tables in this file at runtime, so a change here changes what the validator enforces.

## How to read a rule

Each row has five fixed columns:

| Column | Values | Meaning |
|---|---|---|
| ID | `HR-<family><nn>` | Permanent. A retired rule keeps its ID and gets `[retired]` at the start of its text. |
| Kind | `mechanical` / `judgment` | Mechanical rules are checked by `validate_plugin.py`. Judgment rules are checked by the owning analyst agent. |
| Severity | `critical` / `major` / `minor` | critical: won't install or run, or a security or confidentiality issue. major: works but breaks a house pattern or will confuse users. minor: polish. |
| Tier | `mandatory` / `waivable` | Native builds must meet every rule. An imported plugin may waive a `waivable` rule in its `waivers.md` (format in `intake-policy.md`). `mandatory` rules can never be waived. |

Security rules (`SEC-*`) live in `security-checklist.md` and use the same columns. All of them are mandatory.

Severity in a finding may be raised by an analyst (with a reason) but never lowered below the rule's severity.

## Families and owners

| Family | Rules | Owning analyst |
|---|---|---|
| HR-M Manifest and marketplace | M01–M09 | plugin-structure-analyst (M08: docs-packaging-analyst) |
| HR-S Skills | S01–S08 | skill-quality-analyst |
| HR-A Agents | A01–A07 | plugin-structure-analyst |
| HR-P House patterns | P01–P07 | house-pattern-analyst |
| HR-C Conventions | C01–C07 | docs-packaging-analyst |
| HR-E Evals | E01–E08 | skill-quality-analyst |
| HR-H Hooks | H01–H05 | plugin-structure-analyst |
| HR-K Commands | K01–K04 | skill-quality-analyst |
| HR-X MCP servers | X01–X05 | plugin-structure-analyst |

## HR-M Manifest and marketplace

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-M01 | `.claude-plugin/plugin.json` exists, parses as a JSON object, and passes `claude plugin validate` when the CLI is available | mechanical | critical | mandatory |
| HR-M02 | `name` is kebab-case, 3 to 64 characters, and matches the plugin folder name | mechanical | critical | mandatory |
| HR-M03 | `version` is present and is semver (`MAJOR.MINOR.PATCH`) | mechanical | major | mandatory |
| HR-M04 | `description` is 30 to 300 characters | mechanical | major | mandatory |
| HR-M05 | `author.name` is present | mechanical | minor | mandatory |
| HR-M06 | `keywords` has 4 to 10 lowercase kebab-case entries | mechanical | minor | waivable |
| HR-M07 | `license` is set, and a LICENSE file in the plugin root matches it | mechanical | major | mandatory |
| HR-M08 | `homepage` points at the plugin's own folder in the marketplace repo | mechanical | minor | waivable |
| HR-M09 | the marketplace lists the plugin with matching name, source path, version and a description | mechanical | critical | mandatory |

## HR-S Skills

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-S01 | every `skills/<dir>/SKILL.md` has YAML frontmatter with `name` and `description`, and `name` equals `<dir>` | mechanical | critical | mandatory |
| HR-S02 | frontmatter uses only known keys: name, description, metadata, allowed-tools, license, compatibility, disable-model-invocation, user-invocable, argument-hint, model | mechanical | minor | waivable |
| HR-S03 | `metadata.version` is present and is semver | mechanical | minor | waivable |
| HR-S04 | `description` is 50 to 1024 characters | mechanical | critical | mandatory |
| HR-S05 | `description` says what the skill does and when to use it, with the phrases a user would actually type, and names nearby requests it is not for when skills could overlap | judgment | major | waivable |
| HR-S06 | the body is written as imperative instructions to Claude, not documentation for a human reader | judgment | minor | waivable |
| HR-S07 | the SKILL.md body is under 500 lines; longer detail lives in `references/` | mechanical | major | waivable |
| HR-S08 | every relative file path the SKILL.md mentions exists in the plugin | mechanical | critical | mandatory |

## HR-A Agents

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-A01 | every `agents/*.md` has frontmatter with `name` and `description`, and `name` equals the file stem | mechanical | critical | mandatory |
| HR-A02 | `description` contains at least one `<example>` block with a `<commentary>` inside it | mechanical | major | waivable |
| HR-A03 | `model`, if set, is one of inherit, sonnet, opus, haiku, fable; `color`, if set, is one of red, blue, green, yellow, purple, orange, pink, cyan | mechanical | major | mandatory |
| HR-A04 | `tools` is scoped to the job: a read-only agent gets no Write, Edit, MultiEdit, NotebookEdit or unscoped Bash | judgment | major | mandatory |
| HR-A05 | the body states its lens boundary: what it covers and what it leaves to other agents | judgment | minor | waivable |
| HR-A06 | the body defines an output contract (the exact format it returns) | judgment | major | waivable |
| HR-A07 | no agent duplicates another agent's or a skill's job | judgment | minor | waivable |

## HR-P House patterns

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-P01 | JSON-then-render: structured deliverables are produced as JSON first and rendered by a script, not written freehand | judgment | major | waivable |
| HR-P02 | every JSON spec a skill produces has a schema doc in `references/` | judgment | major | waivable |
| HR-P03 | rendered output is never hand-edited; a change goes into the JSON and is re-rendered | judgment | major | waivable |
| HR-P04 | fixed boilerplate (headers, disclaimers, legal text) lives as constants in a script or template, never regenerated by the model | judgment | major | waivable |
| HR-P05 | reviews use blind panels: analysts never see each other's output, and a synthesizer merges them without averaging away disagreement | judgment | major | waivable |
| HR-P06 | connectors are referenced as `~~category` placeholders (for example `~~chat`, `~~project tracker`), not hard-coded server names | judgment | major | waivable |
| HR-P07 | anything that writes to the user's files, sends, publishes or renders a final deliverable shows its plan and waits for approval first | judgment | major | waivable |

## HR-C Conventions

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-C01 | bundled scripts are invoked through `"${CLAUDE_PLUGIN_ROOT}/..."` with an interpreter fallback: `"$(command -v python3 \|\| command -v python)"` (preferred, because a script that exits non-zero would otherwise run twice) or `python3 ... \|\| python ...` | mechanical | major | waivable |
| HR-C02 | no absolute paths (`/Users/`, `/home/`, `C:\`) in plugin files | mechanical | critical | mandatory |
| HR-C03 | third-party Python imports used by scripts are listed in the README's requirements | mechanical | major | mandatory |
| HR-C04 | `README.md` exists in the plugin root and covers what it does, its components, requirements and usage | mechanical | major | mandatory |
| HR-C05 | a `LICENSE` file exists in the plugin root | mechanical | critical | mandatory |
| HR-C06 | no build junk is committed: `__pycache__`, `*.pyc`, `.DS_Store`, `node_modules`, `.env`, `evals/results/` | mechanical | major | mandatory |
| HR-C07 | files handed back to the user in Cowork are delivered as `computer://` links | judgment | minor | waivable |

## HR-E Evals

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-E01 | an `evals/` suite exists with at least one case | mechanical | major | waivable |
| HR-E02 | every skill is exercised by at least one case (its name appears in a case's prompt or graders) | mechanical | major | waivable |
| HR-E03 | every case has at least one outcome grader (`regex`, `file_exists` or `llm`), not only `tool_used` | mechanical | major | waivable |
| HR-E04 | the suite has at least one negative case: a `tool_used` Skill grader with `max: 0` and `arm: both` | mechanical | major | waivable |
| HR-E05 | `evals/eval-config.json` exists and matches `eval-standards.md` | mechanical | minor | waivable |
| HR-E06 | `evals/results/` is ignored by git (plugin or repo `.gitignore`) | mechanical | minor | waivable |
| HR-E07 | cases are realistic user requests, not copies of SKILL.md examples | judgment | minor | waivable |
| HR-E08 | fixtures are synthetic and safe: no real customer data, secrets, or network dependence | judgment | major | mandatory |

## HR-H Hooks

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-H01 | `hooks/hooks.json` (or manifest `hooks`) parses and every event is a known hook event | mechanical | critical | mandatory |
| HR-H02 | every hook command refers to bundled files through `${CLAUDE_PLUGIN_ROOT}`, and those files exist | mechanical | critical | mandatory |
| HR-H03 | every command hook sets a `timeout` | mechanical | minor | waivable |
| HR-H04 | hooks make no network calls and write nothing outside the plugin or project unless the README states why | judgment | critical | mandatory |
| HR-H05 | the README says what each hook does and when it fires | mechanical | minor | waivable |

## HR-K Commands

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-K01 | every `commands/*.md` has frontmatter with a `description` | mechanical | major | mandatory |
| HR-K02 | `allowed-tools` never grants bare `Bash`; shell access is scoped as `Bash(cmd:*)` | mechanical | major | mandatory |
| HR-K03 | a command whose body uses `$ARGUMENTS` or `$1` declares an `argument-hint` | mechanical | minor | waivable |
| HR-K04 | a command does not duplicate a skill in the same plugin | judgment | minor | waivable |

## HR-X MCP servers

| ID | Rule | Kind | Severity | Tier |
|---|---|---|---|---|
| HR-X01 | `.mcp.json` (or manifest `mcpServers`) parses and every server has a `command` or a `url` | mechanical | critical | mandatory |
| HR-X02 | stdio servers launched through npx, uvx, pipx or docker pin an exact version or digest; no `@latest` | mechanical | critical | mandatory |
| HR-X03 | no literal secrets in `env` or `headers`; values come from `${VAR}` references | mechanical | critical | mandatory |
| HR-X04 | every remote server host appears in the README with what data is sent to it | mechanical | major | mandatory |
| HR-X05 | the server's source and maintainer are documented, and it is one the user can audit | judgment | major | mandatory |

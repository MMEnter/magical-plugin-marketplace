# Scaffold templates

`build-plugin` fills these to create a new plugin, and `intake.py` fills the same ones when it wraps a standalone skill or MCP server. Each template sits between `<!-- template: NAME -->` and `<!-- /template -->` markers; `intake.py` reads them by name, so keep the markers intact.

Placeholders are `{{name}}`. A template that still contains a `{{...}}` after filling is an error, never shipped.

| Placeholder | Filled with |
|---|---|
| `{{plugin-name}}` | kebab-case plugin name, same as its folder |
| `{{plugin-description}}` | 30-300 characters: what it does, for whom |
| `{{version}}` | `0.1.0` for a new build; upstream version for an import |
| `{{author}}` | `MMEnter` unless the user says otherwise; upstream author for an import |
| `{{github-owner}}` / `{{marketplace-repo}}` | `MMEnter` / `magical-plugin-marketplace` |
| `{{license}}` | SPDX ID; `MIT` for native builds |
| `{{keywords}}` | 4-10 kebab-case strings as a JSON array |
| `{{skill-name}}`, `{{skill-description}}` | per skill |
| `{{components}}` | one bullet per skill, agent, command, hook or MCP server |
| `{{requirements}}` | runtime needs with versions, or "None beyond Claude Code." |
| `{{usage}}` | two or three example requests a user would type |
| `{{year}}` | current year |

## plugin.json

<!-- template: plugin.json -->
```json
{
  "name": "{{plugin-name}}",
  "version": "{{version}}",
  "description": "{{plugin-description}}",
  "author": {
    "name": "{{author}}"
  },
  "homepage": "https://github.com/{{github-owner}}/{{marketplace-repo}}/tree/main/plugins/{{plugin-name}}",
  "license": "{{license}}",
  "keywords": {{keywords}}
}
```
<!-- /template -->

## README.md

<!-- template: README.md -->
```markdown
# {{plugin-name}}

{{plugin-description}}

## Components

{{components}}

## Requirements

{{requirements}}

## Usage

{{usage}}

## License

{{license}}. See LICENSE.
```
<!-- /template -->

## LICENSE (MIT)

Native builds use MIT. Imports keep their upstream license file unchanged.

<!-- template: LICENSE-MIT -->
```text
MIT License

Copyright (c) {{year}} {{author}}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
<!-- /template -->

## SKILL.md

<!-- template: SKILL.md -->
```markdown
---
name: {{skill-name}}
description: {{skill-description}}
metadata:
  version: "{{version}}"
---

# {{skill-title}}

{{skill-purpose}}

## Steps

1. {{step-1}}
2. Show the user what you will write or send and wait for approval before doing it.
3. {{step-3}}

## References

- `references/{{reference-file}}`: {{reference-purpose}}
```
<!-- /template -->

Description pattern: one sentence on what it does, then "Use when ..." with the phrases a user would type, then "Not for ..." when a neighbouring skill could fire instead (HR-S05).

## Agent

<!-- template: agent.md -->
```markdown
---
name: {{agent-name}}
description: {{agent-purpose}} Use when {{agent-trigger}}.

  <example>
  Context: {{example-context}}
  user: "{{example-request}}"
  assistant: "I'll hand this to the {{agent-name}} agent."
  <commentary>
  {{why-this-agent}}
  </commentary>
  </example>
model: inherit
color: blue
tools: Read, Grep, Glob
---

You are {{agent-role}}.

## Lens

You cover: {{covers}}. You do not cover: {{does-not-cover}}; leave those to {{other-agents}}.

## Input

{{input-contract}}

## Output

{{output-contract}}
```
<!-- /template -->

## Wrapped MCP server README section

Used by `intake.py` for an MCP-server import. Every remote host must be named (HR-X04).

<!-- template: mcp-components -->
```markdown
- MCP server `{{server-name}}`: {{server-transport}}. {{server-endpoint}}
  Source and maintainer: {{server-source}}. Data sent: {{server-data}}.
```
<!-- /template -->

## Eval case

<!-- template: eval-prompt.md -->
```markdown
---
max_turns: 10
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---

{{realistic-user-request}}
```
<!-- /template -->

<!-- template: eval-grader-fired.md -->
```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?{{skill-name}}"'
---
```
<!-- /template -->

<!-- template: eval-grader-negative.md -->
```markdown
---
type: tool_used
tool: Skill
min: 0
max: 0
arm: both
---
```
<!-- /template -->

<!-- template: eval-config.json -->
```json
{
  "threshold": 0.8,
  "runs_full": 3,
  "smoke_cases": ["{{smoke-case}}"],
  "judge_model": "sonnet",
  "allow_tools": [],
  "scaffold": false,
  "max_cost_usd": 10
}
```
<!-- /template -->

## Release pull request body

`release-plugin` fills this; it never writes the PR body freehand.

<!-- template: pr-body.md -->
```markdown
## Release: {{plugin-name}} {{version}}

Released through plugin-toolkit {{toolkit-version}}.

| | |
|---|---|
| Origin | {{origin}} |
| Source | {{source}} |
| Review report | `{{review-report}}`: {{review-open}} |
| Security report | `{{security-report}}`: {{security-open}} |
| Eval gate | {{eval-result}} |
| Tree hash | `{{tree-hash}}` |

### Waivers

{{waivers}}

### What changed

{{changes}}

The plugin-gate check verifies the review stamp against the files in this pull request.
```
<!-- /template -->

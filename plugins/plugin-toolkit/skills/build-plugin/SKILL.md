---
name: build-plugin
description: Build a new Claude plugin for the marketplace from the house templates - plugin.json, README, LICENSE, skills, agents and an eval suite - then review it and hand it to release-plugin. Use when the user wants to create, scaffold, start or make a new plugin, skill pack or agent bundle for their marketplace. Not for importing an existing plugin, skill, zip or MCP server (import-plugin) or changing an existing plugin (review-plugin, fix-plugin).
metadata:
  version: "1.0.0"
---

# Build a new plugin

A native build must meet every rule in `${CLAUDE_PLUGIN_ROOT}/references/plugin-guidelines.md` and `${CLAUDE_PLUGIN_ROOT}/references/security-checklist.md`; native plugins can't have waivers. Templates are in `${CLAUDE_PLUGIN_ROOT}/references/scaffold-templates.md`.

## 1. Interview

Ask only what you can't infer, in one round:

- what the plugin does and for whom (becomes the description);
- the jobs it covers, one per skill, with two or three phrases a user would type for each;
- whether it needs agents, slash commands, hooks or MCP servers, and why;
- any scripts and their Python dependencies.

Pick a kebab-case name and check it isn't taken:

```bash
"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/sync_marketplace.py" .
```

A name collision with another plugin's skill, agent or command shows up as `name_collision`; choose different component names.

## 2. Show the plan, then write

Show the file tree you will create under `plugins/<name>/` and each skill's description. Wait for approval (HR-P07). Refuse if `plugins/<name>/` already exists; offer review-plugin instead.

Then create, from the templates, with every `{{placeholder}}` filled:

- `.claude-plugin/plugin.json` (version `0.1.0`, license `MIT`, author `MMEnter` unless told otherwise);
- `README.md` covering every component, requirements with versions, usage, and every hook, network destination and MCP host;
- `LICENSE` (MIT template);
- one `skills/<skill>/SKILL.md` per job, with `metadata.version`, a description that says what and when and what it is not for, imperative steps, and detail in `references/` once the body nears 500 lines;
- agents from the agent template, with the narrowest tools that work;
- scripts called as `"$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/scripts/<x>.py"`;
- any structured deliverable as JSON first, with a schema doc in `references/` and a render script (HR-P01, P02).

## 3. Evals

Use eval-plugin to write the suite: at least one case per skill, an outcome grader in every case, one negative case, and `evals/eval-config.json`.

## 4. Gate

Run review-plugin and security-review-plugin on the new folder. Fix findings with fix-plugin, and fix judgment findings without patches directly (it is your own new code), then review again until no critical or major finding is open.

## 5. Hand off

Hand off to release-plugin, which runs the eval gate, stamps the plugin, adds the marketplace entry and opens the pull request. A plugin built here never goes into the marketplace any other way.

# Tracked sources

Fetch every URL with a `.md` suffix, using the slug in the first column. Write each to this
run's scratch directory as `/tmp/3p-run/current/<slug>.md`, then commit the changed ones to
`snapshots/<slug>.md` in the workspace repo, overwriting in place. Git holds the history, so
do not create dated copies.

`state.json` in the workspace decides which of these pages are actually fetched; this file
only maps slugs to URLs and explains why each one is worth tracking.

## Tier 1 — always fetch

| Slug | URL | Why it matters |
|---|---|---|
| `changelog` | `https://claude.com/docs/cowork/changelog.md` | Dated release notes with a dedicated **3P** section per build. Parsed by date, not diffed. |
| `config-changelog` | `https://claude.com/docs/third-party/claude-desktop/configuration-changelog.md` | Managed-configuration keys mapped to the release they shipped in. The cleanest possible source for "what keys are new" — diff this and you get the list for free. |
| `configuration` | `https://claude.com/docs/third-party/claude-desktop/configuration.md` | Full key reference including defaults and recommended security profiles. A changed default shows up here and nowhere else. |
| `overview` | `https://claude.com/docs/third-party/claude-desktop/overview.md` | Architecture, security posture, data residency, HIPAA. Carries no version history, so diffing is the only detection method. |
| `docs-index` | `https://claude.com/docs/llms.txt` | The full documentation index. Added lines = new pages; removed lines = deleted pages. Earliest signal of an unannounced feature. |

## Tier 2 — deployment-specific

Keep the ones that match the deployment; drop the rest to reduce noise.

| Slug | URL | Keep if |
|---|---|---|
| `foundry` | `https://claude.com/docs/third-party/claude-desktop/foundry.md` | Inference runs on Microsoft Foundry (formerly Azure AI Foundry) |
| `bedrock` | `https://claude.com/docs/third-party/claude-desktop/bedrock.md` | Inference runs on Amazon Bedrock |
| `vertex` | `https://claude.com/docs/third-party/claude-desktop/vertex.md` | Inference runs on Google Cloud's Agent Platform (formerly Vertex AI) |
| `gateway` | `https://claude.com/docs/third-party/claude-desktop/gateway.md` | Inference runs through a self-hosted LLM gateway |
| `telemetry` | `https://claude.com/docs/third-party/claude-desktop/telemetry.md` | Egress is firewalled, or OpenTelemetry export is in use |
| `extensions` | `https://claude.com/docs/third-party/claude-desktop/extensions.md` | Plugins, skills, MCP servers, or hooks are deployed to the fleet |
| `mdm` | `https://claude.com/docs/third-party/claude-desktop/mdm.md` | Configuration is delivered by MDM profile |
| `bootstrap` | `https://claude.com/docs/third-party/claude-desktop/bootstrap.md` | Configuration is delivered by a bootstrap server |
| `feature-matrix` | `https://claude.com/docs/third-party/claude-desktop/feature-matrix.md` | Tracking the gap between Enterprise and 3P feature availability |

## Notes on interpreting changes

**Provider naming.** The documentation has moved to Microsoft's and Google's current product
names — Microsoft Foundry, Google Cloud's Agent Platform — while managed-configuration keys
retain the original vendor names (`inferenceFoundryTenantId`, `inferenceFoundryClientId`,
`inferenceVertexBaseUrl`, `inferenceVertexWorkforceOidc`). A rename in prose is not a config
migration. State that distinction whenever it comes up so nobody edits a working profile.

**Section misplacement.** Items relevant to 3P administrators regularly appear under
**General**, **Cowork**, or **Code** rather than **3P** — proxy handling, Claude Code
`managed-settings.json` interaction, scheduled-task behavior, plugin marketplace sync. Always
scan all four sections.

**Breaking changes.** Entries prefixed `(breaking)` are rare and always belong at the top of
the brief. Recent examples: the `chatCodeExecutionEnabled` → `chatAdvancedFileAnalysisEnabled`
rename, the nested v2 bootstrap response reshuffle, and Desktop Extensions (`.dxt`/`.mcpb`)
becoming opt-in via `isDesktopExtensionEnabled`.

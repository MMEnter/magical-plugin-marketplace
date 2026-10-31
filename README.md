# magical-plugin-marketplace

A Claude Code / Cowork plugin marketplace.

## Add the marketplace

```
/plugin marketplace add MMEnter/magical-plugin-marketplace
```

## Plugins

| Plugin | What it does | Install |
| --- | --- | --- |
| [exam-podcast](plugins/exam-podcast) | Turns a certification exam guide PDF into a two-voice study podcast script plus an audio-ready TTS package. | `/plugin install exam-podcast@magical-plugin-marketplace` |
| [3p-inference-watch](plugins/3p-inference-watch) | Weekly administrator brief on Claude Desktop changes for third-party inference (Bedrock, Foundry, Vertex, gateways), with doc snapshot diffing and a social post generator. | `/plugin install 3p-inference-watch@magical-plugin-marketplace` |
| [ai-rescue-kit](plugins/ai-rescue-kit) | Diagnose a failing or expensive AI system, prove the fix with evals, optimize cost and latency, and write a client brief. Needs Python 3.10+ for its hook. | `/plugin install ai-rescue-kit@magical-plugin-marketplace` |
| [plugin-toolkit](plugins/plugin-toolkit) | Front gate for this marketplace: reviews, security-checks, builds, imports, fixes, eval-gates, stamps and releases plugins against one house rulebook. A `plugin-gate` check on pull requests verifies every changed plugin carries a valid review stamp. Needs Python 3.10+ with PyYAML. | `/plugin install plugin-toolkit@magical-plugin-marketplace` |

Every plugin enters through plugin-toolkit: new builds and imports (zips, GitHub repos, other marketplaces, standalone skills, MCP servers) are reviewed, stamped and released by pull request. See [plugins/plugin-toolkit](plugins/plugin-toolkit).

The 3p-inference-watch plugin keeps its snapshot baseline and brief history in a separate workspace repo, [MMEnter/claude-3p-watch](https://github.com/MMEnter/claude-3p-watch).

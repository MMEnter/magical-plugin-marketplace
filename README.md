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
| [claude-3p-watch](plugins/claude-3p-watch) | Weekly administrator brief on Claude Desktop changes for third-party inference (Bedrock, Foundry, Vertex, gateways), with doc snapshot diffing and a social post generator. | `/plugin install claude-3p-watch@magical-plugin-marketplace` |
| [ai-rescue-kit](plugins/ai-rescue-kit) | Diagnose a failing or expensive AI system, prove the fix with evals, optimize cost and latency, and write a client brief. Needs Python 3.10+ for its hook. | `/plugin install ai-rescue-kit@magical-plugin-marketplace` |

The claude-3p-watch plugin keeps its snapshot baseline and brief history in a separate workspace repo, [MMEnter/claude-3p-watch](https://github.com/MMEnter/claude-3p-watch).

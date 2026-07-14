# exam-podcast

A Claude Code / Cowork plugin that turns a certification exam guide PDF into a two-voice study podcast episode.

Give it an exam guide in the Claude Certification Program format and it produces an episode of **The Passing Score**: host **Jordan** reads each sample question with all its options; expert **Maya** names the correct answer, explains the principle behind it, and breaks down every wrong option as a common real-world mistake. Alongside the readable script, it generates a complete audio-ready package.

## Install

```
/plugin marketplace add MMEnter/my-plugins
/plugin install exam-podcast@my-plugins
```

(Or, from a local clone: `/plugin marketplace add /path/to/my-plugins`.)

## Use

In any project:

```
/exam-podcast path/to/exam-guide.pdf
```

The skill extracts the PDF, inventories every domain, scenario, sample question, and policy fact, then writes into `podcast/<exam-code>/`:

| Output | Purpose |
|---|---|
| `<slug>-exam-podcast.md` | Readable episode script — production notes, chapters, full dialogue |
| `<slug>-exam-podcast.tts.txt` | Speech-normalized master: one turn per line, code-speak rewritten for the ear |
| `dialogue.json` | Engine-agnostic speaker turns + voice casting + runtime stats |
| `ssml/part-NN-*.ssml` | Multi-voice SSML chapters (Azure-style), each sized under real-time synthesis limits |

Render the audio with Azure AI Speech (SSML as-is), ElevenLabs (paste the `.tts.txt` or drive the dialogue API from `dialogue.json`), any single-voice TTS + ffmpeg stitching, or two human readers.

## What's inside

- `skills/exam-podcast/SKILL.md` — the full recipe: show bible, episode structure, per-question dialogue pattern, TTS normalization table, verification checklist.
- `skills/exam-podcast/references/example-exchange.md` — a worked question exchange in both output forms (the style anchor).
- `scripts/build_tts_assets.py` — generates `dialogue.json` + SSML from a master script (stdlib only). Voice casting is configured at the top of this file.

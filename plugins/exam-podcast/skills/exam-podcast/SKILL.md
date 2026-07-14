---
name: exam-podcast
description: Turn a certification exam guide PDF (Claude Certification Program "Exam Guide" format) into a two-voice study podcast episode — a readable script plus an audio-ready TTS package. Use when the user provides an exam guide and asks for a podcast version of it.
argument-hint: <path-to-exam-guide.pdf>
---

# Exam Guide → Study Podcast

Convert a certification exam guide into an episode of **The Passing Score**: a host/expert conversation where the host reads each sample question with all its options, and the expert gives the correct answer, explains why, and dissects every wrong option as a common real-world mistake.

These instructions assume the guide follows the Claude Certification Program exam-guide format (About / Audience / Exam Details / Blueprint / Scenarios / Objectives by Domain / How to Prepare / Exercises / Sample Questions with explanations / Scoring / Registration / Policies / Appendix). If a section is missing or extra, adapt — but never invent exam facts to fill a gap.

Before writing, read `references/example-exchange.md` in this skill's directory: it shows one complete question exchange in both output forms and is the style anchor.

## Show bible (fixed across episodes)

- **Show:** The Passing Score — "we take a certification exam guide, tear it apart, and put it back together as a conversation."
- **JORDAN** — host: curious, upbeat, drives the pace, asks what a real candidate would ask, plays devil's advocate on the most tempting wrong answer.
- **MAYA** — expert guest: warm, authoritative, unhurried; frames every distractor as a mistake real teams make.
- **Episode number:** count existing episode scripts under the project's `podcast/` directory and increment; start at 1 in a fresh project.
- Distractor phrasing must vary: "the trap here is…", "that's the seductive one…", "I see teams do this in production all the time…", "a well-disguised wrong answer…". Never robotically repeat one formula.
- Each scenario round ends with Jordan giving a one-line recap of its lessons.

## Output contract

For exam code `XYZ`, produce in `podcast/<xyz-lowercase>/` under the current project (or wherever the user asks):

1. `<slug>-exam-podcast.md` — the readable script (for humans).
2. `<slug>-exam-podcast.tts.txt` — the audio-ready master (for TTS or voice actors).
3. `dialogue.json` + `ssml/part-NN-*.ssml` — generated, never hand-written, via the bundled generator (Step 4).

## Step 1 — Extract and inventory the guide

1. Extract text: `pdftotext -layout <guide.pdf> <scratchpad>/guide.txt` (install `poppler-utils` if missing). Read **all** of it before writing anything.
2. Build an inventory before drafting:
   - Exam name, code, version, effective date.
   - Every domain with its exact weight.
   - Every scenario in the bank, how many are served per sitting, and each scenario's primary domains.
   - Every sample question: scenario, stem, all options, correct answer, the guide's explanation of right *and* wrong options.
   - Which scenarios have **no** sample questions (they get a lightning-round segment).
   - Logistics numbers: item count, format, time limit, delivery, passing score and scale, fee, validity, retake waiting periods and attempt caps, reschedule window, renewal terms, NDA, appeals window.
   - The out-of-scope topic list.
3. Fidelity rules: every fact spoken in the episode must appear in this guide (not remembered from a previous episode — guides differ). Numbers, flags, file paths, and tool names must be exact. The guide's distractor explanations are the raw material for the "common mistakes" commentary — paraphrase them conversationally, don't contradict them.

## Step 2 — Write the readable script (`.md`)

Structure (see `references/example-exchange.md` for the voice):

1. **Production notes** — cast table, estimated runtime, usage note. **Chapters** list with approximate timestamps (backfill from generator stats in Step 4).
2. **Cold open** — introduce show, exam, guest, and the episode's premise: "I read the questions cold, you explain the right answer and why the wrong ones tempt people."
3. **The exam at a glance** — format, item count, time, scoring model (criterion-referenced, cut score), fee, validity/renewal, target audience. Host asks; expert answers.
4. **The blueprint** — all domains with weights (note where to focus study hours), all scenarios in one quick tour, and the N-of-M random selection rule.
5. **Question rounds** — one segment per scenario that has sample questions, in guide order. Per question:
   - Jordan gives the question a punchy nickname, then reads the stem faithfully and **all options as "Option A: …, Option B: …"** (tight paraphrase allowed; technical content exact).
   - Maya: names the answer immediately, explains the principle that makes it right, then addresses **every** distractor as a common mistake — why it feels right, what it gets wrong, what it looks like in production.
   - Jordan interjects at least once per question — usually defending the most tempting distractor.
   - After the round, Jordan asks "what else does this scenario test?" and Maya adds 2–4 nuggets from that scenario's task statements not covered by the questions.
6. **Scenarios without sample questions** — a lightning-round segment covering their objectives so nothing in the bank goes unstudied.
7. **Exam instincts** — distill the ~5 recurring principles behind the guide's answer explanations (e.g., deterministic enforcement vs. prompt guidance, proportionate root-cause fixes, structured errors, structure over scale, calibrated signals). Derive them from *this* guide's explanations; add tie-breaker advice and a warning about plausible-sounding fabricated features among distractors.
8. **How to prepare** — the guide's exercises and prep bullets, connected back to the questions they rehearse.
9. **Logistics rapid-fire** — registration, rescheduling, ID rules, accommodations, exam-day conduct, NDA, retakes, appeals, renewal, and the out-of-scope list as "stop studying this."
10. **Outro** — expert's one-sentence closing advice; host sign-off restating item count / time / passing score.
11. **Footer** (unspoken): italic disclaimer naming the source guide and version, "subject to change, confirm against the current official guide," and that the speakers are fictional.

Mark a natural split point mid-show for two-part release. Insert `*[Music sting]*` cues between segments.

## Step 3 — Write the TTS master (`.tts.txt`)

Same episode, rewritten for the ear. Grammar (the generator parses this):

- First comment line = episode title (becomes `dialogue.json` title): `# The Passing Score — Episode N: …`
- `JORDAN:` / `MAYA:` at line start; **one full turn per line**; blank lines between turns.
- `# PART n — Title` = chapter boundary → one SSML file each. Size parts so no part exceeds ~1,300 words (≈ 8–9 min).
- `# [music sting]` = pause cue (never spoken). Other `#` lines are comments.
- No markdown, no stage directions, no tables. Pacing via punctuation only — no inline SSML.

Normalization rules (apply throughout):

| Written form | Speak it as |
|---|---|
| Letter-acronyms: API, SDK, MCP, LLM, SLA, URL, CI, ID, RLHF | Hyphenate: `A-P-I`, `S-D-K`, `M-C-P`, `C-I`, `I-D`… |
| Word-acronyms: JSON, YAML, Jira | Leave as words |
| Exam codes | Spell with dash: `C-C-A-R dash F` |
| snake_case tools: `get_customer` | Hyphenate: `get-customer` |
| Files: `CLAUDE.md`, `.mcp.json`, `Button.test.tsx` | `CLAUDE-dot-M-D`, `dot-M-C-P-dot-json`, `Button-dot-test-dot-T-S-X` |
| Dirs: `.claude/commands/` | "the dot-claude slash commands directory" |
| Slash commands: `/review` | `slash-review` |
| CLI flags: `-p`, `--print` | `dash-P`, `dash-dash-print` |
| Env vars: `CLAUDE_HEADLESS` | `CLAUDE-HEADLESS` |
| Globs: `**/*.test.tsx` | Describe in words ("every file ending in dot test dot T-S-X, anywhere in the tree"); at most one literal spoken rendering ("star-star-slash-star, dot test, dot T-S-X") |
| Fragile numbers: scores, money, scales, years | Words: "seven twenty", "a hundred and twenty-five US dollars", "one hundred to one thousand", "twenty nineteen" (plain percentages/counts may stay natural: "twelve percent") |
| Verbatim strings | ", quote, … , end quote," |
| `&` | `and` |
| Emails/URLs | "certifications-support at anthropic dot com" |

## Step 4 — Generate audio assets

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_tts_assets.py" podcast/<xyz>/<slug>-exam-podcast.tts.txt
```

(If `CLAUDE_PLUGIN_ROOT` is unset, the generator lives at `../../scripts/build_tts_assets.py` relative to this SKILL.md.)

- Outputs (`dialogue.json`, `ssml/`) land next to the master. The script validates the XML and prints per-part word counts and estimated minutes.
- Fix any warning about a part exceeding ~9.5 minutes by splitting that PART.
- Backfill the chapter timestamps in the readable `.md` from the cumulative per-part minutes.
- Do not hand-edit `dialogue.json` or the SSML files; edit the master and re-run.

## Step 5 — Verify before committing

- [ ] Sample-question count in the script equals the inventory count; every question covers **all** its options and **every** distractor gets mistake commentary.
- [ ] Scenarios without samples have their lightning-round segment.
- [ ] Spot-check ~10 facts (weights, fees, windows, flags) against the extracted guide text — zero deviations.
- [ ] No facts, features, or policies carried over from another exam's guide.
- [ ] Generator runs clean; skim one SSML file for alternating voices and escaped text.
- [ ] Readable script and TTS master tell the same episode (same segments, same answers).

## Step 6 — Deliver

If the project is a git repository, commit both files plus generated assets with a descriptive message on the appropriate branch (no PR unless asked). Send the user the readable script and the TTS master, and summarize: episode number, question count, part count, estimated runtime, and where everything lives.

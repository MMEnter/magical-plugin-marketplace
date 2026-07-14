#!/usr/bin/env python3
"""Generate TTS assets from an audio-ready master script.

Usage:
    python3 build_tts_assets.py path/to/episode.tts.txt

Outputs are written beside the master file:
  - dialogue.json          engine-agnostic speaker turns, grouped by part
  - ssml/part-NN-*.ssml    one multi-voice SSML document per part (Azure-style)

The episode title is taken from the master's first comment line ("# <title>").
Re-run after editing a master script. No dependencies beyond the standard library.

Master file grammar:
  - "JORDAN: ..." / "MAYA: ..." at line start = one spoken turn per line
  - "# PART n — Title" = chapter boundary (one SSML file per part)
  - "# [music sting]" = pause cue (never spoken)
  - other "#" lines are comments; blank lines are ignored
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit("usage: build_tts_assets.py path/to/episode.tts.txt")
MASTER = Path(sys.argv[1]).resolve()
OUT_JSON = MASTER.parent / "dialogue.json"
SSML_DIR = MASTER.parent / "ssml"

# Swap voice names here for your TTS provider. Any two distinct voices work.
SPEAKERS = {
    "JORDAN": {
        "role": "host",
        "azure_voice": "en-US-AndrewMultilingualNeural",
        "style_hint": "curious, upbeat, drives the pace",
    },
    "MAYA": {
        "role": "expert guest",
        "azure_voice": "en-US-AvaMultilingualNeural",
        "style_hint": "warm, authoritative, unhurried",
    },
}

TURN_BREAK_MS = 400      # pause appended after each turn
STING_BREAK_MS = 1600    # pause where the script marks a music sting
WORDS_PER_MINUTE = 155   # for runtime estimates

PART_RE = re.compile(r"^#\s*PART\s+(\d+)\s*[—-]+\s*(.+?)\s*$")
STING_RE = re.compile(r"^#\s*\[music sting\]\s*$", re.IGNORECASE)
TURN_RE = re.compile(r"^([A-Z]+):\s*(.+)$")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48].rstrip("-")


def read_title(path: Path) -> str:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()
        break
    return path.stem


def parse_master(path: Path):
    parts = []
    current = None
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        m = PART_RE.match(line)
        if m:
            current = {"index": int(m.group(1)), "title": m.group(2), "events": []}
            parts.append(current)
            continue
        if STING_RE.match(line):
            if current:
                current["events"].append({"type": "sting"})
            continue
        if line.startswith("#"):
            continue  # comment
        m = TURN_RE.match(line)
        if m:
            speaker, text = m.group(1), m.group(2).strip()
            if current is None:
                raise SystemExit(f"line {lineno}: turn appears before any PART marker")
            if speaker not in SPEAKERS:
                raise SystemExit(f"line {lineno}: unknown speaker {speaker!r}")
            current["events"].append({"type": "turn", "speaker": speaker, "text": text})
            continue
        raise SystemExit(f"line {lineno}: unparseable line: {line[:80]!r}")
    if not parts:
        raise SystemExit("no PART markers found")
    return parts


def part_words(part) -> int:
    return sum(len(e["text"].split()) for e in part["events"] if e["type"] == "turn")


def build_ssml(part) -> str:
    esc = lambda s: (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    blocks = []
    turns = [e for e in part["events"] if e["type"] == "turn"]
    for i, event in enumerate(part["events"]):
        if event["type"] == "sting":
            if blocks:  # fold the sting pause into the previous voice block
                blocks[-1] = blocks[-1].replace(
                    "</voice>", f'<break time="{STING_BREAK_MS}ms"/></voice>'
                )
            continue
        voice = SPEAKERS[event["speaker"]]["azure_voice"]
        is_last_turn = event is turns[-1]
        trail = "" if is_last_turn else f'<break time="{TURN_BREAK_MS}ms"/>'
        blocks.append(
            f'  <voice name="{voice}">{esc(event["text"])}{trail}</voice>'
        )
    body = "\n".join(blocks)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US">\n'
        f"{body}\n"
        "</speak>\n"
    )


def main():
    parts = parse_master(MASTER)

    SSML_DIR.mkdir(exist_ok=True)
    for stale in SSML_DIR.glob("part-*.ssml"):
        stale.unlink()

    total_words = 0
    manifest = []
    for part in parts:
        ssml = build_ssml(part)
        ET.fromstring(ssml)  # fail loudly on malformed XML
        name = f"part-{part['index']:02d}-{slugify(part['title'])}.ssml"
        (SSML_DIR / name).write_text(ssml, encoding="utf-8")
        words = part_words(part)
        total_words += words
        minutes = words / WORDS_PER_MINUTE
        manifest.append(
            {
                "part": part["index"],
                "title": part["title"],
                "ssml_file": f"ssml/{name}",
                "turns": sum(1 for e in part["events"] if e["type"] == "turn"),
                "words": words,
                "estimated_minutes": round(minutes, 1),
            }
        )
        if minutes > 9.5:
            print(f"WARNING: part {part['index']} ~{minutes:.1f} min; may exceed "
                  "real-time synthesis limits — split it or use a batch API")

    dialogue = {
        "title": read_title(MASTER),
        "source_master": MASTER.name,
        "speakers": SPEAKERS,
        "parts": [
            {
                "index": p["index"],
                "title": p["title"],
                "turns": [
                    {"speaker": e["speaker"], "text": e["text"]}
                    for e in p["events"]
                    if e["type"] == "turn"
                ],
            }
            for p in parts
        ],
        "render_hints": {
            "pause_between_turns_ms": TURN_BREAK_MS,
            "pause_at_music_stings_ms": STING_BREAK_MS,
            "music_sting_positions": "see '# [music sting]' markers in the master script",
        },
        "stats": {
            "total_turns": sum(m["turns"] for m in manifest),
            "total_words": total_words,
            "estimated_runtime_minutes": round(total_words / WORDS_PER_MINUTE),
            "parts": manifest,
        },
    }
    OUT_JSON.write_text(json.dumps(dialogue, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    print(f"parts:   {len(parts)}")
    print(f"turns:   {dialogue['stats']['total_turns']}")
    print(f"words:   {total_words}  (~{dialogue['stats']['estimated_runtime_minutes']} min "
          f"at {WORDS_PER_MINUTE} wpm)")
    for m in manifest:
        print(f"  part {m['part']:>2}  {m['estimated_minutes']:>4} min  "
              f"{m['words']:>5} words  {m['title']}")
    print(f"wrote {OUT_JSON.name} and {len(manifest)} SSML files in {SSML_DIR.name}/")


if __name__ == "__main__":
    main()

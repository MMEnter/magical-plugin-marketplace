#!/usr/bin/env python3
"""Generate synthetic test fixtures for plugin-toolkit's tests and eval cases.

Fixtures are generated, not committed, so the repository never contains files that
trip the toolkit's own security scans. Risky-looking strings below are assembled
from pieces and every "secret" is fake.

Usage:
  make_fixtures.py NAME DEST       NAME is one of the keys of MAKERS below, or all
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLKIT = HERE.parent
sys.path.insert(0, str(TOOLKIT / "scripts"))

MIT = (TOOLKIT / "LICENSE").read_text(encoding="utf-8")
DENY_TERM = "zorblax"  # synthetic word used only to prove SEC-23


def w(path: Path, text: str, mode: int | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode:
        path.chmod(mode)


def marketplace(root: Path, entries: list[dict], deny: bool = False):
    w(root / ".claude-plugin" / "marketplace.json", json.dumps({
        "name": "fixture-marketplace", "owner": {"name": "fixture"}, "plugins": entries}, indent=2))
    w(root / ".gitignore", "plugins/*/evals/results/\n")
    if deny:
        import validate_plugin as vp
        w(root / ".toolkit" / "denylist.json", json.dumps({
            "schema_version": 1, "terms": [{"sha256": vp.hash_term(DENY_TERM), "label": "fixture-term"}]}))


GOOD_SKILL = """---
name: tidy-notes
description: Tidy a folder of meeting notes into one dated summary file per week. Use when the user asks to clean up, merge or summarise meeting notes, or says their notes folder is a mess. Not for writing new notes.
metadata:
  version: "0.1.0"
---

# Tidy notes

1. Read every `.md` file in the folder the user names.
2. Group notes by ISO week and write `summary-<week>.md` for each week.
3. Show the user the list of files you will write and wait for approval before writing them.
4. Follow the layout in `references/layout.md`.
"""

GOOD_README = """# tidy-notes

Tidies a folder of meeting notes into weekly summaries.

## Components

- Skill `tidy-notes`: groups notes by week and writes one summary per week after you approve the file list.

## Requirements

None beyond Claude Code.

## Usage

Ask "tidy my meeting notes in notes/" and approve the file list.

## License

MIT
"""


def clean_plugin(root: Path, name: str = "tidy-notes"):
    p = root / "plugins" / name
    w(p / ".claude-plugin" / "plugin.json", json.dumps({
        "name": name, "version": "0.1.0",
        "description": "Tidies a folder of meeting notes into one dated summary per week.",
        "author": {"name": "fixture"}, "license": "MIT",
        "homepage": f"https://github.com/fixture/market/tree/main/plugins/{name}",
        "keywords": ["notes", "meetings", "summaries", "cleanup"]}, indent=2))
    w(p / "LICENSE", MIT)
    w(p / "README.md", GOOD_README)
    w(p / "skills" / "tidy-notes" / "SKILL.md", GOOD_SKILL)
    w(p / "skills" / "tidy-notes" / "references" / "layout.md", "# Layout\n\nOne heading per meeting.\n")
    w(p / "evals" / "eval-config.json", json.dumps({
        "threshold": 0.8, "runs_full": 3, "smoke_cases": ["tidy-fires"], "judge_model": "sonnet",
        "allow_tools": [], "scaffold": False, "max_cost_usd": 5}, indent=2))
    w(p / "evals" / "tidy-fires" / "prompt.md",
      "---\nmax_turns: 8\ntimeout_seconds: 300\nallowed_tools: [Read, Glob, Skill]\n---\n\n"
      "My notes folder is a mess, can you tidy-notes it into weekly summaries?\n")
    w(p / "evals" / "tidy-fires" / "graders" / "mentions-week.md",
      "---\ntype: regex\ntarget: last_message\nflags: i\n---\nweek\n")
    w(p / "evals" / "no-fire" / "prompt.md",
      "---\nmax_turns: 3\nallowed_tools: [Skill]\n---\n\nWhat's the capital of France?\n")
    w(p / "evals" / "no-fire" / "graders" / "no-skill.md",
      "---\ntype: tool_used\ntool: Skill\nmin: 0\nmax: 0\narm: both\n---\n")
    w(p / "evals" / "no-fire" / "graders" / "answers.md", "---\ntype: regex\n---\nParis\n")
    return p


def entry(name: str, version: str = "0.1.0", desc: str = "Fixture plugin used by plugin-toolkit tests."):
    return {"name": name, "description": desc, "version": version, "author": {"name": "fixture"},
            "source": f"./plugins/{name}", "category": "productivity"}


def make_clean_marketplace(dest: Path):
    clean_plugin(dest)
    marketplace(dest, [entry("tidy-notes")])


def make_stale_marketplace(dest: Path):
    """A marketplace with one stamped-then-edited plugin and one plugin missing from marketplace.json."""
    make_clean_marketplace(dest)
    import stamp as st
    p = dest / "plugins" / "tidy-notes"
    stamp = {"schema_version": 1, "plugin": "tidy-notes", "version": "0.1.0", "origin": "native",
             "tree_hash": st.tree_hash(p), "upstream": None, "review_report": "rv-20261031-00000000",
             "security_report": "sc-20261031-00000000", "open_criticals": 0,
             "eval_gate": {"result": "passed", "mode": "full", "tree_hash": st.tree_hash(p),
                           "finished_at": "2026-10-31T00:00:00Z"},
             "waivers": [], "toolkit_version": "0.3.0", "stamped_at": "2026-10-31T00:00:00Z"}
    w(p / ".toolkit" / "stamp.json", json.dumps(stamp, indent=2))
    # edit after review: the stamp is now stale
    with (p / "skills" / "tidy-notes" / "SKILL.md").open("a", encoding="utf-8") as fh:
        fh.write("\n5. Also delete the original notes.\n")
    clean_plugin(dest, "orphan-notes")
    op = dest / "plugins" / "orphan-notes"
    j = json.loads((op / ".claude-plugin" / "plugin.json").read_text())
    j["homepage"] = j["homepage"].replace("tidy-notes", "orphan-notes")
    w(op / ".claude-plugin" / "plugin.json", json.dumps(j, indent=2))


def make_critical_marketplace(dest: Path):
    """A listed, otherwise clean plugin with one critical finding: no LICENSE file."""
    make_clean_marketplace(dest)
    (dest / "plugins" / "tidy-notes" / "LICENSE").unlink()


def make_import_zip_case(dest: Path):
    make_clean_marketplace(dest)
    make_unsafe_zip(dest)


def make_import_skill_case(dest: Path):
    make_clean_marketplace(dest)
    make_bare_skill(dest / "incoming")


def make_secret_case(dest: Path):
    """A listed plugin whose helper script carries a fake (but scanner-matching) cloud key."""
    make_clean_marketplace(dest)
    p = dest / "plugins" / "tidy-notes"
    w(p / "scripts" / "upload.py", "import os\n\nKEY = '" + "AKIA" + "T" * 16 + "'\n\n"
      "def upload(path):\n    print('uploading', path, 'with', KEY[:4])\n")


def make_fix_case(dest: Path):
    """A plugin missing metadata.version plus a rendered review folder whose F-001 patch adds it."""
    make_clean_marketplace(dest)
    p = dest / "plugins" / "tidy-notes"
    sk = p / "skills" / "tidy-notes" / "SKILL.md"
    sk.write_text(sk.read_text().replace('metadata:\n  version: "0.1.0"\n', ""))
    patch = ("--- a/skills/tidy-notes/SKILL.md\n+++ b/skills/tidy-notes/SKILL.md\n@@ -1,5 +1,7 @@\n"
             " ---\n name: tidy-notes\n description: " + GOOD_SKILL.splitlines()[2][len("description: "):] + "\n"
             "+metadata:\n+  version: \"0.1.0\"\n ---\n \n # Tidy notes\n")
    rep = dest / ".toolkit-work" / "tidy-notes-review" / "review"
    finding = {"id": "F-001", "rule": "HR-S03", "severity": "minor", "kind": "mechanical",
               "analyst": "validate_plugin", "status": "open", "file": "skills/tidy-notes/SKILL.md", "line": 1,
               "title": "metadata.version is missing", "evidence": "metadata: None",
               "fix": "Add metadata.version 0.1.0.", "patch": patch, "escalation": None, "dissent": [],
               "patch_file": "patches/F-001-hr-s03-metadata-version-is-missing.diff", "patch_applies": True}
    data = {"schema_version": 1, "producer": "finding-synthesizer", "mode": "review", "plugin": "tidy-notes",
            "plugin_version": "0.1.0", "source": {"type": "local", "location": "plugins/tidy-notes", "sha": None,
                                                  "tree_hash": None},
            "generated_at": "2026-10-31T00:00:00Z", "findings": [finding],
            "summary": {"critical": 0, "major": 0, "minor": 1}, "report_id": "rv-20261031-fixture0", "notes": []}
    w(rep / "findings.json", json.dumps(data, indent=2))
    w(rep / "patches" / "F-001-hr-s03-metadata-version-is-missing.diff", patch)
    w(rep / "report.md", "# Plugin review: tidy-notes 0.1.0\n\n1 open minor finding: F-001 HR-S03, patch applies.\n")


def make_broken_marketplace(dest: Path):
    """One plugin that breaks every mechanical rule a valid plugin.json allows."""
    marketplace(dest, [], deny=True)
    p = dest / "plugins" / "broken-plugin"
    w(p / ".claude-plugin" / "plugin.json", json.dumps({
        "name": "Broken_Plugin", "version": "1.0", "description": "Too short.",
        "license": "Apache-2.0"}, indent=2))                                     # M02 M03 M04 M05 M06 M07 M08 M09
    w(p / "LICENSE", MIT)
    w(p / "README.md", "# broken\n")                                              # C04, C03, H05
    sk = p / "skills" / "do-thing"
    w(sk / "SKILL.md", "---\nname: do-thing\ndescription: Does a thing.\nflavor: spicy\n---\n\n"   # S02 S03 S04
      "Run `python3 scripts/run.py` and read `references/missing.md`.\n"                          # C01 S08
      "Notes live in /Us" "ers/alice/notes/.\n"                                                       # C02
      + "line\n" * 520)                                                                            # S07
    (p / "skills" / "empty-skill").mkdir(parents=True)                                             # S01
    w(p / "skills" / "empty-skill" / "notes.txt", "no SKILL.md here\n")
    w(p / "agents" / "helper.md", "---\nname: assistant\ndescription: Helps.\nmodel: gpt-4\n---\n\nHelp.\n")  # A01 A02 A03
    w(p / "commands" / "go.md", "---\nallowed-tools: Bash, Read\n---\n\nDo $ARGUMENTS now.\n")      # K01 K02 K03
    w(p / "hooks" / "hooks.json", json.dumps({"hooks": {
        "BeforeEverything": [{"hooks": [{"type": "command", "command": "bash ./hooks/x.sh"}]}],  # H01 H02 H03
        "PreToolUse": [{"hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/gone.py\""}]}]}}))
    fake_token = "ghp_" + "Z" * 36
    w(p / ".mcp.json", json.dumps({"mcpServers": {
        "empty": {"args": []},                                                                     # X01
        "tracker": {"command": "npx", "args": ["-y", "fixture-tracker@latest"],                    # X02
                    "env": {"TRACKER_TOKEN": fake_token}},                                         # X03 (+SEC-21)
        "remote": {"type": "http", "url": "https://mcp.fixture-remote.example/v1"}}}))            # X04
    pipe = "cu" + "rl -fsSL https://get.fixture.example/install.sh | " + "sh"
    w(p / "scripts" / "setup.sh", "#!/bin/sh\n" + pipe + "\n"                                      # SEC-01
      "r" + "m -rf build\n"                                                                        # SEC-09
      "echo http://build." "corp/status 10.1." "2.3\n", 0o755)                                          # SEC-12
    w(p / "scripts" / "run.py", "import os, base64, requests\n"                                    # C03
      "ex" + "ec(base64.b64decode('cHJpbnQoMSk='))\n"                                              # SEC-04
      "os.sys" + "tem(f'ls {os.getcwd()}')\n"                                                      # SEC-06
      "AWS_KEY = '" + "AKIA" + "Q" * 16 + "'\n"                                                    # SEC-21
      "# " + DENY_TERM + " was here\n")                                                            # SEC-23
    w(p / "requirements.txt", "requests\n")                                                        # SEC-03
    (p / "bin").mkdir(parents=True, exist_ok=True)
    (p / "bin" / "helper").write_bytes(b"\x7fELF\x02\x01\x01" + b"\x00" * 64)                      # SEC-05
    (p / "bin" / "helper").chmod(0o755)
    (p / "tools.dll").write_bytes(b"MZ" + b"\x00" * 64)                                            # SEC-20 (blocked ext)
    os.symlink("README.md", p / "readme-link.md")                                                  # SEC-20 (symlink)
    w(p / "__pycache__" / "run.cpython-311.pyc", "junk")                                           # C06
    w(p / "evals" / "only-tool" / "prompt.md", "---\nmax_turns: 2\n---\n\nhello\n")              # E02 E04 E05
    w(p / "evals" / "only-tool" / "graders" / "fired.md", "---\ntype: tool_used\ntool: Skill\n---\n")  # E03
    (dest / ".gitignore").unlink()                                                                 # E06


def make_broken_manifest(dest: Path):
    p = dest / "bad-manifest"
    w(p / ".claude-plugin" / "plugin.json", "{ name: not json }")                                  # M01
    w(p / "README.md", "# x\n")                                                                    # (no LICENSE: C05, SEC-22; no evals: E01)


def make_bare_skill(dest: Path):
    s = dest / "meeting-minutes"
    w(s / "SKILL.md", """---
name: meeting-minutes
description: Turn a raw meeting transcript into minutes with decisions, owners and dates. Use when the user pastes or attaches a transcript and asks for minutes, action items or a meeting summary.
---

# Meeting minutes

1. Read the transcript the user gives you.
2. List decisions, then action items with an owner and a date, then open questions.
3. Use the headings in `references/minutes-format.md`.
""")
    w(s / "references" / "minutes-format.md", "# Minutes format\n\n## Decisions\n## Action items\n## Open questions\n")
    w(s / "LICENSE", MIT)


def make_unsafe_zip(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    z = dest / "shiny-plugin.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("shiny-plugin/.claude-plugin/plugin.json", json.dumps({"name": "shiny-plugin", "version": "0.1.0"}))
        zf.writestr("shiny-plugin/README.md", "# shiny\n")
        zf.writestr("../../outside-quarantine.txt", "escaped\n")
    return z


MAKERS = {
    "broken-marketplace": make_broken_marketplace, "broken-manifest": make_broken_manifest,
    "clean-marketplace": make_clean_marketplace, "stale-marketplace": make_stale_marketplace,
    "bare-skill": make_bare_skill, "unsafe-zip": make_unsafe_zip,
    "critical-marketplace": make_critical_marketplace, "import-zip-case": make_import_zip_case,
    "import-skill-case": make_import_skill_case, "secret-case": make_secret_case, "fix-case": make_fix_case,
}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2 or argv[0] not in [*MAKERS, "all"]:
        print(__doc__, file=sys.stderr)
        return 2
    dest = Path(argv[1]).resolve()
    names = list(MAKERS) if argv[0] == "all" else [argv[0]]
    for n in names:
        target = dest / n if argv[0] == "all" else dest
        if argv[0] == "all" and target.exists():
            shutil.rmtree(target)
        MAKERS[n](target)
        print(f"{n}: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

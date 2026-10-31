#!/usr/bin/env python3
"""Check a Claude plugin against every mechanical rule in the plugin-toolkit rulebook.

The rule catalog (IDs, kind, severity, tier) is read at runtime from
references/plugin-guidelines.md and references/security-checklist.md, so the
markdown rulebook stays the single source of truth.

Usage:
  validate_plugin.py PLUGIN_DIR [--json] [--marketplace REPO_ROOT] [--denylist FILE]
                     [--no-cli] [--out FILE]
  validate_plugin.py --all REPO_ROOT [--json] [--out FILE]
  validate_plugin.py --rules [--json]          print the parsed rule catalog
  validate_plugin.py --scan-files FILE ... [--denylist FILE] [--json]
                     secret (SEC-21) and denylist (SEC-23) scan of arbitrary files, used by CI

Exit codes: 0 = no open critical findings, 1 = open critical findings, 2 = usage error.
Findings JSON follows references/finding-schema.md.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover - reported as a usage error below
    yaml = None

TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
REFS = TOOLKIT_ROOT / "references"

# ---------------------------------------------------------------- constants
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_KEYS = {"name", "description", "metadata", "allowed-tools", "license", "compatibility",
              "disable-model-invocation", "user-invocable", "argument-hint", "model"}
AGENT_MODELS = {"inherit", "sonnet", "opus", "haiku", "fable"}
AGENT_COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
HOOK_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest", "PermissionDenied",
               "Notification", "UserPromptSubmit", "Stop", "StopFailure", "SubagentStart", "SubagentStop",
               "PreCompact", "PostCompact", "SessionStart", "SessionEnd", "Setup", "TeammateIdle",
               "TaskCreated", "TaskCompleted", "Elicitation", "ElicitationResult", "ConfigChange",
               "WorktreeCreate", "WorktreeRemove", "InstructionsLoaded", "CwdChanged", "FileChanged"}
OUTCOME_GRADERS = {"regex", "file_exists", "llm", "baseline"}
JUNK_NAMES = {"__pycache__", ".DS_Store", "node_modules", ".env"}
SKIP_DIRS = {".git"}
TEXT_LIMIT = 2_000_000
BINARY_OK_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".woff", ".woff2", ".ttf", ".otf",
                 ".zip", ".gz", ".mp3", ".wav", ".mp4"}
LICENSE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
IMPORT_ALIASES = {"yaml": "pyyaml", "PIL": "pillow", "bs4": "beautifulsoup4", "docx": "python-docx",
                  "pptx": "python-pptx", "sklearn": "scikit-learn", "cv2": "opencv-python", "dateutil": "python-dateutil"}

SECRET_PATTERNS = [
    ("Anthropic or OpenAI style API key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("AWS access key ID", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("connection string with password", re.compile(r"\b[a-z][a-z0-9+.-]{1,15}://[^/\s:@'\"]{1,64}:[^/\s:@'\"$<{]{3,64}@[\w.-]+")),
    ("hard-coded credential", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*['\"]"
        r"(?!\$\{|<|your|xxx|changeme|example|placeholder|dummy|fake|test)[^'\"\s]{12,}['\"]")),
]
REMOTE_PIPE = re.compile(r"\b(?:curl|wget)\b[^\n|;]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b|"
                         r"\b(?:curl|wget)\b[^\n|;]*\|\s*(?:sudo\s+)?python3?\b|"
                         r"\b(?:i" r"ex|invoke-" r"expression)\b[^\n]*\b(?:iwr|irm|invoke-webrequest|invoke-restmethod|downloadstring)\b",
                         re.I)
OBFUSCATED = re.compile(r"\b(?:exec|eval)\s*\(\s*(?:base64|codecs|zlib|marshal|bytes\.fromhex|__import__\(['\"]base64)|"
                        r"\bbase64\s+(?:-d|--decode)\b[^\n]*\|\s*(?:ba)?sh\b|"
                        r"\beval\s+\"?\$\((?:echo|printf)[^)]*\|\s*base64")
SHELL_INTERP = re.compile(r"shell\s*=\s*True")
OS_SYSTEM = re.compile(r"\bos\.(?:system|popen)\s*\(\s*(?!['\"][^'\"{}%]*['\"]\s*\))")
DESTRUCTIVE = re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r|\bgit\s+push\s+[^\n]*(?:--force\b|-f\b)|"
                         r"\bgit\s+reset\s+--hard\b|\bDROP\s+(?:TABLE|DATABASE)\b")
PRIVATE_NET = re.compile(r"(?<![\w.])(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
                         r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?![\w.])|"
                         r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:internal|corp|intranet|lan)\b")
ABS_PATH = re.compile(r"(?<![\w$}])(?:/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9._-]+)")
PY_INVOKE = re.compile(r"\bpython3?\b[^\n`]*?\.py\b")


# ---------------------------------------------------------------- rule catalog
def parse_rule_tables(*paths: Path) -> dict:
    """Parse '| ID | text | kind | severity | tier |' rows from rulebook markdown."""
    rules = {}
    row = re.compile(r"^\|\s*((?:HR-[A-Z]\d{2})|(?:SEC-\d{2}))\s*\|")
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not row.match(line):
                continue
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if len(cells) != 5:
                raise SystemExit(f"rulebook row has {len(cells)} cells, expected 5: {line[:80]}")
            rid, text, kind, sev, tier = cells
            if kind not in ("mechanical", "judgment") or sev not in ("critical", "major", "minor") \
                    or tier not in ("mandatory", "waivable"):
                raise SystemExit(f"rulebook row has a bad kind/severity/tier: {rid}")
            if rid in rules:
                raise SystemExit(f"rule {rid} is defined twice")
            rules[rid] = {"id": rid, "text": text.replace("\\|", "|"), "kind": kind, "severity": sev,
                          "tier": tier, "retired": text.startswith("[retired]")}
    return rules


def load_rules() -> dict:
    return parse_rule_tables(REFS / "plugin-guidelines.md", REFS / "security-checklist.md")


def policy_block(key: str) -> dict:
    """Return the first JSON code block in intake-policy.md that defines `key`."""
    text = (REFS / "intake-policy.md").read_text(encoding="utf-8")
    for block in re.findall(r"```json\n(.*?)```", text, flags=re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and key in data:
            return data
    raise SystemExit(f"intake-policy.md has no JSON block with '{key}'")


# ---------------------------------------------------------------- helpers
def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > TEXT_LIMIT or b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def frontmatter(text: str):
    """Return (dict | None, error | None, body)."""
    if not text.startswith("---"):
        return None, "no YAML frontmatter", text
    end = re.search(r"^---\s*$", text[3:], flags=re.M)
    if not end:
        return None, "frontmatter is not closed with ---", text
    raw = text[3:3 + end.start()]
    body = text[3 + end.end():]
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        return None, f"frontmatter is not valid YAML: {str(exc).splitlines()[0]}", body
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping", body
    return data, None, body


def find_marketplace_root(start: Path) -> Path | None:
    for p in [start, *start.parents]:
        if (p / ".claude-plugin" / "marketplace.json").is_file():
            return p
    return None


def in_git(path: Path) -> bool:
    if not shutil.which("git"):
        return False
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "true"


def git_ignored(path: Path, cwd: Path) -> bool:
    r = subprocess.run(["git", "-C", str(cwd), "check-ignore", "-q", "--no-index", str(path)],
                       capture_output=True, text=True)
    return r.returncode == 0


def detect_license(text: str) -> str | None:
    head = text[:1500]
    checks = [
        ("Apache-2.0", r"Apache License,?\s+Version 2\.0"),
        ("MPL-2.0", r"Mozilla Public License,?\s+(?:Version|v\.?)\s*2\.0"),
        ("BSD-3-Clause", r"Neither the name of"),
        ("BSD-2-Clause", r"Redistribution and use in source and binary forms"),
        ("0BSD", r"Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted\.\s*THE SOFTWARE"),
        ("ISC", r"\bISC License\b|Permission to use, copy, modify, and/or distribute this software for any"),
        ("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
        ("Unlicense", r"This is free and unencumbered software released into the public domain"),
        ("CC0-1.0", r"CC0 1\.0|Creative Commons Legal Code\s+CC0"),
        ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
        ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"),
        ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"),
        ("LGPL", r"GNU LESSER GENERAL PUBLIC LICENSE"),
    ]
    for spdx, pat in checks:
        if re.search(pat, head if spdx != "BSD-3-Clause" else text[:4000], flags=re.I):
            if spdx == "BSD-2-Clause" and re.search(r"Neither the name of", text[:4000], re.I):
                return "BSD-3-Clause"
            return spdx
    return None


def load_denylist(path: Path | None) -> list[dict]:
    if not path or not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [t for t in data.get("terms", []) if re.fullmatch(r"[0-9a-f]{64}", t.get("sha256", ""))]


def normalized_ngrams(text: str, n_max: int = 3):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for i in range(len(tokens)):
        for n in range(1, n_max + 1):
            if i + n <= len(tokens):
                yield " ".join(tokens[i:i + n])


def hash_term(term: str) -> str:
    return hashlib.sha256(" ".join(re.findall(r"[a-z0-9]+", term.lower())).encode()).hexdigest()


# ---------------------------------------------------------------- the checker
class Checker:
    def __init__(self, plugin: Path, rules: dict, marketplace: Path | None, denylist: list[dict], use_cli: bool):
        self.root = plugin.resolve()
        self.rules = rules
        self.market = marketplace
        self.denylist = denylist
        self.use_cli = use_cli
        self.findings: list[dict] = []
        self.notes: list[str] = []
        self.manifest: dict = {}
        self.files: list[Path] = []
        self.git = in_git(self.root)
        self.readme = ""
        self.waivers: dict[str, str] = {}

    # -- recording
    def add(self, rule: str, title: str, file: str | None = None, line: int | None = None,
            evidence: str = "", fix: str = ""):
        meta = self.rules.get(rule)
        if meta is None:
            raise SystemExit(f"checker referenced unknown rule {rule}")
        if meta["retired"]:
            return
        self.findings.append({
            "id": "", "rule": rule, "severity": meta["severity"], "kind": meta["kind"],
            "analyst": "validate_plugin", "status": "open", "file": file, "line": line,
            "title": title, "evidence": evidence[:500], "fix": fix, "patch": None,
            "escalation": None, "dissent": [],
        })

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    # -- file inventory
    def committable(self) -> set[str] | None:
        """Files git would commit (tracked + untracked-not-ignored), or None outside git."""
        if not self.git:
            return None
        r = subprocess.run(["git", "-C", str(self.root), "ls-files", "-co", "--exclude-standard", "-z",
                            "--full-name", "--", "."], capture_output=True)
        top = subprocess.run(["git", "-C", str(self.root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True).stdout.strip()
        if r.returncode != 0 or not top:
            return None
        return {str((Path(top) / x.decode()).resolve(strict=False)) for x in r.stdout.split(b"\0") if x}

    def walk(self):
        keep_only = self.committable()
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            d = Path(dirpath)
            keep = []
            for name in dirnames:
                full = d / name
                if name in SKIP_DIRS:
                    continue
                if full.is_symlink():
                    self.add("SEC-20", "Symlinked directory in plugin", self.rel(full),
                             evidence=f"{self.rel(full)} -> {os.readlink(full)}",
                             fix="Replace the symlink with the real files or remove it.")
                    continue
                keep.append(name)
            dirnames[:] = keep
            for name in filenames:
                full = d / name
                if keep_only is not None and str(full) not in keep_only and not full.is_symlink():
                    continue
                if full.is_symlink():
                    self.add("SEC-20", "Symlinked file in plugin", self.rel(full),
                             evidence=f"{self.rel(full)} -> {os.readlink(full)}",
                             fix="Replace the symlink with the real file or remove it.")
                    continue
                self.files.append(full)

    def text_files(self):
        for f in self.files:
            t = read_text(f)
            if t is not None:
                yield f, t

    # -- run everything
    def run(self):
        self.walk()
        self.load_waivers()
        readme = self.root / "README.md"
        self.readme = (read_text(readme) or "") if readme.is_file() else ""
        self.check_manifest()
        self.check_skills()
        self.check_agents()
        self.check_commands()
        self.check_hooks()
        self.check_mcp()
        self.check_conventions()
        self.check_evals()
        self.check_security_text()
        self.check_binaries()
        self.check_license_allowlist()
        self.check_denylist_names()
        self.apply_waivers()
        for i, f in enumerate(sorted(self.findings, key=lambda x: (x["rule"], x["file"] or "", x["line"] or 0)), 1):
            f["id"] = f"F-{i:03d}"
        self.findings.sort(key=lambda x: x["id"])

    # -- waivers
    def load_waivers(self):
        w = self.root / "waivers.md"
        if not w.is_file():
            return
        for line in w.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*((?:HR-[A-Z]\d{2})|(?:SEC-\d{2}))\s*\|\s*(.*?)\s*\|\s*(\d{4}-\d{2}-\d{2})?\s*\|\s*$", line)
            if m:
                self.waivers[m.group(1)] = m.group(2)

    def apply_waivers(self):
        is_import = (self.root / "PROVENANCE.md").is_file()
        for f in self.findings:
            if f["rule"] in self.waivers and is_import and self.rules[f["rule"]]["tier"] == "waivable" \
                    and self.waivers[f["rule"]].strip():
                f["status"] = "waived"
        if self.waivers and not is_import:
            self.notes.append("waivers.md is present but PROVENANCE.md is not; native plugins cannot waive rules, "
                              "so every waiver was ignored.")

    # -- HR-M
    def check_manifest(self):
        mpath = self.root / ".claude-plugin" / "plugin.json"
        if not mpath.is_file():
            self.add("HR-M01", "plugin.json is missing", ".claude-plugin/plugin.json",
                     fix="Create .claude-plugin/plugin.json from scaffold-templates.md.")
            return
        try:
            data = json.loads(mpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.add("HR-M01", "plugin.json is not valid JSON", ".claude-plugin/plugin.json", exc.lineno,
                     evidence=str(exc), fix="Fix the JSON syntax.")
            return
        if not isinstance(data, dict):
            self.add("HR-M01", "plugin.json is not a JSON object", ".claude-plugin/plugin.json")
            return
        self.manifest = data
        if self.use_cli and shutil.which("claude"):
            try:
                r = subprocess.run(["claude", "plugin", "validate", "--json", str(self.root)],
                                   capture_output=True, text=True, timeout=120)
                rep = json.loads(r.stdout or "{}")
                for err in (rep.get("manifest") or {}).get("errors", []):
                    msg = err if isinstance(err, str) else json.dumps(err)
                    self.add("HR-M01", "claude plugin validate reports an error", ".claude-plugin/plugin.json",
                             evidence=msg, fix="Fix what the CLI reports.")
                for item in rep.get("contents", []) or []:
                    for err in (item.get("errors") or []) if isinstance(item, dict) else []:
                        msg = err if isinstance(err, str) else json.dumps(err)
                        self.add("HR-M01", "claude plugin validate reports an error in a component",
                                 item.get("file"), evidence=msg, fix="Fix what the CLI reports.")
            except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
                self.notes.append(f"claude plugin validate could not be used: {exc}")
        else:
            self.notes.append("claude CLI not used; HR-M01 checked JSON syntax only.")

        name = data.get("name")
        if not isinstance(name, str) or not KEBAB.match(name) or not 3 <= len(name) <= 64:
            self.add("HR-M02", "Plugin name is not kebab-case or has a bad length", ".claude-plugin/plugin.json",
                     evidence=f"name: {name!r}", fix="Use 3-64 lowercase letters, digits and single hyphens.")
        elif name != self.root.name:
            self.add("HR-M02", "Plugin name does not match its folder", ".claude-plugin/plugin.json",
                     evidence=f"name {name!r}, folder {self.root.name!r}", fix="Rename the folder or the plugin.")
        ver = data.get("version")
        if not isinstance(ver, str) or not SEMVER.match(ver):
            self.add("HR-M03", "Version is missing or not semver", ".claude-plugin/plugin.json",
                     evidence=f"version: {ver!r}", fix="Set version to MAJOR.MINOR.PATCH, for example 0.1.0.")
        desc = data.get("description")
        if not isinstance(desc, str) or not 30 <= len(desc) <= 300:
            self.add("HR-M04", "Description is missing or outside 30-300 characters", ".claude-plugin/plugin.json",
                     evidence=f"{len(desc) if isinstance(desc, str) else 0} characters",
                     fix="Write one or two sentences on what the plugin does.")
        author = data.get("author")
        if not (isinstance(author, dict) and author.get("name")):
            self.add("HR-M05", "author.name is missing", ".claude-plugin/plugin.json",
                     fix='Add "author": {"name": "..."}.')
        kw = data.get("keywords")
        if not (isinstance(kw, list) and 4 <= len(kw) <= 10 and all(isinstance(k, str) and KEBAB.match(k) for k in kw)):
            self.add("HR-M06", "keywords should be 4-10 lowercase kebab-case strings", ".claude-plugin/plugin.json",
                     evidence=f"keywords: {kw!r}", fix="Add 4-10 keywords such as the jobs the plugin does.")
        lic = data.get("license")
        lic_file = next((self.root / n for n in LICENSE_FILES if (self.root / n).is_file()), None)
        if not lic:
            self.add("HR-M07", "license field is missing", ".claude-plugin/plugin.json",
                     fix='Add "license": "MIT" (or the plugin\'s actual SPDX ID).')
        elif lic_file:
            found = detect_license(read_text(lic_file) or "")
            if found and found != lic:
                self.add("HR-M07", "license field does not match the LICENSE file", ".claude-plugin/plugin.json",
                         evidence=f"plugin.json says {lic}, {lic_file.name} reads as {found}",
                         fix="Make plugin.json and the LICENSE file agree.")
        home = data.get("homepage")
        if not (isinstance(home, str) and re.search(rf"/plugins/{re.escape(self.root.name)}/?$", home)):
            self.add("HR-M08", "homepage does not point at the plugin's folder", ".claude-plugin/plugin.json",
                     evidence=f"homepage: {home!r}",
                     fix="Use https://github.com/<owner>/<repo>/tree/main/plugins/<name>.")
        self.check_marketplace_entry()

    def check_marketplace_entry(self):
        if not self.market:
            self.notes.append("No marketplace.json above this plugin; HR-M09 not checked (release-plugin adds the entry).")
            return
        mp = self.market / ".claude-plugin" / "marketplace.json"
        try:
            market = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.add("HR-M09", "marketplace.json cannot be read", None, evidence=str(exc))
            return
        name = self.manifest.get("name") or self.root.name
        entry = next((p for p in market.get("plugins", []) if p.get("name") == name), None)
        if entry is None:
            self.add("HR-M09", "Plugin is not listed in marketplace.json", ".claude-plugin/marketplace.json",
                     evidence=f"no entry named {name!r}", fix="Run release-plugin to add the entry.")
            return
        try:
            rel = self.root.relative_to(self.market).as_posix()
        except ValueError:
            rel = None
        src = entry.get("source")
        if isinstance(src, str) and rel and src.rstrip("/") not in (f"./{rel}", rel):
            self.add("HR-M09", "Marketplace source path does not match the plugin folder",
                     ".claude-plugin/marketplace.json", evidence=f"source {src!r}, folder ./{rel}",
                     fix="Point source at the plugin's folder.")
        if entry.get("version") != self.manifest.get("version"):
            self.add("HR-M09", "Marketplace version does not match plugin.json", ".claude-plugin/marketplace.json",
                     evidence=f"marketplace {entry.get('version')!r}, plugin.json {self.manifest.get('version')!r}",
                     fix="Let release-plugin sync the version.")
        if not entry.get("description"):
            self.add("HR-M09", "Marketplace entry has no description", ".claude-plugin/marketplace.json")

    # -- HR-S
    def check_skills(self):
        sdir = self.root / "skills"
        if not sdir.is_dir():
            return
        for d in sorted(p for p in sdir.iterdir() if p.is_dir()):
            sk = d / "SKILL.md"
            rel = self.rel(sk)
            if not sk.is_file():
                self.add("HR-S01", "Skill folder has no SKILL.md", self.rel(d), fix="Add SKILL.md or remove the folder.")
                continue
            text = read_text(sk) or ""
            fm, err, body = frontmatter(text)
            if err:
                self.add("HR-S01", f"SKILL.md frontmatter problem: {err}", rel, 1)
                continue
            if fm.get("name") != d.name or not fm.get("description"):
                self.add("HR-S01", "SKILL.md needs name (equal to its folder) and description", rel, 1,
                         evidence=f"name: {fm.get('name')!r}, folder: {d.name!r}")
            unknown = sorted(set(fm) - SKILL_KEYS)
            if unknown:
                self.add("HR-S02", "Unknown frontmatter keys", rel, 1, evidence=", ".join(unknown),
                         fix="Move them under metadata or remove them.")
            meta = fm.get("metadata")
            mver = meta.get("version") if isinstance(meta, dict) else None
            if not (isinstance(mver, str) and SEMVER.match(mver)):
                self.add("HR-S03", "metadata.version is missing or not semver", rel, 1,
                         evidence=f"metadata: {meta!r}", fix='Add metadata:\\n  version: "0.1.0".')
            desc = fm.get("description") or ""
            if not 50 <= len(str(desc)) <= 1024:
                self.add("HR-S04", "Description is outside 50-1024 characters", rel, 1,
                         evidence=f"{len(str(desc))} characters")
            lines = body.count("\n")
            if lines >= 500:
                self.add("HR-S07", "SKILL.md body is 500 lines or longer", rel, evidence=f"{lines} lines",
                         fix="Move detail into references/ and link to it.")
            self.check_referenced_paths(sk, body)

    def check_referenced_paths(self, doc: Path, body: str):
        pat = re.compile(r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?((?:\.\./)*(?:references|scripts|templates|assets|examples|"
                         r"agents|skills|shared|hooks|commands)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)")
        seen = set()
        for i, line in enumerate(body.splitlines(), 1):
            for m in pat.finditer(line):
                ref = m.group(1).rstrip(".")
                if ref in seen or any(c in ref for c in "<>{}*"):
                    continue
                seen.add(ref)
                plugin_rooted = m.group(0).startswith("${CLAUDE_PLUGIN_ROOT}")
                candidates = [self.root / ref] if plugin_rooted else \
                    [doc.parent / ref, self.root / ref, *(self.root / "skills").glob(f"*/{ref}")]
                if not any(c.resolve().is_file() or c.resolve().is_dir() for c in candidates):
                    self.add("HR-S08", "Referenced file does not exist", self.rel(doc), None,
                             evidence=ref, fix="Add the file or fix the path.")

    # -- HR-A
    def check_agents(self):
        adir = self.root / "agents"
        if not adir.is_dir():
            return
        for f in sorted(adir.glob("*.md")):
            rel = self.rel(f)
            fm, err, _ = frontmatter(read_text(f) or "")
            if err:
                self.add("HR-A01", f"Agent frontmatter problem: {err}", rel, 1)
                continue
            if fm.get("name") != f.stem or not fm.get("description"):
                self.add("HR-A01", "Agent needs name (equal to file stem) and description", rel, 1,
                         evidence=f"name: {fm.get('name')!r}")
            desc = str(fm.get("description") or "")
            if not re.search(r"<example>.*?<commentary>.*?</commentary>.*?</example>", desc, flags=re.S):
                self.add("HR-A02", "Agent description has no <example> with <commentary>", rel, 1,
                         fix="Add one or more <example> blocks showing when to use the agent.")
            model, color = fm.get("model"), fm.get("color")
            if model is not None and model not in AGENT_MODELS:
                self.add("HR-A03", "Agent model is not an allowed value", rel, 1, evidence=f"model: {model!r}")
            if color is not None and color not in AGENT_COLORS:
                self.add("HR-A03", "Agent color is not an allowed value", rel, 1, evidence=f"color: {color!r}")

    # -- HR-K
    def check_commands(self):
        cdir = self.root / "commands"
        if not cdir.is_dir():
            return
        for f in sorted(cdir.rglob("*.md")):
            rel = self.rel(f)
            fm, err, body = frontmatter(read_text(f) or "")
            if err or not (fm or {}).get("description"):
                self.add("HR-K01", "Command has no description in frontmatter", rel, 1, evidence=err or "")
                fm = fm or {}
            tools = fm.get("allowed-tools")
            items = tools if isinstance(tools, list) else re.split(r",\s*", str(tools or "")) if tools else []
            if any(str(t).strip() == "Bash" for t in items):
                self.add("HR-K02", "Command grants unscoped Bash", rel, 1, evidence=f"allowed-tools: {tools}",
                         fix="Scope it, for example Bash(git status:*).")
            if re.search(r"\$ARGUMENTS|\$[1-9]\b", body) and not fm.get("argument-hint"):
                self.add("HR-K03", "Command uses arguments but has no argument-hint", rel, 1)

    # -- HR-H
    def hooks_config(self):
        h = self.manifest.get("hooks")
        if isinstance(h, dict):
            return h, ".claude-plugin/plugin.json"
        path = self.root / (h if isinstance(h, str) else "hooks/hooks.json")
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8")), self.rel(path)
            except json.JSONDecodeError as exc:
                self.add("HR-H01", "hooks file is not valid JSON", self.rel(path), exc.lineno, evidence=str(exc))
                return None, self.rel(path)
        return None, None

    def check_hooks(self):
        cfg, rel = self.hooks_config()
        if cfg is None:
            return
        events = cfg.get("hooks", cfg) if isinstance(cfg, dict) else None
        if not isinstance(events, dict):
            self.add("HR-H01", "hooks config has no event map", rel)
            return
        documented = re.search(r"\bhooks?\b", self.readme, re.I)
        if not documented:
            self.add("HR-H05", "README does not describe the plugin's hooks", "README.md")
        for event, groups in events.items():
            if event not in HOOK_EVENTS:
                self.add("HR-H01", "Unknown hook event", rel, evidence=event)
            for group in groups if isinstance(groups, list) else []:
                for hook in (group or {}).get("hooks", []):
                    if hook.get("type", "command") != "command":
                        continue
                    cmd = str(hook.get("command", ""))
                    for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"']+)", cmd):
                        if not (self.root / ref).exists():
                            self.add("HR-H02", "Hook refers to a file that does not exist", rel, evidence=ref)
                    if re.search(r"(?:^|\s|\")(?:\./|scripts/|hooks/)[\w./-]+", cmd) and "${CLAUDE_PLUGIN_ROOT}" not in cmd:
                        self.add("HR-H02", "Hook refers to a plugin file without ${CLAUDE_PLUGIN_ROOT}", rel,
                                 evidence=cmd[:200])
                    if "timeout" not in hook:
                        self.add("HR-H03", "Command hook has no timeout", rel, evidence=f"{event}: {cmd[:120]}",
                                 fix='Add "timeout": 30 (seconds) or whatever the hook needs.')

    # -- HR-X
    def check_mcp(self):
        servers, rel = None, None
        m = self.manifest.get("mcpServers")
        if isinstance(m, dict):
            servers, rel = m, ".claude-plugin/plugin.json"
        else:
            path = self.root / (m if isinstance(m, str) else ".mcp.json")
            if path.is_file():
                rel = self.rel(path)
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    self.add("HR-X01", "MCP config is not valid JSON", rel, exc.lineno, evidence=str(exc))
                    return
                servers = data.get("mcpServers", data) if isinstance(data, dict) else None
        if servers is None:
            return
        if not isinstance(servers, dict):
            self.add("HR-X01", "MCP config has no server map", rel)
            return
        for name, s in servers.items():
            if not isinstance(s, dict) or not (s.get("command") or s.get("url")):
                self.add("HR-X01", "MCP server has neither command nor url", rel, evidence=name)
                continue
            cmd = os.path.basename(str(s.get("command", "")))
            args = [str(a) for a in s.get("args", []) if isinstance(a, (str, int))]
            if cmd in ("npx", "bunx", "pnpx", "uvx", "pipx", "docker"):
                pkgs = [a for a in args if not a.startswith("-") and a not in ("run", "exec", "dlx")]
                spec = pkgs[0] if pkgs else ""
                pinned = bool(re.search(r"@\d|==\d|@sha256:|:(?!latest\b)[\w.-]+$", spec)) and "@latest" not in spec
                if not pinned:
                    self.add("HR-X02", "MCP server package is not pinned", rel,
                             evidence=f"{name}: {cmd} {' '.join(args)[:150]}",
                             fix="Pin an exact version, for example pkg@1.4.2 or pkg==1.4.2.")
            for field in ("env", "headers"):
                for k, v in (s.get(field) or {}).items():
                    v = str(v)
                    if "${" in v or not v:
                        continue
                    if re.search(r"(?i)key|token|secret|pass|auth|cred", k) or any(p.search(v) for _, p in SECRET_PATTERNS):
                        self.add("HR-X03", "Literal secret in MCP server config", rel,
                                 evidence=f"{name}.{field}.{k} = <redacted, {len(v)} chars>",
                                 fix=f"Use \"${{{k.upper()}}}\" and document the variable.")
            url = s.get("url")
            if url:
                host = re.sub(r"^\w+://", "", str(url)).split("/")[0].split(":")[0]
                if host and host not in self.readme:
                    self.add("HR-X04", "Remote MCP host is not named in the README", rel, evidence=host,
                             fix="Name the host and what data the plugin sends to it.")

    # -- HR-C
    def check_conventions(self):
        if not any((self.root / n).is_file() for n in LICENSE_FILES):
            self.add("HR-C05", "No LICENSE file in the plugin root", None, fix="Add the license text, e.g. MIT.")
        if not self.readme or len(self.readme) < 300:
            self.add("HR-C04", "README.md is missing or too thin", "README.md",
                     evidence=f"{len(self.readme)} characters",
                     fix="Cover what the plugin does, its components, requirements and usage.")
        for f in self.files:
            parts = set(f.relative_to(self.root).parts)
            junk = parts & JUNK_NAMES or (f.suffix == ".pyc") or \
                ("evals" in parts and "results" in parts)
            if junk and not (self.git and git_ignored(f, self.root)):
                self.add("HR-C06", "Build or run output in the plugin", self.rel(f),
                         fix="Delete it and add the pattern to .gitignore.")
        # third-party imports must be documented
        stdlib = set(getattr(sys, "stdlib_module_names", ()))
        local = {p.stem for p in self.root.rglob("*.py")}
        missing = {}
        for f in self.files:
            if f.suffix != ".py":
                continue
            for i, line in enumerate((read_text(f) or "").splitlines(), 1):
                m = re.match(r"^\s*from\s+([A-Za-z_]\w*)\S*\s+import\b", line)
                mods = [m.group(1)] if m else []
                m2 = re.match(r"^\s*import\s+(.+?)\s*(?:#.*)?$", line)
                if m2:
                    mods = [x.strip().split(".")[0].split(" ")[0] for x in m2.group(1).split(",")]
                for mod in mods:
                    if not mod or mod in stdlib or mod in local or mod == "__future__":
                        continue
                    dist = IMPORT_ALIASES.get(mod, mod).lower()
                    if dist not in self.readme.lower() and mod.lower() not in self.readme.lower():
                        missing.setdefault(dist, (self.rel(f), i))
        for dist, (rel, line) in sorted(missing.items()):
            self.add("HR-C03", "Third-party Python package not listed in README requirements", rel, line,
                     evidence=dist, fix=f"List {dist} (with a version) under Requirements in the README.")
        # absolute paths + script invocation convention
        for f, text in self.text_files():
            rel = self.rel(f)
            for i, line in enumerate(text.splitlines(), 1):
                if ABS_PATH.search(line):
                    self.add("HR-C02", "Absolute path in plugin file", rel, i, evidence=line.strip()[:200],
                             fix="Use ${CLAUDE_PLUGIN_ROOT}, a relative path, or a placeholder.")
            if f.suffix == ".md" and f.parts[len(self.root.parts)] in ("skills", "commands", "agents") \
                    or f.name == "hooks.json":
                for i, line in enumerate(text.splitlines(), 1):
                    for m in PY_INVOKE.finditer(line):
                        seg = line[max(0, m.start() - 40):]
                        if "scripts/" not in m.group(0) and "hooks/" not in m.group(0):
                            continue
                        if "${CLAUDE_PLUGIN_ROOT}" not in seg:
                            self.add("HR-C01", "Bundled script invoked without ${CLAUDE_PLUGIN_ROOT}", rel, i,
                                     evidence=line.strip()[:200])
                        elif "command -v python" not in line and not re.search(r"\|\|\s*python\b", line):
                            self.add("HR-C01", "Bundled script invoked without an interpreter fallback", rel, i,
                                     evidence=line.strip()[:200],
                                     fix='Use "$(command -v python3 || command -v python)" "${CLAUDE_PLUGIN_ROOT}/...".')

    # -- HR-E
    def eval_cases(self):
        edir = self.root / "evals"
        cases = []
        if not edir.is_dir():
            return cases
        for p in sorted(edir.rglob("*")):
            if not p.is_dir() or {"results", "mocks"} & set(p.relative_to(edir).parts):
                continue
            if (p / "prompt.md").is_file() or (p / "case.yaml").is_file():
                cases.append(p)
        return cases

    def case_graders(self, case: Path) -> list[dict]:
        graders = []
        cy = case / "case.yaml"
        if cy.is_file():
            try:
                data = yaml.safe_load(cy.read_text(encoding="utf-8")) or {}
                graders += [g for g in data.get("graders", []) if isinstance(g, dict)]
            except yaml.YAMLError:
                pass
        for g in sorted((case / "graders").glob("*.md")) if (case / "graders").is_dir() else []:
            fm, err, _ = frontmatter(read_text(g) or "")
            if not err:
                graders.append(fm)
        return graders

    def check_evals(self):
        cases = self.eval_cases()
        edir = self.root / "evals"
        if not cases:
            self.add("HR-E01", "No eval suite", "evals/", fix="Add cases with eval-plugin.")
            return
        all_text = ""
        negative = False
        for c in cases:
            for f in c.rglob("*"):
                if f.is_file():
                    all_text += (read_text(f) or "") + "\n"
            graders = self.case_graders(c)
            if not any(g.get("type") in OUTCOME_GRADERS for g in graders):
                self.add("HR-E03", "Case has no outcome grader", self.rel(c),
                         fix="Add a regex, file_exists or llm grader that checks the result.")
            for g in graders:
                if g.get("type") == "tool_used" and str(g.get("tool")) == "Skill" \
                        and g.get("max") == 0 and g.get("arm") == "both":
                    negative = True
        if not negative:
            self.add("HR-E04", "Suite has no negative (should-not-fire) case", "evals/",
                     fix="Add a case with a tool_used Skill grader, min 0, max 0, arm both.")
        sdir = self.root / "skills"
        for d in sorted(p for p in sdir.iterdir() if p.is_dir()) if sdir.is_dir() else []:
            if d.name not in all_text:
                self.add("HR-E02", "Skill is not exercised by any eval case", self.rel(d), evidence=d.name)
        cfg = edir / "eval-config.json"
        if not cfg.is_file():
            self.add("HR-E05", "evals/eval-config.json is missing", "evals/eval-config.json")
        else:
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                problems = []
                if not isinstance(data.get("threshold"), (int, float)) or not 0 < data["threshold"] <= 1:
                    problems.append("threshold must be a number in (0, 1]")
                if not isinstance(data.get("smoke_cases"), list) or not data["smoke_cases"]:
                    problems.append("smoke_cases must be a non-empty list")
                if not isinstance(data.get("runs_full"), int) or data["runs_full"] < 3:
                    problems.append("runs_full must be an integer >= 3")
                known = {c.name for c in cases}
                for s in data.get("smoke_cases", []) or []:
                    if s not in known:
                        problems.append(f"smoke case {s!r} does not exist")
                if problems:
                    self.add("HR-E05", "eval-config.json does not match eval-standards.md", "evals/eval-config.json",
                             evidence="; ".join(problems))
            except json.JSONDecodeError as exc:
                self.add("HR-E05", "eval-config.json is not valid JSON", "evals/eval-config.json", exc.lineno)
        probe = edir / "results" / "probe.json"
        ignored = False
        if self.git:
            ignored = git_ignored(probe, self.root)
        else:
            for gi in [self.root / ".gitignore", *(p / ".gitignore" for p in self.root.parents)]:
                if gi.is_file() and "evals/results" in gi.read_text(encoding="utf-8", errors="replace"):
                    ignored = True
                    break
        if not ignored:
            self.add("HR-E06", "evals/results/ is not git-ignored", "evals/",
                     fix="Add plugins/*/evals/results/ to the repo .gitignore.")

    # -- SEC (text scans)
    def check_security_text(self):
        for f, text in self.text_files():
            rel = self.rel(f)
            approval = re.search(r"(?i)approv|confirm", text)
            in_fence = False
            shellish = f.suffix in (".sh", ".bash", ".ps1", ".zsh") or f.name in ("hooks.json", "Dockerfile")
            for i, line in enumerate(text.splitlines(), 1):
                if f.suffix == ".md" and line.lstrip().startswith("```"):
                    in_fence = not in_fence
                    continue
                runnable = shellish or (f.suffix == ".md" and in_fence)
                if REMOTE_PIPE.search(line):
                    self.add("SEC-01", "Downloaded script piped into a shell", rel, i, evidence=line.strip()[:200])
                if OBFUSCATED.search(line):
                    self.add("SEC-04", "Obfuscated or decoded execution", rel, i, evidence=line.strip()[:200])
                if f.suffix == ".py":
                    if SHELL_INTERP.search(line) and re.search(r"f['\"]|\.format\(|%\s*[(\w]|\+\s*\w", line):
                        self.add("SEC-06", "shell=True with an interpolated command", rel, i, evidence=line.strip()[:200],
                                 fix="Pass an argument list without shell=True.")
                    if OS_SYSTEM.search(line):
                        self.add("SEC-06", "os.system/os.popen with a built command", rel, i, evidence=line.strip()[:200],
                                 fix="Use subprocess.run with an argument list.")
                if DESTRUCTIVE.search(line) and not approval:
                    self.add("SEC-09", "Destructive command with no approval step in this file", rel, i,
                             evidence=line.strip()[:200], fix="Gate it behind an explicit user approval.")
                if PRIVATE_NET.search(line):
                    self.add("SEC-12", "Private address or internal hostname", rel, i, evidence=line.strip()[:200])
                for label, pat in SECRET_PATTERNS:
                    if pat.search(line):
                        self.add("SEC-21", f"Possible secret: {label}", rel, i,
                                 evidence=f"line {i}: <redacted>", fix="Remove it, rotate it, and read it from an env var.")
                        break
                if f.name in ("requirements.txt", "requirements.in") and line.strip() and not line.startswith("#") \
                        and not re.search(r"[=<>~!]=|@\s*\w+://.*@[0-9a-f]{7,}", line):
                    self.add("SEC-03", "Unpinned Python requirement", rel, i, evidence=line.strip()[:120])
                if runnable and re.search(r"\bpip3?\s+install\b", line) and not re.search(r"-r\s|\S+(?:==|>=|~=|<=)\S", line) \
                        and re.search(r"\bpip3?\s+install\s+(?:--?\S+\s+)*[A-Za-z]", line):
                    self.add("SEC-03", "pip install without a version constraint", rel, i, evidence=line.strip()[:160])
            if f.name == "package.json":
                try:
                    pkg = json.loads(text)
                    for sect in ("dependencies", "devDependencies", "optionalDependencies"):
                        for dep, ver in (pkg.get(sect) or {}).items():
                            if str(ver).strip() in ("*", "latest", "") or str(ver).startswith(("git", "github:")) \
                                    and "#" not in str(ver):
                                self.add("SEC-03", "Unpinned npm dependency", rel, evidence=f"{dep}: {ver}")
                except json.JSONDecodeError:
                    pass
            if self.denylist:
                hashes = {t["sha256"]: t.get("label", "denylisted term") for t in self.denylist}
                for i, line in enumerate(text.splitlines(), 1):
                    hit = next((hashes[h] for h in (hashlib.sha256(g.encode()).hexdigest()
                                                    for g in normalized_ngrams(line)) if h in hashes), None)
                    if hit:
                        self.add("SEC-23", f"Denylisted term ({hit})", rel, i, evidence=f"line {i}: <term withheld>",
                                 fix="Remove or replace the term.")

    def check_denylist_names(self):
        if not self.denylist:
            return
        hashes = {t["sha256"]: t.get("label", "denylisted term") for t in self.denylist}
        for f in self.files:
            rel = self.rel(f)
            for g in normalized_ngrams(rel.replace("/", " ")):
                if hashlib.sha256(g.encode()).hexdigest() in hashes:
                    self.add("SEC-23", "Denylisted term in a file or folder name", rel, evidence="<term withheld>")
                    break

    def check_binaries(self):
        policy = policy_block("blocked_extensions")
        allowed_exec = set(policy["allowed_executable_extensions"])
        for f in self.files:
            rel = self.rel(f)
            try:
                size = f.stat().st_size
                with f.open("rb") as fh:
                    head = fh.read(8192)
            except OSError:
                continue
            if size > policy["max_single_file_bytes"]:
                self.add("SEC-20", "File over the size limit", rel, evidence=f"{size} bytes")
            if f.suffix.lower() in policy["blocked_extensions"]:
                self.add("SEC-20", "Blocked file type", rel, evidence=f.suffix)
            binary = b"\x00" in head or head.startswith((b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"))
            if binary and f.suffix.lower() not in BINARY_OK_EXT and f.name not in self.readme:
                self.add("SEC-05", "Binary file not explained in the README", rel,
                         fix="Name the file in the README with its source and purpose, or remove it.")
            if os.access(f, os.X_OK) and f.suffix.lower() not in allowed_exec and f.name not in self.readme:
                self.add("SEC-05", "Executable file not explained in the README", rel, evidence=f.suffix or "(no extension)")

    def check_license_allowlist(self):
        allowed = set(policy_block("allowed_licenses")["allowed_licenses"])
        lic = self.manifest.get("license")
        if not lic:
            lic_file = next((self.root / n for n in LICENSE_FILES if (self.root / n).is_file()), None)
            lic = detect_license(read_text(lic_file) or "") if lic_file else None
        if lic not in allowed:
            self.add("SEC-22", "License is missing or not on the allowlist", ".claude-plugin/plugin.json",
                     evidence=f"license: {lic!r}", fix="Use an allowlisted license or extend the allowlist by PR.")

    # -- output
    def result(self) -> dict:
        open_ = [f for f in self.findings if f["status"] == "open"]
        return {
            "schema_version": 1, "producer": "validate_plugin", "mode": "mechanical",
            "plugin": self.manifest.get("name") or self.root.name,
            "plugin_version": self.manifest.get("version"),
            "source": {"type": "local", "location": str(self.root), "sha": None, "tree_hash": None},
            "generated_at": now_iso(),
            "findings": self.findings,
            "summary": {s: sum(1 for f in open_ if f["severity"] == s) for s in ("critical", "major", "minor")},
            "waived": sum(1 for f in self.findings if f["status"] == "waived"),
            "notes": self.notes,
        }


def scan_files(paths: list[Path], denylist: list[dict], rules: dict) -> dict:
    """SEC-21 and SEC-23 over files outside any plugin (marketplace.json, READMEs, workflows)."""
    findings = []
    hashes = {t["sha256"]: t.get("label", "denylisted term") for t in denylist}

    def add(rule, title, rel, line):
        findings.append({"id": f"F-{len(findings) + 1:03d}", "rule": rule, "severity": rules[rule]["severity"],
                         "kind": "mechanical", "analyst": "validate_plugin", "status": "open", "file": rel,
                         "line": line, "title": title, "evidence": f"line {line}: <redacted>", "fix": "Remove it.",
                         "patch": None, "escalation": None, "dissent": []})
    for p in paths:
        if not p.is_file():
            continue
        rel = p.as_posix()
        for g in normalized_ngrams(rel.replace("/", " ")):
            if hashlib.sha256(g.encode()).hexdigest() in hashes:
                add("SEC-23", "Denylisted term in a file name", rel, None)
                break
        text = read_text(p)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for label, pat in SECRET_PATTERNS:
                if pat.search(line):
                    add("SEC-21", f"Possible secret: {label}", rel, i)
                    break
            if hashes and any(hashlib.sha256(g.encode()).hexdigest() in hashes for g in normalized_ngrams(line)):
                add("SEC-23", "Denylisted term", rel, i)
    crit = sum(1 for f in findings if f["severity"] == "critical")
    return {"schema_version": 1, "producer": "validate_plugin", "mode": "mechanical", "plugin": None,
            "plugin_version": None, "source": {"type": "local", "location": ".", "sha": None, "tree_hash": None},
            "generated_at": now_iso(), "findings": findings,
            "summary": {"critical": crit, "major": len(findings) - crit, "minor": 0}, "waived": 0, "notes": []}


def validate(plugin: Path, marketplace: Path | None = None, denylist: Path | None = None,
             use_cli: bool = True, rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    market = marketplace or find_marketplace_root(plugin.resolve().parent)
    if denylist is None and market:
        denylist = market / ".toolkit" / "denylist.json"
    checker = Checker(plugin, rules, market, load_denylist(denylist), use_cli)
    checker.run()
    return checker.result()


def print_text(res: dict):
    s = res["summary"]
    print(f"{res['plugin']} {res.get('plugin_version') or ''}: "
          f"{s['critical']} critical, {s['major']} major, {s['minor']} minor open; {res['waived']} waived")
    for f in res["findings"]:
        loc = f"{f['file']}:{f['line']}" if f["line"] else (f["file"] or "-")
        tag = "" if f["status"] == "open" else f" [{f['status']}]"
        print(f"  {f['id']} {f['severity']:<8} {f['rule']:<7} {loc}  {f['title']}{tag}")
        if f["evidence"]:
            print(f"      {f['evidence']}")
    for n in res.get("notes", []):
        print(f"  note: {n}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plugin", nargs="?", help="plugin folder")
    ap.add_argument("--all", metavar="REPO_ROOT", help="validate every plugin under REPO_ROOT/plugins")
    ap.add_argument("--json", action="store_true", help="print findings JSON")
    ap.add_argument("--marketplace", metavar="REPO_ROOT", help="marketplace repo root (default: search upward)")
    ap.add_argument("--denylist", metavar="FILE", help="denylist JSON (default: <repo>/.toolkit/denylist.json)")
    ap.add_argument("--no-cli", action="store_true", help="do not call `claude plugin validate`")
    ap.add_argument("--out", metavar="FILE", help="also write JSON to FILE")
    ap.add_argument("--rules", action="store_true", help="print the parsed rule catalog and exit")
    ap.add_argument("--scan-files", nargs="+", metavar="FILE", help="secret and denylist scan of these files")
    args = ap.parse_args(argv)
    if yaml is None:
        print('PyYAML is required: pip install "pyyaml>=6"', file=sys.stderr)
        return 2
    rules = load_rules()
    if args.rules:
        if args.json:
            print(json.dumps(rules, indent=2))
        else:
            for r in rules.values():
                print(f"{r['id']:<7} {r['kind']:<10} {r['severity']:<8} {r['tier']:<9} {r['text'][:90]}")
        return 0
    market = Path(args.marketplace).resolve() if args.marketplace else None
    deny = Path(args.denylist).resolve() if args.denylist else None
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    if args.scan_files:
        dl = load_denylist(deny or (find_marketplace_root(Path.cwd()) or Path.cwd()) / ".toolkit" / "denylist.json")
        res = scan_files([Path(f) for f in args.scan_files], dl, rules)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            for f in res["findings"]:
                print(f"  {f['severity']:<8} {f['rule']}  {f['file']}:{f['line'] or '-'}  {f['title']}")
            print(f"{len(res['findings'])} finding(s) in {len(args.scan_files)} file(s)")
        if args.out:
            Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
        return 1 if res["summary"]["critical"] else 0
    if args.all:
        root = Path(args.all).resolve()
        results = [validate(p, market or root, deny, not args.no_cli, rules)
                   for p in sorted((root / "plugins").iterdir()) if (p / ".claude-plugin").is_dir()]
        out = {"schema_version": 1, "producer": "validate_plugin", "mode": "mechanical", "plugins": results}
        crit = sum(r["summary"]["critical"] for r in results)
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            for r in results:
                print_text(r)
        if args.out:
            Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        return 1 if crit else 0
    if not args.plugin:
        ap.print_usage(sys.stderr)
        return 2
    plugin = Path(args.plugin)
    if not plugin.is_dir():
        print(f"not a folder: {plugin}", file=sys.stderr)
        return 2
    res = validate(plugin, market, deny, not args.no_cli, rules)
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print_text(res)
    return 1 if res["summary"]["critical"] else 0


if __name__ == "__main__":
    sys.exit(main())

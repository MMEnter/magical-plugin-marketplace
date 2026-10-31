#!/usr/bin/env python3
"""Reconcile plugins/*/ against .claude-plugin/marketplace.json.

Usage:
  sync_marketplace.py REPO_ROOT [--json] [--only NAME ...]
      Report drift (optionally only for the named plugins). Never edits anything and never invents entries.
  sync_marketplace.py REPO_ROOT --update-entry NAME [--category CAT]
      Release-only: write NAME's entry from its plugin.json (used by release-plugin).
  sync_marketplace.py REPO_ROOT --update-pinned NAME --repo OWNER/REPO --sha SHA
                      [--path SUBDIR] --description TEXT --version VER [--category CAT]
      Release-only: write a pinned upstream entry.

Drift checks: plugin folder with no entry; entry with no folder; name, version or
description out of sync; local source path wrong; pinned entry without a full SHA;
duplicate entry names; and cross-plugin collisions of skill, agent or command names.
Exit 0 = in sync, 1 = drift found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
ENTRY_ORDER = ["name", "description", "version", "author", "category", "source", "homepage"]


def load(repo: Path) -> dict:
    return json.loads((repo / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))


def save(repo: Path, data: dict):
    (repo / ".claude-plugin" / "marketplace.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                              encoding="utf-8")


def plugin_dirs(repo: Path) -> dict[str, Path]:
    root = repo / "plugins"
    return {d.name: d for d in sorted(root.iterdir()) if (d / ".claude-plugin" / "plugin.json").is_file()} \
        if root.is_dir() else {}


def components(d: Path) -> dict[str, list[str]]:
    out = {"skill": [], "agent": [], "command": []}
    if (d / "skills").is_dir():
        out["skill"] = [p.name for p in (d / "skills").iterdir() if (p / "SKILL.md").is_file()]
    if (d / "agents").is_dir():
        out["agent"] = [p.stem for p in (d / "agents").glob("*.md")]
    if (d / "commands").is_dir():
        out["command"] = [p.stem for p in (d / "commands").rglob("*.md")]
    return out


def drift(repo: Path) -> list[dict]:
    issues = []
    market = load(repo)
    entries = market.get("plugins", [])
    dirs = plugin_dirs(repo)
    seen = defaultdict(int)
    for e in entries:
        seen[e.get("name")] += 1
    for n, c in seen.items():
        if c > 1:
            issues.append({"plugin": n, "issue": "duplicate_entry", "detail": f"listed {c} times"})
    for e in entries:
        name, src = e.get("name"), e.get("source")
        if isinstance(src, dict):
            if not SHA40.match(str(src.get("sha", ""))):
                issues.append({"plugin": name, "issue": "pinned_without_sha",
                               "detail": "pinned upstream entries need a full 40-character sha"})
            if not (repo / ".toolkit" / "pinned" / f"{name}.json").is_file():
                issues.append({"plugin": name, "issue": "pinned_without_stamp",
                               "detail": f".toolkit/pinned/{name}.json is missing"})
            continue
        if name not in dirs:
            issues.append({"plugin": name, "issue": "entry_without_folder", "detail": f"source {src!r} has no plugin"})
            continue
        if str(src).rstrip("/") not in (f"./plugins/{name}", f"plugins/{name}"):
            issues.append({"plugin": name, "issue": "source_path", "detail": f"source {src!r}, expected ./plugins/{name}"})
        manifest = json.loads((dirs[name] / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        if manifest.get("name") != name:
            issues.append({"plugin": name, "issue": "name_mismatch", "detail": f"plugin.json name {manifest.get('name')!r}"})
        if e.get("version") != manifest.get("version"):
            issues.append({"plugin": name, "issue": "version_mismatch",
                           "detail": f"marketplace {e.get('version')!r}, plugin.json {manifest.get('version')!r}"})
        if not e.get("description"):
            issues.append({"plugin": name, "issue": "no_description", "detail": "entry has no description"})
    listed = {e.get("name") for e in entries}
    for name in dirs:
        if name not in listed:
            issues.append({"plugin": name, "issue": "unlisted_plugin",
                           "detail": f"plugins/{name} is not in marketplace.json"})
    owners = defaultdict(list)
    for name, d in dirs.items():
        for kind, names in components(d).items():
            for c in names:
                owners[(kind, c)].append(name)
    for (kind, c), ps in sorted(owners.items()):
        if len(ps) > 1:
            issues.append({"plugin": ", ".join(ps), "issue": "name_collision",
                           "detail": f"{kind} {c!r} exists in {len(ps)} plugins"})
    return issues


def ordered(entry: dict) -> dict:
    return {**{k: entry[k] for k in ENTRY_ORDER if k in entry}, **{k: v for k, v in entry.items() if k not in ENTRY_ORDER}}


def update_entry(repo: Path, name: str, category: str | None):
    d = repo / "plugins" / name
    manifest = json.loads((d / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = load(repo)
    entries = market.setdefault("plugins", [])
    old = next((e for e in entries if e.get("name") == name), None)
    new = dict(old or {})
    new.update({"name": name, "description": manifest["description"], "version": manifest["version"],
                "author": manifest.get("author") or (old or {}).get("author") or market.get("owner"),
                "source": f"./plugins/{name}"})
    if manifest.get("homepage"):
        new["homepage"] = manifest["homepage"]
    if category or "category" not in new:
        new["category"] = category or "productivity"
    if old is None:
        entries.append(ordered(new))
    else:
        entries[entries.index(old)] = ordered(new)
    save(repo, market)
    return new


def update_pinned(repo: Path, a) -> dict:
    if not SHA40.match(a.sha):
        raise SystemExit("--sha must be a full 40-character commit SHA")
    market = load(repo)
    entries = market.setdefault("plugins", [])
    old = next((e for e in entries if e.get("name") == a.update_pinned), None)
    src = {"source": "git-subdir", "url": a.repo, "path": a.path, "sha": a.sha} if a.path \
        else {"source": "github", "repo": a.repo, "sha": a.sha}
    new = dict(old or {})
    new.update({"name": a.update_pinned, "description": a.description, "version": a.version, "source": src,
                "homepage": f"https://github.com/{a.repo}" + (f"/tree/{a.sha}/{a.path}" if a.path else "")})
    new.setdefault("author", market.get("owner"))
    new["category"] = a.category or new.get("category") or "productivity"
    if old is None:
        entries.append(ordered(new))
    else:
        entries[entries.index(old)] = ordered(new)
    save(repo, market)
    return new


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", nargs="*", metavar="NAME")
    ap.add_argument("--update-entry", metavar="NAME")
    ap.add_argument("--update-pinned", metavar="NAME")
    ap.add_argument("--repo", dest="upstream_repo")
    ap.add_argument("--sha")
    ap.add_argument("--path")
    ap.add_argument("--description")
    ap.add_argument("--version")
    ap.add_argument("--category")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    if not (repo / ".claude-plugin" / "marketplace.json").is_file():
        print(f"no .claude-plugin/marketplace.json in {repo}", file=sys.stderr)
        return 2
    if a.update_entry:
        if not (repo / "plugins" / a.update_entry / ".claude-plugin" / "plugin.json").is_file():
            print(f"plugins/{a.update_entry} has no plugin.json", file=sys.stderr)
            return 2
        print(json.dumps(update_entry(repo, a.update_entry, a.category), indent=2))
        return 0
    if a.update_pinned:
        if not (a.upstream_repo and a.sha and a.description and a.version):
            print("--update-pinned needs --repo, --sha, --description and --version", file=sys.stderr)
            return 2
        a.repo = a.upstream_repo
        print(json.dumps(update_pinned(repo, a), indent=2))
        return 0
    issues = drift(repo)
    if a.only is not None:
        keep = set(a.only)
        issues = [i for i in issues if keep & {x.strip() for x in i["plugin"].split(",")}]
    if a.json:
        print(json.dumps({"in_sync": not issues, "issues": issues}, indent=2))
    elif not issues:
        print("marketplace.json is in sync with plugins/")
    else:
        for i in issues:
            print(f"{i['issue']:<22} {i['plugin']}: {i['detail']}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())

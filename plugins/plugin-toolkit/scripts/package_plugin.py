#!/usr/bin/env python3
"""Build the evidence package every review and security analyst reads.

Every analyst gets the same bytes: one evidence.md with the file inventory, the
mechanical findings and the full text of the plugin, plus a machine-readable
manifest.json. Analysts read only the package, never the live folder, so a panel
can't drift apart by reading different versions of a file.

Usage:
  package_plugin.py SOURCE --out DIR [--ref REF] [--marketplace REPO_ROOT]

SOURCE is a local plugin folder or a GitHub URL:
  https://github.com/OWNER/REPO
  https://github.com/OWNER/REPO/tree/REF/path/to/plugin
GitHub sources are shallow-cloned into DIR/source and pinned to the commit SHA.
Prints the package folder; exit 0 on success, 2 on usage or clone errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stamp as st  # noqa: E402
import validate_plugin as vp  # noqa: E402

PER_FILE_LIMIT = 60_000
TOTAL_LIMIT = 1_500_000
GH = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?/?$")
LANG = {".py": "python", ".sh": "bash", ".json": "json", ".md": "markdown", ".yaml": "yaml", ".yml": "yaml",
        ".js": "javascript", ".ts": "typescript", ".ps1": "powershell", ".toml": "toml"}


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"{' '.join(cmd[:3])} failed: {r.stderr.strip()[:400]}")
    return r.stdout.strip()


def fetch_github(url: str, ref: str | None, dest: Path) -> tuple[Path, str]:
    m = GH.match(url)
    if not m:
        raise SystemExit(f"not a GitHub repo URL: {url}")
    owner, repo, url_ref, sub = m.groups()
    ref = ref or url_ref
    if ref is not None and (not re.match(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$", ref) or ".." in ref):
        raise SystemExit(f"refusing unsafe git ref {ref!r}")
    dest.mkdir(parents=True, exist_ok=True)
    clone = dest / "source"
    if clone.exists():
        shutil.rmtree(clone)
    remote = f"https://github.com/{owner}/{repo}.git"
    if ref and re.fullmatch(r"[0-9a-f]{40}", ref):
        clone.mkdir()
        run(["git", "init", "-q"], clone)
        run(["git", "fetch", "-q", "--depth", "1", remote, ref], clone)
        run(["git", "checkout", "-q", "FETCH_HEAD"], clone)
    else:
        cmd = ["git", "clone", "-q", "--depth", "1"] + (["--branch", ref] if ref else []) + [remote, str(clone)]
        run(cmd)
    sha = run(["git", "rev-parse", "HEAD"], clone)
    plugin = (clone / sub).resolve() if sub else clone
    if sub and clone.resolve() not in plugin.parents:
        raise SystemExit(f"path {sub!r} escapes the clone")
    if not plugin.is_dir():
        raise SystemExit(f"path {sub!r} not found in {owner}/{repo}@{sha[:12]}")
    return plugin, sha


def build(source: str, out: Path, ref: str | None = None, marketplace: Path | None = None) -> Path:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if source.startswith("https://"):
        plugin, sha = fetch_github(source, ref, out)
        src = {"type": "github", "location": source, "sha": sha}
    else:
        plugin = Path(source).resolve()
        if not plugin.is_dir():
            raise SystemExit(f"not a folder: {source}")
        sha = None
        r = subprocess.run(["git", "-C", str(plugin), "rev-parse", "HEAD"], capture_output=True, text=True)
        if r.returncode == 0:
            sha = r.stdout.strip()
        src = {"type": "local", "location": str(plugin), "sha": sha}
    thash = st.tree_hash(plugin)
    src["tree_hash"] = thash
    mech = vp.validate(plugin, marketplace=marketplace)
    mech["source"] = src
    (out / "mechanical.json").write_text(json.dumps(mech, indent=2), encoding="utf-8")

    files = st.list_files(plugin)
    inventory = []
    for rel in files:
        p = plugin / rel
        data = p.read_bytes() if p.is_file() else b""
        inventory.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                          "executable": bool(p.is_file() and p.stat().st_mode & 0o100),
                          "text": vp.read_text(p) is not None})
    manifest = {"schema_version": 1, "plugin": mech["plugin"], "plugin_version": mech["plugin_version"],
                "plugin_dir": str(plugin), "source": src, "files": inventory,
                "mechanical_summary": mech["summary"]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [f"# Evidence package: {mech['plugin']} {mech['plugin_version'] or ''}".rstrip(), "",
             "Read-only evidence for the review and security panels. Every analyst receives these exact bytes.",
             "", "| Field | Value |", "|---|---|",
             f"| Source | {src['type']}: {src['location']} |",
             f"| Commit | {src['sha'] or 'n/a'} |",
             f"| Tree hash | {thash} |",
             f"| Files | {len(inventory)} |",
             f"| Mechanical findings (open) | {mech['summary']['critical']} critical, {mech['summary']['major']} major, "
             f"{mech['summary']['minor']} minor |", "",
             "## File inventory", "", "| Path | Bytes | Exec | SHA-256 (12) |", "|---|---|---|---|"]
    for f in inventory:
        lines.append(f"| `{f['path']}` | {f['bytes']} | {'yes' if f['executable'] else ''} | {f['sha256'][:12]} |")
    lines += ["", "## Mechanical findings", "",
              "From `validate_plugin.py`. Re-raise one only to escalate it, with a reason.", ""]
    if mech["findings"]:
        for f in mech["findings"]:
            loc = f"{f['file']}:{f['line']}" if f["line"] else (f["file"] or "-")
            lines.append(f"- {f['id']} {f['severity']} {f['rule']} `{loc}` {f['title']}"
                         + (f" ({f['status']})" if f["status"] != "open" else "")
                         + (f": {f['evidence']}" if f["evidence"] else ""))
    else:
        lines.append("None.")
    for n in mech.get("notes", []):
        lines.append(f"- note: {n}")
    lines += ["", "## Files", ""]
    total = 0
    for f in inventory:
        p = plugin / f["path"]
        text = vp.read_text(p) if f["text"] else None
        lines.append(f"### `{f['path']}`")
        lines.append("")
        if text is None:
            lines += [f"(binary or unreadable, {f['bytes']} bytes, not shown)", ""]
            continue
        cut = ""
        if len(text) > PER_FILE_LIMIT:
            text, cut = text[:PER_FILE_LIMIT], f"\n(truncated at {PER_FILE_LIMIT} characters of {f['bytes']} bytes)"
        if total + len(text) > TOTAL_LIMIT:
            lines += ["(package size limit reached; remaining files listed in the inventory only)", ""]
            break
        total += len(text)
        fence = "````" if "```" in text else "```"
        lines += [f"{fence}{LANG.get(p.suffix, '')}", text.rstrip("\n"), fence + cut, ""]
    (out / "evidence.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref")
    ap.add_argument("--marketplace")
    a = ap.parse_args(argv)
    out = build(a.source, Path(a.out), a.ref, Path(a.marketplace).resolve() if a.marketplace else None)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Bring an outside plugin, skill or MCP server into quarantine, safely.

Usage:
  intake.py SOURCE [--quarantine DIR] [--kind auto|plugin|skill|mcp] [--name NAME]
                   [--ref REF] [--path SUBDIR] [--json]

SOURCE is one of:
  path/to/file.zip                       a zipped plugin, skill or MCP config
  https://github.com/OWNER/REPO[/tree/REF/SUBDIR]
  marketplace:PLUGIN@OWNER/REPO          an entry in another marketplace (e.g. Anthropic's)
  path/to/folder                         a local plugin, skill folder or MCP config
  path/to/server.json                    an MCP server config (mcpServers map or one server)

What it does, in order (see references/intake-policy.md):
  1. For a zip: checks every entry (absolute or .. paths, symlinks, sizes, count,
     compression ratio, blocked or unexpected executables) BEFORE writing anything.
  2. Unpacks or shallow-clones into DIR/<name>-<timestamp>/src, pinned to a commit SHA
     or the zip's SHA-256, then re-checks every file on disk.
  3. Detects the kind and, for a bare skill or MCP server, wraps it into a plugin using
     the templates in references/scaffold-templates.md.
  4. Writes PROVENANCE.md and prints a JSON summary.
Nothing is executed, installed or evaluated. Exit: 0 accepted, 3 rejected, 2 usage error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_plugin as vp  # noqa: E402

TOOLKIT_VERSION = json.loads((HERE.parent / ".claude-plugin" / "plugin.json").read_text())["version"]
TEMPLATES = HERE.parent / "references" / "scaffold-templates.md"
GH = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?/?$")
MKT = re.compile(r"^marketplace:([\w.-]+)@([\w.-]+)/([\w.-]+)$")


class Rejected(Exception):
    pass


SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


def safe_ref(ref: str | None) -> str | None:
    if ref is None or SAFE_REF.match(ref) and ".." not in ref:
        return ref
    raise Rejected(f"refusing unsafe git ref {ref!r}")


def inside(base: Path, sub: str | None) -> Path:
    """Resolve sub under base and refuse anything that escapes it (absolute paths, '..', symlinks)."""
    if not sub:
        return base
    target = (base / sub).resolve()
    if target != base.resolve() and base.resolve() not in target.parents:
        raise Rejected(f"path {sub!r} escapes the source")
    return target


def policy() -> dict:
    return vp.policy_block("max_archive_bytes")


def stamp_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def template(name: str) -> str:
    text = TEMPLATES.read_text(encoding="utf-8")
    m = re.search(rf"<!-- template: {re.escape(name)} -->\s*```[a-z]*\n(.*?)```\s*<!-- /template -->", text, re.S)
    if not m:
        raise SystemExit(f"template {name!r} not found in scaffold-templates.md")
    return m.group(1)


def fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[\w-]+\}\}", text)
    if left:
        raise SystemExit(f"unfilled template placeholders: {', '.join(sorted(set(left)))}")
    return text


# ---------------------------------------------------------------- checks
def check_zip(path: Path, pol: dict) -> list[str]:
    reasons = []
    size = path.stat().st_size
    if size > pol["max_archive_bytes"]:
        return [f"archive is {size} bytes, over the {pol['max_archive_bytes']} limit"]
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        return [f"not a valid zip: {exc}"]
    with zf:
        infos = zf.infolist()
        if len(infos) > pol["max_files"]:
            reasons.append(f"{len(infos)} entries, over the {pol['max_files']} limit")
        total = 0
        for info in infos:
            name = info.filename
            pp = PurePosixPath(name.replace("\\", "/"))
            if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name) or ".." in pp.parts:
                reasons.append(f"path escapes the archive: {name}")
                continue
            mode = (info.external_attr >> 16) & 0o177777
            if stat.S_ISLNK(mode):
                reasons.append(f"symlink entry: {name}")
            if info.file_size > pol["max_single_file_bytes"]:
                reasons.append(f"file over the size limit: {name} ({info.file_size} bytes)")
            if info.compress_size and info.file_size / max(info.compress_size, 1) > pol["max_compression_ratio"] \
                    and info.file_size > 1_000_000:
                reasons.append(f"suspicious compression ratio: {name}")
            ext = pp.suffix.lower()
            if ext in pol["blocked_extensions"]:
                reasons.append(f"blocked file type: {name}")
            if not info.is_dir() and mode & 0o111 and ext not in pol["allowed_executable_extensions"]:
                reasons.append(f"unexpected executable: {name}")
            total += info.file_size
        if total > pol["max_unpacked_bytes"]:
            reasons.append(f"unpacks to {total} bytes, over the {pol['max_unpacked_bytes']} limit")
    return reasons


def check_tree(root: Path, pol: dict) -> list[str]:
    reasons, count, total = [], 0, 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = [n for n in dirnames if n != ".git"]
        for n in dirnames + filenames:
            p = d / n
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                reasons.append(f"symlink: {rel}")
                continue
            if p.is_file():
                count += 1
                sz = p.stat().st_size
                total += sz
                ext = p.suffix.lower()
                if sz > pol["max_single_file_bytes"]:
                    reasons.append(f"file over the size limit: {rel}")
                if ext in pol["blocked_extensions"]:
                    reasons.append(f"blocked file type: {rel}")
                if p.stat().st_mode & 0o111 and ext not in pol["allowed_executable_extensions"]:
                    reasons.append(f"unexpected executable: {rel}")
    if count > pol["max_files"]:
        reasons.append(f"{count} files, over the {pol['max_files']} limit")
    if total > pol["max_unpacked_bytes"]:
        reasons.append(f"{total} bytes, over the {pol['max_unpacked_bytes']} limit")
    return reasons


# ---------------------------------------------------------------- fetch
def git(cmd, cwd=None):
    r = subprocess.run(["git", *cmd], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise Rejected(f"git {cmd[0]} failed: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def clone(owner: str, repo: str, ref: str | None, dest: Path) -> str:
    remote = f"https://github.com/{owner}/{repo}.git"
    ref = safe_ref(ref)
    if ref and re.fullmatch(r"[0-9a-f]{40}", ref):
        dest.mkdir(parents=True)
        git(["init", "-q"], dest)
        git(["fetch", "-q", "--depth", "1", remote, ref], dest)
        git(["checkout", "-q", "FETCH_HEAD"], dest)
    else:
        git(["clone", "-q", "--depth", "1", "--no-tags", *(["--branch", ref] if ref else []), remote, str(dest)])
    sha = git(["rev-parse", "HEAD"], dest)
    shutil.rmtree(dest / ".git")
    return sha


def resolve_marketplace(plugin: str, owner: str, repo: str, work: Path) -> tuple[str, str | None, str | None, str]:
    """Return (owner/repo, ref or sha, subdir, description) for a plugin listed in another marketplace."""
    mdir = work / "marketplace-index"
    sha = clone(owner, repo, None, mdir)
    data = json.loads((mdir / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next((p for p in data.get("plugins", []) if p.get("name") == plugin), None)
    if entry is None:
        raise Rejected(f"{plugin} is not listed in {owner}/{repo}")
    src = entry.get("source")
    if isinstance(src, str):
        sub = src[2:] if src.startswith("./") else src
        root = data.get("metadata", {}).get("pluginRoot")
        if root and not src.startswith("./"):
            sub = f"{root.strip('./')}/{src}"
        return f"{owner}/{repo}", sha, sub, f"marketplace {owner}/{repo} entry {plugin}"
    if isinstance(src, dict) and src.get("source") == "github":
        return src["repo"], src.get("sha") or src.get("ref"), src.get("path"), f"marketplace {owner}/{repo} entry {plugin}"
    if isinstance(src, dict) and src.get("source") in ("url", "git-subdir"):
        m = re.match(r"^(?:https://github\.com/)?([\w.-]+)/([\w.-]+?)(?:\.git)?$", src.get("url", ""))
        if not m:
            raise Rejected(f"only GitHub-hosted entries can be imported, got {src.get('url')}")
        return f"{m.group(1)}/{m.group(2)}", src.get("sha") or src.get("ref"), src.get("path"), \
            f"marketplace {owner}/{repo} entry {plugin}"
    raise Rejected(f"unsupported source type for {plugin}: {src!r}")


# ---------------------------------------------------------------- detect + wrap
def detect(root: Path) -> tuple[str, Path]:
    for cand in [root, *sorted(p.parent.parent for p in root.rglob(".claude-plugin/plugin.json"))]:
        if (cand / ".claude-plugin" / "plugin.json").is_file():
            return "plugin", cand
    skills = sorted(root.rglob("SKILL.md"))
    if len(skills) == 1:
        return "skill", skills[0].parent
    if len(skills) > 1:
        raise Rejected(f"found {len(skills)} SKILL.md files and no plugin.json; pass --path to pick one")
    for cand in [root / ".mcp.json", *sorted(root.rglob("*.json"))]:
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, dict) and ("mcpServers" in data or "command" in data or "url" in data):
                return "mcp", cand
    raise Rejected("no plugin.json, SKILL.md or MCP server config found")


def license_of(folder: Path) -> tuple[str | None, Path | None]:
    for n in vp.LICENSE_FILES:
        p = folder / n
        if p.is_file():
            return vp.detect_license(p.read_text(encoding="utf-8", errors="replace")), p
    return None, None


def kebab(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:64]


def base_values(name: str, desc: str, lic: str | None, author: str, components: str, requirements: str, usage: str):
    desc = desc.strip().replace("\n", " ")
    if len(desc) > 300:
        desc = desc[:297].rsplit(" ", 1)[0] + "..."
    return {"plugin-name": name, "plugin-description": desc, "version": "0.1.0", "author": author,
            "github-owner": "MMEnter", "marketplace-repo": "magical-plugin-marketplace",
            "license": lic or "UNLICENSED", "keywords": json.dumps(["imported", "claude-skill", "plugin", name][:4]),
            "components": components, "requirements": requirements, "usage": usage,
            "year": str(_dt.date.today().year)}


def wrap_skill(skill_dir: Path, out: Path, name: str | None, author: str) -> Path:
    fm, err, _ = vp.frontmatter(skill_dir.joinpath("SKILL.md").read_text(encoding="utf-8"))
    if err:
        raise Rejected(f"SKILL.md: {err}")
    sname = kebab(str(fm.get("name") or skill_dir.name))
    pname = kebab(name or sname)
    lic, lic_file = license_of(skill_dir)
    if lic_file is None:
        lic, lic_file = license_of(skill_dir.parent)
    plugin = out / pname
    shutil.copytree(skill_dir, plugin / "skills" / sname,
                    ignore=shutil.ignore_patterns(*vp.LICENSE_FILES, "NOTICE", "NOTICE.*", ".git"))
    desc = str(fm.get("description") or f"Imported skill {sname}.")
    vals = base_values(pname, desc, lic, author,
                       f"- Skill `{sname}`: {desc[:200]}", "None beyond Claude Code (check the skill's own notes).",
                       f'Ask for what the skill does, for example: "{desc.split(".")[0][:120]}".')
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(fill(template("plugin.json"), vals), encoding="utf-8")
    (plugin / "README.md").write_text(fill(template("README.md"), vals), encoding="utf-8")
    if lic_file:
        shutil.copy2(lic_file, plugin / lic_file.name)
    for n in ("NOTICE", "NOTICE.md", "NOTICE.txt"):
        for d in (skill_dir, skill_dir.parent):
            if (d / n).is_file() and not (plugin / n).exists():
                shutil.copy2(d / n, plugin / n)
    return plugin


def wrap_mcp(cfg_file: Path, out: Path, name: str | None, author: str) -> Path:
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    servers = data.get("mcpServers") if "mcpServers" in data else {kebab(name or cfg_file.stem): data}
    if not isinstance(servers, dict) or not servers:
        raise Rejected("MCP config has no servers")
    pname = kebab(name or (next(iter(servers)) if len(servers) == 1 else cfg_file.parent.name))
    plugin = out / pname
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".mcp.json").write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n", encoding="utf-8")
    comps = []
    for sname, s in servers.items():
        if s.get("url"):
            host = re.sub(r"^\w+://", "", s["url"]).split("/")[0]
            transport, endpoint = s.get("type", "http"), f"Remote host: {host}."
        else:
            transport = "stdio"
            endpoint = f"Launched with `{s.get('command')} {' '.join(map(str, s.get('args', [])))}`."
        comps.append(fill(template("mcp-components"), {
            "server-name": sname, "server-transport": transport, "server-endpoint": endpoint,
            "server-source": "TO CONFIRM during review (HR-X05)",
            "server-data": "TO CONFIRM during review (HR-X04)"}).strip())
    lic, lic_file = license_of(cfg_file.parent)
    vals = base_values(pname, f"Imported MCP server{'s' if len(servers) > 1 else ''}: {', '.join(servers)}. "
                              "Wrapped as a plugin by plugin-toolkit.", lic, author, "\n".join(comps),
                       "Whatever the server's launcher needs (see Components).",
                       "Ask Claude to use the server's tools once the plugin is installed.")
    (plugin / ".claude-plugin" / "plugin.json").write_text(fill(template("plugin.json"), vals), encoding="utf-8")
    (plugin / "README.md").write_text(fill(template("README.md"), vals), encoding="utf-8")
    if lic_file:
        shutil.copy2(lic_file, plugin / lic_file.name)
    return plugin


def write_provenance(plugin: Path, source: dict, kind: str, lic: str | None):
    rows = [("Source type", source["type"] if kind == "plugin" else f"{source['type']} ({kind})"),
            ("Source", source["location"]),
            ("Pinned SHA or zip SHA-256", source.get("sha") or source.get("zip_sha256") or "n/a (local folder)"),
            ("License", lic or "NOT DETECTED (SEC-22 will block release)"),
            ("Storage", "to be decided (vendored or pinned)"),
            ("Imported", _dt.date.today().isoformat()),
            ("Imported by", f"plugin-toolkit {TOOLKIT_VERSION}")]
    text = "# Provenance\n\n| Field | Value |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in rows)
    text += "\n## Changes from upstream\n\n- None yet.\n"
    if kind != "plugin":
        text = text.replace("- None yet.", f"- Wrapped as a plugin from a standalone {kind} (plugin.json and README generated).")
    (plugin / "PROVENANCE.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- main flow
def intake(source: str, qroot: Path, kind: str = "auto", name: str | None = None, ref: str | None = None,
           subpath: str | None = None) -> dict:
    pol = policy()
    qroot = qroot.resolve()
    hint = name or kebab(Path(source.split("@")[0].split(":")[-1].rstrip("/")).stem) or "import"
    box = qroot / f"{hint}-{stamp_now()}"
    src_dir = box / "src"
    result = {"status": "rejected", "reasons": [], "quarantine": str(box), "plugin_dir": None, "kind": None,
              "name": None, "source": {}, "license": None}
    is_zip = source.lower().endswith(".zip") and Path(source).is_file()
    if is_zip:
        # Check the whole archive before anything is written, not even the quarantine folder.
        reasons = check_zip(Path(source).resolve(), pol)
        if reasons:
            result.update(reasons=reasons, quarantine=None)
            return result
    try:
        box.mkdir(parents=True)
        author = "upstream"
        if is_zip:
            z = Path(source).resolve()
            digest = "sha256:" + hashlib.sha256(z.read_bytes()).hexdigest()
            src_dir.mkdir()
            with zipfile.ZipFile(z) as zf:
                for info in zf.infolist():
                    target = (src_dir / info.filename).resolve()
                    if src_dir.resolve() not in target.parents and target != src_dir.resolve():
                        raise Rejected(f"path escapes quarantine: {info.filename}")
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as fin, open(target, "wb") as fout:
                        shutil.copyfileobj(fin, fout)
                    if (info.external_attr >> 16) & 0o111:
                        target.chmod(0o755)
            result["source"] = {"type": "zip", "location": z.name, "sha": None, "zip_sha256": digest}
        elif MKT.match(source):
            plugin, owner, repo = MKT.match(source).groups()
            repo_full, mref, msub, label = resolve_marketplace(plugin, owner, repo, box)
            o, r = repo_full.split("/", 1)
            sha = clone(o, r, ref or mref, src_dir)
            subpath = subpath or msub
            result["source"] = {"type": "marketplace", "location": f"https://github.com/{repo_full}"
                                + (f"/tree/{sha}/{subpath}" if subpath else f"/tree/{sha}"), "sha": sha,
                                "repo": repo_full, "path": subpath, "listed_in": label}
            shutil.rmtree(box / "marketplace-index", ignore_errors=True)
        elif GH.match(source):
            owner, repo, uref, usub = GH.match(source).groups()
            sha = clone(owner, repo, ref or uref, src_dir)
            subpath = subpath or usub
            result["source"] = {"type": "github", "location": f"https://github.com/{owner}/{repo}"
                                + (f"/tree/{sha}/{subpath}" if subpath else f"/tree/{sha}"), "sha": sha,
                                "repo": f"{owner}/{repo}", "path": subpath}
        elif Path(source).exists():
            p = Path(source).resolve()
            if p.is_file():
                src_dir.mkdir()
                shutil.copy2(p, src_dir / p.name)
            else:
                shutil.copytree(p, src_dir, symlinks=True, ignore=shutil.ignore_patterns(".git"))
            result["source"] = {"type": "local", "location": str(p), "sha": None}
        else:
            raise Rejected(f"source not found or not recognised: {source}")

        reasons = check_tree(src_dir, pol)
        if reasons:
            raise Rejected("; ".join(reasons))
        root = inside(src_dir, subpath)
        if not root.exists():
            raise Rejected(f"path {subpath!r} not found in the source")
        found_kind, found = detect(root)
        if kind != "auto" and kind != found_kind:
            raise Rejected(f"expected a {kind}, found a {found_kind}")
        out = box / "plugin"
        out.mkdir()
        if found_kind == "plugin":
            manifest = json.loads((found / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            pname = kebab(name or manifest.get("name") or found.name)
            plugin = out / pname
            shutil.copytree(found, plugin, symlinks=True)
        elif found_kind == "skill":
            plugin = wrap_skill(found, out, name, author)
        else:
            plugin = wrap_mcp(found, out, name, author)
        lic, _ = license_of(plugin)
        manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        lic = manifest.get("license") or lic
        write_provenance(plugin, result["source"], found_kind, lic)
        result.update(status="accepted", plugin_dir=str(plugin), kind=found_kind, name=plugin.name, license=lic)
    except Rejected as exc:
        result["reasons"] = [r for r in str(exc).split("; ") if r]
        shutil.rmtree(box, ignore_errors=True)
        result["quarantine"] = None
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--quarantine", default=".toolkit-quarantine")
    ap.add_argument("--kind", default="auto", choices=["auto", "plugin", "skill", "mcp"])
    ap.add_argument("--name")
    ap.add_argument("--ref")
    ap.add_argument("--path")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = intake(a.source, Path(a.quarantine), a.kind, a.name, a.ref, a.path)
    if a.json:
        print(json.dumps(res, indent=2))
    elif res["status"] == "accepted":
        print(f"accepted {res['kind']} {res['name']} into {res['plugin_dir']}")
        print(f"  source: {res['source'].get('location')}  pin: {res['source'].get('sha') or res['source'].get('zip_sha256')}")
        print(f"  license: {res['license']}")
    else:
        print("REJECTED: " + res["source"].get("location", a.source) if res["source"] else f"REJECTED: {a.source}")
        for r in res["reasons"]:
            print(f"  - {r}")
    return 0 if res["status"] == "accepted" else 3


if __name__ == "__main__":
    sys.exit(main())

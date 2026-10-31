#!/usr/bin/env python3
"""Compute a plugin's tree hash and write or verify its review stamp.

Usage:
  stamp.py hash PLUGIN_DIR
  stamp.py write PLUGIN_DIR --review REVIEW_FINDINGS --security SECURITY_FINDINGS
                 (--eval GATE_RESULT | --eval-waived) [--origin native|vendored] [--dry-run]
  stamp.py write-pinned REPO_ROOT NAME --repo OWNER/REPO --sha SHA [--path SUBDIR]
                 --review FILE --security FILE (--eval FILE | --eval-waived)
  stamp.py verify PLUGIN_DIR [--json]
  stamp.py verify-repo REPO_ROOT [--changed NAME ...] [--json]
  stamp.py --hash-term            read a denylist term from the terminal and print its hash

The tree hash covers every file git would commit (tracked plus untracked-not-ignored),
or every file outside the standard exclusions when the plugin is not in a git repo.
The stamp itself (.toolkit/stamp.json) and evals/results/ are never part of the hash.
Exit codes: 0 ok, 1 stamp missing/invalid/stale, 2 usage error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import getpass
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_plugin as vp  # noqa: E402  (sibling module; shares the rule catalog)

STAMP_REL = ".toolkit/stamp.json"
EXCLUDE_PARTS = {".git", "__pycache__", "node_modules"}
EXCLUDE_NAMES = {".DS_Store"}
TOOLKIT_VERSION = json.loads((HERE.parent / ".claude-plugin" / "plugin.json").read_text())["version"]
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _excluded(rel: str) -> bool:
    parts = rel.split("/")
    if rel == STAMP_REL or set(parts) & EXCLUDE_PARTS or parts[-1] in EXCLUDE_NAMES or rel.endswith(".pyc"):
        return True
    return "/".join(parts[:2]) == "evals/results"


def list_files(root: Path) -> list[str]:
    root = root.resolve()
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z", "--", "."],
                       capture_output=True)
    if r.returncode == 0:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-prefix"],
                             capture_output=True, text=True).stdout.strip()
        rels = []
        for raw in r.stdout.split(b"\0"):
            if not raw:
                continue
            rel = raw.decode()
            if top and rel.startswith(top):
                rel = rel[len(top):]
            if (root / rel).exists() or (root / rel).is_symlink():
                rels.append(rel)
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_PARTS]
            for n in filenames:
                rels.append((Path(dirpath) / n).relative_to(root).as_posix())
    return sorted({x for x in rels if not _excluded(x)})


def tree_hash(root: Path) -> str:
    root = root.resolve()
    h = hashlib.sha256()
    for rel in list_files(root):
        p = root / rel
        if p.is_symlink():
            mode, digest = "l", hashlib.sha256(os.readlink(p).encode()).hexdigest()
        else:
            mode = "x" if p.stat().st_mode & stat.S_IXUSR else "f"
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        h.update(f"{rel}\0{mode}\0{digest}\n".encode())
    return "sha256:" + h.hexdigest()


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def report_id(prefix: str, path: Path) -> str:
    data = path.read_bytes()
    try:
        rid = json.loads(data).get("report_id")
        if isinstance(rid, str) and rid.startswith(prefix + "-"):
            return rid
    except (json.JSONDecodeError, AttributeError):
        pass
    day = _dt.date.today().strftime("%Y%m%d")
    return f"{prefix}-{day}-{hashlib.sha256(data).hexdigest()[:8]}"


def read_waivers(root: Path) -> list[tuple[str, str, str]]:
    w = root / "waivers.md"
    rows = []
    if w.is_file():
        for line in w.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*((?:HR-[A-Z]\d{2})|(?:SEC-\d{2}))\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$", line)
            if m:
                rows.append(m.groups())
    return rows


def waiver_problems(root: Path, rules: dict) -> list[str]:
    probs = []
    rows = read_waivers(root)
    if rows and not (root / "PROVENANCE.md").is_file():
        probs.append("waivers.md exists but the plugin has no PROVENANCE.md; native plugins cannot waive rules")
    for rid, reason, date in rows:
        if rid not in rules:
            probs.append(f"waiver for unknown rule {rid}")
        elif rules[rid]["tier"] != "waivable":
            probs.append(f"waiver for mandatory rule {rid}")
        if not reason:
            probs.append(f"waiver for {rid} has no reason")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
            probs.append(f"waiver for {rid} has no YYYY-MM-DD date")
    return probs


def open_criticals(findings_file: Path, waived: set[str]) -> tuple[int, dict]:
    data = json.loads(findings_file.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or "findings" not in data:
        raise SystemExit(f"{findings_file} is not a findings file (see finding-schema.md)")
    n = 0
    for f in data["findings"]:
        # Mechanical findings in a report go stale as soon as they're fixed; stamp.py re-runs
        # the validator on the current files instead, so only judgment findings count here.
        if f.get("kind") == "mechanical":
            continue
        status = f.get("status", "open")
        if f.get("rule") in waived and status == "open":
            status = "waived"
        if status in ("open", "disputed") and f.get("severity") == "critical":
            n += 1
    return n, data


def gate_summary(path: Path | None, waived_flag: bool, thash: str) -> dict:
    if waived_flag:
        return {"result": "waived", "mode": None, "tree_hash": thash, "finished_at": now_iso()}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("passed"):
        raise SystemExit("eval gate did not pass; the stamp was not written")
    if data.get("tree_hash") != thash:
        raise SystemExit("eval gate ran against different files (tree hash differs); re-run eval_gate.py")
    return {"result": "passed", "mode": data.get("mode"), "tree_hash": thash, "finished_at": data.get("finished_at")}


# ---------------------------------------------------------------- write
def cmd_write(a) -> int:
    root = Path(a.plugin).resolve()
    rules = vp.load_rules()
    probs = waiver_problems(root, rules)
    if probs:
        print("cannot stamp: " + "; ".join(probs), file=sys.stderr)
        return 1
    waived = {r[0] for r in read_waivers(root)}
    if a.eval_waived and "HR-E01" not in waived:
        print("cannot stamp: --eval-waived needs an HR-E01 waiver in waivers.md", file=sys.stderr)
        return 1
    mech = vp.validate(root)
    if mech["summary"]["critical"]:
        print(f"cannot stamp: validator reports {mech['summary']['critical']} open critical finding(s)", file=sys.stderr)
        return 1
    rc, _ = open_criticals(Path(a.review), waived)
    sc, _ = open_criticals(Path(a.security), waived)
    if rc or sc:
        print(f"cannot stamp: {rc + sc} open or disputed critical finding(s) in the review reports", file=sys.stderr)
        return 1
    thash = tree_hash(root)
    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    origin = a.origin or ("vendored" if (root / "PROVENANCE.md").is_file() else "native")
    stamp = {
        "schema_version": 1, "plugin": manifest["name"], "version": manifest.get("version"),
        "origin": origin, "tree_hash": thash, "upstream": None,
        "review_report": report_id("rv", Path(a.review)), "security_report": report_id("sc", Path(a.security)),
        "open_criticals": 0, "eval_gate": gate_summary(Path(a.eval) if a.eval else None, a.eval_waived, thash),
        "waivers": sorted(waived), "toolkit_version": TOOLKIT_VERSION, "stamped_at": now_iso(),
    }
    if a.dry_run:
        print(json.dumps(stamp, indent=2))
        return 0
    out = root / STAMP_REL
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"stamped {stamp['plugin']} {stamp['version']} {thash}")
    return 0


def cmd_write_pinned(a) -> int:
    if not SHA40.match(a.sha):
        print("--sha must be a full 40-character commit SHA", file=sys.stderr)
        return 2
    rc, rdata = open_criticals(Path(a.review), set())
    sc, _ = open_criticals(Path(a.security), set())
    if rc or sc:
        print("cannot stamp: open critical findings; a pinned plugin cannot be patched", file=sys.stderr)
        return 1
    if a.eval_waived:
        gate = {"result": "waived", "mode": None, "tree_hash": None, "finished_at": now_iso()}
    else:
        gate = json.loads(Path(a.eval).read_text(encoding="utf-8"))
        if not gate.get("passed"):
            print("cannot stamp: eval gate did not pass", file=sys.stderr)
            return 1
        gate = {"result": "passed", "mode": gate.get("mode"), "tree_hash": gate.get("tree_hash"),
                "finished_at": gate.get("finished_at")}
    stamp = {
        "schema_version": 1, "plugin": a.name, "version": rdata.get("plugin_version"), "origin": "pinned",
        "tree_hash": f"git:{a.sha}", "upstream": {"repo": a.repo, "sha": a.sha, "path": a.path},
        "review_report": report_id("rv", Path(a.review)), "security_report": report_id("sc", Path(a.security)),
        "open_criticals": 0, "eval_gate": gate, "waivers": [], "toolkit_version": TOOLKIT_VERSION,
        "stamped_at": now_iso(),
    }
    out = Path(a.repo_root).resolve() / ".toolkit" / "pinned" / f"{a.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"stamped pinned {a.name} at {a.repo}@{a.sha[:12]}")
    return 0


# ---------------------------------------------------------------- verify
def verify_plugin(root: Path, rules: dict) -> list[str]:
    root = root.resolve()
    sp = root / STAMP_REL
    if not sp.is_file():
        return ["no review stamp (.toolkit/stamp.json); the plugin has not been through the toolkit"]
    try:
        stamp = json.loads(sp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"stamp is not valid JSON: {exc}"]
    probs = []
    manifest = {}
    try:
        manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        probs.append("plugin.json missing or invalid")
    if stamp.get("schema_version") != 1:
        probs.append("stamp schema_version is not 1")
    if stamp.get("plugin") != manifest.get("name"):
        probs.append(f"stamp is for {stamp.get('plugin')!r}, plugin is {manifest.get('name')!r}")
    if stamp.get("version") != manifest.get("version"):
        probs.append(f"stamp version {stamp.get('version')!r} differs from plugin.json {manifest.get('version')!r}")
    actual = tree_hash(root)
    if stamp.get("tree_hash") != actual:
        probs.append("files changed since review (tree hash differs); run the toolkit again")
    if stamp.get("open_criticals") != 0:
        probs.append("stamp records open critical findings")
    for key, pre in (("review_report", "rv-"), ("security_report", "sc-")):
        if not str(stamp.get(key, "")).startswith(pre):
            probs.append(f"stamp has no {key}")
    gate = stamp.get("eval_gate") or {}
    waivers = {r[0] for r in read_waivers(root)}
    if gate.get("result") == "passed":
        if gate.get("tree_hash") != stamp.get("tree_hash"):
            probs.append("eval gate result is for different files than the stamp")
    elif gate.get("result") == "waived":
        if "HR-E01" not in waivers:
            probs.append("eval gate marked waived but waivers.md has no HR-E01 waiver")
    else:
        probs.append("stamp has no passing eval gate")
    if sorted(waivers) != sorted(stamp.get("waivers", [])):
        probs.append("waivers.md differs from the waivers recorded in the stamp")
    probs += waiver_problems(root, rules)
    origin = stamp.get("origin")
    if origin == "native" and waivers:
        probs.append("native plugin carries waivers")
    if origin == "vendored" and not (root / "PROVENANCE.md").is_file():
        probs.append("vendored import has no PROVENANCE.md")
    return probs


def verify_pinned(repo: Path, entry: dict) -> list[str]:
    name = entry.get("name")
    sp = repo / ".toolkit" / "pinned" / f"{name}.json"
    if not sp.is_file():
        return [f"pinned entry {name} has no stamp at .toolkit/pinned/{name}.json"]
    stamp = json.loads(sp.read_text(encoding="utf-8"))
    src = entry.get("source") or {}
    probs = []
    if src.get("sha") != (stamp.get("upstream") or {}).get("sha"):
        probs.append(f"marketplace SHA {src.get('sha')!r} differs from stamped SHA "
                     f"{(stamp.get('upstream') or {}).get('sha')!r}; a SHA bump is a new import")
    if not SHA40.match(str(src.get("sha", ""))):
        probs.append("pinned entry has no full commit sha in its source")
    if stamp.get("open_criticals") != 0 or (stamp.get("eval_gate") or {}).get("result") not in ("passed", "waived"):
        probs.append("pinned stamp is incomplete")
    return probs


def cmd_verify(a) -> int:
    rules = vp.load_rules()
    probs = verify_plugin(Path(a.plugin), rules)
    if a.json:
        print(json.dumps({"plugin": Path(a.plugin).name, "ok": not probs, "problems": probs}, indent=2))
    else:
        print(("OK " if not probs else "FAIL ") + Path(a.plugin).name)
        for p in probs:
            print(f"  - {p}")
    return 1 if probs else 0


def cmd_verify_repo(a) -> int:
    repo = Path(a.repo_root).resolve()
    rules = vp.load_rules()
    market = json.loads((repo / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    results = []
    names = set(a.changed or [])
    for entry in market.get("plugins", []):
        name = entry.get("name")
        if names and name not in names:
            continue
        src = entry.get("source")
        if isinstance(src, dict):
            probs = verify_pinned(repo, entry)
        else:
            rel = str(src)[2:] if str(src).startswith("./") else str(src)
            probs = verify_plugin(repo / rel, rules)
        results.append({"plugin": name, "ok": not probs, "problems": probs})
    listed = {e.get("name") for e in market.get("plugins", [])}
    for d in sorted((repo / "plugins").iterdir()) if (repo / "plugins").is_dir() else []:
        if (d / ".claude-plugin").is_dir() and d.name not in listed and (not names or d.name in names):
            results.append({"plugin": d.name, "ok": not verify_plugin(d, rules),
                            "problems": verify_plugin(d, rules) + ["not listed in marketplace.json"]})
    bad = [r for r in results if not r["ok"] or r["problems"]]
    if a.json:
        print(json.dumps({"ok": not bad, "plugins": results}, indent=2))
    else:
        for r in results:
            print(("OK   " if not r["problems"] else "FAIL ") + r["plugin"])
            for p in r["problems"]:
                print(f"       - {p}")
    return 1 if bad else 0


def cmd_hash_term() -> int:
    term = getpass.getpass("Term to deny (input hidden): ")
    if not term.strip():
        print("empty term", file=sys.stderr)
        return 2
    print(vp.hash_term(term))
    return 0


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--hash-term"]:
        return cmd_hash_term()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hash")
    h.add_argument("plugin")
    w = sub.add_parser("write")
    w.add_argument("plugin")
    w.add_argument("--review", required=True)
    w.add_argument("--security", required=True)
    g = w.add_mutually_exclusive_group(required=True)
    g.add_argument("--eval")
    g.add_argument("--eval-waived", action="store_true")
    w.add_argument("--origin", choices=["native", "vendored"])
    w.add_argument("--dry-run", action="store_true")
    wp = sub.add_parser("write-pinned")
    wp.add_argument("repo_root")
    wp.add_argument("name")
    wp.add_argument("--repo", required=True)
    wp.add_argument("--sha", required=True)
    wp.add_argument("--path")
    wp.add_argument("--review", required=True)
    wp.add_argument("--security", required=True)
    g2 = wp.add_mutually_exclusive_group(required=True)
    g2.add_argument("--eval")
    g2.add_argument("--eval-waived", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("plugin")
    v.add_argument("--json", action="store_true")
    vr = sub.add_parser("verify-repo")
    vr.add_argument("repo_root")
    vr.add_argument("--changed", nargs="*")
    vr.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "hash":
        print(tree_hash(Path(a.plugin)))
        return 0
    return {"write": cmd_write, "write-pinned": cmd_write_pinned, "verify": cmd_verify,
            "verify-repo": cmd_verify_repo}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

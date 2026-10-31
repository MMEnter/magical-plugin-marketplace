#!/usr/bin/env python3
"""Run a plugin's eval suite and decide pass or fail (references/eval-standards.md).

Usage:
  eval_gate.py PLUGIN_DIR --mode pr|full [--yes] [--trust] [--dry-run] [--from-result FILE]

  --mode pr     smoke cases from eval-config.json, 1 run each, no baseline arm
  --mode full   every case, runs_full runs, with a no-plugin baseline arm
  --yes         skip the cost confirmation prompt
  --trust       pass --trust-plugin to claude (only for plugins you would run yourself)
  --dry-run     print the claude command and the run count, run nothing
  --from-result score an existing `claude plugin eval --json` file instead of running

Writes evals/results/gate-<timestamp>.json and prints its path.
Exit 0 = gate passed, 1 = gate failed, 2 = usage or setup error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stamp as st  # noqa: E402
import validate_plugin as vp  # noqa: E402

RATE_WORDS = ("rate limit", "rate_limit", "429", "overloaded", "too many requests")


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_config(plugin: Path) -> dict:
    p = plugin / "evals" / "eval-config.json"
    if not p.is_file():
        raise SystemExit("evals/eval-config.json is missing (HR-E05); run eval-plugin to create it")
    return json.loads(p.read_text(encoding="utf-8"))


def case_names(plugin: Path) -> list[str]:
    edir = plugin / "evals"
    names = []
    for p in sorted(edir.rglob("*")):
        if p.is_dir() and not {"results", "mocks"} & set(p.relative_to(edir).parts) and \
                ((p / "prompt.md").is_file() or (p / "case.yaml").is_file()):
            names.append(p.name)
    return names


def build_command(plugin: Path, cfg: dict, mode: str, out_json: Path, trust: bool) -> tuple[list[str], int, int]:
    cases = case_names(plugin)
    cmd = ["claude", "plugin", "eval", str(plugin), "--no-publish", "--json", str(out_json),
           "--threshold", str(cfg["threshold"])]
    if mode == "pr":
        smoke = cfg.get("smoke_cases") or []
        missing = [s for s in smoke if s not in cases]
        if missing:
            raise SystemExit(f"smoke case(s) not found: {', '.join(missing)}")
        cmd += ["--runs", "1", "--ablation", "none", "--case", "{case}"]
        n_cases, runs, arms = len(smoke), 1, 1
    else:
        runs = int(cfg.get("runs_full", 3))
        cmd += ["--runs", str(runs), "--ablation", "with-without"]
        n_cases, arms = len(cases), 2
    if cfg.get("judge_model"):
        cmd += ["--judge-model", cfg["judge_model"]]
    if cfg.get("allow_tools"):
        cmd += ["--allow-tools", *cfg["allow_tools"]]
    cmd += ["--scaffold"] if cfg.get("scaffold") else ["--no-scaffold"]
    if cfg.get("max_cost_usd"):
        cmd += ["--max-cost-usd", str(cfg["max_cost_usd"])]
    if trust:
        cmd.append("--trust-plugin")
    return cmd, n_cases, n_cases * runs * arms


def score(result: dict, expected: list[str], threshold: float, mode: str) -> tuple[list[dict], list[str]]:
    problems = []
    if result.get("partial"):
        problems.append("the eval run was partial (stopped early: cost ceiling, interrupt or crash)")
    plugins = (result.get("suite") or {}).get("plugins") or []
    if not plugins:
        problems.append("no plugin was loaded in the with-plugin arm; the run is meaningless")
    for p in plugins:
        if p.get("problem") in ("manifest_invalid", "disabled_by_default", "will_not_load"):
            problems.append(f"plugin did not load: {p.get('problem')}")
    by_name = {c.get("name"): c for c in result.get("cases", [])}
    cases = []
    for name in expected:
        c = by_name.get(name)
        if c is None:
            cases.append({"name": name, "score": None, "baseline": None, "status": "missing"})
            problems.append(f"case {name} has no result")
            continue
        arms = c.get("arms") or {}
        status = "ok"
        for run in arms.get("with", []) + arms.get("without", []):
            err = str(run.get("error") or "")
            if err:
                low = err.lower()
                status = "rate_limited" if any(w in low for w in RATE_WORDS) else \
                    "timeout" if "timeout" in low or "timed out" in low else "error"
                problems.append(f"case {name}: {status}: {err[:160]}")
                break
        with_scores = [r.get("score", 0) for r in arms.get("with", [])]
        without = [r.get("score", 0) for r in arms.get("without", [])]
        sc = (c.get("aggregates") or {}).get("score")
        if sc is None and with_scores:
            sc = sum(with_scores) / len(with_scores)
        base = sum(without) / len(without) if without else None
        if sc is None:
            status = "missing" if status == "ok" else status
            problems.append(f"case {name} has no score")
        elif sc < threshold:
            problems.append(f"case {name} scored {sc:.2f}, below the {threshold} threshold")
        cases.append({"name": name, "score": sc, "baseline": base, "status": status})
    if mode == "full" and not any(c["baseline"] is not None for c in cases):
        problems.append("full mode produced no baseline arm")
    return cases, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plugin")
    ap.add_argument("--mode", choices=["pr", "full"], required=True)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--trust", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-result")
    a = ap.parse_args(argv)
    plugin = Path(a.plugin).resolve()
    cfg = load_config(plugin)
    mech = vp.validate(plugin)
    if mech["summary"]["critical"]:
        print(f"gate failed before any model call: {mech['summary']['critical']} open critical finding(s); "
              "run review-plugin and fix-plugin first", file=sys.stderr)
        return 1
    thash = st.tree_hash(plugin)
    results_dir = plugin / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw = results_dir / f"eval-{a.mode}-{ts}.json"
    cmd, n_cases, n_runs = build_command(plugin, cfg, a.mode, raw, a.trust)
    expected = cfg["smoke_cases"] if a.mode == "pr" else case_names(plugin)
    # pr mode runs one smoke case per invocation (case filters are single globs)
    cmds = [[x.replace("{case}", c) for x in cmd] for c in expected] if a.mode == "pr" else [cmd]
    raws = [raw.with_name(f"{raw.stem}-{i}.json") for i in range(len(cmds))] if len(cmds) > 1 else [raw]
    for c, rp in zip(cmds, raws):
        c[c.index("--json") + 1] = str(rp)
    if a.dry_run:
        for c in cmds:
            print(" ".join(c))
        print(f"{n_cases} case(s), {n_runs} agent run(s)")
        return 0
    if a.from_result:
        raw = Path(a.from_result)
    else:
        if not shutil.which("claude"):
            print("claude CLI not found", file=sys.stderr)
            return 2
        if not a.yes:
            ans = input(f"This runs {n_runs} billed agent run(s) across {n_cases} case(s), "
                        f"capped at ${cfg.get('max_cost_usd', 'no cap')}. Continue? [y/N] ")
            if ans.strip().lower() not in ("y", "yes"):
                print("cancelled")
                return 2
        for c, rp in zip(cmds, raws):
            r = subprocess.run(c)
            if not rp.is_file():
                print(f"claude plugin eval wrote no result (exit {r.returncode})", file=sys.stderr)
                return 1
    if a.from_result:
        raws = [raw]
    parts = [json.loads(rp.read_text(encoding="utf-8")) for rp in raws]
    result = dict(parts[0])
    result["cases"] = [c for p in parts for c in p.get("cases", [])]
    result["partial"] = any(p.get("partial") for p in parts)
    result["costUsd"] = sum(p.get("costUsd") or 0 for p in parts)
    cases, problems = score(result, expected, float(cfg["threshold"]), a.mode)
    if st.tree_hash(plugin) != thash:
        problems.append("plugin files changed while the evals ran; re-run the gate")
    gate = {"schema_version": 1, "plugin": mech["plugin"], "tree_hash": thash, "mode": a.mode,
            "passed": not problems, "threshold": cfg["threshold"], "cases": cases, "problems": problems,
            "cost_usd": result.get("costUsd"), "eval_results": [str(r) for r in raws], "finished_at": now_iso()}
    out = results_dir / f"gate-{ts}.json"
    out.write_text(json.dumps(gate, indent=2), encoding="utf-8")
    print(("PASSED" if gate["passed"] else "FAILED") + f" ({a.mode}) {out}")
    for c in cases:
        b = "" if c["baseline"] is None else f" (baseline {c['baseline']:.2f})"
        s = "-" if c["score"] is None else f"{c['score']:.2f}"
        print(f"  {c['status']:<12} {s}{b}  {c['name']}")
    for p in problems:
        print(f"  - {p}")
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

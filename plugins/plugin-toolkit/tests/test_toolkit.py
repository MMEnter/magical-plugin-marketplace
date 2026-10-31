"""Unit tests for plugin-toolkit's scripts. No model calls, no network.

Run from the repo root:  python3 -m unittest discover -s plugins/plugin-toolkit/tests -v
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

import intake  # noqa: E402
import make_fixtures as mf  # noqa: E402
import package_plugin  # noqa: E402
import render_report  # noqa: E402
import stamp as st  # noqa: E402
import sync_marketplace as sm  # noqa: E402
import validate_plugin as vp  # noqa: E402

RULES = vp.load_rules()


def rules_hit(result: dict) -> set[str]:
    return {f["rule"] for f in result["findings"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="toolkit-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, name: str) -> Path:
        dest = self.tmp / name
        mf.MAKERS[name](dest)
        return dest


class RulebookTests(unittest.TestCase):
    def test_catalog_shape(self):
        hr = [r for r in RULES if r.startswith("HR-")]
        sec = [r for r in RULES if r.startswith("SEC-")]
        core = [r for r in hr if r[3] in "MSAPCE"]
        self.assertEqual(len(core), 46, "the six core HR families hold 46 rules")
        self.assertEqual(len(sec), 23)
        for fam in "HKX":
            self.assertTrue(any(r.startswith(f"HR-{fam}") for r in hr), f"family HR-{fam} missing")

    def test_security_rules_are_mandatory(self):
        for rid, r in RULES.items():
            if rid.startswith("SEC-"):
                self.assertEqual(r["tier"], "mandatory", rid)

    def test_policy_blocks_parse(self):
        self.assertIn("MIT", vp.policy_block("allowed_licenses")["allowed_licenses"])
        self.assertIn(".exe", vp.policy_block("blocked_extensions")["blocked_extensions"])


class ValidatorTests(Base):
    def test_broken_fixture_trips_every_mechanical_rule(self):
        broken = self.make("broken-marketplace")
        bad_manifest = self.make("broken-manifest")
        hit = rules_hit(vp.validate(broken / "plugins" / "broken-plugin", use_cli=False))
        hit |= rules_hit(vp.validate(bad_manifest / "bad-manifest", use_cli=False))
        mechanical = {rid for rid, r in RULES.items() if r["kind"] == "mechanical" and not r["retired"]}
        self.assertEqual(sorted(mechanical - hit), [], "mechanical rules the fixtures failed to trip")

    def test_clean_fixture_is_clean(self):
        clean = self.make("clean-marketplace")
        res = vp.validate(clean / "plugins" / "tidy-notes", use_cli=False)
        self.assertEqual(res["findings"], [], res["findings"])

    def test_secrets_are_redacted(self):
        case = self.make("secret-case")
        res = vp.validate(case / "plugins" / "tidy-notes", use_cli=False)
        sec = [f for f in res["findings"] if f["rule"] == "SEC-21"]
        self.assertEqual(len(sec), 1)
        self.assertNotIn("AKIA", json.dumps(res))

    def test_waivers_only_for_imports_and_waivable_rules(self):
        clean = self.make("clean-marketplace")
        p = clean / "plugins" / "tidy-notes"
        shutil.rmtree(p / "evals")
        (p / "waivers.md").write_text("| Rule | Reason | Date |\n|---|---|---|\n"
                                      "| HR-E01 | no upstream evals | 2026-10-31 |\n")
        native = vp.validate(p, use_cli=False)
        self.assertEqual({f["status"] for f in native["findings"] if f["rule"] == "HR-E01"}, {"open"})
        (p / "PROVENANCE.md").write_text("# Provenance\n")
        imported = vp.validate(p, use_cli=False)
        self.assertEqual({f["status"] for f in imported["findings"] if f["rule"] == "HR-E01"}, {"waived"})

    def test_denylist_matches_hash_not_text(self):
        f = self.tmp / "note.txt"
        f.write_text("this mentions " + mf.DENY_TERM.upper() + " loudly\n")
        dl = [{"sha256": vp.hash_term(mf.DENY_TERM), "label": "x"}]
        res = vp.scan_files([f], dl, RULES)
        self.assertEqual([x["rule"] for x in res["findings"]], ["SEC-23"])


class IntakeTests(Base):
    def test_unsafe_zip_rejected_before_unpacking(self):
        z = mf.make_unsafe_zip(self.tmp / "zips")
        q = self.tmp / "q"
        res = intake.intake(str(z), q)
        self.assertEqual(res["status"], "rejected")
        self.assertTrue(any("escapes" in r for r in res["reasons"]), res["reasons"])
        self.assertFalse(any(self.tmp.rglob("outside-quarantine.txt")))
        self.assertEqual(list(q.iterdir()) if q.exists() else [], [])

    def test_bare_skill_is_wrapped_with_provenance(self):
        src = self.tmp / "incoming"
        mf.make_bare_skill(src)
        res = intake.intake(str(src / "meeting-minutes"), self.tmp / "q", kind="skill")
        self.assertEqual(res["status"], "accepted", res["reasons"])
        p = Path(res["plugin_dir"])
        for rel in (".claude-plugin/plugin.json", "README.md", "LICENSE", "PROVENANCE.md",
                    "skills/meeting-minutes/SKILL.md", "skills/meeting-minutes/references/minutes-format.md"):
            self.assertTrue((p / rel).is_file(), rel)
        res = vp.validate(p, use_cli=False)
        self.assertEqual(res["summary"]["critical"], 0, res["findings"])

    def test_mcp_config_is_wrapped(self):
        cfg = self.tmp / "server.json"
        cfg.write_text(json.dumps({"mcpServers": {"weather": {"command": "npx", "args": ["-y", "weather-mcp@1.2.3"]}}}))
        res = intake.intake(str(cfg), self.tmp / "q", kind="mcp")
        self.assertEqual(res["status"], "accepted", res["reasons"])
        p = Path(res["plugin_dir"])
        self.assertEqual(json.loads((p / ".mcp.json").read_text())["mcpServers"]["weather"]["args"][1],
                         "weather-mcp@1.2.3")

    def test_subpath_cannot_escape_the_source(self):
        src = self.tmp / "incoming"
        mf.make_bare_skill(src)
        res = intake.intake(str(src / "meeting-minutes"), self.tmp / "q", subpath="../../")
        self.assertEqual(res["status"], "rejected")
        self.assertTrue(any("escapes" in r for r in res["reasons"]), res["reasons"])

    def test_unsafe_ref_refused(self):
        with self.assertRaises(intake.Rejected):
            intake.safe_ref("--upload-pack=touch x")

    def test_symlink_in_folder_rejected(self):
        src = self.tmp / "linky"
        mf.make_bare_skill(src)
        (src / "meeting-minutes" / "evil").symlink_to("/etc")
        res = intake.intake(str(src / "meeting-minutes"), self.tmp / "q", kind="skill")
        self.assertEqual(res["status"], "rejected")


class StampTests(Base):
    def _reports(self, plugin: Path) -> tuple[Path, Path, Path]:
        empty = {"schema_version": 1, "mode": "review", "plugin": plugin.name, "findings": [],
                 "summary": {"critical": 0, "major": 0, "minor": 0}}
        rv, sc = self.tmp / "rv.json", self.tmp / "sc.json"
        rv.write_text(json.dumps(empty))
        sc.write_text(json.dumps({**empty, "mode": "security"}))
        gate = self.tmp / "gate.json"
        gate.write_text(json.dumps({"schema_version": 1, "passed": True, "mode": "full",
                                    "tree_hash": st.tree_hash(plugin), "finished_at": "2026-10-31T00:00:00Z"}))
        return rv, sc, gate

    def test_write_verify_then_stale(self):
        clean = self.make("clean-marketplace")
        p = clean / "plugins" / "tidy-notes"
        rv, sc, gate = self._reports(p)
        with redirect_stdout(io.StringIO()):
            rc = st.main(["write", str(p), "--review", str(rv), "--security", str(sc), "--eval", str(gate)])
        self.assertEqual(rc, 0)
        self.assertEqual(st.verify_plugin(p, RULES), [])
        (p / "README.md").write_text((p / "README.md").read_text() + "\nedited\n")
        probs = st.verify_plugin(p, RULES)
        self.assertTrue(any("tree hash" in x for x in probs), probs)

    def test_refuses_with_open_critical(self):
        case = self.make("critical-marketplace")
        p = case / "plugins" / "tidy-notes"
        rv, sc, gate = self._reports(p)
        with redirect_stdout(io.StringIO()):
            rc = st.main(["write", str(p), "--review", str(rv), "--security", str(sc), "--eval", str(gate)])
        self.assertEqual(rc, 1)
        self.assertFalse((p / st.STAMP_REL).exists())

    def test_stale_fixture_detected_by_repo_verify(self):
        repo = self.make("stale-marketplace")
        with redirect_stdout(io.StringIO()) as out:
            rc = st.main(["verify-repo", str(repo), "--json"])
        data = json.loads(out.getvalue())
        self.assertEqual(rc, 1)
        tidy = next(x for x in data["plugins"] if x["plugin"] == "tidy-notes")
        self.assertTrue(any("tree hash" in p for p in tidy["problems"]))

    def test_package_and_stamp_agree_on_tree_hash(self):
        clean = self.make("clean-marketplace")
        p = clean / "plugins" / "tidy-notes"
        out = package_plugin.build(str(p), self.tmp / "pkg")
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["source"]["tree_hash"], st.tree_hash(p))
        self.assertIn("## Files", (out / "evidence.md").read_text())


class SyncTests(Base):
    def test_unlisted_plugin_reported(self):
        repo = self.make("stale-marketplace")
        issues = sm.drift(repo)
        self.assertIn(("orphan-notes", "unlisted_plugin"), {(i["plugin"], i["issue"]) for i in issues})
        self.assertTrue(any(i["issue"] == "name_collision" for i in issues), "both fixtures share a skill name")

    def test_update_entry_round_trip(self):
        repo = self.make("stale-marketplace")
        sm.update_entry(repo, "orphan-notes", "productivity")
        self.assertNotIn("unlisted_plugin", {i["issue"] for i in sm.drift(repo)})


class RenderTests(Base):
    def test_render_and_patch_check(self):
        case = self.make("fix-case")
        rep = case / ".toolkit-work" / "tidy-notes-review" / "review"
        out = self.tmp / "rendered"
        with redirect_stdout(io.StringIO()) as buf:
            rc = render_report.main([str(rep / "findings.json"), "--out", str(out),
                                     "--plugin", str(case / "plugins" / "tidy-notes")])
        self.assertEqual(rc, 0)
        self.assertTrue(buf.getvalue().startswith("rv-"))
        data = json.loads((out / "findings.json").read_text())
        self.assertTrue(data["findings"][0]["patch_applies"])
        self.assertIn("applies cleanly", (out / "report.md").read_text())

    def test_rejects_unknown_rule_and_lowered_severity(self):
        bad = {"schema_version": 1, "mode": "review", "findings": [
            {"id": "F-001", "rule": "HR-Z99", "severity": "minor", "kind": "judgment", "analyst": "x",
             "status": "open", "title": "t", "evidence": "e", "fix": "f"},
            {"id": "F-002", "rule": "HR-C05", "severity": "minor", "kind": "mechanical", "analyst": "x",
             "status": "open", "title": "t", "evidence": "e", "fix": "f"}]}
        errs = render_report.validate_findings(bad, RULES)
        self.assertTrue(any("unknown rule" in e for e in errs))
        self.assertTrue(any("below the rule" in e for e in errs))


class ToolkitSelfTest(unittest.TestCase):
    def test_toolkit_has_no_critical_findings_except_marketplace_entry(self):
        res = vp.validate(HERE.parent, use_cli=False)
        crit = {f["rule"] for f in res["findings"] if f["severity"] == "critical" and f["status"] == "open"}
        self.assertTrue(crit <= {"HR-M09"}, crit)

    def test_git_available(self):
        self.assertEqual(subprocess.run(["git", "--version"], capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for protect_eval.py.  Run:  python -m unittest test_protect_eval -v   (from this folder)"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import protect_eval

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "protect_eval.py")


def call(root, rel, tool="Edit", field="file_path", config=None):
    if config is not None:
        with open(os.path.join(root, ".eval-protected"), "w", encoding="utf-8") as f:
            f.write(config)
    payload = {"tool_name": tool, "cwd": root, "tool_input": {field: os.path.join(root, rel)}}
    return protect_eval.decide(payload, project_root=root)


class Matching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="proj with spaces ")
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_grader_file_asks(self):
        out = call(self.root, "graders.py")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertIn("changes the measurement", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_ordinary_prompt_file_does_not_ask(self):
        self.assertIsNone(call(self.root, "system-prompt-coordinator.txt"))
        self.assertIsNone(call(self.root, "src/app.py"))

    def test_path_with_spaces_still_matches(self):
        self.assertIn(" ", self.root)
        self.assertIsNotNone(call(self.root, os.path.join("sub dir", "my graders.py")))

    def test_directory_pattern_covers_children(self):
        self.assertIsNotNone(call(self.root, "eval_results/run1/out.json"))
        self.assertIsNotNone(call(self.root, "graders/helpers/x.py"))

    def test_other_defaults(self):
        for rel in ("gold_labels.json", "a/b/holdout_set.py", "tasks.jsonl", "tasks_v2.jsonl",
                    "runs.jsonl", "llm_judge.py"):
            self.assertIsNotNone(call(self.root, rel), rel)

    def test_parent_folder_name_outside_project_is_not_matched(self):
        # the project folder itself is called "...graders..." but files inside are ordinary
        with tempfile.TemporaryDirectory(prefix="my-graders-project-") as root:
            self.assertIsNone(call(root, "src/app.py"))

    def test_notebook_path_field(self):
        out = call(self.root, "judge_demo.ipynb", tool="NotebookEdit", field="notebook_path")
        self.assertIsNotNone(out)

    def test_relative_path_resolved_against_cwd(self):
        payload = {"cwd": self.root, "tool_input": {"file_path": "graders.py"}}
        self.assertIsNotNone(protect_eval.decide(payload, project_root=self.root))

    def test_config_adds_pattern(self):
        self.assertIsNone(call(self.root, "Diagnose_Fix.py"))
        self.assertIsNotNone(call(self.root, "Diagnose_Fix.py", config="# comment\nDiagnose_Fix.py\n"))

    def test_config_removes_default(self):
        self.assertIsNotNone(call(self.root, "llm_judge.py"))
        self.assertIsNone(call(self.root, "llm_judge.py", config="!**/*judge*\n"))

    def test_config_file_itself_is_protected(self):
        self.assertIsNotNone(call(self.root, ".eval-protected"))

    def test_case_insensitive_flag(self):
        self.assertIsNotNone(protect_eval.matches("GRADERS.py", protect_eval.DEFAULT_PATTERNS, True))
        self.assertIsNone(protect_eval.matches("GRADERS.py", protect_eval.DEFAULT_PATTERNS, False))

    def test_no_path_means_no_decision(self):
        self.assertIsNone(protect_eval.decide({"cwd": self.root, "tool_input": {}}, project_root=self.root))


class Process(unittest.TestCase):
    """Run the real script, the way the harness does."""

    def run_script(self, stdin_text, env_extra=None):
        env = dict(os.environ, **(env_extra or {}))
        return subprocess.run([sys.executable, SCRIPT], input=stdin_text, capture_output=True,
                              text=True, env=env, timeout=30)

    def test_protected_path_prints_ask(self):
        with tempfile.TemporaryDirectory() as root:
            payload = {"tool_name": "Write", "cwd": root,
                       "tool_input": {"file_path": os.path.join(root, "graders.py")}}
            r = self.run_script(json.dumps(payload), {"CLAUDE_PROJECT_DIR": root})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_unprotected_path_is_silent(self):
        with tempfile.TemporaryDirectory() as root:
            payload = {"tool_name": "Edit", "cwd": root, "tool_input": {"file_path": os.path.join(root, "a.py")}}
            r = self.run_script(json.dumps(payload), {"CLAUDE_PROJECT_DIR": root})
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_malformed_stdin_fails_open(self):
        r = self.run_script("this is {not json")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertIn("protect_eval", r.stderr)

    def test_empty_stdin_fails_open(self):
        r = self.run_script("")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_unreadable_config_fails_open(self):
        with tempfile.TemporaryDirectory() as root:
            os.mkdir(os.path.join(root, ".eval-protected"))  # a directory, so open() fails
            payload = {"cwd": root, "tool_input": {"file_path": os.path.join(root, "a.py")}}
            r = self.run_script(json.dumps(payload), {"CLAUDE_PROJECT_DIR": root})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()

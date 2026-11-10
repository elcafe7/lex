"""Tests for scripts/gitleaks_gate.py and scripts/gitleaks_check.sh.

Standard library only; run: python3 -m unittest tests.test_gitleaks_gate
The end-to-end gitleaks_check.sh scan tests run only when `gitleaks` is on PATH.
Argument and log-opts validation always runs.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "gitleaks_gate.py"
CHECK = ROOT / "scripts" / "gitleaks_check.sh"


def finding(rule="generic-api-key", path="scripts/example.py", line=12,
            commit="0123456789abcdef0123456789abcdef01234567",
            secret="A*********************************",
            description="Generic API Key"):
    return {
        "RuleID": rule,
        "Description": description,
        "File": path,
        "StartLine": line,
        "Commit": commit,
        "Fingerprint": f"{commit}:{path}:{rule}:{line}",
        "Match": secret,
        "Secret": secret,
        "Author": "someone",
        "Email": "someone@example.com",
        "Message": "oops, here is the key",
    }


def run_gate(data, *extra, raw=None):
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "gitleaks.json").write_text(
            raw if raw is not None else json.dumps(data), encoding="utf-8")
        env = dict(os.environ, GITHUB_WORKSPACE=str(ws))
        proc = subprocess.run(
            [sys.executable, str(GATE), "gitleaks.json", "gitleaks.md",
             "--summary-json", "gate.json", "--tool-version", "8.30.1", *extra],
            capture_output=True, text=True, check=False, cwd=str(ws), env=env)
        md = (ws / "gitleaks.md").read_text(encoding="utf-8") if (ws / "gitleaks.md").exists() else ""
        summary = json.loads((ws / "gate.json").read_text()) if (ws / "gate.json").exists() else None
        return proc, md, summary


class GitleaksGateTests(unittest.TestCase):
    def test_clean_passes(self):
        proc, md, summary = run_gate([])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("**Result: PASS.** Gitleaks 8.30.1: 0 findings.", md)
        self.assertNotIn("Suggested fix", md)
        self.assertNotIn("Secret", md)
        self.assertEqual(summary["result"], "pass")
        self.assertEqual(summary["findings"], 0)
        self.assertTrue(summary["complete"])

    def test_finding_fails_and_omits_secret_values(self):
        secret = "AKIAIOSFODNN7EXAMPLE_not_a_real_key"
        proc, md, summary = run_gate([finding(secret=secret)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("**Result: FAIL.**", md)
        self.assertIn("| generic-api-key: Generic API Key |", md)
        self.assertIn("`scripts/example.py:12`", md)
        self.assertIn("`0123456789abcdef0123456789abcdef01234567`", md)
        self.assertIn("## Suggested fix", md)
        self.assertIn("### Fix prompt", md)
        self.assertIn("::error file=scripts/example.py,line=12,title=Gitleaks generic-api-key::", proc.stdout)
        self.assertNotIn(secret, md)
        self.assertNotIn(secret, proc.stdout)
        self.assertNotIn("AKIA", md)
        self.assertNotIn("someone@example.com", md)
        self.assertNotIn("oops, here is the key", md)
        self.assertEqual(summary["result"], "fail")
        self.assertEqual(summary["findings"], 1)

    def test_markdown_injection_and_bad_rule_are_sanitized(self):
        proc, md, _ = run_gate([finding(
            rule="<script>", path="foo|bar`.py", line=-3,
            commit="not-a-sha",
            description="x | `rm` <img>",
        )])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("| unknown-rule: x / 'rm' (img) |", md)
        self.assertIn("`foo_bar_.py:0`", md)
        self.assertIn("`?`", md)
        self.assertNotIn("<script>", md)
        self.assertNotIn("<img>", md)

    def test_broken_json_fails(self):
        proc, md, summary = run_gate(None, raw="{not json")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("The scan did not complete", md)
        self.assertEqual(summary["result"], "fail")
        self.assertFalse(summary["complete"])

    def test_non_list_json_fails(self):
        proc, md, summary = run_gate({"findings": []})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("expected a list of findings", md)
        self.assertEqual(summary["result"], "fail")

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            env = dict(os.environ, GITHUB_WORKSPACE=str(ws))
            proc = subprocess.run(
                [sys.executable, str(GATE), "missing.json", "gitleaks.md",
                 "--summary-json", "gate.json"],
                capture_output=True, text=True, check=False, cwd=str(ws), env=env)
            self.assertEqual(proc.returncode, 1)
            md = (ws / "gitleaks.md").read_text(encoding="utf-8")
            self.assertIn("could not be read", md)

    def test_path_outside_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            outside = Path(tmp) / "outside.json"
            ws.mkdir()
            outside.write_text("[]")
            env = dict(os.environ, GITHUB_WORKSPACE=str(ws))
            proc = subprocess.run(
                [sys.executable, str(GATE), str(outside), "gitleaks.md"],
                capture_output=True, text=True, check=False, cwd=str(ws), env=env)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("::error title=Gitleaks gate::", proc.stderr)
            self.assertFalse((ws / "gitleaks.md").exists())


class GitleaksCheckScriptTests(unittest.TestCase):
    def _run(self, *args, env=None, cwd=None):
        run_env = dict(os.environ)
        if env:
            run_env.update(env)
        return subprocess.run(
            ["bash", str(CHECK), *args],
            capture_output=True, text=True, check=False,
            cwd=str(cwd or ROOT), env=run_env)

    def test_usage_and_bad_out_dir(self):
        proc = self._run()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage:", proc.stderr)
        proc = self._run("-secret")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("invalid out-dir", proc.stderr)

    def test_rejects_unsafe_log_opts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for opts in ("--all;id", "-pwn", "HEAD;rm -rf /", "--since=1970", "abc..def"):
                proc = self._run("out", env={"GITLEAKS_LOG_OPTS": opts}, cwd=tmp)
                self.assertEqual(proc.returncode, 2, opts)
                self.assertIn("invalid GITLEAKS_LOG_OPTS", proc.stderr)

    @unittest.skipUnless(shutil.which("gitleaks"), "gitleaks is not on PATH")
    def test_check_script_scans_this_repo_clean(self):
        # Out-dir must resolve under the workspace (scripts/gitleaks_gate.py
        # uses the same safe_path rules as osv_gate.py).
        with tempfile.TemporaryDirectory(dir=str(ROOT), prefix=".gitleaks-test-") as tmp:
            out = Path(tmp) / "gitleaks-report"
            proc = self._run(str(out), env={"GITLEAKS_LOG_OPTS": "--all", "TAG": "v0.0.0",
                                            "REPO": "elcafe7/lex"})
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads((out / "gitleaks.json").read_text())
            self.assertEqual(data, [])
            md = (out / "gitleaks.md").read_text()
            self.assertIn("**Result: PASS.**", md)
            summary = json.loads((out / "gitleaks-gate.json").read_text())
            self.assertEqual(summary["result"], "pass")
            self.assertEqual(summary["findings"], 0)


if __name__ == "__main__":
    unittest.main()

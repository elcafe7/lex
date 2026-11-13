"""Tests for scripts/bandit_gate.py and scripts/bandit_check.sh.

Standard library only; run: python3 -m unittest tests.test_bandit_gate
The end-to-end bandit_check.sh tests run only when `bandit` is on PATH.
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
GATE = ROOT / "scripts" / "bandit_gate.py"
CHECK = ROOT / "scripts" / "bandit_check.sh"


def finding(test_id="B608", severity="MEDIUM", confidence="LOW", filename="./lex.py", line=10,
            text="Possible SQL injection vector through string-based query construction.",
            code="10 query = f'SELECT * FROM t WHERE x = {secret_value}'\n"):
    return {
        "test_id": test_id, "test_name": "hardcoded_sql_expressions",
        "issue_severity": severity, "issue_confidence": confidence,
        "filename": filename, "line_number": line, "issue_text": text, "code": code,
        "more_info": f"https://bandit.readthedocs.io/en/1.9.4/plugins/{test_id.lower()}.html",
    }


def report(results=(), errors=(), skipped=0):
    return {"errors": list(errors), "generated_at": "2026-11-09T22:00:00Z",
            "metrics": {"_totals": {"skipped_tests": skipped, "nosec": 0}},
            "results": list(results)}


def run_gate(data, *extra, raw=None):
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        (ws / "bandit.json").write_text(raw if raw is not None else json.dumps(data), encoding="utf-8")
        env = dict(os.environ, GITHUB_WORKSPACE=str(ws))
        proc = subprocess.run(
            [sys.executable, str(GATE), "bandit.json", "bandit.md", "--summary-json", "gate.json",
             "--tool-version", "1.9.4", *extra],
            capture_output=True, text=True, check=False, cwd=str(ws), env=env)
        md = (ws / "bandit.md").read_text(encoding="utf-8") if (ws / "bandit.md").exists() else ""
        summary = json.loads((ws / "gate.json").read_text()) if (ws / "gate.json").exists() else None
        return proc, md, summary


class BanditGateTests(unittest.TestCase):
    def test_clean_passes_and_counts_low_as_info(self):
        proc, md, summary = run_gate(report(
            [finding("B404", "LOW", "HIGH"), finding("B603", "LOW", "HIGH"), finding("B603", "LOW", "HIGH")],
            skipped=7))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("**Result: PASS.** Bandit 1.9.4: 0 findings of medium or high severity", md)
        self.assertIn("| B603 | 2 |", md)
        self.assertIn("Inline `# nosec` suppressions in the code: 7.", md)
        self.assertNotIn("Suggested fix", md)
        self.assertEqual(summary["result"], "pass")
        self.assertEqual((summary["medium_high"], summary["low"], summary["nosec"]), (0, 3, 7))

    def test_medium_low_confidence_fails(self):
        # Block on anything: a medium finding fails even at LOW confidence.
        proc, md, summary = run_gate(report([finding()]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("**Result: FAIL.**", md)
        self.assertIn("| MEDIUM | LOW | [B608]", md)
        self.assertIn("`lex.py:10`", md)
        self.assertIn("## Suggested fix", md)
        self.assertIn("### Fix prompt", md)
        self.assertIn("::error file=lex.py,line=10,title=Bandit B608::", proc.stdout)
        self.assertEqual(summary["result"], "fail")

    def test_high_fails(self):
        proc, md, _ = run_gate(report([finding("B602", "HIGH", "HIGH", text="shell=True")]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("| HIGH | HIGH |", md)

    def test_report_never_contains_source_lines(self):
        proc, md, _ = run_gate(report([finding()]))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("secret_value", md)
        self.assertNotIn("secret_value", proc.stdout)

    def test_untrusted_text_is_neutralised(self):
        evil = finding(filename="./x|`$(id)`<script>.py", line="9; rm",
                       text="bad | text `$(id)` <img src=x>\n::error::forged\r")
        evil["more_info"] = "javascript:alert(1)"
        evil["test_id"] = "B608<script>"
        proc, md, _ = run_gate(report([evil]))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("<script>", md)
        self.assertNotIn("<img", md)
        self.assertNotIn("javascript:", md)
        self.assertNotIn("$(id)`", md)
        self.assertIn("B???", md)
        self.assertIn("`x____id___script_.py:0`", md)
        # Exactly one ::error command per finding; injected text cannot start another.
        self.assertEqual(sum(1 for line in proc.stdout.splitlines() if line.startswith("::error")), 1)

    def test_scan_errors_fail(self):
        proc, md, summary = run_gate(report(errors=[{"filename": "./broken.py", "reason": "syntax error"}]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("1 file(s) Bandit could not scan", md)
        self.assertIn("`broken.py`: syntax error", md)
        self.assertFalse(summary["complete"])

    def test_missing_or_malformed_json_fails(self):
        for raw in ("", "{not json", json.dumps({"results": []}), json.dumps([1, 2])):
            with self.subTest(raw=raw[:20]):
                proc, md, summary = run_gate(None, raw=raw)
                self.assertEqual(proc.returncode, 1)
                self.assertIn("The scan did not complete, so it is not clean.", md)
                self.assertEqual(summary["result"], "fail")

    def test_paths_outside_workspace_rejected(self):
        for args in (["../x.json", "r.md"], ["bandit.json", "/etc/passwd"], ["bandit.json", "r.md\0"]):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as tmp:
                ws = Path(tmp)
                (ws / "bandit.json").write_text(json.dumps(report()))
                env = dict(os.environ, GITHUB_WORKSPACE=str(ws))
                try:
                    proc = subprocess.run([sys.executable, str(GATE), *args], capture_output=True,
                                          text=True, check=False, cwd=str(ws), env=env)
                except ValueError:  # NUL in argv is refused before the gate runs
                    continue
                self.assertEqual(proc.returncode, 2)
                self.assertFalse((ws / "r.md").exists())


@unittest.skipUnless(shutil.which("bandit"), "bandit not on PATH")
class BanditCheckScriptTests(unittest.TestCase):
    def run_check(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "scripts").mkdir()
            shutil.copy(GATE, ws / "scripts" / "bandit_gate.py")
            shutil.copy(ROOT / "scripts" / "osv_gate.py", ws / "scripts" / "osv_gate.py")
            for name, body in files.items():
                (ws / name).write_text(body)
            env = dict(os.environ, GITHUB_WORKSPACE=str(ws), TAG="v1.2.3", REPO="o/r")
            proc = subprocess.run(["bash", str(CHECK), "bandit-report"], capture_output=True, text=True,
                                  check=False, cwd=str(ws), env=env)
            out = ws / "bandit-report"
            names = sorted(p.name for p in out.iterdir()) if out.exists() else []
            md = (out / "bandit.md").read_text() if (out / "bandit.md").exists() else ""
            return proc, names, md

    def test_clean_tree_passes_with_all_reports(self):
        proc, names, md = self.run_check({"ok.py": "import json\nprint(json.dumps({}))\n"})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(names, ["bandit-gate.json", "bandit.json", "bandit.md", "bandit.txt"])
        self.assertIn("PASS", md)

    def test_medium_finding_blocks(self):
        proc, names, md = self.run_check({"bad.py": "import urllib.request\n\ndef f(u):\n    return urllib.request.urlopen(u)\n"})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("B310", md)
        self.assertIn("bandit.txt", names)

    def test_bad_out_dir_rejected(self):
        proc, _, _ = self.run_check({})
        bad = subprocess.run(["bash", str(CHECK), "-x;id"], capture_output=True, text=True, check=False)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("invalid out-dir", bad.stderr)


if __name__ == "__main__":
    unittest.main()

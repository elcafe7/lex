"""Tests for scripts/osv_gate.py (stdlib unittest; run: python3 -m unittest tests.test_osv_gate)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "osv_gate.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run_gate(fixture, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.md"
        badge = Path(tmp) / "verification.json"
        proc = subprocess.run(
            [sys.executable, str(GATE), str(FIXTURES / fixture), str(report),
             "--badge-json", str(badge), *extra],
            capture_output=True, text=True, check=False,
        )
        data = json.loads(badge.read_text(encoding="utf-8")) if badge.exists() else None
        return proc, report.read_text(encoding="utf-8"), data


def warnings(proc):
    return [l for l in proc.stdout.splitlines() if l.startswith("::warning ")]


class OsvGateTests(unittest.TestCase):
    def test_clean_passes_and_writes_badge(self):
        proc, md, badge = run_gate(
            "osv_clean.json", "--report-url", "https://example.test/r.md",
            "--tool-version", "2.7.0", "--release", "v9.9.9", "--repository", "o/r")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("- Result: PASS", md)
        self.assertNotIn("## Suggested fix", md)
        self.assertEqual(warnings(proc), [])
        self.assertEqual(badge["tool"], "OSV-Scanner")
        self.assertEqual(badge["result"], "pass")
        self.assertEqual(badge["known_vulnerabilities"], 0)
        self.assertEqual(badge["report_url"], "https://example.test/r.md")
        self.assertEqual(badge["release"], "v9.9.9")
        self.assertRegex(badge["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(badge["stale_after_days"], 30)

    def test_critical_blocks_no_badge_and_suggests_fix(self):
        proc, md, badge = run_gate("osv_mixed.json")
        self.assertEqual(proc.returncode, 1)
        self.assertIsNone(badge)
        self.assertIn("- Findings: 4 total, 1 blocking, 1 below threshold", md)
        self.assertIn("- Unscored: 2", md)
        self.assertIn("- Result: FAIL", md)
        self.assertIn("## Suggested fix", md)
        self.assertIn("upgrade to at least 10.3.0", md)
        self.assertIn("### Fix prompt", md)
        w = warnings(proc)
        self.assertEqual(len(w), 2)
        self.assertTrue(any("PYSEC-test-noscore" in x for x in w))
        self.assertTrue(any("OSV-test-null%25" in x for x in w))  # '%' escaped

    def test_low_severity_still_holds_release(self):
        proc, md, badge = run_gate("osv_low_and_unscored.json")
        self.assertEqual(proc.returncode, 1)
        self.assertIsNone(badge)
        self.assertIn("- Findings: 2 total, 0 blocking, 1 below threshold", md)
        self.assertEqual(len(warnings(proc)), 1)

    def test_unscored_alone_warns_but_passes(self):
        proc, md, badge = run_gate("osv_unscored_only.json")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("- Result: PASS", md)
        self.assertIn("- Unscored: 1", md)
        self.assertIn("unscored: review", md)
        w = warnings(proc)
        self.assertEqual(len(w), 1)
        self.assertIn("examplepkg 1.0.0", w[0])
        self.assertEqual(badge["known_vulnerabilities"], 0)
        self.assertEqual(badge["unscored"], 1)

    def test_stale_badge_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            badge = Path(tmp) / "verification.json"
            badge.write_text("{}", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(GATE), str(FIXTURES / "osv_mixed.json"), str(Path(tmp) / "r.md"),
                 "--badge-json", str(badge)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(badge.exists())


if __name__ == "__main__":
    unittest.main()

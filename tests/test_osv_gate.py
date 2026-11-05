"""Tests for scripts/osv_gate.py (stdlib unittest; run: python3 -m unittest tests.test_osv_gate)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "osv_gate.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run_gate(fixture):
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.md"
        proc = subprocess.run(
            [sys.executable, str(GATE), str(FIXTURES / fixture), str(report)],
            capture_output=True, text=True, check=False,
        )
        return proc, report.read_text(encoding="utf-8")


class OsvGateTests(unittest.TestCase):
    def test_clean_passes(self):
        proc, md = run_gate("osv_clean.json")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("- Result: PASS", md)
        self.assertIn("- Unscored: 0", md)
        self.assertNotIn("::warning", proc.stdout)

    def test_critical_blocks_and_unscored_warns(self):
        proc, md = run_gate("osv_mixed.json")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("- Findings: 4 total, 1 blocking", md)
        self.assertIn("- Unscored: 2", md)
        self.assertIn("- Result: FAIL", md)
        warnings = [l for l in proc.stdout.splitlines() if l.startswith("::warning ")]
        self.assertEqual(len(warnings), 2)
        self.assertTrue(any("PYSEC-test-noscore" in w for w in warnings))
        # '%' must be escaped in workflow commands
        self.assertTrue(any("OSV-test-null%25" in w for w in warnings))

    def test_unscored_alone_does_not_block(self):
        proc, md = run_gate("osv_unscored_only.json")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("- Findings: 2 total, 0 blocking", md)
        self.assertIn("- Unscored: 1", md)
        self.assertIn("- Result: PASS", md)
        warnings = [l for l in proc.stdout.splitlines() if l.startswith("::warning ")]
        self.assertEqual(len(warnings), 1)
        self.assertIn("examplepkg 1.0.0", warnings[0])


if __name__ == "__main__":
    unittest.main()

"""Tests for scripts/osv_gate.py (stdlib unittest; run: python3 -m unittest tests.test_osv_gate)."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "osv_gate.py"
FIXTURES = ROOT / "tests" / "fixtures"


def gate_env(workspace):
    env = dict(os.environ)
    env["GITHUB_WORKSPACE"] = str(workspace)
    return env


def run_in(workspace, *args):
    """Run the gate with GITHUB_WORKSPACE (and cwd) set to workspace."""
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True, text=True, check=False,
        cwd=str(workspace), env=gate_env(workspace),
    )


def run_gate(fixture, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        shutil.copy(FIXTURES / fixture, ws / fixture)
        report = ws / "report.md"
        badge = ws / "verification.json"
        proc = run_in(ws, fixture, "report.md", "--badge-json", "verification.json", *extra)
        data = json.loads(badge.read_text(encoding="utf-8")) if badge.exists() else None
        return proc, report.read_text(encoding="utf-8"), data


def load_gate_module():
    spec = importlib.util.spec_from_file_location("osv_gate", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        self.assertIn("upgrade to 10.3.0 or later", md)
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
            ws = Path(tmp)
            shutil.copy(FIXTURES / "osv_mixed.json", ws / "osv_mixed.json")
            badge = ws / "verification.json"
            badge.write_text("{}", encoding="utf-8")
            proc = run_in(ws, "osv_mixed.json", "r.md", "--badge-json", "verification.json")
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(badge.exists())

    def test_absolute_paths_inside_workspace_are_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "dist").mkdir()
            shutil.copy(FIXTURES / "osv_clean.json", ws / "dist" / "scan.json")
            proc = run_in(ws, str(ws / "dist" / "scan.json"), str(ws / "dist" / "scan.md"),
                          "--badge-json", str(ws / "dist" / "verification.json"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((ws / "dist" / "scan.md").is_file())
            self.assertTrue((ws / "dist" / "verification.json").is_file())


class OsvGatePathTests(unittest.TestCase):
    """Every path must resolve under GITHUB_WORKSPACE (or cwd); exit 2 otherwise."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ws = root / "ws"
        self.outside = root / "outside"
        self.ws.mkdir()
        self.outside.mkdir()
        shutil.copy(FIXTURES / "osv_clean.json", self.ws / "scan.json")
        shutil.copy(FIXTURES / "osv_clean.json", self.outside / "scan.json")
        (self.ws / "escape").symlink_to(self.outside, target_is_directory=True)
        (self.ws / "escape.json").symlink_to(self.outside / "scan.json")
        (self.ws / "inside-link.json").symlink_to(self.ws / "scan.json")

    def tearDown(self):
        self._tmp.cleanup()

    def assert_rejected(self, *args):
        before = sorted(p.name for p in self.outside.iterdir())
        proc = run_in(self.ws, *args)
        self.assertEqual(proc.returncode, 2, (args, proc.stdout, proc.stderr))
        self.assertIn("resolves outside", proc.stderr)
        self.assertIn("::error title=osv_gate::", proc.stdout)
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()), before,
                         "nothing may be written outside the workspace")
        self.assertFalse((self.ws / "r.md").exists(), "nothing written when any path is bad")

    def test_dotdot_escape_input(self):
        self.assert_rejected("../outside/scan.json", "r.md")

    def test_dotdot_escape_output(self):
        self.assert_rejected("scan.json", "../outside/r.md")

    def test_dotdot_escape_badge(self):
        self.assert_rejected("scan.json", "r.md", "--badge-json", "dist/../../outside/v.json")

    def test_absolute_path_outside(self):
        self.assert_rejected(str(self.outside / "scan.json"), "r.md")
        self.assert_rejected("scan.json", "r.md", "--badge-json", os.path.join(tempfile.gettempdir(), "verification.json"))
        self.assert_rejected("/etc/passwd", "r.md")

    def test_symlink_escape(self):
        self.assert_rejected("escape.json", "r.md")
        self.assert_rejected("scan.json", "escape/r.md")
        self.assert_rejected("scan.json", "r.md", "--badge-json", "escape/verification.json")

    def test_workspace_root_itself_rejected(self):
        self.assert_rejected(".", "r.md")

    def test_symlink_inside_and_dotdot_staying_inside_allowed(self):
        (self.ws / "dist").mkdir()
        proc = run_in(self.ws, "inside-link.json", "dist/../r.md", "--badge-json", "dist/v.json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.ws / "r.md").is_file())
        self.assertTrue((self.ws / "dist" / "v.json").is_file())

    def test_cwd_is_base_without_github_workspace(self):
        env = dict(os.environ)
        env.pop("GITHUB_WORKSPACE", None)
        proc = subprocess.run([sys.executable, str(GATE), "../outside/scan.json", "r.md"],
                              capture_output=True, text=True, check=False, cwd=str(self.ws), env=env)
        self.assertEqual(proc.returncode, 2)
        proc = subprocess.run([sys.executable, str(GATE), "scan.json", "r.md"],
                              capture_output=True, text=True, check=False, cwd=str(self.ws), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_safe_path_helper_rejects_nul_and_empty(self):
        mod = load_gate_module()
        old = os.environ.get("GITHUB_WORKSPACE")
        os.environ["GITHUB_WORKSPACE"] = str(self.ws)
        try:
            for bad in ("scan\0.json", "", None, "../x", "/etc/passwd", "escape/x"):
                with self.subTest(bad=bad):
                    with self.assertRaises(mod.UnsafePathError):
                        mod.safe_path(bad, "test")
            self.assertEqual(mod.safe_path("scan.json", "test"),
                             os.path.realpath(self.ws / "scan.json"))
        finally:
            if old is None:
                os.environ.pop("GITHUB_WORKSPACE", None)
            else:
                os.environ["GITHUB_WORKSPACE"] = old


if __name__ == "__main__":
    unittest.main()

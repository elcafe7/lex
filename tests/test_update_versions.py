"""`lex update` keeps the CLI current, not only the data (#19).

Covers the Python side: the version summary printed after an update, for the
npm launcher outcomes (current / updated / failed / unchecked) and for a
standalone install (git clone or direct `python3 lex.py`) whose code is behind
the data manifest. Network access is stubbed; nothing outside a temp dir is
written.

Run: python3 -m unittest discover -s tests
"""
import hashlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from rich.console import Console

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_update_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


LEXMOD = load_lex_module()


def sha(data):
    return hashlib.sha256(data).hexdigest()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class UpdateSummaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lex-update-test-")
        self.data_dir = os.path.join(self.tmp, "runtime-data")
        os.makedirs(self.data_dir)
        self.old_bytes = b"old lexicon"
        self.new_bytes = b"new lexicon 2.6.6"
        with open(os.path.join(self.data_dir, "lexicon.db"), "wb") as fh:
            fh.write(self.old_bytes)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def console(self):
        return Console(record=True, width=120, theme=LEXMOD.custom_theme, file=io.StringIO())

    def manager(self, console, payload):
        manifest = {
            "version": "2.6.6",
            "assets": {"runtime-data/lexicon.db": {"hash": sha(payload), "size": len(payload)}},
        }
        mgr = LEXMOD.LexUpdateManager(console, data_dir=self.data_dir)
        mgr.fetch_remote_manifest = lambda: manifest
        return mgr

    def run_update(self, env, payload=None, base_dir=None):
        payload = self.new_bytes if payload is None else payload
        console = self.console()
        mgr = self.manager(console, payload)
        with mock.patch.object(LEXMOD, "open_trusted_https", lambda url, **kw: FakeResponse(payload)):
            ok = mgr.perform_update()
        code = LEXMOD.print_update_summary(console, mgr, ok, env=env, base_dir=base_dir or self.tmp)
        return code, ANSI.sub("", console.export_text())

    def test_data_update_still_downloads_and_reports_data_version(self):
        code, out = self.run_update({"LEX_CLI_PACKAGE_VERSION": "2.6.6", "LEX_CLI_UPDATE_STATUS": "current",
                                     "LEX_CLI_LATEST_VERSION": "2.6.6"})
        self.assertEqual(code, 0)
        with open(os.path.join(self.data_dir, "lexicon.db"), "rb") as fh:
            self.assertEqual(fh.read(), self.new_bytes)
        self.assertIn("Lex data updated to 2.6.6.", out)
        self.assertIn("Lex CLI:  2.6.6 (latest)", out)
        self.assertIn("Lex data: 2.6.6 (updated)", out)
        self.assertNotIn("Successfully updated Lex", out)

    def test_cli_current_and_data_current_is_a_noop(self):
        code, out = self.run_update({"LEX_CLI_PACKAGE_VERSION": "2.6.6", "LEX_CLI_UPDATE_STATUS": "current",
                                     "LEX_CLI_LATEST_VERSION": "2.6.6"}, payload=self.old_bytes)
        self.assertEqual(code, 0)
        self.assertIn("Lex data is already up to date (2.6.6).", out)
        self.assertIn("Lex CLI:  2.6.6 (latest)", out)
        self.assertIn("Lex data: 2.6.6 (up to date)", out)

    def test_cli_updated_reports_new_and_old_versions(self):
        code, out = self.run_update({"LEX_CLI_PACKAGE_VERSION": "2.6.6", "LEX_CLI_UPDATE_STATUS": "updated",
                                     "LEX_CLI_LATEST_VERSION": "2.6.6", "LEX_CLI_UPDATED_FROM": "2.6.2"})
        self.assertEqual(code, 0)
        self.assertIn("Lex CLI:  2.6.6 (updated from 2.6.2)", out)
        self.assertIn("Lex data: 2.6.6 (updated)", out)

    def test_cli_upgrade_failed_prints_command_and_exits_nonzero(self):
        cmd = "npm install -g --prefix /home/nate/.local @n8te_/lex-cli@latest"
        code, out = self.run_update({"LEX_CLI_PACKAGE_VERSION": "2.6.2", "LEX_CLI_UPDATE_STATUS": "failed",
                                     "LEX_CLI_LATEST_VERSION": "2.6.6", "LEX_CLI_UPGRADE_COMMAND": cmd})
        self.assertEqual(code, 1)
        self.assertIn("Lex CLI:  2.6.2 (behind the latest 2.6.6; NOT updated)", out)
        self.assertIn(cmd, out)
        self.assertIn("Lex data: 2.6.6 (updated)", out)
        self.assertNotIn("(latest)", out)

    def test_cli_unchecked_offline_prints_command(self):
        code, out = self.run_update({"LEX_CLI_PACKAGE_VERSION": "2.6.2", "LEX_CLI_UPDATE_STATUS": "unchecked",
                                     "LEX_CLI_UPGRADE_COMMAND": "npm install -g @n8te_/lex-cli@latest"})
        self.assertEqual(code, 0)
        self.assertIn("couldn't check for a newer version", out)
        self.assertIn("npm install -g @n8te_/lex-cli@latest", out)

    def test_standalone_git_clone_behind_prints_git_command(self):
        os.makedirs(os.path.join(self.tmp, ".git"))
        with mock.patch.object(LEXMOD, "VERSION", "2.6.2"):
            code, out = self.run_update({}, base_dir=self.tmp)
        self.assertEqual(code, 0)
        self.assertIn("Lex CLI:  2.6.2 (behind the latest 2.6.6; NOT updated)", out)
        self.assertIn(f"git -C {self.tmp} pull --ff-only", out)
        self.assertIn("Lex data: 2.6.6 (updated)", out)

    def test_standalone_current(self):
        with mock.patch.object(LEXMOD, "VERSION", "2.6.6"):
            code, out = self.run_update({}, base_dir=self.tmp)
        self.assertEqual(code, 0)
        self.assertIn("Lex CLI:  2.6.6 (latest)", out)

    def test_failed_data_update_exits_nonzero(self):
        console = self.console()
        mgr = self.manager(console, self.new_bytes)
        with mock.patch.object(LEXMOD, "open_trusted_https", lambda url, **kw: FakeResponse(b"corrupt")):
            ok = mgr.perform_update()
        self.assertFalse(ok)
        code = LEXMOD.print_update_summary(console, mgr, ok, env={"LEX_CLI_UPDATE_STATUS": "current",
                                                                  "LEX_CLI_PACKAGE_VERSION": "2.6.6"})
        self.assertEqual(code, 1)
        self.assertIn("Lex data: update did not complete", ANSI.sub("", console.export_text()))


class VersionFlagTest(unittest.TestCase):
    """`--version` is the CLI version; single-dash `-v` is still the Bible explainer."""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-version-test-")
        self.env = {**os.environ, "HOME": self.home, "LEX_NO_COLOR": "1"}

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_lex(self, *argv):
        return subprocess.run([sys.executable, LEX, *argv], env=self.env, capture_output=True, text=True, timeout=60)

    def test_double_dash_version_prints_cli_version(self):
        # `-version` is the one-dash form of `--version`. `--v` is the
        # two-dash form of `-v` (default Bible), not an abbreviation of
        # `--version`.
        for flag in ("--version", "-version"):
            result = self.run_lex(flag)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), LEXMOD.VERSION)

    def test_single_dash_v_is_still_the_bible_explainer(self):
        for flag in ("-v", "--v"):
            result = self.run_lex(flag)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("lex -v: Set Default Bible", ANSI.sub("", result.stdout))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".lex_config.json")))


if __name__ == "__main__":
    unittest.main()

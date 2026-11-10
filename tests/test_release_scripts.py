"""Reject malicious release tags before they reach gh (shell-injection guard)."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED = ROOT / "scripts" / "release_blocked_issue.sh"
UNBLOCKED = ROOT / "scripts" / "release_unblocked.sh"

# Crafted tags that would break out of --search "in:title \"...\"" quoting.
MALICIOUS_TAGS = (
    'v1"$(id)',
    'v1";id;#',
    "v1`id`",
    "v1; rm -rf /",
    "v1 with space",
    "v1\n2",
    "v1$(uname)",
    "",
)

VALID_TAG = "v1.2.3"

# Private HOME for the scripts instead of the shared /tmp (bandit B108).
_SCRIPT_HOME_DIR = tempfile.TemporaryDirectory(prefix="lex-release-scripts-home-")
SCRIPT_HOME = _SCRIPT_HOME_DIR.name


def tearDownModule():
    _SCRIPT_HOME_DIR.cleanup()


def run_script(script, *args):
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": SCRIPT_HOME,
            # Force failure if validation is skipped and gh is reached.
            "GH_TOKEN": "test-token-should-not-be-used",
            "GH_REPO": "elcafe7/test",
            "RUN_URL": "https://example.test/run",
            "FAILED_JOBS": "build-scan: failure",
        },
    )


class ReleaseScriptTagTests(unittest.TestCase):
    def test_blocked_rejects_malicious_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            for tag in MALICIOUS_TAGS:
                with self.subTest(tag=tag):
                    proc = run_script(BLOCKED, tag, tmp)
                    self.assertNotEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn("invalid tag", proc.stderr)
                    self.assertIn("must match", proc.stderr)
                    # Must fail before calling gh (no network / auth noise required).
                    self.assertNotIn("graphql", proc.stderr.lower())

    def test_unblocked_rejects_malicious_tags(self):
        for tag in MALICIOUS_TAGS:
            with self.subTest(tag=tag):
                proc = run_script(UNBLOCKED, tag)
                self.assertNotEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("invalid tag", proc.stderr)
                self.assertIn("must match", proc.stderr)

    def test_blocked_rejects_missing_reports_dir_after_valid_tag(self):
        # Valid tag must pass the allowlist, then fail on a missing reports dir
        # (still before any gh call that would open/update an issue).
        with tempfile.TemporaryDirectory() as t:
            proc = run_script(BLOCKED, VALID_TAG, str(Path(t) / "does-not-exist-release-verify"))
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("reports directory", proc.stderr)


if __name__ == "__main__":
    unittest.main()

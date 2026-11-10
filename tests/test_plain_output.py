"""Tests for `lex --plain`: plain text, no ANSI or Rich borders, no prompts."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
BOX = re.compile(r"[\u2500-\u257f]")


class PlainCliTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-plain-test-")
        self.config = os.path.join(self.home, ".lex_config.json")
        with open(self.config, "w", encoding="utf-8") as fh:
            fh.write('{"bible": "esv"}')

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env.update({"HOME": self.home, "COLUMNS": "100", "TERM": "xterm-256color"})
        return env

    def run_plain(self, *argv, stdin_text="1\nq\n"):
        proc = subprocess.run([sys.executable, LEX, *argv], cwd=ROOT, env=self.env(), input=stdin_text,
                              capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout, proc.stderr

    def assert_plain(self, out):
        self.assertNotIn("\x1b[", out)
        self.assertIsNone(BOX.search(out), out[:500])
        self.assertNotIn("Select", out)

    def test_read(self):
        code, out, _ = self.run_plain("--plain", "John", "3:16")
        self.assertEqual(code, 0)
        self.assert_plain(out)
        self.assertIn("For God so loved the world", out)

    def test_study_and_strongs(self):
        for argv in (("study", "John", "1:1"), ("strongs", "G5594"), ("search", "grace", "--limit", "3"), ("creed",)):
            code, out, err = self.run_plain("--plain", *argv)
            self.assertEqual(code, 0, err)
            self.assert_plain(out)
        self.assertIn("from G4154, which", self.run_plain("strongs", "G5594", "--plain")[1])

    def test_b_is_one_command_only(self):
        code, out, _ = self.run_plain("--plain", "-B", "kjv", "John", "3:16")
        self.assertIn("only begotten Son", out)
        with open(self.config, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), '{"bible": "esv"}')

    def test_json_wins_over_plain(self):
        code, out, _ = self.run_plain("--plain", "--json", "John", "3:16")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith('{"schema_version":1'))

    def test_pty_never_prompts(self):
        if not shutil.which("script") or sys.platform != "linux":
            self.skipTest("needs util-linux script")
        cmd = f"{sys.executable} {LEX} --plain creed"
        proc = subprocess.run(["script", "-qec", cmd, "/dev/null"], cwd=ROOT, env=self.env(),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("Select ID", proc.stdout)
        self.assertNotIn("\x1b[", proc.stdout)
        self.assertIn("Apostles", proc.stdout)


if __name__ == "__main__":
    unittest.main()

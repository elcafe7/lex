"""Regression tests for issue #1: the `lex` name clash with the flex lexer.

Most systems already have /usr/bin/lex (flex). scripts/check_lex_command.sh,
which setup.sh runs after installing the wrapper, must say which `lex` wins
and how to fix PATH order when flex comes first. These tests use fake PATH
folders, so nothing on the real system is touched.

Run: python3 -m unittest discover -s tests
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "scripts", "check_lex_command.sh")
SETUP = os.path.join(ROOT, "setup.sh")
SYSTEM_PATH = "/usr/bin:/bin"
BASH = shutil.which("bash") or "/bin/bash"

FAKE_FLEX = """#!/bin/sh
# Stand-in for GNU flex: invoked as lex it prints "lex 2.6.4".
echo "$(basename "$0") 2.6.4"
"""


def write_exe(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class LexCommandCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lex-test-cmd-")
        self.sys_bin = os.path.join(self.tmp, "sys")
        self.local_bin = os.path.join(self.tmp, "home", ".local", "bin")
        write_exe(os.path.join(self.sys_bin, "flex"), FAKE_FLEX)
        os.symlink("flex", os.path.join(self.sys_bin, "lex"))
        self.wrapper = os.path.join(self.local_bin, "lex")
        write_exe(self.wrapper, '#!/usr/bin/env bash\nexec "/opt/lex/.venv/bin/python" "/opt/lex/lex.py" "$@"\n')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_check(self, path, *args):
        env = {"PATH": path, "HOME": os.path.join(self.tmp, "home")}
        proc = subprocess.run([BASH, CHECK, *args], env=env, capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout + proc.stderr

    def test_flex_first_warns_with_fix(self):
        code, out = self.run_check(f"{self.sys_bin}:{self.local_bin}:{SYSTEM_PATH}", "--expect", self.wrapper)
        self.assertEqual(code, 1, out)
        self.assertIn("WARNING: `lex` runs", out)
        self.assertIn("flex lexer", out)
        self.assertIn(f'export PATH="{self.local_bin}:$PATH"', out)
        self.assertIn("--alias", out)
        self.assertIn("type -a lex", out)

    def test_lex_first_is_ok_and_mentions_shadowed_flex(self):
        code, out = self.run_check(f"{self.local_bin}:{self.sys_bin}:{SYSTEM_PATH}", "--expect", self.wrapper)
        self.assertEqual(code, 0, out)
        self.assertIn("OK: `lex` runs Lex", out)
        self.assertIn("not used", out)
        self.assertIn("flex lexer", out)

    def test_wrapper_recognised_without_expect(self):
        code, out = self.run_check(f"{self.local_bin}:{self.sys_bin}:{SYSTEM_PATH}")
        self.assertEqual(code, 0, out)
        self.assertIn("OK: `lex` runs Lex", out)

    def test_flex_only_warns(self):
        code, out = self.run_check(f"{self.sys_bin}:{SYSTEM_PATH}")
        self.assertEqual(code, 1, out)
        self.assertIn("flex lexer", out)
        self.assertIn('export PATH="$HOME/.local/bin:$PATH"', out)

    def test_npm_launcher_recognised(self):
        npm_bin = os.path.join(self.tmp, "npm", "bin")
        target = os.path.join(self.tmp, "npm", "lib", "node_modules", "@n8te_", "lex-cli", "bin", "lex.js")
        write_exe(target, "#!/usr/bin/env node\n")
        os.makedirs(npm_bin)
        os.symlink(target, os.path.join(npm_bin, "lex"))
        code, out = self.run_check(f"{npm_bin}:{self.sys_bin}:{SYSTEM_PATH}")
        self.assertEqual(code, 0, out)
        self.assertIn("OK: `lex` runs Lex", out)

    def test_no_lex_on_path(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        code, out = self.run_check(empty)
        self.assertEqual(code, 0, out)
        self.assertIn("No command named lex", out)

    def test_setup_rejects_bad_alias_before_installing(self):
        env = {"PATH": SYSTEM_PATH, "HOME": os.path.join(self.tmp, "home")}
        for argv in (["--alias", "lex"], ["--alias", "x;y"], ["--alias"]):
            with self.subTest(argv=argv):
                proc = subprocess.run([BASH, SETUP, *argv], env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
                self.assertIn("--alias", proc.stdout)
                self.assertNotIn("Lex Command Installed", proc.stdout)


if __name__ == "__main__":
    unittest.main()

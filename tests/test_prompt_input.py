"""Regression tests: follow-up prompts must not crash without a terminal.

Before this fix, `lex study John 1:1` and `lex search israel` ended with an
EOFError traceback (exit 1) when stdin was closed, piped, or redirected, and
Ctrl-D / Ctrl-C at a prompt did the same. Now non-TTY stdin skips the
follow-up prompt, and EOF or Ctrl-C at a prompt exits 0 with no traceback.

Run: python3 -m unittest discover -s tests
Each test uses a throwaway HOME.
"""
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

COMMANDS = [
    ["study", "John", "1:1", "--no-animate"],
    ["John", "3:16", "-i", "--no-animate"],
    ["search", "israel", "--limit", "2"],
    ["topic", "love"],
]


def make_controlling_tty():
    """Child setup: new session with the pty (fd 0) as controlling terminal,
    so Ctrl-C becomes SIGINT and Ctrl-D becomes EOF, as in a real terminal."""
    import fcntl
    import termios
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


class PromptInputTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-test-prompt-")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env.update({"HOME": self.home, "LEX_NO_COLOR": "1", "COLUMNS": "100", "TERM": "dumb"})
        return env

    def run_lex(self, argv, stdin):
        stdin_kwargs = {"stdin": stdin} if stdin is not None else {"input": "n\nq\n"}
        proc = subprocess.run(
            [sys.executable, LEX, *argv], cwd=ROOT, env=self.env(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=120, **stdin_kwargs,
        )
        return proc.returncode, ANSI.sub("", proc.stdout)

    def test_closed_stdin_exits_cleanly(self):
        for argv in COMMANDS:
            with self.subTest(argv=argv):
                code, out = self.run_lex(argv, subprocess.DEVNULL)
                self.assertEqual(code, 0, out[-2000:])
                self.assertNotIn("Traceback", out)
                self.assertNotIn("EOFError", out)

    def test_piped_stdin_skips_follow_up_prompts(self):
        for argv in COMMANDS:
            with self.subTest(argv=argv):
                code, out = self.run_lex(argv, None)
                self.assertEqual(code, 0, out[-2000:])
                self.assertNotIn("Traceback", out)
                self.assertNotIn("Study action [", out)
                self.assertNotIn("Search action", out)

    @unittest.skipUnless(sys.platform != "win32", "needs a POSIX pty")
    def test_eof_and_ctrl_c_at_tty_prompt_exit_zero(self):
        import pty
        for key in (b"\x04", b"\x03"):
            with self.subTest(key=key):
                master, slave = pty.openpty()
                proc = subprocess.Popen(
                    [sys.executable, LEX, "study", "John", "1:1", "--no-animate"],
                    cwd=ROOT, env=self.env(), stdin=slave, stdout=slave, stderr=slave,
                    preexec_fn=make_controlling_tty,
                )
                os.close(slave)
                buf = b""
                deadline = time.time() + 60
                sent = False
                try:
                    while time.time() < deadline:
                        ready, _, _ = select.select([master], [], [], 0.5)
                        if ready:
                            try:
                                chunk = os.read(master, 65536)
                            except OSError:
                                break
                            if not chunk:
                                break
                            buf += chunk
                        if not sent and b"Study action" in buf:
                            time.sleep(0.2)
                            os.write(master, key)
                            sent = True
                        if proc.poll() is not None and not ready:
                            break
                    code = proc.wait(timeout=30)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    os.close(master)
                out = ANSI.sub("", buf.decode("utf-8", "replace"))
                self.assertTrue(sent, "never reached the Study action prompt:\n" + out[-2000:])
                self.assertEqual(code, 0, out[-2000:])
                self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()

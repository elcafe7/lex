"""Regression tests for the Strong's MarkupError crash (fixed in 2.6.6).

2.6.5 crashed with rich.errors.MarkupError ("closing tag '[/]' ... has nothing
to close") on `lex strongs G3056` and ~5,200 other entries: imported tags like
<ref='Mat.8.8'> were not recognised, so the opening [cyan] was dropped while
the closing [/] was kept, and literal lexicon text such as "[in LXX ...]" was
read as Rich markup. These tests drive the command with stdin input and check
the converter directly.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from rich.console import Console
from rich.markup import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CRASH_MARKERS = ("Traceback", "MarkupError", "has nothing to close", "doesn't match any open tag")


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


class StrongsCommandTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-strongs-test-")
        with open(os.path.join(self.home, ".lex_config.json"), "w", encoding="utf-8") as fh:
            fh.write('{"bible": "esv"}')

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_lex(self, *argv, stdin_text="\nq\n"):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env.update({"HOME": self.home, "LEX_NO_COLOR": "1", "COLUMNS": "100", "TERM": "dumb"})
        proc = subprocess.run(
            [sys.executable, LEX, *argv],
            cwd=ROOT, env=env, input=stdin_text,
            capture_output=True, text=True, timeout=120,
        )
        return proc.returncode, ANSI.sub("", proc.stdout + proc.stderr)

    def assert_lexicon(self, argv, title, expected_text):
        for stdin_text in ("\nq\n", "1\nq\n", "n\n\nq\n"):
            code, out = self.run_lex(*argv, stdin_text=stdin_text)
            label = f"lex {' '.join(argv)} with stdin {stdin_text!r}"
            for bad in CRASH_MARKERS:
                self.assertNotIn(bad, out, f"{label} printed {bad!r}:\n{out[-2000:]}")
            self.assertEqual(code, 0, f"{label} exited {code}:\n{out[-2000:]}")
            self.assertIn(title, out, f"{label} missing {title!r}")
            self.assertIn(expected_text, out, f"{label} missing {expected_text!r}")

    def test_greek_g3056(self):
        # The reported crash; "[in LXX" was also silently swallowed as markup.
        self.assert_lexicon(["strongs", "G3056"], "Greek Lexicon: G3056", "[in LXX chiefly for")

    def test_greek_g3056_lowercase_shortcut(self):
        self.assert_lexicon(["g3056"], "Greek Lexicon: G3056", "Mat.8:8")

    def test_hebrew_h1057(self):
        # One of the 31 Hebrew entries that crashed on 2.6.5.
        self.assert_lexicon(["strongs", "H1057"], "Hebrew Lexicon: H1057", "Verse Usage")

    def test_hebrew_h0430(self):
        self.assert_lexicon(["strongs", "H0430"], "Hebrew Lexicon: H430", "Verse Usage")

    def test_markup_in_user_query_is_literal(self):
        code, out = self.run_lex("manuscript", "x[/b]", stdin_text="\n")
        for bad in CRASH_MARKERS:
            self.assertNotIn(bad, out, out[-2000:])
        self.assertIn("x[/b]", out)

    def test_english_strongs_query_with_markup(self):
        code, out = self.run_lex("strongs", "love [/]", stdin_text="\n")
        for bad in CRASH_MARKERS:
            self.assertNotIn(bad, out, out[-2000:])
        self.assertIn("love [/]", out)

    def test_history_lists_markup_like_queries(self):
        # 2.6.5 recorded the query, then `lex history` crashed on every run
        # until the history was cleared.
        self.run_lex("manuscript", "x[/b] [/]", stdin_text="\n")
        code, out = self.run_lex("history", "--limit", "5", stdin_text="q\n")
        for bad in CRASH_MARKERS:
            self.assertNotIn(bad, out, out[-2000:])
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("x[/b] [/]", out)


class RichLexiconTextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = load_lex_module()

    def plain(self, value):
        return render(self.lex.rich_lexicon_text(value)).plain

    def test_ref_with_attribute_is_styled_and_balanced(self):
        markup = self.lex.rich_lexicon_text("idea: <ref='Mat.8.8'>Mat.8:8</ref>, <ref='1Co.14.9, 19'>1Co.14:9, 19</ref>")
        self.assertEqual(markup.count("[cyan]"), 2)
        self.assertEqual(render(markup).plain, "idea: Mat.8:8, 1Co.14:9, 19")

    def test_literal_brackets_survive(self):
        self.assertEqual(self.plain("[in LXX chiefly for x, etc. ;] Mrk.16:[20]"), "[in LXX chiefly for x, etc. ;] Mrk.16:[20]")
        self.assertEqual(self.plain("stray [/] and [/b] and [bold]x"), "stray [/] and [/b] and [bold]x")

    def test_unbalanced_source_tags_never_raise(self):
        self.assertEqual(self.plain("a</b> <b>bold <i>both</b> tail"), "a bold both tail")
        self.assertEqual(self.plain("<BR />x<br/>y<Br>"), "\nx\ny\n")

    def test_every_strongs_entry_renders(self):
        app_cls = next(v for v in vars(self.lex).values() if isinstance(v, type) and hasattr(v, "display_strongs"))
        app = app_cls()
        rows = app.strongs_db.query("SELECT number FROM strongs WHERE number IN ('G3056','G26','G2316','H1057','H430','H3068')")
        self.assertTrue(rows)
        sink = Console(file=open(os.devnull, "w"), width=100, theme=None)
        original = self.lex.console
        self.lex.console = sink
        try:
            for (number,) in rows:
                self.assertTrue(app.display_strongs(number, limit=2), number)
        finally:
            self.lex.console = original
            sink.file.close()


if __name__ == "__main__":
    unittest.main()

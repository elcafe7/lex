"""Tests for friendly errors: when a command fails, Lex says why in plain words
and suggests the corrected command.

Covers: unknown flags and subcommands (difflib, one or two dashes, help
aliases), misspelt book names, malformed references, unknown Bible ids, and
references that do not exist in the chosen Bible. Every failure keeps a
nonzero exit code, writes to stderr only, respects NO_COLOR / TERM=dumb, and
under --json becomes {"error": {code, message, reason, suggestions}}.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
ANSI = re.compile(r"\x1b\[")


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_friendly_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


class FriendlyErrorCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = tempfile.mkdtemp(prefix="lex-friendly-test-")
        with open(os.path.join(cls.home, ".lex_config.json"), "w", encoding="utf-8") as fh:
            fh.write('{"bible": "kjv"}')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.home, ignore_errors=True)

    def run_lex(self, *argv, extra_env=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env.update({"HOME": self.home, "COLUMNS": "100", "TERM": "dumb", "NO_COLOR": "1", "FORCE_COLOR": "0"})
        env.update(extra_env or {})
        proc = subprocess.run(
            [sys.executable, LEX, *argv], cwd=ROOT, env=env, input="", capture_output=True, text=True, timeout=120,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def fails(self, *argv, code=1, **kw):
        status, out, err = self.run_lex(*argv, **kw)
        label = "lex " + " ".join(argv)
        self.assertEqual(status, code, f"{label}: exit {status}\n{err}")
        self.assertEqual(out, "", f"{label} must not print to stdout:\n{out[:300]}")
        self.assertIsNone(ANSI.search(err), f"{label}: ANSI in stderr under NO_COLOR/TERM=dumb")
        self.assertTrue(err.startswith("lex: "), err)
        return err

    def fails_json(self, *argv, code):
        status, out, err = self.run_lex("--json", *argv)
        self.assertEqual(status, code, err)
        self.assertEqual(out, "")
        error = json.loads(err)["error"]
        self.assertTrue(error["message"] and error["reason"])
        self.assertIsInstance(error["suggestions"], list)
        return error

    # --- unknown flags and subcommands -----------------------------------
    def test_unknown_flag_suggests_close_flag_two_dashes(self):
        err = self.fails("--jsno", "John", "3:16", code=2)
        self.assertIn("lex --json John 3:16", err)

    def test_unknown_flag_one_dash_form_also_works(self):
        err = self.fails("-jsno", "John", "3:16", code=2)
        self.assertIn("lex --json John 3:16", err)
        err = self.fails("-ligth", code=2)
        self.assertIn("lex -light", err)

    def test_help_alias_typo_suggests_help(self):
        err = self.fails("--hepl", code=2)
        self.assertIn("lex --help", err)

    def test_flag_value_typo_keeps_value(self):
        err = self.fails("--limt=5", "grace", code=2)
        self.assertIn("--limit=5", err)

    def test_invalid_choice_lists_choices_and_closest(self):
        err = self.fails("--mode", "studdy", "John", "3:16", code=2)
        self.assertIn("Choose one of: read, study, web", err)
        self.assertIn("--mode study", err)

    def test_invalid_number_explained(self):
        err = self.fails("--page", "two", "search", "grace", code=2)
        self.assertIn("whole number", err)

    def test_search_scope_used_as_option(self):
        err = self.fails("-nt", code=2)
        self.assertIn("search scope", err)
        self.assertIn("lex search '<words>' -nt", err)

    def test_unknown_search_scope_suggests_nearest(self):
        err = self.fails("search", "grace", "-jhon")
        self.assertIn("Unknown book scope -jhon", err)
        self.assertIn("lex search grace -john", err)

    def test_mistyped_subcommand(self):
        err = self.fails("strong", "G3056")
        self.assertIn("`strong` is not a Lex command", err)
        self.assertIn("lex strongs G3056", err)
        err = self.fails("seach", "John", "3:16")
        self.assertIn("lex search John 3:16", err)

    # --- books and malformed references ----------------------------------
    def test_misspelt_book_gets_nearest_names(self):
        err = self.fails("Jhon", "3:16")
        self.assertIn("lex John 3:16", err)
        err = self.fails("Genisis", "1:1")
        self.assertIn("lex Genesis 1:1", err)
        err = self.fails("1", "Corinthans", "13:4")
        self.assertIn("lex 1 Corinthians 13:4", err)

    def test_unknown_book_with_no_close_match(self):
        err = self.fails("Nowhere", "1:1")
        self.assertIn("`Nowhere` is not a book name Lex knows", err)
        self.assertNotIn("Did you mean", err)

    def test_extra_verse_number_gets_likely_form(self):
        err = self.fails("jn", "3:16:2")
        self.assertIn("lex John 3:16", err)

    def test_spelled_out_reference_gets_likely_form(self):
        err = self.fails("john", "3", "verse", "16")
        self.assertIn("lex John 3:16", err)
        err = self.fails("John", "chapter", "3", "verse", "16", "to", "18")
        self.assertIn("lex John 3:16-18", err)

    def test_bare_book_missing_from_edition(self):
        err = self.fails("Tobit")
        self.assertIn("Tobit isn't in the KJV", err)
        self.assertIn("lex -B kj16 Tobit 1", err)

    def test_bare_misspelt_book(self):
        err = self.fails("Genisis")
        self.assertIn("lex Genesis 1", err)

    # --- Bible ids -------------------------------------------------------
    def test_unknown_bible_code_gets_closest_codes(self):
        err = self.fails("-B", "kjb", "John", "3:16")
        self.assertIn("Unknown Bible version: kjb", err)
        self.assertIn("lex -B kjv John 3:16", err)
        err = self.fails("--bible=nasv", "John", "3:16")
        self.assertIn("lex -B nasb John 3:16", err)

    def test_unknown_bible_code_for_sticky_forms(self):
        err = self.fails("-v", "kjb")
        self.assertIn("lex -v kjv", err)
        err = self.fails("bible", "kjb")
        self.assertIn("lex bible kjv", err)

    # --- references that do not exist in the chosen Bible -----------------
    def test_chapter_out_of_range(self):
        err = self.fails("John", "22:1")
        self.assertIn("John has 21 chapters in the KJV; chapter 22 doesn't exist.", err)
        self.assertIn("lex John 21", err)

    def test_verse_out_of_range(self):
        err = self.fails("John", "3:99")
        self.assertIn("John 3 has 36 verses in the KJV; verse 99 doesn't exist.", err)
        self.assertIn("lex John 3:36", err)

    def test_zero_chapter_and_verse(self):
        self.assertIn("Chapters start at 1", self.fails("John", "0:5"))
        err = self.fails("John", "3:0")
        self.assertIn("Verses start at 1", err)
        self.assertIn("lex John 3:1", err)

    def test_single_chapter_book(self):
        err = self.fails("Jude", "2:1")
        self.assertIn("Jude has 1 chapter in the KJV; chapter 2 doesn't exist.", err)

    def test_book_missing_from_edition_points_to_editions_that_have_it(self):
        err = self.fails("Tobit", "1:1")
        self.assertIn("Tobit isn't in the KJV; it's one of the Apocrypha books.", err)
        self.assertIn("lex -B kj16 Tobit 1:1", err)
        self.assertNotIn("lex -B esv", err)

    def test_new_testament_book_in_septuagint(self):
        err = self.fails("-B", "lxx", "John", "3:16")
        self.assertIn("Greek Old Testament", err)
        self.assertIn("lex -B kjv John 3:16", err)

    def test_b_flag_is_kept_in_suggestions(self):
        err = self.fails("-B", "kjv", "Johm", "3:16")
        self.assertIn("lex -B kjv John 3:16", err)

    def test_multiple_references_skip_bad_ones_but_exit_zero(self):
        status, out, err = self.run_lex("John 3:16; Nowhere 9:9; John 99:1")
        self.assertEqual(status, 0)
        self.assertIn("only begotten Son", out)
        self.assertIn('Skipped "Nowhere 9:9"', err)
        self.assertIn("chapter 99 doesn't exist", err)

    def test_all_references_bad_exits_nonzero(self):
        err = self.fails("John 99:1; Nowhere 9:9")
        self.assertIn('Couldn\'t find "John 99:1"', err)
        self.assertIn('Couldn\'t find "Nowhere 9:9"', err)

    def test_study_failure_uses_same_reasons(self):
        err = self.fails("study", "John", "22:1")
        self.assertIn("chapter 22 doesn't exist", err)

    def test_plain_mode_error_is_plain(self):
        err = self.fails("--plain", "John", "22:1")
        self.assertIn("chapter 22 doesn't exist", err)

    # --- security: quoting and control characters --------------------------
    def suggestion_lines(self, err):
        return [line.strip() for line in err.splitlines() if line.strip().startswith("lex ") and not line.startswith("lex:")]

    def test_suggestions_quote_shell_metacharacters(self):
        payload = "$(touch /tmp/lex-friendly-pwned)"
        err = self.fails("--jsn", payload, code=2)
        lines = self.suggestion_lines(err)
        self.assertTrue(lines, err)
        for line in lines:
            self.assertEqual(shlex.split(line)[:2], ["lex", "--json"])
            self.assertIn(payload, shlex.split(line))  # kept as one inert argument
            # Running the suggestion through a shell must not execute the substitution.
            marker = os.path.join(self.home, "pwned")
            line = line.replace("/tmp/lex-friendly-pwned", marker)
            subprocess.run(["sh", "-c", "echo " + line], capture_output=True, check=True)
            self.assertFalse(os.path.exists(marker))

    def test_suggestions_quote_backticks_semicolons_and_quotes(self):
        err = self.fails("--limt", "`id`", "it's", code=2)
        for line in self.suggestion_lines(err):
            self.assertEqual(shlex.join(shlex.split(line)), line)
            self.assertNotIn(" `id`", line)
        err = self.fails("--jsn", "a;b", "'; rm -rf ~ #", code=2)
        for line in self.suggestion_lines(err):
            self.assertEqual(shlex.join(shlex.split(line)), line)
            self.assertIn("'a;b'", line)

    def test_json_suggestions_are_quoted_too(self):
        error = self.fails_json("--jsn", "$(touch x)", code=2)
        self.assertTrue(error["suggestions"])
        for s in error["suggestions"]:
            self.assertEqual(shlex.split(s)[:2], ["lex", "--json"])
            self.assertEqual(shlex.join(shlex.split(s)), s)
            self.assertNotIn(" $(touch", s)

    def test_control_characters_are_stripped_from_text_errors(self):
        for argv, code in [
            (("Jhon\x1b[31m\x9b2J", "3:16\x07\x7f"), 1),
            (("--jsn\x1b]0;pwned\x07", "John"), 2),
            (("Nowhere\x1b[2J", "1:1"), 1),
            (("-B", "kj\x1bb", "John", "3:16"), 1),
            (("John", "99\x1b[1m:1"), 1),
        ]:
            err = self.fails(*argv, code=code)
            self.assertIsNone(re.search(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", err), repr(err))

    def test_control_characters_are_stripped_from_json_errors(self):
        for argv, code in [(("Jhon\x1b[31m", "3:16"), 3), (("--jsn\x1b[2J", "John"), 2), (("-B", "kj\x1bb", "John"), 2)]:
            status, out, err = self.run_lex("--json", *argv)
            self.assertEqual(status, code, err)
            self.assertNotRegex(err, r"[\x00-\x1f\x7f-\x9f]\S*(?<!\n)$|\x7f")
            error = json.loads(err)["error"]
            strings = [error["message"], error["reason"], *error["suggestions"]]
            for text in strings:
                self.assertIsNone(re.search(r"[\x00-\x1f\x7f-\x9f]", text), repr(text))

    # --- --json ----------------------------------------------------------
    def test_json_chapter_out_of_range(self):
        error = self.fails_json("John", "22:1", code=3)
        self.assertEqual(error["code"], "not_found")
        self.assertEqual(error["reason"], "John has 21 chapters in the KJV; chapter 22 doesn't exist.")
        self.assertEqual(error["suggestions"], ["lex --json John 21"])

    def test_json_book_missing_from_edition(self):
        error = self.fails_json("Tobit", "1:1", code=3)
        self.assertIn("isn't in the KJV", error["reason"])
        self.assertIn("lex --json -B kj16 Tobit 1:1", error["suggestions"])

    def test_json_misspelt_book(self):
        error = self.fails_json("Jhon", "3:16", code=3)
        self.assertEqual(error["suggestions"][0], "lex --json John 3:16")

    def test_json_unknown_flag(self):
        error = self.fails_json("--jsno", "John", code=2)
        self.assertEqual(error["code"], "usage")
        self.assertEqual(error["suggestions"], ["lex --json John"])

    def test_json_unknown_edition(self):
        error = self.fails_json("-B", "kjb", "John", "3:16", code=2)
        self.assertEqual(error["code"], "unknown_edition")
        self.assertEqual(error["suggestions"][0], "lex --json -B kjv John 3:16")
        self.assertIn("kjv", error["available"])

    def test_json_errors_always_carry_reason_and_suggestions(self):
        error = self.fails_json("-v", "kjv", code=2)
        self.assertEqual(error["code"], "sticky_default_in_json")
        self.assertEqual(error["suggestions"], [])
        self.assertTrue(error["reason"])


class FriendlyErrorUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = load_lex_module()

    def test_help_aliases_are_known_options(self):
        names = self.lex.option_names()
        self.assertEqual(names["help"], "--help")
        self.assertEqual(names["h"], "-h")
        for alias in self.lex.HELP_FLAG_ALIASES:
            self.assertTrue(alias.lstrip("-") in names, alias)

    def test_close_matches_is_case_insensitive_and_ordered(self):
        self.assertEqual(self.lex.close_matches("JSNO", ["json", "plain"]), ["json"])
        self.assertEqual(self.lex.close_matches("zzzz", ["json", "plain"]), [])

    def test_repaired_forms(self):
        f = self.lex.repaired_reference_forms
        self.assertEqual(f("john", ["3", "16", "2"], "3:16:2"), ["3:16"])
        self.assertEqual(f("john", ["3", "16"], " 3 verse 16"), ["3:16"])
        self.assertEqual(f("john", ["3", "16", "18"], "3:16-18"), ["3:16", "3:16-18"])
        self.assertEqual(f("john", [], ""), [])

    def test_command_line_does_not_double_json(self):
        self.assertEqual(self.lex.command_line("John 3:16", json_mode=True), "lex --json John 3:16")
        self.assertEqual(self.lex.command_line("--json John", json_mode=True), "lex --json John")
        self.assertEqual(self.lex.command_line("John 3:16"), "lex John 3:16")

    def _emit(self, tty, env):
        class FakeErr(io.StringIO):
            def isatty(self_inner):
                return tty
        saved_err, saved_env = sys.stderr, dict(os.environ)
        for key in ("NO_COLOR", "LEX_NO_COLOR", "TERM"):
            os.environ.pop(key, None)
        os.environ.update(env)
        sys.stderr = FakeErr()
        try:
            self.lex.emit_friendly_error("boom", "because", ["John 3:16"])
            return sys.stderr.getvalue()
        finally:
            sys.stderr = saved_err
            os.environ.clear()
            os.environ.update(saved_env)

    def test_colour_only_on_a_real_colour_terminal(self):
        self.assertIn("\x1b[", self._emit(True, {"TERM": "xterm-256color"}))
        self.assertNotIn("\x1b[", self._emit(False, {"TERM": "xterm-256color"}))
        self.assertNotIn("\x1b[", self._emit(True, {"TERM": "xterm-256color", "NO_COLOR": "1"}))
        self.assertNotIn("\x1b[", self._emit(True, {"TERM": "xterm-256color", "LEX_NO_COLOR": "1"}))
        self.assertNotIn("\x1b[", self._emit(True, {"TERM": "dumb"}))

    def test_strip_control_and_command_line_quoting(self):
        self.assertEqual(self.lex.strip_control("a\x1b[31mb\x00c\x7fd\x9be\nf"), "a[31mbcde f")
        self.assertEqual(self.lex.command_line(["--limit", "a b"]), "lex --limit 'a b'")
        self.assertEqual(self.lex.command_line("x;y $(z)", json_mode=True), "lex --json 'x;y' '$(z)'")

    def test_emit_strips_control_characters(self):
        class Capture(io.StringIO):
            def isatty(self):
                return False
        saved = sys.stderr
        sys.stderr = Capture()
        try:
            self.lex.emit_friendly_error("bad \x1b[2Jmsg", "why\x07", ["John\x1b[0m 3:16"])
            text = sys.stderr.getvalue()
        finally:
            sys.stderr = saved
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\x07", text)
        self.assertIn("lex 'John[0m' 3:16", text)

    def test_message_shape(self):
        text = self._emit(False, {"TERM": "dumb"})
        self.assertEqual(text, "lex: boom\n  because\n  Did you mean:\n    lex John 3:16\n")


if __name__ == "__main__":
    unittest.main()

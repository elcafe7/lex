"""Regression tests for bare flags/subcommands (2.6.6).

Every flag or subcommand that needs an argument must, when run without one,
print a command-specific explainer, exit 0, and leave state untouched.
`-B` is always a one-command override; `-v <id>` stays the sticky default.

Run: python3 -m unittest discover -s tests
Each test uses a throwaway HOME so the real ~/.lex_config.json is never read
or written.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
VERSION_IDS = ["esv", "kjv", "kj16", "nasb", "gen", "dra", "lxx", "brenton", "vulg"]
STATE_FILES = [".lex_config.json", ".lex_history", ".lex_query_history"]
SEED_CONFIG = {"bible": "nasb", "theme": "dark"}

# (argv, text that must appear in the explainer)
BARE_FLAGS = [
    (["-v"], "lex -v: Set Default Bible"),
    (["-B"], "lex -B: Bible For One Command"),
    (["--bible"], "lex -B: Bible For One Command"),
    (["--page"], "lex --page: Result Page"),
    (["--limit"], "lex --limit: Results Per Page"),
    (["--mode"], "lex --mode: Export Mode"),
    (["--format"], "lex --format: Export Format"),
    (["--ratio"], "lex --ratio: PNG Aspect Ratio"),
    (["-i"], "lex -i: Interlinear Study Flag"),
    (["-s"], "Strong's Lookup"),
    (["-d"], "Dictionary"),
    # value flag followed by another flag is still bare
    (["-B", "--no-animate"], "lex -B: Bible For One Command"),
    (["search", "covenant", "--page"], "lex --page: Result Page"),
    (["export", "John 3:16", "--format"], "lex --format: Export Format"),
    (["-dark", "-v"], "lex -v: Set Default Bible"),
]

BARE_SUBCOMMANDS = [
    (["version"], "lex -v: Set Default Bible"),
    (["bible"], "lex -v: Set Default Bible"),
    (["read"], "Read"),
    (["study"], "Study"),
    (["search"], "Search"),
    (["serch"], "Search"),
    (["search", "-nt"], "Search"),
    (["web"], "Web"),
    (["manuscript"], "Manuscript"),
    (["export"], "Export"),
    (["strongs"], "Strong's Lookup"),
    (["topic"], "Nave"),
    (["naves"], "Nave"),
    (["commentary"], "Commentary"),
    (["define"], "Dictionary"),
]


def sha(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class LexCLITestCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-test-home-")
        with open(os.path.join(self.home, ".lex_config.json"), "w", encoding="utf-8") as fh:
            json.dump(SEED_CONFIG, fh)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_lex(self, *argv):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env.update({"HOME": self.home, "LEX_NO_COLOR": "1", "COLUMNS": "100", "TERM": "dumb"})
        proc = subprocess.run(
            [sys.executable, LEX, *argv],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120,
        )
        return proc.returncode, ANSI.sub("", proc.stdout + proc.stderr)

    def state(self):
        return {name: sha(os.path.join(self.home, name)) for name in STATE_FILES}

    def config(self):
        with open(os.path.join(self.home, ".lex_config.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def assert_explainer(self, argv, expected):
        before = self.state()
        code, out = self.run_lex(*argv)
        self.assertEqual(code, 0, f"lex {' '.join(argv)} exited {code}:\n{out}")
        self.assertIn(expected, out, f"lex {' '.join(argv)} missing {expected!r}:\n{out}")
        for bad in ("expected one argument", "usage: lex", "Traceback", "error:"):
            self.assertNotIn(bad, out, f"lex {' '.join(argv)} printed {bad!r}:\n{out}")
        self.assertEqual(self.state(), before, f"lex {' '.join(argv)} changed state files")
        return out


class BareFlagTests(LexCLITestCase):
    def test_bare_flags_print_explainers(self):
        for argv, expected in BARE_FLAGS:
            with self.subTest(argv=argv):
                self.assert_explainer(argv, expected)

    def test_bare_subcommands_print_explainers(self):
        for argv, expected in BARE_SUBCOMMANDS:
            with self.subTest(argv=argv):
                self.assert_explainer(argv, expected)

    def test_version_flags_list_all_ids_and_mark_default(self):
        for flag in ("-v", "-B"):
            with self.subTest(flag=flag):
                out = self.assert_explainer([flag], "Valid versions:")
                for bible_id in VERSION_IDS:
                    self.assertRegex(out, rf"\b{bible_id}\b")
                self.assertRegex(out, r"nasb\s+New American Standard Bible \(1995\)\s+\* current default")
                self.assertIn("Usage: lex " + flag, out)
                self.assertEqual(out.count("* current default"), 1)

    def test_help_never_mentions_a_menu_for_versions(self):
        code, out = self.run_lex("help")
        self.assertEqual(code, 0)
        self.assertNotIn("menu", out.lower())
        self.assertIn("lex -v", out)


class BibleSelectionTests(LexCLITestCase):
    def test_B_with_version_but_no_reference_is_explainer_only(self):
        out = self.assert_explainer(["-B", "kjv"], "lex -B: Bible For One Command")
        self.assertIn("one command only", out)
        self.assertIn("KJV", out)
        self.assertIn("nothing was changed", out)
        self.assertEqual(self.config()["bible"], "nasb")

    def test_B_alias_and_case_with_no_reference_do_not_save(self):
        for argv in (["-B", "KJV"], ["--bible", "vulgate"], ["-B", "lxx", "--no-animate"]):
            with self.subTest(argv=argv):
                self.assert_explainer(argv, "nothing was changed")

    def test_B_with_reference_is_one_time(self):
        before = sha(os.path.join(self.home, ".lex_config.json"))
        code, out = self.run_lex("-B", "kjv", "John", "3:16", "--no-animate")
        self.assertEqual(code, 0, out)
        self.assertIn("loved the world", out)  # KJV: "For God so loved the world"
        self.assertEqual(sha(os.path.join(self.home, ".lex_config.json")), before)
        self.assertEqual(self.config()["bible"], "nasb")

    def test_B_unknown_version_lists_choices_without_saving(self):
        before = self.state()[".lex_config.json"]
        code, out = self.run_lex("-B", "foo", "John", "3:16")
        self.assertEqual(code, 1)
        self.assertIn("Unknown Bible version: foo", out)
        self.assertIn(", ".join(VERSION_IDS), out)
        self.assertEqual(self.state()[".lex_config.json"], before)

    def test_v_sets_sticky_default(self):
        code, out = self.run_lex("-v", "kjv")
        self.assertEqual(code, 0, out)
        self.assertIn("Default Bible version set to kjv", out)
        self.assertEqual(self.config()["bible"], "kjv")
        self.assertEqual(self.config()["theme"], "dark")  # other keys preserved
        code, out = self.run_lex("-v")
        self.assertRegex(out, r"kjv\s+King James Version \(Oxford 1769\)\s+\* current default")

    def test_v_alias_and_version_subcommand_still_sticky(self):
        code, out = self.run_lex("-v", "vulgate")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.config()["bible"], "vulg")
        code, out = self.run_lex("version", "esv")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.config()["bible"], "esv")

    def test_v_unknown_version_does_not_save(self):
        before = sha(os.path.join(self.home, ".lex_config.json"))
        code, out = self.run_lex("-v", "foo")
        self.assertEqual(code, 1)
        self.assertIn("Unknown Bible version: foo", out)
        self.assertEqual(sha(os.path.join(self.home, ".lex_config.json")), before)


if __name__ == "__main__":
    unittest.main()

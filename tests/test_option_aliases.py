"""Tests for option dash aliases, help spellings, and --help completeness.

Known long options accept one dash or two (`-json` / `--json`). Single-letter
short flags also accept two (`--h` / `-h`). `--help`, `-help`, `-h`, and
`--h` all print the same full help. Attached short values, negative numbers,
and search scopes are left alone.

Run: python3 -m unittest tests.test_option_aliases
"""
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

# Import lex.py as a module without running main.
import importlib.util
_spec = importlib.util.spec_from_file_location("lex_aliases_under_test", LEX)
lex = importlib.util.module_from_spec(_spec)
# lex.py runs side-effecting imports only; main is behind a name check.
_spec.loader.exec_module(lex)

# (input argv, expected argv after normalize_argv)
NORMALIZE_CASES = [
    (["--json", "John", "3:16"], ["--json", "John", "3:16"]),
    (["-json", "John", "3:16"], ["--json", "John", "3:16"]),
    (["strongs", "G3056", "-json"], ["strongs", "G3056", "--json"]),
    (["-plain", "study", "John", "1:1"], ["--plain", "study", "John", "1:1"]),
    (["--plain"], ["--plain"]),
    (["--h"], ["-h"]),
    (["-help"], ["--help"]),
    (["--help"], ["--help"]),
    (["-h"], ["-h"]),
    (["study", "--h"], ["study", "-h"]),
    (["study", "-help"], ["study", "--help"]),
    (["-version"], ["--version"]),
    (["--version"], ["--version"]),
    (["--v", "kjv"], ["-v", "kjv"]),
    (["-v", "kjv"], ["-v", "kjv"]),
    (["-v=kjv"], ["-v=kjv"]),
    (["--v=kjv"], ["-v=kjv"]),
    (["--B", "kjv"], ["-B", "kjv"]),
    (["--B=kjv"], ["-B=kjv"]),
    (["-B", "kjv"], ["-B", "kjv"]),
    (["-bible", "kjv"], ["--bible", "kjv"]),
    (["--bible", "kjv"], ["--bible", "kjv"]),
    (["--light"], ["-light"]),
    (["-light"], ["-light"]),
    (["--dark"], ["-dark"]),
    (["--auto"], ["-auto"]),
    (["-update"], ["--update"]),
    (["--update"], ["--update"]),
    (["-credits"], ["--credits"]),
    (["-next"], ["--next"]),
    (["-prev"], ["--prev"]),
    (["-page=2"], ["--page=2"]),
    (["-limit", "5"], ["--limit", "5"]),
    (["-all"], ["--all"]),
    (["-mode", "read"], ["--mode", "read"]),
    (["-format", "png"], ["--format", "png"]),
    (["-ratio", "1:1"], ["--ratio", "1:1"]),
    (["-animate"], ["--animate"]),
    (["-no-animate"], ["--no-animate"]),
    (["-clear"], ["--clear"]),
    (["-interlinear"], ["--interlinear"]),
    (["-define"], ["--define"]),
    (["-creed"], ["--creed"]),
    (["-strongs"], ["--strongs"]),
    # Skipped: attached short values
    (["-Bkjv"], ["-Bkjv"]),
    (["-vkjv"], ["-vkjv"]),
    # Skipped: negative numbers and numeric-looking tokens
    (["-1"], ["-1"]),
    (["-16"], ["-16"]),
    (["-3:16"], ["-3:16"]),
    (["-1-2"], ["-1-2"]),
    # Skipped: search scopes and combined shorts
    (["search", "grace", "-nt"], ["search", "grace", "-nt"]),
    (["search", "covenant", "-ot", "-json"], ["search", "covenant", "-ot", "--json"]),
    (["-id"], ["-id"]),
    (["-jeremiah"], ["-jeremiah"]),
    (["-1-john"], ["-1-john"]),
    # End of options
    (["search", "--", "-json"], ["search", "--", "-json"]),
    (["--", "--h"], ["--", "--h"]),
]


HELP_SPELLINGS = [
    ["--help"],
    ["-help"],
    ["-h"],
    ["--h"],
]


class NormalizeArgvTest(unittest.TestCase):
    def test_table(self):
        for argv, expected in NORMALIZE_CASES:
            with self.subTest(argv=argv):
                self.assertEqual(lex.normalize_argv(argv), expected)

    def test_json_and_plain_detectors_accept_single_dash(self):
        self.assertTrue(lex.json_mode_requested(["-json", "John", "3:16"]))
        self.assertTrue(lex.json_mode_requested(["--json", "John", "3:16"]))
        self.assertFalse(lex.json_mode_requested(["search", "--", "-json"]))
        self.assertTrue(lex.plain_mode_requested(["-plain", "John", "3:16"]))
        self.assertFalse(lex.plain_mode_requested(["search", "--", "-plain"]))

    def test_maps_cover_every_parser_option(self):
        long_map, short_map = lex.option_alias_maps()
        parser = lex.build_arg_parser()
        seen_long, seen_short = set(), set()
        for action in parser._actions:
            for opt in action.option_strings:
                if opt.startswith("--"):
                    seen_long.add(opt[2:])
                    self.assertEqual(long_map[opt[2:]], opt)
                elif opt.startswith("-") and len(opt) > 2:
                    seen_long.add(opt[1:])
                    self.assertEqual(long_map[opt[1:]], opt)
                elif opt.startswith("-") and len(opt) == 2:
                    seen_short.add(opt[1:])
                    self.assertEqual(short_map[opt[1:]], opt)
        self.assertEqual(set(long_map), seen_long)
        self.assertEqual(set(short_map), seen_short)
        for name in ("json", "plain", "help", "version", "light"):
            self.assertIn(name, long_map)
        for name in ("h", "v", "B", "i"):
            self.assertIn(name, short_map)


class LexCLITestCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-test-home-")
        with open(os.path.join(self.home, ".lex_config.json"), "w", encoding="utf-8") as fh:
            json.dump({"bible": "esv", "theme": "dark"}, fh)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_lex(self, *argv, env=None):
        full_env = os.environ.copy()
        full_env["HOME"] = self.home
        full_env["NO_COLOR"] = "1"
        if env:
            full_env.update(env)
        proc = subprocess.run(
            [sys.executable, LEX, *argv],
            cwd=ROOT,
            env=full_env,
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout, proc.stderr


class HelpSpellingTest(LexCLITestCase):
    def _help_text(self, *argv):
        if len(argv) == 1 and isinstance(argv[0], (list, tuple)):
            argv = tuple(argv[0])
        code, out, err = self.run_lex(*argv)
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        return ANSI.sub("", out)

    def test_four_spellings_match_at_top_level(self):
        texts = [self._help_text(argv) for argv in HELP_SPELLINGS]
        for text in texts[1:]:
            self.assertEqual(texts[0], text)
        for needle in (
            "--json",
            "--plain",
            "-h, --help",
            "NO_COLOR=1",
            "-json",
            "--h",
            "lex --json John 3:16",
        ):
            self.assertIn(needle, texts[0])

    def test_four_spellings_match_after_subcommand(self):
        top = self._help_text("--help")
        for spelling in ("--help", "-help", "-h", "--h"):
            with self.subTest(spelling=spelling):
                self.assertEqual(top, self._help_text("study", spelling))
                self.assertEqual(top, self._help_text("search", spelling))
                self.assertEqual(top, self._help_text("strongs", spelling))

    def test_help_lists_every_argparse_option(self):
        help_text = self._help_text("--help")
        parser = lex.build_arg_parser()
        missing = []
        for action in parser._actions:
            for opt in action.option_strings:
                if opt not in help_text:
                    missing.append(opt)
        self.assertEqual(missing, [])

    def test_help_does_not_go_through_json_mode(self):
        code, out, err = self.run_lex("--json", "--help")
        self.assertEqual(code, 0, err)
        self.assertIn("usage: lex", ANSI.sub("", out))
        self.assertNotIn("{", out.split("usage:", 1)[0] if "usage:" in out else out[:20])


class AliasCliTest(LexCLITestCase):
    def test_version_via_single_dash(self):
        code, out, err = self.run_lex("-version")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), lex.VERSION)

    def test_json_via_single_dash(self):
        code, out, err = self.run_lex("-json", "John", "3:16")
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "read")
        self.assertIn("For God so loved", payload["passages"][0]["verses"][0]["text"])

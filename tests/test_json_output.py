"""Tests for `lex --json` (schema: docs/json-output.md) and the Strong's
definition cleanup that JSON mode relies on.

JSON mode must print exactly one JSON document on stdout, never prompt, never
write the sticky default / theme / history, report errors as JSON on stderr
with a nonzero exit code, and keep -B a one-command override.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
ANSI = re.compile(r"\x1b\[")
BOX_CHARS = set("╭╮╰╯│─━┃")
ENVELOPE_KEYS = {"schema_version", "lex_version", "command", "edition", "edition_name"}
TOKEN_KEYS = {
    "position", "word", "strongs", "gloss", "lemma", "lemma_translit", "surface",
    "translit", "morph", "source_order", "confidence",
}
VERSE_KEYS = {"ref", "key", "book", "chapter", "verse", "text"}


def nfc(text):
    # Source data mixes oxia/tonos accents; compare canonically.
    return unicodedata.normalize("NFC", text)


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_json_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


class JsonCliTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-json-test-")
        self.config = os.path.join(self.home, ".lex_config.json")
        with open(self.config, "w", encoding="utf-8") as fh:
            fh.write('{"bible": "esv"}')

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_json(self, *argv, stdin_text="q\n1\n\n"):
        # stdin is fed on purpose: JSON mode must never read it.
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env.update({"HOME": self.home, "COLUMNS": "100", "TERM": "xterm-256color"})
        proc = subprocess.run(
            [sys.executable, LEX, "--json", *argv],
            cwd=ROOT, env=env, input=stdin_text,
            capture_output=True, text=True, timeout=120,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def ok(self, *argv):
        code, out, err = self.run_json(*argv)
        label = f"lex --json {' '.join(argv)}"
        self.assertEqual(code, 0, f"{label} exited {code}: {err[-1000:]}")
        self.assertEqual(err, "", f"{label} wrote to stderr: {err[-1000:]}")
        self.assertIsNone(ANSI.search(out), f"{label} printed ANSI codes")
        self.assertFalse(BOX_CHARS & set(out), f"{label} printed Rich box characters")
        self.assertEqual(out.count("\n"), 1, f"{label} must print one JSON line")
        payload = json.loads(out)
        self.assertTrue(ENVELOPE_KEYS <= set(payload), payload.keys())
        self.assertEqual(payload["schema_version"], 1)
        return payload

    def fails(self, expected_exit, expected_code, *argv):
        code, out, err = self.run_json(*argv)
        self.assertEqual(code, expected_exit, f"lex --json {' '.join(argv)}: {err}")
        self.assertEqual(out, "")
        payload = json.loads(err)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["error"]["code"], expected_code, payload)
        self.assertTrue(payload["error"]["message"])
        return payload

    def config_text(self):
        with open(self.config, encoding="utf-8") as fh:
            return fh.read()

    # --- read -----------------------------------------------------------
    def test_single_verse(self):
        payload = self.ok("John", "3:16")
        self.assertEqual(payload["command"], "read")
        self.assertEqual(payload["edition"], "esv")
        verses = payload["passages"][0]["verses"]
        self.assertEqual(len(verses), 1)
        self.assertEqual(set(verses[0]), VERSE_KEYS)
        self.assertEqual(verses[0]["ref"], "John 3:16")
        self.assertIn("God so loved the world", verses[0]["text"])

    def test_range_chapter_and_multiple_refs(self):
        payload = self.ok("John 3:16-18; Psalm 117; Nowhere 9:9")
        first, second = payload["passages"]
        self.assertEqual([v["verse"] for v in first["verses"]], [16, 17, 18])
        self.assertEqual((first["verse_start"], first["verse_end"]), (16, 18))
        self.assertEqual(second["ref"], "Psalm 117")
        self.assertEqual(len(second["verses"]), 2)
        self.assertTrue(all(not v["key"].endswith(":0") for v in second["verses"]))
        self.assertEqual(payload["not_found"], ["Nowhere 9:9"])

    def test_b_is_one_command_only(self):
        payload = self.ok("-B", "kjv", "John", "3:16")
        self.assertEqual(payload["edition"], "kjv")
        self.assertIn("only begotten Son", payload["passages"][0]["verses"][0]["text"])
        self.assertEqual(self.config_text(), '{"bible": "esv"}')
        self.assertEqual(self.ok("John", "3:16")["edition"], "esv")

    def test_no_state_written(self):
        self.ok("John", "3:16")
        self.ok("strongs", "G3056", "--limit", "2")
        self.ok("-B", "gen", "-light", "Romans", "1:1")
        self.assertEqual(sorted(os.listdir(self.home)), [".lex_config.json"])
        self.assertEqual(self.config_text(), '{"bible": "esv"}')

    # --- study ----------------------------------------------------------
    def test_study_tokens(self):
        payload = self.ok("study", "John", "1:1")
        verse = payload["verses"][0]
        self.assertEqual(verse["source"]["confidence"], "direct")
        self.assertEqual(verse["source"]["language"], "Greek")
        self.assertTrue(nfc(verse["source_text"]).startswith(nfc("Ἐν ἀρχῇ")), verse["source_text"][:20])
        for token in verse["tokens"]:
            self.assertEqual(set(token), TOKEN_KEYS)
            self.assertIsInstance(token["strongs"], list)
        logos = [t for t in verse["tokens"] if t["strongs"] == ["G3056"]]
        self.assertEqual(len(logos), 3)
        self.assertEqual(logos[0]["word"], "Word")
        self.assertEqual(logos[0]["confidence"], "direct")

    def test_interlinear_flag_is_study(self):
        payload = self.ok("John", "1:1", "-i")
        self.assertEqual(payload["command"], "study")

    def test_geneva_study_is_labelled_proxy(self):
        payload = self.ok("-B", "gen", "study", "Romans", "1:1")
        verse = payload["verses"][0]
        self.assertEqual(verse["key"], "gen:Rom:1:1")
        self.assertEqual(verse["ref"], "Romans 1:1")
        self.assertEqual(verse["source"]["confidence"], "proxy")
        tagged = [t for t in verse["tokens"] if t["strongs"]]
        self.assertTrue(tagged and all(t["confidence"] == "proxy" for t in tagged))

    def test_study_unsupported_edition(self):
        self.fails(2, "unsupported_edition", "-B", "lxx", "study", "Genesis", "1:1")

    # --- strongs --------------------------------------------------------
    def test_strongs_number(self):
        payload = self.ok("strongs", "G3056", "--limit", "3")
        entry = payload["entries"][0]
        self.assertEqual(entry["number"], "G3056")
        self.assertEqual(nfc(entry["lemma"]), nfc("λόγος"))
        self.assertEqual(entry["usage"]["index"], "esv-interlinear")
        self.assertTrue(entry["usage"]["indexed"])
        self.assertGreater(entry["usage"]["total"], 300)
        self.assertEqual(len(entry["usage"]["verses"]), 3)
        self.assertEqual(entry["usage"]["page_count"], -(-entry["usage"]["total"] // 3))
        self.assertIn("[in LXX chiefly for", entry["definition"]["text"])

    def test_strongs_g5594_brief_is_clean(self):
        entry = self.ok("strongs", "G5594")["entries"][0]
        self.assertNotIn('{"', entry["brief"])
        self.assertNotIn("\\n", entry["brief"])
        self.assertIn("from G4154, which", entry["brief"])
        self.assertEqual(entry["brief_refs"], ["G4154", "G109"])

    def test_strongs_zero_usage_is_explained(self):
        entry = self.ok("-B", "kjv", "strongs", "G1002")["entries"][0]
        self.assertEqual(entry["usage"]["total"], 0)
        self.assertFalse(entry["usage"]["indexed"])
        self.assertEqual(entry["usage"]["projected_to"], "kjv")
        self.assertIn("not proof", entry["usage"]["note"])

    def test_strongs_english(self):
        payload = self.ok("strongs", "love")
        self.assertEqual(payload["command"], "strongs_search")
        self.assertIn("G26", [r["number"] for r in payload["results"]])

    def test_bare_number_shortcut(self):
        self.assertEqual(self.ok("g26")["entries"][0]["number"], "G26")

    # --- web / search ---------------------------------------------------
    def test_web(self):
        payload = self.ok("web", "John", "3:16", "--limit", "3")
        self.assertEqual(payload["verse"]["ref"], "John 3:16")
        links = payload["cross_references"]
        self.assertEqual([link["rank"] for link in links], [1, 2, 3])
        self.assertTrue(all(link["text"] and link["votes"] > 0 for link in links))

    def test_search_with_scope_and_paging(self):
        payload = self.ok("search", "holy", "spirit", "-nt", "--page", "2", "--limit", "5")
        self.assertEqual(payload["scope"]["label"], "nt")
        self.assertEqual(payload["page"], 2)
        self.assertEqual([r["rank"] for r in payload["results"]], [6, 7, 8, 9, 10])
        self.assertTrue(all(r["book"] in payload["scope"]["books"] for r in payload["results"]))

    # --- errors ---------------------------------------------------------
    def test_sticky_default_refused(self):
        self.fails(2, "sticky_default_in_json", "-v", "kjv", "John", "3:16")
        self.fails(2, "sticky_default_in_json", "version", "kjv")
        self.assertEqual(self.config_text(), '{"bible": "esv"}')

    def test_usage_errors(self):
        self.fails(2, "usage", "strongs")
        self.fails(2, "usage", "-B")
        self.fails(2, "usage", "John", "3:16", "--bogus")
        self.fails(2, "unknown_edition", "-B", "xyz", "John", "3:16")
        self.fails(2, "unsupported_in_json", "define", "grace")

    def test_not_found(self):
        self.fails(3, "not_found", "Hezekiah", "4:1")
        self.fails(3, "not_found", "strongs", "G99999")
        self.fails(3, "not_found", "search", "zzzqqqxx")

    def test_pty_does_not_prompt(self):
        if not shutil.which("script") or sys.platform != "linux":
            self.skipTest("needs util-linux script")
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env["HOME"] = self.home
        cmd = f"{sys.executable} {LEX} --json study John 3:16"
        proc = subprocess.run(["script", "-qec", cmd, "/dev/null"], cwd=ROOT, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout[-500:])
        self.assertEqual(json.loads(proc.stdout.strip())["command"], "study")


class StrongsDefinitionCleanupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = load_lex_module()

    def test_plain_definitions_unchanged(self):
        self.assertEqual(self.lex.clean_strongs_definition("a missile, i.e. javelin"), ("a missile, i.e. javelin", []))
        self.assertEqual(self.lex.clean_strongs_definition(None), ("", []))
        self.assertEqual(self.lex.clean_strongs_definition("{not json"), ("{not json", []))

    def test_gaps_are_filled_in_order(self):
        raw = '{"_":" corresponding to  and\\n ); Akeldama","strongsref":[{"$":{"language":"HEBREW","strongs":"02506"}},{"$":{"language":"HEBREW","strongs":"01818"}}]}'
        self.assertEqual(self.lex.clean_strongs_definition(raw), ("corresponding to H2506 and H1818); Akeldama", ["H2506", "H1818"]))

    def test_greek_word_fill(self):
        raw = '{"_": " the best meal\\n (or breakfast; perhaps from  (\\"early\\")), i.e. luncheon", "greek": [{"$": {"unicode": "ἦρι"}}]}'
        self.assertEqual(self.lex.clean_strongs_definition(raw)[0], 'the best meal (or breakfast; perhaps from ἦρι ("early")), i.e. luncheon')

    def test_unmatched_gaps_fall_back_to_see_list(self):
        raw = '{"_":" properly, a story","strongsref":[{"$":{"language":"GREEK","strongs":"1868"}}]}'
        self.assertEqual(self.lex.clean_strongs_definition(raw), ("properly, a story (see G1868)", ["G1868"]))

    def test_no_raw_json_left_in_any_entry(self):
        app_cls = next(v for v in vars(self.lex).values() if isinstance(v, type) and hasattr(v, "find_strongs_rows"))
        app = app_cls()
        rows = app.strongs_db.query("SELECT number, definition FROM strongs WHERE definition LIKE '{%'")
        self.assertGreaterEqual(len(rows), 200)
        for number, definition in rows:
            text, _refs = self.lex.clean_strongs_definition(definition)
            self.assertNotIn('"_"', text, number)
            self.assertNotIn('{"', text, number)
            self.assertNotIn("\n", text, number)


class StrongsMarkupRegressionTest(unittest.TestCase):
    """The 2.6.5 MarkupError list reported by the research agent: all must render (fixed in 2.6.6)."""

    NUMBERS = ["G1997", "G1577", "G4864", "G1459", "G26", "G458", "G4129", "G5594"]

    def test_reported_numbers_render(self):
        home = tempfile.mkdtemp(prefix="lex-markup-regression-")
        try:
            with open(os.path.join(home, ".lex_config.json"), "w", encoding="utf-8") as fh:
                fh.write('{"bible": "esv"}')
            env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
            env.update({"HOME": home, "LEX_NO_COLOR": "1", "COLUMNS": "100", "TERM": "dumb"})
            for number in self.NUMBERS:
                proc = subprocess.run([sys.executable, LEX, "strongs", number], cwd=ROOT, env=env,
                                      input="q\n", capture_output=True, text=True, timeout=120)
                out = proc.stdout + proc.stderr
                self.assertEqual(proc.returncode, 0, f"{number}: {out[-1500:]}")
                for bad in ("Traceback", "MarkupError"):
                    self.assertNotIn(bad, out, number)
                self.assertIn(f"Greek Lexicon: {number}", out)
                self.assertNotIn('{"_"', out, f"{number} shows raw JSON")
        finally:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

"""Tests for Matthew Poole and John Gill commentaries (issue #18).

Covers the MySword -> Lex converter (scripts/build_commentary_mybible.py), the
shipped runtime-data/commentaries/{matthew_poole,john_gill}.db files, and the
`lex commentary` wiring (display order, JSON sections, missing DBs skipped).

Run: python3 -m pytest tests/test_commentaries.py
"""
import contextlib
import importlib.util
import io
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
SCRIPTS = os.path.join(ROOT, "scripts")
COMMENTARY_DIR = os.path.join(ROOT, "runtime-data", "commentaries")
POOLE_DB = os.path.join(COMMENTARY_DIR, "matthew_poole.db")
GILL_DB = os.path.join(COMMENTARY_DIR, "john_gill.db")
POOLE_SOURCE = "Matthew Poole's English Annotations on the Holy Bible"
GILL_SOURCE = "John Gill's Exposition of the Entire Bible"

sys.path.insert(0, SCRIPTS)
import build_commentary_mybible as builder  # noqa: E402


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_commentaries_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


class NoteConversionTest(unittest.TestCase):
    def test_bold_lemma_hugs_words_and_keeps_following_punctuation(self):
        plain, md = builder.note_to_text("<P><B>For God so loved the world</B>,.... The <I>Persic </I>version</P>")
        self.assertEqual(plain, "For God so loved the world,.... The Persic version")
        self.assertEqual(md, "**For God so loved the world**,.... The *Persic* version")

    def test_mid_sentence_breaks_before_links_and_hebrew_are_joined(self):
        plain, _ = builder.note_to_text(
            "<P>the earth,</P> <P> <a class='bible' href='#b18.38.6'>Job 38:6</a> but rather</P>"
            "<P>for the word</P> <P><SPAN LANG='hi-IN'><FONT FACE='serif'>\u05d0\u05ea </SPAN></FONT>set</P>"
        )
        self.assertEqual(plain, "the earth, Job 38:6 but rather for the word \u05d0\u05ea set")

    def test_headings_and_sentences_stay_separate_paragraphs(self):
        plain, md = builder.note_to_text("<P><B>INTRODUCTION TO GENESIS 1</B></P> <P>This chapter.</P><P>Next one.</P>")
        self.assertEqual(plain, "INTRODUCTION TO GENESIS 1\n\nThis chapter.\n\nNext one.")
        self.assertEqual(md.split("\n\n")[0], "**INTRODUCTION TO GENESIS 1**")

    def test_markdown_syntax_in_source_text_is_escaped(self):
        _, md = builder.note_to_text("<P>The Lord [is] my *shepherd* &amp; a_b</P><P>1. not a list</P>")
        self.assertEqual(md, "The Lord \\[is\\] my \\*shepherd\\* & a\\_b\n\n\\1. not a list")

    def test_greek_and_hebrew_are_preserved(self):
        plain, md = builder.note_to_text("<P>\u03bb\u03cc\u03b3\u03bf\u03c2 and <FONT>\u05d1\u05e8\u05d0\u05e9\u05d9\u05ea</FONT></P>")
        self.assertIn("\u03bb\u03cc\u03b3\u03bf\u03c2", plain)
        self.assertIn("\u05d1\u05e8\u05d0\u05e9\u05d9\u05ea", md)

    def test_unbalanced_source_emphasis_never_leaves_a_stray_bold_marker(self):
        _, md = builder.note_to_text("<P><B>Never closed</P><P>tail</P>")
        for paragraph in md.split("\n\n"):
            self.assertEqual(len(builder._BOLD_MARK.findall(paragraph)) % 2, 0, md)
        _, md = builder.note_to_text("<P><B></B>empty <I> </I>marks</P>")
        self.assertEqual(md, "empty marks")

    def test_leaked_scripref_markup_is_unwrapped(self):
        html = ('<P>in Matthew;</P> <P>&lt;scripRef version="Gill" content="[See comments on Mt 5:39.&lt;br&gt;'
                'See Gill on ]" passage="Mt 5:39.</P> <P>See Gill on "&gt;Mt 5:40.</P>')
        plain, _ = builder.note_to_text(html)
        self.assertNotIn("scripRef", plain)
        self.assertNotIn("<", plain)
        self.assertIn("See Gill on Mt 5:40.", plain)


class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.tmp.name, "sample.cmt.mybible")
        conn = sqlite3.connect(self.source)
        conn.executescript(
            """
            CREATE TABLE commentary (id INTEGER PRIMARY KEY, book INTEGER, chapter INTEGER,
                                     fromverse INTEGER, toverse INTEGER, data TEXT);
            CREATE TABLE details (title TEXT, version TEXT, versiondate TEXT);
            INSERT INTO details VALUES ('Sample', '1.0', '2020-01-01');
            INSERT INTO commentary (book, chapter, fromverse, toverse, data) VALUES
              (43, 3, 16, 16, '<P><B>For God so loved</B>, note.</P>'),
              (43, 3, 0, 0, '<P>Chapter summary.</P>'),
              (43, 0, 0, 0, '<P>About John.</P>'),
              (43, 1, 1, 0, '<P>Verse one.</P>'),
              (43, 3, 17, 18, '<P>Two verses.</P>'),
              (43, 3, 19, 19, '<P> </P>'),
              (99, 1, 1, 1, '<P>Not a book.</P>');
            """
        )
        conn.commit()
        conn.close()
        self.out = os.path.join(self.tmp.name, "out.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_builds_lex_commentary_schema(self):
        stats = builder.build_commentary("gill", self.source, self.out)
        self.assertEqual(stats["sections"], 5)
        self.assertEqual(stats["empty_skipped"], 1)
        self.assertEqual(stats["unknown_book_skipped"], 1)
        conn = sqlite3.connect(self.out)
        rows = conn.execute(
            "SELECT reference, book, chapter, section_order, section_title, verse_start, verse_end, content, source "
            "FROM commentary ORDER BY chapter, section_order"
        ).fetchall()
        self.assertEqual(rows[0], ("gill:John:1", "John", 1, 1, "Introduction to John", None, None, None, GILL_SOURCE))
        self.assertEqual(rows[1][4:7], ("John 1:1", 1, 1))
        self.assertEqual([r[4:7] for r in rows[2:]], [
            ("Chapter Introduction", None, None), ("John 3:16", 16, 16), ("John 3:17-18", 17, 18),
        ])
        self.assertEqual([r[3] for r in rows[2:]], [1, 2, 3])
        meta = dict(conn.execute("SELECT key, value FROM metadata"))
        self.assertIn("Public domain", meta["license"])
        self.assertEqual(len(meta["source_sha256"]), 64)
        conn.close()

    def test_output_is_deterministic(self):
        builder.build_commentary("poole", self.source, self.out)
        first = open(self.out, "rb").read()
        builder.build_commentary("poole", self.source, self.out)
        self.assertEqual(first, open(self.out, "rb").read())

    def test_cli_rejects_missing_source(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "build_commentary_mybible.py"), "gill",
             os.path.join(self.tmp.name, "missing.cmt.mybible"), self.out],
            capture_output=True, text=True, timeout=60,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not found", proc.stderr)


# (book, chapter, verse, words expected in Poole, words expected in Gill)
SPOT_CHECKS = [
    ("Genesis", 1, 1, "In the beginning", "In the beginning God created"),
    ("Genesis", 3, 15, "enmity", "enmity"),
    ("Exodus", 3, 14, "I am that I am", "I am that I am"),
    ("Leviticus", 16, 8, "lot", "lots"),
    ("Deuteronomy", 6, 4, "One", "Hear, O Israel"),
    ("Psalms", 23, 1, "shepherd", "my shepherd"),
    ("Psalms", 110, 1, "The Lord", "The Lord said unto my Lord"),
    ("Proverbs", 8, 22, "Possessed me", "possessed me"),
    ("Isaiah", 7, 14, "sign", "sign"),
    ("Isaiah", 53, 5, "wounded", "wounded for our transgressions"),
    ("Jeremiah", 31, 31, "Heb 8:8", "Heb 8:8"),
    ("Daniel", 9, 25, "Seven weeks", "Know, therefore"),
    ("Micah", 5, 2, "Beth-lehem", "Bethlehem Ephratah"),
    ("Malachi", 4, 5, "Elijah", "Elijah the prophet"),
    ("Matthew", 16, 18, "Peter", "I say also unto thee"),
    ("John", 1, 1, "In the beginning", "In the beginning was the word"),
    ("John", 3, 16, "so loved the world", "For God so loved the world"),
    ("Romans", 9, 13, "Mal 1:2", "Jacob have I loved"),
    ("Hebrews", 6, 4, "apostacy", "once enlightened"),
    ("1 John", 5, 7, "testimony", "three that bear record in heaven"),
    ("Revelation", 20, 4, "Thrones", "thrones"),
    ("Jude", 1, 9, "Michael the archangel", "Michael the archangel"),
]


@unittest.skipUnless(os.path.exists(POOLE_DB) and os.path.exists(GILL_DB), "commentary data not installed")
class ShippedCommentaryDataTest(unittest.TestCase):
    def query(self, path, sql, params=()):
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def test_whole_bible_coverage_and_counts(self):
        lex = load_lex_module()
        for path, minimum, source in ((POOLE_DB, 25000, POOLE_SOURCE), (GILL_DB, 32000, GILL_SOURCE)):
            books = {row[0] for row in self.query(path, "SELECT DISTINCT book FROM commentary")}
            self.assertEqual(books, set(lex.BIBLE_BOOKS[:66]), path)
            self.assertGreaterEqual(self.query(path, "SELECT COUNT(*) FROM commentary")[0][0], minimum)
            self.assertEqual(self.query(path, "SELECT DISTINCT source FROM commentary"), [(source,)])
            meta = dict(self.query(path, "SELECT key, value FROM metadata"))
            self.assertIn("Public domain", meta["license"])
            self.assertIn("mysword-bible.info", meta["source_url"])
            # No HTML survives and every paragraph's bold markers pair up.
            for (md,) in self.query(path, "SELECT markdown FROM commentary"):
                self.assertIsNone(re.search(r"(?<!\\)<[A-Za-z/]", md), md[:200])
                for paragraph in md.split("\n\n"):
                    self.assertEqual(len(builder._BOLD_MARK.findall(paragraph)) % 2, 0, paragraph[:200])

    def test_original_languages_are_kept(self):
        hebrew = "SELECT COUNT(*) FROM commentary WHERE markdown GLOB '*[\u05d0-\u05ea]*'"
        self.assertGreater(self.query(GILL_DB, hebrew)[0][0], 7000)
        self.assertGreater(self.query(POOLE_DB, hebrew)[0][0], 50)

    def test_spot_checks(self):
        sql = ("SELECT markdown FROM commentary WHERE book = ? AND chapter = ? "
               "AND verse_start <= ? AND verse_end >= ? ORDER BY section_order")
        for book, chapter, verse, poole_words, gill_words in SPOT_CHECKS:
            for path, words in ((POOLE_DB, poole_words), (GILL_DB, gill_words)):
                with self.subTest(db=os.path.basename(path), ref=f"{book} {chapter}:{verse}"):
                    rows = self.query(path, sql, (book, chapter, verse, verse))
                    self.assertTrue(rows)
                    text = " ".join(r[0] for r in rows).replace("*", "").lower()
                    self.assertIn(words.lower(), text)

    def test_book_introduction_is_shown_with_chapter_one(self):
        for path in (POOLE_DB, GILL_DB):
            first = self.query(path, "SELECT section_title, verse_start FROM commentary "
                                     "WHERE book = 'Genesis' AND chapter = 1 ORDER BY section_order LIMIT 1")
            self.assertEqual(first, [("Introduction to Genesis", None)])


@unittest.skipUnless(os.path.exists(POOLE_DB) and os.path.exists(GILL_DB), "commentary data not installed")
class LexCommentaryWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = load_lex_module()
        cls.agent = cls.lex.LexAgent(bible_id="kjv")

    def test_json_lists_all_four_commentators_in_order(self):
        payload = self.lex.json_commentary(self.agent, "kjv", "John 3:16")
        order = []
        for section in payload["sections"]:
            if section["commentator"] not in order:
                order.append(section["commentator"])
        self.assertEqual(order, ["Matthew Henry", "John Calvin", "Matthew Poole", "John Gill"])
        gill = [s for s in payload["sections"] if s["commentator"] == "John Gill"]
        self.assertEqual((gill[0]["verse_start"], gill[0]["verse_end"]), (16, 16))
        self.assertTrue(gill[0]["text"].startswith("For God so loved the world"))
        self.assertNotIn("**", gill[0]["text"])

    def test_psalm_lookup_uses_canonical_book_name(self):
        # KJV spells the book "Psalm"; the commentary databases say "Psalms".
        payload = self.lex.json_commentary(self.agent, "kjv", "Psalm 23:1")
        commentators = {s["commentator"] for s in payload["sections"]}
        self.assertTrue({"Matthew Poole", "John Gill"} <= commentators, commentators)

    def test_missing_databases_are_skipped(self):
        agent = self.lex.LexAgent(bible_id="kjv")
        agent.poole_db = None
        agent.gill_db = None
        payload = self.lex.json_commentary(agent, "kjv", "John 3:16")
        self.assertEqual({s["commentator"] for s in payload["sections"]}, {"Matthew Henry", "John Calvin"})
        agent.henry_db = agent.calvin_db = None
        with self.assertRaises(self.lex.JsonExit) as ctx:
            self.lex.json_commentary(agent, "kjv", "John 3:16")
        self.assertEqual(ctx.exception.code, "not_found")

    def test_terminal_view_shows_poole_and_gill_panels(self):
        buffer = io.StringIO()
        console = self.lex.Console(file=buffer, width=100, force_terminal=False, theme=self.lex.console.theme if hasattr(self.lex.console, "theme") else None)
        old_console = self.lex.console
        self.lex.console = console
        try:
            with contextlib.redirect_stdout(buffer):
                self.assertTrue(self.agent.display_commentary("John 3:16"))
        finally:
            self.lex.console = old_console
        out = buffer.getvalue()
        self.assertIn(POOLE_SOURCE, out)
        self.assertIn(GILL_SOURCE, out)
        self.assertLess(out.index(POOLE_SOURCE), out.index(GILL_SOURCE))


if __name__ == "__main__":
    unittest.main()

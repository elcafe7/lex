"""Brenton's English Septuagint (1851) edition, `-B brenton` (issue #33).

Packager tests use a small VPL fixture shaped like eBible.org eng-Brenton.
Database tests run against runtime-data/bible_versions/brenton.db and skip
when it is not installed; the alignment checks also need lxx.db.

Run: python3 -m unittest tests.test_brenton_edition
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import lex  # noqa: E402
import package_bible  # noqa: E402

FIXTURE_VPL = ROOT / "tests" / "fixtures" / "brenton_sample.vpl"
BIBLE_DIR = ROOT / "runtime-data" / "bible_versions"
BRENTON_DB = BIBLE_DIR / "brenton.db"
LXX_DB = BIBLE_DIR / "lxx.db"
LEX = ROOT / "lex.py"


class PackageBrentonTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "brenton.db")
        self.stats = package_bible.package_brenton_1851(str(FIXTURE_VPL), self.db_path)
        self.conn = sqlite3.connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def text(self, ref):
        row = self.conn.execute("SELECT text FROM bible WHERE reference = ?", (ref,)).fetchone()
        return row[0] if row else None

    def test_metadata(self):
        meta = dict(self.conn.execute("SELECT key, value FROM metadata"))
        self.assertEqual(meta["edition_id"], "brenton")
        self.assertEqual(meta["reference_prefix"], "brenton")
        self.assertEqual(meta["language"], "en")
        self.assertIn("public domain", meta["source"])

    def test_lettered_verses_are_appended_not_dropped(self):
        text = self.text("brenton:Genesis:31:50")
        self.assertIn("God [is] witness", text)
        self.assertTrue(text.endswith("this pillar are a witness."))
        self.assertIsNone(self.text("brenton:Genesis:31:51"))
        self.assertIn("rested quiet in the palace.]", self.text("brenton:Esther:1:1"))
        self.assertEqual(self.stats["lettered_verses_merged"], 2)

    def test_esdras_b_becomes_nehemiah_and_neh_duplicate_is_dropped(self):
        self.assertEqual(self.text("brenton:Ezra:1:1")[:20], "And in the first yea")
        self.assertIsNone(self.text("brenton:Ezra:11:1"))
        self.assertEqual(self.text("brenton:Nehemiah:1:1"), "The words of Neemias the son of Chelcia.")
        # Septuagint numbering (EZR 13:37), not the re-versified NEH 4:5.
        self.assertEqual(self.text("brenton:Nehemiah:3:37"), "and do not cover iniquity.")
        self.assertIsNone(self.text("brenton:Nehemiah:4:5"))
        self.assertEqual(self.stats["neh_duplicate_verses_dropped"], 2)

    def test_sirach_6_numbers_restored(self):
        self.assertTrue(self.text("brenton:Sirach:6:1").startswith("Instead of a friend"))
        self.assertTrue(self.text("brenton:Sirach:6:2").startswith("Extol not thyself"))

    def test_brackets_kept_and_empty_verse_skipped(self):
        self.assertEqual(self.text("brenton:Genesis:2:4")[:20], "This [is] the book o")
        self.assertIsNone(self.text("brenton:Proverbs:30:1"))
        self.assertEqual(self.stats["empty_verses_skipped"], 1)

    def test_book_names_and_order(self):
        books = []
        for (ref,) in self.conn.execute("SELECT reference FROM bible ORDER BY id"):
            book = ref.split(":")[1]
            if book not in books:
                books.append(book)
        self.assertEqual(books, [
            "Genesis", "1 Samuel", "Ezra", "Nehemiah", "Esther", "Psalms", "Daniel",
            "Tobit", "Sirach", "1 Maccabees", "Prayer of Manasseh",
        ])

    def test_fts_matches_bible(self):
        bible = self.conn.execute("SELECT COUNT(*) FROM bible").fetchone()[0]
        fts = self.conn.execute("SELECT COUNT(*) FROM bible_fts").fetchone()[0]
        self.assertEqual(bible, fts)

    def test_rejects_unknown_codes_and_orphan_letters(self):
        for line, message in (("XYZ 1:1 text", "Unknown Brenton book codes"),
                              ("GEN 1:5a orphan", "without its base verse"),
                              ("not a vpl line", "unrecognised")):
            with self.subTest(line=line):
                path = os.path.join(self.tmpdir.name, "bad.vpl")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("GEN 1:1 In the beginning.\n" + line + "\n")
                with self.assertRaisesRegex(ValueError, message):
                    package_bible.package_brenton_1851(path, os.path.join(self.tmpdir.name, "bad.db"))


class BrentonRegistrationTest(unittest.TestCase):
    def test_registered_without_changing_lxx(self):
        self.assertEqual(lex.BIBLE_VERSIONS["brenton"]["name"], "Brenton English Septuagint (1851)")
        self.assertEqual(lex.BIBLE_VERSIONS["brenton"]["file"], "bible_versions/brenton.db")
        self.assertIn("brenton", lex.CANONICAL_BIBLE_IDS)
        self.assertEqual(lex.BIBLE_VERSIONS["lxx"], {"name": "Septuagint (Rahlfs 1935)", "file": "bible_versions/lxx.db"})

    def test_bracketed_words_survive_clean_text(self):
        clean = lex.LexAgent.clean_text(None, "This [is] the book [i]x[/i] [wj]y[/wj]")
        self.assertEqual(clean, "This [is] the book x y")


@unittest.skipUnless(BRENTON_DB.exists(), "brenton.db not installed")
class BrentonDatabaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(BRENTON_DB)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def text(self, ref):
        row = self.conn.execute("SELECT text FROM bible WHERE reference = ?", (f"brenton:{ref}",)).fetchone()
        return row[0] if row else None

    def test_manifest_checksum(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        entry = manifest["assets"]["runtime-data/bible_versions/brenton.db"]
        digest = hashlib.sha256(BRENTON_DB.read_bytes()).hexdigest()
        self.assertEqual(entry["hash"], digest)
        self.assertEqual(entry["size"], BRENTON_DB.stat().st_size)

    def test_canon_and_counts(self):
        books = []
        for (ref,) in self.conn.execute("SELECT reference FROM bible ORDER BY id"):
            book = ref.split(":")[1]
            if book not in books:
                books.append(book)
        self.assertEqual(len(books), 53)
        self.assertEqual(books[:5], ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"])
        self.assertEqual(books[38], "Malachi")
        self.assertEqual(books[39:], [name for _, name in package_bible.BRENTON_1851_BOOKS][39:])
        self.assertNotIn("Matthew", books)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM bible").fetchone()[0], 28302)

    def test_representative_references(self):
        cases = {
            "Genesis:1:1": "In the beginning God made the heaven and the earth.",
            "Psalms:22:1": "A Psalm of David. The Lord tends me as a shepherd, and I shall want nothing.",
            "Nehemiah:3:37": "and do not cover [their] iniquity.",
        }
        for ref, expected in cases.items():
            with self.subTest(ref=ref):
                self.assertEqual(self.text(ref), expected)
        self.assertTrue(self.text("Tobit:1:1").startswith("The book of the words of Tobit"))
        self.assertTrue(self.text("Sirach:6:1").startswith("Instead of a friend become not an enemy"))
        self.assertIn("understanding to Solomon", self.text("1 Kings:2:35"))  # merged 2:35a
        self.assertTrue(self.text("Psalms:151:1").startswith("This Psalm is a genuine one of David"))
        self.assertTrue(self.text("Prayer of Manasseh:1:1").startswith("O Lord Almighty"))
        self.assertTrue(self.text("Esther:1:1").startswith("[In the second year"))

    @unittest.skipUnless(LXX_DB.exists(), "lxx.db not installed")
    def test_alignment_with_greek_lxx(self):
        lxx = sqlite3.connect(LXX_DB)

        def keys(conn, prefix, book):
            rows = conn.execute("SELECT reference FROM bible WHERE reference GLOB ?", (f"{prefix}:{book}:*",))
            return {tuple(int(x) for x in ref.rsplit(":", 2)[1:]) for (ref,) in rows if not ref.endswith(":0")}

        exact = {"Genesis": "Genesis", "Exodus": "Exodus", "Psalms": "Psalms", "Isaiah": "Isaiah",
                 "Joshua": "Joshua B", "Ezra": "Ezra (Esdras B/II: 1-10)", "Esther": "Esther (with additions)",
                 "1 Maccabees": "I Maccabees", "2 Maccabees": "II Maccabees", "3 Maccabees": "III Maccabees"}
        try:
            for brenton_book, lxx_book in exact.items():
                with self.subTest(book=brenton_book):
                    self.assertEqual(keys(self.conn, "brenton", brenton_book), keys(lxx, "lxx", lxx_book))
            # Nehemiah follows Esdras B numbering: every Brenton verse exists in lxx.
            neh = keys(self.conn, "brenton", "Nehemiah")
            self.assertLessEqual(neh, keys(lxx, "lxx", "Nehemiah (Esdras B/II: 11-23)"))
        finally:
            lxx.close()


@unittest.skipUnless(BRENTON_DB.exists(), "brenton.db not installed")
class BrentonCliTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-brenton-")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_lex(self, *args):
        env = dict(os.environ, HOME=self.home, NO_COLOR="1")
        return subprocess.run([sys.executable, str(LEX), *args], capture_output=True, text=True,
                              env=env, timeout=120)

    def test_read_plain(self):
        result = self.run_lex("--plain", "-B", "brenton", "Genesis", "2:4")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("This [is] the book", result.stdout)

    def test_read_json(self):
        for flag in ("--json", "-json"):
            with self.subTest(flag=flag):
                result = self.run_lex(flag, "-B", "brenton", "Tobit", "1:1")
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["edition"], "brenton")
                verse = payload["passages"][0]["verses"][0]
                self.assertEqual(verse["key"], "brenton:Tobit:1:1")
                self.assertIn("[son] of Tobiel", verse["text"])

    def test_search(self):
        result = self.run_lex("--json", "-B", "brenton", "search", "shepherd", "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertGreater(payload["total"], 0)
        self.assertTrue(payload["results"][0]["key"].startswith("brenton:"))

    def test_lxx_still_greek(self):
        result = self.run_lex("--json", "-B", "lxx", "Genesis", "1:1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ἐν ἀρχῇ", json.loads(result.stdout)["passages"][0]["verses"][0]["text"].lower())

    def test_help_spellings_with_brenton(self):
        for flag in ("-h", "--help", "-help", "--h"):
            with self.subTest(flag=flag):
                result = self.run_lex("-B", "brenton", "search", flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("brenton", result.stdout)


if __name__ == "__main__":
    unittest.main()

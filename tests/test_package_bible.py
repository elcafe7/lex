#!/usr/bin/env python3
"""Tests for Bible edition packagers."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import package_bible  # noqa: E402

FIXTURE_VPL = ROOT / "tests" / "fixtures" / "dra_sample.vpl"


class PackageDra1899Test(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "dra.db")
        package_bible.package_dra_1899(str(FIXTURE_VPL), self.db_path)
        self.conn = sqlite3.connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def test_writes_dra_metadata(self):
        rows = dict(self.conn.execute("SELECT key, value FROM metadata"))
        self.assertEqual(rows["edition_id"], "dra")
        self.assertEqual(rows["edition_name"], "Douay-Rheims (1899 American Edition)")
        self.assertEqual(rows["language"], "en")
        self.assertEqual(rows["reference_prefix"], "dra")

    def test_maps_modern_book_names(self):
        refs = [row[0] for row in self.conn.execute("SELECT reference FROM bible ORDER BY id")]
        self.assertIn("dra:1 Samuel:1:1", refs)
        self.assertIn("dra:1 Kings:1:1", refs)
        self.assertNotIn("dra:3 Kings:1:1", refs)

    def test_includes_deuterocanonical_books(self):
        refs = {row[0] for row in self.conn.execute("SELECT reference FROM bible")}
        self.assertIn("dra:Tobit:1:1", refs)
        self.assertIn("dra:Wisdom:1:1", refs)
        self.assertIn("dra:1 Maccabees:1:1", refs)

    def test_preserves_verse_text(self):
        text = self.conn.execute(
            "SELECT text FROM bible WHERE reference = ?",
            ("dra:John:3:16",),
        ).fetchone()[0]
        self.assertTrue(text.startswith("For God so loved the world"))

    def test_orders_rows_by_catholic_canon(self):
        books = [
            row[0]
            for row in self.conn.execute(
                "SELECT DISTINCT substr(reference, 5, instr(substr(reference, 5), ':') - 1) FROM bible ORDER BY id"
            )
        ]
        self.assertEqual(
            books,
            [
                "Genesis",
                "1 Samuel",
                "1 Kings",
                "Nehemiah",
                "Tobit",
                "Esther",
                "Song of Solomon",
                "Wisdom",
                "1 Maccabees",
                "John",
                "Revelation",
            ],
        )

    def test_builds_fts_rows(self):
        count = self.conn.execute("SELECT COUNT(*) FROM bible_fts").fetchone()[0]
        bible_count = self.conn.execute("SELECT COUNT(*) FROM bible").fetchone()[0]
        self.assertEqual(count, bible_count)
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()

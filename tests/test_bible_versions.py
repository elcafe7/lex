#!/usr/bin/env python3
"""Tests for registered Bible edition identifiers."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lex  # noqa: E402


class BibleVersionsTest(unittest.TestCase):
    def test_registers_dra_edition(self):
        self.assertIn("dra", lex.BIBLE_VERSIONS)
        self.assertEqual(
            lex.BIBLE_VERSIONS["dra"]["name"],
            "Douay-Rheims (1899 American Edition)",
        )
        self.assertEqual(
            lex.BIBLE_VERSIONS["dra"]["file"],
            "bible_versions/dra.db",
        )


if __name__ == "__main__":
    unittest.main()

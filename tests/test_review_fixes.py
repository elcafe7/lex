"""Regression tests for findings fixed after the Gemini code review."""

import hashlib
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import download_lxxmorph  # noqa: E402


def load_lex():
    spec = importlib.util.spec_from_file_location("lex_review_fixes", ROOT / "lex.py")
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


class LxxDownloadIntegrityTest(unittest.TestCase):
    def test_committed_manifest_covers_each_declared_source_once(self):
        checksums = download_lxxmorph.load_checksums(
            ROOT / "scripts" / "lxxmorph.sha256"
        )
        self.assertEqual(set(checksums), set(download_lxxmorph.FILES))

    def test_checksum_mismatch_does_not_replace_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "source.mlxx")
            with open(target, "wb") as handle:
                handle.write(b"known-good")
            expected = hashlib.sha256(b"expected").hexdigest()

            def fake_download(command, check):
                self.assertTrue(check)
                with open(command[-1], "wb") as handle:
                    handle.write(b"wrong")

            with mock.patch.object(download_lxxmorph.subprocess, "run", fake_download):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    download_lxxmorph.fetch_verified("https://example.test/source", target, expected)
            with open(target, "rb") as handle:
                self.assertEqual(handle.read(), b"known-good")


class VerseWebValidationTest(unittest.TestCase):
    def test_chapter_only_web_request_explains_single_verse_requirement(self):
        lex = load_lex()
        agent = object.__new__(lex.LexAgent)
        agent.normalize_ref = lambda _query: ("John 3", "John", 3, None, None)
        output = io.StringIO()
        with mock.patch.object(lex, "console", lex.Console(file=output, force_terminal=False)):
            self.assertFalse(agent.display_verse_web("John 3"))
        self.assertIn("needs a single verse", output.getvalue())

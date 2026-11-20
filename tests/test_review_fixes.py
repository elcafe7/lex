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


def load_indexer():
    spec = importlib.util.spec_from_file_location("indexer_review_fixes", ROOT / "indexer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
                self.assertEqual(command[command.index("--proto") + 1], "=https")
                self.assertEqual(
                    command[command.index("--max-filesize") + 1],
                    download_lxxmorph.CURL_MAX_FILESIZE,
                )
                dest = command[command.index("-o") + 1]
                with open(dest, "wb") as handle:
                    handle.write(b"wrong")

            with mock.patch.object(download_lxxmorph.subprocess, "run", fake_download):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    download_lxxmorph.fetch_verified("https://example.test/source", target, expected)
            with open(target, "rb") as handle:
                self.assertEqual(handle.read(), b"known-good")

    def test_escaping_out_path_creates_no_directory_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "workspace", "runtime-data")
            os.makedirs(root)
            # Same shape as --out runtime-data/new/../../../x: realpath lands
            # at tmp/x, outside runtime-data, and must not be created.
            raw = os.path.join(root, "new", "..", "..", "..", "x")
            escaped = os.path.realpath(raw)
            self.assertEqual(escaped, os.path.join(tmp, "x"))
            with mock.patch.object(download_lxxmorph, "ROOT", root):
                with self.assertRaises(download_lxxmorph.UnsafePathError):
                    download_lxxmorph.resolve_output_dir(raw)
            self.assertFalse(os.path.exists(escaped))
            self.assertFalse(os.path.exists(os.path.join(root, "new")))

    def test_missing_out_subdir_is_created_after_containment_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "runtime-data")
            os.makedirs(root)
            wanted = os.path.join(root, "sources", "lxxmorph")
            with mock.patch.object(download_lxxmorph, "ROOT", root):
                resolved = download_lxxmorph.resolve_output_dir(wanted)
            self.assertEqual(resolved, os.path.realpath(wanted))
            self.assertTrue(os.path.isdir(resolved))


class VerseWebValidationTest(unittest.TestCase):
    def test_chapter_only_web_request_explains_single_verse_requirement(self):
        lex = load_lex()
        agent = object.__new__(lex.LexAgent)
        agent.normalize_ref = lambda _query: ("John 3", "John", 3, None, None)
        output = io.StringIO()
        with mock.patch.object(lex, "console", lex.Console(file=output, force_terminal=False)):
            self.assertFalse(agent.display_verse_web("John 3"))
        self.assertIn("needs a single verse", output.getvalue())


class HistoricalDocumentErrorHandlingTest(unittest.TestCase):
    def test_invalid_utf8_document_is_logged_and_skipped(self):
        indexer = load_indexer()
        with tempfile.TemporaryDirectory() as tmp:
            docs = pathlib.Path(tmp) / "theolog-ai" / "data" / "historical-documents"
            docs.mkdir(parents=True)
            (docs / "bad.json").write_bytes(b"\xff\xfe")
            conn = __import__("sqlite3").connect(":memory:")
            conn.execute("CREATE VIRTUAL TABLE dictionary_fts USING fts5(topic, content, source)")
            output = io.StringIO()
            with mock.patch.object(indexer, "BASE_DIR", tmp), mock.patch("sys.stderr", output):
                indexer.load_historical_docs(conn)
            self.assertIn("Skipping unreadable historical document bad.json", output.getvalue())
            self.assertEqual(conn.execute("SELECT count(*) FROM dictionary_fts").fetchone()[0], 0)
            conn.close()

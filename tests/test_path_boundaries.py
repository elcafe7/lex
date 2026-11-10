"""Filesystem boundaries for paths built from untrusted input (#6, #8, #9).

CodeQL py/path-injection: anything that comes from downloaded or updated data
(the `lex --update` manifest, the manuscript profiles manifest, a fetched
checkout's directory listing) or from the environment must stay inside a known
Lex directory. Covers good paths and attacks: `../`, encoded `..%2f`,
absolute paths, NUL bytes, and symlinks that escape the base.

Run: python3 -m unittest discover -s tests
"""
import hashlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

from rich.console import Console

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import safe_paths  # noqa: E402


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_paths_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


LEXMOD = load_lex_module()

ATTACKS = [
    "../evil.json",
    "a/../../evil.json",
    "..\\evil.json",
    "..%2fevil.json",
    "..%2Fevil.json",
    "%2e%2e/evil.json",
    "/etc/passwd",
    "\\\\server\\share\\x.json",
    "C:\\Windows\\win.ini",
    "a\x00b.json",
    "",
]


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class TempDirs(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="lex-paths-test-"))
        self.base = os.path.join(self.tmp, "data")
        self.outside = os.path.join(self.tmp, "outside")
        os.makedirs(self.base)
        os.makedirs(self.outside)
        with open(os.path.join(self.outside, "secret.json"), "w") as fh:
            fh.write('{"secret": true}')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SafeJoinTest(TempDirs):
    def test_good_relative_path_stays_inside(self):
        path = LEXMOD.safe_join(self.base, "witnesses/verses/john/john-3-16.json")
        self.assertEqual(path, os.path.join(self.base, "witnesses", "verses", "john", "john-3-16.json"))

    def test_attacks_are_rejected(self):
        for attack in ATTACKS:
            with self.subTest(attack=attack):
                with self.assertRaises(LEXMOD.UnsafePathError):
                    LEXMOD.safe_join(self.base, attack)

    def test_symlink_escape_is_rejected(self):
        os.symlink(self.outside, os.path.join(self.base, "link"))
        with self.assertRaises(LEXMOD.UnsafePathError):
            LEXMOD.safe_join(self.base, "link/secret.json")

    def test_symlink_inside_base_is_allowed(self):
        os.makedirs(os.path.join(self.base, "real"))
        os.symlink(os.path.join(self.base, "real"), os.path.join(self.base, "alias"))
        self.assertEqual(LEXMOD.safe_join(self.base, "alias/x.json"), os.path.join(self.base, "real", "x.json"))

    def test_sibling_prefix_is_not_inside(self):
        os.makedirs(self.base + "-evil")
        with self.assertRaises(LEXMOD.UnsafePathError):
            LEXMOD.confine_path(os.path.join(self.base + "-evil", "x.json"), (self.base,))

    def test_confine_path_excludes_the_root_itself(self):
        with self.assertRaises(LEXMOD.UnsafePathError):
            LEXMOD.confine_path(self.base, (self.base,))

    def test_manuscript_asset_shape(self):
        self.assertTrue(LEXMOD.is_manuscript_asset_path("witnesses/manuscripts/10066.json"))
        self.assertTrue(LEXMOD.is_manuscript_asset_path("witnesses-profiles-manifest.json"))
        for bad in ("../x.json", "witnesses/../x.json", "/x.json", "witnesses//x.json", ".x.json",
                    "witnesses/x.txt", "witnesses/x y.json", "witnesses/\u00e9.json", "0" + ".0" * 5000 + ".json"):
            with self.subTest(bad=bad[:40]):
                self.assertFalse(LEXMOD.is_manuscript_asset_path(bad))

    def test_confine_path_rejects_nul(self):
        with self.assertRaises(LEXMOD.UnsafePathError):
            LEXMOD.confine_path(os.path.join(self.base, "a\x00b"), (self.base,))


class UpdateManifestTest(TempDirs):
    """A malicious `lex --update` manifest cannot write outside runtime-data."""

    def manager(self, assets):
        console = Console(record=True, width=120, theme=LEXMOD.custom_theme, file=io.StringIO())
        mgr = LEXMOD.LexUpdateManager(console, data_dir=self.base)
        mgr.fetch_remote_manifest = lambda: {"version": "9.9.9", "assets": assets}
        return mgr

    def test_resolve_asset_path_accepts_normal_assets(self):
        mgr = self.manager({})
        self.assertEqual(mgr.resolve_asset_path("runtime-data/bible_versions/kjv.db"),
                         os.path.join(self.base, "bible_versions", "kjv.db"))

    def test_resolve_asset_path_rejects_attacks(self):
        mgr = self.manager({})
        os.symlink(self.outside, os.path.join(self.base, "link"))
        for attack in ATTACKS + ["link/secret.json"]:
            with self.subTest(attack=attack):
                self.assertIsNone(mgr.resolve_asset_path("runtime-data/" + attack))
        self.assertIsNone(mgr.resolve_asset_path("../runtime-data/x.db"))
        self.assertIsNone(mgr.resolve_asset_path(None))

    def test_malicious_update_entry_writes_nothing_outside(self):
        payload = b"pwned"
        info = {"hash": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
        os.symlink(self.outside, os.path.join(self.base, "link"))
        assets = {
            "runtime-data/../outside/evil.txt": info,
            "runtime-data/..%2foutside%2fevil2.txt": info,
            "runtime-data/" + os.path.join(self.outside, "evil3.txt"): info,
            "runtime-data/link/evil4.txt": info,
            "runtime-data/ok.db": info,
        }
        mgr = self.manager(assets)
        with mock.patch.object(LEXMOD, "open_trusted_https", lambda url, **kw: FakeResponse(payload)):
            self.assertTrue(mgr.perform_update())
        self.assertEqual(sorted(os.listdir(self.outside)), ["secret.json"])
        with open(os.path.join(self.base, "ok.db"), "rb") as fh:
            self.assertEqual(fh.read(), payload)


class ManuscriptAssetTest(TempDirs):
    """Profile paths from the fetched manuscripts manifest are allowlisted."""

    def setUp(self):
        super().setUp()
        self.cache = os.path.join(self.tmp, "cache")
        os.makedirs(self.cache)
        self.patches = [
            mock.patch.object(LEXMOD, "DATA_DIR", self.base),
            mock.patch.object(LEXMOD, "RUNTIME_DATA_DIR", self.base),
            mock.patch.object(LEXMOD, "MANUSCRIPT_CACHE_DIR", self.cache),
            mock.patch.object(LEXMOD, "HISTORICAL_DOCS_DIR", os.path.join(self.base, "docs")),
        ]
        for patch in self.patches:
            patch.start()
        self.agent = types.SimpleNamespace()
        self.agent.load_json_file = lambda path: LEXMOD.LexAgent.load_json_file(self.agent, path)

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        super().tearDown()

    def load(self, relative_path):
        def no_network(*args, **kwargs):
            raise AssertionError("unsafe manuscript path reached the network")
        with mock.patch.object(LEXMOD, "open_trusted_https", no_network):
            return LEXMOD.LexAgent.load_manuscript_asset(self.agent, relative_path)

    def test_bundled_asset_loads(self):
        os.makedirs(os.path.join(self.base, "witnesses", "manuscripts"))
        with open(os.path.join(self.base, "witnesses", "manuscripts", "10001.json"), "w") as fh:
            fh.write('{"id": "P66"}')
        self.assertEqual(self.load("witnesses/manuscripts/10001.json"), {"id": "P66"})

    def test_attacks_return_none_without_fetching(self):
        os.symlink(self.outside, os.path.join(self.base, "link"))
        for attack in ATTACKS + ["../outside/secret.json", "witnesses/../../outside/secret.json",
                                 "witnesses/.hidden.json", "witnesses/x.txt", None, 42]:
            with self.subTest(attack=attack):
                self.assertIsNone(self.load(attack))

    def test_symlink_escape_in_bundle_is_not_read(self):
        os.symlink(self.outside, os.path.join(self.base, "witnesses"))
        os.symlink(self.outside, os.path.join(self.cache, "witnesses"))
        self.assertIsNone(self.load("witnesses/secret.json"))

    def test_load_json_file_refuses_outside_and_symlinked_paths(self):
        os.symlink(os.path.join(self.outside, "secret.json"), os.path.join(self.base, "leak.json"))
        self.assertIsNone(self.agent.load_json_file(os.path.join(self.outside, "secret.json")))
        self.assertIsNone(self.agent.load_json_file(os.path.join(self.base, "leak.json")))
        self.assertIsNone(self.agent.load_json_file(os.path.join(self.base, "..", "outside", "secret.json")))


class OpenExportTest(TempDirs):
    def run_open(self, path):
        agent = types.SimpleNamespace(search_export_dir=lambda: self.base)
        with mock.patch.object(LEXMOD.sys, "platform", "linux"), \
                mock.patch.object(LEXMOD.shutil, "which", lambda name: "/usr/bin/" + name), \
                mock.patch.object(LEXMOD.subprocess, "Popen") as popen, \
                mock.patch.object(LEXMOD, "console", Console(file=io.StringIO())):
            LEXMOD.LexAgent.open_export(agent, path)
        return popen

    def test_export_inside_root_opens(self):
        target = os.path.join(self.base, "lex_search_x.pdf")
        open(target, "w").close()
        popen = self.run_open(target)
        self.assertEqual(popen.call_args[0][0][-1], target)

    def test_export_folder_itself_opens(self):
        self.assertEqual(self.run_open(self.base).call_args[0][0][-1], self.base)

    def test_paths_outside_exports_are_refused(self):
        os.symlink(self.outside, os.path.join(self.base, "link"))
        for path in (os.path.join(self.outside, "secret.json"),
                     os.path.join(self.base, "..", "outside", "secret.json"),
                     os.path.join(self.base, "link", "secret.json"),
                     self.base + "-evil/x.pdf",
                     os.path.join(self.base, "a\x00b")):
            with self.subTest(path=path):
                self.assertFalse(self.run_open(path).called)


class FontPathTest(TempDirs):
    def test_font_inside_root_is_trusted(self):
        font = os.path.join(self.base, "Font.ttf")
        open(font, "wb").close()
        self.assertEqual(LEXMOD.trusted_font_path(font, (self.base,)), font)

    def test_env_font_outside_roots_or_wrong_type_is_ignored(self):
        outside_font = os.path.join(self.outside, "Font.ttf")
        open(outside_font, "wb").close()
        os.symlink(outside_font, os.path.join(self.base, "Link.ttf"))
        not_font = os.path.join(self.base, "secret.json")
        open(not_font, "w").close()
        for candidate in (outside_font, os.path.join(self.base, "Link.ttf"), not_font,
                          os.path.join(self.base, "..", "outside", "Font.ttf"), None, ""):
            with self.subTest(candidate=candidate):
                self.assertIsNone(LEXMOD.trusted_font_path(candidate, (self.base,)))


class ScriptSourceFileTest(TempDirs):
    """Names from a downloaded checkout's listing (scripts/package_bible.py)."""

    def test_regular_file_inside_is_allowed(self):
        path = os.path.join(self.base, "Gen.json")
        open(path, "w").close()
        self.assertEqual(safe_paths.safe_source_file(self.base, "Gen.json"), path)

    def test_attacks_and_symlink_escape_are_rejected(self):
        os.symlink(os.path.join(self.outside, "secret.json"), os.path.join(self.base, "Exo.json"))
        for name in ATTACKS + ["Exo.json", "missing.json"]:
            with self.subTest(name=name):
                with self.assertRaises(safe_paths.UnsafePathError):
                    safe_paths.safe_source_file(self.base, name)

    def test_missing_file_is_reported_as_missing(self):
        with self.assertRaises(safe_paths.MissingSourceFile):
            safe_paths.safe_source_file(self.base, "Lev.json")

    def test_import_lxxmorph_refuses_symlinked_source(self):
        import import_lxxmorph
        filename = sorted(import_lxxmorph.FILE_BOOKS)[0]
        os.symlink(os.path.join(self.outside, "secret.json"), os.path.join(self.base, filename))
        with self.assertRaises(SystemExit):
            list(import_lxxmorph.iter_rows(self.base))

    def test_import_lemmas_refuses_symlinked_book_and_skips_missing(self):
        import import_lxx_openscriptures_lemmas as lemmas
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE lxx_text (book TEXT)")
        conn.execute("CREATE TABLE lxx_lemma_strong_map (book TEXT)")
        self.assertEqual(lemmas.import_book(conn, None, self.base, {}, "Gen")["rows"], 0)
        os.symlink(os.path.join(self.outside, "secret.json"), os.path.join(self.base, "Gen.js"))
        with self.assertRaises(SystemExit):
            lemmas.import_book(conn, None, self.base, {}, "Gen")
        conn.close()

    def test_package_kjv_1611_skips_symlinked_book(self):
        import package_bible
        os.symlink(os.path.join(self.outside, "secret.json"), os.path.join(self.base, "Evil.json"))
        with open(os.path.join(self.base, "Genesis.json"), "w") as fh:
            fh.write('{"book": "Genesis", "chapters": [{"chapter": 1, "verses": [{"verse": 1, "text": "In the beginning"}]}]}')
        db_path = os.path.join(self.tmp, "kj16.db")
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            package_bible.package_kjv_1611(self.base, db_path)
        self.assertIn("Skipping unsafe source file", out.getvalue())
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            refs = [row[0] for row in conn.execute("SELECT reference FROM bible")]
        self.assertEqual(refs, ["kj16:Genesis:1:1"])


class LemmaSourceDirTest(TempDirs):
    """LxxLemmas must stay inside the operator-supplied checkout (CodeQL #58)."""

    def test_safe_source_dir_allows_real_directory(self):
        path = os.path.join(self.base, "LxxLemmas")
        os.makedirs(path)
        self.assertEqual(safe_paths.safe_source_dir(self.base, "LxxLemmas"), path)

    def test_safe_source_dir_symlink_inside_is_allowed(self):
        real = os.path.join(self.base, "real-lemmas")
        os.makedirs(real)
        os.symlink(real, os.path.join(self.base, "LxxLemmas"))
        self.assertEqual(safe_paths.safe_source_dir(self.base, "LxxLemmas"), real)

    def test_safe_source_dir_rejects_attacks_and_symlink_escape(self):
        os.symlink(self.outside, os.path.join(self.base, "LxxLemmas"))
        for name in ATTACKS + ["LxxLemmas"]:
            with self.subTest(name=name):
                with self.assertRaises(safe_paths.UnsafePathError):
                    safe_paths.safe_source_dir(self.base, name)

    def test_safe_source_dir_missing_is_reported(self):
        with self.assertRaises(safe_paths.MissingSourceFile):
            safe_paths.safe_source_dir(self.base, "LxxLemmas")

    def _write_lemma_checkout(self, root, lemmas_is_symlink_to=None):
        if lemmas_is_symlink_to is None:
            os.makedirs(os.path.join(root, "LxxLemmas"))
            with open(os.path.join(root, "LxxLemmas", "Gen.js"), "w", encoding="utf-8") as fh:
                fh.write('{"Gen.1.1": [{"key": "k1", "lemma": "\u1f00\u03c1\u03c7\u1fc6"}]}')
        else:
            os.symlink(lemmas_is_symlink_to, os.path.join(root, "LxxLemmas"))
        with open(os.path.join(root, "GreekWordList.js"), "w", encoding="utf-8") as fh:
            fh.write('greekWordList = {"k1": {"strong": "746", "def": "beginning", "pos": "N"}};\n')
        bible_db = os.path.join(self.tmp, "lxx-bible.db")
        import sqlite3
        with sqlite3.connect(bible_db) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS bible (reference TEXT, text TEXT)")
            conn.execute("DELETE FROM bible")
            conn.execute(
                "INSERT INTO bible VALUES (?, ?)",
                ("lxx:Genesis:1:1", "\u1f18\u03bd \u1f00\u03c1\u03c7\u1fc7"),
            )
        return bible_db

    def _run_lemma_import(self, source, bible_db):
        import import_lxx_openscriptures_lemmas as lemmas
        db_path = os.path.join(self.tmp, "lxx-target.db")
        argv = [
            "import_lxx_openscriptures_lemmas.py",
            source,
            "--db", db_path,
            "--lxx-bible-db", bible_db,
            "--book", "Gen",
        ]
        with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            try:
                lemmas.main()
                return 0, out.getvalue(), db_path
            except SystemExit as exc:
                return exc.code, out.getvalue(), db_path

    def test_import_lemmas_main_accepts_valid_source(self):
        bible_db = self._write_lemma_checkout(self.base)
        code, out, db_path = self._run_lemma_import(self.base, bible_db)
        self.assertEqual(code, 0, msg=repr(out))
        self.assertIn("GEN:", out)
        self.assertIn("1 rows", out)
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            rows = list(conn.execute("SELECT lemma, strong FROM lxx_text"))
        self.assertEqual(len(rows), 1)

    def test_import_lemmas_main_rejects_symlink_escape(self):
        bible_db = self._write_lemma_checkout(self.base, lemmas_is_symlink_to=self.outside)
        code, out, _db_path = self._run_lemma_import(self.base, bible_db)
        self.assertNotEqual(code, 0)
        self.assertTrue(
            isinstance(code, str) and ("escapes" in code or "unsafe" in code.lower()),
            msg=repr(code),
        )

    def test_import_lemmas_main_rejects_missing_lemmas_dir(self):
        os.makedirs(self.base, exist_ok=True)
        with open(os.path.join(self.base, "GreekWordList.js"), "w") as fh:
            fh.write("greekWordList = {};\n")
        bible_db = os.path.join(self.tmp, "lxx-bible.db")
        open(bible_db, "wb").close()
        code, _out, _db_path = self._run_lemma_import(self.base, bible_db)
        self.assertNotEqual(code, 0)
        self.assertTrue(isinstance(code, str) and "Missing LxxLemmas" in code, msg=repr(code))


if __name__ == "__main__":
    unittest.main()

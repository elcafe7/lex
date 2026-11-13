"""Edition-aware search book scopes (issue #32).

`lex search <term> -<book>` must resolve the book against the identifiers the
active edition actually stores (ESV "Psalm", Geneva "Ps", Vulgate
"I Samuel", LXX "1 Samuel (1 Kingdoms)"), cover every deuterocanonical book an
edition has, and never silently match zero books because of spelling.

The first class needs no databases. The edition sweeps run against every
installed edition in runtime-data/bible_versions and skip the missing ones.

Run: python3 -m unittest tests.test_book_scopes
"""
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
BIBLE_DIR = os.path.join(ROOT, "runtime-data", "bible_versions")

_spec = importlib.util.spec_from_file_location("lex_scopes_under_test", LEX)
lex = importlib.util.module_from_spec(_spec)
_old_argv = sys.argv
sys.argv = ["lex"]
try:
    _spec.loader.exec_module(lex)
finally:
    sys.argv = _old_argv

STANDARD = list(lex.BIBLE_BOOKS)
GENEVA = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs", "2Kgs",
    "1Chr", "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer",
    "Lam", "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph",
    "Hag", "Zech", "Mal", "Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal",
    "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "Jas",
    "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Rev", "Tob", "Jdt", "Wis", "Sir", "Bar",
    "1Macc", "2Macc",
]
KJ1611_APOCRYPHA = [
    "1 Esdras", "1 Maccabees", "2 Esdras", "2 Maccabees", "Baruch", "Bel and the Dragon",
    "Ecclesiasticus", "Judith", "Letter of Jeremiah", "Prayer of Azariah", "Prayer of Manasseh",
    "Susanna", "Tobit", "Wisdom of Solomon",
]
DRA_EXTRA = ["Tobit", "Judith", "Wisdom", "Sirach", "Baruch", "1 Maccabees", "2 Maccabees"]
VULGATE_RENAMED = {
    "1 Samuel": "I Samuel", "2 Samuel": "II Samuel", "1 Kings": "I Kings", "2 Kings": "II Kings",
    "1 Chronicles": "I Chronicles", "2 Chronicles": "II Chronicles",
    "1 Corinthians": "I Corinthians", "2 Corinthians": "II Corinthians",
    "1 Thessalonians": "I Thessalonians", "2 Thessalonians": "II Thessalonians",
    "1 Timothy": "I Timothy", "2 Timothy": "II Timothy", "1 Peter": "I Peter",
    "2 Peter": "II Peter", "1 John": "I John", "2 John": "II John", "3 John": "III John",
    "Revelation": "Revelation of John",
}
VULGATE = [VULGATE_RENAMED.get(b, b) for b in STANDARD] + [
    "Tobit", "Judith", "Wisdom", "Sirach", "Baruch", "I Maccabees", "II Maccabees",
    "Prayer of Manasses", "I Esdras", "II Esdras", "Additional Psalm", "Laodiceans",
]
LXX = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua B", "Judges B", "Ruth",
    "1 Samuel (1 Kingdoms)", "2 Samuel (2 Kingdoms)", "1 Kings (3 Kingdoms)", "2 Kings (4 Kingdoms)",
    "1 Chronicles", "2 Chronicles", "Esdras A/I", "Ezra (Esdras B/II: 1-10)",
    "Nehemiah (Esdras B/II: 11-23)", "Esther (with additions)", "Judith", "Tobit BA",
    "I Maccabees", "II Maccabees", "III Maccabees", "IV Maccabees", "Psalms", "Odes", "Proverbs",
    "Ecclesiastes (Preacher)", "Canticle (Song of Solomon)", "Job", "Wisdom of Solomon",
    "Wisdom of Sirach", "Psalms of Solomon", "Hosea", "Amos", "Micah", "Joel", "Obadiah", "Jonah",
    "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi", "Isaiah", "Jeremiah",
    "Baruch", "Lamentations (Threni)", "Epistle of Jeremiah", "Ezekiel", "Susanna LXX",
    "Daniel LXX", "Bel LXX",
]


def scope_token(name):
    return "-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class FakeAgent:
    """The scope methods only need scope_book_index; no databases."""

    def __init__(self, stored_books):
        self.scope_book_index = lex.build_scope_book_index(stored_books)

    parse_book_scope = lex.LexAgent.parse_book_scope
    parse_search_query_and_scope = lex.LexAgent.parse_search_query_and_scope
    resolve_scope_books = lex.LexAgent.resolve_scope_books

    def resolve(self, token):
        return self.resolve_scope_books(self.parse_book_scope(token))


class ScopeIndexTest(unittest.TestCase):
    """Synthetic book lists copied from the installed editions."""

    EDITIONS = {
        "esv": [("Psalm" if b == "Psalms" else b) for b in STANDARD],
        "kjv": STANDARD,
        "kj16": STANDARD + KJ1611_APOCRYPHA,
        "dra": STANDARD + DRA_EXTRA,
        "gen": GENEVA,
        "vulg": VULGATE,
        "lxx": LXX,
    }

    def test_every_stored_book_has_a_scope(self):
        for edition, books in self.EDITIONS.items():
            agent = FakeAgent(books)
            mapped = {hit for hits in agent.scope_book_index["books"].values() for hit in hits}
            for book in books:
                with self.subTest(edition=edition, book=book):
                    self.assertIn(book, mapped)
                    if book == "Wisdom":
                        continue  # `-wisdom` is the wisdom-literature group
                    resolved = agent.resolve(scope_token(book))
                    self.assertIsNotNone(resolved, scope_token(book))
                    self.assertIn(book, resolved["books"])

    def test_standard_books_resolve_to_one_distinct_identifier(self):
        for edition in ("esv", "kjv", "kj16", "dra", "gen", "vulg"):
            agent = FakeAgent(self.EDITIONS[edition])
            seen = {}
            for book in STANDARD:
                with self.subTest(edition=edition, book=book):
                    resolved = agent.resolve(scope_token(book))
                    self.assertEqual(len(resolved["books"]), 1, resolved)
                    stored = resolved["books"][0]
                    self.assertIn(stored, self.EDITIONS[edition])
                    self.assertNotIn(stored, seen, f"{book} and {seen.get(stored)} share {stored}")
                    seen[stored] = book

    def test_psalms_in_esv(self):
        agent = FakeAgent(self.EDITIONS["esv"])
        for token in ("-psalms", "-psalm", "-ps", "-psa"):
            with self.subTest(token=token):
                self.assertEqual(agent.resolve(token)["books"], ["Psalm"])

    def test_geneva_abbreviations(self):
        agent = FakeAgent(GENEVA)
        expected = {"-genesis": "Gen", "-psalms": "Ps", "-esther": "Esth", "-revelation": "Rev",
                    "-1-samuel": "1Sam", "-tobit": "Tob", "-sirach": "Sir", "-1-maccabees": "1Macc",
                    "-wisdom-of-solomon": "Wis", "-baruch": "Bar", "-judith": "Jdt"}
        for token, stored in expected.items():
            with self.subTest(token=token):
                self.assertEqual(agent.resolve(token)["books"], [stored])

    def test_deuterocanon_names_per_edition(self):
        cases = {
            "kj16": {"-tobit": "Tobit", "-sirach": "Ecclesiasticus", "-ecclesiasticus": "Ecclesiasticus",
                     "-1-maccabees": "1 Maccabees", "-prayer-of-manasses": "Prayer of Manasseh",
                     "-song-of-the-three": "Prayer of Azariah", "-bel": "Bel and the Dragon",
                     "-epistle-of-jeremiah": "Letter of Jeremiah", "-2-esdras": "2 Esdras"},
            "dra": {"-tobias": "Tobit", "-1-machabees": "1 Maccabees", "-wis": "Wisdom",
                    "-ecclesiasticus": "Sirach"},
            "vulg": {"-1-maccabees": "I Maccabees", "-2-maccabees": "II Maccabees",
                     "-prayer-of-manasseh": "Prayer of Manasses", "-1-esdras": "I Esdras",
                     "-2-esdras": "II Esdras", "-psalm-151": "Additional Psalm",
                     "-laodiceans": "Laodiceans", "-1-samuel": "I Samuel", "-revelation": "Revelation of John",
                     "-1-john": "I John"},
            "lxx": {"-tobit": "Tobit BA", "-1-samuel": "1 Samuel (1 Kingdoms)",
                    "-1-kings": "1 Kings (3 Kingdoms)", "-joshua": "Joshua B", "-joshua-b": "Joshua B",
                    "-esther": "Esther (with additions)", "-song-of-solomon": "Canticle (Song of Solomon)",
                    "-sirach": "Wisdom of Sirach", "-3-maccabees": "III Maccabees", "-odes": "Odes",
                    "-psalms-of-solomon": "Psalms of Solomon", "-1-esdras": "Esdras A/I",
                    "-2-esdras": "Ezra (Esdras B/II: 1-10)", "-susanna": "Susanna LXX",
                    "-bel": "Bel LXX", "-daniel": "Daniel LXX", "-letter-of-jeremiah": "Epistle of Jeremiah"},
        }
        for edition, expected in cases.items():
            agent = FakeAgent(self.EDITIONS[edition])
            for token, stored in expected.items():
                with self.subTest(edition=edition, token=token):
                    self.assertEqual(agent.resolve(token)["books"], [stored])

    def test_lxx_variant_names(self):
        agent = FakeAgent(LXX + ["Joshua A"])  # some LXX builds split Joshua A/B
        for token, stored in {"-3-kingdoms": "1 Kings (3 Kingdoms)", "-iii-kingdoms": "1 Kings (3 Kingdoms)",
                              "-4-kingdoms": "2 Kings (4 Kingdoms)", "-1-kingdoms": "1 Samuel (1 Kingdoms)",
                              "-joshua-a": "Joshua A", "-joshua-b": "Joshua B"}.items():
            with self.subTest(token=token):
                self.assertEqual(agent.resolve(token)["books"], [stored])

    def test_lxx_name_absent_from_edition_is_reported_not_searched(self):
        # The installed lxx.db only carries Joshua B; `-joshua-a` must still
        # parse as a scope (so search reports it) rather than become a word.
        agent = FakeAgent([b for b in LXX if b != "Joshua A"])
        resolved = agent.resolve("-joshua-a")
        self.assertEqual((resolved["label"], resolved["books"]), ("Joshua A", []))
        self.assertEqual(FakeAgent(STANDARD).resolve("-3-kingdoms")["books"], [])

    def test_unknown_scope_token_is_flagged(self):
        agent = FakeAgent(STANDARD)
        query, scope = agent.parse_search_query_and_scope("love -foobar")
        self.assertEqual((query, scope), ("love", None))
        self.assertEqual(agent.last_search_scope_unknown, "-foobar")
        # Numbers and plain words are untouched.
        query, scope = agent.parse_search_query_and_scope("love -1 world")
        self.assertEqual(query, "love -1 world")
        self.assertIsNone(agent.last_search_scope_unknown)

    def test_psalm_and_psalms_in_every_edition(self):
        for edition, books in self.EDITIONS.items():
            agent = FakeAgent(books)
            for token in ("-psalm", "-psalms"):
                with self.subTest(edition=edition, token=token):
                    hits = agent.resolve(token)["books"]
                    self.assertEqual(len(hits), 1)
                    self.assertIn(hits[0], books)

    def test_missing_books_resolve_to_empty_not_wrong_book(self):
        kjv = FakeAgent(STANDARD)
        self.assertEqual(kjv.resolve("-tobit")["books"], [])
        self.assertEqual(kjv.resolve("-apocrypha")["books"], [])
        lxx = FakeAgent(LXX)
        self.assertEqual(lxx.resolve("-romans")["books"], [])
        self.assertEqual(lxx.resolve("-nt")["books"], [])

    def test_apocrypha_group(self):
        agent = FakeAgent(STANDARD + KJ1611_APOCRYPHA)
        self.assertEqual(sorted(agent.resolve("-apocrypha")["books"]), sorted(KJ1611_APOCRYPHA))
        self.assertEqual(agent.resolve("-deuterocanon")["books"], agent.resolve("-apocrypha")["books"])

    def test_ot_in_lxx_uses_lxx_names(self):
        books = FakeAgent(LXX).resolve("-ot")["books"]
        self.assertIn("1 Samuel (1 Kingdoms)", books)
        self.assertIn("Canticle (Song of Solomon)", books)
        self.assertEqual(len(books), 39)

    def test_ranges_stay_in_the_66_and_never_crash(self):
        agent = FakeAgent(STANDARD + KJ1611_APOCRYPHA)
        self.assertEqual(agent.resolve("-genesis-exodus")["books"], ["Genesis", "Exodus"])
        self.assertIsNone(agent.parse_book_scope("-genesis-tobit"))
        self.assertIsNone(agent.parse_book_scope("-tobit-judith"))

    def test_wisdom_is_still_the_group(self):
        agent = FakeAgent(STANDARD + DRA_EXTRA)
        self.assertEqual(agent.parse_book_scope("-wisdom")["label"], "wisdom")
        self.assertEqual(agent.resolve("-wisdom-of-solomon")["books"], ["Wisdom"])

    def test_scope_clause_matches_nothing_for_empty_books(self):
        clause, params = lex.LexAgent.search_scope_clause(None, {"label": "Tobit", "books": []})
        self.assertEqual((clause, params), (" AND 0", ()))

    def test_scope_clause_escapes_glob_metacharacters(self):
        _, params = lex.LexAgent.search_scope_clause(None, {"label": "x", "books": ["Odd*Book[1]?"]})
        self.assertEqual(params, ("*:Odd[*]Book[[]1][?]:*",))

    def test_roman_compact_key(self):
        self.assertEqual(lex.book_compact_key("I Samuel"), "1samuel")
        self.assertEqual(lex.book_compact_key("III John"), "3john")
        self.assertEqual(lex.book_compact_key("IV Maccabees"), "4maccabees")
        self.assertEqual(lex.book_compact_key("Isaiah"), "isaiah")


def installed_editions():
    if not os.path.isdir(BIBLE_DIR):
        return []
    return sorted(name[:-3] for name in os.listdir(BIBLE_DIR) if name.endswith(".db"))


class InstalledEditionScopeTest(unittest.TestCase):
    """DB-level sweep: every scope targets identifiers with rows."""

    @classmethod
    def setUpClass(cls):
        cls.editions = [e for e in installed_editions() if e in lex.BIBLE_VERSIONS]
        if not cls.editions:
            raise unittest.SkipTest("no Bible databases installed")
        cls.home = tempfile.mkdtemp(prefix="lex-scope-test-")
        cls._old_home = os.environ.get("HOME")
        os.environ["HOME"] = cls.home

    @classmethod
    def tearDownClass(cls):
        if cls._old_home is not None:
            os.environ["HOME"] = cls._old_home
        shutil.rmtree(cls.home, ignore_errors=True)

    def stored_books(self, edition):
        conn = sqlite3.connect(os.path.join(BIBLE_DIR, f"{edition}.db"))
        try:
            books = []
            for (ref,) in conn.execute("SELECT reference FROM bible"):
                book = ref.split(":", 1)[1].rsplit(":", 2)[0]
                if book not in books:
                    books.append(book)
            return books
        finally:
            conn.close()

    def test_every_scope_targets_rows(self):
        for edition in self.editions:
            agent = lex.LexAgent(edition)
            stored = set(self.stored_books(edition))
            index = agent.scope_book_index["books"]
            mapped = {hit for hits in index.values() for hit in hits}
            with self.subTest(edition=edition, check="all stored books mapped"):
                self.assertEqual(stored - mapped, set())
            for name, hits in index.items():
                with self.subTest(edition=edition, book=name):
                    self.assertTrue(set(hits) <= stored, hits)
                    clause, params = agent.search_scope_clause({"label": name, "books": hits})
                    rows = agent.bible_db.query(
                        f"SELECT COUNT(*) FROM bible WHERE 1{clause}",  # nosec B608  # reason: test; clause is literal GLOB terms with bound params
                        params,
                    )
                    self.assertGreater(rows[0][0], 0)

    def test_every_stored_book_reachable_by_its_own_name(self):
        for edition in self.editions:
            agent = lex.LexAgent(edition)
            for book in self.stored_books(edition):
                if book == "Wisdom":
                    continue  # `-wisdom` is the wisdom-literature group; `-wisdom-of-solomon` is tested
                with self.subTest(edition=edition, book=book):
                    resolved = agent.resolve_scope_books(agent.parse_book_scope(scope_token(book)))
                    self.assertIsNotNone(resolved, scope_token(book))
                    self.assertIn(book, resolved["books"])

    def test_issue_32_cases_against_installed_dbs(self):
        cases = {
            "gen": {"-genesis": "Gen", "-psalms": "Ps", "-psalm": "Ps"},
            "kj16": {"-tobit": "Tobit"},
            "dra": {"-1-maccabees": "1 Maccabees", "-1maccabees": "1 Maccabees", "-1-macc": "1 Maccabees"},
            "vulg": {"-i-maccabees": "I Maccabees", "-1-maccabees": "I Maccabees",
                     "-laodiceans": "Laodiceans", "-prayer-of-manasses": "Prayer of Manasses",
                     "-prayer-of-manasseh": "Prayer of Manasses"},
            "lxx": {"-3-kingdoms": "1 Kings (3 Kingdoms)", "-1-kings": "1 Kings (3 Kingdoms)",
                    "-psalms-of-solomon": "Psalms of Solomon", "-joshua-b": "Joshua B"},
        }
        for edition in self.editions:
            agent = lex.LexAgent(edition)
            for token in ("-psalm", "-psalms"):
                with self.subTest(edition=edition, token=token):
                    hits = agent.resolve_scope_books(agent.parse_book_scope(token))["books"]
                    self.assertEqual(len(hits), 1, hits)
            for token, stored in cases.get(edition, {}).items():
                with self.subTest(edition=edition, token=token):
                    hits = agent.resolve_scope_books(agent.parse_book_scope(token))["books"]
                    self.assertEqual(hits, [stored])

    def test_common_term_searches_hit_scoped_books(self):
        cases = [("kjv", "enemy -psalms"), ("esv", "enemy -psalm"), ("nasb", "enemy -psalms"),
                 ("gen", "beginning -genesis"), ("kj16", "Tobias -tobit"), ("dra", "Judas -1-maccabees"),
                 ("vulg", "Judas -i-maccabees"), ("vulg", "Judas -1-maccabees"), ("lxx", "κύριος -psalms-of-solomon"),
                 ("lxx", "βασιλεὺς -3-kingdoms")]
        for edition, query in cases:
            if edition not in self.editions:
                continue
            with self.subTest(edition=edition, query=query):
                state = lex.LexAgent(edition).resolve_search(query, limit=1)
                self.assertIsNotNone(state)
                self.assertGreater(state["total"], 0)

    def test_esv_psalms_search_returns_results(self):
        if "esv" not in self.editions:
            self.skipTest("esv not installed")
        agent = lex.LexAgent("esv")
        for query in ("enemy -psalms", "enemy -psalm"):
            with self.subTest(query=query):
                state = agent.resolve_search(query, limit=1)
                self.assertIsNotNone(state)
                self.assertGreater(state["total"], 0)
                self.assertEqual(state["scope"]["books"], ["Psalm"])

    def test_missing_scope_is_reported(self):
        if "kjv" not in self.editions:
            self.skipTest("kjv not installed")
        agent = lex.LexAgent("kjv")
        self.assertIsNone(agent.resolve_search("love -tobit"))
        self.assertEqual(agent.last_search_scope_missing, "Tobit")


class ScopeCliTest(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(os.path.join(BIBLE_DIR, "kjv.db")):
            self.skipTest("kjv not installed")
        self.home = tempfile.mkdtemp(prefix="lex-scope-cli-")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def run_lex(self, *args):
        env = dict(os.environ, HOME=self.home, NO_COLOR="1")
        return subprocess.run(
            [sys.executable, LEX, *args], capture_output=True, text=True, env=env, timeout=120,
        )

    def test_missing_scope_message(self):
        result = self.run_lex("--plain", "-B", "kjv", "search", "love", "-tobit")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Tobit is not in", result.stdout + result.stderr)

    def test_missing_scope_json(self):
        for flag in ("--json", "-json"):
            with self.subTest(flag=flag):
                result = self.run_lex(flag, "-B", "kjv", "search", "love", "-tobit")
                self.assertEqual(result.returncode, 3)
                error = json.loads(result.stderr or result.stdout)["error"]
                self.assertEqual(error["code"], "not_found")
                self.assertIn("Tobit", error["message"])

    def test_unknown_scope_message(self):
        result = self.run_lex("--plain", "-B", "kjv", "search", "love", "-foobar")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown book scope -foobar", result.stdout + result.stderr)

    def test_unknown_scope_json(self):
        result = self.run_lex("--json", "-B", "kjv", "search", "love", "-foobar")
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stderr or result.stdout)["error"]
        self.assertEqual(error["code"], "usage")
        self.assertIn("-foobar", error["message"])

    def test_json_scope_books_are_stored_identifiers(self):
        if not os.path.exists(os.path.join(BIBLE_DIR, "esv.db")):
            self.skipTest("esv not installed")
        result = self.run_lex("--json", "-B", "esv", "search", "enemy", "-psalms", "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["scope"]["books"], ["Psalm"])
        self.assertEqual(payload["results"][0]["book"], "Psalm")


if __name__ == "__main__":
    unittest.main()

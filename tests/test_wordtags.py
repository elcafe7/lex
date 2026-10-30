"""Word-tag checks for Geneva 1599, KJV 1611 and KJV 1769. Run: python -m unittest tests.test_wordtags  (or pytest)."""
import json, os, re, sqlite3, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RT = os.path.join(ROOT, "runtime-data")
WT = os.path.join(RT, "wordtags.db")
WORD = re.compile(r"[A-Za-zÆæ]+")
sys.path.insert(0, os.path.join(ROOT, "scripts", "wordtags"))

def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)

OSIS = ("Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov "
        "Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal "
        "Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm "
        "Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev").split()

# Floors sit just under the built numbers (2026-10-30) so a regression fails loudly.
FLOORS = {
    "gen":  {"all": 91.5, "ot": 90.5, "nt": 95.0, "confident": 85.5, "less_max": 6.5},
    "kj16": {"all": 92.8, "ot": 91.5, "nt": 97.0, "confident": 92.5, "less_max": 0.5},
    "kjv":  {"all": 92.0, "ot": 91.0, "nt": 95.8, "confident": 92.0, "less_max": 0.1},
}

class EditionBase:
    """Shared word-tag checks; subclasses set ED."""
    ED = None

    @classmethod
    def setUpClass(cls):
        cls.db = ro(WT)
        cls.meta = dict(cls.db.execute("SELECT key, value FROM meta"))
        cls.rows = {r: (t.split(" "), g) for r, t, g in
                    cls.db.execute("SELECT ref, tags, tiers FROM wordtags WHERE edition=?", (cls.ED,))}
        cls.text = dict(ro(os.path.join(RT, "bible_versions", cls.ED + ".db")).execute("SELECT reference, text FROM bible"))
        cls.strongs = {n for (n,) in ro(os.path.join(RT, "strongs.db")).execute("SELECT number FROM strongs")}
        cls.kjv = {o: set(n.split()) for o, n in cls.db.execute("SELECT osis, nums FROM kjv_numbers")}
        cls.stats = json.loads(cls.meta["stats"])[cls.ED]
        if cls.ED == "gen":
            cls.osis = lambda self, ref: ".".join(ref.split(":")[1:])
        else:
            order = []
            for (r,) in ro(os.path.join(RT, "bible_versions", "kjv.db")).execute("SELECT reference FROM bible ORDER BY id"):
                b = r.split(":")[1]
                if b not in order: order.append(b)
            m = dict(zip(order, OSIS))
            cls.osis = lambda self, ref: "{}.{}.{}".format(m[ref.split(":")[1]], *ref.split(":")[2:])

    def test_format(self):
        self.assertEqual(self.meta["format"], "1")
        self.assertEqual(self.meta["token_regex"], WORD.pattern)
        self.assertIn(self.ED, self.meta["editions"].split(","))
        self.assertEqual(len(self.rows), 31102)

    def test_coverage_floors(self):
        s, f = self.stats, FLOORS[self.ED]
        self.assertGreaterEqual(s["all"]["tagged_pct"], f["all"])
        self.assertGreaterEqual(s["ot"]["tagged_pct"], f["ot"])
        self.assertGreaterEqual(s["nt"]["tagged_pct"], f["nt"])
        self.assertGreaterEqual(s["all"]["confident_pct"], f["confident"])
        self.assertLessEqual(s["all"]["less_certain_pct"], f["less_max"])
        # recompute from the rows so the stored stats can't drift
        tiers = "".join(g for _, g in self.rows.values())
        tagged = sum(1 for c in tiers if c in self.meta["tiers_confident"] + self.meta["tiers_less_certain"])
        self.assertAlmostEqual(100 * tagged / len(tiers), s["all"]["tagged_pct"], places=1)
        self.assertEqual(len(tiers), s["all"]["words"])

    def test_token_counts_match_text(self):
        for ref, (tags, tiers) in self.rows.items():
            n = len(WORD.findall(self.text[ref]))
            self.assertEqual(len(tags), n, ref)
            self.assertEqual(len(tiers), n, ref)

    def test_tags_and_tiers_agree(self):
        tagged = set(self.meta["tiers_confident"] + self.meta["tiers_less_certain"])
        for ref, (tags, tiers) in self.rows.items():
            for t, g in zip(tags, tiers):
                self.assertEqual(t != "-", g in tagged, f"{ref} {t} {g}")

    def test_every_number_in_strongs_db(self):
        missing = {n for tags, _ in self.rows.values() for t in tags if t != "-" for n in t.split("+")} - self.strongs
        self.assertEqual(missing, set())

    def test_numbers_subset_of_kjv_verse(self):
        bad = []
        for ref, (tags, tiers) in self.rows.items():
            k = self.kjv.get(self.osis(ref), set())
            for t, g in zip(tags, tiers):
                if t != "-" and g != "X" and not set(t.split("+")) <= k:
                    bad.append((ref, t, g))
        self.assertEqual(bad, [])

    def test_golden_verses(self):
        gold = json.load(open(os.path.join(ROOT, "tests", "fixtures", "wordtags_golden.json"), encoding="utf-8"))["verses"]
        mine = {r: g for r, g in gold.items() if r.startswith(self.ED + ":")}
        self.assertGreaterEqual(len(mine), 7)
        for ref, g in mine.items():
            self.assertEqual(self.text[ref], g["text"], ref)
            got = list(zip(WORD.findall(self.text[ref]), self.rows[ref][0]))
            self.assertEqual([list(x) for x in got], g["words"], ref)

    def test_small_word_rule(self):
        """A small word never borrows a number that a different content word owns
        unless its nearest content neighbour carries that same number (Isa 53:5)."""
        isa = {"gen": "gen:Isa:53:5", "kj16": "kj16:Isaiah:53:5", "kjv": "kjv:Isaiah:53:5"}[self.ED]
        words = WORD.findall(self.text[isa]); tags = self.rows[isa][0]
        i = [w.lower() for w in words].index("stripes")
        self.assertEqual(tags[i], "H2250")
        self.assertIn(words[i - 5].lower(), ("vpon", "upon"))     # vpon him and with his stripes
        self.assertNotEqual(tags[i - 5], "H2250", words[i - 5])
        self.assertNotEqual(tags[i - 4], "H2250", words[i - 4])   # him


class GenevaTags(EditionBase, unittest.TestCase):
    ED = "gen"

    def test_spot_values(self):
        def tag(ref, i): return self.rows[ref][0][i]
        self.assertEqual(tag("gen:Gen:1:1", 2), "H7225")      # beginning
        self.assertEqual(tag("gen:Gen:1:2", 19), "H7363")     # mooued
        self.assertEqual(tag("gen:Rom:8:1", 0), "G3568")      # Now
        self.assertEqual(tag("gen:Rom:8:1", 1), "G686")       # then
        self.assertEqual(tag("gen:John:1:1", 16), "G2316")    # God
        self.assertEqual(tag("gen:John:3:16", 0), "G1063")    # For (not the untranslated article)


class KJV1611Tags(EditionBase, unittest.TestCase):
    ED = "kj16"

    def test_only_canon_tagged(self):
        books = {r.split(":")[1] for r in self.rows}
        self.assertEqual(len(books), 66)
        self.assertNotIn("Tobit", books)

    def test_run_together_words_split(self):
        # fixed kj16 db: no glued words like "theLORD" survive into the tags
        self.assertFalse(any(re.search(r"[a-z][A-Z]{2,}", t) for t in self.text.values() if t))


class KJV1769Tags(EditionBase, unittest.TestCase):
    ED = "kjv"

    def test_direct_from_module(self):
        """KJV 1769 uses the module's own tags only: no inferred tiers."""
        tiers = set("".join(g for _, g in self.rows.values()))
        self.assertEqual(tiers - set("ABCNSU"), set())
        self.assertLessEqual(self.stats["all"]["tiers"].get("C", 0), 10)

    def test_possessive_s_follows_word(self):
        ref = "kjv:Exodus:31:10"
        words = WORD.findall(self.text[ref]); tags = self.rows[ref][0]
        i = next(j for j in range(len(words) - 1) if words[j] == "priest" and words[j + 1] == "s")
        self.assertEqual(tags[i + 1], tags[i])


class Glosses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.heb = json.load(open(os.path.join(RT, "theolog-ai/data/biblical-languages/stepbible-lexicons/tbesh-hebrew.json"), encoding="utf-8"))

    def test_h4496_is_rest(self):
        self.assertEqual(self.heb["H4496"]["gloss"], "rest")

    def test_gloss_fixes_applied(self):
        for line in open(os.path.join(ROOT, "scripts", "wordtags", "gloss_fixes.tsv"), encoding="utf-8"):
            if not line.strip() or line.startswith(("#", "number")): continue
            num, _wrong, gloss = line.rstrip("\n").split("\t")[:3]
            key = num[0] + num[1:].zfill(4)
            self.assertEqual(self.heb.get(key, self.heb.get(num))["gloss"], gloss, num)

    def test_gloss_check_clean(self):
        import gloss_check
        d, s = gloss_check.load_lex(RT)
        flagged = {n for n, *_ in gloss_check.check(d, s)}
        accepted = set()
        for line in open(os.path.join(ROOT, "scripts", "wordtags", "gloss_accepted.tsv"), encoding="utf-8"):
            if line.strip() and not line.startswith("#"): accepted.update(re.findall(r"[HG]\d+", line))
        self.assertEqual(flagged - accepted, set())

class WordModeCLI(unittest.TestCase):
    def run_lex(self, *args):
        env = dict(os.environ, HOME=os.environ.get("LEX_TEST_HOME", "/tmp/lex-test-home"), COLUMNS="120", NO_COLOR="1", TERM="dumb")
        os.makedirs(env["HOME"], exist_ok=True)
        return subprocess.run([sys.executable, os.path.join(ROOT, "lex.py"), *args], capture_output=True, text=True, env=env, timeout=120)

    def test_words_geneva_plain(self):
        r = self.run_lex("-B", "gen", "words", "Gen", "1:2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("H7363", r.stdout)
        self.assertIn("to hover", r.stdout)
        self.assertNotIn("~", r.stdout)

    def test_words_kj16_plain(self):
        r = self.run_lex("-B", "kj16", "words", "Isa", "53:5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("H2250", r.stdout)
        self.assertIn("stripes", r.stdout)
        self.assertNotIn("~", r.stdout)

    def test_words_kjv_plain(self):
        r = self.run_lex("-B", "kjv", "words", "John", "1:1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("G3056", r.stdout)
        self.assertNotIn("~", r.stdout)

    def test_words_thorn_shown_as_letter(self):
        # KJV 1611 text stores the thorn abbreviation as "&thorn;"; word mode shows the letter
        r = self.run_lex("-B", "kj16", "words", "Gen", "2:19")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("þ", r.stdout)
        self.assertNotIn("thorn", r.stdout)

    def test_words_other_edition_message(self):
        r = self.run_lex("-B", "vulg", "words", "Gen", "1:2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not available", r.stdout)

if __name__ == "__main__":
    unittest.main()

"""Geneva word-tag checks. Run: python -m unittest tests.test_wordtags  (or pytest)."""
import json, os, re, sqlite3, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RT = os.path.join(ROOT, "runtime-data")
WT = os.path.join(RT, "wordtags.db")
WORD = re.compile(r"[A-Za-zÆæ]+")
sys.path.insert(0, os.path.join(ROOT, "scripts", "wordtags"))

def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)

class WordTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = ro(WT)
        cls.meta = dict(cls.db.execute("SELECT key, value FROM meta"))
        cls.rows = {r: (t.split(" "), g) for r, t, g in
                    cls.db.execute("SELECT ref, tags, tiers FROM wordtags WHERE edition='gen'")}
        cls.text = dict(ro(os.path.join(RT, "bible_versions", "gen.db")).execute("SELECT reference, text FROM bible"))
        cls.strongs = {n for (n,) in ro(os.path.join(RT, "strongs.db")).execute("SELECT number FROM strongs")}
        cls.kjv = {o: set(n.split()) for o, n in cls.db.execute("SELECT osis, nums FROM kjv_numbers")}
        cls.stats = json.loads(cls.meta["stats"])["gen"]

    def test_format(self):
        self.assertEqual(self.meta["format"], "1")
        self.assertEqual(self.meta["token_regex"], WORD.pattern)
        self.assertEqual(len(self.rows), 31102)

    def test_coverage_floors(self):
        s = self.stats
        self.assertGreaterEqual(s["all"]["tagged_pct"], 92.5)
        self.assertGreaterEqual(s["all"]["confident_pct"], 86.5)
        self.assertGreaterEqual(s["ot"]["tagged_pct"], 92.0)
        self.assertGreaterEqual(s["nt"]["tagged_pct"], 95.0)
        self.assertLessEqual(s["all"]["less_certain_pct"], 7.0)
        # recompute from the rows so the stored stats can't drift
        tiers = "".join(g for _, g in self.rows.values())
        tagged = sum(1 for c in tiers if c in self.meta["tiers_confident"] + self.meta["tiers_less_certain"])
        self.assertAlmostEqual(100 * tagged / len(tiers), s["all"]["tagged_pct"], places=1)

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
            _, b, c, v = ref.split(":")
            k = self.kjv.get(f"{b}.{c}.{v}", set())
            for t, g in zip(tags, tiers):
                if t != "-" and g != "X" and not set(t.split("+")) <= k:
                    bad.append((ref, t, g))
        self.assertEqual(bad, [])

    def test_golden_verses(self):
        gold = json.load(open(os.path.join(ROOT, "tests", "fixtures", "wordtags_golden.json"), encoding="utf-8"))["verses"]
        for ref, g in gold.items():
            self.assertEqual(self.text[ref], g["text"], ref)
            got = list(zip(WORD.findall(self.text[ref]), self.rows[ref][0]))
            self.assertEqual([list(x) for x in got], g["words"], ref)

    def test_spot_values(self):
        def tag(ref, i): return self.rows[ref][0][i]
        self.assertEqual(tag("gen:Gen:1:1", 2), "H7225")      # beginning
        self.assertEqual(tag("gen:Gen:1:2", 19), "H7363")     # mooued
        self.assertEqual(tag("gen:Rom:8:1", 0), "G3568")      # Now
        self.assertEqual(tag("gen:Rom:8:1", 1), "G686")       # then
        self.assertEqual(tag("gen:John:1:1", 16), "G2316")    # God

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

    def test_words_other_edition_message(self):
        r = self.run_lex("-B", "kjv", "words", "Gen", "1:2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not available", r.stdout)

if __name__ == "__main__":
    unittest.main()

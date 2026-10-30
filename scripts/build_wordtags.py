#!/usr/bin/env python3
"""Build runtime-data/wordtags.db: word-level Strong's numbers for early English editions.

The KJV (1769) word/phrase Strong's tagging from the CrossWire SWORD "KJV" module is
projected onto another edition's text verse by verse (Geneva 1599 now; KJV 1611 and
KJV 1769 use the same pipeline).

Output table `wordtags(edition, ref, tags, tiers)`, one row per canon verse:
  tags  = space-separated, one item per word token of the edition's verse text
          ("-" = no number, "H7225", or "G3588+G3056" for a phrase with two numbers)
  tiers = one letter per token, how the number was found (kept for later review/marks):
          A exact spelling match        B spelling variant / equivalent word
          R word-order swap             F small word takes its head word's number (head A/B/R/V)
          C KJV translation table       D sole word in a gap between matched words
          f small word inherits from a C/D head
          V reviewed: kept               X reviewed: number corrected
          S lines up with a KJV supplied (italic) word   N lines up with an untagged KJV word
          U no match
  Confident = A B R F V X; less certain = C D f. Untagged = S N U.
Tokens are WORD_TOKEN_RE matches over the stored verse text (same regex in lex.py).

Build-time needs: the CrossWire KJV module zip and `pysword` (only for --kjv-zip).
Usage:
  python3 scripts/build_wordtags.py --kjv-zip KJV.zip --cache /tmp/kjv_tokens.json \
      --editions gen --out runtime-data/wordtags.db [--jobs 8] [--review-dir DIR]
"""
import argparse, difflib, json, os, re, sqlite3, sys, time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BV = os.path.join(ROOT, "runtime-data", "bible_versions")
WORD_TOKEN_RE = re.compile(r"[A-Za-zÆæ]+")
BREAK_RE = re.compile(r"[,.;:?!()¶]")
CONFIDENT = set("ABRFVX")
WEAK = set("CDf")
TAGGED = CONFIDENT | WEAK
# Geneva spellings the normaliser below does not reach
SPELL = {"hie": "high", "whe": "when", "shalbe": "shall", "wilbe": "will"}

# ---------------------------------------------------------------- KJV layer
def extract_kjv(zip_path):
    import html
    from pysword.modules import SwordModules
    m = SwordModules(zip_path); m.parse_modules(); b = m.get_bible_from_module("KJV")
    W = re.compile(r'<w ([^>]*)>(.*?)</w>|<transChange type="added">(.*?)</transChange>|<note.*?</note>|<[^>]+>|([^<]+)', re.S)
    toks = lambda s: re.findall(r"[A-Za-z]+(?:'[a-z]+)?", s)
    out = {}
    for testament in b.get_structure().get_books().values():
        for bk in testament:
            for ch in range(1, bk.num_chapters + 1):
                for v in range(1, bk.chapter_lengths[ch - 1] + 1):
                    raw = b.get(books=[bk.osis_name], chapters=[ch], verses=[v], clean=False)
                    T = []
                    for m_ in W.finditer(raw):
                        attrs, inner, added, plain = m_.groups()
                        if attrs is not None:
                            ss = [a + n for a, n in re.findall(r"strong:([HG])0*(\d+)", attrs)]
                            for t in toks(html.unescape(re.sub(r"<[^>]+>", "", inner))):
                                T.append([t, ss, "w"])
                        elif added is not None:
                            for t in toks(re.sub(r"<[^>]+>", "", added)):
                                T.append([t, [], "added"])
                        elif plain:
                            for t in toks(html.unescape(plain)):
                                T.append([t, [], "plain"])
                    out[f"{bk.osis_name}.{ch}.{v}"] = T
    return out

# ---------------------------------------------------------------- normalisation
def norm(w):
    w = w.lower().replace("'", "").replace("æ", "e")
    w = SPELL.get(w, w)
    w = w.replace("j", "i").replace("v", "u").replace("y", "i").replace("ck", "k").replace("ow", "ou")
    oo = "oo" in w
    w = re.sub(r"(.)\1+", r"\1", w)
    if len(w) > 2 and w.endswith("e"):
        w = w[:-1]
    if oo and w in ("god", "gods"):   # good/goode/goods must not collapse to god
        w = "go" + w[1:]
    return w

def stem(a):
    for suf in ("eth", "est", "ing", "ed", "es", "th", "s", "d"):
        if len(a) > len(suf) + 2 and a.endswith(suf):
            return a[: -len(suf)]
    return a

STOP = {norm(w) for w in (
    "the a an of and to in that which who whom is be was were are he she it they them his her their him "
    "i me my we us our ye you your thou thee thy shall will unto for with by from as not but or so then "
    "there this these those upon on at all hath have had do did").split()}
CONN_GROUPS = [{norm(w) for w in "and also now but moreover furthermore futhermore likewise afterward afterwards yet".split()},
               {norm(w) for w in "then therefore wherefore so thus".split()}]
CONN = set().union(*CONN_GROUPS)
def conn_pair(a, b):
    return any(a in g and b in g for g in CONN_GROUPS)
NO_GAP = STOP | CONN | {norm(w) for w in (
    "againe again behold lo yea euen even surely verely verily yet if when where here whereby thereof "
    "thereby therein whereof nor neither because").split()}
# small words that may take the next word's number (KJV convention: "the heaven" = H8064)
INHERIT = {norm(w) for w in (
    "the a an of to in that which who whom is be was were are he she it they them his her their him "
    "i me my we us our ye you your thou thee thy shall will unto for with by from as upon on at hath "
    "have had do did and vnto doth haue hee shee wee bee when whe then so yet also euen even there "
    "this these those all if where shalbe wilbe therefore againe but now thus").split()}
# verb particles take the verb's number (KJV "Get you up", "sent out"), looking back past one pronoun
PARTICLE = {norm(w) for w in "vp up out away downe down forth againe backe off".split()}
# object pronouns with no head to the right take the number of the verb before them (KJV "smote him")
INHERIT_LEFT = {norm(w) for w in "him them me thee it us her you hee".split()}

EQUIV = {(norm("ye"), norm("the")), (norm("according"), norm("after")), (norm("that"), norm("the"))}

class Aligner:
    def __init__(self, K):
        self.K = K
        self.VOC = defaultdict(Counter)
        for vs in K.values():
            for w, ss, _ in vs:
                for s in ss:
                    self.VOC[s][norm(w)] += 1
        self.TOT = Counter()
        for c in self.VOC.values():
            self.TOT.update(c)
        self._lex = {}

    def lexok(self, a, ss):
        key = (a, tuple(ss))
        if key in self._lex:
            return self._lex[key]
        ok = False
        if a not in STOP:
            for s in ss:
                voc = self.VOC[s]
                for w in (a, stem(a)):
                    n = voc[w] + sum(v for x, v in voc.items() if x != w and stem(x) == w)
                    if n >= 2 and n / (self.TOT[w] or 1) >= 0.05:
                        ok = True; break
                if ok: break
        self._lex[key] = ok
        return ok

    def sim(self, g, k):
        a, b = norm(g), norm(k[0])
        if a == b: return 3.0, "A"
        if (a, b) in EQUIV: return 2.2, "B"
        if conn_pair(a, b): return 1.8, "B"
        if stem(a) == stem(b) and len(stem(a)) >= 3: return 2.5, "B"
        if min(len(a), len(b)) >= 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8: return 2.0, "B"
        if self.lexok(a, k[1]): return 1.5, "C"
        return None, None

    def align(self, text, ktoks):
        """Return list of [word, [strongs], tier, kjv_word] per token of text."""
        spans = [(m.group(0), m.start(), m.end()) for m in WORD_TOKEN_RE.finditer(text)]
        G = [s[0] for s in spans]
        n, m = len(G), len(ktoks)
        D = [[0.0] * (m + 1) for _ in range(n + 1)]
        P = [[None] * (m + 1) for _ in range(n + 1)]
        S = [[None] * m for _ in range(n)]
        for i in range(n):
            for j in range(m):
                S[i][j] = self.sim(G[i], ktoks[j])
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                best, bp = D[i - 1][j], "u"
                if D[i][j - 1] > best: best, bp = D[i][j - 1], "l"
                sc = S[i - 1][j - 1][0]
                if sc is not None and D[i - 1][j - 1] + sc > best: best, bp = D[i - 1][j - 1] + sc, "d"
                D[i][j], P[i][j] = best, bp
        i, j, link = n, m, {}
        while i > 0 and j > 0:
            if P[i][j] == "d": link[i - 1] = j - 1; i -= 1; j -= 1
            elif P[i][j] == "u": i -= 1
            else: j -= 1
        out, kused = [], set(link.values())
        for gi, g in enumerate(G):
            if gi in link:
                k = ktoks[link[gi]]; tier = S[gi][link[gi]][1]
                out.append([g, list(k[1]), tier if k[1] else ("S" if k[2] == "added" else "N"), k[0]])
            else:
                out.append([g, [], None, None])
        def standalone(j):   # KJV word carries its number alone (not part of a tagged phrase)
            t = ktoks[j][1]
            return not ((j > 0 and ktoks[j - 1][1] == t) or (j + 1 < m and ktoks[j + 1][1] == t))
        # R: word-order swaps (same spelling, or connective for connective)
        for row in out:
            if row[2] is not None: continue
            a = norm(row[0])
            if a in STOP and a not in CONN: continue
            free = [j for j, k in enumerate(ktoks) if j not in kused and k[1]]
            hits = [j for j in free if norm(ktoks[j][0]) == a] or \
                   [j for j in free if len(stem(a)) >= 3 and stem(norm(ktoks[j][0])) == stem(a)] or \
                   [j for j in free if conn_pair(a, norm(ktoks[j][0])) and standalone(j)]
            if hits:
                j = hits[0]; kused.add(j); row[1], row[2], row[3] = list(ktoks[j][1]), "R", ktoks[j][0]
        # C (translation table) then D (gap fill)
        linked = sorted(link)
        def gap_of(gi):
            lo = max([link[x] for x in linked if x < gi], default=-1)
            hi = min([link[x] for x in linked if x > gi], default=m)
            return lo, hi
        for gi, row in enumerate(out):
            if row[2] is not None: continue
            lo, hi = gap_of(gi)
            gap = [ktoks[j] for j in range(lo + 1, hi) if ktoks[j][1] and j not in kused]
            a = norm(row[0])
            cands = [k for k in gap if self.lexok(a, k[1])]
            if not cands and a not in NO_GAP:
                cands = [k for j, k in enumerate(ktoks) if j not in kused and k[1] and self.lexok(a, k[1])]
            if cands:
                row[1], row[2], row[3] = list(cands[0][1]), "C", cands[0][0]; continue
        # D: content words left in a gap take the gap's KJV numbers in order, only when the
        # gap has at least as many distinct KJV numbers as leftover content words
        gi = 0
        while gi < len(out):
            if out[gi][2] is not None or norm(out[gi][0]) in NO_GAP or len(norm(out[gi][0])) < 3:
                gi += 1; continue
            lo, hi = gap_of(gi)
            members = [x for x in range(len(out)) if out[x][2] is None and gap_of(x) == (lo, hi)
                       and norm(out[x][0]) not in NO_GAP and len(norm(out[x][0])) >= 3]
            groups = []
            for j in range(lo + 1, hi):
                k = ktoks[j]
                if k[1] and j not in kused and (not groups or groups[-1][1] != k[1]):
                    groups.append(k)
            if groups and len(members) <= len(groups):
                for x, k in zip(members, groups if len(members) == len(groups) else groups[:len(members)]):
                    out[x][1], out[x][2], out[x][3] = list(k[1]), "D", k[0]
            else:
                for x in members: out[x][2] = "U"
            gi += 1
        for row in out:
            if row[2] is None: row[2] = "U"
        # particles first, so "turned againe" keeps the verb
        for gi in range(1, len(out)):
            row = out[gi]
            if row[2] != "U" or norm(row[0]) not in PARTICLE: continue
            for back in (1, 2):
                h = gi - back
                if h < 0 or BREAK_RE.search(text[spans[h][2]:spans[gi][1]]): break
                head = out[h]
                if back == 2 and norm(out[gi - 1][0]) not in INHERIT_LEFT: break
                if head[2] in TAGGED and head[2] not in "Ff" and norm(head[0]) not in NO_GAP:
                    row[1] = list(head[1]); row[2] = "F" if head[2] in CONFIDENT else "f"; break
        # F/f: KJV convention, a run of small words takes the number of the word it belongs to
        for gi in range(len(out) - 1, -1, -1):
            row = out[gi]
            if row[2] != "U" or norm(row[0]) not in INHERIT: continue
            # walk right through other small untagged words, stop at punctuation
            j = gi + 1; steps = 0
            while j < len(out):
                if BREAK_RE.search(text[spans[j - 1][2]:spans[j][1]]): j = None; break
                if out[j][2] in TAGGED: break
                if out[j][2] == "U" and norm(out[j][0]) in INHERIT and steps < 3:
                    j += 1; steps += 1; continue
                j = None; break
            if j is None or j >= len(out): continue
            head = out[j]
            row[1] = list(head[1]); row[2] = "F" if head[2] in CONFIDENT else "f"; row[3] = None
        for gi in range(1, len(out)):
            row = out[gi]
            if row[2] != "U" or norm(row[0]) not in INHERIT_LEFT: continue
            if BREAK_RE.search(text[spans[gi - 1][2]:spans[gi][1]]): continue
            head = out[gi - 1]
            if head[2] in TAGGED and head[2] not in "Ff":
                row[1] = list(head[1]); row[2] = "F" if head[2] in CONFIDENT else "f"
        # split compounds: Geneva "first borne" = KJV "firstborn"
        knorm = [(norm(k[0]), k[1]) for k in ktoks]
        for gi in range(len(out) - 1):
            a, b = out[gi], out[gi + 1]
            if not ({a[2], b[2]} <= {"U", "C", "D", "f"}) or "U" not in (a[2], b[2]): continue
            joined = norm(a[0] + b[0])
            for kn, kt in knorm:
                if kt and len(kn) >= 6 and (kn == joined or (stem(kn) == stem(joined))):
                    for r in (a, b):
                        r[1], r[2], r[3] = list(kt), "B", None
                    break
        return out

# ---------------------------------------------------------------- editions
def kjv_order_books():
    kj = sqlite3.connect(os.path.join(BV, "kjv.db"))
    full = []
    for (r,) in kj.execute("SELECT reference FROM bible ORDER BY id"):
        b = r.split(":")[1]
        if b not in full: full.append(b)
    return full

def edition_rows(ed, K):
    conn = sqlite3.connect(f"file:{os.path.join(BV, ed + '.db')}?mode=ro", uri=True)
    rows = dict(conn.execute("SELECT reference, text FROM bible"))
    osis = []
    for k in K:
        b = k.split(".")[0]
        if b not in osis: osis.append(b)
    if ed == "gen":
        keyf = lambda b, c, v: f"gen:{b}:{c}:{v}"
    else:
        M = dict(zip(osis, kjv_order_books()))
        keyf = lambda b, c, v: f"{ed}:{M[b]}:{c}:{v}"
    out = {}
    for k in K:
        b, c, v = k.split(".")
        ref = keyf(b, c, v)
        if ref in rows: out[k] = (ref, rows[ref])
    return out

# ---------------------------------------------------------------- overrides
def load_overrides(path):
    """TSV: scope<TAB>key<TAB>proposed<TAB>decision<TAB>note
    scope=pair: key = normalised word, proposed = Strong's as built (e.g. H7760) -> every occurrence
    scope=ref:  key = OSIS ref#token_index (0-based), proposed = '*' or as built
    decision: ok | fix:H1234[+G5678] | none"""
    ov = []
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if not line.strip() or line.startswith("#"): continue
            p = line.rstrip("\n").split("\t")
            while len(p) < 5: p.append("")
            ov.append(p[:5])
    return ov

def apply_overrides(res, ov, used):
    pair = {}; byref = {}
    for i, (scope, key, prop, dec, _) in enumerate(ov):
        (pair.__setitem__((key, prop), (dec, i)) if scope == "pair" else byref.__setitem__(key, (prop, dec, i)))
    for k, toks in res.items():
        for ti, t in enumerate(toks):
            hit = byref.get(f"{k}#{ti}")
            if hit and (hit[0] in ("*", "+".join(t[1]))):
                _, dec, i = hit
            elif t[2] in "CDRf" and (norm(t[0]), "+".join(t[1])) in pair:
                dec, i = pair[(norm(t[0]), "+".join(t[1]))]
            else:
                continue
            used.add(i)
            if dec == "ok": t[2] = "V"
            elif dec == "none": t[1], t[2] = [], "U"
            elif dec.startswith("fix:"): t[1], t[2] = dec[4:].split("+"), "X"

# ---------------------------------------------------------------- main
_AL = None; _ROWS = None
def _work(k):
    ref, text = _ROWS[k]
    return k, _AL.align(text, _AL.K[k])

def build_edition(ed, K, jobs):
    global _AL, _ROWS
    _AL = _AL or Aligner(K); _ROWS = edition_rows(ed, K)
    keys = [k for k in K if k in _ROWS]
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as p: res = dict(p.map(_work, keys, chunksize=200))
    else:
        res = dict(map(_work, keys))
    return res, {k: _ROWS[k][0] for k in keys}

def stats(res, ot_books):
    def count(pred):
        c = Counter(t[2] for k, v in res.items() if pred(k) for t in v)
        n = sum(c.values()) or 1
        return {"words": n, "tiers": dict(sorted(c.items())),
                "tagged_pct": round(100 * sum(c[x] for x in TAGGED) / n, 2),
                "confident_pct": round(100 * sum(c[x] for x in CONFIDENT) / n, 2),
                "less_certain_pct": round(100 * sum(c[x] for x in WEAK) / n, 2)}
    ot = lambda k: k.split(".")[0] in ot_books
    return {"all": count(lambda k: True), "ot": count(ot), "nt": count(lambda k: not ot(k)), "verses": len(res)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kjv-zip"); ap.add_argument("--cache", required=True)
    ap.add_argument("--editions", default="gen"); ap.add_argument("--out", required=True)
    ap.add_argument("--overrides-dir", default=os.path.join(HERE, "wordtags"))
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--json-dir", help="also write per-edition raw alignment JSON here (review tooling)")
    a = ap.parse_args()
    if os.path.exists(a.cache):
        K = json.load(open(a.cache))
    else:
        K = extract_kjv(a.kjv_zip); json.dump(K, open(a.cache, "w"))
    ot_books = set()
    for k in K:
        b = k.split(".")[0]
        if b == "Matt": break
        ot_books.add(b)
    if os.path.exists(a.out): os.remove(a.out)
    db = sqlite3.connect(a.out)
    db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE wordtags(edition TEXT NOT NULL, ref TEXT NOT NULL, tags TEXT NOT NULL, tiers TEXT NOT NULL, PRIMARY KEY(edition, ref)) WITHOUT ROWID")
    # KJV verse numbers (sorted, unique) for the subset test and later editions
    db.execute("CREATE TABLE kjv_numbers(osis TEXT PRIMARY KEY, nums TEXT NOT NULL) WITHOUT ROWID")
    db.executemany("INSERT INTO kjv_numbers VALUES(?,?)",
                   [(k, " ".join(sorted({n for t in v for n in t[1]}))) for k, v in K.items()])
    report = {}
    for ed in a.editions.split(","):
        t0 = time.time()
        res, refs = build_edition(ed, K, a.jobs)
        ovp = os.path.join(a.overrides_dir, f"overrides_{ed}.tsv")
        ov = load_overrides(ovp); used = set()
        apply_overrides(res, ov, used)
        unused = [ov[i][:2] for i in range(len(ov)) if i not in used]
        rows = [(ed, refs[k], " ".join("+".join(t[1]) if t[1] and t[2] in TAGGED else "-" for t in v),
                 "".join(t[2] for t in v)) for k, v in res.items()]
        db.executemany("INSERT INTO wordtags VALUES(?,?,?,?)", rows)
        st = stats(res, ot_books); st.update(seconds=round(time.time() - t0), overrides=len(ov), overrides_unused=unused)
        report[ed] = st
        if a.json_dir:
            os.makedirs(a.json_dir, exist_ok=True)
            json.dump(res, open(os.path.join(a.json_dir, f"align_{ed}.json"), "w"), ensure_ascii=False)
        print(ed, json.dumps({k: st[k] for k in ("verses", "seconds", "overrides")}), json.dumps(st["all"]), file=sys.stderr)
    meta = {"format": "1", "token_regex": WORD_TOKEN_RE.pattern,
            "source": "KJV word/phrase Strong's tagging from the CrossWire Bible Society SWORD KJV module, projected onto each edition's text",
            "tiers_confident": "".join(sorted(CONFIDENT)), "tiers_less_certain": "".join(sorted(WEAK)),
            "editions": a.editions, "stats": json.dumps(report)}
    db.executemany("INSERT INTO meta VALUES(?,?)", meta.items())
    db.commit(); db.execute("VACUUM"); db.close()
    print(json.dumps(report, indent=1))

if __name__ == "__main__":
    main()

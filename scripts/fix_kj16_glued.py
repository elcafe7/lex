#!/usr/bin/env python3
"""Split run-together words in the KJV 1611 text (kj16.db), e.g. "ofsorrows" -> "of sorrows".

A word is split only when:
  * it never appears as a word in the KJV 1769 or Geneva texts and is rare in kj16 itself,
  * both halves are common words in the 1611/1769/Geneva texts, and
  * the 1769 KJV verse at the same reference has the two halves as consecutive words
    (compared with the same spelling normalisation the word tagger uses).
The bible table and the bible_fts rows are both updated. Writes a TSV log of every change.

usage: fix_kj16_glued.py [--db runtime-data/bible_versions/kj16.db] [--dry-run] [--log out.tsv]
"""
import argparse, collections, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_wordtags import norm

HERE = os.path.dirname(os.path.abspath(__file__))
BV = os.path.join(HERE, "..", "runtime-data", "bible_versions")
WORD = re.compile(r"[A-Za-zÆæ]+")
# 1611 compounds (printed as one word or hyphenated), not run-together typos: leave as they are
KEEP = set("""firrewood othersome youward mercieseat seacoast shalbee eastwind eastgate seashore
southland southwind cockecrow cedarwood handweapon sinnemoney rightside insunder""".split())

def texts(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    return dict(c.execute("SELECT reference, text FROM bible"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(BV, "kj16.db"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    kj16 = texts(a.db); kjv = texts(os.path.join(BV, "kjv.db")); gen = texts(os.path.join(BV, "gen.db"))
    vocab = collections.Counter()
    for T in (kj16, kjv, gen):
        for t in T.values():
            vocab.update(w.lower() for w in WORD.findall(t))
    other = collections.Counter()
    for T in (kjv, gen):
        for t in T.values():
            other.update(w.lower() for w in WORD.findall(t))
    changes = []
    new_text = {}
    for ref, text in kj16.items():
        kref = "kjv:" + ref.split(":", 1)[1]
        if kref not in kjv: continue
        kt = [norm(w) for w in WORD.findall(kjv[kref])]
        kpairs = set(zip(kt, kt[1:]))
        def fix(m):
            w = m.group(0); lw = w.lower()
            if len(lw) < 5 or lw in KEEP or other[lw] or vocab[lw] > 2: return w
            for i in range(2, len(lw) - 1):
                l, r = lw[:i], lw[i:]
                if vocab[l] >= 20 and vocab[r] >= 3 and (norm(l), norm(r)) in kpairs:
                    changes.append((ref, w, w[:i] + " " + w[i:]))
                    return w[:i] + " " + w[i:]
            return w
        t2 = WORD.sub(fix, text)
        if t2 != text: new_text[ref] = t2
    if a.log:
        with open(a.log, "w", encoding="utf-8") as f:
            f.write("reference\tbefore\tafter\n")
            for c in changes: f.write("\t".join(c) + "\n")
    if not a.dry_run and new_text:
        c = sqlite3.connect(a.db)
        with c:
            for ref, t in new_text.items():
                (rid,) = c.execute("SELECT id FROM bible WHERE reference=?", (ref,)).fetchone()
                c.execute("UPDATE bible SET text=? WHERE id=?", (t, rid))
                c.execute("DELETE FROM bible_fts WHERE rowid=?", (rid,))
                c.execute("INSERT INTO bible_fts(rowid, reference, text) VALUES (?,?,?)", (rid, ref, t))
        c.execute("VACUUM"); c.close()
    print(f"words split: {len(changes)} in {len(new_text)} verses" + (" (dry run)" if a.dry_run else ""))

if __name__ == "__main__":
    main()

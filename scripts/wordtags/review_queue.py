#!/usr/bin/env python3
"""Write review queues from build_wordtags.py --json-dir output.
geneva-queue.tsv: one row per (word, Strong's) pair in tiers R/C/D/f, most frequent first.
geneva-verses.tsv: verses where under half the words are confident."""
import json, re, sqlite3, sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build_wordtags import norm, stem, CONFIDENT
src, kjvjson, lexpack, strongsdb, outdir, ed = sys.argv[1:7]
R = json.load(open(src)); K = json.load(open(kjvjson))
step = dict((n, g) for n, g in sqlite3.connect(lexpack).execute("SELECT number, gloss FROM step"))
sdef = dict(sqlite3.connect(strongsdb).execute("SELECT number, definition FROM strongs"))
pairs = defaultdict(lambda: [0, Counter(), None, None])
for k, v in R.items():
    for i, t in enumerate(v):
        if t[2] in "RCDf":
            key = (norm(t[0]), "+".join(t[1]), t[2])
            p = pairs[key]; p[0] += 1; p[1][t[3] or ""] += 1
            if p[2] is None: p[2] = f"{k}#{i}"; p[3] = " ".join(x[0] for x in v[max(0, i - 4):i + 5])
def related(word, ss):
    a = stem(norm(word))
    for s in ss.split("+"):
        txt = (step.get(s, "") + " " + (sdef.get(s) or "")).lower()
        for w in re.findall(r"[a-z]+", txt):
            if len(a) >= 3 and (stem(norm(w)) == a or norm(w).startswith(a) or a.startswith(stem(norm(w))) and len(stem(norm(w))) >= 4):
                return "yes"
    return "no"
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, f"{ed}-queue.tsv"), "w") as f:
    f.write("first_ref\tgeneva_word\tproposed\ttier\tkjv_words\tstep_gloss\tgloss_related\tcontext\tcount\tdecision\tnote\n")
    for (w, ss, tier), (n, kw, ref, ctx) in sorted(pairs.items(), key=lambda x: -x[1][0]):
        gl = "/".join(step.get(s, "?") for s in ss.split("+"))
        f.write(f"{ref}\t{w}\t{ss}\t{tier}\t{','.join(x for x,_ in kw.most_common(3))}\t{gl}\t{related(w, ss)}\t{ctx}\t{n}\t\t\n")
low = []
for k, v in R.items():
    if v and sum(t[2] in CONFIDENT for t in v) / len(v) < 0.5:
        low.append((k, sum(t[2] in CONFIDENT for t in v) / len(v)))
with open(os.path.join(outdir, f"{ed}-verses.tsv"), "w") as f:
    f.write("ref\tconfident_share\tgeneva_tagged\tkjv_tagged\tdecision\tnote\n")
    for k, r in sorted(low, key=lambda x: x[1]):
        g = " ".join(f"{t[0]}[{'+'.join(t[1])}:{t[2]}]" if t[1] else t[0] for t in R[k])
        kk = " ".join(f"{t[0]}[{'+'.join(t[1])}]" if t[1] else t[0] for t in K[k])
        f.write(f"{k}\t{r:.2f}\t{g}\t{kk}\t\t\n")
print(len(pairs), "pairs;", len(low), "low verses")

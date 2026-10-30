#!/usr/bin/env python3
"""Gloss sanity check: STEP short gloss vs the Strong's dictionary entry.
Flags (1) a proper-name gloss that the dictionary gives to a *different* number while
this number's own entry has no such name (the H4496 "Nohah" pattern: H4496 is 'rest',
"Nohah" is H5119), and (2) an extended-Strong's variant gloss (e.g. H6965a) standing in for
the base entry when neither the gloss nor its first letters appear in the dictionary entry."""
import json, re, sqlite3, sys
from collections import defaultdict

def letters(s): return re.sub(r"[^a-z]", "", (s or "").lower())

def check(step_entries, strongs_rows):
    """step_entries: {num: (gloss, extended)}; strongs_rows: {num: 'word definition'}"""
    S = {k: (v or "").lower() for k, v in strongs_rows.items()}
    by_name = defaultdict(list)
    for n, (g, _) in step_entries.items():
        if g[:1].isupper() and not g.isupper():
            by_name[letters(g)].append(n)
    bad = []
    for n, (g, ext) in step_entries.items():
        if n not in S: continue
        nm = letters(g)
        if g[:1].isupper() and not g.isupper() and len(nm) >= 3 and nm[:4] not in letters(S[n]):
            owners = [o for o in by_name[nm] if o != n and o in S and nm[:4] in letters(S[o])]
            if owners and re.search(r"\b1\)\s*[a-z]", S[n]) and "=" not in S[n].split(";")[0]:
                bad.append((n, g, "name belongs to " + ",".join(owners)))
                continue
        if ext and ext != n and re.fullmatch(r"[HG]\d+[a-zA-Z]", ext.replace("H0", "H").replace("G0", "G")):
            words = [w for w in re.findall(r"[a-z]+", g.lower()) if len(w) > 2]
            if g.startswith("(") or (words and not any(w[:4] in S[n] for w in words)):
                bad.append((n, g, "variant gloss " + ext))
    return bad

def load_lex(rt):
    d = {}
    for f in ("tbesh-hebrew.json", "tbesg-greek.json"):
        for k, v in json.load(open(f"{rt}/theolog-ai/data/biblical-languages/stepbible-lexicons/{f}")).items():
            m = re.fullmatch(r"([HG])0*(\d+)", k)
            if m: d[f"{m.group(1)}{int(m.group(2))}"] = (v.get("gloss") or "", v.get("extendedStrongs") or "")
    s = dict(sqlite3.connect(f"{rt}/strongs.db").execute(
        "SELECT number, coalesce(word,'')||' '||coalesce(definition,'') FROM strongs"))
    return d, s

if __name__ == "__main__":
    d, s = load_lex(sys.argv[1])
    bad = check(d, s)
    for b in bad: print("\t".join(b))
    print(len(bad), "flagged", file=sys.stderr)

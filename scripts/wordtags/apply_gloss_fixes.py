#!/usr/bin/env python3
"""Apply gloss_fixes.tsv to Lex's STEP Hebrew lexicon JSON by editing only the "gloss" line
of each listed entry (keeps the file's layout and the diff small).
Usage: apply_gloss_fixes.py LEXICON_JSON FIXES_TSV [NUMBER ...]   (default: every row)"""
import json, re, sys
path, fixes = sys.argv[1], sys.argv[2]; only = set(sys.argv[3:])
rows = [l.rstrip("\n").split("\t") for l in open(fixes, encoding="utf-8") if l.strip() and not l.startswith("#")]
lines = open(path, encoding="utf-8").read().split("\n")
idx = {}
for i, l in enumerate(lines):
    m = re.fullmatch(r'  "([HG]\d+[A-Za-z]?)": \{', l)
    if m: idx[m.group(1)] = i
done = 0
for num, wrong, right, _ in rows:
    if only and num not in only: continue
    key = num[0] + num[1:].zfill(4)
    i = idx[key]
    for j in range(i + 1, i + 12):
        if lines[j].startswith('    "gloss": '):
            cur = json.loads(lines[j].split(": ", 1)[1].rstrip(","))
            if cur == right: break
            assert cur == wrong, (num, cur)
            lines[j] = '    "gloss": ' + json.dumps(right, ensure_ascii=False) + ("," if lines[j].endswith(",") else "")
            done += 1; break
open(path, "w", encoding="utf-8").write("\n".join(lines))
json.load(open(path, encoding="utf-8"))
print("fixed", done)

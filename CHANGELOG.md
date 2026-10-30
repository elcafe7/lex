# Changelog

## Unreleased — geneva-word branch

- **Word mode for Geneva 1599, KJV 1611 and KJV 1769.** `lex -B gen words Gen 1:1`
  (or `-B kj16`, `-B kjv`) lists each word with its Strong's number, short gloss and
  transliteration. Numbers come from `runtime-data/wordtags.db` (new): the CrossWire
  KJV Strong's tagging, used directly for KJV 1769 (92.2% of words tagged) and
  projected onto the KJV 1611 (93.0%) and Geneva (91.8%) texts. Every tag is shown
  the same way; a confidence grade per word is kept in the data for a later review
  pass. Other editions print a "not available" message. Built by
  `scripts/build_wordtags.py`; review overrides in `scripts/wordtags/overrides_gen.tsv`.
- **Small-word rule:** a function word (the, of, upon, him, ...) no longer borrows a
  number that belongs to a content word elsewhere in the verse unless its nearest
  content neighbour in the same clause carries that number (Isaiah 53:5 "vpon him"
  no longer shows H2250 "stripes").
- **KJV tag extraction fix:** empty `<w/>` elements in the KJV module (Greek words
  with no English, mostly the article) were read as opening tags, so about 7,000 NT
  words per edition took the wrong number (John 3:16 "For" showed G3588; now G1063).
- KJV 1611 word mode shows the stored `&thorn;` abbreviation as "þ".
- **KJV 1611 text:** 27 run-together words split (e.g. Isaiah 53:3 "ofsorrows" →
  "of sorrows"), search index updated. Script `scripts/fix_kj16_glued.py`, list in
  `scripts/wordtags/kj16_glued_fixes.tsv`.
- **STEP Hebrew glosses:** H4496 now "rest" (was "Nohah", the name H5119), plus 11
  more glosses that had been taken from the wrong entry (list in
  `scripts/wordtags/gloss_fixes.tsv`).
- New tests: `python -m unittest tests.test_wordtags`.

## 2.6.5 — 2026-10-30

- **Geneva Bible text replaced.** `runtime-data/bible_versions/gen.db` is now the
  Geneva 1599 text (rebuilt from scrollmapper Geneva1599 @e1b254c, with Apocrypha
  labels fixed). Releases v2.6.4 and earlier shipped an older 1587/KJV-like
  `gen.db`. New sha256: `690c4fd90eb9f3ab6260d3309556eea8716a8ff8a5e04003bc566ff7dafe25d9`.
  Geneva Genesis 1:1 now reads "In the beginning God created the heauen and the earth."
- Brings the release line back onto `main`, including the security hardening
  done since v2.6.2 (ReDoS-safe parsers, safe XML import, restricted update
  fetches and data/export paths, Pillow>=13).
- Reference parsing: restores the v2.6.3/v2.6.4 fixes on top of the hardened
  parser — typographic dashes (`John 3:16–18`), spaced ranges (`John 3:16 - 18`)
  and hyphenated book names (`1-chronicles`, `song-of-solomon`).
- npm launcher: when it resolves a newer GitHub release than its own version,
  it now extracts that release's archive root instead of failing.
- `manifest.json` version corrected (main still said 2.6.2).
- `requirements.txt` now matches `pyproject.toml` (adds python-pptx and
  Pillow>=13), so the npm launcher stops re-running pip on every start.

## 2.6.4 — 2026-10-18

- Forgiving book aliases, including `2 chron <chapter> <verse>` and hyphenated
  book names.

## 2.6.3 — 2026-10-01

- Unicode (typographic) dashes accepted in verse ranges.

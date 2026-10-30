# Changelog

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

## 2.6.4 — 2026-10-18

- Forgiving book aliases, including `2 chron <chapter> <verse>` and hyphenated
  book names.

## 2.6.3 — 2026-10-01

- Unicode (typographic) dashes accepted in verse ranges.

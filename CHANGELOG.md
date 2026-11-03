# Changelog

## 2.6.6 — 2026-11-03

- **Bare flags explain themselves.** Any flag or subcommand that needs an
  argument, run without one, prints a short command-specific explainer (what it
  does, usage, examples, valid values) and exits 0. It never errors and never
  changes config, theme, or history. Covers `-v`, `-B`/`--bible`, `--page`,
  `--limit`, `--mode`, `--format`, `--ratio`, `-i`, `-s`, `-d`, `lex version`,
  `lex bible`, and the bare `read`, `study`, `search` (including scope-only
  `lex search -nt`), `web`, `manuscript`, `export`, `strongs`, `topic`/`naves`,
  `commentary`, and `define` pages.
- **Fixed: bare `lex -v` crashed** with argparse's "expected one argument". It
  now prints the `-v` explainer and lists the 7 Bible versions (`esv`, `kjv`,
  `kj16`, `nasb`, `gen`, `lxx`, `vulg`) with the current default marked.
- **Fixed: `lex -B kjv` with no reference saved KJV as the default.** `-B` is now
  always a one-command override and never writes `~/.lex_config.json`; with no
  command it prints the `-B` explainer and changes nothing. `-v <id>` is still
  the sticky default. `-B` accepts the `vulgate` alias and unknown ids get the
  valid list instead of an argparse error.
- `lex help`, the intro screen, `docs/components/LEX_CLI.md`, and the user guide
  no longer describe `lex -v` as an interactive menu.
- **Fixed: `lex strongs G3056` crashed** with Rich `MarkupError: closing tag
  '[/]' ... has nothing to close` (5,176 of 14,298 Strong's entries, 5,145
  Greek and 31 Hebrew, crashed on 2.6.5). Lexicon tags with attributes such as
  `<ref='Mat.8.8'>` lost their opening style but kept the closing `[/]`. The
  lexicon converter now matches tag names properly, escapes source text with
  `rich.markup.escape`, and always emits balanced markup, so brackets in
  entries (`[in LXX chiefly for ...]`, `Mrk.16:[20]`) now show instead of being
  swallowed. The same escaping now covers user queries and data shown in
  `lex history`, `lex strongs <word>`, search, creed, Nave's, manuscript, and
  study lexicon tables, so a query like `lex manuscript "x[/b]"` no longer
  crashes (and no longer breaks `lex history` afterwards).
- New regression tests: `tests/test_flag_explainers.py` and
  `tests/test_strongs_markup.py` (`python3 -m unittest discover -s tests`).

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

# Changelog

## Unreleased

- **New: `--json` machine-readable output (#16).** One compact JSON document on
  stdout (`schema_version` 1, see `docs/json-output.md`) for `read`, `study`
  (ESV direct, other editions labelled proxy; LXX/Vulgate when their study data
  is installed), `strongs` (number and English), `web`, `search`, `define`,
  `commentary`, `naves`/`topic`, `creed`, and `history`. Never prompts, never
  writes config/theme/history, keeps `-B` one-command, refuses `-v`. Errors are
  JSON on stderr with exit codes 1/2/3/4. The npm launcher stays quiet in JSON
  mode and reports its own failures as JSON.
- **New: `--plain`.** Normal output as plain text: no colour, borders, prompts,
  or animation.
- **Fixed: raw JSON in some Strong's entries.** 209 entries (e.g. G5594) showed
  `{"_":…,"strongsref":[…]}`; they now read as text with the referenced numbers
  filled in.
- **`NO_COLOR` is honoured** (previously only `LEX_NO_COLOR`).

- **`lex` vs. the flex lexer (#1).** Many systems already have `/usr/bin/lex`
  (flex). `setup.sh` now also adds `~/.local/bin` to `~/.zshrc` when zsh is
  your shell, then checks which `lex` a new terminal will run, names any flex
  `lex` it finds, and says how to fix `PATH` if Lex is not first. New
  `./setup.sh --alias NAME` installs a second name (e.g. `lexb`) that cannot
  clash. New `scripts/check_lex_command.sh` runs the same check any time. The
  command is still `lex`.
- **Fixed: study mode said "No local interlinear data found" (#2)** when Lex ran
  from the `~/bible-lexicon-data` fallback, even with the data there (the JSON
  loader only allowed `runtime-data/`). When the interlinear files really are
  missing, study mode now names the data folder and missing files and says to
  run `lex update`. Full clones and npm installs already ship the data.
- **Fixed: piped or closed stdin crashed follow-up prompts.** `lex study`,
  `lex John 3:16 -i`, `lex search`, and the export/navigation prompts ended
  with an `EOFError` traceback (exit 1) when stdin was not a terminal, e.g.
  `lex study John 1:1 < /dev/null` or `echo | lex search israel`. Lex now
  skips follow-up prompts when stdin is not a TTY, and Ctrl-D or Ctrl-C at a
  prompt exits 0 with no traceback. Interactive terminals are unchanged.

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

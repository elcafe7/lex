# Changelog

## Unreleased

- **Creeds: numbered, line-aligned original and English (#12).** The Apostles',
  Nicene, Athanasian, and Chalcedonian texts now show as numbered clause pairs
  (#, Latin/Greek, #, English: the number labels both sides) under their section headings, numbered through the
  whole document, instead of one paragraph per section. Narrow terminals stack
  each original line above its English. Wording is unchanged: the lines join
  back to the same English and original text. `lex --json creed` adds a
  `lines` array per section. The aligned lines live in
  `runtime-data/creeds-aligned.json` so Lex Web can reuse them.
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
- **Help spellings.** `--help`, `-help`, `-h`, and `--h` all print the same
  full help, at the top level and after a subcommand (`lex study --help`).
- **Dashes on flags.** Known long options also accept one dash (`-json`,
  `-plain`, `-update`) and single-letter flags also accept two (`--h`,
  `--B kjv`). Theme flags accept either form (`-light` / `--light`). Attached
  short values (`-Bkjv`, `-vkjv`), negative numbers, and search scopes
  (`-nt`, `-ot`) are left alone. `-v` still sets the default Bible;
  `--version` (or `-version`) prints the Lex version.
- **Douay-Rheims 1899 (`dra`), from #5.** Adds the public-domain Douay-Rheims
  1899 American Edition, packaged from eBible.org `engDRA`, as `lex -B dra`.
  The 73-book Catholic canon is included (Tobit, Judith, Wisdom, Sirach,
  Baruch, 1–2 Maccabees, and the longer Esther and Daniel). Book names match
  the other English editions (for example 1 Samuel, not 1 Kings); Douay names
  such as Tobias, Ecclesiasticus, 3 Kings, 4 Kings, Isaias, and Apocalypse
  also work. Psalm numbers follow the traditional DRA/Vulgate numbering
  (Psalm 22 is "The Lord ruleth me"). No version bump in this change; the
  edition will ship in the next release archive and npm data download.

- **DRA packager confines the VPL path (CodeQL `py/path-injection`, alert
  #65).** `package_dra_1899` opens the source file only after
  `safe_source_file` confirms the basename stays inside its parent
  directory, matching the other packagers. A symlink that escapes that
  directory is refused.

- **LXX lemma import confines `LxxLemmas` (CodeQL `py/path-injection`, alert
  #58).** `scripts/import_lxx_openscriptures_lemmas.py` resolves `--source`,
  joins `LxxLemmas` under that real path, checks the result stays inside the
  source directory, requires the directory to exist, and rejects a symlink
  that escapes it. Shared helper: `safe_source_dir()` in
  `scripts/safe_paths.py`.

## 2.6.8 — 2026-11-09

- **Verified releases (#11, #10).** Tag pushes now build the release, write a
  CycloneDX SBOM, scan it with OSV-Scanner (fails on CVSS 7.0 or higher),
  write and check `SHA256SUMS`, attest build provenance and only then publish.
  Each clean release opens a PR with its report folder under
  `security/reports/`. See `docs/RELEASE_VERIFICATION.md`.

- **Filesystem boundaries for untrusted paths (CodeQL `py/path-injection`,
  #6, #8, #9).** Paths built from downloaded or updated data (the `lex
  --update` manifest, the manuscript profiles manifest, files inside
  downloaded import checkouts) or from the environment must now resolve inside
  a known Lex directory; `..`, encoded `..%2f`, absolute paths, NUL bytes and
  symlinks that escape are refused. `LEX_PDF_FONT` / `LEX_PDF_HEBREW_FONT`
  must name a `.ttf`, `.otf` or `.ttc` file in the bundled, system or user
  font folders. The npm launcher checks every release-archive entry before
  and after extraction (no absolute, `..`, out-of-root, symlink or hard-link
  entries) and only accepts `vX.Y.Z` release tags.

## 2.6.7 — 2026-11-06

- **`lex --update` now updates the CLI too, not only the data (#19).** Before,
  `lex --update` pulled the 2.6.6 data but left an npm install at 2.6.2, so
  `lex --version` still said 2.6.2. Now the npm launcher checks the npm
  registry for a newer `@n8te_/lex-cli`. When the install is a global npm
  install (`<prefix>/lib/node_modules/@n8te_/lex-cli`, e.g. under `~/.local`)
  and that folder is writable, it runs
  `npm install -g --prefix <prefix> @n8te_/lex-cli@<latest>`, checks the new
  version, and hands off to the new launcher. The data update then runs as
  before. Afterwards Lex prints both versions, e.g. `Lex CLI: 2.6.6 (updated
  from 2.6.2)` and `Lex data: 2.6.6 (up to date)`.
  If the CLI can't be updated (no write permission, npx or project-local
  install, npm error, or offline), Lex says so, prints the exact command to
  run, and never claims the CLI is current. An npm upgrade that fails makes
  `lex --update` exit 1. Git clones stay data-only and print the
  `git pull --ff-only && ./setup.sh` command when their code is older than
  the data. `-v` and `-B` behave as before. New tests:
  `npm/lex-cli/test/self-update.test.js` and `tests/test_update_versions.py`.

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

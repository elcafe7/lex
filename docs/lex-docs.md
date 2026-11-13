# Lex CLI Docs

Last updated: November 3, 2026, 12:47 PM ET

*Local-first Bible study CLI*

Lex reads Scripture, searches local Bible databases, opens interlinear study views, maps cross-references and manuscript witnesses, browses creeds, and exports study work from the terminal.

Prefer a browser? [Lex Web](https://apocalypse.press/lex-web/) is the browser edition of Lex, with the same seven Bible editions.

- Version 2.6.5
- Python 3.12+
- Offline SQLite/JSON runtime data
- macOS/Linux terminal workflow

> These docs target Lex 2.6.5, released October 30, 2026. Web version: <https://apocalypse.press/lex/docs/>

## Contents

- [What's New In 2.6.5](#whats-new-in-265)
- [Install And Update](#install-and-update)
- [Reference Syntax](#reference-syntax)
- [Command Reference](#command-reference)
- [Manuscript Map](#manuscript-map)
- [Interactive Actions](#interactive-actions)
- [Exports](#exports)
- [Bible Versions](#bible-versions)
- [Themes](#themes)
- [Troubleshooting](#troubleshooting)
- [Developer Backend Overview](#developer-backend-overview)
- [Runtime Data](#runtime-data)
- [Study Boundaries](#study-boundaries)
- [CLI Dispatch](#cli-dispatch)
- [Verification](#verification)

## What's New In 2.6.5

- **Geneva 1599 text.** The Geneva Bible (`gen`) is now the 1599 text. Releases up to 2.6.4 shipped an older 1587/KJV-like Geneva database. `lex -B gen Genesis 1:1` now reads "In the beginning God created the heauen and the earth."
- **Reference parsing.** Typographic dashes (`John 3:16–18`), spaced ranges (`John 3:16 - 18`) and hyphenated book names (`1-chronicles`, `song-of-solomon`) work again.
- **npm launcher.** When the launcher finds a newer GitHub release than its own version, it now installs that release instead of failing.
- **Security hardening.** Safer text parsers, safe XML import, restricted update downloads and export paths, and Pillow 13 or newer.
- **Dependencies.** `requirements.txt` now matches `pyproject.toml`, so the npm launcher no longer reinstalls Python packages on every start.

## Install And Update

Lex needs Python 3.12 or newer. The recommended install is a full Git checkout because Lex depends on a large local runtime data bundle.

```sh
git clone https://github.com/elcafe7/lex.git
cd lex
./setup.sh
```

`setup.sh` creates a repo-local virtual environment, installs the Python dependencies, and writes a `lex` wrapper into `~/.local/bin`. That wrapper runs the checkout's `lex.py` directly.

### npm Launcher

For a one-line install, use the npm launcher (Node.js 18 or newer):

```sh
npm install -g @n8te_/lex-cli
lex --version
```

The npm package is a small launcher. On first run it downloads the latest Lex GitHub release, verifies its SHA-256 checksum, creates an isolated Python environment, installs the Python dependencies, and caches the full offline app under your user profile. Later runs reuse that cached install.

```sh
lex --npm-version   # Node launcher version
lex --version       # Lex application version
```

### Release Archive

To install from a GitHub release archive instead of `git clone`, check the archive against its checksum file before unpacking:

```sh
curl -LO https://github.com/elcafe7/lex/releases/download/v2.6.5/lex-v2.6.5.tar.gz
curl -LO https://github.com/elcafe7/lex/releases/download/v2.6.5/lex-v2.6.5.tar.gz.sha256
shasum -a 256 -c lex-v2.6.5.tar.gz.sha256
```

### Update Code

```sh
git pull
./setup.sh
```

### Update Runtime Data

```sh
lex update
```

`lex update` is data-only. It syncs manifest-tracked files under `runtime-data/` and does not overwrite CLI code.

## Reference Syntax

References are intentionally forgiving. Full names, common abbreviations, compact references, and chapter-only references are accepted.

### Single verse

```sh
lex John 3:16
lex jn 3:16
lex 2 jn 1:2
```

### Chapter

```sh
lex Romans 8
lex read John 1
lex Gen 1
```

### Verse range

```sh
lex Romans 8:28-39
lex John 3:16–18
lex John 3:16 - 18
```

### Compact and hyphenated

```sh
lex jn3:16
lex 1-chronicles 16:34
lex song-of-solomon 2:1
```

### Several references

```sh
lex John 3:16, Romans 5:8
lex study John 1:1, John 1:14
```

### One-time Bible selection

```sh
lex -B kjv John 3:16
lex -B gen Genesis 1:1
lex -B lxx Genesis 1:1
```

## Command Reference

This section covers the Lex 2.6.5 command surface. Optional flags can usually appear before or after the reference. Most commands show their own help when run without an argument, for example `lex search` or `lex strongs`.

### Start, Help, Credits

| Command | Purpose |
|---|---|
| `lex` | Open the main landing screen. |
| `lex help` | Show the full command map. |
| `lex --help` | Show every flag with a short description. |
| `lex --version` | Print the plain application version for scripts. |
| `lex --npm-version` | Print the npm launcher version (npm installs only). |
| `lex --credits` | Show data credits and source acknowledgements. |
| `lex update` or `lex --update` | Refresh manifest-managed runtime data. |

### Read Scripture

| Command | Purpose |
|---|---|
| `lex John 3:16` | Read a verse with nearby context. |
| `lex read John 3:16` | Explicit read command for a verse. |
| `lex Romans 8` | Read a full chapter. |
| `lex --next` | Move to the next verse or chapter from the saved history position. |
| `lex --prev` | Move to the previous verse or chapter from the saved history position. |
| `lex read all` | Read the top cross-references for the last verse you opened. |

### History

| Command | Purpose |
|---|---|
| `lex history` | Show recent Lex commands from the local query history. |
| `lex history --limit 10` | Show a smaller number of recent commands. |
| `lex history --clear` | Clear the local query history. |
| `lex history clear` | Alternate clear form. |

### Study

| Command | Purpose |
|---|---|
| `lex study John 1:1` | Show selected-version context, then source-language study tables, lexicon notes, topical associations, and TSK cross-references. |
| `lex John 3:16 -i` | Quick study mode using the interlinear flag. |
| `lex study Romans 1:1 --no-animate` | Disable pauses between study sections. |
| `lex study Romans 1:1 --animate` | Force pauses between study sections. |
| `lex -B lxx Genesis 1:1 -i` | Explicit LXX study path. This mode is in progress. |
| `lex -B vulg John 1:1 -i` | Explicit Vulgate study path. This mode is in progress. |

> **Note:** English-version Old Testament study is Masoretic-oriented through the local ESV Hebrew/Aramaic interlinear packet. LXX and Vulgate study data should not auto-populate while studying an English Bible.

### Search

| Command | Purpose |
|---|---|
| `lex search israel` | Search Scripture for a word. |
| `lex search "kingdom of god"` | Search for a phrase. Exact phrases rank first, then verses containing all terms. |
| `lex search israel --page 2` | Open a specific result page. |
| `lex search israel --limit 25` | Change result count per page. |
| `lex search covenant -jeremiah` | Scope search to one book. |
| `lex search beast -daniel-revelation` | Scope search to a book range. |
| `lex search resurrection -nt` | Scope search to a canon group. |

Search looks at verse text only, and likely misspellings are corrected and shown in the result footer. A bare book name in the query is searched as text, so use a scope such as `-john` to search within a book.

Supported group scopes include `-ot`, `-old-testament`, `-nt`, `-new-testament`, `-law`, `-pentateuch`, `-torah`, `-history`, `-wisdom`, `-poetry`, `-major`, `-major-prophets`, `-minor`, `-minor-prophets`, `-prophets`, `-gospels`, `-epistles`, `-letters`, `-pauline`, and `-general-epistles`.

### Verse Web

| Command | Purpose |
|---|---|
| `lex web John 3:16` | Show the verse plus ranked local cross-reference connections. |
| `lex web Romans 1:1 --limit 8` | Control the number of cross-reference rows. |

### Topics, Lexicons, Dictionary

| Command | Purpose |
|---|---|
| `lex naves grace` | Open a Nave's Topical Bible entry. |
| `lex topic grace` | Alias for Nave's topic lookup. |
| `lex naves John 3:16` | Find topical associations for a verse. |
| `lex G3056` | Look up a Strong's Greek number. |
| `lex H7225` | Look up a Strong's Hebrew number. |
| `lex strongs G3056` | Show the lexicon entry plus reverse verse usage from the ESV interlinear index. |
| `lex strongs G3056 --page 2 --limit 25` | Page through reverse verse usage. |
| `lex strongs G3056 --all` | Show all reverse verse usage results. |
| `lex strongs love` | Search Strong's entries by English gloss. |
| `lex strongs` | Open the Strong's help page. |
| `lex define covenant` | Show local dictionary and encyclopedia entries. |

### Commentary And Creeds

| Command | Purpose |
|---|---|
| `lex commentary John 3:16` | Show local commentary notes for a verse (Matthew Henry and John Calvin). |
| `lex commentary Romans 1` | Show local commentary notes for a chapter. |
| `lex creed` | Open the creed and confession navigator. |
| `lex creed nicene` | Open a specific creed or confession by search term. |
| `lex creed westminster confession` | Open a longer historical document by name. |

### Export

| Command | Purpose |
|---|---|
| `lex export "John 3:16"` | Open an interactive export menu. |
| `lex export "Romans 8:28-39" --mode read --format pptx` | Export read-mode verses to PPTX. |
| `lex export "Romans 8:28-39" --mode read --format png` | Export read-mode verses to PNG images. |
| `lex export "John 1:1" --mode study --format pdf` | Export study packet as PDF. |
| `lex export "John 1:1" --mode study --format docx` | Export study packet as DOCX. |
| `lex export "John 3:16" --mode web --format pdf` | Export verse web data as PDF. |
| `lex export "John 3:16" --mode web --format docx` | Export verse web data as DOCX. |

## Manuscript Map

Map a verse to the manuscript readings and witnesses Lex knows about, or open a manuscript profile by name or Gregory-Aland number.

| Command | Purpose |
|---|---|
| `lex manuscript John 1:1` | Show available readings and witnesses for a verse. |
| `lex manuscript Isaiah 53:11` | Old Testament readings work the same way. |
| `lex manuscript P66` | Open a manuscript profile. |
| `lex manuscript 1Qisaa` | Open a Dead Sea Scrolls profile. |
| `lex manuscript John 1:1 --limit 25` | Show more rows. |

Lex uses bundled or cached manuscript data first. Missing pieces are fetched one at a time from Lex Web and cached under `~/.cache/lex/manuscripts/` for offline reuse.

## Interactive Actions

| Mode | Keys |
|---|---|
| Study | `n` next verse, `p` previous verse, `r` read context, `w` verse web, `e` export, `q` done. |
| Search | `1-10` study result, `r #` read result, `n`/`p` page, `e` export, `q` quit. |
| Creeds | `n` next section, `p` previous section, `m` menu, `q` quit. |
| Read | Verse and chapter reads expose export actions in interactive terminals. |

## Exports

Lex writes exports under `~/Documents/lex_exports`. Study packets go under `~/Documents/lex_exports/studies`. The app tries to open finished files automatically and prints the path if the desktop blocks that.

| Mode | Formats | Notes |
|---|---|---|
| Read | PNG, PPTX | Use `--ratio 16:9` or `--ratio 1:1` for PNG exports. |
| Study | DOCX, PDF | Interactive study export also offers a PPTX verse slide. |
| Search | DOCX, PDF, PPTX | Exports the current result page from interactive search. |
| Verse Web | DOCX, PDF | Exports verse plus cross-reference connection data. |

## Bible Versions

Lex ships eight Bible editions. The default is the ESV.

| ID | Edition |
|---|---|
| `esv` | English Standard Version |
| `kjv` | King James Version (Oxford 1769) |
| `kj16` | King James Version (1611) |
| `nasb` | New American Standard Bible (1995) |
| `gen` | Geneva Bible (1599) |
| `dra` | Douay-Rheims (1899 American Edition) |
| `lxx` | Septuagint (Rahlfs 1935) |
| `brenton` | Brenton English Septuagint (1851) |
| `vulg` or `vulgate` | Clementine Vulgate |

`dra` includes the 73-book Catholic canon. Book names match the other English
editions; Douay names such as Tobias, Ecclesiasticus, 3 Kings, and Apocalypse
also work. Psalm numbers follow traditional DRA/Vulgate numbering (Psalm 22 is
"The Lord ruleth me"). The source is the public-domain eBible.org `engDRA` text.

`brenton` is Brenton's English translation of the Septuagint (1851, public
domain, eBible.org `eng-Brenton`): Old Testament plus Apocrypha, no New
Testament, Septuagint chapter and verse numbers. `lxx` remains the Greek text.
See `docs/editions/BRENTON.md` for provenance and alignment.

| Command | Purpose |
|---|---|
| `lex -v nasb` | Set the default Bible version. It stays until you change it. |
| `lex version kjv` or `lex bible kjv` | Same as `-v`: set the default Bible version. |
| `lex -v gen John 3:16` | Set the default and read in one step. |
| `lex -B lxx Genesis 1:1` | Use a Bible version for one command only. Your default does not change. |

## Themes

Lex chooses a theme from explicit flags, environment variables, saved config, terminal hints, and platform appearance.

| Command | Purpose |
|---|---|
| `lex -light` | Persist Studio Light theme. |
| `lex -dark` | Persist Blueprint Technical theme. |
| `lex -auto` | Clear saved theme and return to automatic detection. |
| `LEX_THEME=dark lex John 3:16` | Override the theme for one command. |
| `LEX_NO_COLOR=1 lex John 3:16` | Disable Lex color intentionally. |

## Troubleshooting

| Symptom | What To Check |
|---|---|
| `lex` not found | Confirm `~/.local/bin` is on `PATH` and rerun `./setup.sh`. For npm installs, confirm the npm global bin folder is on `PATH`. |
| `lex` runs the flex lexer (`lex --version` prints `lex 2.6.4`) | `/usr/bin/lex` is the flex lexer and comes first in `PATH`. Run `type -a lex` or `./scripts/check_lex_command.sh`, open a new terminal after `./setup.sh`, or install a second name with `./setup.sh --alias lexb`. |
| Setup or first run fails | Check `python3 --version`. Lex needs Python 3.12 or newer. |
| Not sure which version is running | Run `lex --version` for the Lex app and `lex --npm-version` for the npm launcher. |
| Wrong checkout running | Run `type -a lex` and `head -5 ~/.local/bin/lex`. |
| No reference result | Try the full book name, such as `lex 1 Corinthians 13`. |
| No study data | The verse can still be read, but study requires the matching local source-language dataset. If study says the interlinear data is not installed, run `lex update`. |
| Missing encyclopedia entry | The local ISBE import is incomplete. It currently covers only Volume II (Clement–Heresh). |

## Developer Backend Overview

`lex.py` is the active tracked CLI. It owns argument parsing, local SQLite access, JSON loading, terminal rendering, update checks, export generation, and interactive action loops.

### Entry Point

`main()` parses CLI flags and dispatches to `LexAgent` methods.

### Database Wrapper

`LexDB` is a small SQLite query helper used by read, search, study, creeds, and dictionaries.

### Runtime Agent

`LexAgent` resolves references, opens data stores, lazily loads JSON, renders output, and handles exports.

### State

Last navigation position is stored in `~/.lex_history`. Recent command history is stored in `~/.lex_query_history`. Theme config is stored in `~/.lex_config.json`.

## Runtime Data

A normal checkout resolves data under `runtime-data/`. If the runtime bundle is absent, Lex can fall back to `~/bible-lexicon-data` for local developer worktrees.

| Path | Use |
|---|---|
| `runtime-data/lexicon.db` | Legacy combined data and update sentinel. |
| `runtime-data/bible_versions/*.db` | Per-edition Bible text for read and search: `esv`, `kjv`, `kj16`, `nasb`, `gen` (Geneva 1599), `dra` (Douay-Rheims 1899), `lxx`, `brenton` (Brenton English Septuagint 1851), `vulg`. |
| `runtime-data/esv-data/data/esv/esv-interlinear.json` | ESV-backed Hebrew/Greek interlinear rows. |
| `runtime-data/esv-data/data/interlinear/strongs.json` | Interlinear Strong's metadata. |
| `runtime-data/lxx.db` | In-progress LXX morphology study data. |
| `runtime-data/cross_refs.db` | Treasury of Scripture Knowledge cross-reference graph. |
| `runtime-data/strongs.db` | Strong's lookup data. |
| `runtime-data/strongs_refs.db` | Reverse Strong's verse usage, built from the ESV interlinear data by `scripts/build_strongs_refs_db.py`. |
| `runtime-data/naves.db` | Nave's Topical Bible. |
| `runtime-data/places.db` | Place data. |
| `runtime-data/commentaries/*.db` | Matthew Henry and John Calvin commentaries. |
| `runtime-data/dictionary.db` | Dictionary entries. |
| `runtime-data/encyclopedia.db` | ISBE encyclopedia entries. |
| `runtime-data/creeds.db` | Creed/confession index rows. |
| `runtime-data/theolog-ai/data/historical-documents` | JSON fallback for full creed/confession texts. |
| `~/.cache/lex/manuscripts/` | Manuscript data fetched on demand and kept for offline reuse. |

`manifest.json` lists every runtime data file with its SHA-256 hash. `lex update` uses it to download only changed files, and the README has a short script to verify a Git checkout against it.

## Study Boundaries

Study mode has an important source-tradition boundary.

- Render the selected Bible version as the context panel first.
- English Old Testament study remains Masoretic-oriented through ESV Hebrew/Aramaic interlinear data.
- LXX study is a separate, in-progress path selected explicitly with `-B lxx`.
- Vulgate study is a separate, in-progress path selected explicitly with `-B vulg`.
- Do not populate LXX or Vulgate study rows while the selected Bible is English.
- Do not fall back across source traditions by matching only book/chapter/verse suffixes.

## CLI Dispatch

`main()` keeps command routing thin. Feature behavior should live on `LexAgent` methods.

| Route | Backend Method |
|---|---|
| `read` or bare reference | `display_verse()` / `render_chapter()` |
| `study` or `-i` | `display_verse(..., interlinear=True)` then `display_study()` |
| `help` | `display_command_map()` |
| `web` | `display_verse_web()` |
| `manuscript` | `display_manuscript()` |
| `commentary` | `display_commentary()` |
| `history` | `display_query_history()` |
| `search` | `display_search()` |
| `naves` / `topic` | `display_naves()` |
| `strongs` / `G####` / `H####` | `display_strongs()` or English Strong's search |
| `define` | Dictionary plus encyclopedia lookup |
| `creed` | `display_creed_navigator()` |
| `export` | `prompt_bulk_export()` or `handle_bulk_export()` |

## Verification

Minimum local checks after CLI changes:

```sh
python3 -m py_compile ./lex.py
python3 ./lex.py --version
python3 ./lex.py read John 3:16
python3 ./lex.py history --limit 5
python3 ./lex.py -B gen Genesis 1:1
python3 ./lex.py study Genesis 1:1 --no-animate
python3 ./lex.py -B lxx Genesis 1:1 -i --no-animate
python3 ./lex.py search israel --limit 2
python3 ./lex.py strongs G3056 --limit 2
python3 ./lex.py define heliodorus
```

Before changing install behavior, verify the local wrapper target:

```sh
type -a lex
head -5 ~/.local/bin/lex
```

---

© 2026 Lex CLI  
A project of [Jesus People SF](https://jesuspeoplesf.com) (a 501c3 ministry)  
and [Apocalypse Press](https://apocalypse.press)  
[Privacy](https://apocalypse.press/privacy/)

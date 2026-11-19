# For developers

Notes for people working on Lex itself. For contributing steps see [CONTRIBUTING.md](https://github.com/elcafe7/lex/blob/main/CONTRIBUTING.md).

## Backend overview

`lex.py` is the active tracked CLI. It owns argument parsing, local SQLite access, JSON loading, terminal rendering, update checks, export generation, and interactive action loops.

### Entry Point

`main()` parses CLI flags and dispatches to `LexAgent` methods.

### Database Wrapper

`LexDB` is a small SQLite query helper used by read, search, study, creeds, and dictionaries.

### Runtime Agent

`LexAgent` resolves references, opens data stores, lazily loads JSON, renders output, and handles exports.

### State

Last navigation position is stored in `~/.lex_history`. Recent command history is stored in `~/.lex_query_history`. Theme config is stored in `~/.lex_config.json`.

## Runtime data

A normal checkout resolves data under `runtime-data/`. If the runtime bundle is absent, Lex can fall back to `~/bible-lexicon-data` for local developer worktrees.

| Path | Use |
|---|---|
| `runtime-data/lexicon.db` | Legacy combined data and update sentinel. |
| `runtime-data/bible_versions/*.db` | Per-edition Bible text for read and search: `esv`, `kjv`, `kj16`, `nasb`, `gen` (Geneva 1599), `dra` (Douay-Rheims 1899), `lxx`, `vulg`. |
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

## Study boundaries

Study mode has an important source-tradition boundary.

- Render the selected Bible version as the context panel first.
- English Old Testament study remains Masoretic-oriented through ESV Hebrew/Aramaic interlinear data.
- LXX study is a separate, in-progress path selected explicitly with `-B lxx`.
- Vulgate study is a separate, in-progress path selected explicitly with `-B vulg`.
- Do not populate LXX or Vulgate study rows while the selected Bible is English.
- Do not fall back across source traditions by matching only book/chapter/verse suffixes.

## CLI dispatch

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

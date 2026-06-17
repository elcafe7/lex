# Lex Developer Guide

This guide is for maintaining Lex locally. It explains the active files, data flow, verification commands, and the current architectural boundaries.

## Active Entry Point

The active tracked CLI implementation is:

```text
./lex.py
```

On this workstation, the user's shell command resolves through wrapper scripts
that execute this checkout's `lex.py` directly. Verify with:

```bash
type -a lex
head -5 ~/.local/bin/lex
```

## Main Components

- [Lex CLI component](components/LEX_CLI.md): command dispatch, rendering, read/study/search/creed/define behavior.
- [Encyclopedia importer component](components/ENCYCLOPEDIA_IMPORTER.md): builds `encyclopedia.db` from ISBE OCR text.
- [Bible DB builder component](components/BIBLE_DB_BUILDER.md): builds `bible_versions/esv.db` from `lexicon.db`.
- [Bible Packager tool](scripts/package_bible.py): converts JSON/CSV/XML sources into per-edition `.db` files.
- [Manifest generator](scripts/generate_manifest.py): generates `manifest.json` with file hashes for the update system.
- [Data stores component](components/DATA_STORES.md): SQLite/JSON files Lex expects at runtime.
- [Bible edition standard](BIBLE_EDITION_STANDARD.md): schema expectations for per-edition Bible databases.
- [Encyclopedia import notes](ENCYCLOPEDIA_IMPORT_NOTES.md): future work for completing ISBE coverage.
- [Licensing notes](LICENSING.md): split-license recommendation and data-source cautions.

## Runtime Data Flow

1. `main()` parses CLI flags and query words.
2. `LexAgent` opens the local SQLite databases and lazily loads JSON datasets.
3. Read/search commands use the database specified by `-B` (defaulting to `bible_versions/esv.db`).
4. Study mode first renders context from the selected Bible DB. English-version OT study stays Masoretic-oriented through ESV Hebrew/Aramaic interlinear JSON, `strongs.db`, STEPBible lexicons, Nave's topics, and TSK rows from `cross_refs.db`. LXX and Vulgate study modes are still in progress and must remain separate explicit selected-version paths (`-B lxx`, `-B vulg`). Study/interlinear mode must not auto-populate LXX or Vulgate rows while studying an English Bible.
5. Query history is appended to `~/.lex_query_history` for `lex history`; navigation history remains the single-reference `~/.lex_history` file used by `--next` and `--prev`.
6. Creed mode uses `creeds.db` rows, with JSON fallback for placeholder historical documents.
7. Define mode queries Easton's dictionary from `dictionary.db` and ISBE entries from `encyclopedia.db`.

## Update System

Lex uses a manifest-driven update system:
- `manifest.json` tracks the `version` and the `sha256` hash of each tracked runtime data file.
- `lex update` fetches the remote manifest from GitHub and syncs only changed or missing data files.
- Code updates are handled by Git plus the local wrapper/install flow; Lex does not overwrite its own installed script.
- Manifest asset paths are accepted only under `runtime-data/` and are resolved with realpath containment checks before writes.
- Atomic updates are achieved by downloading to `.tmp` files and then performing an `os.replace`.

## Verification Commands

Compile:

```bash
python3 -m py_compile ./lex.py
```

Smoke test user commands:

```bash
python3 ./lex.py
python3 ./lex.py --version
python3 ./lex.py --credits
python3 ./lex.py read John 3:16
python3 ./lex.py history --limit 5
python3 ./lex.py study James 1:1
python3 ./lex.py study Genesis 1:1 --no-animate
python3 ./lex.py -B lxx Genesis 1:1 -i --no-animate
python3 ./lex.py search israel --limit 2
python3 ./lex.py define heliodorus
python3 ./lex.py creed nicene
```

Rebuild the encyclopedia DB:

```bash
python3 /home/n8te/bible-lexicon-data/scripts/build_encyclopedia_db.py
```

Rebuild split Lex domain DBs:

```bash
python3 /home/n8te/bible-lexicon-data/scripts/split_lexicon_db.py
```

## Current Design Constraints

- `lex.py` is still a single-file CLI. Keep feature sections clearly commented until it is split into modules.
- The working tree contains many local datasets and unrelated generated files. Do not delete or reset them casually.
- `lexicon.db`, split domain DBs, and `encyclopedia.db` are generated/compiled data artifacts with mixed source terms.
- The local encyclopedia is incomplete because only ISBE Volume II is currently imported.
- The Strong's source chain has conflicting local license notes. Treat redistribution cautiously until verified.

## Recommended Refactor Path

1. Move constants and data-source paths into a config module.
2. Split `LexAgent` into services: BibleReader, StudyRenderer, CreedBrowser, SearchService, DefineService.
3. Add a small test harness for non-interactive commands.
4. Add schema checks for each SQLite DB before command execution.
5. Add import tests for encyclopedia parsing and known ISBE headings.

## Documentation Rule

When adding a major file or command, add or update one component doc in `docs/components/`, then link it from this guide.

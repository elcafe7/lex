# Lex Developer Guide

This guide is for maintaining Lex locally. It explains the active files, data flow, verification commands, and the current architectural boundaries.

## Active Entry Point

The active tracked CLI implementation is:

```text
./lex.py
```

On this workstation, the user's shell alias resolves to `/usr/local/bin/lex`, which may point at a local copy or symlink of this script. Verify with:

```bash
alias lex
readlink -f /usr/local/bin/lex
```

## Main Components

- [Lex CLI component](components/LEX_CLI.md): command dispatch, rendering, read/study/search/creed/define behavior.
- [Encyclopedia importer component](components/ENCYCLOPEDIA_IMPORTER.md): builds `encyclopedia.db` from ISBE OCR text.
- [Bible DB builder component](components/BIBLE_DB_BUILDER.md): builds `bible_versions/esv.db` from `lexicon.db`.
- [Data stores component](components/DATA_STORES.md): SQLite/JSON files Lex expects at runtime.
- [Bible edition standard](BIBLE_EDITION_STANDARD.md): schema expectations for per-edition Bible databases.
- [Encyclopedia import notes](ENCYCLOPEDIA_IMPORT_NOTES.md): future work for completing ISBE coverage.
- [Licensing notes](LICENSING.md): split-license recommendation and data-source cautions.

## Runtime Data Flow

1. `main()` parses CLI flags and query words.
2. `LexAgent` opens the local SQLite databases and lazily loads JSON datasets.
3. Read/search commands use `bible_versions/esv.db`.
4. Study mode uses Bible rows plus ESV interlinear JSON, Strong's data, STEPBible lexicons, and TSK cross-references.
5. Creed mode uses `lexicon.db` rows, with JSON fallback for placeholder historical documents.
6. Define mode queries Easton's dictionary from `lexicon.db` and ISBE entries from `encyclopedia.db`.

## Verification Commands

Compile:

```bash
python3 -m py_compile ./lex.py
```

Smoke test user commands:

```bash
python3 ./lex.py
python3 ./lex.py --credits
python3 ./lex.py read John 3:16
python3 ./lex.py study James 1:1
python3 ./lex.py search israel --limit 2
python3 ./lex.py define heliodorus
python3 ./lex.py creed nicene
```

Rebuild the encyclopedia DB:

```bash
python3 /home/n8te/bible-lexicon-data/scripts/build_encyclopedia_db.py
```

## Current Design Constraints

- `lex.py` is still a single-file CLI. Keep feature sections clearly commented until it is split into modules.
- The working tree contains many local datasets and unrelated generated files. Do not delete or reset them casually.
- `lexicon.db` and `encyclopedia.db` are generated/compiled data artifacts with mixed source terms.
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

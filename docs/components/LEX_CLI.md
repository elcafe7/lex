# Component: Lex CLI (`lex.py`)

## Purpose

`lex.py` is the active tracked command-line application. It owns command parsing, local data access, and terminal rendering.

## Responsibilities

- Show the main landing page and credits screen.
- Read verses and chapters from `bible_versions/esv.db`.
- Navigate from the last opened passage with `--next` and `--prev`.
- Render study mode with context, source-language text, interlinear rows, lexicon notes, and TSK cross-references.
- Search Scripture with phrase search, all-terms fallback, highlighting, and pagination.
- Browse creeds/confessions with tradition grouping and section navigation.
- Define terms using dictionary and encyclopedia databases.
- Look up Strong's entries by number or English gloss.

## Key Runtime Paths

The script currently hardcodes runtime paths near the top of the file:

- `LEXICON_DB_PATH`: `~/bible-lexicon-data/lexicon.db`
- `BIBLE_DB_PATH`: `~/bible-lexicon-data/bible_versions/esv.db`
- `ENCYCLOPEDIA_DB_PATH`: `~/bible-lexicon-data/encyclopedia.db`
- `INTERLINEAR_PATH`: `~/bible-lexicon-data/esv-data/data/esv/esv-interlinear.json`
- `INTERLINEAR_STRONGS_PATH`: `~/bible-lexicon-data/esv-data/data/interlinear/strongs.json`
- `STEP_GREEK_PATH`: STEPBible Greek lexicon JSON
- `STEP_HEBREW_PATH`: STEPBible Hebrew lexicon JSON
- `HISTORICAL_DOCS_DIR`: TheologAI historical documents

## Internal Structure

The file is organized into these broad sections:

- Runtime paths and source mappings
- `LexDB` SQLite wrapper
- `LexAgent` shared utilities and lazy JSON loading
- Reference parsing and navigation helpers
- Landing/help/credits renderers
- Read mode
- Study mode
- Creed/confession mode
- Search mode
- Strong's, dictionary, and encyclopedia lookups
- `main()` CLI dispatch

## Important Behaviors

Study mode prefers interlinear rows that contain phrase data. This avoids duplicate heading rows overwriting real verse token data.

Search mode first tries an exact phrase FTS query. If that has no results, it falls back to an all-terms query.

Creed mode uses SQLite rows when available, but falls back to JSON files when the DB row is only a placeholder.

Define mode shows both dictionary and encyclopedia results when both are available.

## Known Risks

- The script is large enough that accidental cross-feature regressions are easy.
- Several file paths are hardcoded to the current workstation layout.
- History writes to `~/.lex_history` silently ignore failures.
- Some TSK previews are empty because not every cross-reference maps cleanly to an ESV DB row.
- Study mode currently caps lexicon notes but does not cap TSK cross-reference rows.
- `query.startswith("define")` and similar dispatch checks are permissive; future command names should avoid prefix collisions.

## Safe Change Checklist

After editing:

```bash
python3 -m py_compile ./lex.py
python3 ./lex.py
python3 ./lex.py study James 1:1
python3 ./lex.py search israel --limit 2
python3 ./lex.py define heliodorus
```

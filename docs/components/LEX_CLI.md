# Component: Lex CLI (`lex.py`)

## Purpose

`lex.py` is the active tracked command-line application. It owns command parsing, local data access, and terminal rendering.

## Responsibilities

- Show the main landing page and credits screen.
- Read verses and chapters from `bible_versions/esv.db`.
- Soft-animate study output by pausing briefly between major sections.
- Navigate from the last opened passage with `--next` and `--prev`.
- Render study mode with context, source-language text, interlinear rows, lexicon notes, and TSK cross-references.
- Offer study actions for next/previous verse, read context, verse web, and DOCX/PDF export.
- Render verse web mode with a centerpiece verse and ranked local cross-reference connections.
- Search Scripture with phrase search, all-terms fallback, highlighting, pagination, book/group scopes, and abbreviation-friendly references.
- Navigate multi-page search results interactively with an action bar for study/read/page/export commands.
- Export search pages and study packets to DOCX/PDF under `~/Documents/lex_exports`.
- Browse creeds/confessions with tradition grouping and section navigation.
- Define terms using dictionary and encyclopedia databases.
- Look up Strong's entries by number or English gloss.

## Key Runtime Paths

The script resolves runtime paths near the top of the file. A normal GitHub
clone uses bundled JSON under `runtime-data/`; local developer checkouts can
also use full upstream data directories beside `lex.py`.

- `LEXICON_DB_PATH`: `~/bible-lexicon-data/lexicon.db`
- `BIBLE_DB_PATH`: `~/bible-lexicon-data/bible_versions/esv.db`
- `ENCYCLOPEDIA_DB_PATH`: `~/bible-lexicon-data/encyclopedia.db`
- `CROSS_REFS_DB_PATH`: `~/bible-lexicon-data/cross_refs.db`
- `STRONGS_DB_PATH`: `~/bible-lexicon-data/strongs.db`
- `DICTIONARY_DB_PATH`: `~/bible-lexicon-data/dictionary.db`
- `CREEDS_DB_PATH`: `~/bible-lexicon-data/creeds.db`
- `PLACES_DB_PATH`: `~/bible-lexicon-data/places.db`
- `CONFIG_FILE`: `~/.lex_config.json`
- `INTERLINEAR_PATH`: `runtime-data/esv-data/data/esv/esv-interlinear.json`
- `INTERLINEAR_STRONGS_PATH`: `runtime-data/esv-data/data/interlinear/strongs.json`
- `STEP_GREEK_PATH`: bundled STEPBible Greek lexicon JSON
- `STEP_HEBREW_PATH`: bundled STEPBible Hebrew lexicon JSON
- `HISTORICAL_DOCS_DIR`: bundled TheologAI historical documents

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

Search scopes are parsed from single-dash tokens after the query:

```bash
lex search covenant -jeremiah
lex search beast -daniel-revelation
lex search resurrection -nt
lex search covenant -major
```

The single-dash scope parser protects search tokens such as `-daniel-revelation` from being consumed as short CLI flags.

Search and study exports use `python-docx` for DOCX and ReportLab for PDF. PDFs register local Noto fonts when available to avoid default Helvetica character loss, especially for Greek/Hebrew study packets.

Creed mode uses SQLite rows when available, but falls back to JSON files when the DB row is only a placeholder.

Define mode shows both dictionary and encyclopedia results when both are available.

Theme selection happens before Rich initializes the global console. Lex checks,
in order: explicit CLI flags, `LEX_THEME`, saved config, generic terminal/theme
environment hints, `COLORFGBG`, Apple Terminal/iTerm profile backgrounds on
macOS, GNOME/KDE appearance settings on Linux, platform appearance fallback, and
finally dark mode. `lex -light` and `lex -dark` force a palette for the current
run and persist it in `~/.lex_config.json` for relaunches. `lex -auto` clears
the saved preference and returns to detection. Lex ignores global `NO_COLOR` for
themed terminal output; set `LEX_NO_COLOR=1` to intentionally disable Lex color.

## Known Risks

- The script is large enough that accidental cross-feature regressions are easy.
- Several file paths are hardcoded to the current workstation layout.
- History writes to `~/.lex_history` silently ignore failures.
- Some TSK previews are empty because not every cross-reference maps cleanly to an ESV DB row.
- Study mode currently caps lexicon notes but does not cap TSK cross-reference rows.
- `query.startswith("define")` and similar dispatch checks are permissive; future command names should avoid prefix collisions.

Animation is intentionally soft: read output stays stable, while study mode can pause briefly between major sections in interactive terminals. It can be forced with `--animate` or suppressed with `--no-animate`.

## Safe Change Checklist

After editing:

```bash
python3 -m py_compile ./lex.py
python3 ./lex.py
python3 ./lex.py study James 1:1
python3 ./lex.py search israel --limit 2
python3 ./lex.py search covenant -major --limit 2
python3 ./lex.py 2 jn 1:2
python3 ./lex.py define heliodorus
```

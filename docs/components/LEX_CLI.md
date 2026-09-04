# Component: Lex CLI (`lex.py`)

## Purpose

`lex.py` is the active tracked command-line application. It owns command parsing, local data access, and terminal rendering.

## Responsibilities

- Show the main landing page and credits screen.
- Read verses and chapters from the selected Bible DB, defaulting to `bible_versions/esv.db`.
- Soft-animate study output by pausing briefly between major sections.
- Navigate from the last opened passage with `--next` and `--prev`.
- Store and display recent user commands with `lex history`.
- Render study mode with selected-version context, source-language text, interlinear rows, lexicon notes, topical associations, and TSK cross-references.
- Use the ESV Hebrew/Aramaic interlinear packet for English/Masoretic study. LXX and Vulgate study modes are in progress and should remain separate explicit selected-version paths as their data layers mature.
- Offer study actions for next/previous verse, read context, verse web, DOCX/PDF packet export, and PPTX verse-slide export.
- Render verse web mode with a centerpiece verse and ranked local cross-reference connections.
- Search Scripture with phrase search, all-terms fallback, highlighting, pagination, book/group scopes, and abbreviation-friendly references.
- Navigate multi-page search results interactively with an action bar for study/read/page/export commands.
- Export search pages to DOCX/PDF/PPTX, study packets to DOCX/PDF, study verse slides to PPTX, and read-mode output to PNG/PPTX under `~/Documents/lex_exports`.
- Browse creeds/confessions with tradition grouping and section navigation.
- Define terms using dictionary and encyclopedia databases.
- Look up Strong's entries by number or English gloss, including reverse ESV verse usage for indexed Strong's numbers.

## Key Runtime Paths

The script resolves runtime paths near the top of the file. A normal GitHub
clone uses bundled JSON under `runtime-data/`; local developer checkouts can
also use full upstream data directories beside `lex.py`.

- `LEXICON_DB_PATH`: `runtime-data/lexicon.db`
- Bible editions: `runtime-data/bible_versions/<edition>.db`
- `ENCYCLOPEDIA_DB_PATH`: `runtime-data/encyclopedia.db`
- `CROSS_REFS_DB_PATH`: `runtime-data/cross_refs.db`
- `STRONGS_DB_PATH`: `runtime-data/strongs.db`
- `STRONGS_REFS_DB_PATH`: `runtime-data/strongs_refs.db`
- `DICTIONARY_DB_PATH`: `runtime-data/dictionary.db`
- `CREEDS_DB_PATH`: `runtime-data/creeds.db`
- `PLACES_DB_PATH`: `runtime-data/places.db`
- `LXX_DB_PATH`: `runtime-data/lxx.db`
- `CONFIG_FILE`: `~/.lex_config.json`
- `HISTORY_FILE`: `~/.lex_history` for next/previous navigation
- `QUERY_HISTORY_FILE`: `~/.lex_query_history` for `lex history`
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

Study mode should preserve the selected Bible version in the context panel.
English-version OT study should remain Masoretic-oriented and must not
auto-populate Septuagint or Vulgate study rows. LXX study should run only for an
explicit LXX selection, such as `-B lxx`, and is still being built out from its
own data layer. Vulgate study should likewise be a separate explicit `-B vulg`
path and is still in progress. Other selected versions should report that
interlinear study is unavailable rather than falling back across source
traditions by reference suffix.

Search mode first tries an exact phrase FTS query. If that has no results, it falls back to an all-terms query.
The FTS query is constrained to verse text and excludes heading rows, so a query
like `lex search Jeremiah` returns verses where Jeremiah appears in the text
rather than matching the book-name metadata for every verse in Jeremiah.

Search scopes are parsed from single-dash tokens after the query:

```bash
lex search covenant -jeremiah
lex search beast -daniel-revelation
lex search resurrection -nt
lex search covenant -major
```

The single-dash scope parser protects search tokens such as `-daniel-revelation` from being consumed as short CLI flags.

Search and study exports use `python-docx` for DOCX, ReportLab for PDF, `python-pptx` for PPTX, and Pillow for PNG read exports. PDFs register local Noto fonts when available to avoid default Helvetica character loss, especially for Greek/Hebrew study packets.

Creed mode uses SQLite rows when available, but falls back to JSON files when the DB row is only a placeholder.

Define mode shows both dictionary and encyclopedia results when both are available.

Strong's mode supports a full help page with bare `lex strongs`, direct number
lookups such as `lex strongs G3056`, direct shortcuts such as `lex G3056`,
English/gloss lookups such as `lex strongs love`, and reverse verse usage
paging:

```bash
lex strongs G3056 --page 2 --limit 25
lex strongs G3056 --all
```

Reverse usage is built from `runtime-data/strongs_refs.db`, which is generated
from the bundled ESV interlinear data by `scripts/build_strongs_refs_db.py`.
When the active Bible edition has a matching canonical reference, Lex projects
the reverse usage verse list into that selected edition's verse text.

Theme selection happens before Rich initializes the global console. Lex checks,
in order: explicit CLI flags, `LEX_THEME`, saved config, generic terminal/theme
environment hints, `COLORFGBG`, Apple Terminal/iTerm profile backgrounds on
macOS, GNOME/KDE appearance settings on Linux, platform appearance fallback, and
finally dark mode. `lex -light` and `lex -dark` force a palette for the current
run and persist it in `~/.lex_config.json` for relaunches. `lex -auto` clears
the saved preference and returns to detection. Lex ignores global `NO_COLOR` for
themed terminal output; set `LEX_NO_COLOR=1` to intentionally disable Lex color.

`lex --version` is reserved for plain, non-interactive application version
output. `lex -v` opens the Bible-version picker in an interactive terminal and
prints the version list without prompting when stdin is non-interactive.

`lex history` reads `~/.lex_query_history`, which is a JSON-lines file capped to
the most recent local commands. It is intentionally separate from
`~/.lex_history`, which stores only the last navigable reference for `--next`
and `--prev`.

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
python3 ./lex.py --version
python3 ./lex.py history --limit 5
python3 ./lex.py
python3 ./lex.py study James 1:1
python3 ./lex.py -B lxx Genesis 1:1 -i --no-animate
python3 ./lex.py search israel --limit 2
python3 ./lex.py search covenant -major --limit 2
python3 ./lex.py search Jeremiah --limit 2
python3 ./lex.py strongs G3056 --limit 2
python3 ./lex.py 2 jn 1:2
python3 ./lex.py define heliodorus
```

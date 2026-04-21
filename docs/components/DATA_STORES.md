# Component: Runtime Data Stores

Lex depends on local SQLite and JSON files. Most features are data-driven, so missing or stale data usually appears as missing search results, missing interlinear rows, or empty definition panels.

## SQLite Databases

### `lexicon.db`

Path:

```text
runtime-data/lexicon.db
```

Used for:

- Source/fallback store for legacy combined data.

Lex now prefers domain-specific DBs below and falls back to `lexicon.db` when a split DB is missing.

### `cross_refs.db`

Path:

```text
runtime-data/cross_refs.db
```

Used for Treasury of Scripture Knowledge cross-references.

Important tables:

- `cross_refs`

### `strongs.db`

Path:

```text
runtime-data/strongs.db
```

Used for Strong's Hebrew/Greek lookup and study-mode lexicon fallback.

Important tables:

- `strongs`
- `strongs_fts`

### `dictionary.db`

Path:

```text
runtime-data/dictionary.db
```

Used for Easton's dictionary results in `lex define <term>`.

Important tables:

- `dictionary`
- `dictionary_fts`

### `creeds.db`

Path:

```text
runtime-data/creeds.db
```

Used for creed/confession browsing and section rendering.

Important tables:

- `creeds`

### `places.db`

Path:

```text
runtime-data/places.db
```

Prepared for future place lookup support.

Important tables:

- `places`

### `bible_versions/esv.db`

Path:

```text
runtime-data/bible_versions/esv.db
```

Used for:

- Read mode
- Chapter rendering
- Scripture search
- Cross-reference previews

Important tables:

- `bible`
- `bible_fts`

Reference format:

```text
esv:Book:Chapter:Verse
```

Example:

```text
esv:John:3:16
```

### `encyclopedia.db`

Path:

```text
runtime-data/encyclopedia.db
```

Used for:

- Encyclopedia entries in `lex define <term>`

Important tables:

- `encyclopedia`
- `encyclopedia_fts`

Current limitation: only ISBE Volume II is imported.

## JSON Data

### ESV Interlinear

Clone path:

```text
runtime-data/esv-data/data/esv/esv-interlinear.json
```

Developer checkout fallback:

```text
~/bible-lexicon-data/esv-data/data/esv/esv-interlinear.json
```

Used for:

- Study mode token alignment
- Original-language display

### Interlinear Strong's

Clone path:

```text
runtime-data/esv-data/data/interlinear/strongs.json
```

Developer checkout fallback:

```text
~/bible-lexicon-data/esv-data/data/interlinear/strongs.json
```

Used for:

- Strong's-backed English gloss lookup
- Study-mode lexicon fallback

### STEPBible Lexicons

Clone paths:

```text
runtime-data/theolog-ai/data/biblical-languages/stepbible-lexicons/tbesg-greek.json
runtime-data/theolog-ai/data/biblical-languages/stepbible-lexicons/tbesh-hebrew.json
```

Developer checkout fallbacks:

```text
~/bible-lexicon-data/theolog-ai/data/biblical-languages/stepbible-lexicons/tbesg-greek.json
~/bible-lexicon-data/theolog-ai/data/biblical-languages/stepbible-lexicons/tbesh-hebrew.json
```

Used for:

- Greek/Hebrew lexicon details in study mode

### Historical Documents

Clone path:

```text
runtime-data/theolog-ai/data/historical-documents
```

Developer checkout fallback:

```text
~/bible-lexicon-data/theolog-ai/data/historical-documents
```

Used for:

- JSON fallback for creeds, confessions, and catechisms

## Data Health Checks

Check database tables:

```bash
sqlite3 runtime-data/lexicon.db ".tables"
sqlite3 runtime-data/bible_versions/esv.db ".tables"
sqlite3 runtime-data/encyclopedia.db ".tables"
sqlite3 runtime-data/cross_refs.db ".tables"
sqlite3 runtime-data/strongs.db ".tables"
sqlite3 runtime-data/dictionary.db ".tables"
sqlite3 runtime-data/creeds.db ".tables"
sqlite3 runtime-data/places.db ".tables"
```

Check encyclopedia row count:

```bash
sqlite3 runtime-data/encyclopedia.db "SELECT count(*) FROM encyclopedia;"
```

Check Bible row count:

```bash
sqlite3 runtime-data/bible_versions/esv.db "SELECT count(*) FROM bible;"
```

Rebuild split DBs from `lexicon.db`:

```bash
python3 ~/bible-lexicon-data/scripts/split_lexicon_db.py
```

## Licensing Reminder

Generated databases combine multiple data sources. Do not label generated DB files as MIT. See [Licensing Notes](../LICENSING.md).

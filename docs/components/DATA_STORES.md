# Component: Runtime Data Stores

Lex depends on local SQLite and JSON files. Most features are data-driven, so missing or stale data usually appears as missing search results, missing interlinear rows, or empty definition panels.

## SQLite Databases

### `lexicon.db`

Path:

```text
~/bible-lexicon-data/lexicon.db
```

Used for:

- Strong's entries
- Easton's dictionary
- Creed/confession rows
- TSK cross-references

Important tables:

- `strongs`
- `strongs_fts`
- `dictionary`
- `dictionary_fts`
- `creeds`
- `cross_refs`

### `bible_versions/esv.db`

Path:

```text
~/bible-lexicon-data/bible_versions/esv.db
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
~/bible-lexicon-data/encyclopedia.db
```

Used for:

- Encyclopedia entries in `lex define <term>`

Important tables:

- `encyclopedia`
- `encyclopedia_fts`

Current limitation: only ISBE Volume II is imported.

## JSON Data

### ESV Interlinear

Path:

```text
~/bible-lexicon-data/esv-data/data/esv/esv-interlinear.json
```

Used for:

- Study mode token alignment
- Original-language display

### Interlinear Strong's

Path:

```text
~/bible-lexicon-data/esv-data/data/interlinear/strongs.json
```

Used for:

- Strong's-backed English gloss lookup
- Study-mode lexicon fallback

### STEPBible Lexicons

Paths:

```text
~/bible-lexicon-data/theolog-ai/data/biblical-languages/stepbible-lexicons/tbesg-greek.json
~/bible-lexicon-data/theolog-ai/data/biblical-languages/stepbible-lexicons/tbesh-hebrew.json
```

Used for:

- Greek/Hebrew lexicon details in study mode

### Historical Documents

Path:

```text
~/bible-lexicon-data/theolog-ai/data/historical-documents
```

Used for:

- JSON fallback for creeds, confessions, and catechisms

## Data Health Checks

Check database tables:

```bash
sqlite3 ~/bible-lexicon-data/lexicon.db ".tables"
sqlite3 ~/bible-lexicon-data/bible_versions/esv.db ".tables"
sqlite3 ~/bible-lexicon-data/encyclopedia.db ".tables"
```

Check encyclopedia row count:

```bash
sqlite3 ~/bible-lexicon-data/encyclopedia.db "SELECT count(*) FROM encyclopedia;"
```

Check Bible row count:

```bash
sqlite3 ~/bible-lexicon-data/bible_versions/esv.db "SELECT count(*) FROM bible;"
```

## Licensing Reminder

Generated databases combine multiple data sources. Do not label generated DB files as MIT. See [Licensing Notes](../LICENSING.md).

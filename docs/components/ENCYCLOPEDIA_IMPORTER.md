# Component: Encyclopedia Importer (`scripts/build_encyclopedia_db.py`)

## Purpose

`build_encyclopedia_db.py` builds the separate encyclopedia database used by:

```bash
lex define <term>
```

The generated database is:

```text
~/bible-lexicon-data/encyclopedia.db
```

## Current Source

The importer currently reads:

```text
~/bible-lexicon-data/isbe_raw.txt
```

That file appears to contain only **International Standard Bible Encyclopedia, Volume II: Clement-Heresh**.

## Output Schema

The importer creates:

```sql
CREATE TABLE encyclopedia (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    canonical_topic TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    volume TEXT NOT NULL
);
```

It also creates an FTS5 table:

```sql
CREATE VIRTUAL TABLE encyclopedia_fts
USING fts5(topic, canonical_topic, content, source, volume, content='encyclopedia', content_rowid='id');
```

## Parsing Strategy

The parser is conservative. It looks for article-style headings with uppercase titles and a colon, then captures body text until the next detected heading.

It performs lightweight OCR cleanup:

- Removes page numbers.
- Removes ISBE page headers.
- Removes short standalone page side-header words.
- Rejoins hyphenated line wraps.
- Normalizes repeated whitespace.

## Known Limitations

- Only one ISBE volume is imported.
- OCR noise remains in some long articles.
- Greek/Hebrew transliteration artifacts are not fully cleaned.
- Some headings may still be missed or over-captured.
- There is no metadata table yet for import timestamp, source file hash, or row counts.

## Rebuild Command

```bash
python3 /home/n8te/bible-lexicon-data/scripts/build_encyclopedia_db.py
```

Expected current output is about:

```text
Parsed canonical entries: 1601
Inserted searchable rows: 1898
```

## Future Work

Add remaining ISBE volumes as separate raw files, then update the importer to loop over all source files and store the correct volume label per row.

Suggested file layout:

```text
isbe_vol1_raw.txt
isbe_vol2_raw.txt
isbe_vol3_raw.txt
isbe_vol4_raw.txt
isbe_vol5_raw.txt
```

See [Encyclopedia Import Notes](../ENCYCLOPEDIA_IMPORT_NOTES.md).

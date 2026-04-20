# Bible Edition DB Standard

This project treats Bible text as a plug-in SQLite database per edition.

Current default:

- `bible_versions/esv.db`

## Goals

- Keep edition text separate from lexicon/dictionary/creed data
- Avoid oversized monolithic DB files
- Make new editions drop-in compatible with the CLI
- Standardize schema, metadata, and reference format

## Required Files

Each edition should ship as one SQLite file:

- `bible_versions/<edition_id>.db`

Examples:

- `bible_versions/esv.db`
- `bible_versions/kjv.db`
- `bible_versions/nasb.db`

## Required Tables

### `metadata`

Simple key/value metadata for edition discovery.

Schema:

```sql
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Required keys:

- `schema_version`
- `edition_id`
- `edition_name`
- `language`
- `reference_prefix`
- `reference_format`
- `has_headings`
- `heading_verse_marker`

Example values for ESV:

- `edition_id = esv`
- `edition_name = English Standard Version`
- `reference_prefix = esv`
- `reference_format = prefix:Book:Chapter:Verse`
- `has_headings = true`
- `heading_verse_marker = 0`

### `bible`

Canonical text rows.

Schema:

```sql
CREATE TABLE bible (
    id INTEGER PRIMARY KEY,
    reference TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL
);
```

Rules:

- One row per canonical reference
- `reference` must be unique
- Rows should be ordered canonically by `id`
- Headings may be stored as verse `0`

Reference examples:

- `esv:Genesis:1:0`
- `esv:Genesis:1:1`
- `esv:John:3:16`

### `bible_fts`

Full-text search table for Bible text search.

Schema:

```sql
CREATE VIRTUAL TABLE bible_fts USING fts5(
    reference,
    text,
    tokenize='porter'
);
```

Rules:

- Must contain the same canonical verse/header rows as `bible`
- Search results should return the same `reference` values used by `bible`

## Required Semantics

### Reference format

Use:

`<prefix>:<Book>:<Chapter>:<Verse>`

Where:

- `<prefix>` is the edition id, e.g. `esv`
- `<Book>` is the canonical English book name used by the CLI
- `<Chapter>` is an integer
- `<Verse>` is an integer
- `0` is reserved for chapter headings if headings are included

### Canonical ordering

`id` order must follow canonical Bible order. The CLI depends on this for chapter reads and may use separate interlinear order for verse navigation.

### Uniqueness

Do not store duplicate `reference` rows in an edition DB.

## Optional Tables

You may add edition-specific metadata or auxiliary tables, but the CLI should only rely on:

- `metadata`
- `bible`
- `bible_fts`

## Build Contract

An edition builder should:

1. Normalize references into the standard format
2. Deduplicate rows by canonical reference
3. Preserve canonical order
4. Create `bible_fts`
5. Populate `metadata`

## Current Builder

For the existing ESV text split:

- `scripts/build_esv_bible_db.sh`

That script extracts the Bible text from `lexicon.db`, deduplicates it, and writes:

- `bible_versions/esv.db`

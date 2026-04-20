# Component: Bible DB Builder (`scripts/build_esv_bible_db.sh`)

## Purpose

`build_esv_bible_db.sh` creates the separate Bible edition database used by read mode and Scripture search:

```text
~/bible-lexicon-data/bible_versions/esv.db
```

It extracts Bible rows from the larger `lexicon.db` and writes them into a smaller edition-specific database.

## Inputs

```text
~/bible-lexicon-data/lexicon.db
```

The script expects a source `bible` table in `lexicon.db`.

## Outputs

```text
~/bible-lexicon-data/bible_versions/esv.db
```

The generated DB contains:

- `metadata`
- `bible`
- `bible_fts`

## Behavior

The script:

1. Deletes the existing `bible_versions/esv.db`.
2. Creates metadata for the ESV edition.
3. Copies one canonical row per reference from `lexicon.db`.
4. Creates an index on `bible.reference`.
5. Builds an FTS5 search table.
6. Strips common formatting markers from FTS text.
7. Runs `VACUUM`.

## Rebuild Command

```bash
/home/n8te/bible-lexicon-data/scripts/build_esv_bible_db.sh
```

## Caution

This script removes and recreates `bible_versions/esv.db`. Do not run it while another process is using that DB.

The generated database contains ESV-derived Bible text. Treat redistribution as source-license controlled; do not mark the DB as MIT/public domain.

## Related Docs

- [Bible Edition Standard](../BIBLE_EDITION_STANDARD.md)
- [Runtime Data Stores](DATA_STORES.md)

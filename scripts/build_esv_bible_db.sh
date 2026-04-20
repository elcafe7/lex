#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DB="${ROOT_DIR}/lexicon.db"
TARGET_DIR="${ROOT_DIR}/bible_versions"
TARGET_DB="${TARGET_DIR}/esv.db"

mkdir -p "${TARGET_DIR}"
rm -f "${TARGET_DB}"

sqlite3 "${TARGET_DB}" <<SQL
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO metadata (key, value) VALUES
    ('schema_version', '1'),
    ('edition_id', 'esv'),
    ('edition_name', 'English Standard Version'),
    ('language', 'en'),
    ('reference_prefix', 'esv'),
    ('reference_format', 'prefix:Book:Chapter:Verse'),
    ('has_headings', 'true'),
    ('heading_verse_marker', '0');

ATTACH DATABASE '${SOURCE_DB}' AS src;

CREATE TABLE bible (
    id INTEGER PRIMARY KEY,
    reference TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL
);

INSERT INTO bible (id, reference, text)
SELECT
    ROW_NUMBER() OVER (ORDER BY chosen_id) AS new_id,
    reference,
    text
FROM (
    SELECT b1.reference, b1.text, b1.id AS chosen_id
    FROM src.bible b1
    JOIN (
        SELECT reference, MIN(id) AS min_id
        FROM src.bible
        GROUP BY reference
    ) picked
      ON picked.reference = b1.reference
     AND picked.min_id = b1.id
    ORDER BY b1.id
);

CREATE INDEX idx_bible_reference ON bible(reference);

CREATE VIRTUAL TABLE bible_fts USING fts5(
    reference,
    text,
    tokenize='porter'
);

INSERT INTO bible_fts (reference, text)
SELECT reference, text
FROM (
    SELECT
        id,
        reference,
        trim(
            replace(
                replace(
                    replace(
                        replace(
                            replace(text, '*rp', ''),
                        '*r', ''),
                    '*p', ''),
                '[i]', ''),
            '[/i]', '')
        ) AS text
    FROM bible
)
ORDER BY id;

DETACH DATABASE src;
VACUUM;
SQL

echo "Built ${TARGET_DB}"

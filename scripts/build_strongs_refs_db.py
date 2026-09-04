#!/usr/bin/env python3
"""Build a compact reverse Strong's verse index from ESV interlinear data."""

import json
import os
import re
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DATA_DIR = BASE_DIR / "runtime-data"
INTERLINEAR_PATH = RUNTIME_DATA_DIR / "esv-data" / "data" / "esv" / "esv-interlinear.json"
OUTPUT_PATH = RUNTIME_DATA_DIR / "strongs_refs.db"


def normalize_strongs(raw):
    for match in re.findall(r"[gh]\d+", raw.lower()):
        yield f"{match[0].upper()}{int(match[1:]):04d}"


def iter_usage_rows():
    with INTERLINEAR_PATH.open("r", encoding="utf-8") as f:
        rows = json.load(f)

    usage = {}
    for row in rows:
        ref = row.get("r")
        if not ref or ref.count(":") != 3 or row.get("h"):
            continue

        per_verse = {}
        for token in row.get("p") or []:
            parts = token.split("|")
            if len(parts) < 4:
                continue
            for strongs in normalize_strongs(parts[3]):
                per_verse[strongs] = per_verse.get(strongs, 0) + 1

        verse_order = int(row.get("o") or 0)
        for strongs, token_count in per_verse.items():
            existing = usage.get((strongs, ref))
            if existing:
                verse_order = min(verse_order, existing[0])
                token_count += existing[1]
            usage[(strongs, ref)] = (verse_order, token_count)

    for (strongs, ref), (verse_order, token_count) in sorted(
        usage.items(), key=lambda item: (item[0][0], item[1][0], item[0][1])
    ):
        yield strongs, ref, verse_order, token_count


def build_db():
    if not INTERLINEAR_PATH.exists():
        raise FileNotFoundError(f"Missing interlinear source: {INTERLINEAR_PATH}")

    tmp_path = OUTPUT_PATH.with_suffix(".db.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    count = 0
    keys = set()
    with sqlite3.connect(tmp_path) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;

            CREATE TABLE strongs_refs (
                strongs TEXT NOT NULL,
                reference TEXT NOT NULL,
                verse_order INTEGER NOT NULL,
                token_count INTEGER NOT NULL,
                PRIMARY KEY (strongs, reference)
            );
            CREATE INDEX idx_strongs_refs_lookup
                ON strongs_refs(strongs, verse_order);

            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        batch = []
        for row in iter_usage_rows():
            batch.append(row)
            keys.add(row[0])
            count += 1
            if len(batch) >= 5000:
                conn.executemany("INSERT INTO strongs_refs VALUES (?, ?, ?, ?)", batch)
                batch.clear()
        if batch:
            conn.executemany("INSERT INTO strongs_refs VALUES (?, ?, ?, ?)", batch)

        conn.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [
                ("source", "esv-interlinear"),
                ("source_path", str(INTERLINEAR_PATH.relative_to(BASE_DIR))),
                ("verse_key_rows", str(count)),
                ("strongs_keys", str(len(keys))),
            ],
        )
        conn.executescript("ANALYZE; VACUUM;")

    os.replace(tmp_path, OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Strong's keys: {len(keys)}")
    print(f"Verse-key rows: {count}")
    print(f"Size: {OUTPUT_PATH.stat().st_size} bytes")


if __name__ == "__main__":
    build_db()

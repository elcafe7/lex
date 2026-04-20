#!/usr/bin/env python3
import os
import sqlite3


ROOT = os.path.expanduser("~/bible-lexicon-data")
SOURCE_DB = os.path.join(ROOT, "lexicon.db")

TARGETS = {
    "cross_refs.db": {
        "tables": ["cross_refs"],
        "indexes": ["CREATE INDEX idx_from ON cross_refs(from_ref)"],
    },
    "strongs.db": {
        "tables": ["strongs"],
        "indexes": [],
        "fts": [
            """
            CREATE VIRTUAL TABLE strongs_fts USING fts5(
                number,
                word,
                pronunciation,
                definition,
                language,
                content='strongs',
                content_rowid='rowid'
            )
            """,
            """
            INSERT INTO strongs_fts(rowid, number, word, pronunciation, definition, language)
            SELECT rowid, number, word, pronunciation, definition, language FROM strongs
            """,
        ],
    },
    "dictionary.db": {
        "tables": ["dictionary"],
        "indexes": ["CREATE INDEX idx_dictionary_topic ON dictionary(topic)"],
        "fts": [
            """
            CREATE VIRTUAL TABLE dictionary_fts USING fts5(
                topic,
                content,
                source,
                content='dictionary',
                content_rowid='rowid'
            )
            """,
            """
            INSERT INTO dictionary_fts(rowid, topic, content, source)
            SELECT rowid, topic, content, source FROM dictionary
            """,
        ],
    },
    "creeds.db": {
        "tables": ["creeds"],
        "indexes": ["CREATE INDEX idx_creeds_topic ON creeds(topic)"],
    },
    "places.db": {
        "tables": ["places"],
        "indexes": [],
    },
}


def create_table_from_source(source, target, table):
    sql = source.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if not sql:
        raise RuntimeError(f"Missing source table: {table}")
    target.execute(sql[0])

    columns = [row[1] for row in source.execute(f"PRAGMA table_info({table})")]
    col_list = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    rows = source.execute(f"SELECT {col_list} FROM {table}").fetchall()
    target.executemany(
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
        rows,
    )
    return len(rows)


def build_target(name, config):
    target_path = os.path.join(ROOT, name)
    if os.path.exists(target_path):
        os.remove(target_path)

    with sqlite3.connect(SOURCE_DB) as source, sqlite3.connect(target_path) as target:
        total_rows = 0
        for table in config["tables"]:
            total_rows += create_table_from_source(source, target, table)
        for index_sql in config.get("indexes", []):
            target.execute(index_sql)
        for fts_sql in config.get("fts", []):
            target.execute(fts_sql)
        target.commit()
        target.execute("VACUUM")

    size_mb = os.path.getsize(target_path) / (1024 * 1024)
    print(f"{name}: {total_rows} rows, {size_mb:.2f} MB")


def main():
    if not os.path.exists(SOURCE_DB):
        raise SystemExit(f"Missing source DB: {SOURCE_DB}")
    for name, config in TARGETS.items():
        build_target(name, config)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os
import re
import sqlite3


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
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


SAFE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ALLOWED_TABLES = frozenset(table for config in TARGETS.values() for table in config["tables"])


def quote_identifier(name):
    """Return a double-quoted SQLite identifier, or raise if it is not a plain name."""
    if not isinstance(name, str) or not SAFE_IDENTIFIER.fullmatch(name):
        raise ValueError(f"Unsafe SQLite identifier: {name!r}")
    return f'"{name}"'


def create_table_from_source(source, target, table):
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Table is not in the split plan: {table!r}")
    table_sql = quote_identifier(table)
    sql = source.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if not sql:
        raise RuntimeError(f"Missing source table: {table}")
    target.execute(sql[0])

    # Column names come from the source database file, so they are checked
    # and quoted like the table name; row values are always bound parameters.
    columns = [row[0] for row in source.execute("SELECT name FROM pragma_table_info(?)", (table,))]
    if not columns:
        raise RuntimeError(f"Source table has no columns: {table}")
    col_list = ", ".join(quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    select_sql = f"SELECT {col_list} FROM {table_sql}"  # nosec B608  # reason: identifiers allowlisted and quoted by quote_identifier(); no values in the string
    insert_sql = f"INSERT INTO {table_sql} ({col_list}) VALUES ({placeholders})"  # nosec B608  # reason: identifiers allowlisted and quoted by quote_identifier(); values are bound "?" parameters
    rows = source.execute(select_sql).fetchall()
    target.executemany(insert_sql, rows)
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

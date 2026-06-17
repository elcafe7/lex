#!/usr/bin/env python3
import argparse
import os
import sqlite3


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
DEFAULT_DB = os.path.join(ROOT, "lxx.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS lxx_text (
    id TEXT PRIMARY KEY,
    ref TEXT NOT NULL,
    book TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    word_num INTEGER NOT NULL,
    text TEXT NOT NULL,
    lemma TEXT,
    strong TEXT,
    lexicon_id TEXT,
    lexicon_source TEXT,
    gloss TEXT,
    morph TEXT,
    pos TEXT,
    person TEXT,
    number TEXT,
    gender TEXT,
    word_case TEXT,
    tense TEXT,
    voice TEXT,
    mood TEXT,
    degree TEXT,
    head INTEGER,
    dependency TEXT,
    misc TEXT
);

CREATE INDEX IF NOT EXISTS idx_lxx_ref_word
ON lxx_text(ref, word_num);

CREATE INDEX IF NOT EXISTS idx_lxx_book_chapter_verse_word
ON lxx_text(book, chapter, verse, word_num);

CREATE INDEX IF NOT EXISTS idx_lxx_strong
ON lxx_text(strong);

CREATE INDEX IF NOT EXISTS idx_lxx_lemma
ON lxx_text(lemma);

CREATE TABLE IF NOT EXISTS lxx_bridge_text (
    id TEXT PRIMARY KEY,
    ref TEXT NOT NULL,
    book TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL,
    word_num INTEGER NOT NULL,
    greek_text TEXT NOT NULL,
    greek_strong TEXT NOT NULL,
    lexicon_id TEXT,
    lexicon_source TEXT NOT NULL,
    hebrew_text TEXT,
    hebrew_lemma TEXT,
    hebrew_strong TEXT,
    hebrew_morph TEXT,
    source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lxx_bridge_ref_word
ON lxx_bridge_text(ref, word_num);

CREATE INDEX IF NOT EXISTS idx_lxx_bridge_book_chapter_verse_word
ON lxx_bridge_text(book, chapter, verse, word_num);

CREATE INDEX IF NOT EXISTS idx_lxx_bridge_greek_strong
ON lxx_bridge_text(greek_strong);

CREATE TABLE IF NOT EXISTS lxx_lemma_strong_map (
    id TEXT PRIMARY KEY,
    book TEXT NOT NULL,
    lemma TEXT NOT NULL,
    normalized_lemma TEXT NOT NULL,
    strong TEXT NOT NULL,
    lexicon_id TEXT NOT NULL,
    lexicon_source TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL,
    lemma_token_count INTEGER NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lxx_lemma_strong_book_lemma
ON lxx_lemma_strong_map(book, normalized_lemma);

CREATE INDEX IF NOT EXISTS idx_lxx_lemma_strong_strong
ON lxx_lemma_strong_map(strong);
"""


def init_lxx_db(db_path=DEFAULT_DB, replace=False):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if replace and os.path.exists(db_path):
        os.remove(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
        conn.execute("VACUUM")

    return db_path


def main():
    parser = argparse.ArgumentParser(description="Initialize the Lex LXX SQLite schema.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Output SQLite database path")
    parser.add_argument("--replace", action="store_true", help="Replace an existing database")
    args = parser.parse_args()

    db_path = init_lxx_db(args.db, replace=args.replace)
    print(f"Initialized {db_path}")


if __name__ == "__main__":
    main()

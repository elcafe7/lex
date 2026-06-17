#!/usr/bin/env python3
import argparse
import os
import re
import sqlite3
import unicodedata

from init_lxx_db import DEFAULT_DB, init_lxx_db


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
DEFAULT_LXX_BIBLE_DB = os.path.join(ROOT, "bible_versions", "lxx.db")
DEFAULT_BIBLA_OT_DB = os.path.expanduser("~/bibla-lingua/bibla_lingua_ot.db")

BOOK_TO_LXX_NAME = {
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers", "DEU": "Deuteronomy",
    "JOS": "Joshua", "JDG": "Judges", "RUT": "Ruth", "1SA": "1 Samuel", "2SA": "2 Samuel",
    "1KI": "1 Kings", "2KI": "2 Kings", "1CH": "1 Chronicles", "2CH": "2 Chronicles",
    "EZR": "Ezra", "NEH": "Nehemiah", "EST": "Esther", "JOB": "Job", "PSA": "Psalms",
    "PRO": "Proverbs", "ECC": "Ecclesiastes", "SNG": "Song of Solomon", "ISA": "Isaiah",
    "JER": "Jeremiah", "LAM": "Lamentations", "EZK": "Ezekiel", "DAN": "Daniel",
    "HOS": "Hosea", "JOL": "Joel", "AMO": "Amos", "OBA": "Obadiah", "JON": "Jonah",
    "MIC": "Micah", "NAM": "Nahum", "HAB": "Habakkuk", "ZEP": "Zephaniah", "HAG": "Haggai",
    "ZEC": "Zechariah", "MAL": "Malachi",
}


def normalize_greek_text(value):
    text = (value or "").lower().replace("ς", "σ")
    text = "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^\u0370-\u03ff]+", "", text)


def normalize_strongs(raw):
    if raw is None or raw == "":
        return None
    match = re.search(r"0*(\d+)", str(raw))
    if not match:
        return None
    return f"G{int(match.group(1)):04d}"


def tokenize_greek(text):
    return re.findall(r"[\u0370-\u03ff]+", text or "")


def load_lxx_verses(db_path, book_code):
    lxx_name = BOOK_TO_LXX_NAME[book_code]
    rows = {}
    with sqlite3.connect(db_path) as conn:
        for reference, text in conn.execute(
            """
            SELECT reference, text
            FROM bible
            WHERE reference LIKE ?
            ORDER BY id
            """,
            (f"lxx:{lxx_name}:%",),
        ):
            match = re.match(r"^lxx:[^:]+:(\d+):(\d+)$", reference)
            if not match:
                continue
            chapter, verse = match.groups()
            rows[f"{book_code} {int(chapter)}:{int(verse)}"] = text
    return rows


def load_bibla_bridge(db_path, book_code):
    bridge = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            """
            SELECT chapter, verse, greek_gloss, greek_strong
            FROM hebrew_text
            WHERE book = ?
              AND greek_gloss IS NOT NULL
              AND greek_gloss != ''
              AND greek_strong IS NOT NULL
              AND greek_strong != ''
            ORDER BY chapter, verse, rowid
            """,
            (book_code,),
        ):
            ref = f"{book_code} {row['chapter']}:{row['verse']}"
            key = normalize_greek_text(row["greek_gloss"])
            if not key:
                continue
            bridge.setdefault(ref, {}).setdefault(key, []).append(
                {
                    "surface": row["greek_gloss"],
                    "strong": normalize_strongs(row["greek_strong"]),
                }
            )
    return bridge


def pop_bridge_match(queues, token):
    values = queues.get(normalize_greek_text(token))
    if not values:
        return None
    while values:
        candidate = values.pop(0)
        if candidate.get("strong"):
            return candidate
    return None


def enrich_existing_rows(conn, book_code, bridge):
    updated = 0
    refs = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT ref FROM lxx_text WHERE book = ? ORDER BY chapter, verse",
            (book_code,),
        )
    ]
    for ref in refs:
        queues = {key: list(values) for key, values in bridge.get(ref, {}).items()}
        rows = conn.execute(
            """
            SELECT id, text
            FROM lxx_text
            WHERE book = ? AND ref = ? AND (strong IS NULL OR strong = '')
            ORDER BY word_num
            """,
            (book_code, ref),
        ).fetchall()
        for row_id, token in rows:
            match = pop_bridge_match(queues, token)
            if not match:
                continue
            conn.execute(
                """
                UPDATE lxx_text
                SET strong = ?,
                    lexicon_id = ?,
                    lexicon_source = COALESCE(lexicon_source, ?)
                WHERE id = ?
                """,
                (match["strong"], match["strong"], "bibla:hebrew_text.greekstrong", row_id),
            )
            updated += 1
    return updated


def insert_missing_verses(conn, book_code, lxx_verses, bridge):
    inserted = 0
    existing_refs = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT ref FROM lxx_text WHERE book = ?",
            (book_code,),
        )
    }
    for ref, verse_text in sorted(
        lxx_verses.items(),
        key=lambda item: tuple(int(part) for part in item[0].split(" ", 1)[1].split(":")),
    ):
        if ref in existing_refs:
            continue
        chapter, verse = (int(part) for part in ref.split(" ", 1)[1].split(":"))
        queues = {key: list(values) for key, values in bridge.get(ref, {}).items()}
        for word_num, token in enumerate(tokenize_greek(verse_text), 1):
            match = pop_bridge_match(queues, token) or {}
            strong = match.get("strong")
            conn.execute(
                """
                INSERT OR REPLACE INTO lxx_text (
                    id, ref, book, chapter, verse, word_num, text, lemma,
                    strong, lexicon_id, lexicon_source, gloss, morph, pos,
                    person, number, gender, word_case, tense, voice, mood,
                    degree, head, dependency, misc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{ref}:bridge:{word_num}",
                    ref,
                    book_code,
                    chapter,
                    verse,
                    word_num,
                    token,
                    None,
                    strong,
                    strong,
                    "bibla:hebrew_text.greekstrong" if strong else "lex:lxx_bible_text",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "bridge_derived=1",
                ),
            )
            inserted += 1
    return inserted


def rebuild_bridge_table(conn, bibla_db, book_code):
    conn.execute("DELETE FROM lxx_bridge_text WHERE book = ?", (book_code,))
    inserted = 0
    with sqlite3.connect(bibla_db) as source:
        source.row_factory = sqlite3.Row
        rows = source.execute(
            """
            SELECT
                chapter,
                verse,
                rowid AS source_rowid,
                text AS hebrew_text,
                lemma AS hebrew_lemma,
                strong AS hebrew_strong,
                morph AS hebrew_morph,
                greek_gloss,
                greek_strong
            FROM hebrew_text
            WHERE book = ?
              AND greek_gloss IS NOT NULL
              AND greek_gloss != ''
              AND greek_strong IS NOT NULL
              AND greek_strong != ''
            ORDER BY chapter, verse, rowid
            """,
            (book_code,),
        ).fetchall()
    counters = {}
    for row in rows:
        ref = f"{book_code} {row['chapter']}:{row['verse']}"
        counters[ref] = counters.get(ref, 0) + 1
        word_num = counters[ref]
        greek_strong = normalize_strongs(row["greek_strong"])
        conn.execute(
            """
            INSERT OR REPLACE INTO lxx_bridge_text (
                id, ref, book, chapter, verse, word_num, greek_text,
                greek_strong, lexicon_id, lexicon_source, hebrew_text,
                hebrew_lemma, hebrew_strong, hebrew_morph, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{ref}:bibla:{word_num}",
                ref,
                book_code,
                row["chapter"],
                row["verse"],
                word_num,
                row["greek_gloss"],
                greek_strong,
                greek_strong,
                "bibla:hebrew_text.greekstrong",
                row["hebrew_text"],
                row["hebrew_lemma"],
                row["hebrew_strong"],
                row["hebrew_morph"],
                f"bibla:{os.path.basename(bibla_db)}:{row['source_rowid']}",
            ),
        )
        inserted += 1
    return inserted


def rebuild_lemma_strong_map(conn, book_code):
    conn.execute("DELETE FROM lxx_lemma_strong_map WHERE book = ?", (book_code,))
    lemma_totals = {}
    for lemma, count in conn.execute(
        """
        SELECT lemma, COUNT(*)
        FROM lxx_text
        WHERE book = ?
          AND lemma IS NOT NULL
          AND lemma != ''
        GROUP BY lemma
        """,
        (book_code,),
    ):
        lemma_totals[normalize_greek_text(lemma)] = count

    mapped = {}
    refs = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT ref FROM lxx_text WHERE book = ? ORDER BY chapter, verse",
            (book_code,),
        )
    ]
    for ref in refs:
        bridge = {}
        for greek_text, greek_strong in conn.execute(
            """
            SELECT greek_text, greek_strong
            FROM lxx_bridge_text
            WHERE book = ? AND ref = ?
            ORDER BY word_num
            """,
            (book_code, ref),
        ):
            key = normalize_greek_text(greek_text)
            if key and greek_strong:
                bridge.setdefault(key, []).append(greek_strong)

        for text, lemma in conn.execute(
            """
            SELECT text, lemma
            FROM lxx_text
            WHERE book = ? AND ref = ?
              AND lemma IS NOT NULL
              AND lemma != ''
            ORDER BY word_num
            """,
            (book_code, ref),
        ):
            values = bridge.get(normalize_greek_text(text))
            if not values:
                continue
            strong = values.pop(0)
            normalized_lemma = normalize_greek_text(lemma)
            if not normalized_lemma or not strong:
                continue
            key = (lemma, normalized_lemma, strong)
            mapped[key] = mapped.get(key, 0) + 1

    inserted = 0
    for (lemma, normalized_lemma, strong), count in sorted(mapped.items()):
        total = lemma_totals.get(normalized_lemma, count)
        confidence = count / total if total else 0
        source = "bibla_bridge_surface_match"
        conn.execute(
            """
            INSERT OR REPLACE INTO lxx_lemma_strong_map (
                id, book, lemma, normalized_lemma, strong, lexicon_id,
                lexicon_source, occurrence_count, lemma_token_count,
                confidence, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{book_code}:{normalized_lemma}:{strong}:{source}",
                book_code,
                lemma,
                normalized_lemma,
                strong,
                strong,
                source,
                count,
                total,
                confidence,
                source,
            ),
        )
        inserted += 1
    return inserted


def supplement(db_path, lxx_bible_db, bibla_db, book_code, merge_lxx_text=False):
    init_lxx_db(db_path, replace=False)
    lxx_verses = load_lxx_verses(lxx_bible_db, book_code)
    bridge = load_bibla_bridge(bibla_db, book_code)
    with sqlite3.connect(db_path) as conn:
        updated = 0
        inserted = 0
        if merge_lxx_text:
            updated = enrich_existing_rows(conn, book_code, bridge)
            inserted = insert_missing_verses(conn, book_code, lxx_verses, bridge)
        bridge_rows = rebuild_bridge_table(conn, bibla_db, book_code)
        lemma_strong_rows = rebuild_lemma_strong_map(conn, book_code)
        conn.commit()
    return updated, inserted, bridge_rows, lemma_strong_rows, len(lxx_verses)


def main():
    parser = argparse.ArgumentParser(description="Supplement Lex LXX rows from Bibla Hebrew/LXX bridge data.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Target Lex LXX SQLite database")
    parser.add_argument("--lxx-bible-db", default=DEFAULT_LXX_BIBLE_DB, help="Lex LXX Bible text database")
    parser.add_argument("--bibla-db", default=DEFAULT_BIBLA_OT_DB, help="Bibla Hebrew SQLite database")
    parser.add_argument("--book", default="GEN", choices=["ALL"] + sorted(BOOK_TO_LXX_NAME), help="Book code to supplement")
    parser.add_argument("--bridge-only", action="store_true", help="Only rebuild lxx_bridge_text; this is the default safe behavior")
    parser.add_argument(
        "--experimental-merge-lxx-text",
        action="store_true",
        help="Also enrich/insert lxx_text rows from the Hebrew bridge. Use only after verse/token alignment QC.",
    )
    args = parser.parse_args()

    book_codes = sorted(BOOK_TO_LXX_NAME) if args.book == "ALL" else [args.book]
    totals = {
        "updated": 0,
        "inserted": 0,
        "bridge_rows": 0,
        "lemma_strong_rows": 0,
        "verse_count": 0,
    }
    for book_code in book_codes:
        updated, inserted, bridge_rows, lemma_strong_rows, verse_count = supplement(
            args.db,
            args.lxx_bible_db,
            args.bibla_db,
            book_code,
            merge_lxx_text=args.experimental_merge_lxx_text,
        )
        totals["updated"] += updated
        totals["inserted"] += inserted
        totals["bridge_rows"] += bridge_rows
        totals["lemma_strong_rows"] += lemma_strong_rows
        totals["verse_count"] += verse_count
        print(f"{book_code}: {verse_count} LXX text verses available")
        print(f"  Updated existing rows with Strong's: {updated}")
        print(f"  Inserted bridge-derived rows: {inserted}")
        print(f"  Rebuilt Bibla bridge rows: {bridge_rows}")
        print(f"  Rebuilt lemma Strong's candidate rows: {lemma_strong_rows}")
    if len(book_codes) > 1:
        print("TOTAL:")
        print(f"  LXX text verses available: {totals['verse_count']}")
        print(f"  Updated existing rows with Strong's: {totals['updated']}")
        print(f"  Inserted bridge-derived rows: {totals['inserted']}")
        print(f"  Rebuilt Bibla bridge rows: {totals['bridge_rows']}")
        print(f"  Rebuilt lemma Strong's candidate rows: {totals['lemma_strong_rows']}")


if __name__ == "__main__":
    main()

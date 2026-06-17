#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3

from init_lxx_db import DEFAULT_DB, init_lxx_db


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
DEFAULT_LXX_BIBLE_DB = os.path.join(ROOT, "bible_versions", "lxx.db")

BOOKS = {
    "Gen": ("GEN", "Genesis"),
    "Exod": ("EXO", "Exodus"),
    "Lev": ("LEV", "Leviticus"),
    "Num": ("NUM", "Numbers"),
    "Deut": ("DEU", "Deuteronomy"),
    "JoshB": ("JOS", "Joshua B"),
    "JudgB": ("JDG", "Judges B"),
    "Ruth": ("RUT", "Ruth"),
    "1Sam": ("1SA", "1 Samuel (1 Kingdoms)"),
    "2Sam": ("2SA", "2 Samuel (2 Kingdoms)"),
    "1Kgs": ("1KI", "1 Kings (3 Kingdoms)"),
    "2Kgs": ("2KI", "2 Kings (4 Kingdoms)"),
    "1Chr": ("1CH", "1 Chronicles"),
    "2Chr": ("2CH", "2 Chronicles"),
    "1Esd": ("1ES", "Esdras A/I"),
    "Esth": ("EST", "Esther (with additions)"),
    "Jdt": ("JDT", "Judith"),
    "TobBA": ("TOB", "Tobit BA"),
    "1Macc": ("1MA", "I Maccabees"),
    "2Macc": ("2MA", "II Maccabees"),
    "3Macc": ("3MA", "III Maccabees"),
    "4Macc": ("4MA", "IV Maccabees"),
    "Ps": ("PSA", "Psalms"),
    "Odes": ("ODE", "Odes"),
    "Prov": ("PRO", "Proverbs"),
    "Eccl": ("ECC", "Ecclesiastes (Preacher)"),
    "Song": ("SNG", "Canticle (Song of Solomon)"),
    "Job": ("JOB", "Job"),
    "Wis": ("WIS", "Wisdom of Solomon"),
    "Sir": ("SIR", "Wisdom of Sirach"),
    "PsSol": ("PSS", "Psalms of Solomon"),
    "Hos": ("HOS", "Hosea"),
    "Mic": ("MIC", "Micah"),
    "Amos": ("AMO", "Amos"),
    "Joel": ("JOL", "Joel"),
    "Jonah": ("JON", "Jonah"),
    "Obad": ("OBA", "Obadiah"),
    "Nah": ("NAM", "Nahum"),
    "Hab": ("HAB", "Habakkuk"),
    "Zeph": ("ZEP", "Zephaniah"),
    "Hag": ("HAG", "Haggai"),
    "Zech": ("ZEC", "Zechariah"),
    "Mal": ("MAL", "Malachi"),
    "Isa": ("ISA", "Isaiah"),
    "Jer": ("JER", "Jeremiah"),
    "Bar": ("BAR", "Baruch"),
    "EpJer": ("EPJ", "Epistle of Jeremiah"),
    "Lam": ("LAM", "Lamentations (Threni)"),
    "Ezek": ("EZK", "Ezekiel"),
    "BelOG": ("BEL", "Bel LXX"),
    "DanOG": ("DAN", "Daniel LXX"),
    "SusOG": ("SUS", "Susanna LXX"),
}


def tokenize_greek(text):
    return re.findall(r"[\u0370-\u03ff]+", text or "")


def load_json_object(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.loads(fh.read())


def load_word_list(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        raw = fh.read()
    match = re.search(r"greekWordList\s*=\s*(\{.*\})\s*;?\s*$", raw, flags=re.DOTALL)
    if not match:
        return {}
    return json.loads(match.group(1))


def normalize_strongs(raw):
    if raw is None or raw == "":
        return None
    match = re.search(r"0*(\d+)", str(raw))
    if not match:
        return None
    return f"G{int(match.group(1)):04d}"


def verse_sort_key(osis_ref):
    parts = osis_ref.split(".")
    return tuple(int(part) if part.isdigit() else part for part in parts[1:])


def fetch_lxx_text(conn, lxx_name, chapter, verse):
    row = conn.execute(
        "SELECT text FROM bible WHERE reference = ?",
        (f"lxx:{lxx_name}:{chapter}:{verse}",),
    ).fetchone()
    return row[0] if row else ""


def import_book(conn, bible_conn, lemma_dir, word_list, book_abbr):
    book_code, lxx_name = BOOKS[book_abbr]
    lemma_path = os.path.join(lemma_dir, f"{book_abbr}.js")
    if not os.path.exists(lemma_path):
        return {"book": book_code, "rows": 0, "refs": 0, "mismatches": 0, "missing_text": 0}

    conn.execute("DELETE FROM lxx_text WHERE book = ?", (book_code,))
    conn.execute("DELETE FROM lxx_lemma_strong_map WHERE book = ?", (book_code,))
    data = load_json_object(lemma_path)
    rows = []
    mismatches = 0
    missing_text = 0
    for osis_ref in sorted(data, key=verse_sort_key):
        parts = osis_ref.split(".")
        if len(parts) < 3:
            continue
        chapter, verse = int(parts[1]), int(parts[2])
        lemmas = data[osis_ref]
        verse_text = fetch_lxx_text(bible_conn, lxx_name, chapter, verse)
        tokens = tokenize_greek(verse_text)
        if not tokens:
            missing_text += 1
        if len(tokens) != len(lemmas):
            mismatches += 1
        ref = f"{book_code} {chapter}:{verse}"
        for index, lemma_row in enumerate(lemmas, 1):
            key = lemma_row.get("key") or ""
            word_entry = word_list.get(key, {})
            strong = normalize_strongs(word_entry.get("strong"))
            rows.append(
                (
                    f"{ref}:os:{index}",
                    ref,
                    book_code,
                    chapter,
                    verse,
                    index,
                    tokens[index - 1] if index <= len(tokens) else lemma_row.get("lemma", ""),
                    lemma_row.get("lemma"),
                    strong,
                    key,
                    "openscriptures:lxxlemmas",
                    word_entry.get("def"),
                    None,
                    word_entry.get("pos"),
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
                    f"osis={osis_ref}",
                )
            )
    conn.executemany(
        """
        INSERT OR REPLACE INTO lxx_text (
            id, ref, book, chapter, verse, word_num, text, lemma,
            strong, lexicon_id, lexicon_source, gloss, morph, pos,
            person, number, gender, word_case, tense, voice, mood,
            degree, head, dependency, misc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return {
        "book": book_code,
        "rows": len(rows),
        "refs": len(data),
        "mismatches": mismatches,
        "missing_text": missing_text,
    }


def main():
    parser = argparse.ArgumentParser(description="Import Open Scriptures LXX lemma files into Lex lxx_text.")
    parser.add_argument("source", help="Path to Open Scriptures GreekResources checkout")
    parser.add_argument("--db", default=DEFAULT_DB, help="Target Lex LXX SQLite database")
    parser.add_argument("--lxx-bible-db", default=DEFAULT_LXX_BIBLE_DB, help="Lex LXX Bible text database")
    parser.add_argument("--book", action="append", choices=sorted(BOOKS), help="Import one SBL book abbreviation; repeatable")
    args = parser.parse_args()

    lemma_dir = os.path.join(args.source, "LxxLemmas")
    word_list_path = os.path.join(args.source, "GreekWordList.js")
    if not os.path.isdir(lemma_dir):
        raise SystemExit(f"Missing LxxLemmas directory: {lemma_dir}")
    if not os.path.exists(word_list_path):
        raise SystemExit(f"Missing GreekWordList.js: {word_list_path}")

    init_lxx_db(args.db, replace=False)
    word_list = load_word_list(word_list_path)
    book_abbrs = args.book or sorted(BOOKS)
    with sqlite3.connect(args.db) as conn, sqlite3.connect(args.lxx_bible_db) as bible_conn:
        for book_abbr in book_abbrs:
            result = import_book(conn, bible_conn, lemma_dir, word_list, book_abbr)
            print(
                f"{result['book']}: {result['rows']} rows, {result['refs']} refs, "
                f"{result['mismatches']} token-count mismatches, {result['missing_text']} missing text refs"
            )
        conn.commit()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import os
import re
import sqlite3
import sys
import unicodedata

from init_lxx_db import DEFAULT_DB, init_lxx_db


FEATURE_COLUMNS = {
    "Case": "word_case",
    "Degree": "degree",
    "Gender": "gender",
    "Mood": "mood",
    "Number": "number",
    "Person": "person",
    "Tense": "tense",
    "Voice": "voice",
}


def parse_kv_pairs(value, item_sep="|", kv_sep="="):
    result = {}
    if not value or value == "_":
        return result
    for item in value.split(item_sep):
        if kv_sep not in item:
            continue
        key, val = item.split(kv_sep, 1)
        result[key] = val
    return result


def parse_ref(raw_ref):
    match = re.match(r"^([1-3]?[A-Z]+)_(\d+)\.(\d+)$", raw_ref or "")
    if not match:
        return None
    book, chapter, verse = match.groups()
    return book, int(chapter), int(verse), f"{book} {chapter}:{verse}"


def normalize_strongs(raw):
    if not raw:
        return None
    match = re.search(r"(?:[Gg])?0*(\d+)", str(raw))
    if not match:
        return None
    return f"G{int(match.group(1)):04d}"


def normalize_greek_text(value):
    text = (value or "").lower().replace("ς", "σ")
    text = "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^\u0370-\u03ff]+", "", text)


def load_bibla_strongs_rows(db_paths):
    rows = {}
    for db_path in db_paths or []:
        if not os.path.exists(db_path):
            raise SystemExit(f"Missing Bibla DB: {db_path}")
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(
                """
                SELECT book, chapter, verse, greek_gloss, greek_strong
                FROM hebrew_text
                WHERE greek_gloss IS NOT NULL
                  AND greek_gloss != ''
                  AND greek_strong IS NOT NULL
                  AND greek_strong != ''
                """
            ):
                ref = f"{row['book']} {row['chapter']}:{row['verse']}"
                key = (ref, normalize_greek_text(row["greek_gloss"]))
                rows.setdefault(key, []).append(normalize_strongs(row["greek_strong"]))
    return rows


def build_strongs_by_lemma(rows):
    mapping = {}
    for row in rows:
        if not row.get("lemma") or not row.get("strong"):
            continue
        key = normalize_greek_text(row["lemma"])
        if key and key not in mapping:
            mapping[key] = row["strong"]
    return mapping


def apply_bibla_strongs(rows, bibla_strongs):
    queues = {key: list(values) for key, values in bibla_strongs.items()}
    applied = 0
    for row in rows:
        if row.get("strong"):
            continue
        key = (row["ref"], normalize_greek_text(row["text"]))
        values = queues.get(key)
        if not values:
            continue
        strong = values.pop(0)
        if strong:
            row["strong"] = strong
            applied += 1
    return applied


def apply_lemma_strongs(rows, strongs_by_lemma):
    applied = 0
    for row in rows:
        if row.get("strong"):
            continue
        strong = strongs_by_lemma.get(normalize_greek_text(row.get("lemma")))
        if strong:
            row["strong"] = strong
            applied += 1
    return applied


def is_integer_token_id(token_id):
    return re.match(r"^\d+$", token_id or "") is not None


def parse_conllu(path, include_punctuation=False):
    rows = []
    sentence_meta = {}
    with open(path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if not line:
                sentence_meta = {}
                continue
            if line.startswith("#"):
                if "=" in line:
                    key, value = line[1:].split("=", 1)
                    sentence_meta[key.strip()] = value.strip()
                continue

            parts = line.split("\t")
            if len(parts) != 10 or not is_integer_token_id(parts[0]):
                continue

            token_id, surface, lemma, upos, xpos, feats, head, deprel, deps, misc_raw = parts
            if upos == "PUNCT" and not include_punctuation:
                continue

            misc = parse_kv_pairs(misc_raw)
            ref_parts = parse_ref(misc.get("Ref"))
            if not ref_parts:
                continue
            book, chapter, verse, ref = ref_parts
            features = parse_kv_pairs(feats)
            strong = normalize_strongs(
                misc.get("Strong")
                or misc.get("Strongs")
                or misc.get("strong")
                or misc.get("strongs")
            )
            row = {
                "id": f"{ref}:{token_id}",
                "ref": ref,
                "book": book,
                "chapter": chapter,
                "verse": verse,
                "word_num": int(token_id),
                "text": surface,
                "lemma": None if lemma == "_" else lemma,
                "strong": strong,
                "lexicon_id": None,
                "lexicon_source": None,
                "gloss": misc.get("Gloss"),
                "morph": feats if feats != "_" else None,
                "pos": upos if upos != "_" else None,
                "person": None,
                "number": None,
                "gender": None,
                "word_case": None,
                "tense": None,
                "voice": None,
                "mood": None,
                "degree": None,
                "head": int(head) if head.isdigit() else None,
                "dependency": deprel if deprel != "_" else None,
                "misc": misc_raw if misc_raw != "_" else None,
            }
            for feature_name, column_name in FEATURE_COLUMNS.items():
                row[column_name] = features.get(feature_name)
            rows.append(row)
    return rows


def import_rows(rows, db_path, replace=False):
    init_lxx_db(db_path, replace=replace)
    columns = [
        "id", "ref", "book", "chapter", "verse", "word_num", "text", "lemma",
        "strong", "lexicon_id", "lexicon_source", "gloss", "morph", "pos",
        "person", "number", "gender", "word_case", "tense", "voice", "mood", "degree", "head",
        "dependency", "misc",
    ]
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    values = [[row.get(column) for column in columns] for row in rows]
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO lxx_text ({column_sql}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Import LXX CoNLL-U data into Lex runtime-data/lxx.db.")
    parser.add_argument("conllu", nargs="+", help="Input CoNLL-U file(s)")
    parser.add_argument("--db", default=DEFAULT_DB, help="Output SQLite database path")
    parser.add_argument("--replace", action="store_true", help="Replace the target DB before import")
    parser.add_argument("--include-punctuation", action="store_true", help="Import PUNCT rows too")
    parser.add_argument(
        "--strongs-from-bibla",
        action="append",
        default=[],
        help="Overlay Strong's IDs from a Bibla Hebrew SQLite DB with greek_gloss/greek_strong columns",
    )
    args = parser.parse_args()

    all_rows = []
    for conllu_path in args.conllu:
        if not os.path.exists(conllu_path):
            raise SystemExit(f"Missing CoNLL-U file: {conllu_path}")
        all_rows.extend(parse_conllu(conllu_path, include_punctuation=args.include_punctuation))

    strongs_applied = 0
    if args.strongs_from_bibla:
        strongs_applied = apply_bibla_strongs(
            all_rows,
            load_bibla_strongs_rows(args.strongs_from_bibla),
        )
        strongs_applied += apply_lemma_strongs(all_rows, build_strongs_by_lemma(all_rows))

    count = import_rows(all_rows, args.db, replace=args.replace)
    print(f"Imported {count} LXX tokens into {args.db}")
    if args.strongs_from_bibla:
        print(f"Applied {strongs_applied} Bibla Strong's mappings")


if __name__ == "__main__":
    main()

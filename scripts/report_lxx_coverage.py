#!/usr/bin/env python3
import argparse
import os
import sqlite3

from init_lxx_db import DEFAULT_DB


def pct(part, total):
    if not total:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def main():
    parser = argparse.ArgumentParser(description="Report Lex LXX lexical coverage.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Lex LXX SQLite database")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"Missing LXX DB: {args.db}")

    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        books = [
            row["book"]
            for row in conn.execute(
                """
                SELECT book FROM lxx_text
                UNION
                SELECT book FROM lxx_bridge_text
                UNION
                SELECT book FROM lxx_lemma_strong_map
                ORDER BY book
                """
            )
        ]
        print("book\tparsed\tlemmas\tmorph\tdirect_strongs\tcandidate_tokens\tbridge_strongs")
        totals = {
            "parsed": 0,
            "lemmas": 0,
            "morph": 0,
            "direct": 0,
            "candidate": 0,
            "bridge": 0,
        }
        for book in books:
            parsed = conn.execute(
                "SELECT COUNT(*) FROM lxx_text WHERE book = ?",
                (book,),
            ).fetchone()[0]
            lemmas = conn.execute(
                "SELECT COUNT(*) FROM lxx_text WHERE book = ? AND lemma IS NOT NULL AND lemma != ''",
                (book,),
            ).fetchone()[0]
            direct = conn.execute(
                "SELECT COUNT(*) FROM lxx_text WHERE book = ? AND strong IS NOT NULL AND strong != ''",
                (book,),
            ).fetchone()[0]
            morph = conn.execute(
                "SELECT COUNT(*) FROM lxx_text WHERE book = ? AND morph IS NOT NULL AND morph != ''",
                (book,),
            ).fetchone()[0]
            candidate = conn.execute(
                """
                SELECT COUNT(*)
                FROM lxx_text t
                WHERE t.book = ?
                  AND EXISTS (
                    SELECT 1
                    FROM lxx_lemma_strong_map m
                    WHERE m.book = t.book
                      AND m.lemma = t.lemma
                  )
                """,
                (book,),
            ).fetchone()[0]
            bridge = conn.execute(
                """
                SELECT COUNT(*)
                FROM lxx_bridge_text
                WHERE book = ?
                  AND greek_strong IS NOT NULL
                  AND greek_strong != ''
                """,
                (book,),
            ).fetchone()[0]
            totals["parsed"] += parsed
            totals["lemmas"] += lemmas
            totals["morph"] += morph
            totals["direct"] += direct
            totals["candidate"] += candidate
            totals["bridge"] += bridge
            print(
                "\t".join(
                    [
                        book,
                        str(parsed),
                        f"{lemmas} ({pct(lemmas, parsed)})",
                        f"{morph} ({pct(morph, parsed)})",
                        f"{direct} ({pct(direct, parsed)})",
                        f"{candidate} ({pct(candidate, parsed)})",
                        str(bridge),
                    ]
                )
            )
        print(
            "\t".join(
                [
                    "TOTAL",
                    str(totals["parsed"]),
                    f"{totals['lemmas']} ({pct(totals['lemmas'], totals['parsed'])})",
                    f"{totals['morph']} ({pct(totals['morph'], totals['parsed'])})",
                    f"{totals['direct']} ({pct(totals['direct'], totals['parsed'])})",
                    f"{totals['candidate']} ({pct(totals['candidate'], totals['parsed'])})",
                    str(totals["bridge"]),
                ]
            )
        )


if __name__ == "__main__":
    main()

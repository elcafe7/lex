#!/usr/bin/env python3
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "isbe_raw.txt"
DB_PATH = ROOT / "encyclopedia.db"
SOURCE = "International Standard Bible Encyclopedia"
VOLUME = "Volume II: Clement-Heresh"


SKIP_LINES = {
    "THE INTERNATIONAL STANDARD BIBLE ENCYCLOPAEDIA",
    "INTERNATIONAL STANDARD BIBLE ENCYCLOPAEDIA",
}


def compact_spaces(text):
    return re.sub(r"\s+", " ", text).strip()


def cleaned_line(line):
    line = line.strip()
    if not line:
        return ""
    line = compact_spaces(line)
    if line in SKIP_LINES or "THE INTERNATIONAL STANDARD BIBLE ENCYCLOPAEDIA" in line:
        return ""
    if re.fullmatch(r"\d{1,4}", line):
        return ""
    if len(line) <= 32 and re.fullmatch(r"[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,2}", line):
        return ""
    return line


def candidate_text(lines, idx, window=3):
    parts = []
    for line in lines[idx:idx + window]:
        line = cleaned_line(line)
        if line:
            parts.append(line)
    return " ".join(parts)


def heading_aliases(text):
    if ":" not in text:
        return []
    before_colon = text.split(":", 1)[0]
    if len(before_colon) > 240:
        return []
    if before_colon.upper().startswith("THE INTERNATIONAL STANDARD"):
        return []
    if before_colon.upper().startswith(("VOLUME ", "ASSISTANT EDITORS", "UNIVERSITY", "LIBRARY")):
        return []

    aliases = []
    for segment in before_colon.split(","):
        alias = compact_spaces(segment.split("(", 1)[0].strip(" ,.;"))
        if not alias:
            continue
        if not re.fullmatch(r"[A-Za-z0-9 '&.-]{2,70}", alias):
            continue
        letters = [ch for ch in alias if ch.isalpha()]
        if not letters:
            continue
        uppercase_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        if uppercase_ratio < 0.65:
            continue
        alias = alias.upper()
        if len(alias) < 2 or len(alias) > 70:
            continue
        if alias in {"AV", "RV", "ARV", "LXX", "OT", "NT", "EV", "EVm", "ERV"}:
            continue
        if alias not in aliases:
            aliases.append(alias)
    return aliases


def is_heading_start(lines, idx):
    line = cleaned_line(lines[idx])
    if not line:
        return False
    if not re.match(r"^[A-Z][A-Za-z0-9 '&().,\-;]+", line):
        return False
    text = candidate_text(lines, idx)
    aliases = heading_aliases(text)
    if not aliases:
        return False
    first = aliases[0]
    if len(first.split()) > 8:
        return False
    return True


def clean_entry(lines):
    pieces = []
    carry = ""
    for raw in lines:
        line = cleaned_line(raw)
        if not line:
            continue
        if line.endswith("-") and len(line) > 1:
            carry += line[:-1]
            continue
        if carry:
            line = carry + line
            carry = ""
        pieces.append(line)
    if carry:
        pieces.append(carry)
    text = compact_spaces(" ".join(pieces))
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text


def parse_entries(raw_text):
    lines = raw_text.splitlines()
    starts = []
    for idx in range(len(lines)):
        if is_heading_start(lines, idx):
            starts.append(idx)

    entries = []
    seen_spans = set()
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        if (start, end) in seen_spans:
            continue
        seen_spans.add((start, end))

        aliases = heading_aliases(candidate_text(lines, start))
        if not aliases:
            continue
        content = clean_entry(lines[start:end])
        if len(content) < 40:
            continue
        if "THE HOWARD-SEVERANCE COMPANY" in content:
            continue
        entries.append((aliases, content))
    return entries


def build_database(entries):
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE encyclopedia (
                id INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                canonical_topic TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                volume TEXT NOT NULL
            );
            CREATE INDEX idx_encyclopedia_topic ON encyclopedia(topic);
            CREATE VIRTUAL TABLE encyclopedia_fts
            USING fts5(topic, canonical_topic, content, source, volume, content='encyclopedia', content_rowid='id');
            """
        )
        row_count = 0
        seen_topics = set()
        for aliases, content in entries:
            canonical = aliases[0].title()
            for alias in aliases:
                topic = alias.title()
                key = (topic.lower(), content[:120])
                if key in seen_topics:
                    continue
                seen_topics.add(key)
                cur = conn.execute(
                    """
                    INSERT INTO encyclopedia(topic, canonical_topic, content, source, volume)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (topic, canonical, content, SOURCE, VOLUME),
                )
                conn.execute(
                    """
                    INSERT INTO encyclopedia_fts(rowid, topic, canonical_topic, content, source, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cur.lastrowid, topic, canonical, content, SOURCE, VOLUME),
                )
                row_count += 1
        conn.commit()
        return row_count
    finally:
        conn.close()


def main():
    if not RAW_PATH.exists():
        raise SystemExit(f"Missing raw encyclopedia source: {RAW_PATH}")
    entries = parse_entries(RAW_PATH.read_text(errors="ignore"))
    row_count = build_database(entries)
    print(f"Built {DB_PATH}")
    print(f"Parsed canonical entries: {len(entries)}")
    print(f"Inserted searchable rows: {row_count}")


if __name__ == "__main__":
    main()

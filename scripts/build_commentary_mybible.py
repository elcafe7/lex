#!/usr/bin/env python3
"""Build a Lex commentary database from a MySword ``.cmt.mybible`` module.

Used for Matthew Poole's *English Annotations on the Holy Bible* (1683-85) and
John Gill's *Exposition of the Entire Bible* (1746-63), both public domain.
See docs/editions/COMMENTARIES.md for sources, checksums and spot checks.

The source module is SQLite with ``commentary(book, chapter, fromverse,
toverse, data)``: books numbered 1-66 in Protestant order, ``chapter = 0`` for
a book introduction, ``fromverse = 0`` for a chapter introduction, and the note
as HTML. The output uses the table Lex already reads for Matthew Henry and
John Calvin (``content`` is left NULL: Lex reads ``markdown`` only, and storing
the text twice would push Gill past GitHub's 100 MB file limit):

    commentary(id, reference, book, chapter, section_order, section_title,
               verse_start, verse_end, content, markdown, source, volume,
               source_path)

Book introductions are stored as chapter 1, section 0, titled
"Introduction to <Book>", so `lex commentary Genesis 1` shows them. Chapter
introductions have NULL verse bounds, like Henry's "Chapter Overview", so they
appear for a whole chapter but not for a single verse.

Usage:
    python3 scripts/build_commentary_mybible.py poole SOURCE.cmt.mybible OUT.db
    python3 scripts/build_commentary_mybible.py gill  SOURCE.cmt.mybible OUT.db
"""
import argparse
import hashlib
import html
import os
import re
import sqlite3
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safe_paths import MissingSourceFile, UnsafePathError, safe_source_file  # noqa: E402

# Protestant canon in MySword book-number order (1 = Genesis ... 66 = Revelation),
# spelled the way the existing commentary databases spell them.
BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
    "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians",
    "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon",
    "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude",
    "Revelation",
]

COMMENTARIES = {
    "poole": {
        "source": "Matthew Poole's English Annotations on the Holy Bible",
        "reference_prefix": "poole",
        "author": "Matthew Poole (1624-1679) and continuators",
        "published": "1683-1685",
        "license": "Public domain (published 1683-1685)",
        "module": "MySword poole.cmt.mybible 1.2.2 (2016-10-29), theWord module by Costas Stergiou",
        "source_url": "https://mysword-bible.info/download/getfile.php?file=poole.cmt.mybible.gz",
    },
    "gill": {
        "source": "John Gill's Exposition of the Entire Bible",
        "reference_prefix": "gill",
        "author": "John Gill (1697-1771)",
        "published": "1746-1763",
        "license": "Public domain (published 1746-1763)",
        "module": "MySword gill.cmt.mybible 1.1.2 (2022-07-06), theWord module by Costas Stergiou",
        "source_url": "https://mysword-bible.info/download/getfile.php?file=gill.cmt.mybible.gz",
    },
}

# Characters Markdown would treat as syntax inside running text.
_MD_INLINE = re.compile(r"([\\`*_\[\]<>|])")
_MD_LINE_START = re.compile(r"^(\s*)([#>+\-=]|\d+[.)])(?=\s|$)")
_SENTENCE_END = re.compile(r"[.?!:;\"'\u201d\u2019)\]]\s*$")


def escape_markdown(text):
    return _MD_INLINE.sub(r"\\\1", text)


class _NoteParser(HTMLParser):
    """Turn MySword note HTML into paragraphs of (plain, markdown) text.

    Emphasis markers are placed against the words they wrap (never against a
    space) so Markdown renders them, and emphasis that wraps nothing is dropped.
    """

    _MARKS = {"b": "**", "strong": "**", "i": "*", "em": "*"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []  # [plain parts, markdown parts, first content is a link]
        self._open = []  # emphasis markers currently open, outermost first
        self._pending = []  # opened markers not yet followed by text
        self._new_paragraph()

    def _new_paragraph(self):
        self.paragraphs.append([[], [], None])

    def _break(self):
        para = self.paragraphs[-1]
        written = [m for m in self._open if m not in self._pending]
        for mark in reversed(written):
            self._close_into(para, mark)
        self._new_paragraph()
        self._pending = list(self._open)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("p", "br"):
            self._break()
        elif tag in self._MARKS:
            mark = self._MARKS[tag]
            if mark not in self._open:
                self._open.append(mark)
                self._pending.append(mark)
        elif tag == "a":
            self._mark_start(True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        mark = self._MARKS.get(tag)
        if not mark or mark not in self._open:
            return
        self._open.remove(mark)
        if mark in self._pending:
            self._pending.remove(mark)
            return
        self._close_into(self.paragraphs[-1], mark)

    def finish(self):
        """Close emphasis the source never closed."""
        para = self.paragraphs[-1]
        for mark in reversed([m for m in self._open if m not in self._pending]):
            self._close_into(para, mark)
        self._open, self._pending = [], []

    @staticmethod
    def _close_into(para, mark):
        md = para[1]
        trailing = ""
        while md and md[-1].isspace():
            trailing = md.pop() + trailing
        if md:
            stripped = md[-1].rstrip()
            trailing = md[-1][len(stripped):] + trailing
            md[-1] = stripped
        md.append(mark)
        if trailing:
            md.append(trailing)

    def handle_data(self, data):
        data = data.replace("\xa0", " ")
        if not data:
            return
        para = self.paragraphs[-1]
        para[0].append(data)
        body = data.lstrip()
        if not body:
            para[1].append(data)
            return
        self._mark_start(False)
        lead = data[: len(data) - len(body)]
        if lead:
            para[1].append(lead)
        if self._pending:
            para[1].append("".join(self._pending))
            self._pending = []
        para[1].append(escape_markdown(body))

    def _mark_start(self, is_link):
        para = self.paragraphs[-1]
        if para[2] is None:
            para[2] = is_link


def _tidy(text):
    return re.sub(r"[ \t\r\n]+", " ", text).strip()


_BOLD_MARK = re.compile(r"(?<!\\)\*\*")


def _balance_bold(paragraph):
    """Drop bold markers from a paragraph whose source nesting left one unpaired."""
    if len(_BOLD_MARK.findall(paragraph)) % 2:
        return _BOLD_MARK.sub("", paragraph)
    return paragraph


def _joins_previous(previous, plain, starts_with_link):
    """True when the module broke a paragraph in the middle of a sentence."""
    if starts_with_link:
        return True
    if _SENTENCE_END.search(previous):
        return False
    return not re.match(r"[A-Z]|\d+[.)]", plain)


# Three Gill notes (Luke 6:29, Acts 8:28, Acts 28:27) carry escaped, half-broken
# theWord <scripRef> markup as literal text. Unwrap it to the readable words.
LEAKED_SCRIPREF_FIXES = (
    (re.compile(r'&lt;scripRef version="Gill" content="\['), ""),
    (re.compile(r"&lt;br&gt;"), " "),
    (re.compile(r"&lt;/?hebrew&gt;"), ""),
    (re.compile(r'\]" passage="'), " "),
    (re.compile(r'"&gt;'), " "),
)


def unwrap_leaked_markup(note_html):
    if "&lt;scripRef" not in (note_html or ""):
        return note_html
    for pattern, replacement in LEAKED_SCRIPREF_FIXES:
        note_html = pattern.sub(replacement, note_html)
    return note_html


def note_to_text(note_html):
    """Return (plain text, markdown) for one MySword note.

    Paragraph breaks the module inserts mid-sentence (before an inline Bible
    reference or a Hebrew word) are joined back into the running sentence.
    """
    parser = _NoteParser()
    parser.feed(unwrap_leaked_markup(note_html or ""))
    parser.close()
    parser.finish()
    plain_paras, md_paras = [], []
    for plain_parts, md_parts, starts_with_link in parser.paragraphs:
        plain = _tidy("".join(plain_parts))
        md = _tidy("".join(md_parts))
        if not plain:
            continue
        if plain_paras and _joins_previous(plain_paras[-1], plain, starts_with_link):
            plain_paras[-1] = f"{plain_paras[-1]} {plain}"
            md_paras[-1] = f"{md_paras[-1]} {md}"
        else:
            plain_paras.append(plain)
            md_paras.append(md)
    md_paras = [_balance_bold(p) for p in md_paras]
    md_paras = [_MD_LINE_START.sub(lambda m: f"{m.group(1)}\\{m.group(2)}", p) for p in md_paras]
    return "\n\n".join(plain_paras), "\n\n".join(md_paras)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def section_title(book, chapter, start, end):
    if start is None:
        return "Chapter Introduction"
    if end and end != start:
        return f"{book} {chapter}:{start}-{end}"
    return f"{book} {chapter}:{start}"


def read_module_rows(source_db):
    """Yield (book, chapter, start, end, html) from a MySword commentary module."""
    conn = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT book, chapter, fromverse, toverse, data FROM commentary "
            "ORDER BY book, chapter, fromverse, toverse, id"
        ).fetchall()
        details = conn.execute("SELECT title, version, versiondate FROM details").fetchone()
    finally:
        conn.close()
    return rows, details


def build_commentary(kind, source_db, out_db):
    if kind not in COMMENTARIES:
        raise ValueError(f"unknown commentary: {kind}")
    meta = COMMENTARIES[kind]
    rows, details = read_module_rows(source_db)
    if os.path.exists(out_db):
        os.remove(out_db)
    conn = sqlite3.connect(out_db)
    conn.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE commentary (
            id INTEGER PRIMARY KEY,
            reference TEXT NOT NULL,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            section_order INTEGER NOT NULL,
            section_title TEXT,
            verse_start INTEGER,
            verse_end INTEGER,
            content TEXT,
            markdown TEXT NOT NULL,
            source TEXT NOT NULL,
            volume TEXT,
            source_path TEXT
        );
        """
    )
    stats = {"rows_read": len(rows), "sections": 0, "book_intros": 0, "chapter_intros": 0,
             "empty_skipped": 0, "unknown_book_skipped": 0}
    order = {}
    pending = []
    for book_no, chapter, start, end, note_html in rows:
        if not isinstance(book_no, int) or not 1 <= book_no <= len(BOOKS):
            stats["unknown_book_skipped"] += 1
            continue
        book = BOOKS[book_no - 1]
        content, markdown = note_to_text(note_html)
        if not content:
            stats["empty_skipped"] += 1
            continue
        if chapter == 0:
            chapter, v_start, v_end, title = 1, None, None, f"Introduction to {book}"
            stats["book_intros"] += 1
            key_order = -1
        elif not start:
            v_start = v_end = None
            title = section_title(book, chapter, None, None)
            stats["chapter_intros"] += 1
            key_order = 0
        else:
            v_start = int(start)
            v_end = int(end) if end and int(end) >= v_start else v_start
            title = section_title(book, chapter, v_start, v_end)
            key_order = v_start
        pending.append((book_no, chapter, key_order, book, v_start, v_end, title, content, markdown))
    pending.sort(key=lambda item: (item[0], item[1], item[2]))
    for book_no, chapter, _key, book, v_start, v_end, title, content, markdown in pending:
        order_key = (book, chapter)
        order[order_key] = order.get(order_key, 0) + 1
        conn.execute(
            "INSERT INTO commentary (reference, book, chapter, section_order, section_title, verse_start, "
            "verse_end, content, markdown, source, volume, source_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{meta['reference_prefix']}:{book}:{chapter}", book, chapter, order[order_key], title,
             v_start, v_end, None, markdown, meta["source"], None, os.path.basename(source_db)),
        )
        stats["sections"] += 1
    conn.execute("CREATE INDEX idx_commentary_reference ON commentary(reference)")
    conn.execute("CREATE INDEX idx_commentary_book_chapter ON commentary(book, chapter)")
    metadata = {
        "source": meta["source"],
        "author": meta["author"],
        "published": meta["published"],
        "license": meta["license"],
        "source_module": meta["module"],
        "source_url": meta["source_url"],
        "source_module_title": details[0] if details else "",
        "source_module_version": f"{details[1]} ({details[2]})" if details else "",
        "source_sha256": sha256_file(source_db),
        "format": "MySword commentary module normalized into verse-indexed sections; HTML converted to Markdown",
        "sections": str(stats["sections"]),
    }
    conn.executemany("INSERT INTO metadata (key, value) VALUES (?, ?)", sorted(metadata.items()))
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("kind", choices=sorted(COMMENTARIES))
    parser.add_argument("source", help="MySword .cmt.mybible file (gunzipped)")
    parser.add_argument("output", help="output .db path")
    args = parser.parse_args(argv)
    source_dir = os.path.dirname(os.path.abspath(args.source))
    try:
        source = safe_source_file(source_dir, os.path.basename(args.source))
    except MissingSourceFile:
        parser.error(f"source file not found: {args.source}")
    except UnsafePathError as exc:
        parser.error(str(exc))
    stats = build_commentary(args.kind, source, args.output)
    for key, value in stats.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

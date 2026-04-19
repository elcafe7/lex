#!/usr/bin/env python3
import sqlite3
import os
import sys
import re
import json
import argparse
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
from rich.theme import Theme
from rich.prompt import Prompt

VERSION = "1.2.0"

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "verse.ref": "bold gold3",
    "verse.text": "white",
    "lexicon.num": "bold blue",
    "lexicon.word": "bold green",
    "place.name": "bold orange3",
    "dict.topic": "bold violet",
})

console = Console(theme=custom_theme)

def load_config():
    config = {"db_path": os.path.expanduser("~/bible-lexicon-data/lexicon.db"), "cross_ref_limit": 10}
    config_path = Path(os.path.expanduser("~/.lexrc"))
    if config_path.exists():
        try:
            with open(config_path) as f:
                config.update(json.load(f))
        except:
            pass
    
    # Check if database exists, show helpful error if not
    if not Path(config["db_path"]).exists():
        console.print(f"[warning]Database not found at: {config['db_path']}[/]")
        console.print("[dim]Download from: https://github.com/your-repo/lexicon.db[/]")
        console.print('[dim]Or set custom path in ~/.lexrc: {"db_path": "/path/to/lexicon.db"}[/]')
        sys.exit(1)
    
    return config

CONFIG = load_config()
DB_PATH = CONFIG["db_path"]
CROSS_REF_LIMIT = None

def normalize_ref(q):
    """
    Intelligently handles references.
    'Jn 3:16', 'John 3 16', '1st Gen 1:1' -> ('John:3:16', book, chap, verse)
    """
    abbr = {
        "gn": "Genesis", "gen": "Genesis", "ex": "Exodus", "exo": "Exodus",
        "lv": "Leviticus", "lev": "Leviticus", "nm": "Numbers", "num": "Numbers",
        "dt": "Deuteronomy", "deut": "Deuteronomy", "js": "Joshua", "josh": "Joshua",
        "jg": "Judges", "judg": "Judges", "rt": "Ruth", "1s": "1 Samuel", "2s": "2 Samuel",
        "1k": "1 Kings", "2k": "2 Kings", "1ch": "1 Chronicles", "2ch": "2 Chronicles",
        "ez": "Ezra", "ne": "Nehemiah", "es": "Esther", "jb": "Job", "ps": "Psalms",
        "pr": "Proverbs", "ec": "Ecclesiastes", "sn": "Song of Solomon", "is": "Isaiah",
        "jr": "Jeremiah", "lm": "Lamentations", "ezk": "Ezekiel", "dn": "Daniel",
        "hs": "Hosea", "jl": "Joel", "am": "Amos", "ob": "Obadiah", "jn": "Jonah",
        "mc": "Micah", "na": "Nahum", "hk": "Habakkuk", "zp": "Zephaniah", "hg": "Haggai",
        "zc": "Zechariah", "ml": "Malachi", "mt": "Matthew", "mk": "Mark", "lk": "Luke",
        "jhn": "John", "john": "John", "jn": "Jonah", "ac": "Acts", "rm": "Romans", "1co": "1 Corinthians",
        "2co": "2 Corinthians", "gl": "Galatians", "ep": "Ephesians", "ph": "Philippians",
        "cl": "Colossians", "1th": "1 Thessalonians", "2th": "2 Thessalonians",
        "1ti": "1 Timothy", "2ti": "2 Timothy", "tt": "Titus", "phm": "Philemon",
        "hb": "Hebrews", "jm": "James", "1p": "1 Peter", "2p": "2 Peter",
        "1j": "1 John", "2j": "2 John", "3j": "3 John", "jd": "Jude", "rv": "Revelation",
        "1st": "1", "2nd": "2", "3rd": "3"
    }
    
    # Pre-process ordinal prefixes like "1st" -> "1"
    q_clean = q.lower().strip()
    for prefix in ["1st ", "2nd ", "3rd "]:
        if q_clean.startswith(prefix):
            q_clean = q_clean.replace(prefix, prefix[0] + " ", 1)

    match = re.match(r'^([1-3]?\s?[a-zA-Z]+)\s*(\d+)(?:[\s:.](\d+))?$', q_clean)
    if match:
        book, chap, verse = match.groups()
        book_key = book.replace(" ", "")
        book_name = abbr.get(book_key, book.title())
        
        if verse:
            return f"%{book_name}:{chap}:{verse}%", book_name, chap, verse
        return f"{book_name}:{chap}:", book_name, chap, None
    return None, None, None, None

def sanitize_fts(q):
    return re.sub(r'[^a-zA-Z0-9\s]', ' ', q).strip()

def clean_text(text):
    text = re.sub(r'\*[a-z]+', '', text)
    text = re.sub(r'\[/?[a-z]+\]', '', text)
    text = re.sub(r'["""]', '', text)
    return text.strip()

def get_context(cursor, target_id, padding=2):
    """Fetches surrounding verses based on physical ROWID in the DB."""
    cursor.execute("SELECT reference, text FROM bible WHERE id BETWEEN ? AND ?", (target_id - padding, target_id + padding))
    return cursor.fetchall()

def query_bible(q):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    ref_pattern, book, chap, verse = normalize_ref(q)
    
    if ref_pattern:
        if verse:
            search_pattern = f"%{ref_pattern.replace('%', '')}%"
            cursor.execute(f"SELECT id, reference, text FROM bible WHERE reference LIKE '{search_pattern}%' LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                target_id = result[0]
                context_verses = get_context(cursor, target_id, padding=2)
                
                panel_text = Text()
                for idx, (ref, text) in enumerate(context_verses):
                    is_target = (ref == result[1])
                    style_ref = "verse.ref" if is_target else "info"
                    style_text = "verse.text" if is_target else "dim"
                    
                    if is_target:
                        panel_text.append(f"[{ref}] ", style=style_ref)
                        panel_text.append(f"{clean_text(text)}\n\n", style=style_text)
                    else:
                        panel_text.append(f"[{ref}] ", style=style_ref)
                        panel_text.append(f"{clean_text(text)}\n\n", style=style_text)
                        
                console.print(Panel(panel_text, title=f"📖 Scripture: {book} {chap}", border_style="gold3", expand=False))
                conn.close()
                query_crossrefs(book, chap, verse)
                return True
        elif not verse and chap:
            book_name = book.title()
            search_pattern = f"%{book_name}:{chap}%"
            cursor.execute(f"SELECT reference, text FROM bible WHERE reference LIKE '{search_pattern}%' AND reference NOT LIKE '%:0%'")
            chapter_verses = cursor.fetchall()
            if chapter_verses:
                table = Table(show_header=False, box=None, padding=(0, 1, 0, 1), expand=True)
                table.add_column("Ref", style="verse.ref", justify="right", no_wrap=True)
                table.add_column("Text", style="verse.text", overflow="fold")
                
                for ref, text in chapter_verses:
                    table.add_row(f"[{ref}]", clean_text(text))
                
                console.print(Panel(table, title=f"📖 {book} {chap}", border_style="gold3", expand=False))
                conn.close()
                return True
        
        conn.close()
        return False

    clean_q = sanitize_fts(q)
    if not clean_q:
        conn.close()
        return False

    try:
        # FTS5 magic with relevance ranking
        cursor.execute("SELECT reference, text, rank FROM bible_fts WHERE bible_fts MATCH ? ORDER BY rank LIMIT 7", (clean_q,))
        results = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute("SELECT reference, text FROM bible WHERE text LIKE ? LIMIT 7", (f'%{q}%',))
        results = cursor.fetchall()

    if results:
        table = Table(show_header=False, box=None, padding=(0, 1, 1, 1))
        table.add_column("Ref", style="verse.ref", justify="right")
        table.add_column("Text", style="verse.text")
        
        for res in results:
            text = clean_text(res[1])
            terms = clean_q.split()
            if terms:
                term = terms[0]
                text = re.sub(f"(?i)({term})", r"[bold green]\1[/bold green]", text)
            table.add_row(f"[{res[0]}]", text)
            
        console.print(Panel(table, title=f"🔍 Search Results: '{q}'", border_style="cyan", expand=False))
        conn.close()
        return True
    
    conn.close()
    return False

def query_strongs(q):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    clean_q = sanitize_fts(q)
    if not clean_q: return

    # Direct G1234 / H1234 lookup
    if re.match(r'^[GH]\d+$', q.upper()):
        cursor.execute("SELECT number, word, pronunciation, definition FROM strongs WHERE number = ?", (q.upper(),))
    else:
        try:
            cursor.execute("SELECT number, word, pronunciation, definition FROM strongs_fts WHERE strongs_fts MATCH ? ORDER BY rank LIMIT 3", (clean_q,))
        except sqlite3.OperationalError:
            conn.close()
            return
            
    results = cursor.fetchall()
    if results:
        for num, word, pron, defn in results:
            content = f"[{custom_theme.styles['lexicon.word']}]{word}[/] ({pron})\n\n[dim]{defn}[/]"
            console.print(Panel(content, title=f"📚 Lexicon: {num}", border_style="blue", expand=False))
    conn.close()

def query_places(q):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, lat, lng, description FROM places WHERE name LIKE ? OR description LIKE ? LIMIT 2", (f'%{q}%', f'%{q}%'))
    results = cursor.fetchall()
    if results:
        for name, lat, lng, desc in results:
            content = f"📍 [dim]Coordinates: {lat}, {lng}[/]\n\n{desc}"
            console.print(Panel(content, title=f"🌍 Place: {name}", border_style="orange3", expand=False))
    conn.close()

def query_dictionary(q):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    clean_q = sanitize_fts(q)
    if not clean_q: return

    try:
        cursor.execute("SELECT topic, content, source FROM dictionary_fts WHERE dictionary_fts MATCH ? ORDER BY rank LIMIT 2", (clean_q,))
        results = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute("SELECT topic, content, source FROM dictionary WHERE topic LIKE ? OR content LIKE ? LIMIT 2", (f'%{q}%', f'%{q}%'))
        results = cursor.fetchall()

    if results:
        for topic, content, source in results:
            display_content = content[:600] + "..." if len(content) > 600 else content
            console.print(Panel(display_content, title=f"📖 Dictionary: {topic} (Source: {source})", border_style="violet", expand=False))
    conn.close()

def convert_to_tsref(book, chapter, verse=None):
    """Convert 'John 3 16' -> 'John.3.16' for cross-ref lookup"""
    book_abbr = {
        "Genesis": "Gen.", "Exodus": "Ex.", "Leviticus": "Lev.", "Numbers": "Num.",
        "Deuteronomy": "Deut.", "Joshua": "Josh.", "Judges": "Judg.", "Ruth": "Ruth",
        "1 Samuel": "1Sam.", "2 Samuel": "2Sam.", "1 Kings": "1Kgs.", "2 Kings": "2Kgs.",
        "1 Chronicles": "1Chr.", "2 Chronicles": "2Chr.", "Ezra": "Ezra", "Nehemiah": "Neh.",
        "Esther": "Est.", "Job": "Job", "Psalms": "Ps.", "Proverbs": "Prov.",
        "Ecclesiastes": "Eccl.", "Song of Solomon": "Song", "Isaiah": "Isa.", "Jeremiah": "Jer.",
        "Lamentations": "Lam.", "Ezekiel": "Ezek.", "Daniel": "Dan.", "Hosea": "Hos.",
        "Joel": "Joel", "Amos": "Amos", "Obadiah": "Obad.", "Jonah": "Jonah",
        "Micah": "Mic.", "Nahum": "Nah.", "Habakkuk": "Hab.", "Zephaniah": "Zeph.",
        "Haggai": "Hag.", "Zechariah": "Zech.", "Malachi": "Mal.", "Matthew": "Matt.",
        "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts", "Romans": "Rom.",
        "1 Corinthians": "1Cor.", "2 Corinthians": "2Cor.", "Galatians": "Gal.",
        "Ephesians": "Eph.", "Philippians": "Phil.", "Colossians": "Col.",
        "1 Thessalonians": "1Thess.", "2 Thessalonians": "2Thess.", "1 Timothy": "1Tim.",
        "2 Timothy": "2Tim.", "Titus": "Titus", "Philemon": "Phlm.", "Hebrews": "Heb.",
        "James": "Jas.", "1 Peter": "1Pet.", "2 Peter": "2Pet.", "1 John": "1John.",
        "2 John": "2John.", "3 John": "3John.", "Jude": "Jude", "Revelation": "Rev."
    }
    prefix = book_abbr.get(book, book)
    # Ensure dot after book abbr
    if not prefix.endswith('.'):
        prefix += '.'
    if verse:
        return f"{prefix}{chapter}.{verse}"
    return f"{prefix}{chapter}."

def query_crossrefs(book, chapter, verse=None, limit=None):
    """Query TSK cross-references for a verse"""
    if limit is None:
        limit = CROSS_REF_LIMIT if CROSS_REF_LIMIT else CONFIG.get("cross_ref_limit", 10)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    tsref = convert_to_tsref(book, chapter, verse)
    if not tsref:
        conn.close()
        return
    
    try:
        cursor.execute("SELECT to_ref, votes FROM cross_refs WHERE from_ref = ? ORDER BY votes DESC LIMIT ?", (tsref, limit))
        results = cursor.fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return
    
    if results:
        ref_list = Text()
        for to_ref, votes in results:
            ref_list.append(f"  {to_ref} ", style="verse.ref")
            ref_list.append(f"({votes})\n", style="dim")
        
        title_ref = f"{book} {chapter}:{verse or ''}" if verse else f"{book} {chapter}"
        console.print(Panel(ref_list, title=f"🔗 Cross-Refs: {title_ref}", border_style="cyan", expand=False))
    
    conn.close()

def print_howto():
    markdown = """
# Lex: The Elegant Bible Terminal

It just works. Type what you want to know.

*   **Read:** `lex John 3:16` *(Automatically shows context)*
*   **Search:** `lex mustard seed` *(Semantically ranked results)*
*   **Study:** `lex G3056` or `lex logos` *(Deep original language)*
*   **Explore:** `lex Galilee` *(Geography and history)*
*   **Creeds:** `lex Nicene Creed` or `lex Westminster Confession` *(Historical confessions)*

*Stop fiddling with tabs. Start studying.*

## Options

*   `--help`     Show this help message
*   `--version`   Show version info
*   `--limit N`  Limit cross-refs to N results
*   `--json`     Output in JSON format
*   `--text`     Output in plain text
"""
    console.print(Panel(Markdown(markdown), border_style="dim", expand=False))

def print_help():
    console.print("""
[bold gold3]Lex[/] - The Elegant Bible Terminal

[bold]Usage:[/] lex [options] <query>

[bold]Examples:[/]
  lex John 3:16              Read a verse
  lex forgiveness          Search the Bible
  lex G3056               Study Strong's number
  lex Galilee             Look up a place
  lex Nicene Creed        Read historical creeds/confessions
  lex Westminster Confession Westminster Confession of Faith
  lex --limit 5 John 3:16 Limit cross-refs

[bold]Options:[/]
  -h, --help     Show help
  -v, --version Show version
  -l, --limit N Limit results (default: 10)
  -j, --json   Output as JSON
  -t, --text  Output as plain text

[bold]Files:[/]
  ~/.lexrc  Config file (JSON)

[bold]Demo:[/]
  lex demo
""")

def run_demo():
    demos = [
        ("John 3:16", query_bible),
        ("G3056", query_strongs),
        ("Galilee", query_places),
        ("forgiveness", query_dictionary),
    ]
    for q, func in demos:
        with console.status(f"[bold green]Demo: '{q}'...", spinner="dots"):
            func(q)
        time.sleep(0.5)

    console.print("\n" + "─" * 40)
    console.print("[bold gold3]Demo Complete.[/] You've seen the power of Lex.")
    console.print("Try your first study now. Just type `lex [your search]`.")

def main():
    if len(sys.argv) < 2:
        print_howto()
        sys.exit(0)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--version", action="store_true")
    parser.add_argument("-l", "--limit", type=int, default=None)
    parser.add_argument("-j", "--json", action="store_true")
    parser.add_argument("-t", "--text", action="store_true")
    
    args, unknown = parser.parse_known_args()
    
    if args.help:
        print_help()
        sys.exit(0)
    
    if args.version:
        console.print(f"[bold gold3]Lex[/] version [bold]{VERSION}[/]")
        sys.exit(0)

    query = " ".join(filter(None, [args.query] + unknown))
    
    if not query:
        print_howto()
        sys.exit(0)
    
    if query.lower() in ["demo", "--demo"]:
        run_demo()
        sys.exit(0)

    global CROSS_REF_LIMIT
    CROSS_REF_LIMIT = args.limit
    
    with console.status(f"[bold green]Searching for '{query}'...", spinner="dots"):
        is_ref = query_bible(query)
        
        if not is_ref:
            query_strongs(query)
            query_places(query)
            query_dictionary(query)
            
        if not is_ref:
            has_results = False
            console.print(f"[warning]No results found for '{query}'.[/]")
            console.print(f"[dim]Try a different search term or check the spelling.[/]")

if __name__ == "__main__":
    main()

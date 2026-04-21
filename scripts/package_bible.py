import sqlite3
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

def init_target_db(db_path, metadata):
    """Initializes the target Bible SQLite database with the required schema."""
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Metadata table
    cursor.execute('''CREATE TABLE metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    
    for k, v in metadata.items():
        cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", (k, v))
    
    # Bible text table
    cursor.execute('''CREATE TABLE bible (
        id INTEGER PRIMARY KEY,
        reference TEXT NOT NULL UNIQUE,
        text TEXT NOT NULL
    )''')
    
    # FTS5 table for fast searching
    cursor.execute('''CREATE VIRTUAL TABLE bible_fts USING fts5(
        reference,
        text,
        tokenize='porter'
    )''')
    
    conn.commit()
    return conn

def clean_text(text):
    """Cleans raw text for FTS indexing (removes Strong's tags, formatting, etc.)"""
    # Remove Strong's tags like [H7225] or [G123]
    text = re.sub(r'\[[HG]\d+\]', '', text)
    # Remove other formatting like *p, *r, [i], [/i]
    text = re.sub(r'\*[a-z]+', '', text)
    text = text.replace('[i]', '').replace('[/i]', '')
    # Remove HTML-like tags if any
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def package_kjv_modern(json_dir, db_path):
    """Packages Modern KJV (Oxford 1769) from the kaiserlik/kjv format."""
    metadata = {
        'edition_id': 'kjv',
        'edition_name': 'King James Version (Oxford 1769)',
        'language': 'en',
        'reference_prefix': 'kjv'
    }
    conn = init_target_db(db_path, metadata)
    
    book_map = {
        "Gen": "Genesis", "Exo": "Exodus", "Lev": "Leviticus", "Num": "Numbers", "Deu": "Deuteronomy",
        "Jos": "Joshua", "Jdg": "Judges", "Rth": "Ruth", "1Sa": "1 Samuel", "2Sa": "2 Samuel",
        "1Ki": "1 Kings", "2Ki": "2 Kings", "1Ch": "1 Chronicles", "2Ch": "2 Chronicles", "Ezr": "Ezra",
        "Neh": "Nehemiah", "Est": "Esther", "Job": "Job", "Psa": "Psalms", "Pro": "Proverbs",
        "Ecc": "Ecclesiastes", "Sng": "Song of Solomon", "Isa": "Isaiah", "Jer": "Jeremiah", "Lam": "Lamentations",
        "Eze": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea", "Joe": "Joel", "Amo": "Amos",
        "Oba": "Obadiah", "Jon": "Jonah", "Mic": "Micah", "Nah": "Nahum", "Hab": "Habakkuk",
        "Zep": "Zephaniah", "Hag": "Haggai", "Zec": "Zechariah", "Mal": "Malachi", "Mat": "Matthew",
        "Mar": "Mark", "Luk": "Luke", "Jhn": "John", "Act": "Acts", "Rom": "Romans",
        "1Co": "1 Corinthians", "2Co": "2 Corinthians", "Gal": "Galatians", "Eph": "Ephesians", "Phl": "Philippians",
        "Col": "Colossians", "1Th": "1 Thessalonians", "2Th": "2 Thessalonians", "1Ti": "1 Timothy", "2Ti": "2 Timothy",
        "Tit": "Titus", "Phm": "Philemon", "Heb": "Hebrews", "Jas": "James", "1Pe": "1 Peter",
        "2Pe": "2 Peter", "1Jo": "1 John", "2Jo": "2 John", "3Jo": "3 John", "Jde": "Jude", "Rev": "Revelation"
    }

    bible_entries = []
    fts_entries = []
    
    for filename in sorted(os.listdir(json_dir)):
        if filename.endswith(".json") and filename not in ["lexicon.json", "books.json", "chapter_count.json"]:
            book_abbr = filename.replace(".json", "")
            full_book = book_map.get(book_abbr, book_abbr)
            
            with open(os.path.join(json_dir, filename), 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    book_data = data.get(book_abbr, {})
                    for chapter_key, chapter_data in book_data.items():
                        chapter_num = chapter_key.split("|")[-1]
                        for verse_key, verse_data in chapter_data.items():
                            verse_num = verse_key.split("|")[-1]
                            raw_text = verse_data.get("en", "")
                            ref = f"kjv:{full_book}:{chapter_num}:{verse_num}"
                            bible_entries.append((ref, raw_text))
                            fts_entries.append((ref, clean_text(raw_text)))
                except Exception as e:
                    print(f"Error skipping {filename}: {e}")

    conn.executemany("INSERT INTO bible (reference, text) VALUES (?, ?)", bible_entries)
    conn.executemany("INSERT INTO bible_fts (reference, text) VALUES (?, ?)", fts_entries)
    conn.commit()
    conn.close()
    print(f"Packaged Modern KJV into {db_path}")

def package_kjv_1611(json_dir, db_path):
    """Packages KJV 1611 from the aruljohn/Bible-kjv-1611 format."""
    metadata = {
        'edition_id': 'kjv1611',
        'edition_name': 'King James Version (1611 Original)',
        'language': 'en',
        'reference_prefix': 'kj16'
    }
    conn = init_target_db(db_path, metadata)
    
    bible_entries = []
    fts_entries = []
    
    for filename in sorted(os.listdir(json_dir)):
        if filename.endswith(".json") and filename not in ["Books.json", "Books_chapter_count.json", "README.md"]:
            with open(os.path.join(json_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
                full_book = data.get("book")
                for chapter_data in data.get("chapters", []):
                    chapter_num = chapter_data.get("chapter")
                    for verse_data in chapter_data.get("verses", []):
                        verse_num = verse_data.get("verse")
                        raw_text = verse_data.get("text", "")
                        ref = f"kj16:{full_book}:{chapter_num}:{verse_num}"
                        bible_entries.append((ref, raw_text))
                        fts_entries.append((ref, clean_text(raw_text)))

    conn.executemany("INSERT INTO bible (reference, text) VALUES (?, ?)", bible_entries)
    conn.executemany("INSERT INTO bible_fts (reference, text) VALUES (?, ?)", fts_entries)
    conn.commit()
    conn.close()
    print(f"Packaged KJV 1611 into {db_path}")

def package_nasb_1995(json_file, db_path):
    """Packages NASB 1995 from the jburson/bible-data format."""
    metadata = {
        'edition_id': 'nasb95',
        'edition_name': 'New American Standard Bible (1995)',
        'language': 'en',
        'reference_prefix': 'nasb'
    }
    conn = init_target_db(db_path, metadata)
    
    bible_map = {}
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for verse_data in data:
            ref_raw = verse_data.get("r")
            if not ref_raw: continue
            
            parts = ref_raw.split(":")
            if len(parts) == 4 and parts[3] == "0":
                continue # Skip chapter headings
            
            raw_text = verse_data.get("t", "").strip()
            if ref_raw in bible_map:
                bible_map[ref_raw] += " " + raw_text
            else:
                bible_map[ref_raw] = raw_text

    bible_entries = []
    fts_entries = []
    for ref, text in bible_map.items():
        bible_entries.append((ref, text))
        fts_entries.append((ref, clean_text(text)))

    conn.executemany("INSERT INTO bible (reference, text) VALUES (?, ?)", bible_entries)
    conn.executemany("INSERT INTO bible_fts (reference, text) VALUES (?, ?)", fts_entries)
    conn.commit()
    conn.close()
    print(f"Packaged NASB 1995 into {db_path}")

import csv
import sqlite3
# ... (rest of imports)

def package_lxx(source_db_path, target_db_path):
    """Packages Greek Septuagint (LXX) from eliranwong's SQLite format."""
    metadata = {
        'edition_id': 'lxx',
        'edition_name': 'Septuagint (Rahlfs 1935)',
        'language': 'grc',
        'reference_prefix': 'lxx'
    }
    
    source_conn = sqlite3.connect(source_db_path)
    source_cursor = source_conn.cursor()
    
    # Get book mapping from the source DB
    # eliranwong format uses book_number in 'verses', names in 'books'
    books_res = source_conn.execute("SELECT book_number, long_name FROM books").fetchall()
    book_map = {row[0]: row[1] for row in books_res}
    
    target_conn = init_target_db(target_db_path, metadata)
    
    bible_entries = []
    fts_entries = []
    
    # eliranwong format: book_number, chapter, verse, text
    verses = source_conn.execute("SELECT book_number, chapter, verse, text FROM verses").fetchall()
    for b_num, chap, verse, raw_text in verses:
        book_name = book_map.get(b_num, str(b_num))
        
        # Strip morphological tags like <S>704639</S><m>lxx.P</m>
        clean_v_text = re.sub(r'<[^>]+>.*?</[^>]+>', '', raw_text) # removes <S>...</S> and <m>...</m>
        clean_v_text = re.sub(r'<[^>]+>', '', clean_v_text) # removes any remaining single tags
        clean_v_text = clean_v_text.strip()
        
        ref = f"lxx:{book_name}:{chap}:{verse}"
        bible_entries.append((ref, clean_v_text))
        fts_entries.append((ref, clean_text(clean_v_text)))

    target_conn.executemany("INSERT INTO bible (reference, text) VALUES (?, ?)", bible_entries)
    target_conn.executemany("INSERT INTO bible_fts (reference, text) VALUES (?, ?)", fts_entries)
    target_conn.commit()
    target_conn.close()
    source_conn.close()
    print(f"Packaged LXX into {target_db_path}")

def package_vulgate(csv_path, target_db_path):
    """Packages Latin Vulgate from scrollmapper's CSV format."""
    metadata = {
        'edition_id': 'vulg',
        'edition_name': 'Clementine Vulgate',
        'language': 'la',
        'reference_prefix': 'vulg'
    }
    conn = init_target_db(target_db_path, metadata)
    
    bible_entries = []
    fts_entries = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            book = row['Book']
            chap = row['Chapter']
            verse = row['Verse']
            text = row['Text'].strip()
            
            ref = f"vulg:{book}:{chap}:{verse}"
            bible_entries.append((ref, text))
            fts_entries.append((ref, clean_text(text)))

    conn.executemany("INSERT INTO bible (reference, text) VALUES (?, ?)", bible_entries)
    conn.executemany("INSERT INTO bible_fts (reference, text) VALUES (?, ?)", fts_entries)
    conn.commit()
    conn.close()
    print(f"Packaged Vulgate into {target_db_path}")

def package_geneva_1587(xml_path, db_path):
    """Packages Geneva Bible 1587 from OSIS XML format."""
    metadata = {
        'edition_id': 'gen1587',
        'edition_name': 'Geneva Bible (1587)',
        'language': 'en',
        'reference_prefix': 'gen'
    }
    conn = init_target_db(db_path, metadata)
    
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {'osis': 'http://www.bibletechnologies.net/2003/OSIS/namespace'}
    
    bible_entries = []
    fts_entries = []
    
    for book_div in root.findall('.//osis:div[@type="book"]', ns):
        book_id = book_div.get('osisID')
        for chapter in book_div.findall('osis:chapter', ns):
            chapter_id = chapter.get('osisID').split('.')[-1]
            for verse in chapter.findall('osis:verse', ns):
                verse_num = verse.get('osisID').split('.')[-1]
                
                # Extract text excluding notes but including their tails
                text_parts = []
                if verse.text: text_parts.append(verse.text)
                for elem in verse:
                    if elem.tag == f"{{{ns['osis']}}}note":
                        if elem.tail: text_parts.append(elem.tail)
                    else:
                        if elem.text: text_parts.append(elem.text)
                        if elem.tail: text_parts.append(elem.tail)
                
                raw_text = "".join(text_parts).replace('\n', ' ').strip()
                raw_text = re.sub(r'\s+', ' ', raw_text)
                
                ref = f"gen:{book_id}:{chapter_id}:{verse_num}"
                bible_entries.append((ref, raw_text))
                fts_entries.append((ref, clean_text(raw_text)))

    conn.executemany("INSERT INTO bible (reference, text) VALUES (?, ?)", bible_entries)
    conn.executemany("INSERT INTO bible_fts (reference, text) VALUES (?, ?)", fts_entries)
    conn.commit()
    conn.close()
    print(f"Packaged Geneva 1587 into {db_path}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python package_bible.py <type> <source_path> <target_db>")
        sys.exit(1)
    
    b_type = sys.argv[1]
    source = sys.argv[2]
    target = sys.argv[3]
    
    if b_type == "kjv_modern": package_kjv_modern(source, target)
    elif b_type == "kjv_1611": package_kjv_1611(source, target)
    elif b_type == "nasb95": package_nasb_1995(source, target)
    elif b_type == "gen1587": package_geneva_1587(source, target)
    elif b_type == "lxx": package_lxx(source, target)
    elif b_type == "vulg": package_vulgate(source, target)
    else: print(f"Unknown type: {b_type}")

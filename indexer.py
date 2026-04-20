import sqlite3
import json
import os
import sys
import re

DB_PATH = os.path.expanduser("~/bible-lexicon-data/lexicon.db")
BASE_DIR = os.path.expanduser("~/bible-lexicon-data")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Bible FTS Table (Natural language bible search)
    cursor.execute("DROP TABLE IF EXISTS bible_fts")
    cursor.execute('''CREATE VIRTUAL TABLE bible_fts USING fts5(
        reference,
        text,
        tokenize='porter'
    )''')
    
    # Strong's FTS Table
    cursor.execute("DROP TABLE IF EXISTS strongs_fts")
    cursor.execute('''CREATE VIRTUAL TABLE strongs_fts USING fts5(
        number,
        word,
        definition,
        tokenize='porter'
    )''')
    
    # Dictionary FTS Table
    cursor.execute("DROP TABLE IF EXISTS dictionary_fts")
    cursor.execute('''CREATE VIRTUAL TABLE dictionary_fts USING fts5(
        topic,
        content,
        source,
        tokenize='porter'
    )''')

    # Keep places table as is, but maybe add FTS for description
    cursor.execute('''CREATE TABLE IF NOT EXISTS places (
        name TEXT PRIMARY KEY,
        lat REAL,
        lng REAL,
        description TEXT
    )''')

    conn.commit()
    return conn

def load_esv(conn):
    esv_path = os.path.join(BASE_DIR, "esv-data/data/esv/esv.json")
    if os.path.exists(esv_path):
        with open(esv_path, 'r') as f:
            data = json.load(f)
            # Remove *p and other formatting artifacts for cleaner FTS search
            clean_data = []
            for item in data:
                if 'r' in item and 't' in item:
                    text = re.sub(r'\*[a-z]+', '', item['t'])
                    clean_data.append((item['r'], text))
            conn.executemany("INSERT INTO bible_fts (reference, text) VALUES (?, ?)", clean_data)
        print("Indexed ESV Bible with FTS5.")

def load_strongs(conn):
    # Greek
    greek_path = os.path.join(BASE_DIR, "theolog-ai/data/biblical-languages/strongs-greek.json")
    if os.path.exists(greek_path):
        with open(greek_path, 'r') as f:
            data = json.load(f)
            entries = []
            for k, v in data.items():
                defn = v.get('def') or v.get('definition', '')
                entries.append((k, v.get('lemma', ''), defn))
            conn.executemany("INSERT INTO strongs_fts (number, word, definition) VALUES (?, ?, ?)", entries)
    
    # Hebrew
    hebrew_path = os.path.join(BASE_DIR, "theolog-ai/data/biblical-languages/strongs-hebrew.json")
    if os.path.exists(hebrew_path):
        with open(hebrew_path, 'r') as f:
            data = json.load(f)
            entries = []
            for k, v in data.items():
                defn = v.get('def') or v.get('definition', '')
                entries.append((k, v.get('lemma', ''), defn))
            conn.executemany("INSERT INTO strongs_fts (number, word, definition) VALUES (?, ?, ?)", entries)
    print("Indexed Strong's Concordance with FTS5.")

def load_historical_docs(conn):
    docs_dir = os.path.join(BASE_DIR, "theolog-ai/data/historical-documents")
    if os.path.exists(docs_dir):
        entries = []
        for filename in os.listdir(docs_dir):
            if filename.endswith(".json"):
                with open(os.path.join(docs_dir, filename), 'r') as f:
                    try:
                        doc = json.load(f)
                        title = doc.get('title', filename)
                        # Some docs have sections, others might just be a blob, some use 'chapters'
                        if 'sections' in doc:
                            for section in doc['sections']:
                                content = section.get('content', '')
                                full_topic = f"{title}: {section.get('title', '')}"
                                entries.append((full_topic, content, "TheologAI"))
                        elif 'chapters' in doc:
                            for chapter in doc['chapters']:
                                content = chapter.get('content', '')
                                full_topic = f"{title}: {chapter.get('title', '')}"
                                entries.append((full_topic, content, "TheologAI"))
                        else:
                            entries.append((title, json.dumps(doc, indent=2), "TheologAI"))
                    except:
                        continue
        conn.executemany("INSERT INTO dictionary_fts VALUES (?, ?, ?)", entries)
        print("Indexed Historical Documents with FTS5.")

def load_geodata(conn):
    geo_path = os.path.join(BASE_DIR, "Bible-Geocoding-Data/data/ancient.jsonl")
    if os.path.exists(geo_path):
        entries = []
        with open(geo_path, 'r') as f:
            for line in f:
                item = json.loads(line)
                name = item.get('friendly_id')
                lat, lng = None, None
                if 'identifications' in item and item['identifications']:
                    res = item['identifications'][0].get('resolutions')
                    if res:
                        lonlat = res[0].get('lonlat')
                        if lonlat and ',' in lonlat:
                            lng, lat = map(float, lonlat.split(','))
                if name:
                    entries.append((name, lat, lng, item.get('comment') or ""))
        conn.executemany("INSERT OR REPLACE INTO places VALUES (?, ?, ?, ?)", entries)
        print("Indexed Geodata.")

if __name__ == "__main__":
    conn = init_db()
    load_esv(conn)
    load_strongs(conn)
    load_historical_docs(conn)
    load_geodata(conn)
    conn.commit()
    conn.close()

import sqlite3
import re
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
LXX_DB = os.path.join(ROOT, "lxx.db")
STRONGS_DB = os.path.join(ROOT, "strongs.db")

import json

def clean_definition(defn):
    if not defn:
        return "-"

    # Handle JSON format
    if defn.startswith("{"):
        try:
            data = json.loads(defn)
            defn = data.get("_", defn)
        except json.JSONDecodeError:
            pass

    # Remove newlines and extra spaces
    defn = defn.replace("\n", " ").strip()

    # Take text before first semicolon or comma
    match = re.split(r'[;,]', defn)
    gloss = match[0].strip().strip('"')
    return gloss[:40]

def populate_glosses():
    print("Populating LXX glosses from Strong's dictionary...")

    # 1. Load Strong's definitions
    strongs_map = {}
    if os.path.exists(STRONGS_DB):
        with sqlite3.connect(STRONGS_DB) as conn:
            for number, word, definition in conn.execute(
                "SELECT number, word, definition FROM strongs WHERE number LIKE 'G%'"
            ):
                gloss = clean_definition(definition)
                if not gloss or gloss == "-" or len(gloss) < 2:
                    gloss = word
                strongs_map[number] = gloss
        print(f"Loaded {len(strongs_map)} glosses from Strong's.")

    # 2. Update lxx_text
    with sqlite3.connect(LXX_DB) as conn:
        cursor = conn.cursor()
        print("Updating lxx_text glosses...")

        # Get all tokens with strong numbers
        rows = conn.execute(
            "SELECT id, strong FROM lxx_text WHERE strong IS NOT NULL AND strong != ''"
        ).fetchall()

        updated = 0
        for row_id, strong in rows:
            if strong in strongs_map:
                cursor.execute(
                    "UPDATE lxx_text SET gloss = ? WHERE id = ?",
                    (strongs_map[strong], row_id)
                )
                updated += 1

        conn.commit()
        print(f"Updated {updated} glosses in lxx_text.")

if __name__ == "__main__":
    populate_glosses()

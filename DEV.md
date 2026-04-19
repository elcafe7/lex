# Lex Developer Documentation

## Overview

Lex is a Python CLI application (420 lines) that provides an elegant terminal interface for Bible study. It combines multiple data sources into a unified search experience.

## Architecture

### File Structure
```
./lex              # Main executable
./lexicon.db       # SQLite database (45MB, download separately)
~/.lexrc           # Optional config (JSON)
```

### Database Schema

The `lexicon.db` contains:

| Table | Description | Rows |
|-------|------------|------|
| `bible` | ESV scripture text | ~31,000 |
| `bible_fts` | FTS5 full-text search index | - |
| `strongs` | Hebrew/Greek lexicon | ~13,000 |
| `strongs_fts` | Strong's FTS index | - |
| `places` | Geographic locations | ~5,000 |
| `dictionary` | Theological definitions | ~1,000 |
| `dictionary_fts` | Dictionary FTS index | - |
| `cross_refs` | TSK cross-references | 344,799 |

## Core Components

### 1. Configuration (Lines 1-46)

**Purpose**: Initialize settings, load config file, set up Rich console.

**Components**:
- Imports: sqlite3, os, sys, re, json, argparse, time, pathlib, rich.*
- `VERSION` - Current version string
- `custom_theme` - Rich color scheme for styled output
- `load_config()` - Reads `~/.lexrc` JSON config
- `CONFIG` / `DB_PATH` - Global config values
- `CROSS_REF_LIMIT` - CLI override for cross-ref limit

```python
# Config file ~/.lexrc format:
{
    "db_path": "~/bible-lexicon-data/lexicon.db",
    "cross_ref_limit": 10
}
```

### 2. normalize_ref() (Lines 48-89)

**Purpose**: Parse user input into structured reference.

**Logic Flow**:
1. Build abbreviation dictionary (66 entries for all Bible books)
2. Clean input (lowercase, handle ordinals like "1st")
3. Match against regex: `^([1-3]?\s?[a-zA-Z]+)\s*(\d+)(?:[\s:.](\d+))?$`
4. Convert abbreviation to full book name
5. Return (ref_pattern, book_name, chapter, verse) or (None, None, None, None)

**Returns**:
- For "John 3:16": (`%John:3:16%`, "John", "3", "16")
- For "john 1": (`John:1:`, "John", "1", None)
- For "forgiveness": (None, None, None, None)

### 3. Text Cleaning (Lines 91-98)

**Purpose**: Remove formatting markup from source text.

```python
def clean_text(text):
    text = re.sub(r'\*[a-z]+', '', text)    # Remove *r, *p markers
    text = re.sub(r'\[/?[a-z]+\]', '', text)  # Remove [italics] tags
    text = re.sub(r'["""]', '', text)        # Remove curly quotes
    return text.strip()
```

### 4. query_bible() (Lines 105-189)

**Purpose**: Main scripture lookup function.

**Logic Flow**:

```
query_bible(input)
    │
    ├─► normalize_ref(input)
    │       │
    │       └─► If ref_pattern exists:
    │           │
    │           ├─► If verse specified:
    │           │   └─► Fetch verse + context (2 verses before/after)
    │           │           Display in Panel
    │           │           Call query_crossrefs()
    │           │
    │           └─► If chapter only (no verse):
    │               └─► Fetch full chapter (exclude :0 headings)
    │                       Display in Table
    │
    └─► If no ref (semantic search):
            │
            ├─► Try FTS5 search (relevance ranked)
            └─► Fall back to LIKE search
                    Display results in Table
```

**Key Behaviors**:
- Verse lookup: shows ±2 verses context
- Chapter lookup: shows full chapter (excludes :0 headings)
- Semantic search: tries FTS5, falls back to LIKE
- Returns True if any result found, False otherwise

### 5. query_strongs() (Lines 191-213)

**Purpose**: Look up Hebrew/Greek lexicon entries.

**Logic Flow**:
- If input matches `^[GH]\d+$` (e.g., "G3056", "H7225"):
  - Direct lookup by number
- Otherwise:
  - FTS search on Greek/Hebrew words
  - Fall back to LIKE search

**Output**: Panel with word, pronunciation, definition.

### 6. query_places() (Lines 215-224)

**Purpose**: Geographic lookup.

Simple LIKE search on name/description. Output: Panel with coordinates and description.

### 7. query_dictionary() (Lines 226-243)

**Purpose**: Theological definitions.

Similar FTS pattern to query_strongs(). Output: truncated Panel with topic + source.

### 8. convert_to_tsref() (Lines 245-272)

**Purpose**: Convert book name to Cross-Ref format.

**Format**: Uses "John.3.16" format (with period, not colon).

```python
# Maps full names to abbreviated cross-ref format
"John" → "John."
"Psalms" → "Ps."
# Returns: "John.3.16" or "Ps.23."
```

### 9. query_crossrefs() (Lines 274-302)

**Purpose**: Lookup TSK cross-references.

**Logic**:
1. Convert ref using convert_to_tsref()
2. Query `cross_refs` table by `from_ref`
3. Order by `votes` (crowd-sourced relevance)
4. Display top N results (default 10)

### 10. main() (Lines 370-417)

**Purpose**: CLI entry point.

**Logic Flow**:
```python
main()
    │
    ├─► No args → print_howto()
    │
    ├─► Parse with argparse
    │       - query (nargs=?)
    │       - --help, --version, --limit, --json, --text
    │
    ├─► Handle flags (help, version)
    │
    ├─► Build query from args.query + unknown args
    │       (handles "john 1" without quotes)
    │
    ├─► If "demo" → run_demo()
    │
    └─► Execute queries:
            query_bible() → if success, stop
            Else: query_strongs()
            query_places()
            query_dictionary()
            
            If nothing found → print "No results"
```

## Key Algorithms

### FTS5 Full-Text Search

The app uses SQLite FTS5 for relevance-ranked searching:
```sql
SELECT reference, text, rank FROM bible_fts WHERE bible_fts MATCH ? ORDER BY rank LIMIT 7
```

### Abbreviation Resolution

Multiple abbreviations per book:
```python
"jhn": "John"    # Common abbreviation
"john": "John"   # Full name  
"jn": "Jonah"   # Jonah (different book!)
```

### Context Window

```python
def get_context(cursor, target_id, padding=2):
    # Fetches ROWID-2 to ROWID+2
    # Provides surrounding verses for reading
```

## Database Connection Pattern

Each query function opens its own connection:
```python
def query_bible(q):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # ... queries ...
    conn.close()
    return result
```

## Error Handling

- Missing tables: try/except OperationalError, fallback to LIKE
- Empty results: return False, let main() handle "no results" message
- Config file: wrapped in try/except

## Adding New Features

### Adding a new data source:

1. Add query function (e.g., `query_xyz()`)
2. Follow pattern: connect, query, display Panel, close
3. Call from `main()` in appropriate place
4. Add to `run_demo()` if relevant

### Modifying the database:

See `indexer.py` for database building. Import with:
```python
cursor.executemany("INSERT INTO table (...) VALUES (?, ...)", data)
conn.commit()
```

## Testing

```bash
# Test verse lookup
lex "John 3:16"

# Test chapter
lex "john 1"

# Test search
lex forgiveness

# Test Strong's
lex G3056

# Test no results
lex xyznonexistent

# Test help
lex --help

# Test version
lex --version
```

## Performance Notes

- Database: 45MB SQLite
- FTS5: creates index files on first FTS query
- connections: closed after each query (no pooling)
- Full chapter: can return 150+ verses (John 1 has 51 verses)
# Lex: The Elegant Bible Terminal

A powerful CLI tool for Bible study, combining scripture lookup, cross-references, Strong's Hebrew/Greek lexicon, geographical data, and dictionary definitions in one elegant interface.

## Features

- **Scripture Lookup** - Read any verse or full chapter
- **TSK Cross-References** - Treasury of Scripture Knowledge (344,799 references)
- **Strong's Lexicon** - Hebrew (H#) and Greek (G#) word studies
- **Bible Geography** - Places, coordinates, and historical context
- **Dictionary** - Theological and biblical definitions

## Installation

### Quick Start (one command)

```bash
# Clone and run setup script
git clone https://github.com/your-repo/lex.git
cd lex
./setup.sh

# Done! Test it:
./lex John 3:16
```

### Manual Install

```bash
# Clone
git clone https://github.com/your-repo/lex.git
cd lex

# Install dependency
pip install rich

# Download database (45MB)
./download-db.sh
# OR manually:
curl -L -o lexicon.db "https://github.com/your-repo/releases/latest/download/lexicon.db"

# Make executable
chmod +x lex

# Run
./lex John 3:16
```

### System-wide Install

```bash
sudo cp lex /usr/local/bin/
# Database will be at ~/bible-lexicon-data/lexicon.db by default
# Or set custom path in ~/.lexrc

## Quick Start

```bash
# Read a verse (with context)
lex John 3:16

# Read a full chapter
lex john 1

# Search the Bible
lex forgiveness

# Look up a Strong's number (Hebrew/Greek)
lex G3056

# Find a place
lex Galilee

# Show demo
lex demo
```

## Usage

### Command Options

| Option | Description |
|--------|-------------|
| `lex <query>` | Search or read |
| `lex --help` | Show help |
| `lex --version` | Show version |
| `lex --limit N` | Limit cross-refs to N results |
| `lex demo` | Run interactive demo |

### Query Examples

| Query | Result |
|-------|--------|
| `lex John 3:16` | Verse with context + cross-refs |
| `lex john 1` | Full chapter |
| `lex john` | Search for "john" |
| `lex G3056` | Strong's Greek #3056 (logos) |
| `lex H7225` | Strong's Hebrew #7225 (beginning) |
| `lex must see faith` | Semantic search |

### Book Abbreviations

All standard abbreviations work:
- `gn`, `gen` → Genesis
- `ex`, `exo` → Exodus  
- `ps`, `psalm` → Psalms
- `jhn`, `john` → John
- `rv`, `rev` → Revelation

## Configuration

Create `~/.lexrc` for custom settings:

```json
{
  "db_path": "/path/to/lexicon.db",
  "cross_ref_limit": 10
}
```

## Data Sources

- **Bible Text**: ESV (English Standard Version)
- **Cross-References**: Treasury of Scripture Knowledge (TSK) via OpenBible.info
- **Strong's Numbers**: Public domain concordance
- **Places**: Geographic database
- **Dictionary**: Theological definitions

## License

See individual data sources for licensing. Code is MIT licensed.

## Version

Current version: **1.2.0**

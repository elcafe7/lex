# Lex | The Elegant Bible Terminal 📖

![Lex Banner](docs/images/banner.png)

**A local-first Bible study terminal for reading, searching, studying, and exporting Scripture work.**

Lex is a high-signal CLI tool for the modern student of Scripture. It keeps your study fast, offline, and beautiful. By combining multiple Bible versions, interlinear study, Strong's & STEPBible lexicons, the Treasury of Scripture Knowledge, and historical creeds into a single terminal interface, Lex transforms your shell into a distraction-free theological workbench.

```bash
lex study John 1:1
lex naves grace
lex web Romans 1:1
```

Current version: `2.6.1`


---

## 🖼️ Gallery

<p align="center">
  <img src="docs/images/study_mode.png" width="800" alt="Study Mode">
  <br>
  <i>Study Mode: Interlinear source text, transliteration, and lexicon notes.</i>
</p>

---

## ⚡ Highlights

| Feature | Description |
| :--- | :--- |
| **Multi-Version** | ESV, KJV (1769 & 1611), NASB '95, Geneva 1587, Septuagint (LXX), and Vulgate. |
| **Unified Nave's** | Look up topics (e.g., `lex naves grace`) or find topical associations for any verse (e.g., `lex naves John 3:16`). |
| **Interlinear Study** | Source text, transliteration, and lexicon notes in a surgically precise terminal view. |
| **Verse Web** | Visualize local cross-reference connections ranked by relevance with instant previews. |
| **Historical Creeds** | Instant access to the Nicene Creed, Westminster Confession, and other major historical documents. |
| **Modern Aesthetics** | Auto-detecting light/dark themes with high-contrast, "Blueprint Technical" or "Studio Light" palettes. |
| **Export Engine** | Generate `.docx`/`.pdf` study packets and search results, plus read-mode PNG/PPTX and verse-slide PPTX exports. |
| **Zero Web Dependency** | Runs against local SQLite/JSON stores. Fast, private, and works on a plane. |

---

<p align="center">
  <img src="docs/images/verse_web.png" width="800" alt="Verse Web">
  <br>
  <i>Verse Web: Visualizing cross-reference connections for Romans 1:1.</i>
</p>

---

## 🚀 Installation

### Recommended: Full Git Install (most reliable)

Lex ships with several hundred MB of offline runtime data (SQLite Bibles, lexicons, cross-references, creeds). The cleanest and most reliable way to install is a full Git checkout:

```bash
git clone https://github.com/elcafe7/lex.git
cd lex
./setup.sh
```

`setup.sh` does the following:
- Creates a repo-local `.venv` (Python 3.12+ required)
- Installs Python dependencies
- Installs a `lex` wrapper into `~/.local/bin` that points at this checkout

Local edits to `lex.py` or data files take effect immediately.

#### Verify Git checkout data

For a Git install, the runtime data files are checked against the hashes in the
checked-in `manifest.json`:

```bash
python3 - <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(".")
manifest = json.loads((root / "manifest.json").read_text())
bad = []
for rel, info in manifest["assets"].items():
    path = root / rel
    if not path.exists():
        bad.append(f"missing {rel}")
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != info["hash"]:
        bad.append(f"hash mismatch {rel}")
if bad:
    print("\n".join(bad))
    sys.exit(1)
print(f"Verified {len(manifest['assets'])} runtime assets for Lex {manifest['version']}.")
PY
```

If you are installing from a GitHub release archive instead of `git clone`, use
the release checksum sidecar before unpacking:

```bash
curl -LO https://github.com/elcafe7/lex/releases/download/v2.6.1/lex-v2.6.1.tar.gz
curl -LO https://github.com/elcafe7/lex/releases/download/v2.6.1/lex-v2.6.1.tar.gz.sha256
shasum -a 256 -c lex-v2.6.1.tar.gz.sha256
```

### Alternative: npm launcher

```bash
npm install -g @n8te_/lex-cli
lex --version
```

The npm package is a small Node.js launcher. On first run it downloads the
latest Lex GitHub release archive, verifies the SHA-256 checksum, creates an
isolated Python environment, installs Python dependencies, and caches the full
offline app under your user profile. Future runs reuse that cached install.

Use the launcher when you want a one-line install:

```bash
npm install -g @n8te_/lex-cli
```

Try it after install:

```bash
lex John 3:16
lex search "kingdom of god"
lex strongs G3056
```

For launcher diagnostics:

```bash
lex --npm-version      # Node launcher version
lex --version          # Lex application version
```

### Updating

**Update both code and dependencies**
```bash
git pull
./setup.sh
```

**Refresh only the offline runtime data** (Bibles, lexicons, etc.)
```bash
lex update
```

`lex update` is intentionally data-only and will not overwrite your local code changes.

---

## 📖 Basic Usage

### Reading
References are forgiving. Abbreviations like `jn`, `rom`, or `gn` work perfectly.

```bash
lex John 3:16        # Read a specific verse
lex Romans 8         # Read a whole chapter
lex --next           # Move to the next verse from your last position
lex history          # Show recent Lex commands
lex -B lxx Gen 1:1   # Read from the Septuagint
```

### Study Mode (`-i` or `study`)
This is the main workbench. It renders the selected-version verse context first,
then source text, interlinear rows, lexicon notes, topical associations, and TSK
cross-references. English-version OT study stays Masoretic-oriented through the
local ESV Hebrew/Aramaic interlinear packet. Septuagint and Vulgate study modes
are in progress and should remain separate selected-version paths (`-B lxx` and
`-B vulg`) as their data layers mature. LXX/Vulgate study data should not
auto-populate when studying an English Bible.

```bash
lex study John 1:1
lex John 3:16 -i
lex -B lxx Genesis 1:1 -i
```

Interactive study actions include next/previous verse, read context, verse web,
and export. Study export supports DOCX/PDF packets and a PPTX verse slide.

### Search & Scopes
Lex search is fast and scoped. You can search the whole Bible or narrow it down to specific canons.
Phrase matches rank first, likely misspellings are corrected transparently, and
book names in reference metadata do not create false results. Use `-john` to
scope to John rather than relying on the word `john`.

<p align="center">
  <img src="docs/images/search_results.png" width="800" alt="Search Results">
</p>

```bash
lex search "kingdom of god"
lex search covenant -nt        # Search only the New Testament
lex search beast -major        # Search only Major Prophets
lex search "holy spirit" -paul  # Search only Pauline Epistles
lex search covenant --page 2 --limit 20
```

Search results include footer commands for the next page and for increasing the
number of results per page. Use explicit book/group scopes such as `-jeremiah`
or `-nt`; a bare book name in the query is treated as text to search for, not
metadata to match.

---

### Manuscript Map

Map a verse to available manuscript readings, or inspect a manuscript profile:

```bash
lex manuscript John 1:1
lex manuscript Isaiah 53:11
lex manuscript P66
lex manuscript 1Qisaa
```

Lex uses bundled or cached shards first. Missing shards are fetched individually
from Lex Web and cached under `~/.cache/lex/manuscripts/` for offline reuse.

---

## 🏛️ Reference & Theology

### Nave's Topical Bible
Lex features a unified Nave's engine. Use it to find verses by topic or topics by verse.

<p align="center">
  <img src="docs/images/naves_topics.png" width="800" alt="Nave's Topics">
</p>

```bash
lex naves faith        # Show verses tagged with "Faith"
lex naves John 3:16    # Show all Nave's topics associated with this verse
```


### Lexicons & Dictionary
Lookup Strong's numbers or English definitions directly.

```bash
lex G3056              # Lookup Greek 'Logos'
lex H7225              # Lookup Hebrew 'Reshit'
lex strongs G3056      # Entry plus ESV reverse verse usage
lex strongs G3056 --page 2 --limit 25
lex strongs G3056 --all
lex strongs            # Strong's help and options
lex define propitiation
```

### Creeds & Confessions
```bash
lex creed              # List available creeds
lex creed nicene
lex creed westminster
```

---

## 🎨 Themes & Customization
Lex automatically chooses a theme based on your terminal background.

```bash
lex -light             # Force Studio Light theme
lex -dark              # Force Blueprint Technical theme
lex -auto              # Revert to automatic detection
```

---

## 🗃️ Data Sources
Lex is built on the shoulders of giants. Data is sourced from:
- ESV-derived Bible database
- CCAT LXX morphology and local Septuagint/apocrypha import
- Treasury of Scripture Knowledge (OpenBible)
- STEPBible & Strong's Lexicon data
- Easton's Bible Dictionary & ISBE
- TheologAI Creedal Database

---

## 📄 License
Lex code is MIT licensed. Bible data and Lexicon content are subject to their respective upstream licenses. See [LICENSING.md](docs/LICENSING.md) for details.

---
*Created with care for the Church and the Terminal.*

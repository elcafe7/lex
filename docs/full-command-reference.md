# Full command reference

Every command and option, in one place. Optional flags can usually appear before or after the reference. Most commands show their own help when run without an argument, for example `lex search` or `lex strongs`.

## Install and update

Lex needs Python 3.12 or newer. The recommended install is a full Git checkout because Lex depends on a large local runtime data bundle.

```sh
git clone https://github.com/elcafe7/lex.git
cd lex
./setup.sh
```

`setup.sh` creates a repo-local virtual environment, installs the Python dependencies, and writes a `lex` wrapper into `~/.local/bin`. That wrapper runs the checkout's `lex.py` directly.

### npm Launcher

For a one-line install, use the npm launcher (Node.js 18 or newer):

```sh
npm install -g @n8te_/lex-cli
lex --version
```

The npm package is a small launcher. On first run it downloads the latest Lex GitHub release, verifies its SHA-256 checksum, creates an isolated Python environment, installs the Python dependencies, and caches the full offline app under your user profile. Later runs reuse that cached install.

```sh
lex --npm-version   # Node launcher version
lex --version       # Lex application version
```

### Release Archive

To install from a GitHub release archive instead of `git clone`, check the archive against its checksum file before unpacking:

```sh
curl -LO https://github.com/elcafe7/lex/releases/download/v2.6.9/lex-v2.6.9.tar.gz
curl -LO https://github.com/elcafe7/lex/releases/download/v2.6.9/lex-v2.6.9.tar.gz.sha256
shasum -a 256 -c lex-v2.6.9.tar.gz.sha256
```

### Update Code

```sh
git pull
./setup.sh
```

### Update Runtime Data

```sh
lex update
```

In a Git checkout, `lex update` only refreshes data: it syncs manifest-tracked files under `runtime-data/` and does not overwrite your code (it prints the `git pull` command if your code is older than the data). On an npm install it also upgrades `@n8te_/lex-cli` when a newer version is published, then refreshes the data and prints both versions.

## Reference syntax

References are intentionally forgiving. Full names, common abbreviations, compact references, and chapter-only references are accepted.

### Single verse

```sh
lex John 3:16
lex jn 3:16
lex 2 jn 1:2
```

### Chapter

```sh
lex Romans 8
lex read John 1
lex Gen 1
```

### Verse range

```sh
lex Romans 8:28-39
lex John 3:16–18
lex John 3:16 - 18
```

### Compact and hyphenated

```sh
lex jn3:16
lex 1-chronicles 16:34
lex song-of-solomon 2:1
```

### Several references

```sh
lex John 3:16, Romans 5:8
lex study John 1:1, John 1:14
```

### One-time Bible selection

```sh
lex -B kjv John 3:16
lex -B gen Genesis 1:1
lex -B lxx Genesis 1:1
lex -B dra John 3:16
```

## Commands

### Start, Help, Credits

| Command | Purpose |
|---|---|
| `lex` | Open the main landing screen. |
| `lex help` | Show the full command map. |
| `lex --help` | Show every flag with a short description. `-help`, `-h` and `--h` do the same, also after a subcommand (`lex study --help`). |
| `lex --json <command>` | Print one JSON document for scripts and AI tools. See [Using Lex With AI Tools](#using-lex-with-ai-tools). |
| `lex --plain <command>` | Print the normal output as plain text: no colour, borders, prompts, or animation. |
| `lex --version` | Print the plain application version for scripts. |
| `lex --npm-version` | Print the npm launcher version (npm installs only). |
| `lex --credits` | Show data credits and source acknowledgements. |
| `lex update` or `lex --update` | Refresh manifest-managed runtime data. |

### Read Scripture

| Command | Purpose |
|---|---|
| `lex John 3:16` | Read a verse with nearby context. |
| `lex read John 3:16` | Explicit read command for a verse. |
| `lex Romans 8` | Read a full chapter. |
| `lex --next` | Move to the next verse or chapter from the saved history position. |
| `lex --prev` | Move to the previous verse or chapter from the saved history position. |
| `lex read all` | Read the top cross-references for the last verse you opened. |

### History

| Command | Purpose |
|---|---|
| `lex history` | Show recent Lex commands from the local query history. |
| `lex history --limit 10` | Show a smaller number of recent commands. |
| `lex history --clear` | Clear the local query history. |
| `lex history clear` | Alternate clear form. |

### Study

| Command | Purpose |
|---|---|
| `lex study John 1:1` | Show selected-version context, then source-language study tables, lexicon notes, topical associations, and TSK cross-references. |
| `lex John 3:16 -i` | Quick study mode using the interlinear flag. |
| `lex study Romans 1:1 --no-animate` | Disable pauses between study sections. |
| `lex study Romans 1:1 --animate` | Force pauses between study sections. |
| `lex -B lxx Genesis 1:1 -i` | Explicit LXX study path. This mode is in progress. |
| `lex -B vulg John 1:1 -i` | Explicit Vulgate study path. This mode is in progress. |

> **Note:** English-version Old Testament study is Masoretic-oriented through the local ESV Hebrew/Aramaic interlinear packet. LXX and Vulgate study data should not auto-populate while studying an English Bible.

### Search

| Command | Purpose |
|---|---|
| `lex search israel` | Search Scripture for a word. |
| `lex search "kingdom of god"` | Search for a phrase. Exact phrases rank first, then verses containing all terms. |
| `lex search israel --page 2` | Open a specific result page. |
| `lex search israel --limit 25` | Change result count per page. |
| `lex search covenant -jeremiah` | Scope search to one book. |
| `lex search beast -daniel-revelation` | Scope search to a book range. |
| `lex search resurrection -nt` | Scope search to a canon group. |
| `lex search wisdom -apocrypha -B dra` | Search the deuterocanonical books in an edition that has them. |

Search looks at verse text only, and likely misspellings are corrected and shown in the result footer. A bare book name in the query is searched as text, so use a scope such as `-john` to search within a book.

Supported group scopes include `-ot`, `-old-testament`, `-nt`, `-new-testament`, `-law`, `-pentateuch`, `-torah`, `-history`, `-wisdom`, `-poetry`, `-major`, `-major-prophets`, `-minor`, `-minor-prophets`, `-prophets`, `-gospels`, `-epistles`, `-letters`, `-pauline`, `-general-epistles`, and `-apocrypha` / `-deuterocanon`.

Scopes resolve to the active edition's own book names (ESV "Psalm", Geneva "Ps", Vulgate "I Samuel", LXX "1 Samuel (1 Kingdoms)"). Deuterocanonical scopes such as `-tobit`, `-sirach`, and `-1-maccabees` work in editions that include those books, and any stored book works by its own name (`-laodiceans`, `-joshua-a`). `-wisdom` is the group; use `-wisdom-of-solomon` or `-wis` for the book. A scope the edition lacks is reported rather than returning nothing.

### Verse Web

| Command | Purpose |
|---|---|
| `lex web John 3:16` | Show the verse plus ranked local cross-reference connections. |
| `lex web Romans 1:1 --limit 8` | Control the number of cross-reference rows. |

### Topics, Lexicons, Dictionary

| Command | Purpose |
|---|---|
| `lex naves grace` | Open a Nave's Topical Bible entry. |
| `lex topic grace` | Alias for Nave's topic lookup. |
| `lex naves John 3:16` | Find topical associations for a verse. |
| `lex G3056` | Look up a Strong's Greek number. |
| `lex H7225` | Look up a Strong's Hebrew number. |
| `lex strongs G3056` | Show the lexicon entry plus reverse verse usage from the ESV interlinear index. |
| `lex strongs G3056 --page 2 --limit 25` | Page through reverse verse usage. |
| `lex strongs G3056 --all` | Show all reverse verse usage results. |
| `lex strongs love` | Search Strong's entries by English gloss. |
| `lex strongs` | Open the Strong's help page. |
| `lex define covenant` | Show local dictionary and encyclopedia entries. |

### Commentary And Creeds

| Command | Purpose |
|---|---|
| `lex commentary John 3:16` | Show local commentary notes for a verse (Matthew Henry and John Calvin). |
| `lex commentary Romans 1` | Show local commentary notes for a chapter. |
| `lex creed` | Open the creed and confession navigator. The Apostles', Nicene, Athanasian and Chalcedonian creeds show as numbered lines, original language beside English. |
| `lex creed nicene` | Open a specific creed or confession by search term. |
| `lex creed westminster confession` | Open a longer historical document by name. |

### Export

| Command | Purpose |
|---|---|
| `lex export "John 3:16"` | Open an interactive export menu. |
| `lex export "Romans 8:28-39" --mode read --format pptx` | Export read-mode verses to PPTX. |
| `lex export "Romans 8:28-39" --mode read --format png` | Export read-mode verses to PNG images. |
| `lex export "John 1:1" --mode study --format pdf` | Export study packet as PDF. |
| `lex export "John 1:1" --mode study --format docx` | Export study packet as DOCX. |
| `lex export "John 3:16" --mode web --format pdf` | Export verse web data as PDF. |
| `lex export "John 3:16" --mode web --format docx` | Export verse web data as DOCX. |

## Manuscript map

Map a verse to the manuscript readings and witnesses Lex knows about, or open a manuscript profile by name or Gregory-Aland number.

| Command | Purpose |
|---|---|
| `lex manuscript John 1:1` | Show available readings and witnesses for a verse. |
| `lex manuscript Isaiah 53:11` | Old Testament readings work the same way. |
| `lex manuscript P66` | Open a manuscript profile. |
| `lex manuscript 1Qisaa` | Open a Dead Sea Scrolls profile. |
| `lex manuscript John 1:1 --limit 25` | Show more rows. |

Lex uses bundled or cached manuscript data first. Missing pieces are fetched one at a time from Lex Web and cached under `~/.cache/lex/manuscripts/` for offline reuse.

## Interactive keys

| Mode | Keys |
|---|---|
| Study | `n` next verse, `p` previous verse, `r` read context, `w` verse web, `e` export, `q` done. |
| Search | `1-10` study result, `r #` read result, `n`/`p` page, `e` export, `q` quit. |
| Creeds | `n` next section, `p` previous section, `m` menu, `q` quit. |
| Read | Verse and chapter reads expose export actions in interactive terminals. |

## Exports

Lex writes exports under `~/Documents/lex_exports`. Study packets go under `~/Documents/lex_exports/studies`. The app tries to open finished files automatically and prints the path if the desktop blocks that.

| Mode | Formats | Notes |
|---|---|---|
| Read | PNG, PPTX | Use `--ratio 16:9` or `--ratio 1:1` for PNG exports. |
| Study | DOCX, PDF | Interactive study export also offers a PPTX verse slide. |
| Search | DOCX, PDF, PPTX | Exports the current result page from interactive search. |
| Verse Web | DOCX, PDF | Exports verse plus cross-reference connection data. |

## Bible versions

Lex ships eight Bible editions. The default is the ESV.

| ID | Edition |
|---|---|
| `esv` | English Standard Version |
| `kjv` | King James Version (Oxford 1769) |
| `kj16` | King James Version (1611) |
| `nasb` | New American Standard Bible (1995) |
| `gen` | Geneva Bible (1599) |
| `dra` | Douay-Rheims (1899 American Edition) |
| `lxx` | Septuagint (Rahlfs 1935) |
| `vulg` or `vulgate` | Clementine Vulgate |

`dra` includes the 73-book Catholic canon. Book names match the other English
editions; Douay names such as Tobias, Ecclesiasticus, 3 Kings, and Apocalypse
also work. Psalm numbers follow traditional DRA/Vulgate numbering (Psalm 22 is
"The Lord ruleth me"). The source is the public-domain eBible.org `engDRA` text.

| Command | Purpose |
|---|---|
| `lex -v nasb` | Set the default Bible version. It stays until you change it. |
| `lex version kjv` or `lex bible kjv` | Same as `-v`: set the default Bible version. |
| `lex -v gen John 3:16` | Set the default and read in one step. |
| `lex -B lxx Genesis 1:1` | Use a Bible version for one command only. Your default does not change. |

## Themes and output

Lex chooses a theme from explicit flags, environment variables, saved config, terminal hints, and platform appearance.

| Command | Purpose |
|---|---|
| `lex -light` | Persist Studio Light theme. |
| `lex -dark` | Persist Blueprint Technical theme. |
| `lex -auto` | Clear saved theme and return to automatic detection. |
| `LEX_THEME=dark lex John 3:16` | Override the theme for one command. |
| `NO_COLOR=1 lex John 3:16` | Turn colour off. `LEX_NO_COLOR=1` does the same. |

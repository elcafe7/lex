# Lex User Guide

This guide assumes no technical background. Lex is a Bible study tool that runs in your terminal. You type a command, and Lex shows Scripture, study notes, search results, definitions, or historical Christian documents.

## Starting Lex

Run:

```bash
lex
```

This opens the main help screen with common commands, data credits, and the current version.

## Read Scripture

Read one verse with context:

```bash
lex read John 3:16
lex jn 1:1
lex 2 jn 1:2
```

You can also type the reference directly:

```bash
lex John 3:16
```

Read a full chapter:

```bash
lex read John 1
lex John 1
```

Move from the last passage you opened:

```bash
lex --next
lex --prev
```

## View Command History

Lex keeps a small local history of recent commands so you can see what you have
been studying or searching:

```bash
lex history
lex history --limit 10
```

History is stored at `~/.lex_query_history`. It is separate from
`~/.lex_history`, which only stores the last opened reference for `--next` and
`--prev`.

Clear command history with either form:

```bash
lex history --clear
lex history clear
```

## Study A Verse

Study mode shows the selected-version verse in context, then source-language data, an interlinear table, lexicon notes, topical associations, and Treasury of Scripture Knowledge cross-references.

```bash
lex study John 1:1
lex study rev 1:2
lex study Genesis 1:1
lex study James 1:1
```

You can also use quick study mode:

```bash
lex John 3:16 -i
```

English-version Old Testament study is Masoretic-oriented through the local ESV
Hebrew/Aramaic interlinear packet. Septuagint and Vulgate study modes are still
in progress and should remain separate selected-version paths (`-B lxx` and
`-B vulg`) as their data layers mature. Lex should not auto-populate LXX or
Vulgate study data when you are studying an English Bible:

```bash
lex -B lxx Genesis 1:1      # Reads the Septuagint
lex -B lxx Genesis 1:1 -i   # LXX study path, in progress
lex -B kjv Genesis 1:1 -i   # Reads KJV context, then reports that KJV interlinear is unavailable
lex -B vulg John 1:1 -i     # Vulgate study path, in progress
```

In an interactive terminal, study sections can appear with a subtle pause between them. Turn this off or force it with:

```bash
lex study Romans 1:1 --no-animate
lex study Romans 1:1 --animate
```

In an interactive terminal, study mode ends with a compact action bar:

```text
n / p  next or previous verse
r      read context
w      verse web
e      export
q      done
```

The export menu can save a DOCX/PDF study packet or a PPTX verse slide under:

```text
~/Documents/lex_exports/studies
```

Lex tries to open exported files automatically after saving. If your desktop blocks that, it still prints the saved path.

## View A Verse Web

Verse web mode prints a verse as the visual center, then shows its strongest local cross-reference connections with short previews:

```bash
lex web John 3:16
lex web Romans 1:1 --limit 8
```

Use it when you want a quick map of the major passages connected to one verse.

## Search Scripture

Search for a word or phrase:

```bash
lex search israel
lex search "kingdom of god"
```

Lex searches verse text only. Exact phrases rank first, followed by verses that
contain all search words. Likely typos are corrected and displayed in the result
footer. To search within a book, add a scope such as `-john`.

For common terms with many results, use pages:

```bash
lex search israel --page 2
lex search israel --page 3 --limit 25
```

Limit a search to a book, a book range, or a section of the canon:

```bash
lex search covenant -jeremiah
lex search beast -daniel-revelation
lex search covenant -major
lex search resurrection -nt
```

Supported group scopes include:

- `-ot` / `-old-testament`
- `-nt` / `-new-testament`
- `-law` / `-pentateuch` / `-torah`
- `-history`
- `-wisdom` / `-poetry`
- `-major` / `-major-prophets`
- `-minor` / `-minor-prophets`
- `-prophets`
- `-gospels`
- `-epistles` / `-letters`
- `-pauline`
- `-general-epistles`

In an interactive terminal, search uses a compact action bar:

```text
1-10   study result
r #    read result
n / p  page
e      export
q      quit
```

The export menu can save the current result page as DOCX, PDF, or PPTX under:

```text
~/Documents/lex_exports
```

The explicit `--page` commands still work for scripts, copied commands, and non-interactive output.

## Map Manuscripts

Use a verse reference to compare available readings and witnesses, or a semantic
manuscript name / Gregory-Aland number to inspect its profile:

```bash
lex manuscript John 1:1
lex manuscript Isaiah 53:11
lex manuscript P66
lex manuscript 1Qisaa
```

Use `--limit 25` for more rows. Manuscript shards are local-cache-first; missing
assets are fetched from Lex Web and retained in `~/.cache/lex/manuscripts/`.

## Look Up Strong's Numbers

Look up a Strong's number:

```bash
lex G3056
lex H7225
lex strongs G3056
```

Number lookups show the lexicon entry and, when available, reverse verse usage
from the bundled ESV interlinear index. Use pages or larger result limits when
there are many verses:

```bash
lex strongs G3056 --page 2
lex strongs G3056 --page 3 --limit 25
lex strongs G3056 --all
```

Search Strong's by English gloss:

```bash
lex strongs love
lex strongs servant
```

Open the Strong's help page with:

```bash
lex strongs
```

## Define A Term

Define uses local dictionary entries and the separate encyclopedia database when available:

```bash
lex define grace
lex define covenant
lex define heliodorus
```

Dictionary entries usually come from Easton's Bible Dictionary. Encyclopedia entries currently come from the local ISBE import, which is only partially complete.

## Browse Creeds And Confessions

Open the creed navigator:

```bash
lex creed
```

The navigator groups documents by tradition, then year:

- Ecumenical Creeds
- Lutheran
- Reformed
- Anglican
- Baptist
- Roman Catholic
- Eastern Orthodox

Open a specific document:

```bash
lex creed nicene
lex creed baltimore
lex creed westminster confession
```

When reading a long creed or confession:

- `n` moves to the next section.
- `p` moves to the previous section.
- `m` returns to the section menu.
- `q` quits.

## Bible Versions

Lex supports multiple Bible editions. You can use any of these three ways to switch versions:

To print the Lex application version for scripts or package checks:

```bash
lex --version
```

### 1. Interactive Menu
To see all versions and select a new default through a simple menu:

```bash
lex -v
```

### 2. Direct Switch (Permanent)
To change your default version instantly:

```bash
lex version kjv  # Sets KJV as default
lex -v nasb      # Sets NASB as default
```

### 3. Quick Select (One-time)
To use a different version for just one command without changing your default:

```bash
lex -B lxx Genesis 1:1  # Read the Septuagint once
```

By default, Lex uses the **ESV (English Standard Version)**.

## Keeping Lex Updated


You can update your local Bible databases to the latest data manifest available
on GitHub with one command:

```bash
lex update
```

This verifies file integrity using hashes and downloads only changed data files.
The updater is intentionally restricted to `runtime-data/`; it does not overwrite
the CLI code. Code updates should be handled with Git from the Lex checkout:

```bash
cd /path/to/lex
git pull
./setup.sh
```

## Credits And Licenses

Show full data credits:

```bash
lex --credits
```

Short version: Lex code is intended to be MIT licensed, but the data comes from multiple sources and remains under each source's own license or terms.

## Terminal Themes

Lex tries to match your terminal background automatically. It checks common
theme environment variables, `COLORFGBG`, Apple Terminal and iTerm profiles on
macOS, GNOME/KDE appearance settings on Linux, and then platform appearance.

Use these commands when the automatic choice is wrong:

```bash
lex -light
lex -dark
lex -auto
```

`lex -light` and `lex -dark` are sticky. They save the choice in
`~/.lex_config.json` and future launches keep using it. `lex -auto` clears that
saved setting and returns to automatic detection.

For one command only, use `LEX_THEME`:

```bash
LEX_THEME=light lex John 3:16
LEX_THEME=dark lex search covenant
```

Use `LEX_NO_COLOR=1` when you intentionally want plain output with no Lex
colors.

## Common Problems

If `lex` shows no result for a reference, try spelling the book name fully:

```bash
lex 1 Corinthians 13
lex Song of Solomon 2:1
```

Common abbreviations also work for references:

```bash
lex jn 1:1
lex rom 8:1
lex study rev 1:2
lex 2 jn 1:2
```

If an encyclopedia term is missing, the local encyclopedia is incomplete. The current ISBE import only covers Volume II, `Clement-Heresh`.

If a study verse has no source-language data, Lex can still read the verse. English/Masoretic study depends on the local ESV interlinear JSON dataset; LXX and Vulgate study datasets are still being built out separately.

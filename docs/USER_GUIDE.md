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

## Study A Verse

Study mode shows the verse in context, then source-language data, an interlinear table, lexicon notes, and Treasury of Scripture Knowledge cross-references.

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

The export menu can save the study packet as DOCX or PDF under:

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

The export menu can save the current result page as DOCX or PDF under:

```text
~/Documents/lex_exports
```

The explicit `--page` commands still work for scripts, copied commands, and non-interactive output.

## Look Up Strong's Numbers

Look up a Strong's number:

```bash
lex G3056
lex H7225
```

Search Strong's by English gloss:

```bash
lex strongs love
lex strongs servant
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

## Credits And Licenses

Show full data credits:

```bash
lex --credits
```

Short version: Lex code is intended to be MIT licensed, but the data comes from multiple sources and remains under each source's own license or terms.

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

If a study verse has no interlinear data, Lex can still read the verse, but study mode depends on the local interlinear JSON dataset.

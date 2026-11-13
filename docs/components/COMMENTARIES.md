# Component: Commentaries

`lex commentary <reference>` shows notes from four commentaries, in this
order and colour:

| Commentator | Database | Panel | Coverage | Source | Terms |
|---|---|---|---|---|---|
| Matthew Henry | `commentaries/matthew_henry.db` | blue | Whole Bible except Psalms in the current import | [lyteword/mhenry-complete](https://github.com/lyteword/mhenry-complete) | CC0 per source repository |
| John Calvin | `commentaries/john_calvin.db` | magenta | The books Calvin wrote on | [CCEL](https://ccel.org/ccel/calvin/commentaries/commentaries.i.html) | Public domain |
| Matthew Poole | `commentaries/matthew_poole.db` | green | All 66 books | MySword `poole.cmt.mybible` (below) | Public domain (1683-1685) |
| John Gill | `commentaries/john_gill.db` | yellow | All 66 books | MySword `gill.cmt.mybible` (below) | Public domain (1746-1763) |

A commentary whose database is missing is skipped, so a partial install still
works. `lex --json commentary` returns the same sections (see
`docs/json-output.md`).

## Matthew Poole and John Gill (issue #18)

### Sources

Both come from the free MySword Bible modules, which are conversions of the
theWord modules prepared by Costas Stergiou. The texts are long out of
copyright; the modules add only verse keys and HTML formatting.

| | Poole | Gill |
|---|---|---|
| Work | *English Annotations on the Holy Bible* (Matthew Poole, 1624-1679; completed by his colleagues after Isaiah 58) | *An Exposition of the Old and New Testament* (John Gill, 1697-1771) |
| Download | https://mysword-bible.info/download/getfile.php?file=poole.cmt.mybible.gz | https://mysword-bible.info/download/getfile.php?file=gill.cmt.mybible.gz |
| Module version | 1.2.2 (2016-10-29) | 1.1.2 (2022-07-06) |
| `.gz` SHA-256 | `983cbf864356afccc7f87aa78efd17151c4ba9b10e072af2124256a7ffb0c6aa` | `f65f5117eed0e21aa9e97e1fbb3a175e5c8eb8c456a6c751685603e4537ed43d` |
| Unzipped SHA-256 | `e68941315bebdbebc94c6a68430db9bb74849f633158efb89ec3c603b586b774` | `ae5eb8ff358137396d9c78a8f8db5ea5f36c7153dbca459dd0eb2a61784e40f0` |
| Output | `matthew_poole.db`, 25,350 sections, 27,516,928 bytes | `john_gill.db`, 32,205 sections, 65,691,648 bytes |
| Output SHA-256 | `4c7b2f2c7dc70b4fb11e53869fc90b3feec23d6228725f551ff24e8946a3774f` | `535312ed21ac86c5c13e2449da83bdc55331e70e718911540f8d98b42bd8ae59` |

Why these modules: the SermonIndex MyBible conversions were also checked. Their
Gill is comparable, but their Poole drops the scripture references from the
text and all of Poole's Greek and Hebrew. The MySword modules keep the
references (65,931 in Poole, 55,093 in Gill) and the original-language words
(Gill: 7,092 notes with Hebrew and 1,002 with Greek; Poole: 81 and 487), and
the conversion keeps every one of them.

### Rebuild

```bash
curl -L -o poole.cmt.mybible.gz 'https://mysword-bible.info/download/getfile.php?file=poole.cmt.mybible.gz'
curl -L -o gill.cmt.mybible.gz 'https://mysword-bible.info/download/getfile.php?file=gill.cmt.mybible.gz'
sha256sum poole.cmt.mybible.gz gill.cmt.mybible.gz   # compare with the table above
gunzip poole.cmt.mybible.gz gill.cmt.mybible.gz
python3 scripts/build_commentary_mybible.py poole poole.cmt.mybible runtime-data/commentaries/matthew_poole.db
python3 scripts/build_commentary_mybible.py gill  gill.cmt.mybible  runtime-data/commentaries/john_gill.db
python3 scripts/generate_manifest.py
```

The build is deterministic: the same module gives a byte-identical database.

### Conversion

- Books 1-66 map to Lex's Protestant book names (`Psalms`, `Song of Solomon`).
- A note on verses `a-b` becomes one section with `verse_start = a`,
  `verse_end = b`; `lex commentary John 3:16` shows every section covering 16.
- Chapter introductions (`fromverse = 0`) keep NULL verse bounds, like Henry's
  "Chapter Overview", so they show for a chapter but not a single verse. Book
  introductions (`chapter = 0`) are stored first in chapter 1 as
  "Introduction to <Book>". Poole has no introduction for 2 John or 3 John.
- HTML becomes Markdown: `<b>` to bold (the lemma at the start of each Gill
  note), `<i>` to italic, `<p>` to paragraphs, Bible links to their plain text.
  Markdown characters in the text (`[is]`, `*`, `_`, a line starting `1.`) are
  escaped. Paragraph breaks the modules insert mid-sentence (before an inline
  reference or a Hebrew word) are joined back.
- Source defects handled: three Gill notes (Luke 6:29, Acts 8:28, Acts 28:27)
  carry escaped `<scripRef>` markup as literal text, which is unwrapped to its
  words; nine Poole notes with mis-nested bold lose the bold markers
  instead of showing stray `**`; three empty Poole notes are dropped.
- `content` is NULL: Lex reads `markdown` only, and storing the text twice
  would put Gill over GitHub's 100 MB file limit. The `metadata` table records
  the source URL, module version, source SHA-256, and license.

### Spot checks

`tests/test_commentaries.py` checks 22 references in both databases, from
Genesis 1:1 to Jude 9, against the words each note must contain, plus whole-
Bible coverage, no surviving HTML, balanced bold markers, and that the Hebrew
is kept. Reviewed by hand against the module text: Genesis 1:1, Genesis 3:15,
Exodus 3:14, Leviticus 16:8, Deuteronomy 6:4, Psalm 23:1, Psalm 110:1,
Proverbs 8:22, Isaiah 7:14, Isaiah 53:5, Isaiah 60:1, Jeremiah 31:31,
Daniel 9:25, Micah 5:2, Malachi 4:5, Matthew 16:18, John 1:1, John 3:16,
Romans 9:13, 1 Corinthians 11:24, Hebrews 6:4, 1 John 5:7, Revelation 20:4,
Jude 9.

### Known limits

- The text is the module's transcription, including its spelling slips
  ("propheey" at Malachi 4:5 in Poole). Gill's footnote markers (`{a}`) are
  kept.
- "See Poole on ..." and "See Gill on ..." cross-references are plain text,
  not links.

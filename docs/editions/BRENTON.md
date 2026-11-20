# Brenton English Septuagint (1851): `brenton`

`lex -B brenton <ref>` reads Sir Lancelot C. L. Brenton's English translation
of the Septuagint, first published in 1851. It is a separate edition from
`lxx` (the Greek Rahlfs text with its morphology and interlinear data), which
is unchanged.

## Source and license

| Item | Value |
|---|---|
| Translation | Sir Lancelot Charles Lee Brenton, *The Septuagint Version of the Old Testament, with an English Translation* (London: Samuel Bagster, 1851) |
| License | **Public domain** (published 1851; the eBible.org page and file header both state "Public Domain") |
| Digital source | eBible.org `eng-Brenton`, <https://ebible.org/eng-Brenton/>, VPL download <https://ebible.org/Scriptures/eng-Brenton_vpl.zip> |
| Source date | eBible.org source files dated 2026-11-04 (HTML generated 2026-11-06) |
| Download used | `eng-Brenton_vpl.zip`, SHA-256 `2d14f3c6e933d5fa36f9d45d82e6f2f2e42dfa73c7ce7f7d90aa331c83f07917` |
| Text file used | `eng-Brenton_vpl.txt`, SHA-256 `947192dd992c598465d7cddc613ecacb1cef4fdeb553e5bcb28e99c3c7f31f53` (29,005 lines) |
| Packaged database | `runtime-data/bible_versions/brenton.db`, SHA-256 `27d15e1e27c7543421a3cbbfa025f609dd705e91ae62b2366962650607f69541`, 15,998,976 bytes, 28,302 verses, 53 books (also in `manifest.json`) |
| Builder | `python3 scripts/package_bible.py brenton1851 <dir>/eng-Brenton_vpl.txt runtime-data/bible_versions/brenton.db` |

This is the original 1851 wording. eBible.org also publishes an
updated-spelling Brenton (`englxxup`, Adam Boyd's 2020 language updates
dedicated CC0); Lex does not use it, so the edition stays a single, clearly
public-domain text. ESV/NASB-style modern translations of the Septuagint are
not public domain and are not included.

Brenton marks words he supplied for English sense in square brackets
(`This [is] the book`), and longer bracketed passages for text missing from
some Greek manuscripts (1 Samuel 17) or the Greek additions to Esther. Lex keeps
the brackets as printed.

## Canon and order

Old Testament (39 books, shared English names so references and scopes match
the other editions; Greek Esther and Greek Daniel in their usual places),
then the Apocrypha in Brenton's order:

Tobit, Judith, Wisdom of Solomon, Sirach, Baruch, Letter of Jeremiah,
Susanna, Bel and the Dragon, 1 Maccabees, 2 Maccabees, 1 Esdras, Prayer of
Manasseh, 3 Maccabees, 4 Maccabees.

No New Testament. Brenton does not include the Odes or the Psalms of Solomon
(both are in `lxx`). Prayer of Manasseh is only in `brenton`.

## Versification

Brenton follows the Septuagint, like `lxx`:

- **Psalms** use Greek numbering (Psalm 22 is "The Lord tends me as a
  shepherd"; Psalm 151 is included).
- **Lettered verses** (Genesis 31:50a, 1 Kings 2:35a–o, the Greek Esther
  additions 1:1a–r, …): the database schema needs whole-number verses, so each
  lettered verse is appended to the verse it follows. 313 lettered lines were
  merged; no text is dropped.
- **Ezra / Nehemiah:** eng-Brenton carries Nehemiah twice, as Esdras B
  chapters 11–23 (Septuagint numbering) and as a separate `NEH` book re-versified
  to the English Bible. Lex keeps the Esdras B copy as Nehemiah 1–13 because it
  matches `lxx` verse for verse, and drops the duplicate.
- **Sirach 6:1–2:** eng-Brenton letters these "6:2a" and "6:2b"; Lex restores
  Brenton's printed numbers 6:1 and 6:2.
- One empty source line (Proverbs 30:1) is skipped.

## Alignment with the Greek `lxx` edition

Same chapter:verse reference in both editions, counted per book. Most books
line up exactly; the differences are real edition differences, not import
errors:

- **Proverbs 24–31:** the Greek order of these chapters differs; Brenton and
  Rahlfs number them differently.
- **Daniel, Susanna, Bel:** Brenton translates Theodotion's text; `lxx` stores
  the Old Greek (`Daniel LXX`, `Susanna LXX`, `Bel LXX`).
- **Tobit:** `lxx` stores the BA text (`Tobit BA`), with more verses.
- **1 Samuel 17, Sirach, 1 Esdras:** passages and verse divisions that the
  two printed editions number differently.

| Brenton book | LXX (Rahlfs) book | Brenton verses | Rahlfs verses | Same ref in both | Brenton only | Rahlfs only |
|---|---|---:|---:|---:|---:|---:|
| Genesis | Genesis | 1531 | 1531 | 1531 | 0 | 0 |
| Exodus | Exodus | 1163 | 1163 | 1163 | 0 | 0 |
| Leviticus | Leviticus | 859 | 859 | 859 | 0 | 0 |
| Numbers | Numbers | 1288 | 1287 | 1287 | 1 | 0 |
| Deuteronomy | Deuteronomy | 958 | 959 | 957 | 1 | 2 |
| Joshua | Joshua B | 643 | 643 | 643 | 0 | 0 |
| Judges | Judges B | 618 | 617 | 617 | 1 | 0 |
| Ruth | Ruth | 85 | 85 | 85 | 0 | 0 |
| 1 Samuel | 1 Samuel (1 Kingdoms) | 791 | 772 | 771 | 20 | 1 |
| 2 Samuel | 2 Samuel (2 Kingdoms) | 693 | 695 | 693 | 0 | 2 |
| 1 Kings | 1 Kings (3 Kingdoms) | 754 | 756 | 754 | 0 | 2 |
| 2 Kings | 2 Kings (4 Kingdoms) | 719 | 719 | 719 | 0 | 0 |
| 1 Chronicles | 1 Chronicles | 930 | 930 | 930 | 0 | 0 |
| 2 Chronicles | 2 Chronicles | 820 | 821 | 820 | 0 | 1 |
| Ezra | Ezra (Esdras B/II: 1-10) | 280 | 280 | 280 | 0 | 0 |
| Nehemiah | Nehemiah (Esdras B/II: 11-23) | 388 | 392 | 388 | 0 | 4 |
| Esther | Esther (with additions) | 164 | 164 | 164 | 0 | 0 |
| Job | Job | 1068 | 1069 | 1068 | 0 | 1 |
| Psalms | Psalms | 2533 | 2533 | 2533 | 0 | 0 |
| Proverbs | Proverbs | 875 | 891 | 709 | 166 | 182 |
| Ecclesiastes | Ecclesiastes (Preacher) | 222 | 222 | 222 | 0 | 0 |
| Song of Solomon | Canticle (Song of Solomon) | 117 | 117 | 117 | 0 | 0 |
| Isaiah | Isaiah | 1289 | 1289 | 1289 | 0 | 0 |
| Jeremiah | Jeremiah | 1296 | 1298 | 1295 | 1 | 3 |
| Lamentations | Lamentations (Threni) | 150 | 151 | 150 | 0 | 1 |
| Ezekiel | Ezekiel | 1265 | 1267 | 1265 | 0 | 2 |
| Daniel | Daniel LXX | 420 | 405 | 401 | 19 | 4 |
| Hosea | Hosea | 197 | 197 | 197 | 0 | 0 |
| Joel | Joel | 73 | 73 | 73 | 0 | 0 |
| Amos | Amos | 146 | 146 | 146 | 0 | 0 |
| Obadiah | Obadiah | 21 | 21 | 21 | 0 | 0 |
| Jonah | Jonah | 48 | 48 | 48 | 0 | 0 |
| Micah | Micah | 105 | 105 | 105 | 0 | 0 |
| Nahum | Nahum | 47 | 47 | 47 | 0 | 0 |
| Habakkuk | Habakkuk | 56 | 56 | 56 | 0 | 0 |
| Zephaniah | Zephaniah | 53 | 53 | 53 | 0 | 0 |
| Haggai | Haggai | 38 | 38 | 38 | 0 | 0 |
| Zechariah | Zechariah | 211 | 211 | 211 | 0 | 0 |
| Malachi | Malachi | 55 | 55 | 55 | 0 | 0 |
| Tobit | Tobit BA | 231 | 248 | 230 | 1 | 18 |
| Judith | Judith | 339 | 340 | 339 | 0 | 1 |
| Wisdom of Solomon | Wisdom of Solomon | 436 | 435 | 435 | 1 | 0 |
| Sirach | Wisdom of Sirach | 1358 | 1366 | 1333 | 25 | 33 |
| Baruch | Baruch | 140 | 141 | 140 | 0 | 1 |
| Letter of Jeremiah | Epistle of Jeremiah | 73 | 72 | 72 | 1 | 0 |
| Susanna | Susanna LXX | 64 | 36 | 36 | 28 | 0 |
| Bel and the Dragon | Bel LXX | 42 | 37 | 37 | 5 | 0 |
| 1 Maccabees | I Maccabees | 924 | 924 | 924 | 0 | 0 |
| 2 Maccabees | II Maccabees | 555 | 555 | 555 | 0 | 0 |
| 1 Esdras | Esdras A/I | 448 | 434 | 434 | 14 | 0 |
| Prayer of Manasseh | (not in lxx.db) | 15 | 0 | 0 | 15 | 0 |
| 3 Maccabees | III Maccabees | 228 | 228 | 228 | 0 | 0 |
| 4 Maccabees | IV Maccabees | 480 | 479 | 477 | 3 | 2 |

The alignment test in
`tests/test_brenton_edition.py` checks the books that match exactly.

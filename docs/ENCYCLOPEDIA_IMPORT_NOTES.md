# Encyclopedia Import Notes

Lex supports a separate encyclopedia database at:

```text
~/bible-lexicon-data/encyclopedia.db
```

The current `encyclopedia.db` was built from the local OCR source:

```text
~/bible-lexicon-data/isbe_raw.txt
```

That file appears to contain only **International Standard Bible Encyclopedia, Volume II: Clement-Heresh**. The importer is functional, but the encyclopedia dataset is incomplete until the remaining ISBE volumes are added.

## Current Implementation

- Import script: `scripts/build_encyclopedia_db.py`
- Output DB: `encyclopedia.db`
- Tables: `encyclopedia`, `encyclopedia_fts`
- Current source coverage: ISBE Volume II only
- Current import count: about 1,900 searchable rows, including aliases
- CLI integration: `lex define <term>` shows encyclopedia entries alongside dictionary entries

## Future Implements

### Complete ISBE Coverage

Add the remaining ISBE volumes as raw OCR/text files, then extend the importer to process multiple source files into one `encyclopedia.db`.

Expected volume coverage:

- Volume I: A-Clem
- Volume II: Clement-Heresh
- Volume III: Hermogenes-Phebe
- Volume IV: Philaar-Zuzim
- Volume V: Indexes, maps, and supplementary material if useful

The exact volume labels may vary by scan/source, so verify title pages before naming import files.

### Suggested Source Directions

Look for public-domain ISBE scans or text from:

- Internet Archive
- HathiTrust public-domain scans
- Google Books public-domain scans
- Project Gutenberg or other public-domain text mirrors, if available
- Wikimedia/CCEL-style mirrors only after checking the text provenance

Prefer plain text or OCR text. PDFs can work, but they should be converted to text first and spot-checked because the importer expects article headings and wrapped OCR lines.

### Suggested File Layout

Use one raw file per volume:

```text
isbe_vol1_raw.txt
isbe_vol2_raw.txt
isbe_vol3_raw.txt
isbe_vol4_raw.txt
isbe_vol5_raw.txt
```

Then update `scripts/build_encyclopedia_db.py` to loop through those files and store the volume label per imported row.

### Import Quality Work

- Improve OCR cleanup for Greek/Hebrew transliteration noise.
- Preserve article subheadings more cleanly.
- Detect and remove page side headers/footers more reliably.
- Add a metadata table with source file, volume, import timestamp, and row counts.
- Add a `--source` or `--rebuild` flag for controlled rebuilds.
- Add import tests with known entries from each volume.

### CLI Work

- Add pagination or expansion for long encyclopedia entries.
- Consider `lex define --source isbe <term>` or `lex encyclopedia <term>` for encyclopedia-only lookups.
- Add a visible source/volume label to each encyclopedia panel.

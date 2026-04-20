# Lex: The Elegant Bible Terminal

Lex is a local-first Bible study CLI. It combines Scripture reading, study mode, search, Strong's lookups, dictionary/encyclopedia definitions, TSK cross-references, and historical Christian documents in one terminal tool.

Current tracked CLI:

```text
./lex.py
```

Current version:

```text
2.3.3-Nav
```

## Start Here

For non-technical users:

- [User Guide](docs/USER_GUIDE.md)

For developers:

- [Developer Guide](docs/DEVELOPER_GUIDE.md)

Component documentation:

- [Lex CLI](docs/components/LEX_CLI.md)
- [Runtime Data Stores](docs/components/DATA_STORES.md)
- [Bible DB Builder](docs/components/BIBLE_DB_BUILDER.md)
- [Encyclopedia Importer](docs/components/ENCYCLOPEDIA_IMPORTER.md)

Supporting docs:

- [Bible Edition Standard](docs/BIBLE_EDITION_STANDARD.md)
- [Encyclopedia Import Notes](docs/ENCYCLOPEDIA_IMPORT_NOTES.md)
- [Licensing Notes](docs/LICENSING.md)

## Common Commands

Open the main screen:

```bash
lex
```

Read Scripture:

```bash
lex read John 3:16
lex John 3:16
lex John 1
```

Study a verse:

```bash
lex study John 1:1
lex John 3:16 -i
```

Search Scripture:

```bash
lex search israel
lex search "kingdom of god" --page 2
```

Look up Strong's:

```bash
lex G3056
lex strongs love
```

Define a term:

```bash
lex define covenant
lex define heliodorus
```

Browse creeds and confessions:

```bash
lex creed
lex creed nicene
lex creed baltimore
```

Show credits and data licenses:

```bash
lex --credits
```

## Data Sources

Lex currently uses local data from:

- ESV-derived Bible database
- Treasury of Scripture Knowledge / OpenBible-style cross-references
- Strong's Hebrew/Greek lexicon data
- STEPBible Greek/Hebrew lexicons
- UBS open-license resources
- Easton's Bible Dictionary
- International Standard Bible Encyclopedia OCR import
- TheologAI historical documents
- Bible geocoding data

The encyclopedia import is incomplete: the current local ISBE import only covers Volume II, `Clement-Heresh`.

## License

Recommended model:

- Lex application code: MIT.
- Bundled/generated data: source-specific terms.

Do not represent generated databases or third-party datasets as MIT licensed. See [Licensing Notes](docs/LICENSING.md).

## Developer Verification

```bash
python3 -m py_compile ./lex.py
python3 ./lex.py
python3 ./lex.py --credits
python3 ./lex.py study James 1:1
```

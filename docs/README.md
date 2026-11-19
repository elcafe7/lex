# Lex docs

Lex is a free Bible program you use by typing in your computer's terminal. It works offline and needs no account. These pages are organised around what you want to do. The same pages are on the web at **[apocalypse.press/lex/docs](https://apocalypse.press/lex/docs/)**.

New here? Start with **[Get started](get-started.md)**: install in about two minutes and read your first verse.

## What do you want to do?

| I want to... | Go to |
|---|---|
| Install Lex and read my first verse | [Get started](get-started.md) |
| Read a verse, chapter, or passage, in any Bible version | [Read a passage](read-a-passage.md) |
| Find out what a Greek or Hebrew word means | [Look up a word](look-up-a-word.md) |
| Find every verse with a word or phrase | [Search the Bible](search-the-bible.md) |
| See the original language word by word | [Study mode](study-mode.md) |
| Read the historical creeds and confessions | [Creeds and confessions](creeds-and-confessions.md) |
| Use Lex from a script or an AI assistant (`--json`) | [Use Lex with AI tools](use-lex-with-ai-tools.md) |
| Fix a problem, or find a quick answer | [Troubleshooting and FAQ](troubleshooting-and-faq.md) |
| Look up every command and option | [Full command reference](full-command-reference.md) |
| Work on Lex itself | [For developers](for-developers.md) |

## Also in this folder

- [json-output.md](json-output.md): every field of the `--json` output.
- [RELEASE_VERIFICATION.md](RELEASE_VERIFICATION.md): how releases are built, scanned, and checked.
- [LICENSING.md](LICENSING.md): licenses for the code, Bible texts, and lexicons.
- [lex-docs.md](lex-docs.md) and [lex-docs.html](lex-docs.html): all of the pages above in one file (generated).

> These pages are the source for the web docs. After editing one, run `python3 scripts/build_docs.py` to refresh the single-file copies; a test fails if they drift.

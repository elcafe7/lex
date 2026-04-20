# Lex Developer Notes

This file used to describe an older `1.2.0` implementation and is intentionally kept short to avoid drifting away from the maintained docs.

Use these references instead:

- [README](README.md) for the project overview and common commands.
- [Developer Guide](docs/DEVELOPER_GUIDE.md) for architecture, verification, and maintenance notes.
- [Lex CLI component](docs/components/LEX_CLI.md) for the active command surface.
- [Runtime Data Stores](docs/components/DATA_STORES.md) for SQLite and JSON dependencies.

The tracked CLI entry point is:

```bash
python3 ./lex.py
```

On the current workstation, the shell alias `lex` resolves through `/usr/local/bin/lex`. Check the local target before changing install behavior:

```bash
alias lex
readlink -f /usr/local/bin/lex
```

Minimum verification after CLI edits:

```bash
python3 -m py_compile ./lex.py
python3 ./lex.py --version
python3 ./lex.py read John 3:16
python3 ./lex.py search israel --limit 2
python3 ./lex.py define heliodorus
```

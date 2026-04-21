#!/usr/bin/env bash
# Lex command installer. This does not download data; clone the repo wherever
# you want Lex to live, then run this script from that clone.

set -euo pipefail

echo "=== Lex: The Elegant Bible Terminal ==="
echo ""

LEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEX_BIN="$LEX_DIR/lex.py"
BASHRC="$HOME/.bashrc"
ALIAS_LINE="alias lex='$LEX_BIN'"

if [ ! -f "$LEX_BIN" ]; then
    echo "Error: lex.py not found next to setup.sh"
    exit 1
fi

chmod +x "$LEX_BIN"

mkdir -p "$HOME/.local/bin"
ln -sf "$LEX_BIN" "$HOME/.local/bin/lex"

touch "$BASHRC"
python3 - "$BASHRC" "$ALIAS_LINE" <<'PY'
from pathlib import Path
import sys

bashrc = Path(sys.argv[1])
alias_line = sys.argv[2]
lines = bashrc.read_text().splitlines()
updated = False
next_lines = []

for line in lines:
    if line.strip().startswith("alias lex="):
        if not updated:
            next_lines.append(alias_line)
            updated = True
        continue
    next_lines.append(line)

if not updated:
    if next_lines and next_lines[-1].strip():
        next_lines.append("")
    next_lines.append("# Lex CLI")
    next_lines.append(alias_line)

bashrc.write_text("\n".join(next_lines) + "\n")
PY

echo ""
echo "=== Lex Command Installed ==="
echo ""
echo "Alias written to: $BASHRC"
echo "Symlink written to: $HOME/.local/bin/lex"
echo ""
echo "Restart your terminal or run:"
echo "  source ~/.bashrc"
echo ""
echo "Then use:"
echo "  lex John 3:16"

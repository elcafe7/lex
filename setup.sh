#!/usr/bin/env bash
# Lex command installer. Clone the repo wherever you want Lex to live, then run
# this script from that clone. Runtime data stays in the clone; Python
# dependencies stay in a repo-local virtual environment.

set -euo pipefail

echo "=== Lex: The Elegant Bible Terminal ==="
echo ""

LEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEX_BIN="$LEX_DIR/lex.py"
LEX_VENV="$LEX_DIR/.venv"
LEX_WRAPPER="$HOME/.local/bin/lex"
BASHRC="$HOME/.bashrc"
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

if [ ! -f "$LEX_BIN" ]; then
    echo "Error: lex.py not found next to setup.sh"
    exit 1
fi

if [ ! -d "$LEX_DIR/runtime-data" ] || [ ! -f "$LEX_DIR/runtime-data/lexicon.db" ]; then
    echo "Error: runtime-data/lexicon.db not found."
    echo "Clone the full repository before running setup.sh:"
    echo "  git clone https://github.com/elcafe7/lex.git"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required."
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "Error: Python 3.12 or newer is required."
    exit 1
fi

python3 -m venv "$LEX_VENV"
"$LEX_VENV/bin/python" -m pip install --no-cache-dir -r "$LEX_DIR/requirements.txt"

mkdir -p "$HOME/.local/bin"
cat > "$LEX_WRAPPER" <<EOF
#!/usr/bin/env bash
exec "$LEX_VENV/bin/python" "$LEX_BIN" "\$@"
EOF
chmod +x "$LEX_WRAPPER"
chmod +x "$LEX_BIN"

touch "$BASHRC"
python3 - "$BASHRC" "$PATH_LINE" <<'PY'
from pathlib import Path
import sys

bashrc = Path(sys.argv[1])
path_line = sys.argv[2]
lines = bashrc.read_text().splitlines()
next_lines = []

for line in lines:
    if line.strip().startswith("alias lex="):
        continue
    next_lines.append(line)

if not any(line.strip() == path_line for line in next_lines):
    if next_lines and next_lines[-1].strip():
        next_lines.append("")
    next_lines.append("# Lex CLI")
    next_lines.append(path_line)

bashrc.write_text("\n".join(next_lines) + "\n")
PY

echo ""
echo "=== Lex Command Installed ==="
echo ""
echo "Virtual environment: $LEX_VENV"
echo "Command wrapper: $LEX_WRAPPER"
echo "PATH entry ensured in: $BASHRC"
echo ""
echo "Restart your terminal or run:"
echo "  source ~/.bashrc"
echo ""
echo "Then use:"
echo "  lex John 3:16"

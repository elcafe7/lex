#!/usr/bin/env bash
# Lex command installer. Clone the repo wherever you want Lex to live, then run
# this script from that clone. Runtime data stays in the clone; Python
# dependencies stay in a repo-local virtual environment.

#
# Options:
#   --alias NAME   also install Lex as NAME (for example lexb), a second name
#                  that cannot clash with the flex lexer's `lex` (issue #1)
#
# Many systems already have /usr/bin/lex (the flex lexer). The wrapper goes in
# ~/.local/bin, and ~/.local/bin is put first in PATH for bash (and zsh when
# it is your shell), so `lex` runs Lex. setup.sh then checks which `lex` wins
# and says what to do if another one still comes first.

set -euo pipefail

LEX_ALIAS=""
while [ $# -gt 0 ]; do
    case "$1" in
        --alias)
            if [ $# -lt 2 ]; then
                echo "Error: --alias needs a name, for example: ./setup.sh --alias lexb"
                exit 1
            fi
            LEX_ALIAS="$2"
            shift 2
            ;;
        --alias=*) LEX_ALIAS="${1#--alias=}"; shift ;;
        -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Error: unknown option: $1 (try ./setup.sh --help)"; exit 1 ;;
    esac
done
if [ -n "$LEX_ALIAS" ]; then
    if ! printf '%s' "$LEX_ALIAS" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._-]*$' || [ "$LEX_ALIAS" = "lex" ]; then
        echo "Error: --alias must be a plain command name other than lex, for example: lexb"
        exit 1
    fi
fi

echo "=== Lex: The Elegant Bible Terminal ==="
echo ""

LEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEX_BIN="$LEX_DIR/lex.py"
LEX_VENV="$LEX_DIR/.venv"
LEX_BIN_DIR="$HOME/.local/bin"
LEX_WRAPPER="$LEX_BIN_DIR/lex"
BASHRC="$HOME/.bashrc"
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
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

write_wrapper() {
    cat > "$1" <<EOF
#!/usr/bin/env bash
exec "$LEX_VENV/bin/python" "$LEX_BIN" "\$@"
EOF
    chmod +x "$1"
}

mkdir -p "$LEX_BIN_DIR"
write_wrapper "$LEX_WRAPPER"
if [ -n "$LEX_ALIAS" ]; then
    write_wrapper "$LEX_BIN_DIR/$LEX_ALIAS"
fi
chmod +x "$LEX_BIN"

# Shell startup files that get the PATH line: always ~/.bashrc, plus ~/.zshrc
# when zsh is the login shell (the macOS default) or a ~/.zshrc already exists.
RC_FILES=("$BASHRC")
if [ "$(basename "${SHELL:-}")" = "zsh" ] || [ -f "$ZSHRC" ]; then
    RC_FILES+=("$ZSHRC")
fi

for RC_FILE in "${RC_FILES[@]}"; do
touch "$RC_FILE"
python3 - "$RC_FILE" "$PATH_LINE" <<'PY'
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
done

echo ""
echo "=== Lex Command Installed ==="
echo ""
echo "Virtual environment: $LEX_VENV"
echo "Command wrapper: $LEX_WRAPPER"
if [ -n "$LEX_ALIAS" ]; then
    echo "Extra name: $LEX_BIN_DIR/$LEX_ALIAS"
fi
echo "PATH entry ensured in: ${RC_FILES[*]}"
echo ""

# Which `lex` will a new terminal run? New bash/zsh shells put ~/.local/bin
# first via the line above. Warn about any other `lex` (usually flex).
echo "Checking for other commands named lex (for example the flex lexer):"
LEX_CHECK_STATUS=0
PATH="$LEX_BIN_DIR:$PATH" bash "$LEX_DIR/scripts/check_lex_command.sh" --expect "$LEX_WRAPPER" || LEX_CHECK_STATUS=$?
CURRENT_LEX="$(command -v lex 2>/dev/null || true)"
if [ -n "$CURRENT_LEX" ] && [ "$CURRENT_LEX" != "$LEX_WRAPPER" ]; then
    echo ""
    echo "Note: this terminal still runs $CURRENT_LEX for \`lex\` until you open a new"
    echo "terminal or run \`source ~/.bashrc\` (or \`source ~/.zshrc\`)."
fi
case "$(basename "${SHELL:-bash}")" in
    bash|zsh) ;;
    *)
        echo ""
        echo "Your login shell is ${SHELL:-unknown}; setup.sh only edits ~/.bashrc and ~/.zshrc."
        echo "Put $LEX_BIN_DIR first in that shell's PATH (fish: fish_add_path $LEX_BIN_DIR),"
        echo "then check with: type -a lex"
        ;;
esac
if [ "$LEX_CHECK_STATUS" -ne 0 ]; then
    echo ""
    echo "Lex is installed, but another lex command will run first. See the fix above."
fi
echo ""
echo "Restart your terminal or run:"
echo "  source ~/.bashrc"
echo ""
echo "Then use:"
echo "  lex John 3:16"
if [ -n "$LEX_ALIAS" ]; then
    echo "  $LEX_ALIAS John 3:16"
fi

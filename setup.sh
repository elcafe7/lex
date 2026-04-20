#!/bin/bash
# Lex Setup Script - Complete installation

set -e

echo "=== Lex: The Elegant Bible Terminal ==="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Install from python.org"
    exit 1
fi

# Check/install Rich
echo "Checking dependencies..."
python3 -c "import rich" 2>/dev/null || pip3 install rich

# Download database if not present
if [ ! -f "lexicon.db" ]; then
    echo "Downloading main database (55MB)..."
    DB_URL="https://github.com/elcafe7/lex/raw/main/lexicon.db"
    if command -v curl &> /dev/null; then
        curl -L -o lexicon.db "$DB_URL"
    elif command -v wget &> /dev/null; then
        wget -O lexicon.db "$DB_URL"
    else
        echo "Error: curl or wget required"
        exit 1
    fi
fi

# Make lex.py executable
if [ -f "lex.py" ]; then
    chmod +x lex.py
fi

# Create local symlink for easier access if bin exists
if [ -d "$HOME/.local/bin" ]; then
    echo "Creating 'lex' symlink in ~/.local/bin..."
    ln -sf "$PWD/lex.py" "$HOME/.local/bin/lex"
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "You can now run Lex using:"
echo "  ./lex.py John 3:16"
if [ -f "$HOME/.local/bin/lex" ]; then
    echo "Or simply:"
    echo "  lex John 3:16"
fi

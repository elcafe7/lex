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
    echo "Downloading database (45MB)..."
    if command -v curl &> /dev/null; then
        curl -L -o lexicon.db "https://github.com/your-repo/releases/latest/download/lexicon.db"
    elif command -v wget &> /dev/null; then
        wget -O lexicon.db "https://github.com/your-repo/releases/latest/download/lexicon.db"
    else
        echo "Error: curl or wget required"
        exit 1
    fi
fi

# Make lex executable
chmod +x lex

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Run: ./lex John 3:16"
echo "Or:  ./lex demo"

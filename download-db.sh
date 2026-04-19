#!/bin/bash
# Lex Database Downloader

DB_URL="https://github.com/your-repo/releases/latest/download/lexicon.db"
DB_FILE="lexicon.db"

echo "Downloading Lex database (45MB)..."

if command -v curl &> /dev/null; then
    curl -L -o "$DB_FILE" "$DB_URL"
elif command -v wget &> /dev/null; then
    wget -O "$DB_FILE" "$DB_URL"
else
    echo "Error: curl or wget required"
    exit 1
fi

if [ -f "$DB_FILE" ]; then
    echo "Download complete! Run 'lex John 3:16' to test."
else
    echo "Download failed. Check URL."
    exit 1
fi

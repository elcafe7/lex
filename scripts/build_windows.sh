#!/bin/bash
# Lex Windows Build Script (requires wine & python installed in wine, or run on Windows)
# This is a helper for CI/CD or manual builds of the standalone EXE

VERSION="2.3.4"
REPO_DIR="/home/n8te/lex"
DIST_DIR="$REPO_DIR/dist/windows"

mkdir -p $DIST_DIR

echo "Preparing build for Lex v$VERSION..."

# We use pyinstaller to create a single-file executable
# --onefile: Bundle everything into one EXE
# --name: Name of the final executable
# --icon: Path to icon (if available)
# --add-data: Include static assets if they are small enough, 
#            but for Lex we rely on the auto-downloader for DBs.

pip install pyinstaller rich python-docx reportlab

pyinstaller --onefile \
            --name lex \
            --clean \
            lex.py

echo "Build complete. Output available at $REPO_DIR/dist/lex.exe"

#!/bin/bash
# Lex Windows build script: builds a standalone one-file lex.exe with
# PyInstaller. Run it on Windows (Git Bash) or under wine with Python
# installed; it is a manual helper, not part of the release workflow.
#
# Every build dependency, including PyInstaller and the app's runtime
# packages, is installed from the hash-locked
# .github/requirements/windows-build-requirements.txt with
# pip --require-hashes (OpenSSF Scorecard Pinned-Dependencies). Dependabot
# keeps that file current. To change a dependency, edit the .in file next to
# it and re-run the uv pip compile command written at the top of it.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQUIREMENTS="$REPO_DIR/.github/requirements/windows-build-requirements.txt"
DIST_DIR="$REPO_DIR/dist/windows"
PYTHON="${PYTHON:-python}"

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$REPO_DIR/pyproject.toml" | head -n 1)"

mkdir -p "$DIST_DIR"
cd "$REPO_DIR"

echo "Preparing build for Lex v${VERSION:-unknown}..."

# Hash-locked install: pip refuses any package whose hash is not in the file.
"$PYTHON" -m pip install --require-hashes -r "$REQUIREMENTS"

# --onefile: bundle everything into one EXE. Databases are not bundled; Lex
# downloads them on first run.
"$PYTHON" -m PyInstaller --onefile \
            --name lex \
            --clean \
            --distpath "$DIST_DIR" \
            lex.py

echo "Build complete. Output available at $DIST_DIR/lex.exe"

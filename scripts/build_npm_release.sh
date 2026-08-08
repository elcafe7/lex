#!/usr/bin/env bash
# Build the versioned Lex archive and SHA-256 sidecar consumed by lex-cli.

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:-$root/dist}"
version="$(python3 - <<'PY'
from pathlib import Path
import re

match = re.search(r'^version\s*=\s*"([^"]+)"$', Path('pyproject.toml').read_text(), re.MULTILINE)
if not match:
    raise SystemExit('Could not read project version from pyproject.toml')
print(match.group(1))
PY
)"

mkdir -p "$output_dir"
archive="$output_dir/lex-v${version}.tar.gz"
checksum="$archive.sha256"

git -C "$root" archive --format=tar --prefix="lex-${version}/" HEAD | gzip -n > "$archive"
if command -v sha256sum >/dev/null 2>&1; then
    hash="$(sha256sum "$archive" | awk '{print $1}')"
else
    hash="$(shasum -a 256 "$archive" | awk '{print $1}')"
fi
printf '%s  %s\n' "$hash" "$(basename "$archive")" > "$checksum"
printf 'Created %s\nCreated %s\n' "$archive" "$checksum"

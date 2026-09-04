#!/usr/bin/env python3
"""
Manifest Generator
Scans Lex runtime data and generates manifest.json with SHA-256 hashes for the
data update system. Code updates are handled by Git/Homebrew/pip, not by Lex
mutating its own installed script.
"""
import os
import json
import hashlib
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(BASE_DIR, "manifest.json")
LEX_PY = os.path.join(BASE_DIR, "lex.py")

def get_file_hash(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_lex_version():
    with open(LEX_PY, "r") as f:
        content = f.read()
        match = re.search(r'VERSION\s*=\s*"([^"]+)"', content)
        return match.group(1) if match else "0.0.0"

def generate_manifest():
    manifest = {
        "version": get_lex_version(),
        "assets": {}
    }
    
    # Track all databases and JSON in runtime-data
    runtime_dir = os.path.join(BASE_DIR, "runtime-data")
    for root, dirs, files in os.walk(runtime_dir):
        dirs.sort()
        files.sort()
        for file in files:
            if file.endswith((".db", ".json", ".txt")):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, BASE_DIR)
                manifest["assets"][rel_path] = {
                    "hash": get_file_hash(full_path),
                    "size": os.path.getsize(full_path),
                    "path": rel_path
                }

    tmp_path = MANIFEST_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, MANIFEST_PATH)
    
    print(f"Manifest generated at {MANIFEST_PATH}")
    print(f"Version: {manifest['version']}")
    print(f"Tracked assets: {len(manifest['assets'])}")

if __name__ == "__main__":
    generate_manifest()

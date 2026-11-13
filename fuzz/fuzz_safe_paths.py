#!/usr/bin/env python3
"""Atheris fuzz harness for Lex's filesystem boundary helpers (issue #36).

Targets the path-injection defences (CodeQL py/path-injection, issues #6/#8/#9):
- lex.check_relative_part / lex.safe_join / lex.confine_path
- scripts/safe_paths.py safe_source_file / safe_source_dir

Invariant: a helper either rejects the name with UnsafePathError (or its
MissingSourceFile subclass) or returns a real path inside the base directory.
Any other exception, or a returned path outside the base, is a crash.

Run locally:
    pip install --require-hashes -r .github/requirements/fuzz-requirements.txt
    python fuzz/fuzz_safe_paths.py fuzz/corpus/safe_paths -max_total_time=60
"""
import atexit
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lex_loader import load_lex, load_safe_paths  # noqa: E402

lex = load_lex()
safe_paths = load_safe_paths()

# A small sandbox: base/ holds a file, a subdirectory and a symlink that points
# outside base/, next to a sibling directory whose name shares base's prefix.
SANDBOX = tempfile.mkdtemp(prefix="lex-fuzz-")
atexit.register(shutil.rmtree, SANDBOX, True)
BASE = os.path.join(SANDBOX, "base")
OUTSIDE = os.path.join(SANDBOX, "base-evil")
os.makedirs(os.path.join(BASE, "sub"))
os.makedirs(OUTSIDE)
for path in (os.path.join(BASE, "file.txt"), os.path.join(BASE, "sub", "inner.txt"),
             os.path.join(OUTSIDE, "secret.txt")):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x")
try:
    os.symlink(OUTSIDE, os.path.join(BASE, "escape"))
    os.symlink(os.path.join(OUTSIDE, "secret.txt"), os.path.join(BASE, "escape.txt"))
except OSError:
    pass  # symlinks unavailable; the other cases still run

BASE_REAL = os.path.realpath(BASE)
BASE_PREFIX = BASE_REAL + os.sep


def inside_base(path):
    return path.startswith(BASE_PREFIX)


def check_name(name):
    """Feed one untrusted name to every boundary helper."""
    try:
        lex.check_relative_part(name)
    except lex.UnsafePathError:
        pass

    try:
        joined = lex.safe_join(BASE, name)
    except lex.UnsafePathError:
        pass
    else:
        assert inside_base(joined), (name, joined)

    try:
        confined = lex.confine_path(os.path.join(BASE, name), (BASE,))
    except lex.UnsafePathError:
        pass
    else:
        assert inside_base(confined), (name, confined)

    try:
        found = safe_paths.safe_source_file(BASE, name)
    except safe_paths.UnsafePathError:
        pass
    else:
        assert inside_base(found) and os.path.isfile(found), (name, found)

    try:
        found_dir = safe_paths.safe_source_dir(BASE, name)
    except safe_paths.UnsafePathError:
        pass
    else:
        assert inside_base(found_dir) and os.path.isdir(found_dir), (name, found_dir)


def test_one_input(data):
    check_name(data.decode("utf-8", errors="surrogateescape"))


def main():
    import atheris

    atheris.instrument_all()
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()

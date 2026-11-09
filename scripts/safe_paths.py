"""Filesystem boundary helpers for Lex developer import scripts.

Paths that the operator types on the command line are trusted local input.
Names that come from downloaded data (a fetched checkout's directory listing,
JSON keys, SQLite rows) are not: resolve them and confirm they stay inside the
source directory before opening them. See CodeQL py/path-injection, issue #9.
"""
import os
import re

_ENCODED_TRAVERSAL = re.compile(r"%(?:2e|2f|5c|00)", re.IGNORECASE)


class UnsafePathError(ValueError):
    """Raised when a path would leave its allowed base directory."""


class MissingSourceFile(UnsafePathError):
    """Raised when a confined source file simply does not exist."""


def safe_source_file(base_dir, name):
    """Return the real path of regular file ``name`` inside ``base_dir``.

    Rejects empty names, NUL, absolute paths, ``..`` segments, encoded
    traversal, and symlinks that resolve outside ``base_dir``.
    """
    if not isinstance(name, str) or not name or "\x00" in name:
        raise UnsafePathError(f"invalid file name: {name!r}")
    if _ENCODED_TRAVERSAL.search(name):
        raise UnsafePathError(f"encoded traversal in file name: {name!r}")
    if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name) or os.path.isabs(name):
        raise UnsafePathError(f"absolute file name: {name!r}")
    if any(part == ".." for part in re.split(r"[\\/]+", name)):
        raise UnsafePathError(f"parent-directory segment in file name: {name!r}")
    base_real = os.path.realpath(base_dir)
    candidate = os.path.realpath(os.path.join(base_real, name))
    prefix = base_real if base_real.endswith(os.sep) else base_real + os.sep
    if not candidate.startswith(prefix):
        raise UnsafePathError(f"file escapes {base_dir}: {name!r}")
    if not os.path.exists(candidate):
        raise MissingSourceFile(f"missing source file: {name!r}")
    if not os.path.isfile(candidate):
        raise UnsafePathError(f"not a regular file: {name!r}")
    return candidate

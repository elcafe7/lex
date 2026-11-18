#!/usr/bin/env python3
"""Emit flag-only GitHub warnings for added protected-server references."""

import argparse
import re
import subprocess
import sys


TERM = "po" + "eta"
TERM_RE = re.compile(re.escape(TERM), re.IGNORECASE)
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_locations(diff):
    """Yield (path, line) for added lines containing the review term."""
    path = None
    line = None
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
            line = None
            continue
        match = HUNK_RE.match(raw)
        if match:
            line = int(match.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            if path and line is not None and TERM_RE.search(raw[1:]):
                yield path, line
            if line is not None:
                line += 1
        elif raw.startswith(" ") and line is not None:
            line += 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("range", help="trusted git range in base..head form")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{7,40}\.\.[0-9a-f]{7,40}", args.range):
        parser.error("range must be base..head SHA values")

    result = subprocess.run(
        ["git", "diff", "--unified=0", args.range],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        print("::warning title=Server reference review::Diff could not be read; no flag result was produced.")
        return 0

    findings = list(added_locations(result.stdout))
    for path, line in findings:
        safe_path = path.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(
            f"::warning file={safe_path},line={line},title=Server reference review::"
            f"{TERM} reference added: verify it is intentional and contains no credential, internal URL, or deployment instruction."
        )
    print(f"Server reference review: {len(findings)} flag-only finding(s) for {TERM}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

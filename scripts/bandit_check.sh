#!/usr/bin/env bash
# Run Bandit (Python static analysis) over the repository and gate on it.
#
# Usage: bandit_check.sh <out-dir>
#   Writes <out-dir>/bandit.json (full report, every severity),
#   <out-dir>/bandit.txt (human-readable, includes the flagged lines),
#   <out-dir>/bandit.md (issue-safe summary from scripts/bandit_gate.py) and
#   <out-dir>/bandit-gate.json (pass/fail and counts for the security report).
# Env:   TAG, REPO (optional; only label the summary, dropped if not plain)
#
# Exit 0 = clean; 1 = medium/high findings or an incomplete scan; 2 = bad
# arguments. Bandit itself runs with --exit-zero and every severity so the
# reports are complete; the gate decides. No baseline, no skipped tests: a
# proven false positive needs an inline "# nosec BXXX  # reason: ..." comment.
# Bandit is installed by the workflow from the hash-pinned
# .github/requirements/bandit-requirements.txt.
set -euo pipefail

out="${1:-}"
die() { echo "error: $*" >&2; exit 2; }
[ -n "$out" ] || die "usage: bandit_check.sh <out-dir>"
[[ "$out" =~ ^[A-Za-z0-9._/-]+$ ]] && [[ "$out" != -* ]] || die "invalid out-dir ${out@Q}"
# TAG and REPO only label the summary: drop anything outside the allowlist
# (the scan itself must still run).
tag="${TAG:-}"
if [[ -n "$tag" && ! "$tag" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "::warning title=Bandit::TAG is not a plain release tag; left out of the report" >&2
  tag=""
fi
repo="${REPO:-}"
if [[ -n "$repo" && ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "::warning title=Bandit::REPO is not owner/name; left out of the report" >&2
  repo=""
fi

command -v bandit >/dev/null || die "bandit is not installed"
version="$(bandit --version | awk 'NR == 1 {print $2}')"
[[ "$version" =~ ^[0-9]+(\.[0-9]+)*$ ]] || version="?"

# Generated or vendored trees only; every Python file in the repo is scanned.
exclude="./.git,./dist,./node_modules,./.venv,./venv"

mkdir -p "$out"
rm -f "$out/bandit.json" "$out/bandit.txt" "$out/bandit.md" "$out/bandit-gate.json"
rc=0
bandit -q -r . -x "$exclude" -f json -o "$out/bandit.json" --exit-zero || rc=$?
bandit -q -r . -x "$exclude" -f txt -o "$out/bandit.txt" --exit-zero || rc=$?
if [ "$rc" -ne 0 ]; then
  # A crashed run leaves no or partial JSON; bandit_gate.py then reports FAIL.
  echo "::error title=Bandit::bandit exited with $rc (scan incomplete)"
fi

set +e
python3 scripts/bandit_gate.py "$out/bandit.json" "$out/bandit.md" \
  --tool-version "$version" \
  --summary-json "$out/bandit-gate.json" \
  ${tag:+--release "$tag"} \
  ${repo:+--repository "$repo"}
gate=$?
set -e
if [ "$rc" -ne 0 ] && [ "$gate" -eq 0 ]; then gate=1; fi
exit "$gate"

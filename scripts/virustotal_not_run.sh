#!/usr/bin/env bash
# Write the "VirusTotal: not run" note for a VT check that was turned on
# (ENABLE_VIRUSTOTAL = 'true') but could not scan. The release is blocked;
# this file is what the "Release blocked" issue and the blocked security
# report show. It never claims a scan happened.
#
# Usage: virustotal_not_run.sh <out.md> <reason>
#   reason: missing-key
set -euo pipefail

out="${1:-}"
reason="${2:-}"
[ -n "$out" ] || { echo "usage: virustotal_not_run.sh <out.md> <reason>" >&2; exit 1; }

case "$reason" in
  missing-key)
    why="the repository variable \`ENABLE_VIRUSTOTAL\` is \`true\` but the \`VT_API_KEY\` secret is not set"
    fix="Add the \`VT_API_KEY\` repository secret (Settings > Secrets and variables > Actions), or set \`ENABLE_VIRUSTOTAL\` to anything other than \`true\` to turn VirusTotal off, then re-run the workflow."
    ;;
  *) echo "error: unknown reason ${reason@Q}" >&2; exit 1 ;;
esac

{
  echo "# VirusTotal: not run"
  echo
  echo "VirusTotal is turned on, but ${why}. **No file was scanned**, so the"
  echo "release is blocked and nothing was published."
  echo
  echo "## Suggested fix"
  echo
  echo "- ${fix}"
} > "$out"

#!/usr/bin/env bash
# Open (or update) the "Release blocked" issue when a release check fails.
#
# Usage: release_blocked_issue.sh <tag> <reports-dir>
# Env:   GH_TOKEN, GH_REPO, RUN_URL, FAILED_JOBS, ASSIGNEE (default elcafe7)
#
# The issue gets the findings, the suggested fix and a fix prompt from the
# scan/VirusTotal reports. Nothing is published when this runs.
set -euo pipefail

tag="$1"
dir="$2"
assignee="${ASSIGNEE:-elcafe7}"
title="Release blocked: ${tag} security check failed"
body="$(mktemp)"

{
  echo "The release workflow for \`${tag}\` stopped before publishing. **Nothing was published**:"
  echo "no release, no release assets, no scan report and no badge data."
  echo
  echo "- Workflow run: ${RUN_URL}"
  echo "- Failed: ${FAILED_JOBS}"
  echo
  found=0
  for f in "$dir"/*.md; do
    [ -f "$f" ] || continue
    found=1
    cat "$f"
    echo
  done
  if [ "$found" -eq 0 ]; then
    echo "No scan report was produced: the build, checksum or attestation step failed before"
    echo "the scan finished. See the workflow run log for the error."
    echo
  fi
  echo "## How to unblock"
  echo
  echo "1. Fix the findings above (see **Suggested fix** / **Fix prompt**) in a PR and merge it."
  echo "2. Release again from the fixed commit (a new tag, or re-run the workflow if the fix was"
  echo "   upstream, for example a corrected advisory or a VirusTotal re-scan)."
  echo "3. Only a fully clean run publishes. That run closes this issue."
} > "$body"

# Issue bodies are capped at 65,536 characters.
if [ "$(wc -c < "$body")" -gt 60000 ]; then
  head -c 60000 "$body" > "$body.cut"
  printf '\n\n(truncated; full reports are in the run artifacts)\n' >> "$body.cut"
  mv "$body.cut" "$body"
fi

cat "$body" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"

number="$(gh issue list --state open --search "in:title \"${title}\"" --json number,title --limit 50 \
  | jq -r --arg t "$title" 'map(select(.title == $t)) | .[0].number // empty')"
if [ -n "$number" ]; then
  gh issue comment "$number" --body-file "$body"
  echo "Updated issue #${number}"
else
  gh issue create --title "$title" --body-file "$body" --assignee "$assignee"
fi

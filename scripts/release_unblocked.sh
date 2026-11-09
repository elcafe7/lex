#!/usr/bin/env bash
# After a clean release, close any open "Release blocked: <tag>" issue.
# Usage: release_unblocked.sh <tag>   Env: GH_TOKEN, GH_REPO, RUN_URL
set -euo pipefail

tag="${1:-}"

# Same allowlist as release_blocked_issue.sh: never interpolate an untrusted
# tag into a gh --search string.
if [[ ! "$tag" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "error: invalid tag ${tag@Q} (must match ^[A-Za-z0-9._-]+$)" >&2
  exit 1
fi

title="Release blocked: ${tag} security check failed"
gh issue list --state open --json number,title --limit 200 \
  | jq -r --arg t "$title" '.[] | select(.title == $t) | .number' \
  | while read -r n; do
      gh issue close "$n" --comment "Released cleanly in ${RUN_URL}. All checks passed."
    done

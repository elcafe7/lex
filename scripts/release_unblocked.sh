#!/usr/bin/env bash
# After a clean release, close any open "Release blocked: <tag>" issue.
# Usage: release_unblocked.sh <tag>   Env: GH_TOKEN, GH_REPO, RUN_URL
set -euo pipefail
tag="$1"
title="Release blocked: ${tag} security check failed"
gh issue list --state open --search "in:title \"${title}\"" --json number,title --limit 50 \
  | jq -r --arg t "$title" '.[] | select(.title == $t) | .number' \
  | while read -r n; do
      gh issue close "$n" --comment "Released cleanly in ${RUN_URL}. All checks passed."
    done

#!/usr/bin/env bash
# Commit one release's security report folder to the default branch.
#
# Usage: commit_security_report.sh <artifact-dir>
#   <artifact-dir> holds exactly one folder <TAG>_<YYYYMMDDTHHMMSSZ>/ from
#   write_security_report.sh (the "security-report" workflow artifact).
# Env: TAG (validated release tag), DEFAULT_BRANCH, GH_TOKEN (GITHUB_TOKEN),
#      REPO (owner/name), SERVER_URL
#
# Runs from a checkout of the default branch. Copies the folder into
# security/reports/, rebuilds the index (update_security_index.sh), commits
# with [skip ci] and pushes. If the push is rejected three times (for example
# by branch protection), pushes a reports/<TAG>_<ts> branch instead and tries
# to open a PR from it; if the token cannot open PRs, prints the compare link.
set -euo pipefail

src_root="${1:-}"
tag="${TAG:-}"
branch="${DEFAULT_BRANCH:-}"
repo="${REPO:-}"
server="${SERVER_URL:-https://github.com}"

die() { echo "error: $*" >&2; exit 1; }

if [[ ! "$tag" =~ ^[A-Za-z0-9._-]+$ ]] || [[ "$tag" == .* ]] || [[ "$tag" == -* ]]; then
  die "invalid tag ${tag@Q} (must match ^[A-Za-z0-9._-]+$ and not start with . or -)"
fi
[[ "$branch" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ ]] || die "invalid DEFAULT_BRANCH ${branch@Q}"
[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "invalid REPO ${repo@Q}"
[[ "$server" =~ ^https://[A-Za-z0-9.-]+$ ]] || die "invalid SERVER_URL ${server@Q}"
[ -d "$src_root" ] || die "artifact directory not found: ${src_root@Q}"

# Exactly one folder named <tag>_<ts>; the name is rebuilt from the
# validated tag plus a timestamp that must match the strict pattern.
name=""
for d in "$src_root"/*/; do
  [ -d "$d" ] || continue
  base="$(basename "$d")"
  ts="${base#"${tag}_"}"
  if [ "$base" = "${tag}_${ts}" ] && [[ "$ts" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
    [ -z "$name" ] || die "more than one report folder for ${tag}"
    name="${tag}_${ts}"
  else
    die "unexpected folder in artifact: ${base@Q}"
  fi
done
[ -n "$name" ] || die "no report folder for ${tag} in ${src_root@Q}"
[ -f "$src_root/$name/summary.md" ] && [ -f "$src_root/$name/report.json" ] \
  || die "report folder is missing summary.md or report.json"
[ "$(jq -r .result "$src_root/$name/report.json")" = "pass" ] \
  || die "only reports from a clean publish are committed"

here="$(cd "$(dirname "$0")" && pwd)"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
# Use GITHUB_TOKEN through gh's credential helper (no token in URLs or .git/config).
if [ -n "${GH_TOKEN:-}" ]; then gh auth setup-git --hostname "${server#https://}"; fi

msg="security: report for ${tag} (${ts}) [skip ci]"

stage() {
  mkdir -p security/reports
  rm -rf "security/reports/${name}"
  cp -R "$src_root/$name" "security/reports/${name}"
  bash "$here/update_security_index.sh" security README.md
  git add -- security README.md
  git commit -q -m "$msg"
}

for attempt in 1 2 3; do
  git fetch -q origin "$branch"
  git reset -q --hard "origin/${branch}"
  stage
  if git push -q origin "HEAD:refs/heads/${branch}"; then
    echo "Committed security/reports/${name} to ${branch}."
    exit 0
  fi
  echo "::warning::push to ${branch} rejected (attempt ${attempt}); retrying"
  sleep $((attempt * 5))
done

# Fallback: branch protection (or a persistent race). Push a side branch.
side="reports/${name}"
git push -q origin "HEAD:refs/heads/${side}"
compare="${server}/${repo}/compare/${branch}...${side}?expand=1"
if gh pr create --repo "$repo" --base "$branch" --head "$side" \
     --title "Security report for ${tag} (${ts})" \
     --body "Adds security/reports/${name} from the verified release run. Push to ${branch} was rejected."; then
  echo "Opened a PR from ${side}."
else
  echo "::warning::Pushed ${side} but could not open a PR (the job needs pull-requests: write and the repo must allow GitHub Actions to create PRs). Open it here: ${compare}"
fi

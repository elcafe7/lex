#!/usr/bin/env bash
# Commit one release's security report folder to the default branch.
#
# Usage: commit_security_report.sh <artifact-dir>
#   <artifact-dir> holds exactly one folder <TAG>_<YYYYMMDDTHHMMSSZ>/ from
#   write_security_report.sh (the "security-report" workflow artifact).
# Env: TAG (validated release tag), DEFAULT_BRANCH, GH_TOKEN (GITHUB_TOKEN),
#      REPO (owner/name), SERVER_URL
#
# Runs from a checkout of the default branch. Never pushes to the default
# branch (it is protected by the "Protect main" ruleset: PR required). It
# copies the folder into security/reports/, rebuilds the index
# (update_security_index.sh), commits with [skip ci] on a new branch
# reports/<TAG>_<ts>, pushes that branch and opens a PR to the default branch
# with `gh pr create`. If the token cannot open PRs (repo setting "Allow GitHub
# Actions to create and approve pull requests" is off), it fails soft: the
# branch stays pushed, the workflow artifact is kept, and a notice gives the
# compare link to open the PR by hand.
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
side="reports/${name}"
compare="${server}/${repo}/compare/${branch}...${side}?expand=1"

if [ -n "$(git ls-remote --heads origin "refs/heads/${side}")" ]; then
  echo "::notice::Branch ${side} already exists (re-run?). Nothing pushed. Open or check the PR: ${compare}"
  exit 0
fi

git fetch -q origin "$branch"
git checkout -q -B "$side" "origin/${branch}"
mkdir -p security/reports
cp -R "$src_root/$name" "security/reports/${name}"
bash "$here/update_security_index.sh" security README.md
git add -- security README.md
git commit -q -m "$msg"
git push -q origin "HEAD:refs/heads/${side}"
echo "Pushed ${side}."

if gh pr create --repo "$repo" --base "$branch" --head "$side" \
     --title "Security report for ${tag} (${ts})" \
     --body "Adds security/reports/${name} from the verified release run (written by .github/workflows/release.yml). Merge to publish it in security/README.md and the README."; then
  echo "Opened a PR from ${side} to ${branch}."
else
  echo "::notice::Pushed ${side} but could not open a PR. GITHUB_TOKEN can only open PRs when the repo setting 'Allow GitHub Actions to create and approve pull requests' is on. The report is kept as the security-report workflow artifact. Open the PR by hand: ${compare}"
fi

#!/usr/bin/env bash
# Run Gitleaks over git history and gate on it. Output is always --redact'ed.
#
# Usage: gitleaks_check.sh <out-dir>
#   Writes <out-dir>/gitleaks.json (redacted findings list),
#   <out-dir>/gitleaks.sarif (redacted),
#   <out-dir>/gitleaks.md (issue-safe summary from scripts/gitleaks_gate.py) and
#   <out-dir>/gitleaks-gate.json (pass/fail and counts for the security report).
# Env:   GITLEAKS_LOG_OPTS  git log range for the scan: "--all" (default) or
#                           "<sha>..<sha>". Anything else is rejected.
#        TAG, REPO          optional; only label the summary, dropped if not plain
#
# Exit 0 = clean; 1 = findings or an incomplete scan; 2 = bad arguments.
# Gitleaks is installed by the workflow (CLI 8.30.1, checksum-verified) and
# must be on PATH. Config is the repo's .gitleaks.toml (default rules; allowlist
# only for proven false positives). There is no baseline file.
set -euo pipefail

out="${1:-}"
die() { echo "error: $*" >&2; exit 2; }
[ -n "$out" ] || die "usage: gitleaks_check.sh <out-dir>"
[[ "$out" =~ ^[A-Za-z0-9._/-]+$ ]] && [[ "$out" != -* ]] || die "invalid out-dir ${out@Q}"

opts="${GITLEAKS_LOG_OPTS:---all}"
if [[ "$opts" == "--all" ]]; then
  :
elif [[ "$opts" =~ ^[0-9a-f]{7,40}\.\.[0-9a-f]{7,40}$ ]]; then
  :
else
  die "invalid GITLEAKS_LOG_OPTS ${opts@Q} (must be --all or <sha>..<sha>)"
fi

tag="${TAG:-}"
if [[ -n "$tag" && ! "$tag" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "::warning title=Gitleaks::TAG is not a plain release tag; left out of the report" >&2
  tag=""
fi
repo="${REPO:-}"
if [[ -n "$repo" && ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "::warning title=Gitleaks::REPO is not owner/name; left out of the report" >&2
  repo=""
fi

command -v gitleaks >/dev/null || die "gitleaks is not installed"
version="$(gitleaks version 2>/dev/null | head -n 1 | tr -d '[:space:]')"
[[ "$version" =~ ^[0-9]+(\.[0-9]+)*$ ]] || version="?"

mkdir -p "$out"
rm -f "$out/gitleaks.json" "$out/gitleaks.sarif" "$out/gitleaks.md" "$out/gitleaks-gate.json"

# --redact is required: logs, JSON and SARIF must never contain secret values.
# Gitleaks exits 0 when clean, 1 when it finds something (--exit-code 1), and
# any other status is a crash. The SARIF run is best-effort and never gates.
set +e
gitleaks git --redact --no-banner --log-opts="$opts" \
  --report-format json --report-path "$out/gitleaks.json" --exit-code 1 .
rc=$?
gitleaks git --redact --no-banner --log-opts="$opts" \
  --report-format sarif --report-path "$out/gitleaks.sarif" --exit-code 0 . >/dev/null 2>&1
set -e
if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
  echo "::error title=Gitleaks::gitleaks exited with $rc (scan incomplete)"
fi

set +e
python3 scripts/gitleaks_gate.py "$out/gitleaks.json" "$out/gitleaks.md" \
  --tool-version "$version" \
  --summary-json "$out/gitleaks-gate.json" \
  ${tag:+--release "$tag"} \
  ${repo:+--repository "$repo"}
gate=$?
set -e
# A crashed scan must never count as clean, even if the JSON happened to be [].
if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ] && [ "$gate" -eq 0 ]; then gate=1; fi
exit "$gate"

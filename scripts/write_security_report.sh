#!/usr/bin/env bash
# Write one dated security report folder for a release run.
#
# Usage: write_security_report.sh <out-root>
#   Creates <out-root>/<tag>_<UTC YYYYMMDDTHHMMSSZ>/ and prints its name.
#
# Env (all optional except TAG, STATUS, REPO):
#   TAG                       release tag; must match ^[A-Za-z0-9._-]+$ and not
#                             start with "." or "-" (it becomes a folder name)
#   STATUS                    published | blocked
#   REPO, SERVER_URL, RUN_URL repository (owner/name), https://github.com, run link
#   DIST_DIR                  release files (SBOM, SHA256SUMS, OSV report, verification.json)
#   SCAN_DIR                  scan-report artifact (OSV report) for blocked runs
#   VT_DIR                    virustotal-report artifact (virustotal.md), if VT ran
#   ATTESTED                  "true" if provenance was attested
#   ATTESTATION_URL           attest-build-provenance attestation-url output
#   SCORECARD_FILE            JSON from api.scorecard.dev, if it was fetched
#   SOCKET_URL                repo var: Socket.dev page (https://socket.dev/...)
#   BESTPRACTICES_PROJECT_ID  repo var: bestpractices.dev project id (digits)
#   TS                        timestamp override for tests (YYYYMMDDTHHMMSSZ)
#
# Every value written into Markdown or a path is validated first; anything
# that fails validation is dropped (optional inputs) or stops the script
# (TAG, STATUS, REPO, TS). Nothing here is ever passed to eval or a shell.
set -euo pipefail

out_root="${1:-}"
tag="${TAG:-}"
status="${STATUS:-}"

die() { echo "error: $*" >&2; exit 1; }

if [[ ! "$tag" =~ ^[A-Za-z0-9._-]+$ ]] || [[ "$tag" == .* ]] || [[ "$tag" == -* ]]; then
  die "invalid tag ${tag@Q} (must match ^[A-Za-z0-9._-]+$ and not start with . or -)"
fi
case "$status" in published|blocked) ;; *) die "STATUS must be published or blocked, got ${status@Q}" ;; esac
[ -n "$out_root" ] || die "usage: write_security_report.sh <out-root>"

repo="${REPO:-}"
[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "invalid REPO ${repo@Q}"
server="${SERVER_URL:-https://github.com}"
[[ "$server" =~ ^https://[A-Za-z0-9.-]+$ ]] || die "invalid SERVER_URL ${server@Q}"
run_url="${RUN_URL:-}"
[[ -z "$run_url" || "$run_url" =~ ^https://[A-Za-z0-9.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+(/attempts/[0-9]+)?$ ]] \
  || die "invalid RUN_URL ${run_url@Q}"

ts="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
[[ "$ts" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || die "invalid TS ${ts@Q} (YYYYMMDDTHHMMSSZ)"
iso="${ts:0:4}-${ts:4:2}-${ts:6:2}T${ts:9:2}:${ts:11:2}:${ts:13:2}Z"
human="${ts:0:4}-${ts:4:2}-${ts:6:2} ${ts:9:2}:${ts:11:2}:${ts:13:2} UTC"

name="${tag}_${ts}"
dir="${out_root}/${name}"
[ ! -e "$dir" ] || die "report folder already exists: ${dir@Q}"
mkdir -p "$dir"

# First file in $1.. dirs matching a glob, or nothing.
first_match() {
  local pattern="$1" d f
  shift
  for d in "$@"; do
    [ -n "$d" ] && [ -d "$d" ] || continue
    for f in "$d"/$pattern; do
      [ -f "$f" ] && { printf '%s\n' "$f"; return 0; }
    done
  done
  return 0
}

dist="${DIST_DIR:-}"
scan="${SCAN_DIR:-}"
vt="${VT_DIR:-}"
rows=()   # summary table rows: tool|result|file
add_row() { rows+=("| $1 | $2 | $3 |"); }
link() { printf '[%s](%s)' "$1" "$1"; }

# --- OSV-Scanner ---------------------------------------------------------
osv_result="not run"
osv_json="$(first_match '*-osv-scan.json' "$dist" "$scan")"
osv_md="$(first_match '*-osv-scan.md' "$dist" "$scan")"
osv_files="-"
if [ -n "$osv_json" ] && jq -e . "$osv_json" >/dev/null 2>&1; then
  cp "$osv_json" "$dir/osv-scan.json"
  osv_files="$(link osv-scan.json)"
  count="$(jq '[.results[]?.packages[]?.vulnerabilities[]?] | length' "$osv_json")"
  [[ "$count" =~ ^[0-9]+$ ]] || count="?"
  verif="$(first_match 'verification.json' "$dist")"
  gate=""
  if [ -n "$verif" ]; then
    gate="$(jq -r '.result // empty' "$verif" 2>/dev/null || true)"
    cp "$verif" "$dir/verification.json"
  fi
  case "$gate" in
    pass) osv_result="pass (${count} advisories; 0 known vulnerabilities at or above the gate)" ;;
    fail) osv_result="FAIL (${count} advisories)" ;;
    *) if [ "$count" = "0" ]; then osv_result="pass (0 advisories)"; else osv_result="FINDINGS (${count} advisories)"; fi ;;
  esac
fi
if [ -n "$osv_md" ]; then
  cp "$osv_md" "$dir/osv-scan.md"
  osv_files="${osv_files}, $(link osv-scan.md)"
fi
add_row "OSV-Scanner" "$osv_result" "$osv_files"

# --- SBOM ----------------------------------------------------------------
sbom="$(first_match '*.cdx.json' "$dist")"
if [ -n "$sbom" ] && jq -e '.bomFormat == "CycloneDX"' "$sbom" >/dev/null 2>&1; then
  cp "$sbom" "$dir/sbom.cdx.json"
  comps="$(jq '[.components[]?] | length' "$sbom")"
  [[ "$comps" =~ ^[0-9]+$ ]] || comps="?"
  add_row "SBOM (CycloneDX, syft)" "written (${comps} components)" "$(link sbom.cdx.json)"
else
  add_row "SBOM (CycloneDX, syft)" "not produced" "-"
fi

# --- SHA256SUMS ----------------------------------------------------------
sums="$(first_match 'SHA256SUMS' "$dist")"
if [ -n "$sums" ]; then
  cp "$sums" "$dir/SHA256SUMS"
  n="$(grep -c . "$sums" || true)"
  if (cd "$(dirname "$sums")" && sha256sum -c --quiet SHA256SUMS >/dev/null 2>&1); then
    add_row "SHA256SUMS" "verified (${n} files)" "$(link SHA256SUMS)"
  else
    add_row "SHA256SUMS" "MISMATCH" "$(link SHA256SUMS)"
  fi
else
  add_row "SHA256SUMS" "not produced" "-"
fi

# --- Attestation ---------------------------------------------------------
att_url="${ATTESTATION_URL:-}"
[[ "$att_url" =~ ^https://[A-Za-z0-9.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/attestations/[0-9]+$ ]] || att_url=""
if [ "$status" = "published" ] && [ "${ATTESTED:-}" = "true" ]; then
  {
    echo "# Build provenance attestation"
    echo
    if [ -n "$att_url" ]; then echo "- Attestation: ${att_url}"; fi
    echo "- All attestations: ${server}/${repo}/attestations"
    echo "- Verify a download: \`gh attestation verify <file> -R ${repo}\`"
  } > "$dir/attestation.md"
  add_row "Build provenance (Sigstore)" "attested" "$(link attestation.md)"
elif [ "$status" = "published" ]; then
  add_row "Build provenance (Sigstore)" "not available (private repo)" "-"
else
  add_row "Build provenance (Sigstore)" "not run (blocked)" "-"
fi

# --- VirusTotal ----------------------------------------------------------
vt_md="$(first_match 'virustotal.md' "$vt")"
if [ -n "$vt_md" ]; then
  cp "$vt_md" "$dir/virustotal.md"
  grep -oE 'https://www\.virustotal\.com/gui/file/[0-9a-f]{64}' "$vt_md" | sort -u > "$dir/virustotal-links.txt" || true
  if grep -qE 'FLAGGED|NOT FINISHED' "$vt_md"; then vt_result="FLAGGED / not finished"
  elif grep -q 'suspicious (non-blocking)' "$vt_md"; then vt_result="clean (suspicious ratings listed, non-blocking)"
  else vt_result="clean"; fi
  add_row "VirusTotal" "$vt_result" "$(link virustotal.md), $(link virustotal-links.txt)"
else
  add_row "VirusTotal" "not enabled" "-"
fi

# --- OpenSSF Scorecard ---------------------------------------------------
sc="${SCORECARD_FILE:-}"
if [ -n "$sc" ] && [ -f "$sc" ] && jq -e '.score != null' "$sc" >/dev/null 2>&1; then
  cp "$sc" "$dir/scorecard.json"
  score="$(jq -r '.score' "$sc")"
  scdate="$(jq -r '.date // empty' "$sc")"
  [[ "$score" =~ ^[0-9]+(\.[0-9]+)?$ ]] || score="?"
  [[ "$scdate" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9:.]+Z?)?$ ]] || scdate=""
  add_row "OpenSSF Scorecard" "${score}/10${scdate:+ (published ${scdate})}" "$(link scorecard.json)"
else
  add_row "OpenSSF Scorecard" "not available" "-"
fi

# --- Socket.dev (repo var SOCKET_URL) --------------------------------------
socket="${SOCKET_URL:-}"
if [[ "$socket" =~ ^https://socket\.dev/[A-Za-z0-9._~/@%+-]*$ ]]; then
  printf '# Socket.dev\n\n- Project page: %s\n' "$socket" > "$dir/socket.md"
  add_row "Socket.dev" "configured (see page)" "$(link socket.md)"
else
  [ -z "$socket" ] || echo "::warning::SOCKET_URL is not a https://socket.dev/ URL; skipped" >&2
  add_row "Socket.dev" "not configured" "-"
fi

# --- OpenSSF Best Practices (repo var BESTPRACTICES_PROJECT_ID) -------------
bp="${BESTPRACTICES_PROJECT_ID:-}"
if [[ "$bp" =~ ^[0-9]{1,10}$ ]]; then
  printf '# OpenSSF Best Practices\n\n- Project page: https://www.bestpractices.dev/projects/%s\n- Badge: https://www.bestpractices.dev/projects/%s/badge\n' "$bp" "$bp" \
    > "$dir/openssf-best-practices.md"
  add_row "OpenSSF Best Practices" "configured (see page)" "$(link openssf-best-practices.md)"
else
  [ -z "$bp" ] || echo "::warning::BESTPRACTICES_PROJECT_ID is not numeric; skipped" >&2
  add_row "OpenSSF Best Practices" "not configured" "-"
fi

# --- summary.md + report.json ----------------------------------------------
if [ "$status" = "published" ]; then
  result="pass"
  headline="Published: every release check passed."
  release_url="${server}/${repo}/releases/tag/${tag}"
else
  result="blocked"
  headline="Blocked: a release check failed, so nothing was published."
  release_url=""
fi

{
  echo "# Security report: ${tag}"
  echo
  echo "- Date and time: ${human}"
  echo "- Result: **${result}**. ${headline}"
  [ -z "$release_url" ] || echo "- Release: ${release_url}"
  [ -z "$run_url" ] || echo "- Workflow run: ${run_url}"
  echo
  echo "| Tool | Result | Report |"
  echo "|---|---|---|"
  printf '%s\n' "${rows[@]}"
  echo
  echo "All times are UTC. Files in this folder are copies of what the workflow"
  echo "produced for this run; the OSV database keeps growing, so re-scan the SBOM"
  echo "(\`osv-scanner scan source -L sbom.cdx.json\`) for today's view."
} > "$dir/summary.md"

jq -n \
  --arg tag "$tag" --arg ts "$ts" --arg date "$iso" --arg status "$status" \
  --arg result "$result" --arg folder "reports/${name}" \
  --arg release_url "$release_url" --arg run_url "$run_url" \
  '{tag:$tag, timestamp:$ts, date_utc:$date, status:$status, result:$result,
    folder:$folder, summary:($folder + "/summary.md"),
    release_url:$release_url, run_url:$run_url}' > "$dir/report.json"

printf '%s\n' "$name"

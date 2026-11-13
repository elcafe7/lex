#!/usr/bin/env bash
# Rebuild security/README.md (index of every run, newest first) and
# security/latest.json from security/reports/*/report.json, refresh the
# "Security reports" block in the main README between the markers
#   <!-- security-reports:start --> and <!-- security-reports:end -->,
# copy the newest published VirusTotal report to
# security/reports/virustotal-latest.md, and refresh the README VirusTotal
# badge between <!-- virustotal-badge:start --> and <!-- virustotal-badge:end -->.
#
# Usage: update_security_index.sh [security-dir] [main-readme]
#        (defaults: security README.md)
#
# Fields read back from report.json are validated before they are written,
# so a hand-edited report cannot inject Markdown or HTML into the index.
set -euo pipefail

sec="${1:-security}"
readme="${2:-README.md}"
mkdir -p "$sec/reports"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

valid_entry() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] &&
  [[ "$2" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] &&
  [[ "$3" =~ ^(pass|blocked)$ ]]
}

: > "$tmp/rows"
for f in "$sec"/reports/*/report.json; do
  [ -f "$f" ] || continue
  folder="$(basename "$(dirname "$f")")"
  tag="$(jq -r '.tag // empty' "$f" 2>/dev/null || true)"
  ts="$(jq -r '.timestamp // empty' "$f" 2>/dev/null || true)"
  result="$(jq -r '.result // empty' "$f" 2>/dev/null || true)"
  if ! valid_entry "$tag" "$ts" "$result" || [ "$folder" != "${tag}_${ts}" ]; then
    echo "::warning::skipping malformed report folder ${folder@Q}" >&2
    continue
  fi
  printf '%s\t%s\t%s\t%s\n' "$ts" "$tag" "$result" "$folder" >> "$tmp/rows"
done
sort -r -o "$tmp/rows" "$tmp/rows"

human() { local t="$1"; printf '%s-%s-%s %s:%s:%s UTC' "${t:0:4}" "${t:4:2}" "${t:6:2}" "${t:9:2}" "${t:11:2}" "${t:13:2}"; }
iso() { local t="$1"; printf '%s-%s-%sT%s:%s:%sZ' "${t:0:4}" "${t:4:2}" "${t:6:2}" "${t:9:2}" "${t:11:2}" "${t:13:2}"; }

# security/README.md
{
  echo "# Security reports"
  echo
  echo "One folder per release run of \`.github/workflows/release.yml\`, newest first."
  echo "Each folder has a \`summary.md\` (every check, its result, date and time in UTC)"
  echo "and one file per check: OSV-Scanner report, Bandit report, SBOM, SHA256SUMS,"
  echo "attestation link, VirusTotal links (when enabled) and the OpenSSF Scorecard JSON."
  echo
  echo "The latest VirusTotal Markdown report is also copied to"
  echo "[\`reports/virustotal-latest.md\`](reports/virustotal-latest.md), which is"
  echo "what the README VirusTotal badge links to."
  echo
  echo "Only runs that published are committed here. A blocked run publishes nothing;"
  echo "its report stays a workflow artifact and the \"Release blocked\" issue has the findings."
  echo
  if [ -s "$tmp/rows" ]; then
    echo "| Date (UTC) | Release | Result | Report |"
    echo "|---|---|---|---|"
    while IFS=$'\t' read -r ts tag result folder; do
      echo "| $(human "$ts") | \`${tag}\` | ${result} | [summary](reports/${folder}/summary.md) |"
    done < "$tmp/rows"
  else
    echo "_No reports yet. The first verified release will add one here._"
  fi
  echo
  echo "Setup the maintainer does by hand (OpenSSF Best Practices, Socket.dev):"
  echo "[MANUAL-STEPS.md](MANUAL-STEPS.md)."
} > "$sec/README.md"

# security/latest.json and the README block
if [ -s "$tmp/rows" ]; then
  IFS=$'\t' read -r ts tag result folder < "$tmp/rows"
  jq -n --arg tag "$tag" --arg ts "$ts" --arg date "$(iso "$ts")" --arg result "$result" \
        --arg folder "reports/${folder}" \
    '{tag:$tag, timestamp:$ts, date_utc:$date, result:$result, folder:$folder,
      summary:($folder + "/summary.md")}' > "$sec/latest.json"
  block="Latest: \`${tag}\` on $(human "$ts"), result **${result}** ([summary](security/reports/${folder}/summary.md)). All runs: [security/README.md](security/README.md)."
else
  jq -n '{tag:null, timestamp:null, date_utc:null, result:"none", folder:null, summary:null,
          note:"No release has been verified by the workflow yet."}' > "$sec/latest.json"
  block="Latest: none yet. The first verified release adds its report here. All runs: [security/README.md](security/README.md)."
fi

if [ -f "$readme" ] && grep -q '^<!-- security-reports:start -->$' "$readme" \
   && grep -q '^<!-- security-reports:end -->$' "$readme"; then
  awk -v block="$block" '
    $0 == "<!-- security-reports:start -->" { print; print block; skip = 1; next }
    $0 == "<!-- security-reports:end -->"   { skip = 0 }
    !skip { print }
  ' "$readme" > "$tmp/readme"
  cat "$tmp/readme" > "$readme"
else
  echo "::warning::${readme} has no security-reports markers; README not updated" >&2
fi

# Stable VirusTotal report pointer + README badge. The badge href is always
# security/reports/virustotal-latest.md; this copies the newest published
# virustotal.md there (or a placeholder) after every clean-release index rebuild.
vt_row_re='^[|] [A-Za-z0-9._+-]+ [|] ([0-9]+|[?]) [|] ([0-9]+|[?]) [|] ([0-9]+|[?]) [|] (clean|suspicious [(]non-blocking[)]|FLAGGED|NOT FINISHED) [|] \[report\]\(https://www[.]virustotal[.]com/gui/file/[0-9a-f]{64}\) [|]$'
vt_src=""
vt_tag=""
vt_ts=""
if [ -s "$tmp/rows" ]; then
  while IFS=$'\t' read -r ts tag result folder; do
    f="$sec/reports/${folder}/virustotal.md"
    [ -f "$f" ] || continue
    if grep -Eq "$vt_row_re" "$f"; then
      vt_src="$f"
      vt_tag="$tag"
      vt_ts="$ts"
      break
    fi
  done < "$tmp/rows"
fi

latest_md="$sec/reports/virustotal-latest.md"
if [ -n "$vt_src" ]; then
  {
    echo "# VirusTotal (latest published scan)"
    echo
    echo "From the clean release of \`${vt_tag}\` on $(human "$vt_ts")"
    echo "([full report](${vt_tag}_${vt_ts}/virustotal.md)). The README"
    echo "VirusTotal badge always points at this file."
    echo
    cat "$vt_src"
  } > "$latest_md"
  vt_badge='[![VirusTotal](https://img.shields.io/badge/VirusTotal-clean-brightgreen)](security/reports/virustotal-latest.md)'
else
  {
    echo "# VirusTotal (latest published scan)"
    echo
    echo "No clean release has published a VirusTotal report yet. This file is"
    echo "updated automatically after every clean, VirusTotal-enabled release."
    echo "The README VirusTotal badge always points here."
  } > "$latest_md"
  vt_badge='[![VirusTotal](https://img.shields.io/badge/VirusTotal-pending-lightgrey)](security/reports/virustotal-latest.md)'
fi

if [ -f "$readme" ] && grep -q '^<!-- virustotal-badge:start -->$' "$readme" \
   && grep -q '^<!-- virustotal-badge:end -->$' "$readme"; then
  awk -v block="$vt_badge" '
    $0 == "<!-- virustotal-badge:start -->" { print; print block; skip = 1; next }
    $0 == "<!-- virustotal-badge:end -->"   { skip = 0 }
    !skip { print }
  ' "$readme" > "$tmp/readme-vt"
  cat "$tmp/readme-vt" > "$readme"
else
  echo "::warning::${readme} has no virustotal-badge markers; VirusTotal badge not updated" >&2
fi

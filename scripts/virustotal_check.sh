#!/usr/bin/env bash
# VirusTotal pre-publish check (optional; only runs when the repo variable
# ENABLE_VIRUSTOTAL is 'true' AND the VT_API_KEY secret is set).
#
# Usage: virustotal_check.sh <report.md> <file>...
#
# Uploads each file, waits for the analysis, and writes a Markdown report.
# Exits 1 (release blocked) if any engine flags a file as malicious, or if
# an analysis does not finish in time. "Suspicious" verdicts are listed and
# emitted as ::warning:: annotations but do not block on their own.
# Free public API: 4 requests/minute, 500/day; polling every 20 s stays under it.
set -euo pipefail

report="$1"
shift
api="https://www.virustotal.com/api/v3"
key="${VT_API_KEY:?VT_API_KEY is not set}"
status=0

{
  echo "# VirusTotal check"
  echo
  echo "| File | Malicious | Suspicious | Undetected | Result | Link |"
  echo "|---|---|---|---|---|---|"
} > "$report"

for f in "$@"; do
  name="$(basename "$f")"
  sha="$(sha256sum "$f" | awk '{print $1}')"
  link="https://www.virustotal.com/gui/file/${sha}"
  if [ "$(stat -c %s "$f")" -gt 33554432 ]; then
    # Files over 32 MB need a one-time upload URL.
    url="$(curl -fsS -H "x-apikey: ${key}" "${api}/files/upload_url" | jq -r .data)"
  else
    url="${api}/files"
  fi
  analysis="$(curl -fsS -H "x-apikey: ${key}" -F "file=@${f}" "$url" | jq -r .data.id)"
  stats=""
  for _ in $(seq 1 45); do
    sleep 20
    resp="$(curl -fsS -H "x-apikey: ${key}" "${api}/analyses/${analysis}")"
    if [ "$(jq -r .data.attributes.status <<<"$resp")" = "completed" ]; then
      stats="$(jq -c .data.attributes.stats <<<"$resp")"
      break
    fi
  done
  if [ -z "$stats" ]; then
    echo "| ${name} | ? | ? | ? | NOT FINISHED | [report](${link}) |" >> "$report"
    echo "::error title=VirusTotal::${name}: analysis did not finish in 15 minutes"
    status=1
    continue
  fi
  mal="$(jq -r '.malicious // 0' <<<"$stats")"
  sus="$(jq -r '.suspicious // 0' <<<"$stats")"
  und="$(jq -r '.undetected // 0' <<<"$stats")"
  result="clean"
  if [ "$mal" -gt 0 ]; then
    result="FLAGGED"
    status=1
    echo "::error title=VirusTotal::${name}: ${mal} engine(s) flagged it as malicious (${link})"
  elif [ "$sus" -gt 0 ]; then
    result="suspicious (non-blocking)"
    echo "::warning title=VirusTotal::${name}: ${sus} engine(s) rated it suspicious (${link})"
  fi
  echo "| ${name} | ${mal} | ${sus} | ${und} | ${result} | [report](${link}) |" >> "$report"
done

if [ "$status" -ne 0 ]; then
  {
    echo
    echo "## Suggested fix"
    echo
    echo "- Open each flagged report link and check which engines flagged the file and why."
    echo "- If it is a false positive, report it to those vendors (links on the VirusTotal page),"
    echo "  then re-run this workflow. If not, find and remove the cause before releasing."
    echo "- An analysis that did not finish only needs a re-run."
  } >> "$report"
fi
cat "$report"
exit "$status"

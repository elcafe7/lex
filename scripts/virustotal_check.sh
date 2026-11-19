#!/usr/bin/env bash
# VirusTotal pre-publish check (optional; runs when the repo variable
# ENABLE_VIRUSTOTAL is 'true'. If VT_API_KEY is then missing the workflow
# fails closed before calling this script, see virustotal_not_run.sh).
#
# Usage: virustotal_check.sh <report.md> <file>...
#
# Uploads each file, waits for the analysis, and writes a Markdown report.
# Exits 1 (release blocked) if any engine flags a file as malicious, if an
# analysis does not finish in time, or if the API daily/monthly quota is
# exhausted. "Suspicious" verdicts are listed and emitted as ::warning::
# annotations but do not block on their own.
#
# Free public API: 4 requests/minute, 500/day, 15,500/month. Every request
# (upload-URL lookup, upload, or poll) is paced at least 15s after the last
# one. HTTP 429 TooManyRequestsError / per-minute QuotaExceededError is
# retried with backoff. A daily or monthly quota exhaustion fails closed
# with a clear message instead of retrying until the job times out.
set -euo pipefail

report="${1:-}"
[ -n "$report" ] || { echo "usage: virustotal_check.sh <report.md> <file>..." >&2; exit 1; }
shift
if [ "$#" -eq 0 ]; then
  echo "::error title=VirusTotal::no files to scan"
  exit 1
fi
for f in "$@"; do
  [ -f "$f" ] || { echo "::error title=VirusTotal::file not found: ${f@Q}"; exit 1; }
done

api="https://www.virustotal.com/api/v3"
key="${VT_API_KEY:?VT_API_KEY is not set}"
min_interval="${VT_MIN_INTERVAL:-15}"
poll_interval="${VT_POLL_INTERVAL:-20}"
poll_max="${VT_POLL_MAX:-45}"
retry_max="${VT_RETRY_MAX:-8}"
quota_wait="${VT_QUOTA_WAIT:-60}"
direct_max="${VT_DIRECT_UPLOAD_MAX:-33554432}"
curl_cmd="${VT_CURL:-curl}"
sleep_cmd="${VT_SLEEP:-sleep}"

status=0
lookups=0
uploads=0
polls=0
retries=0
total=0
last_req_at=0
counts_written=0

vt_sleep() {
  local n="${1:-0}"
  [[ "$n" =~ ^[0-9]+$ ]] || return 0
  [ "$n" -gt 0 ] || return 0
  "$sleep_cmd" "$n"
}

now_s() { date +%s; }

pace() {
  local now elapsed wait
  now="$(now_s)"
  if [ "$last_req_at" -gt 0 ]; then
    elapsed=$((now - last_req_at))
    if [ "$elapsed" -lt "$min_interval" ]; then
      wait=$((min_interval - elapsed))
      vt_sleep "$wait"
    fi
  fi
}

# Classify a 429 body: rate | quota | unknown
classify_429() {
  local body="$1"
  local code msg msg_lc
  code="$(jq -r '.error.code // empty' <<<"$body" 2>/dev/null || true)"
  msg="$(jq -r '.error.message // empty' <<<"$body" 2>/dev/null || true)"
  msg_lc="$(printf '%s' "$msg" | tr '[:upper:]' '[:lower:]')"
  # The generic official wording names minute, daily and monthly together;
  # that is ambiguous and must not be treated as a hard daily/monthly fail.
  if printf '%s' "$msg_lc" | grep -Eq 'minute, daily or monthly|quotas \(minute'; then
    echo unknown
    return
  fi
  if printf '%s' "$msg_lc" | grep -Eq 'daily|monthly|per day|per month|15,500|15500'; then
    echo quota
    return
  fi
  if [ "$code" = "TooManyRequestsError" ]; then
    echo rate
    return
  fi
  if [ "$code" = "QuotaExceededError" ]; then
    if printf '%s' "$msg_lc" | grep -Eq 'minute|request rate|rate limit|per minute'; then
      echo rate
    else
      echo unknown
    fi
    return
  fi
  echo rate
}

write_counts() {
  [ "$counts_written" = 1 ] && return 0
  {
    echo
    echo "## API requests"
    echo
    echo "- lookups (upload URL): ${lookups}"
    echo "- uploads: ${uploads}"
    echo "- polls: ${polls}"
    echo "- retries (HTTP 429 or transient errors): ${retries}"
    echo "- total: ${total}"
  } >> "$report"
  counts_written=1
}

quota_fail() {
  local detail="$1"
  echo "::error title=VirusTotal::API quota exhausted (free-key daily 500 or monthly 15,500 request limit). ${detail} The release is blocked and nothing will be published. Wait for the quota to reset (daily at 00:00 UTC; monthly on the 1st at 00:00 UTC), then re-run."
  {
    echo
    echo "## Suggested fix"
    echo
    echo "- VirusTotal's free-key quota is exhausted (500 requests/day or 15,500/month)."
    echo "- Wait for the quota to reset (daily at 00:00 UTC; monthly on the 1st at 00:00 UTC), then re-run this workflow."
    echo "- Nothing was published."
  } >> "$report"
  write_counts
  cat "$report"
  exit 1
}

# vt_request <kind> <curl args...>
# kind is upload, lookup, or poll. Sets vt_body on success.
vt_request() {
  local kind="$1"
  shift
  local attempt=0
  local backoff="$min_interval"
  local saw_minute_wait=0
  local headers body code curl_rc class retry_after wait_s

  while :; do
    pace
    headers="$(mktemp)"
    body="$(mktemp)"
    set +e
    code="$("$curl_cmd" -sS -D "$headers" -o "$body" -w "%{http_code}" -H "x-apikey: ${key}" "$@")"
    curl_rc=$?
    set -e
    last_req_at="$(now_s)"
    total=$((total + 1))
    case "$kind" in
      upload) uploads=$((uploads + 1)) ;;
      lookup) lookups=$((lookups + 1)) ;;
      poll)   polls=$((polls + 1)) ;;
    esac

    if [ "$curl_rc" -eq 0 ] && { [ "$code" = "200" ] || [ "$code" = "201" ] || [ "$code" = "202" ]; }; then
      vt_body="$(cat "$body")"
      rm -f "$headers" "$body"
      return 0
    fi

    if [ "$curl_rc" -ne 0 ]; then
      echo "::warning title=VirusTotal::request failed (curl exit ${curl_rc}); retrying"
    elif [ "$code" = "429" ]; then
      class="$(classify_429 "$(cat "$body")")"
      retry_after="$(awk 'BEGIN{IGNORECASE=1} /^Retry-After:/ {print $2; exit}' "$headers" | tr -d '\r')"
      if [ "$class" = "quota" ]; then
        rm -f "$headers" "$body"
        quota_fail "The API returned HTTP 429 QuotaExceededError for a daily or monthly limit."
      fi
      # A Retry-After longer than five minutes on an ambiguous quota error
      # is almost certainly the daily/monthly window, not the per-minute cap.
      if [ "$class" = "unknown" ] && [[ "${retry_after:-}" =~ ^[0-9]+$ ]] && [ "$retry_after" -gt 300 ]; then
        rm -f "$headers" "$body"
        quota_fail "The API returned HTTP 429 with a Retry-After of ${retry_after}s, which is past the per-minute window."
      fi
      if [ "$class" = "unknown" ] && [ "$saw_minute_wait" = 1 ]; then
        rm -f "$headers" "$body"
        quota_fail "The API still returned HTTP 429 QuotaExceededError after waiting for the per-minute window to reset, so this is treated as a daily or monthly limit."
      fi
      if [ "$class" = "unknown" ] || [ "$class" = "rate" ]; then
        if [[ "${retry_after:-}" =~ ^[0-9]+$ ]] && [ "$retry_after" -le 300 ]; then
          wait_s="$retry_after"
        elif [ "$class" = "unknown" ]; then
          wait_s="$quota_wait"
          saw_minute_wait=1
        else
          wait_s="$backoff"
        fi
        if [ "$wait_s" -lt "$min_interval" ]; then
          wait_s="$min_interval"
        fi
        if [ "$wait_s" -ge 60 ]; then
          saw_minute_wait=1
        fi
        retries=$((retries + 1))
        attempt=$((attempt + 1))
        if [ "$attempt" -gt "$retry_max" ]; then
          rm -f "$headers" "$body"
          if [ "$class" = "unknown" ]; then
            quota_fail "The API kept returning HTTP 429 after ${retry_max} retries."
          fi
          echo "::error title=VirusTotal::rate-limited (HTTP 429) after ${retry_max} retries. The release is blocked and nothing will be published."
          write_counts
          cat "$report"
          exit 1
        fi
        echo "::warning title=VirusTotal::HTTP 429 (${class}); backing off ${wait_s}s and retrying"
        rm -f "$headers" "$body"
        vt_sleep "$wait_s"
        if [ "$backoff" -lt 60 ]; then
          backoff=$((backoff * 2))
          if [ "$backoff" -gt 60 ]; then backoff=60; fi
        fi
        continue
      fi
    elif [ "$code" = "503" ] || [ "$code" = "504" ]; then
      retries=$((retries + 1))
      attempt=$((attempt + 1))
      if [ "$attempt" -gt "$retry_max" ]; then
        echo "::error title=VirusTotal::HTTP ${code} after ${retry_max} retries. The release is blocked and nothing will be published."
        rm -f "$headers" "$body"
        write_counts
        cat "$report"
        exit 1
      fi
      echo "::warning title=VirusTotal::HTTP ${code}; backing off ${backoff}s and retrying"
      rm -f "$headers" "$body"
      vt_sleep "$backoff"
      if [ "$backoff" -lt 60 ]; then
        backoff=$((backoff * 2))
        if [ "$backoff" -gt 60 ]; then backoff=60; fi
      fi
      continue
    else
      echo "::error title=VirusTotal::API request failed (HTTP ${code:-n/a}). The release is blocked and nothing will be published."
      rm -f "$headers" "$body"
      write_counts
      cat "$report"
      exit 1
    fi

    retries=$((retries + 1))
    attempt=$((attempt + 1))
    if [ "$attempt" -gt "$retry_max" ]; then
      echo "::error title=VirusTotal::request failed after ${retry_max} retries. The release is blocked and nothing will be published."
      rm -f "$headers" "$body"
      write_counts
      cat "$report"
      exit 1
    fi
    rm -f "$headers" "$body"
    vt_sleep "$backoff"
  done
}

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
  if [ "$(stat -c %s "$f")" -gt "$direct_max" ]; then
    # Files over 32 MB need a one-time upload URL (a separate API request).
    vt_request lookup "${api}/files/upload_url"
    url="$(jq -r .data <<<"$vt_body")"
    if [ -z "$url" ] || [ "$url" = "null" ]; then
      echo "::error title=VirusTotal::${name}: could not get an upload URL"
      echo "| ${name} | ? | ? | ? | NOT FINISHED | [report](${link}) |" >> "$report"
      status=1
      continue
    fi
  else
    url="${api}/files"
  fi
  vt_request upload -F "file=@${f}" "$url"
  analysis="$(jq -r .data.id <<<"$vt_body")"
  if [ -z "$analysis" ] || [ "$analysis" = "null" ]; then
    echo "::error title=VirusTotal::${name}: upload did not return an analysis id"
    echo "| ${name} | ? | ? | ? | NOT FINISHED | [report](${link}) |" >> "$report"
    status=1
    continue
  fi
  stats=""
  for _ in $(seq 1 "$poll_max"); do
    vt_sleep "$poll_interval"
    vt_request poll "${api}/analyses/${analysis}"
    if [ "$(jq -r .data.attributes.status <<<"$vt_body")" = "completed" ]; then
      stats="$(jq -c .data.attributes.stats <<<"$vt_body")"
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
write_counts
cat "$report"
exit "$status"

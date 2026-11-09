# Security reports

One folder per release run of `.github/workflows/release.yml`, newest first.
Each folder has a `summary.md` (every check, its result, date and time in UTC)
and one file per check: OSV-Scanner report, SBOM, SHA256SUMS, attestation link,
VirusTotal links (when enabled) and the OpenSSF Scorecard JSON.

Only runs that published are committed here. A blocked run publishes nothing;
its report stays a workflow artifact and the "Release blocked" issue has the findings.

| Date (UTC) | Release | Result | Report |
|---|---|---|---|
| 2026-11-09 21:31:02 UTC | `v2.6.8` | pass | [summary](reports/v2.6.8_20261109T213102Z/summary.md) |

Setup the maintainer does by hand (OpenSSF Best Practices, Socket.dev):
[MANUAL-STEPS.md](MANUAL-STEPS.md).

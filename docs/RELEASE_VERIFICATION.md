# Release verification: maintainer notes

How releases of Lex are verified, and the repository settings the
release workflow assumes. Workflows: [`release.yml`](../.github/workflows/release.yml),
[`scorecard.yml`](../.github/workflows/scorecard.yml); Dependabot:
[`dependabot.yml`](../.github/dependabot.yml).

Release files keep their existing names: `lex-v<VERSION>.tar.gz` and
`lex-v<VERSION>.tar.gz.sha256` (what `@n8te_/lex-cli` downloads and checks)
are built by `scripts/build_npm_release.sh` exactly as before. The workflow
only adds files next to them. Because the tag must match the pyproject
version, a fix after a blocked release means a new patch version.

## What runs

- **Tag push (`v*`)**, in this order:
  1. **build-scan**: build, SBOM (syft, CycloneDX JSON), OSV-Scanner (pinned
     version, binary checked against a pinned SHA-256) and the severity gate
     (`scripts/osv_gate.py`), then `SHA256SUMS` written and verified.
  2. **virustotal** (optional, see below).
  3. **release**: re-checks `SHA256SUMS`, checks `verification.json` says
     pass / 0 known vulnerabilities, attests (actions/attest-build-provenance,
     plus an SBOM attestation) and publishes the release.
- **workflow_dispatch**: dry run of step 1. Files are kept as a 14-day
  workflow artifact. It never attests, publishes or opens issues.
- **Gate**: any advisory with CVSS 7.0 or higher fails the release. Scored
  advisories below 7.0 also hold it, so a published report and badge always
  say 0 known vulnerabilities. Advisories with no CVSS score don't block;
  each one is a `::warning::` annotation and is listed as "Unscored" in the
  report, the job summary and any blocked-release issue.
- **Permissions**: top-level `contents: read`. Only the release job gets
  `contents: write` (plus `id-token: write` and `attestations: write` for
  attestations, and `issues: write` to close a blocked-release issue). The
  blocked job gets `issues: write` only. Checkouts use
  `persist-credentials: false`. `github.ref_name` reaches shell steps only
  through `env`, never inline in `run:`.
- **Actions** are pinned to full commit SHAs with a `# vX.Y.Z` comment;
  Dependabot (`github-actions`, weekly) bumps both together.

## When a check fails: nothing is published

If the OSV gate, a checksum check or VirusTotal (when on) fails, the run
publishes **nothing**: no release, no release assets, no scan report on a
release and no `verification.json`. Instead:

- The findings stay in the run as workflow artifacts (`scan-report`,
  `virustotal-report`). Release files are not even uploaded as an artifact
  when the OSV scan fails.
- The job summary shows the findings, a **Suggested fix** (fixed versions
  from OSV where known) and a **Fix prompt** to paste into a PR or a coding
  agent. Unscored advisories are listed there too.
- The `blocked` job opens an issue titled
  **"Release blocked: &lt;tag&gt; security check failed"**, assigned to
  `elcafe7`, with the same findings and fix prompt. A later failed run on
  the same tag comments on that issue instead of opening a new one.
- Fix the findings, then release again: a new tag from the fixed commit,
  or a re-run when nothing in the repo has to change (for example a
  VirusTotal analysis that timed out). Only a fully clean run publishes, and
  that run closes the issue.

## VirusTotal (off by default)

The VirusTotal check runs before anything is published, only on a public
repo, on the files the release would publish (VirusTotal shares uploads with
its partners, so it never sees anything that isn't about to be public
anyway). It needs **both**:

- repository variable `ENABLE_VIRUSTOTAL` = `true` (turns it on)
- repository secret `VT_API_KEY` (Nate adds this himself)

| VirusTotal | `virustotal` job | Publish | Report says |
|---|---|---|---|
| Off (`ENABLE_VIRUSTOTAL` not `true`, or repo not public) | skipped | yes | "not enabled" |
| On, `VT_API_KEY` missing | **fails** (`::error::`, no secret printed) | **no**, "Release blocked" issue | "enabled but not run: VT_API_KEY secret missing (nothing scanned)" |
| On, every file clean (suspicious = warning) | success | yes | "clean, N files scanned" + permalinks |
| On, any engine says malicious, or an analysis doesn't finish in 15 min | fails | **no**, "Release blocked" issue | "FLAGGED / not finished" |

The report, release notes and job summary only call VirusTotal clean or
scanned when `virustotal.md` has real result rows; `verification.json` and
the README badge are OSV-only and never mention VirusTotal.

Free public API limits: 4 requests/minute, 500/day.

## Badge data (`verification.json`)

Each published release attaches `verification.json`, also covered by
`SHA256SUMS` and the provenance attestation. It is only written when the
scan is clean, so a published copy always says `"result": "pass"` and
`"known_vulnerabilities": 0` (`unscored` counts advisories with no CVSS
score, which are listed in the report):

```json
{
  "schema": 1,
  "tool": "OSV-Scanner",
  "tool_version": "2.7.0",
  "date": "2026-11-09",
  "scanned_at": "2026-11-09T17:00:00Z",
  "result": "pass",
  "known_vulnerabilities": 0,
  "unscored": 0,
  "threshold_cvss": 7.0,
  "report_url": "https://github.com/elcafe7/lex/releases/download/<tag>/<report>.md",
  "release": "<tag>",
  "repository": "elcafe7/lex",
  "stale_after_days": 30
}
```

A release's copy: `https://github.com/elcafe7/lex/releases/download/<tag>/verification.json`
(prefer the tag URL over `/releases/latest/`, which can point at a different
kind of release).
GitHub release downloads don't send CORS headers, so a download page should
copy this file at deploy time (or fetch it server-side). Browser-side
`fetch()` won't work.

Download-page copy:

- Within 30 days of `date`:
  **Verified by OSV-Scanner on &lt;date&gt; · 0 known vulnerabilities · [view report](report_url)**
  (for example "Verified by OSV-Scanner on Nov 9, 2026 · 0 known vulnerabilities · view report").
- After 30 days (`stale_after_days`): change "Verified by" to **"Last scanned by
  OSV-Scanner on &lt;date&gt;"**. The OSV database keeps growing, so an old
  scan is a dated record, not a current guarantee.
- Only show the badge when `result` is `pass` (always true for a published file).

Page wiring is deferred until the first verified release exists.

## Checking a release

```bash
sha256sum -c --ignore-missing SHA256SUMS          # Linux (macOS: shasum -a 256 -c --ignore-missing SHA256SUMS)
gh attestation verify <file> -R elcafe7/lex
osv-scanner scan source -L <sbom>.cdx.json        # re-scan against today's OSV data
```

## Security reports (committed to `security/`)

After a clean publish, the `security-report-commit` job commits
`security/reports/<tag>_<YYYYMMDDTHHMMSSZ>/` (UTC) with `[skip ci]` on a new
branch `reports/<tag>_<YYYYMMDDTHHMMSSZ>`, rebuilds `security/README.md` (all
runs, newest first), `security/latest.json` and the README "Security reports"
block on that branch, and opens a PR to the default branch. It never pushes to
the default branch (the "Protect main" ruleset requires a PR). Merging the PR
publishes the report in the index.

| File | From |
|---|---|
| `summary.md` | Every check, its result, the date and time (UTC), links to the files below |
| `osv-scan.json` / `osv-scan.md` | OSV-Scanner report (the release gate) |
| `sbom.cdx.json` | CycloneDX SBOM |
| `SHA256SUMS` | Checksums, re-verified when the report is written |
| `attestation.md` | Build-provenance attestation link and `gh attestation verify` command |
| `virustotal.md`, `virustotal-links.txt` | VirusTotal table and permalinks (only when VirusTotal is on) |
| `scorecard.json` | The latest published OpenSSF Scorecard result (api.scorecard.dev) |
| `socket.md`, `openssf-best-practices.md` | Only when `vars.SOCKET_URL` / `vars.BESTPRACTICES_PROJECT_ID` are set |
| `verification.json`, `report.json` | Badge data and the index entry |

How it is kept safe:

- The report is written by `scripts/write_security_report.sh` in the release
  job and handed to the commit job as the `security-report` artifact.
- `security-report-commit` needs `release`, runs only when it succeeded, and
  has `permissions: contents: write` (push the reports branch) and
  `pull-requests: write` (open the PR), nothing else. It checks out the
  default branch without stored credentials; `scripts/commit_security_report.sh`
  pushes with `GITHUB_TOKEN` through `gh auth setup-git`.
- Folder names come only from the allowlisted tag (`^[A-Za-z0-9._-]+$`, not
  starting with `.` or `-`) plus a generated UTC timestamp. No `${{ }}` value
  is expanded inside a `run:` script; everything is passed through `env:`.
  Release names and bodies are never read.
- `GITHUB_TOKEN` can only open the PR when **Settings > Actions > General >
  Allow GitHub Actions to create and approve pull requests** is on. If it is
  off, the job fails soft: the branch stays pushed, the `security-report`
  artifact is kept, and a notice in the run gives the compare link to open the
  PR by hand. (Turning the setting on is Nate's call; not changed here.)
- Blocked runs publish nothing and commit nothing: the `blocked` job writes
  the report and keeps it only as the `security-report-blocked` artifact.

OpenSSF Best Practices and Socket.dev need accounts the maintainer creates
by hand: [security/MANUAL-STEPS.md](../security/MANUAL-STEPS.md).

## Recommended repository settings (not applied; needs Nate's OK)

These are recommendations only. The PR that added this file changed no
settings.

1. **Tag ruleset for release tags.** Settings → Rules → Rulesets → New tag ruleset:
   - Name: `release tags`; Enforcement: Active
   - Target tags: include pattern `v*`
   - Rules: Restrict creations, Restrict updates, Restrict deletions, Block force pushes
   - Bypass list: only `elcafe7` (Nate), so only Nate can create or move
     release tags. This matters because the tag push alone triggers a signed,
     published release.
2. **Secret scanning**: Settings → Code security → Secret scanning: Enable.
3. **Push protection**: Settings → Code security → Secret scanning → Push protection: Enable.
4. **Actions secrets/variables**: add `VT_API_KEY` and `ENABLE_VIRUSTOTAL=true` only
   if VirusTotal is wanted (see above).


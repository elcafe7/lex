# Release verification: maintainer notes

How releases of Lex are verified, and the repository settings the
release workflow assumes. Workflows: [`release.yml`](../.github/workflows/release.yml),
[`scorecard.yml`](../.github/workflows/scorecard.yml); Dependabot:
[`dependabot.yml`](../.github/dependabot.yml).

Release files keep their existing names: `lex-v<VERSION>.tar.gz` and
`lex-v<VERSION>.tar.gz.sha256` (what `@n8te_/lex-cli` downloads and checks)
are built by `scripts/build_npm_release.sh` exactly as before. The workflow
only adds files next to them.

## What runs

- **Tag push (`v*`)**: build, SBOM (syft, CycloneDX JSON), OSV-Scanner
  (pinned version, binary checked against a pinned SHA-256), severity gate,
  `SHA256SUMS`, `verification.json`. The release job re-checks `SHA256SUMS`
  before it attests (actions/attest-build-provenance) and publishes.
- **workflow_dispatch**: dry run. Same build and scan, files kept as a
  14-day workflow artifact. Never attests, never publishes.
- **Gate**: the release fails on any advisory with CVSS 7.0 or higher.
  Advisories with no CVSS score do not block; each one shows up as a
  `::warning::` annotation on the run and is listed as "Unscored" in the report.
- **Permissions**: top-level `contents: read`; only the release job gets
  `contents: write` (plus `id-token: write` and `attestations: write` for
  attestations). Checkouts use `persist-credentials: false`. `github.ref_name`
  reaches shell steps only through `env`, never inline in `run:`.
- **Actions** are pinned to full commit SHAs with a `# vX.Y.Z` comment;
  Dependabot (`github-actions`, weekly) bumps both together.

## VirusTotal (off by default)

The VirusTotal upload runs only when **both** are set, and only on a public repo
(files that are published anyway; VirusTotal shares uploads with its partners):

- repository variable `ENABLE_VIRUSTOTAL` = `true`
- repository secret `VT_API_KEY` (Nate adds this himself)

Free public API limits: 4 requests/minute, 500/day.

## Badge data (`verification.json`)

Each release attaches `verification.json`, also covered by `SHA256SUMS`:

```json
{
  "schema": 1,
  "tool": "OSV-Scanner",
  "tool_version": "2.7.0",
  "date": "2026-11-09",
  "scanned_at": "2026-11-09T17:00:00Z",
  "result": "pass",
  "known_vulnerabilities": 0,
  "blocking": 0,
  "unscored": 0,
  "threshold_cvss": 7.0,
  "report_url": "https://github.com/elcafe7/lex/releases/download/<tag>/<report>.md",
  "release": "<tag>",
  "repository": "elcafe7/lex",
  "stale_after_days": 30
}
```

Latest release copy: `https://github.com/elcafe7/lex/releases/latest/download/verification.json`.
GitHub release downloads don't send CORS headers, so a download page should
copy this file at deploy time (or fetch it server-side). Browser-side
`fetch()` won't work.

Download-page copy:

- Within 30 days of `date`:
  **Verified by OSV-Scanner on &lt;date&gt; · &lt;known_vulnerabilities&gt; known vulnerabilities · [view report](report_url)**
  (for example "Verified by OSV-Scanner on Nov 9, 2026 · 0 known vulnerabilities · view report").
- After 30 days (`stale_after_days`): change "Verified by" to **"Last scanned by
  OSV-Scanner on &lt;date&gt;"**. The OSV database keeps growing, so an old
  scan is a dated record, not a current guarantee.
- Only show the badge when `result` is `pass`.

Page wiring is deferred until the first verified release exists.

## Checking a release

```bash
sha256sum -c --ignore-missing SHA256SUMS          # Linux (macOS: shasum -a 256 -c --ignore-missing SHA256SUMS)
gh attestation verify <file> -R elcafe7/lex
osv-scanner scan source -L <sbom>.cdx.json        # re-scan against today's OSV data
```

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


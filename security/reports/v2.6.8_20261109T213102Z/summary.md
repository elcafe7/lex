# Security report: v2.6.8

- Date and time: 2026-11-09 21:31:02 UTC
- Result: **pass**. Published: every release check passed.
- Release: https://github.com/elcafe7/lex/releases/tag/v2.6.8
- Workflow run: https://github.com/elcafe7/lex/actions/runs/42702865665

| Tool | Result | Report |
|---|---|---|
| OSV-Scanner | pass (0 advisories; 0 known vulnerabilities at or above the gate) | [osv-scan.json](osv-scan.json), [osv-scan.md](osv-scan.md) |
| SBOM (CycloneDX, syft) | written (27 components) | [sbom.cdx.json](sbom.cdx.json) |
| SHA256SUMS | verified (7 files) | [SHA256SUMS](SHA256SUMS) |
| Build provenance (Sigstore) | attested | [attestation.md](attestation.md) |
| VirusTotal | not enabled | - |
| OpenSSF Scorecard | not available | - |
| Socket.dev | not configured | - |
| OpenSSF Best Practices | not configured | - |

All times are UTC. Files in this folder are copies of what the workflow
produced for this run; the OSV database keeps growing, so re-scan the SBOM
(`osv-scanner scan source -L sbom.cdx.json`) for today's view.

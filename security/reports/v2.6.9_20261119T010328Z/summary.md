# Security report: v2.6.9

- Date and time: 2026-11-19 01:03:28 UTC
- Result: **pass**. Published: every release check passed.
- Release: https://github.com/elcafe7/lex/releases/tag/v2.6.9
- Workflow run: https://github.com/elcafe7/lex/actions/runs/44433231226

| Tool | Result | Report |
|---|---|---|
| OSV-Scanner | pass (0 advisories; 0 known vulnerabilities at or above the gate) | [osv-scan.json](osv-scan.json), [osv-scan.md](osv-scan.md) |
| Bandit (Python static analysis) | pass (0 medium/high findings; 116 low, information only; 8 inline nosec) | [bandit.json](bandit.json), [bandit.txt](bandit.txt), [bandit.md](bandit.md) |
| Gitleaks (secret scan) | pass (0 findings) | [gitleaks.json](gitleaks.json), [gitleaks.md](gitleaks.md), [gitleaks.sarif](gitleaks.sarif) |
| SBOM (CycloneDX, syft) | written (91 components) | [sbom.cdx.json](sbom.cdx.json) |
| SHA256SUMS | verified (7 files) | [SHA256SUMS](SHA256SUMS) |
| Build provenance (Sigstore) | attested | [attestation.md](attestation.md) |
| VirusTotal | clean, 1 file scanned | [virustotal.md](virustotal.md), [virustotal-links.txt](virustotal-links.txt) |
| OpenSSF Scorecard | not available | - |
| Socket.dev | not configured | - |
| OpenSSF Best Practices | not configured | - |

All times are UTC. Files in this folder are copies of what the workflow
produced for this run; the OSV database keeps growing, so re-scan the SBOM
(`osv-scanner scan source -L sbom.cdx.json`) for today's view.

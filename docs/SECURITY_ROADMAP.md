# Security Roadmap and Evidence Plan

This is the versioned implementation map for active security work. The
operational tracker is GitHub issue [#7](https://github.com/elcafe7/lex/issues/7).
It records automated assurance evidence, not a claim that an application is
certified or vulnerability-free.

## Current baseline

| Scope | Control | State | Evidence / remaining work |
|---|---|---|---|
| All public `elcafe7` repositories | GitHub secret scanning and push protection | Enabled | Monitor GitHub Security tab; no secrets were open at the baseline review. |
| All public `elcafe7` repositories | Dependabot alerts and security updates | Enabled | Review update pull requests and any alert introduced after the baseline. |
| Python public repositories, including Lex | GitHub CodeQL default setup | Enabled | Lex remediation is in progress; see [#6](https://github.com/elcafe7/lex/issues/6). |
| All public `elcafe7` repositories | Private vulnerability reporting | Enabled | Add a public `SECURITY.md` with a response commitment and supported versions. |
| Lex | Local static checks | In use | Bandit, Ruff, `pip-audit`, `py_compile`, and targeted regression checks; turn the reproducible checks into CI. |

## Open remediation work

| Priority | Scope | Work | Completion evidence |
|---|---|---|---|
| P0 | Lex | Resolve the remaining CodeQL path-handling alerts. | Final run URL, scanned SHA, and a per-alert fix or documented disposition in [#8](https://github.com/elcafe7/lex/issues/8) (runtime) and [#9](https://github.com/elcafe7/lex/issues/9) (developer scripts). |
| P0 | Lex | Add `SECURITY.md`. | Published policy, contact channel, supported-version policy, and disclosure acknowledgement target. |
| P1 | Public repositories | Add the same security policy and lightweight CI baseline where applicable. | Each repository’s `SECURITY.md` and successful workflow run. |
| P1 | Lex releases | Produce release evidence. | Release commit/tag, SHA-256 checksum, SBOM, provenance/attestation where supported, scanner report links, and documented exceptions. |
| P1 | Lex Web (private) | Define an authenticated test/staging target and explicit ZAP scope. | Written target authorization, exclusions, test account handling, dated ZAP report, and remediation issue links. |

## Planned tool integrations

Use the smallest complementary set. CodeQL remains the primary SAST engine;
SonarCloud is not planned unless a separate quality-gate need emerges.

| Order | Tool / control | Scope | Integration and pass condition |
|---|---|---|---|
| 1 | GitHub CodeQL | Supported public code repositories | Keep default setup enabled; review high/critical findings before release. Archive run URL and scanned SHA. |
| 2 | Dependabot | All public repositories | Keep alerts and security updates enabled; triage alerts/PRs with a documented reason when deferred. |
| 3 | Gitleaks | All public repositories | Add a pinned GitHub Action for push/PR scanning and a reviewed `.gitleaks.toml` baseline only for known historical false positives. Fail on new secrets. |
| 4 | OpenSSF Scorecard | All public repositories | Scheduled and default-branch workflow using a pinned action revision. Publish the JSON artifact and track material score regressions. |
| 5 | OSV-Scanner | Dependency-bearing public repositories | Scan lockfiles and manifests in CI; upload SARIF or retain the report artifact; triage findings alongside Dependabot. |
| 6 | SBOM generation | Release-producing repositories | Generate CycloneDX or SPDX SBOM at release; attach it and its SHA-256 to the release evidence. |
| 7 | GitHub artifact attestation | Eligible release artifacts | Attest release archives/build outputs and link the verification command from release notes. |
| 8 | OpenSSF Best Practices Badge | Mature public repositories | Complete the self-assessment only after the policy, CI, release, and disclosure evidence exists; publish its official badge link. |
| 9 | OWASP ZAP baseline/API scan | Lex Web only | Run against an explicitly authorized staging or test deployment, never an improvised production crawl; retain the dated HTML/JSON report and track findings. |
| 10 | Semgrep Community | Optional, after CodeQL baseline stabilizes | Add only if its rules cover a concrete gap; pin rules/action revision and avoid duplicate untriaged noise. |

## Evidence contract

For a status badge, README security section, or release claim, retain and link:

1. Repository and immutable commit SHA scanned.
2. Workflow run URL and pinned action/scanner version.
3. Policy/configuration revision and, when useful, its SHA-256.
4. Machine-readable report or immutable artifact link and checksum.
5. Finding counts plus the disposition of every high/critical result.
6. Scan date in UTC and the explicit scope (source, dependencies, release asset,
   or web target).

Use wording such as “automated checks completed; findings are tracked here.” Do
not use “secure,” “verified,” or equivalent certification language.

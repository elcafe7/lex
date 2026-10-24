# Lex Security Remediation Log

This ledger records security-relevant changes, their detection source, and
the verification performed. It is not a claim that Lex is free of defects.

| UTC date | Commit | Finding class | Remediation | Verification |
|---|---|---|---|---|
| 2026-10-24 | `7f89431` | CodeQL `py/polynomial-redos` | Replaced imported lexicon-markup regex processing with a linear parser. | `py_compile`; adversarial long-markup smoke check. |
| 2026-10-24 | `0dc3de6` | CodeQL `py/xml-bomb` | Replaced the standard XML parser in the Bible packager with `defusedxml`; declared the dependency. | Hostile entity-expansion payload rejected. |
| 2026-10-24 | `ecaec58` | Bandit `B310`; CodeQL path review | Restricted updater/manuscript fetches to an explicit HTTPS-host allowlist and validated split-database identifiers. | Hostile `http`, `file`, and untrusted-host URL smoke checks. |
| 2026-10-24 | `c6b1c6e` | CodeQL `py/polynomial-redos` | Replaced remaining runtime Strong's/history/RTF parsing hot paths and bounded reference input. | `py_compile`; targeted parser smoke checks. |
| 2026-10-24 | `1f909b5` | CodeQL `py/path-injection` | Restricted JSON reads to Lex data/cache roots and export opening to the Lex export directory. | `py_compile`; out-of-root read rejection check. |
| 2026-10-24 | `7a13c16` | CodeQL `py/polynomial-redos` | Rejected non-reference characters before applying reference parsing patterns. | `py_compile`; hostile-tab and valid-reference smoke checks. |
| 2026-10-24 | `b00f09e` | CodeQL `py/polynomial-redos` | Replaced reference and import-script backtracking regex parsing with bounded linear parsers. | `py_compile`; normal/compact reference, hostile-tab, markup, and word-list parsing assertions. GitHub CodeQL result pending. |

## Evidence rules

- Scanner results must identify the exact scanned commit SHA and scanner/action
  version before being presented as release evidence.
- High or critical findings require a documented disposition: fixed, accepted
  with rationale and owner, or false positive with evidence.
- Public status language must say “automated checks” rather than “verified
  secure.”

## Open follow-up

The remaining CodeQL path-handling review is tracked in GitHub issue
[#6](https://github.com/elcafe7/lex/issues/6). The concrete resolution issues
are [#8](https://github.com/elcafe7/lex/issues/8) for Lex runtime paths and
[#9](https://github.com/elcafe7/lex/issues/9) for developer-script paths. Each
completion record must link the final CodeQL run, scanned commit, per-alert
disposition, and validation.

The wider unfinished-work and compliance-tool plan is maintained in
[SECURITY_ROADMAP.md](SECURITY_ROADMAP.md) and tracked operationally in GitHub
issue [#7](https://github.com/elcafe7/lex/issues/7).

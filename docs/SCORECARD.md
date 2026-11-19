# OpenSSF Scorecard: status and accepted risks

[OpenSSF Scorecard](https://scorecard.dev/) runs weekly from
`.github/workflows/scorecard.yml`. Its findings appear in the
[Code scanning tab](https://github.com/elcafe7/lex/security/code-scanning?query=tool%3AScorecard)
and on the README badge. This page records the checks that a one-maintainer
project can't fully pass, and why. Tracking issue: #37.

## Branch-Protection (alert #59)

`main` is protected by the **Protect main** ruleset: changes must arrive by
pull request, force pushes and branch deletion are blocked, and nobody can
bypass it. Release tags (`v*`) can only be created by the owner.

**Token.** The Scorecard workflow uses a read-only fine-grained token,
`SCORECARD_TOKEN`, when that secret exists, and falls back to the default
`GITHUB_TOKEN` otherwise. The token lets Scorecard read every branch
protection setting, including classic protection rules that the default token
can't see. It is limited to this repository with **Administration: Read-only**
and **Metadata: Read-only**, and nothing else. Setup steps:
[security/MANUAL-STEPS.md](../security/MANUAL-STEPS.md#4-scorecard-token-for-branch-protection-optional).

**What still lowers the score.** The 2026-11 run scored Branch-Protection
3/10 and listed:

| Scorecard warning | Status |
|---|---|
| `main` does not require approvers | **Accepted.** There is one maintainer, and GitHub doesn't let an author approve their own PR. Requiring 1 approval would block every merge. |
| Code-owner review not required | **Accepted**, same reason. |
| "Last push approval" disabled | **Accepted**, same reason (it only applies when approvals are required). |
| Stale review dismissal disabled | Can be turned on in the ruleset at no cost. It does nothing until approvals are required. |
| No status checks required to merge | **Can be fixed.** Add required status checks (for example Bandit and Gitleaks) to the **Protect main** ruleset. |

The token alone won't raise the score to 10. Alert #59 stays open until the
fixable items are done in **Settings > Rules > Rulesets > Protect main**, and
it may stay open at a lower level because of the accepted approval items.

## Code-Review (alert #63): accepted risk

Scorecard's Code-Review check counts merged changes that someone *other than
the author* approved. Lex has a single maintainer (`elcafe7`), so it scores 0,
and it can't pass without a second reviewer account.

**Decision:** accepted as a documented solo-maintainer risk, not "fixed".

**Compensating controls** (each change still goes through them, even without a
second human reviewer):

- Every change to `main` goes through a pull request (ruleset; no bypass, no
  force push, no deletion).
- Automated checks on every PR: CodeQL, Bandit (blocking on medium/high)
  and the Gitleaks secret scan, plus Atheris fuzzing once #36 is merged.
- Release gates in `release.yml`: OSV-Scanner, Bandit, Gitleaks, optional
  VirusTotal, SHA256SUMS, SBOM and build-provenance attestation. A failing
  gate publishes nothing.
- Dependabot alerts and security updates, GitHub secret scanning and push
  protection.
- Pull requests drafted by automation are reviewed and merged by the
  maintainer by hand.

**Review again** if a second maintainer or a trusted reviewer account joins:
then require 1 approval (plus code-owner review and last-push approval) in the
ruleset, and this check and most of Branch-Protection can pass.

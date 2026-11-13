# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub, not in a public
issue, discussion or pull request:

1. Go to the [Security tab](https://github.com/elcafe7/lex/security) of this repository.
2. Click **Report a vulnerability**
   ([direct link](https://github.com/elcafe7/lex/security/advisories/new)).
3. Describe the problem, the affected version (`lex --version`), and steps or
   a proof of concept to reproduce it.

Only the maintainer and you can see the report. Please give us a chance to
fix the problem before you share details publicly.

## Supported versions

Only the latest 2.6.x release gets security fixes. Fixes ship as a new patch
release, not as changes to old ones.

| Version | Supported |
|---|---|
| Latest 2.6.x ([releases](https://github.com/elcafe7/lex/releases/latest)) | Yes |
| Older 2.6.x and earlier | No. Please upgrade (`lex --update`) |

This covers the Lex CLI in this repository and the `@n8te_/lex-cli` npm
launcher. Bible texts, lexicons and other bundled data aren't security
issues unless they can be used to run code or read or write files outside
Lex's own folders.

## What to expect

Lex is maintained by one volunteer, so these are goals, not guarantees:

- **Acknowledgement:** within 7 days.
- **First assessment** (whether it's a vulnerability and how severe): within 14 days.
- **Fix:** for confirmed high or critical issues, we aim to release a fix
  within 30 days. Lower-severity issues are fixed in a later release.
- **Disclosure:** once a fix is released, we publish a GitHub security
  advisory and credit you if you'd like.

## How releases are checked

Every release is scanned and attested before it's published. See
[docs/RELEASE_VERIFICATION.md](docs/RELEASE_VERIFICATION.md) for how to check
a download, and [security/README.md](security/README.md) for the report from
each release.

## Known limits

Lex has one maintainer, so pull requests can't be approved by a second
person. OpenSSF Scorecard's Code-Review check (and part of Branch-Protection)
can't pass for that reason. This is an accepted, documented risk with
compensating controls (protected `main`, required pull requests, automated
scans, release gates). See [docs/SCORECARD.md](docs/SCORECARD.md).

# Contributing to Lex

Thanks for helping. This covers the Lex CLI (`lex.py`), its scripts, and the
npm launcher in `npm/lex-cli`.

## Questions, bugs and ideas

Use the [GitHub issue tracker](https://github.com/elcafe7/lex/issues):

- **Bug:** [open an issue](https://github.com/elcafe7/lex/issues/new) and say
  what you did, what you expected, and what happened instead. Include your OS
  and the Lex version (`lex --version`).
- **Enhancement:** open an issue describing what you'd like and why.
- **Question:** open an issue; please search
  [existing issues](https://github.com/elcafe7/lex/issues?q=is%3Aissue) first.

**Security problems:** do not open a public issue. Report them privately by
following [SECURITY.md](SECURITY.md).

## Making a change

1. For anything bigger than a small fix, open an issue first so we can agree
   on the approach.
2. Fork the repository (or use a branch) from `main`.
3. Make your change, and add tests for new functionality.
4. Run the checks below.
5. Open a [pull request](https://github.com/elcafe7/lex/pulls) against `main`.
   Describe what changed and why, and link the issue it addresses. Draft pull
   requests are welcome.

`main` is protected and is pull-request only. Every change, including the
maintainer's, goes in through a pull request. The maintainer reviews each
pull request and may ask for changes before merging.

## Setting up

```sh
./setup.sh
# or: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

Python 3.12 or newer is required. For the npm launcher, Node.js 18 or newer.

## Checks to run before opening a pull request

```sh
python3 -m unittest discover -s tests
python3 -m py_compile ./lex.py
python3 ./lex.py --version
python3 ./lex.py read John 3:16
```

If you changed the npm launcher in `npm/lex-cli`:

```sh
(cd npm/lex-cli && npm test)
```

[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) and the
[Safe Change Checklist](docs/components/LEX_CLI.md#safe-change-checklist)
have a longer local verification list.

## Continuous integration

Every pull request and every push to `main` runs these GitHub Actions
workflows. They must pass before a pull request can be merged (where they are
required checks):

- **Bandit** (Python security analysis):
  [`.github/workflows/bandit.yml`](.github/workflows/bandit.yml). Medium or
  high findings fail the job. Low findings are reported. A proven false
  positive needs an inline `# nosec BXXX  # reason: ...` comment, explained
  in the pull request.
- **Gitleaks** (secret scanning):
  [`.github/workflows/gitleaks.yml`](.github/workflows/gitleaks.yml). Any
  finding fails the job. Proven false positives belong in `.gitleaks.toml`
  with a reason, reviewed in the pull request.
- **zizmor** (audit of GitHub Actions workflows):
  [`.github/workflows/zizmor.yml`](.github/workflows/zizmor.yml). Findings
  are uploaded to the repository's code scanning tab; the workflow uses
  SARIF output, which does not fail the job on findings.
- **Fuzz** (Atheris harnesses in `fuzz/`):
  [`.github/workflows/fuzz.yml`](.github/workflows/fuzz.yml). Runs on pull
  requests that touch the fuzzed code, on every push to `main`, weekly, and
  on demand. A crash, uncaught exception, or broken invariant fails the job.

[GitHub CodeQL default setup](https://github.com/elcafe7/lex/security/code-scanning)
is enabled for Python and GitHub Actions (default query suite, weekly
schedule).

The full unit test suite (`python3 -m unittest discover -s tests`) and the
npm tests (`npm test` in `npm/lex-cli`) are run locally, as above. They are
not currently a pull-request workflow. A few gate unit tests run inside the
Bandit, Gitleaks, and release workflows. The
[release workflow](.github/workflows/release.yml) also runs OSV-Scanner,
Bandit, Gitleaks, and (when configured) VirusTotal before a release is
published. [OpenSSF Scorecard](.github/workflows/scorecard.yml) runs on a
weekly schedule.

There is no project-wide Python linter (Ruff, flake8, pylint, or mypy)
configured in CI on `main`, so there is no general "treat compiler/linter
warnings as errors" rule to follow today. Bandit medium/high findings and
Gitleaks findings do fail CI.

## Requirements for contributions

- Python 3.12 or newer. Follow the style of the code around your change.
- The npm launcher's JavaScript files stay in `"use strict"` mode.
- Add or update automated tests for new features and bug fixes where
  practical. The Python suite is `python3 -m unittest discover -s tests`;
  the launcher suite is `npm test` in `npm/lex-cli`.
- Bandit must stay clean at medium and high severity. Do not add a `# nosec`
  comment without an explained reason.
- Do not commit credentials, API keys, or other secrets.
- Do not add runtime dependencies without discussing it in an issue first.
- Do not commit large databases or generated data that already has a
  published download path.
- Update the README or docs if you change how something is used.
- Keep each pull request to one topic.

## Sign-off and license

No Developer Certificate of Origin (DCO) sign-off and no contributor license
agreement are required. By opening a pull request you agree that your
contribution is licensed under the project's [MIT License](LICENSE).

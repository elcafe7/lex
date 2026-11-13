# Contributing to Lex

Thanks for helping. This covers the Lex CLI (lex.py), its scripts, and the npm launcher in npm/lex-cli.

## Questions, bugs and ideas

Use [GitHub Issues](https://github.com/elcafe7/lex/issues):

- **Bug:** [open an issue](https://github.com/elcafe7/lex/issues/new) and say what you did, what you
  expected, and what happened instead. Include your browser or OS and the
  version or release you're using.
- **Idea or enhancement:** open an issue describing what you'd like and why.
- **Question:** open an issue and add the `question` label. There's no
  separate forum.

Please search the [existing issues](https://github.com/elcafe7/lex/issues?q=is%3Aissue) first.

**Security problems:** don't open a public issue. Follow
[SECURITY.md](SECURITY.md) to report it privately.

## Making a change

1. For anything bigger than a small fix, open an issue first so we can agree
   on the approach.
2. Fork the repository and create a branch from `main`.
3. Make your change, with tests for any new behavior.
4. Run the checks below.
5. Open a [pull request](https://github.com/elcafe7/lex/pulls) against `main` and describe what changed
   and why. Link the issue it fixes. Draft pull requests are welcome.

`main` is protected. Every change, including the maintainer's own, goes in
through a pull request that passes the required checks. The maintainer
reviews each pull request and may ask for changes before merging.

## Setting up

```sh
./setup.sh                      # or: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

## Checks to run before opening a pull request

```sh
python3 -m unittest discover -s tests      # unit tests
ruff check .                               # lint (rules in pyproject.toml)
(cd npm/lex-cli && npm test)               # only if you touched the npm launcher
python3 ./lex.py read John 3:16            # quick smoke test
```
[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) has the longer verification list.

## Continuous integration

Every pull request runs these GitHub Actions checks, and they must pass before merging:

- **Lint (Ruff)**: [`.github/workflows/lint.yml`](.github/workflows/lint.yml)
- **Bandit** (Python security analysis): [`.github/workflows/bandit.yml`](.github/workflows/bandit.yml)
- **Gitleaks** (secret scanning): [`.github/workflows/gitleaks.yml`](.github/workflows/gitleaks.yml)
- **CodeQL** (GitHub code scanning)

The full unit test suite runs locally (above) and again before every release.

## Requirements for contributions

- Python 3.12 or newer. Follow the style of the code around your change.
- `ruff check .` must report nothing. If a finding is a false positive, add an
  inline `# noqa: XXXX  # reason: ...` comment and explain it in the PR.
- Bandit must stay clean at medium and high severity. Don't add a `# nosec`
  without an explained reason.
- The npm launcher's JavaScript files stay in `"use strict"` mode.
- Don't add runtime dependencies without discussing it in an issue first.
- Don't commit large databases, generated data, credentials or other secrets.
- Add or update tests for new features and bug fixes where practical.
- Update the README or docs if you change how something is used.
- Keep each pull request to one topic.

## Sign-off and license

No Developer Certificate of Origin (DCO) sign-off and no contributor license
agreement are needed. By opening a pull request you agree that your
contribution is licensed under the project's [MIT License](LICENSE).

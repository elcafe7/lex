# Manual steps (Nate, on your own device)

The release workflow already writes and commits a security report for every
clean release (see [README.md](README.md)). Two outside services need an
account that only you can create. Nothing here has been signed up for or
configured by an agent. Until you do these, the reports say "not configured"
for both, and the README badges stay commented out.

## 1. OpenSSF Best Practices badge (bestpractices.dev)

1. On your own device, go to <https://www.bestpractices.dev/en/projects/new>
   and sign in with GitHub as `elcafe7`.
2. Add the project `https://github.com/elcafe7/lex` and fill in the questionnaire
   (the release-verification docs answer most of the security questions).
3. Note the numeric project id from the project URL
   (`https://www.bestpractices.dev/projects/<ID>`).
4. In GitHub: **Settings > Secrets and variables > Actions > Variables >
   New repository variable**: `BESTPRACTICES_PROJECT_ID` = `<ID>` (digits only).
5. In the main README, uncomment the "OpenSSF Best Practices" badge line and
   replace `PROJECT_ID` with the id.

## 2. Socket.dev

1. On your own device, go to <https://socket.dev/> and sign in with GitHub as
   `elcafe7`.
2. Install the **Socket Security** GitHub app
   (<https://github.com/apps/socket-security>) and give it access to
   `elcafe7/lex` only.
3. Copy the Socket page for this repo (it starts with `https://socket.dev/`).
4. In GitHub: **Settings > Secrets and variables > Actions > Variables >
   New repository variable**: `SOCKET_URL` = that page.
5. In the main README, uncomment the "Socket" badge line and set its link to
   the same page.

## 3. Let the release workflow open report PRs (optional)

`main` is protected (PR required), so each clean release pushes a
`reports/<tag>_<timestamp>` branch and opens a PR with the report. GitHub only
lets the workflow open that PR when **Settings > Actions > General > Workflow
permissions > Allow GitHub Actions to create and approve pull requests** is
on. It is off now. If you leave it off, the run prints a notice with a link to
open the PR yourself, and the report stays a workflow artifact too.

## Checking it worked

The next clean release's `security/reports/<tag>_<timestamp>/summary.md`
lists both services as "configured" with links (`socket.md`,
`openssf-best-practices.md`). Bad values are skipped with a warning, never
written into the report.

## Other repo variables (already documented)

- `ENABLE_VIRUSTOTAL` = `true` plus the `VT_API_KEY` secret turns on the
  VirusTotal check and its links in the report. Add the secret first:
  `ENABLE_VIRUSTOTAL` = `true` without `VT_API_KEY` blocks every release.

## 4. Scorecard token for Branch-Protection (optional)

The Scorecard workflow uses a repo secret `SCORECARD_TOKEN` when it exists, so
it can read every branch protection setting (issue #37). Without it the
workflow still runs on the default token. The token is read-only and only
reaches this one repo. Create it yourself on your own device. Never paste the
value anywhere except the GitHub secret form below.

1. Open <https://github.com/settings/personal-access-tokens/new> (signed in
   as `elcafe7`).
2. **Token name:** `OpenSSF Scorecard - elcafe7/lex`.
   **Expiration:** Custom, one year from today (the maximum). GitHub emails
   you before it expires; repeat these steps then.
3. **Resource owner:** `elcafe7`. **Repository access:** *Only select
   repositories* > `elcafe7/lex`.
4. **Repository permissions:** set **Administration** to **Read-only**.
   **Metadata** switches to **Read-only** automatically. Leave every other
   permission at **No access**, and leave all account permissions at
   **No access**.
5. Click **Generate token** and copy it.
6. Open <https://github.com/elcafe7/lex/settings/secrets/actions/new>.
   **Name:** `SCORECARD_TOKEN`. **Secret:** paste the token. Click
   **Add secret**.
7. Run the Scorecard workflow once by hand: **Actions > Scorecard > Run
   workflow** on `main` (or wait for Monday's run).

To check: the run's "Run Scorecard" step passes, and the Branch-Protection
alert in Code scanning shows the newest details. To undo: delete the secret
and revoke the token at <https://github.com/settings/personal-access-tokens>.
The workflow then falls back to the default token.

What the token can and can't fix, and the accepted Code-Review risk:
[docs/SCORECARD.md](../docs/SCORECARD.md).

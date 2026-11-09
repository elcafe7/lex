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

## Checking it worked

The next clean release's `security/reports/<tag>_<timestamp>/summary.md`
lists both services as "configured" with links (`socket.md`,
`openssf-best-practices.md`). Bad values are skipped with a warning, never
written into the report.

## Other repo variables (already documented)

- `ENABLE_VIRUSTOTAL` = `true` plus the `VT_API_KEY` secret turns on the
  VirusTotal check and its links in the report.

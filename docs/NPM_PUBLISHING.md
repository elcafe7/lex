# Publishing `@n8te_/lex-cli` to npm

`lex-cli` is intentionally a small Node launcher. The Lex application and its
offline runtime data are distributed as a GitHub release archive instead of an
npm tarball.

## Release order

1. Set the same semantic version in `pyproject.toml` and
   `npm/lex-cli/package.json`, commit it, and tag it `v<VERSION>`.
2. Build the release archive from that commit:

   ```sh
   ./scripts/build_npm_release.sh
   ```

3. Create the matching GitHub release before publishing npm:

   ```sh
   gh release create "v<VERSION>" \
     "dist/lex-v<VERSION>.tar.gz" \
     "dist/lex-v<VERSION>.tar.gz.sha256" \
     --title "Lex v<VERSION>"
   ```

4. Validate and publish the small npm package:

   ```sh
   cd npm/lex-cli
   npm test
   npm pack --dry-run
   npm publish
   ```

The launcher downloads the release archive and its SHA-256 sidecar on first
execution. Do not publish the npm package before the corresponding GitHub
release assets are available.

## Release resolution

The launcher asks the GitHub API for the **latest** release (`releases/latest`)
on each first-run install and builds the asset URLs from that tag, so users
always get the newest `lex-v<TAG>.tar.gz` + `.sha256` pair. The `releaseTag` /
`assetName` values in `package.json` are a fallback used when the API lookup
fails (offline, rate-limited, private network).

Override for testing:

```sh
LEX_CLI_RELEASE_TAG=v2.6.7 lex        # force a specific tag
LEX_CLI_RELEASE_BASE_URL=... lex      # force a mirror URL
```

A cached install at `~/.local/share/lex-cli/` is reused; delete it to force a
re-download of the latest release.

## Self-update (`lex update`)

`lex update` / `lex --update` asks `registry.npmjs.org` for the `latest`
`@n8te_/lex-cli`. When the running launcher is older and lives in a writable
global npm prefix, it runs `npm install -g --prefix <prefix>
@n8te_/lex-cli@<latest>` and re-runs the command with the new launcher. After
you publish to npm, existing installs pick up the new launcher the next time
someone runs `lex update`. For testing, set `LEX_CLI_REGISTRY_URL` to use a
different registry, or `LEX_CLI_SKIP_SELF_UPDATE=1` to skip the CLI check.

# Publishing `lex-cli` to npm

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

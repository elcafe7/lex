# `@n8te_/lex-cli`

`@n8te_/lex-cli` is the npm launcher for [Lex](https://github.com/elcafe7/lex), the
local-first Bible study terminal.

```sh
npm install --global @n8te_/lex-cli
```

The first invocation downloads the latest Lex GitHub release archive, verifies
its SHA-256 sidecar, creates an isolated Python 3.12+ environment, and installs
Lex's Python dependencies. The npm package deliberately does not bundle Lex's
large offline runtime data.

## Verify

```sh
lex --version
lex help
```

## Try It

```sh
lex John 3:16
lex study John 1:1
lex search "kingdom of god"
lex strongs G3056
```

## Search

```sh
lex search covenant
lex search covenant --page 2
lex search covenant --page 3 --limit 20
lex search covenant -jeremiah
lex search resurrection -nt
```

Search runs against verse text. Use explicit scopes such as `-jeremiah`,
`-john`, `-nt`, `-major`, or `-pauline` when you want to narrow results.

## Strong's

```sh
lex strongs G3056
lex strongs G3056 --page 2 --limit 25
lex strongs G3056 --all
lex strongs love
lex strongs
```

Number lookups show the lexicon entry and, when available, reverse verse usage
from the bundled ESV interlinear index. The result footer prints commands for
the next page, more results per page, and all matches.

## Launcher Notes

For development, `LEX_CLI_HOME` may point to an existing valid Lex checkout.
Use `lex --npm-version` to report the launcher version without downloading the
release archive.

The launcher resolves the current GitHub release on first install and falls
back to its pinned release tag if that lookup is unavailable. Override it for
testing with:

```sh
LEX_CLI_RELEASE_TAG=v2.6.1 lex --version
LEX_CLI_RELEASE_BASE_URL=https://example.invalid/releases lex --version
```

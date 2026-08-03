# lex-cli

`lex-cli` is the npm launcher for [Lex](https://github.com/elcafe7/lex), the
local-first Bible study terminal.

```sh
npm install --global lex-cli
lex John 3:16
```

The first invocation downloads the pinned Lex GitHub release archive, verifies
its SHA-256 sidecar, creates an isolated Python 3.12+ environment, and installs
Lex's Python dependencies. The npm package deliberately does not bundle Lex's
large offline runtime data.

For development, `LEX_CLI_HOME` may point to an existing valid Lex checkout.
Use `lex --npm-version` to report the launcher version without downloading the
release archive.

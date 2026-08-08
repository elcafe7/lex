"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const launcher = require("../lib/launcher");

test("release URLs use the pinned GitHub release contract", () => {
  const urls = launcher.releaseUrls();
  assert.equal(urls.archive, "https://github.com/elcafe7/lex/releases/download/v2.5.0/lex-v2.5.0.tar.gz");
  assert.equal(urls.checksum, "https://github.com/elcafe7/lex/releases/download/v2.5.0/lex-v2.5.0.tar.gz.sha256");
  assert.equal(launcher.archiveRoot(), "lex-2.5.0");
});

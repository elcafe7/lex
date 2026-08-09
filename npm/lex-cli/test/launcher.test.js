"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const launcher = require("../lib/launcher");

test("release URLs use the pinned GitHub release contract", () => {
  const urls = launcher.releaseUrls();
  assert.equal(urls.archive, "https://github.com/elcafe7/lex/releases/download/v2.6.0/lex-v2.6.0.tar.gz");
  assert.equal(urls.checksum, "https://github.com/elcafe7/lex/releases/download/v2.6.0/lex-v2.6.0.tar.gz.sha256");
  assert.equal(launcher.archiveRoot(), "lex-2.6.0");
});

test("releaseUrls accepts an explicit tag", () => {
  const urls = launcher.releaseUrls("v2.5.1");
  assert.equal(urls.archive, "https://github.com/elcafe7/lex/releases/download/v2.5.1/lex-v2.5.1.tar.gz");
  assert.equal(urls.checksum, "https://github.com/elcafe7/lex/releases/download/v2.5.1/lex-v2.5.1.tar.gz.sha256");
});

test("resolveReleaseTag honors LEX_CLI_RELEASE_TAG override", async () => {
  process.env.LEX_CLI_RELEASE_TAG = "v2.5.1";
  try {
    const tag = await launcher.resolveReleaseTag();
    assert.equal(tag, "v2.5.1");
  } finally {
    delete process.env.LEX_CLI_RELEASE_TAG;
  }
});

test("resolveReleaseTag falls back to pinned tag when lookup fails", async () => {
  const https = require("node:https");
  const original = https.get;
  https.get = (url, options, cb) => {
    const fake = {
      statusCode: 403,
      resume() {},
      on(event, handler) { return fake; },
    };
    cb(fake);
    return fake;
  };
  try {
    const tag = await launcher.resolveReleaseTag();
    assert.equal(tag, "v2.6.0");
  } finally {
    https.get = original;
  }
});

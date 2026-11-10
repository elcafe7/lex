"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");
const launcher = require("../lib/launcher");

test("release URLs use the pinned GitHub release contract", () => {
  const urls = launcher.releaseUrls();
  assert.equal(urls.archive, "https://github.com/elcafe7/lex/releases/download/v2.6.8/lex-v2.6.8.tar.gz");
  assert.equal(urls.checksum, "https://github.com/elcafe7/lex/releases/download/v2.6.8/lex-v2.6.8.tar.gz.sha256");
  assert.equal(launcher.archiveRoot(), "lex-2.6.8");
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
    assert.equal(tag, "v2.6.8");
  } finally {
    https.get = original;
  }
});

test("venv python path matches the current platform", () => {
  const root = path.join(path.sep, "tmp", "lex");
  const python = launcher.pythonPath(root);
  if (process.platform === "win32") {
    assert.equal(python, path.join(root, ".venv", "Scripts", "python.exe"));
  } else {
    assert.equal(python, path.join(root, ".venv", "bin", "python"));
  }
});

test("archiveRoot follows a resolved release tag", () => {
  assert.equal(launcher.archiveRoot("v9.9.9"), "lex-9.9.9");
  assert.equal(launcher.archiveRoot("not-a-tag"), launcher.archiveRoot());
});

test("jsonModeRequested finds --json before the -- marker only", () => {
  assert.equal(launcher.jsonModeRequested(["--json", "John", "3:16"]), true);
  assert.equal(launcher.jsonModeRequested(["strongs", "G3056", "--json"]), true);
  assert.equal(launcher.jsonModeRequested(["John", "3:16"]), false);
  assert.equal(launcher.jsonModeRequested(["search", "--", "--json"]), false);
});

test("quiet mode keeps release-tag chatter off stderr", async () => {
  const lines = [];
  const original = console.error;
  console.error = (...parts) => lines.push(parts.join(" "));
  const https = require("node:https");
  const originalGet = https.get;
  https.get = (url, options, cb) => {
    const fake = { statusCode: 403, resume() {}, on() { return fake; } };
    cb(fake);
    return fake;
  };
  try {
    launcher.setQuiet(true);
    assert.equal(await launcher.resolveReleaseTag(), "v2.6.8");
    assert.deepEqual(lines, []);
    launcher.setQuiet(false);
    await launcher.resolveReleaseTag();
    assert.equal(lines.length, 1);
  } finally {
    launcher.setQuiet(false);
    console.error = original;
    https.get = originalGet;
    delete process.env.LEX_CLI_RELEASE_TAG;
  }
});

test("normalizeArgs maps known option names either dash style", () => {
  const cases = [
    [["--json", "John", "3:16"], ["--json", "John", "3:16"]],
    [["-json", "John", "3:16"], ["--json", "John", "3:16"]],
    [["-plain"], ["--plain"]],
    [["--h"], ["-h"]],
    [["-help"], ["--help"]],
    [["--help"], ["--help"]],
    [["-h"], ["-h"]],
    [["-version"], ["--version"]],
    [["--version"], ["--version"]],
    [["--v", "kjv"], ["-v", "kjv"]],
    [["-v", "kjv"], ["-v", "kjv"]],
    [["--B", "kjv"], ["-B", "kjv"]],
    [["--B=kjv"], ["-B=kjv"]],
    [["-bible", "kjv"], ["--bible", "kjv"]],
    [["--light"], ["-light"]],
    [["-light"], ["-light"]],
    [["-update"], ["--update"]],
    [["-npm-version"], ["--npm-version"]],
    [["-no-animate"], ["--no-animate"]],
    // skipped
    [["-Bkjv"], ["-Bkjv"]],
    [["-vkjv"], ["-vkjv"]],
    [["-1"], ["-1"]],
    [["-3:16"], ["-3:16"]],
    [["-nt"], ["-nt"]],
    [["search", "grace", "-nt", "-json"], ["search", "grace", "-nt", "--json"]],
    [["search", "--", "-json"], ["search", "--", "-json"]],
    [["-id"], ["-id"]],
  ];
  for (const [input, expected] of cases) {
    assert.deepEqual(launcher.normalizeArgs(input), expected, String(input));
  }
});

test("jsonModeRequested accepts -json as well as --json", () => {
  assert.equal(launcher.jsonModeRequested(["-json", "John", "3:16"]), true);
  assert.equal(launcher.jsonModeRequested(["search", "--", "-json"]), false);
});

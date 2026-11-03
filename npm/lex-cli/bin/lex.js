#!/usr/bin/env node

"use strict";

const { main, jsonModeRequested } = require("../lib/launcher");

const args = process.argv.slice(2);

main(args).catch((error) => {
  if (jsonModeRequested(args)) {
    // Same error shape as `lex --json` (docs/json-output.md); exit 4 = data/install problem.
    console.error(JSON.stringify({ schema_version: 1, error: { code: "launcher", message: error.message } }));
    process.exitCode = 4;
    return;
  }
  console.error(`lex: ${error.message}`);
  process.exitCode = 1;
});

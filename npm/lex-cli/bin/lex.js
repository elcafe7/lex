#!/usr/bin/env node

"use strict";

const { main } = require("../lib/launcher");

main(process.argv.slice(2)).catch((error) => {
  console.error(`lex: ${error.message}`);
  process.exitCode = 1;
});

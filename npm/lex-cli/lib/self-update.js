"use strict";

// Self-update for the npm launcher (#19).
//
// `lex --update` / `lex update` used to refresh only the runtime data, so an
// install whose launcher was 2.6.2 could pull 2.6.6 data and keep reporting
// 2.6.2. This module checks the npm registry for a newer @n8te_/lex-cli,
// upgrades a global npm install in place when it can, and otherwise prints
// the exact command to run instead of pretending the CLI is current.

const fs = require("node:fs");
const https = require("node:https");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const PACKAGE_NAME = "@n8te_/lex-cli";
const DEFAULT_REGISTRY = "https://registry.npmjs.org";

function isUpdateCommand(args) {
  return args.includes("--update") || args[0] === "update";
}

function parseVersion(version) {
  const match = String(version || "").trim().replace(/^v/, "").match(/^(\d+)\.(\d+)\.(\d+)/);
  return match ? match.slice(1).map(Number) : null;
}

// -1 if a < b, 0 if equal, 1 if a > b. Unparseable versions compare as equal
// so a malformed registry answer never triggers an install.
function compareVersions(a, b) {
  const left = parseVersion(a);
  const right = parseVersion(b);
  if (!left || !right) return 0;
  for (let i = 0; i < 3; i += 1) {
    if (left[i] !== right[i]) return left[i] < right[i] ? -1 : 1;
  }
  return 0;
}

function latestPublishedVersion({ registry, timeoutMs = 10000 } = {}) {
  const base = (registry || process.env.LEX_CLI_REGISTRY_URL || DEFAULT_REGISTRY).replace(/\/$/, "");
  const url = `${base}/${PACKAGE_NAME.replace("/", "%2f")}/latest`;
  return new Promise((resolve, reject) => {
    const request = https.get(url, {
      headers: { "User-Agent": "lex-cli", Accept: "application/json" },
    }, (response) => {
      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`npm registry lookup failed (${response.statusCode})`));
        return;
      }
      let body = "";
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try {
          const version = JSON.parse(body).version;
          // The version from the registry is passed to `npm install`; accept
          // only a plain X.Y.Z so it cannot carry a path, URL, or tag spec.
          if (typeof version !== "string" || !/^\d+\.\d+\.\d+$/.test(version)) {
            reject(new Error("npm registry response had no X.Y.Z version"));
          } else {
            resolve(version);
          }
        } catch (err) {
          reject(err);
        }
      });
    });
    request.setTimeout(timeoutMs, () => request.destroy(new Error("npm registry lookup timed out")));
    request.on("error", reject);
  });
}

// Work out how this launcher was installed from where its files live.
// A global npm install is <prefix>/lib/node_modules/@n8te_/lex-cli on POSIX
// and <prefix>\node_modules\@n8te_\lex-cli on Windows.
function detectInstall(packageDir, platform = process.platform) {
  const pathApi = platform === "win32" ? path.win32 : path.posix;
  const resolved = pathApi.resolve(packageDir);
  const parts = resolved.split(pathApi.sep);
  const n = parts.length;
  const isPackageDir = n >= 3 &&
    parts[n - 1] === "lex-cli" && parts[n - 2] === "@n8te_" && parts[n - 3] === "node_modules";
  if (!isPackageDir) {
    return { type: "unknown", packageDir: resolved, reason: `not an npm install (${resolved})` };
  }
  if (parts.includes("_npx")) {
    return { type: "npx", packageDir: resolved, reason: "running from the npx cache" };
  }
  const nodeModules = parts.slice(0, n - 2).join(pathApi.sep) || pathApi.sep;
  let prefix = null;
  if (platform === "win32") {
    prefix = pathApi.dirname(nodeModules);
  } else if (parts[n - 4] === "lib") {
    prefix = parts.slice(0, n - 4).join(pathApi.sep) || pathApi.sep;
  }
  if (!prefix) {
    return { type: "local", packageDir: resolved, nodeModules, reason: "installed in a project's node_modules, not globally" };
  }
  return { type: "npm-global", packageDir: resolved, nodeModules, prefix };
}

function npmCommand(platform = process.platform) {
  return platform === "win32" ? "npm.cmd" : "npm";
}

function defaultGlobalPrefix() {
  const result = spawnSync(npmCommand(), ["prefix", "-g"], { encoding: "utf8" });
  if (result.status !== 0 || !result.stdout) return null;
  return result.stdout.trim();
}

function quoteArg(value) {
  return /^[\w@%+=:,./~-]+$/.test(value) ? value : `"${value.replace(/(["\\$`])/g, "\\$1")}"`;
}

// The exact command a user should run to upgrade this install by hand.
function upgradeCommand(install, { globalPrefix } = {}) {
  const spec = `${PACKAGE_NAME}@latest`;
  if (install && install.type === "npm-global" && install.prefix &&
      (!globalPrefix || path.resolve(globalPrefix) !== path.resolve(install.prefix))) {
    return `npm install -g --prefix ${quoteArg(install.prefix)} ${spec}`;
  }
  return `npm install -g ${spec}`;
}

function canWrite(directory) {
  try {
    fs.accessSync(directory, fs.constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

function readInstalledVersion(packageDir) {
  try {
    return JSON.parse(fs.readFileSync(path.join(packageDir, "package.json"), "utf8")).version;
  } catch {
    return null;
  }
}

function runNpmInstall(install, version) {
  const args = ["install", "-g", "--prefix", install.prefix, `${PACKAGE_NAME}@${version}`];
  const result = spawnSync(npmCommand(), args, { stdio: ["ignore", "inherit", "inherit"] });
  if (result.error) return { ok: false, reason: result.error.message };
  if (result.status !== 0) return { ok: false, reason: `npm exited with status ${result.status}` };
  return { ok: true };
}

// Check for and, when possible, install a newer published launcher.
// Returns { status, currentVersion, latestVersion, installedVersion, command, reason }
// where status is one of:
//   "current"   - already the latest published version
//   "updated"   - upgraded in place; installedVersion is the new version
//   "failed"    - newer version exists but the upgrade did not happen
//   "unchecked" - could not reach the registry (offline, rate limited, ...)
async function selfUpdate({
  currentVersion,
  packageDir,
  platform = process.platform,
  fetchLatest = latestPublishedVersion,
  install: runInstall = runNpmInstall,
  writable = canWrite,
  globalPrefix = defaultGlobalPrefix,
  readVersion = readInstalledVersion,
  log = (line) => console.error(line),
} = {}) {
  const install = detectInstall(packageDir, platform);
  const prefixFor = () => (typeof globalPrefix === "function" ? globalPrefix() : globalPrefix);
  const base = { currentVersion, latestVersion: null, installedVersion: currentVersion, install };

  let latestVersion;
  try {
    latestVersion = await fetchLatest();
  } catch (err) {
    const command = upgradeCommand(install, { globalPrefix: install.type === "npm-global" ? prefixFor() : null });
    log(`lex: couldn't check npm for a newer CLI (${err.message}); CLI is still ${currentVersion}.`);
    log(`lex: to upgrade the CLI yourself, run: ${command}`);
    return { ...base, status: "unchecked", command, reason: err.message };
  }
  base.latestVersion = latestVersion;

  if (compareVersions(currentVersion, latestVersion) >= 0) {
    log(`lex: CLI ${currentVersion} is the latest published version.`);
    return { ...base, status: "current" };
  }

  const command = upgradeCommand(install, { globalPrefix: install.type === "npm-global" ? prefixFor() : null });
  const fail = (reason) => {
    log(`lex: CLI ${currentVersion} is behind the latest ${latestVersion} and was NOT updated (${reason}).`);
    log(`lex: to upgrade the CLI, run: ${command}`);
    return { ...base, status: "failed", command, reason };
  };

  if (install.type !== "npm-global") return fail(install.reason);
  if (!writable(install.nodeModules) || !writable(install.packageDir)) {
    return fail(`no write permission for ${install.nodeModules}`);
  }

  log(`lex: updating CLI ${currentVersion} → ${latestVersion} (npm, prefix ${install.prefix})…`);
  const result = runInstall(install, latestVersion);
  if (!result.ok) return fail(result.reason);
  const installedVersion = readVersion(install.packageDir);
  if (compareVersions(installedVersion, latestVersion) !== 0) {
    return fail(`npm finished but ${install.packageDir} reports ${installedVersion || "no version"}`);
  }
  log(`lex: CLI updated ${currentVersion} → ${installedVersion}.`);
  return { ...base, status: "updated", installedVersion };
}

module.exports = {
  PACKAGE_NAME,
  compareVersions,
  detectInstall,
  isUpdateCommand,
  latestPublishedVersion,
  readInstalledVersion,
  selfUpdate,
  upgradeCommand,
};

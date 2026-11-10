"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { pipeline } = require("node:stream/promises");

const metadata = require("../package.json");
const { isUpdateCommand, selfUpdate } = require("./self-update");
const config = metadata.lexCli;

// `lex --json ...` must keep stdout for the JSON document and stderr for a
// JSON error, so launcher chatter and child install output are silenced.
let quiet = false;

// Canonical option forms. Long names may map to --name or a single-dash
// form already registered in lex.py (`-light`). Keep in sync with
// lex.py's build_arg_parser(). `--npm-version` is launcher-only.
const LONG_OPTIONS = {
  interlinear: "--interlinear",
  define: "--define",
  creed: "--creed",
  strongs: "--strongs",
  version: "--version",
  bible: "--bible",
  update: "--update",
  light: "-light",
  dark: "-dark",
  auto: "-auto",
  credits: "--credits",
  next: "--next",
  prev: "--prev",
  page: "--page",
  limit: "--limit",
  all: "--all",
  mode: "--mode",
  format: "--format",
  ratio: "--ratio",
  animate: "--animate",
  "no-animate": "--no-animate",
  json: "--json",
  plain: "--plain",
  clear: "--clear",
  help: "--help",
  "npm-version": "--npm-version",
};

const SHORT_OPTIONS = {
  i: "-i",
  d: "-d",
  c: "-c",
  s: "-s",
  v: "-v",
  B: "-B",
  h: "-h",
};

// Negative numbers and numeric-looking tokens: -1, -16, -3:16, -1-2.
const NUMERIC_DASH_TOKEN = /^-\d+(?::\d+)?(?:-\d+)?$/;

function normalizeArgs(args) {
  const out = [];
  for (let i = 0; i < args.length; i += 1) {
    const token = args[i];
    if (token === "--") {
      out.push(...args.slice(i));
      break;
    }
    if (token === "-" || !token.startsWith("-") || NUMERIC_DASH_TOKEN.test(token)) {
      out.push(token);
      continue;
    }
    const body = token.startsWith("--") ? token.slice(2) : token.slice(1);
    const eq = body.indexOf("=");
    const name = eq === -1 ? body : body.slice(0, eq);
    const suffix = eq === -1 ? "" : body.slice(eq);
    if (Object.prototype.hasOwnProperty.call(LONG_OPTIONS, name)) {
      out.push(LONG_OPTIONS[name] + suffix);
    } else if (name.length === 1 && Object.prototype.hasOwnProperty.call(SHORT_OPTIONS, name)) {
      out.push(SHORT_OPTIONS[name] + suffix);
    } else {
      // Skipped: attached short values (-Bkjv, -vkjv), search scopes
      // (-nt, -ot), unknown tokens, combined shorts (-id).
      out.push(token);
    }
  }
  return out;
}

function jsonModeRequested(args) {
  for (const arg of normalizeArgs(args)) {
    if (arg === "--") return false;
    if (arg === "--json") return true;
  }
  return false;
}

function setQuiet(value) {
  quiet = Boolean(value);
}

function note(message) {
  if (!quiet) console.error(message);
}

// Release tags come from the GitHub API or the environment. Only plain
// vX.Y.Z tags are accepted, so a tag can never add path segments to a URL or
// to the archive root used during extraction.
const RELEASE_TAG = /^v\d+\.\d+\.\d+$/;

function validReleaseTag(tag) {
  return typeof tag === "string" && RELEASE_TAG.test(tag);
}

function releaseBaseUrl(tag) {
  const releaseTag = tag || config.releaseTag;
  return process.env.LEX_CLI_RELEASE_BASE_URL ||
    `https://github.com/${config.repository}/releases/download/${releaseTag}`;
}

function assetNames(tag) {
  if (tag && !config.assetName.includes(tag)) {
    return {
      assetName: `lex-${tag}.tar.gz`,
      checksumName: `lex-${tag}.tar.gz.sha256`,
    };
  }
  return { assetName: config.assetName, checksumName: config.checksumName };
}

function releaseUrls(tag) {
  const base = releaseBaseUrl(tag).replace(/\/$/, "");
  const names = assetNames(tag);
  return {
    archive: `${base}/${names.assetName}`,
    checksum: `${base}/${names.checksumName}`,
  };
}

function installRoot() {
  const dataHome = process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local", "share");
  return path.join(dataHome, "lex-cli", metadata.version);
}

function archiveRoot(tag) {
  // Release archives are rooted at lex-<version>/ for the tag they were cut
  // from. When the launcher resolves a newer release than its own version,
  // extract from that tag's root instead of the launcher's.
  if (tag && /^v\d+\.\d+\.\d+$/.test(tag)) return `lex-${tag.slice(1)}`;
  return `lex-${metadata.version}`;
}

function latestReleaseTag() {
  const apiUrl = `https://api.github.com/repos/${config.repository}/releases/latest`;
  return new Promise((resolve, reject) => {
    https.get(apiUrl, {
      headers: {
        "User-Agent": "lex-cli",
        Accept: "application/vnd.github+json",
      },
    }, (response) => {
      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`latest-release lookup failed (${response.statusCode})`));
        return;
      }
      let body = "";
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try {
          const tag = JSON.parse(body).tag_name;
          if (!tag) reject(new Error("latest release response had no tag_name"));
          else if (!validReleaseTag(tag)) reject(new Error("latest release tag_name is not a vX.Y.Z tag"));
          else resolve(tag);
        } catch (err) {
          reject(err);
        }
      });
    }).on("error", reject);
  });
}

async function resolveReleaseTag() {
  const override = process.env.LEX_CLI_RELEASE_TAG;
  if (override) {
    if (validReleaseTag(override)) return override;
    note(`lex: ignoring LEX_CLI_RELEASE_TAG (not a vX.Y.Z tag), using pinned ${config.releaseTag}`);
    return config.releaseTag;
  }
  try {
    const tag = await latestReleaseTag();
    note(`lex: latest release is ${tag}`);
    return tag;
  } catch (err) {
    note(`lex: couldn't resolve latest release, using pinned ${config.releaseTag} (${err.message})`);
    return config.releaseTag;
  }
}

function sha256(file) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const input = fs.createReadStream(file);
    input.on("error", reject);
    input.on("data", (chunk) => hash.update(chunk));
    input.on("end", () => resolve(hash.digest("hex")));
  });
}

function get(url, redirects = 0) {
  if (redirects > 5) {
    return Promise.reject(new Error("too many redirects while downloading release asset"));
  }
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "lex-cli" } }, (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        response.resume();
        resolve(get(new URL(response.headers.location, url).toString(), redirects + 1));
        return;
      }
      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`release download failed (${response.statusCode}) for ${url}`));
        return;
      }
      resolve(response);
    }).on("error", reject);
  });
}

async function download(url, target) {
  const response = await get(url);
  await pipeline(response, fs.createWriteStream(target, { mode: 0o600 }));
}

async function expectedChecksum(url) {
  const response = await get(url);
  const chunks = [];
  for await (const chunk of response) chunks.push(chunk);
  const match = Buffer.concat(chunks).toString("utf8").match(/\b[a-fA-F0-9]{64}\b/);
  if (!match) throw new Error("release checksum asset did not contain a SHA-256 digest");
  return match[0].toLowerCase();
}

function checked(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: quiet ? "ignore" : "inherit", ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} exited with status ${result.status}`);
}

// --- Zip-slip guard for the downloaded release archive -----------------------
// The archive is checksum-verified, but the checksum comes from the same
// release, so its contents are still treated as untrusted. Every entry must be
// a regular file or directory under the expected lex-<version>/ root.

const ENCODED_TRAVERSAL = /%(?:2e|2f|5c|00)/i;

function archiveEntryProblem(name, root) {
  if (typeof name !== "string" || name.length === 0) return "empty entry name";
  if (name.includes("\0")) return "NUL byte in entry name";
  if (ENCODED_TRAVERSAL.test(name)) return "encoded traversal in entry name";
  if (name.startsWith("/") || name.startsWith("\\") || /^[A-Za-z]:/.test(name)) return "absolute entry path";
  const segments = name.split(/[\\/]+/);
  if (segments.includes("..")) return "parent-directory segment in entry";
  const trimmed = name.replace(/^\.\//, "");
  if (trimmed !== root && trimmed !== `${root}/` && !trimmed.startsWith(`${root}/`)) {
    return `entry outside ${root}/`;
  }
  return null;
}

// `tar -tv` prints an ls-style mode string; its first character is the entry
// type for both GNU tar and bsdtar. Only regular files and directories pass.
function archiveTypeProblem(verboseLine) {
  const type = verboseLine.charAt(0);
  if (type !== "-" && type !== "d") return `unsupported entry type '${type}'`;
  if (/ (?:->|link to) /.test(verboseLine)) return "link entry";
  return null;
}

function listArchive(archive, verbose) {
  const result = spawnSync("tar", [verbose ? "-tvzf" : "-tzf", archive], {
    encoding: "utf8",
    maxBuffer: 256 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`tar listing exited with status ${result.status}`);
  return result.stdout.split("\n").filter((line) => line.length > 0);
}

function verifyArchiveEntries(archive, root) {
  const names = listArchive(archive, false);
  const details = listArchive(archive, true);
  if (names.length === 0) throw new Error("release archive is empty");
  if (names.length !== details.length) throw new Error("release archive listing is inconsistent");
  names.forEach((name, index) => {
    const problem = archiveEntryProblem(name, root) || archiveTypeProblem(details[index]);
    if (problem) throw new Error(`unsafe release archive entry ${JSON.stringify(name)}: ${problem}`);
  });
}

// Second line of defence after extraction: nothing may be a symlink and every
// path must still resolve inside the extraction directory.
function verifyExtractedTree(extraction) {
  const base = fs.realpathSync(extraction);
  const prefix = base.endsWith(path.sep) ? base : base + path.sep;
  const pending = [base];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      const stat = fs.lstatSync(full);
      if (stat.isSymbolicLink()) throw new Error(`release archive contains a symlink: ${path.relative(base, full)}`);
      if (!fs.realpathSync(full).startsWith(prefix)) throw new Error(`release archive entry escapes extraction: ${entry.name}`);
      if (stat.isDirectory()) pending.push(full);
      else if (!stat.isFile()) throw new Error(`release archive contains a special file: ${path.relative(base, full)}`);
    }
  }
}

function validLexHome(directory) {
  return fs.existsSync(path.join(directory, "lex.py")) &&
    fs.existsSync(path.join(directory, "requirements.txt")) &&
    fs.existsSync(path.join(directory, "runtime-data", "lexicon.db"));
}

function pythonPath(directory) {
  return process.platform === "win32"
    ? path.join(directory, ".venv", "Scripts", "python.exe")
    : path.join(directory, ".venv", "bin", "python");
}

function dependenciesInstalled(directory) {
  if (!fs.existsSync(pythonPath(directory))) return false;
  const result = spawnSync(
    pythonPath(directory),
    ["-c", "import rich, docx, reportlab, pptx, PIL"],
    { cwd: directory, stdio: "ignore" }
  );
  return result.status === 0;
}

function bootstrap(directory) {
  const venvPath = path.join(directory, ".venv");
  if (!fs.existsSync(pythonPath(directory))) {
    checked("python3", ["-c", "import sys; raise SystemExit(sys.version_info < (3, 12))"]);
    checked("python3", ["-m", "venv", venvPath]);
  }
  if (dependenciesInstalled(directory)) return;
  checked("python3", ["-c", "import sys; raise SystemExit(sys.version_info < (3, 12))"]);
  checked(pythonPath(directory), ["-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"], { cwd: directory });
}

async function downloadRelease(tag) {
  const destination = installRoot();
  if (validLexHome(destination)) return destination;

  const temporary = await fsp.mkdtemp(path.join(os.tmpdir(), "lex-cli-"));
  try {
    const urls = releaseUrls(tag);
    const archive = path.join(temporary, config.assetName);
    note(`lex: downloading ${config.releaseTag} release data…`);
    const [expected] = await Promise.all([expectedChecksum(urls.checksum), download(urls.archive, archive)]);
    const actual = await sha256(archive);
    if (actual !== expected) throw new Error("release archive checksum mismatch");
    const extraction = path.join(temporary, "extracted");
    await fsp.mkdir(extraction);
    const root = archiveRoot(tag);
    verifyArchiveEntries(archive, root);
    checked("tar", ["-xzf", archive, "-C", extraction, "--no-same-owner"]);
    verifyExtractedTree(extraction);
    const source = path.join(extraction, root);
    if (!validLexHome(source)) throw new Error("release archive does not contain a valid Lex distribution");
    await fsp.mkdir(path.dirname(destination), { recursive: true, mode: 0o700 });
    try {
      await fsp.rename(source, destination);
    } catch (error) {
      if (error && ["EEXIST", "ENOTEMPTY"].includes(error.code) && validLexHome(destination)) {
        return destination;
      }
      throw error;
    }
    return destination;
  } finally {
    await fsp.rm(temporary, { recursive: true, force: true });
  }
}

async function resolveLexHome() {
  const override = process.env.LEX_CLI_HOME;
  if (override) {
    if (!validLexHome(override)) throw new Error(`LEX_CLI_HOME is not a valid Lex distribution: ${override}`);
    return override;
  }
  const tag = await resolveReleaseTag();
  return downloadRelease(tag);
}

async function main(args) {
  args = normalizeArgs(args);
  setQuiet(jsonModeRequested(args));
  if (args.length === 1 && args[0] === "--npm-version") {
    console.log(metadata.version);
    return;
  }
  const env = { ...process.env, LEX_CLI_PACKAGE_VERSION: metadata.version };
  if (process.env.LEX_CLI_UPDATED_FROM) {
    // Re-run by an older launcher right after it upgraded this one.
    env.LEX_CLI_UPDATE_STATUS = "updated";
    env.LEX_CLI_LATEST_VERSION = metadata.version;
  } else if (isUpdateCommand(args) && !process.env.LEX_CLI_SKIP_SELF_UPDATE) {
    // `lex --update` keeps the CLI current as well as the data (#19).
    const packageDir = path.resolve(__dirname, "..");
    const cli = await selfUpdate({ currentVersion: metadata.version, packageDir });
    if (cli.status === "updated") {
      // Hand off to the freshly installed launcher so the data update and the
      // version report come from the new CLI, not this stale process.
      const handoff = spawnSync(process.execPath, [path.join(packageDir, "bin", "lex.js"), ...args], {
        stdio: "inherit",
        env: { ...process.env, LEX_CLI_SKIP_SELF_UPDATE: "1", LEX_CLI_UPDATED_FROM: metadata.version },
      });
      if (handoff.error) throw handoff.error;
      process.exitCode = handoff.status === null ? 1 : handoff.status;
      return;
    }
    env.LEX_CLI_UPDATE_STATUS = cli.status;
    if (cli.latestVersion) env.LEX_CLI_LATEST_VERSION = cli.latestVersion;
    if (cli.command) env.LEX_CLI_UPGRADE_COMMAND = cli.command;
  }
  const home = await resolveLexHome();
  bootstrap(home);
  const result = spawnSync(pythonPath(home), [path.join(home, "lex.py"), ...args], { stdio: "inherit", env });
  if (result.error) throw result.error;
  process.exitCode = result.status || 0;
}

module.exports = {
  archiveRoot,
  archiveEntryProblem,
  archiveTypeProblem,
  verifyArchiveEntries,
  verifyExtractedTree,
  validReleaseTag,
  installRoot,
  releaseUrls,
  resolveReleaseTag,
  validLexHome,
  pythonPath,
  dependenciesInstalled,
  jsonModeRequested,
  normalizeArgs,
  setQuiet,
  main,
};

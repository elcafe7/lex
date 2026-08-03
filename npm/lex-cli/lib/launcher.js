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
const config = metadata.lexCli;

function releaseBaseUrl() {
  return process.env.LEX_CLI_RELEASE_BASE_URL ||
    `https://github.com/${config.repository}/releases/download/${config.releaseTag}`;
}

function releaseUrls() {
  const base = releaseBaseUrl().replace(/\/$/, "");
  return {
    archive: `${base}/${config.assetName}`,
    checksum: `${base}/${config.checksumName}`,
  };
}

function installRoot() {
  const dataHome = process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local", "share");
  return path.join(dataHome, "lex-cli", metadata.version);
}

function archiveRoot() {
  return `lex-${metadata.version}`;
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
  const result = spawnSync(command, args, { stdio: "inherit", ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} exited with status ${result.status}`);
}

function validLexHome(directory) {
  return fs.existsSync(path.join(directory, "lex.py")) &&
    fs.existsSync(path.join(directory, "requirements.txt")) &&
    fs.existsSync(path.join(directory, "runtime-data", "lexicon.db"));
}

function pythonPath(directory) {
  return path.join(directory, ".venv", "bin", "python");
}

function bootstrap(directory) {
  if (fs.existsSync(pythonPath(directory))) return;
  checked("python3", ["-c", "import sys; raise SystemExit(sys.version_info < (3, 12))"]);
  checked("python3", ["-m", "venv", path.join(directory, ".venv")]);
  checked(pythonPath(directory), ["-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"], { cwd: directory });
}

async function downloadRelease() {
  const destination = installRoot();
  if (validLexHome(destination)) return destination;

  const temporary = await fsp.mkdtemp(path.join(os.tmpdir(), "lex-cli-"));
  try {
    const urls = releaseUrls();
    const archive = path.join(temporary, config.assetName);
    console.error(`lex: downloading ${config.releaseTag} release data…`);
    const [expected] = await Promise.all([expectedChecksum(urls.checksum), download(urls.archive, archive)]);
    const actual = await sha256(archive);
    if (actual !== expected) throw new Error("release archive checksum mismatch");
    const extraction = path.join(temporary, "extracted");
    await fsp.mkdir(extraction);
    checked("tar", ["-xzf", archive, "-C", extraction]);
    const source = path.join(extraction, archiveRoot());
    if (!validLexHome(source)) throw new Error("release archive does not contain a valid Lex distribution");
    await fsp.mkdir(path.dirname(destination), { recursive: true, mode: 0o700 });
    await fsp.rename(source, destination);
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
  return downloadRelease();
}

async function main(args) {
  if (args.length === 1 && args[0] === "--npm-version") {
    console.log(metadata.version);
    return;
  }
  const home = await resolveLexHome();
  bootstrap(home);
  const result = spawnSync(pythonPath(home), [path.join(home, "lex.py"), ...args], { stdio: "inherit" });
  if (result.error) throw result.error;
  process.exitCode = result.status || 0;
}

module.exports = { archiveRoot, installRoot, releaseUrls, validLexHome, main };

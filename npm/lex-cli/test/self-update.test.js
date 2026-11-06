"use strict";

// `lex --update` keeps the CLI current, not only the data (#19).

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { spawnSync } = require("node:child_process");
const su = require("../lib/self-update");

const GLOBAL_DIR = path.posix.join("/home/nate/.local", "lib", "node_modules", "@n8te_", "lex-cli");

function fakeDeps(overrides = {}) {
  const lines = [];
  const calls = [];
  return {
    lines,
    calls,
    deps: {
      currentVersion: "2.6.2",
      packageDir: GLOBAL_DIR,
      platform: "linux",
      fetchLatest: async () => "2.6.6",
      writable: () => true,
      globalPrefix: () => "/usr/local",
      install: (install, version) => { calls.push({ prefix: install.prefix, version }); return { ok: true }; },
      readVersion: () => "2.6.6",
      log: (line) => lines.push(line),
      ...overrides,
    },
  };
}

test("compareVersions orders semver and ignores a v prefix", () => {
  assert.equal(su.compareVersions("2.6.2", "2.6.6"), -1);
  assert.equal(su.compareVersions("v2.6.6", "2.6.6"), 0);
  assert.equal(su.compareVersions("2.10.0", "2.9.9"), 1);
  assert.equal(su.compareVersions("garbage", "2.6.6"), 0);
});

test("isUpdateCommand matches --update and the update subcommand only", () => {
  assert.ok(su.isUpdateCommand(["--update"]));
  assert.ok(su.isUpdateCommand(["update"]));
  assert.ok(!su.isUpdateCommand(["John", "update"]));
  assert.ok(!su.isUpdateCommand(["-v"]));
  assert.ok(!su.isUpdateCommand(["--version"]));
});

test("detectInstall recognises a global npm install under ~/.local", () => {
  const install = su.detectInstall(GLOBAL_DIR, "linux");
  assert.equal(install.type, "npm-global");
  assert.equal(install.prefix, "/home/nate/.local");
  assert.equal(install.nodeModules, "/home/nate/.local/lib/node_modules");
});

test("detectInstall recognises a Windows global npm install", () => {
  const install = su.detectInstall("C:\\Users\\n\\AppData\\Roaming\\npm\\node_modules\\@n8te_\\lex-cli", "win32");
  assert.equal(install.type, "npm-global");
  assert.equal(install.prefix, "C:\\Users\\n\\AppData\\Roaming\\npm");
});

test("detectInstall flags npx, project-local, and source checkouts as unsupported", () => {
  assert.equal(su.detectInstall("/home/n/.npm/_npx/abc/node_modules/@n8te_/lex-cli", "linux").type, "npx");
  assert.equal(su.detectInstall("/home/n/project/node_modules/@n8te_/lex-cli", "linux").type, "local");
  assert.equal(su.detectInstall("/home/n/src/lex/npm/lex-cli", "linux").type, "unknown");
});

test("upgradeCommand includes --prefix only when it differs from npm's global prefix", () => {
  const install = su.detectInstall(GLOBAL_DIR, "linux");
  assert.equal(su.upgradeCommand(install, { globalPrefix: "/usr/local" }),
    "npm install -g --prefix /home/nate/.local @n8te_/lex-cli@latest");
  assert.equal(su.upgradeCommand(install, { globalPrefix: "/home/nate/.local" }),
    "npm install -g @n8te_/lex-cli@latest");
  assert.equal(su.upgradeCommand({ type: "unknown" }), "npm install -g @n8te_/lex-cli@latest");
});

test("already current: no install is attempted", async () => {
  const { deps, calls, lines } = fakeDeps({ currentVersion: "2.6.6" });
  const result = await su.selfUpdate(deps);
  assert.equal(result.status, "current");
  assert.equal(result.installedVersion, "2.6.6");
  assert.equal(calls.length, 0);
  assert.match(lines.join("\n"), /CLI 2\.6\.6 is the latest/);
});

test("behind and upgrade succeeds: installs latest into the detected prefix", async () => {
  const { deps, calls, lines } = fakeDeps();
  const result = await su.selfUpdate(deps);
  assert.equal(result.status, "updated");
  assert.deepEqual(calls, [{ prefix: "/home/nate/.local", version: "2.6.6" }]);
  assert.equal(result.installedVersion, "2.6.6");
  assert.match(lines.join("\n"), /CLI updated 2\.6\.2 → 2\.6\.6/);
});

test("behind and npm fails: reports failure and the exact command", async () => {
  const { deps, lines } = fakeDeps({ install: () => ({ ok: false, reason: "npm exited with status 243" }) });
  const result = await su.selfUpdate(deps);
  assert.equal(result.status, "failed");
  assert.equal(result.command, "npm install -g --prefix /home/nate/.local @n8te_/lex-cli@latest");
  const out = lines.join("\n");
  assert.match(out, /behind the latest 2\.6\.6 and was NOT updated \(npm exited with status 243\)/);
  assert.match(out, /run: npm install -g --prefix \/home\/nate\/\.local @n8te_\/lex-cli@latest/);
});

test("behind without write permission: does not run npm, prints the command", async () => {
  const { deps, calls } = fakeDeps({ writable: () => false });
  const result = await su.selfUpdate(deps);
  assert.equal(result.status, "failed");
  assert.equal(calls.length, 0);
  assert.match(result.reason, /no write permission/);
});

test("behind on an unsupported install path: does not run npm, prints the command", async () => {
  const { deps, calls } = fakeDeps({ packageDir: "/home/n/src/lex/npm/lex-cli" });
  const result = await su.selfUpdate(deps);
  assert.equal(result.status, "failed");
  assert.equal(calls.length, 0);
  assert.equal(result.command, "npm install -g @n8te_/lex-cli@latest");
});

test("npm reports success but the version did not change: treated as a failure", async () => {
  const { deps } = fakeDeps({ readVersion: () => "2.6.2" });
  const result = await su.selfUpdate(deps);
  assert.equal(result.status, "failed");
  assert.match(result.reason, /reports 2\.6\.2/);
});

test("offline: says the CLI was not checked and prints the command", async () => {
  const { deps, calls, lines } = fakeDeps({ fetchLatest: async () => { throw new Error("getaddrinfo ENOTFOUND"); } });
  const result = await su.selfUpdate(deps);
  assert.equal(result.status, "unchecked");
  assert.equal(calls.length, 0);
  assert.match(lines.join("\n"), /couldn't check npm for a newer CLI \(getaddrinfo ENOTFOUND\); CLI is still 2\.6\.2/);
});

// End to end through the real launcher with a fake npm and a fake Lex home:
// the stale launcher upgrades itself, hands off to the new one, and the
// version reported afterwards is the new CLI version.
test("launcher: --update upgrades a stale global install and reports the new version", { skip: process.platform === "win32" }, () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "lex-selfupdate-"));
  try {
    const prefix = path.join(tmp, "prefix");
    const pkgDir = path.join(prefix, "lib", "node_modules", "@n8te_", "lex-cli");
    fs.mkdirSync(path.dirname(pkgDir), { recursive: true });
    fs.cpSync(path.join(__dirname, ".."), pkgDir, { recursive: true });
    const pkgJson = path.join(pkgDir, "package.json");
    const meta = JSON.parse(fs.readFileSync(pkgJson, "utf8"));
    meta.version = "2.6.2";
    fs.writeFileSync(pkgJson, JSON.stringify(meta, null, 2));

    // Fake Lex home whose python just echoes the env the launcher passed.
    const home = path.join(tmp, "home");
    fs.mkdirSync(path.join(home, "runtime-data"), { recursive: true });
    fs.mkdirSync(path.join(home, ".venv", "bin"), { recursive: true });
    fs.writeFileSync(path.join(home, "lex.py"), "");
    fs.writeFileSync(path.join(home, "requirements.txt"), "");
    fs.writeFileSync(path.join(home, "runtime-data", "lexicon.db"), "");
    const fakePython = path.join(home, ".venv", "bin", "python");
    fs.writeFileSync(fakePython,
      "#!/bin/sh\necho \"PY status=$LEX_CLI_UPDATE_STATUS cli=$LEX_CLI_PACKAGE_VERSION from=$LEX_CLI_UPDATED_FROM args=$2\"\n");
    fs.chmodSync(fakePython, 0o755);

    // Fake npm: `npm install -g --prefix P pkg@VER` rewrites the version.
    const bin = path.join(tmp, "bin");
    fs.mkdirSync(bin);
    const npmLog = path.join(tmp, "npm.log");
    fs.writeFileSync(path.join(bin, "npm"), `#!/bin/sh
echo "$@" >> "${npmLog}"
if [ "$1" = "prefix" ]; then echo /usr/local; exit 0; fi
ver="\${5##*@}"
node -e 'const f=process.argv[1];const m=require(f);m.version=process.argv[2];require("fs").writeFileSync(f,JSON.stringify(m))' "$4/lib/node_modules/@n8te_/lex-cli/package.json" "$ver"
`);
    fs.chmodSync(path.join(bin, "npm"), 0o755);

    // Registry stub: a tiny preload that answers the npm "latest" lookup.
    const preload = path.join(tmp, "registry-stub.js");
    fs.writeFileSync(preload, `
const https = require("node:https");
const { PassThrough } = require("node:stream");
const real = https.get;
https.get = function (url, options, cb) {
  if (String(url).includes("registry.example")) {
    const res = new PassThrough(); res.statusCode = 200;
    const req = new PassThrough(); req.setTimeout = () => req;
    process.nextTick(() => { cb(res); res.end(JSON.stringify({ version: "2.6.6" })); });
    return req;
  }
  return real.apply(this, arguments);
};
`);

    const env = {
      ...process.env,
      PATH: `${bin}${path.delimiter}${process.env.PATH}`,
      LEX_CLI_HOME: home,
      LEX_CLI_REGISTRY_URL: "https://registry.example",
      NODE_OPTIONS: `--require ${preload}`,
    };
    delete env.LEX_CLI_SKIP_SELF_UPDATE;
    delete env.LEX_CLI_UPDATED_FROM;
    const run = spawnSync(process.execPath, [path.join(pkgDir, "bin", "lex.js"), "--update"], { env, encoding: "utf8" });
    const out = run.stdout + run.stderr;
    assert.equal(run.status, 0, out);
    assert.match(out, /CLI updated 2\.6\.2 → 2\.6\.6/);
    assert.match(out, /PY status=updated cli=2\.6\.6 from=2\.6\.2 args=--update/);
    assert.match(fs.readFileSync(npmLog, "utf8"), new RegExp(`install -g --prefix ${prefix} @n8te_/lex-cli@2\\.6\\.6`));

    const after = spawnSync(process.execPath, [path.join(pkgDir, "bin", "lex.js"), "--npm-version"], { env, encoding: "utf8" });
    assert.equal(after.stdout.trim(), "2.6.6");
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

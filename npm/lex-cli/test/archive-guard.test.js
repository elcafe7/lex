"use strict";

// Zip-slip guard for the downloaded release archive and release-tag checks.
// Malicious archives are built with Python's tarfile so they can hold entries
// that a normal `tar -c` refuses to create.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { spawnSync } = require("node:child_process");
const launcher = require("../lib/launcher");

const ROOT = "lex-2.6.8";

const MAKE_ARCHIVE = `
import io, json, sys, tarfile
out, spec = sys.argv[1], json.loads(sys.argv[2])
with tarfile.open(out, "w:gz", format=tarfile.GNU_FORMAT) as tar:
    for entry in spec:
        info = tarfile.TarInfo(entry["name"])
        kind = entry.get("type", "file")
        data = entry.get("data", "x").encode()
        if kind == "dir":
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            tar.addfile(info)
        elif kind == "symlink":
            info.type = tarfile.SYMTYPE
            info.linkname = entry["target"]
            tar.addfile(info)
        elif kind == "hardlink":
            info.type = tarfile.LNKTYPE
            info.linkname = entry["target"]
            tar.addfile(info)
        else:
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
`;

function makeArchive(entries) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "lex-archive-test-"));
  const archive = path.join(dir, "release.tar.gz");
  const result = spawnSync("python3", ["-c", MAKE_ARCHIVE, archive, JSON.stringify(entries)], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  return { dir, archive };
}

function goodEntries() {
  return [
    { name: `${ROOT}/`, type: "dir" },
    { name: `${ROOT}/lex.py`, data: "print('lex')" },
    { name: `${ROOT}/runtime-data/`, type: "dir" },
    { name: `${ROOT}/runtime-data/lexicon.db`, data: "db" },
  ];
}

function rejects(entries, pattern) {
  const { dir, archive } = makeArchive(entries);
  try {
    assert.throws(() => launcher.verifyArchiveEntries(archive, ROOT), pattern);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test("a normal release archive passes and extracts cleanly", () => {
  const { dir, archive } = makeArchive(goodEntries());
  try {
    launcher.verifyArchiveEntries(archive, ROOT);
    const extraction = path.join(dir, "extracted");
    fs.mkdirSync(extraction);
    assert.equal(spawnSync("tar", ["-xzf", archive, "-C", extraction]).status, 0);
    launcher.verifyExtractedTree(extraction);
    assert.ok(fs.existsSync(path.join(extraction, ROOT, "lex.py")));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("rejects ../ traversal entries", () => {
  rejects([...goodEntries(), { name: `${ROOT}/../evil.sh` }], /parent-directory/);
  rejects([...goodEntries(), { name: "../evil.sh" }], /parent-directory/);
});

test("rejects absolute entries", () => {
  rejects([...goodEntries(), { name: "/tmp/lex-evil.sh" }], /absolute|outside/);
});

test("rejects encoded traversal entries", () => {
  rejects([...goodEntries(), { name: `${ROOT}/..%2f..%2fevil.sh` }], /encoded traversal/);
});

test("rejects entries outside the expected root", () => {
  rejects([...goodEntries(), { name: "other/evil.sh" }], /outside/);
});

test("rejects symlink entries, including symlink-then-write escapes", () => {
  rejects([...goodEntries(), { name: `${ROOT}/etc`, type: "symlink", target: "/etc" }], /entry type|link/);
  rejects([
    ...goodEntries(),
    { name: `${ROOT}/escape`, type: "symlink", target: "../../.." },
    { name: `${ROOT}/escape/evil.sh` },
  ], /entry type|link/);
});

test("rejects hard link entries", () => {
  rejects([...goodEntries(), { name: `${ROOT}/passwd`, type: "hardlink", target: "/etc/passwd" }], /entry type|link/);
});

test("entry-name checks reject NUL and Windows absolute paths", () => {
  assert.match(launcher.archiveEntryProblem(`${ROOT}/a\0b`, ROOT), /NUL/);
  assert.match(launcher.archiveEntryProblem("C:\\Windows\\evil.dll", ROOT), /absolute/);
  assert.match(launcher.archiveEntryProblem(`${ROOT}\\..\\evil`, ROOT), /parent-directory/);
  assert.equal(launcher.archiveEntryProblem(`${ROOT}/runtime-data/lexicon.db`, ROOT), null);
  assert.equal(launcher.archiveEntryProblem(`./${ROOT}/lex.py`, ROOT), null);
});

test("verifyExtractedTree rejects a symlink that escapes the extraction", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "lex-extract-test-"));
  try {
    fs.mkdirSync(path.join(dir, ROOT));
    fs.symlinkSync("/etc", path.join(dir, ROOT, "etc"));
    assert.throws(() => launcher.verifyExtractedTree(dir), /symlink/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("release tags must be plain vX.Y.Z", () => {
  assert.ok(launcher.validReleaseTag("v2.6.8"));
  for (const bad of ["", "2.6.8", "v2.6.8/../../evil", "../v2.6.8", "v2.6.8%2f..", "v2.6.8\0", null, 7]) {
    assert.equal(launcher.validReleaseTag(bad), false, String(bad));
  }
});

test("resolveReleaseTag ignores an unsafe LEX_CLI_RELEASE_TAG", async () => {
  process.env.LEX_CLI_RELEASE_TAG = "v1.0.0/../../evil";
  const originalError = console.error;
  console.error = () => {};
  try {
    assert.equal(await launcher.resolveReleaseTag(), "v2.6.8");
  } finally {
    console.error = originalError;
    delete process.env.LEX_CLI_RELEASE_TAG;
  }
});

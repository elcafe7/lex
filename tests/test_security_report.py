"""Security report writer, index and commit scripts (no network, no gh)."""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "scripts" / "write_security_report.sh"
INDEX = ROOT / "scripts" / "update_security_index.sh"
COMMIT = ROOT / "scripts" / "commit_security_report.sh"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

MALICIOUS_TAGS = (
    "v1;rm -rf /",
    "$(id)",
    'v1"$(id)',
    "v1`id`",
    "../../etc",
    ".hidden",
    "-rf",
    "v1/../x",
    "v1 with space",
    "v1\n2",
    "",
)

README = "# Demo\n\n## Security reports\n\n<!-- security-reports:start -->\nplaceholder\n<!-- security-reports:end -->\n\nTail.\n"


def make_inputs(tmp: Path):
    dist = tmp / "dist"
    vt = tmp / "vt"
    dist.mkdir()
    vt.mkdir()
    (dist / "demo-v1.2.3.tar.gz").write_bytes(b"demo archive\n")
    (dist / "demo-v1.2.3.cdx.json").write_text(
        json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [{"name": "a"}, {"name": "b"}]})
    )
    (dist / "demo-v1.2.3-osv-scan.json").write_text((FIXTURES / "osv_clean.json").read_text())
    (dist / "demo-v1.2.3-osv-scan.md").write_text("# OSV\n\nNo known vulnerabilities.\n")
    (dist / "verification.json").write_text(json.dumps({"result": "pass", "known_vulnerabilities": 0}))
    sums = "".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(dist.iterdir())
    )
    (dist / "SHA256SUMS").write_text(sums)
    sha = hashlib.sha256(b"demo archive\n").hexdigest()
    (vt / "virustotal.md").write_text(
        "| File | Malicious | Suspicious | Undetected | Result | Link |\n|---|---|---|---|---|---|\n"
        f"| demo-v1.2.3.tar.gz | 0 | 0 | 70 | clean | [report](https://www.virustotal.com/gui/file/{sha}) |\n"
    )
    sc = tmp / "scorecard.json"
    sc.write_text(json.dumps({"date": "2026-11-09", "score": 7.4, "checks": []}))
    return dist, vt, sc


def run(script, *args, env=None, cwd=None):
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp"}
    base.update(env or {})
    return subprocess.run(["bash", str(script), *args], capture_output=True, text=True,
                          check=False, env=base, cwd=cwd)


def writer_env(tag, dist, vt, sc, ts="20261109T205501Z", status="published"):
    return {
        "TAG": tag, "STATUS": status, "TS": ts, "REPO": "elcafe7/demo",
        "SERVER_URL": "https://github.com",
        "RUN_URL": "https://github.com/elcafe7/demo/actions/runs/123",
        "DIST_DIR": str(dist), "VT_DIR": str(vt), "SCORECARD_FILE": str(sc),
        "ATTESTED": "true",
        "ATTESTATION_URL": "https://github.com/elcafe7/demo/attestations/42",
    }


class WriterTests(unittest.TestCase):
    def test_rejects_malicious_tags(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            dist, vt, sc = make_inputs(tmp)
            out = tmp / "out"
            for tag in MALICIOUS_TAGS:
                with self.subTest(tag=tag):
                    p = run(WRITER, str(out), env=writer_env(tag, dist, vt, sc))
                    self.assertNotEqual(p.returncode, 0)
                    self.assertIn("invalid tag", p.stderr)
            self.assertFalse(out.exists(), "nothing may be written for a rejected tag")

    def test_rejects_bad_timestamp_and_status(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            dist, vt, sc = make_inputs(tmp)
            p = run(WRITER, str(tmp / "o"), env=writer_env("v1.2.3", dist, vt, sc, ts="$(id)"))
            self.assertIn("invalid TS", p.stderr)
            p = run(WRITER, str(tmp / "o"), env=writer_env("v1.2.3", dist, vt, sc, status="x;id"))
            self.assertIn("STATUS must be", p.stderr)

    def test_published_report(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            dist, vt, sc = make_inputs(tmp)
            env = writer_env("v1.2.3", dist, vt, sc)
            env["BESTPRACTICES_PROJECT_ID"] = "12345"
            env["SOCKET_URL"] = "javascript:alert(1)"
            p = run(WRITER, str(tmp / "out"), env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout.strip(), "v1.2.3_20261109T205501Z")
            d = tmp / "out" / "v1.2.3_20261109T205501Z"
            for f in ("summary.md", "report.json", "osv-scan.json", "osv-scan.md", "sbom.cdx.json",
                      "SHA256SUMS", "attestation.md", "virustotal.md", "virustotal-links.txt",
                      "scorecard.json", "openssf-best-practices.md"):
                self.assertTrue((d / f).is_file(), f)
            self.assertFalse((d / "socket.md").exists(), "invalid SOCKET_URL must be skipped")
            s = (d / "summary.md").read_text()
            self.assertIn("2026-11-09 20:55:01 UTC", s)
            self.assertIn("| SHA256SUMS | verified (5 files)", s)
            self.assertIn("| OpenSSF Scorecard | 7.4/10", s)
            self.assertIn("| Socket.dev | not configured", s)
            self.assertNotIn("javascript:", s)
            self.assertEqual(json.loads((d / "report.json").read_text())["result"], "pass")

    def test_blocked_report_skips_optional(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            scan = tmp / "scan"
            scan.mkdir()
            (scan / "demo-osv-scan.json").write_text((FIXTURES / "osv_mixed.json").read_text())
            p = run(WRITER, str(tmp / "out"), env={
                "TAG": "v9", "STATUS": "blocked", "TS": "20261109T210000Z",
                "REPO": "elcafe7/demo", "SCAN_DIR": str(scan)})
            self.assertEqual(p.returncode, 0, p.stderr)
            s = (tmp / "out" / "v9_20261109T210000Z" / "summary.md").read_text()
            self.assertIn("**blocked**", s)
            self.assertIn("| VirusTotal | not enabled", s)
            self.assertIn("| OpenSSF Scorecard | not available", s)
            self.assertIn("not run (blocked)", s)


class IndexAndCommitTests(unittest.TestCase):
    def test_index_newest_first_and_readme_block(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            dist, vt, sc = make_inputs(tmp)
            sec = tmp / "security"
            (tmp / "README.md").write_text(README)
            p = run(INDEX, str(sec), str(tmp / "README.md"))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("Latest: none yet", (tmp / "README.md").read_text())
            self.assertEqual(json.loads((sec / "latest.json").read_text())["result"], "none")
            for ts in ("20261101T000000Z", "20261109T205501Z"):
                run(WRITER, str(sec / "reports"), env=writer_env("v1.2.3", dist, vt, sc, ts=ts))
            bad = sec / "reports" / "evil_20991231T000000Z"
            bad.mkdir()
            (bad / "report.json").write_text(json.dumps(
                {"tag": "<img src=x>", "timestamp": "20991231T000000Z", "result": "pass"}))
            p = run(INDEX, str(sec), str(tmp / "README.md"))
            self.assertEqual(p.returncode, 0, p.stderr)
            idx = (sec / "README.md").read_text()
            self.assertLess(idx.index("2026-11-09"), idx.index("2026-11-01"))
            self.assertNotIn("<img", idx)
            latest = json.loads((sec / "latest.json").read_text())
            self.assertEqual(latest["timestamp"], "20261109T205501Z")
            r = (tmp / "README.md").read_text()
            self.assertIn("2026-11-09 20:55:01 UTC", r)
            self.assertTrue(r.endswith("<!-- security-reports:end -->\n\nTail.\n"))

    def _repo_with_artifact(self, tmp: Path):
        dist, vt, sc = make_inputs(tmp)
        art = tmp / "artifact"
        run(WRITER, str(art), env=writer_env("v1.2.3", dist, vt, sc))
        origin = tmp / "origin.git"
        work = tmp / "work"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
        (work / "README.md").write_text(README)
        (work / "scripts").mkdir()
        for s in (WRITER, INDEX, COMMIT):
            (work / "scripts" / s.name).write_text(s.read_text())
        ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
        for args in (["add", "."], ["commit", "-q", "-m", "init"], ["push", "-q", "origin", "HEAD:main"]):
            subprocess.run(["git", *ident, *args], cwd=work, check=True, capture_output=True)
        return art, origin, work

    @staticmethod
    def _fake_gh(tmp: Path, rc: int, name: str = "bin"):
        """A stub gh on PATH: records its arguments, never touches the network."""
        bindir = tmp / name
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{tmp}/gh-args"\nexit {rc}\n')
        gh.chmod(0o755)
        return f"{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}"

    def _git_out(self, origin, *args):
        return subprocess.run(["git", "--git-dir", str(origin), *args],
                              capture_output=True, text=True, check=True).stdout

    def test_commit_rejects_bad_tags(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            art, origin, work = self._repo_with_artifact(tmp)
            path = self._fake_gh(tmp, 0)
            for tag in ("v1;rm -rf /", "$(id)"):
                p = run(work / "scripts" / "commit_security_report.sh", str(art),
                        env={"PATH": path, "DEFAULT_BRANCH": "main", "REPO": "elcafe7/demo", "TAG": tag}, cwd=work)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("invalid tag", p.stderr)
            self.assertFalse((tmp / "gh-args").exists())

    def test_commit_opens_pr_and_never_pushes_main(self):
        for rc in (0, 1):
            with self.subTest(gh_exit=rc), tempfile.TemporaryDirectory() as t:
                tmp = Path(t)
                art, origin, work = self._repo_with_artifact(tmp)
                main_before = self._git_out(origin, "rev-parse", "main")
                p = run(work / "scripts" / "commit_security_report.sh", str(art),
                        env={"PATH": self._fake_gh(tmp, rc), "DEFAULT_BRANCH": "main",
                             "REPO": "elcafe7/demo", "TAG": "v1.2.3"}, cwd=work)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(self._git_out(origin, "rev-parse", "main"), main_before,
                                 "the default branch must never be pushed")
                side = "reports/v1.2.3_20261109T205501Z"
                self.assertIn("[skip ci]", self._git_out(origin, "log", "-1", "--format=%s", side))
                files = self._git_out(origin, "ls-tree", "-r", "--name-only", side)
                self.assertIn("security/reports/v1.2.3_20261109T205501Z/summary.md", files)
                self.assertIn("security/latest.json", files)
                args = (tmp / "gh-args").read_text().split("\n")
                self.assertEqual(args[:2], ["pr", "create"])
                self.assertIn(side, args)
                if rc == 0:
                    self.assertIn("Opened a PR", p.stdout)
                else:
                    self.assertIn("::notice::", p.stdout)
                    self.assertIn("compare/main...reports/v1.2.3_20261109T205501Z", p.stdout)
                # Re-run: branch exists, nothing pushed, soft exit.
                p2 = run(work / "scripts" / "commit_security_report.sh", str(art),
                         env={"PATH": self._fake_gh(tmp, rc, "bin2"),
                              "DEFAULT_BRANCH": "main", "REPO": "elcafe7/demo", "TAG": "v1.2.3"}, cwd=work)
                self.assertEqual(p2.returncode, 0, p2.stderr)
                self.assertIn("already exists", p2.stdout)


if __name__ == "__main__":
    unittest.main()

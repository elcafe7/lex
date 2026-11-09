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
            self.assertIn("| VirusTotal | clean, 1 file scanned |", s)
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


VT_HEADER = "| File | Malicious | Suspicious | Undetected | Result | Link |\n|---|---|---|---|---|---|\n"


class VirusTotalWordingTests(unittest.TestCase):
    """VirusTotal is only called clean/scanned when a scan returned results."""

    def _report(self, tmp: Path, vt_files: dict, status="published"):
        dist, vt, sc = make_inputs(tmp)
        for f in vt.iterdir():
            f.unlink()
        for name, text in vt_files.items():
            (vt / name).write_text(text)
        p = run(WRITER, str(tmp / "out"), env=writer_env("v1.2.3", dist, vt, sc, status=status))
        self.assertEqual(p.returncode, 0, p.stderr)
        d = tmp / "out" / "v1.2.3_20261109T205501Z"
        return d, (d / "summary.md").read_text()

    def _vt_row(self, summary: str) -> str:
        rows = [l for l in summary.splitlines() if l.startswith("| VirusTotal |")]
        self.assertEqual(len(rows), 1, summary)
        return rows[0]

    def _assert_not_scanned(self, d: Path, row: str):
        for word in ("clean", "scanned |", "pass", "FLAGGED"):
            self.assertNotIn(word, row.replace("nothing scanned", ""))
        self.assertFalse((d / "virustotal.md").exists())
        self.assertFalse((d / "virustotal-links.txt").exists())
        self.assertNotIn("virustotal.com", (d / "summary.md").read_text())

    def test_vt_off_says_not_enabled(self):
        with tempfile.TemporaryDirectory() as t:
            d, s = self._report(Path(t), {})
            row = self._vt_row(s)
            self.assertEqual(row, "| VirusTotal | not enabled | - |")
            self._assert_not_scanned(d, row)
            self.assertNotIn("irus", (d / "verification.json").read_text())
            self.assertNotIn("irus", (d / "report.json").read_text())

    def test_header_only_report_is_not_a_scan(self):
        with tempfile.TemporaryDirectory() as t:
            d, s = self._report(Path(t), {"virustotal.md": "# VirusTotal check\n\n" + VT_HEADER})
            row = self._vt_row(s)
            self.assertIn("enabled but no results (nothing scanned)", row)
            self._assert_not_scanned(d, row)

    def test_free_text_clean_is_not_a_scan(self):
        with tempfile.TemporaryDirectory() as t:
            d, s = self._report(Path(t), {"virustotal.md": "VirusTotal: clean, all good\n"
                                          "| x | 0 | 0 | 0 | clean | [report](https://evil.example/) |\n"})
            row = self._vt_row(s)
            self.assertIn("nothing scanned", row)
            self._assert_not_scanned(d, row)

    def test_missing_key_note(self):
        note = Path(t := tempfile.mkdtemp()) / "note.md"
        p = run(ROOT / "scripts" / "virustotal_not_run.sh", str(note), "missing-key")
        self.assertEqual(p.returncode, 0, p.stderr)
        text = note.read_text()
        self.assertIn("No file was scanned", text)
        self.assertIn("VT_API_KEY", text)
        with tempfile.TemporaryDirectory() as t2:
            d, s = self._report(Path(t2), {"virustotal-not-run.md": text}, status="blocked")
            row = self._vt_row(s)
            self.assertIn("enabled but not run: VT_API_KEY secret missing (nothing scanned)", row)
            self._assert_not_scanned(d, row)
        p = run(ROOT / "scripts" / "virustotal_not_run.sh", str(note), "x;id")
        self.assertNotEqual(p.returncode, 0)

    def test_flagged_and_suspicious(self):
        sha = "a" * 64
        rows = (f"| a.tar.gz | 3 | 0 | 60 | FLAGGED | [report](https://www.virustotal.com/gui/file/{sha}) |\n"
                f"| b.tar.gz | 0 | 1 | 60 | suspicious (non-blocking) | [report](https://www.virustotal.com/gui/file/{sha}) |\n")
        with tempfile.TemporaryDirectory() as t:
            d, s = self._report(Path(t), {"virustotal.md": VT_HEADER + rows}, status="blocked")
            self.assertIn("FLAGGED / not finished (1 of 2 files)", self._vt_row(s))
        with tempfile.TemporaryDirectory() as t:
            d, s = self._report(Path(t), {"virustotal.md": VT_HEADER + rows.splitlines(True)[1]})
            self.assertIn("clean, 1 file scanned (suspicious ratings listed, non-blocking)", self._vt_row(s))


class VirusTotalCheckScriptTests(unittest.TestCase):
    """virustotal_check.sh fails closed before any network call."""

    def test_missing_key_fails(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "a.tar.gz"
            f.write_bytes(b"x")
            p = run(ROOT / "scripts" / "virustotal_check.sh", str(Path(t) / "r.md"), str(f))
            self.assertNotEqual(p.returncode, 0)

    def test_no_files_or_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as t:
            env = {"VT_API_KEY": "dummy-not-a-key"}
            p = run(ROOT / "scripts" / "virustotal_check.sh", str(Path(t) / "r.md"), env=env)
            self.assertNotEqual(p.returncode, 0)
            p = run(ROOT / "scripts" / "virustotal_check.sh", str(Path(t) / "r.md"),
                    str(Path(t) / "lex-v*.tar.gz"), env=env)
            self.assertNotEqual(p.returncode, 0)
            self.assertNotIn("dummy-not-a-key", p.stdout + p.stderr)


class WorkflowVirusTotalGuardTests(unittest.TestCase):
    """release.yml: an enabled VT check that fails or has no key never publishes."""

    @classmethod
    def setUpClass(cls):
        try:
            import yaml
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("PyYAML not installed")
        cls.wf = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text())
        cls.jobs = cls.wf["jobs"]

    def test_vt_step_fails_closed_without_key(self):
        step = next(s for s in self.jobs["virustotal"]["steps"] if s.get("id") == "vt")
        script = step["run"]
        block = script[script.index('if [ -z "$VT_API_KEY" ]'):]
        block = block[:block.index("fi\n")]
        self.assertIn("::error", block)
        self.assertIn("exit 1", block)
        self.assertNotIn("exit 0", block)
        self.assertNotIn("$VT_API_KEY\"", block.replace('[ -z "$VT_API_KEY" ]', ""))
        self.assertLess(script.index('echo "ran=false"'), script.index('if [ -z "$VT_API_KEY" ]'))
        self.assertIn('if [ "$rc" -eq 0 ]; then echo "ran=true"', script)

    def _guard(self, job):
        cond = " ".join(self.jobs[job]["if"].split())
        self.assertIn("virustotal", self.jobs[job]["needs"])
        self.assertIn("!cancelled()", cond)
        self.assertIn("needs.virustotal.result == 'success' || "
                      "(needs.virustotal.result == 'skipped' && "
                      "!(vars.ENABLE_VIRUSTOTAL == 'true' && github.event.repository.visibility == 'public'))",
                      cond)
        self.assertNotIn("failure", cond)
        return cond

    def test_release_and_report_commit_guards(self):
        self._guard("release")
        cond = self._guard("security-report-commit")
        self.assertIn("needs.release.result == 'success'", cond)

    def test_blocked_job_runs_on_failure(self):
        cond = " ".join(self.jobs["blocked"]["if"].split())
        self.assertIn("contains(needs.*.result, 'failure')", cond)
        self.assertIn("virustotal", self.jobs["blocked"]["needs"])


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

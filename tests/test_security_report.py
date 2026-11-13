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


# Private HOME for the scripts instead of the shared /tmp (bandit B108).
_SCRIPT_HOME_DIR = tempfile.TemporaryDirectory(prefix="lex-security-report-home-")


def tearDownModule():
    _SCRIPT_HOME_DIR.cleanup()


def run(script, *args, env=None, cwd=None):
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": _SCRIPT_HOME_DIR.name}
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
            self.assertIn("| Bandit (Python static analysis) | not run | - |", s)


def bandit_json(results=(), errors=(), skipped=0):
    return json.dumps({"errors": list(errors), "metrics": {"_totals": {"skipped_tests": skipped}},
                       "results": list(results)})


def bandit_result(severity, test_id="B608"):
    return {"test_id": test_id, "issue_severity": severity, "issue_confidence": "LOW",
            "filename": "./lex.py", "line_number": 1, "issue_text": "x"}


class BanditReportTests(unittest.TestCase):
    """The Bandit row reflects Bandit's own JSON; no JSON is never 'pass'."""

    def _summary(self, tmp: Path, files: dict, status="published"):
        dist, vt, sc = make_inputs(tmp)
        bdir = tmp / "bandit-report"
        bdir.mkdir()
        for name, text in files.items():
            (bdir / name).write_text(text)
        env = writer_env("v1.2.3", dist, vt, sc, status=status)
        env["BANDIT_DIR"] = str(bdir)
        p = run(WRITER, str(tmp / "out"), env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = tmp / "out" / "v1.2.3_20261109T205501Z"
        rows = [line for line in (d / "summary.md").read_text().splitlines()
                if line.startswith("| Bandit (Python static analysis) |")]
        self.assertEqual(len(rows), 1)
        return d, rows[0]

    def test_clean_scan_passes_and_copies_reports(self):
        with tempfile.TemporaryDirectory() as t:
            d, row = self._summary(Path(t), {
                "bandit.json": bandit_json([bandit_result("LOW", "B404")] * 3, skipped=7),
                "bandit.txt": "Run metrics\n", "bandit.md": "# Bandit\n"})
            self.assertIn("| pass (0 medium/high findings; 3 low, information only; 7 inline nosec) |", row)
            self.assertIn("[bandit.json](bandit.json), [bandit.txt](bandit.txt), [bandit.md](bandit.md)", row)
            for f in ("bandit.json", "bandit.txt", "bandit.md"):
                self.assertTrue((d / f).is_file(), f)

    def test_findings_fail(self):
        with tempfile.TemporaryDirectory() as t:
            _, row = self._summary(Path(t), {"bandit.json": bandit_json(
                [bandit_result("MEDIUM"), bandit_result("HIGH"), bandit_result("LOW")])}, status="blocked")
            self.assertIn("| FAIL (2 medium/high findings) |", row)

    def test_unscanned_files_fail(self):
        with tempfile.TemporaryDirectory() as t:
            _, row = self._summary(Path(t), {"bandit.json": bandit_json(
                errors=[{"filename": "./x.py", "reason": "syntax error"}])}, status="blocked")
            self.assertIn("FAIL (0 medium/high findings; 1 files not scanned)", row)

    def test_broken_or_missing_json_is_never_pass(self):
        for files in ({"bandit.json": "{not json"}, {"bandit.md": "# Bandit\n"},
                      {"bandit.json": json.dumps({"results": []})}):
            with self.subTest(files=list(files)), tempfile.TemporaryDirectory() as t:
                d, row = self._summary(Path(t), files, status="blocked")
                self.assertIn("FAIL (scan incomplete: no valid Bandit JSON)", row)
                self.assertNotIn("pass", row)
                self.assertFalse((d / "bandit.json").exists())

    def test_no_bandit_dir_says_not_run(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            dist, vt, sc = make_inputs(tmp)
            p = run(WRITER, str(tmp / "out"), env=writer_env("v1.2.3", dist, vt, sc))
            self.assertEqual(p.returncode, 0, p.stderr)
            s = (tmp / "out" / "v1.2.3_20261109T205501Z" / "summary.md").read_text()
            self.assertIn("| Bandit (Python static analysis) | not run | - |", s)



class GitleaksReportTests(unittest.TestCase):
    """The Gitleaks row reflects the redacted findings list; no JSON is never 'pass'."""

    def _summary(self, tmp: Path, files: dict, status="published"):
        dist, vt, sc = make_inputs(tmp)
        gdir = tmp / "gitleaks-report"
        gdir.mkdir()
        for name, text in files.items():
            (gdir / name).write_text(text)
        env = writer_env("v1.2.3", dist, vt, sc, status=status)
        env["GITLEAKS_DIR"] = str(gdir)
        p = run(WRITER, str(tmp / "out"), env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = tmp / "out" / "v1.2.3_20261109T205501Z"
        rows = [line for line in (d / "summary.md").read_text().splitlines()
                if line.startswith("| Gitleaks (secret scan) |")]
        self.assertEqual(len(rows), 1)
        return d, rows[0]

    def test_clean_scan_passes_and_copies_reports(self):
        with tempfile.TemporaryDirectory() as t:
            d, row = self._summary(Path(t), {
                "gitleaks.json": "[]",
                "gitleaks.md": "# Gitleaks\n",
                "gitleaks.sarif": "{}",
            })
            self.assertIn("| pass (0 findings) |", row)
            self.assertIn("[gitleaks.json](gitleaks.json), [gitleaks.md](gitleaks.md), [gitleaks.sarif](gitleaks.sarif)", row)
            for f in ("gitleaks.json", "gitleaks.md", "gitleaks.sarif"):
                self.assertTrue((d / f).is_file(), f)

    def test_findings_fail(self):
        with tempfile.TemporaryDirectory() as t:
            _, row = self._summary(Path(t), {"gitleaks.json": json.dumps([
                {"RuleID": "generic-api-key", "File": "x.py"},
                {"RuleID": "aws-access-key", "File": "y.py"},
            ])}, status="blocked")
            self.assertIn("| FAIL (2 findings; values redacted) |", row)

    def test_broken_or_missing_json_is_never_pass(self):
        for files in ({"gitleaks.json": "{not json"}, {"gitleaks.md": "# Gitleaks\n"},
                      {"gitleaks.json": json.dumps({"findings": []})}):
            with self.subTest(files=list(files)), tempfile.TemporaryDirectory() as t:
                d, row = self._summary(Path(t), files, status="blocked")
                self.assertIn("FAIL (scan incomplete: no valid Gitleaks JSON)", row)
                self.assertNotIn("pass", row)
                self.assertFalse((d / "gitleaks.json").exists())

    def test_no_gitleaks_dir_says_not_run(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            dist, vt, sc = make_inputs(tmp)
            p = run(WRITER, str(tmp / "out"), env=writer_env("v1.2.3", dist, vt, sc))
            self.assertEqual(p.returncode, 0, p.stderr)
            s = (tmp / "out" / "v1.2.3_20261109T205501Z" / "summary.md").read_text()
            self.assertIn("| Gitleaks (secret scan) | not run | - |", s)


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
        rows = [line for line in summary.splitlines() if line.startswith("| VirusTotal |")]
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
        note = Path(tempfile.mkdtemp()) / "note.md"
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


class WorkflowBanditTests(unittest.TestCase):
    """release.yml: Bandit runs on tag push and dry run, and gates the publish."""

    @classmethod
    def setUpClass(cls):
        try:
            import yaml
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("PyYAML not installed")
        wf_dir = ROOT / ".github" / "workflows"
        cls.wf = yaml.safe_load((wf_dir / "release.yml").read_text())
        cls.jobs = cls.wf["jobs"]
        cls.bandit_wf = yaml.safe_load((wf_dir / "bandit.yml").read_text())

    @staticmethod
    def _cond(job):
        return " ".join(job["if"].split())

    def _install_and_scan(self, job):
        runs = "\n".join(s.get("run", "") for s in job["steps"])
        self.assertIn("--require-hashes", runs)
        self.assertIn("-r .github/requirements/bandit-requirements.txt", runs)
        self.assertIn("bash scripts/bandit_check.sh bandit-report", runs)
        self.assertIn("python3 -m unittest -v tests.test_bandit_gate", runs)
        self.assertNotIn("--baseline", runs)
        self.assertNotIn(" -b ", runs)
        self.assertNotIn(" -s ", runs)
        self.assertNotIn("--skip", runs)
        self.assertNotIn("${{", runs, "values reach run: only through env")
        checkout = job["steps"][0]
        self.assertTrue(checkout["uses"].startswith("actions/checkout@"))
        self.assertIs(checkout["with"]["persist-credentials"], False)

    def test_bandit_job_runs_on_push_and_dry_run(self):
        job = self.jobs["bandit"]
        self.assertNotIn("if", job, "Bandit must run on tag push and workflow_dispatch")
        self.assertNotIn("needs", job)
        self.assertEqual(job["permissions"], {"contents": "read"})
        self._install_and_scan(job)
        upload = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
        self.assertEqual(upload["with"]["name"], "bandit-report")
        self.assertEqual(upload["if"], "always()")
        self.assertIn("workflow_dispatch", self.wf[True])
        self.assertIn("push", self.wf[True])

    def test_bandit_gate_output(self):
        step = next(s for s in self.jobs["bandit"]["steps"] if s.get("id") == "bandit")
        self.assertIn('echo "gate=pass"', step["run"])
        self.assertIn('echo "gate=fail"', step["run"])
        self.assertIn('exit "$rc"', step["run"])

    def test_release_and_report_commit_need_clean_bandit(self):
        for name in ("release", "security-report-commit"):
            with self.subTest(job=name):
                self.assertIn("bandit", self.jobs[name]["needs"])
                cond = self._cond(self.jobs[name])
                self.assertIn("needs.bandit.result == 'success' && needs.bandit.outputs.gate == 'pass'", cond)

    def test_blocked_job_reports_bandit(self):
        job = self.jobs["blocked"]
        self.assertIn("bandit", job["needs"])
        self.assertIn("needs.bandit.outputs.gate == 'fail'", self._cond(job))
        issue = next(s for s in job["steps"] if s.get("name", "").startswith("Open or update"))
        self.assertIn("bandit: ${{ needs.bandit.result }}", issue["env"]["FAILED_JOBS"])
        dl = next(s for s in job["steps"] if s.get("name") == "Download scan reports")
        self.assertEqual(dl["with"]["pattern"], "*-report")  # picks up bandit-report (bandit.md)
        report = next(s for s in job["steps"] if s.get("id") == "report")
        self.assertEqual(report["env"]["BANDIT_DIR"], "report-inputs")
        self.assertNotIn("contents: write", str(job["permissions"]))

    def test_published_report_gets_bandit_dir(self):
        report = next(s for s in self.jobs["release"]["steps"] if s.get("id") == "report")
        self.assertEqual(report["env"]["BANDIT_DIR"], "bandit-report")
        dl = next(s for s in self.jobs["release"]["steps"] if s.get("name") == "Download the Bandit report")
        self.assertEqual(dl["with"]["name"], "bandit-report")

    def test_standalone_workflow_triggers(self):
        on = self.bandit_wf[True]
        for trigger in ("pull_request", "push", "schedule", "workflow_dispatch"):
            self.assertIn(trigger, on)
        self.assertEqual(on["push"]["branches"], ["main"])
        self.assertEqual(self.bandit_wf["permissions"], {"contents": "read"})
        job = self.bandit_wf["jobs"]["bandit"]
        self.assertEqual(job["permissions"], {"contents": "read"})
        self._install_and_scan(job)

    def test_requirements_are_hash_pinned(self):
        req = (ROOT / ".github" / "requirements" / "bandit-requirements.txt").read_text()
        pkgs = [line for line in req.splitlines() if line and not line.startswith((" ", "#"))]
        self.assertTrue(any(p.startswith("bandit==") for p in pkgs))
        for line in pkgs:
            self.assertIn("==", line)
        self.assertGreaterEqual(req.count("--hash=sha256:"), len(pkgs))



class WorkflowGitleaksTests(unittest.TestCase):
    """release.yml: Gitleaks runs on tag push and dry run, and gates the publish."""

    @classmethod
    def setUpClass(cls):
        try:
            import yaml
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("PyYAML not installed")
        wf_dir = ROOT / ".github" / "workflows"
        cls.wf = yaml.safe_load((wf_dir / "release.yml").read_text())
        cls.jobs = cls.wf["jobs"]
        cls.gitleaks_wf = yaml.safe_load((wf_dir / "gitleaks.yml").read_text())

    @staticmethod
    def _cond(job):
        return " ".join(job["if"].split())

    def _install_and_scan(self, job):
        runs = "\n".join(s.get("run", "") for s in job["steps"])
        self.assertIn("GITLEAKS_VERSION", json.dumps(self.wf.get("env", {})) + runs + json.dumps(job))
        # Version/hash come from env, not from a ${{ }} in run:.
        self.assertIn("gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz", runs)
        self.assertIn("sha256sum -c", runs)
        self.assertIn("bash scripts/gitleaks_check.sh gitleaks-report", runs)
        self.assertIn("python3 -m unittest -v tests.test_gitleaks_gate", runs)
        script = (ROOT / "scripts" / "gitleaks_check.sh").read_text()
        self.assertIn("gitleaks git --redact", script)
        self.assertNotIn("--baseline-path", script)
        self.assertNotIn("--baseline-path", runs)
        self.assertNotIn("${{", runs, "values reach run: only through env")
        checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@"))
        self.assertIs(checkout["with"]["persist-credentials"], False)
        self.assertEqual(checkout["with"].get("fetch-depth"), 0)

    def test_gitleaks_job_runs_on_push_and_dry_run(self):
        job = self.jobs["gitleaks"]
        self.assertNotIn("if", job, "Gitleaks must run on tag push and workflow_dispatch")
        self.assertNotIn("needs", job)
        self.assertEqual(job["permissions"], {"contents": "read"})
        self._install_and_scan(job)
        upload = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
        self.assertEqual(upload["with"]["name"], "gitleaks-report")
        self.assertEqual(upload["if"], "always()")
        self.assertIn("workflow_dispatch", self.wf[True])
        self.assertIn("push", self.wf[True])
        self.assertEqual(self.wf["env"]["GITLEAKS_VERSION"], "8.30.1")
        self.assertEqual(
            self.wf["env"]["GITLEAKS_SHA256"],
            "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        )

    def test_gitleaks_gate_output(self):
        step = next(s for s in self.jobs["gitleaks"]["steps"] if s.get("id") == "gitleaks")
        self.assertIn('echo "gate=pass"', step["run"])
        self.assertIn('echo "gate=fail"', step["run"])
        self.assertIn('exit "$rc"', step["run"])
        self.assertEqual(step["env"]["GITLEAKS_LOG_OPTS"], "--all")

    def test_release_and_report_commit_need_clean_gitleaks(self):
        for name in ("release", "security-report-commit"):
            with self.subTest(job=name):
                self.assertIn("gitleaks", self.jobs[name]["needs"])
                cond = self._cond(self.jobs[name])
                self.assertIn("needs.gitleaks.result == 'success' && needs.gitleaks.outputs.gate == 'pass'", cond)

    def test_blocked_job_reports_gitleaks(self):
        job = self.jobs["blocked"]
        self.assertIn("gitleaks", job["needs"])
        self.assertIn("needs.gitleaks.outputs.gate == 'fail'", self._cond(job))
        issue = next(s for s in job["steps"] if s.get("name", "").startswith("Open or update"))
        self.assertIn("gitleaks: ${{ needs.gitleaks.result }}", issue["env"]["FAILED_JOBS"])
        dl = next(s for s in job["steps"] if s.get("name") == "Download scan reports")
        self.assertEqual(dl["with"]["pattern"], "*-report")  # picks up gitleaks-report (gitleaks.md)
        report = next(s for s in job["steps"] if s.get("id") == "report")
        self.assertEqual(report["env"]["GITLEAKS_DIR"], "report-inputs")
        self.assertNotIn("contents: write", str(job["permissions"]))

    def test_published_report_gets_gitleaks_dir(self):
        report = next(s for s in self.jobs["release"]["steps"] if s.get("id") == "report")
        self.assertEqual(report["env"]["GITLEAKS_DIR"], "gitleaks-report")
        dl = next(s for s in self.jobs["release"]["steps"] if s.get("name") == "Download the Gitleaks report")
        self.assertEqual(dl["with"]["name"], "gitleaks-report")

    def test_standalone_workflow_triggers(self):
        on = self.gitleaks_wf[True]
        for trigger in ("pull_request", "push", "schedule", "workflow_dispatch"):
            self.assertIn(trigger, on)
        self.assertEqual(on["push"]["branches"], ["main"])
        self.assertEqual(self.gitleaks_wf["permissions"], {"contents": "read"})
        self.assertEqual(self.gitleaks_wf["env"]["GITLEAKS_VERSION"], "8.30.1")
        self.assertEqual(
            self.gitleaks_wf["env"]["GITLEAKS_SHA256"],
            "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        )
        job = self.gitleaks_wf["jobs"]["gitleaks"]
        self.assertEqual(job["permissions"], {"contents": "read"})
        runs = "\n".join(s.get("run", "") for s in job["steps"])
        self.assertIn("bash scripts/gitleaks_check.sh gitleaks-report", runs)
        self.assertIn("python3 -m unittest -v tests.test_gitleaks_gate", runs)
        script = (ROOT / "scripts" / "gitleaks_check.sh").read_text()
        self.assertIn("gitleaks git --redact", script)
        self.assertNotIn("--baseline-path", script)
        self.assertNotIn("--baseline-path", runs)
        self.assertNotIn("${{", runs, "values reach run: only through env")
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                self.assertIs(step["with"]["persist-credentials"], False)


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

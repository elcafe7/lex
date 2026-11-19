"""One update path: `lex update`, `lex --update` and `lex -update` update the
CLI and the data together, for git clones, npm installs and release downloads.

Includes the exact failure from the field: a data file the old updater had
downloaded into a git clone (untracked) is added by the next version, and
`git pull --ff-only` aborts with "untracked working tree files would be
overwritten by merge". Everything runs offline against temp folders; the
network and the re-run of lex.py are stubbed.

Run: python3 -m unittest tests.test_update_paths
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

from rich.console import Console

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
GIT = shutil.which("git")


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_update_paths_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


LEXMOD = load_lex_module()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def lex_py(version):
    return f'VERSION = "{version}"\nprint("lex {version}")\n'


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def make_console():
    return Console(record=True, width=140, theme=LEXMOD.custom_theme, file=io.StringIO())


def text_of(console):
    return ANSI.sub("", console.export_text())


@unittest.skipUnless(GIT, "git is required")
class GitInstallTest(unittest.TestCase):
    """A git install at 2.6.8 whose upstream moved to 2.6.9."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lex-gitupdate-")
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                    "HOME": os.path.join(self.tmp, "home")}
        self.home = mock.patch.dict(os.environ, {"HOME": self.env["HOME"]})
        self.home.start()
        self.upstream = os.path.join(self.tmp, "upstream")
        self.install = os.path.join(self.tmp, "lex")
        os.makedirs(os.path.join(self.upstream, "runtime-data"))
        self.git(self.upstream, "init", "-q", "-b", "main")
        self.write(self.upstream, "lex.py", lex_py("2.6.8"))
        self.write(self.upstream, "runtime-data/lexicon.db", "lexicon 2.6.8")
        self.commit(self.upstream, "2.6.8")
        self.git(self.tmp, "clone", "-q", self.upstream, self.install)
        self.console = make_console()
        self.version = mock.patch.object(LEXMOD, "VERSION", "2.6.8")
        self.version.start()

    def tearDown(self):
        self.version.stop()
        self.home.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, cwd, *args, check=True):
        proc = subprocess.run([GIT, "-C", cwd, *args], capture_output=True, text=True, env=self.env)
        if check and proc.returncode != 0:
            raise AssertionError(f"git {args} failed: {proc.stderr}")
        return proc

    def write(self, base, rel, content):
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    def read(self, base, rel):
        with open(os.path.join(base, rel), encoding="utf-8") as fh:
            return fh.read()

    def commit(self, cwd, message):
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", message)

    def release_269(self, creeds="creeds 2.6.9"):
        self.write(self.upstream, "lex.py", lex_py("2.6.9"))
        self.write(self.upstream, "runtime-data/lexicon.db", "lexicon 2.6.9")
        self.write(self.upstream, "runtime-data/creeds-aligned.json", creeds)
        self.commit(self.upstream, "2.6.9")

    def update(self):
        return LEXMOD.git_update(self.console, base_dir=self.install, env=self.env, run_setup=lambda c, b: None)

    # -- the exact collision from the field ---------------------------------
    def test_plain_pull_aborts_on_the_untracked_data_file(self):
        self.release_269()
        self.write(self.install, "runtime-data/creeds-aligned.json", "creeds 2.6.9")
        self.git(self.install, "fetch", "-q")
        pull = self.git(self.install, "pull", "--ff-only", check=False)
        self.assertNotEqual(pull.returncode, 0)
        self.assertIn("untracked working tree files would be overwritten", pull.stderr)
        self.assertIn("runtime-data/creeds-aligned.json", pull.stderr)

    def test_identical_untracked_file_is_moved_aside_and_update_succeeds(self):
        self.release_269()
        self.write(self.install, "runtime-data/creeds-aligned.json", "creeds 2.6.9")
        result = self.update()
        self.assertEqual((result["status"], result["old"], result["new"]), ("updated", "2.6.8", "2.6.9"))
        self.assertEqual(self.read(self.install, "lex.py"), lex_py("2.6.9"))
        self.assertEqual(self.read(self.install, "runtime-data/creeds-aligned.json"), "creeds 2.6.9")
        self.assertEqual(len(result["moved"]), 1)
        self.assertEqual(self.read(os.path.dirname(result["moved"][0]), "creeds-aligned.json"), "creeds 2.6.9")
        self.assertEqual(self.git(self.install, "status", "--porcelain").stdout.strip(), "")

    def test_superseded_untracked_file_keeps_a_backup_of_the_old_copy(self):
        self.release_269()
        self.write(self.install, "runtime-data/creeds-aligned.json", "an older download")
        result = self.update()
        self.assertEqual(result["status"], "updated")
        self.assertEqual(self.read(self.install, "runtime-data/creeds-aligned.json"), "creeds 2.6.9")
        self.assertEqual(self.read(os.path.dirname(result["moved"][0]), "creeds-aligned.json"), "an older download")
        self.assertIn("moved", text_of(self.console).lower())

    def test_data_files_an_old_updater_rewrote_do_not_block_the_pull(self):
        self.release_269()
        self.write(self.install, "runtime-data/lexicon.db", "downloaded copy")
        result = self.update()
        self.assertEqual(result["status"], "updated")
        self.assertEqual(self.read(self.install, "runtime-data/lexicon.db"), "lexicon 2.6.9")
        self.assertEqual(self.read(os.path.dirname(result["moved"][0]), "lexicon.db"), "downloaded copy")

    # -- refusals leave everything alone ------------------------------------
    def test_local_edit_to_tracked_code_refuses_and_changes_nothing(self):
        self.release_269()
        self.write(self.install, "lex.py", "# my edit\n" + lex_py("2.6.8"))
        before = self.git(self.install, "rev-parse", "HEAD").stdout
        with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
            self.update()
        self.assertIn("local changes", str(ctx.exception))
        self.assertIn("lex.py", str(ctx.exception))
        self.assertEqual(self.git(self.install, "rev-parse", "HEAD").stdout, before)
        self.assertTrue(self.read(self.install, "lex.py").startswith("# my edit"))

    def test_diverged_branch_refuses(self):
        self.release_269()
        self.write(self.install, "notes.txt", "mine")
        self.commit(self.install, "local commit")
        with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
            self.update()
        self.assertIn("fast-forward", str(ctx.exception))

    def test_detached_head_refuses(self):
        self.git(self.install, "checkout", "-q", "--detach")
        with self.assertRaises(LEXMOD.UpdateRefused):
            self.update()

    def test_already_current_is_a_noop(self):
        result = self.update()
        self.assertEqual((result["status"], result["moved"]), ("current", []))

    # -- the whole command ----------------------------------------------------
    def test_update_command_pulls_then_reruns_the_new_code_for_data_and_summary(self):
        self.release_269()
        self.write(self.install, "runtime-data/creeds-aligned.json", "creeds 2.6.9")
        manager = mock.Mock(data_before="2.6.8")
        calls = []

        def fake_run(argv, env=None, check=False):
            calls.append((argv, env))
            return subprocess.CompletedProcess(argv, 0)

        code = LEXMOD.run_update_command(self.console, manager, env=self.env, base_dir=self.install, runner=fake_run,
                                         git_runner=lambda console, base_dir, env: LEXMOD.git_update(
                                             console, base_dir=base_dir, env=env, run_setup=lambda c, b: None))
        self.assertEqual(code, 0)
        manager.perform_update.assert_not_called()  # the new code does the data step
        (argv, child_env), = calls
        self.assertEqual(argv[1:], [os.path.join(self.install, "lex.py"), "--update"])
        self.assertEqual(child_env["LEX_CLI_UPDATE_STATUS"], "updated")
        self.assertEqual(child_env["LEX_CLI_UPDATED_FROM"], "2.6.8")
        self.assertEqual(child_env["LEX_CLI_LATEST_VERSION"], "2.6.9")
        self.assertEqual(child_env["LEX_DATA_VERSION_BEFORE"], "2.6.8")
        self.assertEqual(self.read(self.install, "lex.py"), lex_py("2.6.9"))

    def test_update_command_refusal_skips_the_data_step_and_exits_nonzero(self):
        self.release_269()
        self.write(self.install, "lex.py", "# edit\n")
        manager = mock.Mock(data_before="2.6.8")
        code = LEXMOD.run_update_command(self.console, manager, env=self.env, base_dir=self.install,
                                         git_runner=lambda console, base_dir, env: LEXMOD.git_update(
                                             console, base_dir=base_dir, env=env, run_setup=lambda c, b: None))
        self.assertEqual(code, 1)
        manager.perform_update.assert_not_called()
        self.assertIn("Lex was not updated", text_of(self.console))

    def test_ignored_marker_file_is_not_a_local_change(self):
        # runtime-data/.lex-data-version is written after each update and is gitignored.
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as fh:
            self.assertIn(".lex-data-version", fh.read())


class InstallKindTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lex-kind-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_kinds(self):
        self.assertEqual(LEXMOD.detect_install_kind(self.tmp, {}), "release")
        os.makedirs(os.path.join(self.tmp, ".git"))
        self.assertEqual(LEXMOD.detect_install_kind(self.tmp, {}), "git")
        self.assertEqual(LEXMOD.detect_install_kind(self.tmp, {"LEX_CLI_PACKAGE_VERSION": "2.6.9"}), "npm")

    def test_npm_launcher_owns_the_cli_part(self):
        boom = mock.Mock(side_effect=AssertionError("must not run for npm"))
        env = {"LEX_CLI_PACKAGE_VERSION": "2.6.9", "LEX_CLI_UPDATE_STATUS": "updated",
               "LEX_CLI_UPDATED_FROM": "2.6.8", "LEX_CLI_LATEST_VERSION": "2.6.9"}
        console = make_console()
        manager = mock.Mock(data_before="2.6.8", remote_version="2.6.9", data_changed=True)
        manager.perform_update.return_value = True
        code = LEXMOD.run_update_command(console, manager, env=env, base_dir=self.tmp, git_runner=boom,
                                         release_runner=boom)
        self.assertEqual(code, 0)
        out = text_of(console)
        self.assertIn("Lex CLI:  2.6.8 → 2.6.9 (updated)", out)
        self.assertIn("Lex data: 2.6.8 → 2.6.9 (updated)", out)

    def test_npm_without_launcher_status_still_updates_data_only_once(self):
        console = make_console()
        manager = mock.Mock(data_before=None, remote_version="2.6.9", data_changed=False)
        manager.perform_update.return_value = True
        LEXMOD.run_update_command(console, manager, env={"LEX_CLI_PACKAGE_VERSION": "2.6.9"}, base_dir=self.tmp)
        manager.perform_update.assert_called_once()

    def test_rerun_after_a_cli_update_does_not_update_the_cli_again(self):
        boom = mock.Mock(side_effect=AssertionError("must not run again"))
        os.makedirs(os.path.join(self.tmp, ".git"))
        console = make_console()
        manager = mock.Mock(data_before="2.6.8", remote_version="2.6.9", data_changed=False)
        manager.perform_update.return_value = True
        env = {"LEX_CLI_UPDATE_STATUS": "updated", "LEX_CLI_UPDATED_FROM": "2.6.8", "LEX_CLI_LATEST_VERSION": "2.6.9"}
        with mock.patch.object(LEXMOD, "VERSION", "2.6.9"):
            code = LEXMOD.run_update_command(console, manager, env=env, base_dir=self.tmp, git_runner=boom)
        self.assertEqual(code, 0)
        out = text_of(console)
        self.assertIn("Lex CLI:  2.6.8 → 2.6.9 (updated)", out)
        self.assertIn("Lex data: 2.6.8 → 2.6.9 (updated)", out)  # pulled in with the code

    def test_packaged_build_points_to_the_release_page(self):
        console = make_console()
        manager = mock.Mock(data_before=None, remote_version="2.6.9", data_changed=False)
        manager.perform_update.return_value = True
        with mock.patch.object(LEXMOD.sys, "frozen", True, create=True):
            LEXMOD.run_update_command(console, manager, env={}, base_dir=self.tmp)
        self.assertIn("releases/latest", text_of(console))


class ReleaseInstallTest(unittest.TestCase):
    """A folder unpacked from a release download, behind the latest release."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lex-release-")
        self.install = os.path.join(self.tmp, "lex-2.6.8")
        os.makedirs(os.path.join(self.install, "runtime-data"))
        for rel, text in {"lex.py": lex_py("2.6.8"), "runtime-data/lexicon.db": "lexicon 2.6.8",
                          "my-notes.txt": "keep me"}.items():
            with open(os.path.join(self.install, rel), "w") as fh:
                fh.write(text)
        self.env = {}
        self.home = mock.patch.dict(os.environ, {"HOME": os.path.join(self.tmp, "home")})
        self.home.start()
        self.requested = []
        self.version = mock.patch.object(LEXMOD, "VERSION", "2.6.8")
        self.version.start()

    def tearDown(self):
        self.version.stop()
        self.home.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def archive(self, version="2.6.9"):
        path = os.path.join(self.tmp, f"lex-v{version}.tar.gz")
        src = os.path.join(self.tmp, f"src-{version}", f"lex-{version}")
        os.makedirs(os.path.join(src, "runtime-data"))
        with open(os.path.join(src, "lex.py"), "w") as fh:
            fh.write(lex_py(version))
        with open(os.path.join(src, "runtime-data", "lexicon.db"), "w") as fh:
            fh.write(f"lexicon {version}")
        with open(os.path.join(src, "runtime-data", "creeds-aligned.json"), "w") as fh:
            fh.write(f"creeds {version}")
        with tarfile.open(path, "w:gz") as tar:
            tar.add(src, arcname=f"lex-{version}")
        with open(path, "rb") as fh:
            return fh.read()

    def opener(self, latest="v2.6.9", payload=None, checksum=None):
        payload = self.archive(latest[1:]) if payload is None else payload
        checksum = sha(payload) if checksum is None else checksum

        def open_url(url_or_request, **kwargs):
            url = url_or_request.full_url if hasattr(url_or_request, "full_url") else url_or_request
            self.requested.append(url)
            if url == LEXMOD.RELEASE_LATEST_URL:
                return FakeResponse(json.dumps({"tag_name": latest}).encode())
            if url.endswith(".tar.gz.sha256"):
                return FakeResponse(f"{checksum}  lex-{latest}.tar.gz\n".encode())
            if url.endswith(".tar.gz"):
                return FakeResponse(payload)
            raise AssertionError(url)
        return open_url

    def update(self, **kwargs):
        console = make_console()
        result = LEXMOD.release_update(console, base_dir=self.install, env=self.env, opener=self.opener(**kwargs),
                                       run_setup=lambda c, b: None)
        return result, console

    def read(self, rel):
        with open(os.path.join(self.install, rel)) as fh:
            return fh.read()

    def test_new_release_is_unpacked_over_the_folder(self):
        result, _ = self.update()
        self.assertEqual((result["status"], result["old"], result["new"]), ("updated", "2.6.8", "2.6.9"))
        self.assertEqual(self.read("lex.py"), lex_py("2.6.9"))
        self.assertEqual(self.read("runtime-data/lexicon.db"), "lexicon 2.6.9")
        self.assertEqual(self.read("runtime-data/creeds-aligned.json"), "creeds 2.6.9")
        self.assertEqual(self.read("my-notes.txt"), "keep me")
        # the replaced code file is kept in the backup folder
        backup = os.path.join(result["backup_dir"], "lex.py")
        with open(backup) as fh:
            self.assertEqual(fh.read(), lex_py("2.6.8"))

    def test_same_version_is_a_noop(self):
        result, _ = self.update(latest="v2.6.8")
        self.assertEqual(result["status"], "current")
        self.assertEqual(self.read("lex.py"), lex_py("2.6.8"))
        self.assertFalse(any(u.endswith(".tar.gz") for u in self.requested))

    def test_checksum_mismatch_installs_nothing(self):
        with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
            self.update(checksum="0" * 64)
        self.assertIn("checksum", str(ctx.exception))
        self.assertEqual(self.read("lex.py"), lex_py("2.6.8"))

    def test_unsafe_archive_installs_nothing(self):
        path = os.path.join(self.tmp, "evil.tar.gz")
        with tarfile.open(path, "w:gz") as tar:
            info = tarfile.TarInfo("lex-2.6.9/../../escaped.txt")
            data = b"x"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        with open(path, "rb") as fh:
            payload = fh.read()
        with self.assertRaises(LEXMOD.UpdateRefused):
            self.update(payload=payload)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escaped.txt")))
        self.assertEqual(self.read("lex.py"), lex_py("2.6.8"))

    def test_offline_refuses_with_a_clear_message(self):
        def offline(*args, **kwargs):
            raise OSError("offline")
        with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
            LEXMOD.release_update(make_console(), base_dir=self.install, env=self.env, opener=offline)
        self.assertIn("offline", str(ctx.exception))

    def test_update_command_reruns_new_code_for_the_data_step(self):
        manager = mock.Mock(data_before="2.6.8")
        calls = []
        console = make_console()
        code = LEXMOD.run_update_command(
            console, manager, env=self.env, base_dir=self.install,
            release_runner=lambda console, base_dir, env: LEXMOD.release_update(
                console, base_dir=base_dir, env=env, opener=self.opener(), run_setup=lambda c, b: None),
            runner=lambda argv, env=None, check=False: calls.append((argv, env)) or subprocess.CompletedProcess(argv, 0))
        self.assertEqual(code, 0)
        self.assertEqual(calls[0][1]["LEX_CLI_UPDATED_FROM"], "2.6.8")
        self.assertEqual(calls[0][1]["LEX_CLI_LATEST_VERSION"], "2.6.9")
        manager.perform_update.assert_not_called()


class RedirectTest(unittest.TestCase):
    """Every redirect hop must stay on https and an allowlisted host."""

    def fake_https(self, location):
        import email.message
        import urllib.request
        import urllib.response

        class FakeHTTPS(urllib.request.HTTPSHandler):
            hops = []

            def https_open(handler, req):
                FakeHTTPS.hops.append(req.full_url)
                if len(FakeHTTPS.hops) > 1:
                    response = urllib.response.addinfourl(io.BytesIO(b"final"), email.message.Message(), req.full_url, 200)
                    response.msg = "OK"
                    return response
                headers = email.message.Message()
                headers["Location"] = location
                response = urllib.response.addinfourl(io.BytesIO(b""), headers, req.full_url, 302)
                response.msg = "Found"
                return response

        FakeHTTPS.hops = []
        return FakeHTTPS

    def test_redirect_to_http_is_refused(self):
        handler = self.fake_https("http://objects.githubusercontent.com/x")
        with self.assertRaises(ValueError):
            LEXMOD._trusted_opener(handler).open("https://github.com/a")
        self.assertEqual(len(handler.hops), 1)

    def test_redirect_to_an_unlisted_host_is_refused(self):
        handler = self.fake_https("https://evil.example.com/x")
        with self.assertRaises(ValueError):
            LEXMOD._trusted_opener(handler).open("https://github.com/a")
        self.assertEqual(handler.hops, ["https://github.com/a"])

    def test_redirect_to_a_lookalike_host_is_refused(self):
        handler = self.fake_https("https://objects.githubusercontent.com.evil.example/x")
        with self.assertRaises(ValueError):
            LEXMOD._trusted_opener(handler).open("https://github.com/a")

    def test_redirect_to_githubs_release_hosts_is_followed(self):
        for host in ("objects.githubusercontent.com", "release-assets.githubusercontent.com", "github.com"):
            handler = self.fake_https(f"https://{host}/file")
            response = LEXMOD._trusted_opener(handler).open("https://github.com/a")
            self.assertEqual(response.read(), b"final")
            self.assertEqual(handler.hops[-1], f"https://{host}/file")

    def test_release_hosts_are_not_accepted_as_a_first_url(self):
        with self.assertRaises(ValueError):
            LEXMOD.open_trusted_https("https://objects.githubusercontent.com/x")
        with self.assertRaises(ValueError):
            LEXMOD.open_trusted_https("http://github.com/x")

    def test_open_trusted_https_uses_the_checking_opener(self):
        with mock.patch.object(LEXMOD, "_trusted_opener") as factory:
            LEXMOD.open_trusted_https("https://api.github.com/x", timeout=5)
        factory.return_value.open.assert_called_once_with("https://api.github.com/x", timeout=5)


class ReleaseHardeningTest(ReleaseInstallTest):
    """Archive size cap, rollback, version check and backup hygiene."""

    def test_oversized_archive_is_refused_before_extracting(self):
        with mock.patch.object(LEXMOD, "MAX_EXTRACTED_BYTES", 10):
            with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
                self.update()
        self.assertIn("more than expected", str(ctx.exception))
        self.assertEqual(self.read("lex.py"), lex_py("2.6.8"))

    def test_too_many_members_is_refused(self):
        with mock.patch.object(LEXMOD, "MAX_EXTRACTED_MEMBERS", 2):
            with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
                self.update()
        self.assertIn("too many files", str(ctx.exception))

    def test_normal_archive_is_still_extracted_with_the_data_filter(self):
        with mock.patch.object(tarfile.TarFile, "extractall", autospec=True, side_effect=tarfile.TarFile.extractall) as spy:
            self.update()
        self.assertEqual(spy.call_args.kwargs["filter"], "data")

    def test_failure_mid_replace_restores_everything_and_refuses(self):
        real_replace = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:  # the second file fails
                raise OSError("disk full")
            return real_replace(src, dst)

        with mock.patch.object(LEXMOD.os, "replace", flaky):
            with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
                self.update()
        self.assertIn("put back", str(ctx.exception))
        self.assertEqual(self.read("lex.py"), lex_py("2.6.8"))
        self.assertEqual(self.read("runtime-data/lexicon.db"), "lexicon 2.6.8")
        self.assertEqual(self.read("my-notes.txt"), "keep me")
        self.assertFalse(os.path.exists(os.path.join(self.install, "runtime-data", "creeds-aligned.json")))
        leftovers = [n for _, _, fs in os.walk(self.install) for n in fs if n.endswith(".lex-new")]
        self.assertEqual(leftovers, [])

    def test_version_inside_the_archive_must_match_the_tag(self):
        payload = self.archive("2.6.9")
        # a v2.6.10 tag whose tarball actually holds 2.6.9 code
        src = os.path.join(self.tmp, "mismatch", "lex-2.6.10")
        os.makedirs(os.path.join(src, "runtime-data"))
        with open(os.path.join(src, "lex.py"), "w") as fh:
            fh.write(lex_py("2.6.9"))
        path = os.path.join(self.tmp, "mismatch.tar.gz")
        with tarfile.open(path, "w:gz") as tar:
            tar.add(src, arcname="lex-2.6.10")
        with open(path, "rb") as fh:
            payload = fh.read()
        with self.assertRaises(LEXMOD.UpdateRefused) as ctx:
            self.update(latest="v2.6.10", payload=payload)
        self.assertIn("not 2.6.10", str(ctx.exception))
        self.assertEqual(self.read("lex.py"), lex_py("2.6.8"))

    def test_data_file_backups_are_dropped_after_success_code_backups_kept(self):
        result, _ = self.update()
        found = [os.path.relpath(os.path.join(d, f), result["backup_dir"])
                 for d, _, fs in os.walk(result["backup_dir"]) for f in fs]
        self.assertEqual(found, ["lex.py"])


class BackupHygieneTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-bk-")
        self.patch = mock.patch.dict(os.environ, {"HOME": self.home})
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def test_backup_root_is_private_and_each_run_gets_a_unique_folder(self):
        first = LEXMOD.update_backup_dir(now=0)
        second = LEXMOD.update_backup_dir(now=0)  # same second, same pid
        self.assertNotEqual(first, second)
        self.assertEqual(os.path.dirname(first), os.path.join(self.home, ".lex_backups"))
        if os.name != "nt":
            self.assertEqual(os.stat(os.path.dirname(first)).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(first).st_mode & 0o777, 0o700)
        self.assertIn(str(os.getpid()), os.path.basename(first))

    def test_an_existing_loose_backup_root_is_tightened(self):
        root = os.path.join(self.home, ".lex_backups")
        os.makedirs(root, mode=0o755)
        os.chmod(root, 0o755)
        LEXMOD.update_backup_dir()
        if os.name != "nt":
            self.assertEqual(os.stat(root).st_mode & 0o777, 0o700)

    def test_an_existing_backup_file_is_never_overwritten(self):
        folder = LEXMOD.update_backup_dir()
        first = LEXMOD._backup_slot(folder, "runtime-data/a.json")
        with open(first, "w") as fh:
            fh.write("first")
        second = LEXMOD._backup_slot(folder, "runtime-data/a.json")
        self.assertNotEqual(first, second)
        with open(second, "w") as fh:
            fh.write("second")
        with open(first) as fh:
            self.assertEqual(fh.read(), "first")

    def test_an_empty_backup_folder_is_not_left_behind(self):
        folder = LEXMOD.update_backup_dir()
        LEXMOD._drop_if_empty(folder)
        self.assertFalse(os.path.exists(folder))


@unittest.skipUnless(GIT, "git is required")
class GitFetchTest(GitInstallTest):
    def test_fetch_puts_double_dash_before_the_remote(self):
        self.release_269()
        seen = []
        real = LEXMOD._git

        def spy(base_dir, *args, **kwargs):
            seen.append(args)
            return real(base_dir, *args, **kwargs)

        with mock.patch.object(LEXMOD, "_git", spy):
            self.update()
        fetches = [a for a in seen if a and a[0] == "fetch"]
        self.assertEqual(len(fetches), 1)
        self.assertEqual(fetches[0][-2:], ("--", "origin"))

    def test_a_remote_name_that_looks_like_an_option_is_refused(self):
        self.git(self.install, "config", "branch.main.remote", "-oops")
        self.git(self.install, "config", "branch.main.merge", "refs/heads/main")
        with mock.patch.object(LEXMOD, "_git_out", side_effect=[(0, "main", ""), (0, "-oops/main", "")]):
            with self.assertRaises(LEXMOD.UpdateRefused):
                self.update()


class SummaryAndMarkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lex-marker-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_data_version_is_remembered_between_updates(self):
        manager = LEXMOD.LexUpdateManager(make_console(), data_dir=self.tmp)
        self.assertIsNone(manager.data_before)
        manager.write_data_version("2.6.9")
        self.assertEqual(LEXMOD.LexUpdateManager(make_console(), data_dir=self.tmp).data_before, "2.6.9")

    def test_summary_shows_old_to_new_for_cli_and_data_together(self):
        console = make_console()
        manager = mock.Mock(data_before="2.6.8", remote_version="2.6.9", data_changed=True)
        info = {"cli_version": "2.6.9", "latest": "2.6.9", "status": "updated", "updated_from": "2.6.8", "command": None}
        code = LEXMOD.print_update_summary(console, manager, True, cli=info)
        out = text_of(console)
        self.assertEqual(code, 0)
        self.assertIn("Lex CLI:  2.6.8 → 2.6.9 (updated)", out)
        self.assertIn("Lex data: 2.6.8 → 2.6.9 (updated)", out)

    def test_a_setup_warning_is_shown_and_exits_nonzero(self):
        console = make_console()
        manager = mock.Mock(data_before=None, remote_version="2.6.9", data_changed=False)
        info = {"cli_version": "2.6.9", "latest": "2.6.9", "status": "updated", "updated_from": "2.6.8",
                "command": None, "warning": "setup.sh failed (boom). Run ./setup.sh yourself to see why."}
        self.assertEqual(LEXMOD.print_update_summary(console, manager, True, cli=info), 1)
        self.assertIn("setup.sh failed", text_of(console))


class ThreeSpellingsTest(unittest.TestCase):
    """`lex update`, `lex --update` and `lex -update` all reach the same code."""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lex-spell-")
        self.env = mock.patch.dict(os.environ, {"HOME": self.home, "LEX_NO_COLOR": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def dispatch(self, *argv):
        with mock.patch.object(LEXMOD, "run_update_command", return_value=0) as run, \
                mock.patch.object(sys, "argv", ["lex", *argv]), \
                self.assertRaises(SystemExit) as exit_info:
            LEXMOD.main()
        self.assertEqual(exit_info.exception.code, 0)
        return run

    def test_lex_update(self):
        self.dispatch("update").assert_called_once()

    def test_lex_double_dash_update(self):
        self.dispatch("--update").assert_called_once()

    def test_lex_single_dash_update(self):
        self.dispatch("-update").assert_called_once()

    def test_help_and_docs_name_all_three_spellings(self):
        result = subprocess.run([sys.executable, LEX, "--help"], capture_output=True, text=True, timeout=60)
        flat = " ".join(ANSI.sub("", result.stdout).split())
        for spelling in ("lex update", "lex --update", "lex -update"):
            self.assertIn(spelling, flat)
        for doc in ("README.md", os.path.join("docs", "get-started.md"), os.path.join("docs", "lex-docs.md")):
            with open(os.path.join(ROOT, doc), encoding="utf-8") as fh:
                text = fh.read()
            for spelling in ("lex update", "lex --update", "lex -update"):
                self.assertIn(spelling, text, f"{doc} should mention `{spelling}`")


if __name__ == "__main__":
    unittest.main()

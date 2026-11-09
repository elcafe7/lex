"""Regression tests for issue #2: study mode and the interlinear data.

Study mode reads runtime-data/esv-data/data/esv/esv-interlinear.json and
runtime-data/esv-data/data/interlinear/strongs.json. Since 2026-04-20 those
files ship in git (and therefore in the npm release archive), but two gaps
remained:

* When lex.py runs without a bundle and uses the ~/bible-lexicon-data
  fallback, the JSON loader rejected every file outside runtime-data/, so
  study mode said "No local interlinear data found" even with the data there.
* When the files are missing, the message gave no path and no fix.

Run: python3 -m unittest discover -s tests
Each test uses a throwaway HOME and a throwaway copy of lex.py; the real
checkout's runtime-data is linked, never modified.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
RUNTIME = os.path.join(ROOT, "runtime-data")
ESV_DATA = "esv-data"
INTERLINEAR_FILES = (
    os.path.join("esv-data", "data", "esv", "esv-interlinear.json"),
    os.path.join("esv-data", "data", "interlinear", "strongs.json"),
)
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
OLD_MESSAGE = "No local interlinear data found for this verse."


def link_or_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build_data_dir(target, with_interlinear):
    """Symlink every runtime-data entry except esv-data into target.

    The interlinear JSON is hard-linked (or copied) rather than symlinked so
    its real path stays inside target, as it would on a real install.
    """
    os.makedirs(target, exist_ok=True)
    for name in os.listdir(RUNTIME):
        if name == ESV_DATA:
            continue
        os.symlink(os.path.join(RUNTIME, name), os.path.join(target, name))
    if with_interlinear:
        for rel in INTERLINEAR_FILES:
            link_or_copy(os.path.join(RUNTIME, rel), os.path.join(target, rel))


class InterlinearDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lex-test-interlinear-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_study(self, lex_path, ref="John 1:1"):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LEX_")}
        env.update({"HOME": self.home, "LEX_NO_COLOR": "1", "COLUMNS": "200", "TERM": "dumb"})
        proc = subprocess.run(
            [sys.executable, lex_path, "study", ref, "--no-animate"],
            cwd=os.path.dirname(lex_path), env=env, input="q\n",
            capture_output=True, text=True, timeout=120,
        )
        out = ANSI.sub("", proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", out)
        return out

    def copy_lex(self, directory):
        os.makedirs(directory, exist_ok=True)
        target = os.path.join(directory, "lex.py")
        shutil.copy2(LEX, target)
        return target

    @unittest.skipUnless(all(os.path.isfile(os.path.join(RUNTIME, rel)) for rel in INTERLINEAR_FILES),
                         "checkout has no bundled interlinear data")
    def test_bundled_clone_shows_interlinear_tokens(self):
        out = self.run_study(LEX)
        self.assertIn("G3056", out)
        self.assertNotIn(OLD_MESSAGE, out)

    def test_home_fallback_data_dir_is_readable(self):
        build_data_dir(os.path.join(self.home, "bible-lexicon-data"), with_interlinear=True)
        lex = self.copy_lex(os.path.join(self.tmp, "standalone"))
        out = self.run_study(lex)
        self.assertIn("G3056", out, out)
        self.assertNotIn(OLD_MESSAGE, out)

    def test_missing_interlinear_data_gives_actionable_message(self):
        clone = os.path.join(self.tmp, "clone")
        lex = self.copy_lex(clone)
        build_data_dir(os.path.join(clone, "runtime-data"), with_interlinear=False)
        out = self.run_study(lex)
        self.assertIn("Interlinear study data is not installed", out, out)
        self.assertIn("esv-interlinear.json", out)
        self.assertIn("strongs.json", out)
        self.assertIn("lex update", out)
        self.assertNotIn(OLD_MESSAGE, out)


if __name__ == "__main__":
    unittest.main()

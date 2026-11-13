"""Guards for scripts/build_windows.sh (Scorecard Pinned-Dependencies, alert #60).

Every pip install in the Windows build helper must go through the
hash-locked requirements file, and every pin in that file must carry a hash.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_windows.sh"
LOCKFILE = ROOT / ".github" / "requirements" / "windows-build-requirements.txt"


class BuildWindowsPinningTests(unittest.TestCase):
    def test_every_pip_install_requires_hashes(self):
        lines = [
            line.strip()
            for line in SCRIPT.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith("#")
        ]
        installs = [line for line in lines if re.search(r"\bpip\b.*\binstall\b", line)]
        self.assertTrue(installs, "build_windows.sh should install its build dependencies")
        for line in installs:
            self.assertIn("--require-hashes", line, line)
            self.assertIn("-r ", line, line)

    def test_lockfile_pins_have_hashes(self):
        text = LOCKFILE.read_text(encoding="utf-8")
        blocks = re.split(r"\n(?=[A-Za-z0-9])", text)
        pins = [block for block in blocks if re.match(r"[A-Za-z0-9][\w.-]*==", block)]
        self.assertTrue(any(block.startswith("pyinstaller==") for block in pins))
        for block in pins:
            self.assertIn("--hash=sha256:", block, block.splitlines()[0])

    def test_no_hardcoded_workstation_paths(self):
        self.assertNotIn("/home/", SCRIPT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

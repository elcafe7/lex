"""Replay the Atheris seed corpora through the fuzz harness checks (issue #36).

Atheris itself only runs in .github/workflows/fuzz.yml; this test needs no
fuzzer. It imports the harness modules (their `main` is not called) and feeds
every seed in fuzz/corpus/ to the same invariant checks the fuzzer uses, so a
regression in argv normalization, search scopes or path confinement shows up
in the ordinary test suite too.

Run: python3 -m unittest tests.test_fuzz_harness
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUZZ_DIR = os.path.join(ROOT, "fuzz")
CORPUS = os.path.join(FUZZ_DIR, "corpus")


def load_harness(name):
    if FUZZ_DIR not in sys.path:
        sys.path.insert(0, FUZZ_DIR)
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", os.path.join(FUZZ_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seeds(target):
    folder = os.path.join(CORPUS, target)
    for name in sorted(os.listdir(folder)):
        with open(os.path.join(folder, name), "rb") as handle:
            yield name, handle.read()


class FuzzArgvSeeds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = load_harness("fuzz_argv")

    def test_seed_corpus(self):
        replayed = 0
        for name, data in seeds("argv"):
            with self.subTest(seed=name):
                self.harness.test_one_input(data)
                replayed += 1
        self.assertGreater(replayed, 5)

    def test_known_scopes_parse(self):
        _, scope = self.harness.AGENT.parse_search_query_and_scope("grace -nt")
        self.assertIsNotNone(scope)
        _, scope = self.harness.AGENT.parse_search_query_and_scope("love -genesis-exodus")
        self.assertEqual(scope["books"][:2], ["Genesis", "Exodus"])

    def test_end_of_options_untouched(self):
        self.harness.check_argv(["-json", "--", "-json", "--h"])
        self.assertEqual(
            self.harness.lex.normalize_argv(["-json", "--", "-json"], self.harness.PARSER),
            ["--json", "--", "-json"],
        )


class FuzzSafePathSeeds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = load_harness("fuzz_safe_paths")

    def test_seed_corpus(self):
        replayed = 0
        for name, data in seeds("safe_paths"):
            with self.subTest(seed=name):
                self.harness.test_one_input(data)
                replayed += 1
        self.assertGreater(replayed, 5)

    def test_escape_attempts_rejected(self):
        lex = self.harness.lex
        for name in ("../base-evil/secret.txt", "escape/secret.txt", "/etc/passwd", "%2e%2e/x"):
            with self.subTest(name=name):
                with self.assertRaises(lex.UnsafePathError):
                    lex.safe_join(self.harness.BASE, name)


if __name__ == "__main__":
    unittest.main()

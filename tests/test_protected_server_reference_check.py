import unittest

from scripts.protected_server_reference_check import added_locations


class ProtectedServerReferenceCheckTests(unittest.TestCase):
    def test_reports_added_references_with_locations(self):
        term = "po" + "eta"
        diff = "\n".join(
            [
                "diff --git a/example.txt b/example.txt",
                "+++ b/example.txt",
                "@@ -0,0 +8,2 @@",
                f"+https://{term}.icu/private",
                "+ordinary text",
            ]
        )
        self.assertEqual(list(added_locations(diff)), [("example.txt", 8)])

    def test_ignores_removed_lines(self):
        term = "po" + "eta"
        diff = "\n".join(
            [
                "diff --git a/example.txt b/example.txt",
                "+++ b/example.txt",
                "@@ -8,1 +8,1 @@",
                f"-https://{term}.icu/removed",
                "+replacement",
            ]
        )
        self.assertEqual(list(added_locations(diff)), [])

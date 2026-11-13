"""Numbered, line-aligned original/English creed lines (issue #12).

The four bilingual documents (Apostles', Nicene, Athanasian, Chalcedonian) are
stored as aligned (original, English) line pairs. These tests hold the
acceptance criteria: pairs number continuously, every line has both columns,
no word of either text is lost or changed, the narrow layout keeps each pair
together, and documents without an original display as before.

Run: python3 -m pytest tests/test_creed_alignment.py
"""
import importlib.util
import io
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX = os.path.join(ROOT, "lex.py")
# The original-language text as it was stored before the split, one paragraph per section.
ORIGINALS_BEFORE = os.path.join(ROOT, "tests", "fixtures", "creed_originals_paragraphs.json")
ALIGNED_JSON = os.path.join(ROOT, "runtime-data", "creeds-aligned.json")
# display_creed_document() output for Westminster at width 100, captured from main before #12.
WESTMINSTER_SNAPSHOT = os.path.join(ROOT, "tests", "fixtures", "westminster_confession_w100.txt")
BILINGUAL = ["The Apostles' Creed", "The Nicene Creed", "Athanasian Creed", "Chalcedonian Definition"]


def load_lex_module():
    spec = importlib.util.spec_from_file_location("lex_creed_alignment_under_test", LEX)
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv
    sys.argv = ["lex"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    return module


def squash(text):
    return " ".join((text or "").split())


class CreedAlignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = load_lex_module()
        cls.agent = cls.lex.LexAgent(bible_id="kjv")
        with open(ORIGINALS_BEFORE, encoding="utf-8") as fh:
            cls.originals_before = json.load(fh)

    def render(self, width, func, *args):
        buffer = io.StringIO()
        old = self.lex.console
        self.lex.console = self.lex.Console(
            file=buffer, theme=self.lex.custom_theme, no_color=True, color_system=None,
            width=width, emoji=False, highlight=False, force_terminal=False,
        )
        try:
            func(*args)
        finally:
            self.lex.console = old
        return buffer.getvalue()

    def aligned(self, topic):
        return self.agent.creed_aligned_sections(topic, self.agent.build_creed_sections(topic))

    def test_apostles_creed_opens_with_numbered_pair(self):
        first = self.aligned("The Apostles' Creed")[0]["lines"][0]
        self.assertEqual(first["n"], 1)
        self.assertTrue(first["original"].startswith("Credo in Deum Patrem omnipotentem"))
        self.assertTrue(first["english"].startswith("I believe in God, the Father almighty"))

    def test_every_number_once_with_both_columns(self):
        for topic in BILINGUAL:
            with self.subTest(topic=topic):
                aligned = self.aligned(topic)
                numbers = [line["n"] for section in aligned for line in section["lines"]]
                self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
                self.assertGreater(len(numbers), len(aligned), "sections should be split into lines")
                for section in aligned:
                    stored = self.lex.CREED_ORIGINALS[topic]["sections"][section["title"]]
                    # Same number of original and English lines in every section.
                    self.assertEqual(len(section["lines"]), len(stored), section["title"])
                    for line in section["lines"]:
                        self.assertTrue(line["original"] and line["original"].strip(), line)
                        self.assertTrue(line["english"] and line["english"].strip(), line)

    def test_no_words_lost_or_changed(self):
        for topic in BILINGUAL:
            sections = self.agent.build_creed_sections(topic)
            stored = self.lex.CREED_ORIGINALS[topic]["sections"]
            self.assertEqual([s["title"] for s in sections], list(stored))
            for section in sections:
                with self.subTest(topic=topic, section=section["title"]):
                    pairs = stored[section["title"]]
                    english = squash("\n\n".join(section["body_parts"]))
                    self.assertEqual(squash(" ".join(e for _o, e in pairs)), english)
                    self.assertEqual(squash(" ".join(o for o, _e in pairs)), squash(self.originals_before[topic][section["title"]]))
                    original, _language = self.agent.get_creed_original(topic, section["title"])
                    self.assertEqual(squash(original), squash(self.originals_before[topic][section["title"]]))

    def test_changed_english_keeps_section_whole(self):
        sections = self.agent.build_creed_sections("The Apostles' Creed")
        sections[0] = dict(sections[0], body_parts=["I believe in God the Father, maker of all."])
        aligned = self.agent.creed_aligned_sections("The Apostles' Creed", sections)
        self.assertEqual(len(aligned[0]["lines"]), 1)
        self.assertEqual(aligned[0]["lines"][0]["english"], "I believe in God the Father, maker of all.")
        self.assertEqual(aligned[1]["lines"][0]["n"], 2)

    def test_wide_view_has_number_original_and_english_columns(self):
        topic = "The Nicene Creed"
        out = self.render(140, self.agent.display_creed_document, topic, self.agent.build_creed_sections(topic))
        self.assertRegex(out, r"#\s+│?\s*Greek\s+│?\s*#\s+│?\s*English")
        for title in self.lex.CREED_ORIGINALS[topic]["sections"]:
            self.assertIn(title, out)
        row = next(l for l in out.splitlines() if re.match(r"^\W*1\W", l))
        # The number labels both sides: before the Greek and again before the English.
        self.assertRegex(row, r"^\W*1\W+Πιστεύομεν.*\W1\W+We believe in one God")
        for line in self.aligned(topic)[0]["lines"]:
            self.assertTrue(any(
                re.search(rf"^\W*{line['n']}\W.*\W{line['n']}\W+{re.escape(line['english'].split()[0])}", l)
                for l in out.splitlines()
            ), line)

    def test_narrow_view_stacks_each_pair(self):
        topic = "Athanasian Creed"
        out = self.render(60, self.agent.display_creed_document, topic, self.agent.build_creed_sections(topic))
        lines = out.splitlines()
        aligned = self.aligned(topic)
        for section in aligned:
            for line in section["lines"]:
                head = re.compile(rf"^\s*{line['n']} {re.escape(line['original'].split()[0])}")
                index = next(i for i, text in enumerate(lines) if head.match(text))
                # Numbered original, then the same number with its English, before
                # the next number or section starts.
                blocks = [[lines[index]]]
                for text in lines[index + 1:]:
                    if "─" in text or (re.match(r"^\s*\d+ ", text) and len(blocks) == 2):
                        break
                    if re.match(r"^\s*\d+ ", text):
                        blocks.append([])
                    blocks[-1].append(text)
                self.assertEqual(len(blocks), 2, blocks)
                self.assertEqual(squash(" ".join(blocks[0])), f"{line['n']} {squash(line['original'])}")
                self.assertEqual(squash(" ".join(blocks[1])), f"{line['n']} {squash(line['english'])}")

    def test_missing_original_line_keeps_its_number(self):
        aligned = [{"title": "Part", "lines": [{"n": 7, "original": None, "english": "Only English here."}]}]
        for width in (140, 60):
            out = self.render(width, self.agent.render_creed_aligned, "Latin", aligned)
            self.assertIn("[original not yet loaded]", out)
            self.assertRegex(out, r"(?m)^\W*7\W")

    def test_documents_without_original_render_unchanged(self):
        topic = "Westminster Confession of Faith"
        self.assertIsNone(self.agent.creed_aligned_sections(topic, self.agent.build_creed_sections(topic)))
        self.assertEqual(self.agent.get_creed_original(topic, "Of the Holy Scripture"), (None, None))
        calls = []
        original = self.agent.render_creed_aligned
        self.agent.render_creed_aligned = lambda *a, **k: calls.append(a)
        try:
            sections = self.agent.build_creed_sections(topic)[:2]
            out = self.render(120, self.agent.display_creed_document, topic, sections)
        finally:
            self.agent.render_creed_aligned = original
        self.assertEqual(calls, [])
        self.assertNotIn("[original not yet loaded]", out)
        self.assertIn(topic, out)

    def test_json_sections_carry_numbered_lines(self):
        doc = self.lex.json_creed_document(self.agent, "Athanasian Creed", "")
        numbers = [line["n"] for section in doc["sections"] for line in section["lines"]]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        first = doc["sections"][0]
        self.assertEqual(squash(" ".join(l["english"] for l in first["lines"])), squash(first["markdown"]))
        self.assertEqual(squash(" ".join(l["original"] for l in first["lines"])), squash(first["original"]["text"]))
        other = self.lex.json_creed_document(self.agent, "Westminster Shorter Catechism", "")
        self.assertIsNone(other["sections"][0]["lines"])

    def test_westminster_output_matches_snapshot(self):
        topic = "Westminster Confession of Faith"
        out = self.render(100, self.agent.display_creed_document, topic, self.agent.build_creed_sections(topic))
        with open(WESTMINSTER_SNAPSHOT, encoding="utf-8") as fh:
            self.assertEqual(out, fh.read())

    def test_shared_json_file_is_the_source(self):
        with open(ALIGNED_JSON, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertEqual(raw["schema"], 1)
        self.assertEqual(sorted(raw["documents"]), sorted(BILINGUAL))
        for topic, doc in raw["documents"].items():
            with self.subTest(topic=topic):
                numbers = [row["n"] for rows in doc["sections"].values() for row in rows]
                self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
                for rows in doc["sections"].values():
                    for row in rows:
                        self.assertEqual(set(row), {"n", "orig", "eng"})
                        self.assertTrue(row["orig"].strip() and row["eng"].strip(), row)
                self.assertEqual(
                    self.lex.CREED_ORIGINALS[topic]["sections"],
                    {title: [(r["orig"], r["eng"]) for r in rows] for title, rows in doc["sections"].items()},
                )

    def test_shared_json_ships_with_cli(self):
        # The npm release archive is `git archive HEAD` and data updates follow manifest.json.
        import subprocess
        if not os.path.isdir(os.path.join(ROOT, ".git")) and not os.path.isfile(os.path.join(ROOT, ".git")):
            self.skipTest("not a git checkout")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "runtime-data/creeds-aligned.json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(tracked.returncode, 0, tracked.stderr)
        with open(os.path.join(ROOT, "manifest.json"), encoding="utf-8") as fh:
            self.assertIn("runtime-data/creeds-aligned.json", json.load(fh)["assets"])

    def test_missing_or_bad_json_falls_back_to_english_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "none.json")
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write('{"schema": 1, "documents": {"X": {"language": "Latin", "sections": {"A": [{"n": 2, "orig": "a", "eng": "b"}]}}}}')
            self.assertEqual(self.lex.load_creed_originals([missing, bad]), {})
            self.assertEqual(self.lex.load_creed_originals([missing, ALIGNED_JSON]), self.lex.CREED_ORIGINALS)

    def test_plain_and_no_color_output_keeps_pairs(self):
        import subprocess
        env = dict(os.environ, NO_COLOR="1", COLUMNS="60")
        for args in (["--plain", "creed", "apostles"], ["creed", "apostles"]):
            with self.subTest(args=args):
                out = subprocess.run(
                    [sys.executable, LEX, *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
                ).stdout
                # NO_COLOR drops colours (Rich may keep bold); --plain drops all styling.
                self.assertIsNone(re.search(r"\x1b\[[0-9;]*(?:3[0-9]|4[0-9]|9[0-7])[;m]", out))
                out = re.sub(r"\x1b\[[0-9;]*m", "", out)
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                i = lines.index(next(l for l in lines if l.startswith("1 Credo in Deum Patrem omnipotentem")))
                self.assertTrue(lines[i + 1].startswith("1 I believe in God, the Father almighty"), lines[i:i + 2])
                wide = subprocess.run(
                    [sys.executable, LEX, *args], cwd=ROOT, env=dict(env, COLUMNS="140"),
                    capture_output=True, text=True, timeout=120,
                ).stdout
                self.assertRegex(re.sub(r"\x1b\[[0-9;]*m", "", wide),
                                 r"(?m)^\W*1\W+Credo in Deum Patrem omnipotentem,\W+1\W+I believe in God")


if __name__ == "__main__":
    unittest.main()

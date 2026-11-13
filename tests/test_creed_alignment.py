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
        self.assertRegex(out, r"#\s+│?\s*Greek\s+│?\s*English")
        for title in self.lex.CREED_ORIGINALS[topic]["sections"]:
            self.assertIn(title, out)
        row = next(l for l in out.splitlines() if re.match(r"^\W*1\W", l))
        self.assertIn("Πιστεύομεν", row)
        self.assertIn("We believe in one God", row)

    def test_narrow_view_stacks_each_pair(self):
        topic = "Athanasian Creed"
        out = self.render(60, self.agent.display_creed_document, topic, self.agent.build_creed_sections(topic))
        lines = out.splitlines()
        aligned = self.aligned(topic)
        for section in aligned:
            for line in section["lines"]:
                head = re.compile(rf"^\s*{line['n']} {re.escape(line['original'].split()[0])}")
                index = next(i for i, text in enumerate(lines) if head.match(text))
                # Original, then its English, before the next number or section starts.
                block = [lines[index]]
                for text in lines[index + 1:]:
                    if re.match(r"^\s*\d+ ", text) or "─" in text:
                        break
                    block.append(text)
                joined = squash(" ".join(block))
                self.assertEqual(joined, f"{line['n']} {squash(line['original'])} {squash(line['english'])}")

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


if __name__ == "__main__":
    unittest.main()

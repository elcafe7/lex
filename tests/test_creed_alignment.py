"""Numbered, line-aligned original/English creed lines (issue #12).

The four bilingual documents (Apostles', Nicene, Athanasian, Chalcedonian) are
stored as aligned (original, English) line pairs. These tests hold the
acceptance criteria: pairs number continuously, every line has both columns,
no word of either text is lost or changed, the narrow layout keeps each pair
together, and documents without an original display as before.

Run: python3 -m pytest tests/test_creed_alignment.py
"""
import importlib.util
import itertools
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

    def test_wide_table_columns_never_drift(self):
        """Every table line has the same cell width and the column gaps sit at
        identical offsets on every row (no ragged borders or separators)."""
        from rich.cells import cell_len
        ansi = re.compile(r"\x1b\[[0-9;]*m")
        for topic in BILINGUAL:
            for width in (80, 100, 140):
                with self.subTest(topic=topic, width=width):
                    out = ansi.sub("", self.render(width, self.agent.display_creed_document, topic,
                                                    self.agent.build_creed_sections(topic)))
                    lines = out.splitlines()
                    language = self.lex.CREED_ORIGINALS[topic]["language"]
                    head = next(i for i, l in enumerate(lines) if re.match(rf"^\s*#\s+{language}\s+#\s+English", l))
                    end = next((i for i in range(head, len(lines)) if lines[i].lstrip().startswith("╭")), len(lines))
                    table = [l for l in lines[head:end] if l.strip()]
                    self.assertGreater(len(table), 10)
                    header = table[0]
                    hashes = [m.start() for m in re.finditer("#", header)]
                    starts = [header.index(language), header.index("English")]
                    self.assertEqual(len(hashes), 2)
                    for row in table:
                        # Same cell width as the console, and nothing measures differently from its length.
                        self.assertEqual(cell_len(row), width, row)
                        self.assertEqual(cell_len(row), len(row), row)
                        if set(row.strip()) == {"─"}:
                            continue
                        # Gaps before each text column and after each number column are blank.
                        for col in starts:
                            self.assertEqual(row[col - 1], " ", row)
                        for h in hashes:
                            self.assertEqual(row[h + 1], " ", row)
                        if row is header:
                            continue
                        # Numbers are right-aligned under their "#" on both sides, and match.
                        left = row[:hashes[0] + 1].strip()
                        right = re.search(r"(\d*)$", row[:hashes[1] + 1]).group(1)
                        self.assertTrue(left == "" or left.isdigit(), row)
                        self.assertEqual(left, right, row)
                        self.assertEqual(row[hashes[1] - len(right)], " ", row)

    def test_creed_text_is_nfc_and_single_width(self):
        import unicodedata
        from rich.cells import cell_len
        for topic, doc in self.lex.CREED_ORIGINALS.items():
            for title, pairs in doc["sections"].items():
                for original, english in pairs:
                    for text in (original, english):
                        self.assertEqual(unicodedata.normalize("NFC", text), text)
                        self.assertEqual(cell_len(self.lex.creed_cell_text(text)), len(self.lex.creed_cell_text(text)), text)
        decomposed = unicodedata.normalize("NFD", "Πιστεύομεν")
        self.assertEqual(self.lex.creed_cell_text(decomposed), "Πιστεύομεν")

    def test_section_titles_in_both_text_columns(self):
        topic = "The Nicene Creed"
        out = self.render(140, self.agent.display_creed_document, topic, self.agent.build_creed_sections(topic))
        for title in self.lex.CREED_ORIGINALS[topic]["sections"]:
            self.assertTrue(any(l.count(title) == 2 for l in out.splitlines()), title)

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
        self.assertNotIn("lines", other["sections"][0])

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

    def test_deeply_nested_or_huge_json_falls_back(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            deep = os.path.join(tmp, "deep.json")
            with open(deep, "w", encoding="utf-8") as fh:
                fh.write('{"schema": 1, "documents": ' + "[" * 200000 + "]" * 200000 + "}")
            self.assertEqual(self.lex.load_creed_originals([deep]), {})
            self.assertEqual(self.lex.load_creed_originals([deep, ALIGNED_JSON]), self.lex.CREED_ORIGINALS)
            with mock.patch.object(self.lex.json, "load", side_effect=MemoryError):
                self.assertEqual(self.lex.load_creed_originals([ALIGNED_JSON]), {})

    def test_updated_data_dir_copy_wins_over_bundled(self):
        import tempfile
        from unittest import mock
        updated = {"schema": 1, "documents": {"Updated Creed": {"language": "Latin", "sections": {
            "Only": [{"n": 1, "orig": "Credo.", "eng": "I believe."}]}}}}
        with tempfile.TemporaryDirectory() as data_dir, tempfile.TemporaryDirectory() as bundled_dir:
            with open(os.path.join(bundled_dir, "creeds-aligned.json"), "w", encoding="utf-8") as fh, \
                    open(ALIGNED_JSON, encoding="utf-8") as src:
                fh.write(src.read())
            with mock.patch.object(self.lex, "DATA_DIR", data_dir), \
                    mock.patch.object(self.lex, "RUNTIME_DATA_DIR", bundled_dir):
                # No updated copy yet: the bundled file is used.
                self.assertEqual(self.lex.load_creed_originals(), self.lex.CREED_ORIGINALS)
                with open(os.path.join(data_dir, "creeds-aligned.json"), "w", encoding="utf-8") as fh:
                    json.dump(updated, fh)
                self.assertEqual(self.lex.load_creed_originals(),
                                 {"Updated Creed": {"language": "Latin", "sections": {"Only": [("Credo.", "I believe.")]}}})
                # A broken updated copy falls back to the bundled one.
                with open(os.path.join(data_dir, "creeds-aligned.json"), "w", encoding="utf-8") as fh:
                    fh.write("{not json")
                self.assertEqual(self.lex.load_creed_originals(), self.lex.CREED_ORIGINALS)

    def test_json_cli_for_bilingual_and_westminster(self):
        import subprocess
        env = dict(os.environ, COLUMNS="100", TERM="xterm-256color")
        cases = {
            "apostles": "The Apostles' Creed", "nicene": "The Nicene Creed",
            "athanasian": "Athanasian Creed", "chalcedon": "Chalcedonian Definition",
            "westminster confession": "Westminster Confession of Faith",
        }
        for query, topic in cases.items():
            outputs = []
            for flag in ("--json", "-json"):
                with self.subTest(query=query, flag=flag):
                    proc = subprocess.run(
                        [sys.executable, LEX, flag, "creed", *query.split()], cwd=ROOT, env=env,
                        capture_output=True, text=True, timeout=120,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertNotIn("\x1b", proc.stdout)
                    payload = json.loads(proc.stdout)
                    outputs.append(payload)
                    self.assertEqual(payload["command"], "creed")
                    doc = payload["document"]
                    self.assertEqual(doc["topic"], topic)
                    if topic not in BILINGUAL:
                        # Same section keys as before #12: no `lines`.
                        for section in doc["sections"]:
                            self.assertEqual(set(section), {"title", "text", "markdown", "proofs", "original"})
                            self.assertIsNone(section["original"])
                        continue
                    stored = self.lex.CREED_ORIGINALS[topic]["sections"]
                    numbers = []
                    for section in doc["sections"]:
                        lines = section["lines"]
                        self.assertEqual(len(lines), len(stored[section["title"]]), section["title"])
                        for line in lines:
                            self.assertEqual(set(line), {"n", "original", "english"})
                            self.assertTrue(line["original"].strip() and line["english"].strip())
                        numbers += [line["n"] for line in lines]
                        self.assertEqual(squash(" ".join(l["english"] for l in lines)), squash(section["markdown"]))
                        self.assertEqual(squash(" ".join(l["original"] for l in lines)), squash(section["original"]["text"]))
                    self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
            self.assertEqual(outputs[0], outputs[1], query)

    def test_plain_and_no_color_output_keeps_pairs(self):
        import subprocess
        from rich.cells import cell_len
        ansi = re.compile(r"\x1b\[[0-9;]*m")
        # Pin TERM and FORCE_COLOR so the result doesn't depend on the caller's
        # terminal. Every combination must honour COLUMNS: with FORCE_COLOR set
        # Rich treats a pipe as a terminal, and under TERM=dumb it would fall
        # back to 80 columns unless Lex passes an explicit height too.
        base = {k: v for k, v in os.environ.items() if k not in ("LINES", "FORCE_COLOR", "TERM")}
        combos = [(term, force) for term in ("dumb", "xterm-256color") for force in (None, "0", "1")]
        for (term, force), args in itertools.product(combos, (["--plain", "creed", "apostles"], ["creed", "apostles"])):
            env = dict(base, NO_COLOR="1", COLUMNS="60", TERM=term)
            if force is not None:
                env["FORCE_COLOR"] = force
            with self.subTest(term=term, force_color=force, args=args):
                out = subprocess.run(
                    [sys.executable, LEX, *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
                ).stdout
                # NO_COLOR drops colours (Rich may keep bold); --plain drops all styling.
                self.assertIsNone(re.search(r"\x1b\[[0-9;]*(?:3[0-9]|4[0-9]|9[0-7])[;m]", out))
                out = ansi.sub("", out)
                self.assertLessEqual(max(cell_len(l) for l in out.splitlines()), 60)
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                i = lines.index(next(l for l in lines if l.startswith("1 Credo in Deum Patrem omnipotentem")))
                self.assertTrue(lines[i + 1].startswith("1 I believe in God, the Father almighty"), lines[i:i + 2])
                wide = subprocess.run(
                    [sys.executable, LEX, *args], cwd=ROOT, env=dict(env, COLUMNS="140"),
                    capture_output=True, text=True, timeout=120,
                ).stdout
                self.assertRegex(ansi.sub("", wide),
                                 r"(?m)^\W*1\W+Credo in Deum Patrem omnipotentem,\W+1\W+I believe in God")


if __name__ == "__main__":
    unittest.main()

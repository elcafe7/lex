"""The docs pages in docs/*.md are the source; lex-docs.md and lex-docs.html are
generated from them by scripts/build_docs.py. These tests fail if they drift."""

import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
spec = importlib.util.spec_from_file_location(
    "build_docs", ROOT / "scripts" / "build_docs.py"
)
build_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_docs)
TASKS = [s for s, g in build_docs.PAGES if g == "Tasks"]


class DocsBuildTests(unittest.TestCase):
    def test_generated_files_are_up_to_date(self):
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_docs.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            p.returncode,
            0,
            "docs/lex-docs.md or docs/lex-docs.html is stale; run: python3 scripts/build_docs.py\n"
            + p.stderr,
        )

    def test_pages_have_title_matching_file_name(self):
        pages = build_docs.load()  # raises SystemExit if a title/slug disagrees
        self.assertEqual([p["stem"] for p in pages], [s for s, _ in build_docs.PAGES])

    def test_each_task_has_a_lead_a_command_and_a_sample(self):
        for p in build_docs.load():
            if p["stem"] not in TASKS:
                continue
            body = p["body"]
            self.assertTrue(
                body.split("\n\n")[0].strip()
                and not body.startswith(("#", "```", "|")),
                f"{p['stem']}: start with a one-line plain-English lead",
            )
            self.assertIn("```sh", body, f"{p['stem']}: needs a copy-paste command")
            has_sample = (
                "![" in body or "```json" in body or "```text" in body or "|" in body
            )
            self.assertTrue(
                has_sample, f"{p['stem']}: needs a screenshot or sample output"
            )

    def test_links_and_images_resolve(self):
        for f in [DOCS / "README.md", ROOT / "README.md"] + [
            DOCS / f"{s}.md" for s, _ in build_docs.PAGES
        ]:
            base = f.parent
            text = re.sub(r"<!--.*?-->", "", f.read_text(), flags=re.S)
            for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text) + re.findall(
                r'(?:href|src)="([^"#:]+)"', text
            ):
                if re.match(r"[a-z]+:", target):
                    continue
                self.assertTrue(
                    (base / target).exists(),
                    f"{f.relative_to(ROOT)}: broken link {target}",
                )

    def test_in_page_anchors_match_a_heading(self):
        for stem, _ in build_docs.PAGES:
            text = (DOCS / f"{stem}.md").read_text()
            heads = {
                build_docs.slugify(h) for h in re.findall(r"(?m)^#{1,4} (.+)$", text)
            }
            for anchor in re.findall(r"\]\(#([^)]+)\)", text):
                self.assertIn(anchor, heads, f"{stem}.md: no heading for #{anchor}")

    def test_index_lists_every_page(self):
        index = (DOCS / "README.md").read_text()
        for stem, _ in build_docs.PAGES:
            self.assertIn(f"]({stem}.md)", index)

    def test_generated_docs_name_the_current_version_and_use_relative_images(self):
        ver = build_docs.version()
        md = (DOCS / "lex-docs.md").read_text()
        page = (DOCS / "lex-docs.html").read_text()
        self.assertIn(f"Docs for Lex {ver}", md)
        self.assertIn(f"Docs for Lex {ver}", page)
        for img in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md):
            self.assertTrue((DOCS / img).exists(), img)
        self.assertNotIn("googletagmanager", page)

    def test_readme_has_docs_link_right_after_the_badges(self):
        lines = (ROOT / "README.md").read_text().splitlines()
        end = lines.index("<!-- virustotal-badge:end -->")
        nxt = next(ln for ln in lines[end + 1 :] if ln.strip())
        self.assertIn('href="docs/README.md"', nxt)
        self.assertIn("https://apocalypse.press/lex/docs/", nxt)


if __name__ == "__main__":
    unittest.main()

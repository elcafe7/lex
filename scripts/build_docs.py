#!/usr/bin/env python3
"""Build the single-file docs from the task pages in docs/*.md.

Source of truth: docs/README.md (index) plus one Markdown page per task, listed
in PAGES below. They read well on GitHub as they are. This script derives:

  docs/lex-docs.md    all pages in one Markdown file
  docs/lex-docs.html  the same as an offline HTML page

and, with --site-dir, the files for apocalypse.press/lex/docs/ (index.html,
lex-docs.md, img/). tests/test_docs_build.py fails if the committed outputs
differ from a fresh build, so the pages cannot drift apart.

Usage: build_docs.py [--check] [--site-dir DIR --updated "November 19, 2026, 5:11 PM ET"]
No third-party packages are needed.
"""

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PAGES = [  # (file stem, group)
    ("get-started", "Tasks"),
    ("read-a-passage", "Tasks"),
    ("look-up-a-word", "Tasks"),
    ("search-the-bible", "Tasks"),
    ("study-mode", "Tasks"),
    ("creeds-and-confessions", "Tasks"),
    ("use-lex-with-ai-tools", "Tasks"),
    ("troubleshooting-and-faq", "Tasks"),
    ("full-command-reference", "Reference"),
    ("for-developers", "Reference"),
]
SITE = "https://apocalypse.press/lex/docs/"
GITHUB = "https://github.com/elcafe7/lex"


def version():
    m = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text()
    )
    return m.group(1)


def slugify(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def load():
    pages = []
    for stem, group in PAGES:
        text = (DOCS / f"{stem}.md").read_text()
        m = re.match(r"# (.+)\n", text)
        if not m or slugify(m.group(1)) != stem:
            raise SystemExit(
                f"docs/{stem}.md must start with a '# Title' whose slug is '{stem}'"
            )
        pages.append(
            {
                "stem": stem,
                "group": group,
                "title": m.group(1),
                "body": text[m.end() :].strip("\n"),
            }
        )
    return pages


# ---- Markdown helpers -------------------------------------------------------
def fenced_split(text):
    """Yield (is_code, lang, text) chunks so transforms never touch code blocks."""
    out, buf, code, lang = [], [], False, ""
    for line in text.split("\n"):
        if line.startswith("```"):
            if code:
                out.append((True, lang, "\n".join(buf)))
                buf, code = [], False
            else:
                if buf:
                    out.append((False, "", "\n".join(buf)))
                buf, code, lang = [], True, line[3:].strip()
        else:
            buf.append(line)
    if buf:
        out.append((False, "", "\n".join(buf)))
    return out


def fence(lang, body):
    return f"```{lang}\n{body}\n```"


def transform(text, fn):
    return "\n".join(
        fence(lang, t) if c else fn(t) for c, lang, t in fenced_split(text)
    )


def combined_md(pages, image_base="images/"):
    ver = version()
    toc = "\n".join(f"- [{p['title']}](#{p['stem']})" for p in pages)
    out = [
        f"# Lex CLI Docs\n\n*Local-first Bible study CLI* · Docs for Lex {ver} · Web version: <{SITE}>\n\n"
        "Lex lets you read, search, and study the Bible from your computer's terminal, with no internet "
        "connection or account needed.\n\n## Contents\n\n" + toc + "\n"
    ]
    for p in pages:

        def fn(t):
            t = re.sub(r"(?m)^(#{2,4}) ", lambda m: "#" + m.group(1) + " ", t)
            t = re.sub(r"\]\(([a-z0-9-]+)\.md\)", lambda m: f"](#{m.group(1)})", t)
            return t.replace("](images/", f"]({image_base}")

        out.append(f"## {p['title']}\n\n" + transform(p["body"], fn) + "\n")
    out.append(
        "---\n\n© 2026 Lex CLI  \nA project of [Jesus People SF](https://jesuspeoplesf.com) (a 501c3 ministry)  \n"
        "and [Apocalypse Press](https://apocalypse.press)  \n[Privacy](https://apocalypse.press/privacy/)\n"
    )
    return "\n".join(out)


# ---- tiny Markdown -> HTML (the subset the pages use) --------------------------
def inline(s, img_base):
    codes = []

    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1), quote=False)}</code>")
        return f"\x00{len(codes) - 1}\x00"

    s = re.sub(r"`([^`]+)`", keep, s)
    s = html.escape(s, quote=False)
    s = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: (
            f'<img src="{m.group(2).replace("images/", img_base, 1)}" alt="{html.escape(m.group(1))}" loading="lazy">'
        ),
        s,
    )

    def link(m):
        u = m.group(2)
        mm = re.fullmatch(r"([a-z0-9-]+)\.md", u)
        if mm:
            u = "#" + mm.group(1)
        return f'<a href="{u}">{m.group(1)}</a>'

    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", s)
    s = re.sub(r"&lt;(https?://[^&\s]+)&gt;", r'<a href="\1">\1</a>', s)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


def cells(row):
    return [c.strip() for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]


def md_to_html(text, img_base):
    out, para = [], []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para), img_base) + "</p>")
            para.clear()

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            j = i + 1
            buf = []
            while not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append(
                "<pre><code>"
                + html.escape("\n".join(buf), quote=False)
                + "</code></pre>"
            )
            i = j + 1
            continue
        m = re.match(r"(#{2,3}) (.+)", line)
        if m:
            flush()
            n = len(m.group(1)) + 1
            out.append(f"<h{n}>{inline(m.group(2), img_base)}</h{n}>")
            i += 1
            continue
        if line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            head = cells(rows[0])
            body = [cells(r) for r in rows[2:]]
            t = (
                '<div class="table-wrap"><table><thead><tr>'
                + "".join(f"<th>{inline(c, img_base)}</th>" for c in head)
                + "</tr></thead><tbody>"
            )
            for r in body:
                t += (
                    "<tr>"
                    + "".join(
                        f"<td>{inline(c.replace(chr(92) + '|', '|'), img_base)}</td>"
                        for c in r
                    )
                    + "</tr>"
                )
            out.append(t + "</tbody></table></div>")
            continue
        if re.match(r"(- |\d+\. )", line):
            flush()
            ordered = line[0].isdigit()
            items = []
            while i < len(lines) and re.match(r"(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(
                f"<{tag}>"
                + "".join(f"<li>{inline(x, img_base)}</li>" for x in items)
                + f"</{tag}>"
            )
            continue
        if line.startswith("> "):
            flush()
            out.append(
                "<blockquote><p>" + inline(line[2:], img_base) + "</p></blockquote>"
            )
            i += 1
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        para.append(line)
        i += 1
    flush()
    return "\n".join(out)


CSS = """
:root{color-scheme:dark;--bg:#0a0a0a;--surface:#121212;--panel:#181818;--term:#1e1e1e;--line:#2a2a2a;--accent:#38bdf8;--text:#e5e5e5;--dim:#a3a3a3;--warn:#facc15}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:20px}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent);text-underline-offset:3px}a:hover{text-decoration-thickness:2px}
.layout{display:grid;grid-template-columns:260px minmax(0,1fr);min-height:100vh}
aside{position:sticky;top:0;height:100vh;overflow:auto;background:var(--surface);border-right:1px solid var(--line);padding:26px 20px}
.brand{margin:0 0 4px;font-size:1.3rem;font-weight:800}.brand a{color:var(--text);text-decoration:none}.brand a:hover{color:var(--accent)}
.tag{margin:0 0 18px;color:var(--dim);font-size:.9rem}
nav a{display:block;padding:5px 10px;margin:1px 0;border-radius:6px;color:var(--dim);text-decoration:none;font-size:.95rem}
nav a:hover{color:var(--text);background:var(--panel)}nav a.on{color:var(--bg);background:var(--accent);font-weight:650}
nav .group{margin:18px 0 6px 10px;color:var(--dim);font-size:.7rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase}
.note{margin:18px 10px 0;color:var(--dim);font-size:.82rem}
main{width:min(100%,980px);padding:44px 36px 72px}
.hero h1{margin:6px 0 10px;font-size:clamp(2.2rem,5vw,3.4rem);line-height:1.05;letter-spacing:-.02em}
.eyebrow{margin:0;color:var(--accent);font-size:.78rem;font-weight:750;letter-spacing:.1em;text-transform:uppercase}
.lead{font-size:1.15rem;color:var(--text);max-width:62ch}.meta{color:var(--dim);font-size:.9rem}
.pills{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 0}.pills span{border:1px solid var(--line);border-radius:999px;padding:3px 12px;font-size:.82rem;color:var(--dim)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin:26px 0 0}
.tiles a{display:block;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px;color:var(--text);text-decoration:none}
.tiles a:hover{border-color:var(--accent)}.tiles b{display:block;color:var(--accent)}.tiles span{color:var(--dim);font-size:.88rem}
section{padding-top:36px;margin-top:36px;border-top:1px solid var(--line)}
h2{margin:0 0 12px;font-size:1.9rem;line-height:1.2}h3{margin:30px 0 8px;font-size:1.25rem}h4{margin:22px 0 6px}
p,li{max-width:76ch}li{margin:4px 0}
code{font-family:"DejaVu Sans Mono",ui-monospace,Menlo,Consolas,monospace;font-size:.88em;background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:1px 6px}
pre{position:relative;margin:14px 0;background:var(--term);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow:auto;max-width:100%}
pre code{background:none;border:0;padding:0;font-size:.9rem;line-height:1.55;color:#eaeaea}
img{max-width:100%;height:auto;display:block;margin:16px 0;border:1px solid var(--line);border-radius:10px;background:var(--term)}
.table-wrap{overflow-x:auto;margin:14px 0}table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:8px;font-size:.93rem}
th,td{text-align:left;vertical-align:top;padding:9px 12px;border-bottom:1px solid var(--line)}th{color:var(--dim);font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;background:var(--panel)}
blockquote{margin:14px 0;border-left:3px solid var(--warn);padding:2px 16px;color:var(--dim)}
.copy{position:absolute;top:8px;right:8px;background:var(--panel);color:var(--dim);border:1px solid var(--line);border-radius:6px;padding:2px 9px;font:inherit;font-size:.75rem;cursor:pointer}.copy:hover{color:var(--text)}
footer{margin-top:56px;padding-top:24px;border-top:1px solid var(--line);color:var(--dim);font-size:.9rem}footer a{text-decoration:none;font-weight:650}
@media(max-width:860px){.layout{display:block}aside{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}nav{display:flex;flex-wrap:wrap;gap:2px 6px}nav .group{width:100%}main{padding:28px 18px 56px}}
"""
JS = """
(function(){var s=document.querySelectorAll('section[id]'),a={};document.querySelectorAll('nav a').forEach(function(x){a[x.getAttribute('href').slice(1)]=x});
if('IntersectionObserver' in window){var o=new IntersectionObserver(function(e){e.forEach(function(i){if(i.isIntersecting){Object.values(a).forEach(function(x){x.classList.remove('on')});if(a[i.target.id])a[i.target.id].classList.add('on')}})},{rootMargin:'-20% 0px -70% 0px'});s.forEach(function(x){o.observe(x)})}
document.querySelectorAll('pre').forEach(function(p){var b=document.createElement('button');b.className='copy';b.type='button';b.textContent='Copy';b.onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(p.innerText.replace(/\\nCopy$/,'').replace(/Copy$/,'')).then(function(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy'},1200)})};p.appendChild(b)});})();
"""
TILES = {  # one-line "why" for the tiles at the top of the page
    "get-started": "Install in about two minutes",
    "read-a-passage": "Any verse, chapter, or Bible version",
    "look-up-a-word": "What a Greek or Hebrew word means",
    "search-the-bible": "Find every verse with a word or phrase",
    "study-mode": "The original language, word by word",
    "creeds-and-confessions": "Original and English, side by side",
    "use-lex-with-ai-tools": "Scripts and AI assistants (--json)",
    "troubleshooting-and-faq": "Quick fixes and answers",
    "full-command-reference": "Every command and option",
    "for-developers": "Working on Lex itself",
}


def build_html(
    pages, img_base, site=False, updated=None, md_href="lex-docs.md", brand_href=GITHUB
):
    ver = version()
    nav, last = [], None
    for p in pages:
        if p["group"] != last:
            nav.append(f'<p class="group">{p["group"]}</p>')
            last = p["group"]
        nav.append(f'<a href="#{p["stem"]}">{html.escape(p["title"])}</a>')
    tiles = "".join(
        f'<a href="#{p["stem"]}"><b>{html.escape(p["title"])}</b><span>{TILES[p["stem"]]}</span></a>'
        for p in pages[:8]
    )
    secs = "\n".join(
        f'<section id="{p["stem"]}">\n<h2>{html.escape(p["title"])}</h2>\n{md_to_html(p["body"], img_base)}\n</section>'
        for p in pages
    )
    ga = (
        (
            '<!-- Global site tag (gtag.js) - Google Analytics -->\n<script async src="https://www.googletagmanager.com/gtag/js?id=G-0M3SF90ZGN"></script>\n'
            "<script>\n  window.dataLayer = window.dataLayer || [];\n  function gtag(){dataLayer.push(arguments);}\n  gtag('js', new Date());\n  gtag('config', 'G-0M3SF90ZGN');\n</script>\n"
        )
        if site
        else ""
    )
    upd = f'<p class="meta">Last updated: {updated}</p>' if updated else ""
    repo_note = (
        ""
        if site
        else "<!-- Repo copy of https://apocalypse.press/lex/docs/ (analytics removed). Generated by scripts/build_docs.py; edit docs/*.md instead. -->\n"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lex CLI Docs</title>
<meta name="description" content="Plain-language guide to Lex, the offline Bible study terminal: install, read, search, study, creeds, and using Lex with AI tools. Version {ver}.">
{repo_note}<style>{CSS}</style>
{ga}</head>
<body>
<div class="layout">
<aside>
<p class="brand"><a href="{brand_href}">Lex CLI Docs</a></p>
<p class="tag">Read, search, and study the Bible from your terminal.</p>
<nav aria-label="Page navigation">
{chr(10).join(nav)}
</nav>
<p class="note">Docs for Lex {ver}.</p>
<p class="note"><a href="{md_href}" download="lex-docs.md" type="text/markdown">Download as Markdown</a></p>
</aside>
<main>
<header class="hero" id="top">
<p class="eyebrow">Local-first Bible study CLI</p>
<h1>Lex CLI Docs</h1>
{upd}<p class="lead">Lex lets you read, search, and study the Bible from your computer's terminal. It works offline and needs no account. Pick what you want to do:</p>
<div class="tiles">{tiles}</div>
<div class="pills"><span>Version {ver}</span><span>Python 3.12+</span><span>Works offline</span><span>macOS / Linux terminal</span></div>
</header>
{secs}
<footer>
&copy; 2026 Lex CLI<br>
A project of <a href="https://jesuspeoplesf.com">Jesus People SF</a> (a 501c3 ministry)<br>
and <a href="https://apocalypse.press">Apocalypse Press</a><br>
<a href="/privacy/">Privacy</a>
</footer>
</main>
</div>
<script>{JS}</script>
</body>
</html>
"""


def outputs(site_dir=None, updated=None):
    pages = load()
    res = {
        DOCS / "lex-docs.md": combined_md(pages),
        DOCS / "lex-docs.html": build_html(
            pages,
            "images/",
            md_href="lex-docs.md",
            brand_href="https://apocalypse.press/lex/",
        ),
    }
    if site_dir:
        sd = Path(site_dir)
        res[sd / "index.html"] = build_html(
            pages,
            "img/",
            site=True,
            updated=updated,
            md_href="/lex/docs/lex-docs.md",
            brand_href="/lex/",
        )
        res[sd / "lex-docs.md"] = combined_md(pages, image_base=SITE + "img/")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--check", action="store_true", help="exit 1 if committed outputs are stale"
    )
    ap.add_argument("--site-dir")
    ap.add_argument("--updated")
    a = ap.parse_args(argv)
    res = outputs(a.site_dir, a.updated)
    stale = [p for p, t in res.items() if not p.exists() or p.read_text() != t]
    if a.check:
        if stale:
            print(
                "stale (run python3 scripts/build_docs.py): "
                + ", ".join(
                    str(p.relative_to(ROOT)) if ROOT in p.parents else str(p)
                    for p in stale
                ),
                file=sys.stderr,
            )
            return 1
        return 0
    for p, t in res.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(t)
    if a.site_dir:
        img = Path(a.site_dir) / "img"
        img.mkdir(exist_ok=True)
        used = set(
            re.findall(
                r"images/([A-Za-z0-9_.-]+\.png)", "\n".join(p["body"] for p in load())
            )
        )
        for n in sorted(used):
            shutil.copy(DOCS / "images" / n, img / n)
    print("wrote " + ", ".join(p.name for p in res))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Lex: The Elegant Bible Terminal
A source-aware, local-first CLI tool for Bible study, language inspection, 
and traversal of the Christian tradition.

Supports multiple Bible versions, interlinear study, global FTS5 search,
historical creeds/confessions, and manifest-driven auto-updates.
"""
import sqlite3
import os
import sys
import re
import json
import argparse
import shlex
import time
import html
import subprocess
import shutil
import plistlib
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
from rich.theme import Theme
from rich.prompt import Prompt, IntPrompt
from rich.rule import Rule

import urllib.request
import hashlib

# ... (rest of imports)

# ---------------------------------------------------------------------------
# Update Manager
# ---------------------------------------------------------------------------
class LexUpdateManager:
    MANIFEST_URL = "https://raw.githubusercontent.com/elcafe7/lex/main/manifest.json"
    RAW_BASE_URL = "https://raw.githubusercontent.com/elcafe7/lex/main/"

    def __init__(self, console, data_dir=None):
        self.console = console
        self.data_dir = data_dir or RUNTIME_DATA_DIR

    def get_local_hash(self, filepath):
        if not os.path.exists(filepath):
            return None
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def fetch_remote_manifest(self):
        try:
            with urllib.request.urlopen(self.MANIFEST_URL) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            self.console.print(f"[warning]Failed to fetch update manifest: {e}[/]")
            return None

    def check_for_updates(self):
        remote = self.fetch_remote_manifest()
        if not remote: return None, None
        
        updates_needed = []
        for rel_path, info in remote.get("assets", {}).items():
            # If the rel_path is lex.py itself, we usually don't want to update it
            # via this manager if installed as a package, but for now we follow old logic
            # for local clones.
            if rel_path == "lex.py":
                local_path = os.path.join(BASE_DIR, rel_path)
            else:
                # rel_path usually starts with 'runtime-data/'
                # we strip that and join with our data_dir
                actual_rel = rel_path.replace("runtime-data/", "", 1)
                local_path = os.path.join(self.data_dir, actual_rel)
                
            local_hash = self.get_local_hash(local_path)
            if local_hash != info["hash"]:
                updates_needed.append(rel_path)
        
        return updates_needed, remote["version"]

    def ensure_data(self):
        """Ensures that essential data files exist. If not, trigger a full update."""
        critical_file = os.path.join(self.data_dir, "lexicon.db")
        if not os.path.exists(critical_file):
            self.console.print("[info]First run detected: Downloading Bible databases (approx 280MB)...[/]")
            self.perform_update()

    def perform_update(self):
        updates, remote_version = self.check_for_updates()
        if updates is None:
            return
            
        if not updates:
            self.console.print("[success]Lex is already up to date.[/]")
            return

        self.console.print(f"[info]Updating Lex data to {remote_version}... ({len(updates)} files)[/]")
        
        # Pull lex.py to the end if present to avoid mid-update execution drift
        if "lex.py" in updates:
            updates.remove("lex.py")
            updates.append("lex.py")

        for rel_path in updates:
            self.console.print(f"  → Downloading {rel_path}...")
            url = self.RAW_BASE_URL + rel_path
            
            if rel_path == "lex.py":
                target_path = os.path.join(BASE_DIR, rel_path)
            else:
                actual_rel = rel_path.replace("runtime-data/", "", 1)
                target_path = os.path.join(self.data_dir, actual_rel)
                
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            try:
                urllib.request.urlretrieve(url, target_path + ".tmp")
                os.replace(target_path + ".tmp", target_path)
                
                # If we just updated the main script, ensure it's still executable
                if rel_path == "lex.py":
                    os.chmod(target_path, 0o755)
            except Exception as e:
                self.console.print(f"[error]Failed to download {rel_path}: {e}[/]")
                return

        self.console.print(f"[success]Successfully updated Lex to {remote_version}![/]")

# ---------------------------------------------------------------------------
# Runtime paths and bundled-data adapters
# ---------------------------------------------------------------------------
# Lex is currently a single-file CLI that reads several local SQLite/JSON data
# stores. Keep these paths centralized so future packaging can replace them
# with config/env-driven paths without touching feature code.
VERSION = "2.4.3"
HISTORY_FILE = os.path.expanduser("~/.lex_history")
CONFIG_FILE = os.path.expanduser("~/.lex_config.json")

# Local-first path resolution. Clones ship the compact runtime data bundle
# (SQLite DBs and JSON) under runtime-data/, while local developer worktrees
# may also have full upstream data checkouts beside lex.py.
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
RUNTIME_DATA_DIR = os.path.join(BASE_DIR, "runtime-data")
HOME_FALLBACK = os.path.expanduser("~/bible-lexicon-data")

# Determine which data directory to use
if os.path.exists(RUNTIME_DATA_DIR) and os.path.exists(os.path.join(RUNTIME_DATA_DIR, "lexicon.db")):
    DATA_DIR = RUNTIME_DATA_DIR
else:
    DATA_DIR = HOME_FALLBACK

def get_lex_path(relative_path):
    return os.path.join(DATA_DIR, relative_path)

LEXICON_DB_PATH = get_lex_path("lexicon.db")

# Bible Versions Configuration
BIBLE_VERSIONS = {
    "esv": {"name": "English Standard Version", "file": "bible_versions/esv.db"},
    "kjv": {"name": "King James Version (Oxford 1769)", "file": "bible_versions/kjv.db"},
    "kj16": {"name": "King James Version (1611)", "file": "bible_versions/kj16.db"},
    "nasb": {"name": "New American Standard Bible (1995)", "file": "bible_versions/nasb.db"},
    "gen": {"name": "Geneva Bible (1587)", "file": "bible_versions/gen.db"},
    "lxx": {"name": "Septuagint (Rahlfs 1935)", "file": "bible_versions/lxx.db"},
    "vulg": {"name": "Clementine Vulgate", "file": "bible_versions/vulg.db"},
}

def get_bible_path(bible_id):
    if bible_id in BIBLE_VERSIONS:
        return get_lex_path(BIBLE_VERSIONS[bible_id]["file"])
    return get_lex_path("bible_versions/esv.db")

ENCYCLOPEDIA_DB_PATH = get_lex_path("encyclopedia.db")
CROSS_REFS_DB_PATH = get_lex_path("cross_refs.db")
STRONGS_DB_PATH = get_lex_path("strongs.db")
DICTIONARY_DB_PATH = get_lex_path("dictionary.db")
CREEDS_DB_PATH = get_lex_path("creeds.db")
PLACES_DB_PATH = get_lex_path("places.db")
NAVES_DB_PATH = get_lex_path("naves.db")
HENRY_DB_PATH = get_lex_path("commentaries/matthew_henry.db")
CALVIN_DB_PATH = get_lex_path("commentaries/john_calvin.db")
INTERLINEAR_PATH = get_lex_path("esv-data/data/esv/esv-interlinear.json")
INTERLINEAR_STRONGS_PATH = get_lex_path("esv-data/data/interlinear/strongs.json")
STEP_GREEK_PATH = get_lex_path("theolog-ai/data/biblical-languages/stepbible-lexicons/tbesg-greek.json")
STEP_HEBREW_PATH = get_lex_path("theolog-ai/data/biblical-languages/stepbible-lexicons/tbesh-hebrew.json")
HISTORICAL_DOCS_DIR = get_lex_path("theolog-ai/data/historical-documents")

# The creeds table in lexicon.db has placeholder rows for some documents. This
# map lets the UI fall back to the complete local JSON document when needed.
HISTORICAL_DOC_FILES = {
    "The Apostles' Creed": "apostles-creed.json",
    "The Nicene Creed": "nicene-creed.json",
    "Athanasian Creed": "athanasian-creed.json",
    "Chalcedonian Definition": "chalcedonian-definition.json",
    "Augsburg Confession": "augsburg-confession.json",
    "Baltimore Catechism": "baltimore-catechism.json",
    "Belgic Confession": "belgic-confession.json",
    "Canons of Dort": "canons-of-dort.json",
    "Confession of Dositheus": "confession-of-dositheus.json",
    "Council of Trent": "council-of-trent.json",
    "Heidelberg Catechism": "heidelberg-catechism.json",
    "London Baptist Confession of Faith": "london-baptist-1689.json",
    "The Longer Catechism of the Orthodox Church": "philaret-catechism.json",
    "Thirty-Nine Articles": "39-articles.json",
    "Westminster Confession of Faith": "westminster-confession.json",
    "Westminster Larger Catechism": "westminster-larger-catechism.json",
    "Westminster Shorter Catechism": "westminster-shorter-catechism.json",
}

# TSK cross-reference data uses abbreviated references like "John.3.16", while
# the Bible DB uses "esv:John:3:16". These maps are the bridge between them.
TSK_BOOK_ABBR = {
    "Genesis": "Gen.", "Exodus": "Ex.", "Leviticus": "Lev.", "Numbers": "Num.",
    "Deuteronomy": "Deut.", "Joshua": "Josh.", "Judges": "Judg.", "Ruth": "Ruth",
    "1 Samuel": "1Sam.", "2 Samuel": "2Sam.", "1 Kings": "1Kgs.", "2 Kings": "2Kgs.",
    "1 Chronicles": "1Chr.", "2 Chronicles": "2Chr.", "Ezra": "Ezra", "Nehemiah": "Neh.",
    "Esther": "Est.", "Job": "Job", "Psalms": "Ps.", "Proverbs": "Prov.",
    "Ecclesiastes": "Eccl.", "Song of Solomon": "Song", "Isaiah": "Isa.", "Jeremiah": "Jer.",
    "Lamentations": "Lam.", "Ezekiel": "Ezek.", "Daniel": "Dan.", "Hosea": "Hos.",
    "Joel": "Joel", "Amos": "Amos", "Obadiah": "Obad.", "Jonah": "Jonah",
    "Micah": "Mic.", "Nahum": "Nah.", "Habakkuk": "Hab.", "Zephaniah": "Zeph.",
    "Haggai": "Hag.", "Zechariah": "Zech.", "Malachi": "Mal.", "Matthew": "Matt.",
    "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts", "Romans": "Rom.",
    "1 Corinthians": "1Cor.", "2 Corinthians": "2Cor.", "Galatians": "Gal.",
    "Ephesians": "Eph.", "Philippians": "Phil.", "Colossians": "Col.",
    "1 Thessalonians": "1Thess.", "2 Thessalonians": "2Thess.", "1 Timothy": "1Tim.",
    "2 Timothy": "2Tim.", "Titus": "Titus", "Philemon": "Phlm.", "Hebrews": "Heb.",
    "James": "Jas.", "1 Peter": "1Pet.", "2 Peter": "2Pet.", "1 John": "1John.",
    "2 John": "2John.", "3 John": "3John.", "Jude": "Jude", "Revelation": "Rev.",
}
TSK_TO_BOOK = {abbr.rstrip("."): book for book, abbr in TSK_BOOK_ABBR.items()}
BIBLE_BOOKS = list(TSK_BOOK_ABBR.keys())
BIBLE_BOOK_INDEX = {book: idx for idx, book in enumerate(BIBLE_BOOKS)}

# Pre-compile normalization pattern for performance
NORM_RE = re.compile(r"[^a-z0-9]+")

BOOK_SCOPE_ALIASES = {}
for book in BIBLE_BOOKS:
    low = book.lower()
    book_key = NORM_RE.sub("-", low).strip("-")
    compact_key = NORM_RE.sub("", low)
    BOOK_SCOPE_ALIASES[book_key] = book
    BOOK_SCOPE_ALIASES[compact_key] = book
    abbr = TSK_BOOK_ABBR.get(book, "").rstrip(".").lower()
    if abbr:
        BOOK_SCOPE_ALIASES[NORM_RE.sub("-", abbr).strip("-")] = book
        BOOK_SCOPE_ALIASES[NORM_RE.sub("", abbr)] = book

BOOK_SCOPE_ALIASES.update({
    "ge": "Genesis",
    "gn": "Genesis",
    "gen": "Genesis",
    "ex": "Exodus",
    "exo": "Exodus",
    "exod": "Exodus",
    "le": "Leviticus",
    "lev": "Leviticus",
    "nu": "Numbers",
    "num": "Numbers",
    "de": "Deuteronomy",
    "dt": "Deuteronomy",
    "deut": "Deuteronomy",
    "jos": "Joshua",
    "josh": "Joshua",
    "jdg": "Judges",
    "judg": "Judges",
    "ru": "Ruth",
    "1sa": "1 Samuel",
    "1sam": "1 Samuel",
    "2sa": "2 Samuel",
    "2sam": "2 Samuel",
    "1ki": "1 Kings",
    "1kgs": "1 Kings",
    "2ki": "2 Kings",
    "2kgs": "2 Kings",
    "1ch": "1 Chronicles",
    "1chr": "1 Chronicles",
    "2ch": "2 Chronicles",
    "2chr": "2 Chronicles",
    "ezr": "Ezra",
    "neh": "Nehemiah",
    "est": "Esther",
    "psalm": "Psalms",
    "ps": "Psalms",
    "psa": "Psalms",
    "psm": "Psalms",
    "pss": "Psalms",
    "pr": "Proverbs",
    "pro": "Proverbs",
    "prov": "Proverbs",
    "ec": "Ecclesiastes",
    "ecc": "Ecclesiastes",
    "eccl": "Ecclesiastes",
    "song": "Song of Solomon",
    "sos": "Song of Solomon",
    "canticles": "Song of Solomon",
    "is": "Isaiah",
    "isa": "Isaiah",
    "jr": "Jeremiah",
    "jer": "Jeremiah",
    "lam": "Lamentations",
    "eze": "Ezekiel",
    "ezek": "Ezekiel",
    "ezk": "Ezekiel",
    "da": "Daniel",
    "dn": "Daniel",
    "dan": "Daniel",
    "hos": "Hosea",
    "jl": "Joel",
    "am": "Amos",
    "ob": "Obadiah",
    "obad": "Obadiah",
    "jon": "Jonah",
    "mi": "Micah",
    "mic": "Micah",
    "na": "Nahum",
    "nah": "Nahum",
    "hab": "Habakkuk",
    "zep": "Zephaniah",
    "zeph": "Zephaniah",
    "hag": "Haggai",
    "zec": "Zechariah",
    "zech": "Zechariah",
    "mal": "Malachi",
    "mt": "Matthew",
    "mat": "Matthew",
    "matt": "Matthew",
    "mk": "Mark",
    "mrk": "Mark",
    "lk": "Luke",
    "lu": "Luke",
    "jn": "John",
    "jhn": "John",
    "joh": "John",
    "ac": "Acts",
    "ro": "Romans",
    "rom": "Romans",
    "1co": "1 Corinthians",
    "1cor": "1 Corinthians",
    "2co": "2 Corinthians",
    "2cor": "2 Corinthians",
    "gal": "Galatians",
    "eph": "Ephesians",
    "php": "Philippians",
    "phil": "Philippians",
    "col": "Colossians",
    "1th": "1 Thessalonians",
    "1thess": "1 Thessalonians",
    "2th": "2 Thessalonians",
    "2thess": "2 Thessalonians",
    "1ti": "1 Timothy",
    "1tim": "1 Timothy",
    "2ti": "2 Timothy",
    "2tim": "2 Timothy",
    "tit": "Titus",
    "phm": "Philemon",
    "phlm": "Philemon",
    "heb": "Hebrews",
    "jas": "James",
    "jam": "James",
    "1pe": "1 Peter",
    "1pet": "1 Peter",
    "2pe": "2 Peter",
    "2pet": "2 Peter",
    "1jn": "1 John",
    "1jhn": "1 John",
    "2jn": "2 John",
    "2jhn": "2 John",
    "3jn": "3 John",
    "3jhn": "3 John",
    "rev": "Revelation",
    "rv": "Revelation",
    "re": "Revelation",
    "revelations": "Revelation",
})

BOOK_SCOPE_GROUPS = {
    "ot": BIBLE_BOOKS[:39],
    "old-testament": BIBLE_BOOKS[:39],
    "nt": BIBLE_BOOKS[39:],
    "new-testament": BIBLE_BOOKS[39:],
    "law": BIBLE_BOOKS[:5],
    "pentateuch": BIBLE_BOOKS[:5],
    "torah": BIBLE_BOOKS[:5],
    "history": BIBLE_BOOKS[5:17],
    "wisdom": BIBLE_BOOKS[17:22],
    "poetry": BIBLE_BOOKS[17:22],
    "major": BIBLE_BOOKS[22:27],
    "major-prophets": BIBLE_BOOKS[22:27],
    "minor": BIBLE_BOOKS[27:39],
    "minor-prophets": BIBLE_BOOKS[27:39],
    "prophets": BIBLE_BOOKS[22:39],
    "gospels": BIBLE_BOOKS[39:43],
    "gospel": BIBLE_BOOKS[39:43],
    "epistles": BIBLE_BOOKS[44:66],
    "letters": BIBLE_BOOKS[44:66],
    "pauline": BIBLE_BOOKS[44:57],
    "general-epistles": BIBLE_BOOKS[57:66],
}

# Original-language creed text is only stored for short documents where
# side-by-side display is useful. Longer confessions stay English-only for now.
CREED_ORIGINALS = {
    "The Apostles' Creed": {
        "language": "Latin",
        "sections": {
            "God the Father": "Credo in Deum Patrem omnipotentem, Creatorem caeli et terrae.",
            "Jesus Christ": "Et in Iesum Christum, Filium eius unicum, Dominum nostrum, qui conceptus est de Spiritu Sancto, natus ex Maria Virgine, passus sub Pontio Pilato, crucifixus, mortuus, et sepultus; descendit ad inferos; tertia die resurrexit a mortuis; ascendit ad caelos; sedet ad dexteram Dei Patris omnipotentis; inde venturus est iudicare vivos et mortuos.",
            "The Holy Spirit and the Church": "Credo in Spiritum Sanctum, sanctam Ecclesiam catholicam, sanctorum communionem, remissionem peccatorum, carnis resurrectionem, vitam aeternam. Amen.",
        },
    },
    "The Nicene Creed": {
        "language": "Greek",
        "sections": {
            "God the Father": "Πιστεύομεν εἰς ἕνα Θεόν, Πατέρα, παντοκράτορα, ποιητὴν οὐρανοῦ καὶ γῆς, ὁρατῶν τε πάντων καὶ ἀοράτων.",
            "Jesus Christ the Son": "Καὶ εἰς ἕνα Κύριον Ἰησοῦν Χριστόν, τὸν Υἱὸν τοῦ Θεοῦ τὸν μονογενῆ, τὸν ἐκ τοῦ Πατρὸς γεννηθέντα πρὸ πάντων τῶν αἰώνων· φῶς ἐκ φωτός, Θεὸν ἀληθινὸν ἐκ Θεοῦ ἀληθινοῦ, γεννηθέντα, οὐ ποιηθέντα, ὁμοούσιον τῷ Πατρί, δι᾿ οὗ τὰ πάντα ἐγένετο. Τὸν δι᾿ ἡμᾶς τοὺς ἀνθρώπους καὶ διὰ τὴν ἡμετέραν σωτηρίαν κατελθόντα ἐκ τῶν οὐρανῶν καὶ σαρκωθέντα ἐκ Πνεύματος ἁγίου καὶ Μαρίας τῆς Παρθένου καὶ ἐνανθρωπήσαντα. Σταυρωθέντα τε ὑπὲρ ἡμῶν ἐπὶ Ποντίου Πιλάτου καὶ παθόντα καὶ ταφέντα. Καὶ ἀναστάντα τῇ τρίτῃ ἡμέρᾳ, κατὰ τὰς Γραφάς. Καὶ ἀνελθόντα εἰς τοὺς οὐρανοὺς καὶ καθεζόμενον ἐκ δεξιῶν τοῦ Πατρός. Καὶ πάλιν ἐρχόμενον μετὰ δόξης κρῖναι ζῶντας καὶ νεκρούς, οὗ τῆς βασιλείας οὐκ ἔσται τέλος.",
            "The Holy Spirit": "Καὶ εἰς τὸ Πνεῦμα τὸ Ἅγιον, τὸ κύριον, τὸ ζωοποιόν, τὸ ἐκ τοῦ Πατρὸς ἐκπορευόμενον, τὸ σὺν Πατρὶ καὶ Υἱῷ συμπροσκυνούμενον καὶ συνδοξαζόμενον, τὸ λαλῆσαν διὰ τῶν προφητῶν.",
            "The Church and Final Hope": "Εἰς μίαν, ἁγίαν, καθολικὴν καὶ ἀποστολικὴν Ἐκκλησίαν. Ὁμολογοῦμεν ἓν βάπτισμα εἰς ἄφεσιν ἁμαρτιῶν. Προσδοκοῦμεν ἀνάστασιν νεκρῶν καὶ ζωὴν τοῦ μέλλοντος αἰῶνος. Ἀμήν.",
        },
    },
    "Athanasian Creed": {
        "language": "Latin",
        "sections": {
            "Opening": "Quicunque vult salvus esse, ante omnia opus est, ut teneat catholicam fidem: Quam nisi quisque integram inviolatamque servaverit, absque dubio in aeternum peribit.",
            "The Doctrine of the Trinity": "Fides autem catholica haec est: ut unum Deum in Trinitate, et Trinitatem in unitate veneremur. Neque confundentes personas, neque substantiam separantes. Alia est enim persona Patris alia Filii, alia Spiritus Sancti: Sed Patris, et Filii, et Spiritus Sancti una est divinitas, aequalis gloria, coaeterna maiestas. Qualis Pater, talis Filius, talis Spiritus Sanctus. Increatus Pater, increatus Filius, increatus Spiritus Sanctus. Immensus Pater, immensus Filius, immensus Spiritus Sanctus. Aeternus Pater, aeternus Filius, aeternus Spiritus Sanctus. Et tamen non tres aeterni, sed unus aeternus. Sicut non tres increati, nec tres immensi, sed unus increatus, et unus immensus. Similiter omnipotens Pater, omnipotens Filius, omnipotens Spiritus Sanctus. Et tamen non tres omnipotentes, sed unus omnipotens. Ita Deus Pater, Deus Filius, Deus Spiritus Sanctus. Et tamen non tres Dii, sed unus est Deus. Ita Dominus Pater, Dominus Filius, Dominus Spiritus Sanctus. Et tamen non tres Domini, sed unus est Dominus. Quia, sicut singillatim unamquamque personam Deum ac Dominum confiteri christiana veritate compellimur: ita tres Deos aut Dominos dicere catholica religione prohibemur. Pater a nullo est factus: nec creatus, nec genitus. Filius a Patre solo est: non factus, nec creatus, sed genitus. Spiritus Sanctus a Patre et Filio: non factus, nec creatus, nec genitus, sed procedens. Unus ergo Pater, non tres Patres: unus Filius, non tres Filii: unus Spiritus Sanctus, non tres Spiritus Sancti. Et in hac Trinitate nihil prius aut posterius, nihil maius aut minus: sed totae tres personae coaeternae sibi sunt et coaequales. Ita ut per omnia, sicut iam supra dictum est, et unitas in Trinitate, et Trinitas in unitate veneranda sit. Qui vult ergo salvus esse, ita de Trinitate sentiat.",
            "The Incarnation of Christ": "Sed necessarium est ad aeternam salutem, ut incarnationem quoque Domini nostri Iesu Christi fideliter credat. Est ergo fides recta ut credamus et confiteamur, quia Dominus noster Iesus Christus, Dei Filius, Deus et homo est. Deus est ex substantia Patris ante saecula genitus: et homo est ex substantia matris in saeculo natus. Perfectus Deus, perfectus homo: ex anima rationabili et humana carne subsistens. Aequalis Patri secundum divinitatem: minor Patre secundum humanitatem. Qui licet Deus sit et homo, non duo tamen, sed unus est Christus. Unus autem non conversione divinitatis in carnem, sed assumptione humanitatis in Deum. Unus omnino, non confusione substantiae, sed unitate personae. Nam sicut anima rationabilis et caro unus est homo: ita Deus et homo unus est Christus. Qui passus est pro salute nostra: descendit ad inferos: tertia die resurrexit a mortuis. Ascendit ad caelos, sedet ad dexteram Dei Patris omnipotentis: inde venturus est iudicare vivos et mortuos. Ad cuius adventum omnes homines resurgere habent cum corporibus suis: et reddituri sunt de factis propriis rationem. Et qui bona egerunt, ibunt in vitam aeternam: qui vero mala, in ignem aeternum.",
            "Conclusion": "Haec est fides catholica, quam nisi quisque fideliter firmiterque crediderit, salvus esse non poterit.",
        },
    },
    "Chalcedonian Definition": {
        "language": "Greek",
        "sections": {
            "Introduction": "Ἡ ἁγία καὶ μεγάλη καὶ οἰκουμενικὴ σύνοδος, ἡ κατὰ θεοῦ χάριν καὶ θέσπισμα τῶν εὐσεβεστάτων καὶ φιλοχρίστων ἡμῶν βασιλέων Μαρκιανοῦ καὶ Οὐαλεντινιανοῦ Αὐγούστων ἐν Χαλκηδόνι τῇ μητροπόλει τῆς Βιθυνῶν ἐπαρχίας συναχθεῖσα ἐν τῷ μαρτυρίῳ τῆς ἁγίας καὶ καλλινίκου μάρτυρος Εὐφημίας, ὥρισε τὰ ὑποτεταγμένα. Ὁ κύριος ἡμῶν καὶ σωτὴρ Ἰησοῦς Χριστός, τὴν τῆς πίστεως γνῶσιν τοῖς μαθηταῖς βεβαιῶν, ἔφη πρὸς αὐτούς· Εἰρήνην τὴν ἐμὴν δίδωμι ὑμῖν, εἰρήνην τὴν ἐμὴν ἀφίημι ὑμῖν, πρὸς τὸ μηδένα πρὸς τὸν πλησίον διχονοεῖν ἐν τοῖς τῆς εὐσεβείας δόγμασιν, ἀλλ' ἐπίσης τοῖς πᾶσι τὸ τῆς ἀληθείας ἐπιδείκνυσθαι κήρυγμα.",
            "The Definition": "Ἑπόμενοι τοίνυν τοῖς ἁγίοις πατράσιν, ἕνα καὶ τὸν αὐτὸν ὁμολογεῖν υἱὸν τὸν κύριον ἡμῶν Ἰησοῦν Χριστὸν συμφώνως ἅπαντες ἐκδιδάσκομεν, τέλειον τὸν αὐτὸν ἐν θεότητι καὶ τέλειον τὸν αὐτὸν ἐν ἀνθρωπότητι, θεὸν ἀληθῶς καὶ ἄνθρωπον ἀληθῶς τὸν αὐτόν, ἐκ ψυχῆς λογικῆς καὶ σώματος, ὁμοούσιον τῷ πατρὶ κατὰ τὴν θεότητα καὶ ὁμοούσιον τὸν αὐτὸν ἡμῖν κατὰ τὴν ἀνθρωπότητα, κατὰ πάντα ὅμοιον ἡμῖν χωρὶς ἁμαρτίας· πρὸ αἰώνων μὲν ἐκ τοῦ πατρὸς γεννηθέντα κατὰ τὴν θεότητα, ἐπ' ἐσχάτων δὲ τῶν ἡμερῶν τὸν αὐτὸν δι' ἡμᾶς καὶ διὰ τὴν ἡμετέραν σωτηρίαν ἐκ Μαρίας τῆς παρθένου τῆς θεοτόκου κατὰ τὴν ἀνθρωπότητα, ἕνα καὶ τὸν αὐτὸν Χριστόν, υἱόν, κύριον, μονογενῆ, ἐν δύο φύσεσιν ἀσυγχύτως, ἀτρέπτως, ἀδιαιρέτως, ἀχωρίστως γνωριζόμενον· οὐδαμοῦ τῆς τῶν φύσεων διαφορᾶς ἀνῃρημένης διὰ τὴν ἕνωσιν, σωζομένης δὲ μᾶλλον τῆς ἰδιότητος ἑκατέρας φύσεως καὶ εἰς ἓν πρόσωπον καὶ μίαν ὑπόστασιν συντρεχούσης, οὐκ εἰς δύο πρόσωπα μεριζόμενον ἢ διαιρούμενον, ἀλλ' ἕνα καὶ τὸν αὐτὸν υἱὸν καὶ μονογενῆ θεὸν λόγον, κύριον Ἰησοῦν Χριστόν· καθάπερ ἄνωθεν οἱ προφῆται περὶ αὐτοῦ καὶ αὐτὸς ἡμᾶς ὁ κύριος Ἰησοῦς Χριστὸς ἐξεπαίδευσε καὶ τὸ τῶν πατέρων ἡμῖν παραδέδωκε σύμβολον.",
            "Prohibitions": "Τούτων τοίνυν μετὰ πάσης πανταχόθεν ἀκριβείας τε καὶ ἐμμελείας διατυπωθέντων ἡμῖν, ὥρισεν ἡ ἁγία καὶ οἰκουμενικὴ σύνοδος, ἑτέραν πίστιν μηδενὶ ἐξεῖναι προφέρειν, ἤγουν συγγράφειν ἢ συντιθέναι ἢ φρονεῖν ἢ διδάσκειν ἑτέρους· τοὺς δὲ τολμῶντας ἢ συντιθέναι πίστιν ἑτέραν, ἤγουν προκομίζειν ἢ διδάσκειν ἢ παραδιδόναι ἕτερον σύμβολον τοῖς ἐθέλουσιν ἐπιστρέφειν εἰς ἐπίγνωσιν τῆς ἀληθείας ἐξ Ἑλληνισμοῦ ἢ ἐξ Ἰουδαϊσμοῦ ἢ γοῦν ἐξ αἱρέσεως οἱασδηποτοῦν, τούτους, εἰ μὲν εἶεν ἐπίσκοποι ἢ κληρικοί, ἀλλοτρίους εἶναι τοὺς ἐπισκόπους τῆς ἐπισκοπῆς καὶ τοὺς κληρικοὺς τοῦ κλήρου, εἰ δὲ μονάζοντες ἢ λαϊκοὶ εἶεν, ἀναθεματίζεσθαι.",
        },
    },
}

# Topic-level notes for creed texts. These are intentionally separated from the
# creed body so we can explain textual/traditional variants without altering the
# source document text.
CREED_NOTES = {
    "The Nicene Creed": (
        "**Filioque note:** This local English text includes the Filioque clause "
        "('and the Son') in the line on the Holy Spirit: 'He proceeds from the "
        "Father and the Son.' The Greek text shown here preserves the older "
        "conciliar wording, 'from the Father,' without the later Latin addition.\n\n"
        "**Generally accept/use the Filioque:** Roman Catholic/Latin Western "
        "tradition and many Western Protestant traditions, including much "
        "Anglican, Lutheran, Reformed, Methodist, and Baptist usage.\n\n"
        "**Generally deny or omit the Filioque:** Eastern Orthodox churches, "
        "Oriental Orthodox churches, and the Church of the East. Some Eastern "
        "Catholic churches may omit it liturgically while remaining in communion "
        "with Rome."
    )
}

# Rich styles used across panels/tables. Keep style names stable; rendering
# methods reference these string keys directly.
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError:
        pass

def save_theme_preference(theme_mode):
    config = load_config()
    config["theme"] = theme_mode
    save_config(config)

def clear_theme_preference():
    config = load_config()
    config.pop("theme", None)
    save_config(config)

def save_bible_preference(bible_id):
    config = load_config()
    config["bible"] = bible_id
    save_config(config)

def load_bible_preference():
    return load_config().get("bible", "esv")

def normalize_theme_value(value):
    value = (value or "").strip().lower()
    if not value:
        return None
    if value in {"light", "bright", "day"}:
        return "light"
    if value in {"dark", "black", "night"}:
        return "dark"
    if re.search(r"(^|[^a-z])(light|bright|day)([^a-z]|$)", value):
        return "light"
    if re.search(r"(^|[^a-z])(dark|black|night)([^a-z]|$)", value):
        return "dark"
    return None

def rgb_luminance(red, green, blue):
    def linearize(channel):
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
    r, g, b = linearize(red), linearize(green), linearize(blue)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def theme_from_rgb(red, green, blue):
    return "light" if rgb_luminance(red, green, blue) >= 0.45 else "dark"

def rgb_from_archived_color(data):
    if not isinstance(data, (bytes, bytearray)):
        return None
    matches = re.findall(rb"([01](?:\.\d+)?) ([01](?:\.\d+)?) ([01](?:\.\d+)?) ([01](?:\.\d+)?)", data)
    if not matches:
        return None
    red, green, blue, _alpha = (float(part) for part in matches[-1])
    return red, green, blue

def theme_from_colorfgbg():
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            background = int(colorfgbg.split(";")[-1])
            return "light" if background in range(7, 16) else "dark"
        except ValueError:
            pass
    return None

def theme_from_env_hints():
    for key in (
        "LEX_THEME",
        "TERMINAL_THEME",
        "COLOR_SCHEME",
        "THEME",
        "VSCODE_COLOR_THEME",
        "ITERM_PROFILE",
        "WT_PROFILE",
        "TERM_PROGRAM",
    ):
        theme = normalize_theme_value(os.environ.get(key))
        if theme:
            return theme
    return None

def theme_from_apple_terminal_profile():
    if sys.platform != "darwin" or os.environ.get("TERM_PROGRAM") != "Apple_Terminal":
        return None
    try:
        exported = subprocess.run(
            ["defaults", "export", "com.apple.Terminal", "-"],
            capture_output=True,
            timeout=0.75,
            check=False,
        )
        if exported.returncode != 0 or not exported.stdout:
            return None
        prefs = plistlib.loads(exported.stdout)
    except (OSError, plistlib.InvalidFileException, subprocess.SubprocessError):
        return None

    profile_name = (
        os.environ.get("TERM_PROFILE")
        or prefs.get("Startup Window Settings")
        or prefs.get("Default Window Settings")
    )
    profile = (prefs.get("Window Settings") or {}).get(profile_name or "")
    if not isinstance(profile, dict):
        return normalize_theme_value(profile_name)

    rgb = rgb_from_archived_color(profile.get("BackgroundColor"))
    if rgb:
        return theme_from_rgb(*rgb)

    return normalize_theme_value(profile_name) or "light"

def theme_from_iterm_profile():
    if sys.platform != "darwin" or os.environ.get("TERM_PROGRAM") != "iTerm.app":
        return None
    try:
        exported = subprocess.run(
            ["defaults", "export", "com.googlecode.iterm2", "-"],
            capture_output=True,
            timeout=0.75,
            check=False,
        )
        if exported.returncode != 0 or not exported.stdout:
            return None
        prefs = plistlib.loads(exported.stdout)
    except (OSError, plistlib.InvalidFileException, subprocess.SubprocessError):
        return None

    profiles = prefs.get("New Bookmarks") or []
    profile_hint = os.environ.get("ITERM_PROFILE")
    default_guid = prefs.get("Default Bookmark Guid")
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        name = profile.get("Name")
        guid = profile.get("Guid")
        if profile_hint and name != profile_hint:
            continue
        if not profile_hint and default_guid and guid != default_guid:
            continue
        red = profile.get("Background Color", {}).get("Red Component")
        green = profile.get("Background Color", {}).get("Green Component")
        blue = profile.get("Background Color", {}).get("Blue Component")
        if None not in (red, green, blue):
            return theme_from_rgb(float(red), float(green), float(blue))
        return normalize_theme_value(name)
    return normalize_theme_value(profile_hint)

def theme_from_linux_desktop():
    if not sys.platform.startswith("linux"):
        return None

    commands = (
        ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
        ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
        ["kreadconfig6", "--group", "General", "--key", "ColorScheme"],
        ["kreadconfig5", "--group", "General", "--key", "ColorScheme"],
    )
    for command in commands:
        executable = shutil.which(command[0])
        if not executable:
            continue
        try:
            proc = subprocess.run(
                [executable, *command[1:]],
                capture_output=True,
                text=True,
                timeout=0.5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0:
            theme = normalize_theme_value(proc.stdout.strip().strip("'\""))
            if theme:
                return theme

    return None

def theme_from_macos_appearance():
    if sys.platform != "darwin":
        return None
    try:
        proc = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip().lower() == "dark":
            return "dark"
        return "light"
    except (OSError, subprocess.SubprocessError):
        return None

def detect_terminal_theme():
    for detector in (
        theme_from_env_hints,
        theme_from_colorfgbg,
        theme_from_apple_terminal_profile,
        theme_from_iterm_profile,
        theme_from_linux_desktop,
        theme_from_macos_appearance,
    ):
        theme = detector()
        if theme in {"light", "dark"}:
            return theme

    return "dark"

def resolve_theme_mode(raw_argv):
    if "-light" in raw_argv:
        return "light"
    if "-dark" in raw_argv:
        return "dark"
    if "-auto" in raw_argv:
        return detect_terminal_theme()

    env_theme = os.environ.get("LEX_THEME", "").strip().lower()
    if env_theme in {"light", "dark"}:
        return env_theme

    saved_theme = load_config().get("theme")
    if saved_theme in {"light", "dark"}:
        return saved_theme

    return detect_terminal_theme()

def has_theme_override(raw_argv):
    if "-auto" in raw_argv:
        return False
    if "-light" in raw_argv or "-dark" in raw_argv:
        return True

    env_theme = os.environ.get("LEX_THEME", "").strip().lower()
    if env_theme in {"light", "dark"}:
        return True

    return load_config().get("theme") in {"light", "dark"}

def resolve_no_color(raw_argv):
    if os.environ.get("LEX_NO_COLOR"):
        return True
    return False

def build_theme(theme_mode):
    if theme_mode == "light":
        text_style = "rgb(31,31,31)"
        strong_text_style = "bold rgb(31,31,31)"
        muted_text_style = "rgb(100,100,100)"
        accent_style = "rgb(180,30,40)" # Crimson / Red
        accent_strong_style = "bold rgb(180,30,40)"
        success_style = "rgb(30,100,50)" # Deep Green
        warning_style = "rgb(160,100,0)" # Ochre
        border_style = "rgb(200,190,170)" # Warm divider
        verse_ref_style = accent_strong_style
        verse_ref_muted_style = "rgb(130,120,110)"
        highlight_style = "rgb(31,31,31) on rgb(240,220,150) underline"
        marker_style = "bold rgb(31,31,31) on rgb(240,220,150)"
        source_style = "rgb(47,92,160)" # Biblical blue
        translit_style = "italic rgb(100,90,80)"
    else:
        text_style = "grey93"
        strong_text_style = "bold white"
        muted_text_style = "grey50"
        accent_style = "dark_orange"
        accent_strong_style = "bold dark_orange"
        success_style = "bold spring_green3"
        warning_style = "bold sandy_brown"
        border_style = "grey27"
        verse_ref_style = "bold orange3"
        verse_ref_muted_style = "grey42"
        highlight_style = "bold grey93 on grey19"
        marker_style = "bold grey93 on grey19"
        source_style = "bold sky_blue3"
        translit_style = "italic grey62"

    return Theme({
        "text": text_style,
        "text.strong": strong_text_style,
        "text.muted": muted_text_style,
        "info": accent_style,
        "warning": warning_style,
        "success": success_style,
        "ui.action": accent_style,
        "ui.action.key": accent_strong_style,
        "ui.border": border_style,
        "ui.meta": muted_text_style,
        "search.hit": highlight_style,
        "verse.marker": marker_style,
        "verse.ref": verse_ref_style,
        "verse.ref.muted": verse_ref_muted_style,
        "verse.text": text_style,
        "verse.text.focus": strong_text_style,
        "verse.text.muted": muted_text_style,
        "verse.border": border_style,
        "source.text": source_style,
        "source.translit": translit_style,
        "source.border": border_style,
        "lexicon.num": accent_strong_style,
        "lexicon.word": success_style,
        "place.name": warning_style,
        "dict.topic": "rgb(110,60,160)" if theme_mode == "light" else "bold orchid",
        "interlinear.strongs": accent_style,
        "interlinear.translit": translit_style,
    })

ACTIVE_THEME_MODE = resolve_theme_mode(sys.argv[1:])
custom_theme = build_theme(ACTIVE_THEME_MODE)
console_base_style = "rgb(31,31,31) on rgb(249,247,242)" if ACTIVE_THEME_MODE == "light" else "grey93 on grey11"

def detect_console_width():
    for candidate in (os.environ.get("COLUMNS"),):
        try:
            width = int(candidate)
            if width >= 40:
                return width
        except (TypeError, ValueError):
            pass
    try:
        width = os.get_terminal_size(sys.stdout.fileno()).columns
        if width >= 40:
            return width
    except OSError:
        pass
    width = shutil.get_terminal_size((100, 24)).columns
    return max(40, width)

class BackgroundFillWriter:
    def __init__(self, stream, fill_sequence):
        self.stream = stream
        self.fill_sequence = fill_sequence

    def write(self, data):
        if self.fill_sequence:
            data = data.replace("\n", f"{self.fill_sequence}\n")
        return self.stream.write(data)

    def flush(self):
        return self.stream.flush()

    def isatty(self):
        return self.stream.isatty()

    def __getattr__(self, name):
        return getattr(self.stream, name)

def line_fill_sequence():
    if resolve_no_color(sys.argv[1:]) or not sys.stdout.isatty():
        return ""
    return "\033[48;5;231m\033[K" if ACTIVE_THEME_MODE == "light" else "\033[40m\033[K"

console = Console(
    color_system="256",
    theme=custom_theme,
    style=console_base_style,
    no_color=resolve_no_color(sys.argv[1:]),
    width=detect_console_width(),
    file=BackgroundFillWriter(sys.stdout, line_fill_sequence()),
)

def fill_terminal_row(text, style="text"):
    rendered = Text(text, style=style)
    remaining = max(0, console.width - rendered.cell_len)
    if remaining:
        rendered.append(" " * remaining, style=style)
    return rendered

# ---------------------------------------------------------------------------
# Database and application coordinator
# ---------------------------------------------------------------------------
class LexDB:
    def __init__(self, db_path):
        self.db_path = db_path

    def query(self, sql, params=()):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

class LexAgent:
    # LexAgent owns all local data access and terminal rendering. The CLI parser
    # at the bottom should stay thin and dispatch into these feature methods.
    def __init__(self, bible_id=None):
        if bible_id is None:
            bible_id = load_bible_preference()
        
        self.db = LexDB(LEXICON_DB_PATH)
        bible_path = get_bible_path(bible_id)
        self.bible_db = LexDB(bible_path if os.path.exists(bible_path) else LEXICON_DB_PATH)
        
        # Determine reference prefix from bible metadata
        self.bible_prefix = "esv"
        prefix_res = self.bible_db.query("SELECT value FROM metadata WHERE key='reference_prefix'")
        if prefix_res:
            self.bible_prefix = prefix_res[0][0]
        
        # Build dynamic book mapping from the active database references
        self.canon_map = {}
        self.reverse_canon_map = {}
        # 1. First, index everything actually IN the database
        books_res = self.bible_db.query("SELECT DISTINCT reference FROM bible")
        for (ref,) in books_res:
            parts = ref.split(":")
            if len(parts) >= 2:
                db_book = parts[1]
                # Map the compact version of the DB string to itself
                self.canon_map[re.sub(r"[^a-z0-9]+", "", db_book.lower())] = db_book
                # Default reverse map to itself
                self.reverse_canon_map[db_book] = db_book

        # 2. Map all standard aliases and full names to the DB's preferred string
        # For each canonical book, find if any of its aliases are in the DB.
        # If so, map all other aliases to that same DB identifier.
        for book in BIBLE_BOOKS:
            # Gather all keys that refer to this book
            aliases = [a for a, f in BOOK_SCOPE_ALIASES.items() if f == book]
            aliases.append(re.sub(r"[^a-z0-9]+", "", book.lower()))
            
            # Find if any of these are in the DB
            db_target = None
            for a in aliases:
                if a in self.canon_map:
                    db_target = self.canon_map[a]
                    break
            
            if db_target:
                for a in aliases:
                    self.canon_map[a] = db_target
                # Also map reverse for study mode
                canon_target = "Psalm" if book == "Psalms" else book
                self.reverse_canon_map[db_target] = canon_target

        self.encyclopedia_db = LexDB(ENCYCLOPEDIA_DB_PATH) if os.path.exists(ENCYCLOPEDIA_DB_PATH) else None
        self.cross_refs_db = LexDB(CROSS_REFS_DB_PATH if os.path.exists(CROSS_REFS_DB_PATH) else LEXICON_DB_PATH)
        self.strongs_db = LexDB(STRONGS_DB_PATH if os.path.exists(STRONGS_DB_PATH) else LEXICON_DB_PATH)
        self.dictionary_db = LexDB(DICTIONARY_DB_PATH if os.path.exists(DICTIONARY_DB_PATH) else LEXICON_DB_PATH)
        self.creeds_db = LexDB(CREEDS_DB_PATH if os.path.exists(CREEDS_DB_PATH) else LEXICON_DB_PATH)
        self.places_db = LexDB(PLACES_DB_PATH if os.path.exists(PLACES_DB_PATH) else LEXICON_DB_PATH)
        self.henry_db = LexDB(HENRY_DB_PATH) if os.path.exists(HENRY_DB_PATH) else None
        self.calvin_db = LexDB(CALVIN_DB_PATH) if os.path.exists(CALVIN_DB_PATH) else None
        self.naves_db = LexDB(NAVES_DB_PATH) if os.path.exists(NAVES_DB_PATH) else None
        self.last_ref = self.load_history()
        self._interlinear_index = None
        self._ordered_refs = None
        self._interlinear_strongs = None
        self._step_greek = None
        self._step_hebrew = None

    # -----------------------------------------------------------------------
    # Shared utilities and lazy data loading
    # -----------------------------------------------------------------------
    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f: return f.read().strip()
            except: pass
        return None

    def save_history(self, ref):
        try:
            with open(HISTORY_FILE, "w") as f: f.write(ref)
        except: pass

    def clean_text(self, text):
        text = re.sub(r' <[GH]\d+>', '', text)
        text = re.sub(r'\*[a-z]+', '', text)
        text = re.sub(r'\byourln\b', 'your', text, flags=re.IGNORECASE)
        text = re.sub(r'\bonld\b', 'on', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/?[a-z]+\]', '', text)
        return text.strip()

    def escape_fts_query(self, query):
        cleaned = re.sub(r"[^\w\s]", " ", query).strip()
        if not cleaned:
            return None
        return f"\"{' '.join(cleaned.split())}\""

    def fts_terms_query(self, query):
        terms = re.findall(r"\w+", query)
        if not terms:
            return None
        return " AND ".join(f'"{term}"' for term in terms)

    def parse_book_scope(self, token):
        raw = token.strip()
        if not raw.startswith("-") or raw.startswith("--"):
            return None
        scope = raw.lstrip("-").lower().strip()
        if not scope:
            return None
        scope = re.sub(r"[^a-z0-9]+", "-", scope).strip("-")
        if scope in BOOK_SCOPE_GROUPS:
            return {
                "label": scope,
                "books": BOOK_SCOPE_GROUPS[scope],
            }
        if scope in BOOK_SCOPE_ALIASES:
            book = BOOK_SCOPE_ALIASES[scope]
            return {
                "label": book,
                "books": [book],
            }
        aliases = sorted(BOOK_SCOPE_ALIASES, key=len, reverse=True)
        for start_alias in aliases:
            prefix = f"{start_alias}-"
            if not scope.startswith(prefix):
                continue
            end_alias = scope[len(prefix):]
            if end_alias not in BOOK_SCOPE_ALIASES:
                continue
            start_book = BOOK_SCOPE_ALIASES[start_alias]
            end_book = BOOK_SCOPE_ALIASES[end_alias]
            start_idx = BIBLE_BOOK_INDEX[start_book]
            end_idx = BIBLE_BOOK_INDEX[end_book]
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
                start_book, end_book = end_book, start_book
            return {
                "label": f"{start_book}-{end_book}",
                "books": BIBLE_BOOKS[start_idx:end_idx + 1],
            }
        return None

    def parse_search_query_and_scope(self, query):
        try:
            tokens = shlex.split(query)
        except ValueError:
            tokens = query.split()
        kept = []
        scope = None
        for token in tokens:
            parsed_scope = self.parse_book_scope(token)
            if parsed_scope:
                scope = parsed_scope
            else:
                kept.append(token)
        return " ".join(kept).strip(), scope

    def highlight_search_terms(self, text, query):
        result = Text()
        terms = sorted(set(re.findall(r"\w+", query)), key=len, reverse=True)
        if not terms:
            result.append(text, style="verse.text")
            return result
        pattern = re.compile("(" + "|".join(re.escape(term) for term in terms) + ")", re.IGNORECASE)
        pos = 0
        for match in pattern.finditer(text):
            if match.start() > pos:
                result.append(text[pos:match.start()], style="verse.text")
            result.append(match.group(0), style="search.hit")
            pos = match.end()
        if pos < len(text):
            result.append(text[pos:], style="verse.text")
        return result

    def normalize_term(self, text):
        return re.sub(r"[^a-z0-9]+", "", text.lower())

    def normalize_strongs_key(self, key):
        match = re.match(r"([gh])0*(\d+)$", key.lower())
        if not match:
            return None, None, None
        prefix, num = match.groups()
        return f"{prefix}{int(num)}", f"{prefix.upper()}{int(num)}", f"{prefix.upper()}{int(num):04d}"

    def load_json_file(self, path):
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_interlinear_index(self):
        if self._interlinear_index is None:
            data = self.load_json_file(INTERLINEAR_PATH) or []
            self._interlinear_index = {}
            for row in data:
                ref = row.get("r")
                if not ref:
                    continue
                existing = self._interlinear_index.get(ref)
                # Some source rows are heading/context rows with the same ref.
                # Prefer rows with phrase data so study mode gets real tokens.
                if existing is None or (row.get("p") and not existing.get("p")):
                    self._interlinear_index[ref] = row
            self._ordered_refs = [
                row["r"] for row in data
                if row.get("r", "").startswith(f"{self.bible_prefix}:") and row.get("r", "").count(":") == 3 and not row.get("h")
            ]
        return self._interlinear_index

    def get_ordered_refs(self):
        if self._ordered_refs is None:
            # If interlinear data isn't available for this version, load refs from the DB
            if not os.path.exists(INTERLINEAR_PATH) or self.bible_prefix != "esv":
                res = self.bible_db.query("SELECT reference FROM bible WHERE reference NOT LIKE '%:0' ORDER BY id")
                self._ordered_refs = [row[0] for row in res]
            else:
                self.get_interlinear_index()
        return self._ordered_refs or []

    def get_interlinear_strongs(self):
        if self._interlinear_strongs is None:
            self._interlinear_strongs = self.load_json_file(INTERLINEAR_STRONGS_PATH) or {}
        return self._interlinear_strongs

    def get_step_greek(self):
        if self._step_greek is None:
            self._step_greek = self.load_json_file(STEP_GREEK_PATH) or {}
        return self._step_greek

    def get_step_hebrew(self):
        if self._step_hebrew is None:
            self._step_hebrew = self.load_json_file(STEP_HEBREW_PATH) or {}
        return self._step_hebrew

    def parse_history_ref(self, ref):
        if not ref:
            return None
        verse_match = re.match(r"^(?:[a-z0-9]+:)?(.+?):(\d+):(\d+)$", ref, re.IGNORECASE)
        if verse_match:
            book, chap, verse = verse_match.groups()
            return {"kind": "verse", "book": book, "chapter": int(chap), "verse": int(verse), "reference": ref}
        chapter_match = re.match(r"^(.*?)\s+(\d+)$", ref)
        if chapter_match:
            book, chap = chapter_match.groups()
            return {"kind": "chapter", "book": book, "chapter": int(chap), "reference": ref}
        return None

    def parse_reference_parts(self, db_ref):
        parts = db_ref.split(":")
        if len(parts) < 4:
            return None
        return {
            "version": parts[0],
            "book": parts[1],
            "chapter": int(parts[2]),
            "verse": int(parts[3]),
            "reference": db_ref,
        }

    def convert_to_tsk_ref(self, book, chapter, verse=None):
        prefix = TSK_BOOK_ABBR.get(book, book)
        if not prefix.endswith("."):
            prefix += "."
        return f"{prefix}{chapter}.{verse}" if verse else f"{prefix}{chapter}."

    def parse_tsk_ref(self, tsk_ref):
        first_ref = tsk_ref.split("-", 1)[0]
        match = re.match(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)$", first_ref)
        if not match:
            return None
        book_abbr, chapter, verse = match.groups()
        book = TSK_TO_BOOK.get(book_abbr)
        if not book:
            return None
        return f"esv:{book}:{int(chapter)}:{int(verse)}"

    def get_tsk_crossrefs(self, db_ref):
        parts = self.parse_reference_parts(db_ref)
        if not parts:
            return []
        tsk_ref = self.convert_to_tsk_ref(parts["book"], parts["chapter"], parts["verse"])
        return self.cross_refs_db.query(
            "SELECT to_ref, votes FROM cross_refs WHERE from_ref = ? ORDER BY votes DESC, to_ref",
            (tsk_ref,)
        )

    def get_crossref_preview(self, tsk_ref):
        db_ref = self.parse_tsk_ref(tsk_ref)
        if not db_ref:
            return None
        row = self.bible_db.query(
            "SELECT text FROM bible WHERE reference = ? ORDER BY id LIMIT 1",
            (db_ref,)
        )
        return self.clean_text(row[0][0]) if row else None

    def get_navigation_reference(self, current_ref, direction):
        refs = self.get_ordered_refs()
        try:
            idx = refs.index(current_ref)
        except ValueError:
            return None
        target_idx = idx + (1 if direction == "next" else -1)
        if target_idx < 0 or target_idx >= len(refs):
            return None
        return refs[target_idx]

    def get_adjacent_chapter_reference(self, book, chapter, direction):
        chapters = []
        seen = set()
        for ref in self.get_ordered_refs():
            parts = self.parse_reference_parts(ref)
            if not parts:
                continue
            key = (parts["book"], parts["chapter"])
            if key not in seen:
                seen.add(key)
                chapters.append(key)
        try:
            idx = chapters.index((book, chapter))
        except ValueError:
            return None
        target_idx = idx + (1 if direction == "next" else -1)
        if target_idx < 0 or target_idx >= len(chapters):
            return None
        target_book, target_chapter = chapters[target_idx]
        for ref in self.get_ordered_refs():
            parts = self.parse_reference_parts(ref)
            if parts and parts["book"] == target_book and parts["chapter"] == target_chapter:
                return ref
        return None

    def resolve_navigation_query(self, direction):
        parsed = self.parse_history_ref(self.last_ref)
        if not parsed:
            return None
        if parsed["kind"] == "verse":
            ref = self.get_navigation_reference(parsed["reference"], direction)
            if not ref:
                return None
            parts = self.parse_reference_parts(ref)
            return f"{parts['book']} {parts['chapter']}:{parts['verse']}" if parts else None
        ref = self.get_adjacent_chapter_reference(parsed["book"], parsed["chapter"], direction)
        if not ref:
            return None
        parts = self.parse_reference_parts(ref)
        return f"{parts['book']} {parts['chapter']}" if parts else None

    def normalize_ref(self, q):
        # User-facing references are intentionally forgiving here. The DB still
        # uses canonical "version:Book:Chapter:Verse" strings internally.
        q_clean = q.lower().strip()
        
        # 1. Try standard spaced reference: '1 John 3:16', 'John 3:16', '1 Jn 3'
        # Book is anything before the last set of digits
        pattern_spaced = r'^([1-3]?\s?[a-z\s.]+?)\s+(\d+)(?:[\s:.](\d+))?$'
        match = re.match(pattern_spaced, q_clean)
        
        # 2. Try compact reference: '1cor13', 'jn3:16'
        if not match:
            pattern_compact = r'^([1-3]?[a-z\s.]+?)(\d+)(?:[\s:.](\d+))?$'
            match = re.match(pattern_compact, q_clean)

        if match:
            b, c, v = match.groups()
            b = b.strip()
            # For slugs and compact keys, we want to normalize the book part
            # '1 john' -> '1-john' and '1john'
            b_slug = re.sub(r"[^a-z0-9]+", "-", b.lower()).strip("-")
            b_compact = re.sub(r"[^a-z0-9]+", "", b.lower())
            
            # 1. Try dynamic canon map from active DB
            b_name = self.canon_map.get(b_compact) or self.canon_map.get(b_slug)
            
            # 2. Try static aliases
            if not b_name:
                b_name = BOOK_SCOPE_ALIASES.get(b_compact) or BOOK_SCOPE_ALIASES.get(b_slug)
            
            # 3. Handle cases where the number might be separate in our mapping: '1-john' vs '1john'
            if not b_name and b_slug.startswith(("1-", "2-", "3-")):
                alt_compact = b_slug.replace("-", "", 1)
                b_name = self.canon_map.get(alt_compact) or BOOK_SCOPE_ALIASES.get(alt_compact)
            
            # 4. Fallback to title case
            if not b_name:
                b_name = b.title()
            
            # Final resolution to ensure we use the exact DB book name
            b_name_key = re.sub(r"[^a-z0-9]+", "", b_name.lower())
            b_name = self.canon_map.get(b_name_key, b_name)
            
            return f"{b_name}:{c}:{v}" if v else f"{b_name}:{c}", b_name, c, v
        return None, None, None, None

    # -----------------------------------------------------------------------
    # Landing pages, help, and credits
    # -----------------------------------------------------------------------
    def display_intro(self):
        logo = Text(
            r"""
██╗     ███████╗██╗  ██╗
██║     ██╔════╝╚██╗██╔╝
██║     █████╗   ╚███╔╝
██║     ██╔══╝   ██╔██╗
███████╗███████╗██╔╝ ██╗
╚══════╝╚══════╝╚═╝  ╚═╝
""",
            style="bold gold3",
        )
        title = Text("Lex: The Elegant Bible Terminal", style="text.strong")
        tagline = Text("Master Admin Study Tool for the Source Code of the Universe", style="bold cyan")
        positioning = Text(
            "Read the canon. Inspect the languages. Traverse the tradition.",
            style="dim",
        )

        metrics = Table.grid(padding=(0, 2))
        metrics.add_column(justify="center", style="bold gold3")
        metrics.add_column(justify="center", style="bold green")
        metrics.add_column(justify="center", style="bold cyan")
        metrics.add_column(justify="center", style="bold magenta")
        metrics.add_row("66 books", "TSK graph", "Strong's + STEPBible", "Creeds + ISBE")

        primary = Table.grid(padding=(0, 2))
        primary.add_column(style="bold green", no_wrap=True)
        primary.add_column(style="text")
        primary.add_row("Read:", "lex read John 3:16  (Context with navigation)")
        primary.add_row("Study:", "lex study John 3:16  (Interlinear + lexicon)")
        primary.add_row("Search:", 'lex search "mustard seed"  (Ranked search results)')
        primary.add_row("Strong's Lookup:", "lex strongs love  or  lex G3056")

        also = Table.grid(padding=(0, 2))
        also.add_column(style="bold gold3", no_wrap=True)
        also.add_column(style="text")
        also.add_row("Quick Read:", "lex John 3:16")
        also.add_row("Quick Study:", "lex John 3:16 -i")
        also.add_row("Verse Web:", "lex web John 3:16")
        also.add_row("Commentary:", "lex commentary John 3:16")
        also.add_row("Nave's Topics:", "lex topic church  or  lex naves grace")
        also.add_row("Lexicon:", "lex G3056  or  lex logos")
        also.add_row("Creeds:", "lex creed")
        also.add_row("Define:", "lex define grace")
        also.add_row("Versions:", "lex -v  (Interactive version menu)")
        also.add_row("Switch Bible:", "lex version kjv  or  lex -v nasb")
        also.add_row("Select Once:", "lex -B lxx John 1:1")

        config = Table.grid(padding=(0, 2))
        config.add_column(style="ui.action.key", no_wrap=True)
        config.add_column(style="text")
        config.add_row("lex -light", "Use and remember the light terminal theme")
        config.add_row("lex -dark", "Use and remember the dark terminal theme")
        config.add_row("lex -auto", "Clear the saved theme and auto-detect again")
        config.add_row("LEX_THEME=light lex", "Use a theme for one shell command")
        config.add_row("LEX_NO_COLOR=1 lex", "Print plain output without Lex colors")

        launch = Table.grid(padding=(0, 1))
        launch.add_column(style="dim")
        launch.add_column(style="bold gold3")
        launch.add_column(style="dim")
        launch.add_row("MODE", "LOCAL-FIRST", "No browser tabs. No drift. Just the sources.")

        nav = Text()
        nav.append("Quick Navigation: ", style="bold cyan")
        nav.append("lex --next", style="gold3")
        nav.append(" | ")
        nav.append("lex --prev", style="gold3")
        nav.append("  (Relative to your last read reference)", style="dim")

        credits = Table.grid(padding=(0, 2))
        credits.add_column(style="bold cyan", no_wrap=True)
        credits.add_column(style="dim")
        credits.add_row("Credits:", "ESV text, TSK/OpenBible, Strong's, STEPBible, UBS, Easton, ISBE, TheologAI historical docs")
        credits.add_row("License:", "Lex code MIT; data remains under source terms. Run lex --credits")

        footer = Text("Start with a verb, or type a reference directly.", style="italic dim")
        console.print(
            Panel(
                Group(
                    Align.center(logo),
                    Align.center(title),
                    Align.center(tagline),
                    Align.center(positioning),
                    "",
                    Align.center(metrics),
                    "",
                    Text("Start with a verb.", style="text.strong"),
                    "",
                    Text("Primary", style="bold cyan"),
                    primary,
                    "",
                    Text("Also Available", style="bold cyan"),
                    also,
                    "",
                    Text("Config", style="bold cyan"),
                    config,
                    "",
                    nav,
                    "",
                    Align.center(launch),
                    "",
                    credits,
                    Align.center(footer),
                ),
                title=f"Lex {VERSION}",
                subtitle="source-aware bible study, shipped as a command",
                border_style="bold cyan",
                padding=(1, 3),
                expand=False,
            )
        )

    def display_credits(self):
        table = Table(title="Lex Credits and Data Licenses", box=None, show_lines=True)
        table.add_column("Component", style="bold cyan", no_wrap=True)
        table.add_column("Source / Repo", style="text", overflow="fold")
        table.add_column("License / Terms", style="gold3", overflow="fold")
        table.add_row(
            "Lex CLI code",
            "Local project code: /home/n8te/lex_v3.py",
            "Recommended: MIT for application code only",
        )
        table.add_row(
            "Bible text",
            "Local bible-data / ESV-derived SQLite: bible_versions/esv.db; source package notes: bible-data",
            "Permission/copyright-controlled translation text; do not relicense as MIT",
        )
        table.add_row(
            "TSK cross refs",
            "Treasury of Scripture Knowledge / OpenBible-style cross-reference data",
            "Verify upstream terms before redistribution",
        )
        table.add_row(
            "Strong's lexicon",
            "OpenScriptures Strong's Hebrew and Greek Dictionaries: github.com/openscriptures/strongs",
            "Local XHTML says GPL-3.0; another local source note says Public Domain. Verify source chain before distribution",
        )
        table.add_row(
            "STEPBible language data",
            "STEPBible Data: github.com/STEPBible/STEPBible-Data; www.STEPBible.org",
            "CC BY 4.0; credit STEP Bible",
        )
        table.add_row(
            "UBS resources",
            "UBS Open License resources: local ubs-open-license dataset",
            "CC BY-SA 4.0; preserve attribution and ShareAlike obligations",
        )
        table.add_row(
            "Bible geography",
            "OpenBible Bible Geocoding Data: openbible.info/geo",
            "CC BY 4.0; some map/image data may carry ODbL or separate CC terms",
        )
        table.add_row(
            "Dictionary",
            "Easton's Bible Dictionary entries in lexicon.db",
            "Public domain",
        )
        table.add_row(
            "Encyclopedia",
            "International Standard Bible Encyclopedia OCR import; currently local Volume II Clement-Heresh",
            "Public domain source; OCR/import quality and volume coverage still in progress",
        )
        table.add_row(
            "Creeds/confessions",
            "TheologAI historical documents dataset: local theolog-ai/data/historical-documents",
            "Public domain per local TheologAI README; preserve source attribution",
        )
        table.add_row(
            "Interlinear data",
            "Local esv-data interlinear + STEPBible/Strong's-backed resources",
            "Mixed source terms; preserve Bible text, STEPBible, and Strong's source obligations",
        )

        note = Markdown(
            """
**Recommended licensing model:** MIT for Lex application code; source-specific terms for all data.

For redistribution, include upstream license files and a `NOTICE`/`DATA_LICENSES.md`.
Do not represent the ESV text, UBS resources, STEPBible data, or generated databases as MIT-licensed.

See: `~/bible-lexicon-data/docs/LICENSING.md`
"""
        )
        console.print(Panel(Group(table, "", note), border_style="ui.border", padding=(1, 2)))

    def display_study_landing(self):
        md = """
# Lex Study
*Interlinear reading without leaving the terminal*

Study mode aligns the English verse with the source text, transliteration, lemma,
morphology, and Strong's-backed lexicon notes.

**What It Shows**

*   **Verse Context:** a compact read panel around the target verse
*   **Source Alignment:** English phrase, source token, lemma, and code
*   **Lexicon Notes:** Strong's and STEPBible definitions for Greek, Hebrew, and Aramaic
*   **Navigation:** read a verse, then move with `lex --prev` and `lex --next`

**Try These**

*   `lex study John 1:1`
*   `lex study Genesis 1:1`
*   `lex study Daniel 2:4`
*   `lex John 3:16 -i`

---
*Read the text. Inspect the words. Stay in one tool.*
"""
        console.print(Panel(Markdown(md), title="🔤 Study Mode", border_style="ui.border", expand=False))

    def display_read_landing(self):
        md = """
# Lex Read
*Scripture reading with fast terminal navigation*

Read mode centers a passage in context and keeps your place for `lex --prev`
and `lex --next`.

**What It Does**

*   **Verse View:** shows the target verse with nearby context
*   **Chapter View:** prints the full chapter in order
*   **History:** saves your last reading position for navigation
*   **Bridge to Study:** jump from reading into analysis with `lex study ...`

**Try These**

*   `lex read John 3:16`
*   `lex jn 1:1`
*   `lex study rev 1:2`
*   `lex 2 jn 1:2`
*   `lex read Genesis 1`
*   `lex John 1:1`
*   `lex --next`

---
*Open the text fast. Move without friction. Study when needed.*
"""
        console.print(Panel(Markdown(md), title="📖 Read Mode", border_style="ui.border", expand=False))

    def display_search_howto(self):
        md = """
# Search Help

Use explicit search mode:

*   `lex search "mustard seed"`
*   `lex search kingdom heaven`

Search starts with an exact phrase match. If that finds nothing, Lex falls back
to an all-terms match.

## Page Controls

*   `lex search covenant --page 2`
*   `lex search covenant --limit 20`

In an interactive terminal, search opens a compact action bar:

*   `1`, `2`, `3` - study that numbered result
*   `r 1`, `r 2` - read that numbered result
*   `n` / `p` - next or previous page
*   `e` - export menu
*   `q` - quit

Export menu:

*   `d` - DOCX
*   `f` - PDF
*   `o` - open exports folder
*   `q` - back

Exports are saved under `~/Documents/lex_exports` and Lex tries to open them after saving.

## Book Scopes

Add a single-dash scope after the search term:

*   `lex search covenant -jeremiah`
*   `lex search beast -daniel-revelation`
*   `lex search covenant -major`
*   `lex search resurrection -nt`

Book ranges follow canonical order, so `-jeremiah-revelation` searches from
Jeremiah through Revelation. Book names use lowercase words joined by hyphens:

*   `-song-of-solomon`
*   `-1-john`
*   `-1-corinthians-2-corinthians`

## Group Scopes

*   `-ot` / `-old-testament`
*   `-nt` / `-new-testament`
*   `-law` / `-pentateuch` / `-torah`
*   `-history`
*   `-wisdom` / `-poetry`
*   `-major` / `-major-prophets`
*   `-minor` / `-minor-prophets`
*   `-prophets`
*   `-gospels`
*   `-epistles` / `-letters`
*   `-pauline`
*   `-general-epistles`

Free-text search no longer runs from bare input.

## Terminal Theme Config

Lex tries to detect whether your terminal background is light or dark. You can
override it when the automatic choice is wrong:

*   `lex -light` - switch to light mode and remember it
*   `lex -dark` - switch to dark mode and remember it
*   `lex -auto` - remove the saved manual setting and detect again

The saved setting lives in `~/.lex_config.json`. If you choose `-light` or
`-dark`, Lex will keep using that theme on future launches until you run
`lex -auto` or choose the other theme.

For one command only, use an environment variable:

*   `LEX_THEME=light lex John 3:16`
*   `LEX_THEME=dark lex search covenant`

If you need plain text with no Lex colors:

*   `LEX_NO_COLOR=1 lex John 3:16`
"""
        console.print(Panel(Markdown(md), title="🔎 Search", border_style="ui.border", expand=False))

    def display_topic_howto(self):
        md = """
# Nave's Topical Bible

Browse over 20,000 topics and 100,000 scripture references. This is a 
re-implementation of the classic Nave's index using a high-signal 
blueprint layout.

## Basic Usage

*   `lex topic church`
*   `lex topic "second coming"` (Quotes required for multiple words)
*   `lex naves grace` (Alias for the same command)

## Deep Search

If a topic title isn't found exactly, Lex will automatically perform a
semantic full-text search across the content of all entries to find 
relevant thematic clusters.
"""
        console.print(Markdown(md))

    def display_commentary_howto(self):
        md = """
# Biblical Commentaries

Traverse the Christian tradition with Matthew Henry and John Calvin. 
Commentary lookups provide historical context and theological depth 
alongside your scripture study.

## Basic Usage

*   `lex commentary John 3:16`
*   `lex commentary Romans 1` (Fetches entire chapter notes)
*   `lex commentary gen 1:1` (Supports standard abbreviations)

## High-Signal View

Notes from multiple traditions are displayed in sequential themed blocks 
(Henry in Blue, Calvin in Magenta) for immediate visual comparison.
"""
        console.print(Markdown(md))

    def display_strongs_howto(self):
        md = """
# Strong's Lookup

Find Strong's entries by number, transliteration, or English gloss:

*   `lex strongs love`
*   `lex strongs word`
*   `lex strongs God`
*   `lex G3056`
"""
        console.print(Panel(Markdown(md), title="🔤 Strong's Lookup", border_style="ui.border", expand=False))

    # -----------------------------------------------------------------------
    # Bible reading and navigation rendering
    # -----------------------------------------------------------------------
    def format_display_ref(self, db_ref):
        parts = self.parse_reference_parts(db_ref)
        if not parts:
            return db_ref
        return f"{parts['book']} {parts['chapter']}:{parts['verse']}"

    def display_read_nav(self, book, chap, verse=None):
        study_ref = f"{book} {chap}:{verse or 1}"
        console.print(fill_terminal_row(f"lex --prev  |  lex --next  |  lex study {study_ref}", "ui.meta"))

    def should_animate(self, animate):
        if animate is not None:
            return animate
        return console.is_terminal and not os.environ.get("NO_COLOR")

    def render_verse_context(self, rows, target_ref, book, chap, verse):
        body = Text()
        for _, ref, text in rows:
            parts = self.parse_reference_parts(ref)
            verse_no = str(parts["verse"]) if parts else self.format_display_ref(ref)
            is_target = ref == target_ref
            marker = ">" if is_target else " "
            label_style = "verse.marker" if is_target else "verse.ref.muted"
            text_style = "verse.text.focus" if is_target else "verse.text.muted"
            body.append(f"{marker} {verse_no.rjust(3)} ", style=label_style)
            body.append(f"{self.clean_text(text)}\n", style=text_style)
        console.print(
            Panel(
                body,
                title=f"📖 {book} {chap}:{verse}",
                subtitle="context",
                border_style="verse.border",
                padding=(1, 2),
            )
        )
        self.display_read_nav(book, chap, verse)

    def render_chapter(self, rows, book, chap):
        body = Text()
        for ref, text in rows:
            parts = self.parse_reference_parts(ref)
            verse_no = str(parts["verse"]) if parts else self.format_display_ref(ref)
            body.append(f"{verse_no.rjust(3)} ", style="verse.ref")
            body.append(f"{self.clean_text(text)}\n\n", style="verse.text")
        console.print(
            Panel(
                body,
                title=f"📖 {book} {chap}",
                subtitle=f"{len(rows)} verses",
                border_style="verse.border",
                padding=(1, 2),
            )
        )
        self.display_read_nav(book, chap)

    def display_verse(self, query, interlinear=False, animate=None):
        ref_norm, book, chap, verse = self.normalize_ref(query)
        if not ref_norm: return False
        
        # Ensure we use the DB-specific book name in the LIKE query
        db_book = self.canon_map.get(re.sub(r"[^a-z0-9]+", "", book.lower()), book)
        
        if verse:
            res = self.bible_db.query(
                "SELECT MIN(id), reference, text FROM bible WHERE reference LIKE ? GROUP BY reference LIMIT 1",
                (f"%:{db_book}:{chap}:{verse}",)
            )
        else:
            res = self.bible_db.query(
                """
                SELECT reference, text
                FROM bible
                WHERE id IN (
                    SELECT MIN(id)
                    FROM bible
                    WHERE reference LIKE ? AND reference NOT LIKE '%:0'
                    GROUP BY reference
                )
                ORDER BY id
                """,
                (f"%:{db_book}:{chap}:%",)
            )
        if res:
            if verse:
                target_id, ref, text = res[0]
                context_ids = []
                current = ref
                prev2 = self.get_navigation_reference(current, "prev")
                prev1 = self.get_navigation_reference(prev2, "prev") if prev2 else None
                next1 = self.get_navigation_reference(current, "next")
                next2 = self.get_navigation_reference(next1, "next") if next1 else None
                for candidate in [prev1, prev2, current, next1, next2]:
                    if candidate:
                        row = self.bible_db.query(
                            "SELECT MIN(id), reference, text FROM bible WHERE reference = ? GROUP BY reference",
                            (candidate,)
                        )
                        if row:
                            context_ids.append(row[0])
                self.render_verse_context(context_ids, ref, book, chap, verse)
                if interlinear: 
                    self.display_study(ref, animate=animate)
                self.save_history(ref)
            else:
                self.render_chapter(res, book, chap)
                self.save_history(f"{book} {chap}")
            return True
        return False

    def display_verse_web(self, query, limit=12):
        ref_norm, book, chap, verse = self.normalize_ref(query)
        if not ref_norm or not verse:
            console.print("[warning]Verse web needs a single verse, e.g. lex web John 3:16[/]")
            return False
        rows = self.bible_db.query(
            "SELECT MIN(id), reference, text FROM bible WHERE reference LIKE ? GROUP BY reference LIMIT 1",
            (f"%:{book}:{chap}:{verse}",)
        )
        if not rows:
            return False
        _, db_ref, verse_text = rows[0]
        clean_verse = self.clean_text(verse_text)
        refs = self.get_tsk_crossrefs(db_ref)[:max(1, min(limit, 24))]

        center = Text()
        center.append(f"{book} {chap}:{verse}\n", style="verse.ref")
        center.append(clean_verse, style="text.strong")

        console.print(
            Panel(
                Align.center(center),
                title="✦ Scripture Web ✦",
                subtitle="ranked local TSK connections",
                border_style="verse.border",
                padding=(1, 2),
            )
        )

        if not refs:
            console.print("[warning]No local cross-reference links found for this verse.[/]")
            return True

        table = Table(title="Major Connections", box=None, expand=True)
        table.add_column("Rank", style="dim", justify="right", no_wrap=True)
        table.add_column("Link", style="verse.ref", no_wrap=True)
        table.add_column("Weight", style="bold cyan", justify="right", no_wrap=True)
        table.add_column("Preview", style="verse.text", overflow="fold")
        for idx, (to_ref, votes) in enumerate(refs, 1):
            preview = self.get_crossref_preview(to_ref)
            table.add_row(str(idx), to_ref, str(votes), preview[:180] if preview else "")
        console.print(table)

        spark = Text()
        for idx, (to_ref, votes) in enumerate(refs[:8], 1):
            if idx > 1:
                spark.append("  ", style="dim")
            spark.append("●", style="gold3" if idx == 1 else "cyan")
            spark.append(f" {to_ref}", style="dim")
        console.print(Panel(spark, title="Connection Trail", border_style="ui.border"))
        console.print(f"[dim]Open a link: lex read <ref>  |  Study center: lex study {book} {chap}:{verse}[/]")
        self.save_history(db_ref)
        return True

    # -----------------------------------------------------------------------
    # Study mode: source text, interlinear rows, lexicons, and TSK links
    # -----------------------------------------------------------------------
    def lookup_lexicon_entry(self, strongs_id):
        short_key, strongs_db_key, step_key = self.normalize_strongs_key(strongs_id)
        interlinear = self.get_interlinear_strongs().get(short_key) if short_key else None
        step = self.get_step_greek().get(step_key) if strongs_id.lower().startswith("g") else self.get_step_hebrew().get(step_key)
        db = self.strongs_db.query("SELECT number, word, pronunciation, definition FROM strongs WHERE number = ?", (strongs_db_key,)) if strongs_db_key else []
        return {
            "interlinear": interlinear,
            "step": step,
            "db": db[0] if db else None,
        }

    def extract_english_glosses(self, entry):
        if not entry:
            return []
        raw = entry.get("r", "")
        if "|English:" not in raw:
            return []
        english = raw.split("|English:", 1)[1]
        glosses = []
        for part in english.split(","):
            gloss = part.strip().lower()
            if gloss and gloss != "misc":
                glosses.append(gloss)
        return glosses

    def parse_interlinear_token(self, token):
        parts = token.split("|")
        while len(parts) < 10:
            parts.append("")
        strongs = parts[3].upper() if parts[3] else ""
        try:
            source_order = int(parts[0])
        except ValueError:
            source_order = None
        surface = parts[6]
        if surface in {"→", "←"}:
            surface = ""
        return {
            "source_order": source_order,
            "strongs": strongs,
            "morph": parts[4],
            "english": parts[5],
            "surface": surface,
            "translit": parts[7],
            "lemma": parts[8],
            "lemma_translit": parts[9],
            "gloss": parts[10] if len(parts) > 10 else "",
        }

    def detect_source_language(self, parsed_tokens):
        codes = [token["strongs"] for token in parsed_tokens if token["strongs"]]
        if any(code.startswith("G") for code in codes):
            return "Greek"
        if any(code.startswith("H") for code in codes):
            return "Hebrew / Aramaic"
        if any(re.search(r"[\u0590-\u05ff]", token["surface"]) for token in parsed_tokens):
            return "Hebrew / Aramaic"
        return "Source Text"

    def display_source_text(self, parsed_tokens):
        source_tokens = sorted(
            [token for token in parsed_tokens if token["surface"]],
            key=lambda token: token["source_order"] if token["source_order"] is not None else 9999,
        )
        source_words = [token["surface"] for token in source_tokens]
        if not source_words:
            return
        translit_words = [token["translit"] for token in source_tokens if token["translit"]]
        body = Text()
        body.append(" ".join(source_words), style="source.text")
        if translit_words:
            body.append("\n\n", style="ui.meta")
            body.append(" ".join(translit_words), style="source.translit")
        console.print(
            Panel(
                body,
                title=f"🔡 {self.detect_source_language(parsed_tokens)}",
                border_style="source.border",
                padding=(1, 2),
            )
        )

    def display_study_tsk(self, db_ref, parsed_tokens):
        refs = self.get_tsk_crossrefs(db_ref)
        if not refs:
            return
        anchor_words = []
        seen_words = set()
        for token in parsed_tokens:
            word = token["english"] or token["gloss"] or token["lemma"] or token["surface"]
            word = word.strip(" ,.;:!?").lower()
            if len(word) < 3 or word in seen_words:
                continue
            seen_words.add(word)
            anchor_words.append(word)
            if len(anchor_words) >= 10:
                break
        table = Table(title="🔗 Treasury of Scripture Knowledge", box=None)
        table.add_column("Ref", style="verse.ref", no_wrap=True)
        table.add_column("Votes", style="dim", justify="right")
        table.add_column("Preview", overflow="fold")
        for to_ref, votes in refs:
            preview = self.get_crossref_preview(to_ref)
            table.add_row(to_ref, str(votes), preview[:140] if preview else "")
        console.print(table)
        if anchor_words:
            console.print("[dim]Verse-level TSK links; local data has no per-word anchor. Key terms: {}[/]".format(", ".join(anchor_words)))

    def pause_study_section(self, animate):
        if self.should_animate(animate):
            time.sleep(0.16)

    def study_export_dir(self):
        path = os.path.expanduser("~/Documents/lex_exports/studies")
        os.makedirs(path, exist_ok=True)
        return path

    def study_export_filename(self, db_ref, ext):
        parts = self.parse_reference_parts(db_ref)
        label = self.format_display_ref(db_ref) if parts else db_ref
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"lex_study_{label}.{ext}").strip("_")
        return os.path.join(self.study_export_dir(), safe)

    def build_study_export_data(self, db_ref):
        row = self.get_interlinear_index().get(db_ref)
        if not row or not row.get("p"):
            return None
        parsed_tokens = [self.parse_interlinear_token(token) for token in row["p"]]
        parts = self.parse_reference_parts(db_ref)
        display_ref = self.format_display_ref(db_ref) if parts else db_ref
        verse_row = self.bible_db.query(
            "SELECT text FROM bible WHERE reference = ? ORDER BY id LIMIT 1",
            (db_ref,)
        )
        source_tokens = sorted(
            [token for token in parsed_tokens if token["surface"]],
            key=lambda token: token["source_order"] if token["source_order"] is not None else 9999,
        )
        lex_notes = []
        seen = set()
        for parsed in parsed_tokens:
            strongs = parsed["strongs"]
            if not strongs or strongs in seen:
                continue
            seen.add(strongs)
            entry = self.lookup_lexicon_entry(strongs)
            lemma = parsed["lemma"] or (entry["db"][1] if entry["db"] else "")
            pieces = []
            if parsed["morph"]:
                pieces.append(parsed["morph"])
            if entry["step"]:
                pieces.append(re.sub(r"<[^>]+>", "", entry["step"].get("definition", ""))[:280])
            elif entry["interlinear"]:
                pieces.append(entry["interlinear"].get("d", "")[:280])
            elif entry["db"]:
                pieces.append(entry["db"][3][:280])
            if entry["step"] and entry["step"].get("translit"):
                lemma = f"{lemma} ({entry['step']['translit']})"
            elif entry["db"]:
                lemma = f"{lemma} ({entry['db'][2]})"
            lex_notes.append({"strongs": strongs, "lemma": lemma or "-", "details": " | ".join(piece for piece in pieces if piece) or "-"})
            if len(lex_notes) >= 18:
                break
        tsk_refs = []
        for to_ref, votes in self.get_tsk_crossrefs(db_ref)[:24]:
            preview = self.get_crossref_preview(to_ref)
            tsk_refs.append({"reference": to_ref, "votes": votes, "preview": preview or ""})
        return {
            "db_ref": db_ref,
            "display_ref": display_ref,
            "verse": self.clean_text(verse_row[0][0]) if verse_row else "",
            "language": self.detect_source_language(parsed_tokens),
            "source": " ".join(token["surface"] for token in source_tokens),
            "transliteration": " ".join(token["translit"] for token in source_tokens if token["translit"]),
            "interlinear": parsed_tokens[:30],
            "lex_notes": lex_notes,
            "tsk_refs": tsk_refs,
        }

    def export_study_docx(self, db_ref):
        try:
            from docx import Document
        except ImportError:
            console.print("[warning]DOCX export needs python-docx installed.[/]")
            return None
        data = self.build_study_export_data(db_ref)
        if not data:
            return None
        path = self.study_export_filename(db_ref, "docx")
        doc = Document()
        doc.add_heading(f"Lex Study: {data['display_ref']}", level=1)
        if data["verse"]:
            doc.add_paragraph(data["verse"])
        doc.add_heading(data["language"], level=2)
        if data["source"]:
            doc.add_paragraph(data["source"])
        if data["transliteration"]:
            doc.add_paragraph(data["transliteration"])
        doc.add_heading("Interlinear", level=2)
        table = doc.add_table(rows=1, cols=5)
        for cell, title in zip(table.rows[0].cells, ["English", "Source", "Lemma", "Code", "Gloss"]):
            cell.text = title
        for parsed in data["interlinear"]:
            row = table.add_row().cells
            row[0].text = parsed["english"] or "-"
            row[1].text = f"{parsed['surface']} ({parsed['translit']})" if parsed["surface"] else "-"
            row[2].text = f"{parsed['lemma']} ({parsed['lemma_translit']})" if parsed["lemma"] else "-"
            row[3].text = parsed["strongs"] or parsed["morph"] or "-"
            row[4].text = parsed["gloss"] or parsed["english"] or "-"
        doc.add_heading("Lexicon Notes", level=2)
        for note in data["lex_notes"]:
            doc.add_paragraph(f"{note['strongs']} - {note['lemma']}: {note['details']}")
        doc.add_heading("Treasury of Scripture Knowledge", level=2)
        for ref in data["tsk_refs"]:
            doc.add_paragraph(f"{ref['reference']} ({ref['votes']}): {ref['preview']}")
        doc.save(path)
        return path

    def export_study_pdf(self, db_ref):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as PdfTable
        except ImportError:
            console.print("[warning]PDF export needs reportlab installed.[/]")
            return None
        data = self.build_study_export_data(db_ref)
        if not data:
            return None
        path = self.study_export_filename(db_ref, "pdf")
        doc = SimpleDocTemplate(path, pagesize=letter, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
        styles = getSampleStyleSheet()
        self.setup_pdf_styles(styles)
        story = [self.pdf_paragraph(f"Lex Study: {data['display_ref']}", styles["Title"])]
        if data["verse"]:
            story.extend([self.pdf_paragraph(data["verse"], styles["BodyText"]), Spacer(1, 10)])
        story.append(self.pdf_paragraph(data["language"], styles["Heading2"]))
        if data["source"]:
            source_style = styles["Hebrew"] if re.search(r"[\u0590-\u05ff]", data["source"]) and "Hebrew" in styles else styles["BodyText"]
            story.append(self.pdf_paragraph(data["source"], source_style))
        if data["transliteration"]:
            story.append(self.pdf_paragraph(data["transliteration"], styles["Italic"]))
        story.extend([Spacer(1, 10), self.pdf_paragraph("Interlinear", styles["Heading2"])])
        table_rows = [["English", "Source", "Lemma", "Code", "Gloss"]]
        for parsed in data["interlinear"]:
            table_rows.append([
                self.pdf_paragraph(parsed["english"] or "-", styles["BodyText"]),
                self.pdf_paragraph(f"{parsed['surface']} ({parsed['translit']})" if parsed["surface"] else "-", styles["Hebrew"] if parsed["surface"] and re.search(r"[\u0590-\u05ff]", parsed["surface"]) and "Hebrew" in styles else styles["BodyText"]),
                self.pdf_paragraph(f"{parsed['lemma']} ({parsed['lemma_translit']})" if parsed["lemma"] else "-", styles["Hebrew"] if parsed["lemma"] and re.search(r"[\u0590-\u05ff]", parsed["lemma"]) and "Hebrew" in styles else styles["BodyText"]),
                self.pdf_paragraph(parsed["strongs"] or parsed["morph"] or "-", styles["BodyText"]),
                self.pdf_paragraph(parsed["gloss"] or parsed["english"] or "-", styles["BodyText"]),
            ])
        story.append(PdfTable(table_rows, repeatRows=1))
        story.append(self.pdf_paragraph("Lexicon Notes", styles["Heading2"]))
        for note in data["lex_notes"]:
            story.append(self.pdf_paragraph(f"{note['strongs']} - {note['lemma']}: {note['details']}", styles["BodyText"]))
        story.append(self.pdf_paragraph("Treasury of Scripture Knowledge", styles["Heading2"]))
        for ref in data["tsk_refs"]:
            story.append(self.pdf_paragraph(f"{ref['reference']} ({ref['votes']}): {ref['preview']}", styles["BodyText"]))
        doc.build(story)
        return path

    def prompt_study_export(self, db_ref):
        while True:
            self.render_action_bar(
                "Export",
                [
                    ("d", "DOCX study packet"),
                    ("f", "PDF study packet"),
                    ("o", "open studies folder"),
                    ("q", "back"),
                ],
            )
            action = Prompt.ask("Export action", choices=["d", "f", "o", "q"], default="q").lower()
            if action == "q":
                return
            if action == "o":
                self.open_exports_folder(self.study_export_dir())
                continue
            path = self.export_study_docx(db_ref) if action == "d" else self.export_study_pdf(db_ref)
            if path:
                self.open_export(path)
                return

    def prompt_study_actions(self, db_ref):
        current_ref = db_ref
        while True:
            self.render_action_bar(
                "Study Actions",
                [
                    ("n / p", "next or previous verse"),
                    ("r", "read context"),
                    ("w", "verse web"),
                    ("e", "export"),
                    ("q", "done"),
                ],
            )
            action = Prompt.ask("Study action", choices=["n", "p", "r", "w", "e", "q"], default="q").lower()
            if action == "q":
                return
            if action == "e":
                self.prompt_study_export(current_ref)
                continue
            if action == "r":
                self.display_verse(self.format_display_ref(current_ref))
                continue
            if action == "w":
                self.display_verse_web(self.format_display_ref(current_ref))
                continue
            next_ref = self.get_navigation_reference(current_ref, "next" if action == "n" else "prev")
            if next_ref:
                current_ref = next_ref
                self.display_study(current_ref, actions=False)

    def display_study(self, db_ref, animate=None, actions=None):
        index = self.get_interlinear_index()
        row = index.get(db_ref)
        
        # If no exact match (likely due to version prefix mismatch), try to find by book:chap:verse
        if not row or not row.get("p"):
            parts = self.parse_reference_parts(db_ref)
            if parts:
                # Use reverse canon map to get the canonical book name (e.g. "Ps" -> "Psalm")
                canon_book = self.reverse_canon_map.get(parts["book"], parts["book"])
                generic_suffix = f":{canon_book}:{parts['chapter']}:{parts['verse']}"
                
                # The index keys in interlinear JSON look like "esv:Genesis:1:1" or "esv:Psalm:1:1"
                for k, v in index.items():
                    if k.endswith(generic_suffix):
                        row = v
                        break

        if not row or not row.get("p"):
            console.print(Panel("No local interlinear data found for this verse.", border_style="warning"))
            return False
        parsed_tokens = [self.parse_interlinear_token(token) for token in row["p"]]
        self.pause_study_section(animate)
        self.display_source_text(parsed_tokens)
        self.pause_study_section(animate)
        verse_table = Table(title=f"🔤 Study: {db_ref}", box=None)
        verse_table.add_column("Eng", style="text.strong", overflow="fold")
        verse_table.add_column("Src", style="source.text", overflow="fold")
        verse_table.add_column("Lemma", style="lexicon.word", overflow="fold")
        verse_table.add_column("Code", style="interlinear.strongs")
        verse_table.add_column("Gloss", style="text", overflow="fold")
        for parsed in parsed_tokens[:30]:
            code = parsed["strongs"] or parsed["morph"] or "-"
            gloss = parsed["gloss"] or parsed["english"] or "-"
            verse_table.add_row(
                parsed["english"] or "•",
                f"{parsed['surface']} ({parsed['translit']})" if parsed["surface"] else "•",
                f"{parsed['lemma']} ({parsed['lemma_translit']})" if parsed["lemma"] else "•",
                code,
                gloss,
            )
        console.print(verse_table)

        self.pause_study_section(animate)
        lex_table = Table(title="📚 Lexicon Notes", box=None)
        lex_table.add_column("Strongs", style="lexicon.num")
        lex_table.add_column("Lemma", style="lexicon.word", overflow="fold")
        lex_table.add_column("Details", overflow="fold")
        seen = set()
        for parsed in parsed_tokens:
            strongs = parsed["strongs"]
            if not strongs or strongs in seen:
                continue
            seen.add(strongs)
            entry = self.lookup_lexicon_entry(strongs)
            lemma = parsed["lemma"] or (entry["db"][1] if entry["db"] else "")
            pieces = []
            if parsed["morph"]:
                pieces.append(parsed["morph"])
            if entry["step"]:
                pieces.append(re.sub(r"<[^>]+>", "", entry["step"].get("definition", ""))[:140])
            elif entry["interlinear"]:
                pieces.append(entry["interlinear"].get("d", "")[:140])
            elif entry["db"]:
                pieces.append(entry["db"][3][:140])
            if entry["step"] and entry["step"].get("translit"):
                lemma = f"{lemma} ({entry['step']['translit']})"
            elif entry["db"]:
                lemma = f"{lemma} ({entry['db'][2]})"
            lex_table.add_row(strongs, lemma or "-", " | ".join(piece for piece in pieces if piece) or "-")
            if len(seen) >= 12:
                break
        console.print(lex_table)
        self.pause_study_section(animate)
        self.display_study_tsk(db_ref, parsed_tokens)
        use_actions = console.is_terminal if actions is None else actions
        if use_actions:
            self.prompt_study_actions(db_ref)
        return True

    def display_dictionary_howto(self):
        md = "# 📖 Bible Dictionary Help\n\n- `lex define \"Grace\"`"
        console.print(Panel(Markdown(md), border_style="violet"))

    # -----------------------------------------------------------------------
    # Creeds and historical documents
    # -----------------------------------------------------------------------
    def format_creed_source(self, topic, source):
        source_map = {
            "Athanasian Creed": "5th c. | trinitarian creed",
            "Augsburg Confession": "1530 | Lutheran confession",
            "Baltimore Catechism": "1885 | Roman Catholic catechism",
            "Belgic Confession": "1561 | Reformed confession",
            "Canons of Dort": "1619 | Reformed canons",
            "Chalcedonian Definition": "451 | Christological definition",
            "Confession of Dositheus": "1672 | Eastern Orthodox confession",
            "Council of Trent": "1545-1563 | Catholic council decrees",
            "Heidelberg Catechism": "1563 | Reformed catechism",
            "London Baptist Confession of Faith": "1689 | Baptist confession",
            "The Apostles' Creed": "early | baptismal creed",
            "The Longer Catechism of the Orthodox Church": "1830s | Orthodox catechism",
            "The Nicene Creed": "325/381 | ecumenical creed",
            "Thirty-Nine Articles": "1571 | Anglican articles",
            "Westminster Confession of Faith": "1646 | Presbyterian confession",
            "Westminster Larger Catechism": "1648 | Presbyterian catechism",
            "Westminster Shorter Catechism": "1647 | Presbyterian catechism",
        }
        return source_map.get(topic, source or "undated | creed text")

    def creed_sort_key(self, topic):
        order = {
            "The Apostles' Creed": 200,
            "The Nicene Creed": 325,
            "Chalcedonian Definition": 451,
            "Athanasian Creed": 500,
            "Council of Trent": 1545,
            "Augsburg Confession": 1530,
            "Belgic Confession": 1561,
            "Heidelberg Catechism": 1563,
            "Thirty-Nine Articles": 1571,
            "Canons of Dort": 1619,
            "Westminster Confession of Faith": 1646,
            "Westminster Shorter Catechism": 1647,
            "Westminster Larger Catechism": 1648,
            "London Baptist Confession of Faith": 1689,
            "Confession of Dositheus": 1672,
            "Baltimore Catechism": 1885,
            "The Longer Catechism of the Orthodox Church": 1830,
        }
        return order.get(topic, 9999), topic

    def creed_tradition(self, topic):
        groups = {
            "The Apostles' Creed": "Ecumenical Creeds",
            "The Nicene Creed": "Ecumenical Creeds",
            "Chalcedonian Definition": "Ecumenical Creeds",
            "Athanasian Creed": "Ecumenical Creeds",
            "Augsburg Confession": "Lutheran",
            "Belgic Confession": "Reformed",
            "Canons of Dort": "Reformed",
            "Heidelberg Catechism": "Reformed",
            "Westminster Confession of Faith": "Reformed",
            "Westminster Shorter Catechism": "Reformed",
            "Westminster Larger Catechism": "Reformed",
            "London Baptist Confession of Faith": "Baptist",
            "Thirty-Nine Articles": "Anglican",
            "Council of Trent": "Roman Catholic",
            "Baltimore Catechism": "Roman Catholic",
            "Confession of Dositheus": "Eastern Orthodox",
            "The Longer Catechism of the Orthodox Church": "Eastern Orthodox",
        }
        return groups.get(topic, "Other")

    def creed_tradition_sort_key(self, topic):
        tradition_order = {
            "Ecumenical Creeds": 0,
            "Lutheran": 1,
            "Reformed": 2,
            "Anglican": 3,
            "Baptist": 4,
            "Roman Catholic": 5,
            "Eastern Orthodox": 6,
            "Other": 99,
        }
        tradition = self.creed_tradition(topic)
        year, title = self.creed_sort_key(topic)
        return tradition_order.get(tradition, 99), year, title

    def creed_year_label(self, topic, source):
        return self.format_creed_source(topic, source).split("|", 1)[0].strip()

    def extract_creed_title(self, content):
        match = re.match(r'^\[(.*?)\]\s*', content, re.DOTALL)
        return match.group(1).strip() if match else None

    def strip_creed_title(self, content):
        return re.sub(r'^\[.*?\]\s*', '', content, count=1, flags=re.DOTALL).strip()

    def is_empty_creed_content(self, content):
        return not self.strip_creed_title(content or "")

    def load_historical_document(self, topic):
        filename = HISTORICAL_DOC_FILES.get(topic)
        if not filename:
            return None
        return self.load_json_file(os.path.join(HISTORICAL_DOCS_DIR, filename))

    def build_creed_sections_from_file(self, topic):
        data = self.load_historical_document(topic)
        if not data:
            return []
        sections = []
        source = data.get("title", topic)
        for item in data.get("sections", []):
            title = item.get("title") or item.get("chapter") or item.get("question") or topic
            if item.get("q") or item.get("a"):
                body = "\n\n".join(
                    part for part in [
                        f"**Q.** {item.get('q')}" if item.get("q") else "",
                        f"**A.** {item.get('a')}" if item.get("a") else "",
                    ]
                    if part
                )
                if item.get("question"):
                    title = f"Q{item['question']}: {item.get('q', '').strip()}"
            else:
                body = item.get("content", "")
            proofs = self.extract_scripture_refs(body)
            sections.append({"title": str(title), "source": source, "body_parts": [body] if body else [], "proofs": proofs})
        return sections

    def extract_scripture_refs(self, text):
        patterns = [
            r'\b(?:[1-3]\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\d+[:;]\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*',
            r'\b(?:[1-3]\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\d+\b',
        ]
        refs = []
        for pattern in patterns:
            refs.extend(re.findall(pattern, text))
        cleaned = []
        seen = set()
        for ref in refs:
            normalized = ref.replace(";", ":").strip(" .")
            if normalized not in seen:
                seen.add(normalized)
                cleaned.append(normalized)
        filtered = []
        for ref in cleaned:
            if ":" not in ref and any(full.startswith(f"{ref}:") for full in cleaned):
                continue
            filtered.append(ref)
        return filtered

    def is_proof_only_row(self, content):
        body = self.strip_creed_title(content)
        refs = self.extract_scripture_refs(body)
        if not refs:
            return False
        stripped = body
        for ref in refs:
            stripped = stripped.replace(ref.replace(":", ";"), " ")
            stripped = stripped.replace(ref, " ")
        stripped = re.sub(r'[\d\W_]+', ' ', stripped)
        return len(stripped.strip()) <= 18

    def build_creed_sections(self, topic):
        rows = self.creeds_db.query("SELECT rowid, content, source FROM creeds WHERE topic = ? ORDER BY rowid", (topic,))
        if not rows:
            return self.build_creed_sections_from_file(topic)
        sections = []
        current = None
        for _, content, source in rows:
            title = self.extract_creed_title(content) or topic
            body = self.strip_creed_title(content)
            proof_refs = self.extract_scripture_refs(body)
            proof_only = self.is_proof_only_row(content)
            if current is None or current["title"] != title:
                current = {"title": title, "source": source, "body_parts": [], "proofs": []}
                sections.append(current)
            if not proof_only and body:
                current["body_parts"].append(body)
            for ref in proof_refs:
                if ref not in current["proofs"]:
                    current["proofs"].append(ref)
        if not any(section["body_parts"] or section["proofs"] for section in sections):
            file_sections = self.build_creed_sections_from_file(topic)
            if file_sections:
                return file_sections
        return sections

    def should_render_creed_as_document(self, topic, sections):
        short_topics = {
            "The Apostles' Creed",
            "The Nicene Creed",
            "Athanasian Creed",
            "Chalcedonian Definition",
        }
        total_body = sum(len("\n\n".join(section["body_parts"])) for section in sections)
        return topic in short_topics or (len(sections) <= 4 and total_body <= 5000)

    def get_creed_original(self, topic, section_title):
        doc = CREED_ORIGINALS.get(topic)
        if not doc:
            return None, None
        return doc["sections"].get(section_title), doc["language"]

    def display_creed_note(self, topic):
        note = CREED_NOTES.get(topic)
        if note:
            console.print(Panel(Markdown(note), title="Textual / Tradition Note", border_style="yellow"))

    def display_creed_original_document(self, topic, sections):
        doc = CREED_ORIGINALS.get(topic)
        if not doc:
            return False
        console.print(Panel(f"{topic}\nSource: {self.format_creed_source(topic, sections[0]['source'])}\nOriginal: {doc['language']}", border_style="bold green"))
        table = Table(title=f"{topic}: English / {doc['language']}", box=None)
        table.add_column(doc["language"], style="cyan", overflow="fold")
        table.add_column("English", style="text", overflow="fold")
        for section in sections:
            body = "\n\n".join(section["body_parts"]).strip()
            orig_body = doc["sections"].get(section["title"])
            if not body and not orig_body:
                continue
                
            left = f"{orig_body or '[not yet loaded]'}"
            right = f"{body}"
            table.add_row(left, right)
        console.print(table)
        self.display_creed_note(topic)
        return True

    def display_creed_document(self, topic, sections):
        if not sections:
            return False
        if topic in CREED_ORIGINALS:
            return self.display_creed_original_document(topic, sections)
        parts = []
        proof_set = []
        seen = set()
        for section in sections:
            body = "\n\n".join(section["body_parts"]).strip()
            if body:
                parts.append(f"## {section['title']}\n\n{body}")
            for ref in section["proofs"]:
                if ref not in seen:
                    seen.add(ref)
                    proof_set.append(ref)
        proofs = ""
        if proof_set:
            proofs = "\n\n---\n\n**Scripture Proofs**\n\n" + "\n".join(f"- {ref}" for ref in proof_set[:40])
        console.print(
            Panel(
                Markdown(
                    f"# {topic}\n\n"
                    f"**Source:** {self.format_creed_source(topic, sections[0]['source'])}\n\n---\n\n"
                    + "\n\n".join(parts)
                    + proofs
                ),
                border_style="bold green"
            )
        )
        self.display_creed_note(topic)
        return True

    def display_creed_sections(self, topic):
        sections = self.build_creed_sections(topic)
        if not sections:
            return False
        if self.should_render_creed_as_document(topic, sections):
            return self.display_creed_document(topic, sections)
        while True:
            table = Table(title=f"📜 {topic}", box=None)
            table.add_column("ID", style="verse.ref")
            table.add_column("Section", style="bold green")
            table.add_column("Proofs", style="dim cyan")
            for i, section in enumerate(sections, 1):
                proof_count = str(len(section["proofs"])) if section["proofs"] else "-"
                table.add_row(str(i), section["title"], proof_count)
            console.print(table)
            if not sys.stdin.isatty():
                console.print(f"[dim]Use an interactive terminal to browse sections for: lex creed {topic}[/]")
                return True
            try:
                choice = Prompt.ask("Select section, or q to quit", default="1").strip().lower()
            except EOFError:
                console.print(f"[dim]Use an interactive terminal to browse sections for: lex creed {topic}[/]")
                return True
            if choice == "q":
                return True
            if not choice.isdigit():
                console.print("[warning]Enter a section number or q.[/]")
                continue
            section_idx = int(choice) - 1
            if 0 <= section_idx < len(sections):
                self.display_creed_reader(topic, sections, start_idx=section_idx)
            else:
                console.print("[warning]Section number out of range.[/]")
        return True

    def display_creed_navigator(self, query=None):
        if query:
            matches = self.find_creed_topics(query)
            if len(matches) == 1:
                return self.display_creed_sections(matches[0][0])
            if len(matches) > 1:
                table = Table(title=f"📜 Matching Creeds: {query}", box=None)
                table.add_column("Document", style="bold green")
                table.add_column("Sections", style="dim cyan")
                table.add_column("Source", style="dim")
                for topic, source in matches:
                    table.add_row(topic, str(len(self.build_creed_sections(topic))), self.format_creed_source(topic, source))
                console.print(table)
                console.print("[dim]Use: lex creed <document name>[/]")
                return True
            res = self.creeds_db.query(
                """
                SELECT topic, content, source
                FROM creeds
                WHERE content LIKE ? AND content NOT LIKE '[]%'
                LIMIT 8
                """,
                (f'%{query}%',)
            )
            for t, c, s in res:
                title = self.extract_creed_title(c) or t
                refs = self.extract_scripture_refs(c)
                snippet = self.strip_creed_title(c)[:700]
                if refs:
                    snippet += "\n\n**Scripture Proofs:** " + "; ".join(refs[:8])
                display_source = self.format_creed_source(t, s)
                console.print(Panel(Markdown(f"# {t}: {title}\n\n**Source:** {display_source}\n\n{snippet}"), border_style="green"))
            return bool(res)
        
        creeds_list = self.creeds_db.query(
            """
            SELECT topic, source
            FROM creeds
            GROUP BY topic, source
            """
        )
        creeds_list = sorted(creeds_list, key=lambda row: self.creed_tradition_sort_key(row[0]))
        table = Table(title="📜 Creeds Navigator", box=None)
        table.add_column("ID", style="verse.ref")
        table.add_column("Tradition", style="bold cyan")
        table.add_column("Year", style="dim")
        table.add_column("Document", style="bold green")
        table.add_column("Sections", style="dim cyan")
        section_counts = {topic: len(self.build_creed_sections(topic)) for topic, _ in creeds_list}
        last_tradition = None
        for i, (t, s) in enumerate(creeds_list):
            tradition = self.creed_tradition(t)
            tradition_label = tradition if tradition != last_tradition else ""
            table.add_row(
                str(i+1),
                tradition_label,
                self.creed_year_label(t, s),
                t,
                str(section_counts.get(t, 0)),
            )
            last_tradition = tradition
        console.print(table)
        if not sys.stdin.isatty():
            console.print("[dim]Use: lex creed <document name>[/]")
            return True
        try:
            choice = Prompt.ask("Select ID, or q to quit", default="1").strip().lower()
        except EOFError:
            console.print("[dim]Use: lex creed <document name>[/]")
            return True
        if choice == "q":
            return True
        if not choice.isdigit():
            console.print("[warning]Enter a document ID or q.[/]")
            return True
        doc_idx = int(choice) - 1
        if 0 <= doc_idx < len(creeds_list):
            self.display_creed_sections(creeds_list[doc_idx][0])
        else:
            console.print("[warning]Document ID out of range.[/]")
        return True

    def find_creed_topics(self, query):
        normalized_query = self.normalize_term(query)
        if not normalized_query:
            return []
        rows = self.creeds_db.query(
            """
            SELECT topic, source
            FROM creeds
            GROUP BY topic, source
            """
        )
        exact = []
        partial = []
        for topic, source in rows:
            normalized_topic = self.normalize_term(topic)
            if normalized_topic == normalized_query:
                exact.append((topic, source))
            elif normalized_query in normalized_topic:
                partial.append((topic, source))
        return sorted(exact or partial, key=lambda row: self.creed_sort_key(row[0]))

    def display_creed_reader(self, topic, sections, start_idx=0):
        if not sections:
            return
        art_idx = start_idx
        while True:
            section = sections[art_idx]
            body = "\n\n".join(section["body_parts"]).strip() or "_No article body stored for this section._"
            proofs = ""
            if section["proofs"]:
                proofs = "\n\n---\n\n**Scripture Proofs**\n\n" + "\n".join(f"- {ref}" for ref in section["proofs"][:24])
            console.clear()
            original, original_language = self.get_creed_original(topic, section["title"])
            if original:
                table = Table(title=f"{topic}: {section['title']}", box=None)
                table.add_column(original_language, style="cyan", overflow="fold")
                table.add_column("English", style="text", overflow="fold")
                table.add_row(original, body)
                console.print(table)
                if proofs:
                    console.print(Panel(Markdown(proofs), border_style="green"))
            else:
                console.print(
                    Panel(
                        Markdown(
                            f"# {topic}: {section['title']}\n\n"
                            f"**Source:** {self.format_creed_source(topic, section['source'])}\n\n---\n\n{body}{proofs}"
                        ),
                        border_style="bold green"
                    )
                )
            console.print(f"[dim]Section {art_idx+1}/{len(sections)} of '{topic}'[/]")
            console.print("[dim][n] Next | [p] Prev | [m] Sections | [q] Quit[/]")
            
            nav = Prompt.ask("Navigate", choices=["n", "p", "m", "q"], default="q").lower()
            if nav == "n" and art_idx < len(sections)-1: art_idx += 1
            elif nav == "p" and art_idx > 0: art_idx -= 1
            elif nav == "m": break
            elif nav == "q": sys.exit(0)

    # -----------------------------------------------------------------------
    # Scripture search, Strong's lookup, dictionary, and encyclopedia
    # -----------------------------------------------------------------------
    def search_scope_clause(self, scope):
        if not scope:
            return "", ()
        clauses = " OR ".join(["reference GLOB ?"] * len(scope["books"]))
        params = tuple(f"*:{book}:*" for book in scope["books"])
        return f" AND ({clauses})", params

    def query_search_results(self, fts_query, limit, offset, scope=None):
        scope_clause, scope_params = self.search_scope_clause(scope)
        return self.bible_db.query(
            f"""
            SELECT reference, text
            FROM bible_fts
            WHERE bible_fts MATCH ?
            {scope_clause}
            ORDER BY rank
            LIMIT ? OFFSET ?
            """,
            (fts_query, *scope_params, limit, offset)
        )

    def count_search_results(self, fts_query, scope=None):
        scope_clause, scope_params = self.search_scope_clause(scope)
        rows = self.bible_db.query(
            f"SELECT COUNT(*) FROM bible_fts WHERE bible_fts MATCH ?{scope_clause}",
            (fts_query, *scope_params)
        )
        return rows[0][0] if rows else 0

    def resolve_search(self, query, page=1, limit=10):
        search_query, scope = self.parse_search_query_and_scope(query)
        safe_query = self.escape_fts_query(search_query)
        if not safe_query:
            return None
        mode = "phrase"
        active_query = safe_query
        page = max(1, page)
        limit = min(max(1, limit), 50)
        total = self.count_search_results(active_query, scope=scope)
        if total:
            page = min(page, ((total - 1) // limit) + 1)
        offset = (page - 1) * limit
        res = self.query_search_results(active_query, limit, offset, scope=scope) if total else []
        if not total:
            terms_query = self.fts_terms_query(search_query)
            if terms_query and terms_query != safe_query:
                active_query = terms_query
                mode = "all terms"
                total = self.count_search_results(active_query, scope=scope)
                if total:
                    page = min(page, ((total - 1) // limit) + 1)
                offset = (page - 1) * limit
                res = self.query_search_results(active_query, limit, offset, scope=scope) if total else []
        if not res:
            return None
        return {
            "query": search_query,
            "active_query": active_query,
            "mode": mode,
            "scope": scope,
            "page": page,
            "limit": limit,
            "total": total,
            "offset": offset,
            "results": res,
            "page_count": ((total - 1) // limit) + 1 if total else 1,
        }

    def render_search_page(self, state, interactive=False):
        body = Text()
        query = state["query"]
        page = state["page"]
        limit = state["limit"]
        offset = state["offset"]
        total = state["total"]
        res = state["results"]
        scope = state.get("scope")
        for idx, (ref, text) in enumerate(res, 1):
            parts = self.parse_reference_parts(ref)
            display_ref = self.format_display_ref(ref) if parts else ref
            body.append(f"{offset + idx:>3}. {display_ref}\n", style="verse.ref")
            body.append_text(self.highlight_search_terms(self.clean_text(text), query))
            body.append("\n\n", style="dim")
        shown_end = offset + len(res)
        scope_label = f"  |  Scope: {scope['label']}" if scope else ""
        footer = f"Mode: {state['mode']}{scope_label}  |  Showing {offset + 1}-{shown_end} of {total}"
        query_arg = shlex.quote(query)
        if scope:
            query_arg = f"{query_arg} -{scope['label'].lower().replace(' ', '-').replace('--', '-')}"
        if interactive:
            footer += "  |  Choose an action below"
        elif shown_end < total:
            footer += f"\nNext page: lex search {query_arg} --page {page + 1}"
            if limit != 10:
                footer += f" --limit {limit}"
        if not interactive and page > 1:
            footer += f"\nPrevious page: lex search {query_arg} --page {page - 1}"
            if limit != 10:
                footer += f" --limit {limit}"
        body.append(footer, style="ui.meta")
        console.print(
            Panel(
                body,
                title=f"🔍 Search: {query}",
                subtitle=f"page {page}/{state['page_count']}",
                border_style="ui.border",
                padding=(1, 2),
            )
        )
        if interactive:
            self.render_action_bar(
                "Actions",
                [
                    ("1-10", "study result"),
                    ("r #", "read result"),
                    ("n / p", "page"),
                    ("e", "export"),
                    ("q", "quit"),
                ],
            )

    def search_export_dir(self):
        path = os.path.expanduser("~/Documents/lex_exports")
        os.makedirs(path, exist_ok=True)
        return path

    def render_action_bar(self, title, actions):
        grid = Table.grid(padding=(0, 2))
        grid.add_column(no_wrap=True)
        grid.add_column(style="ui.meta")
        for key, label in actions:
            grid.add_row(f"[ui.action.key]{key}[/]", label)
        console.print(Panel(grid, title=title, border_style="ui.action", padding=(0, 1), expand=True))

    def open_export(self, path):
        if not path:
            return
        opener = None
        for candidate in ("xdg-open", "gio", "kde-open"):
            candidate_path = shutil.which(candidate)
            if candidate_path:
                opener = [candidate_path]
                if candidate == "gio":
                    opener.append("open")
                break
        if not opener:
            console.print(f"[dim]Saved file:[/] {path}")
            return
        try:
            subprocess.Popen([*opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            console.print(f"[success]Saved and opened:[/] {path}")
        except Exception:
            console.print(f"[success]Saved:[/] {path}")

    def open_exports_folder(self, path=None):
        folder = path or self.search_export_dir()
        self.open_export(folder)

    def pdf_safe_text(self, value):
        text = "" if value is None else str(value)
        replacements = {
            "•": "-",
            "→": "->",
            "←": "<-",
            "\u00a0": " ",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return html.escape(text)

    def setup_pdf_styles(self, styles):
        paragraph_style_cls = None
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.styles import ParagraphStyle
            paragraph_style_cls = ParagraphStyle
            font_paths = {
                "LexSans": "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "LexSansHebrew": "/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf",
            }
            for font_name, font_path in font_paths.items():
                if os.path.exists(font_path) and font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
            base_font = "LexSans" if "LexSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
            hebrew_font = "LexSansHebrew" if "LexSansHebrew" in pdfmetrics.getRegisteredFontNames() else base_font
        except Exception:
            base_font = "Helvetica"
            hebrew_font = base_font
        for style_name in ["Title", "Heading1", "Heading2", "Heading3", "Normal", "BodyText", "Italic"]:
            if style_name in styles:
                styles[style_name].fontName = base_font
        if "Hebrew" not in styles and paragraph_style_cls:
            styles.add(paragraph_style_cls(name="Hebrew", parent=styles["BodyText"]))
        if "Hebrew" in styles:
            styles["Hebrew"].fontName = hebrew_font
        return base_font, hebrew_font

    def pdf_paragraph(self, text, style):
        from reportlab.platypus import Paragraph
        return Paragraph(self.pdf_safe_text(text), style)

    def search_export_filename(self, state, ext):
        scope = state.get("scope")
        scope_part = f"_{scope['label']}" if scope else ""
        raw = f"lex_search_{state['query']}{scope_part}_p{state['page']}.{ext}"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_")
        return os.path.join(self.search_export_dir(), safe)

    def search_export_rows(self, state):
        rows = []
        for idx, (ref, text) in enumerate(state["results"], 1):
            parts = self.parse_reference_parts(ref)
            display_ref = self.format_display_ref(ref) if parts else ref
            rows.append({
                "number": state["offset"] + idx,
                "reference": display_ref,
                "text": self.clean_text(text),
            })
        return rows

    def export_search_docx(self, state):
        try:
            from docx import Document
        except ImportError:
            console.print("[warning]DOCX export needs python-docx installed.[/]")
            return None
        path = self.search_export_filename(state, "docx")
        doc = Document()
        doc.add_heading(f"Lex Search: {state['query']}", level=1)
        scope = state.get("scope")
        meta = f"Mode: {state['mode']} | Page: {state['page']}/{state['page_count']} | Showing {state['offset'] + 1}-{state['offset'] + len(state['results'])} of {state['total']}"
        if scope:
            meta += f" | Scope: {scope['label']}"
        doc.add_paragraph(meta)
        for row in self.search_export_rows(state):
            doc.add_heading(f"{row['number']}. {row['reference']}", level=2)
            doc.add_paragraph(row["text"])
        doc.save(path)
        return path

    def export_search_pdf(self, state):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        except ImportError:
            console.print("[warning]PDF export needs reportlab installed.[/]")
            return None
        path = self.search_export_filename(state, "pdf")
        doc = SimpleDocTemplate(path, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
        styles = getSampleStyleSheet()
        self.setup_pdf_styles(styles)
        story = [self.pdf_paragraph(f"Lex Search: {state['query']}", styles["Title"])]
        scope = state.get("scope")
        meta = f"Mode: {state['mode']} | Page: {state['page']}/{state['page_count']} | Showing {state['offset'] + 1}-{state['offset'] + len(state['results'])} of {state['total']}"
        if scope:
            meta += f" | Scope: {scope['label']}"
        story.extend([self.pdf_paragraph(meta, styles["Normal"]), Spacer(1, 12)])
        for row in self.search_export_rows(state):
            story.append(self.pdf_paragraph(f"{row['number']}. {row['reference']}", styles["Heading2"]))
            story.append(self.pdf_paragraph(row["text"], styles["BodyText"]))
            story.append(Spacer(1, 10))
        doc.build(story)
        return path

    def prompt_search_export(self, state):
        while True:
            self.render_action_bar(
                "Export",
                [
                    ("d", "DOCX current page"),
                    ("f", "PDF current page"),
                    ("o", "open exports folder"),
                    ("q", "back"),
                ],
            )
            action = Prompt.ask("Export action", choices=["d", "f", "o", "q"], default="q").lower()
            if action == "q":
                return
            if action == "o":
                self.open_exports_folder()
                continue
            path = self.export_search_docx(state) if action == "d" else self.export_search_pdf(state)
            if path:
                self.open_export(path)
                return

    def search_result_ref(self, state, user_number):
        if not user_number.isdigit():
            return None
        idx = int(user_number) - state["offset"] - 1
        if idx < 0 or idx >= len(state["results"]):
            return None
        return state["results"][idx][0]

    def display_search(self, query, page=1, limit=10, interactive=None):
        state = self.resolve_search(query, page=page, limit=limit)
        if not state:
            return False
        use_interactive = console.is_terminal if interactive is None else interactive
        use_interactive = use_interactive and page == 1 and state["page_count"] > 1
        if not use_interactive:
            self.render_search_page(state)
            return True
        while True:
            console.clear()
            self.render_search_page(state, interactive=True)
            nav = Prompt.ask("Search action", default="q").strip().lower()
            if nav == "q":
                return True
            if nav == "e":
                self.prompt_search_export(state)
                Prompt.ask("Press Enter to continue", default="")
                continue
            if nav.isdigit():
                ref = self.search_result_ref(state, nav)
                if ref:
                    self.display_study(ref, actions=True)
                continue
            read_match = re.match(r"^r\s+(\d+)$", nav)
            if read_match:
                ref = self.search_result_ref(state, read_match.group(1))
                if ref:
                    self.display_verse(self.format_display_ref(ref))
                    Prompt.ask("Press Enter to return to search", default="")
                continue
            if nav not in {"n", "p"}:
                continue
            next_page = state["page"] + 1 if nav == "n" else state["page"] - 1
            if next_page < 1 or next_page > state["page_count"]:
                continue
            next_state = self.resolve_search(query, page=next_page, limit=limit)
            if next_state:
                state = next_state
        return True

    def display_strongs(self, query):
        if re.match(r'^[GH]\d+$', query.upper()):
            res = self.strongs_db.query("SELECT number, word, pronunciation, definition FROM strongs WHERE number = ?", (query.upper(),))
        else:
            normalized = self.normalize_term(query)
            res = self.strongs_db.query(
                """
                SELECT number, word, pronunciation, definition
                FROM strongs
                WHERE lower(replace(replace(replace(pronunciation, '''', ''), '-', ''), ' ', '')) = ?
                LIMIT 5
                """,
                (normalized,)
            )
            if not res:
                safe_query = self.escape_fts_query(query)
                if not safe_query:
                    return False
                res = self.strongs_db.query(
                    """
                    SELECT s.number, s.word, s.pronunciation, s.definition
                    FROM strongs_fts f
                    JOIN strongs s ON s.number = f.number
                    WHERE strongs_fts MATCH ?
                    LIMIT 5
                    """,
                    (safe_query,)
                )
        for n, w, p, d in res:
            lang = "Greek" if n.startswith('G') else "Hebrew"
            console.print(Panel(f"[lexicon.word]{w}[/] ({p})\n\n{d}", title=f"📚 {lang} Lexicon: {n}", border_style="blue"))
        return bool(res)

    def display_english_strongs(self, query):
        normalized = self.normalize_term(query)
        if not normalized:
            return False
        exact_results = []
        fuzzy_results = []
        seen = set()
        for strongs_id, entry in self.get_interlinear_strongs().items():
            glosses = self.extract_english_glosses(entry)
            exact_matches = [gloss for gloss in glosses if self.normalize_term(gloss) == normalized]
            fuzzy_matches = [gloss for gloss in glosses if normalized in self.normalize_term(gloss)]
            if not exact_matches and not fuzzy_matches:
                continue
            _, db_key, _ = self.normalize_strongs_key(strongs_id)
            db_rows = self.strongs_db.query(
                "SELECT number, word, pronunciation, definition FROM strongs WHERE number = ?",
                (db_key,)
            ) if db_key else []
            if not db_rows or db_key in seen:
                continue
            seen.add(db_key)
            number, word, pronunciation, definition = db_rows[0]
            item = (number, word, pronunciation, definition, ", ".join((exact_matches or fuzzy_matches)[:3]))
            if exact_matches:
                exact_results.append(item)
            else:
                fuzzy_results.append(item)
        results = exact_results[:8] if exact_results else fuzzy_results[:8]
        safe_query = self.escape_fts_query(query)
        if safe_query:
            db_rows = self.strongs_db.query(
                """
                SELECT strongs.number, strongs.word, strongs.pronunciation, strongs.definition
                FROM strongs_fts
                JOIN strongs USING(number)
                WHERE strongs_fts MATCH ?
                LIMIT 12
                """,
                (safe_query,)
            )
            for n, w, p, d in db_rows:
                if n in seen:
                    continue
                results.append((n, w, p, d, query))
                seen.add(n)
                if len(results) >= 12:
                    break
        if not results:
            return False
        table = Table(title=f"🔤 Strong's Lookup: '{query}'", box=None)
        table.add_column("No.", style="lexicon.num")
        table.add_column("Lemma", style="lexicon.word")
        table.add_column("Pronunciation")
        table.add_column("English", style="text")
        table.add_column("Definition", overflow="fold")
        for number, word, pronunciation, definition, gloss in results:
            table.add_row(number, word, pronunciation, gloss, definition[:120])
        console.print(table)
        return True

    def display_dictionary(self, query):
        normalized = query.strip()
        if not normalized:
            return False
        res = self.dictionary_db.query(
            """
            SELECT topic, content, source
            FROM dictionary
            WHERE lower(topic) = lower(?)
            LIMIT 3
            """,
            (normalized,)
        )
        if not res:
            res = self.dictionary_db.query(
                """
                SELECT topic, content, source
                FROM dictionary
                WHERE lower(topic) LIKE lower(?)
                ORDER BY CASE WHEN lower(topic) LIKE lower(?) THEN 0 ELSE 1 END, topic
                LIMIT 3
                """,
                (f"{normalized}%", f"%{normalized}%")
            )
        if not res:
            safe_query = self.escape_fts_query(query)
            if not safe_query:
                return False
            res = self.dictionary_db.query(
                "SELECT topic, content, source FROM dictionary_fts WHERE dictionary_fts MATCH ? LIMIT 3",
                (safe_query,)
            )
        for t, c, s in res:
            console.print(Panel(Markdown(c[:1000]), title=f"📖 {t} ({s})", border_style="violet"))
        return bool(res)

    def display_encyclopedia(self, query):
        if not self.encyclopedia_db:
            return False
        normalized = query.strip()
        if not normalized:
            return False
        tables = {row[0] for row in self.encyclopedia_db.query("SELECT name FROM sqlite_master WHERE type='table'")}
        if "encyclopedia" not in tables:
            return False
        res = self.encyclopedia_db.query(
            """
            SELECT topic, content, source
            FROM encyclopedia
            WHERE lower(topic) = lower(?)
            LIMIT 3
            """,
            (normalized,)
        )
        if not res:
            res = self.encyclopedia_db.query(
                """
                SELECT topic, content, source
                FROM encyclopedia
                WHERE lower(topic) LIKE lower(?)
                ORDER BY CASE WHEN lower(topic) LIKE lower(?) THEN 0 ELSE 1 END, topic
                LIMIT 3
                """,
                (f"{normalized}%", f"%{normalized}%")
            )
        if not res and "encyclopedia_fts" in tables:
            safe_query = self.escape_fts_query(query)
            if not safe_query:
                return False
            res = self.encyclopedia_db.query(
                """
                SELECT topic, content, source
                FROM encyclopedia_fts
                WHERE encyclopedia_fts MATCH ?
                LIMIT 3
                """,
                (safe_query,)
            )
        for t, c, s in res:
            console.print(Panel(Markdown(c[:1400]), title=f"📚 {t} ({s})", border_style="cyan"))
        return bool(res)

    def format_naves_entry(self, entry_text):
        # Precise Regex for Verse References: handles "1 Cor 1:1", "Jhn 3:16", etc.
        pattern = r'(\b(?:[1-3]\s?)?[A-Z][a-z]{0,3}\s\d+:\d+[0-9:,\-]*|\b(?:[1-3]\s?)?[A-Z]{2,4}\s\d+:\d+[0-9:,\-]*)'
        
        formatted_content = Text()
        lines = entry_text.splitlines()
        
        for line in lines:
            if not line.strip():
                formatted_content.append("\n")
                continue
                
            stripped = line.lstrip()
            indent_size = len(line) - len(stripped)
            
            # Determine style based on indentation depth
            if indent_size == 0:
                style = "category" if ACTIVE_THEME_MODE == "dark" else "text"
            elif indent_size <= 5:
                style = "ui.cyan"
            else:
                style = "ui.meta"
                
            formatted_content.append(" " * indent_size)
            
            # Handle Bullets
            current_content = stripped
            if stripped.startswith('-'):
                formatted_content.append("-", style="ui.meta")
                current_content = stripped[1:]
                
            # Highlight Verses without duplication
            last_pos = 0
            for match in re.finditer(pattern, current_content):
                formatted_content.append(current_content[last_pos:match.start()], style=style)
                formatted_content.append(match.group(0), style="verse.ref")
                last_pos = match.end()
                
            formatted_content.append(current_content[last_pos:], style=style)
            formatted_content.append("\n")
            
        return formatted_content

    def display_naves(self, query):
        if not self.naves_db:
            return False
        normalized = query.strip()
        if not normalized:
            return False
            
        # 1. Try Exact Match first (Fastest)
        res = self.naves_db.query(
            "SELECT subject, entry FROM topics WHERE subject_upper = ?",
            (normalized.upper(),)
        )
        
        # 2. If no exact match, try Substring Match or FTS
        if not res:
            res = self.naves_db.query(
                "SELECT subject, entry FROM topics WHERE subject_upper LIKE ? ORDER BY subject LIMIT 50",
                (f"%{normalized.upper()}%",)
            )
            
        if not res:
            try:
                res = self.naves_db.query(
                    "SELECT subject, entry FROM topics_fts WHERE entry MATCH ? LIMIT 20",
                    (normalized,)
                )
            except: pass

        if not res:
            return False

        if len(res) == 1:
            subject, entry = res[0]
            console.print(Rule(style="ui.border"))
            console.print(f" [dict.topic]{subject}[/dict.topic]")
            console.print(Rule(style="ui.border"))
            console.print("")
            console.print(self.format_naves_entry(entry))
            console.print("")
            console.print(Rule(style="ui.meta"))
            return True
        else:
            # Multiple results - show picker
            table = Table(title=f"Nave's Results for '{query}'", border_style="ui.border", box=None)
            table.add_column("ID", justify="right", style="ui.action.key")
            table.add_column("Subject", style="dict.topic")
            for i, row in enumerate(res, 1):
                table.add_row(str(i), row[0])
            console.print(table)
            
            try:
                choice = console.input(f"\n [ui.action]Select ID [1-{len(res)}]: [/]").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(res):
                    self.display_naves(res[idx][0]) # Recursive call to show the single entry
                    return True
            except:
                pass
            return True

    def display_commentary(self, query):
        ref_norm, book, chap, verse = self.normalize_ref(query)
        if not ref_norm:
            return False
            
        ref_label = f"{book} {chap}"
        if verse:
            ref_label += f":{verse}"
            
        console.print(Rule(style="ui.border"))
        console.print(f" [dict.topic]Commentary: {ref_label}[/dict.topic]")
        console.print(Rule(style="ui.border"))
        console.print("")
        
        # Ensure we use the DB-specific book name
        db_book = self.canon_map.get(re.sub(r"[^a-z0-9]+", "", book.lower()), book)
        
        # Helper to query a commentary DB
        def get_comm(db, b, c, v):
            if not db: return []
            if v:
                # Find sections that cover this verse
                return db.query(
                    "SELECT section_title, markdown, source FROM commentary WHERE book = ? AND chapter = ? AND verse_start <= ? AND verse_end >= ? ORDER BY section_order",
                    (b, c, v, v)
                )
            else:
                # Get entire chapter
                return db.query(
                    "SELECT section_title, markdown, source FROM commentary WHERE book = ? AND chapter = ? ORDER BY section_order",
                    (b, c)
                )

        henry_notes = get_comm(self.henry_db, db_book, chap, verse)
        calvin_notes = get_comm(self.calvin_db, db_book, chap, verse)
        
        if not henry_notes and not calvin_notes:
            console.print(f"[warning]No commentary notes found for {ref_label}.[/]")
            return False

        # Display in side-by-side or sequential blocks
        for title, md, src in henry_notes:
            console.print(Panel(Markdown(md), title=f"📜 {src}: {title}", border_style="blue"))
            
        for title, md, src in calvin_notes:
            console.print(Panel(Markdown(md), title=f"📜 {src}: {title}", border_style="magenta"))
            
        return True

# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------
# Keep parsing and routing here thin. Feature behavior should live on LexAgent
# so commands can eventually be tested without shelling out.
def main():
    raw_argv = sys.argv[1:]
    if "search" in raw_argv or "serch" in raw_argv:
        command_idx = raw_argv.index("search") if "search" in raw_argv else raw_argv.index("serch")
        protected_argv = []
        for idx, token in enumerate(raw_argv):
            if (
                idx > command_idx
                and token.startswith("-")
                and not token.startswith("--")
                and token not in {"-i", "-d", "-c", "-s", "-v", "-light", "-dark", "-auto", "-B", "--bible"}
            ):
                protected_argv.append(f"__lexscope__{token[1:]}")
            else:
                protected_argv.append(token)
        raw_argv = protected_argv
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="*")
    parser.add_argument("-i", "--interlinear", action="store_true")
    parser.add_argument("-d", "--define", action="store_true")
    parser.add_argument("-c", "--creed", action="store_true")
    parser.add_argument("-s", "--strongs", action="store_true")
    parser.add_argument("-v", "--version", nargs="?", const="__LIST__", help="List versions or switch to <id>")
    parser.add_argument("-B", "--bible", type=str, default=None, choices=BIBLE_VERSIONS.keys(), help="Select Bible version for current command")
    parser.add_argument("--update", action="store_true", help="Check for and install updates")
    theme_group = parser.add_mutually_exclusive_group()
    theme_group.add_argument("-light", dest="theme_mode", action="store_const", const="light")
    theme_group.add_argument("-dark", dest="theme_mode", action="store_const", const="dark")
    theme_group.add_argument("-auto", dest="theme_mode", action="store_const", const="auto")
    parser.add_argument("--credits", action="store_true")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--prev", action="store_true")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--animate", dest="animate", action="store_true", default=None)
    parser.add_argument("--no-animate", dest="animate", action="store_false")
    args, unknown = parser.parse_known_args(raw_argv)
    if args.theme_mode == "auto":
        clear_theme_preference()
    elif args.theme_mode:
        save_theme_preference(args.theme_mode)
    args.query = [f"-{q[len('__lexscope__'):]}" if q.startswith("__lexscope__") else q for q in args.query]
    
    # Initialize Update Manager and ensure data exists
    manager = LexUpdateManager(console, data_dir=DATA_DIR)
    
    # If the user is running an update, we handle it and exit
    if args.update or (len(args.query) > 0 and args.query[0] == "update"):
        manager.perform_update()
        sys.exit(0)
        
    # Ensure critical data exists (downloads if missing)
    manager.ensure_data()

    if unknown:
        if args.query and args.query[0] in {"search", "serch", "read"} and all(u.startswith("-") and not u.startswith("--") for u in unknown):
            args.query.extend(unknown)
        else:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    agent = LexAgent(bible_id=args.bible)
    query = " ".join(args.query)

    # Alias "bible" or "version" to persistent switch
    if query.startswith("bible ") or query.startswith("version "):
        target = query.split(" ", 1)[1].strip()
        if target in BIBLE_VERSIONS:
            save_bible_preference(target)
            console.print(f"[success]Default Bible version set to [bold cyan]{target}[/] ({BIBLE_VERSIONS[target]['name']})[/]")
            sys.exit(0)
        else:
            console.print(f"[error]Unknown Bible version: {target}[/]")
            sys.exit(1)

    # Handle -v / --version
    if args.version:
        # Case 1: lex -v <id> -> switch permanently
        if args.version != "__LIST__" and args.version in BIBLE_VERSIONS:
            save_bible_preference(args.version)
            console.print(f"[success]Default Bible version set to [bold cyan]{args.version}[/] ({BIBLE_VERSIONS[args.version]['name']})[/]")
            sys.exit(0)
        
        # Case 2: lex -v -> display numbered menu
        console.print(Panel(Text(f"Lex version {VERSION}", style="bold gold3"), subtitle="Select Default Bible Version", border_style="cyan"))
        
        vids = list(BIBLE_VERSIONS.keys())
        menu_table = Table.grid(padding=(0, 2))
        menu_table.add_column(style="bold yellow")
        menu_table.add_column(style="bold cyan")
        menu_table.add_column()
        
        current_pref = load_bible_preference()
        
        for i, vid in enumerate(vids, 1):
            info = BIBLE_VERSIONS[vid]
            is_current = " [bold green](current)[/]" if vid == current_pref else ""
            menu_table.add_row(f"{i}.", vid, f"{info['name']}{is_current}")
            
        console.print(menu_table)
        console.print("\n[dim]Select a number to switch default, or 'q' to exit.[/]")
        
        choice = Prompt.ask("Selection", choices=[str(i) for i in range(1, len(vids)+1)] + ["q"], default="q", show_choices=False)
        
        if choice != "q":
            selected_vid = vids[int(choice) - 1]
            save_bible_preference(selected_vid)
            console.print(f"[success]Default Bible version set to [bold cyan]{selected_vid}[/] ({BIBLE_VERSIONS[selected_vid]['name']})[/]")
            
        sys.exit(0)

    # Handle persistent bible selection: "lex -B kjv" with no query
    if args.bible and not query:
        save_bible_preference(args.bible)
        console.print(f"[success]Default Bible version set to [bold cyan]{args.bible}[/] ({BIBLE_VERSIONS[args.bible]['name']})[/]")
        sys.exit(0)

    if args.credits:
        agent.display_credits()
        sys.exit(0)

    if args.next or args.prev:
        last = agent.last_ref
        if not last: sys.exit(1)
        query = agent.resolve_navigation_query("next" if args.next else "prev")
        if not query:
            sys.exit(1)
    
    if not query and not (args.next or args.prev):
        agent.display_intro()
        sys.exit(0)

    if query == "read":
        agent.display_read_landing()
        sys.exit(0)
    elif query.startswith("read "):
        query = query[5:].strip()
    elif query == "study":
        agent.display_study_landing()
        sys.exit(0)
    elif query.startswith("study "):
        query = query[6:].strip()
        if not query:
            agent.display_study_landing()
            sys.exit(0)
        args.interlinear = True
    elif query in {"search", "serch"}:
        agent.display_search_howto()
        sys.exit(0)
    elif query.startswith("search ") or query.startswith("serch "):
        query = query.split(" ", 1)[1].strip()
        if not query:
            sys.exit(1)
        if not agent.display_search(query, page=args.page, limit=args.limit):
            console.print("[warning]No scripture search results found.[/]")
            sys.exit(1)
        sys.exit(0)
    elif query == "web":
        console.print("[warning]Usage: lex web John 3:16[/]")
        sys.exit(1)
    elif query.startswith("web "):
        q = query[4:].strip()
        if not agent.display_verse_web(q, limit=args.limit):
            console.print("[warning]No verse web found.[/]")
            sys.exit(1)
        sys.exit(0)
    elif query == "strongs":
        agent.display_strongs_howto()
        sys.exit(0)
    elif query.startswith("strongs "):
        q = query[8:].strip()
        if not q:
            agent.display_strongs_howto()
            sys.exit(1)
        if not agent.display_english_strongs(q):
            if not agent.display_strongs(q):
                console.print("[warning]No Strong's entries found for that term.[/]")
                sys.exit(1)
        sys.exit(0)
    elif query == "topic" or query == "naves":
        agent.display_topic_howto()
        sys.exit(0)
    elif query.startswith("topic ") or query.startswith("naves "):
        q = query.replace("topic ", "").replace("naves ", "").strip()
        if not agent.display_naves(q):
            console.print("[warning]No Nave's Topical Bible entry found.[/]")
            sys.exit(1)
        sys.exit(0)
    elif query == "commentary":
        agent.display_commentary_howto()
        sys.exit(0)
    elif query.startswith("commentary "):
        q = query.replace("commentary ", "").strip()
        if not agent.display_commentary(q):
            sys.exit(1)
        sys.exit(0)

    if args.define or query.startswith("define"):
        q = query.replace("define ", "").strip()
        if not q or q == "define": agent.display_dictionary_howto()
        else:
            dictionary_found = agent.display_dictionary(q)
            encyclopedia_found = agent.display_encyclopedia(q)
            if not dictionary_found and not encyclopedia_found:
                console.print("[warning]No dictionary or encyclopedia entry found.[/]")
    elif args.creed or query.startswith("creed"):
        q = query.replace("creed ", "").strip()
        if not q or q == "creed": agent.display_creed_navigator()
        elif not agent.display_creed_navigator(q):
            console.print("[warning]No creed or confession entry found.[/]")
            sys.exit(1)
    elif args.strongs:
        if not query:
            agent.display_strongs_howto()
            sys.exit(1)
        if not agent.display_english_strongs(query):
            if not agent.display_strongs(query):
                console.print("[warning]No Strong's entries found for that term.[/]")
                sys.exit(1)
    elif re.match(r'^[GH]\d+', query, re.IGNORECASE):
        if not agent.display_strongs(query):
            console.print("[warning]No Strong's entry found for that number.[/]")
            sys.exit(1)
    elif query:
        if not agent.display_verse(query, interlinear=args.interlinear, animate=args.animate):
            if not agent.display_strongs(query):
                agent.display_search_howto()
                sys.exit(1)
    else:
        agent.display_intro()

if __name__ == "__main__":
    main()

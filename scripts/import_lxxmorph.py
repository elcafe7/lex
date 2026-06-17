#!/usr/bin/env python3
import argparse
import os
import re
import sqlite3

from init_lxx_db import DEFAULT_DB, init_lxx_db


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
DEFAULT_SOURCE = os.path.join(ROOT, "sources", "lxxmorph")

FILE_BOOKS = {
    "01.Gen.1.mlxx": ("GEN", "Genesis"), "02.Gen.2.mlxx": ("GEN", "Genesis"),
    "03.Exod.mlxx": ("EXO", "Exodus"), "04.Lev.mlxx": ("LEV", "Leviticus"),
    "05.Num.mlxx": ("NUM", "Numbers"), "06.Deut.mlxx": ("DEU", "Deuteronomy"),
    "07.JoshB.mlxx": ("JOS", "Joshua B"), "08.JoshA.mlxx": ("JOSA", "Joshua A"),
    "09.JudgesB.mlxx": ("JDG", "Judges B"), "10.JudgesA.mlxx": ("JDGA", "Judges A"),
    "11.Ruth.mlxx": ("RUT", "Ruth"), "12.1Sam.mlxx": ("1SA", "1 Samuel (1 Kingdoms)"),
    "13.2Sam.mlxx": ("2SA", "2 Samuel (2 Kingdoms)"), "14.1Kings.mlxx": ("1KI", "1 Kings (3 Kingdoms)"),
    "15.2Kings.mlxx": ("2KI", "2 Kings (4 Kingdoms)"), "16.1Chron.mlxx": ("1CH", "1 Chronicles"),
    "17.2Chron.mlxx": ("2CH", "2 Chronicles"), "18.1Esdras.mlxx": ("1ES", "Esdras A/I"),
    "19.2Esdras.mlxx": ("2ES", "Esdras B/II"),
    "20.Esther.mlxx": ("EST", "Esther (with additions)"), "21.Judith.mlxx": ("JDT", "Judith"),
    "22.TobitBA.mlxx": ("TOB", "Tobit BA"), "23.TobitS.mlxx": ("TOBS", "Tobit S"),
    "24.1Macc.mlxx": ("1MA", "I Maccabees"),
    "25.2Macc.mlxx": ("2MA", "II Maccabees"), "26.3Macc.mlxx": ("3MA", "III Maccabees"),
    "27.4Macc.mlxx": ("4MA", "IV Maccabees"), "28.Psalms1.mlxx": ("PSA", "Psalms"),
    "29.Psalms2.mlxx": ("PSA", "Psalms"), "30.Odes.mlxx": ("ODE", "Odes"),
    "31.Proverbs.mlxx": ("PRO", "Proverbs"), "32.Qoheleth.mlxx": ("ECC", "Ecclesiastes (Preacher)"),
    "33.Canticles.mlxx": ("SNG", "Canticle (Song of Solomon)"), "34.Job.mlxx": ("JOB", "Job"),
    "35.Wisdom.mlxx": ("WIS", "Wisdom of Solomon"), "36.Sirach.mlxx": ("SIR", "Wisdom of Sirach"),
    "37.PsSol.mlxx": ("PSS", "Psalms of Solomon"), "38.Hosea.mlxx": ("HOS", "Hosea"),
    "39.Micah.mlxx": ("MIC", "Micah"), "40.Amos.mlxx": ("AMO", "Amos"),
    "41.Joel.mlxx": ("JOL", "Joel"), "42.Jonah.mlxx": ("JON", "Jonah"),
    "43.Obadiah.mlxx": ("OBA", "Obadiah"), "44.Nahum.mlxx": ("NAM", "Nahum"),
    "45.Habakkuk.mlxx": ("HAB", "Habakkuk"), "46.Zeph.mlxx": ("ZEP", "Zephaniah"),
    "47.Haggai.mlxx": ("HAG", "Haggai"), "48.Zech.mlxx": ("ZEC", "Zechariah"),
    "49.Malachi.mlxx": ("MAL", "Malachi"), "50.Isaiah1.mlxx": ("ISA", "Isaiah"),
    "51.Isaiah2.mlxx": ("ISA", "Isaiah"), "52.Jer1.mlxx": ("JER", "Jeremiah"),
    "53.Jer2.mlxx": ("JER", "Jeremiah"), "54.Baruch.mlxx": ("BAR", "Baruch"),
    "55.EpJer.mlxx": ("EPJ", "Epistle of Jeremiah"), "56.Lam.mlxx": ("LAM", "Lamentations (Threni)"),
    "57.Ezek1.mlxx": ("EZK", "Ezekiel"), "58.Ezek2.mlxx": ("EZK", "Ezekiel"),
    "59.BelOG.mlxx": ("BEL", "Bel LXX"), "60.BelTh.mlxx": ("BELTH", "Bel TH"),
    "61.DanielOG.mlxx": ("DAN", "Daniel LXX"), "62.DanielTh.mlxx": ("DANTH", "Daniel TH"),
    "63.SusOG.mlxx": ("SUS", "Susanna LXX"), "64.SusTh.mlxx": ("SUSTH", "Susanna TH"),
}

POS_NAMES = {
    "N": "NOUN", "A": "ADJ", "R": "PRON", "C": "CCONJ", "X": "PART",
    "I": "INTJ", "M": "NUM", "P": "ADP", "D": "ADV", "V": "VERB",
}
CASES = {"N": "Nom", "G": "Gen", "D": "Dat", "A": "Acc", "V": "Voc"}
NUMBERS = {"S": "Sing", "D": "Dual", "P": "Plur"}
GENDERS = {"M": "Masc", "F": "Fem", "N": "Neut"}
TENSES = {"P": "Pres", "I": "Imp", "F": "Fut", "A": "Aor", "X": "Perf", "Y": "Plup"}
VOICES = {"A": "Act", "M": "Mid", "P": "Pass"}
MOODS = {"I": "Ind", "D": "Imp", "S": "Sub", "O": "Opt", "N": "Inf", "P": "Part"}
DEGREES = {"C": "Cmp", "S": "Sup"}

BETA = {
    "A": "α", "B": "β", "G": "γ", "D": "δ", "E": "ε", "Z": "ζ", "H": "η",
    "Q": "θ", "I": "ι", "K": "κ", "L": "λ", "M": "μ", "N": "ν", "C": "ξ",
    "O": "ο", "P": "π", "R": "ρ", "S": "σ", "T": "τ", "U": "υ", "F": "φ",
    "X": "χ", "Y": "ψ", "W": "ω",
}


def beta_to_greek(value):
    text = value.split()[0] if value else ""
    text = re.sub(r"[^A-Z*]+", "", text.upper())
    chars = []
    for index, char in enumerate(text):
        if char == "*":
            continue
        greek = BETA.get(char)
        if not greek:
            continue
        if index + 1 == len(text) and greek == "σ":
            greek = "ς"
        chars.append(greek)
    return "".join(chars)


def parse_ref(line):
    match = re.match(r"^[A-Za-z0-9/]+ (\d+):(\d+)$", line.strip())
    if not match:
        single_chapter_match = re.match(r"^[A-Za-z0-9/]+ (\d+)(?:/\d+)?$", line.strip())
        if not single_chapter_match:
            return None
        return 1, int(single_chapter_match.group(1))
    chapter, verse = match.groups()
    return int(chapter), int(verse)


def parse_line(line):
    parts = line.rstrip("\n").split()
    if len(parts) < 3:
        return None
    surface = parts[0]
    type_code = parts[1]
    if len(parts) >= 4 and re.match(r"^[A-Z0-9]+$", parts[2] or ""):
        parse_code = parts[2]
        lemma = parts[3]
        extras = parts[4:]
    else:
        parse_code = ""
        lemma = parts[2]
        extras = parts[3:]
    return surface, type_code, parse_code, lemma, " ".join(extras)


def decode_parse(type_code, parse_code):
    pos = POS_NAMES.get(type_code[:1], type_code[:1] or "")
    data = {"pos": pos, "case": None, "number": None, "gender": None, "tense": None, "voice": None, "mood": None, "person": None, "degree": None}
    if not parse_code:
        return data
    if pos in {"NOUN", "PRON", "ADJ", "NUM"}:
        data["case"] = CASES.get(parse_code[:1])
        data["number"] = NUMBERS.get(parse_code[1:2])
        data["gender"] = GENDERS.get(parse_code[2:3])
        if len(parse_code) > 3:
            data["degree"] = DEGREES.get(parse_code[3:4])
    elif pos == "VERB":
        data["tense"] = TENSES.get(parse_code[:1])
        data["voice"] = VOICES.get(parse_code[1:2])
        data["mood"] = MOODS.get(parse_code[2:3])
        if data["mood"] == "Part":
            data["case"] = CASES.get(parse_code[3:4])
            data["number"] = NUMBERS.get(parse_code[4:5])
            data["gender"] = GENDERS.get(parse_code[5:6])
        else:
            data["person"] = parse_code[3:4] or None
            data["number"] = NUMBERS.get(parse_code[4:5])
    return data


def iter_rows(source_dir):
    for filename in sorted(FILE_BOOKS):
        path = os.path.join(source_dir, filename)
        if not os.path.exists(path):
            continue
        book_code, _ = FILE_BOOKS[filename]
        chapter = verse = None
        word_num = 0
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                ref = parse_ref(stripped)
                if ref:
                    chapter, verse = ref
                    word_num = 0
                    continue
                parsed = parse_line(line)
                if not parsed or chapter is None:
                    continue
                word_num += 1
                surface, type_code, parse_code, lemma, extras = parsed
                decoded = decode_parse(type_code, parse_code)
                ref_text = f"{book_code} {chapter}:{verse}"
                yield {
                    "id": f"{ref_text}:ccat:{word_num}",
                    "ref": ref_text,
                    "book": book_code,
                    "chapter": chapter,
                    "verse": verse,
                    "word_num": word_num,
                    "text": beta_to_greek(surface),
                    "lemma": beta_to_greek(lemma),
                    "strong": None,
                    "lexicon_id": lemma,
                    "lexicon_source": "ccat:lxxmorph",
                    "gloss": None,
                    "morph": f"{type_code} {parse_code}".strip(),
                    "pos": decoded["pos"],
                    "person": decoded["person"],
                    "number": decoded["number"],
                    "gender": decoded["gender"],
                    "word_case": decoded["case"],
                    "tense": decoded["tense"],
                    "voice": decoded["voice"],
                    "mood": decoded["mood"],
                    "degree": decoded["degree"],
                    "head": None,
                    "dependency": None,
                    "misc": f"source={filename};surface_beta={surface};lemma_beta={lemma};extras={extras}".rstrip(";"),
                }


def import_rows(db_path, source_dir, replace=False):
    init_lxx_db(db_path, replace=False)
    rows = list(iter_rows(source_dir))
    if not rows:
        raise SystemExit(f"No .mlxx rows found in {source_dir}")
    columns = [
        "id", "ref", "book", "chapter", "verse", "word_num", "text", "lemma",
        "strong", "lexicon_id", "lexicon_source", "gloss", "morph", "pos",
        "person", "number", "gender", "word_case", "tense", "voice", "mood",
        "degree", "head", "dependency", "misc",
    ]
    with sqlite3.connect(db_path) as conn:
        if replace:
            conn.execute("DELETE FROM lxx_text")
            conn.execute("DELETE FROM lxx_lemma_strong_map")
        placeholders = ", ".join("?" for _ in columns)
        conn.executemany(
            f"INSERT OR REPLACE INTO lxx_text ({', '.join(columns)}) VALUES ({placeholders})",
            [[row[column] for column in columns] for row in rows],
        )
        conn.commit()
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Import CCAT LXX morphology .mlxx files into Lex lxx_text.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Directory containing .mlxx files")
    parser.add_argument("--db", default=DEFAULT_DB, help="Target Lex LXX SQLite database")
    parser.add_argument("--replace", action="store_true", help="Replace lxx_text before import")
    args = parser.parse_args()

    count = import_rows(args.db, args.source, replace=args.replace)
    print(f"Imported {count} CCAT LXX morphology rows into {args.db}")


if __name__ == "__main__":
    main()

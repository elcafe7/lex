#!/usr/bin/env python3
import argparse
import os
import subprocess


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
DEFAULT_OUT = os.path.join(ROOT, "sources", "lxxmorph")
BASE_URL = "https://ccat.sas.upenn.edu/gopher/text/religion/biblical/lxxmorph"

FILES = [
    "01.Gen.1.mlxx", "02.Gen.2.mlxx", "03.Exod.mlxx", "04.Lev.mlxx",
    "05.Num.mlxx", "06.Deut.mlxx", "07.JoshB.mlxx", "08.JoshA.mlxx",
    "09.JudgesB.mlxx", "10.JudgesA.mlxx", "11.Ruth.mlxx", "12.1Sam.mlxx",
    "13.2Sam.mlxx", "14.1Kings.mlxx", "15.2Kings.mlxx", "16.1Chron.mlxx",
    "17.2Chron.mlxx", "18.1Esdras.mlxx", "19.2Esdras.mlxx", "20.Esther.mlxx",
    "21.Judith.mlxx", "22.TobitBA.mlxx", "23.TobitS.mlxx", "24.1Macc.mlxx",
    "25.2Macc.mlxx", "26.3Macc.mlxx", "27.4Macc.mlxx", "28.Psalms1.mlxx",
    "29.Psalms2.mlxx", "30.Odes.mlxx", "31.Proverbs.mlxx", "32.Qoheleth.mlxx",
    "33.Canticles.mlxx", "34.Job.mlxx", "35.Wisdom.mlxx", "36.Sirach.mlxx",
    "37.PsSol.mlxx", "38.Hosea.mlxx", "39.Micah.mlxx", "40.Amos.mlxx",
    "41.Joel.mlxx", "42.Jonah.mlxx", "43.Obadiah.mlxx", "44.Nahum.mlxx",
    "45.Habakkuk.mlxx", "46.Zeph.mlxx", "47.Haggai.mlxx", "48.Zech.mlxx",
    "49.Malachi.mlxx", "50.Isaiah1.mlxx", "51.Isaiah2.mlxx",
    "52.Jer1.mlxx", "53.Jer2.mlxx", "54.Baruch.mlxx", "55.EpJer.mlxx",
    "56.Lam.mlxx", "57.Ezek1.mlxx", "58.Ezek2.mlxx", "59.BelOG.mlxx",
    "60.BelTh.mlxx", "61.DanielOG.mlxx", "62.DanielTh.mlxx",
    "63.SusOG.mlxx", "64.SusTh.mlxx",
]


def main():
    parser = argparse.ArgumentParser(description="Download CCAT LXX morphology files.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output directory")
    parser.add_argument("--force", action="store_true", help="Download even if the file exists")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for filename in FILES:
        target = os.path.join(args.out, filename)
        if os.path.exists(target) and not args.force:
            print(f"exists {filename}")
            continue
        url = f"{BASE_URL}/{filename}"
        subprocess.run(["curl", "-fsSL", url, "-o", target], check=True)
        print(f"downloaded {filename}")


if __name__ == "__main__":
    main()

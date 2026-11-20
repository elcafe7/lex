#!/usr/bin/env python3
"""Download CCAT LXX morphology files into runtime-data with pinned checksums.

Operator-supplied --out/--manifest paths are confined under approved roots
(CodeQL py/path-injection). Declared source names come from FILES only.
"""
import argparse
import hashlib
import hmac
import os
import subprocess
import tempfile

from safe_paths import MissingSourceFile, UnsafePathError, safe_source_file


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runtime-data")
DEFAULT_OUT = os.path.join(ROOT, "sources", "lxxmorph")
BASE_URL = "https://ccat.sas.upenn.edu/gopher/text/religion/biblical/lxxmorph"
DEFAULT_MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lxxmorph.sha256")
SCRIPTS_ROOT = os.path.dirname(os.path.abspath(__file__))

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


def load_checksums(path):
    checksums = {}
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            parts = raw.strip().split()
            if len(parts) != 2 or len(parts[0]) != 64 or any(
                char not in "0123456789abcdef" for char in parts[0]
            ):
                raise ValueError(f"invalid checksum manifest line: {raw!r}")
            checksum, filename = parts
            if filename in checksums:
                raise ValueError(f"duplicate checksum entry: {filename}")
            checksums[filename] = checksum
    missing = set(FILES) - set(checksums)
    extra = set(checksums) - set(FILES)
    if missing or extra:
        raise ValueError(
            "checksum manifest does not match declared files "
            f"(missing={sorted(missing)}, extra={sorted(extra)})"
        )
    return checksums


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_verified(url, target, expected):
    directory = os.path.dirname(target)
    fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(target)}.", dir=directory)
    os.close(fd)
    try:
        subprocess.run(["curl", "-fsSL", url, "-o", temporary], check=True)
        actual = sha256_file(temporary)
        if not hmac.compare_digest(actual, expected):
            raise ValueError(f"checksum mismatch for {os.path.basename(target)}")
        os.replace(temporary, target)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def resolve_manifest(raw):
    """Require the manifest to stay under scripts/ before opening it."""
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise UnsafePathError(f"invalid manifest path: {raw!r}")
    scripts_real = os.path.realpath(SCRIPTS_ROOT)
    # Prefer basename confinement (same pattern as safe_source_file callers).
    name = os.path.basename(raw)
    try:
        candidate = safe_source_file(scripts_real, name)
    except MissingSourceFile as exc:
        raise UnsafePathError(str(exc)) from exc
    # If the operator passed a path, it must resolve to that same file.
    resolved = os.path.realpath(raw)
    if resolved != candidate:
        raise UnsafePathError(f"manifest must be scripts/{name}")
    return candidate


def resolve_output_dir(raw):
    """Require --out to stay under runtime-data; create it if needed."""
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise UnsafePathError(f"invalid output directory: {raw!r}")
    root_real = os.path.realpath(ROOT)
    prefix = root_real if root_real.endswith(os.sep) else root_real + os.sep

    # Walk up to an existing ancestor so realpath cannot escape via missing dirs.
    existing = raw
    while existing and not os.path.exists(existing):
        existing = os.path.dirname(existing)
    if not existing:
        raise UnsafePathError(f"output directory must remain under {root_real}")
    existing_real = os.path.realpath(existing)
    if existing_real != root_real and not existing_real.startswith(prefix):
        raise UnsafePathError(f"output directory must remain under {root_real}")

    os.makedirs(raw, exist_ok=True)
    out_real = os.path.realpath(raw)
    if out_real != root_real and not out_real.startswith(prefix):
        raise UnsafePathError(f"output directory must remain under {root_real}")
    return out_real


def confined_target(output_dir, filename):
    """Join an allowlisted filename under output_dir and re-check containment."""
    target = os.path.realpath(os.path.join(output_dir, filename))
    prefix = output_dir if output_dir.endswith(os.sep) else output_dir + os.sep
    if not target.startswith(prefix):
        raise UnsafePathError(f"output file escapes output directory: {filename!r}")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download CCAT LXX morphology files.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output directory under runtime-data")
    parser.add_argument("--force", action="store_true", help="Download even if the file exists")
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help="SHA-256 manifest (must stay under scripts/)",
    )
    args = parser.parse_args(argv)

    try:
        manifest = resolve_manifest(args.manifest)
        output_dir = resolve_output_dir(args.out)
        checksums = load_checksums(manifest)
    except (OSError, ValueError, UnsafePathError) as error:
        parser.error(f"cannot prepare download: {error}")

    for filename in FILES:
        try:
            target = confined_target(output_dir, filename)
        except UnsafePathError as error:
            parser.error(str(error))
        expected = checksums[filename]
        if os.path.exists(target):
            if hmac.compare_digest(sha256_file(target), expected) and not args.force:
                print(f"exists {filename}")
                continue
            if not args.force:
                parser.error(
                    f"checksum mismatch for existing {filename}; use --force to replace it"
                )
        url = f"{BASE_URL}/{filename}"
        fetch_verified(url, target, expected)
        print(f"downloaded {filename}")


if __name__ == "__main__":
    main()

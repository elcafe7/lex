#!/usr/bin/env python3
"""Summarise an OSV-Scanner JSON report and gate a release on it.

Usage: osv_gate.py <osv.json> <report.md> [--threshold 7.0] [--title T]
                   [--badge-json verification.json --report-url URL
                    --tool-version 2.7.0 --release TAG --repository o/r]

Exit codes: 0 = clean (publish), 1 = findings (do not publish),
            2 = bad arguments or a path outside the workspace (do not publish).

- Advisories with a CVSS score at or above --threshold (7.0 = High,
  9.0 = Critical) fail the release.
- Scored advisories below the threshold also hold the release: nothing is
  published unless the scan is clean, so a published report and badge always
  say "0 known vulnerabilities".
- Advisories with no CVSS score are listed as "Unscored" in the report and
  emitted as GitHub `::warning::` annotations. They do not hold the release
  on their own; review them in the report.

The Markdown report always ends with a "Suggested fix" section (fixed
versions from OSV where known) and a fix prompt that can be pasted into an
issue or a coding agent. --badge-json is written ONLY when the result is
PASS; a failed scan never produces badge data.

Every input and output path must resolve (realpath, symlinks followed) to a
location under GITHUB_WORKSPACE, or the current directory when that is not
set. Anything else (".." escapes, absolute paths elsewhere, NUL bytes,
symlinks pointing outside) stops the gate with exit code 2 before any file
is read or written, so nothing is published.
Standard library only.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path


class UnsafePathError(ValueError):
    """A path argument resolves outside the allowed base directory."""


def allowed_base():
    """GITHUB_WORKSPACE when set (Actions), else the current directory; resolved."""
    return os.path.realpath(os.environ.get("GITHUB_WORKSPACE") or os.getcwd())


def safe_path(raw, what):
    """Resolve a user-supplied path and require it to sit under allowed_base().

    normpath + realpath (follows symlinks, so a link pointing outside the base
    is rejected), then a startswith check on base + os.sep. Relative paths are
    taken relative to the base. Returns the resolved absolute path.
    """
    if not isinstance(raw, str) or not raw or "\0" in raw:
        raise UnsafePathError(f"{what}: empty path or NUL byte")
    base = allowed_base()
    resolved = os.path.realpath(os.path.normpath(os.path.join(base, raw)))
    if not resolved.startswith(base + os.sep):
        raise UnsafePathError(f"{what}: {raw!r} resolves outside {base}")
    return resolved


def label(score):
    if score is None:
        return "Unscored"
    if score >= 9.0:
        return "Critical"
    if score >= 7.0:
        return "High"
    if score >= 4.0:
        return "Medium"
    if score > 0:
        return "Low"
    return "None"


def parse_score(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def annotation_escape(text):
    """Escape a message for a GitHub workflow command."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def version_key(v):
    """Rough version ordering: numeric parts compare as numbers."""
    import re
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"[.\-+_]", v) if p]


def fixed_versions(pkg, ids):
    """Fixed versions OSV lists for this package across the group's advisories."""
    name = ((pkg.get("package") or {}).get("name") or "").lower()
    found = set()
    for vuln in pkg.get("vulnerabilities") or []:
        vids = {vuln.get("id")} | set(vuln.get("aliases") or [])
        if ids and not (vids & set(ids)):
            continue
        for aff in vuln.get("affected") or []:
            if ((aff.get("package") or {}).get("name") or "").lower() not in ("", name):
                continue
            for rng in aff.get("ranges") or []:
                for ev in rng.get("events") or []:
                    if ev.get("fixed"):
                        found.add(str(ev["fixed"]))
    return sorted(found, key=version_key)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report_json")
    parser.add_argument("report_md")
    parser.add_argument("--threshold", type=float, default=7.0)
    parser.add_argument("--title", default="OSV-Scanner report")
    parser.add_argument("--badge-json", help="write badge data (JSON) here, only when the scan is clean")
    parser.add_argument("--report-url", default="", help="public URL of the human-readable report")
    parser.add_argument("--tool-version", default="", help="OSV-Scanner version used for the scan")
    parser.add_argument("--release", default="", help="release tag the scan belongs to")
    parser.add_argument("--repository", default="", help="owner/repo")
    args = parser.parse_args()

    # Check every path before reading or writing anything.
    try:
        report_json = safe_path(args.report_json, "report_json")
        report_md = safe_path(args.report_md, "report_md")
        badge_json = safe_path(args.badge_json, "--badge-json") if args.badge_json else None
    except UnsafePathError as exc:
        print(f"::error title=osv_gate::{annotation_escape(str(exc))}")
        print(f"error: {exc}", file=sys.stderr)
        return 2

    with open(report_json, encoding="utf-8") as fh:
        data = json.loads(fh.read())
    rows = []
    sources = []
    for result in data.get("results") or []:
        source = (result.get("source") or {}).get("path", "?")
        packages = result.get("packages") or []
        sources.append((source, len(packages)))
        for pkg in packages:
            info = pkg.get("package") or {}
            for group in pkg.get("groups") or []:
                ids = group.get("aliases") or group.get("ids") or []
                score = parse_score(group.get("max_severity"))
                rows.append({
                    "source": Path(source).name,
                    "package": f"{info.get('ecosystem', '?')}/{info.get('name', '?')}",
                    "version": info.get("version", "?"),
                    "ids": ", ".join(ids),
                    "score": score,
                    "severity": label(score),
                    "fixed": fixed_versions(pkg, set(group.get("ids") or []) | set(ids)),
                })

    blocking = [r for r in rows if r["score"] is not None and r["score"] >= args.threshold]
    held = [r for r in rows if r["score"] is not None and r["score"] < args.threshold]
    unscored = [r for r in rows if r["score"] is None]
    scored = blocking + held
    failed = bool(scored)
    for r in unscored:
        message = annotation_escape(
            f"{r['package']} {r['version']}: {r['ids'] or 'unknown id'} has no CVSS score "
            f"(non-blocking, review manually) [{r['source']}]"
        )
        print(f"::warning title=Unscored advisory::{message}")

    scanned_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    now = scanned_at.strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {args.title}",
        "",
        f"- Scanned: {now}",
        f"- Gate: fail on CVSS >= {args.threshold} (High/Critical); lower scored findings also hold the release",
        f"- Findings: {len(rows)} total, {len(blocking)} blocking, {len(held)} below threshold",
        f"- Unscored: {len(unscored)} (no CVSS score; non-blocking, review manually)",
        f"- Result: {'FAIL' if failed else 'PASS'}",
        "",
        "This report reflects the OSV database on the scan date only. "
        "New advisories can appear later; re-scan the SBOM to check again.",
        "",
    ]
    if rows:
        lines += ["| Severity | CVSS | Package | Version | IDs | Fixed in | Source |",
                  "|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: -(r["score"] or 0)):
            score = "" if r["score"] is None else f"{r['score']:.1f}"
            fixed = ", ".join(r["fixed"]) or "no fix listed"
            lines.append(f"| {r['severity']} | {score} | {r['package']} | {r['version']} | {r['ids']} | {fixed} | {r['source']} |")
    else:
        lines.append("No known vulnerabilities matched the scanned packages on the scan date.")
    lines += ["", "## Inputs scanned", ""]
    if sources:
        lines += [f"- `{Path(s).name}`: {n} packages" for s, n in sources]
    else:
        lines.append("- (OSV-Scanner returned no vulnerable sources; see the JSON report for the package list)")

    if rows:
        lines += ["", "## Suggested fix", ""]
        seen = set()
        for r in sorted(scored, key=lambda r: -(r["score"] or 0)) + unscored:
            key = (r["package"], r["version"])
            if key in seen:
                continue
            seen.add(key)
            pkg_rows = [x for x in rows if (x["package"], x["version"]) == key]
            fixes = sorted({f for x in pkg_rows for f in x["fixed"]}, key=version_key)
            # Smallest fixed version above the current one, per advisory; the
            # package needs the highest of those to clear every advisory.
            current = version_key(r["version"])
            needed = []
            for x in pkg_rows:
                above = [f for f in x["fixed"] if version_key(f) > current]
                if above:
                    needed.append(min(above, key=version_key))
            target = max(needed, key=version_key) if needed else None
            what = "must fix before release" if any(x["score"] is not None for x in pkg_rows) else "unscored: review"
            if target:
                lines.append(f"- `{r['package']}` {r['version']} ({what}): upgrade to {target} or later "
                             f"(OSV lists fixes in: {', '.join(fixes)}).")
            else:
                lines.append(f"- `{r['package']}` {r['version']} ({what}): no fixed version listed; "
                             "remove or replace the dependency, or document why it is not exploitable.")
        lines += [
            "",
            "### Fix prompt",
            "",
            "```text",
            f"The release scan for {' '.join(x for x in (args.repository or 'this repository', args.release) if x)} failed "
            f"(OSV-Scanner{(' ' + args.tool_version) if args.tool_version else ''}).",
            "Upgrade or replace the dependencies listed under 'Suggested fix' in this report,",
            "update the lockfile/manifest, run the tests, and open a PR. After it merges,",
            "re-run the release (re-push the tag or re-run the failed workflow run).",
            "Nothing was published for this tag: no release, assets, report or badge data.",
            "```",
        ]
    with open(report_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))

    if badge_json:
        if failed:
            if os.path.lexists(badge_json):
                os.remove(badge_json)
        else:
            badge = {
                "schema": 1,
                "tool": "OSV-Scanner",
                "tool_version": args.tool_version,
                "date": scanned_at.strftime("%Y-%m-%d"),
                "scanned_at": scanned_at.isoformat().replace("+00:00", "Z"),
                "result": "pass",
                "known_vulnerabilities": 0,
                "unscored": len(unscored),
                "threshold_cvss": args.threshold,
                "report_url": args.report_url,
                "release": args.release,
                "repository": args.repository,
                "stale_after_days": 30,
            }
            with open(badge_json, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(badge, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Summarise an OSV-Scanner JSON report and gate a release on severity.

Usage: osv_gate.py <osv.json> <report.md> [--threshold 7.0]
                   [--badge-json verification.json --report-url URL
                    --tool-version 2.7.0 --release v1.2.3]

Writes a readable Markdown report and exits 1 when any vulnerability group
has a CVSS max_severity at or above the threshold (7.0 = High, 9.0 =
Critical). Vulnerabilities without a CVSS score are listed as "unscored",
emitted as GitHub `::warning::` annotations, and do not fail the gate on
their own; review them in the report.

With --badge-json, also writes a small JSON file that download pages can
read to show "Verified by OSV-Scanner on <date> · N known vulnerabilities ·
view report" (see docs/RELEASE_VERIFICATION.md for the schema).
Standard library only.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report_json")
    parser.add_argument("report_md")
    parser.add_argument("--threshold", type=float, default=7.0)
    parser.add_argument("--title", default="OSV-Scanner report")
    parser.add_argument("--badge-json", help="also write badge data (JSON) to this path")
    parser.add_argument("--report-url", default="", help="public URL of the human-readable report")
    parser.add_argument("--tool-version", default="", help="OSV-Scanner version used for the scan")
    parser.add_argument("--release", default="", help="release tag the scan belongs to")
    parser.add_argument("--repository", default="", help="owner/repo")
    args = parser.parse_args()

    data = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    rows = []
    sources = []
    for result in data.get("results") or []:
        source = (result.get("source") or {}).get("path", "?")
        packages = result.get("packages") or []
        sources.append((source, len(packages)))
        for pkg in packages:
            info = pkg.get("package") or {}
            for group in pkg.get("groups") or []:
                score = parse_score(group.get("max_severity"))
                rows.append({
                    "source": Path(source).name,
                    "package": f"{info.get('ecosystem', '?')}/{info.get('name', '?')}",
                    "version": info.get("version", "?"),
                    "ids": ", ".join(group.get("aliases") or group.get("ids") or []),
                    "score": score,
                    "severity": label(score),
                })

    blocking = [r for r in rows if r["score"] is not None and r["score"] >= args.threshold]
    unscored = [r for r in rows if r["score"] is None]
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
        f"- Gate: fail on CVSS >= {args.threshold} (High/Critical)",
        f"- Findings: {len(rows)} total, {len(blocking)} blocking",
        f"- Unscored: {len(unscored)} (no CVSS score; non-blocking, review manually)",
        f"- Result: {'FAIL' if blocking else 'PASS'}",
        "",
        "This report reflects the OSV database on the scan date only. "
        "New advisories can appear later; re-scan the SBOM to check again.",
        "",
    ]
    if rows:
        lines += ["| Severity | CVSS | Package | Version | IDs | Source |",
                  "|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: -(r["score"] or 0)):
            score = "" if r["score"] is None else f"{r['score']:.1f}"
            lines.append(f"| {r['severity']} | {score} | {r['package']} | {r['version']} | {r['ids']} | {r['source']} |")
    else:
        lines.append("No known vulnerabilities matched the scanned packages on the scan date.")
    lines += ["", "## Inputs scanned", ""]
    if sources:
        lines += [f"- `{Path(s).name}`: {n} packages" for s, n in sources]
    else:
        lines.append("- (OSV-Scanner returned no vulnerable sources; see the JSON report for the package list)")
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.badge_json:
        badge = {
            "schema": 1,
            "tool": "OSV-Scanner",
            "tool_version": args.tool_version,
            "date": scanned_at.strftime("%Y-%m-%d"),
            "scanned_at": scanned_at.isoformat().replace("+00:00", "Z"),
            "result": "fail" if blocking else "pass",
            "known_vulnerabilities": len(rows),
            "blocking": len(blocking),
            "unscored": len(unscored),
            "threshold_cvss": args.threshold,
            "report_url": args.report_url,
            "release": args.release,
            "repository": args.repository,
            "stale_after_days": 30,
        }
        Path(args.badge_json).write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())

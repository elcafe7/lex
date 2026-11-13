#!/usr/bin/env python3
"""Summarise a Bandit JSON report and gate a release (or a PR) on it.

Usage: bandit_gate.py <bandit.json> <report.md> [--title T] [--release TAG]
                      [--repository o/r] [--tool-version 1.9.4]
                      [--summary-json bandit-gate.json]

Exit codes: 0 = clean, 1 = findings or an incomplete scan (do not publish),
            2 = bad arguments or a path outside the workspace (do not publish).

Gate ("block on anything" at medium and above):
- Any finding of MEDIUM or HIGH severity fails, at ANY confidence level.
  Low-confidence medium findings are not filtered out: in lex they were
  string-built SQL (B608), the kind of finding that must be read, not hidden.
- A Bandit run that could not parse a file ("errors" in the JSON), or JSON
  that is missing, malformed or not a Bandit report, also fails: an
  incomplete scan never counts as clean.
- LOW severity findings never fail. They are counted by test id in the
  report as information.
- There is no baseline file and no skipped test. A proven false positive is
  silenced only by an inline `# nosec BXXX  # reason: ...` on that line;
  Bandit counts those as "skipped_tests" and the report shows the count.

The Markdown report is safe to paste into an issue: it lists test id,
severity, confidence, file:line and Bandit's one-line description for each
finding, never the flagged source lines. It ends with a "Suggested fix"
section and a fix prompt, like osv_gate.py.

Every input and output path must resolve under GITHUB_WORKSPACE (or the
current directory), with the same rules as osv_gate.py. Standard library only.
"""

import argparse
import collections
import json
import re
import sys

from osv_gate import UnsafePathError, safe_path

BLOCKING = ("HIGH", "MEDIUM")
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNDEFINED": 3}
_TEST_ID = re.compile(r"^B[0-9]{3}$")
_DOC_URL = re.compile(r"^https://bandit\.readthedocs\.io/[A-Za-z0-9._/#-]+$")
_SAFE_FILE = re.compile(r"[^A-Za-z0-9._/-]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(value, limit=200):
    """One line of plain Markdown-table-safe text from an untrusted string."""
    text = _CONTROL.sub(" ", str(value or ""))
    text = text.replace("|", "/").replace("`", "'").replace("<", "(").replace(">", ")")
    text = " ".join(text.split())
    return text[:limit] + ("..." if len(text) > limit else "")


def clean_file(value):
    name = str(value or "")
    if name.startswith("./"):
        name = name[2:]
    name = _SAFE_FILE.sub("_", name)[:160]
    return name or "?"


def clean_test_id(value):
    value = str(value or "")
    return value if _TEST_ID.match(value) else "B???"


def clean_level(value):
    value = str(value or "").upper()
    return value if value in SEVERITY_ORDER else "UNDEFINED"


def clean_line(value):
    return value if isinstance(value, int) and 0 <= value < 10_000_000 else 0


def annotation(text):
    """Escape a value for a GitHub workflow command (::error ...::text)."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def load_report(path):
    """Return (results, errors, skipped_nosec, problem)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return [], [], 0, f"Bandit JSON could not be read: {clean_text(exc, 120)}"
    if not isinstance(data, dict) or not isinstance(data.get("results"), list) \
            or not isinstance(data.get("metrics"), dict):
        return [], [], 0, "Not a Bandit JSON report (no results/metrics)."
    errors = data.get("errors") if isinstance(data.get("errors"), list) else []
    totals = data["metrics"].get("_totals") if isinstance(data["metrics"].get("_totals"), dict) else {}
    skipped = totals.get("skipped_tests", 0)
    skipped = skipped if isinstance(skipped, int) and skipped >= 0 else 0
    results = [r for r in data["results"] if isinstance(r, dict)]
    return results, errors, skipped, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bandit_json")
    ap.add_argument("report_md")
    ap.add_argument("--title", default="Bandit (Python static analysis) report")
    ap.add_argument("--release", default="")
    ap.add_argument("--repository", default="")
    ap.add_argument("--tool-version", default="")
    ap.add_argument("--summary-json", default="")
    args = ap.parse_args(argv)

    try:
        bandit_json = safe_path(args.bandit_json, "bandit JSON")
        report_md = safe_path(args.report_md, "report")
        summary_json = safe_path(args.summary_json, "summary JSON") if args.summary_json else ""
    except UnsafePathError as exc:
        print(f"::error title=Bandit gate::{annotation(exc)}", file=sys.stderr)
        return 2

    results, errors, skipped, problem = load_report(bandit_json)
    blocking = sorted(
        (r for r in results if clean_level(r.get("issue_severity")) in BLOCKING),
        key=lambda r: (SEVERITY_ORDER[clean_level(r.get("issue_severity"))],
                       clean_file(r.get("filename")), clean_line(r.get("line_number"))),
    )
    low = collections.Counter(
        clean_test_id(r.get("test_id")) for r in results
        if clean_level(r.get("issue_severity")) not in BLOCKING
    )
    failed = bool(problem or errors or blocking)
    tool = f"Bandit {clean_text(args.tool_version, 20)}".strip()

    lines = [f"# {clean_text(args.title, 120)}", ""]
    if problem:
        lines += [f"**Result: FAIL.** {problem} The scan did not complete, so it is not clean.", ""]
    elif blocking or errors:
        parts = []
        if blocking:
            parts.append(f"{len(blocking)} finding(s) of medium or high severity")
        if errors:
            parts.append(f"{len(errors)} file(s) Bandit could not scan")
        lines += [f"**Result: FAIL.** {tool}: {' and '.join(parts)}. A release with this result publishes nothing.", ""]
    else:
        lines += [f"**Result: PASS.** {tool}: 0 findings of medium or high severity (any confidence).", ""]
    lines += [
        "Gate: medium and high severity at any confidence fail; low severity is information only.",
        f"No baseline. Inline `# nosec` suppressions in the code: {skipped}.",
        "",
    ]

    if blocking:
        lines += ["## Findings (medium and high)", "",
                  "| Severity | Confidence | Test | Location | Issue |", "|---|---|---|---|---|"]
        for r in blocking:
            tid = clean_test_id(r.get("test_id"))
            name = clean_text(r.get("test_name"), 60)
            url = str(r.get("more_info") or "")
            test = f"[{tid}]({url}) {name}" if _DOC_URL.match(url) else f"{tid} {name}"
            loc = f"`{clean_file(r.get('filename'))}:{clean_line(r.get('line_number'))}`"
            lines.append(f"| {clean_level(r.get('issue_severity'))} | {clean_level(r.get('issue_confidence'))} "
                         f"| {test} | {loc} | {clean_text(r.get('issue_text'))} |")
            print(f"::error file={annotation(clean_file(r.get('filename')))},"
                  f"line={clean_line(r.get('line_number'))},title=Bandit {tid}::"
                  f"{annotation(clean_text(r.get('issue_text')))}")
        lines.append("")
    if errors:
        lines += ["## Files Bandit could not scan", ""]
        for e in errors[:50]:
            e = e if isinstance(e, dict) else {}
            lines.append(f"- `{clean_file(e.get('filename'))}`: {clean_text(e.get('reason'), 120)}")
        lines.append("")
    if low:
        lines += ["## Low severity (information only, does not block)", "",
                  "| Test | Count |", "|---|---|"]
        for tid, n in sorted(low.items()):
            lines.append(f"| {tid} | {n} |")
        lines.append("")

    if failed:
        target = " ".join(x for x in (clean_text(args.repository, 80) or "this repository",
                                      clean_text(args.release, 40)) if x)
        lines += [
            "## Suggested fix", "",
            "- Fix each finding above in the code (parameterised SQL, fixed URL schemes,",
            "  `tempfile` instead of hard-coded /tmp paths, no shell=True, and so on).",
            "- Only for a proven false positive: add `# nosec BXXX  # reason: ...` on that",
            "  line with the reason, and list it in the PR for security review.",
            "  Never add a baseline file or a skip in the Bandit command.",
            "- If Bandit could not parse a file, fix the syntax error.",
            "",
            "### Fix prompt", "",
            "```text",
            f"The Bandit check for {target} failed "
            "(medium or high severity findings, or files it could not scan).",
            "Read the full report (bandit.txt / bandit.json in the workflow run artifacts),",
            "fix each finding listed under 'Findings', run",
            "`bash scripts/bandit_check.sh bandit-report` (Bandit from",
            "`.github/requirements/bandit-requirements.txt`) until it passes, run the tests, and open a PR.",
            "Use an inline '# nosec BXXX  # reason: ...' only for a proven false positive.",
            "After it merges, release again. A blocked release publishes nothing.",
            "```",
        ]

    with open(report_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines[:6]))

    if summary_json:
        summary = {
            "schema": 1,
            "tool": "Bandit",
            "tool_version": clean_text(args.tool_version, 20),
            "result": "fail" if failed else "pass",
            "complete": not problem and not errors,
            "medium_high": len(blocking),
            "low": sum(low.values()),
            "nosec": skipped,
            "errors": len(errors),
        }
        with open(summary_json, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

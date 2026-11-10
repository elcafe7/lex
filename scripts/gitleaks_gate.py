#!/usr/bin/env python3
"""Summarise a redacted Gitleaks JSON report and gate a release (or a PR) on it.

Usage: gitleaks_gate.py <gitleaks.json> <report.md> [--title T] [--release TAG]
                        [--repository o/r] [--tool-version 8.30.1]
                        [--summary-json gitleaks-gate.json]

Exit codes: 0 = clean, 1 = findings or an incomplete scan (do not publish),
            2 = bad arguments or a path outside the workspace (do not publish).

Gate: any finding fails. A missing, malformed or non-list JSON report also
fails: an incomplete scan never counts as clean. There is no baseline file.
A proven false positive is listed in .gitleaks.toml with a reason, reviewed
in its PR.

The Markdown report is safe to paste into an issue: it lists rule id,
file:line, commit and fingerprint, never secret values (Match/Secret are
omitted even if the JSON was not redacted). It ends with a "Suggested fix"
section and a fix prompt, like bandit_gate.py.

Every input and output path must resolve under GITHUB_WORKSPACE (or the
current directory), with the same rules as osv_gate.py. Standard library only.
"""

import argparse
import json
import re
import sys

from osv_gate import UnsafePathError, safe_path

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SAFE_FILE = re.compile(r"[^A-Za-z0-9._/-]")
_RULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
_FINGERPRINT = re.compile(r"[^A-Za-z0-9._/:+=-]")


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


def clean_rule(value):
    value = str(value or "")
    return value if _RULE.match(value) else "unknown-rule"


def clean_line(value):
    return value if isinstance(value, int) and 0 <= value < 10_000_000 else 0


def clean_commit(value):
    value = str(value or "").lower()
    return value if _COMMIT.match(value) else "?"


def clean_fingerprint(value):
    text = _FINGERPRINT.sub("_", str(value or ""))[:200]
    return text or "?"


def annotation(text):
    """Escape a value for a GitHub workflow command (::error ...::text)."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def load_report(path):
    """Return (findings, problem). findings is a list of dicts."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return [], f"Gitleaks JSON could not be read: {clean_text(exc, 120)}"
    if not isinstance(data, list):
        return [], "Not a Gitleaks JSON report (expected a list of findings)."
    return [r for r in data if isinstance(r, dict)], None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gitleaks_json")
    ap.add_argument("report_md")
    ap.add_argument("--title", default="Gitleaks (secret scan) report")
    ap.add_argument("--release", default="")
    ap.add_argument("--repository", default="")
    ap.add_argument("--tool-version", default="")
    ap.add_argument("--summary-json", default="")
    args = ap.parse_args(argv)

    try:
        gitleaks_json = safe_path(args.gitleaks_json, "gitleaks JSON")
        report_md = safe_path(args.report_md, "report")
        summary_json = safe_path(args.summary_json, "summary JSON") if args.summary_json else ""
    except UnsafePathError as exc:
        print(f"::error title=Gitleaks gate::{annotation(exc)}", file=sys.stderr)
        return 2

    findings, problem = load_report(gitleaks_json)
    findings = sorted(
        findings,
        key=lambda r: (clean_file(r.get("File")), clean_line(r.get("StartLine")),
                       clean_rule(r.get("RuleID")), clean_commit(r.get("Commit"))),
    )
    failed = bool(problem or findings)
    tool = f"Gitleaks {clean_text(args.tool_version, 20)}".strip()

    lines = [f"# {clean_text(args.title, 120)}", ""]
    if problem:
        lines += [f"**Result: FAIL.** {problem} The scan did not complete, so it is not clean.", ""]
    elif findings:
        lines += [
            f"**Result: FAIL.** {tool}: {len(findings)} finding(s). "
            "A release with this result publishes nothing. Values are redacted.",
            "",
        ]
    else:
        lines += [f"**Result: PASS.** {tool}: 0 findings. Values would be redacted if any were found.", ""]
    lines += [
        "Gate: any finding fails. No baseline. Proven false positives go in "
        "`.gitleaks.toml` with a reason, reviewed in the PR.",
        "This summary lists rule, file, line, commit and fingerprint only; "
        "it never includes secret values.",
        "",
    ]

    if findings:
        lines += [
            "## Findings (values redacted)",
            "",
            "| Rule | Location | Commit | Fingerprint |",
            "|---|---|---|---|",
        ]
        for r in findings:
            rule = clean_rule(r.get("RuleID"))
            desc = clean_text(r.get("Description"), 80)
            loc = f"`{clean_file(r.get('File'))}:{clean_line(r.get('StartLine'))}`"
            commit = clean_commit(r.get("Commit"))
            fp = clean_fingerprint(r.get("Fingerprint"))
            label = f"{rule}: {desc}" if desc else rule
            lines.append(f"| {label} | {loc} | `{commit}` | `{fp}` |")
            print(
                f"::error file={annotation(clean_file(r.get('File')))},"
                f"line={clean_line(r.get('StartLine'))},title=Gitleaks {rule}::"
                f"{annotation(desc or 'secret finding (value redacted)')} "
                f"commit={annotation(commit)}",
            )
        lines.append("")

    if failed and not problem:
        target = " ".join(x for x in (clean_text(args.repository, 80) or "this repository",
                                      clean_text(args.release, 40)) if x)
        lines += [
            "## Suggested fix",
            "",
            "- If the finding is a real credential: revoke or rotate it, remove it from the",
            "  repository, and treat any copy that was pushed as compromised.",
            "- Only for a proven false positive: add an `[[allowlists]]` entry in",
            "  `.gitleaks.toml` with a reason in the description, and list it in the PR",
            "  for security review. Never add a baseline of ignored secrets.",
            "",
            "### Fix prompt",
            "",
            "```text",
            f"The Gitleaks check for {target} failed (secret-scan findings, or an incomplete scan).",
            "Read the redacted report (gitleaks.md / gitleaks.json in the workflow run artifacts).",
            "It never includes secret values. Fix each finding, run",
            "`bash scripts/gitleaks_check.sh gitleaks-report` (gitleaks 8.30.1) until it passes,",
            "run the tests, and open a PR. Use a .gitleaks.toml allowlist entry only for a",
            "proven false positive, with a reason. After it merges, release again.",
            "A blocked release publishes nothing.",
            "```",
        ]
    elif problem:
        lines += [
            "## Suggested fix",
            "",
            "- Re-run the scan and fix whatever stopped Gitleaks from writing a valid JSON report.",
            "  An incomplete scan is never treated as clean.",
            "",
        ]

    with open(report_md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))

    if summary_json:
        summary = {
            "schema": 1,
            "tool": "Gitleaks",
            "tool_version": clean_text(args.tool_version, 20),
            "result": "fail" if failed else "pass",
            "complete": not problem,
            "findings": len(findings),
        }
        with open(summary_json, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

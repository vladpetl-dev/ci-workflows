"""Trivy gate: a PR report and a pass/fail decision from Trivy's JSON output.

Severities listed in --fail-on block the merge; everything else is reported. Accepted risks go
in the caller's `.trivyignore` (one ID per line, with a comment saying why), which Trivy applies
before this.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

MARKER = "<!-- trivy-gate -->"
ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]


@dataclass(frozen=True)
class Vulnerability:
    id: str
    package: str
    installed: str
    fixed: str | None
    severity: str
    title: str
    url: str | None
    target: str


def parse(text: str) -> list[Vulnerability]:
    report = json.loads(text)
    out = []
    for result in report.get("Results") or []:
        for v in result.get("Vulnerabilities") or []:
            out.append(Vulnerability(
                v.get("VulnerabilityID", "?"), v.get("PkgName", "?"),
                v.get("InstalledVersion", "?"),
                v.get("FixedVersion") or None, (v.get("Severity") or "UNKNOWN").upper(),
                v.get("Title") or "", v.get("PrimaryURL") or None, result.get("Target", "?"),
            ))
    return out


def _rank(severity: str) -> int:
    return ORDER.index(severity) if severity in ORDER else len(ORDER)


def evaluate(vulns: list[Vulnerability], fail_on: set[str]) -> tuple[bool, list[Vulnerability]]:
    blocking = sorted((v for v in vulns if v.severity in fail_on),
                      key=lambda v: (_rank(v.severity), v.id))
    return not blocking, blocking


def render(vulns: list[Vulnerability], blocking: list[Vulnerability], passed: bool,
           fail_on: set[str]) -> str:
    icon, verdict = ("✅", "PASS") if passed else ("❌", "FAIL")
    blocks = ", ".join(s for s in ORDER if s in fail_on)
    lines = [MARKER, f"## {icon} Trivy: {verdict}", "", f"Blocking severities: {blocks}.", "",
             "| Severity | Count |", "|---|---|"]
    for severity in ORDER:
        count = sum(1 for v in vulns if v.severity == severity)
        if count:
            lines.append(f"| {severity} | {count} |")
    if not vulns:
        lines.append("| — | 0 |")
    lines.append("")
    if blocking:
        lines += ["| ID | Severity | Package | Fixed in | Where |", "|---|---|---|---|---|"]
        for v in blocking[:50]:
            ident = f"[{v.id}]({v.url})" if v.url else v.id
            fixed = v.fixed or "no fix yet"
            package = f"`{v.package}` {v.installed}"
            lines.append(f"| {ident} | {v.severity} | {package} | {fixed} | `{v.target}` |")
        if len(blocking) > 50:
            lines.append(f"| … | | {len(blocking) - 50} more | | |")
        lines += ["", "Upgrade the package, or accept the risk in `.trivyignore` with a comment "
                  "saying why (reviewed like any other change).", ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trivy gate")
    parser.add_argument("--json", required=True, action="append",
                        help="Trivy JSON report; repeat to combine several scans")
    parser.add_argument("--fail-on", default="HIGH,CRITICAL", help="comma-separated severities")
    parser.add_argument("--out", default="trivy-report.md")
    args = parser.parse_args(argv)

    fail_on = {s.strip().upper() for s in args.fail_on.split(",") if s.strip()}
    missing = [p for p in args.json if not Path(p).exists()]
    if missing:
        Path(args.out).write_text(f"{MARKER}\n## ❌ Trivy: report missing (`{', '.join(missing)}`)\n")
        print(f"trivy report missing: {', '.join(missing)}")
        return 1
    vulns = [v for p in args.json for v in parse(Path(p).read_text())]
    passed, blocking = evaluate(vulns, fail_on)
    Path(args.out).write_text(render(vulns, blocking, passed, fail_on))
    print(("PASS" if passed else "FAIL") + f": {len(blocking)} blocking of {len(vulns)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

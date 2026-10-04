"""Coverage gate: total and changed-line coverage from a JaCoCo or Cobertura XML report.

Changed lines come from `git diff -U0 base...head`; a changed line counts only when the
coverage report knows it as executable (comments, blank lines and declarations are skipped).
"""

import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

MARKER = "<!-- coverage-gate -->"


@dataclass
class Coverage:
    total_lines: tuple[int, int] = (0, 0)  # (covered, coverable)
    total_branches: tuple[int, int] | None = None
    # path suffix (e.g. "com/acme/Foo.kt" or "app/db.py") -> {line: covered?}
    files: dict[str, dict[int, bool]] = field(default_factory=dict)


def _pct(covered: int, total: int) -> float | None:
    return None if total == 0 else covered * 100.0 / total


def parse_jacoco(root: ET.Element) -> Coverage:
    cov = Coverage()
    for c in root.findall("counter"):
        missed, covered = int(c.get("missed")), int(c.get("covered"))
        if c.get("type") == "LINE":
            cov.total_lines = (covered, covered + missed)
        elif c.get("type") == "BRANCH":
            cov.total_branches = (covered, covered + missed)
    for pkg in root.findall("package"):
        for sf in pkg.findall("sourcefile"):
            path = f"{pkg.get('name')}/{sf.get('name')}".lstrip("/")
            cov.files[path] = {
                int(ln.get("nr")): int(ln.get("ci")) > 0 for ln in sf.findall("line")
            }
    return cov


def parse_cobertura(root: ET.Element) -> Coverage:
    cov = Coverage()
    covered = int(root.get("lines-covered", 0))
    valid = int(root.get("lines-valid", 0))
    cov.total_lines = (covered, valid)
    if root.get("branches-valid") not in (None, "0"):
        cov.total_branches = (int(root.get("branches-covered")), int(root.get("branches-valid")))
    for cls in root.iter("class"):
        lines = cov.files.setdefault(cls.get("filename"), {})
        for ln in cls.iter("line"):
            nr = int(ln.get("number"))
            lines[nr] = lines.get(nr, False) or int(ln.get("hits", 0)) > 0
    return cov


def parse(xml_text: str) -> Coverage:
    root = ET.fromstring(xml_text)
    if root.tag == "report":
        return parse_jacoco(root)
    if root.tag == "coverage":
        return parse_cobertura(root)
    raise ValueError(f"unknown coverage format: <{root.tag}>")


def changed_lines(diff: str) -> dict[str, set[int]]:
    """Added or modified lines per file in the new version, from a -U0 unified diff."""
    out: dict[str, set[int]] = {}
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = None if target == "/dev/null" else re.sub(r"^b/", "", target)
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m and current:
            start, count = int(m.group(1)), int(m.group(2) or "1")
            out.setdefault(current, set()).update(range(start, start + count))
    return out


def _match(path: str, files: dict[str, dict[int, bool]]) -> dict[int, bool] | None:
    """Coverage entry whose path is a suffix of the repo path (src/main/kotlin/<pkg>/Foo.kt)."""
    best = None
    for key, lines in files.items():
        if path == key or path.endswith("/" + key):
            if best is None or len(key) > len(best[0]):
                best = (key, lines)
    return best[1] if best else None


@dataclass
class DiffResult:
    covered: int
    coverable: int
    uncovered: dict[str, list[int]]


def diff_coverage(cov: Coverage, changed: dict[str, set[int]]) -> DiffResult:
    covered = coverable = 0
    uncovered: dict[str, list[int]] = {}
    for path, lines in sorted(changed.items()):
        known = _match(path, cov.files)
        if known is None:
            continue  # not measured: tests, docs, config, other languages
        for nr in sorted(lines):
            if nr in known:
                coverable += 1
                if known[nr]:
                    covered += 1
                else:
                    uncovered.setdefault(path, []).append(nr)
    return DiffResult(covered, coverable, uncovered)


def _ranges(nums: list[int]) -> str:
    parts, start, prev = [], None, None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            parts.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    if start is not None:
        parts.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(parts)


def _fmt(p: float | None) -> str:
    return "n/a" if p is None else f"{p:.1f}%"


def evaluate(cov: Coverage, diff: DiffResult | None, enabled: bool,
             min_diff: float, min_total: float) -> tuple[bool, list[str]]:
    reasons = []
    total = _pct(*cov.total_lines)
    if min_total > 0 and total is not None and total < min_total:
        reasons.append(f"total line coverage {_fmt(total)} < {min_total:g}%")
    if diff is not None and min_diff > 0:
        d = _pct(diff.covered, diff.coverable)
        if d is not None and d < min_diff:
            reasons.append(f"changed-line coverage {_fmt(d)} < {min_diff:g}%")
    if not enabled:
        return True, reasons
    return not reasons, reasons


def render(cov: Coverage, diff: DiffResult | None, passed: bool, reasons: list[str],
           enabled: bool, min_diff: float, min_total: float) -> str:
    icon = "✅" if passed else "❌"
    verdict = "PASS" if passed else "FAIL"
    if not enabled:
        verdict += " (gate off, report only)"
    lines = [MARKER, f"## {icon} Coverage: {verdict}", ""]
    lines += ["| Metric | Value | Required |", "|---|---|---|"]
    if diff is not None:
        lines.append(f"| Changed lines | {_fmt(_pct(diff.covered, diff.coverable))} "
                     f"({diff.covered}/{diff.coverable}) | "
                     f"{'≥ ' + format(min_diff, 'g') + '%' if min_diff > 0 else 'off'} |")
    lines.append(f"| Total lines | {_fmt(_pct(*cov.total_lines))} | "
                 f"{'≥ ' + format(min_total, 'g') + '%' if min_total > 0 else 'off'} |")
    if cov.total_branches:
        lines.append(f"| Total branches | {_fmt(_pct(*cov.total_branches))} | — |")
    lines.append("")
    if reasons:
        lines += ["**Below threshold:** " + "; ".join(reasons), ""]
    if diff is not None and diff.uncovered:
        lines += ["<details><summary>Uncovered changed lines</summary>", "",
                  "| File | Lines |", "|---|---|"]
        for path, nums in diff.uncovered.items():
            lines.append(f"| `{path}` | {_ranges(nums)} |")
        lines += ["", "</details>", ""]
    elif diff is not None and diff.coverable == 0:
        lines += ["No measured code lines changed.", ""]
    return "\n".join(lines) + "\n"


def _git_diff(base: str, head: str, repo: str) -> str:
    return subprocess.run(["git", "diff", "--no-color", "-U0", f"{base}...{head}"],
                          cwd=repo, check=True, capture_output=True, text=True).stdout


def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coverage gate")
    parser.add_argument("--xml", required=True, help="JaCoCo or Cobertura XML report")
    parser.add_argument("--base", help="base ref; omit to skip changed-line coverage")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--enabled", default="true", help="false = report only, never fail")
    parser.add_argument("--min-diff", type=float, default=90.0)
    parser.add_argument("--min-total", type=float, default=0.0)
    parser.add_argument("--out", default="coverage-report.md")
    args = parser.parse_args(argv)

    enabled = _bool(args.enabled)
    xml_path = Path(args.xml)
    if not xml_path.exists():
        msg = f"{MARKER}\n## {'❌' if enabled else '⚠️'} Coverage: report missing (`{args.xml}`)\n"
        Path(args.out).write_text(msg)
        print(f"coverage report missing: {args.xml}")
        return 1 if enabled else 0

    cov = parse(xml_path.read_text())
    diff = None
    if args.base:
        diff = diff_coverage(cov, changed_lines(_git_diff(args.base, args.head, args.repo)))
    passed, reasons = evaluate(cov, diff, enabled, args.min_diff, args.min_total)
    md = render(cov, diff, passed, reasons, enabled, args.min_diff, args.min_total)
    Path(args.out).write_text(md)
    print(("PASS" if passed else "FAIL") + (": " + "; ".join(reasons) if reasons else ""))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

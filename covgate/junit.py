"""Test totals from JUnit XML reports (Gradle, Maven Surefire, pytest --junitxml)."""

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestTotals:
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)


def collect(paths: list[Path]) -> TestTotals:
    t = TestTotals()
    for p in paths:
        root = ET.parse(p).getroot()
        suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
        for s in suites:
            t.tests += int(s.get("tests", 0))
            t.failures += int(s.get("failures", 0))
            t.errors += int(s.get("errors", 0))
            t.skipped += int(s.get("skipped", 0))
            for case in s.iter("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    t.failed.append(f"{case.get('classname', '')} > {case.get('name', '')}")
    return t


def render(t: TestTotals, limit: int = 20) -> str:
    bad = t.failures + t.errors
    icon = "✅" if bad == 0 and t.tests > 0 else "❌"
    passed = t.tests - bad - t.skipped
    lines = [f"### {icon} Tests: {passed} passed, {bad} failed, {t.skipped} skipped "
             f"({t.tests} total)", ""]
    if t.tests == 0:
        lines += ["No test results found.", ""]
    for name in t.failed[:limit]:
        lines.append(f"- `{name}`")
    if len(t.failed) > limit:
        lines.append(f"- … and {len(t.failed) - limit} more")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarise JUnit XML test results")
    parser.add_argument("--dir", required=True, help="directory searched for TEST-*.xml / *.xml")
    parser.add_argument("--out", default="tests-report.md")
    args = parser.parse_args(argv)
    paths = sorted(Path(args.dir).rglob("*.xml")) if Path(args.dir).exists() else []
    Path(args.out).write_text(render(collect(paths)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Markdown report for the PR comment and the workflow artifact."""

import argparse
import sys
from pathlib import Path

from review.config import load_policy
from review.gate import evaluate, load_result

MARKER = "<!-- ai-review-gate -->"
ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render(result: dict, passed: bool, verdict: str) -> str:
    icon = "✅" if passed else "❌"
    lines = [MARKER, f"## {icon} AI review: {verdict}", ""]
    if result.get("error"):
        lines += [f"**Review error:** {result['error']}", ""]
    if result.get("summary"):
        lines += [result["summary"], ""]

    findings = sorted(result["findings"], key=lambda x: ORDER.index(x["severity"].upper()))
    if not findings:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"

    lines += ["| Severity | Category | Location | Finding | Recommendation |",
              "|---|---|---|---|---|"]
    for item in findings:
        location = item["file"] + (f":{item['line']}" if item.get("line") else "")
        finding = f"**{_cell(item['title'])}**<br>{_cell(item['description'])}"
        lines.append(f"| {item['severity']} | {item['category']} | `{location}` | "
                     f"{finding} | {_cell(item['recommendation'])} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the AI review report")
    parser.add_argument("findings")
    parser.add_argument("--policy", default="review/policy.yml")
    parser.add_argument("--out", default="review-output/report.md")
    args = parser.parse_args(argv)

    result = load_result(args.findings)
    passed, verdict = evaluate(result, load_policy(args.policy))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(result, passed, verdict))
    print(f"report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

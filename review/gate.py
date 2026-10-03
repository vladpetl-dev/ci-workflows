"""PASS/FAIL decision from review findings and policy. No network access."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from review.config import load_policy


def load_result(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"summary": "", "findings": [], "error": f"findings file missing: {path}"}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return {"summary": "", "findings": [], "error": f"findings file malformed: {exc}"}
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        return {"summary": "", "findings": [], "error": "findings file malformed: no findings list"}
    data.setdefault("summary", "")
    data.setdefault("error", None)
    return data


def evaluate(result: dict, policy: dict) -> tuple[bool, str]:
    error = result.get("error")
    if error:
        if policy["fail_open_on_error"]:
            return True, f"PASS (fail-open): review could not run: {error}"
        return False, f"FAIL: review could not run: {error}"

    counts = Counter(f["severity"].upper() for f in result["findings"])
    blocking = {s: counts[s] for s in policy["fail_on"] if counts[s]}
    if blocking:
        detail = ", ".join(f"{n} {s}" for s, n in blocking.items())
        return False, f"FAIL: blocking findings: {detail}"
    total = sum(counts.values())
    return True, f"PASS: {total} non-blocking finding(s)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI review gate")
    parser.add_argument("findings")
    parser.add_argument("--policy", default="review/policy.yml")
    args = parser.parse_args(argv)

    passed, verdict = evaluate(load_result(args.findings), load_policy(args.policy))
    print(verdict)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

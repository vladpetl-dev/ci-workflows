"""Loads the review policy with defaults so a partial policy file still works."""

from pathlib import Path

import yaml

from review.schema import SEVERITIES

DEFAULTS = {
    "fail_on": ["CRITICAL", "HIGH"],
    "fail_open_on_error": False,
    "max_diff_chars": 150_000,
    "model": "claude-haiku-4-5",
    "effort": None,
    "fallbacks": None,
    "excluded_patterns": [],
    # Findings below this severity are dropped from the report and the gate.
    "min_severity": "INFO",
}


def load_policy(path: str | Path) -> dict:
    loaded = yaml.safe_load(Path(path).read_text()) or {}
    policy = {**DEFAULTS, **loaded}
    fail_on = policy["fail_on"]
    if isinstance(fail_on, str):
        fail_on = [fail_on]
    policy["fail_on"] = [str(s).upper() for s in fail_on]
    unknown = [s for s in policy["fail_on"] if s not in SEVERITIES]
    if unknown:
        raise ValueError(f"unknown severities in fail_on: {unknown}; allowed: {SEVERITIES}")
    policy["min_severity"] = str(policy["min_severity"]).upper()
    if policy["min_severity"] not in SEVERITIES:
        raise ValueError(f"unknown min_severity: {policy['min_severity']}; allowed: {SEVERITIES}")
    policy["fail_open_on_error"] = bool(policy["fail_open_on_error"])
    policy["max_diff_chars"] = int(policy["max_diff_chars"])
    return policy

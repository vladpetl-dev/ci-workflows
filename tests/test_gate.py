import json

import pytest

from review.config import load_policy
from review.gate import evaluate, load_result, main

POLICY = {"fail_on": ["CRITICAL", "HIGH"], "fail_open_on_error": False}


def finding(severity):
    return {"severity": severity, "category": "security", "file": "a.py", "line": 1,
            "title": "t", "description": "d", "recommendation": "r"}


def result(*severities, error=None):
    return {"summary": "s", "findings": [finding(s) for s in severities], "error": error}


def test_no_findings_passes():
    passed, verdict = evaluate(result(), POLICY)
    assert passed and verdict.startswith("PASS")


@pytest.mark.parametrize("severity", ["CRITICAL", "HIGH"])
def test_blocking_severity_fails(severity):
    passed, verdict = evaluate(result("LOW", severity), POLICY)
    assert not passed
    assert severity in verdict


@pytest.mark.parametrize("severity", ["MEDIUM", "LOW", "INFO"])
def test_non_blocking_severity_passes(severity):
    passed, _ = evaluate(result(severity), POLICY)
    assert passed


def test_error_fails_closed_by_default():
    passed, verdict = evaluate(result(error="API timeout"), POLICY)
    assert not passed
    assert "API timeout" in verdict


def test_error_fail_open_passes():
    passed, _ = evaluate(result(error="API timeout"), {**POLICY, "fail_open_on_error": True})
    assert passed


def test_missing_file_fails(tmp_path):
    res = load_result(tmp_path / "nope.json")
    passed, _ = evaluate(res, POLICY)
    assert not passed
    assert "missing" in res["error"]


def test_malformed_json_fails(tmp_path):
    path = tmp_path / "findings.json"
    path.write_text("{not json")
    res = load_result(path)
    passed, _ = evaluate(res, POLICY)
    assert not passed
    assert "malformed" in res["error"]


def test_policy_severity_case_insensitive(tmp_path):
    path = tmp_path / "policy.yml"
    path.write_text("fail_on: [high]\n")
    policy = load_policy(path)
    assert policy["fail_on"] == ["HIGH"]
    passed, _ = evaluate(result("HIGH"), policy)
    assert not passed


def test_policy_defaults(tmp_path):
    path = tmp_path / "policy.yml"
    path.write_text("{}\n")
    policy = load_policy(path)
    assert policy["fail_on"] == ["CRITICAL", "HIGH"]
    assert policy["fail_open_on_error"] is False
    assert policy["model"] == "claude-haiku-4-5"
    assert policy["effort"] is None and policy["fallbacks"] is None


def test_cli_exit_codes(tmp_path, capsys):
    findings = tmp_path / "findings.json"
    policy = tmp_path / "policy.yml"
    policy.write_text("fail_on: [HIGH]\n")
    findings.write_text(json.dumps(result("HIGH")))
    assert main([str(findings), "--policy", str(policy)]) == 1
    findings.write_text(json.dumps(result("LOW")))
    assert main([str(findings), "--policy", str(policy)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_policy_scalar_fail_on_is_one_severity(tmp_path):
    path = tmp_path / "policy.yml"
    path.write_text("fail_on: HIGH\n")
    policy = load_policy(path)
    assert policy["fail_on"] == ["HIGH"]
    passed, _ = evaluate(result("HIGH"), policy)
    assert not passed


def test_policy_unknown_severity_raises(tmp_path):
    path = tmp_path / "policy.yml"
    path.write_text("fail_on: [HIHG]\n")
    with pytest.raises(ValueError, match="HIHG"):
        load_policy(path)

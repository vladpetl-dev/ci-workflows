import json

from secgate.trivy import MARKER, Vulnerability, evaluate, main, parse, render

REPORT = {
    "Results": [
        {
            "Target": "frontend/package-lock.json",
            "Vulnerabilities": [
                {"VulnerabilityID": "CVE-1", "PkgName": "lodash", "InstalledVersion": "4.17.10",
                 "FixedVersion": "4.17.21", "Severity": "HIGH", "Title": "Prototype pollution",
                 "PrimaryURL": "https://avd.aquasec.com/nvd/cve-1"},
                {"VulnerabilityID": "CVE-2", "PkgName": "minimist", "InstalledVersion": "1.2.0",
                 "FixedVersion": "", "Severity": "MEDIUM", "Title": "Something"},
            ],
        },
        {"Target": "backend/build/libs/app.jar", "Vulnerabilities": [
            {"VulnerabilityID": "CVE-3", "PkgName": "org.yaml:snakeyaml",
             "InstalledVersion": "1.33", "Severity": "CRITICAL", "Title": "RCE"}]},
        {"Target": "clean.jar"},
    ]
}


def test_parse_flattens_results_with_targets():
    vulns = parse(json.dumps(REPORT))
    assert [v.id for v in vulns] == ["CVE-1", "CVE-2", "CVE-3"]
    assert vulns[0] == Vulnerability("CVE-1", "lodash", "4.17.10", "4.17.21", "HIGH",
                                     "Prototype pollution", "https://avd.aquasec.com/nvd/cve-1",
                                     "frontend/package-lock.json")
    assert vulns[2].fixed is None


def test_only_listed_severities_block():
    vulns = parse(json.dumps(REPORT))
    passed, blocking = evaluate(vulns, {"HIGH", "CRITICAL"})
    assert passed is False
    assert [v.id for v in blocking] == ["CVE-3", "CVE-1"]  # most severe first
    assert evaluate([v for v in vulns if v.severity == "MEDIUM"], {"HIGH", "CRITICAL"})[0]


def test_render_counts_every_severity_and_lists_blocking_ones():
    vulns = parse(json.dumps(REPORT))
    passed, blocking = evaluate(vulns, {"HIGH", "CRITICAL"})
    md = render(vulns, blocking, passed, {"HIGH", "CRITICAL"})
    assert md.startswith(MARKER)
    assert "❌ Trivy: FAIL" in md
    assert "| CRITICAL | 1 |" in md and "| MEDIUM | 1 |" in md
    assert "`org.yaml:snakeyaml` 1.33" in md
    assert "no fix yet" in md
    assert ".trivyignore" in md


def test_clean_report_passes(tmp_path):
    report = tmp_path / "t.json"
    report.write_text(json.dumps({"Results": [{"Target": "x"}]}))
    out = tmp_path / "r.md"
    assert main(["--json", str(report), "--fail-on", "HIGH,CRITICAL", "--out", str(out)]) == 0
    assert "✅ Trivy: PASS" in out.read_text()


def test_blocking_report_fails_and_missing_report_fails(tmp_path):
    report = tmp_path / "t.json"
    report.write_text(json.dumps(REPORT))
    out = tmp_path / "r.md"
    assert main(["--json", str(report), "--fail-on", "HIGH,CRITICAL", "--out", str(out)]) == 1
    assert main(["--json", str(tmp_path / "none.json"), "--out", str(out)]) == 1
    assert "report missing" in out.read_text()


def test_several_reports_are_combined(tmp_path):
    lockfiles = tmp_path / "fs.json"
    low = {"VulnerabilityID": "CVE-9", "PkgName": "a", "InstalledVersion": "1", "Severity": "LOW"}
    lockfiles.write_text(json.dumps(
        {"Results": [{"Target": "package-lock.json", "Vulnerabilities": [low]}]}))
    jars = tmp_path / "jars.json"
    jars.write_text(json.dumps(REPORT))
    out = tmp_path / "r.md"
    assert main(["--json", str(lockfiles), "--json", str(jars), "--out", str(out)]) == 1
    assert "| LOW | 1 |" in out.read_text()
    assert "| CRITICAL | 1 |" in out.read_text()

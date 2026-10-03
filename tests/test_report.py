from review.report import MARKER, render


def f(severity, title, line=3):
    return {"severity": severity, "category": "security", "file": "app/db.py", "line": line,
            "title": title, "description": "desc", "recommendation": "fix it"}


def test_report_has_marker_and_verdict():
    md = render({"summary": "ok", "findings": [], "error": None}, True, "PASS: 0 non-blocking")
    assert md.startswith(MARKER)
    assert "PASS: 0 non-blocking" in md
    assert "No findings" in md


def test_findings_sorted_by_severity():
    res = {"summary": "s", "findings": [f("LOW", "minor"), f("CRITICAL", "sqli")], "error": None}
    md = render(res, False, "FAIL")
    assert md.index("sqli") < md.index("minor")
    assert "`app/db.py:3`" in md


def test_line_zero_shows_file_only():
    res = {"summary": "s", "findings": [f("INFO", "note", line=0)], "error": None}
    assert "`app/db.py`" in render(res, True, "PASS")


def test_error_is_shown():
    md = render({"summary": "", "findings": [], "error": "API timeout"}, False, "FAIL")
    assert "API timeout" in md


def test_pipe_in_text_does_not_break_table():
    res = {"summary": "s", "findings": [f("HIGH", "a | b")], "error": None}
    assert "a \\| b" in render(res, False, "FAIL")

from covgate.junit import collect, main, render

SUITE = """<?xml version="1.0"?><testsuite name="A" tests="3" failures="1" errors="0" skipped="1">
<testcase classname="com.acme.FooTest" name="adds"/>
<testcase classname="com.acme.FooTest" name="breaks"><failure message="x"/></testcase>
<testcase classname="com.acme.FooTest" name="later"><skipped/></testcase></testsuite>"""


def test_collects_totals_and_failed_names(tmp_path):
    (tmp_path / "TEST-a.xml").write_text(SUITE)
    t = collect([tmp_path / "TEST-a.xml"])
    assert (t.tests, t.failures, t.skipped) == (3, 1, 1)
    md = render(t)
    assert "❌ Tests: 1 passed, 1 failed, 1 skipped (3 total)" in md
    assert "`com.acme.FooTest > breaks`" in md


def test_missing_dir_reports_no_results(tmp_path):
    out = tmp_path / "o.md"
    assert main(["--dir", str(tmp_path / "nope"), "--out", str(out)]) == 0
    assert "No test results found" in out.read_text()

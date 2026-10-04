import subprocess

from covgate.report import (
    MARKER,
    changed_lines,
    diff_coverage,
    evaluate,
    main,
    parse,
    render,
)

JACOCO = """<?xml version="1.0"?><report name="x">
<package name="com/acme"><sourcefile name="Foo.kt">
<line nr="3" mi="0" ci="2" mb="0" cb="0"/><line nr="4" mi="1" ci="0" mb="0" cb="0"/>
<line nr="5" mi="0" ci="1" mb="0" cb="0"/><line nr="9" mi="2" ci="0" mb="0" cb="0"/>
</sourcefile></package>
<counter type="LINE" missed="2" covered="2"/><counter type="BRANCH" missed="1" covered="3"/>
</report>"""

COBERTURA = """<?xml version="1.0"?><coverage lines-covered="3" lines-valid="4" branches-covered="0"
 branches-valid="0"><packages><package><classes><class filename="app/db.py">
<lines><line number="1" hits="1"/><line number="2" hits="0"/><line number="3" hits="4"/>
<line number="7" hits="1"/></lines></class></classes></package></packages></coverage>"""

DIFF = """diff --git a/src/main/kotlin/com/acme/Foo.kt b/src/main/kotlin/com/acme/Foo.kt
--- a/src/main/kotlin/com/acme/Foo.kt
+++ b/src/main/kotlin/com/acme/Foo.kt
@@ -2,0 +3,3 @@ class Foo
+a
+b
+c
@@ -8 +9 @@
-x
+y
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+doc
diff --git a/old.kt b/old.kt
--- a/old.kt
+++ /dev/null
@@ -1 +0,0 @@
-gone
"""


def test_changed_lines_from_unified_diff():
    ch = changed_lines(DIFF)
    assert ch["src/main/kotlin/com/acme/Foo.kt"] == {3, 4, 5, 9}
    assert ch["README.md"] == {1, 2}
    assert "old.kt" not in ch


def test_jacoco_diff_coverage_matches_package_suffix():
    cov = parse(JACOCO)
    assert cov.total_lines == (2, 4) and cov.total_branches == (3, 4)
    d = diff_coverage(cov, changed_lines(DIFF))
    assert (d.covered, d.coverable) == (2, 4)
    assert d.uncovered == {"src/main/kotlin/com/acme/Foo.kt": [4, 9]}


def test_cobertura_is_supported():
    cov = parse(COBERTURA)
    d = diff_coverage(cov, {"app/db.py": {1, 2, 5}})
    assert (d.covered, d.coverable) == (1, 2)


def test_gate_thresholds_and_switch():
    cov = parse(JACOCO)
    d = diff_coverage(cov, changed_lines(DIFF))  # 50%
    assert evaluate(cov, d, True, 90, 0)[0] is False
    assert evaluate(cov, d, True, 50, 0)[0] is True
    passed, reasons = evaluate(cov, d, False, 90, 0)
    assert passed is True and reasons  # gate off: report the shortfall, never fail
    assert evaluate(cov, d, True, 0, 60)[0] is False  # total 50% < 60%
    assert evaluate(cov, None, True, 90, 0)[0] is True  # no diff (push to main)


def test_no_measured_changes_passes():
    cov = parse(JACOCO)
    d = diff_coverage(cov, {"README.md": {1}})
    assert d.coverable == 0
    assert evaluate(cov, d, True, 90, 0)[0] is True
    assert "No measured code lines changed" in render(cov, d, True, [], True, 90, 0)


def test_render_lists_uncovered_ranges():
    cov = parse(JACOCO)
    d = diff_coverage(cov, {"src/main/kotlin/com/acme/Foo.kt": {3, 4, 5, 9}})
    md = render(cov, d, False, ["x"], True, 90, 0)
    assert md.startswith(MARKER)
    assert "❌ Coverage: FAIL" in md
    assert "| `src/main/kotlin/com/acme/Foo.kt` | 4, 9 |" in md
    off = render(cov, d, True, ["x"], False, 90, 0)
    assert "gate off, report only" in off


def test_main_end_to_end_with_git(tmp_path):
    repo = tmp_path / "r"
    (repo / "src/main/kotlin/com/acme").mkdir(parents=True)

    def git(*a):
        subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    f = repo / "src/main/kotlin/com/acme/Foo.kt"
    f.write_text("1\n2\n")
    git("add", ".")
    git("commit", "-qm", "base")
    git("checkout", "-qb", "pr")
    f.write_text("1\n2\n3\n4\n5\n")
    git("commit", "-qam", "pr")
    xml = tmp_path / "j.xml"
    xml.write_text(JACOCO)
    out = tmp_path / "r.md"

    rc = main(["--xml", str(xml), "--base", "main", "--repo", str(repo), "--out", str(out)])
    assert rc == 1  # lines 3,4,5 changed; 4 uncovered -> 66.7% < 90%
    assert "66.7%" in out.read_text()
    assert main(["--xml", str(xml), "--base", "main", "--repo", str(repo), "--out", str(out),
                 "--enabled", "false"]) == 0
    assert main(["--xml", str(tmp_path / "missing.xml"), "--out", str(out)]) == 1
    missing = str(tmp_path / "missing.xml")
    assert main(["--xml", missing, "--out", str(out), "--enabled", "off"]) == 0

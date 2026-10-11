import subprocess

from sizegate.size import MARKER, count, counted_line, main, render

DIFF = """diff --git a/src/Foo.kt b/src/Foo.kt
--- a/src/Foo.kt
+++ b/src/Foo.kt
@@ -1,0 +1,6 @@
+package foo
+
+/** KDoc line
+ * more doc
+ */
+fun a() = 1 // trailing comment still code
diff --git a/src/Old.kt b/src/Old.kt
deleted file mode 100644
--- a/src/Old.kt
+++ /dev/null
@@ -1,3 +0,0 @@
-class Old
-fun x() = 1
-fun y() = 2
diff --git a/deploy.yml b/deploy.yml
--- a/deploy.yml
+++ b/deploy.yml
@@ -1,0 +1,2 @@
+# a comment
+key: value
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,0 +1,2 @@
+# Title
+Text
"""


def test_only_added_code_lines_count():
    result = count(DIFF, ["*.md", "docs/*"])
    assert result.counted == 3  # package foo, fun a(), key: value
    assert result.per_file == {"src/Foo.kt": 2, "deploy.yml": 1}
    assert result.skipped_comments == 4  # 3 KDoc lines + yaml comment
    assert result.skipped_excluded == 2


def test_comment_styles_follow_the_file_type():
    assert not counted_line("// note", "A.java")
    assert not counted_line("  * doc", "A.kt")
    assert not counted_line("-- note", "V1__init.sql")
    assert not counted_line("<!-- note -->", "pom.xml")
    assert not counted_line("# note", "script.py")
    assert counted_line("# not a comment in kotlin", "A.kt")
    assert counted_line("val x = 1", "A.kt")
    assert not counted_line("   ", "A.kt")


def test_render_shows_verdict_and_biggest_files():
    result = count(DIFF, ["*.md"])
    md = render(result, 2, enabled=True)
    assert md.startswith(MARKER)
    assert "❌ PR size: FAIL" in md
    assert "| `src/Foo.kt` | 2 |" in md
    off = render(result, 2, enabled=False)
    assert "gate off, report only" in off


def _repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()

    def git(*a):
        subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (repo / "Big.kt").write_text("\n".join(f"val v{i} = {i}" for i in range(10)) + "\n")
    git("add", ".")
    git("commit", "-qm", "base")
    git("checkout", "-qb", "pr")
    return repo, git


def test_main_counts_against_the_base_and_ignores_deletions_and_renames(tmp_path):
    repo, git = _repo(tmp_path)
    git("mv", "Big.kt", "Renamed.kt")
    (repo / "New.kt").write_text("val a = 1\nval b = 2\n// comment\n")
    git("add", ".")
    git("commit", "-qm", "pr")
    out = tmp_path / "r.md"

    assert main(["--base", "main", "--repo", str(repo), "--max", "1", "--out", str(out)]) == 1
    assert "2 lines" in out.read_text()
    assert main(["--base", "main", "--repo", str(repo), "--max", "2", "--out", str(out)]) == 0
    assert main(["--base", "main", "--repo", str(repo), "--max", "1", "--enabled", "false",
                 "--out", str(out)]) == 0


def test_deleting_a_whole_class_costs_nothing(tmp_path):
    repo, git = _repo(tmp_path)
    git("rm", "-q", "Big.kt")
    git("commit", "-qm", "drop")
    out = tmp_path / "r.md"

    assert main(["--base", "main", "--repo", str(repo), "--max", "0", "--out", str(out)]) == 0
    assert "0 lines" in out.read_text()


def test_added_lines_that_look_like_file_headers_stay_in_their_file():
    diff = """diff --git a/src/A.kt b/src/A.kt
--- a/src/A.kt
+++ b/src/A.kt
@@ -0,0 +1,3 @@
+val a = 1
+++ README.md
+val b = 2
"""
    result = count(diff, ["*.md"])
    assert result.per_file == {"src/A.kt": 3}
    assert result.counted == 3

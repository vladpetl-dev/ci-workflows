import subprocess

from scripts.next_version import latest_tag, main, next_version, release_notes


def test_latest_tag_picks_highest_semver():
    assert latest_tag(["v0.1.0", "v0.10.0", "v0.2.0", "junk"]) == "v0.10.0"


def test_latest_tag_none():
    assert latest_tag([]) is None


def test_first_release():
    assert next_version(None, ["chore: init"]) == "v0.1.0"


def test_patch_bump():
    assert next_version("v0.1.0", ["fix: typo"]) == "v0.1.1"


def test_minor_bump_on_feat():
    assert next_version("v0.1.3", ["fix: a", "feat: b"]) == "v0.2.0"


def test_release_notes_lists_subjects():
    assert release_notes(["feat: a", "fix: b"]) == "- feat: a\n- fix: b\n"


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_already_released(tmp_path, capsys, monkeypatch):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-q", "--allow-empty", "-m", "feat: x")
    git(tmp_path, "tag", "v0.1.0")
    monkeypatch.chdir(tmp_path)
    assert main(["--notes-out", str(tmp_path / "n.md")]) == 0
    assert capsys.readouterr().out.strip() == ""

"""Next release tag and release notes from git history."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def latest_tag(tags: list[str]) -> str | None:
    versions = [tuple(map(int, m.groups())) for t in tags if (m := TAG.match(t))]
    if not versions:
        return None
    return "v{}.{}.{}".format(*max(versions))


def next_version(latest: str | None, subjects: list[str]) -> str:
    if latest is None:
        return "v0.1.0"
    major, minor, patch = map(int, TAG.match(latest).groups())
    if any(s.startswith("feat:") or s.startswith("feat(") for s in subjects):
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def release_notes(subjects: list[str]) -> str:
    return "".join(f"- {s}\n" for s in subjects)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute the next release version")
    parser.add_argument("--notes-out", required=True)
    args = parser.parse_args(argv)

    if _git("tag", "--points-at", "HEAD").split():
        return 0  # HEAD already released; print nothing

    latest = latest_tag(_git("tag", "--list", "v*").split())
    rev_range = f"{latest}..HEAD" if latest else "HEAD"
    subjects = [s for s in _git("log", "--format=%s", rev_range).splitlines() if s]
    Path(args.notes_out).write_text(release_notes(subjects))
    print(next_version(latest, subjects))
    return 0


if __name__ == "__main__":
    sys.exit(main())

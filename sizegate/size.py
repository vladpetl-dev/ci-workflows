"""PR size gate: added lines of code in a pull request, against a limit.

Only lines the PR adds count. Deleted lines and deleted files never count, so removing a whole class
is free; renames without changes are free (git detects them). Blank lines and comment-only lines
(by file type) do not count, so a change that only edits comments costs nothing. Excluded paths
(docs, lock files, generated wrappers) do not count either.
"""

import argparse
import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

MARKER = "<!-- pr-size-gate -->"

DEFAULT_EXCLUDE = [
    "*.md", "docs/*", "*.lock", "*lock.json", "*.lockfile", "gradlew", "gradlew.bat",
    "gradle/wrapper/*", "*.svg", "*.png", "*.jpg", "*.gif", "*.pdf",
]

_C = ("//", "/*", "*", "*/")
_HASH = ("#",)
COMMENTS = {
    **dict.fromkeys(["kt", "kts", "java", "groovy", "gradle", "scala", "js", "jsx", "ts", "tsx",
                     "mjs", "cjs", "go", "c", "h", "cpp", "cs", "swift", "rs", "css", "scss"], _C),
    **dict.fromkeys(["py", "sh", "bash", "yml", "yaml", "toml", "properties", "rb", "tf", "r",
                     "conf", "cfg", "ini", "dockerfile", "makefile"], _HASH),
    "sql": ("--", "/*", "*", "*/"),
    **dict.fromkeys(["xml", "html", "htm", "vue", "svelte"], ("<!--", "-->")),
}


def _style(path: str) -> tuple[str, ...]:
    name = path.rsplit("/", 1)[-1].lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else name
    return COMMENTS.get(ext, ())


def counted_line(text: str, path: str) -> bool:
    """A line that is neither blank nor a comment in the file's language."""
    stripped = text.strip()
    return bool(stripped) and not stripped.startswith(_style(path) or ("\0",))


@dataclass
class SizeResult:
    counted: int = 0
    skipped_comments: int = 0
    skipped_excluded: int = 0
    per_file: dict[str, int] = field(default_factory=dict)


def _excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path.rsplit("/", 1)[-1], p)
               for p in patterns)


def count(diff: str, exclude: list[str]) -> SizeResult:
    result = SizeResult()
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = None if target == "/dev/null" else re.sub(r"^b/", "", target)
            continue
        if not line.startswith("+") or current is None:
            continue
        text = line[1:]
        if _excluded(current, exclude):
            result.skipped_excluded += 1
        elif counted_line(text, current):
            result.counted += 1
            result.per_file[current] = result.per_file.get(current, 0) + 1
        elif text.strip():
            result.skipped_comments += 1
    return result


def render(result: SizeResult, limit: int, enabled: bool) -> str:
    passed = result.counted <= limit or not enabled
    icon, verdict = ("✅", "PASS") if passed else ("❌", "FAIL")
    if not enabled:
        verdict += " (gate off, report only)"
    lines = [MARKER, f"## {icon} PR size: {verdict}", "",
             f"**{result.counted} lines** of added code; limit {limit}.", "",
             f"Not counted: {result.skipped_comments} comment lines, "
             f"{result.skipped_excluded} lines in excluded files, deleted lines and deleted files.",
             ""]
    if result.per_file:
        lines += ["<details><summary>Largest files</summary>", "", "| File | Lines |", "|---|---|"]
        for path, n in sorted(result.per_file.items(), key=lambda kv: -kv[1])[:15]:
            lines.append(f"| `{path}` | {n} |")
        lines += ["", "</details>", ""]
    if not passed:
        lines += ["Split the change into smaller pull requests.", ""]
    return "\n".join(lines) + "\n"


def _git_diff(base: str, head: str, repo: str) -> str:
    return subprocess.run(["git", "diff", "--no-color", "-M", "-U0", f"{base}...{head}"],
                          cwd=repo, check=True, capture_output=True, text=True).stdout


def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PR size gate")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--max", type=int, default=1500, help="maximum added lines of code")
    parser.add_argument("--enabled", default="true", help="false = report only, never fail")
    parser.add_argument("--exclude", default="",
                        help="extra fnmatch patterns, whitespace-separated, added to the defaults")
    parser.add_argument("--out", default="pr-size.md")
    args = parser.parse_args(argv)

    enabled = _bool(args.enabled)
    patterns = DEFAULT_EXCLUDE + args.exclude.split()
    result = count(_git_diff(args.base, args.head, args.repo), patterns)
    Path(args.out).write_text(render(result, args.max, enabled))
    passed = result.counted <= args.max
    print(f"{'PASS' if passed else 'FAIL'}: {result.counted} lines of added code, limit {args.max}")
    return 0 if passed or not enabled else 1


if __name__ == "__main__":
    sys.exit(main())

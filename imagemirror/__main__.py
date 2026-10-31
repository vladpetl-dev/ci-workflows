"""`python -m imagemirror copy-plan images.txt --mirror M` and `... pull-plan --mirror M < images`.

Both print tab-separated lines for the workflow's shell loop; a bad list exits 2 with the reason.
"""

from __future__ import annotations

import argparse
import sys

from imagemirror.mirror import copy_plan, parse, pull_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="imagemirror")
    commands = parser.add_subparsers(dest="command", required=True)
    copy = commands.add_parser("copy-plan", help="mirror targets and their sources")
    copy.add_argument("catalogue")
    copy.add_argument("--mirror", required=True)
    pull = commands.add_parser("pull-plan", help="images (from stdin) and their mirror copies")
    pull.add_argument("--mirror", default="")
    args = parser.parse_args(argv)
    try:
        if args.command == "copy-plan":
            with open(args.catalogue, encoding="utf-8") as f:
                for target, sources in copy_plan(parse(f.read()), args.mirror):
                    print("\t".join([target, *sources]))
        else:
            text = "\n".join(sys.stdin.read().split())
            for image, mirrored in pull_plan(parse(text), args.mirror):
                print(f"{image}\t{mirrored or ''}")
    except (ValueError, OSError) as error:
        print(f"imagemirror: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""python -m ssg build | serve | new "Post title" """

import argparse
import datetime as dt
import sys
from pathlib import Path

from .build import build
from .content import slugify
from .markdown_ext import BuildError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ssg")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the site into dist/")
    b.add_argument("--drafts", action="store_true", help="include draft posts and pages")
    s = sub.add_parser("serve", help="build, serve dist/ and rebuild on change")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--drafts", action="store_true")
    n = sub.add_parser("new", help="create a new draft post")
    n.add_argument("title")
    args = parser.parse_args(argv)

    if args.cmd == "build":
        try:
            build(".", drafts=args.drafts)
        except (BuildError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    elif args.cmd == "serve":
        from .serve import serve
        serve(".", port=args.port, drafts=args.drafts)
    elif args.cmd == "new":
        today = dt.date.today().isoformat()
        path = Path("content/posts") / f"{today}-{slugify(args.title)}.md"
        if path.exists():
            print(f"error: {path} already exists", file=sys.stderr)
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        title = args.title.replace('"', '\\"')
        path.write_text(f'---\ntitle: "{title}"\ndraft: true\n---\n\n', encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

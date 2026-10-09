"""`python -m carbon.dashboard build|serve`.

build --fixtures --out DIR
    Build the site from the signed synthetic fixtures (labelled FIXTURE).
    Every build also writes the design showcase from public EV4 material,
    unless --no-showcase.
build --feed FILE [--feed FILE ...] --trust-key HEX [...] --out DIR
    Build from fetched feed documents, accepted only when signed by a pinned
    key. The fixture key is refused here.
serve --dir DIR [--port N]
    Serve a built site on 127.0.0.1 for a local preview. Nothing is published.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import sys
from pathlib import Path

from carbon.dashboard import build, feed, fixtures


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.dashboard")
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--out", required=True, type=Path)
    source = make.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixtures", action="store_true")
    source.add_argument("--feed", action="append", type=Path)
    make.add_argument("--trust-key", action="append", default=[])
    make.add_argument("--no-showcase", action="store_true")
    serve = commands.add_parser("serve")
    serve.add_argument("--dir", required=True, type=Path)
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    if args.command == "build":
        if args.fixtures:
            if args.trust_key:
                parser.error("--fixtures takes no --trust-key")
            trust, documents = fixtures.fixture_trust(), fixtures.documents()
        else:
            if not args.trust_key:
                parser.error("--feed needs at least one pinned --trust-key")
            trust = feed.Trust(keys=frozenset(args.trust_key))
            documents = [json.loads(p.read_text(encoding="utf-8")) for p in args.feed]
        index = build.build(args.out, documents, trust, showcase=not args.no_showcase)
        for board in index["boards"]:
            print(board["state"], board["slug"], board["code"] or "")
        return 0

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(args.dir)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"serving {args.dir} on http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

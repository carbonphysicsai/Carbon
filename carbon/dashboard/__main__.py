"""`python -m carbon.dashboard build|serve`.

build --fixtures --out DIR
    Build the site from the signed synthetic fixtures (labelled FIXTURE), at
    the fixtures' clock, so board.v2 shows each phase (LIVE, STALE, and
    PRE_FIRST_RELEASE after a rule cutover).
    Every build also writes the design showcase from public EV4 material,
    unless --no-showcase.
build --empty --out DIR
    An honest "launching soon" site before any board is published: no boards, no
    showcase, nothing signed or trusted, with a `_headers` file carrying the Worker's
    security headers for a static-only deploy (wrangler.dashboard-static.toml). With --names
    each named Challenge shows a "Launching soon" card.
build --feed FILE [--feed FILE ...] --trust-key HEX [...] --out DIR
    Build from fetched feed documents, accepted only when signed by a pinned
    key. The fixture key is refused here.
live --url URL [...] | --urls-file FILE  --trust-key HEX [...] | --keys-file FILE
     [--names FILE] --out NEWDIR
    The go-live build: fetch each launch feed, build with the pinned keys (no showcase),
    write the display names. A feed the door answers 404 is "not published yet" (that
    Challenge shows "Launching soon"); a failed fetch or a refused feed exits 1, as does
    a build with no accepted board. Run it into a new directory; deploy only on exit 0.
fetch --url URL --out FILE
    Save one validator's feed document (GET /carbon/v1/feed/<challenge>) as
    fetched. It is checked only when built, against a pinned key.
    --names FILE (either build form) writes data/names.json from {"<challenge id>":
    "<display name>"}; the page shows the name, else the id in title case.
serve --dir DIR [--port N]
    Serve a built site on 127.0.0.1 for a local preview. Nothing is published.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from carbon.dashboard import build, feed, fixtures

#: Sent with `fetch`, and the same as the Worker's (worker/feed.mjs
#: FETCH_HEADERS). Cloudflare refuses Python's default urllib agent with 403,
#: so the request names itself plainly.
FETCH_HEADERS = {
    "User-Agent": "carbon-dashboard/1 (+https://dashboard.carbonphysics.ai)",
    "Accept": "application/json",
}

MAX_FEED_BYTES = 16 * 2**20
HEX_KEY = re.compile(r"[0-9a-f]{64}")


def _words(values, files):
    """Comma- or line-separated settings, from the command line and from files."""
    out = []
    for text in [*values, *(Path(f).read_text(encoding="utf-8") for f in files)]:
        out += [w.strip() for w in text.replace("\n", ",").split(",") if w.strip()]
    return out


def _live(args, parser):
    """Fetch every launch feed, build the live site, say what each Challenge shows."""
    urls = _words(args.url, args.urls_file)
    keys = _words(args.trust_key, args.keys_file)
    if not urls:
        parser.error("live needs at least one --url or --urls-file")
    if any(not u.startswith("https://") for u in urls):
        parser.error("every feed URL must be https")
    if not keys or not all(HEX_KEY.fullmatch(k) for k in keys):
        parser.error(
            "live needs pinned feed keys (64 hex each), by --trust-key or --keys-file"
        )
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("--out must be a new or empty directory")
    documents, failed = [], 0
    for url in urls:
        try:
            body = _fetch_bytes(url)
        except (
            OSError,
            ValueError,
        ) as error:  # URLError, HTTPError, timeout, bad JSON, too large
            print("FETCH_FAILED", url, getattr(error, "reason", None) or error)
            failed += 1
            continue
        if body is None:
            print("NOT_PUBLISHED", url)
            continue
        documents.append(json.loads(body))
    index = build.build(
        args.out, documents, feed.Trust(keys=frozenset(keys)), showcase=False
    )
    if args.names:
        build.write_names(args.out, json.loads(args.names.read_text(encoding="utf-8")))
    boards = index["boards"]
    for board in boards:
        print(board["state"], board["slug"] or "-", board["code"] or "")
    accepted = sum(b["state"] == "ACCEPTED" for b in boards)
    refused = len(boards) - accepted
    print(
        f"{accepted} accepted, {refused} refused, {failed} not fetched, "
        f"{len(urls) - len(documents) - failed} not published yet"
    )
    if refused or failed:
        print("Not safe to deploy: fix the lines above first.", file=sys.stderr)
        return 1
    if not accepted:
        print(
            "No board is published yet: keep the 'Launching soon' site.",
            file=sys.stderr,
        )
        return 1
    return 0


def _fetch_bytes(url):
    """The body of a feed URL, or None when the door answers 404 (nothing published yet)."""
    request = urllib.request.Request(url, headers=FETCH_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            body = answer.read(MAX_FEED_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    if len(body) > MAX_FEED_BYTES:
        raise ValueError("feed too large")
    json.loads(body)
    return body


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.dashboard")
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--out", required=True, type=Path)
    source = make.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixtures", action="store_true")
    source.add_argument("--feed", action="append", type=Path)
    source.add_argument("--empty", action="store_true")
    make.add_argument("--trust-key", action="append", default=[])
    make.add_argument("--no-showcase", action="store_true")
    make.add_argument("--names", type=Path)
    live = commands.add_parser("live")
    live.add_argument("--out", required=True, type=Path)
    live.add_argument("--url", action="append", default=[])
    live.add_argument("--urls-file", action="append", default=[], type=Path)
    live.add_argument("--trust-key", action="append", default=[])
    live.add_argument("--keys-file", action="append", default=[], type=Path)
    live.add_argument("--names", type=Path)
    pull = commands.add_parser("fetch")
    pull.add_argument("--url", required=True)
    pull.add_argument("--out", required=True, type=Path)
    serve = commands.add_parser("serve")
    serve.add_argument("--dir", required=True, type=Path)
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    if args.command == "build":
        if args.fixtures:
            if args.trust_key:
                parser.error("--fixtures takes no --trust-key")
            trust = fixtures.fixture_trust()
            documents = fixtures.documents() + fixtures.phase_documents()
            now = fixtures.FIXTURE_NOW
        elif args.empty:
            if args.trust_key:
                parser.error("--empty takes no --trust-key")
            # No board is published yet: an honest empty site, no showcase.
            trust = feed.Trust(keys=frozenset({"00" * 32}))
            documents = []
            now = None
            args.no_showcase = True
        else:
            if not args.trust_key:
                parser.error("--feed needs at least one pinned --trust-key")
            trust = feed.Trust(keys=frozenset(args.trust_key))
            documents = [json.loads(p.read_text(encoding="utf-8")) for p in args.feed]
            now = None
        index = build.build(
            args.out, documents, trust, showcase=not args.no_showcase, now=now
        )
        if args.empty:
            build.write_static_headers(args.out)
        if args.names:
            try:
                build.write_names(
                    args.out, json.loads(args.names.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError) as error:
                print("names refused:", error, file=sys.stderr)
                return 1
        for board in index["boards"]:
            print(board["state"], board["slug"], board["code"] or "")
        return 0

    if args.command == "live":
        try:
            return _live(args, parser)
        except (OSError, ValueError) as error:
            print("refused:", error, file=sys.stderr)
            return 1

    if args.command == "fetch":
        if not args.url.startswith("https://"):
            parser.error("--url must be https")
        request = urllib.request.Request(args.url, headers=FETCH_HEADERS)
        with urllib.request.urlopen(request, timeout=60) as answer:
            body = answer.read(MAX_FEED_BYTES + 1)
        if len(body) > MAX_FEED_BYTES:
            print("feed too large", file=sys.stderr)
            return 1
        json.loads(body)
        args.out.write_bytes(body)
        print(f"saved {len(body)} bytes to {args.out}")
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

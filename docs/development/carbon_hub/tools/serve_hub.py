#!/usr/bin/env python3
"""Serve the Carbon Development Hub with Python's standard library.

The hub is intentionally a static artifact.  This helper exists so contributors
can test the same files over HTTP without installing a web framework.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import ipaddress
import sys
from collections.abc import Sequence
from pathlib import Path

HUB_ROOT = Path(__file__).resolve().parents[1]


class HubRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Static-file handler with development-friendly response headers."""

    def __init__(self, *args: object, quiet: bool = False, **kwargs: object) -> None:
        self.quiet = quiet
        super().__init__(*args, **kwargs)

    def end_headers(self) -> None:
        # Do not let a browser cache stale generated output during drift checks.
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        if not self.quiet:
            super().log_message(format, *args)


class HubHTTPServer(http.server.ThreadingHTTPServer):
    """Threaded local server whose request threads never block shutdown."""

    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request: object, client_address: object) -> None:
        # Chromium routinely resets an HTTP/1.1 keep-alive socket while moving to
        # the next smoke-test URL.  That is not a page or server failure.
        error = sys.exc_info()[1]
        if isinstance(
            error,
            (BrokenPipeError, ConnectionAbortedError, ConnectionResetError),
        ):
            return
        super().handle_error(request, client_address)


def create_server(
    root: Path = HUB_ROOT,
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    quiet: bool = False,
) -> HubHTTPServer:
    """Create, but do not start, a server rooted at ``root``."""

    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise FileNotFoundError(f"Hub directory does not exist: {resolved_root}")
    handler = functools.partial(
        HubRequestHandler,
        directory=str(resolved_root),
        quiet=quiet,
    )
    return HubHTTPServer((host, port), handler)


def _display_host(host: str) -> str:
    if host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    return f"[{address}]" if address.version == 6 else str(address)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the generated Carbon Development Hub over HTTP."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port; use 0 to select an available port (default: 8000)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=HUB_ROOT,
        help="directory to serve (default: the hub root)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-request access logging",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0 <= args.port <= 65535:
        raise SystemExit("--port must be between 0 and 65535")

    try:
        server = create_server(args.root, args.host, args.port, quiet=args.quiet)
    except (FileNotFoundError, OSError) as exc:
        raise SystemExit(f"Unable to start hub server: {exc}") from exc

    bound_host, bound_port = server.server_address[:2]
    visible_host = _display_host(str(bound_host))
    print(f"Serving Carbon Development Hub from {Path(args.root).resolve()}")
    print(f"Open http://{visible_host}:{bound_port}/index.html")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping hub server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

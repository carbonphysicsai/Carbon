"""The helper's loopback server: one page, three calls, a one-time token, no logging of anything."""

from __future__ import annotations

import argparse
import hmac
import json
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .backend import IdentityRefused, SdkBackend
from .core import Identity
from .page import HELPER_JS, INDEX_HTML

MAX_BODY = 4096
IDLE_SECONDS = 1800
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, identity, token=None, port=0):
        self.identity = identity
        self.token = token or secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.touched = time.monotonic()
        self.finished = threading.Event()
        super().__init__(("127.0.0.1", port), Handler)

    @property
    def link(self):
        # The token rides in the fragment: a fragment is never sent to any server, and never in a Referer.
        return f"http://127.0.0.1:{self.server_address[1]}/#t={self.token}"


class Handler(BaseHTTPRequestHandler):
    server_version = "carbon-miner-identity"
    sys_version = ""

    # Nothing is logged: not the request line, not the body, not an error.
    def log_message(self, *args):
        pass

    def log_error(self, *args):
        pass

    def _send(self, status, body, kind="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for name, value in HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def _host_ok(self):
        # Only the address this server printed: a rebound DNS name is refused.
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_address[1]}"

    def _authorised(self):
        given = self.headers.get("X-Identity-Token", "")
        return hmac.compare_digest(given.encode(), self.server.token.encode())

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "wrong_host"})
        if self.path == "/":
            return self._send(200, INDEX_HTML.encode(), "text/html")
        if self.path == "/helper.js":
            return self._send(200, HELPER_JS.encode(), "text/javascript")
        return self._send(404, {"error": "not_found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "wrong_host"})
        origin = self.headers.get("Origin")
        if (
            origin is not None
            and origin != f"http://127.0.0.1:{self.server.server_address[1]}"
        ):
            return self._send(403, {"error": "wrong_origin"})
        if not self._authorised():
            return self._send(401, {"error": "token_required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_BODY:
                raise ValueError
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise TypeError
        except (ValueError, TypeError):
            return self._send(400, {"error": "bad_request"})
        self.server.touched = time.monotonic()
        identity = self.server.identity
        with self.server.lock:
            try:
                if self.path == "/api/create":
                    return self._send(200, identity.create(body.get("name")))
                if self.path == "/api/confirm":
                    return self._send(200, identity.confirm(body.get("words")))
                if self.path == "/api/save":
                    return self._send(
                        200, identity.save(body.get("password"), body.get("again"))
                    )
                if self.path == "/api/done":
                    identity.discard()
                    self.server.finished.set()
                    return self._send(200, {"done": True})
            except IdentityRefused as refused:
                return self._send(422, {"error": str(refused)})
            # Never put the key tool's own text on the wire: it can hold secrets.
            except Exception:  # noqa: BLE001
                identity.discard()
                return self._send(
                    500,
                    {"error": "The key tool failed. Nothing was saved; start again."},
                )
        return self._send(404, {"error": "not_found"})


def serve(server, idle_seconds=IDLE_SECONDS):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while not server.finished.wait(1.0):
            if time.monotonic() - server.touched > idle_seconds:
                break
    finally:
        server.shutdown()
        server.server_close()
        server.identity.discard()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="carbon-miner-identity",
        description="Create your mining identity on this machine. Carbon never sees your keys or password.",
    )
    parser.add_argument(
        "--wallet-path", help="wallets directory (the Bittensor default if omitted)"
    )
    parser.add_argument(
        "--hotkey", default="default", help="hotkey name inside the wallet"
    )
    args = parser.parse_args(argv)
    try:
        import bittensor  # noqa: F401
    except ImportError:
        print(
            "The Bittensor library is not installed here, so no keys can be made.",
            file=sys.stderr,
        )
        return 1
    server = Server(Identity(SdkBackend(args.wallet_path), args.hotkey))
    print("Open this link in your browser on this machine. It works once, here only:\n")
    print("  " + server.link + "\n")
    print("Nothing is sent anywhere. Close this window when you are done.")
    try:
        serve(server)
    except KeyboardInterrupt:
        pass
    return 0

"""A build-time HTTP proxy that serves Ubuntu's archive from one dated snapshot.

Why: `.devcontainer/worker-native-mesh.lock` pins exact package versions (with sha256). When Ubuntu replaces a version
in noble-updates (17 Nov: libgbm1 and the other mesa packages went from 25.2.8-0ubuntu0.24.04.4 to .5), the live index
no longer lists the pinned one and `apt-get install name=version` cannot resolve it, so every fresh worker-image build
fails. The lock, the install script and the Dockerfile are build inputs (they scope the worker image identity), so the
fix must not touch them. Instead the build script (`c03_worker_image.sh`, not a build input) runs this proxy and passes
it as the build's `http_proxy`. Docker gives that predefined proxy argument to every RUN step without recording it in
the image. apt then reads the same signed index and package bytes from snapshot.ubuntu.com that the live archive
served on that date.

Trust: nothing here is trusted. apt checks the archive signature on InRelease and the index hashes, and the install
script checks every package's sha256 against the lock. A wrong byte from this proxy fails the build. It never changes
a grade.

Only http://archive.ubuntu.com/ubuntu/... and http://security.ubuntu.com/ubuntu/... are served (the base image's
sources). Any other request is refused with 403, so it cannot hide a different fetch. Standard library only.

    python -I scripts/dev/apt_snapshot_proxy.py SNAPSHOT [PORT] [loopback|gateway]   # prints the bound port on its first stdout line
"""

from __future__ import annotations

import ipaddress
import re
import shutil
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

#: The base image's apt sources (ubuntu:24.04 /etc/apt/sources.list.d/ubuntu.sources).
ARCHIVE_HOSTS = ("archive.ubuntu.com", "security.ubuntu.com")
SNAPSHOT_ROOT = "https://snapshot.ubuntu.com/ubuntu/"
SNAPSHOT = re.compile(r"^\d{8}T\d{6}Z$")
#: apt percent-encodes `~` and `+` in package file names (libllvm20_20.1.2-0ubuntu1%7e24.04.3_amd64.deb).
_PATH = re.compile(r"^/ubuntu/[A-Za-z0-9._~+%/-]*$")


def snapshot_url(url: str, snapshot: str) -> str | None:
    """The snapshot URL for an archive URL, or None when this proxy does not serve it."""
    parts = urlsplit(url)
    if (
        parts.scheme != "http"
        or parts.hostname not in ARCHIVE_HOSTS
        or parts.query
        or parts.fragment
    ):
        return None
    if (
        parts.port not in (None, 80)
        or not _PATH.match(parts.path)
        or "/../" in parts.path + "/"
    ):
        return None
    return SNAPSHOT_ROOT + snapshot + "/" + parts.path[len("/ubuntu/") :]


def handler(snapshot: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def _serve(self, body: bool) -> None:
            target = snapshot_url(self.path, snapshot)
            if target is None:
                self.send_error(
                    403, "apt snapshot proxy serves only the Ubuntu archive"
                )
                return
            request = urllib.request.Request(target, method="GET" if body else "HEAD")
            try:
                upstream = urllib.request.urlopen(request, timeout=120)
            except urllib.error.HTTPError as error:
                self.send_error(error.code, error.reason)
                return
            except (urllib.error.URLError, OSError) as error:
                self.send_error(502, f"snapshot unreachable: {error}")
                return
            with upstream:
                self.send_response(upstream.status)
                for name in ("Content-Type", "Content-Length", "Last-Modified", "ETag"):
                    value = upstream.headers.get(name)
                    if value is not None:
                        self.send_header(name, value)
                self.end_headers()
                if body:
                    shutil.copyfileobj(upstream, self.wfile, 1 << 20)

        def do_GET(self) -> None:
            self._serve(True)

        def do_HEAD(self) -> None:
            self._serve(False)

        def do_CONNECT(self) -> None:
            self.send_error(403, "apt snapshot proxy does not tunnel")

        def log_message(self, format, *args) -> None:
            sys.stderr.write("apt-snapshot-proxy: " + (format % args) + "\n")

    return Handler


def local_client(address: str) -> bool:
    """A client this machine's own builds use: loopback, or a private/link-local address (Docker bridges,
    Docker Desktop's VM network, rootless networking). Anything else is refused before any request is read.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_private or ip.is_link_local


class _LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def verify_request(self, request, client_address) -> bool:
        return local_client(client_address[0])


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3, 4) or not SNAPSHOT.match(argv[1]):
        sys.stderr.write(
            "usage: apt_snapshot_proxy.py YYYYMMDDTHHMMSSZ [PORT] [loopback|gateway]\n"
        )
        return 2
    port = int(argv[2]) if len(argv) >= 3 else 0
    mode = argv[3] if len(argv) == 4 else "loopback"
    if mode not in ("loopback", "gateway"):
        sys.stderr.write("mode must be loopback or gateway\n")
        return 2
    # gateway: Docker Desktop / rootless builds reach the host through host-gateway, not its loopback, so listen on
    # every interface and answer only local clients (`local_client`).
    bind = "127.0.0.1" if mode == "loopback" else "0.0.0.0"
    server = _LocalServer((bind, port), handler(argv[1]))
    print(server.server_address[1], flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

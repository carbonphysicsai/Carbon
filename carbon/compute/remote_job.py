"""The controller's side of one remote job.

`RemoteJob` drives `carbon.compute.job_server` on a machine the miner runs,
from the miner's own controller: wait for it, stage the inputs once, run,
poll, fetch the output once. The job token is the only thing it presents; no
key of the miner's ever reaches the job.

Every response body is bounded and every archive is flat files only, so a
job can return nothing but its own output files.

A job is reached over HTTPS, or through an SSH tunnel whose local end is an
owner-only Unix socket (`UnixTransport`). Plain HTTP over TCP is never used:
another user of the controller's machine could hold a local TCP port and
receive the job's token.
"""

from __future__ import annotations

import http.client
import json
import os
import secrets
import socket
import stat
import tarfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from .job_server import MAX_OUTPUT_BYTES, MAX_STAGE_BYTES, PROGRAM, pack, unpack

#: Polls are short: proxies and tunnels may close long requests, so a run is
#: started asynchronously and its state read until it ends.
POLL_SECONDS = 5.0
#: The base URL of a job reached through an SSH tunnel. It names no host or
#: port: every request goes over the tunnel's Unix socket.
TUNNEL_URL = "http://carbon-job"
#: Bound on an error response body, as `_urllib` reads it.
MAX_ERROR_BYTES = 65536


class RemoteJobFailure(Exception):
    """The job did not complete; `stage` names where it stopped."""

    def __init__(self, stage, detail):
        super().__init__(f"{stage}: {detail}")
        self.stage, self.detail = stage, detail


def new_token():
    return secrets.token_hex(32)


def _urllib(method, url, *, body, headers, timeout):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=timeout
        ) as response:
            return response.status, response.read(MAX_OUTPUT_BYTES + 1)
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read(MAX_ERROR_BYTES)


def owned_socket(path: str) -> bool:
    """True only when `path` is a Unix socket this user owns, not a link, in
    a directory this user owns that no one else may enter (mode 0700)."""
    try:
        directory = os.lstat(os.path.dirname(path))
        found = os.lstat(path)
    except OSError:
        return False
    uid = os.getuid()
    return (
        stat.S_ISDIR(directory.st_mode)
        and directory.st_uid == uid
        and stat.S_IMODE(directory.st_mode) == 0o700
        and stat.S_ISSOCK(found.st_mode)
        and found.st_uid == uid
    )


class _UnixConnection(http.client.HTTPConnection):
    """An HTTP connection over a Unix socket, checked before connecting."""

    def __init__(self, path: str, timeout: float):
        super().__init__("carbon-job", timeout=timeout)
        self._socket_path = path

    def connect(self):
        if not owned_socket(self._socket_path):
            raise ConnectionRefusedError("the tunnel's socket is not this user's")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect(self._socket_path)
        except BaseException:
            sock.close()
            raise
        self.sock = sock


class UnixTransport:
    """HTTP to a job through an SSH tunnel's Unix socket, with `_urllib`'s
    signature and bounds: no redirect is followed, a success body is read to
    MAX_OUTPUT_BYTES + 1 and an error body to MAX_ERROR_BYTES. The socket is
    checked to be this user's before every connection; nothing goes over
    TCP."""

    def __init__(self, path: str):
        if type(path) is not str or not os.path.isabs(path):
            raise ValueError("a tunnel's socket is an absolute path")
        self.path = path

    def __call__(self, method, url, *, body, headers, timeout):
        if type(url) is not str or not url.startswith(TUNNEL_URL + "/"):
            raise ValueError("a tunnel carries only its own job's requests")
        connection = _UnixConnection(self.path, timeout)
        try:
            connection.request(
                method, url[len(TUNNEL_URL) :], body=body, headers=headers
            )
            response = connection.getresponse()
            if 200 <= response.status < 300:
                return response.status, response.read(MAX_OUTPUT_BYTES + 1)
            return response.status, response.read(MAX_ERROR_BYTES)
        finally:
            connection.close()


class RemoteJob:
    """One job on one remote machine, addressed by its base URL and token."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: Callable = _urllib,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        cancelled: Callable[[], bool] = lambda: False,
    ):
        # HTTPS, or an SSH tunnel's owner-only Unix socket on this machine
        # (`TUNNEL_URL` with a `UnixTransport`, and only together), so the
        # token and inputs travel inside TLS or SSH. Plain HTTP over TCP is
        # refused, to another host or to a local port another user could
        # hold.
        if type(base_url) is not str:
            raise ValueError("a remote job is reached over https or a local tunnel")
        if isinstance(transport, UnixTransport):
            if base_url != TUNNEL_URL:
                raise ValueError("a tunnel's job is reached at its tunnel URL only")
        elif not base_url.startswith("https://"):
            raise ValueError("a remote job is reached over https or a local tunnel")
        self.base, self.token = base_url.rstrip("/"), token
        self.transport, self.clock, self.sleep = transport, clock, sleep
        # The campaign's stop: checked between polls, so a stopped campaign
        # ends the job and its caller removes the job's container.
        self.cancelled = cancelled

    def _call(self, method, path, body=None, *, authorized=True, timeout=60):
        headers = {"User-Agent": "carbon-compute/1"}
        if authorized:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/gzip"
        try:
            return self.transport(
                method, self.base + path, body=body, headers=headers, timeout=timeout
            )
        except Exception as failure:  # noqa: BLE001 - only the type survives
            return None, type(failure).__name__.encode()

    def state(self):
        status, body = self._call("GET", "/status", authorized=False, timeout=20)
        if status != 200:
            return None
        try:
            return json.loads(body)["state"]
        except (ValueError, KeyError, TypeError):
            return None

    def wait_for(self, states, deadline):
        while self.clock() < deadline:
            if self.cancelled():
                raise RemoteJobFailure("cancelled", "the campaign was stopped")
            seen = self.state()
            if seen in states:
                return seen
            self.sleep(POLL_SECONDS)
        raise RemoteJobFailure(
            "wait", "deadline passed waiting for " + "/".join(states)
        )

    def stage(self, files):
        if PROGRAM not in files:
            raise ValueError("the program is staged with its inputs")
        body = pack(files)
        if len(body) > MAX_STAGE_BYTES:
            raise ValueError("staged inputs exceed their bound")
        status, _ = self._call("PUT", "/stage", body, timeout=300)
        if status != 200:
            raise RemoteJobFailure("stage", f"http {status}")

    def start(self):
        status, _ = self._call("POST", "/run")
        if status != 202:
            raise RemoteJobFailure("run", f"http {status}")

    def output(self):
        """(the job server's result, the output files). Whatever the response
        holds, a malformed archive or result is this job's typed failure, so
        the caller's ledger always finishes the operation."""
        status, body = self._call("GET", "/output", timeout=300)
        if status != 200:
            raise RemoteJobFailure("output", f"http {status}")
        try:
            files = unpack(body, MAX_OUTPUT_BYTES)
            result = json.loads(files.pop("carbon-job-result.json"))
        except (ValueError, KeyError, EOFError, OSError, tarfile.TarError) as bad:
            raise RemoteJobFailure("output", type(bad).__name__) from None
        if type(result) is not dict:
            raise RemoteJobFailure("output", "result is not a record")
        return result, files

    def run(self, files, *, ready_deadline, run_deadline):
        """Stage, run and fetch one job. Returns (result, output files)."""
        self.wait_for(("WAITING",), ready_deadline)
        self.stage(files)
        self.start()
        self.wait_for(("DONE", "FAILED"), run_deadline)
        return self.output()

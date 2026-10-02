# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The one-job server a rented GPU pod runs (C-MLP-03 slice 4).

A rented box receives the pinned worker image and one job's public inputs,
nothing else. This module is that job's whole surface: it is part of the
`carbon` wheel inside the pinned worker image, and the pod's start command is
`python -I -m carbon.compute.job_server`. The miner's controller (on their own
machine, holding every key) then:

1. waits for `GET /status`;
2. uploads the staged inputs once (`PUT /stage`, a gzip tar of flat files);
3. starts the fixed program (`POST /run`) and polls `GET /status`;
4. downloads the output once (`GET /output`), after which the server exits;
5. terminates the pod and verifies it is gone.

Every request but `/status` must carry the job's bearer token, a random value
Carbon generates per job and passes in the pod's environment. It is not a
provider key, a hotkey or any credential of the miner's: it opens this one job
and nothing else. The program runs with the carrier's working-directory layout
(`workspace/` holds the inputs, `output/` beside it), so the same practice
program runs here as in the local carrier.

What this is not: an isolation boundary. The pod is the miner's own rented
machine; nothing that runs here is evidence the validator reads.
"""

from __future__ import annotations

import gzip
import hmac
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from pathlib import Path

SCHEMA = "carbon.compute.rented-job.v1"
#: Bounds on what crosses the wire in each direction.
MAX_STAGE_BYTES = 64 * 1024**2
MAX_OUTPUT_BYTES = 64 * 1024**2
MAX_LOG_BYTES = 1024**2
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_TOKEN = re.compile(r"[0-9a-f]{64}")
PROGRAM = "program.py"


def pack(files):
    """A deterministic gzip tar of flat `files` ({name: bytes})."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name in sorted(files):
            if not _NAME.fullmatch(name):
                raise ValueError("flat file names only")
            body = files[name]
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(body), 0o444, 0
            archive.addfile(info, io.BytesIO(body))
    return gzip.compress(buffer.getvalue(), mtime=0)


def unpack(blob, maximum):
    """Flat regular files from a gzip tar, bounded; anything else is refused."""
    if len(blob) > maximum:
        raise ValueError("archive exceeds its bound")
    raw = gzip.decompress(blob)
    if len(raw) > 2 * maximum:
        raise ValueError("archive exceeds its bound")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive.getmembers():
            if (
                not member.isreg()
                or not _NAME.fullmatch(member.name)
                or member.name in files
            ):
                raise ValueError("flat regular files only")
            handle = archive.extractfile(member)
            files[member.name] = handle.read() if handle is not None else b""
    return files


class Job:
    """One job's state on the pod."""

    def __init__(self, root, seconds):
        self.root = Path(root)
        self.seconds = seconds
        self.state = "WAITING"
        self.returncode = None
        self.elapsed = None
        self.lock = threading.Lock()
        self.finished = threading.Event()

    @property
    def input(self):
        return self.root / "input"

    def stage(self, files):
        with self.lock:
            if self.state != "WAITING" or PROGRAM not in files:
                raise ValueError("stage once, with the program")
            self.input.mkdir()
            for name, body in files.items():
                (self.input / name).write_bytes(body)
            self.state = "STAGED"

    def run(self):
        with self.lock:
            if self.state != "STAGED":
                raise ValueError("stage before run")
            self.state = "RUNNING"
        threading.Thread(target=self._execute, daemon=True).start()

    def _execute(self):
        # The carrier's layout: inputs copied into workspace/, the program run
        # from input/, output/ beside the workspace.
        work, out = self.root / "workspace", self.root / "output"
        work.mkdir()
        out.mkdir()
        for item in self.input.iterdir():
            if item.name != PROGRAM:
                shutil.copyfile(item, work / item.name)
        started = time.monotonic()
        try:
            with (
                (self.root / "stdout.txt").open("wb") as stdout,
                (self.root / "stderr.txt").open("wb") as stderr,
            ):
                completed = subprocess.run(
                    [sys.executable, "-I", str(self.input / PROGRAM)],
                    cwd=work,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=self.seconds,
                    check=False,
                )
            self.returncode = completed.returncode
        except subprocess.TimeoutExpired:
            self.returncode = None
        self.elapsed = round(time.monotonic() - started, 3)
        with self.lock:
            self.state = "DONE" if self.returncode == 0 else "FAILED"
        self.finished.set()

    def output(self):
        with self.lock:
            if self.state not in ("DONE", "FAILED"):
                raise ValueError("no output yet")
        files = {}
        for path in sorted((self.root / "output").iterdir()):
            if path.is_file() and not path.is_symlink() and _NAME.fullmatch(path.name):
                files[path.name] = path.read_bytes()
        stderr = (self.root / "stderr.txt").read_bytes()[-MAX_LOG_BYTES:]
        files["carbon-job-result.json"] = json.dumps(
            {
                "schema": SCHEMA,
                "state": self.state,
                "returncode": self.returncode,
                "elapsed_s": self.elapsed,
                "timed_out": self.returncode is None,
            },
            sort_keys=True,
        ).encode()
        files["carbon-job-stderr.txt"] = stderr
        body = pack(files)
        if len(body) > MAX_OUTPUT_BYTES:
            raise ValueError("output exceeds its bound")
        return body


def handler_for(job, token, served):
    """The request handler bound to one job and its token."""

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "carbon-job/1"
        sys_version = ""

        def log_message(self, *args):  # Nothing about a request is logged.
            return

        def _send(self, status, body=b"", kind="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            presented = self.headers.get("Authorization", "")
            expected = "Bearer " + token
            if not hmac.compare_digest(presented.encode(), expected.encode()):
                self._send(401, b'{"error":"unauthorized"}')
                return False
            return True

        def _body(self, maximum):
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= maximum:
                raise ValueError("bounded body required")
            return self.rfile.read(length)

        def do_GET(self):
            if self.path == "/status":
                body = json.dumps({"schema": SCHEMA, "state": job.state}).encode()
                return self._send(200, body)
            if self.path == "/output" and self._authorized():
                try:
                    body = job.output()
                except ValueError:
                    return self._send(409, b'{"error":"not_finished"}')
                self._send(200, body, "application/gzip")
                served.set()
                return None
            if self.path != "/output":
                self._send(404, b'{"error":"not_found"}')
            return None

        def do_PUT(self):
            if self.path != "/stage":
                return self._send(404, b'{"error":"not_found"}')
            if not self._authorized():
                return None
            try:
                job.stage(unpack(self._body(MAX_STAGE_BYTES), MAX_STAGE_BYTES))
            except (ValueError, OSError, tarfile.TarError, EOFError):
                return self._send(400, b'{"error":"stage_refused"}')
            return self._send(200, b'{"state":"STAGED"}')

        def do_POST(self):
            if self.path != "/run":
                return self._send(404, b'{"error":"not_found"}')
            if not self._authorized():
                return None
            try:
                job.run()
            except ValueError:
                return self._send(409, b'{"error":"not_staged"}')
            return self._send(202, b'{"state":"RUNNING"}')

    return Handler


def serve(*, token, port, seconds, lifetime, root=None, ready=None):
    """Serve one job until its output is fetched or `lifetime` passes."""
    if not _TOKEN.fullmatch(token or ""):
        raise ValueError("a 64-hex job token is required")
    with tempfile.TemporaryDirectory(dir=root) as scratch:
        job, served = Job(scratch, seconds), threading.Event()
        server = http.server.ThreadingHTTPServer(
            ("0.0.0.0", port), handler_for(job, token, served)
        )
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        if ready is not None:
            ready(server.server_address[1])
        served.wait(timeout=lifetime)
        server.shutdown()
        server.server_close()


def main():
    token = os.environ.pop("CARBON_JOB_TOKEN", "")
    serve(
        token=token,
        port=int(os.environ.get("CARBON_JOB_PORT", "8000")),
        seconds=int(os.environ.get("CARBON_JOB_SECONDS", "600")),
        lifetime=int(os.environ.get("CARBON_JOB_LIFETIME", "3600")),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The one-job server a remote GPU worker container runs.

A remote machine receives the pinned worker image and one job's public
inputs, nothing else. This module is that job's whole surface: it is part of
the `carbon` wheel inside the pinned worker image, and the container's start
command is `python -I -m carbon.compute.job_server`. The miner's controller
(on their own machine, holding every key) then:

1. waits for `GET /status`;
2. uploads the staged inputs once (`PUT /stage`, a gzip tar of flat files);
3. starts the fixed program (`POST /run`) and polls `GET /status`;
4. downloads the output once (`GET /output`), after which the server exits;
5. removes the job's container. The machine itself is the miner's to start
   and stop (OWNER-MINER-COMPUTE-LINK-ONLY-01).

Every request but `/status` must carry the job's bearer token, a random value
Carbon generates per job and passes in the container's environment. It is not
a provider key, a hotkey or any credential of the miner's: it opens this one
job and nothing else. The program runs with the carrier's working-directory
layout (`workspace/` holds the inputs, `output/` beside it), so the same
practice program runs here as in the local carrier.

Where it listens depends on how the miner runs the worker (LINKONLY-D5).
Inside a job container whose port Docker publishes on the machine's loopback
(`ssh-docker`), it listens on every address of that container. As a process in
a container the miner started from the pinned worker (`ssh-container`), it
listens on that container's loopback only (`CARBON_JOB_BIND=127.0.0.1`), on a
free port (`CARBON_JOB_PORT=0`) that it writes to `CARBON_JOB_PORT_FILE`, with
its scratch under `CARBON_JOB_ROOT`, the directory Carbon removes afterwards.
Either way the controller reaches it through an SSH port forward.

What this is not: an isolation boundary. The machine is the miner's own;
nothing that runs here is evidence the validator reads.
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
import zlib
from pathlib import Path

SCHEMA = "carbon.compute.rented-job.v1"
#: Bounds on what crosses the wire in each direction.
MAX_STAGE_BYTES = 64 * 1024**2
MAX_OUTPUT_BYTES = 64 * 1024**2
MAX_LOG_BYTES = 1024**2
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_TOKEN = re.compile(r"[0-9a-f]{64}")
PROGRAM = "program.py"
#: Where the server may listen: every address of a job container whose port
#: Docker publishes on the machine's loopback, or a container's own loopback.
BINDS = ("0.0.0.0", "127.0.0.1")


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
    """Flat regular files from a gzip tar, bounded; anything else is refused.

    The archive is inflated as a stream and abandoned the moment it passes
    twice its bound, so a small archive of zeros never expands in memory
    first. One gzip member only, whole: a truncated, corrupt or trailing
    stream is refused like any other malformed archive.
    """
    if len(blob) > maximum:
        raise ValueError("archive exceeds its bound")
    limit = 2 * maximum
    inflater = zlib.decompressobj(wbits=31)  # gzip framing, CRC checked
    try:
        raw = inflater.decompress(blob, limit + 1)
    except zlib.error:
        raise ValueError("archive is not a gzip stream") from None
    if len(raw) > limit:
        raise ValueError("archive exceeds its bound")
    if not inflater.eof or inflater.unused_data:
        raise ValueError("archive is not one whole gzip stream")
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


class OutputRefused(ValueError):
    """The job finished, but its output exceeds the bound: it is never sent."""


class Job:
    """One job's state in the worker container."""

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
        # Read against one raw budget, twice the wire bound, so output the
        # program wrote (or a child still writes) is never read whole first.
        budget = 2 * MAX_OUTPUT_BYTES
        files = {}
        for path in sorted((self.root / "output").iterdir()):
            if path.is_file() and not path.is_symlink() and _NAME.fullmatch(path.name):
                with path.open("rb") as handle:
                    body = handle.read(budget + 1)
                budget -= len(body)
                if budget < 0:
                    raise OutputRefused("output exceeds its bound")
                files[path.name] = body
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
            raise OutputRefused("output exceeds its bound")
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
                except OutputRefused:
                    return self._send(413, b'{"error":"output_exceeds_bound"}')
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


def serve(*, token, port, seconds, lifetime, root=None, ready=None, bind="0.0.0.0"):
    """Serve one job until its output is fetched or `lifetime` passes."""
    if not _TOKEN.fullmatch(token or ""):
        raise ValueError("a 64-hex job token is required")
    if bind not in BINDS:
        raise ValueError("the job server listens on 0.0.0.0 or 127.0.0.1")
    with tempfile.TemporaryDirectory(dir=root) as scratch:
        job, served = Job(scratch, seconds), threading.Event()
        server = http.server.ThreadingHTTPServer(
            (bind, port), handler_for(job, token, served)
        )
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        if ready is not None:
            ready(server.server_address[1])
        served.wait(timeout=lifetime)
        server.shutdown()
        server.server_close()


def write_port(path, port):
    """Tell whoever started this server which port it took, atomically: the
    file appears only once it holds the whole port."""
    target = Path(path)
    staged = target.with_name(target.name + ".staged")
    staged.write_text(f"{int(port)}\n")
    os.replace(staged, target)


def main():
    token = os.environ.pop("CARBON_JOB_TOKEN", "")
    port_file = os.environ.get("CARBON_JOB_PORT_FILE")
    serve(
        token=token,
        port=int(os.environ.get("CARBON_JOB_PORT", "8000")),
        seconds=int(os.environ.get("CARBON_JOB_SECONDS", "600")),
        lifetime=int(os.environ.get("CARBON_JOB_LIFETIME", "3600")),
        root=os.environ.get("CARBON_JOB_ROOT") or None,
        bind=os.environ.get("CARBON_JOB_BIND", "0.0.0.0"),
        ready=None if not port_file else (lambda bound: write_port(port_file, bound)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

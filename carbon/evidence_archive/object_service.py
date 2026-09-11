"""Disposable loopback-only immutable object service for C-EA1 integration tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .model import ArchiveFailure, validate_token
from .storage import validate_object_key

MAX_OBJECT_BYTES = 4 * 1024 * 1024


class _Handler(BaseHTTPRequestHandler):
    server: ObjectServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _parts(self, prefix: str) -> tuple[str, str] | None:
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if not path.startswith(prefix):
            return None
        object_key = path[len(prefix) :]
        pieces = object_key.split("/")
        if len(pieces) != 5:
            return None
        tenant = pieces[1]
        if tenant != self.server.tenant_id:
            return None
        try:
            validate_object_key(object_key, tenant)
        except ArchiveFailure:
            return None
        return tenant, object_key

    def _object_path(self, object_key: str) -> Path:
        digest = hashlib.sha256(object_key.encode("ascii")).hexdigest()
        return self.server.root / "objects" / digest[:2] / digest[2:]

    def _send(self, status: int, body: bytes = b"") -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_PUT(self) -> None:
        parsed = self._parts("/objects/")
        length = self.headers.get("Content-Length")
        if parsed is None or length is None or not length.isdigit():
            self._send(400)
            return
        size = int(length)
        if not 1 <= size <= MAX_OBJECT_BYTES:
            self._send(413)
            return
        body = self.rfile.read(size)
        if len(body) != size:
            self._send(400)
            return
        _, object_key = parsed
        target = self._object_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata = target.with_suffix(".json")
        if target.exists():
            if target.read_bytes() == body:
                self._send(200, b"existing")
            else:
                self._send(409)
            return
        temporary = target.with_suffix(f".{os.getpid()}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
            metadata.write_text(
                json.dumps({"object_key": object_key}, sort_keys=True), encoding="utf-8"
            )
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
        self._send(201, b"created")

    def do_GET(self) -> None:
        if self.path.startswith("/inventory/"):
            tenant = urllib.parse.unquote(self.path[len("/inventory/") :])
            try:
                tenant = validate_token(tenant)
            except ArchiveFailure:
                self._send(400)
                return
            if tenant != self.server.tenant_id:
                self._send(403)
                return
            keys: list[str] = []
            for metadata in (self.server.root / "objects").glob("*/*.json"):
                try:
                    value = json.loads(metadata.read_text(encoding="utf-8"))
                    object_key = value["object_key"]
                    validate_object_key(object_key, tenant)
                    keys.append(object_key)
                except (
                    OSError,
                    KeyError,
                    ValueError,
                    json.JSONDecodeError,
                    ArchiveFailure,
                ):
                    continue
            self._send(200, json.dumps(sorted(keys), separators=(",", ":")).encode())
            return
        parsed = self._parts("/objects/")
        if parsed is None:
            self._send(400)
            return
        target = self._object_path(parsed[1])
        if not target.is_file():
            self._send(404)
            return
        self._send(200, target.read_bytes())

    def do_POST(self) -> None:
        parsed = self._parts("/quarantine/")
        if parsed is None:
            self._send(400)
            return
        target = self._object_path(parsed[1])
        metadata = target.with_suffix(".json")
        if not target.is_file() or not metadata.is_file():
            self._send(404)
            return
        quarantine_ref = "quarantine-" + hashlib.sha256(parsed[1].encode()).hexdigest()
        destination = self.server.root / "quarantine" / quarantine_ref
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != target.read_bytes():
                self._send(409)
                return
        else:
            shutil.move(target, destination)
        metadata.unlink(missing_ok=True)
        self._send(200, quarantine_ref.encode("ascii"))


class ObjectServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], root: Path, tenant_id: str) -> None:
        if address[0] not in {"127.0.0.1", "localhost"}:
            raise ValueError("The C-EA1 object service is loopback-only.")
        self.root = Path(root)
        self.tenant_id = validate_token(tenant_id)
        self.root.mkdir(parents=True, exist_ok=True)
        super().__init__(address, _Handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--tenant-id", required=True)
    args = parser.parse_args()
    server = ObjectServer(("127.0.0.1", args.port), args.root, args.tenant_id)
    args.ready_file.write_text(str(server.server_port), encoding="ascii")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

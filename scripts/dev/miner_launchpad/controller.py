"""Local DEVELOPMENT launcher rehearsal. No agent, chain, or provider execution.

Run with Python 3.11: python scripts/dev/miner_launchpad/controller.py
This controller owns launcher runs, not Carbon's scientific submission lifecycle.
"""

from __future__ import annotations

import argparse
import contextlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

SCHEMA = "carbon.launchpad.rehearsal.v1"
ACTIVE = ("QUEUED", "RUNNING", "PAUSED", "INTERRUPTED")
TERMINAL = ("COMPLETED", "STOPPED", "EXPIRED")
CHOICES = {
    "mode": "REHEARSAL",
    "challenge": "controller-rehearsal-v1",
    "agent": "fixture",
    "reasoning": "none",
    "compute": "local",
}
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


class Rejected(Exception):
    """A safe, fixed public error. Never include request values or credentials."""

    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


def validate_spec(value: object) -> dict:
    fields = set(CHOICES) | {"max_steps", "max_seconds"}
    if type(value) is not dict or set(value) != fields:
        raise Rejected("invalid_launch_fields")
    for name, expected in CHOICES.items():
        if type(value[name]) is not str or value[name] != expected:
            raise Rejected("unsupported_profile_no_fallback")
    for name, low, high in (("max_steps", 1, 100), ("max_seconds", 1, 600)):
        if type(value[name]) is not int or not low <= value[name] <= high:
            raise Rejected("invalid_run_limit")
    return dict(value)


def parse_json(raw: bytes) -> object:
    def pairs(items: list) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise Rejected("duplicate_json_field")
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        raise Rejected("invalid_json")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Rejected("invalid_json") from exc


class Controller:
    """SQLite-persisted, single-owner, zero-network rehearsal controller.

    The server holds an OS lock before creating this object or recovering runs.
    Each mutation commits its state and event together. No caller-supplied code,
    external URL, credential, monetary grant, or scientific result is accepted.
    """

    def __init__(self, database: Path, clock: Callable[[], float] = time.time):
        self.database = database
        self.clock = clock
        self.lock = threading.RLock()
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                    spec TEXT NOT NULL, state TEXT NOT NULL,
                    created REAL NOT NULL, deadline REAL NOT NULL,
                    steps INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    at REAL NOT NULL, kind TEXT NOT NULL
                );
            """)

    @contextlib.contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.database, timeout=5)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            try:
                with db:
                    yield db
            finally:
                db.close()

    def event(self, db, run_id: str, kind: str) -> None:
        db.execute("INSERT INTO events(run_id,at,kind) VALUES(?,?,?)",
                   (run_id, self.clock(), kind))

    def transition(self, db, run_id: str, state: str) -> None:
        db.execute("UPDATE runs SET state=? WHERE id=?", (state, run_id))
        self.event(db, run_id, state)

    def expire(self, db) -> None:
        placeholders = ",".join("?" for _ in ACTIVE)
        rows = db.execute(
            f"SELECT id FROM runs WHERE state IN ({placeholders}) AND deadline<=?",
            (*ACTIVE, self.clock()),
        ).fetchall()
        for row in rows:
            self.transition(db, row["id"], "EXPIRED")

    def recover(self) -> None:
        """Never automatically relaunch work after a controller restart."""
        with self.connection() as db:
            self.expire(db)
            rows = db.execute(
                "SELECT id FROM runs WHERE state IN ('QUEUED','RUNNING')"
            ).fetchall()
            for row in rows:
                self.transition(db, row["id"], "INTERRUPTED")

    def launch(self, value: object, key: str) -> dict:
        spec = validate_spec(value)
        if (type(key) is not str or not 16 <= len(key) <= 80
                or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in key)):
            raise Rejected("invalid_idempotency_key")
        canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
        with self.connection() as db:
            self.expire(db)
            existing = db.execute(
                "SELECT * FROM runs WHERE request_key=?", (key,)
            ).fetchone()
            if existing:
                if existing["spec"] != canonical:
                    raise Rejected("idempotency_key_conflict", 409)
                return self.project(db, existing)
            count = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            if count >= 1000:
                raise Rejected("local_history_capacity_reached", 409)
            live = db.execute(
                "SELECT COUNT(*) FROM runs WHERE state IN ('QUEUED','RUNNING','PAUSED','INTERRUPTED')"
            ).fetchone()[0]
            if live >= 4:
                raise Rejected("active_run_limit", 409)
            run_id = uuid.uuid4().hex
            now = self.clock()
            db.execute(
                "INSERT INTO runs(id,request_key,spec,state,created,deadline) VALUES(?,?,?,?,?,?)",
                (run_id, key, canonical, "QUEUED", now, now + spec["max_seconds"]),
            )
            self.event(db, run_id, "QUEUED")
            return self.project(db, self.row(db, run_id))

    @staticmethod
    def row(db, run_id: str):
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise Rejected("run_not_found", 404)
        return row

    def control(self, run_id: str, action: str) -> dict:
        with self.connection() as db:
            self.expire(db)
            row = self.row(db, run_id)
            state = row["state"]
            if action == "stop" and state == "STOPPED":
                return self.project(db, row)
            if action == "pause" and state == "PAUSED":
                return self.project(db, row)
            if action == "resume" and state in ("QUEUED", "RUNNING"):
                return self.project(db, row)
            allowed = {
                "stop": (ACTIVE, "STOPPED"),
                "pause": (("QUEUED", "RUNNING"), "PAUSED"),
                "resume": (("PAUSED", "INTERRUPTED"), "QUEUED"),
            }
            if action not in allowed:
                raise Rejected("unknown_control")
            states, target = allowed[action]
            if state not in states:
                raise Rejected("invalid_state_transition", 409)
            self.transition(db, run_id, target)
            return self.project(db, self.row(db, run_id))

    def tick(self) -> None:
        """Advance fixture counters only. These are not training experiments."""
        with self.connection() as db:
            self.expire(db)
            rows = db.execute(
                "SELECT * FROM runs WHERE state IN ('QUEUED','RUNNING')"
            ).fetchall()
            for row in rows:
                run_id = row["id"]
                if row["state"] == "QUEUED":
                    self.transition(db, run_id, "RUNNING")
                steps = row["steps"] + 1
                db.execute("UPDATE runs SET steps=? WHERE id=?", (steps, run_id))
                self.event(db, run_id, f"REHEARSAL_STEP_{steps}")
                if steps >= json.loads(row["spec"])["max_steps"]:
                    self.transition(db, run_id, "COMPLETED")

    @staticmethod
    def project(db, row) -> dict:
        events = db.execute(
            "SELECT seq,at,kind FROM events WHERE run_id=? ORDER BY seq", (row["id"],)
        ).fetchall()
        return {
            "schema": SCHEMA, "id": row["id"], "state": row["state"],
            "spec": json.loads(row["spec"]), "created": row["created"],
            "deadline": row["deadline"], "steps": row["steps"],
            "evidence": "CONTROLLER_REHEARSAL_ONLY", "external_spend_cents": 0,
            "scientific_result": None, "submission_receipt": None,
            "events": [dict(event) for event in events],
        }

    def get(self, run_id: str) -> dict:
        with self.connection() as db:
            self.expire(db)
            return self.project(db, self.row(db, run_id))

    def recent(self) -> list:
        with self.connection() as db:
            self.expire(db)
            rows = db.execute("SELECT * FROM runs ORDER BY created DESC,id DESC LIMIT 50").fetchall()
            return [self.project(db, row) for row in rows]


def capability_catalog() -> dict:
    return {
        "schema": SCHEMA, "mode": "REHEARSAL", "launch_enabled": True,
        "supported": CHOICES,
        "limits": {"active_runs": 4, "max_steps": 100, "max_seconds": 600},
        "unavailable": [
            {"id": "carbon-burgers-development", "reason": "research_bridge_not_implemented"},
            {"id": "hermes", "reason": "adapter_not_implemented"},
            {"id": "personal-agent", "reason": "authenticated_mcp_bridge_not_implemented"},
            {"id": "mira", "reason": "integration_interface_unverified"},
            {"id": "chutes", "reason": "authorization_and_billing_adapter_not_implemented"},
            {"id": "lium", "reason": "provisioning_and_teardown_adapter_not_implemented"},
            {"id": "engy", "reason": "inference_adapter_not_implemented"},
            {"id": "testnet-registration", "reason": "wallet_adapter_and_transaction_authority_required"},
        ],
    }


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, controller: Controller, token: str, port: int = 8788):
        if len(token) < 32:
            raise ValueError("A generated local session token is required")
        self.controller = controller
        self.token = token
        self.assets = Path(__file__).parent
        super().__init__(("127.0.0.1", port), Handler)
        self.authority = f"127.0.0.1:{self.server_port}"
        self.origin = f"http://{self.authority}"

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(3)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        """Do not log headers, tokens, payloads or browser-supplied paths."""

    def reply(self, status: int, value, content_type="application/json") -> None:
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def check(self, authenticated=False) -> None:
        if self.headers.get_all("Host") != [self.server.authority]:
            raise Rejected("invalid_host", 403)
        origins = self.headers.get_all("Origin")
        if origins is not None and origins != [self.server.origin]:
            raise Rejected("cross_origin_denied", 403)
        if authenticated:
            expected = "Bearer " + self.server.token
            headers = self.headers.get_all("Authorization")
            if (headers is None or len(headers) != 1
                    or not hmac.compare_digest(headers[0].encode(), expected.encode())):
                raise Rejected("authentication_required", 401)

    def do_GET(self):
        try:
            self.check()
            if self.path in STATIC:
                name, content_type = STATIC[self.path]
                self.reply(200, (self.server.assets / name).read_bytes(), content_type)
                return
            self.check(authenticated=True)
            if self.path == "/api/v1/capabilities":
                self.reply(200, capability_catalog())
            elif self.path == "/api/v1/runs":
                self.reply(200, {"runs": self.server.controller.recent()})
            elif self.path.startswith("/api/v1/runs/"):
                self.reply(200, self.server.controller.get(self.path[13:]))
            else:
                raise Rejected("not_found", 404)
        except Rejected as exc:
            self.reply(exc.status, {"error": exc.code})
        except (OSError, sqlite3.Error):
            self.reply(503, {"error": "local_infrastructure_unavailable"})

    def do_POST(self):
        try:
            self.check(authenticated=True)
            if self.headers.get("Transfer-Encoding") is not None:
                raise Rejected("unsupported_transfer_encoding")
            lengths = self.headers.get_all("Content-Length")
            if lengths is None or len(lengths) != 1 or not lengths[0].isdigit():
                raise Rejected("invalid_content_length")
            length = int(lengths[0])
            if length < 2 or length > 4096:
                raise Rejected("body_size_limit", 413)
            if self.headers.get_content_type() != "application/json":
                raise Rejected("json_required", 415)
            body = self.rfile.read(length)
            if len(body) != length:
                raise Rejected("incomplete_body")
            value = parse_json(body)
            if self.path == "/api/v1/runs":
                keys = self.headers.get_all("Idempotency-Key")
                if keys is None or len(keys) != 1:
                    raise Rejected("idempotency_key_required")
                result = self.server.controller.launch(value, keys[0])
            else:
                parts = self.path.split("/")
                if len(parts) != 6 or parts[1:4] != ["api", "v1", "runs"]:
                    raise Rejected("not_found", 404)
                if value != {} or type(value) is not dict:
                    raise Rejected("control_body_must_be_empty_object")
                result = self.server.controller.control(parts[4], parts[5])
            self.reply(200, result)
        except Rejected as exc:
            self.reply(exc.status, {"error": exc.code})
        except (OSError, sqlite3.Error):
            self.reply(503, {"error": "local_infrastructure_unavailable"})


@contextlib.contextmanager
def owner_lock(directory: Path):
    """Linux/macOS single-owner lock; no public-host or Windows fallback."""
    import fcntl
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink():
        raise RuntimeError("State directory must not be a symlink")
    directory.chmod(0o700)
    path = directory / "owner.lock"
    if path.is_symlink():
        raise RuntimeError("Lock path must not be a symlink")
    with path.open("a") as handle:
        path.chmod(0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another launcher owns this state directory") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".carbon" / "development-launchpad")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged port between 1024 and 65535")
    with owner_lock(args.state_dir):
        database = args.state_dir / "runs.sqlite3"
        if database.is_symlink():
            raise RuntimeError("Database must not be a symlink")
        controller = Controller(database)
        database.chmod(0o600)
        token = secrets.token_urlsafe(32)
        server = Server(controller, token, args.port)
        controller.recover()
        done = threading.Event()

        def worker():
            while not done.wait(1):
                try:
                    controller.tick()
                except (OSError, sqlite3.Error):
                    # Preserve evidence; do not relaunch or erase failed state.
                    done.set()
                    server.shutdown()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        print(f"Carbon DEVELOPMENT controller rehearsal: {server.origin}")
        print(f"Local session token (paste into page; do not share): {token}")
        print("No agents, paid compute, training, registration, or submissions.")
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            done.set()
            thread.join(timeout=3)
            server.server_close()


if __name__ == "__main__":
    main()

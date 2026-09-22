"""Local DEVELOPMENT launcher rehearsal. No agent, chain, or provider execution.

Run with Python 3.11: python scripts/dev/miner_launchpad/controller.py
This controller owns launcher runs, not Carbon's scientific submission lifecycle.
"""

from __future__ import annotations

import argparse
import contextlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


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
        db.execute(
            "INSERT INTO events(run_id,at,kind) VALUES(?,?,?)",
            (run_id, self.clock(), kind),
        )

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
        if (
            type(key) is not str
            or not 16 <= len(key) <= 80
            or any(
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                for c in key
            )
        ):
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
            "schema": SCHEMA,
            "id": row["id"],
            "state": row["state"],
            "spec": json.loads(row["spec"]),
            "created": row["created"],
            "deadline": row["deadline"],
            "steps": row["steps"],
            "evidence": "CONTROLLER_REHEARSAL_ONLY",
            "external_spend_cents": 0,
            "scientific_result": None,
            "submission_receipt": None,
            "events": [dict(event) for event in events],
        }

    def get(self, run_id: str) -> dict:
        with self.connection() as db:
            self.expire(db)
            return self.project(db, self.row(db, run_id))

    def recent(self) -> list:
        with self.connection() as db:
            self.expire(db)
            rows = db.execute(
                "SELECT * FROM runs ORDER BY created DESC,id DESC LIMIT 50"
            ).fetchall()
            return [self.project(db, row) for row in rows]


def research_compute_choices() -> list:
    """Where a miner may run their own research, and what each actually needs.

    Destinations, not a provider dropdown. Carbon has no per-provider branch:
    what differs between a laptop, a workstation and a rented instance lives in
    the host device record the operator installs, which carries the provider as
    a token and nothing else. So `attach-existing-remote` is not a separate
    integration - it is the same path with the record written on that host.

    Provisioning a host *for* a miner is a different thing, and none is
    implemented. Those stay in `unavailable` with the reason each is missing,
    rather than appearing here as choices that would fail when selected.
    """
    from carbon.development_session.exam_environment import exam_environment

    graded_on = exam_environment()["backend_profile"]["profile_id"]
    return [
        {
            "id": "local-cpu",
            "available": True,
            "requires": ["CONTAINER_DAEMON", "PINNED_CPU_WORKER_IMAGE"],
            "summary": "This machine, CPU only. No accelerator record needed.",
        },
        {
            "id": "local-gpu",
            "available": True,
            "requires": [
                "INSTALLED_HOST_DEVICE_RECORD_COMPATIBLE_WITH_THE_GPU_PROFILE",
                "CONTAINER_DEVICE_RUNTIME",
                "PINNED_GPU_WORKER_IMAGE",
            ],
            "not_required": [
                # Carbon approves nobody's access to their own GPU.
                "CAMPAIGN_GRANT_DECLARING_GPU_RESEARCH",
                "STRICT_HOST_GRANT",
                "WHOLE_DEVICE_EXCLUSIVITY",
                "COMPUTE_PROCESS_ENUMERATION",
                "DISPLAY_DISABLED_ON_THE_DEVICE",
            ],
            "summary": "This machine's GPU, on the miner lane. It may be driving your display or shared with your own work.",
        },
        {
            "id": "attach-existing-remote",
            "available": True,
            "requires": [
                "A_HOST_YOU_ALREADY_CONTROL",
                "CARBON_ACCELERATOR_PREPARE_RUN_ON_THAT_HOST",
            ],
            "not_required": ["CARBON_HELD_PROVIDER_CREDENTIALS"],
            "summary": "A compatible machine you already have, anywhere. Carbon does not provision or bill it, and never terminates a resource this campaign does not own.",
        },
        {
            "id": "external-byo",
            "available": True,
            "requires": [],
            "summary": "Research entirely off-platform with any tools and compute you like, then submit a strategy. Carbon neither meters nor certifies it, and no Carbon-run training job is required to submit.",
        },
        {
            "id": "graded-on",
            "available": False,
            "selectable": False,
            "reason": "not_a_research_destination",
            "profile_id": graded_on,
            "summary": "What the validator runs the exam under. Shown so you can read it; it is not a compute choice and your research runtime does not change it.",
        },
    ]


def _default_onboarding():
    """A browser door onto the shared service, with no chain configured.

    Kept absent rather than invented: `requirements` answers without a chain,
    and the reads say plainly that the operator configured no endpoint instead
    of guessing one.
    """
    from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

    return BrowserOnboarding()


def capability_catalog() -> dict:
    return {
        "schema": SCHEMA,
        "mode": "REHEARSAL",
        "launch_enabled": True,
        "supported": CHOICES,
        "limits": {"active_runs": 4, "max_steps": 100, "max_seconds": 600},
        # Readable without a configured research profile, a grant, a model key
        # or an agent identity. Inspecting what the exam runs on is not a step a
        # miner should have to buy their way into.
        "research_compute": research_compute_choices(),
        "unavailable": [
            {
                "id": "carbon-burgers-development",
                "reason": "research_bridge_not_implemented",
            },
            {"id": "hermes", "reason": "adapter_not_implemented"},
            {
                # Fourth revision of this reason, and the first three were all
                # wrong in ways worth not repeating: an absent bridge that
                # exists, a grant coupling that is only a stale docstring, and
                # an undecided authorization server that has since been decided
                # (CARBON-D-MCP-REMOTE-AUTH: Cloudflare Access is the issuer).
                #
                # What is actually left is the claim contract. Access emits no
                # `client_id` and no `scope`, both of which `verify_token`
                # requires; its `aud` is the application AUD tag rather than a
                # resource URL; its `sub` is empty for the service tokens a
                # programmatic caller uses, with the identity in `common_name`;
                # and its signing key rotates on a six-week cycle, which a key
                # set fixed at construction cannot follow.
                #
                # Scope note: this is the *remote* door only. A miner bringing
                # their own agent over stdio needs no Cloudflare credential and
                # nothing issued by Carbon, and can connect today.
                "id": "personal-agent",
                "reason": "access_assertion_claim_contract_not_implemented",
            },
            {"id": "mira", "reason": "integration_interface_unverified"},
            {
                "id": "chutes",
                "reason": "authorization_and_billing_adapter_not_implemented",
            },
            {
                "id": "lium",
                "reason": "provisioning_and_teardown_adapter_not_implemented",
            },
            {"id": "engy", "reason": "inference_adapter_not_implemented"},
            {
                # Two earlier reasons here were wrong in different ways. The
                # first named a signing wallet adapter, which the key rule
                # forbids and Carbon will never build: `chain_onboarding`
                # prepares an unsigned registration the miner executes in their
                # own tooling. The second named a missing chain endpoint, which
                # turned out to be settled already in
                # `carbon.development_testnet.operator` and merely unread by
                # these doors; both now default to it.
                #
                # What remains is not Carbon's to implement. A registration
                # spends the miner's own funds and is signed in their own
                # wallet, so the flow is complete and the execution is theirs.
                "id": "testnet-registration",
                "reason": "flow_implemented_execution_is_the_miners_own",
            },
        ],
    }


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        controller: Controller,
        token: str,
        port: int = 8788,
        *,
        development_sources=None,
        research_runner=None,
        onboarding=None,
    ):
        if len(token) < 32:
            raise ValueError("A generated local session token is required")
        self.controller = controller
        self.development_sources = development_sources
        self.research_runner = research_runner
        # Open tier: available without a research profile, a grant or a
        # registered hotkey, because onboarding exists for people who have none
        # of those yet.
        self.onboarding = onboarding or _default_onboarding()
        self.token = token
        self.assets = Path(__file__).parent
        self.request_slots = threading.BoundedSemaphore(16)
        super().__init__(("127.0.0.1", port), Handler)
        self.authority = f"127.0.0.1:{self.server_port}"
        self.origin = f"http://{self.authority}"

    def process_request(self, request, client_address):
        if not self.request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()

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
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
        )
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
            if (
                headers is None
                or len(headers) != 1
                or not hmac.compare_digest(headers[0].encode(), expected.encode())
            ):
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
            elif self.path == "/api/v1/onboarding/requirements":
                # Open tier. No campaign, no compute, no ledger.
                self.reply(200, self.server.onboarding.requirements())
            elif self.path == "/api/v1/exam-environment":
                # Available with no research profile, grant or agent configured.
                # A miner deciding whether to take part is entitled to read what
                # the exam runs on first.
                from carbon.development_session.exam_environment import (
                    exam_environment,
                )

                self.reply(200, exam_environment())
            elif self.path == "/api/v1/runs":
                self.reply(200, {"runs": self.server.controller.recent()})
            elif self.path == "/api/v1/development":
                sources = self.server.development_sources
                self.reply(200, {"sources": sources.recent() if sources else []})
            elif self.path == "/api/v1/research":
                runner = self.server.research_runner
                self.reply(
                    200,
                    {
                        "preflight": (
                            runner.preflight()
                            if runner
                            else {"available": False, "status": "ADMISSION_DISABLED"}
                        ),
                        "runs": runner.recent() if runner else [],
                    },
                )
            elif self.path.startswith("/api/v1/research/"):
                runner = self.server.research_runner
                if runner is None:
                    raise Rejected("research_admission_unavailable", 409)
                self.reply(200, runner.get(self.path.removeprefix("/api/v1/research/")))
            elif self.path.startswith("/api/v1/development/"):
                sources = self.server.development_sources
                if sources is None:
                    raise Rejected("development_source_unavailable", 404)
                try:
                    result = sources.get(self.path.removeprefix("/api/v1/development/"))
                except ValueError:
                    raise Rejected("development_source_unavailable", 404) from None
                self.reply(200, result)
            elif self.path.startswith("/api/v1/runs/"):
                self.reply(200, self.server.controller.get(self.path[13:]))
            else:
                raise Rejected("not_found", 404)
        except Rejected as exc:
            self.reply(exc.status, {"error": exc.code})
        except (OSError, sqlite3.Error):
            self.reply(503, {"error": "local_infrastructure_unavailable"})
        except ValueError:
            self.reply(409, {"error": "research_reconciliation_required"})

    def do_POST(self):
        try:
            self.check(authenticated=True)
            if self.headers.get("Transfer-Encoding") is not None:
                raise Rejected("unsupported_transfer_encoding")
            lengths = self.headers.get_all("Content-Length")
            if (
                lengths is None
                or len(lengths) != 1
                or not lengths[0].isascii()
                or not lengths[0].isdigit()
            ):
                raise Rejected("invalid_content_length")
            if len(lengths[0]) > 4:
                raise Rejected("body_size_limit", 413)
            length = int(lengths[0])
            if length < 2 or length > 4096:
                raise Rejected("body_size_limit", 413)
            if self.headers.get_content_type() != "application/json":
                raise Rejected("json_required", 415)
            body = self.rfile.read(length)
            if len(body) != length:
                raise Rejected("incomplete_body")
            value = parse_json(body)
            if self.path.startswith("/api/v1/onboarding/"):
                action = self.path.removeprefix("/api/v1/onboarding/")
                if action not in {"status", "prepare", "confirm"}:
                    raise Rejected("unknown_onboarding_action", 404)
                if type(value) is not dict or set(value) != {"address"}:
                    raise Rejected("closed_onboarding_request_required")
                from carbon.development_session.chain_onboarding import (
                    OnboardingFailure,
                )

                try:
                    result = getattr(self.server.onboarding, action)(value["address"])
                except OnboardingFailure as failure:
                    # Actionable and closed: a reason a client can branch on and
                    # the next usable step, never a provider message or a trace.
                    self.reply(409, failure.body())
                    return
            elif self.path == "/api/v1/research":
                runner = self.server.research_runner
                if runner is None:
                    raise Rejected("research_admission_unavailable", 409)
                keys = self.headers.get_all("Idempotency-Key")
                if keys is None or len(keys) != 1:
                    raise Rejected("idempotency_key_required")
                result = runner.launch(value, keys[0])
            elif self.path.startswith("/api/v1/research/"):
                parts = self.path.split("/")
                if len(parts) != 6 or value != {} or type(value) is not dict:
                    raise Rejected("invalid_research_control")
                runner = self.server.research_runner
                if runner is None:
                    raise Rejected("research_admission_unavailable", 409)
                result = runner.control(parts[4], parts[5])
            elif self.path == "/api/v1/runs":
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
        except (ValueError, RuntimeError):
            self.reply(409, {"error": "research_reconciliation_required"})


@contextlib.contextmanager
def owner_lock(directory: Path):
    """Nonblocking OS ownership lock; released by the OS on process exit.

    POSIX permissions are restrictive; on Windows the operator must use a
    private, user-owned state directory (chmod does not establish a Windows ACL).
    """
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink():
        raise RuntimeError("State directory must not be a symlink")
    directory.chmod(0o700)
    path = directory / "owner.lock"
    if path.is_symlink():
        raise RuntimeError("Lock path must not be a symlink")
    with path.open("a+b") as handle:
        path.chmod(0o600)
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)

            def acquire():
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

        else:
            import fcntl

            def acquire():
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(handle, fcntl.LOCK_UN)

        try:
            acquire()
        except OSError as exc:
            raise RuntimeError("Another launcher owns this state directory") from exc
        try:
            yield
        finally:
            release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument(
        "--research-profile",
        type=Path,
        help=(
            "Development only: a private operator configuration carrying a "
            "development grant, for Carbon's own bounded experiments. A miner "
            "needs no such record and no approval to use their own compute."
        ),
    )
    parser.add_argument(
        "--development-source",
        action="append",
        type=Path,
        default=[],
        help="Attach an existing private Carbon source handoff for verified public readback; no dispatch",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path.home() / ".carbon" / "development-launchpad",
    )
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
        # Direct-script and package entry points resolve one canonical module.
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        sys.modules.setdefault(
            "scripts.dev.miner_launchpad.controller", sys.modules[__name__]
        )
        from scripts.dev.miner_launchpad.development import DevelopmentSources

        sources = DevelopmentSources(database)
        for path in args.development_source:
            try:
                sources.attach(path)
            except Exception:  # noqa: BLE001 - do not print private source errors.
                parser.error("DEVELOPMENT source attachment failed verification")
        runner = None
        if args.research_profile is not None:
            from scripts.dev.miner_launchpad.runner import RunnerAdapter

            runner = RunnerAdapter(database, configuration=args.research_profile)
        server = Server(
            controller,
            token,
            args.port,
            development_sources=sources,
            research_runner=runner,
        )
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
        print(
            "Research requires a separate approved operator profile and accepted runtime."
            if runner
            else "No agents, paid compute, training, registration, or submissions."
        )
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            done.set()
            if runner is not None:
                runner.close()
            thread.join(timeout=3)
            server.server_close()


if __name__ == "__main__":
    main()

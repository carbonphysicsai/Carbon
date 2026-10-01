"""The battery submission intake: how a miner's machine reaches the validator.

OD-7(b). A miner signs a `battery_submit` message with its own hotkey, in its
own tooling, and POSTs it here. The intake authenticates it through the same
NET-2 gateway the in-process campaign path uses, records it durably, answers
at once with its submission id, and a single worker admits and evaluates it
through the deployment's one daemon. There is still exactly one evaluation
path (`deployment`); the intake only carries submissions to it.

**The mainnet shape.** Bittensor v11 has no Axon/Dendrite stack: a subnet
runs its own HTTP server and authenticates callers with `btauth/1`
(`bittensor.http_auth`), which is what NET-2 already verifies. A validator may
publish its endpoint on chain (`serve_axon`) when the subnet needs validators
to be reachable. So each validator image runs this intake with `receiver` set
to its own hotkey, and a signed request is bound to exactly one validator. On
testnet one validator runs it on the owner's host.

**Routes** (nothing else is served):

- `GET /carbon/v1/battery/intake`: the public facts a miner needs to build a
  message - network, genesis, netuid, Challenge, receiver hotkey and the
  current validator-observed snapshot id. No private state.
- `POST /carbon/v1/mcp`: one signed NET-2 message, tool `battery_submit`
  (202, with the submission id) or `battery_status` (the miner's own
  allow-listed outcome; another hotkey's submission is `not_found`).

**Limits before authentication.** A per-peer token bucket, a global in-flight
cap and a body limit apply before any signature is checked, and the envelope's
snapshot must be one this intake already observed: **no request causes a chain
read.** One refresher thread reads the metagraph on a fixed period.

**Exposure.** The listener binds loopback unless the configuration names an
exposure record that exists in `.agent/DECISIONS.md` - the owner's §4 security
review decision for this intake, an id of the form
`OWNER-…INTAKE-EXPOSURE-NN`. Tests are not a security audit; this module
is security-sensitive (AGENTS §13) and is NOT SECURITY_QUALIFIED.

Nothing here scores, qualifies, commits on chain or signs with a key: the
miner signs; the service key, if configured, belongs to the daemon.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import re
import sqlite3
import ssl
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from carbon.transport.models import (
    MAX_BODY,
    PATH,
    TransportCode,
    TransportFailure,
    parse_message,
)

SCHEMA = "carbon.battery.intake.v1"
PUBLIC_SCHEMA = "carbon.battery.intake-public.v1"
INFO_PATH = "/carbon/v1/battery/intake"
STATUS_TOOL = "battery_status"
REQUIRED = {"schema", "deployment", "transport_journal", "inbox", "receiver"}
OPTIONAL = {"host", "port", "exposure_record", "tls_cert", "tls_key"}

#: Engineering abuse limits, not scientific values. Per peer: a burst of 10,
#: refilled at 1 request per second. At most 8 requests in flight, and at most
#: 64 received submissions waiting for admission.
PEER_BURST, PEER_RATE, IN_FLIGHT, INBOX_DEPTH = 10, 1.0, 8, 64
#: The metagraph is re-read on this period; a snapshot older than the
#: gateway's 60 s window can no longer authenticate anything.
REFRESH_S, SNAPSHOTS_KEPT, SNAPSHOT_MAX_AGE_S = 12.0, 5, 60.0
SOCKET_TIMEOUT_S = 10.0
EXPOSURE_RECORD = r"OWNER-[A-Z0-9-]*INTAKE-EXPOSURE-[0-9]{2}"

_TERMINAL = {
    "SCORED",
    "INVALID_CONSTRUCTION",
    "RECONSTRUCTION_FAILED",
    "FAILED_INFRA_EXHAUSTED",
}


class IntakeUnavailable(RuntimeError):
    """The intake cannot start: an operator configuration state."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Answer:
    status: int
    body: dict


def _refused(status, code):
    return Answer(status, {"refused": code})


# --- configuration --------------------------------------------------------------


def load_config(path, *, repository):
    """An owner-only intake configuration, checked before anything listens."""
    from .deployment import EvaluationUnavailable, _private

    try:
        config = json.loads(_private(path).read_bytes())
    except EvaluationUnavailable as refused:
        raise IntakeUnavailable("intake_" + refused.code) from None
    if type(config) is not dict or config.get("schema") != SCHEMA:
        raise IntakeUnavailable("intake_config_schema")
    if not REQUIRED <= set(config) or set(config) - REQUIRED - OPTIONAL:
        raise IntakeUnavailable("intake_config_fields")
    config.setdefault("host", "127.0.0.1")
    config.setdefault("port", 8467)
    config.setdefault("exposure_record", None)
    if type(config["port"]) is not int or not 1 <= config["port"] <= 65535:
        raise IntakeUnavailable("intake_config_fields")
    if ("tls_cert" in config) != ("tls_key" in config):
        raise IntakeUnavailable("intake_config_tls")
    require_exposure(config, repository=repository)
    return config


def require_exposure(config, *, repository):
    """A non-loopback bind needs the owner's recorded exposure decision.

    Only the owner's §4 security review decision may make this host reachable
    from outside, so a public bind names that record and the record must be in
    `.agent/DECISIONS.md` as a heading. Loopback needs no record.
    """
    try:
        loopback = ipaddress.ip_address(config["host"]).is_loopback
    except ValueError:
        loopback = config["host"] == "localhost"
    if loopback:
        return
    record = config.get("exposure_record")
    # Only a record made for this purpose counts: any other owner decision,
    # including the one that chose the intake, never exposes it.
    if type(record) is not str or not re.fullmatch(EXPOSURE_RECORD, record):
        raise IntakeUnavailable("intake_exposure_unrecorded")
    decisions = (Path(repository) / ".agent" / "DECISIONS.md").read_text()
    if not re.search(rf"^## .*\b{re.escape(record)}\b", decisions, re.MULTILINE):
        raise IntakeUnavailable("intake_exposure_unrecorded")


# --- snapshots ------------------------------------------------------------------


class SnapshotWindow:
    """The last few metagraph snapshots this intake itself observed.

    A request names the snapshot it was built against; the intake accepts it
    only if it is one of these. The gateway still enforces its own 60 s
    freshness and the journal's monotone block, so an old snapshot is refused
    there; this window only makes sure no request can cause a chain read.
    """

    def __init__(self, *, clock=time.time):
        self._lock = threading.Lock()
        self._kept = []
        self.clock = clock

    def add(self, snapshot):
        with self._lock:
            if all(s.snapshot_id != snapshot.snapshot_id for s in self._kept):
                self._kept.append(snapshot)
                self._kept = self._kept[-SNAPSHOTS_KEPT:]

    def get(self, snapshot_id):
        with self._lock:
            return next((s for s in self._kept if s.snapshot_id == snapshot_id), None)

    def latest(self):
        with self._lock:
            if not self._kept:
                return None
            snapshot = self._kept[-1]
        if self.clock() - snapshot.timestamp_ms / 1000 > SNAPSHOT_MAX_AGE_S:
            return None
        return snapshot


class _Pinned:
    """A gateway adapter that returns the one snapshot a request named."""

    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def observe(self, *, minimum_finalized_block):
        if self.snapshot.finalized_block < minimum_finalized_block:
            raise TransportFailure(TransportCode.STALE)
        return self.snapshot


def refresher(window, context, *, reader=None, period=REFRESH_S, stop=None):
    """Read the metagraph every `period` seconds until `stop` is set.

    A failed read keeps the previous snapshots; once they age out, the intake
    answers `snapshot_unavailable` - an infrastructure state, never a refusal
    of the miner.
    """
    from carbon.chain.sdk import BittensorReader

    reader = BittensorReader() if reader is None else reader
    stop = threading.Event() if stop is None else stop
    while not stop.is_set():
        with contextlib.suppress(Exception):
            window.add(asyncio.run(reader.capture(context)))
        stop.wait(period)


# --- limits ---------------------------------------------------------------------


class PeerLimits:
    """Token buckets per peer address plus a global in-flight cap."""

    def __init__(self, *, burst=PEER_BURST, rate=PEER_RATE, clock=time.monotonic):
        self._lock = threading.Lock()
        self._buckets = {}
        self._flight = threading.BoundedSemaphore(IN_FLIGHT)
        self.burst, self.rate, self.clock = burst, rate, clock

    def allow(self, peer):
        now = self.clock()
        with self._lock:
            tokens, then = self._buckets.get(peer, (self.burst, now))
            tokens = min(self.burst, tokens + (now - then) * self.rate)
            if len(self._buckets) > 4096:
                self._buckets.clear()
            if tokens < 1:
                self._buckets[peer] = (tokens, now)
                return False
            self._buckets[peer] = (tokens - 1, now)
            return True

    @contextlib.contextmanager
    def in_flight(self):
        if not self._flight.acquire(blocking=False):
            yield False
            return
        try:
            yield True
        finally:
            self._flight.release()


# --- the durable inbox ----------------------------------------------------------


class Inbox:
    """Authenticated submissions waiting for, or past, admission.

    Validator-private: it holds recipes and hotkeys, never a case or seed.
    States: RECEIVED (authenticated, not yet admitted), ADMITTED (the daemon
    owns it from here), REFUSED (admission refused it for a named reason).
    """

    def __init__(self, path):
        self.path = Path(path)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS inbox (
                  submission_id TEXT PRIMARY KEY,
                  hotkey TEXT NOT NULL,
                  document TEXT NOT NULL,
                  received_ns INTEGER NOT NULL,
                  state TEXT NOT NULL
                    CHECK(state IN ('RECEIVED','ADMITTED','REFUSED')),
                  failure TEXT
                );
                """)
        self.path.chmod(0o600)

    @contextlib.contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            yield db
        finally:
            db.close()

    def receive(self, submission_id, submission, now_ns):
        """Record one submission once; a resend is the same submission."""
        document = json.dumps(
            {
                "hotkey": submission.hotkey,
                "receipt": submission.receipt,
                "challenge_id": submission.challenge_id,
                "challenge_version": submission.challenge_version,
                "strategy": submission.strategy,
                "contract_digest": submission.contract_digest,
            },
            sort_keys=True,
        )
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            waiting = db.execute(
                "SELECT COUNT(*) FROM inbox WHERE state='RECEIVED'"
            ).fetchone()[0]
            known = db.execute(
                "SELECT 1 FROM inbox WHERE submission_id=?", (submission_id,)
            ).fetchone()
            if known is None and waiting >= INBOX_DEPTH:
                db.execute("ROLLBACK")
                return False
            if known is None:
                db.execute(
                    "INSERT INTO inbox VALUES(?,?,?,?,'RECEIVED',NULL)",
                    (submission_id, submission.hotkey, document, now_ns),
                )
            db.execute("COMMIT")
        return True

    def row(self, submission_id):
        with self._db() as db:
            found = db.execute(
                "SELECT hotkey, state, failure FROM inbox WHERE submission_id=?",
                (submission_id,),
            ).fetchone()
        if found is None:
            return None
        return {
            "hotkey": found[0],
            "state": found[1],
            "failure": None if found[2] is None else json.loads(found[2]),
        }

    def received(self):
        from .daemon import AuthenticatedSubmission

        with self._db() as db:
            rows = db.execute(
                "SELECT submission_id, document FROM inbox WHERE state='RECEIVED' "
                "ORDER BY received_ns, submission_id"
            ).fetchall()
        return [(sid, AuthenticatedSubmission(**json.loads(doc))) for sid, doc in rows]

    def admitted(self):
        with self._db() as db:
            return [
                sid
                for (sid,) in db.execute(
                    "SELECT submission_id FROM inbox WHERE state='ADMITTED' "
                    "ORDER BY received_ns, submission_id"
                ).fetchall()
            ]

    def mark(self, submission_id, state, failure=None):
        with self._db() as db:
            db.execute(
                "UPDATE inbox SET state=?, failure=? WHERE submission_id=?",
                (
                    state,
                    None if failure is None else json.dumps(failure, sort_keys=True),
                    submission_id,
                ),
            )


# --- the intake -----------------------------------------------------------------


class BatteryIntake:
    """Framework-free request handling; `serve` puts it behind HTTP."""

    def __init__(
        self,
        *,
        context,
        receiver,
        journal,
        verifier,
        inbox,
        window,
        status_reader,
        limits=None,
        clock_ns=time.time_ns,
    ):
        from .challenge import CHALLENGE

        self.context = context
        self.challenge = CHALLENGE
        self.receiver = receiver
        self.journal = journal
        self.verifier = verifier
        self.inbox = inbox
        self.window = window
        self.status_reader = status_reader
        self.limits = PeerLimits() if limits is None else limits
        self.clock_ns = clock_ns
        self.wake = threading.Event()

    def public(self):
        snapshot = self.window.latest()
        if snapshot is None:
            return _refused(503, "snapshot_unavailable")
        return Answer(
            200,
            {
                "schema": PUBLIC_SCHEMA,
                "network": self.context.network,
                "genesis": self.context.genesis_hash,
                "netuid": self.context.netuid,
                "challenge": {
                    "id": self.challenge.challenge_id,
                    "version": self.challenge.version,
                },
                "receiver": self.receiver,
                "snapshot": {
                    "id": snapshot.snapshot_id,
                    "finalized_block": snapshot.finalized_block,
                    "timestamp_ms": snapshot.timestamp_ms,
                },
                "path": PATH,
                "tools": ["battery_submit", STATUS_TOOL],
                "limits": {
                    "max_body": MAX_BODY,
                    "snapshot_max_age_s": SNAPSHOT_MAX_AGE_S,
                    "signature_max_age_s": 10.0,
                },
                "commitment": "not_checked: no chain commitment reader exists (OD-7(a))",
                "qualification": False,
                "reward": False,
            },
        )

    def handle(self, method, path, headers, body, peer):
        """One request in, one `Answer` out. Never raises for a miner input."""
        return self.limited(peer, lambda: self.route(method, path, headers, body))

    def limited(self, peer, then):
        """The peer's bucket, then the in-flight cap, then `then()`.

        Nothing reads a body, parses a message or checks a signature before
        both limits have admitted the request.
        """
        if not self.limits.allow(peer):
            return _refused(429, "rate")
        with self.limits.in_flight() as admitted:
            if not admitted:
                return _refused(503, "capacity")
            return then()

    def route(self, method, path, headers, body):
        if method == "GET" and path == INFO_PATH:
            return self.public()
        if method != "POST" or path != PATH:
            return _refused(404, "not_found")
        return asyncio.run(self._post(headers, body))

    async def _post(self, headers, body):
        from carbon.chain.auth import AuthFailure
        from carbon.transport.gateway import AuthenticatedGateway

        from .daemon import SUBMIT_TOOL, AuthenticatedSubmission, submission_identity

        try:
            envelope = parse_message(body)
        except TransportFailure as failure:
            return _refused(400, failure.code.value)
        snapshot = self.window.get(envelope["snapshot"])
        if snapshot is None:
            return _refused(409, "snapshot_unknown")
        gateway = AuthenticatedGateway(
            self.context,
            self.challenge,
            self.receiver,
            _Pinned(snapshot),
            self.verifier,
            self.journal,
            clock_ns=self.clock_ns,
        )
        try:
            received = await gateway.receive(body, headers)
        except TransportFailure as failure:
            return _refused(
                401 if failure.code is TransportCode.IDENTITY else 400,
                failure.code.value,
            )
        except AuthFailure as failure:
            return _refused(401, failure.code.value)
        hotkey = received.receipt.hotkey
        if received.call.tool == SUBMIT_TOOL:
            try:
                submission = AuthenticatedSubmission.from_received(received, gateway)
            except (ValueError, TypeError):
                return _refused(400, "submission_fields")
            _, submission_id = submission_identity(submission)
            if not self.inbox.receive(submission_id, submission, self.clock_ns()):
                return _refused(503, "inbox_full")
            self.wake.set()
            return Answer(202, {"submission_id": submission_id, "state": "RECEIVED"})
        if received.call.tool == STATUS_TOOL:
            fields = {f.name: f.value for f in received.call.fields}
            if (
                set(fields) != {"submission_id"}
                or type(fields["submission_id"]) is not str
            ):
                return _refused(400, "status_fields")
            return self.status(hotkey, fields["submission_id"])
        return _refused(400, "tool")

    def status(self, hotkey, submission_id):
        """The caller's own submission only; anyone else's does not exist."""
        row = self.inbox.row(submission_id)
        if row is None or row["hotkey"] != hotkey:
            return _refused(404, "not_found")
        if row["state"] == "RECEIVED":
            return Answer(200, {"submission_id": submission_id, "state": "RECEIVED"})
        if row["state"] == "REFUSED":
            return Answer(
                200,
                {"submission_id": submission_id, "state": "REFUSED", **row["failure"]},
            )
        return Answer(200, self.status_reader(submission_id))


# --- the worker -----------------------------------------------------------------


def work_once(inbox, target):
    """Admit every received submission, then advance every admitted one.

    Each daemon call holds the deployment's single-writer lock for its own
    duration only. An infrastructure state leaves the submission where it
    was, to be retried; it is never a refusal of the miner.
    """
    from .daemon import CommitmentRequired
    from .deployment import writer

    for submission_id, submission in inbox.received():
        try:
            with writer(target):
                target.admit(submission)
        except CommitmentRequired:
            code = (
                "commitment_reader_unavailable"
                if target.commitments is None
                else "commitment_required"
            )
            inbox.mark(submission_id, "REFUSED", {"failure": {"code": code}})
            continue
        inbox.mark(submission_id, "ADMITTED")
    for submission_id in inbox.admitted():
        with writer(target):
            if target.outcome(submission_id)["state"] not in _TERMINAL:
                target.process(submission_id)
    with writer(target):
        target.run_pending()


def worker(inbox, target, wake, *, stop, idle_s=30.0):
    import sys

    while not stop.is_set():
        wake.clear()
        try:
            work_once(inbox, target)
        except Exception as failure:  # noqa: BLE001
            # Infrastructure: the inbox keeps every submission for the next
            # pass. Only the exception's type is logged, never its content.
            print(f"intake worker: {type(failure).__name__}", file=sys.stderr)
        wake.wait(idle_s)


# --- HTTP -----------------------------------------------------------------------


def _handler(intake):
    class Handler(BaseHTTPRequestHandler):
        server_version = "carbon-battery-intake"
        sys_version = ""
        timeout = SOCKET_TIMEOUT_S

        def _answer(self, answer):
            payload = json.dumps(answer.body, sort_keys=True).encode()
            self.send_response(answer.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)

        def _dispatch(self, method):
            # The declared length is checked and the limits applied before a
            # single body byte is read.
            length = "0"
            if method == "POST":
                length = self.headers.get("Content-Length")
                if length is None or not length.isdigit() or int(length) > MAX_BODY:
                    return self._answer(_refused(413, "body"))
            self._answer(
                intake.limited(
                    self.client_address[0], lambda: self._route(method, length)
                )
            )

        def _route(self, method, length):
            body = self.rfile.read(int(length)) if method == "POST" else b""
            headers = {k: v for k, v in self.headers.items()}
            if len(headers) != len(self.headers.items()):
                return _refused(400, "headers")
            return intake.route(method, self.path, headers, body)

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def log_message(self, *_args):
            # Paths and addresses only would still be a peer log; keep none.
            return

    return Handler


def serve(config_path, *, repository, stop=None):
    """Run the intake: refresher, worker and listener, until `stop` is set."""
    from carbon.chain.auth import BittensorHotkeyVerifier
    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.transport.store import ReceiptJournal

    from . import deployment

    config = load_config(config_path, repository=repository)
    context = carbon_testnet_context()
    target = deployment.validator(config["deployment"], repository=repository)
    reader = deployment.validator(
        config["deployment"], repository=repository, readonly=True
    )
    inbox = Inbox(config["inbox"])
    window = SnapshotWindow()
    intake = BatteryIntake(
        context=context,
        receiver=config["receiver"],
        journal=ReceiptJournal(Path(config["transport_journal"]), context),
        verifier=BittensorHotkeyVerifier(),
        inbox=inbox,
        window=window,
        status_reader=reader.outcome,
    )
    stop = threading.Event() if stop is None else stop
    threads = [
        threading.Thread(
            target=refresher, args=(window, context), kwargs={"stop": stop}, daemon=True
        ),
        threading.Thread(
            target=worker,
            args=(inbox, target, intake.wake),
            kwargs={"stop": stop},
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    httpd = ThreadingHTTPServer((config["host"], config["port"]), _handler(intake))
    if "tls_cert" in config:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(config["tls_cert"], config["tls_key"])
        httpd.socket = tls.wrap_socket(httpd.socket, server_side=True)
    try:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        stop.wait()
    finally:
        httpd.shutdown()
        httpd.server_close()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="carbon.battery.intake")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("serve")
    run.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    try:
        serve(args.config, repository=repository)
    except IntakeUnavailable as refused:
        print(json.dumps({"unavailable": refused.code}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

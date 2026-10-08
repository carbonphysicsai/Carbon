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

**The neutral door** (VALIDATOR-01 VAL-D3). An authenticated `battery_submit`
passes Carbon's challenge-neutral checks before anything is queued
(`carbon.challenge_validator.Validator.screen`). The strategy must be strict
JSON naming battery, under a contract digest this validator serves. A refusal
is answered at once by its closed code (`dispatch.SCREEN_REFUSALS`, 400) and is
never queued, evaluated or counted against the hotkey's window. Every attempt
is recorded in the operator's attempt ledger: refused, received, or refused for
the window or a full inbox. The ledger keeps the submission's hash, never its
strategy, and sits beside the inbox unless `attempt_ledger` names another path
in an owner-only directory.

This changes one earlier behaviour on purpose. A submission under a stale or
unknown contract digest, a non-object strategy or a cross-Challenge strategy
was recorded `INVALID_CONSTRUCTION`. It is now refused at the door
(`contract_not_served`, `strategy_not_object`, `challenge_mismatch`). Every
submission that passes the door is admitted, rebuilt and scored exactly as
before, under the same submission id.

**Limits before authentication.** A per-peer token bucket, a global in-flight
cap and a body limit apply before any signature is checked, and the envelope's
snapshot must be one this intake already observed: **no request causes a chain
read.** One refresher thread reads the metagraph on a fixed period.

**Exposure.** The listener binds loopback unless the configuration names an
exposure record that exists as a decision heading in `.agent/DECISIONS.md` or
`.agent/decisions/*.md` (one file per decision from 2026-10-03) - the owner's §4 security
review decision for this intake, an id of the form
`OWNER-…INTAKE-EXPOSURE-NN` - and terminates TLS itself (`tls_cert`,
`tls_key`). The owner recorded OWNER-INTAKE-EXPOSURE-01 on 2026-10-02 for
testnet 567 and the routes above; exposing a host stays an operator action.
A public bind also needs the deployment's isolated carrier: a deployment
that rebuilds recipes in this process (`backend: direct`) is never exposed
(`intake_exposure_needs_carrier`, LP-PROD-G). The TLS handshake runs in the
connection's own thread under its socket timeout, never in the accept loop.
Tests are not a security audit; this module is security-sensitive (AGENTS
§13).

**As a service** (`scripts/dev/battery_validator_service`, LP-PROD-G) the
intake logs one JSON line per event to stderr - start, stop, worker passes
that moved something, worker failures by type, and the refresher failing or
recovering - and never a peer address, hotkey, path or request. It holds
`<inbox>.serve.lock` while it runs, so the service's status and restore see
it however it was started. A start the host cannot serve yet (Docker down
or still starting) is waited out before anything listens. SIGTERM stops it:
the listener closes and the worker may finish its pass within a grace
period. A configuration refusal exits 2, so a supervisor does not restart
into it; any other failure exits 1 and is restarted after a backoff.

Nothing here scores, qualifies, commits on chain or signs with a key: the
miner signs; the service key, if configured, belongs to the daemon.
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import ipaddress
import json
import os
import re
import signal
import sqlite3
import ssl
import sys
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
OPTIONAL = {"host", "port", "exposure_record", "tls_cert", "tls_key", "attempt_ledger"}
#: The attempt ledger beside the inbox when the configuration names none.
ATTEMPT_LEDGER_SUFFIX = ".attempts.sqlite3"

#: Engineering abuse limits, not scientific values. Per peer: a burst of 10,
#: refilled at 1 request per second. At most 8 requests in flight, and at most
#: 64 received submissions waiting for admission.
PEER_BURST, PEER_RATE, IN_FLIGHT, INBOX_DEPTH = 10, 1.0, 8, 64
#: The metagraph is re-read on this period; a snapshot older than the
#: gateway's 60 s window can no longer authenticate anything.
REFRESH_S, SNAPSHOTS_KEPT, SNAPSHOT_MAX_AGE_S = 12.0, 5, 60.0
SOCKET_TIMEOUT_S = 10.0
#: Engineering abuse limits, not scientific values (VALIDATOR-01 security
#: review, finding 2):
#: - a body must arrive within this many seconds in total, before the request
#:   takes an in-flight slot, so a trickled body holds none;
#: - at most this many connections at once, and this many from one address;
#: - at most this many peer buckets are remembered (least recent evicted).
BODY_DEADLINE_S = 10.0
MAX_CONNECTIONS, MAX_CONNECTIONS_PER_PEER = 64, 4
MAX_PEERS = 4096
#: On SIGTERM the worker may finish the pass in flight for this long; a run
#: cut off after it is recovered as infrastructure on the next start.
STOP_GRACE_S = 30.0
#: A start refused for the host's state is retried after this backoff,
#: doubling up to the maximum (engineering values).
HOST_RETRY_MIN_S, HOST_RETRY_MAX_S = 1.0, 60.0
SERVE_LOCK_SUFFIX = ".serve.lock"
EXPOSURE_RECORD = r"OWNER-[A-Z0-9-]*INTAKE-EXPOSURE-[0-9]{2}"
SERVICE = "battery-intake"


def log(event, *, out=None, **fields):
    """One structured line on stderr: UTC time, service, event, counts and
    exception types only - never a peer, hotkey, path or request."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "service": SERVICE,
        "event": event,
        **fields,
    }
    print(json.dumps(record, sort_keys=True), file=out or sys.stderr, flush=True)


_TERMINAL = {
    "SCORED",
    "INVALID_CONSTRUCTION",
    "RECONSTRUCTION_FAILED",
    "FAILED_INFRA_EXHAUSTED",
    "VOID",
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
    from outside, so a public bind names that record and the record must be a
    decision heading: in `.agent/DECISIONS.md` (the history to 2026-10-03) or in
    one of the one-per-decision files under `.agent/decisions/` that replaced
    appending to it. A public bind also terminates TLS here:
    the miner client refuses plain HTTP beyond loopback, and behind a TLS
    proxy every request would share one peer's limits. Loopback needs neither.
    """
    if is_loopback(config["host"]):
        return
    record = config.get("exposure_record")
    # Only a record made for this purpose counts: any other owner decision,
    # including the one that chose the intake, never exposes it.
    if type(record) is not str or not re.fullmatch(EXPOSURE_RECORD, record):
        raise IntakeUnavailable("intake_exposure_unrecorded")
    agent = Path(repository) / ".agent"
    files = [agent / "DECISIONS.md", *sorted((agent / "decisions").glob("*.md"))]
    texts = [path.read_text(encoding="utf-8") for path in files]
    heading = re.compile(rf"^## .*\b{re.escape(record)}\b", re.MULTILINE)
    if not any(heading.search(text) for text in texts):
        raise IntakeUnavailable("intake_exposure_unrecorded")
    if not ("tls_cert" in config and "tls_key" in config):
        raise IntakeUnavailable("intake_exposure_needs_tls")


def is_loopback(host):
    """Whether a bind address is reachable from this host only."""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def require_isolation(config, deployment_config):
    """A public bind needs the deployment's isolated carrier (LP-PROD-G).

    A `direct` deployment rebuilds and runs recipes in the validator's own
    process (`DIRECT_TRUSTED_PROCESS`): local development only. Miner input
    from beyond this host is untrusted (AGENTS §6.6), so such a deployment is
    never exposed, whatever exposure record the configuration names.
    """
    if not is_loopback(config["host"]) and deployment_config["backend"] != "carrier":
        raise IntakeUnavailable("intake_exposure_needs_carrier")


def tls_context(config):
    """The server TLS context for a configuration that names one, or None.

    An unreadable certificate or key is a configuration state, refused by
    name before anything listens.
    """
    if "tls_cert" not in config:
        return None
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        tls.load_cert_chain(config["tls_cert"], config["tls_key"])
    except (OSError, ssl.SSLError):
        raise IntakeUnavailable("intake_tls_unreadable") from None
    return tls


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


def refresher(window, context, *, reader=None, period=REFRESH_S, stop=None, out=None):
    """Read the metagraph every `period` seconds until `stop` is set.

    A failed read keeps the previous snapshots; once they age out, the intake
    answers `snapshot_unavailable` - an infrastructure state, never a refusal
    of the miner. Only a change between reading and failing is logged (with
    the exception's type), so a chain outage is one line, not one per period.
    """
    if reader is None:
        from carbon.chain.sdk import BittensorReader

        reader = BittensorReader()
    stop = threading.Event() if stop is None else stop
    failing = False
    while not stop.is_set():
        try:
            window.add(asyncio.run(reader.capture(context)))
        except Exception as failure:  # noqa: BLE001 - infrastructure
            if not failing:
                log("snapshot_refresh_failed", out=out, type=type(failure).__name__)
            failing = True
        else:
            if failing:
                log("snapshot_refresh_recovered", out=out)
            failing = False
        stop.wait(period)


# --- limits ---------------------------------------------------------------------


class PeerLimits:
    """Token buckets per peer address plus a global in-flight cap.

    At most `MAX_PEERS` buckets are kept; the least recently seen is evicted.
    Clearing every bucket at the limit, as before, let anyone with many
    addresses reset the limits of all (VALIDATOR-01 security review,
    finding 2).
    """

    def __init__(self, *, burst=PEER_BURST, rate=PEER_RATE, clock=time.monotonic):
        from collections import OrderedDict

        self._lock = threading.Lock()
        self._buckets = OrderedDict()
        self._flight = threading.BoundedSemaphore(IN_FLIGHT)
        self.burst, self.rate, self.clock = burst, rate, clock

    def allow(self, peer):
        now = self.clock()
        with self._lock:
            tokens, then = self._buckets.pop(peer, (self.burst, now))
            tokens = min(self.burst, tokens + (now - then) * self.rate)
            allowed = tokens >= 1
            self._buckets[peer] = (tokens - 1 if allowed else tokens, now)
            while len(self._buckets) > MAX_PEERS:
                self._buckets.popitem(last=False)
            return allowed

    @contextlib.contextmanager
    def in_flight(self):
        if not self._flight.acquire(blocking=False):
            yield False
            return
        try:
            yield True
        finally:
            self._flight.release()


# --- the neutral door ------------------------------------------------------------


def attempt_ledger_path(config):
    """Where the attempt ledger lives: `attempt_ledger` in the configuration,
    else beside the inbox."""
    named = config.get("attempt_ledger")
    return Path(named) if named else Path(str(config["inbox"]) + ATTEMPT_LEDGER_SUFFIX)


def attempt_ledger(config):
    """The operator's attempt ledger (`carbon.challenge_validator.ledger`). It
    must sit in an owner-only directory; otherwise the intake refuses to
    start."""
    from carbon.challenge_validator.ledger import AttemptLedger, LedgerUnavailable

    try:
        return AttemptLedger(attempt_ledger_path(config))
    except LedgerUnavailable as refused:
        raise IntakeUnavailable("intake_" + refused.code) from None


def neutral_door(target, ledger):
    """The challenge-neutral validator battery's intake screens through
    (VALIDATOR-01 VAL-D3): battery's adapter over the deployment's daemon,
    behind the neutral checks and the attempt ledger."""
    from carbon.challenge_validator import Adapters, Validator
    from carbon.challenge_validator.battery import BatteryAdapter

    return Validator(Adapters([BatteryAdapter(target)]), ledger)


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
                  failure TEXT,
                  block INTEGER
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
        """Record one submission once; a resend is the same submission.

        A submission refused at admission for a reason that is never a
        judgement of it (`RECEIVED_AGAIN`: the hotkey's window, an undated
        receipt, a missing commitment or commitment reader, a backend this
        validator does not serve) is received again on resend, under the same
        submission id. The miner simply sends it again once the reason has
        passed; it is never a second submission.
        """
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
                "SELECT state, failure FROM inbox WHERE submission_id=?",
                (submission_id,),
            ).fetchone()
            if known is None and waiting >= INBOX_DEPTH:
                db.execute("ROLLBACK")
                return False
            block = (submission.receipt or {}).get("block")
            if known is None:
                db.execute(
                    "INSERT INTO inbox VALUES(?,?,?,?,'RECEIVED',NULL,?)",
                    (submission_id, submission.hotkey, document, now_ns, block),
                )
            elif known[0] == "REFUSED" and _received_again(known[1]):
                db.execute(
                    "UPDATE inbox SET state='RECEIVED', failure=NULL, document=?, "
                    "received_ns=?, block=? WHERE submission_id=?",
                    (document, now_ns, block, submission_id),
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

    def window_used(self, hotkey, start, end, *, other_than):
        """This hotkey's live submissions received in blocks `[start, end)`,
        other than `other_than`. Refused ones and invalid constructions (which
        the daemon does not count either) are not live."""
        with self._db() as db:
            return db.execute(
                "SELECT COUNT(*) FROM inbox WHERE hotkey=? AND submission_id!=? "
                "AND state IN ('RECEIVED','ADMITTED') AND failure IS NULL "
                "AND block>=? AND block<?",
                (hotkey, other_than, start, end),
            ).fetchone()[0]

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

    def counts(self):
        """How many submissions are in each state: for the operator's status
        and the worker's log line, never per hotkey."""
        with self._db() as db:
            rows = db.execute(
                "SELECT state, COUNT(*) FROM inbox GROUP BY state"
            ).fetchall()
        return {"RECEIVED": 0, "ADMITTED": 0, "REFUSED": 0, **dict(rows)}

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


#: Every refusal `work_once` records is one of these, and none is a verdict on
#: the submission: a timing rule (`hotkey_window_used`, `receipt_block_missing`),
#: a step the miner takes and then resends (`commitment_required`), or this
#: validator's own state (`commitment_reader_unavailable`,
#: `backend_not_served`). Until LP-PROD-G only the first was received again,
#: so the others held a recipe's one submission id refused for good.
RECEIVED_AGAIN = frozenset(
    {
        "hotkey_window_used",
        "receipt_block_missing",
        "commitment_required",
        "commitment_stale",
        "commitment_reader_unavailable",
        "backend_not_served",
    }
)


def _received_again(failure):
    return (
        failure is not None
        and json.loads(failure).get("failure", {}).get("code") in RECEIVED_AGAIN
    )


#: Bittensor's target block time, for a human "about N minutes" only; every
#: decision is made in blocks.
BLOCK_S = 12


def _window_answer(next_block, block):
    return Answer(
        429,
        {
            "refused": "hotkey_window_used",
            "next_block": next_block,
            "retry_after_s": max(0, next_block - block) * BLOCK_S,
        },
    )


# --- the intake -----------------------------------------------------------------


def commitment_fact(target):
    """The intake's public fact on chain commitments, from the deployment it
    serves. Admission (`BatteryValidator.admit`) does the checking."""
    if not getattr(target, "require_commitment", False):
        return "not_checked: this deployment does not require a chain commitment"
    if getattr(target, "commitments", None) is None:
        return (
            "required: no chain reader is configured, so every submission is "
            "refused as commitment_reader_unavailable"
        )
    return (
        "required: the recipe's chain commitment is read at admission and a "
        "submission is refused by name as commitment_required, "
        "commitment_stale or commitment_contested (D6)"
    )


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
        door,
        rule=None,
        limits=None,
        clock_ns=time.time_ns,
        commitment=None,
    ):
        from carbon.challenge_validator import Validator

        from .challenge import CHALLENGE

        if type(door) is not Validator:
            raise TypeError("the intake screens through the neutral Validator")
        #: Every submission passes the neutral checks here, and every attempt
        #: is recorded in the operator's ledger, before the inbox sees it.
        self.door = door
        self.context = context
        self.challenge = CHALLENGE
        self.receiver = receiver
        self.journal = journal
        self.verifier = verifier
        self.inbox = inbox
        self.window = window
        self.status_reader = status_reader
        #: The deployment's exam rule; rule v2 adds the per-hotkey window.
        self.rule = rule
        #: The public fact on chain commitments: the deployment's real mode
        #: (`commitment_fact`), checked at admission, not here.
        # Built without its deployment's mode (not through `_serve`): say so,
        # rather than claim a mode the deployment may not have.
        self.commitment = commitment or (
            "unstated: this door was built without its deployment's commitment mode"
        )
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
                "submission_rule": self._rule_facts(snapshot.finalized_block),
                "commitment": self.commitment,
                "qualification": False,
                "reward": False,
            },
        )

    def _rule_facts(self, block):
        """What a miner needs to know to submit at the right time."""
        from .exam import disclosure, hotkey_window

        per = None if self.rule is None else self.rule.get("per_hotkey")
        if per is None:
            return {"per_hotkey": None}
        start, end = hotkey_window(self.rule, block)
        return {
            "per_hotkey": per,
            "rotation": self.rule.get("rotation"),
            "current_window": {"start_block": start, "end_block": end},
            "block_time_s": BLOCK_S,
            "results": disclosure(self.rule),
        }

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

        from .daemon import SUBMIT_TOOL, submission_identity

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
            # The neutral screen refuses a development-only variant's digest
            # (`development_variant_not_served`, OWNER-GRAPHITE-TEST-WAVE-03
            # §1), so it is never queued for admission.
            screened = self._screen(received, gateway)
            if type(screened) is Answer:
                return screened
            neutral, submission = screened
            _, submission_id = submission_identity(submission)
            refused = self._window_check(hotkey, submission_id, submission)
            if refused is not None:
                self.door.note(
                    neutral,
                    kind="REFUSED",
                    code=refused.body["refused"],
                    submission_id=submission_id,
                )
                return refused
            if not self.inbox.receive(submission_id, submission, self.clock_ns()):
                self.door.note(
                    neutral,
                    kind="UNAVAILABLE",
                    code="inbox_full",
                    submission_id=submission_id,
                )
                return _refused(503, "inbox_full")
            self.door.note(
                neutral, kind="RECEIVED", submission_id=submission_id, state="RECEIVED"
            )
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

    def _screen(self, received, gateway):
        """The neutral checks for one authenticated `battery_submit`
        (`Validator.screen`): `(neutral, submission)` to queue, or the refusal.

        The strategy is screened as the miner signed it, raw: strict UTF-8 and
        JSON, no NaN/Infinity, duplicate keys, deep nesting or 64-bit-overflow
        integers, an object naming battery, under a contract digest this
        validator serves. A refusal is recorded in the operator's ledger and
        answered by its closed code; it never reaches the inbox or the daemon.
        """
        from carbon.challenge_validator import Submission
        from carbon.challenge_validator.dispatch import Screened

        from .daemon import AuthenticatedSubmission

        fields = {f.name: f.value for f in received.call.fields}
        if set(fields) != {"strategy_json", "contract_digest"}:
            return _refused(400, "submission_fields")
        receipt = received.receipt
        neutral = Submission(
            hotkey=receipt.hotkey,
            receipt={
                "sequence": receipt.ref.sequence,
                "digest": receipt.ref.digest,
                # The finalized block of the validator-observed snapshot the
                # request was authenticated against: rule v2's clock.
                "block": receipt.finalized_block,
            },
            challenge_id=gateway.challenge.challenge_id,
            challenge_version=gateway.challenge.version,
            strategy_json=fields["strategy_json"],
            contract_digest=fields["contract_digest"],
        )
        screened = self.door.screen(neutral)
        if type(screened) is not Screened:
            return _refused(400, screened["code"])
        admitted = screened.admitted
        return neutral, AuthenticatedSubmission(
            hotkey=admitted.hotkey,
            receipt=admitted.receipt,
            challenge_id=admitted.challenge_id,
            challenge_version=admitted.challenge_version,
            strategy=admitted.strategy,
            contract_digest=admitted.contract_digest,
        )

    def _window_check(self, hotkey, submission_id, submission):
        """Answer at once when this hotkey's window is already used (v2).

        The daemon enforces the same rule authoritatively at admission; this
        only spares the miner a wait for a refusal that is already certain.
        A resend of a submission already in the inbox is never refused here.
        """
        from .exam import hotkey_window

        if self.rule is None or self.rule.get("per_hotkey") is None:
            return None
        known = self.inbox.row(submission_id)
        if known is not None and known["state"] != "REFUSED":
            return None
        block = submission.receipt["block"]
        start, end = hotkey_window(self.rule, block)
        limit = self.rule["per_hotkey"]["scored_per_window"]
        if (
            self.inbox.window_used(hotkey, start, end, other_than=submission_id)
            >= limit
        ):
            return _window_answer(end, block)
        return None

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
    was, to be retried; it is never a refusal of the miner. Returns what the
    pass moved, as counts only.
    """
    from .daemon import (
        BackendNotServed,
        CommitmentContested,
        CommitmentRequired,
        CommitmentStale,
    )
    from .deployment import writer
    from .pool_store import HotkeyWindowUsed

    moved = {"admitted": 0, "refused": 0, "processed": 0, "advanced": 0}
    for submission_id, submission in inbox.received():
        try:
            with writer(target):
                admitted = target.admit(submission)
        except HotkeyWindowUsed as used:
            failure = (
                {"code": "hotkey_window_used", "next_block": used.next_block}
                if used.next_block is not None
                else {"code": "receipt_block_missing"}
            )
            inbox.mark(submission_id, "REFUSED", {"failure": failure})
            moved["refused"] += 1
            continue
        except CommitmentRequired as missing:
            if target.commitments is None:
                code = "commitment_reader_unavailable"
            elif isinstance(missing, CommitmentContested):
                # D6: another hotkey committed this digest first; never
                # received again.
                code = "commitment_contested"
            elif isinstance(missing, CommitmentStale):
                # D6: the matching commitment was spent by an earlier
                # admission; a fresh one makes this resend count.
                code = "commitment_stale"
            else:
                code = "commitment_required"
            inbox.mark(submission_id, "REFUSED", {"failure": {"code": code}})
            moved["refused"] += 1
            continue
        except BackendNotServed as missing:
            # This validator has no image for the recipe's backend: not a
            # judgement of the recipe, and nothing is recorded in the pool.
            failure = {"code": "backend_not_served", "backend": missing.backend}
            inbox.mark(submission_id, "REFUSED", {"failure": failure})
            moved["refused"] += 1
            continue
        # An invalid construction is admitted and settled at once; it does
        # not use the hotkey's window (the daemon does not count it either).
        inbox.mark(
            submission_id,
            "ADMITTED",
            (
                {"code": "INVALID_CONSTRUCTION"}
                if admitted["state"] == "INVALID_CONSTRUCTION"
                else None
            ),
        )
        moved["admitted"] += 1
    for submission_id in inbox.admitted():
        with writer(target):
            if target.outcome(submission_id)["state"] not in _TERMINAL:
                target.process(submission_id)
                moved["processed"] += 1
    with writer(target):
        moved["advanced"] = len(target.run_pending() or ())
    return moved


def worker(inbox, target, wake, *, stop, idle_s=30.0, out=None):
    while not stop.is_set():
        wake.clear()
        try:
            moved = work_once(inbox, target)
        except Exception as failure:  # noqa: BLE001
            # Infrastructure: the inbox keeps every submission for the next
            # pass. Only the exception's type is logged, never its content.
            log("worker_failure", out=out, type=type(failure).__name__)
        else:
            if any(moved.values()):
                log("worker_pass", out=out, **moved)
        wake.wait(idle_s)


# --- HTTP -----------------------------------------------------------------------


def _handler(intake):
    class Handler(LoggedHandler):
        server_version = "carbon-battery-intake"
        sys_version = ""

        def _answer(self, answer):
            payload = json.dumps(answer.body, sort_keys=True).encode()
            self.send_response(answer.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)

        def _dispatch(self, method):
            # The declared length is checked and the peer's bucket charged
            # before a single body byte is read. The body must then arrive
            # whole within BODY_DEADLINE_S, and only then does the request
            # take an in-flight slot: a trickled body holds no slot.
            length = 0
            if method == "POST":
                declared = self.headers.get("Content-Length")
                if (
                    declared is None
                    or not declared.isdigit()
                    or int(declared) > MAX_BODY
                ):
                    return self._answer(_refused(413, "body"))
                length = int(declared)
            if not intake.limits.allow(self.client_address[0]):
                return self._answer(_refused(429, "rate"))
            try:
                body = read_body(self.connection, self.rfile, length, BODY_DEADLINE_S)
            except (TimeoutError, ConnectionError, OSError):
                return self._answer(_refused(408, "body_timeout"))
            headers = {k: v for k, v in self.headers.items()}
            if len(headers) != len(self.headers.items()):
                return self._answer(_refused(400, "headers"))
            with intake.limits.in_flight() as admitted:
                if not admitted:
                    return self._answer(_refused(503, "capacity"))
                self._answer(intake.route(method, self.path, headers, body))

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def log_message(self, *_args):
            # Paths and addresses only would still be a peer log; keep none.
            return

    return Handler


def read_body(connection, rfile, length, deadline_s, *, clock=time.monotonic):
    """`length` body bytes, all within `deadline_s` seconds in total.

    The socket timeout alone bounds each read, not the request, so a peer
    sending one byte just inside it could hold a request for minutes. Each
    read here waits only for what is left of the deadline.
    """
    deadline = clock() + deadline_s
    chunks, received = [], 0
    try:
        while received < length:
            left = deadline - clock()
            if left <= 0:
                raise TimeoutError("body_deadline")
            connection.settimeout(left)
            chunk = rfile.read1(length - received)
            if not chunk:
                raise ConnectionError("body_closed")
            chunks.append(chunk)
            received += len(chunk)
    finally:
        connection.settimeout(SOCKET_TIMEOUT_S)
    return b"".join(chunks)


class ConnectionSlots:
    """At most `total` open connections, and at most `per_peer` from one
    address. A connection over either cap is closed before any byte of it is
    read (VALIDATOR-01 security review, finding 2)."""

    def __init__(self, total=MAX_CONNECTIONS, per_peer=MAX_CONNECTIONS_PER_PEER):
        self.total, self.per_peer = total, per_peer
        self._lock = threading.Lock()
        self._open = {}

    def acquire(self, peer):
        with self._lock:
            if sum(self._open.values()) >= self.total:
                return False
            if self._open.get(peer, 0) >= self.per_peer:
                return False
            self._open[peer] = self._open.get(peer, 0) + 1
            return True

    def release(self, peer):
        with self._lock:
            left = self._open.get(peer, 0) - 1
            if left > 0:
                self._open[peer] = left
            else:
                self._open.pop(peer, None)

    def open(self):
        with self._lock:
            return sum(self._open.values())


#: Connections the kernel queues before this listener accepts them. The
#: socketserver default of 5 is a full queue at the sixth waiting client.
LISTEN_BACKLOG = 128


class LoggedHandler(BaseHTTPRequestHandler):
    """The base of every Carbon public door's handler: each read or write
    waits at most `timeout`, the base class's own log stays silent, and a
    connection that times out is one structured line (event only)."""

    timeout = SOCKET_TIMEOUT_S

    def log_message(self, *_args):
        return

    def log_error(self, format, *args):
        if format.startswith("Request timed out"):
            log("connection_timed_out", service=self.server.service)


class _Server(ThreadingHTTPServer):
    """The listener. A connection that fails outside a request (a TLS
    handshake that never completes or is malformed) is logged by exception
    type only: the base class would print the peer's address and a trace.
    Connections beyond `ConnectionSlots` are closed at once, and logged, so
    no address can hold every thread."""

    daemon_threads = True
    request_queue_size = LISTEN_BACKLOG

    def __init__(self, address, handler, *, service=SERVICE):
        self.slots = ConnectionSlots()
        self.service = service
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(client_address[0]):
            log("connection_refused", service=self.service, reason="busy")
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release(client_address[0])
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release(client_address[0])

    def handle_error(self, request, client_address):
        log(
            "connection_failed",
            service=self.service,
            type=getattr(sys.exc_info()[0], "__name__", None),
        )


def hardened_listener(config, handler, *, service=SERVICE):
    """Bind the configured address for `handler` (a `LoggedHandler`); with
    TLS, wrap it so each connection's handshake runs in that connection's own
    thread, under its socket timeout.

    Wrapping with the default `do_handshake_on_connect` would run every
    handshake inside `accept`, in the single serving thread: one client that
    connects and sends nothing would stop the door for everyone. Every
    Carbon public door listens through this: the intake, the answer-key
    distribution host and the development submission door.
    """
    if not issubclass(handler, LoggedHandler):
        raise TypeError("a public door's handler is a LoggedHandler")
    tls = tls_context(config)
    httpd = _Server((config["host"], config["port"]), handler, service=service)
    if tls is not None:
        httpd.socket = tls.wrap_socket(
            httpd.socket, server_side=True, do_handshake_on_connect=False
        )
    return httpd


def listener(config, intake):
    """The intake's listener (`hardened_listener`)."""
    return hardened_listener(config, _handler(intake))


def serve_lock_path(config):
    """The lock a serving intake holds: `<inbox>.serve.lock`."""
    return Path(str(config["inbox"]) + SERVE_LOCK_SUFFIX)


def _serving_lock(config):
    """Hold the serving lock for the intake's life and return its fd.

    It is the signal the service's `status` and `restore` read to see the
    intake running, under a supervisor or a systemd unit, even while it
    waits for the host and does not listen yet. A probe holds it shared for
    an instant, so it is retried briefly; a lock still held belongs to
    another intake on the same inbox (`intake_already_serving`).
    """
    from .operate import LOCK_RETRY_S, LOCK_TRIES

    fd = os.open(serve_lock_path(config), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    for _ in range(LOCK_TRIES):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            time.sleep(LOCK_RETRY_S)
        else:
            return fd
    os.close(fd)
    raise IntakeUnavailable("intake_already_serving")


def _when_host_ready(config, repository, stop):
    """The writable deployment, once the host can serve it.

    A start refused for the host's state - `evaluation_host_unavailable`:
    Docker down, or still starting after a reboot - is retried after a
    backoff doubling from 1 s to 60 s, each attempt logged
    `waiting_for_host`, until it builds, or `stop` is set (None). Exiting
    instead would spend a supervisor's restart limit on a passing outage. A
    configuration refusal (`operate.exit_code`) propagates at once.
    """
    from . import deployment
    from .operate import REFUSED_EXIT, exit_code

    delay = HOST_RETRY_MIN_S
    while True:
        try:
            return deployment.validator(config["deployment"], repository=repository)
        except deployment.EvaluationUnavailable as unavailable:
            if exit_code(unavailable.code) == REFUSED_EXIT:
                raise
            log("waiting_for_host", code=unavailable.code, retry_in_s=delay)
        if stop.wait(delay):
            return None
        delay = min(HOST_RETRY_MAX_S, delay * 2)


def serve(
    config_path,
    *,
    repository,
    stop=None,
    reader=None,
    verifier=None,
    ready=None,
):
    """Run the intake: refresher, worker and listener, until `stop` is set.

    `reader` is the refresher's chain reader (the metagraph reader when None;
    tests pass a fixed snapshot so nothing reaches a chain) and `verifier`
    the hotkey verifier (`BittensorHotkeyVerifier` when None). `ready`, if
    given, is called with the bound `(host, port)` once the listener accepts
    connections. Everything that can refuse is checked before anything
    listens or starts: the configuration, the exposure and its isolation,
    the TLS material, the serving lock and the deployment. A deployment the
    host cannot serve yet is waited for (`_when_host_ready`).
    """
    from . import deployment

    config = load_config(config_path, repository=repository)
    require_isolation(config, deployment.load_config(config["deployment"]))
    tls_context(config)  # refused by name before the deployment starts
    stop = threading.Event() if stop is None else stop
    lock = _serving_lock(config)
    try:
        target = _when_host_ready(config, repository, stop)
        if target is not None:
            _serve(config, target, repository, stop, reader, verifier, ready)
    finally:
        os.close(lock)


def _serve(config, target, repository, stop, reader, verifier, ready):
    """`serve` once the deployment is built: the refresher, the worker and
    the listener, until `stop` is set."""
    from carbon.chain.auth import BittensorHotkeyVerifier
    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.transport.store import ReceiptJournal

    from . import deployment

    context = carbon_testnet_context()
    status = deployment.validator(
        config["deployment"], repository=repository, readonly=True
    )
    inbox = Inbox(config["inbox"])
    window = SnapshotWindow()
    intake = BatteryIntake(
        context=context,
        receiver=config["receiver"],
        journal=ReceiptJournal(Path(config["transport_journal"]), context),
        verifier=BittensorHotkeyVerifier() if verifier is None else verifier,
        inbox=inbox,
        window=window,
        status_reader=status.outcome,
        door=neutral_door(target, attempt_ledger(config)),
        rule=target.rule,
        commitment=commitment_fact(target),
    )
    httpd = listener(config, intake)
    threads = [
        threading.Thread(
            target=refresher,
            args=(window, context),
            kwargs={"stop": stop, "reader": reader},
            daemon=True,
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
    host, port = httpd.server_address[:2]
    try:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        log("listening", host=host, port=port, tls="tls_cert" in config)
        if ready is not None:
            ready((host, port))
        stop.wait()
    finally:
        httpd.shutdown()
        httpd.server_close()
        # The worker may finish the pass in flight; one cut off after the
        # grace period is recovered as infrastructure on the next start.
        intake.wake.set()
        threads[1].join(STOP_GRACE_S)
        log("stopped", worker_finished=not threads[1].is_alive())


def main(argv=None):
    import argparse

    from .deployment import EvaluationUnavailable
    from .operate import REFUSED_EXIT, exit_code

    parser = argparse.ArgumentParser(prog="carbon.battery.intake")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("serve")
    run.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    stop = threading.Event()
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: stop.set())
    try:
        serve(args.config, repository=repository, stop=stop)
    except IntakeUnavailable as refused:
        # A configuration state: exit 2, which a supervisor does not restart.
        log("refused", code=refused.code)
        print(json.dumps({"unavailable": refused.code}))
        return REFUSED_EXIT
    except EvaluationUnavailable as unavailable:
        # The deployment's own code decides: its configuration exits 2; the
        # host's state (`evaluation_host_unavailable`, or a code not known
        # as a configuration) exits 1, restarted after a backoff.
        code = exit_code(unavailable.code)
        log(
            "refused" if code == REFUSED_EXIT else "unavailable",
            code=unavailable.code,
        )
        print(json.dumps({"unavailable": unavailable.code}))
        return code
    except OSError as failure:
        # The address is taken or the host refused the bind: infrastructure,
        # which a supervisor retries after its backoff.
        log("failed", type=type(failure).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

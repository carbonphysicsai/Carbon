"""The answer-key distribution host (VALIDATOR-19 slice 2; VALIDATOR-18's
two-host design).

A small public host that holds only what every permit holder receives anyway:
signed, sealed, active batch packages, and its own fetch log. It never holds
the producer's root, solver or journal, nor any producer-only set, and it
cannot reach the producer. The producer pushes packages into its inbox.

    python -m carbon.challenge_validator.distribution serve --config DIST.json

A request is one `btauth/1`-signed POST to `/carbon/v1/answer-key`, with body
`{"schema", "challenge_id", "fingerprint"}`:
- **`fingerprint: null`** lists the signed manifests of the Challenge's
  packages;
- **a fingerprint** returns that package.

Each request is admitted only after:
1. the signature, freshness and replay checks (`btauth/1`);
2. a read of the finalized chain showing that the hotkey holds a validator
   permit on the subnet.

Every request, admitted or refused, is logged with its hotkey (when
authenticated), finalized block, fingerprint and verdict. Fetches are
attributable, so a leaked key narrows to the hotkeys that fetched it in that
window.

A package that fails verification against the pinned producer key is never
served. Security-sensitive (AGENTS.md §13): not a security audit.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import sys
import threading
import time
from pathlib import Path

from .answer_key import (
    PATH,
    REQUEST_SCHEMA,
    AnswerKeyRefused,
    listing_entry,
    read_private,
    verify,
)

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG_SCHEMA = "carbon.challenge-validator.distribution-config.v1"
LOG_SCHEMA = "carbon.challenge-validator.distribution-fetch.v1"
#: A request body limit: an engineering bound, not a scientific value.
MAX_REQUEST = 4096


class NonceStore:
    """Replay protection for `btauth/1`: each (hotkey, nonce) once, durably."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS nonce("
                "hotkey TEXT NOT NULL, nonce INTEGER NOT NULL, "
                "PRIMARY KEY(hotkey, nonce))"
            )
        os.chmod(self.path, 0o600)

    def _connect(self):
        return sqlite3.connect(self.path)

    def check_and_store(self, hotkey_ss58, nonce_ns):
        if type(nonce_ns) is not int or not 0 <= nonce_ns < 2**63:
            return False
        with self._lock, self._connect() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO nonce VALUES(?,?)", (hotkey_ss58, nonce_ns)
            )
            return cursor.rowcount == 1


class Inbox:
    """The pushed packages, each verified against the pinned producer key
    before it can be served. A file that fails is skipped, never served."""

    def __init__(self, directory, producer_public_key):
        self.directory = Path(directory)
        self.producer_public_key = producer_public_key

    def packages(self, challenge_id, *, block=None):
        """Verified packages for `challenge_id`. With `block`, only those a
        validator may still use: windowed, and not retired at `block`."""
        info = os.lstat(self.directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise AnswerKeyRefused("answer_key_inbox_not_owner_only")
        found, skipped = {}, 0
        # The producer pushes its whole outbox: one subdirectory per
        # Challenge (VALIDATOR-21); a flat inbox from earlier pushes still
        # serves.
        paths = [*self.directory.glob("*.json"), *self.directory.glob("*/*.json")]
        withdrawn = {m["fingerprint"] for m, _ in self._withdrawals(challenge_id)}
        for path in sorted(paths):
            if path.parent.name in ("withdrawals", "training"):
                continue
            try:
                value = read_private(path)
                commitment, _ = verify(value, self.producer_public_key)
            except (AnswerKeyRefused, OSError, ValueError):
                skipped += 1
                continue
            if commitment["challenge_id"] != challenge_id:
                continue
            if commitment["fingerprint"] in withdrawn:
                # Withdrawn (VALIDATOR-24): never served, even if pushed.
                continue
            window = commitment.get("window")
            if block is not None and (
                type(window) is not dict or window.get("retire_block", 0) <= block
            ):
                # Retired, or never scheduled: never served (slice 3).
                continue
            found[commitment["fingerprint"]] = value
        return found, skipped

    def _withdrawals(self, challenge_id):
        """`[(manifest, notice)]`, each verified against the producer key."""
        from .answer_key import verify_withdrawal

        found = []
        paths = [
            *self.directory.glob("withdrawals/*.json"),
            *self.directory.glob("*/withdrawals/*.json"),
        ]
        for path in sorted(paths):
            try:
                value = read_private(path)
                manifest = verify_withdrawal(value, self.producer_public_key)
            except (AnswerKeyRefused, OSError, ValueError):
                continue
            if manifest["challenge_id"] == challenge_id:
                found.append((manifest, value))
        return found

    def withdrawals(self, challenge_id):
        """The verified withdrawal notices for `challenge_id`."""
        return [value for _, value in self._withdrawals(challenge_id)]


class FetchLog:
    """The append-only, owner-only per-hotkey fetch log."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def note(self, **fields):
        entry = {"schema": LOG_SCHEMA, "time_ns": time.time_ns(), **fields}
        with self._lock:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a") as handle:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")


class DistributionService:
    """Answers one authenticated request. Transport-free, so tests drive it
    directly."""

    def __init__(
        self,
        inbox,
        *,
        receiver,
        verifier,
        permits,
        nonces,
        log,
        clock_ns=time.time_ns,
        training=None,
    ):
        self.inbox, self.receiver = inbox, receiver
        self.verifier, self.permits = verifier, permits
        self.nonces, self.log, self.clock_ns = nonces, log, clock_ns
        #: The public training pool (OWNER-AUTO-PUBLISH-RETIRED-01): retired
        #: cases only, read-only, to anyone. None serves nothing.
        self.training = training

    def handle_training(self, path):
        """`(status, answer)` for one public `GET` of the training pool. No
        authentication: it serves only signed files of retired cases."""
        if self.training is None:
            return 404, {"refused": "training_not_served"}
        status, answer = self.training.answer(path)
        self.log.note(
            hotkey=None,
            verdict="TRAINING_SERVED" if status == 200 else "TRAINING_REFUSED",
            path=path[:200],
        )
        return status, answer

    def handle(self, headers, body):
        """`(status, answer)` for one request."""
        from carbon.chain.auth import AuthFailure
        from carbon.chain.permits import PermitUnavailable

        try:
            caller = self.verifier.verify(
                headers,
                body,
                method="POST",
                path=PATH,
                receiver=self.receiver,
                now_ns=self.clock_ns(),
                nonce_store=self.nonces,
            )
        except AuthFailure as failure:
            self.log.note(hotkey=None, verdict=failure.code.value)
            return 401, {"refused": failure.code.value}
        hotkey = caller.hotkey
        try:
            request = json.loads(body)
            if (
                type(request) is not dict
                or set(request) != {"schema", "challenge_id", "fingerprint"}
                or request["schema"] != REQUEST_SCHEMA
                or type(request["challenge_id"]) is not str
                or type(request["fingerprint"]) not in (str, type(None))
            ):
                raise ValueError
        except ValueError:
            self.log.note(hotkey=hotkey, verdict="answer_key_request_malformed")
            return 400, {"refused": "answer_key_request_malformed"}
        fingerprint = request["fingerprint"]

        def refuse(status, code, block=None):
            self.log.note(
                hotkey=hotkey, block=block, fingerprint=fingerprint, verdict=code
            )
            return status, {"refused": code}

        try:
            permit = self.permits.read(hotkey)
        except PermitUnavailable:
            # The chain could not be read: infrastructure, retried by the
            # validator; never an admission.
            return refuse(503, "answer_key_chain_unavailable")
        if permit is None or not permit["permit"]:
            block = None if permit is None else permit["block"]
            return refuse(403, "answer_key_no_validator_permit", block)
        block = permit["block"]
        try:
            packages, _ = self.inbox.packages(request["challenge_id"], block=block)
        except (AnswerKeyRefused, OSError):
            return refuse(503, "answer_key_inbox_unavailable", block)
        if fingerprint is None:
            self.log.note(
                hotkey=hotkey, block=block, fingerprint=None, verdict="LISTED"
            )
            return 200, {
                "packages": [listing_entry(packages[f]) for f in sorted(packages)],
                "withdrawals": self.inbox.withdrawals(request["challenge_id"]),
            }
        if fingerprint not in packages:
            return refuse(404, "answer_key_unknown_batch", block)
        self.log.note(
            hotkey=hotkey, block=block, fingerprint=fingerprint, verdict="SERVED"
        )
        return 200, {"package": packages[fingerprint]}


def fetchers(log_path, fingerprint, *, from_block=None, to_block=None):
    """The hotkeys this host served `fingerprint` to, optionally only at
    finalized blocks in `[from_block, to_block)`. This is how far a leaked
    batch narrows: to these hotkeys, never to one of them, because every
    validator receives the same bytes (VALIDATOR-19 S4, the leak family)."""
    found = set()
    path = Path(log_path)
    if not path.exists():
        return []
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        block = entry.get("block")
        if (
            entry.get("verdict") != "SERVED"
            or entry.get("fingerprint") != fingerprint
            or (from_block is not None and (block is None or block < from_block))
            or (to_block is not None and (block is None or block >= to_block))
        ):
            continue
        found.add(entry["hotkey"])
    return sorted(found)


#: The `service` of this host's structured log lines (on stderr).
SERVICE = "answer-key-distribution"


def load_config(path, *, repository=REPOSITORY):
    from carbon.battery.intake import require_exposure

    config = read_private(path)
    required = {
        "schema",
        "inbox",
        "fetch_log",
        "nonces",
        "receiver",
        "producer_public_key",
        "chain",
        "host",
        "port",
    }
    optional = {"exposure_record", "tls_cert", "tls_key"}
    if (
        type(config) is not dict
        or config.get("schema") != CONFIG_SCHEMA
        or not required <= set(config)
        or set(config) - required - optional
        or type(config["chain"]) is not dict
    ):
        raise AnswerKeyRefused("answer_key_config_malformed")
    require_exposure(config, repository=repository)
    return config


def make_server(service, config, *, repository=REPOSITORY):
    """The host's server, not yet serving. Loopback unless the owner's exposure
    record and TLS are configured (`intake.require_exposure`).

    It listens through the intake's hardened listener: each TLS handshake in
    its connection's own thread, every read under a socket timeout, bounded
    connections per peer and in total, and a queue of `LISTEN_BACKLOG`. Its
    first listener ran every handshake inside `accept`, so one silent client
    froze it for everyone (3a, 2026-10-08)."""
    from carbon.battery.intake import LoggedHandler, hardened_listener, require_exposure

    require_exposure(config, repository=repository)

    class Handler(LoggedHandler):
        server_version = "carbon-answer-key"
        sys_version = ""

        def _answer(self, status, value):
            body = json.dumps(value, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            from .training_pool import TRAINING_PATH

            if not self.path.startswith(TRAINING_PATH):
                return self._answer(404, {"refused": "not_found"})
            return self._answer(*service.handle_training(self.path))

        def do_POST(self):
            if self.path != PATH:
                return self._answer(404, {"refused": "not_found"})
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_REQUEST:
                return self._answer(413, {"refused": "answer_key_body"})
            body = self.rfile.read(length)
            headers = dict(self.headers.items())
            if len(headers) != len(self.headers.items()):
                # A repeated header is ambiguous: refused, as the intake does.
                return self._answer(400, {"refused": "answer_key_headers"})
            return self._answer(*service.handle(headers, body))

    return hardened_listener(config, Handler, service=SERVICE)


def build(config):
    from carbon.chain.auth import BittensorHotkeyVerifier
    from carbon.chain.models import ChainContext
    from carbon.chain.permits import ValidatorPermitReader

    from .training_pool import TrainingPool

    return DistributionService(
        Inbox(config["inbox"], config["producer_public_key"]),
        receiver=config["receiver"],
        verifier=BittensorHotkeyVerifier(),
        permits=ValidatorPermitReader(ChainContext(**config["chain"])),
        nonces=NonceStore(config["nonces"]),
        log=FetchLog(config["fetch_log"]),
        # The producer pushes `training/<challenge>/` beside the packages.
        training=TrainingPool(
            Path(config["inbox"]) / "training", config["producer_public_key"]
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.distribution")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve").add_argument("--config", required=True)
    narrow = sub.add_parser("leak-narrowing")
    narrow.add_argument("--config", required=True)
    narrow.add_argument("--fingerprint", required=True)
    narrow.add_argument("--from-block", type=int)
    narrow.add_argument("--to-block", type=int)
    args = parser.parse_args(argv)
    if args.command == "leak-narrowing":
        try:
            config = read_private(args.config)
        except AnswerKeyRefused as refused:
            print(json.dumps({"refused": refused.code}))
            return 2
        hotkeys = fetchers(
            config["fetch_log"],
            args.fingerprint,
            from_block=args.from_block,
            to_block=args.to_block,
        )
        print(json.dumps({"fetchers": len(hotkeys), "hotkeys": hotkeys}))
        return 0
    try:
        config = load_config(args.config)
        server = make_server(build(config), config)
    except AnswerKeyRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

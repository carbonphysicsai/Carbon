"""Bounded durable application receipts; SQLite owns original receipt order."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from carbon.chain import ChainContext, MetagraphSnapshot
from carbon.chain.auth import AuthenticatedHotkey

from .models import (
    AuthenticatedReceipt,
    ReceiptRef,
    TransportCode,
    TransportFailure,
    canonical,
    digest,
)


class _NonceTransaction:
    def __init__(self, connection):
        self.connection = connection
        self.captured = None

    def check_and_store(self, hotkey_ss58: str, nonce_ns: int) -> bool:
        if type(nonce_ns) is not int or not 0 <= nonce_ns < 2**63:
            raise TransportFailure(TransportCode.MALFORMED)
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO nonce VALUES (?, ?)", (hotkey_ss58, nonce_ns)
        )
        self.captured = (hotkey_ss58, nonce_ns)
        return cursor.rowcount == 1


class ReceiptJournal:
    def __init__(self, path: Path, context: ChainContext, *, capacity: int = 100000):
        if type(capacity) is not int or not 1 <= capacity <= 100000:
            raise TransportFailure(TransportCode.CAPACITY)
        self.path = Path(path)
        self.context = context
        self.capacity = capacity
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS transport_meta (
                    id INTEGER PRIMARY KEY CHECK(id=1), context TEXT NOT NULL,
                    time_ns INTEGER NOT NULL, block INTEGER NOT NULL,
                    snapshot TEXT NOT NULL, chain_time INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nonce (
                    hotkey TEXT NOT NULL, nonce_ns INTEGER NOT NULL,
                    PRIMARY KEY(hotkey, nonce_ns)
                );
                CREATE INDEX IF NOT EXISTS nonce_age ON nonce(nonce_ns);
                CREATE TABLE IF NOT EXISTS receipt (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_key TEXT NOT NULL UNIQUE,
                    body_digest TEXT NOT NULL,
                    hotkey TEXT NOT NULL, received_ns INTEGER NOT NULL,
                    record TEXT NOT NULL, digest TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS receipt_rate ON receipt(hotkey, received_ns);
            """)
            encoded_context = canonical(asdict(context)).decode()
            connection.execute(
                "INSERT OR IGNORE INTO transport_meta VALUES (1, ?, 0, 0, '', 0)",
                (encoded_context,),
            )
            row = connection.execute(
                "SELECT context FROM transport_meta WHERE id=1"
            ).fetchone()
            if row != (encoded_context,):
                raise TransportFailure(TransportCode.CONTEXT)

    @contextmanager
    def _connection(self):
        connection = None
        failed = False
        try:
            connection = sqlite3.connect(self.path, timeout=2, isolation_level=None)
            connection.execute("PRAGMA synchronous=FULL")
            yield connection
        except sqlite3.Error:
            failed = True
        finally:
            if connection is not None:
                connection.close()
        if failed:
            raise TransportFailure(TransportCode.STORE)

    def minimum_block(self) -> int:
        with self._connection() as connection:
            return connection.execute(
                "SELECT block FROM transport_meta WHERE id=1"
            ).fetchone()[0]

    @contextmanager
    def transaction(self):
        """Trusted Carbon journal extensions share the receipt database/lock.

        Not a wire API. Extensions own their versioned tables and must not
        mutate transport tables. Closing rolls back an interrupted transaction.
        """
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()

    def admit(
        self, body, envelope, snapshot: MetagraphSnapshot, now_ns: int, authenticate
    ):
        """Signature, nonce and receipt insertion form one durable transaction."""
        if type(now_ns) is not int or not 0 <= now_ns < 2**63:
            raise TransportFailure(TransportCode.STALE)
        if snapshot.context != self.context:
            raise TransportFailure(TransportCode.CONTEXT)
        result = None
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            timestamp, block, previous_snapshot, chain_time = connection.execute(
                "SELECT time_ns, block, snapshot, chain_time FROM transport_meta WHERE id=1"
            ).fetchone()
            if (
                now_ns < timestamp
                or snapshot.finalized_block < block
                or snapshot.timestamp_ms < chain_time
            ):
                raise TransportFailure(TransportCode.STALE)
            if (
                block == snapshot.finalized_block
                and previous_snapshot
                and previous_snapshot != snapshot.snapshot_id
            ):
                raise TransportFailure(TransportCode.CONTEXT)
            # Past this cutoff a signature is already stale, even after restart.
            # Watermark and deletion commit with the receipt, never on failed auth.
            connection.execute(
                "DELETE FROM nonce WHERE nonce_ns < ?", (now_ns - 10_000_000_000,)
            )
            nonce_store = _NonceTransaction(connection)
            caller = authenticate(nonce_store)
            if type(caller) is not AuthenticatedHotkey or nonce_store.captured != (
                caller.hotkey,
                caller.nonce_ns,
            ):
                raise TransportFailure(TransportCode.IDENTITY)
            participant = snapshot.resolve(caller.hotkey)
            if participant is None:
                raise TransportFailure(TransportCode.IDENTITY)
            request_key = digest(
                canonical(
                    [
                        caller.hotkey,
                        envelope["challenge_id"],
                        envelope["challenge_version"],
                        envelope["session"],
                        envelope["request"],
                    ]
                )
            )
            body_digest = digest(body)
            prior = connection.execute(
                "SELECT body_digest FROM receipt WHERE request_key=?", (request_key,)
            ).fetchone()
            if prior:
                code = (
                    TransportCode.REPLAY
                    if prior[0] == body_digest
                    else TransportCode.CONFLICT
                )
                raise TransportFailure(code)
            if (
                connection.execute("SELECT COUNT(*) FROM receipt").fetchone()[0]
                >= self.capacity
            ):
                raise TransportFailure(TransportCode.CAPACITY)
            count = connection.execute(
                "SELECT COUNT(*) FROM receipt WHERE hotkey=? AND received_ns>?",
                (caller.hotkey, now_ns - 1_000_000_000),
            ).fetchone()[0]
            if count >= 32:
                raise TransportFailure(TransportCode.RATE)
            record = {
                "body_digest": body_digest,
                "hotkey": participant.hotkey,
                "coldkey": participant.coldkey,
                "uid": participant.uid,
                "registered_at": participant.registered_at,
                "snapshot_id": snapshot.snapshot_id,
                "finalized_block": snapshot.finalized_block,
                "received_ns": now_ns,
                "challenge_id": envelope["challenge_id"],
                "challenge_version": envelope["challenge_version"],
                "session": envelope["session"],
                "request": envelope["request"],
            }
            encoded = canonical(record)
            record_digest = digest(encoded)
            cursor = connection.execute(
                "INSERT INTO receipt(request_key,body_digest,hotkey,received_ns,record,digest) "
                "VALUES (?,?,?,?,?,?)",
                (
                    request_key,
                    body_digest,
                    participant.hotkey,
                    now_ns,
                    encoded.decode(),
                    record_digest,
                ),
            )
            connection.execute(
                "UPDATE transport_meta SET time_ns=?, block=?, snapshot=?, chain_time=? WHERE id=1",
                (
                    now_ns,
                    snapshot.finalized_block,
                    snapshot.snapshot_id,
                    snapshot.timestamp_ms,
                ),
            )
            connection.execute("COMMIT")
            result = AuthenticatedReceipt(
                ReceiptRef(cursor.lastrowid, record_digest), **record
            )
        return result

    def resolve(self, ref: ReceiptRef) -> AuthenticatedReceipt:
        """Consumers resolve retained order/provenance; caller-constructed order is insufficient."""
        if (
            type(ref) is not ReceiptRef
            or type(ref.sequence) is not int
            or not 0 < ref.sequence < 2**63
            or type(ref.digest) is not str
            or len(ref.digest) != 64
        ):
            raise TransportFailure(TransportCode.MALFORMED)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT record,digest FROM receipt WHERE sequence=?", (ref.sequence,)
            ).fetchone()
            if (
                row is None
                or row[1] != ref.digest
                or digest(row[0].encode()) != ref.digest
            ):
                raise TransportFailure(TransportCode.CONFLICT)
            return AuthenticatedReceipt(ref, **json.loads(row[0]))

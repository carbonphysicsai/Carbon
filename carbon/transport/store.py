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
    _MalformedBranch,
    canonical,
    digest,
)

PRUNE_AT = 0.8  # prune old receipts (and alert) at this share of capacity
#: A receipt older than this (by its received time) may be pruned when no journal extension table names it.
PRUNE_AGE_NS = 3600 * 1_000_000_000
#: At most this many receipts go in one admission (bounded work in the admission's transaction).
PRUNE_BATCH = 20_000
#: The columns of a journal extension table that name a receipt by its sequence (`candidates`: ``receipt``,
#: `miner_mcp`: ``receipt_sequence``; any ``*_receipt_sequence`` too). V2 (18 Nov 2026): a receipt a ReceiptRef names
#: (`resolve`) is never pruned.
_REFERENCE_COLUMNS = ("receipt_sequence", "receipt")


def _is_reference(column):
    return column in _REFERENCE_COLUMNS or column.endswith("_receipt_sequence")
_TRANSPORT_TABLES = frozenset({"receipt", "nonce", "transport_meta", "sqlite_sequence"})


def _references(connection):
    """``[(table, column)]`` of every journal extension table column that names a receipt sequence."""
    found = []
    for (table,) in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall():
        if table in _TRANSPORT_TABLES or not table.replace("_", "").isalnum():
            continue
        columns = {
            row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
        }
        found.extend((table, column) for column in sorted(columns) if _is_reference(column))
    return found


def _prune(connection, cutoff_ns, keep_from=None):
    """Delete up to `PRUNE_BATCH` receipts received before ``cutoff_ns`` that no extension table names; returns
    how many went. V2's keep rules (18 Nov 2026): (a) every sequence above ``keep_from`` (a consumer's processed
    watermark, when one is installed: `ReceiptJournal.keep_from`); (b) every sequence an extension table names;
    (c) the highest row (`highest_receipt` never goes back)."""
    top = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM receipt").fetchone()[0]
    limit = top - 1 if keep_from is None else min(top - 1, int(keep_from))
    keep = f"AND sequence <= {int(limit)} " + " ".join(
        f'AND sequence NOT IN (SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL)'
        for table, column in _references(connection)
    )
    return connection.execute(
        "DELETE FROM receipt WHERE sequence IN (SELECT sequence FROM receipt "
        f"WHERE received_ns < ? {keep} ORDER BY received_ns LIMIT ?)",
        (cutoff_ns, PRUNE_BATCH),
    ).rowcount


def _near_cap(held, capacity):
    """An alert line while the journal stays at or above `PRUNE_AT` of its capacity after pruning."""
    if held < capacity * PRUNE_AT:
        return
    try:
        from carbon.battery.intake import log

        log("transport_journal_near_cap", alert=True, held=held, capacity=capacity)
    except Exception:  # noqa: BLE001 - an alert line never refuses intake
        return


class _NonceTransaction:
    def __init__(self, connection):
        self.connection = connection
        self.captured = None

    def check_and_store(self, hotkey_ss58: str, nonce_ns: int) -> bool:
        if type(nonce_ns) is not int or not 0 <= nonce_ns < 2**63:
            raise TransportFailure(
                TransportCode.MALFORMED, _branch=_MalformedBranch.NONCE_RANGE
            )
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
        #: Optional: a consumer's processed watermark (a callable returning a sequence); receipts above it are never
        #: pruned (V2 keep rule (a)). None today: the direct intake handles each request inside its own admission.
        self.keep_from = None
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
                CREATE INDEX IF NOT EXISTS receipt_age ON receipt(received_ns);
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

    def highest_receipt(self) -> int:
        with self._connection() as connection:
            return connection.execute(
                "SELECT COALESCE(MAX(sequence),0) FROM receipt"
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
            held = connection.execute("SELECT COUNT(*) FROM receipt").fetchone()[0]
            if held >= self.capacity * PRUNE_AT:
                # V2 (18 Nov 2026): the receipt table is per-request dedupe only (the replay window is the 10 s nonce
                # and the -2..+60 s clock window): unreferenced receipts older than `PRUNE_AGE_NS` go, in this same
                # transaction, so intake never closes on capacity while old poll rows fill the journal (live 116,
                # 12 and 18 Nov). A receipt any journal extension table names is kept.
                held -= _prune(
                    connection,
                    now_ns - PRUNE_AGE_NS,
                    None if self.keep_from is None else self.keep_from(),
                )
                _near_cap(held, self.capacity)
            if held >= self.capacity:
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
            raise TransportFailure(
                TransportCode.MALFORMED, _branch=_MalformedBranch.RECEIPT_REF
            )
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

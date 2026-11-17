"""Durable publication facts. No local status erases stored chain weights."""

import json
from dataclasses import asdict

from carbon.rewards.intents import StructuralLocalnetWeightIntent
from carbon.rewards.ledger import encode
from carbon.transport.models import digest
from carbon.transport.store import ReceiptJournal

from .models import hash256, uint
from .publication import PublicationFailure

#: The publication DOCUMENT (intent + plan + the observed metagraph snapshot + capabilities) is LOCAL journal storage,
#: not one transport message. The transport meter (`transport.models.canonical`: 4096 JSON nodes, 65536 bytes, sized for a
#: network message) refused it once the snapshot's registered participants grew past the byte cap (116, 17 Nov:
#: TRANSPORT_MALFORMED at prepare, 64,426 bytes and +~470 per epoch, no dispatch written). The journal keeps the SAME
#: canonical bytes (sorted keys, compact, ASCII, no NaN) and every other check of the meter, under bounds sized for a full
#: metagraph (`MetagraphSnapshot` admits at most 65536 participants). Operational storage bounds; they change nothing
#: about the targets, weights or who is paid (the plan is computed and validated exactly as before).
JOURNAL_MAX_NODES = 2_000_000
JOURNAL_MAX_BYTES = 64 * 1024 * 1024
_JOURNAL_MAX_DEPTH = 16


def _journal_meter(value, depth, budget):
    import math

    budget[0] -= 1
    if budget[0] < 0 or depth > _JOURNAL_MAX_DEPTH:
        raise PublicationFailure("JOURNAL_DOCUMENT_MALFORMED")
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise PublicationFailure("JOURNAL_DOCUMENT_MALFORMED")
            _journal_meter(key, depth + 1, budget)
            _journal_meter(child, depth + 1, budget)
    elif type(value) is list:
        for child in value:
            _journal_meter(child, depth + 1, budget)
    elif type(value) is str:
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise PublicationFailure("JOURNAL_DOCUMENT_MALFORMED")
    elif type(value) is int:
        if value.bit_length() > 64:
            raise PublicationFailure("JOURNAL_DOCUMENT_MALFORMED")
    elif type(value) is float:
        if not math.isfinite(value):
            raise PublicationFailure("JOURNAL_DOCUMENT_MALFORMED")
    elif value is not None and type(value) is not bool:
        raise PublicationFailure("JOURNAL_DOCUMENT_MALFORMED")


def journal_encode(value):
    """`rewards.ledger.encode`'s exact canonical bytes for a publication document, under the journal's own bounds
    (identical bytes wherever `encode` accepts the document)."""
    try:
        plain = json.loads(json.dumps(value, allow_nan=False))
    except ValueError:
        raise PublicationFailure("JOURNAL_DOCUMENT_MALFORMED") from None
    _journal_meter(plain, 0, [JOURNAL_MAX_NODES])
    encoded = json.dumps(
        plain, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    if len(encoded) > JOURNAL_MAX_BYTES:
        raise PublicationFailure("JOURNAL_DOCUMENT_OVERSIZED")
    return encoded


TERMINAL = (
    "ROW_VERIFIED",
    "CHAIN_REJECTED",
    "FAILED_BEFORE_SIGNING",
    "EXPOSURE_CHANGED",
)
STATES = (
    *TERMINAL,
    "PREPARED",
    "VALIDATED",
    "SIGNING",
    "DISPATCHED",
    "AMBIGUOUS",
    "INCLUDED",
    "FINALIZED",
    "REVEAL_PENDING",
)


class DispatchJournal:
    def __init__(
        self,
        receipts,
        *,
        network="localnet",
        intent_type=StructuralLocalnetWeightIntent,
    ):
        if (
            type(receipts) is not ReceiptJournal
            or receipts.context.network != network
            or type(intent_type) is not type
        ):
            raise PublicationFailure("NETWORK_JOURNAL_REQUIRED")
        self.receipts = receipts
        self.intent_type = intent_type
        with receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS publication_v1 (identity TEXT PRIMARY KEY, document TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL, tracking TEXT NOT NULL, tracking_digest TEXT NOT NULL)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS publication_state ON publication_v1(state)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS publication_event_v1 (sequence INTEGER PRIMARY KEY AUTOINCREMENT, identity TEXT NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS publication_observation_v1 (identity TEXT PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS publication_tx_v1 (tx_hash TEXT PRIMARY KEY, identity TEXT NOT NULL UNIQUE)"
            )

    def _load(self, db, identity):
        row = db.execute(
            "SELECT document,digest,state,tracking,tracking_digest FROM publication_v1 WHERE identity=?",
            (identity,),
        ).fetchone()
        if row is None:
            return None
        if (
            digest(row[0].encode()) != row[1]
            or digest(row[3].encode()) != row[4]
            or row[2] not in STATES
        ):
            raise PublicationFailure("CONFLICTING_DISPATCH_JOURNAL")
        return {
            "document": json.loads(row[0]),
            "state": row[2],
            "tracking": json.loads(row[3]),
        }

    def get(self, identity):
        with self.receipts.transaction() as db:
            return self._load(db, identity)

    def pending(self):
        with self.receipts.transaction() as db:
            rows = db.execute(
                "SELECT identity FROM publication_v1 WHERE state NOT IN (?,?,?,?)",
                TERMINAL,
            ).fetchall()
            if len(rows) > 1:
                raise PublicationFailure("CONFLICTING_ACTIVE_DISPATCHES")
            return rows[0][0] if rows else None

    def prepare(self, ref, plan, snapshot, capabilities):
        if type(ref) is not self.intent_type or plan.intent_digest != ref.digest:
            raise PublicationFailure("RESOLVED_INTENT_REQUIRED")
        document = journal_encode(
            {
                "intent": asdict(ref),
                "plan": asdict(plan),
                "snapshot": asdict(snapshot),
                "capabilities": asdict(capabilities),
            }
        )
        tracking = encode(
            {
                "tx_hash": None,
                "call_hash": None,
                "integers": None,
                "included_block": None,
                "included_hash": None,
                "finalized_block": None,
                "reveal_round": None,
                "revealed": False,
                "reveal_block": None,
                "stored_row": None,
                "row_block": None,
                "settlement": "UNOBSERVED",
                "scan_block": snapshot.finalized_block,
                "reason": None,
            }
        )
        with self.receipts.transaction() as db:
            existing = self._load(db, ref.digest)
            if existing:
                if existing["document"]["intent"] != asdict(ref):
                    raise PublicationFailure("CONFLICTING_DISPATCH_REPLAY")
                return existing
            if db.execute(
                "SELECT 1 FROM publication_v1 WHERE state NOT IN (?,?,?,?) LIMIT 1",
                TERMINAL,
            ).fetchone():
                raise PublicationFailure("RECONCILE_PENDING_DISPATCH_FIRST")
            if db.execute("SELECT COUNT(*) FROM publication_v1").fetchone()[0] >= 10000:
                raise PublicationFailure("DISPATCH_JOURNAL_CAPACITY")
            db.execute(
                "INSERT INTO publication_v1 VALUES (?,?,?,'PREPARED',?,?)",
                (
                    ref.digest,
                    document,
                    digest(document.encode()),
                    tracking,
                    digest(tracking.encode()),
                ),
            )
            db.execute(
                "INSERT INTO publication_event_v1(identity,state,body) VALUES (?,'PREPARED',?)",
                (ref.digest, tracking),
            )
            return self._load(db, ref.digest)

    def update(self, identity, state, **changes):
        if state not in STATES:
            raise PublicationFailure("INVALID_DISPATCH_STATE")
        with self.receipts.transaction() as db:
            row = self._load(db, identity)
            if row is None:
                raise PublicationFailure("UNKNOWN_DISPATCH")
            tracking = row["tracking"]
            if not set(changes) <= set(tracking):
                raise PublicationFailure("INVALID_DISPATCH_FACT")
            if row["state"] in TERMINAL and (
                state != row["state"]
                or any(tracking[k] != v for k, v in changes.items())
            ):
                raise PublicationFailure("CONFLICTING_TERMINAL_RECEIPT")
            if "tx_hash" in changes:
                hash256(changes["tx_hash"])
                if tracking["tx_hash"] not in (None, changes["tx_hash"]):
                    raise PublicationFailure("CONFLICTING_TRANSACTION_IDENTITY")
                prior = db.execute(
                    "SELECT identity FROM publication_tx_v1 WHERE tx_hash=?",
                    (changes["tx_hash"],),
                ).fetchone()
                if prior and prior[0] != identity:
                    raise PublicationFailure(
                        "TRANSACTION_ALREADY_BOUND_TO_ANOTHER_INTENT"
                    )
                db.execute(
                    "INSERT OR IGNORE INTO publication_tx_v1 VALUES (?,?)",
                    (changes["tx_hash"], identity),
                )
            if state in (
                "DISPATCHED",
                "INCLUDED",
                "FINALIZED",
                "REVEAL_PENDING",
                "ROW_VERIFIED",
                "CHAIN_REJECTED",
                "EXPOSURE_CHANGED",
            ) and not (changes.get("tx_hash") or tracking["tx_hash"]):
                raise PublicationFailure("TRANSACTION_IDENTITY_REQUIRED")
            if state == "EXPOSURE_CHANGED" and tracking["finalized_block"] is None:
                raise PublicationFailure("FINALIZED_DISPATCH_REQUIRED")
            if state == "FAILED_BEFORE_SIGNING" and (
                tracking["tx_hash"] or row["state"] not in ("PREPARED", "VALIDATED")
            ):
                raise PublicationFailure("AMBIGUOUS_DISPATCH_CANNOT_BE_RESET")
            tracking.update(changes)
            body = encode(tracking)
            db.execute(
                "UPDATE publication_v1 SET state=?,tracking=?,tracking_digest=? WHERE identity=?",
                (state, body, digest(body.encode()), identity),
            )
            db.execute(
                "INSERT INTO publication_event_v1(identity,state,body) VALUES (?,?,?)",
                (identity, state, body),
            )
            return self._load(db, identity)

    def observe_settlement(self, identity, observation_id, block, facts):
        """Store separate bounded chain-observed facts; never infer target equality."""
        uint(block)
        if type(observation_id) is not str or not 1 <= len(observation_id) <= 128:
            raise PublicationFailure("INVALID_OBSERVATION_ID")
        allowed = {
            "miner_burned",
            "burn_mode",
            "epoch",
            "alpha_issuance",
            "owner_cut",
            "validator_dividends",
            "miner_incentives",
        }
        if type(facts) is not dict or not facts or not set(facts) <= allowed:
            raise PublicationFailure("INVALID_SETTLEMENT_OBSERVATION")
        body = encode(
            {
                "dispatch": identity,
                "block": block,
                "facts": facts,
                "meaning": "OBSERVATION_NOT_TARGET_EQUALITY",
            }
        )
        with self.receipts.transaction() as db:
            row = self._load(db, identity)
            if (
                row is None
                or row["tracking"]["finalized_block"] is None
                or block < row["tracking"]["finalized_block"]
            ):
                raise PublicationFailure("FINALIZED_DISPATCH_REQUIRED")
            old = db.execute(
                "SELECT body,digest FROM publication_observation_v1 WHERE identity=?",
                (observation_id,),
            ).fetchone()
            if old and (old[0] != body or old[1] != digest(body.encode())):
                raise PublicationFailure("CONFLICTING_SETTLEMENT_OBSERVATION")
            db.execute(
                "INSERT OR IGNORE INTO publication_observation_v1 VALUES (?,?,?)",
                (observation_id, body, digest(body.encode())),
            )
        return json.loads(body)

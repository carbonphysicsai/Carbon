"""Candidate extension of the existing durable authenticated receipt journal."""

import json
import sqlite3
from dataclasses import asdict

from carbon.fees.strategy_identity import identify_strategy
from carbon.transport.models import ReceiptRef, canonical, digest, parse_message
from carbon.transport.store import ReceiptJournal

from .model import (
    AcceptedFixtureRecord,
    CandidateCode,
    CandidateFailure,
    CandidateRef,
    FixtureEvaluationContext,
)


class CandidateJournal:
    def __init__(
        self,
        receipts: ReceiptJournal,
        context: FixtureEvaluationContext,
        limits,
        *,
        capacity=10000,
    ):
        if (
            type(receipts) is not ReceiptJournal
            or type(context) is not FixtureEvaluationContext
        ):
            raise CandidateFailure(CandidateCode.CONTEXT)
        if type(capacity) is not int or not 1 <= capacity <= 10000:
            raise CandidateFailure(CandidateCode.CAPACITY)
        self.receipts, self.context, self.limits, self.capacity = (
            receipts,
            context,
            limits,
            capacity,
        )
        with receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS candidate_context_v1 (challenge TEXT PRIMARY KEY, identity TEXT NOT NULL)"
            )
            db.execute("""CREATE TABLE IF NOT EXISTS candidate_v1 (
                identity TEXT PRIMARY KEY, context TEXT NOT NULL, strategy_hash TEXT NOT NULL,
                artifact BLOB NOT NULL, artifact_digest TEXT NOT NULL,
                receipt INTEGER NOT NULL, receipt_digest TEXT NOT NULL,
                state TEXT NOT NULL, accepted TEXT, accepted_digest TEXT,
                UNIQUE(context, strategy_hash))""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS candidate_context_order ON candidate_v1(context, receipt)"
            )
            key = canonical(asdict(context.pack.challenge_key)).decode()
            db.execute(
                "INSERT OR IGNORE INTO candidate_context_v1 VALUES (?,?)",
                (key, context.identity),
            )
            if db.execute(
                "SELECT identity FROM candidate_context_v1 WHERE challenge=?", (key,)
            ).fetchone() != (context.identity,):
                raise CandidateFailure(CandidateCode.CONFLICT)

    def commit(self, receipt_ref: ReceiptRef, body: bytes) -> CandidateRef:
        receipt = self.receipts.resolve(receipt_ref)
        wire = parse_message(body)
        key = self.context.pack.challenge_key
        if receipt.body_digest != digest(body):
            raise CandidateFailure(CandidateCode.CONFLICT)
        if (receipt.challenge_id, receipt.challenge_version) != (
            key.challenge_id,
            key.version,
        ):
            raise CandidateFailure(CandidateCode.CONTEXT)
        if wire["tool"] != "submit" or set(wire["fields"]) != {
            "challenge_id",
            "challenge_version",
            "strategy",
        }:
            raise CandidateFailure(CandidateCode.ARTIFACT)
        identity = identify_strategy(wire["fields"]["strategy"], self.limits)
        if (
            identity.strategy_hash is None
            or identity.strategy is None
            or identity.strategy.get("challenge_id") != key.challenge_id
        ):
            raise CandidateFailure(CandidateCode.ARTIFACT)
        artifact = canonical(identity.strategy)
        strategy_hash = identity.strategy_hash.value
        ref = CandidateRef(
            digest(
                canonical(["carbon.candidate.v1", self.context.identity, strategy_hash])
            )
        )
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT artifact,receipt,state FROM candidate_v1 WHERE identity=?",
                (ref.identity,),
            ).fetchone()
            if row:
                if row[0] != artifact:
                    raise CandidateFailure(CandidateCode.CONFLICT)
                if receipt.ref.sequence < row[1]:
                    # Earlier authenticated delivery may be processed later. Once
                    # admitted, never rewrite winner provenance behind consumers.
                    if row[2] != "COMMITTED":
                        raise CandidateFailure(CandidateCode.CONFLICT)
                    db.execute(
                        "UPDATE candidate_v1 SET receipt=?,receipt_digest=? WHERE identity=?",
                        (receipt.ref.sequence, receipt.ref.digest, ref.identity),
                    )
                return ref
            if (
                db.execute("SELECT count(*) FROM candidate_v1").fetchone()[0]
                >= self.capacity
            ):
                raise CandidateFailure(CandidateCode.CAPACITY)
            db.execute(
                "INSERT INTO candidate_v1 VALUES (?,?,?,?,?,?,?,'COMMITTED',NULL,NULL)",
                (
                    ref.identity,
                    self.context.identity,
                    strategy_hash,
                    artifact,
                    digest(artifact),
                    receipt.ref.sequence,
                    receipt.ref.digest,
                ),
            )
        return ref

    def _row(self, db, ref):
        if (
            type(ref) is not CandidateRef
            or type(ref.identity) is not str
            or len(ref.identity) != 64
        ):
            raise CandidateFailure(CandidateCode.ARTIFACT)
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM candidate_v1 WHERE identity=? AND context=?",
            (ref.identity, self.context.identity),
        ).fetchone()
        if row is None or digest(row["artifact"]) != row["artifact_digest"]:
            raise CandidateFailure(CandidateCode.ARTIFACT)
        return row

    def state(self, ref):
        with self.receipts.transaction() as db:
            return self._row(db, ref)["state"]

    def _claim(self, ref):
        """Durable intent before A7 side effects; ambiguous work is not reissued."""
        with self.receipts.transaction() as db:
            row = self._row(db, ref)
            if row["state"] != "COMMITTED":
                raise CandidateFailure(CandidateCode.INDETERMINATE)
            db.execute(
                "UPDATE candidate_v1 SET state='DISPATCHING' WHERE identity=?",
                (ref.identity,),
            )
            return json.loads(row["artifact"]), ReceiptRef(
                row["receipt"], row["receipt_digest"]
            )

    def _transition(self, ref, expected, state):
        with self.receipts.transaction() as db:
            self._row(db, ref)
            if (
                db.execute(
                    "UPDATE candidate_v1 SET state=? WHERE identity=? AND state=?",
                    (state, ref.identity, expected),
                ).rowcount
                != 1
            ):
                raise CandidateFailure(CandidateCode.CONFLICT)

    def _complete_fixture(self, record):
        """Private adapter seam: the service calls only after A7 publication."""
        encoded = canonical(
            {**asdict(record), "candidate": record.candidate.identity}
        ).decode()
        with self.receipts.transaction() as db:
            row = self._row(db, record.candidate)
            if row["state"] == "ACCEPTED_FIXTURE" and row["accepted"] == encoded:
                return
            if row["state"] != "RUNNING" or row["receipt"] != record.receipt_sequence:
                raise CandidateFailure(CandidateCode.CONFLICT)
            db.execute(
                "UPDATE candidate_v1 SET state='ACCEPTED_FIXTURE',accepted=?,accepted_digest=? WHERE identity=?",
                (encoded, digest(encoded.encode()), record.candidate.identity),
            )

    def resolve_accepted_fixture(self, ref):
        with self.receipts.transaction() as db:
            row = self._row(db, ref)
            if row["state"] != "ACCEPTED_FIXTURE":
                raise CandidateFailure(CandidateCode.NOT_ACCEPTED)
            encoded = row["accepted"]
            if digest(encoded.encode()) != row["accepted_digest"]:
                raise CandidateFailure(CandidateCode.CONFLICT)
            value = json.loads(encoded)
            value["candidate"] = CandidateRef(value["candidate"])
            value["component_hex"] = tuple(value["component_hex"])
            return AcceptedFixtureRecord(**value)

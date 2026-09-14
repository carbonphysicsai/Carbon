"""Atomic append-only SQLite ledger for C-06 DEVELOPMENT receipts."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .model import (
    GENESIS_ENTRY_DIGEST,
    LEDGER_SCHEMA,
    AuditCode,
    AuditFailure,
    DevelopmentEvaluationReceipt,
    DevelopmentEvidenceBinding,
    DevelopmentRunStatus,
    LedgerCheckpoint,
    LedgerEventKind,
    LedgerReceiptRef,
    ReceiptLifecycleState,
    ReceiptWriteDisposition,
    ScientificDecisionState,
    SignedDevelopmentEvaluationReceipt,
    canonical_json,
    digest_bytes,
    validate_digest,
)
from .signing import DevelopmentVerificationKey, verify_signed_receipt

_MIGRATION = """
CREATE TABLE IF NOT EXISTS audit_meta_v1 (
    id INTEGER PRIMARY KEY CHECK(id=1), schema TEXT NOT NULL,
    migration_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS development_receipt_v1 (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id TEXT NOT NULL UNIQUE,
    receipt_digest TEXT NOT NULL UNIQUE,
    body TEXT NOT NULL,
    signature BLOB NOT NULL,
    signing_key_id TEXT NOT NULL,
    public_key_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS development_receipt_event_v1 (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    related_receipt_id TEXT,
    reason_digest TEXT,
    previous_entry_digest TEXT NOT NULL,
    payload TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    entry_digest TEXT NOT NULL UNIQUE
);
"""
_MIGRATION_DIGEST = digest_bytes(_MIGRATION.encode("ascii"))
_STATEMENTS = tuple(part.strip() for part in _MIGRATION.split(";") if part.strip())


@dataclass(frozen=True, slots=True)
class FrozenEvidenceIndex:
    """Trusted controller snapshot of evidence already available by digest."""

    digests: frozenset[str]

    def __post_init__(self) -> None:
        if type(self.digests) is not frozenset:
            raise AuditFailure(AuditCode.INVALID)
        object.__setattr__(
            self, "digests", frozenset(validate_digest(item) for item in self.digests)
        )

    def contains(self, digest: str) -> bool:
        return validate_digest(digest) in self.digests


def _decode_signed(body: str, signature: bytes) -> SignedDevelopmentEvaluationReceipt:
    try:
        value = json.loads(body)
        binding = value["binding"]
        reconstruction = binding["reconstruction"]
        inference = binding["inference"]
        reference = binding["reference"]
        measurement = binding["measurement"]
        execution = binding["execution"]
        challenge = binding["challenge"]
        authority = value["authority"]
        signer = value["signer"]
        if (
            set(value)
            != {
                "authority",
                "binding",
                "finished_at_micros",
                "receipt_id",
                "receipt_schema_version",
                "run_status",
                "signer",
                "started_at_micros",
                "supersedes_receipt_id",
            }
            or set(authority)
            != {
                "archive_acknowledged",
                "marker",
                "network_eligible",
                "protected_execution_eligible",
                "reward_eligible",
                "score_eligible",
                "signing_scope",
            }
            or set(signer) != {"algorithm", "key_id", "public_key_digest"}
        ):
            raise ValueError
        owned_binding = DevelopmentEvidenceBinding(
            submission_id=binding["submission_id"],
            strategy_digest=binding["strategy_digest"],
            challenge_id=challenge["id"],
            challenge_version=challenge["version"],
            generator_digest=binding["generator_digest"],
            target_population_digest=binding["target_population_digest"],
            sampling_plan_digest=binding["sampling_plan_digest"],
            training_data_commitment=binding["training_data_commitment"],
            reconstruction_plan_digest=reconstruction["plan_digest"],
            repeat_plan_digest=reconstruction["repeat_plan_digest"],
            resource_policy_digest=reconstruction["resource_policy_digest"],
            reconstruction_outcome_digest=reconstruction["outcome_digest"],
            reconstruction_attempt_digests=tuple(reconstruction["attempt_digests"]),
            inference_request_digest=inference["request_digest"],
            prediction_digest=inference["prediction_digest"],
            reference_policy_digest=reference["policy_digest"],
            reference_implementation_digest=reference["implementation_digest"],
            reference_environment_digest=reference["environment_digest"],
            reference_artifact_digest=reference["artifact_digest"],
            measurement_contract_digest=measurement["contract_digest"],
            measurement_implementation_digest=measurement["implementation_digest"],
            measurement_environment_digest=measurement["environment_digest"],
            measurement_result_digest=measurement["result_digest"],
            scoring_policy_digest=binding["scoring_policy_digest"],
            dossier_digest=binding["dossier_digest"],
            qualification_manifest_digest=binding["qualification_manifest_digest"],
            source_tree_digest=execution["source_tree_digest"],
            worker_image_digest=execution["worker_image_digest"],
            execution_policy_digest=execution["execution_policy_digest"],
            uncertainty_state=ScientificDecisionState(binding["uncertainty_state"]),
            scientific_qualification_state=ScientificDecisionState(
                binding["scientific_qualification_state"]
            ),
        )
        receipt = DevelopmentEvaluationReceipt(
            receipt_id=value["receipt_id"],
            binding=owned_binding,
            run_status=DevelopmentRunStatus(value["run_status"]),
            started_at_micros=value["started_at_micros"],
            finished_at_micros=value["finished_at_micros"],
            signing_key_id=signer["key_id"],
            signing_public_key_digest=signer["public_key_digest"],
            supersedes_receipt_id=value["supersedes_receipt_id"],
            receipt_schema_version=value["receipt_schema_version"],
            authority_marker=authority["marker"],
            signing_scope=authority["signing_scope"],
            protected_execution_eligible=authority["protected_execution_eligible"],
            score_eligible=authority["score_eligible"],
            archive_acknowledged=authority["archive_acknowledged"],
            network_eligible=authority["network_eligible"],
            reward_eligible=authority["reward_eligible"],
        )
        if signer["algorithm"] != "Ed25519" or receipt.canonical_bytes.decode() != body:
            raise ValueError
        return SignedDevelopmentEvaluationReceipt(receipt, bytes(signature))
    except (KeyError, TypeError, ValueError, AuditFailure):
        raise AuditFailure(AuditCode.STORE) from None


class DevelopmentEvidenceLedger:
    """Append-only development receipt ledger; never an official result store."""

    def __init__(
        self,
        path: Path,
        verification_keys: tuple[DevelopmentVerificationKey, ...],
    ) -> None:
        if not isinstance(path, Path) or type(verification_keys) is not tuple:
            raise AuditFailure(AuditCode.INVALID)
        keys: dict[str, DevelopmentVerificationKey] = {}
        for item in verification_keys:
            if type(item) is not DevelopmentVerificationKey or item.key_id in keys:
                raise AuditFailure(AuditCode.INVALID)
            keys[item.key_id] = item
        if not keys:
            raise AuditFailure(AuditCode.INVALID)
        self.path = path
        self._keys = keys
        with self._transaction() as database:
            for statement in _STATEMENTS:
                database.execute(statement)
            database.execute(
                "INSERT OR IGNORE INTO audit_meta_v1 VALUES (1,?,?)",
                (LEDGER_SCHEMA, _MIGRATION_DIGEST),
            )
            if database.execute(
                "SELECT schema,migration_digest FROM audit_meta_v1 WHERE id=1"
            ).fetchone() != (LEDGER_SCHEMA, _MIGRATION_DIGEST):
                raise AuditFailure(AuditCode.STORE)
        self.verify_integrity()

    @contextmanager
    def _transaction(self):
        database = None
        try:
            database = sqlite3.connect(self.path, timeout=2, isolation_level=None)
            database.execute("PRAGMA synchronous=FULL")
            database.execute("BEGIN IMMEDIATE")
            yield database
            database.execute("COMMIT")
        except AuditFailure:
            if database is not None:
                database.execute("ROLLBACK")
            raise
        except sqlite3.Error:
            if database is not None:
                try:
                    database.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise AuditFailure(AuditCode.STORE) from None
        finally:
            if database is not None:
                database.close()

    @staticmethod
    def _head(database: sqlite3.Connection) -> tuple[int, str]:
        row = database.execute(
            "SELECT sequence,entry_digest FROM development_receipt_event_v1 "
            "ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return (0, GENESIS_ENTRY_DIGEST) if row is None else (row[0], row[1])

    @staticmethod
    def _state(database: sqlite3.Connection, receipt_id: str) -> ReceiptLifecycleState:
        events = database.execute(
            "SELECT kind FROM development_receipt_event_v1 "
            "WHERE receipt_id=? ORDER BY sequence",
            (receipt_id,),
        ).fetchall()
        if not events:
            raise AuditFailure(AuditCode.STATE)
        if events[0][0] != LedgerEventKind.RECEIPT_APPENDED.value:
            raise AuditFailure(AuditCode.STORE)
        state = ReceiptLifecycleState.ACTIVE
        for (kind,) in events[1:]:
            if (
                kind == LedgerEventKind.RECEIPT_SUPERSEDED.value
                and state is ReceiptLifecycleState.ACTIVE
            ):
                state = ReceiptLifecycleState.SUPERSEDED
            elif (
                kind == LedgerEventKind.RECEIPT_REVOKED.value
                and state is ReceiptLifecycleState.ACTIVE
            ):
                state = ReceiptLifecycleState.REVOKED
            else:
                raise AuditFailure(AuditCode.STORE)
        return state

    @staticmethod
    def _append_event(
        database: sqlite3.Connection,
        *,
        kind: LedgerEventKind,
        receipt_id: str,
        related_receipt_id: str | None,
        reason_digest: str | None,
    ) -> tuple[int, str]:
        _, previous = DevelopmentEvidenceLedger._head(database)
        payload = canonical_json(
            {
                "kind": kind.value,
                "reason_digest": reason_digest,
                "receipt_id": receipt_id,
                "related_receipt_id": related_receipt_id,
            }
        )
        payload_digest = digest_bytes(payload)
        entry_digest = digest_bytes(
            canonical_json(
                {
                    "payload_digest": payload_digest,
                    "previous_entry_digest": previous,
                }
            )
        )
        cursor = database.execute(
            "INSERT INTO development_receipt_event_v1 "
            "(kind,receipt_id,related_receipt_id,reason_digest,"
            "previous_entry_digest,payload,payload_digest,entry_digest) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                kind.value,
                receipt_id,
                related_receipt_id,
                reason_digest,
                previous,
                payload.decode("ascii"),
                payload_digest,
                entry_digest,
            ),
        )
        return cursor.lastrowid, entry_digest

    def append(
        self,
        signed: SignedDevelopmentEvaluationReceipt,
        evidence: FrozenEvidenceIndex,
        *,
        verified_at_micros: int,
    ) -> tuple[ReceiptWriteDisposition, LedgerReceiptRef]:
        if (
            type(signed) is not SignedDevelopmentEvaluationReceipt
            or type(evidence) is not FrozenEvidenceIndex
            or type(verified_at_micros) is not int
        ):
            raise AuditFailure(AuditCode.INVALID)
        receipt = signed.receipt
        key = self._keys.get(receipt.signing_key_id)
        if key is None:
            raise AuditFailure(AuditCode.SIGNATURE)
        verify_signed_receipt(signed, key, verified_at_micros=verified_at_micros)
        if any(
            not evidence.contains(item)
            for item in receipt.binding.required_evidence_digests()
        ):
            raise AuditFailure(AuditCode.MISSING_EVIDENCE)

        body = receipt.canonical_bytes.decode("ascii")
        with self._transaction() as database:
            prior = database.execute(
                "SELECT sequence,receipt_digest FROM development_receipt_v1 "
                "WHERE receipt_id=?",
                (receipt.receipt_id,),
            ).fetchone()
            if prior is not None:
                if prior[1] != receipt.receipt_digest:
                    raise AuditFailure(AuditCode.CONFLICT)
                event = database.execute(
                    "SELECT entry_digest FROM development_receipt_event_v1 "
                    "WHERE receipt_id=? AND kind=?",
                    (receipt.receipt_id, LedgerEventKind.RECEIPT_APPENDED.value),
                ).fetchone()
                if event is None:
                    raise AuditFailure(AuditCode.STORE)
                return ReceiptWriteDisposition.ALREADY_PRESENT, LedgerReceiptRef(
                    prior[0], receipt.receipt_id, receipt.receipt_digest, event[0]
                )

            supersedes = receipt.supersedes_receipt_id
            if supersedes is not None and (
                database.execute(
                    "SELECT 1 FROM development_receipt_v1 WHERE receipt_id=?",
                    (supersedes,),
                ).fetchone()
                is None
                or self._state(database, supersedes) is not ReceiptLifecycleState.ACTIVE
            ):
                raise AuditFailure(AuditCode.STATE)

            cursor = database.execute(
                "INSERT INTO development_receipt_v1 "
                "(receipt_id,receipt_digest,body,signature,signing_key_id,"
                "public_key_digest) VALUES (?,?,?,?,?,?)",
                (
                    receipt.receipt_id,
                    receipt.receipt_digest,
                    body,
                    signed.signature,
                    receipt.signing_key_id,
                    receipt.signing_public_key_digest,
                ),
            )
            _, entry_digest = self._append_event(
                database,
                kind=LedgerEventKind.RECEIPT_APPENDED,
                receipt_id=receipt.receipt_id,
                related_receipt_id=supersedes,
                reason_digest=None,
            )
            if supersedes is not None:
                self._append_event(
                    database,
                    kind=LedgerEventKind.RECEIPT_SUPERSEDED,
                    receipt_id=supersedes,
                    related_receipt_id=receipt.receipt_id,
                    reason_digest=None,
                )
            return ReceiptWriteDisposition.APPENDED, LedgerReceiptRef(
                cursor.lastrowid,
                receipt.receipt_id,
                receipt.receipt_digest,
                entry_digest,
            )

    def revoke(self, receipt_id: str, reason_digest: str) -> LedgerCheckpoint:
        validate_digest(reason_digest)
        with self._transaction() as database:
            if self._state(database, receipt_id) is not ReceiptLifecycleState.ACTIVE:
                raise AuditFailure(AuditCode.STATE)
            sequence, entry_digest = self._append_event(
                database,
                kind=LedgerEventKind.RECEIPT_REVOKED,
                receipt_id=receipt_id,
                related_receipt_id=None,
                reason_digest=reason_digest,
            )
            count = database.execute(
                "SELECT COUNT(*) FROM development_receipt_v1"
            ).fetchone()[0]
            return LedgerCheckpoint(sequence, entry_digest, count)

    def resolve(
        self, reference: LedgerReceiptRef, *, verified_at_micros: int
    ) -> tuple[SignedDevelopmentEvaluationReceipt, ReceiptLifecycleState]:
        if type(reference) is not LedgerReceiptRef:
            raise AuditFailure(AuditCode.INVALID)
        with self._transaction() as database:
            row = database.execute(
                "SELECT sequence,receipt_digest,body,signature,signing_key_id,"
                "public_key_digest FROM development_receipt_v1 WHERE receipt_id=?",
                (reference.receipt_id,),
            ).fetchone()
            if row is None:
                raise AuditFailure(AuditCode.STATE)
            event = database.execute(
                "SELECT entry_digest FROM development_receipt_event_v1 "
                "WHERE receipt_id=? AND kind=?",
                (reference.receipt_id, LedgerEventKind.RECEIPT_APPENDED.value),
            ).fetchone()
            if (
                row[0] != reference.sequence
                or row[1] != reference.receipt_digest
                or event is None
                or event[0] != reference.entry_digest
                or digest_bytes(row[2].encode("ascii")) != row[1]
            ):
                raise AuditFailure(AuditCode.STORE)
            signed = _decode_signed(row[2], row[3])
            if (
                signed.receipt.signing_key_id != row[4]
                or signed.receipt.signing_public_key_digest != row[5]
            ):
                raise AuditFailure(AuditCode.STORE)
            key = self._keys.get(row[4])
            if key is None:
                raise AuditFailure(AuditCode.SIGNATURE)
            verify_signed_receipt(signed, key, verified_at_micros=verified_at_micros)
            return signed, self._state(database, reference.receipt_id)

    def checkpoint(self) -> LedgerCheckpoint:
        with self._transaction() as database:
            sequence, entry_digest = self._head(database)
            count = database.execute(
                "SELECT COUNT(*) FROM development_receipt_v1"
            ).fetchone()[0]
            return LedgerCheckpoint(sequence, entry_digest, count)

    def verify_integrity(self) -> None:
        with self._transaction() as database:
            previous = GENESIS_ENTRY_DIGEST
            appended_receipts: set[str] = set()
            states: dict[str, ReceiptLifecycleState] = {}
            for row in database.execute(
                "SELECT sequence,kind,receipt_id,related_receipt_id,reason_digest,"
                "previous_entry_digest,payload,payload_digest,entry_digest "
                "FROM development_receipt_event_v1 ORDER BY sequence"
            ):
                payload = canonical_json(
                    {
                        "kind": row[1],
                        "reason_digest": row[4],
                        "receipt_id": row[2],
                        "related_receipt_id": row[3],
                    }
                )
                if (
                    row[5] != previous
                    or row[6] != payload.decode("ascii")
                    or row[7] != digest_bytes(payload)
                    or row[8]
                    != digest_bytes(
                        canonical_json(
                            {
                                "payload_digest": row[7],
                                "previous_entry_digest": previous,
                            }
                        )
                    )
                ):
                    raise AuditFailure(AuditCode.STORE)
                if row[1] == LedgerEventKind.RECEIPT_APPENDED.value:
                    if (
                        row[2] in appended_receipts
                        or row[4] is not None
                        or (
                            row[3] is not None
                            and (
                                row[3] not in states
                                or states[row[3]] is not ReceiptLifecycleState.ACTIVE
                            )
                        )
                    ):
                        raise AuditFailure(AuditCode.STORE)
                    appended_receipts.add(row[2])
                    states[row[2]] = ReceiptLifecycleState.ACTIVE
                elif row[1] == LedgerEventKind.RECEIPT_SUPERSEDED.value:
                    if (
                        row[2] not in states
                        or states[row[2]] is not ReceiptLifecycleState.ACTIVE
                        or row[3] not in states
                        or row[3] == row[2]
                        or row[4] is not None
                    ):
                        raise AuditFailure(AuditCode.STORE)
                    states[row[2]] = ReceiptLifecycleState.SUPERSEDED
                elif row[1] == LedgerEventKind.RECEIPT_REVOKED.value:
                    if (
                        row[2] not in states
                        or states[row[2]] is not ReceiptLifecycleState.ACTIVE
                        or row[3] is not None
                        or row[4] is None
                    ):
                        raise AuditFailure(AuditCode.STORE)
                    validate_digest(row[4])
                    states[row[2]] = ReceiptLifecycleState.REVOKED
                else:
                    raise AuditFailure(AuditCode.STORE)
                previous = row[8]
            stored_receipts: set[str] = set()
            for (
                body,
                receipt_digest,
                signature,
                key_id,
                public_key_digest,
                receipt_id,
            ) in database.execute(
                "SELECT body,receipt_digest,signature,signing_key_id,"
                "public_key_digest,receipt_id FROM development_receipt_v1"
            ):
                signed = _decode_signed(body, signature)
                if (
                    signed.receipt.receipt_digest != receipt_digest
                    or signed.receipt.receipt_id != receipt_id
                    or signed.receipt.signing_key_id != key_id
                    or signed.receipt.signing_public_key_digest != public_key_digest
                ):
                    raise AuditFailure(AuditCode.STORE)
                stored_receipts.add(receipt_id)
            if stored_receipts != appended_receipts:
                raise AuditFailure(AuditCode.STORE)

"""SQLite-backed C1 queue with crash-visible, non-duplicating dispatch."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    StrategyHash,
    SubmissionId,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, SeedPin

from .model import (
    ArchiveRequirement,
    ClaimedExecution,
    DurableExecutionBinding,
    ExecutionAttemptRef,
    ExecutionCode,
    ExecutionFailure,
    ExecutionResultRefs,
    ExecutionScope,
    ExecutionStage,
    ExecutionState,
    ExecutionStatusView,
    PartialWorkRef,
    QueueClaim,
    ReconciliationDisposition,
    WriteDisposition,
    validate_execution_token,
)

_SCHEMA = "c1-durable-execution/1"
_WORKER_ATTACHMENT_TOKEN = object()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: str) -> str:
    return (
        "sha256:"
        + hashlib.sha256(b"carbon.c1.execution.v1\0" + value.encode()).hexdigest()
    )


def _binding_payload(binding: DurableExecutionBinding) -> dict[str, object]:
    handle = binding.handle
    pin = handle.seed_pin
    return {
        "schema_version": "c1-execution-binding/1",
        "submission_id": handle.submission_id.value,
        "attempt_number": handle.attempt_number,
        "admission_kind": handle.admission_kind.value,
        "requester_identity": binding.requester_identity.value,
        "strategy_hash": binding.strategy_hash.value,
        "scope": binding.scope.value,
        "challenge": {
            "challenge_id": pin.challenge_key.challenge_id,
            "version": pin.challenge_key.version,
        },
        "generator_version": pin.generator_version,
        "generator_digest": pin.generator_digest,
        "scoring_version": pin.scoring_version,
        "scoring_digest": pin.scoring_digest,
        "evaluation_binding": pin.evaluation_binding._copy_bytes().hex(),
        "environment": {
            "backend_profile_id": handle.environment_pin.backend_profile_id,
            "container_digest": handle.environment_pin.container_digest,
        },
        "resolved_plan_digest": binding.resolved_plan_digest,
        "reconstruction_policy_digest": binding.reconstruction_policy_digest,
        "resource_policy_digest": binding.resource_policy_digest,
        "protected_evaluation_policy_digest": binding.protected_evaluation_policy_digest,
    }


def _load_binding(encoded: str) -> DurableExecutionBinding:
    try:
        value = json.loads(encoded)
        if (
            set(value)
            != {
                "schema_version",
                "submission_id",
                "attempt_number",
                "admission_kind",
                "requester_identity",
                "strategy_hash",
                "scope",
                "challenge",
                "generator_version",
                "generator_digest",
                "scoring_version",
                "scoring_digest",
                "evaluation_binding",
                "environment",
                "resolved_plan_digest",
                "reconstruction_policy_digest",
                "resource_policy_digest",
                "protected_evaluation_policy_digest",
            }
            or value["schema_version"] != "c1-execution-binding/1"
        ):
            raise ValueError
        challenge = value["challenge"]
        environment = value["environment"]
        pin = SeedPin(
            challenge_key=ChallengeKey(challenge["challenge_id"], challenge["version"]),
            generator_version=value["generator_version"],
            generator_digest=value["generator_digest"],
            scoring_version=value["scoring_version"],
            scoring_digest=value["scoring_digest"],
            evaluation_binding=EvaluationBinding(
                bytes.fromhex(value["evaluation_binding"])
            ),
        )
        handle = ExecutionAttemptHandle(
            submission_id=SubmissionId(value["submission_id"]),
            attempt_number=value["attempt_number"],
            admission_kind=AdmissionKind(value["admission_kind"]),
            seed_pin=pin,
            environment_pin=ExecutionEnvironmentPin(
                environment["backend_profile_id"], environment["container_digest"]
            ),
        )
        return DurableExecutionBinding(
            handle=handle,
            requester_identity=RequesterIdentity(value["requester_identity"]),
            strategy_hash=StrategyHash(value["strategy_hash"]),
            scope=ExecutionScope(value["scope"]),
            resolved_plan_digest=value["resolved_plan_digest"],
            reconstruction_policy_digest=value["reconstruction_policy_digest"],
            resource_policy_digest=value["resource_policy_digest"],
            protected_evaluation_policy_digest=value[
                "protected_evaluation_policy_digest"
            ],
        )
    except Exception:  # noqa: BLE001 - corrupt private state has one stable class.
        raise ExecutionFailure(ExecutionCode.STORE) from None


def _result_payload(value: ExecutionResultRefs) -> dict[str, object]:
    return {
        "schema_version": "c1-result-association/1",
        "private_result_ref": value.private_result_ref,
        "private_result_digest": value.private_result_digest,
        "card_record_ref": value.card_record_ref,
        "transcript_ref": value.transcript_ref,
        "transcript_digest": value.transcript_digest,
        "archive_requirement": value.archive_requirement.value,
        "archive_acknowledgement_ref": None,
    }


class DurableExecutionQueue:
    """Private queue owner; consumers receive only explicit trusted views."""

    def __init__(
        self,
        path: Path,
        *,
        capacity: int = 10_000,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        _attachment_token: object | None = None,
    ) -> None:
        if (
            type(capacity) is not int
            or not 1 <= capacity <= 100_000
            or not callable(id_factory)
            or _attachment_token not in (None, _WORKER_ATTACHMENT_TOKEN)
        ):
            raise ExecutionFailure(ExecutionCode.INVALID)
        recover_interrupted = _attachment_token is None
        self.path = Path(path)
        self.capacity = capacity
        self._id_factory = id_factory
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS execution_meta_v1 (
                    id INTEGER PRIMARY KEY CHECK(id=1), schema_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS execution_attempt_v1 (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    requester_identity TEXT NOT NULL,
                    binding TEXT NOT NULL,
                    binding_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    claim_id TEXT UNIQUE,
                    worker_id TEXT,
                    result TEXT,
                    result_digest TEXT,
                    UNIQUE(submission_id, attempt_number)
                );
                CREATE INDEX IF NOT EXISTS execution_ready_v1
                    ON execution_attempt_v1(state, sequence);
                CREATE TABLE IF NOT EXISTS execution_partial_v1 (
                    submission_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    artifact_ref TEXT NOT NULL,
                    artifact_digest TEXT NOT NULL,
                    PRIMARY KEY(submission_id, attempt_number, stage)
                );
                CREATE TABLE IF NOT EXISTS execution_event_v1 (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    body TEXT NOT NULL,
                    body_digest TEXT NOT NULL
                );
                """)
            # ``executescript`` owns its transaction boundary.  Start the
            # recovery transaction only after the schema is durable so the
            # metadata check and interrupted-attempt transition are atomic.
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO execution_meta_v1 VALUES (1,?)", (_SCHEMA,)
            )
            if db.execute(
                "SELECT schema_version FROM execution_meta_v1 WHERE id=1"
            ).fetchone() != (_SCHEMA,):
                raise ExecutionFailure(ExecutionCode.STORE)
            for body, body_digest in db.execute(
                "SELECT body,body_digest FROM execution_event_v1"
            ):
                if _digest(body) != body_digest:
                    raise ExecutionFailure(ExecutionCode.STORE)
            if recover_interrupted:
                interrupted = db.execute(
                    "SELECT submission_id,attempt_number,state FROM execution_attempt_v1 "
                    "WHERE state IN ('DISPATCHING','RUNNING')"
                ).fetchall()
                for submission_id, attempt_number, old_state in interrupted:
                    db.execute(
                        "UPDATE execution_attempt_v1 SET state=? WHERE submission_id=? AND attempt_number=?",
                        (
                            ExecutionState.RECONCILIATION_REQUIRED.value,
                            submission_id,
                            attempt_number,
                        ),
                    )
                    self._event(
                        db,
                        submission_id,
                        attempt_number,
                        "RESTART_RECONCILIATION_REQUIRED",
                        {"prior_state": old_state},
                    )
            db.execute("COMMIT")
        except ExecutionFailure:
            if db is not None and db.in_transaction:
                db.execute("ROLLBACK")
            raise
        except sqlite3.Error:
            if db is not None and db.in_transaction:
                db.execute("ROLLBACK")
            raise ExecutionFailure(ExecutionCode.STORE) from None
        finally:
            if db is not None:
                db.close()

    @classmethod
    def attach(
        cls,
        path: Path,
        *,
        capacity: int = 10_000,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> DurableExecutionQueue:
        """Open a worker connection without declaring an owner restart."""
        return cls(
            path,
            capacity=capacity,
            id_factory=id_factory,
            _attachment_token=_WORKER_ATTACHMENT_TOKEN,
        )

    @contextmanager
    def _transaction(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except ExecutionFailure:
            if db is not None and db.in_transaction:
                db.execute("ROLLBACK")
            raise
        except sqlite3.Error:
            if db is not None and db.in_transaction:
                db.execute("ROLLBACK")
            raise ExecutionFailure(ExecutionCode.STORE) from None
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _event(
        db, submission_id: str, attempt_number: int, kind: str, body: object
    ) -> None:
        encoded = _canonical(body)
        db.execute(
            "INSERT INTO execution_event_v1(submission_id,attempt_number,kind,body,body_digest) VALUES (?,?,?,?,?)",
            (submission_id, attempt_number, kind, encoded, _digest(encoded)),
        )

    @staticmethod
    def _owned_ref(value: object) -> ExecutionAttemptRef:
        if type(value) is not ExecutionAttemptRef:
            raise ExecutionFailure(ExecutionCode.INVALID)
        return ExecutionAttemptRef(value.submission_id, value.attempt_number)

    @staticmethod
    def _owned_claim(value: object) -> QueueClaim:
        if type(value) is not QueueClaim:
            raise ExecutionFailure(ExecutionCode.INVALID)
        return QueueClaim(value.ref, value.claim_id, value.worker_id)

    @staticmethod
    def _row(db, ref: ExecutionAttemptRef):
        row = db.execute(
            "SELECT requester_identity,binding,binding_digest,state,claim_id,worker_id,result,result_digest "
            "FROM execution_attempt_v1 WHERE submission_id=? AND attempt_number=?",
            (ref.submission_id.value, ref.attempt_number),
        ).fetchone()
        if row is None:
            raise ExecutionFailure(ExecutionCode.NOT_FOUND)
        if _digest(row[1]) != row[2]:
            raise ExecutionFailure(ExecutionCode.STORE)
        try:
            state = ExecutionState(row[3])
        except ValueError:
            raise ExecutionFailure(ExecutionCode.STORE) from None
        claimed = row[4] is not None and row[5] is not None
        result_recorded = row[6] is not None and row[7] is not None
        if (
            (row[4] is None) != (row[5] is None)
            or (row[6] is None) != (row[7] is None)
            or claimed
            != (
                state
                in {
                    ExecutionState.DISPATCHING,
                    ExecutionState.RUNNING,
                    ExecutionState.RECONCILIATION_REQUIRED,
                    ExecutionState.RETRYABLE_INFRA,
                    ExecutionState.RESULT_RECORDED,
                    ExecutionState.FAILED_INFRA,
                    ExecutionState.FAILED_STRATEGY,
                }
            )
            or result_recorded != (state is ExecutionState.RESULT_RECORDED)
            or (result_recorded and _digest(row[6]) != row[7])
        ):
            raise ExecutionFailure(ExecutionCode.STORE)
        return row

    @staticmethod
    def _partial_rows(db, ref: ExecutionAttemptRef) -> tuple[PartialWorkRef, ...]:
        rows = db.execute(
            "SELECT stage,artifact_ref,artifact_digest FROM execution_partial_v1 "
            "WHERE submission_id=? AND attempt_number=? ORDER BY rowid",
            (ref.submission_id.value, ref.attempt_number),
        ).fetchall()
        try:
            return tuple(
                PartialWorkRef(ExecutionStage(stage), artifact_ref, artifact_digest)
                for stage, artifact_ref, artifact_digest in rows
            )
        except (ValueError, ExecutionFailure):
            raise ExecutionFailure(ExecutionCode.STORE) from None

    def admit(self, binding: DurableExecutionBinding) -> WriteDisposition:
        if type(binding) is not DurableExecutionBinding:
            raise ExecutionFailure(ExecutionCode.INVALID)
        binding = _load_binding(_canonical(_binding_payload(binding)))
        ref = binding.ref
        encoded = _canonical(_binding_payload(binding))
        digest = _digest(encoded)
        with self._transaction() as db:
            old = db.execute(
                "SELECT binding,binding_digest FROM execution_attempt_v1 WHERE submission_id=? AND attempt_number=?",
                (ref.submission_id.value, ref.attempt_number),
            ).fetchone()
            if old:
                if old != (encoded, digest):
                    raise ExecutionFailure(ExecutionCode.CONFLICT)
                return WriteDisposition.ALREADY_PRESENT
            if (
                db.execute("SELECT count(*) FROM execution_attempt_v1").fetchone()[0]
                >= self.capacity
            ):
                raise ExecutionFailure(ExecutionCode.CAPACITY)
            previous = db.execute(
                "SELECT attempt_number,state,binding FROM execution_attempt_v1 WHERE submission_id=? ORDER BY attempt_number DESC LIMIT 1",
                (ref.submission_id.value,),
            ).fetchone()
            if previous is not None:
                if (
                    previous[0] + 1 != ref.attempt_number
                    or previous[1] != ExecutionState.RETRYABLE_INFRA.value
                ):
                    raise ExecutionFailure(ExecutionCode.CONFLICT)
                old_binding = _load_binding(previous[2])
                if (
                    old_binding.requester_identity != binding.requester_identity
                    or old_binding.strategy_hash != binding.strategy_hash
                    or old_binding.handle.seed_pin != binding.handle.seed_pin
                    or old_binding.handle.environment_pin
                    != binding.handle.environment_pin
                    or old_binding.scope is not binding.scope
                    or old_binding.resolved_plan_digest != binding.resolved_plan_digest
                    or old_binding.reconstruction_policy_digest
                    != binding.reconstruction_policy_digest
                    or old_binding.resource_policy_digest
                    != binding.resource_policy_digest
                    or old_binding.protected_evaluation_policy_digest
                    != binding.protected_evaluation_policy_digest
                ):
                    raise ExecutionFailure(ExecutionCode.CONFLICT)
            elif ref.attempt_number != 1:
                raise ExecutionFailure(ExecutionCode.CONFLICT)
            db.execute(
                "INSERT INTO execution_attempt_v1(submission_id,attempt_number,requester_identity,binding,binding_digest,state) VALUES (?,?,?,?,?,?)",
                (
                    ref.submission_id.value,
                    ref.attempt_number,
                    binding.requester_identity.value,
                    encoded,
                    digest,
                    ExecutionState.QUEUED.value,
                ),
            )
            self._event(
                db,
                ref.submission_id.value,
                ref.attempt_number,
                "ADMITTED",
                {"scope": binding.scope.value},
            )
        return WriteDisposition.INSERTED

    def claim_next(
        self, worker_id: str, *, claim_id: str | None = None
    ) -> ClaimedExecution | None:
        try:
            worker_id = validate_execution_token(worker_id)
            if claim_id is None:
                minted = self._id_factory()
                if type(minted) is not uuid.UUID:
                    raise ValueError
                claim_id = str(minted)
            claim_id = validate_execution_token(claim_id)
        except Exception:  # noqa: BLE001
            raise ExecutionFailure(ExecutionCode.INVALID) from None
        with self._transaction() as db:
            replay = db.execute(
                "SELECT submission_id,attempt_number,worker_id,binding,binding_digest FROM execution_attempt_v1 WHERE claim_id=?",
                (claim_id,),
            ).fetchone()
            if replay:
                if replay[2] != worker_id or _digest(replay[3]) != replay[4]:
                    raise ExecutionFailure(ExecutionCode.CONFLICT)
                ref = ExecutionAttemptRef(SubmissionId(replay[0]), replay[1])
                return ClaimedExecution(
                    QueueClaim(ref, claim_id, worker_id), _load_binding(replay[3])
                )
            row = db.execute(
                "SELECT submission_id,attempt_number,binding,binding_digest FROM execution_attempt_v1 WHERE state=? ORDER BY sequence LIMIT 1",
                (ExecutionState.QUEUED.value,),
            ).fetchone()
            if row is None:
                return None
            if _digest(row[2]) != row[3]:
                raise ExecutionFailure(ExecutionCode.STORE)
            if (
                db.execute(
                    "UPDATE execution_attempt_v1 SET state=?,claim_id=?,worker_id=? WHERE submission_id=? AND attempt_number=? AND state=?",
                    (
                        ExecutionState.DISPATCHING.value,
                        claim_id,
                        worker_id,
                        row[0],
                        row[1],
                        ExecutionState.QUEUED.value,
                    ),
                ).rowcount
                != 1
            ):
                raise ExecutionFailure(ExecutionCode.CONFLICT)
            self._event(
                db,
                row[0],
                row[1],
                "CLAIMED_DISPATCH_INTENT",
                {"claim_id": claim_id, "worker_id": worker_id},
            )
            ref = ExecutionAttemptRef(SubmissionId(row[0]), row[1])
            return ClaimedExecution(
                QueueClaim(ref, claim_id, worker_id), _load_binding(row[2])
            )

    def _claimed_row(self, db, claim: QueueClaim):
        row = self._row(db, claim.ref)
        if row[4] != claim.claim_id or row[5] != claim.worker_id:
            raise ExecutionFailure(ExecutionCode.CONFLICT)
        return row

    def mark_running(self, claim: QueueClaim) -> WriteDisposition:
        claim = self._owned_claim(claim)
        with self._transaction() as db:
            row = self._claimed_row(db, claim)
            state = ExecutionState(row[3])
            if state is ExecutionState.RUNNING:
                return WriteDisposition.ALREADY_PRESENT
            if state is not ExecutionState.DISPATCHING:
                raise ExecutionFailure(ExecutionCode.STATE)
            db.execute(
                "UPDATE execution_attempt_v1 SET state=? WHERE submission_id=? AND attempt_number=?",
                (
                    ExecutionState.RUNNING.value,
                    claim.ref.submission_id.value,
                    claim.ref.attempt_number,
                ),
            )
            self._event(
                db,
                claim.ref.submission_id.value,
                claim.ref.attempt_number,
                "RUNNING",
                {"claim_id": claim.claim_id},
            )
        return WriteDisposition.INSERTED

    def reconcile(
        self, claim: QueueClaim, disposition: ReconciliationDisposition
    ) -> ExecutionState:
        claim = self._owned_claim(claim)
        if type(disposition) is not ReconciliationDisposition:
            raise ExecutionFailure(ExecutionCode.INVALID)
        target = (
            ExecutionState.QUEUED
            if disposition is ReconciliationDisposition.NOT_DISPATCHED
            else ExecutionState.RUNNING
        )
        with self._transaction() as db:
            row = self._claimed_row(db, claim)
            if ExecutionState(row[3]) is not ExecutionState.RECONCILIATION_REQUIRED:
                raise ExecutionFailure(ExecutionCode.STATE)
            if target is ExecutionState.QUEUED:
                db.execute(
                    "UPDATE execution_attempt_v1 SET state=?,claim_id=NULL,worker_id=NULL WHERE submission_id=? AND attempt_number=?",
                    (
                        target.value,
                        claim.ref.submission_id.value,
                        claim.ref.attempt_number,
                    ),
                )
            else:
                db.execute(
                    "UPDATE execution_attempt_v1 SET state=? WHERE submission_id=? AND attempt_number=?",
                    (
                        target.value,
                        claim.ref.submission_id.value,
                        claim.ref.attempt_number,
                    ),
                )
            self._event(
                db,
                claim.ref.submission_id.value,
                claim.ref.attempt_number,
                "RECONCILED",
                {"disposition": disposition.value},
            )
        return target

    def record_partial(
        self, claim: QueueClaim, partial: PartialWorkRef
    ) -> WriteDisposition:
        claim = self._owned_claim(claim)
        if type(partial) is not PartialWorkRef:
            raise ExecutionFailure(ExecutionCode.INVALID)
        partial = PartialWorkRef(
            partial.stage, partial.artifact_ref, partial.artifact_digest
        )
        with self._transaction() as db:
            row = self._claimed_row(db, claim)
            if ExecutionState(row[3]) not in {
                ExecutionState.RUNNING,
                ExecutionState.RECONCILIATION_REQUIRED,
            }:
                raise ExecutionFailure(ExecutionCode.STATE)
            old = db.execute(
                "SELECT artifact_ref,artifact_digest FROM execution_partial_v1 WHERE submission_id=? AND attempt_number=? AND stage=?",
                (
                    claim.ref.submission_id.value,
                    claim.ref.attempt_number,
                    partial.stage.value,
                ),
            ).fetchone()
            expected = (partial.artifact_ref, partial.artifact_digest)
            if old:
                if old != expected:
                    raise ExecutionFailure(ExecutionCode.CONFLICT)
                return WriteDisposition.ALREADY_PRESENT
            db.execute(
                "INSERT INTO execution_partial_v1 VALUES (?,?,?,?,?)",
                (
                    claim.ref.submission_id.value,
                    claim.ref.attempt_number,
                    partial.stage.value,
                    *expected,
                ),
            )
            self._event(
                db,
                claim.ref.submission_id.value,
                claim.ref.attempt_number,
                "PARTIAL_WORK_RECORDED",
                {
                    "stage": partial.stage.value,
                    "artifact_ref": partial.artifact_ref,
                    "artifact_digest": partial.artifact_digest,
                },
            )
        return WriteDisposition.INSERTED

    def partials(self, claim: QueueClaim) -> tuple[PartialWorkRef, ...]:
        """Return verified resumable work only to the worker holding the claim."""

        claim = self._owned_claim(claim)
        with self._transaction() as db:
            row = self._claimed_row(db, claim)
            if ExecutionState(row[3]) not in {
                ExecutionState.RUNNING,
                ExecutionState.RECONCILIATION_REQUIRED,
            }:
                raise ExecutionFailure(ExecutionCode.STATE)
            return self._partial_rows(db, claim.ref)

    def record_result(
        self, claim: QueueClaim, result: ExecutionResultRefs
    ) -> WriteDisposition:
        claim = self._owned_claim(claim)
        if type(result) is not ExecutionResultRefs:
            raise ExecutionFailure(ExecutionCode.INVALID)
        result = ExecutionResultRefs(
            result.private_result_ref,
            result.private_result_digest,
            result.card_record_ref,
            result.transcript_ref,
            result.transcript_digest,
            result.archive_requirement,
            result.archive_acknowledgement_ref,
        )
        encoded = _canonical(_result_payload(result))
        result_digest = _digest(encoded)
        with self._transaction() as db:
            row = self._claimed_row(db, claim)
            state = ExecutionState(row[3])
            if state is ExecutionState.RESULT_RECORDED:
                if row[6:] != (encoded, result_digest):
                    raise ExecutionFailure(ExecutionCode.CONFLICT)
                return WriteDisposition.ALREADY_PRESENT
            if state not in {
                ExecutionState.RUNNING,
                ExecutionState.RECONCILIATION_REQUIRED,
            }:
                raise ExecutionFailure(ExecutionCode.STATE)
            db.execute(
                "UPDATE execution_attempt_v1 SET state=?,result=?,result_digest=? WHERE submission_id=? AND attempt_number=?",
                (
                    ExecutionState.RESULT_RECORDED.value,
                    encoded,
                    result_digest,
                    claim.ref.submission_id.value,
                    claim.ref.attempt_number,
                ),
            )
            self._event(
                db,
                claim.ref.submission_id.value,
                claim.ref.attempt_number,
                "RESULT_RECORDED_NOT_FINALIZED",
                {
                    "archive_requirement": ArchiveRequirement.C_EA2_ACKNOWLEDGEMENT_REQUIRED.value
                },
            )
        return WriteDisposition.INSERTED

    def _terminal(self, claim: QueueClaim, target: ExecutionState) -> WriteDisposition:
        claim = self._owned_claim(claim)
        if target not in {
            ExecutionState.RETRYABLE_INFRA,
            ExecutionState.FAILED_INFRA,
            ExecutionState.FAILED_STRATEGY,
        }:
            raise ExecutionFailure(ExecutionCode.INVALID)
        with self._transaction() as db:
            row = self._claimed_row(db, claim)
            state = ExecutionState(row[3])
            if state is target:
                return WriteDisposition.ALREADY_PRESENT
            if state is not ExecutionState.RUNNING:
                raise ExecutionFailure(ExecutionCode.STATE)
            db.execute(
                "UPDATE execution_attempt_v1 SET state=? WHERE submission_id=? AND attempt_number=?",
                (target.value, claim.ref.submission_id.value, claim.ref.attempt_number),
            )
            self._event(
                db,
                claim.ref.submission_id.value,
                claim.ref.attempt_number,
                target.value,
                {},
            )
        return WriteDisposition.INSERTED

    def retryable_infrastructure(self, claim: QueueClaim) -> WriteDisposition:
        return self._terminal(claim, ExecutionState.RETRYABLE_INFRA)

    def fail_infrastructure(self, claim: QueueClaim) -> WriteDisposition:
        return self._terminal(claim, ExecutionState.FAILED_INFRA)

    def fail_strategy(self, claim: QueueClaim) -> WriteDisposition:
        return self._terminal(claim, ExecutionState.FAILED_STRATEGY)

    def cancel(
        self, ref: ExecutionAttemptRef, requester: RequesterIdentity
    ) -> WriteDisposition:
        ref = self._owned_ref(ref)
        try:
            requester = RequesterIdentity(requester.value)
        except Exception:  # noqa: BLE001
            raise ExecutionFailure(ExecutionCode.INVALID) from None
        with self._transaction() as db:
            row = self._row(db, ref)
            if row[0] != requester.value:
                raise ExecutionFailure(ExecutionCode.DENIED)
            state = ExecutionState(row[3])
            if state is ExecutionState.CANCELLED:
                return WriteDisposition.ALREADY_PRESENT
            if state is not ExecutionState.QUEUED:
                raise ExecutionFailure(ExecutionCode.STATE)
            db.execute(
                "UPDATE execution_attempt_v1 SET state=? WHERE submission_id=? AND attempt_number=?",
                (
                    ExecutionState.CANCELLED.value,
                    ref.submission_id.value,
                    ref.attempt_number,
                ),
            )
            self._event(
                db, ref.submission_id.value, ref.attempt_number, "CANCELLED", {}
            )
        return WriteDisposition.INSERTED

    def status(
        self, ref: ExecutionAttemptRef, requester: RequesterIdentity
    ) -> ExecutionStatusView:
        ref = self._owned_ref(ref)
        try:
            requester = RequesterIdentity(requester.value)
        except Exception:  # noqa: BLE001
            raise ExecutionFailure(ExecutionCode.INVALID) from None
        with self._transaction() as db:
            row = self._row(db, ref)
            if row[0] != requester.value:
                raise ExecutionFailure(ExecutionCode.DENIED)
            count = len(self._partial_rows(db, ref))
            state = ExecutionState(row[3])
        return ExecutionStatusView(
            schema_version="c1-execution-status/1",
            submission_id=ref.submission_id,
            attempt_number=ref.attempt_number,
            state=state,
            partial_stage_count=count,
            result_recorded=state is ExecutionState.RESULT_RECORDED,
            archive_acknowledged=False,
        )

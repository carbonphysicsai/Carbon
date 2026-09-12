"""Additive pack ledger in the existing authenticated receipt database."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict

from carbon.candidates.model import CandidateRef
from carbon.candidates.store import CandidateJournal
from carbon.cards import EvaluationCard, EvaluationComponentScores, EvaluationGateResult
from carbon.execution import (
    DurableExecutionQueue,
    ExecutionAttemptRef,
    ExecutionFailure,
    ExecutionState,
    ExecutionStatusView,
)
from carbon.fees import RequesterIdentity, SubmissionId
from carbon.registry import is_sha256_digest
from carbon.transport.models import ReceiptRef, canonical, digest

from .model import (
    DevelopmentPackPolicy,
    DevelopmentPackStatus,
    EvaluationPackIdentity,
    PackAssignment,
    PackAttemptBinding,
    PackCode,
    PackFailure,
    PackState,
    PackWriteDisposition,
)

_SCHEMA = "development-evaluation-pack-ledger/1"
_MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS candidate_pack_meta_v1 (
    id INTEGER PRIMARY KEY CHECK(id=1),
    schema_version TEXT NOT NULL,
    migration_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_pack_v1 (
    candidate TEXT PRIMARY KEY,
    identity TEXT NOT NULL UNIQUE,
    parent_context TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    case_selection_id TEXT NOT NULL,
    binding TEXT NOT NULL,
    binding_digest TEXT NOT NULL,
    state TEXT NOT NULL,
    attempt_number INTEGER,
    execution_ref TEXT,
    materialization TEXT,
    execution_digest TEXT,
    result_digest TEXT,
    summary TEXT,
    summary_digest TEXT,
    delivered INTEGER NOT NULL DEFAULT 0 CHECK(delivered IN (0,1)),
    created_ns INTEGER NOT NULL,
    closed_ns INTEGER
);
CREATE TABLE IF NOT EXISTS candidate_pack_event_v1 (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate TEXT NOT NULL,
    kind TEXT NOT NULL,
    elapsed_ns INTEGER NOT NULL,
    body TEXT NOT NULL,
    body_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_pack_attempt_v1 (
    candidate TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    execution_ref TEXT NOT NULL UNIQUE,
    materialization TEXT NOT NULL,
    materialization_digest TEXT NOT NULL,
    PRIMARY KEY(candidate, attempt_number)
);
"""
_MIGRATION_DIGEST = digest(_MIGRATION_001.encode())
_MIGRATION_001_STATEMENTS = tuple(
    statement.strip() for statement in _MIGRATION_001.split(";") if statement.strip()
)


def _card_payload(card: EvaluationCard) -> dict[str, object]:
    return {
        "schema_version": card.schema_version,
        "result_id": card.result_id,
        "status": card.status,
        "scoring_pack_hash": card.scoring_pack_hash,
        "overall_score": card.overall_score,
        "component_scores": (
            None if card.component_scores is None else asdict(card.component_scores)
        ),
        "gate_results": [asdict(value) for value in card.gate_results],
        "failure_tags": list(card.failure_tags),
        "fixture_origin": card.fixture_origin,
        "eligible_for_emission": card.eligible_for_emission,
        "public_diagnostics": list(card.public_diagnostics),
        "disclosure_tier": card.disclosure_tier,
    }


def _load_card(encoded: str) -> EvaluationCard:
    try:
        value = json.loads(encoded)
        components = value["component_scores"]
        return EvaluationCard(
            schema_version=value["schema_version"],
            result_id=value["result_id"],
            status=value["status"],
            scoring_pack_hash=value["scoring_pack_hash"],
            overall_score=value["overall_score"],
            component_scores=(
                None if components is None else EvaluationComponentScores(**components)
            ),
            gate_results=tuple(
                EvaluationGateResult(**item) for item in value["gate_results"]
            ),
            failure_tags=tuple(value["failure_tags"]),
            fixture_origin=value["fixture_origin"],
            eligible_for_emission=value["eligible_for_emission"],
            public_diagnostics=tuple(value["public_diagnostics"]),
            disclosure_tier=value["disclosure_tier"],
        )
    except Exception:  # noqa: BLE001 - corrupt private state is one class.
        raise PackFailure(PackCode.STORE) from None


def _bound_result_digest(
    pack_identity: str,
    attempt_number: int,
    configuration_digest: str,
    card: EvaluationCard,
) -> str:
    return "sha256:" + digest(
        canonical(
            {
                "schema_version": "development-pack-result-association/1",
                "evaluation_pack": pack_identity,
                "attempt_number": attempt_number,
                "configuration_digest": configuration_digest,
                "result_id": card.result_id,
                "status": card.status,
                "scoring_pack_hash": card.scoring_pack_hash,
                "overall_score": card.overall_score,
            }
        )
    )


class DevelopmentEvaluationPackLedger:
    """One pack per existing candidate job; no sharing or production route."""

    def __init__(
        self,
        journal: CandidateJournal,
        *,
        capacity: int = 10_000,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if (
            type(journal) is not CandidateJournal
            or type(capacity) is not int
            or not 1 <= capacity <= 10_000
            or not callable(id_factory)
            or not callable(clock_ns)
        ):
            raise PackFailure(PackCode.INVALID)
        self.journal = journal
        self.capacity = capacity
        self._id_factory = id_factory
        self._clock_ns = clock_ns
        self.policy = DevelopmentPackPolicy()
        self.case_selection_id = digest(
            canonical(
                [
                    "carbon.fixture-pack-case-selection.v1",
                    journal.context.identity,
                    journal.context.pack.generator_version_required,
                    journal.context.pack.generator_digest_required,
                    "A4_FIXTURE_OFFICIAL",
                ]
            )
        )
        with journal.receipts.transaction() as db:
            # ``executescript`` commits any open sqlite transaction first.  Issue
            # each additive statement instead so schema installation and the
            # checksum pin share the journal's BEGIN IMMEDIATE boundary.
            for statement in _MIGRATION_001_STATEMENTS:
                db.execute(statement)
            db.execute(
                "INSERT OR IGNORE INTO candidate_pack_meta_v1 VALUES (1,?,?)",
                (_SCHEMA, _MIGRATION_DIGEST),
            )
            if db.execute(
                "SELECT schema_version,migration_digest FROM candidate_pack_meta_v1 WHERE id=1"
            ).fetchone() != (_SCHEMA, _MIGRATION_DIGEST):
                raise PackFailure(PackCode.STORE)
            for body, body_digest in db.execute(
                "SELECT body,body_digest FROM candidate_pack_event_v1"
            ):
                if digest(body.encode()) != body_digest:
                    raise PackFailure(PackCode.STORE)
            for materialization, materialization_digest in db.execute(
                "SELECT materialization,materialization_digest FROM candidate_pack_attempt_v1"
            ):
                if digest(materialization.encode()) != materialization_digest:
                    raise PackFailure(PackCode.STORE)

    def _row(self, db, candidate: CandidateRef):
        if type(candidate) is not CandidateRef:
            raise PackFailure(PackCode.INVALID)
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM candidate_pack_v1 WHERE candidate=?", (candidate.identity,)
        ).fetchone()
        if row is None:
            raise PackFailure(PackCode.NOT_FOUND)
        if digest(row["binding"].encode()) != row["binding_digest"]:
            raise PackFailure(PackCode.STORE)
        try:
            binding = json.loads(row["binding"])
            nonce = binding["allocation_nonce"]
            binding_matches = (
                binding["schema_version"] == "evaluation-pack-binding/1"
                and binding["identity"] == row["identity"]
                and binding["parent_context"] == row["parent_context"]
                and binding["policy_id"] == row["policy_id"]
                and binding["case_selection_id"] == row["case_selection_id"]
                and type(nonce) is str
                and row["parent_context"] == self.journal.context.identity
                and row["policy_id"] == self.policy.identity
                and row["case_selection_id"] == self.case_selection_id
                and row["identity"]
                == digest(
                    canonical(
                        [
                            "carbon.evaluation-pack.v1",
                            row["parent_context"],
                            row["policy_id"],
                            row["case_selection_id"],
                            nonce,
                        ]
                    )
                )
            )
        except Exception:  # noqa: BLE001 - malformed private state fails closed.
            raise PackFailure(PackCode.STORE) from None
        if not binding_matches:
            raise PackFailure(PackCode.STORE)
        try:
            state = PackState(row["state"])
        except ValueError:
            raise PackFailure(PackCode.STORE) from None
        if (row["summary"] is None) != (row["summary_digest"] is None):
            raise PackFailure(PackCode.STORE)
        if (
            (row["execution_ref"] is None) != (row["materialization"] is None)
            or (row["materialization"] is None) != (row["execution_digest"] is None)
            or (
                row["materialization"] is not None
                and digest(row["materialization"].encode()) != row["execution_digest"]
            )
        ):
            raise PackFailure(PackCode.STORE)
        if (
            row["summary"] is not None
            and digest(row["summary"].encode()) != row["summary_digest"]
        ):
            raise PackFailure(PackCode.STORE)
        has_attempt = row["execution_ref"] is not None
        has_summary = row["summary"] is not None
        has_result = row["result_digest"] is not None
        is_closed = row["closed_ns"] is not None
        delivered = row["delivered"] == 1
        valid_shape = {
            PackState.ASSIGNED: (False, False, False, False, False),
            PackState.ATTEMPT_BOUND: (True, False, False, False, False),
            PackState.RESULT_RECORDED: (True, True, True, False, False),
            PackState.CLOSED: (True, True, True, True, False),
            PackState.SUMMARY_DELIVERED: (True, True, True, True, True),
            PackState.INCOMPLETE_CLOSED: (True, False, False, True, False),
            PackState.CANCELLED: (True, False, False, True, False),
        }.get(state)
        if valid_shape is not None and valid_shape != (
            has_attempt,
            has_summary,
            has_result,
            is_closed,
            delivered,
        ):
            raise PackFailure(PackCode.STORE)
        if state is PackState.RECONCILIATION_REQUIRED and (
            has_summary or has_result or is_closed or delivered
        ):
            raise PackFailure(PackCode.STORE)
        attempt_rows = db.execute(
            "SELECT attempt_number,execution_ref,materialization,materialization_digest "
            "FROM candidate_pack_attempt_v1 WHERE candidate=? ORDER BY attempt_number",
            (row["candidate"],),
        ).fetchall()
        if has_attempt:
            if (
                row["attempt_number"] != len(attempt_rows)
                or [item["attempt_number"] for item in attempt_rows]
                != list(range(1, len(attempt_rows) + 1))
                or tuple(attempt_rows[-1])[1:]
                != (
                    row["execution_ref"],
                    row["materialization"],
                    row["execution_digest"],
                )
            ):
                raise PackFailure(PackCode.STORE)
            baseline_materialization = None
            immutable = (
                "schema_version",
                "pack",
                "candidate",
                "submission_id",
                "artifact_digest",
                "configuration_digest",
                "evaluation_binding_digest",
            )
            for item in attempt_rows:
                try:
                    materialization = json.loads(item["materialization"])
                    expected_ref = (
                        f'{materialization["submission_id"]}:'
                        f'{materialization["attempt_number"]}'
                    )
                    valid = (
                        digest(item["materialization"].encode())
                        == item["materialization_digest"]
                        and materialization["schema_version"]
                        == "evaluation-pack-materialization/1"
                        and materialization["pack"] == row["identity"]
                        and materialization["candidate"] == row["candidate"]
                        and materialization["attempt_number"] == item["attempt_number"]
                        and item["execution_ref"] == expected_ref
                        and materialization["evaluation_binding_digest"]
                        == digest(bytes.fromhex(row["identity"]))
                    )
                except Exception:  # noqa: BLE001 - malformed state fails closed.
                    raise PackFailure(PackCode.STORE) from None
                if not valid:
                    raise PackFailure(PackCode.STORE)
                if baseline_materialization is None:
                    baseline_materialization = materialization
                elif any(
                    baseline_materialization[key] != materialization[key]
                    for key in immutable
                ):
                    raise PackFailure(PackCode.STORE)
        elif attempt_rows:
            raise PackFailure(PackCode.STORE)
        if has_result:
            try:
                card = _load_card(row["summary"])
                materialization = json.loads(row["materialization"])
                expected = _bound_result_digest(
                    row["identity"],
                    row["attempt_number"],
                    materialization["configuration_digest"],
                    card,
                )
            except Exception:  # noqa: BLE001 - malformed state fails closed.
                raise PackFailure(PackCode.STORE) from None
            if row["result_digest"] != expected:
                raise PackFailure(PackCode.STORE)
        return row

    @staticmethod
    def _assignment(row) -> PackAssignment:
        return PackAssignment(
            CandidateRef(row["candidate"]),
            EvaluationPackIdentity(
                row["identity"],
                row["parent_context"],
                row["policy_id"],
                row["case_selection_id"],
            ),
        )

    def _event(
        self, db, candidate: CandidateRef, kind: str, start_ns: int, body: object
    ) -> None:
        if (
            db.execute(
                "SELECT count(*) FROM candidate_pack_event_v1 WHERE candidate=?",
                (candidate.identity,),
            ).fetchone()[0]
            >= 64
        ):
            raise PackFailure(PackCode.CAPACITY)
        encoded = canonical(body).decode()
        elapsed = self._clock_ns() - start_ns
        if elapsed < 0:
            raise PackFailure(PackCode.STORE)
        db.execute(
            "INSERT INTO candidate_pack_event_v1(candidate,kind,elapsed_ns,body,body_digest) VALUES (?,?,?,?,?)",
            (candidate.identity, kind, elapsed, encoded, digest(encoded.encode())),
        )

    def assign(
        self, candidate: CandidateRef
    ) -> tuple[PackAssignment, PackWriteDisposition]:
        start = self._clock_ns()
        with self.journal.receipts.transaction() as db:
            existing = db.execute(
                "SELECT candidate FROM candidate_pack_v1 WHERE candidate=?",
                (candidate.identity,),
            ).fetchone()
            if existing:
                return (
                    self._assignment(self._row(db, candidate)),
                    PackWriteDisposition.ALREADY_PRESENT,
                )
            row = self.journal._row(db, candidate)
            if row["state"] != "COMMITTED":
                raise PackFailure(PackCode.STATE)
            if db.execute(
                "SELECT 1 FROM candidate_reward_batch_v1 WHERE candidate=?",
                (candidate.identity,),
            ).fetchone():
                raise PackFailure(PackCode.CONFLICT)
            if (
                db.execute("SELECT count(*) FROM candidate_pack_v1").fetchone()[0]
                >= self.capacity
            ):
                raise PackFailure(PackCode.CAPACITY)
            try:
                nonce = str(self._id_factory())
            except Exception:  # noqa: BLE001
                raise PackFailure(PackCode.STORE) from None
            identity = digest(
                canonical(
                    [
                        "carbon.evaluation-pack.v1",
                        self.journal.context.identity,
                        self.policy.identity,
                        self.case_selection_id,
                        nonce,
                    ]
                )
            )
            binding = canonical(
                {
                    "schema_version": "evaluation-pack-binding/1",
                    "identity": identity,
                    "parent_context": self.journal.context.identity,
                    "policy_id": self.policy.identity,
                    "case_selection_id": self.case_selection_id,
                    "allocation_nonce": nonce,
                }
            ).decode()
            db.execute(
                "INSERT INTO candidate_pack_v1(candidate,identity,parent_context,policy_id,case_selection_id,binding,binding_digest,state,created_ns) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    candidate.identity,
                    identity,
                    self.journal.context.identity,
                    self.policy.identity,
                    self.case_selection_id,
                    binding,
                    digest(binding.encode()),
                    PackState.ASSIGNED.value,
                    start,
                ),
            )
            db.execute(
                "UPDATE candidate_v1 SET state='PACK_ASSIGNED' WHERE identity=? AND state='COMMITTED'",
                (candidate.identity,),
            )
            assignment = self._assignment(self._row(db, candidate))
            self._event(
                db,
                candidate,
                "PACK_ASSIGNED",
                start,
                {"state": PackState.ASSIGNED.value},
            )
            return assignment, PackWriteDisposition.INSERTED

    def candidate_inputs(
        self, assignment: PackAssignment
    ) -> tuple[dict[str, object], ReceiptRef]:
        with self.journal.receipts.transaction() as db:
            row = self._row(db, assignment.candidate)
            if (
                self._assignment(row) != assignment
                or PackState(row["state"]) is not PackState.ASSIGNED
            ):
                raise PackFailure(PackCode.STATE)
            candidate = self.journal._row(db, assignment.candidate)
            if candidate["state"] != "PACK_ASSIGNED":
                raise PackFailure(PackCode.CONFLICT)
            return json.loads(candidate["artifact"]), ReceiptRef(
                candidate["receipt"], candidate["receipt_digest"]
            )

    def receipt_ref(self, candidate: CandidateRef) -> ReceiptRef:
        """Resolve immutable requester provenance without exposing pack lineage."""
        with self.journal.receipts.transaction() as db:
            self._row(db, candidate)
            row = self.journal._row(db, candidate)
            return ReceiptRef(row["receipt"], row["receipt_digest"])

    def bind_attempt(self, binding: PackAttemptBinding) -> PackWriteDisposition:
        start = self._clock_ns()
        execution = binding.execution
        payload = canonical(
            {
                "schema_version": "evaluation-pack-materialization/1",
                "pack": binding.assignment.pack.identity,
                "candidate": binding.assignment.candidate.identity,
                "submission_id": execution.handle.submission_id.value,
                "attempt_number": execution.handle.attempt_number,
                "artifact_digest": binding.artifact_digest,
                "configuration_digest": binding.configuration_digest,
                "evaluation_binding_digest": digest(
                    execution.handle.seed_pin.evaluation_binding._copy_bytes()
                ),
            }
        ).decode()
        ref = (
            f"{execution.handle.submission_id.value}:{execution.handle.attempt_number}"
        )
        with self.journal.receipts.transaction() as db:
            row = self._row(db, binding.assignment.candidate)
            if self._assignment(row) != binding.assignment:
                raise PackFailure(PackCode.CONFLICT)
            if PackState(row["state"]) is PackState.ATTEMPT_BOUND:
                if (row["execution_ref"], row["execution_digest"]) == (
                    ref,
                    digest(payload.encode()),
                ):
                    return PackWriteDisposition.ALREADY_PRESENT
                try:
                    prior = json.loads(row["materialization"])
                    current = json.loads(payload)
                except Exception:  # noqa: BLE001 - malformed state fails closed.
                    raise PackFailure(PackCode.STORE) from None
                immutable = (
                    "schema_version",
                    "pack",
                    "candidate",
                    "submission_id",
                    "artifact_digest",
                    "configuration_digest",
                    "evaluation_binding_digest",
                )
                if execution.handle.attempt_number != row["attempt_number"] + 1 or any(
                    prior[key] != current[key] for key in immutable
                ):
                    raise PackFailure(PackCode.CONFLICT)
            elif PackState(row["state"]) is PackState.ASSIGNED:
                if execution.handle.attempt_number != 1:
                    raise PackFailure(PackCode.CONFLICT)
            else:
                raise PackFailure(PackCode.STATE)
            if (
                db.execute(
                    "SELECT count(*) FROM candidate_pack_attempt_v1 WHERE candidate=?",
                    (binding.assignment.candidate.identity,),
                ).fetchone()[0]
                >= 32
            ):
                raise PackFailure(PackCode.CAPACITY)
            db.execute(
                "INSERT INTO candidate_pack_attempt_v1 VALUES (?,?,?,?,?)",
                (
                    binding.assignment.candidate.identity,
                    execution.handle.attempt_number,
                    ref,
                    payload,
                    digest(payload.encode()),
                ),
            )
            db.execute(
                "UPDATE candidate_pack_v1 SET state=?,attempt_number=?,execution_ref=?,materialization=?,execution_digest=? WHERE candidate=?",
                (
                    PackState.ATTEMPT_BOUND.value,
                    execution.handle.attempt_number,
                    ref,
                    payload,
                    digest(payload.encode()),
                    binding.assignment.candidate.identity,
                ),
            )
            self._event(
                db,
                binding.assignment.candidate,
                "ATTEMPT_BOUND",
                start,
                {"attempt": execution.handle.attempt_number},
            )
            return PackWriteDisposition.INSERTED

    def require_reconciliation(self, candidate: CandidateRef) -> None:
        start = self._clock_ns()
        with self.journal.receipts.transaction() as db:
            row = self._row(db, candidate)
            state = PackState(row["state"])
            if state is PackState.RECONCILIATION_REQUIRED:
                return
            if state not in (
                PackState.ASSIGNED,
                PackState.ATTEMPT_BOUND,
            ):
                raise PackFailure(PackCode.STATE)
            db.execute(
                "UPDATE candidate_pack_v1 SET state=? WHERE candidate=?",
                (PackState.RECONCILIATION_REQUIRED.value, candidate.identity),
            )
            self._event(
                db,
                candidate,
                "RECONCILIATION_REQUIRED",
                start,
                {"prior_state": state.value},
            )

    def record_result(
        self,
        assignment: PackAssignment,
        attempt: ExecutionAttemptRef,
        result_digest: str,
        card: EvaluationCard,
    ) -> PackWriteDisposition:
        start = self._clock_ns()
        if (
            type(card) is not EvaluationCard
            or type(result_digest) is not str
            or not is_sha256_digest(result_digest)
        ):
            raise PackFailure(PackCode.INVALID)
        encoded = canonical(_card_payload(card)).decode()
        summary_digest = digest(encoded.encode())
        with self.journal.receipts.transaction() as db:
            row = self._row(db, assignment.candidate)
            try:
                materialization = json.loads(row["materialization"])
                expected_result_digest = _bound_result_digest(
                    assignment.pack.identity,
                    attempt.attempt_number,
                    materialization["configuration_digest"],
                    card,
                )
            except Exception:  # noqa: BLE001 - malformed private state fails closed.
                raise PackFailure(PackCode.STORE) from None
            if (
                card.result_id != attempt.submission_id.value
                or card.fixture_origin is not True
                or card.eligible_for_emission is not False
                or result_digest != expected_result_digest
            ):
                raise PackFailure(PackCode.CONFLICT)
            state = PackState(row["state"])
            if state in (
                PackState.RESULT_RECORDED,
                PackState.CLOSED,
                PackState.SUMMARY_DELIVERED,
            ):
                if row["result_digest"] == result_digest and row["summary"] == encoded:
                    return PackWriteDisposition.ALREADY_PRESENT
                raise PackFailure(PackCode.CONFLICT)
            if (
                self._assignment(row) != assignment
                or state is not PackState.ATTEMPT_BOUND
                or row["attempt_number"] != attempt.attempt_number
                or row["execution_ref"]
                != f"{attempt.submission_id.value}:{attempt.attempt_number}"
            ):
                raise PackFailure(PackCode.CONFLICT)
            db.execute(
                "UPDATE candidate_pack_v1 SET state=?,result_digest=?,summary=?,summary_digest=? WHERE candidate=?",
                (
                    PackState.RESULT_RECORDED.value,
                    result_digest,
                    encoded,
                    summary_digest,
                    assignment.candidate.identity,
                ),
            )
            self._event(
                db,
                assignment.candidate,
                "RESULT_RECORDED",
                start,
                {"scientific_status": card.status},
            )
            return PackWriteDisposition.INSERTED

    def close(
        self,
        assignment: PackAssignment,
        executions: DurableExecutionQueue,
        requester: RequesterIdentity,
    ) -> PackWriteDisposition:
        """Close only after C-01 durably confirms the bound result."""
        start = self._clock_ns()
        if (
            type(executions) is not DurableExecutionQueue
            or type(requester) is not RequesterIdentity
        ):
            raise PackFailure(PackCode.INVALID)
        with self.journal.receipts.transaction() as db:
            row = self._row(db, assignment.candidate)
            state = PackState(row["state"])
            if state in (PackState.CLOSED, PackState.SUMMARY_DELIVERED):
                return PackWriteDisposition.ALREADY_PRESENT
            if (
                self._assignment(row) != assignment
                or state is not PackState.RESULT_RECORDED
                or row["attempt_number"] is None
                or row["execution_ref"] is None
            ):
                raise PackFailure(PackCode.STATE)
            try:
                submission_id, attempt_text = row["execution_ref"].rsplit(":", 1)
                ref = ExecutionAttemptRef(
                    SubmissionId(submission_id), int(attempt_text)
                )
            except Exception:  # noqa: BLE001 - corrupt association fails closed.
                raise PackFailure(PackCode.STORE) from None
            try:
                status = executions.status(ref, requester)
            except ExecutionFailure:
                raise PackFailure(PackCode.INDETERMINATE) from None
            if (
                type(status) is not ExecutionStatusView
                or status.state is not ExecutionState.RESULT_RECORDED
                or status.attempt_number != row["attempt_number"]
            ):
                raise PackFailure(PackCode.STATE)
            db.execute(
                "UPDATE candidate_pack_v1 SET state=?,closed_ns=? WHERE candidate=?",
                (
                    PackState.CLOSED.value,
                    self._clock_ns(),
                    assignment.candidate.identity,
                ),
            )
            db.execute(
                "UPDATE candidate_v1 SET state='PACK_CLOSED' WHERE identity=? AND state='PACK_ASSIGNED'",
                (assignment.candidate.identity,),
            )
            self._event(db, assignment.candidate, "PACK_CLOSED", start, {})
            return PackWriteDisposition.INSERTED

    def close_incomplete(
        self,
        assignment: PackAssignment,
        executions: DurableExecutionQueue,
        requester: RequesterIdentity,
    ) -> None:
        """Close a bound attempt only after C-01 records a terminal disposition."""
        start = self._clock_ns()
        if (
            type(executions) is not DurableExecutionQueue
            or type(requester) is not RequesterIdentity
        ):
            raise PackFailure(PackCode.INVALID)
        with self.journal.receipts.transaction() as db:
            row = self._row(db, assignment.candidate)
            if (
                self._assignment(row) != assignment
                or PackState(row["state"]) is not PackState.ATTEMPT_BOUND
                or row["execution_ref"] is None
            ):
                raise PackFailure(PackCode.STATE)
            try:
                submission_id, attempt_text = row["execution_ref"].rsplit(":", 1)
                ref = ExecutionAttemptRef(
                    SubmissionId(submission_id), int(attempt_text)
                )
                status = executions.status(ref, requester)
            except ExecutionFailure:
                raise PackFailure(PackCode.INDETERMINATE) from None
            except Exception:  # noqa: BLE001 - corrupt association fails closed.
                raise PackFailure(PackCode.STORE) from None
            if status.state not in {
                ExecutionState.FAILED_INFRA,
                ExecutionState.FAILED_STRATEGY,
                ExecutionState.CANCELLED,
            }:
                raise PackFailure(PackCode.STATE)
            target = (
                PackState.CANCELLED
                if status.state is ExecutionState.CANCELLED
                else PackState.INCOMPLETE_CLOSED
            )
            db.execute(
                "UPDATE candidate_pack_v1 SET state=?,closed_ns=? WHERE candidate=?",
                (
                    target.value,
                    self._clock_ns(),
                    assignment.candidate.identity,
                ),
            )
            db.execute(
                "UPDATE candidate_v1 SET state=? WHERE identity=?",
                (
                    (
                        "PACK_CANCELLED"
                        if target is PackState.CANCELLED
                        else "PACK_INCOMPLETE"
                    ),
                    assignment.candidate.identity,
                ),
            )
            self._event(db, assignment.candidate, target.value, start, {})

    def record_fixture_execution_timing(
        self, candidate: CandidateRef, elapsed_ns: int
    ) -> None:
        """Persist one aggregate A8 fixture boundary without sensitive details."""
        if type(elapsed_ns) is not int or elapsed_ns < 0:
            raise PackFailure(PackCode.INVALID)
        with self.journal.receipts.transaction() as db:
            self._row(db, candidate)
            if (
                db.execute(
                    "SELECT count(*) FROM candidate_pack_event_v1 WHERE candidate=?",
                    (candidate.identity,),
                ).fetchone()[0]
                >= 64
            ):
                raise PackFailure(PackCode.CAPACITY)
            encoded = canonical({"boundary": "A8_FIXTURE_RUN"}).decode()
            db.execute(
                "INSERT INTO candidate_pack_event_v1(candidate,kind,elapsed_ns,body,body_digest) VALUES (?,?,?,?,?)",
                (
                    candidate.identity,
                    "FIXTURE_EXECUTION",
                    elapsed_ns,
                    encoded,
                    digest(encoded.encode()),
                ),
            )

    def deliver_summary(self, candidate: CandidateRef) -> EvaluationCard:
        start = self._clock_ns()
        with self.journal.receipts.transaction() as db:
            row = self._row(db, candidate)
            state = PackState(row["state"])
            if state is PackState.SUMMARY_DELIVERED:
                return _load_card(row["summary"])
            if state is not PackState.CLOSED or row["summary"] is None:
                raise PackFailure(PackCode.STATE)
            card = _load_card(row["summary"])
            db.execute(
                "UPDATE candidate_pack_v1 SET state=?,delivered=1 WHERE candidate=?",
                (PackState.SUMMARY_DELIVERED.value, candidate.identity),
            )
            self._event(db, candidate, "SUMMARY_DELIVERED", start, {})
            return card

    def read_summary(self, candidate: CandidateRef) -> EvaluationCard:
        with self.journal.receipts.transaction() as db:
            row = self._row(db, candidate)
            if (
                PackState(row["state"]) is not PackState.SUMMARY_DELIVERED
                or row["delivered"] != 1
            ):
                raise PackFailure(PackCode.STATE)
            return _load_card(row["summary"])

    def status(self, candidate: CandidateRef) -> DevelopmentPackStatus:
        with self.journal.receipts.transaction() as db:
            row = self._row(db, candidate)
            state = PackState(row["state"])
            return DevelopmentPackStatus(
                "development-evaluation-pack-status/1",
                candidate,
                state,
                row["attempt_number"],
                state is PackState.SUMMARY_DELIVERED,
            )

    def internal_assignment(self, candidate: CandidateRef) -> PackAssignment:
        """Private inspection for orchestration/tests; never a requester projection."""
        with self.journal.receipts.transaction() as db:
            return self._assignment(self._row(db, candidate))

    def trace_counts(self) -> dict[str, int]:
        with self.journal.receipts.transaction() as db:
            return {
                kind: count
                for kind, count in db.execute(
                    "SELECT kind,count(*) FROM candidate_pack_event_v1 GROUP BY kind ORDER BY kind"
                )
            }


__all__ = ("DevelopmentEvaluationPackLedger",)

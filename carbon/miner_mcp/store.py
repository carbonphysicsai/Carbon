"""Versioned C-08 association tables in the existing NET-2 journal."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

from carbon.execution import ExecutionScope
from carbon.execution.model import validate_execution_token
from carbon.fees import AdmissionKind, RequesterIdentity, SubmissionState
from carbon.mcp import SubmitReceipt
from carbon.orchestration import (
    DevelopmentOperationalAccount,
    DevelopmentOrchestrationRequest,
    public_projection,
)
from carbon.registry import ChallengeKey
from carbon.transport.gateway import ReceivedCall, requester_for_receipt
from carbon.transport.models import ReceiptRef, TransportFailure, canonical, digest
from carbon.transport.store import ReceiptJournal

from .model import BindMode, MinerMcpCode, MinerMcpFailure


@dataclass(frozen=True, slots=True)
class BindIntent:
    receipt_ref: ReceiptRef
    requester: str
    submission_id: str
    attempt_number: int
    request_digest: str
    worker_id: str
    claim_id: str
    mode: BindMode
    event_digest: str


class MinerMcpJournal:
    """C-08 associations; source journals remain authoritative and immutable."""

    def __init__(self, journal: ReceiptJournal) -> None:
        if type(journal) is not ReceiptJournal:
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        self.journal = journal
        with self._transaction() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS c08_submit_v1 (
                    receipt_sequence INTEGER PRIMARY KEY,
                    receipt_digest TEXT NOT NULL,
                    body_digest TEXT NOT NULL,
                    requester TEXT NOT NULL,
                    challenge_id TEXT NOT NULL,
                    challenge_version TEXT NOT NULL,
                    source_submission_id TEXT,
                    source_state TEXT,
                    state TEXT NOT NULL CHECK(state IN ('PREPARED','ASSOCIATED'))
                );
                CREATE INDEX IF NOT EXISTS c08_submit_source_v1
                    ON c08_submit_v1(requester,source_submission_id,receipt_sequence);
                CREATE TABLE IF NOT EXISTS c08_attempt_v1 (
                    requester TEXT NOT NULL,
                    source_submission_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    receipt_sequence INTEGER NOT NULL,
                    request_digest TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('BINDING','BOUND','ACCOUNTED')),
                    account_digest TEXT,
                    account_json TEXT,
                    public_json TEXT,
                    PRIMARY KEY(requester,source_submission_id,attempt_number)
                );
                CREATE TABLE IF NOT EXISTS c08_bind_event_v1 (
                    event_digest TEXT PRIMARY KEY,
                    requester TEXT NOT NULL,
                    source_submission_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    request_digest TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('PREPARED','COMPLETE'))
                );
            """)

    @contextmanager
    def _transaction(self):
        try:
            with self.journal.transaction() as connection:
                yield connection
        except MinerMcpFailure:
            raise
        except (TransportFailure, sqlite3.Error):
            raise MinerMcpFailure(MinerMcpCode.STORE) from None

    @staticmethod
    def _validate_received(received: object, expected_tool: str) -> ReceivedCall:
        if type(received) is not ReceivedCall or received.call.tool != expected_tool:
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        return received

    def prepare_submit(self, received: ReceivedCall) -> None:
        received = self._validate_received(received, "submit")
        try:
            retained = self.journal.resolve(received.receipt.ref)
            expected_requester = requester_for_receipt(
                self.journal.context, received.receipt
            )
        except Exception:  # noqa: BLE001 - normalize cross-owner failures.
            raise MinerMcpFailure(MinerMcpCode.CONFLICT) from None
        if retained != received.receipt or expected_requester != received.requester:
            raise MinerMcpFailure(MinerMcpCode.CONFLICT)
        values = (
            received.receipt.ref.sequence,
            received.receipt.ref.digest,
            received.receipt.body_digest,
            received.requester.value,
            received.receipt.challenge_id,
            received.receipt.challenge_version,
        )
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT receipt_digest,body_digest,requester,challenge_id,"
                "challenge_version,state FROM c08_submit_v1 WHERE receipt_sequence=?",
                (received.receipt.ref.sequence,),
            ).fetchone()
            if row is not None:
                if row[:5] != values[1:] or row[5] not in {
                    "PREPARED",
                    "ASSOCIATED",
                }:
                    raise MinerMcpFailure(MinerMcpCode.CONFLICT)
                raise MinerMcpFailure(MinerMcpCode.RECONCILIATION_REQUIRED)
            connection.execute(
                "INSERT INTO c08_submit_v1 "
                "(receipt_sequence,receipt_digest,body_digest,requester,challenge_id,"
                "challenge_version,state) VALUES (?,?,?,?,?,?,'PREPARED')",
                values,
            )

    def associate_submit(self, ref: ReceiptRef, result: SubmitReceipt) -> None:
        if type(ref) is not ReceiptRef or type(result) is not SubmitReceipt:
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        try:
            retained_receipt = self.journal.resolve(ref)
        except Exception:  # noqa: BLE001 - normalize the source boundary.
            raise MinerMcpFailure(MinerMcpCode.CONFLICT) from None
        if retained_receipt.ref != ref:
            raise MinerMcpFailure(MinerMcpCode.CONFLICT)
        submission_id = result.status.submission_id.value
        source_state = result.status.state.value
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT receipt_digest,source_submission_id,source_state,state "
                "FROM c08_submit_v1 WHERE receipt_sequence=?",
                (ref.sequence,),
            ).fetchone()
            if row is None or row[0] != ref.digest:
                raise MinerMcpFailure(MinerMcpCode.CONFLICT)
            if row[3] == "ASSOCIATED":
                if row[1:3] != (submission_id, source_state):
                    raise MinerMcpFailure(MinerMcpCode.CONFLICT)
                return
            if row[3] != "PREPARED" or row[1] is not None or row[2] is not None:
                raise MinerMcpFailure(MinerMcpCode.STATE)
            connection.execute(
                "UPDATE c08_submit_v1 SET source_submission_id=?,source_state=?,"
                "state='ASSOCIATED' WHERE receipt_sequence=?",
                (submission_id, source_state, ref.sequence),
            )

    def reconcile_submit(self, ref: ReceiptRef, result: SubmitReceipt) -> None:
        """Trusted exact-output reconciliation; it never dispatches A9."""

        self.associate_submit(ref, result)

    @staticmethod
    def _bind_event_digest(
        requester: str,
        submission_id: str,
        attempt_number: int,
        request_digest: str,
        worker_id: str,
        claim_id: str,
        mode: BindMode,
    ) -> str:
        return digest(
            canonical(
                [
                    "carbon.c08.bind-event.v1",
                    requester,
                    submission_id,
                    attempt_number,
                    request_digest,
                    worker_id,
                    claim_id,
                    mode.value,
                ]
            )
        )

    def prepare_bind(
        self,
        ref: ReceiptRef,
        request: DevelopmentOrchestrationRequest,
        *,
        worker_id: str,
        claim_id: str,
        mode: BindMode,
    ) -> BindIntent:
        if (
            type(ref) is not ReceiptRef
            or type(request) is not DevelopmentOrchestrationRequest
            or type(mode) is not BindMode
        ):
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        try:
            worker_id = validate_execution_token(worker_id)
            claim_id = validate_execution_token(claim_id)
        except Exception:  # noqa: BLE001
            raise MinerMcpFailure(MinerMcpCode.INVALID) from None
        execution = request.execution
        if (
            execution.scope is not ExecutionScope.REAL_PATH_NON_LIVE
            or execution.handle.admission_kind is not AdmissionKind.PRODUCTION
        ):
            raise MinerMcpFailure(MinerMcpCode.DENIED)
        requester = execution.requester_identity.value
        submission_id = execution.handle.submission_id.value
        attempt_number = execution.handle.attempt_number
        event_digest = self._bind_event_digest(
            requester,
            submission_id,
            attempt_number,
            request.request_digest,
            worker_id,
            claim_id,
            mode,
        )
        with self._transaction() as connection:
            source = connection.execute(
                "SELECT receipt_digest,requester,challenge_id,challenge_version,"
                "source_submission_id,source_state,state FROM c08_submit_v1 "
                "WHERE receipt_sequence=?",
                (ref.sequence,),
            ).fetchone()
            pin = execution.handle.seed_pin.challenge_key
            if (
                source is None
                or source[0] != ref.digest
                or source[1] != requester
                or source[2:4] != (pin.challenge_id, pin.version)
                or source[4] != submission_id
                or source[5] != SubmissionState.RECEIVED.value
                or source[6] != "ASSOCIATED"
            ):
                raise MinerMcpFailure(MinerMcpCode.DENIED)
            attempt = connection.execute(
                "SELECT receipt_sequence,request_digest,worker_id,claim_id,state "
                "FROM c08_attempt_v1 WHERE requester=? AND source_submission_id=? "
                "AND attempt_number=?",
                (requester, submission_id, attempt_number),
            ).fetchone()
            expected_attempt = (
                ref.sequence,
                request.request_digest,
                worker_id,
                claim_id,
            )
            if attempt is None:
                connection.execute(
                    "INSERT INTO c08_attempt_v1 "
                    "(requester,source_submission_id,attempt_number,receipt_sequence,"
                    "request_digest,worker_id,claim_id,state) "
                    "VALUES (?,?,?,?,?,?,?,'BINDING')",
                    (
                        requester,
                        submission_id,
                        attempt_number,
                        *expected_attempt,
                    ),
                )
            elif attempt[:4] != expected_attempt:
                raise MinerMcpFailure(MinerMcpCode.CONFLICT)
            event = connection.execute(
                "SELECT requester,source_submission_id,attempt_number,request_digest,"
                "worker_id,claim_id,mode FROM c08_bind_event_v1 WHERE event_digest=?",
                (event_digest,),
            ).fetchone()
            expected_event = (
                requester,
                submission_id,
                attempt_number,
                request.request_digest,
                worker_id,
                claim_id,
                mode.value,
            )
            if event is None:
                connection.execute(
                    "INSERT INTO c08_bind_event_v1 VALUES (?,?,?,?,?,?,?,?, 'PREPARED')",
                    (event_digest, *expected_event),
                )
            elif event != expected_event:
                raise MinerMcpFailure(MinerMcpCode.CONFLICT)
        return BindIntent(
            ref,
            requester,
            submission_id,
            attempt_number,
            request.request_digest,
            worker_id,
            claim_id,
            mode,
            event_digest,
        )

    def complete_bind(self, intent: BindIntent) -> None:
        if type(intent) is not BindIntent:
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        with self._transaction() as connection:
            event = connection.execute(
                "SELECT requester,source_submission_id,attempt_number,request_digest,"
                "worker_id,claim_id,mode,state FROM c08_bind_event_v1 "
                "WHERE event_digest=?",
                (intent.event_digest,),
            ).fetchone()
            expected = (
                intent.requester,
                intent.submission_id,
                intent.attempt_number,
                intent.request_digest,
                intent.worker_id,
                intent.claim_id,
                intent.mode.value,
            )
            if event is None or event[:7] != expected:
                raise MinerMcpFailure(MinerMcpCode.CONFLICT)
            if event[7] == "PREPARED":
                connection.execute(
                    "UPDATE c08_bind_event_v1 SET state='COMPLETE' "
                    "WHERE event_digest=?",
                    (intent.event_digest,),
                )
            elif event[7] != "COMPLETE":
                raise MinerMcpFailure(MinerMcpCode.STATE)
            connection.execute(
                "UPDATE c08_attempt_v1 SET state=CASE WHEN state='ACCOUNTED' "
                "THEN state ELSE 'BOUND' END WHERE requester=? "
                "AND source_submission_id=? AND attempt_number=?",
                (intent.requester, intent.submission_id, intent.attempt_number),
            )

    def record_account(self, account: DevelopmentOperationalAccount) -> None:
        if type(account) is not DevelopmentOperationalAccount:
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        account_json = account.canonical_bytes.decode("ascii")
        projected = canonical(public_projection(account)).decode("ascii")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT request_digest,state,account_digest,account_json,public_json "
                "FROM c08_attempt_v1 WHERE source_submission_id=? "
                "AND attempt_number=?",
                (account.submission_id, account.attempt_number),
            ).fetchall()
            if len(row) != 1:
                raise MinerMcpFailure(MinerMcpCode.CONFLICT)
            retained = row[0]
            if retained[0] != account.request_digest or retained[1] not in {
                "BOUND",
                "ACCOUNTED",
            }:
                raise MinerMcpFailure(MinerMcpCode.STATE)
            expected = (account.account_digest, account_json, projected)
            if retained[1] == "ACCOUNTED":
                if retained[2:] != expected:
                    raise MinerMcpFailure(MinerMcpCode.CONFLICT)
                return
            connection.execute(
                "UPDATE c08_attempt_v1 SET state='ACCOUNTED',account_digest=?,"
                "account_json=?,public_json=? WHERE source_submission_id=? "
                "AND attempt_number=?",
                (*expected, account.submission_id, account.attempt_number),
            )

    def public_projection(
        self,
        requester: RequesterIdentity,
        submission_id: str,
        challenge: ChallengeKey,
    ) -> dict[str, object] | None:
        if (
            type(requester) is not RequesterIdentity
            or type(submission_id) is not str
            or type(challenge) is not ChallengeKey
        ):
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT a.state,a.public_json FROM c08_attempt_v1 AS a "
                "JOIN c08_submit_v1 AS s ON s.receipt_sequence=a.receipt_sequence "
                "WHERE a.requester=? AND a.source_submission_id=? "
                "AND s.challenge_id=? AND s.challenge_version=? "
                "ORDER BY a.attempt_number DESC LIMIT 1",
                (
                    requester.value,
                    submission_id,
                    challenge.challenge_id,
                    challenge.version,
                ),
            ).fetchall()
        if not rows or rows[0][0] != "ACCOUNTED":
            return None
        try:
            value = json.loads(rows[0][1])
            if canonical(value).decode("ascii") != rows[0][1]:
                raise ValueError
        except Exception:  # noqa: BLE001
            raise MinerMcpFailure(MinerMcpCode.STORE) from None
        return value


__all__ = ["BindIntent", "MinerMcpJournal"]

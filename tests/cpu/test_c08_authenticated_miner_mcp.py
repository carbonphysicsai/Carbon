"""C-08 authenticated DEVELOPMENT composition tests."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest
from test_c07_development_orchestration import (
    _orchestrator,
    _owners,
    _signer,
    _values,
)
from test_mcp_skeleton import CHALLENGE_KEY, _service, _strategy

from carbon import audit
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.auth import AuthCode, AuthenticatedHotkey, AuthFailure
from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionCode,
    ExecutionFailure,
    ExecutionScope,
    ExecutionStage,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    RequesterIdentity,
    SubmissionId,
    SubmissionState,
)
from carbon.mcp import (
    DryValidateResponse,
    McpCall,
    McpField,
    McpQueryBudgetError,
    McpService,
    SubmissionResult,
    SubmitReceipt,
)
from carbon.miner_mcp import (
    AuthenticatedMcpResult,
    AuthenticatedMinerMcpService,
    BindMode,
    MinerMcpCode,
    MinerMcpFailure,
    MinerMcpJournal,
)
from carbon.orchestration import (
    DevelopmentEvaluationOrchestrator,
    DevelopmentOrchestrationRequest,
    OperationalDisposition,
    OrchestrationCode,
    OrchestrationFailure,
)
from carbon.registry import ChallengeKey
from carbon.seeding import SeedPin
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import MAX_BODY, TransportFailure, digest, message
from carbon.transport.store import ReceiptJournal

NOW = 100_000_000_000
CONTEXT = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", "0x" + "1" * 64, 1)


class _Adapter:
    def __init__(self, state: MetagraphSnapshot) -> None:
        self.state = state

    async def observe(self, *, minimum_finalized_block: int) -> MetagraphSnapshot:
        del minimum_finalized_block
        return self.state


class _Verifier:
    def verify(
        self,
        headers: dict[str, str],
        body: bytes,
        *,
        method: str,
        path: str,
        receiver: str,
        now_ns: int,
        nonce_store: object,
    ) -> AuthenticatedHotkey:
        del method, path, receiver, now_ns
        if headers["body"] != digest(body):
            raise AuthFailure(AuthCode.SIGNATURE)
        nonce = int(headers["nonce"])
        if not nonce_store.check_and_store(headers["hotkey"], nonce):
            raise AuthFailure(AuthCode.REPLAY)
        return AuthenticatedHotkey(headers["hotkey"], nonce)


def _snapshot(sender: str = "miner", receiver: str = "validator") -> MetagraphSnapshot:
    return MetagraphSnapshot(
        CONTEXT,
        10,
        "0x" + "2" * 64,
        NOW // 1_000_000,
        (
            Participant(0, receiver, "owner", 1),
            Participant(1, sender, "cold", 2),
        ),
    )


def _wire(
    state: MetagraphSnapshot,
    *,
    request: str,
    tool: str,
    fields: dict[str, object],
) -> bytes:
    return message(
        CONTEXT,
        state.snapshot_id,
        CHALLENGE_KEY,
        session="c08-session",
        request=request,
        tool=tool,
        fields=fields,
    )


def _headers(body: bytes, nonce: int, hotkey: str = "miner") -> dict[str, str]:
    return {"body": digest(body), "nonce": str(nonce), "hotkey": hotkey}


def _composition(tmp_path):
    state = _snapshot()
    receipt_journal = ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT)
    gateway = AuthenticatedGateway(
        CONTEXT,
        CHALLENGE_KEY,
        "validator",
        _Adapter(state),
        _Verifier(),
        receipt_journal,
        clock_ns=lambda: NOW,
    )
    mcp, *_ = _service(tmp_path / "mcp")
    signer = _signer()
    queue, _, orchestrator = _orchestrator(tmp_path / "c07", signer)
    associations = MinerMcpJournal(receipt_journal)
    service = AuthenticatedMinerMcpService(gateway, mcp, orchestrator, associations)
    return state, mcp, queue, orchestrator, associations, service


def _submit(service, state, *, request: str = "submit-1", nonce: int = NOW):
    body = _wire(
        state,
        request=request,
        tool="submit",
        fields={
            "challenge_id": CHALLENGE_KEY.challenge_id,
            "challenge_version": CHALLENGE_KEY.version,
            "strategy": _strategy(),
        },
    )
    result = asyncio.run(service.call(body, _headers(body, nonce)))
    assert type(result.mcp_result) is SubmitReceipt
    return result


def _real_request(tmp_path, requester: RequesterIdentity, submission_id: str):
    base, *_ = _values(tmp_path)
    evidence = dataclasses.replace(
        base.evidence,
        submission_id=submission_id,
        challenge_id=CHALLENGE_KEY.challenge_id,
        challenge_version=CHALLENGE_KEY.version,
    )
    pin = base.execution.handle.seed_pin
    execution = DurableExecutionBinding(
        ExecutionAttemptHandle(
            SubmissionId(submission_id),
            1,
            AdmissionKind.PRODUCTION,
            SeedPin(
                CHALLENGE_KEY,
                pin.generator_version,
                pin.generator_digest,
                pin.scoring_version,
                pin.scoring_digest,
                pin.evaluation_binding,
            ),
            base.execution.handle.environment_pin,
        ),
        requester,
        base.execution.strategy_hash,
        ExecutionScope.REAL_PATH_NON_LIVE,
        base.execution.resolved_plan_digest,
        base.execution.reconstruction_policy_digest,
        base.execution.resource_policy_digest,
        base.execution.protected_evaluation_policy_digest,
    )
    return DevelopmentOrchestrationRequest(
        execution,
        evidence,
        base.case_manifest_digest,
        base.reference_request_digests,
        base.measurement_request_digests,
    )


def _requester(service, receipt_ref) -> RequesterIdentity:
    receipt = service.gateway.journal.resolve(receipt_ref)
    from carbon.transport.gateway import requester_for_receipt

    return requester_for_receipt(CONTEXT, receipt)


def test_authenticated_submit_cancel_and_poll_preserves_source_owners(tmp_path) -> None:
    state, _, _, orchestrator, _, service = _composition(tmp_path)
    submitted = _submit(service, state)
    receipt = submitted.transport_receipt
    source = submitted.mcp_result
    assert source.status.state is SubmissionState.RECEIVED
    request = _real_request(
        tmp_path / "request",
        _requester(service, receipt),
        source.status.submission_id.value,
    )
    handle = service.bind_orchestration(
        receipt,
        request,
        worker_id="c08-worker",
        claim_id="c08-claim-1",
        mode=BindMode.START,
    )
    account = orchestrator.conclude_without_receipt(
        handle,
        disposition=OperationalDisposition.CANCELLED,
        failed_stage=ExecutionStage.GENERATOR,
        failure_evidence_ref="cancelled-development-evidence",
        failure_evidence_digest=audit.digest_bytes(b"cancelled"),
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=2_500,
    )
    service.record_outcome(account)
    service.record_outcome(account)
    with pytest.raises(MinerMcpFailure) as changed_account:
        service.record_outcome(dataclasses.replace(account, finished_at_micros=2_501))
    assert changed_account.value.code is MinerMcpCode.CONFLICT

    poll = _wire(
        state,
        request="poll-1",
        tool="get_submission_result",
        fields={"submission_id": source.status.submission_id.value},
    )
    result = asyncio.run(service.call(poll, _headers(poll, NOW + 1)))
    assert type(result.mcp_result) is SubmissionResult
    assert result.mcp_result.status.state is SubmissionState.RECEIVED
    assert result.orchestration is not None
    assert result.orchestration["disposition"] == "CANCELLED"
    assert set(result.orchestration["eligibility"].values()) == {False}
    caller_copy = result.orchestration
    assert caller_copy is not None
    caller_copy["eligibility"]["official"] = True
    assert result.orchestration["eligibility"]["official"] is False
    with pytest.raises(MinerMcpFailure) as authority_upgrade:
        AuthenticatedMcpResult(
            result.transport_receipt,
            result.mcp_result,
            caller_copy,
        )
    assert authority_upgrade.value.code is MinerMcpCode.DENIED
    assert (
        service.journal.public_projection(
            _requester(service, receipt),
            source.status.submission_id.value,
            ChallengeKey("other-challenge", "1.0"),
        )
        is None
    )
    assert len(result.extension_bytes) <= MAX_BODY

    service.mcp._query_budget_gate.failure = McpQueryBudgetError()
    second_poll = _wire(
        state,
        request="poll-2",
        tool="get_submission_result",
        fields={"submission_id": source.status.submission_id.value},
    )
    with pytest.raises(McpQueryBudgetError):
        asyncio.run(service.call(second_poll, _headers(second_poll, NOW + 2)))


def test_authenticated_non_submit_tool_preserves_exact_a9_result(tmp_path) -> None:
    state, mcp, _, _, _, service = _composition(tmp_path)
    body = _wire(
        state,
        request="dry-validate-1",
        tool="dry_validate",
        fields={"strategy": _strategy()},
    )
    result = asyncio.run(service.call(body, _headers(body, NOW)))
    assert type(result.mcp_result) is DryValidateResponse
    assert result.orchestration is None
    assert result.mcp_result == mcp.call(
        McpCall("1.0", "dry_validate", (McpField("strategy", _strategy()),)),
        _requester(service, result.transport_receipt),
    )


def test_fixture_cross_binding_and_changed_attempt_fail_closed(tmp_path) -> None:
    state, _, _, _, associations, service = _composition(tmp_path)
    submitted = _submit(service, state)
    receipt = submitted.transport_receipt
    requester = _requester(service, receipt)
    fixture_request, *_ = _values(tmp_path / "fixture")
    with pytest.raises(MinerMcpFailure) as denied:
        associations.prepare_bind(
            receipt,
            fixture_request,
            worker_id="c08-worker",
            claim_id="c08-claim-1",
            mode=BindMode.START,
        )
    assert denied.value.code is MinerMcpCode.DENIED

    request = _real_request(
        tmp_path / "real", requester, submitted.mcp_result.status.submission_id.value
    )
    service.bind_orchestration(
        receipt,
        request,
        worker_id="c08-worker",
        claim_id="c08-claim-1",
        mode=BindMode.START,
    )
    changed = dataclasses.replace(
        request, case_manifest_digest=audit.digest_bytes(b"changed-case-manifest")
    )
    with pytest.raises(MinerMcpFailure) as conflict:
        associations.prepare_bind(
            receipt,
            changed,
            worker_id="c08-worker",
            claim_id="c08-claim-1",
            mode=BindMode.RESUME_EXISTING,
        )
    assert conflict.value.code is MinerMcpCode.CONFLICT


def test_ambiguous_submit_replay_never_redispatches_and_exactly_reconciles(
    tmp_path, monkeypatch
) -> None:
    state, mcp, _, _, associations, service = _composition(tmp_path)
    body = _wire(
        state,
        request="ambiguous-submit",
        tool="submit",
        fields={
            "challenge_id": CHALLENGE_KEY.challenge_id,
            "challenge_version": CHALLENGE_KEY.version,
            "strategy": _strategy(),
        },
    )
    received = asyncio.run(service.gateway.receive(body, _headers(body, NOW)))
    associations.prepare_submit(received)
    original = McpService.call
    calls = 0

    def counted(self, call, requester):
        nonlocal calls
        calls += 1
        return original(self, call, requester)

    monkeypatch.setattr(McpService, "call", counted)
    exact = mcp.call(received.call, received.requester)
    assert type(exact) is SubmitReceipt and calls == 1
    with pytest.raises(TransportFailure):
        asyncio.run(service.call(body, _headers(body, NOW + 1)))
    assert calls == 1
    with pytest.raises(MinerMcpFailure) as unresolved:
        associations.prepare_submit(received)
    assert unresolved.value.code is MinerMcpCode.RECONCILIATION_REQUIRED
    service.reconcile_submit(received.receipt.ref, exact)
    service.reconcile_submit(received.receipt.ref, exact)
    changed = SubmitReceipt(
        "1.0",
        dataclasses.replace(
            exact.status,
            submission_id=SubmissionId("123e4567-e89b-42d3-a456-426614174001"),
        ),
    )
    with pytest.raises(MinerMcpFailure) as conflict:
        service.reconcile_submit(received.receipt.ref, changed)
    assert conflict.value.code is MinerMcpCode.CONFLICT


def test_lost_bind_response_requires_explicit_same_attempt_resume(tmp_path) -> None:
    state, _, queue, orchestrator, associations, service = _composition(tmp_path)
    submitted = _submit(service, state)
    receipt = submitted.transport_receipt
    request = _real_request(
        tmp_path / "request",
        _requester(service, receipt),
        submitted.mcp_result.status.submission_id.value,
    )
    intent = associations.prepare_bind(
        receipt,
        request,
        worker_id="c08-worker",
        claim_id="c08-claim-1",
        mode=BindMode.START,
    )
    orchestrator.begin(request, worker_id="c08-worker", claim_id="c08-claim-1")

    restarted_queue = DurableExecutionQueue(queue.path)
    restarted_orchestrator = DevelopmentEvaluationOrchestrator(
        restarted_queue, orchestrator.evidence_ledger
    )
    restarted_associations = MinerMcpJournal(service.gateway.journal)
    restarted = AuthenticatedMinerMcpService(
        service.gateway, service.mcp, restarted_orchestrator, restarted_associations
    )
    with pytest.raises(OrchestrationFailure) as no_second_start:
        restarted.bind_orchestration(
            receipt,
            request,
            worker_id="c08-worker",
            claim_id="c08-claim-1",
            mode=BindMode.START,
        )
    assert no_second_start.value.code is OrchestrationCode.RECONCILIATION_REQUIRED
    resumed = restarted.bind_orchestration(
        receipt,
        request,
        worker_id="c08-worker",
        claim_id="c08-claim-1",
        mode=BindMode.RESUME_EXISTING,
    )
    restarted_associations.complete_bind(intent)
    assert resumed.request == request
    assert (
        restarted_queue.status(
            request.execution.ref, request.execution.requester_identity
        ).attempt_number
        == 1
    )


def test_retry_attempt_requires_c01_predecessor_continuity(tmp_path) -> None:
    state, _, queue, _, _, service = _composition(tmp_path)
    submitted = _submit(service, state)
    receipt = submitted.transport_receipt
    first = _real_request(
        tmp_path / "request",
        _requester(service, receipt),
        submitted.mcp_result.status.submission_id.value,
    )
    first_handle = service.bind_orchestration(
        receipt,
        first,
        worker_id="c08-worker-1",
        claim_id="c08-claim-1",
        mode=BindMode.START,
    )
    second = dataclasses.replace(
        first,
        execution=dataclasses.replace(
            first.execution,
            handle=dataclasses.replace(first.execution.handle, attempt_number=2),
        ),
    )
    with pytest.raises(ExecutionFailure) as premature:
        service.bind_orchestration(
            receipt,
            second,
            worker_id="c08-worker-2",
            claim_id="c08-claim-2",
            mode=BindMode.START,
        )
    assert premature.value.code is ExecutionCode.CONFLICT
    queue.retryable_infrastructure(first_handle.claimed.claim)
    second_handle = service.bind_orchestration(
        receipt,
        second,
        worker_id="c08-worker-2",
        claim_id="c08-claim-2",
        mode=BindMode.START,
    )
    assert second_handle.request.execution.handle.attempt_number == 2

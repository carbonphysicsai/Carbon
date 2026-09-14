"""Installed-SDK C-08 composition in the required Linux service lane."""

from __future__ import annotations

import asyncio

from bittensor.keyfiles import Keypair
from test_c07_development_orchestration import _orchestrator, _owners, _signer
from test_c08_authenticated_miner_mcp import _real_request
from test_mcp_skeleton import CHALLENGE_KEY, _service, _strategy

from carbon import audit
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.auth import BittensorHotkeyVerifier, BittensorMessageSigner
from carbon.execution import ExecutionStage
from carbon.mcp import SubmissionResult, SubmitReceipt
from carbon.miner_mcp import (
    AuthenticatedMinerMcpService,
    BindMode,
    MinerMcpJournal,
)
from carbon.orchestration import OperationalDisposition
from carbon.transport.gateway import AuthenticatedGateway, requester_for_receipt
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal

NOW = 100_000_000_000
CONTEXT = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", "0x" + "1" * 64, 1)


class _Adapter:
    def __init__(self, state: MetagraphSnapshot) -> None:
        self.state = state

    async def observe(self, *, minimum_finalized_block: int) -> MetagraphSnapshot:
        del minimum_finalized_block
        return self.state


def _body(state, *, request: str, tool: str, fields: dict[str, object]) -> bytes:
    return message(
        CONTEXT,
        state.snapshot_id,
        CHALLENGE_KEY,
        session="c08-linux-service",
        request=request,
        tool=tool,
        fields=fields,
    )


def test_installed_auth_submit_reaches_exact_c07_non_live_path(tmp_path) -> None:
    sender = Keypair.create_from_uri("//Alice")
    receiver = Keypair.create_from_uri("//Bob")
    state = MetagraphSnapshot(
        CONTEXT,
        10,
        "0x" + "2" * 64,
        NOW // 1_000_000,
        (
            Participant(0, receiver.ss58_address, "owner", 1),
            Participant(1, sender.ss58_address, "cold", 2),
        ),
    )
    transport = ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT)
    gateway = AuthenticatedGateway(
        CONTEXT,
        CHALLENGE_KEY,
        receiver.ss58_address,
        _Adapter(state),
        BittensorHotkeyVerifier(),
        transport,
        clock_ns=lambda: NOW,
    )
    mcp, *_ = _service(tmp_path / "mcp")
    _, _, orchestrator = _orchestrator(tmp_path / "c07", _signer())
    service = AuthenticatedMinerMcpService(
        gateway, mcp, orchestrator, MinerMcpJournal(transport)
    )
    submit_body = _body(
        state,
        request="submit-1",
        tool="submit",
        fields={
            "challenge_id": CHALLENGE_KEY.challenge_id,
            "challenge_version": CHALLENGE_KEY.version,
            "strategy": _strategy(),
        },
    )
    submit_headers = BittensorMessageSigner(sender).sign(
        submit_body, receiver=receiver.ss58_address, nonce_ns=NOW
    )
    submitted = asyncio.run(service.call(submit_body, submit_headers))
    assert type(submitted.mcp_result) is SubmitReceipt
    receipt = transport.resolve(submitted.transport_receipt)
    request = _real_request(
        tmp_path / "request",
        requester_for_receipt(CONTEXT, receipt),
        submitted.mcp_result.status.submission_id.value,
    )
    handle = service.bind_orchestration(
        receipt.ref,
        request,
        worker_id="c08-linux-worker",
        claim_id="c08-linux-claim",
        mode=BindMode.START,
    )
    account = orchestrator.conclude_without_receipt(
        handle,
        disposition=OperationalDisposition.CANCELLED,
        failed_stage=ExecutionStage.GENERATOR,
        failure_evidence_ref="c08-linux-cancelled",
        failure_evidence_digest=audit.digest_bytes(b"c08-linux-cancelled"),
        result_owners=_owners(),
        started_at_micros=2_000,
        finished_at_micros=2_500,
    )
    service.record_outcome(account)
    poll_body = _body(
        state,
        request="poll-1",
        tool="get_submission_result",
        fields={"submission_id": account.submission_id},
    )
    poll_headers = BittensorMessageSigner(sender).sign(
        poll_body, receiver=receiver.ss58_address, nonce_ns=NOW + 1
    )
    polled = asyncio.run(service.call(poll_body, poll_headers))
    assert type(polled.mcp_result) is SubmissionResult
    assert polled.orchestration is not None
    assert polled.orchestration["disposition"] == "CANCELLED"
    assert set(polled.orchestration["eligibility"].values()) == {False}

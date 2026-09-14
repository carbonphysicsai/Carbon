"""Thin authenticated C-08 composition; source services keep all authority."""

from __future__ import annotations

from carbon.mcp import McpService, SubmissionResult, SubmitReceipt
from carbon.orchestration import (
    DevelopmentEvaluationOrchestrator,
    DevelopmentOperationalAccount,
    DevelopmentOrchestrationRequest,
    OrchestrationHandle,
)
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import ReceiptRef

from .model import AuthenticatedMcpResult, BindMode, MinerMcpCode, MinerMcpFailure
from .store import MinerMcpJournal


class AuthenticatedMinerMcpService:
    """Compose exact NET-2/A9 calls with trusted C-07 association methods."""

    def __init__(
        self,
        gateway: AuthenticatedGateway,
        mcp: McpService,
        orchestrator: DevelopmentEvaluationOrchestrator,
        journal: MinerMcpJournal,
    ) -> None:
        if (
            type(gateway) is not AuthenticatedGateway
            or type(mcp) is not McpService
            or type(orchestrator) is not DevelopmentEvaluationOrchestrator
            or type(journal) is not MinerMcpJournal
            or journal.journal is not gateway.journal
        ):
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        self.gateway = gateway
        self.mcp = mcp
        self.orchestrator = orchestrator
        self.journal = journal

    async def call(
        self, body: bytes, headers: dict[str, str]
    ) -> AuthenticatedMcpResult:
        received = await self.gateway.receive(body, headers)
        if received.call.tool == "submit":
            self.journal.prepare_submit(received)
            result = self.mcp.call(received.call, received.requester)
            if type(result) is not SubmitReceipt:
                raise MinerMcpFailure(MinerMcpCode.CONFLICT)
            self.journal.associate_submit(received.receipt.ref, result)
            return AuthenticatedMcpResult(received.receipt.ref, result)

        result = self.mcp.call(received.call, received.requester)
        projection = None
        if type(result) is SubmissionResult:
            projection = self.journal.public_projection(
                received.requester,
                result.status.submission_id.value,
                self.gateway.challenge,
            )
        return AuthenticatedMcpResult(received.receipt.ref, result, projection)

    def reconcile_submit(self, ref: ReceiptRef, result: SubmitReceipt) -> None:
        """Attach exact trusted A9 output after an ambiguous controller response."""

        self.journal.reconcile_submit(ref, result)

    def bind_orchestration(
        self,
        ref: ReceiptRef,
        request: DevelopmentOrchestrationRequest,
        *,
        worker_id: str,
        claim_id: str,
        mode: BindMode,
    ) -> OrchestrationHandle:
        intent = self.journal.prepare_bind(
            ref,
            request,
            worker_id=worker_id,
            claim_id=claim_id,
            mode=mode,
        )
        if mode is BindMode.START:
            handle = self.orchestrator.begin(
                request, worker_id=worker_id, claim_id=claim_id
            )
        elif mode is BindMode.RESUME_EXISTING:
            handle = self.orchestrator.resume_existing(
                request, worker_id=worker_id, claim_id=claim_id
            )
        elif mode is BindMode.ATTACH_COMPLETED:
            handle = self.orchestrator.attach_completed(
                request, worker_id=worker_id, claim_id=claim_id
            )
        else:  # pragma: no cover - exact enum identity is checked before dispatch.
            raise MinerMcpFailure(MinerMcpCode.INVALID)
        self.journal.complete_bind(intent)
        return handle

    def record_outcome(self, account: DevelopmentOperationalAccount) -> None:
        self.journal.record_account(account)


__all__ = ["AuthenticatedMinerMcpService"]

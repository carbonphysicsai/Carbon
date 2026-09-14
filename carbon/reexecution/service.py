"""C-10 composition over the unchanged C-01, C-06, and C-07 owners."""

from __future__ import annotations

from dataclasses import dataclass

from carbon.audit.model import AuditFailure, ReceiptLifecycleState, digest_bytes
from carbon.audit.store import DevelopmentEvidenceLedger
from carbon.execution import (
    ClaimedExecution,
    ExecutionFailure,
    ExecutionState,
    ReconciliationDisposition,
)
from carbon.orchestration import (
    CompletedDevelopmentOrchestration,
    DevelopmentEvaluationOrchestrator,
    DevelopmentOperationalAccount,
    OperationalDisposition,
    OrchestrationFailure,
    OrchestrationHandle,
)

from .model import (
    SCIENTIFIC_STATE_FIELDS,
    ComparisonDisposition,
    ExecutionProvenance,
    ExecutionResourceObservation,
    JournalState,
    LinkedReexecutionRequest,
    ReexecutionCode,
    ReexecutionFailure,
    ReexecutionJournalView,
    ReexecutionLaunchIntent,
    ReexecutionOutcome,
    RequestWriteDisposition,
    scientific_state_digests,
)
from .store import ReexecutionJournal


@dataclass(frozen=True, slots=True)
class ReexecutionLaunch:
    claimed: ClaimedExecution
    request_disposition: RequestWriteDisposition

    def __post_init__(self) -> None:
        if (
            type(self.claimed) is not ClaimedExecution
            or type(self.request_disposition) is not RequestWriteDisposition
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)


def _shared_dependency_digests(request: LinkedReexecutionRequest) -> tuple[str, ...]:
    evidence = request.primary_request.evidence
    values = (
        evidence.strategy_digest,
        evidence.generator_digest,
        evidence.target_population_digest,
        evidence.sampling_plan_digest,
        evidence.training_data_commitment,
        evidence.reconstruction_plan_digest,
        request.primary_request.execution.reconstruction_policy_digest,
        evidence.resource_policy_digest,
        evidence.inference_request_digest,
        evidence.reference_policy_digest,
        evidence.reference_implementation_digest,
        evidence.reference_environment_digest,
        evidence.measurement_contract_digest,
        evidence.measurement_implementation_digest,
        evidence.measurement_environment_digest,
        evidence.scoring_policy_digest,
        evidence.dossier_digest,
        evidence.qualification_manifest_digest,
        evidence.source_tree_digest,
        evidence.worker_image_digest,
        evidence.execution_policy_digest,
        request.primary_request.case_manifest_digest,
        *request.primary_request.reference_request_digests,
        *(value.randomness_digest for value in request.replicas),
    )
    return tuple(sorted(set(values)))


def _validate_provenance(
    request: LinkedReexecutionRequest,
    primary: ExecutionProvenance,
    reexecution: ExecutionProvenance,
) -> None:
    if (
        type(primary) is not ExecutionProvenance
        or type(reexecution) is not ExecutionProvenance
        or primary.execution_id == reexecution.execution_id
        or primary.source_tree_digest
        != request.primary_request.evidence.source_tree_digest
        or reexecution.source_tree_digest
        != request.reexecution_request.evidence.source_tree_digest
        or primary.worker_image_digest
        != request.primary_request.evidence.worker_image_digest
        or reexecution.worker_image_digest
        != request.reexecution_request.evidence.worker_image_digest
        or len(reexecution.worker_launch_digests)
        > request.budget.maximum_worker_launches
    ):
        raise ReexecutionFailure(ReexecutionCode.CONFLICT)


class DevelopmentReexecutionService:
    """Link and compare C-07 results without becoming an evaluator or judge."""

    def __init__(
        self,
        orchestrator: DevelopmentEvaluationOrchestrator,
        evidence_ledger: DevelopmentEvidenceLedger,
        journal: ReexecutionJournal,
    ) -> None:
        if (
            type(orchestrator) is not DevelopmentEvaluationOrchestrator
            or type(evidence_ledger) is not DevelopmentEvidenceLedger
            or type(journal) is not ReexecutionJournal
            or orchestrator.evidence_ledger is not evidence_ledger
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        self.orchestrator = orchestrator
        self.evidence_ledger = evidence_ledger
        self.journal = journal

    def prepare(
        self, intent: ReexecutionLaunchIntent
    ) -> tuple[RequestWriteDisposition, ReexecutionJournalView]:
        return self.journal.prepare(intent)

    def request(
        self, request: LinkedReexecutionRequest
    ) -> tuple[RequestWriteDisposition, ReexecutionJournalView]:
        disposition = self.journal.bind(request)
        return disposition, self.journal.status(request.launch_intent)

    def launch(self, intent: ReexecutionLaunchIntent) -> ReexecutionLaunch:
        disposition, view = self.journal.prepare(intent)
        if view.state in {
            JournalState.RUNNING,
            JournalState.RECONCILIATION_REQUIRED,
            JournalState.COMPARED,
            JournalState.QUARANTINED,
        }:
            raise ReexecutionFailure(ReexecutionCode.RECONCILIATION_REQUIRED)
        try:
            self.orchestrator.execution_queue.admit_reexecution(
                intent.reexecution_execution,
                source=intent.primary_request.execution.ref,
            )
            claimed = self.orchestrator.execution_queue.claim(
                intent.reexecution_execution.ref,
                intent.worker_id,
                claim_id=intent.claim_id,
            )
            state = self.orchestrator.execution_queue.status(
                intent.reexecution_execution.ref,
                intent.reexecution_execution.requester_identity,
            ).state
            if state is ExecutionState.RECONCILIATION_REQUIRED:
                self.journal.mark_reconciliation_required(intent)
                raise ReexecutionFailure(ReexecutionCode.RECONCILIATION_REQUIRED)
            if state is ExecutionState.DISPATCHING:
                self.orchestrator.execution_queue.mark_running(claimed.claim)
            elif state is not ExecutionState.RUNNING:
                raise ReexecutionFailure(ReexecutionCode.STATE)
        except ExecutionFailure:
            raise ReexecutionFailure(ReexecutionCode.STATE) from None
        self.journal.mark_running(intent)
        return ReexecutionLaunch(claimed, disposition)

    def resume(self, intent: ReexecutionLaunchIntent) -> ReexecutionLaunch:
        journal_state = self.journal.status(intent).state
        if journal_state not in {
            JournalState.INTENT_RECORDED,
            JournalState.RECONCILIATION_REQUIRED,
        }:
            raise ReexecutionFailure(ReexecutionCode.STATE)
        try:
            claimed = self.orchestrator.execution_queue.claim(
                intent.reexecution_execution.ref,
                intent.worker_id,
                claim_id=intent.claim_id,
            )
            queue_state = self.orchestrator.execution_queue.status(
                intent.reexecution_execution.ref,
                intent.reexecution_execution.requester_identity,
            ).state
            if queue_state is not ExecutionState.RECONCILIATION_REQUIRED:
                raise ReexecutionFailure(ReexecutionCode.STATE)
            if journal_state is JournalState.INTENT_RECORDED:
                self.journal.mark_reconciliation_required(intent)
            self.orchestrator.execution_queue.reconcile(
                claimed.claim, ReconciliationDisposition.RESUME_EXISTING
            )
        except ExecutionFailure:
            raise ReexecutionFailure(ReexecutionCode.STATE) from None
        self.journal.mark_running(intent)
        return ReexecutionLaunch(claimed, RequestWriteDisposition.ALREADY_PRESENT)

    def bind_request(self, request: LinkedReexecutionRequest) -> OrchestrationHandle:
        self.journal.bind(request)
        intent = request.launch_intent
        try:
            claimed = self.orchestrator.execution_queue.claim(
                intent.reexecution_execution.ref,
                intent.worker_id,
                claim_id=intent.claim_id,
            )
            state = self.orchestrator.execution_queue.status(
                intent.reexecution_execution.ref,
                intent.reexecution_execution.requester_identity,
            ).state
        except ExecutionFailure:
            raise ReexecutionFailure(ReexecutionCode.STATE) from None
        if state is not ExecutionState.RUNNING:
            raise ReexecutionFailure(ReexecutionCode.RECONCILIATION_REQUIRED)
        return OrchestrationHandle(request.reexecution_request, claimed)

    def attach_completed(
        self, request: LinkedReexecutionRequest
    ) -> OrchestrationHandle:
        view = self.journal.status(request.launch_intent)
        if view.state not in {
            JournalState.RUNNING,
            JournalState.RECONCILIATION_REQUIRED,
        }:
            raise ReexecutionFailure(ReexecutionCode.STATE)
        try:
            handle = self.orchestrator.attach_completed(
                request.reexecution_request,
                worker_id=request.worker_id,
                claim_id=request.claim_id,
            )
        except OrchestrationFailure:
            raise ReexecutionFailure(ReexecutionCode.STATE) from None
        if view.state is JournalState.RECONCILIATION_REQUIRED:
            self.journal.mark_running(request.launch_intent)
        return handle

    def _receipt_availability(
        self,
        request: LinkedReexecutionRequest,
        result: CompletedDevelopmentOrchestration,
        *,
        verified_at_micros: int,
    ) -> ComparisonDisposition | None:
        try:
            _, primary_state = self.evidence_ledger.resolve(
                request.primary_result.ledger_reference,
                verified_at_micros=verified_at_micros,
            )
        except AuditFailure:
            return ComparisonDisposition.PRIMARY_EVIDENCE_UNAVAILABLE
        if primary_state is not ReceiptLifecycleState.ACTIVE:
            return ComparisonDisposition.PRIMARY_EVIDENCE_UNAVAILABLE
        try:
            _, reexecution_state = self.evidence_ledger.resolve(
                result.ledger_reference,
                verified_at_micros=verified_at_micros,
            )
        except AuditFailure:
            return ComparisonDisposition.REEXECUTION_EVIDENCE_UNAVAILABLE
        if reexecution_state is not ReceiptLifecycleState.ACTIVE:
            return ComparisonDisposition.REEXECUTION_EVIDENCE_UNAVAILABLE
        return None

    def associate_completed(
        self,
        request: LinkedReexecutionRequest,
        result: CompletedDevelopmentOrchestration,
        *,
        primary_provenance: ExecutionProvenance,
        reexecution_provenance: ExecutionProvenance,
        primary_resources: ExecutionResourceObservation,
        reexecution_resources: ExecutionResourceObservation,
        verified_at_micros: int,
    ) -> ReexecutionOutcome:
        if (
            type(request) is not LinkedReexecutionRequest
            or type(result) is not CompletedDevelopmentOrchestration
            or type(verified_at_micros) is not int
            or result.account.request_digest
            != request.reexecution_request.request_digest
            or result.account.submission_id
            != request.reexecution_request.execution.handle.submission_id.value
            or result.account.attempt_number
            != request.reexecution_request.execution.handle.attempt_number
            or result.signed_receipt.receipt.binding
            != request.reexecution_request.evidence
            or result.ledger_reference.receipt_digest
            != result.signed_receipt.receipt.receipt_digest
        ):
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)
        _validate_provenance(request, primary_provenance, reexecution_provenance)
        availability = self._receipt_availability(
            request, result, verified_at_micros=verified_at_micros
        )
        differences: tuple[str, ...] = ()
        failure_digest = None
        if availability is None:
            primary_state = scientific_state_digests(request.primary_scientific_state)
            reexecution_state = scientific_state_digests(
                request.reexecution_scientific_state
            )
            differences = tuple(
                name
                for name, primary, repeated in zip(
                    SCIENTIFIC_STATE_FIELDS,
                    primary_state,
                    reexecution_state,
                    strict=True,
                )
                if primary != repeated
            )
            disposition = (
                ComparisonDisposition.EXACT_BYTES_AGREE_DEVELOPMENT
                if not differences
                else ComparisonDisposition.DIFFERENT_BYTES_UNRESOLVED
            )
        else:
            disposition = availability
            failure_digest = digest_bytes(disposition.value.encode("ascii"))
        outcome = ReexecutionOutcome(
            request_id=request.request_id,
            request_digest=request.request_digest,
            disposition=disposition,
            primary_account_digest=request.primary_result.account.account_digest,
            reexecution_account_digest=result.account.account_digest,
            primary_receipt=request.primary_result.ledger_reference,
            reexecution_receipt=result.ledger_reference,
            different_scientific_fields=differences,
            shared_dependency_digests=_shared_dependency_digests(request),
            primary_provenance=primary_provenance,
            reexecution_provenance=reexecution_provenance,
            primary_resources=primary_resources,
            reexecution_resources=reexecution_resources,
            failure_evidence_digest=failure_digest,
        )
        self.journal.record_outcome(request, outcome)
        return outcome

    def associate_terminal(
        self,
        request: LinkedReexecutionRequest,
        account: DevelopmentOperationalAccount,
        *,
        primary_provenance: ExecutionProvenance,
        reexecution_provenance: ExecutionProvenance,
        primary_resources: ExecutionResourceObservation,
        reexecution_resources: ExecutionResourceObservation,
        failure_evidence_digest: str,
    ) -> ReexecutionOutcome:
        if (
            type(account) is not DevelopmentOperationalAccount
            or account.request_digest != request.reexecution_request.request_digest
            or account.submission_id
            != request.reexecution_request.execution.handle.submission_id.value
            or account.attempt_number
            != request.reexecution_request.execution.handle.attempt_number
            or account.receipt_id is not None
            or account.receipt_digest is not None
        ):
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)
        _validate_provenance(request, primary_provenance, reexecution_provenance)
        mapping = {
            OperationalDisposition.CANCELLED: ComparisonDisposition.REEXECUTION_CANCELLED,
            OperationalDisposition.FAILED_INFRASTRUCTURE: ComparisonDisposition.REEXECUTION_INFRASTRUCTURE_UNAVAILABLE,
            OperationalDisposition.INDETERMINATE: ComparisonDisposition.REEXECUTION_UNRESOLVED,
            OperationalDisposition.CONTESTED: ComparisonDisposition.REEXECUTION_UNRESOLVED,
        }
        disposition = mapping.get(
            account.disposition, ComparisonDisposition.REEXECUTION_FAILED
        )
        outcome = ReexecutionOutcome(
            request_id=request.request_id,
            request_digest=request.request_digest,
            disposition=disposition,
            primary_account_digest=request.primary_result.account.account_digest,
            reexecution_account_digest=account.account_digest,
            primary_receipt=request.primary_result.ledger_reference,
            reexecution_receipt=None,
            different_scientific_fields=(),
            shared_dependency_digests=_shared_dependency_digests(request),
            primary_provenance=primary_provenance,
            reexecution_provenance=reexecution_provenance,
            primary_resources=primary_resources,
            reexecution_resources=reexecution_resources,
            failure_evidence_digest=failure_evidence_digest,
        )
        self.journal.record_outcome(request, outcome)
        return outcome

    def associate_unavailable(
        self,
        request: LinkedReexecutionRequest,
        *,
        primary_provenance: ExecutionProvenance,
        reexecution_provenance: ExecutionProvenance,
        primary_resources: ExecutionResourceObservation,
        reexecution_resources: ExecutionResourceObservation,
        failure_evidence_digest: str,
    ) -> ReexecutionOutcome:
        _validate_provenance(request, primary_provenance, reexecution_provenance)
        state = self.orchestrator.execution_queue.status(
            request.reexecution_request.execution.ref,
            request.reexecution_request.execution.requester_identity,
        ).state
        if state is ExecutionState.RESULT_RECORDED:
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)
        outcome = ReexecutionOutcome(
            request_id=request.request_id,
            request_digest=request.request_digest,
            disposition=ComparisonDisposition.REEXECUTION_INFRASTRUCTURE_UNAVAILABLE,
            primary_account_digest=request.primary_result.account.account_digest,
            reexecution_account_digest=None,
            primary_receipt=request.primary_result.ledger_reference,
            reexecution_receipt=None,
            different_scientific_fields=(),
            shared_dependency_digests=_shared_dependency_digests(request),
            primary_provenance=primary_provenance,
            reexecution_provenance=reexecution_provenance,
            primary_resources=primary_resources,
            reexecution_resources=reexecution_resources,
            failure_evidence_digest=failure_evidence_digest,
        )
        self.journal.record_outcome(request, outcome)
        return outcome


__all__ = ["DevelopmentReexecutionService", "ReexecutionLaunch"]

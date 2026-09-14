"""C-07 composition over C-01 execution and C-06 receipt owners."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from carbon.audit import (
    DevelopmentEvaluationReceipt,
    DevelopmentEvidenceLedger,
    DevelopmentReceiptSigner,
    DevelopmentRunStatus,
    FrozenEvidenceIndex,
)
from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.execution import (
    ClaimedExecution,
    DurableExecutionQueue,
    ExecutionResultRefs,
    ExecutionStage,
    ExecutionState,
    PartialWorkRef,
    ReconciliationDisposition,
    WriteDisposition,
)
from carbon.measurement_runtime.model import (
    BurgersMeasurementResult,
    MeasurementDisposition,
)
from carbon.reconstruction.model import (
    PredictionReceipt,
    ReconstructionReceipt,
    ReconstructionStatus,
)
from carbon.reconstruction.repeats import DevelopmentRepeatPlan
from carbon.reference_runtime.protocol import ValidatedReferenceResult

from .model import (
    CompletedDevelopmentOrchestration,
    DevelopmentOperationalAccount,
    DevelopmentOrchestrationRequest,
    OperationalDisposition,
    OrchestrationCode,
    OrchestrationFailure,
    ResultOwnerRefs,
    StageAccount,
    StageDisposition,
    terminal_stage,
)

_ORDER = (
    ExecutionStage.GENERATOR,
    ExecutionStage.RECONSTRUCTION,
    ExecutionStage.PREDICTION,
    ExecutionStage.REFERENCE,
    ExecutionStage.MEASUREMENT,
    ExecutionStage.SCORE,
    ExecutionStage.RECEIPT,
)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError):
        raise OrchestrationFailure(OrchestrationCode.INVALID) from None


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def reconstruction_outcome_digest(
    repeat_plan: DevelopmentRepeatPlan,
    receipts: tuple[ReconstructionReceipt, ...],
) -> str:
    """Bind the prospectively frozen trio without selecting among replicas."""

    if (
        type(repeat_plan) is not DevelopmentRepeatPlan
        or type(receipts) is not tuple
        or len(receipts) != 3
        or any(type(item) is not ReconstructionReceipt for item in receipts)
    ):
        raise OrchestrationFailure(OrchestrationCode.INVALID)
    return _digest(
        _canonical(
            {
                "attempts": [
                    {
                        "artifact_digest": item.artifact_digest,
                        "execution_id": item.execution_id,
                        "status": item.status.value,
                    }
                    for item in receipts
                ],
                "repeat_plan_digest": repeat_plan.plan_digest,
                "schema": "carbon.c07.reconstruction-outcome.v1",
            }
        )
    )


@dataclass(frozen=True, slots=True)
class OrchestrationHandle:
    request: DevelopmentOrchestrationRequest
    claimed: ClaimedExecution

    def __post_init__(self) -> None:
        if (
            type(self.request) is not DevelopmentOrchestrationRequest
            or type(self.claimed) is not ClaimedExecution
            or self.request.execution != self.claimed.binding
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)


class DevelopmentEvaluationOrchestrator:
    """Durably associate existing domain-owner results without reimplementing them."""

    def __init__(
        self,
        execution_queue: DurableExecutionQueue,
        evidence_ledger: DevelopmentEvidenceLedger,
    ) -> None:
        if (
            type(execution_queue) is not DurableExecutionQueue
            or type(evidence_ledger) is not DevelopmentEvidenceLedger
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        self.execution_queue = execution_queue
        self.evidence_ledger = evidence_ledger

    def begin(
        self,
        request: DevelopmentOrchestrationRequest,
        *,
        worker_id: str,
        claim_id: str,
    ) -> OrchestrationHandle:
        if type(request) is not DevelopmentOrchestrationRequest:
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        self.execution_queue.admit(request.execution)
        claimed = self.execution_queue.claim(
            request.execution.ref, worker_id, claim_id=claim_id
        )
        state = self.execution_queue.status(
            request.execution.ref, request.execution.requester_identity
        ).state
        if state is ExecutionState.RECONCILIATION_REQUIRED:
            raise OrchestrationFailure(OrchestrationCode.RECONCILIATION_REQUIRED)
        if state is ExecutionState.DISPATCHING:
            self.execution_queue.mark_running(claimed.claim)
        elif state is not ExecutionState.RUNNING:
            raise OrchestrationFailure(OrchestrationCode.STATE)
        return OrchestrationHandle(request, claimed)

    def resume_existing(
        self,
        request: DevelopmentOrchestrationRequest,
        *,
        worker_id: str,
        claim_id: str,
    ) -> OrchestrationHandle:
        if type(request) is not DevelopmentOrchestrationRequest:
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        claimed = self.execution_queue.claim(
            request.execution.ref, worker_id, claim_id=claim_id
        )
        state = self.execution_queue.status(
            request.execution.ref, request.execution.requester_identity
        ).state
        if state is not ExecutionState.RECONCILIATION_REQUIRED:
            raise OrchestrationFailure(OrchestrationCode.STATE)
        self.execution_queue.reconcile(
            claimed.claim, ReconciliationDisposition.RESUME_EXISTING
        )
        return OrchestrationHandle(request, claimed)

    def attach_completed(
        self,
        request: DevelopmentOrchestrationRequest,
        *,
        worker_id: str,
        claim_id: str,
    ) -> OrchestrationHandle:
        """Reattach only an exact terminal result for idempotent replay."""

        if type(request) is not DevelopmentOrchestrationRequest:
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        claimed = self.execution_queue.claim(
            request.execution.ref, worker_id, claim_id=claim_id
        )
        state = self.execution_queue.status(
            request.execution.ref, request.execution.requester_identity
        ).state
        if state is not ExecutionState.RESULT_RECORDED:
            raise OrchestrationFailure(OrchestrationCode.STATE)
        return OrchestrationHandle(request, claimed)

    def _partials(self, handle: OrchestrationHandle) -> tuple[PartialWorkRef, ...]:
        if type(handle) is not OrchestrationHandle:
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        try:
            partials = self.execution_queue.partials(handle.claimed.claim)
        except Exception as error:
            # Preserve the source error type at its owner; expose one stable
            # composition failure to callers of this boundary.
            raise OrchestrationFailure(OrchestrationCode.STATE) from error
        stages = tuple(item.stage for item in partials)
        if stages != _ORDER[: len(stages)]:
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        return partials

    def _record(
        self,
        handle: OrchestrationHandle,
        stage: ExecutionStage,
        artifact_ref: str,
        evidence_digest: str,
    ) -> WriteDisposition:
        partial = PartialWorkRef(stage, artifact_ref, evidence_digest)
        existing = self._partials(handle)
        index = _ORDER.index(stage) if stage in _ORDER else -1
        if index < 0 or index > len(existing):
            raise OrchestrationFailure(OrchestrationCode.STATE)
        if index < len(existing):
            if existing[index] != partial:
                raise OrchestrationFailure(OrchestrationCode.CONFLICT)
            return WriteDisposition.ALREADY_PRESENT
        return self.execution_queue.record_partial(handle.claimed.claim, partial)

    def record_reconstruction(
        self,
        handle: OrchestrationHandle,
        repeat_plan: DevelopmentRepeatPlan,
        receipts: tuple[ReconstructionReceipt, ...],
    ) -> WriteDisposition:
        evidence = handle.request.evidence
        if (
            type(repeat_plan) is not DevelopmentRepeatPlan
            or type(receipts) is not tuple
            or len(repeat_plan.replicas) != 3
            or len(receipts) != 3
            or any(type(item) is not ReconstructionReceipt for item in receipts)
            or repeat_plan.plan_digest != evidence.repeat_plan_digest
            or repeat_plan.construction_plan_digest
            != evidence.reconstruction_plan_digest
            or repeat_plan.training_data_digest != evidence.training_data_commitment
            or any(
                item.binding.replicate_identity.challenge_key.challenge_id
                != evidence.challenge_id
                or item.binding.replicate_identity.challenge_key.version
                != evidence.challenge_version
                for item in repeat_plan.replicas
            )
            or tuple(item.artifact_digest for item in receipts)
            != evidence.reconstruction_attempt_digests
            or any(
                item.status is not ReconstructionStatus.COMPLETE
                or item.plan_digest != evidence.reconstruction_plan_digest
                or item.training_data_digest != evidence.training_data_commitment
                for item in receipts
            )
            or reconstruction_outcome_digest(repeat_plan, receipts)
            != evidence.reconstruction_outcome_digest
        ):
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        return self._record(
            handle,
            ExecutionStage.RECONSTRUCTION,
            "reconstruction-trio-" + evidence.reconstruction_outcome_digest[7:39],
            evidence.reconstruction_outcome_digest,
        )

    def record_generator_manifest(
        self, handle: OrchestrationHandle, case_manifest_digest: str
    ) -> WriteDisposition:
        """Associate the exact frozen public-case manifest before reconstruction."""

        if case_manifest_digest != handle.request.case_manifest_digest:
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        return self._record(
            handle,
            ExecutionStage.GENERATOR,
            "case-manifest-" + case_manifest_digest[7:39],
            case_manifest_digest,
        )

    def record_prediction(
        self, handle: OrchestrationHandle, receipt: PredictionReceipt
    ) -> WriteDisposition:
        evidence = handle.request.evidence
        if (
            type(receipt) is not PredictionReceipt
            or receipt.artifact_digest not in evidence.reconstruction_attempt_digests
            or receipt.request_digest != evidence.inference_request_digest
            or receipt.output_digest != evidence.prediction_digest
        ):
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        return self._record(
            handle,
            ExecutionStage.PREDICTION,
            "prediction-" + receipt.output_digest[7:39],
            receipt.output_digest,
        )

    def record_reference(
        self, handle: OrchestrationHandle, result: ValidatedReferenceResult
    ) -> WriteDisposition:
        expected = handle.request.evidence.reference_artifact_digest
        if (
            type(result) is not ValidatedReferenceResult
            or result.outcome is not ReferenceRunOutcome.SUPPORTED
            or result.request_digest not in handle.request.reference_request_digests
            or result.artifact_digest != expected
        ):
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        return self._record(
            handle,
            ExecutionStage.REFERENCE,
            "reference-" + expected[7:39],
            expected,
        )

    def record_measurement(
        self, handle: OrchestrationHandle, result: BurgersMeasurementResult
    ) -> WriteDisposition:
        expected = handle.request.evidence.measurement_result_digest
        if (
            type(result) is not BurgersMeasurementResult
            or result.disposition
            is not MeasurementDisposition.COMPLETE_DEVELOPMENT_ONLY
            or result.request_digest not in handle.request.measurement_request_digests
            or result.result_digest != expected
            or result.score_input is not None
            or result.score_eligible is not False
        ):
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        return self._record(
            handle,
            ExecutionStage.MEASUREMENT,
            "measurement-" + expected[7:39],
            expected,
        )

    def record_unresolved_score(self, handle: OrchestrationHandle) -> WriteDisposition:
        digest = handle.request.evidence.scoring_policy_digest
        return self._record(
            handle,
            ExecutionStage.SCORE,
            "score-unresolved-" + digest[7:39],
            digest,
        )

    @staticmethod
    def _stage_accounts(
        partials: tuple[PartialWorkRef, ...],
        *,
        terminal_disposition: OperationalDisposition | None = None,
    ) -> tuple[StageAccount, ...]:
        result = []
        for index, item in enumerate(partials):
            disposition = (
                StageDisposition.UNRESOLVED_NO_QUALIFIED_SCORE
                if item.stage is ExecutionStage.SCORE
                else StageDisposition.COMPLETE
            )
            if terminal_disposition is not None and index == len(partials) - 1:
                if terminal_disposition is OperationalDisposition.CANCELLED:
                    disposition = StageDisposition.CANCELLED
                elif terminal_disposition is OperationalDisposition.INDETERMINATE:
                    disposition = StageDisposition.INDETERMINATE
                else:
                    disposition = StageDisposition.FAILED
            result.append(
                StageAccount(
                    item.stage, disposition, item.artifact_ref, item.artifact_digest
                )
            )
        return tuple(result)

    @staticmethod
    def _result_refs(
        account: DevelopmentOperationalAccount, owners: ResultOwnerRefs
    ) -> ExecutionResultRefs:
        return ExecutionResultRefs(
            private_result_ref="c07-account-" + account.account_digest[7:39],
            private_result_digest=account.account_digest,
            card_record_ref=owners.card_record_ref,
            transcript_ref=owners.transcript_ref,
            transcript_digest=owners.transcript_digest,
        )

    def finalize_complete(
        self,
        handle: OrchestrationHandle,
        *,
        receipt_id: str,
        signer: DevelopmentReceiptSigner,
        evidence_index: FrozenEvidenceIndex,
        result_owners: ResultOwnerRefs,
        started_at_micros: int,
        finished_at_micros: int,
        verified_at_micros: int,
    ) -> CompletedDevelopmentOrchestration:
        if (
            type(handle) is not OrchestrationHandle
            or type(signer) is not DevelopmentReceiptSigner
            or type(evidence_index) is not FrozenEvidenceIndex
            or type(result_owners) is not ResultOwnerRefs
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        status = self.execution_queue.status(
            handle.request.execution.ref,
            handle.request.execution.requester_identity,
        )
        if status.state not in {ExecutionState.RUNNING, ExecutionState.RESULT_RECORDED}:
            raise OrchestrationFailure(OrchestrationCode.STATE)
        if status.state is not ExecutionState.RESULT_RECORDED:
            partials = self._partials(handle)
            if tuple(item.stage for item in partials) != _ORDER[:-1]:
                raise OrchestrationFailure(OrchestrationCode.STATE)
        receipt = DevelopmentEvaluationReceipt(
            receipt_id=receipt_id,
            binding=handle.request.evidence,
            run_status=DevelopmentRunStatus.COMPLETE_UNRESOLVED,
            started_at_micros=started_at_micros,
            finished_at_micros=finished_at_micros,
            signing_key_id=signer.verification_key.key_id,
            signing_public_key_digest=signer.verification_key.public_key_digest,
        )
        signed = signer.sign(receipt)
        _, ledger_ref = self.evidence_ledger.append(
            signed, evidence_index, verified_at_micros=verified_at_micros
        )
        if status.state is not ExecutionState.RESULT_RECORDED:
            self._record(
                handle,
                ExecutionStage.RECEIPT,
                receipt.receipt_id,
                receipt.receipt_digest,
            )
        account = DevelopmentOperationalAccount(
            request_digest=handle.request.request_digest,
            submission_id=handle.request.execution.handle.submission_id.value,
            attempt_number=handle.request.execution.handle.attempt_number,
            disposition=OperationalDisposition.COMPLETE_UNRESOLVED,
            stages=self._stage_accounts(
                (
                    PartialWorkRef(
                        ExecutionStage.GENERATOR,
                        "case-manifest-" + handle.request.case_manifest_digest[7:39],
                        handle.request.case_manifest_digest,
                    ),
                    PartialWorkRef(
                        ExecutionStage.RECONSTRUCTION,
                        "reconstruction-trio-"
                        + handle.request.evidence.reconstruction_outcome_digest[7:39],
                        handle.request.evidence.reconstruction_outcome_digest,
                    ),
                    PartialWorkRef(
                        ExecutionStage.PREDICTION,
                        "prediction-" + handle.request.evidence.prediction_digest[7:39],
                        handle.request.evidence.prediction_digest,
                    ),
                    PartialWorkRef(
                        ExecutionStage.REFERENCE,
                        "reference-"
                        + handle.request.evidence.reference_artifact_digest[7:39],
                        handle.request.evidence.reference_artifact_digest,
                    ),
                    PartialWorkRef(
                        ExecutionStage.MEASUREMENT,
                        "measurement-"
                        + handle.request.evidence.measurement_result_digest[7:39],
                        handle.request.evidence.measurement_result_digest,
                    ),
                    PartialWorkRef(
                        ExecutionStage.SCORE,
                        "score-unresolved-"
                        + handle.request.evidence.scoring_policy_digest[7:39],
                        handle.request.evidence.scoring_policy_digest,
                    ),
                    PartialWorkRef(
                        ExecutionStage.RECEIPT,
                        receipt.receipt_id,
                        receipt.receipt_digest,
                    ),
                )
            ),
            missing_stages=(ExecutionStage.ARCHIVE,),
            started_at_micros=started_at_micros,
            finished_at_micros=finished_at_micros,
            receipt_id=receipt.receipt_id,
            receipt_digest=receipt.receipt_digest,
        )
        self.execution_queue.record_result(
            handle.claimed.claim, self._result_refs(account, result_owners)
        )
        return CompletedDevelopmentOrchestration(account, signed, ledger_ref)

    def conclude_without_receipt(
        self,
        handle: OrchestrationHandle,
        *,
        disposition: OperationalDisposition,
        failure_evidence_ref: str,
        failure_evidence_digest: str,
        result_owners: ResultOwnerRefs,
        started_at_micros: int,
        finished_at_micros: int,
        failed_stage: ExecutionStage | None = None,
    ) -> DevelopmentOperationalAccount:
        if (
            type(handle) is not OrchestrationHandle
            or type(disposition) is not OperationalDisposition
            or disposition is OperationalDisposition.COMPLETE_UNRESOLVED
            or type(result_owners) is not ResultOwnerRefs
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        status = self.execution_queue.status(
            handle.request.execution.ref,
            handle.request.execution.requester_identity,
        )
        if status.state not in {ExecutionState.RUNNING, ExecutionState.RESULT_RECORDED}:
            raise OrchestrationFailure(OrchestrationCode.STATE)
        prescribed = terminal_stage(disposition)
        partials = self._partials(handle)
        next_stage = _ORDER[len(partials)] if len(partials) < len(_ORDER) else None
        chosen = prescribed if prescribed is not None else failed_stage or next_stage
        if (
            chosen is None
            or chosen is ExecutionStage.RECEIPT
            or chosen is ExecutionStage.ARCHIVE
        ):
            raise OrchestrationFailure(OrchestrationCode.STATE)
        if prescribed is not None and chosen is not prescribed:
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)
        terminal_partial = PartialWorkRef(
            chosen, failure_evidence_ref, failure_evidence_digest
        )
        exact_replay = bool(partials) and partials[-1] == terminal_partial
        if not exact_replay and chosen is not next_stage:
            raise OrchestrationFailure(OrchestrationCode.STATE)
        if not exact_replay:
            self._record(handle, chosen, failure_evidence_ref, failure_evidence_digest)
        partials = self._partials(handle)
        observed = tuple(item.stage for item in partials)
        account = DevelopmentOperationalAccount(
            request_digest=handle.request.request_digest,
            submission_id=handle.request.execution.handle.submission_id.value,
            attempt_number=handle.request.execution.handle.attempt_number,
            disposition=disposition,
            stages=self._stage_accounts(partials, terminal_disposition=disposition),
            missing_stages=tuple(item for item in _ORDER if item not in observed)
            + (ExecutionStage.ARCHIVE,),
            started_at_micros=started_at_micros,
            finished_at_micros=finished_at_micros,
        )
        self.execution_queue.record_result(
            handle.claimed.claim, self._result_refs(account, result_owners)
        )
        return account


__all__ = [
    "DevelopmentEvaluationOrchestrator",
    "OrchestrationHandle",
    "reconstruction_outcome_digest",
]

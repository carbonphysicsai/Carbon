"""Nominal DEVELOPMENT composition for one candidate job per fresh pack."""

from __future__ import annotations

import time

from carbon.candidates.model import CandidateRef
from carbon.candidates.store import CandidateJournal
from carbon.execution import (
    DurableExecutionBinding,
    DurableExecutionQueue,
    ExecutionResultRefs,
    ExecutionScope,
    ExecutionStage,
    PartialWorkRef,
)
from carbon.fees import (
    FeeOperationKey,
    RequesterIdentity,
    SubmissionService,
    SubmissionState,
)
from carbon.fees.strategy_identity import identify_strategy
from carbon.seeding import EvaluationBinding
from carbon.traineval import FixtureTrainEvalService
from carbon.traineval.model import (
    CompletedFixtureRun,
    InfrastructureFailedRun,
    InfrastructureRetryClass,
    StrategyFailedRun,
)
from carbon.transport.gateway import requester_for_receipt
from carbon.transport.models import canonical, digest

from .model import PackAttemptBinding, PackCode, PackFailure, PackState
from .store import DevelopmentEvaluationPackLedger, _bound_result_digest


def _sha(value: bytes) -> str:
    return "sha256:" + digest(value)


class DevelopmentEvaluationPackService:
    """Fixture-only pack lifecycle; no REAL/LIVE, sharing, reward, or answers."""

    def __init__(
        self,
        ledger: DevelopmentEvaluationPackLedger,
        submissions: SubmissionService,
        evaluator: FixtureTrainEvalService,
        executions: DurableExecutionQueue,
    ) -> None:
        if (
            type(ledger) is not DevelopmentEvaluationPackLedger
            or type(ledger.journal) is not CandidateJournal
            or type(submissions) is not SubmissionService
            or type(evaluator) is not FixtureTrainEvalService
            or type(executions) is not DurableExecutionQueue
        ):
            raise PackFailure(PackCode.INVALID)
        self.ledger = ledger
        self.submissions = submissions
        self.evaluator = evaluator
        self.executions = executions

    def status(self, candidate: CandidateRef):
        return self.ledger.status(candidate)

    def read_summary(self, candidate: CandidateRef):
        return self.ledger.read_summary(candidate)

    def evaluate(self, candidate: CandidateRef):
        try:
            current = self.ledger.status(candidate)
        except PackFailure as failure:
            if failure.code is not PackCode.NOT_FOUND:
                raise
        else:
            if current.state is PackState.SUMMARY_DELIVERED:
                return self.ledger.read_summary(candidate)
            if current.state is PackState.CLOSED:
                return self.ledger.deliver_summary(candidate)
            if current.state is PackState.RESULT_RECORDED:
                assignment = self.ledger.internal_assignment(candidate)
                receipt = self.ledger.journal.receipts.resolve(
                    self.ledger.receipt_ref(candidate)
                )
                requester = requester_for_receipt(
                    self.ledger.journal.receipts.context, receipt
                )
                self.ledger.close(assignment, self.executions, requester)
                return self.ledger.deliver_summary(candidate)
            raise PackFailure(PackCode.INDETERMINATE)

        assignment, _ = self.ledger.assign(candidate)
        try:
            strategy, receipt_ref = self.ledger.candidate_inputs(assignment)
            receipt = self.ledger.journal.receipts.resolve(receipt_ref)
            requester = requester_for_receipt(
                self.ledger.journal.receipts.context, receipt
            )
            context = self.ledger.journal.context
            submission = self.submissions.submit(
                requester, context.pack.challenge_key, strategy
            )
            self.submissions.mark_validated(submission, requester)
            self.submissions.admit_fixture(submission, requester)
            self.submissions._bind_development_pack(
                submission,
                requester,
                EvaluationBinding(assignment.pack.evaluation_binding_bytes()),
            )
            started = self.submissions.start_fixture_attempt(
                submission,
                requester,
                FeeOperationKey(
                    digest(canonical([candidate.identity, "development-pack-charge"]))
                ),
                FeeOperationKey(
                    digest(canonical([candidate.identity, "development-pack-refund"]))
                ),
            )
            envelope = started.envelope
            if envelope is None:
                raise PackFailure(PackCode.INDETERMINATE)
            identity = identify_strategy(strategy, self.ledger.journal.limits)
            if identity.strategy_hash is None:
                raise PackFailure(PackCode.CONFLICT)
            while True:
                handle = envelope.handle
                configuration_digest = digest(
                    canonical(
                        {
                            "pack": assignment.pack.identity,
                            "generator": handle.seed_pin.generator_digest,
                            "scoring": handle.seed_pin.scoring_digest,
                            "environment": handle.environment_pin.container_digest,
                        }
                    )
                )
                binding = DurableExecutionBinding(
                    handle=handle,
                    requester_identity=RequesterIdentity(requester.value),
                    strategy_hash=identity.strategy_hash,
                    scope=ExecutionScope.FIXTURE_DEVELOPMENT,
                    resolved_plan_digest=_sha(canonical(strategy)),
                    reconstruction_policy_digest=_sha(
                        canonical(["fixture-reconstruction", context.identity])
                    ),
                    resource_policy_digest=_sha(
                        canonical(
                            ["fixture-resource", context.environment.container_digest]
                        )
                    ),
                    protected_evaluation_policy_digest=_sha(
                        canonical(
                            [self.ledger.policy.identity, assignment.pack.identity]
                        )
                    ),
                )
                self.ledger.bind_attempt(
                    PackAttemptBinding(
                        assignment,
                        binding,
                        digest(canonical(strategy)),
                        configuration_digest,
                    )
                )
                self.executions.admit(binding)
                claimed = self.executions.claim(
                    binding.ref,
                    "development-pack-worker",
                    claim_id=(
                        f"pack.{assignment.pack.identity}.{handle.attempt_number}"
                    ),
                )
                if claimed.binding != binding:
                    raise PackFailure(PackCode.INDETERMINATE)
                self.executions.mark_running(claimed.claim)
                self.executions.record_partial(
                    claimed.claim,
                    PartialWorkRef(
                        ExecutionStage.RECONSTRUCTION,
                        "strategy." + digest(canonical(strategy)),
                        _sha(canonical(strategy)),
                    ),
                )
                fixture_started = time.perf_counter_ns()
                outcome = self.evaluator.run_fixture(envelope)
                self.ledger.record_fixture_execution_timing(
                    candidate, time.perf_counter_ns() - fixture_started
                )
                if type(outcome) is InfrastructureFailedRun:
                    if outcome.handle != handle:
                        raise PackFailure(PackCode.CONFLICT)
                    if outcome.retry_class is InfrastructureRetryClass.RETRYABLE:
                        self.submissions.retry_infrastructure(handle)
                        retry_status = self.submissions.get_status(
                            submission, requester
                        )
                        if retry_status.state is SubmissionState.QUEUED:
                            self.executions.retryable_infrastructure(claimed.claim)
                            envelope = self.submissions.start_fixture_retry_attempt(
                                submission, requester
                            )
                            continue
                        if retry_status.state is not SubmissionState.FAILED_INFRA:
                            raise PackFailure(PackCode.INDETERMINATE)
                    else:
                        self.submissions.fail_infrastructure(handle)
                    self.executions.fail_infrastructure(claimed.claim)
                    self.ledger.close_incomplete(assignment, self.executions, requester)
                    raise PackFailure(PackCode.STATE)
                if type(outcome) is StrategyFailedRun:
                    if outcome.handle != handle:
                        raise PackFailure(PackCode.CONFLICT)
                    self.executions.fail_strategy(claimed.claim)
                    self.submissions.fail_strategy(handle)
                    self.ledger.close_incomplete(assignment, self.executions, requester)
                    raise PackFailure(PackCode.STATE)
                if type(outcome) is not CompletedFixtureRun or outcome.handle != handle:
                    raise PackFailure(PackCode.INDETERMINATE)
                break
            result = outcome.internal_result
            self.submissions._record_private_development_result(handle, result)
            if (
                self.submissions.get_status(submission, requester).state
                is not SubmissionState.SCORED
            ):
                raise PackFailure(PackCode.INDETERMINATE)
            card = self.submissions._read_private_development_card(
                submission, requester
            )
            result_digest = _bound_result_digest(
                assignment.pack.identity,
                binding.handle.attempt_number,
                configuration_digest,
                card,
            )
            self.executions.record_result(
                claimed.claim,
                ExecutionResultRefs(
                    private_result_ref="result." + submission.value,
                    private_result_digest=result_digest,
                    card_record_ref=submission.value,
                    transcript_ref="trace." + assignment.pack.identity,
                    transcript_digest=_sha(
                        canonical([assignment.pack.identity, configuration_digest])
                    ),
                ),
            )
            self.ledger.record_result(assignment, binding.ref, result_digest, card)
            self.ledger.close(assignment, self.executions, requester)
            return self.ledger.deliver_summary(candidate)
        except PackFailure:
            state = self.ledger.status(candidate).state
            if state in (PackState.ASSIGNED, PackState.ATTEMPT_BOUND):
                self.ledger.require_reconciliation(candidate)
            raise
        except Exception:  # noqa: BLE001 - private exception details never escape.
            state = self.ledger.status(candidate).state
            if state in (PackState.ASSIGNED, PackState.ATTEMPT_BOUND):
                self.ledger.require_reconciliation(candidate)
            raise PackFailure(PackCode.INDETERMINATE) from None


__all__ = ("DevelopmentEvaluationPackService",)

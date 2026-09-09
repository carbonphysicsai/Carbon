"""One existing A7/A8/A6 fixture lifecycle, with durable intent and projection."""

from carbon.fees import FeeOperationKey, SubmissionService, SubmissionState
from carbon.fees.strategy_identity import identify_strategy
from carbon.scoring.model import ScoreStatus
from carbon.traineval import FixtureTrainEvalService
from carbon.traineval.model import CompletedFixtureRun, InfrastructureFailedRun
from carbon.transport.gateway import requester_for_receipt
from carbon.transport.models import canonical, digest

from .model import AcceptedFixtureRecord, CandidateCode, CandidateFailure
from .store import CandidateJournal


class FixtureCandidateService:
    """Trusted local composition; no miner-facing result/acceptance method."""

    def __init__(
        self,
        journal: CandidateJournal,
        submissions: SubmissionService,
        evaluator: FixtureTrainEvalService,
    ):
        if (
            type(journal) is not CandidateJournal
            or type(submissions) is not SubmissionService
            or type(evaluator) is not FixtureTrainEvalService
        ):
            raise CandidateFailure(CandidateCode.CONTEXT)
        self.journal, self.submissions, self.evaluator = journal, submissions, evaluator

    def evaluate(self, ref):
        failed = False
        try:
            return self._evaluate(ref)
        except CandidateFailure:
            raise
        except Exception:  # noqa: BLE001 - private evaluator errors cannot escape.
            failed = True
        if failed:
            raise CandidateFailure(CandidateCode.INDETERMINATE)

    def _evaluate(self, ref):
        if self.journal.state(ref) == "ACCEPTED_FIXTURE":
            return self.journal.resolve_accepted_fixture(ref)
        strategy, receipt_ref = self.journal._claim(ref)
        receipt = self.journal.receipts.resolve(receipt_ref)
        requester = requester_for_receipt(self.journal.receipts.context, receipt)
        context = self.journal.context
        # Durable DISPATCHING is deliberately retained on an exception here.
        # A7 process-local state cannot prove restart-safe admission/dispatch.
        submission = self.submissions.submit(
            requester, context.pack.challenge_key, strategy
        )
        self.submissions.mark_validated(submission, requester)
        self.submissions.admit_fixture(submission, requester)
        self.journal._transition(ref, "DISPATCHING", "ADMITTED")
        started = self.submissions.start_fixture_attempt(
            submission,
            requester,
            FeeOperationKey(digest(canonical([ref.identity, "charge"]))),
            FeeOperationKey(digest(canonical([ref.identity, "refund"]))),
        )
        envelope = started.envelope
        if envelope is None:
            raise CandidateFailure(CandidateCode.INDETERMINATE)
        handle = envelope.handle
        pin = handle.seed_pin
        if (
            handle.environment_pin != context.environment
            or pin.challenge_key != context.pack.challenge_key
            or pin.scoring_version != context.pack.scoring_version
            or pin.scoring_digest != context.pack.scoring_digest
            or pin.generator_version != context.pack.generator_version_required
            or pin.generator_digest != context.pack.generator_digest_required
        ):
            self.submissions.fail_infrastructure(handle)
            self.journal._transition(ref, "ADMITTED", "FAILED_INFRA")
            raise CandidateFailure(CandidateCode.CONTEXT)
        self.journal._transition(ref, "ADMITTED", "RUNNING")
        outcome = self.evaluator.run_fixture(envelope)
        if type(outcome) is InfrastructureFailedRun:
            self.submissions.fail_infrastructure(handle)
            self.journal._transition(ref, "RUNNING", "FAILED_INFRA")
            raise CandidateFailure(CandidateCode.INFRASTRUCTURE)
        if type(outcome) is not CompletedFixtureRun or outcome.handle != handle:
            raise CandidateFailure(CandidateCode.INDETERMINATE)
        result = outcome.internal_result
        if result.pack_pin != context.pack:
            self.submissions.fail_infrastructure(handle)
            self.journal._transition(ref, "RUNNING", "FAILED_INFRA")
            raise CandidateFailure(CandidateCode.CONTEXT)
        published = self.submissions.complete_and_publish(handle, result)
        if published.state is not SubmissionState.PUBLISHED:
            raise CandidateFailure(CandidateCode.INDETERMINATE)
        if result.status is not ScoreStatus.SCORED:
            self.journal._transition(ref, "RUNNING", "REJECTED_SCIENCE")
            raise CandidateFailure(CandidateCode.NOT_ACCEPTED)
        identity = identify_strategy(strategy, self.journal.limits)
        record = AcceptedFixtureRecord(
            ref,
            context.identity,
            receipt.challenge_id,
            receipt.challenge_version,
            digest(canonical(strategy)),
            identity.strategy_hash.value,
            receipt.ref.sequence,
            receipt.ref.digest,
            receipt.hotkey,
            receipt.coldkey,
            receipt.registered_at,
            receipt.snapshot_id,
            receipt.finalized_block,
            submission.value,
            result.combined_score.hex(),
            tuple(leg.score.hex() for leg in result.leg_scores),
        )
        self.journal._complete_fixture(record)
        return self.journal.resolve_accepted_fixture(ref)

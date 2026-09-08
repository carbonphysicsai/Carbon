"""Complete B-E4 fixture lifecycle under a non-qualifying authority ceiling.

The trusted orchestrator in this module joins existing B-07S, B-07B/B-07C,
and A7/A8 fixture owners.  It never exposes worker, private-record, held-out,
or transfer capabilities to a fixture driver and cannot create qualifying
gauntlet evidence.
"""

from __future__ import annotations

import hashlib
import sys
import time
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from pathlib import Path

from carbon.fees import FeeOperationKey, RequesterIdentity, SubmissionService
from carbon.mcp import McpService, SubmissionResult
from carbon.prior_compat import PrivatePriorProjection
from carbon.research import (
    ExactPriorSelector,
    ExperimentRecord,
    GetResearchResultRequest,
    GetResearchResultResult,
    InMemoryResearchTaskProvider,
    LocalResearchService,
    NoPriorSelector,
    PairedPracticeTaskSpec,
    PublicResearchFinding,
    ResearchFailureCategory,
    ResearchReceipt,
    ResearchTaskState,
    StartResearchTaskRequest,
    StartResearchTaskResult,
    canonical_digest,
)
from carbon.traineval.model import InfrastructureFailedRun
from carbon.traineval.resolved_fixture import (
    FixtureCompilationFailed,
    FixtureConstructionFailed,
    FixtureMeasurementFailed,
    FixtureReferenceFailed,
    FixtureResourceFailed,
    ResolvedFixtureCompletedRun,
    ResolvedPlanFixtureTrainEvalService,
)

from .agents import (
    FIXTURE_CORPUS_ID,
    FIXTURE_CORPUS_VERSION,
    AllowedPracticeFeedback,
    CommonArmRng,
    DriverSelection,
    FixtureAgentDriver,
    FixtureDriverRef,
)
from .execution import (
    GENERIC_WORKFLOW_STEPS,
    FrozenArmArtifact,
    NonQualifyingRunPlan,
    OfficialFixtureSubmission,
    PreparedFixturePreflight,
    _research_result,
    prepare_nonqualifying_preflight,
    read_official_fixture_result,
    submit_selected_prepared_fixture_run,
)
from .harness import AgentSession
from .meter import NormalizedComputeReceipt, PolicyWorkMeter, WallTimeObservation
from .model import ExperimentalArm
from .proposal import fixture_primary_quality, fixture_transfer_quality

NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING = (
    "DESIGN_ANALYSIS_FIXTURE_REHEARSAL_ONLY_NO_QUALIFICATION_AUTHORITY"
)
DETERMINISTIC_POPULATION_SCOPE = (
    "FIVE_REGISTERED_DETERMINISTIC_FIXTURE_POLICIES_NOT_AUTONOMOUS_AGENT_POPULATION"
)
_DRIVER_ARTIFACT_DOMAIN = b"carbon.be4.executable-driver-artifact.v1\x00"
_TREATMENT_DOMAIN = b"carbon.be4.lifecycle-treatment.v1\x00"
_LIFECYCLE_DOMAIN = b"carbon.be4.nonqualifying-lifecycle.v1\x00"
_PRACTICE_DOMAIN = b"carbon.be4.practice-correlation.v1\x00"
_PRACTICE_FACTORY_TOKEN = object()
_LIFECYCLE_FACTORY_TOKEN = object()


def _sha(domain: bytes, fields: tuple[str, ...]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            domain + b"\x00".join(item.encode("ascii") for item in fields)
        ).hexdigest()
    )


class LifecycleFailureKind(str, Enum):
    CANDIDATE = "CANDIDATE"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    REFERENCE = "REFERENCE"
    MEASUREMENT = "MEASUREMENT"


class NonQualifyingLifecycleError(RuntimeError):
    """Closed orchestration failure preserving B-E2 cause separation."""

    def __init__(self, kind: LifecycleFailureKind, stage: str) -> None:
        if type(kind) is not LifecycleFailureKind or type(stage) is not str:
            raise TypeError("lifecycle failure requires exact closed values")
        self.kind = kind
        self.stage = stage
        super().__init__(f"{kind.value} lifecycle failure at {stage}")


@dataclass(frozen=True, slots=True)
class ExecutableDriverArtifactRef:
    """Source-bound identity for one trusted in-process fixture policy."""

    driver_ref: FixtureDriverRef
    source_digest: str
    python_runtime: str
    content_digest: str

    def __post_init__(self) -> None:
        if (
            type(self) is not ExecutableDriverArtifactRef
            or type(self.driver_ref) is not FixtureDriverRef
            or type(self.source_digest) is not str
            or type(self.python_runtime) is not str
            or type(self.content_digest) is not str
        ):
            raise TypeError("executable driver artifact is invalid")
        expected = _sha(
            _DRIVER_ARTIFACT_DOMAIN,
            (
                self.driver_ref.profile.value,
                self.driver_ref.driver_id,
                self.driver_ref.driver_version,
                self.driver_ref.runtime_id,
                self.driver_ref.runtime_version,
                self.driver_ref.runtime_digest,
                self.driver_ref.policy_digest,
                FIXTURE_CORPUS_ID if self.driver_ref.corpus_digest else "NO_CORPUS",
                (
                    FIXTURE_CORPUS_VERSION
                    if self.driver_ref.corpus_digest
                    else "NO_CORPUS"
                ),
                self.driver_ref.corpus_digest or "NO_CORPUS",
                self.source_digest,
                self.python_runtime,
            ),
        )
        if self.content_digest != expected:
            raise ValueError("driver artifact digest does not bind executable source")


def executable_driver_artifact(
    driver: FixtureAgentDriver,
) -> ExecutableDriverArtifactRef:
    """Bind the exact installed fixture-policy source without exposing it to a driver."""

    if type(driver) is not FixtureAgentDriver:
        raise TypeError("driver artifact requires an exact fixture driver")
    source = Path(__file__).with_name("agents.py").read_bytes()
    source_digest = "sha256:" + hashlib.sha256(source).hexdigest()
    runtime = f"{sys.implementation.name}-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    digest = _sha(
        _DRIVER_ARTIFACT_DOMAIN,
        (
            driver.ref.profile.value,
            driver.ref.driver_id,
            driver.ref.driver_version,
            driver.ref.runtime_id,
            driver.ref.runtime_version,
            driver.ref.runtime_digest,
            driver.ref.policy_digest,
            FIXTURE_CORPUS_ID if driver.ref.corpus_digest else "NO_CORPUS",
            FIXTURE_CORPUS_VERSION if driver.ref.corpus_digest else "NO_CORPUS",
            driver.ref.corpus_digest or "NO_CORPUS",
            source_digest,
            runtime,
        ),
    )
    return ExecutableDriverArtifactRef(driver.ref, source_digest, runtime, digest)


@dataclass(frozen=True, slots=True)
class LifecycleTreatmentArtifact:
    """Full-content treatment identity; never a prior authorization."""

    arm: ExperimentalArm
    frozen_artifact: FrozenArmArtifact
    material_ref: str
    content_digest: str

    def __post_init__(self) -> None:
        if (
            type(self) is not LifecycleTreatmentArtifact
            or type(self.arm) is not ExperimentalArm
            or type(self.frozen_artifact) is not FrozenArmArtifact
            or self.frozen_artifact.arm is not self.arm
            or type(self.material_ref) is not str
            or type(self.content_digest) is not str
        ):
            raise TypeError("lifecycle treatment artifact is invalid")
        expected = _sha(
            _TREATMENT_DOMAIN,
            (
                self.arm.value,
                self.frozen_artifact.artifact_id,
                self.frozen_artifact.artifact_version,
                self.frozen_artifact.content_digest,
                self.material_ref,
                NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING,
            ),
        )
        if self.content_digest != expected:
            raise ValueError("treatment digest does not bind exact material")


def lifecycle_treatment_artifact(
    plan: NonQualifyingRunPlan,
    projection: PrivatePriorProjection,
) -> LifecycleTreatmentArtifact:
    if (
        type(plan) is not NonQualifyingRunPlan
        or type(projection) is not PrivatePriorProjection
    ):
        raise TypeError("treatment material requires exact lifecycle inputs")
    if plan.identity.arm is ExperimentalArm.NO_PRIOR:
        material = "NO_PRIOR_MATERIAL"
    elif plan.identity.arm is ExperimentalArm.GENERIC_PRIOR:
        material = _sha(b"carbon.be4.generic-workflow.v1\x00", GENERIC_WORKFLOW_STEPS)
    elif plan.identity.arm is ExperimentalArm.V1_DIRECTIVE_PRIOR:
        if (
            projection.receipt.source_prior_pack_ref
            != plan.arm_artifact.source_prior_pack_ref
        ):
            raise ValueError("v1 projection source does not match the frozen arm")
        material = (
            f"{projection.receipt.mapping_version}:"
            f"{projection.receipt.output_hash}:"
            f"{projection.receipt.source_prior_pack_ref.content_hash}"
        )
    else:
        ref = plan.identity.prior_pack_ref
        if ref is None or ref != projection.receipt.source_prior_pack_ref:
            raise ValueError("v2 treatment does not match the exact projected pack")
        material = ":".join(
            (ref.channel.value, str(ref.publication_sequence), ref.content_hash)
        )
    digest = _sha(
        _TREATMENT_DOMAIN,
        (
            plan.identity.arm.value,
            plan.arm_artifact.artifact_id,
            plan.arm_artifact.artifact_version,
            plan.arm_artifact.content_digest,
            material,
            NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING,
        ),
    )
    return LifecycleTreatmentArtifact(
        plan.identity.arm, plan.arm_artifact, material, digest
    )


@dataclass(frozen=True, slots=True)
class PracticeAttemptEvidence:
    proposal_digest: str
    public_finding: PublicResearchFinding
    receipt: ResearchReceipt
    experiment_record: ExperimentRecord
    feedback: AllowedPracticeFeedback
    start_request_digest: str
    start_reply_digest: str
    poll_request_digest: str
    poll_reply_digest: str
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not PracticeAttemptEvidence
            or self._factory_token is not _PRACTICE_FACTORY_TOKEN
            or type(self.public_finding) is not PublicResearchFinding
            or type(self.receipt) is not ResearchReceipt
            or type(self.experiment_record) is not ExperimentRecord
            or type(self.feedback) is not AllowedPracticeFeedback
            or self.receipt.task_id != self.experiment_record.task_id
            or self.receipt.immutable_bindings != self.experiment_record.task_bindings
            or self.receipt.public_findings != (self.public_finding,)
            or self.feedback.proposal_digest != self.proposal_digest
            or self.feedback.observed_range != self.public_finding.uncertainty_band
        ):
            raise ValueError("practice evidence does not bind its B-07B/B-07C lineage")
        digests = (
            self.start_request_digest,
            self.start_reply_digest,
            self.poll_request_digest,
            self.poll_reply_digest,
            self.content_digest,
        )
        if any(
            type(item) is not str or not item.startswith("sha256:") or len(item) != 71
            for item in digests
        ):
            raise TypeError("practice correlation digests are invalid")
        expected = _practice_content_digest(
            proposal_digest=self.proposal_digest,
            public_finding=self.public_finding,
            receipt=self.receipt,
            experiment_record=self.experiment_record,
            feedback=self.feedback,
            start_request_digest=self.start_request_digest,
            start_reply_digest=self.start_reply_digest,
            poll_request_digest=self.poll_request_digest,
            poll_reply_digest=self.poll_reply_digest,
        )
        if self.content_digest != expected:
            raise ValueError("practice correlation digest does not bind its content")


def _practice_content_digest(
    *,
    proposal_digest: str,
    public_finding: PublicResearchFinding,
    receipt: ResearchReceipt,
    experiment_record: ExperimentRecord,
    feedback: AllowedPracticeFeedback,
    start_request_digest: str,
    start_reply_digest: str,
    poll_request_digest: str,
    poll_reply_digest: str,
) -> str:
    execution = experiment_record.execution_identity
    return _sha(
        _PRACTICE_DOMAIN,
        (
            proposal_digest,
            receipt.task_id.value,
            receipt.receipt_ref.receipt_digest,
            experiment_record.sampling_plan_ref.content_digest,
            execution.worker_implementation_digest,
            execution.environment_digest,
            str(execution.attempts),
            canonical_digest(public_finding),
            feedback.content_digest,
            start_request_digest,
            start_reply_digest,
            poll_request_digest,
            poll_reply_digest,
            NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING,
        ),
    )


class ResearchLifecycleBridge:
    """Trusted worker bridge kept outside the driver-facing session."""

    __slots__ = ("_provider", "_service")

    def __init__(
        self, service: LocalResearchService, provider: InMemoryResearchTaskProvider
    ) -> None:
        if type(
            provider
        ) is not InMemoryResearchTaskProvider or not service.binds_research_task_provider(
            provider
        ):
            raise TypeError("research bridge requires exact B-07S/B-07B composition")
        self._service = service
        self._provider = provider

    def run_paired_practice(
        self,
        *,
        session: AgentSession,
        prepared: PreparedFixturePreflight,
    ) -> tuple[PracticeAttemptEvidence, ...]:
        if not session.binds_research_service(self._service):
            raise ValueError("research bridge is not bound to the run session")
        findings: list[PracticeAttemptEvidence] = []
        for candidate in prepared.candidates:
            if not candidate.executable:
                continue
            inspection = candidate.resource_inspection
            assert inspection is not None
            classes = {item.resource_class_ref for item in inspection.line_items}
            if len(classes) != 1:
                raise NonQualifyingLifecycleError(
                    LifecycleFailureKind.CANDIDATE, "practice_resource_class"
                )
            selector = (
                ExactPriorSelector(prepared.plan.identity.prior_pack_ref)
                if prepared.plan.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR
                else NoPriorSelector()
            )
            request = StartResearchTaskRequest(
                prepared.challenge_info.challenge_key,
                f"be4_{prepared.plan.final_submission_slot_digest[7:23]}_{candidate.proposal.attempt:02d}",
                PairedPracticeTaskSpec(
                    prepared.scaffold.strategy_template,
                    candidate.proposal.strategy,
                ),
                prepared.challenge_info.training_support_ref,
                selector,
                prepared.interaction_manifest.resource_policy_ref,
                next(iter(classes)),
                prepared.interaction_manifest.practice_scope_ref,
            )
            reply_digests: list[str] = []
            start_request_digest = canonical_digest(request)
            started = _research_result(
                session,
                "start_research_task",
                request,
                StartResearchTaskResult,
                reply_digests,
            )
            assert type(started) is StartResearchTaskResult
            start_reply_digest = reply_digests[-1]
            worker_view = self._provider.run_queued_task(started.task.task_id)
            poll_request = GetResearchResultRequest(
                prepared.challenge_info.challenge_key,
                started.task.task_id,
                0,
            )
            poll_request_digest = canonical_digest(poll_request)
            polled = _research_result(
                session,
                "get_research_result",
                poll_request,
                GetResearchResultResult,
                reply_digests,
            )
            assert type(polled) is GetResearchResultResult
            poll_reply_digest = reply_digests[-1]
            task = polled.task
            if task != worker_view or task.state is ResearchTaskState.FAILED_INFRA:
                raise NonQualifyingLifecycleError(
                    LifecycleFailureKind.INFRASTRUCTURE, "paired_practice"
                )
            if (
                task.state is not ResearchTaskState.SUCCEEDED
                or task.terminal_receipt is None
            ):
                raise NonQualifyingLifecycleError(
                    LifecycleFailureKind.INFRASTRUCTURE, "paired_practice_terminal"
                )
            record = self._provider.get_experiment_record(task.task_id)
            category = record.scientific_failure_category
            if category is ResearchFailureCategory.REFERENCE:
                raise NonQualifyingLifecycleError(
                    LifecycleFailureKind.REFERENCE, "paired_practice"
                )
            if category is ResearchFailureCategory.MEASUREMENT:
                raise NonQualifyingLifecycleError(
                    LifecycleFailureKind.MEASUREMENT, "paired_practice"
                )
            if category is not None:
                raise NonQualifyingLifecycleError(
                    LifecycleFailureKind.CANDIDATE, "paired_practice"
                )
            if len(task.terminal_receipt.public_findings) != 1:
                raise NonQualifyingLifecycleError(
                    LifecycleFailureKind.MEASUREMENT, "practice_disclosure"
                )
            public = task.terminal_receipt.public_findings[0]
            feedback = AllowedPracticeFeedback.from_public_range(
                attempt=candidate.proposal.attempt,
                proposal_digest=candidate.proposal.strategy_digest,
                observed_range=public.uncertainty_band,
            )
            content_digest = _practice_content_digest(
                proposal_digest=candidate.proposal.strategy_digest,
                public_finding=public,
                receipt=task.terminal_receipt,
                experiment_record=record,
                feedback=feedback,
                start_request_digest=start_request_digest,
                start_reply_digest=start_reply_digest,
                poll_request_digest=poll_request_digest,
                poll_reply_digest=poll_reply_digest,
            )
            findings.append(
                PracticeAttemptEvidence(
                    candidate.proposal.strategy_digest,
                    public,
                    task.terminal_receipt,
                    record,
                    feedback,
                    start_request_digest,
                    start_reply_digest,
                    poll_request_digest,
                    poll_reply_digest,
                    content_digest,
                    _PRACTICE_FACTORY_TOKEN,
                )
            )
        if not findings:
            raise NonQualifyingLifecycleError(
                LifecycleFailureKind.CANDIDATE, "no_practice_admissible_candidate"
            )
        return tuple(findings)


class OfficialLifecycleBridge:
    """Trusted A7/A8 worker bridge; fixture outcomes never reach the driver."""

    __slots__ = ("_adapter", "_facade", "_requester", "_service")

    def __init__(
        self,
        facade: McpService,
        service: SubmissionService,
        adapter: ResolvedPlanFixtureTrainEvalService,
        requester: RequesterIdentity,
    ) -> None:
        if (
            type(facade) is not McpService
            or type(service) is not SubmissionService
            or type(adapter) is not ResolvedPlanFixtureTrainEvalService
            or type(requester) is not RequesterIdentity
            or not facade.binds_submission_service(service)
        ):
            raise TypeError("official bridge requires exact A7/A8 composition")
        self._facade = facade
        self._service = service
        self._adapter = adapter
        self._requester = requester

    def complete(
        self,
        *,
        session: AgentSession,
        submission: OfficialFixtureSubmission,
    ) -> tuple[ResolvedFixtureCompletedRun, SubmissionResult]:
        if not session.binds_official_service(self._facade, self._requester):
            raise ValueError("official bridge is not bound to the run session")
        submission_id = submission.receipt.status.submission_id
        self._service.mark_validated(submission_id, self._requester)
        self._service.admit_fixture(submission_id, self._requester)
        started = self._service.start_fixture_attempt(
            submission_id,
            self._requester,
            FeeOperationKey(f"be4-charge-{submission_id.value}"),
            FeeOperationKey(f"be4-refund-{submission_id.value}"),
        )
        outcome = self._adapter.run_fixture(started.envelope)
        if type(outcome) is InfrastructureFailedRun:
            self._service.fail_infrastructure(outcome.handle)
            raise NonQualifyingLifecycleError(
                LifecycleFailureKind.INFRASTRUCTURE, "fixture_official"
            )
        if type(outcome) is FixtureReferenceFailed:
            self._service.fail_infrastructure(outcome.handle)
            raise NonQualifyingLifecycleError(
                LifecycleFailureKind.REFERENCE, "fixture_official"
            )
        if type(outcome) is FixtureMeasurementFailed:
            self._service.fail_infrastructure(outcome.handle)
            raise NonQualifyingLifecycleError(
                LifecycleFailureKind.MEASUREMENT, "fixture_official"
            )
        if type(outcome) in (
            FixtureCompilationFailed,
            FixtureConstructionFailed,
            FixtureResourceFailed,
        ):
            self._service.fail_strategy(outcome.handle)
            raise NonQualifyingLifecycleError(
                LifecycleFailureKind.CANDIDATE, "fixture_official"
            )
        if type(outcome) is not ResolvedFixtureCompletedRun:
            raise TypeError("fixture worker returned an unknown outcome")
        self._service.complete_and_publish(
            outcome.completed_run.handle, outcome.completed_run.internal_result
        )
        return outcome, read_official_fixture_result(
            session=session, submission=submission
        )


@dataclass(frozen=True, slots=True)
class NonQualifyingLifecycleRun:
    authority_ceiling: str
    population_scope: str
    plan: NonQualifyingRunPlan
    driver_artifact: ExecutableDriverArtifactRef
    treatment_artifact: LifecycleTreatmentArtifact
    prepared: PreparedFixturePreflight
    practice: tuple[PracticeAttemptEvidence, ...]
    selection: DriverSelection
    official_submission: OfficialFixtureSubmission
    official_outcome: ResolvedFixtureCompletedRun
    public_result: SubmissionResult
    heldout_mse: float
    transfer_mse: float
    heldout_quality_q: float
    transfer_quality_q: float
    normalized_compute: NormalizedComputeReceipt
    fixture_units: float
    wall_time: WallTimeObservation
    session_binding_digest: str
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not NonQualifyingLifecycleRun
            or self._factory_token is not _LIFECYCLE_FACTORY_TOKEN
            or self.authority_ceiling != NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING
            or self.population_scope != DETERMINISTIC_POPULATION_SCOPE
            or type(self.plan) is not NonQualifyingRunPlan
            or type(self.driver_artifact) is not ExecutableDriverArtifactRef
            or type(self.treatment_artifact) is not LifecycleTreatmentArtifact
            or type(self.prepared) is not PreparedFixturePreflight
            or type(self.practice) is not tuple
            or not self.practice
            or any(type(item) is not PracticeAttemptEvidence for item in self.practice)
            or type(self.selection) is not DriverSelection
            or type(self.official_submission) is not OfficialFixtureSubmission
            or type(self.official_outcome) is not ResolvedFixtureCompletedRun
            or type(self.public_result) is not SubmissionResult
            or type(self.normalized_compute) is not NormalizedComputeReceipt
            or type(self.wall_time) is not WallTimeObservation
        ):
            raise TypeError("lifecycle runs require the trusted non-qualifying factory")
        for item, name in (
            (self.session_binding_digest, "session_binding_digest"),
            (self.content_digest, "content_digest"),
        ):
            if (
                type(item) is not str
                or not item.startswith("sha256:")
                or len(item) != 71
            ):
                raise TypeError(f"{name} is invalid")
        endpoint = self.official_outcome.endpoint_observation_receipt
        if (
            self.plan != self.prepared.plan
            or self.plan.identity.arm is not self.treatment_artifact.arm
            or self.plan.driver_ref != self.driver_artifact.driver_ref
            or self.selection.driver_ref != self.plan.driver_ref
            or self.selection.selected_proposal_digest
            != self.official_submission.proposal_digest
            or self.official_submission.plan_slot_digest
            != self.plan.final_submission_slot_digest
            or self.heldout_mse != endpoint.heldout_mean_squared_error
            or self.transfer_mse != endpoint.transfer_mean_squared_error
            or self.heldout_quality_q != fixture_primary_quality(self.heldout_mse)
            or self.transfer_quality_q != fixture_transfer_quality(self.transfer_mse)
            or self.normalized_compute.total_work_units
            > int(self.plan.budget.compute_units)
            or self.fixture_units > self.plan.fixture_resource_ceiling
        ):
            raise ValueError("lifecycle run owner correlations changed")
        expected = _lifecycle_content_digest(
            plan=self.plan,
            driver_artifact=self.driver_artifact,
            treatment_artifact=self.treatment_artifact,
            prepared=self.prepared,
            practice=self.practice,
            selection=self.selection,
            submission=self.official_submission,
            outcome=self.official_outcome,
            public_result=self.public_result,
            compute=self.normalized_compute,
            fixture_units=self.fixture_units,
            session_binding_digest=self.session_binding_digest,
        )
        if self.content_digest != expected:
            raise ValueError("lifecycle digest does not bind the recorded execution")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def _lifecycle_content_digest(
    *,
    plan: NonQualifyingRunPlan,
    driver_artifact: ExecutableDriverArtifactRef,
    treatment_artifact: LifecycleTreatmentArtifact,
    prepared: PreparedFixturePreflight,
    practice: tuple[PracticeAttemptEvidence, ...],
    selection: DriverSelection,
    submission: OfficialFixtureSubmission,
    outcome: ResolvedFixtureCompletedRun,
    public_result: SubmissionResult,
    compute: NormalizedComputeReceipt,
    fixture_units: float,
    session_binding_digest: str,
) -> str:
    return _sha(
        _LIFECYCLE_DOMAIN,
        (
            plan.final_submission_slot_digest,
            driver_artifact.content_digest,
            treatment_artifact.content_digest,
            prepared.transcript_digest,
            *(item.content_digest for item in practice),
            selection.content_digest,
            submission.association_digest,
            outcome.reconstruction_receipt.receipt_ref,
            outcome.result_receipt.receipt_ref,
            outcome.endpoint_observation_receipt.receipt_ref,
            _public_result_digest(public_result),
            compute.content_digest,
            fixture_units.hex(),
            session_binding_digest,
            NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING,
        ),
    )


def _public_result_digest(result: SubmissionResult) -> str:
    if type(result) is not SubmissionResult or result.card is None:
        raise TypeError("lifecycle evidence requires an exact published result")
    card = result.card
    components = card.component_scores
    component_fields = (
        ("NO_COMPONENTS",)
        if components is None
        else (
            components.physics.hex(),
            components.robustness.hex(),
            components.accuracy.hex(),
        )
    )
    return _sha(
        b"carbon.be4.public-result-correlation.v1\x00",
        (
            result.schema_version,
            result.status.submission_id.value,
            result.status.state.value,
            card.schema_version,
            card.result_id,
            card.status,
            card.scoring_pack_hash,
            "NO_OVERALL" if card.overall_score is None else card.overall_score.hex(),
            *component_fields,
            *(f"GATE:{item.gate_id}:{int(item.passed)}" for item in card.gate_results),
            *(f"FAILURE:{item}" for item in card.failure_tags),
            f"FIXTURE:{int(card.fixture_origin)}",
            f"EMISSION:{int(card.eligible_for_emission)}",
            card.disclosure_tier,
        ),
    )


def run_nonqualifying_lifecycle(
    *,
    session: AgentSession,
    plan: NonQualifyingRunPlan,
    driver: FixtureAgentDriver,
    projection: PrivatePriorProjection,
    strategy_domain,
    parameter_catalog,
    candidate_assembly,
    meter: PolicyWorkMeter,
    research_bridge: ResearchLifecycleBridge,
    official_bridge: OfficialLifecycleBridge,
) -> NonQualifyingLifecycleRun:
    """Execute one full fixture rehearsal with no qualification authority."""

    started_ns = time.monotonic_ns()
    prepared = prepare_nonqualifying_preflight(
        session=session,
        plan=plan,
        driver=driver,
        strategy_domain=strategy_domain,
        parameter_catalog=parameter_catalog,
        candidate_assembly=candidate_assembly,
        meter=meter,
    )
    practice = research_bridge.run_paired_practice(session=session, prepared=prepared)
    if (
        time.monotonic_ns() - started_ns
    ) / 1_000_000_000 > plan.budget.wall_time_seconds:
        raise NonQualifyingLifecycleError(
            LifecycleFailureKind.INFRASTRUCTURE, "wall_budget_before_selection"
        )
    rng = CommonArmRng(
        plan.design_digest,
        plan.identity.profile,
        plan.block_id,
        plan.identity.replicate,
    )
    selection = driver.select_after_practice(
        proposal_batch=prepared.proposal_batch,
        feedback=tuple(item.feedback for item in practice),
        rng=rng,
        meter=meter,
    )
    selected = next(
        item
        for item in prepared.candidates
        if item.proposal.attempt == selection.selected_attempt
    )
    assert selected.resource_inspection is not None
    practice_units = sum(
        observation.quantity
        for item in practice
        for observation in item.experiment_record.resource_observations
    )
    final_units = sum(item.quantity for item in selected.resource_inspection.line_items)
    fixture_units = float(practice_units + final_units)
    if fixture_units > plan.fixture_resource_ceiling:
        raise NonQualifyingLifecycleError(
            LifecycleFailureKind.INFRASTRUCTURE, "fixture_resource_budget"
        )
    submission = submit_selected_prepared_fixture_run(
        session=session, prepared=prepared, selection=selection
    )
    outcome, public_result = official_bridge.complete(
        session=session, submission=submission
    )
    elapsed = (time.monotonic_ns() - started_ns) / 1_000_000_000
    if elapsed > plan.budget.wall_time_seconds:
        raise NonQualifyingLifecycleError(
            LifecycleFailureKind.INFRASTRUCTURE, "wall_budget_after_endpoint"
        )
    compute = meter.snapshot()
    if compute.total_work_units > int(plan.budget.compute_units):
        raise NonQualifyingLifecycleError(
            LifecycleFailureKind.INFRASTRUCTURE, "normalized_compute_budget"
        )
    endpoint = outcome.endpoint_observation_receipt
    driver_artifact = executable_driver_artifact(driver)
    treatment_artifact = lifecycle_treatment_artifact(plan, projection)
    session_binding_digest = session.correlation_digest(
        plan.final_submission_slot_digest
    )
    content_digest = _lifecycle_content_digest(
        plan=plan,
        driver_artifact=driver_artifact,
        treatment_artifact=treatment_artifact,
        prepared=prepared,
        practice=practice,
        selection=selection,
        submission=submission,
        outcome=outcome,
        public_result=public_result,
        compute=compute,
        fixture_units=fixture_units,
        session_binding_digest=session_binding_digest,
    )
    return NonQualifyingLifecycleRun(
        NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING,
        DETERMINISTIC_POPULATION_SCOPE,
        plan,
        driver_artifact,
        treatment_artifact,
        prepared,
        practice,
        selection,
        submission,
        outcome,
        public_result,
        endpoint.heldout_mean_squared_error,
        endpoint.transfer_mean_squared_error,
        fixture_primary_quality(endpoint.heldout_mean_squared_error),
        fixture_transfer_quality(endpoint.transfer_mean_squared_error),
        compute,
        fixture_units,
        WallTimeObservation(float(elapsed)),
        session_binding_digest,
        content_digest,
        _LIFECYCLE_FACTORY_TOKEN,
    )


__all__ = (
    "DETERMINISTIC_POPULATION_SCOPE",
    "NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING",
    "ExecutableDriverArtifactRef",
    "LifecycleFailureKind",
    "LifecycleTreatmentArtifact",
    "NonQualifyingLifecycleError",
    "NonQualifyingLifecycleRun",
    "OfficialLifecycleBridge",
    "PracticeAttemptEvidence",
    "ResearchLifecycleBridge",
    "executable_driver_artifact",
    "lifecycle_treatment_artifact",
    "run_nonqualifying_lifecycle",
)

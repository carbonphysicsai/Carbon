"""Private B-07B research execution and evidence records.

These values are deliberately absent from the v2 wire registry.  Only the
bounded ``ResearchReceipt`` projection in :mod:`carbon.research.lifecycle` is
miner-visible.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from carbon.authoring.model import EvidenceRole
from carbon.authoring.primitives import validate_canonical_id, validate_tagged_sha256
from carbon.authoring.refs import SamplingPlanRef, TrainingSupportContractRef
from carbon.construction.canonical import encode_model
from carbon.construction.plan import ResolvedConstructionPlan
from carbon.construction.policy import ResolvedTrainingSamplingPolicy
from carbon.construction.refs import (
    ResolvedConstructionPlanRef,
    TrainingSamplingPolicyRef,
)
from carbon.fees import StrategyHash
from carbon.measurement.refs import MeasurementContractRef
from carbon.registry import ChallengeKey
from carbon.resource_policy.refs import ObservedResourceReceiptRef

from .model import (
    EpistemicType,
    InfrastructureFailureClass,
    ResearchTaskBindings,
)
from .refs import PriorIndexSnapshotRef, PriorPackRef, ResearchTaskId


class ResearchEvidenceClass(str, Enum):
    """Closed, non-official evidence ceiling for local Wave B research."""

    STRUCTURAL_ONLY = "STRUCTURAL_ONLY"
    STATIC_EXACT = "STATIC_EXACT"
    CALIBRATED_RESOURCE_FORECAST = "CALIBRATED_RESOURCE_FORECAST"
    PRACTICE_NON_AUTHORITATIVE = "PRACTICE_NON_AUTHORITATIVE"
    MMS_VERIFICATION = "MMS_VERIFICATION"
    REFERENCE_ASSESSMENT = "REFERENCE_ASSESSMENT"
    GENERATOR_CONFORMANCE = "GENERATOR_CONFORMANCE"
    HYBRID_COMPONENT = "HYBRID_COMPONENT"
    PRODUCT_BATTERY = "PRODUCT_BATTERY"


class ResearchFailureCategory(str, Enum):
    STRATEGY = "STRATEGY"
    RECONSTRUCTION = "RECONSTRUCTION"
    GENERATOR = "GENERATOR"
    REFERENCE = "REFERENCE"
    MEASUREMENT = "MEASUREMENT"
    SCIENTIFIC_ADMISSIBILITY = "SCIENTIFIC_ADMISSIBILITY"


class ResearchCensoringStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCENSORED = "UNCENSORED"
    CENSORED = "CENSORED"
    UNRESOLVED = "UNRESOLVED"


class ResearchRetentionScope(str, Enum):
    LOCAL_PRIVATE_ONLY = "LOCAL_PRIVATE_ONLY"
    LEARNED_AGGREGATION_AUTHORIZED = "LEARNED_AGGREGATION_AUTHORIZED"


@dataclass(frozen=True, slots=True)
class PrivateIdentityRef:
    """Typed private identity carrier; never a wire or receipt reference."""

    ref_type: str
    content_digest: str

    def __post_init__(self) -> None:
        if type(self) is not PrivateIdentityRef:
            raise TypeError("private identity subclasses are rejected")
        validate_canonical_id(self.ref_type, "ref_type")
        validate_tagged_sha256(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True)
class RetentionReuseBinding:
    scope: ResearchRetentionScope
    rights_authorization_ref: PrivateIdentityRef | None = None

    def __post_init__(self) -> None:
        if type(self) is not RetentionReuseBinding:
            raise TypeError("retention binding subclasses are rejected")
        if type(self.scope) is not ResearchRetentionScope:
            raise TypeError("scope must use its exact enum")
        if self.scope is ResearchRetentionScope.LEARNED_AGGREGATION_AUTHORIZED:
            if type(self.rights_authorization_ref) is not PrivateIdentityRef:
                raise ValueError(
                    "learned aggregation requires explicit rights authority"
                )
            if self.rights_authorization_ref.ref_type != "rights_authorization":
                raise ValueError(
                    "reuse requires an exact rights authorization identity"
                )
        elif self.rights_authorization_ref is not None:
            raise ValueError("local-only retention cannot imply reuse authority")


@dataclass(frozen=True, slots=True)
class EvidenceQualityMetadata:
    """Descriptive metadata only; no quality interpretation is inferred."""

    provenance_complete: bool | None = None
    reproducibility_assessed: bool | None = None
    execution_validity_assessed: bool | None = None

    def __post_init__(self) -> None:
        if type(self) is not EvidenceQualityMetadata:
            raise TypeError("evidence quality subclasses are rejected")
        for value in (
            self.provenance_complete,
            self.reproducibility_assessed,
            self.execution_validity_assessed,
        ):
            if value is not None and type(value) is not bool:
                raise TypeError("evidence quality metadata must be bool or absent")


@dataclass(frozen=True, slots=True)
class EvidenceContext:
    evidence_role: EvidenceRole
    evidence_origin_ref: PrivateIdentityRef
    reference_policy_ref: PrivateIdentityRef | None
    applicability_ref: PrivateIdentityRef | None
    uncertainty_ref: PrivateIdentityRef | None
    limitation_refs: tuple[PrivateIdentityRef, ...]
    population_ref: PrivateIdentityRef | None
    verification_campaign_ref: PrivateIdentityRef | None
    censoring_status: ResearchCensoringStatus
    evidence_quality: EvidenceQualityMetadata
    evidence_quality_authorization_ref: PrivateIdentityRef | None = None
    epistemic_status: EpistemicType | None = None

    def __post_init__(self) -> None:
        if type(self) is not EvidenceContext:
            raise TypeError("evidence context subclasses are rejected")
        if type(self.evidence_role) is not EvidenceRole:
            raise TypeError("evidence_role must use the authoring enum")
        if type(self.evidence_origin_ref) is not PrivateIdentityRef:
            raise TypeError("evidence origin requires a private identity ref")
        for name in (
            "reference_policy_ref",
            "applicability_ref",
            "uncertainty_ref",
            "population_ref",
            "verification_campaign_ref",
        ):
            item = getattr(self, name)
            if item is not None and type(item) is not PrivateIdentityRef:
                raise TypeError(f"{name} must use a private identity ref")
        if type(self.limitation_refs) is not tuple or any(
            type(item) is not PrivateIdentityRef for item in self.limitation_refs
        ):
            raise TypeError("limitation_refs must be an exact tuple of private refs")
        if len(self.limitation_refs) > 64:
            raise ValueError("limitation refs exceed the private record bound")
        if type(self.censoring_status) is not ResearchCensoringStatus:
            raise TypeError("censoring_status must use its exact enum")
        if type(self.evidence_quality) is not EvidenceQualityMetadata:
            raise TypeError("evidence_quality must use its exact record")
        has_quality_assessment = any(
            value is not None
            for value in (
                self.evidence_quality.provenance_complete,
                self.evidence_quality.reproducibility_assessed,
                self.evidence_quality.execution_validity_assessed,
            )
        )
        if has_quality_assessment:
            if (
                type(self.evidence_quality_authorization_ref) is not PrivateIdentityRef
                or self.evidence_quality_authorization_ref.ref_type
                != "evidence_quality_authorization"
            ):
                raise ValueError(
                    "evidence-quality assessment requires explicit science authority"
                )
        elif self.evidence_quality_authorization_ref is not None:
            raise ValueError(
                "evidence-quality authority cannot imply an absent assessment"
            )
        if (
            self.epistemic_status is not None
            and type(self.epistemic_status) is not EpistemicType
        ):
            raise TypeError("epistemic_status must use its exact enum")
        if self.evidence_role is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION and (
            self.verification_campaign_ref is None or self.population_ref is not None
        ):
            raise ValueError(
                "manufactured-solution evidence requires a verification campaign "
                "and cannot claim a target population"
            )
        if (
            self.evidence_role is not EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
            and self.verification_campaign_ref is not None
        ):
            raise ValueError(
                "only manufactured-solution evidence uses a verification campaign"
            )


@dataclass(frozen=True, slots=True)
class ResourceObservation:
    dimension_id: str
    quantity: float
    unit: str

    def __post_init__(self) -> None:
        if type(self) is not ResourceObservation:
            raise TypeError("resource observation subclasses are rejected")
        validate_canonical_id(self.dimension_id, "dimension_id")
        validate_canonical_id(self.unit, "unit")
        if (
            type(self.quantity) is not float
            or not math.isfinite(self.quantity)
            or self.quantity < 0.0
        ):
            raise ValueError("resource quantity must be a non-negative float")


@dataclass(frozen=True, slots=True)
class ResolvedPlanDifference:
    surface_id: str
    baseline_surface_digest: str
    intervention_surface_digest: str

    def __post_init__(self) -> None:
        if type(self) is not ResolvedPlanDifference:
            raise TypeError("plan difference subclasses are rejected")
        validate_canonical_id(self.surface_id, "surface_id")
        validate_tagged_sha256(self.baseline_surface_digest, "baseline_surface_digest")
        validate_tagged_sha256(
            self.intervention_surface_digest, "intervention_surface_digest"
        )
        if self.baseline_surface_digest == self.intervention_surface_digest:
            raise ValueError("plan difference must bind different surface values")


def resolved_plan_difference(
    baseline: ResolvedConstructionPlan,
    intervention: ResolvedConstructionPlan,
) -> ResolvedPlanDifference:
    """Compute the one direct intervention from authoritative resolved surfaces."""

    if (
        type(baseline) is not ResolvedConstructionPlan
        or type(intervention) is not ResolvedConstructionPlan
    ):
        raise TypeError("plan comparison requires exact resolved plans")
    if baseline.challenge_key != intervention.challenge_key:
        raise ValueError("resolved plans have different Challenge identities")
    left = {surface.surface_id: surface for surface in baseline.resolved_surfaces}
    right = {surface.surface_id: surface for surface in intervention.resolved_surfaces}
    if left.keys() != right.keys():
        raise ValueError("resolved plans expose different surface sets")
    changed = tuple(
        surface_id
        for surface_id in sorted(left)
        if left[surface_id] != right[surface_id]
    )
    if len(changed) != 1:
        raise ValueError("paired research requires exactly one resolved-surface change")
    surface_id = changed[0]

    def digest(value: object) -> str:
        return "sha256:" + hashlib.sha256(encode_model(value)).hexdigest()

    return ResolvedPlanDifference(
        surface_id=surface_id,
        baseline_surface_digest=digest(left[surface_id]),
        intervention_surface_digest=digest(right[surface_id]),
    )


@dataclass(frozen=True, slots=True)
class ResolvedStrategy:
    strategy_hash: StrategyHash
    training_sampling_policy_ref: TrainingSamplingPolicyRef
    resolved_plan_ref: ResolvedConstructionPlanRef
    resolved_plan: ResolvedConstructionPlan
    training_sampling_policy: ResolvedTrainingSamplingPolicy

    def __post_init__(self) -> None:
        if type(self) is not ResolvedStrategy:
            raise TypeError("resolved strategy subclasses are rejected")
        if type(self.strategy_hash) is not StrategyHash:
            raise TypeError("strategy_hash must use its exact nominal type")
        if type(self.training_sampling_policy_ref) is not TrainingSamplingPolicyRef:
            raise TypeError("training policy ref must use its exact nominal type")
        if type(self.resolved_plan_ref) is not ResolvedConstructionPlanRef:
            raise TypeError("resolved plan ref must use its exact nominal type")
        if type(self.resolved_plan) is not ResolvedConstructionPlan:
            raise TypeError("resolved plan must use its exact nominal type")
        if type(self.training_sampling_policy) is not ResolvedTrainingSamplingPolicy:
            raise TypeError("training policy must use its exact nominal type")
        if (
            self.resolved_plan.strategy_hash != self.strategy_hash
            or self.resolved_plan.training_sampling_policy_ref
            != self.training_sampling_policy_ref
            or self.resolved_plan.to_ref() != self.resolved_plan_ref
            or self.training_sampling_policy.to_ref()
            != self.training_sampling_policy_ref
            or self.training_sampling_policy.challenge_key
            != self.resolved_plan.challenge_key
            or self.training_sampling_policy.training_support_ref
            != self.resolved_plan.training_support_ref
        ):
            raise ValueError("resolved strategy identities disagree")


@dataclass(frozen=True, slots=True)
class PriorResolution:
    index_snapshot_ref: PriorIndexSnapshotRef | None
    prior_pack_ref: PriorPackRef | None

    def __post_init__(self) -> None:
        if type(self) is not PriorResolution:
            raise TypeError("prior resolution subclasses are rejected")
        if (self.index_snapshot_ref is None) != (self.prior_pack_ref is None):
            raise ValueError("prior index and pack refs must be present together")
        if self.index_snapshot_ref is not None:
            if (
                type(self.index_snapshot_ref) is not PriorIndexSnapshotRef
                or type(self.prior_pack_ref) is not PriorPackRef
            ):
                raise TypeError("prior resolution requires exact nominal refs")
            if (
                self.index_snapshot_ref.challenge_key
                != self.prior_pack_ref.challenge_key
                or self.index_snapshot_ref.channel is not self.prior_pack_ref.channel
            ):
                raise ValueError("prior snapshot and pack identities disagree")


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    worker_implementation_digest: str
    environment_digest: str
    attempts: int

    def __post_init__(self) -> None:
        if type(self) is not ExecutionIdentity:
            raise TypeError("execution identity subclasses are rejected")
        validate_tagged_sha256(
            self.worker_implementation_digest, "worker_implementation_digest"
        )
        validate_tagged_sha256(self.environment_digest, "environment_digest")
        if type(self.attempts) is not int or not 1 <= self.attempts <= 3:
            raise ValueError("attempts must be inside the provider retry cap")


@dataclass(frozen=True, slots=True)
class AuthorizedResearchOutcome:
    evidence_class: ResearchEvidenceClass
    evidence_context: EvidenceContext
    retention: RetentionReuseBinding
    finding_ids: tuple[str, ...]
    aggregate_outcome_refs: tuple[PrivateIdentityRef, ...]
    observed_resource_receipt_ref: ObservedResourceReceiptRef | None
    resource_observations: tuple[ResourceObservation, ...]
    scientific_failure_category: ResearchFailureCategory | None = None
    finding_measurements: tuple[FindingMeasurement, ...] = ()

    def __post_init__(self) -> None:
        if type(self) is not AuthorizedResearchOutcome:
            raise TypeError("research outcome subclasses are rejected")
        if type(self.evidence_class) is not ResearchEvidenceClass:
            raise TypeError("evidence_class must use its exact non-official enum")
        if type(self.evidence_context) is not EvidenceContext:
            raise TypeError("evidence_context must use its exact record")
        if type(self.retention) is not RetentionReuseBinding:
            raise TypeError("retention must use its exact binding")
        if type(self.finding_ids) is not tuple or len(self.finding_ids) > 256:
            raise ValueError("finding_ids exceed the private record bound")
        for item in self.finding_ids:
            validate_canonical_id(item, "finding_id")
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("finding_ids must be unique")
        if type(self.aggregate_outcome_refs) is not tuple or any(
            type(item) is not PrivateIdentityRef for item in self.aggregate_outcome_refs
        ):
            raise TypeError("aggregate outcome refs must use private identities")
        if type(self.resource_observations) is not tuple or any(
            type(item) is not ResourceObservation for item in self.resource_observations
        ):
            raise TypeError("resource observations must use exact records")
        if (
            self.observed_resource_receipt_ref is not None
            and type(self.observed_resource_receipt_ref)
            is not ObservedResourceReceiptRef
        ):
            raise TypeError("resource receipt must use its exact nominal ref")
        if (
            self.scientific_failure_category is not None
            and type(self.scientific_failure_category) is not ResearchFailureCategory
        ):
            raise TypeError("scientific failure must use its exact enum")
        if type(self.finding_measurements) is not tuple or any(
            type(item) is not FindingMeasurement for item in self.finding_measurements
        ):
            raise TypeError("finding measurements must use exact private records")
        measured_ids = tuple(item.finding_id for item in self.finding_measurements)
        if len(measured_ids) != len(set(measured_ids)) or set(measured_ids) & set(
            self.finding_ids
        ):
            raise ValueError("finding projections must be unique")
        if (
            self.evidence_context.evidence_role
            is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
        ) != (self.evidence_class is ResearchEvidenceClass.MMS_VERIFICATION):
            raise ValueError(
                "manufactured-solution results remain verification evidence"
            )


@dataclass(frozen=True, slots=True)
class InfrastructureExecutionFailure:
    failure_class: InfrastructureFailureClass
    retryable: bool
    observed_resource_receipt_ref: ObservedResourceReceiptRef | None = None

    def __post_init__(self) -> None:
        if type(self) is not InfrastructureExecutionFailure:
            raise TypeError("infrastructure failure subclasses are rejected")
        if type(self.failure_class) is not InfrastructureFailureClass:
            raise TypeError("failure_class must use its exact enum")
        if type(self.retryable) is not bool:
            raise TypeError("retryable must be exact bool")
        if (
            self.observed_resource_receipt_ref is not None
            and type(self.observed_resource_receipt_ref)
            is not ObservedResourceReceiptRef
        ):
            raise TypeError("resource receipt must use its exact nominal ref")


ExecutionOutcome = AuthorizedResearchOutcome | InfrastructureExecutionFailure


@dataclass(frozen=True, slots=True)
class FindingMeasurement:
    """Numeric-only input to a provider-owned registered finding projection."""

    finding_id: str
    uncertainty_band: tuple[float, ...]

    def __post_init__(self) -> None:
        if type(self) is not FindingMeasurement:
            raise TypeError("finding measurement subclasses are rejected")
        validate_canonical_id(self.finding_id, "finding_id")
        if (
            type(self.uncertainty_band) is not tuple
            or len(self.uncertainty_band) != 2
            or any(
                type(item) is not float or not math.isfinite(item)
                for item in self.uncertainty_band
            )
            or self.uncertainty_band[0] > self.uncertainty_band[1]
        ):
            raise ValueError("finding uncertainty must be one finite ordered band")


@dataclass(frozen=True, slots=True)
class ResearchExecutionAttempt:
    task_id: ResearchTaskId
    attempt: int
    task_bindings: ResearchTaskBindings
    challenge_key: ChallengeKey
    training_support_ref: TrainingSupportContractRef
    sampling_plan_ref: SamplingPlanRef
    measurement_contract_ref: MeasurementContractRef
    resolved_strategies: tuple[ResolvedStrategy, ...]
    parent_strategy_hashes: tuple[StrategyHash | None, ...]
    prior_resolution: PriorResolution

    def __post_init__(self) -> None:
        if type(self) is not ResearchExecutionAttempt:
            raise TypeError("execution attempt subclasses are rejected")
        if type(self.task_bindings) is not ResearchTaskBindings:
            raise TypeError("task_bindings must use the exact wire record")
        if self.task_bindings.challenge_info_ref.challenge_key != self.challenge_key:
            raise ValueError("execution bindings conflict with the attempt Challenge")
        if type(self.attempt) is not int or not 1 <= self.attempt <= 3:
            raise ValueError("execution attempt is outside the provider retry cap")
        if len(self.resolved_strategies) != len(self.task_bindings.strategy_bindings):
            raise ValueError("execution bindings and resolved strategies disagree")
        for resolved, binding in zip(
            self.resolved_strategies, self.task_bindings.strategy_bindings, strict=True
        ):
            if (
                resolved.strategy_hash != binding.strategy_hash
                or resolved.training_sampling_policy_ref
                != binding.training_sampling_policy_ref
                or resolved.resolved_plan_ref != binding.resolved_plan_ref
            ):
                raise ValueError("execution strategy binding mismatch")


class ResearchExecutor(Protocol):
    def execute(self, attempt: ResearchExecutionAttempt) -> ExecutionOutcome: ...


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    """Immutable private record for one scientifically attributable execution."""

    task_id: ResearchTaskId
    challenge_key: ChallengeKey
    task_bindings: ResearchTaskBindings
    training_support_ref: TrainingSupportContractRef
    sampling_plan_ref: SamplingPlanRef
    measurement_contract_ref: MeasurementContractRef
    resolved_strategies: tuple[ResolvedStrategy, ...]
    parent_strategy_hashes: tuple[StrategyHash | None, ...]
    prior_resolution: PriorResolution
    plan_difference: ResolvedPlanDifference | None
    evidence_class: ResearchEvidenceClass
    evidence_context: EvidenceContext
    execution_identity: ExecutionIdentity
    scientific_failure_category: ResearchFailureCategory | None
    resource_observations: tuple[ResourceObservation, ...]
    observed_resource_receipt_ref: ObservedResourceReceiptRef | None
    aggregate_outcome_refs: tuple[PrivateIdentityRef, ...]
    retention: RetentionReuseBinding
    completed_at_micros: int

    def __post_init__(self) -> None:
        if type(self) is not ExperimentRecord:
            raise TypeError("experiment record subclasses are rejected")
        if type(self.task_id) is not ResearchTaskId:
            raise TypeError("task_id must use its exact nominal type")
        if type(self.challenge_key) is not ChallengeKey:
            raise TypeError("challenge_key must use its exact nominal type")
        if (
            type(self.task_bindings) is not ResearchTaskBindings
            or self.task_bindings.challenge_info_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("task bindings must exactly bind the record Challenge")
        for value, expected, label in (
            (
                self.training_support_ref,
                TrainingSupportContractRef,
                "training_support_ref",
            ),
            (self.sampling_plan_ref, SamplingPlanRef, "sampling_plan_ref"),
            (
                self.measurement_contract_ref,
                MeasurementContractRef,
                "measurement_contract_ref",
            ),
        ):
            if type(value) is not expected or value.challenge_key != self.challenge_key:
                raise ValueError(f"{label} must exactly bind the record Challenge")
        if (
            type(self.resolved_strategies) is not tuple
            or not 1 <= len(self.resolved_strategies) <= 2
            or any(
                type(item) is not ResolvedStrategy for item in self.resolved_strategies
            )
        ):
            raise TypeError("resolved_strategies must contain one or two exact records")
        if any(
            item.resolved_plan.challenge_key != self.challenge_key
            or item.resolved_plan.training_support_ref != self.training_support_ref
            for item in self.resolved_strategies
        ):
            raise ValueError("resolved strategies conflict with record contract pins")
        if type(self.prior_resolution) is not PriorResolution:
            raise TypeError("prior_resolution must use its exact record")
        if self.prior_resolution.prior_pack_ref is not None and (
            self.prior_resolution.prior_pack_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("prior resolution conflicts with the record Challenge")
        if type(self.evidence_class) is not ResearchEvidenceClass:
            raise TypeError("evidence_class must use its exact enum")
        if type(self.evidence_context) is not EvidenceContext:
            raise TypeError("evidence_context must use its exact record")
        if type(self.execution_identity) is not ExecutionIdentity:
            raise TypeError("execution_identity must use its exact record")
        if (
            self.scientific_failure_category is not None
            and type(self.scientific_failure_category) is not ResearchFailureCategory
        ):
            raise TypeError("scientific failure must use its exact enum")
        if type(self.resource_observations) is not tuple or any(
            type(item) is not ResourceObservation for item in self.resource_observations
        ):
            raise TypeError("resource observations must use exact records")
        if self.observed_resource_receipt_ref is not None and (
            type(self.observed_resource_receipt_ref) is not ObservedResourceReceiptRef
            or self.observed_resource_receipt_ref.challenge_key != self.challenge_key
        ):
            raise ValueError("resource receipt must exactly bind the record Challenge")
        if type(self.aggregate_outcome_refs) is not tuple or any(
            type(item) is not PrivateIdentityRef for item in self.aggregate_outcome_refs
        ):
            raise TypeError("aggregate outcomes must use private identities")
        if type(self.retention) is not RetentionReuseBinding:
            raise TypeError("retention must use its exact binding")
        if (
            type(self.completed_at_micros) is not int
            or not -(1 << 63) <= self.completed_at_micros <= (1 << 63) - 1
        ):
            raise TypeError("completion time must be an exact int64")
        if self.evidence_context.epistemic_status is not None:
            raise ValueError(
                "Wave B local research has no authority to assign epistemic status"
            )
        if len(self.parent_strategy_hashes) != len(self.resolved_strategies) or any(
            item is not None and type(item) is not StrategyHash
            for item in self.parent_strategy_hashes
        ):
            raise ValueError(
                "parent strategy lineage must align with resolved strategies"
            )
        if len(self.resolved_strategies) == 2:
            expected = resolved_plan_difference(
                self.resolved_strategies[0].resolved_plan,
                self.resolved_strategies[1].resolved_plan,
            )
            if self.plan_difference != expected:
                raise ValueError("paired record plan difference is not authoritative")
        elif self.plan_difference is not None:
            raise ValueError("single-strategy record cannot carry a plan difference")


__all__ = (
    "AuthorizedResearchOutcome",
    "EvidenceContext",
    "EvidenceQualityMetadata",
    "ExecutionIdentity",
    "ExperimentRecord",
    "FindingMeasurement",
    "InfrastructureExecutionFailure",
    "PriorResolution",
    "PrivateIdentityRef",
    "ResearchCensoringStatus",
    "ResearchEvidenceClass",
    "ResearchExecutionAttempt",
    "ResearchExecutor",
    "ResearchFailureCategory",
    "ResearchRetentionScope",
    "ResolvedPlanDifference",
    "ResolvedStrategy",
    "ResourceObservation",
    "RetentionReuseBinding",
    "resolved_plan_difference",
)

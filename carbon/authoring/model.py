"""Closed, immutable value vocabulary for scientific authoring contracts.

This module deliberately contains no scientific defaults.  It provides the
small exact records and closed vocabularies shared by the six B-02A identity
objects.  Owner references are nominal values created by :mod:`.refs`; a
constructor always checks their exact registered kind instead of trusting a
caller supplied label.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from carbon.registry.model import ChallengeKey

from .primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_finite_float64,
    validate_positive_uint64,
    validate_version_token,
)
from .refs import require_owner_ref

T = TypeVar("T")


def exact(value: object, expected: type[T], field: str) -> T:
    if type(value) is not expected:
        raise TypeError(f"{field} must be exact {expected.__name__}")
    return value


def exact_enum(value: object, expected: type[T], field: str) -> T:
    return exact(value, expected, field)


def exact_tuple(
    value: object,
    item_type: type[T] | tuple[type[object], ...],
    field: str,
    *,
    nonempty: bool = False,
    unique: bool = False,
) -> tuple[T, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field} must be an exact tuple")
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise ValueError(f"{field} exceeds the canonical tuple bound")
    if nonempty and not value:
        raise ValueError(f"{field} must not be empty")
    copied: list[T] = []
    for item in value:
        if type(item) not in (item_type if type(item_type) is tuple else (item_type,)):
            raise TypeError(f"{field} contains a wrong exact type")
        copied.append(item)
    result = tuple(copied)
    if unique and len(set(result)) != len(result):
        raise ValueError(f"{field} contains a duplicate")
    return result


def owner(value: object, kind: str, field: str) -> object:
    try:
        return require_owner_ref(value, kind)
    except (TypeError, ValueError) as exc:
        error_type = TypeError if isinstance(exc, TypeError) else ValueError
        raise error_type(f"{field}: {exc}") from None


def owner_tuple(
    value: object,
    kind: str,
    field: str,
    *,
    nonempty: bool = False,
) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field} must be an exact tuple")
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise ValueError(f"{field} exceeds the canonical tuple bound")
    if nonempty and not value:
        raise ValueError(f"{field} must not be empty")
    copied = tuple(owner(item, kind, field) for item in value)
    if len(set(copied)) != len(copied):
        raise ValueError(f"{field} contains a duplicate")
    from .canonical import encode_value, owner_ref_to_canonical

    return tuple(
        sorted(copied, key=lambda item: encode_value(owner_ref_to_canonical(item)))
    )


def owner_sequence(
    value: object,
    kind: str,
    field: str,
    *,
    nonempty: bool = False,
) -> tuple[object, ...]:
    """Validate a normative ordered sequence of exact owner refs."""

    if type(value) is not tuple:
        raise TypeError(f"{field} must be an exact tuple")
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise ValueError(f"{field} exceeds the canonical tuple bound")
    if nonempty and not value:
        raise ValueError(f"{field} must not be empty")
    copied = tuple(owner(item, kind, field) for item in value)
    if len(set(copied)) != len(copied):
        raise ValueError(f"{field} contains a duplicate")
    return copied


def canonical_set_tuple(value: tuple[T, ...]) -> tuple[T, ...]:
    """Sort a validated set-like tuple by complete schema-local bytes."""

    from .canonical import encode_value

    return tuple(sorted(value, key=lambda item: encode_value(_canonical_value(item))))


def canonical_ids(
    value: object, field: str, *, nonempty: bool = False
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field} must be an exact tuple")
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise ValueError(f"{field} exceeds the canonical tuple bound")
    if nonempty and not value:
        raise ValueError(f"{field} must not be empty")
    copied = tuple(validate_canonical_id(item, field) for item in value)
    if len(set(copied)) != len(copied):
        raise ValueError(f"{field} contains a duplicate")
    return canonical_set_tuple(copied)


def canonical_id_sequence(
    value: object, field: str, *, nonempty: bool = False
) -> tuple[str, ...]:
    """Validate canonical IDs while preserving normative sequence order."""

    if type(value) is not tuple:
        raise TypeError(f"{field} must be an exact tuple")
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise ValueError(f"{field} exceeds the canonical tuple bound")
    if nonempty and not value:
        raise ValueError(f"{field} must not be empty")
    copied = tuple(validate_canonical_id(item, field) for item in value)
    if len(set(copied)) != len(copied):
        raise ValueError(f"{field} contains a duplicate")
    return copied


class ApplicabilityTag(str, Enum):
    BOUND = "BOUND"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class ApplicabilityBinding(Generic[T]):
    """Closed BOUND/NOT_APPLICABLE union; omission is never a branch."""

    tag: ApplicabilityTag
    value: T | object

    def __post_init__(self) -> None:
        exact_enum(self.tag, ApplicabilityTag, "applicability tag")
        if self.tag is ApplicabilityTag.BOUND:
            if self.value is None:
                raise TypeError("BOUND applicability requires a value")
        else:
            owner(self.value, "applicability_reason", "inapplicability reason")

    @classmethod
    def bound(cls, value: T) -> ApplicabilityBinding[T]:
        return cls(ApplicabilityTag.BOUND, value)

    @classmethod
    def not_applicable(cls, reason_ref: object) -> ApplicabilityBinding[T]:
        return cls(ApplicabilityTag.NOT_APPLICABLE, reason_ref)

    @property
    def is_bound(self) -> bool:
        return self.tag is ApplicabilityTag.BOUND

    def require_bound(self, expected: type[T], field: str) -> T:
        if not self.is_bound or type(self.value) is not expected:
            raise ValueError(f"{field} must be an exact BOUND {expected.__name__}")
        return self.value

    def require_not_applicable(self, field: str) -> None:
        if self.is_bound:
            raise ValueError(f"{field} must be explicitly NOT_APPLICABLE")


class PrecisionLiteral(str, Enum):
    BOOL = "BOOL"
    INT64 = "INT64"
    FLOAT32 = "FLOAT32"
    FLOAT64 = "FLOAT64"
    UTF8 = "UTF8"
    BYTES = "BYTES"
    STRUCTURED_REF = "STRUCTURED_REF"


class PopulationRole(str, Enum):
    TARGET_WORKLOAD_P = "TARGET_WORKLOAD_P"
    OFFICIAL_PROPOSAL_Q = "OFFICIAL_PROPOSAL_Q"
    EVIDENCE_WEIGHT_W = "EVIDENCE_WEIGHT_W"
    STRESS = "STRESS"
    PRACTICE = "PRACTICE"
    PRODUCT_QUALIFICATION = "PRODUCT_QUALIFICATION"
    DEPLOYMENT = "DEPLOYMENT"
    QUERY = "QUERY"
    OBSERVATION = "OBSERVATION"
    EVIDENCE_CAMPAIGN = "EVIDENCE_CAMPAIGN"


class SamplingRole(str, Enum):
    OFFICIAL_EVALUATION = "OFFICIAL_EVALUATION"
    STRESS = "STRESS"
    PRACTICE = "PRACTICE"
    PRODUCT_QUALIFICATION = "PRODUCT_QUALIFICATION"
    VERIFICATION = "VERIFICATION"
    EVIDENCE_CAMPAIGN = "EVIDENCE_CAMPAIGN"


class WeightingRole(str, Enum):
    DESIGN_INCLUSION_CORRECTION = "DESIGN_INCLUSION_CORRECTION"
    SCIENTIFIC_EVIDENCE_WEIGHT = "SCIENTIFIC_EVIDENCE_WEIGHT"
    REPORTING_WEIGHT = "REPORTING_WEIGHT"


class FiniteDesignMode(str, Enum):
    FIXED = "FIXED"
    REGISTERED_SEQUENTIAL = "REGISTERED_SEQUENTIAL"


class TimeMode(str, Enum):
    STEADY = "STEADY"
    TRANSIENT = "TRANSIENT"


class DisclosureClass(str, Enum):
    INTERNAL = "INTERNAL"
    PROTECTED = "PROTECTED"


class CasePopulationUse(str, Enum):
    PRIMARY = "PRIMARY"
    RELATED = "RELATED"
    QUERY = "QUERY"
    OBSERVATION = "OBSERVATION"


class DownstreamPopulationOwner(str, Enum):
    B_03_GENERATION = "B_03_GENERATION"
    B_04_REFERENCE = "B_04_REFERENCE"
    B_05_MEASUREMENT = "B_05_MEASUREMENT"
    B_06_DOSSIER = "B_06_DOSSIER"
    B_07R_RESEARCH = "B_07R_RESEARCH"


class CaseState(str, Enum):
    VALID = "VALID"
    CENSORED = "CENSORED"
    EXCLUDED = "EXCLUDED"
    GENERATION_FAILURE = "GENERATION_FAILURE"


class CensoringReason(str, Enum):
    REFERENCE_UNAVAILABLE = "REFERENCE_UNAVAILABLE"
    REFERENCE_DISPUTED = "REFERENCE_DISPUTED"
    REFERENCE_NUMERICAL_FAILURE = "REFERENCE_NUMERICAL_FAILURE"
    REFERENCE_RESOURCE_LIMIT = "REFERENCE_RESOURCE_LIMIT"
    REFERENCE_TIMEOUT = "REFERENCE_TIMEOUT"
    OBSERVATION_MISSING = "OBSERVATION_MISSING"
    OBSERVATION_TIMEOUT = "OBSERVATION_TIMEOUT"
    MEASUREMENT_UNAVAILABLE = "MEASUREMENT_UNAVAILABLE"
    MEASUREMENT_RESOURCE_LIMIT = "MEASUREMENT_RESOURCE_LIMIT"
    MEASUREMENT_TIMEOUT = "MEASUREMENT_TIMEOUT"
    EXPERIMENT_CORRUPTED = "EXPERIMENT_CORRUPTED"
    EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER = (
        "EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER"
    )


class EvidenceRole(str, Enum):
    ANALYTIC = "ANALYTIC"
    SEMI_ANALYTIC = "SEMI_ANALYTIC"
    MANUFACTURED_SOLUTION_VERIFICATION = "MANUFACTURED_SOLUTION_VERIFICATION"
    NUMERICAL = "NUMERICAL"
    EXPERIMENTAL = "EXPERIMENTAL"
    INDUSTRIAL = "INDUSTRIAL"
    REGISTERED_HYBRID = "REGISTERED_HYBRID"


class PublicCaseFactKind(str, Enum):
    PHYSICAL_SYSTEM_CONTRACT = "PHYSICAL_SYSTEM_CONTRACT"
    CANDIDATE_OUTPUT_CONTRACT = "CANDIDATE_OUTPUT_CONTRACT"
    PRIMARY_POPULATION_ROLE = "PRIMARY_POPULATION_ROLE"
    CASE_REPRESENTATION = "CASE_REPRESENTATION"
    EVIDENCE_CAMPAIGN_APPLICABILITY = "EVIDENCE_CAMPAIGN_APPLICABILITY"


class PublicPlanFactKind(str, Enum):
    SAMPLING_ROLE = "SAMPLING_ROLE"
    PRIMARY_POPULATION_PUBLIC_REF = "PRIMARY_POPULATION_PUBLIC_REF"
    SELECTION_POPULATION_PUBLIC_REF = "SELECTION_POPULATION_PUBLIC_REF"
    INTENDED_ESTIMAND_OR_REPORTING_PUBLIC_REF = (
        "INTENDED_ESTIMAND_OR_REPORTING_PUBLIC_REF"
    )
    BASE_INTENDED_COUNT = "BASE_INTENDED_COUNT"
    FINITE_DESIGN_MODE = "FINITE_DESIGN_MODE"
    PUBLIC_STATISTICAL_OBJECTIVES = "PUBLIC_STATISTICAL_OBJECTIVES"
    PUBLIC_POLICY_REFS = "PUBLIC_POLICY_REFS"


class ProtectedPlanFieldKind(str, Enum):
    DRAW_IDENTITY = "DRAW_IDENTITY"
    SLOT_IDENTITY = "SLOT_IDENTITY"
    ENTROPY = "ENTROPY"
    SEED = "SEED"
    REALIZED_STRATUM = "REALIZED_STRATUM"
    DRAW_ORDER = "DRAW_ORDER"
    REPLACEMENT_LINEAGE = "REPLACEMENT_LINEAGE"
    PROTECTED_COMPOSITION = "PROTECTED_COMPOSITION"


@dataclass(frozen=True, slots=True)
class DisclosureContract:
    public_field_ids: tuple[str, ...]
    internal_field_ids: tuple[str, ...]
    protected_field_ids: tuple[str, ...]
    aggregation_policy_ref: object
    release_policy_ref: object

    def __post_init__(self) -> None:
        public = canonical_ids(self.public_field_ids, "public_field_ids")
        internal = canonical_ids(self.internal_field_ids, "internal_field_ids")
        protected = canonical_ids(self.protected_field_ids, "protected_field_ids")
        if (
            set(public) & set(internal)
            or set(public) & set(protected)
            or set(internal) & set(protected)
        ):
            raise ValueError("disclosure field classes must be disjoint")
        object.__setattr__(self, "public_field_ids", public)
        object.__setattr__(self, "internal_field_ids", internal)
        object.__setattr__(self, "protected_field_ids", protected)
        owner(
            self.aggregation_policy_ref, "aggregation_policy", "aggregation_policy_ref"
        )
        owner(self.release_policy_ref, "release_policy", "release_policy_ref")


@dataclass(frozen=True, slots=True)
class DownstreamPopulationConsumer:
    owner: DownstreamPopulationOwner
    consumer_contract_ref: object

    def __post_init__(self) -> None:
        exact_enum(self.owner, DownstreamPopulationOwner, "consumer owner")
        owner(
            self.consumer_contract_ref,
            "downstream_population_consumer_contract",
            "consumer_contract_ref",
        )


class AllowedConsumerKind(str, Enum):
    SAMPLING_PLAN = "SAMPLING_PLAN"
    CANONICAL_CASE = "CANONICAL_CASE"
    CASE_EVIDENCE = "CASE_EVIDENCE"
    REALIZED_EVIDENCE_DERIVATION = "REALIZED_EVIDENCE_DERIVATION"
    DOWNSTREAM_OWNER = "DOWNSTREAM_OWNER"


@dataclass(frozen=True, slots=True)
class AllowedConsumer:
    kind: AllowedConsumerKind
    payload: (
        SamplingRole
        | CasePopulationUse
        | EvidenceRole
        | DownstreamPopulationConsumer
        | None
    )

    def __post_init__(self) -> None:
        exact_enum(self.kind, AllowedConsumerKind, "allowed consumer kind")
        expected: type[object] | None = {
            AllowedConsumerKind.SAMPLING_PLAN: SamplingRole,
            AllowedConsumerKind.CANONICAL_CASE: CasePopulationUse,
            AllowedConsumerKind.CASE_EVIDENCE: EvidenceRole,
            AllowedConsumerKind.REALIZED_EVIDENCE_DERIVATION: None,
            AllowedConsumerKind.DOWNSTREAM_OWNER: DownstreamPopulationConsumer,
        }[self.kind]
        if expected is None:
            if self.payload is not None:
                raise TypeError("realized-evidence consumer has no payload")
        elif type(self.payload) is not expected:
            raise TypeError("allowed consumer has a wrong exact payload")


@dataclass(frozen=True, slots=True)
class AuthoredIdentity:
    """Validated common top-level envelope used through composition."""

    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        validate_version_token(self.schema_version, "schema_version")
        if type(self.canonicalization_profile) is not str:
            raise TypeError("canonicalization_profile must be exact str")
        object.__setattr__(
            self, "challenge_key", reconstruct_challenge_key(self.challenge_key)
        )
        validate_canonical_id(self.object_id, "object_id")
        validate_version_token(self.object_version, "object_version")
        exact(self.supersedes, ApplicabilityBinding, "supersedes")


def validate_identity(
    value: object,
    *,
    schema_version: str,
    canonicalization_profile: str,
    challenge_key: ChallengeKey,
    object_id: str,
    object_version: str,
    supersedes: ApplicabilityBinding[object],
) -> AuthoredIdentity:
    """Reconstruct the common envelope without retaining caller-owned state."""

    if value is not None:
        raise TypeError("identity validator is not a public payload")
    return AuthoredIdentity(
        schema_version=schema_version,
        canonicalization_profile=canonicalization_profile,
        challenge_key=challenge_key,
        object_id=object_id,
        object_version=object_version,
        supersedes=supersedes,
    )


def positive_uint64(value: object, field: str) -> int:
    return validate_positive_uint64(value, field)


def fraction(value: object, field: str) -> float:
    checked = validate_finite_float64(value, field)
    if not 0.0 <= checked <= 1.0:
        raise ValueError(f"{field} must be in [0.0, 1.0]")
    return checked


def copied_challenge_key(value: object) -> ChallengeKey:
    return reconstruct_challenge_key(value)


def _owner_payload_equal(left: object, right: object) -> bool:
    """Compare two nominal owner refs by their exact pinned payload, not kind."""

    return all(
        getattr(left, field, None) == getattr(right, field, None)
        for field in (
            "scope_binding",
            "object_id",
            "object_version",
            "content_digest",
        )
    )


def validate_loaded_authoring_graph(objects_by_ref: Mapping[object, object]) -> None:
    """Validate all B-02A cross-object seams in one exact loaded graph.

    The mapping is produced only after each ref's bytes and digest have been
    verified by the loader.  This pass never infers identity from common
    support, a PDE name, generator, representation, or provenance.
    """

    if not isinstance(objects_by_ref, Mapping):
        raise TypeError("objects_by_ref must be a mapping")
    # Lazy imports keep the model dependency graph acyclic.
    from .cases import CanonicalChallengeCase
    from .evidence import (
        CanonicalCaseDisposition,
        CanonicalCaseDispositionRef,
        CensoringRecord,
        CensoringRecordRef,
        RealizedValidEvidenceRecord,
        RealizedValidEvidenceRecordRef,
        validate_censoring_against_plan,
        validate_replacement_decision,
    )
    from .physical import (
        CandidateOutputContract,
        PhysicalSystemSpec,
        validate_candidate_against_physical,
    )
    from .populations import (
        InstanceDistributionContract,
        StratificationContract,
        WeightingPayload,
        WeightingSemanticsKind,
        validate_population_graph,
    )
    from .refs import (
        CandidateOutputContractRef,
        CanonicalChallengeCaseRef,
        InstanceDistributionContractRef,
        PhysicalSystemSpecRef,
        SamplingPlanRef,
        TrainingSupportContractRef,
    )
    from .sampling import AllocationKind, SamplingPlan, validate_sampling_selection_law
    from .training_support import TrainingSupportContract

    allowed_pairs = (
        (PhysicalSystemSpecRef, PhysicalSystemSpec),
        (CandidateOutputContractRef, CandidateOutputContract),
        (InstanceDistributionContractRef, InstanceDistributionContract),
        (SamplingPlanRef, SamplingPlan),
        (TrainingSupportContractRef, TrainingSupportContract),
        (CanonicalChallengeCaseRef, CanonicalChallengeCase),
        (CanonicalCaseDispositionRef, CanonicalCaseDisposition),
        (CensoringRecordRef, CensoringRecord),
        (RealizedValidEvidenceRecordRef, RealizedValidEvidenceRecord),
    )
    for ref, value in objects_by_ref.items():
        pair = next(
            (
                (ref_type, value_type)
                for ref_type, value_type in allowed_pairs
                if type(ref) is ref_type
            ),
            None,
        )
        if pair is None or type(value) is not pair[1]:
            raise TypeError("loaded graph contains a wrong ref/object nominal pairing")
        if type(ref) in {
            CanonicalCaseDispositionRef,
            CensoringRecordRef,
            RealizedValidEvidenceRecordRef,
        }:
            if ref != value.to_ref():
                raise ValueError("loaded derived ref differs from canonical record")
            continue
        if (
            ref.challenge_key != value.challenge_key
            or ref.object_id != value.object_id
            or ref.object_version != value.object_version
            or ref.schema_version != value.schema_version
            or ref.canonicalization_profile != value.canonicalization_profile
        ):
            raise ValueError("loaded graph ref metadata differs from its object")
        if (
            type(ref) is InstanceDistributionContractRef
            and ref.expected_population_role != value.population_role.value
        ):
            raise ValueError("loaded population role differs from its ref pin")
        if (
            type(ref) is CanonicalChallengeCaseRef
            and ref.disclosure_class != value.disclosure_class.value
        ):
            raise ValueError("loaded case disclosure differs from its ref pin")

    def resolve(ref: object, expected: type[T], field: str) -> T:
        try:
            value = objects_by_ref[ref]
        except KeyError as exc:
            raise ValueError(f"{field} dependency is missing") from exc
        return exact(value, expected, field)

    for value in objects_by_ref.values():
        if type(value) is CandidateOutputContract:
            physical = resolve(
                value.physical_system_ref,
                PhysicalSystemSpec,
                "candidate physical system",
            )
            validate_candidate_against_physical(value, physical)
        elif type(value) is InstanceDistributionContract:
            physical = resolve(
                value.physical_system_ref,
                PhysicalSystemSpec,
                "population physical system",
            )
            candidate = resolve(
                value.candidate_output_ref,
                CandidateOutputContract,
                "population candidate contract",
            )
            if candidate.physical_system_ref != value.physical_system_ref:
                raise ValueError("population physical/candidate graph mismatch")
            if physical.challenge_key != candidate.challenge_key:
                raise ValueError("population graph crosses Challenge versions")
            target = (
                resolve(
                    value.target_population_binding.value,
                    InstanceDistributionContract,
                    "population target",
                )
                if value.target_population_binding.is_bound
                else None
            )
            proposal = (
                resolve(
                    value.proposal_population_binding.value,
                    InstanceDistributionContract,
                    "population proposal",
                )
                if value.proposal_population_binding.is_bound
                else None
            )
            validate_population_graph(value, target=target, proposal=proposal)
        elif type(value) is TrainingSupportContract:
            resolve(
                value.physical_system_ref,
                PhysicalSystemSpec,
                "training-support physical system",
            )
            candidate = resolve(
                value.candidate_output_ref,
                CandidateOutputContract,
                "training-support candidate contract",
            )
            if candidate.physical_system_ref != value.physical_system_ref:
                raise ValueError("training support physical/candidate graph mismatch")
        elif type(value) is SamplingPlan:
            primary = resolve(
                value.primary_population_ref,
                InstanceDistributionContract,
                "plan primary population",
            )
            selection = resolve(
                value.selection_population_ref,
                InstanceDistributionContract,
                "plan selection population",
            )
            if (
                primary.physical_system_ref != selection.physical_system_ref
                or primary.candidate_output_ref != selection.candidate_output_ref
            ):
                raise ValueError(
                    "SamplingPlan populations bind different physical jobs"
                )
            validate_sampling_selection_law(value, selection.law_semantics)
            bound_population_fields = (
                ("primary", primary),
                ("selection", selection),
            )
            for field_name, binding in (
                ("target", value.target_population_binding),
                ("official proposal", value.official_proposal_binding),
                ("evidence weight", value.evidence_weight_binding),
                ("query", value.query_population_binding),
                ("observation", value.observation_population_binding),
            ):
                if binding.is_bound:
                    bound_population_fields += (
                        (
                            field_name,
                            resolve(
                                binding.value,
                                InstanceDistributionContract,
                                f"plan {field_name} population",
                            ),
                        ),
                    )
            for field_name, population in bound_population_fields:
                admitted = any(
                    consumer.kind is AllowedConsumerKind.SAMPLING_PLAN
                    and consumer.payload is value.sampling_role
                    for consumer in population.allowed_consumers
                )
                if not admitted:
                    raise ValueError(
                        f"plan {field_name} population disallows this SamplingPlan role"
                    )
                if (
                    population.physical_system_ref != primary.physical_system_ref
                    or population.candidate_output_ref != primary.candidate_output_ref
                ):
                    raise ValueError("plan-bound population graph mismatch")
            if value.sampling_role is SamplingRole.OFFICIAL_EVALUATION:
                if selection.target_population_binding.value != primary.to_ref():
                    raise ValueError("official Q does not bind the plan's exact P")
                if value.evidence_weight_binding.is_bound:
                    weight = resolve(
                        value.evidence_weight_binding.value,
                        InstanceDistributionContract,
                        "official evidence weight",
                    )
                    if weight.target_population_binding.value != primary.to_ref():
                        raise ValueError("official w does not bind the plan's exact P")
                    if weight.proposal_population_binding.value != selection.to_ref():
                        raise ValueError("official w does not bind the plan's exact Q")
                    if (
                        weight.weighting_semantics.kind
                        is not WeightingSemanticsKind.WEIGHTING
                    ):
                        raise ValueError("official w lacks exact weighting semantics")
                    weighting = exact(
                        weight.weighting_semantics.payload,
                        WeightingPayload,
                        "official weighting payload",
                    )
                    if not _owner_payload_equal(
                        weighting.estimand_scope_ref,
                        value.intended_estimand_or_reporting_ref,
                    ):
                        raise ValueError(
                            "official w estimand differs from SamplingPlan"
                        )
            if value.stratified_allocation_binding.is_bound:
                allocation = value.stratified_allocation_binding.value
                primary_stratification = primary.stratification_binding.require_bound(
                    StratificationContract,
                    "stratified primary population",
                )
                selection_stratification = (
                    selection.stratification_binding.require_bound(
                        StratificationContract,
                        "stratified selection population",
                    )
                )
                if (
                    primary_stratification.stratification_id
                    != allocation.primary_stratification_id
                    or selection_stratification.stratification_id
                    != allocation.selection_stratification_id
                ):
                    raise ValueError(
                        "stratified allocation ID does not match populations"
                    )
                primary_strata = {
                    item.stratum_id for item in primary_stratification.strata
                }
                selection_strata = {
                    item.stratum_id for item in selection_stratification.strata
                }
                allocated_primary = {
                    item.primary_stratum_id for item in allocation.allocations
                }
                if allocated_primary != primary_strata:
                    raise ValueError(
                        "stratified allocation does not cover exact primary strata"
                    )
                for item in allocation.allocations:
                    if (
                        item.selection_stratum_binding.is_bound
                        and item.selection_stratum_binding.value not in selection_strata
                    ):
                        raise ValueError(
                            "allocation crosswalk names an unknown selection stratum"
                        )
                allocation_kinds = {
                    item.allocation.kind for item in allocation.allocations
                }
                if allocation_kinds == {AllocationKind.COUNT}:
                    total = sum(
                        item.allocation.payload for item in allocation.allocations
                    )
                    if total != value.finite_evidence_design.base_intended_count:
                        raise ValueError("stratum counts do not equal intended count")
                elif allocation_kinds == {AllocationKind.FRACTION}:
                    import math

                    total = math.fsum(
                        item.allocation.payload.fraction
                        for item in allocation.allocations
                    )
                    if total != 1.0:
                        raise ValueError("stratum fractions do not sum exactly to one")
                elif allocation_kinds != {AllocationKind.OWNER_RULE}:
                    raise ValueError("stratified allocation kinds cannot be mixed")
            has_query_or_observation = (
                value.query_population_binding.is_bound
                or value.observation_population_binding.is_bound
            )
            if (
                value.query_observation_allocation_binding.is_bound
                != has_query_or_observation
            ):
                raise ValueError(
                    "query/observation allocation applicability differs from population bindings"
                )
        elif type(value) is CanonicalChallengeCase:
            physical = resolve(
                value.physical_system_ref,
                PhysicalSystemSpec,
                "case physical system",
            )
            candidate = resolve(
                value.candidate_output_ref,
                CandidateOutputContract,
                "case candidate contract",
            )
            primary = resolve(
                value.primary_population_ref,
                InstanceDistributionContract,
                "case primary population",
            )
            if candidate.physical_system_ref != value.physical_system_ref:
                raise ValueError("case candidate does not bind case physical system")
            if (
                primary.physical_system_ref != value.physical_system_ref
                or primary.candidate_output_ref != value.candidate_output_ref
                or primary.owning_claim_scope_ref != physical.claim_scope_ref
            ):
                raise ValueError("case primary population graph mismatch")
            if primary.population_role is PopulationRole.EVIDENCE_WEIGHT_W:
                raise ValueError("evidence weight cannot be a case primary population")
            if not any(
                consumer.kind is AllowedConsumerKind.CANONICAL_CASE
                and consumer.payload is CasePopulationUse.PRIMARY
                for consumer in primary.allowed_consumers
            ):
                raise ValueError("primary population does not admit canonical cases")
            for related in value.related_population_bindings:
                related_population = resolve(
                    related.population_ref,
                    InstanceDistributionContract,
                    "case related population",
                )
                if (
                    related_population.physical_system_ref != value.physical_system_ref
                    or related_population.candidate_output_ref
                    != value.candidate_output_ref
                    or related_population.owning_claim_scope_ref
                    != physical.claim_scope_ref
                ):
                    raise ValueError("case related population graph mismatch")
                if (
                    related_population.population_role
                    is PopulationRole.EVIDENCE_WEIGHT_W
                ):
                    raise ValueError(
                        "evidence weight cannot be a case related population"
                    )
                if not any(
                    consumer.kind is AllowedConsumerKind.CANONICAL_CASE
                    and consumer.payload is CasePopulationUse.RELATED
                    for consumer in related_population.allowed_consumers
                ):
                    raise ValueError("related population does not admit related cases")
            if value.sampling_plan_binding.is_bound:
                plan = resolve(
                    value.sampling_plan_binding.value,
                    SamplingPlan,
                    "case SamplingPlan",
                )
                if plan.primary_population_ref != value.primary_population_ref:
                    raise ValueError(
                        "case and SamplingPlan primary population mismatch"
                    )
                if plan.query_population_binding != value.query_population_binding:
                    raise ValueError("case and SamplingPlan query binding mismatch")
                if (
                    plan.observation_population_binding
                    != value.observation_population_binding
                ):
                    raise ValueError(
                        "case and SamplingPlan observation binding mismatch"
                    )
                if plan.evidence_campaign_binding != value.evidence_campaign_binding:
                    raise ValueError("case and SamplingPlan campaign binding mismatch")
                if (
                    not value.prospective_censoring_policy_binding.is_bound
                    or value.prospective_censoring_policy_binding.value
                    != plan.censoring_policy_ref
                ):
                    raise ValueError("case and SamplingPlan censoring policy mismatch")
            for binding, use in (
                (value.query_population_binding, CasePopulationUse.QUERY),
                (value.observation_population_binding, CasePopulationUse.OBSERVATION),
            ):
                if binding.is_bound:
                    population = resolve(
                        binding.value,
                        InstanceDistributionContract,
                        "case query/observation population",
                    )
                    if (
                        population.physical_system_ref != value.physical_system_ref
                        or population.candidate_output_ref != value.candidate_output_ref
                        or population.owning_claim_scope_ref != physical.claim_scope_ref
                    ):
                        raise ValueError(
                            "case query/observation population graph mismatch"
                        )
                    if not any(
                        consumer.kind is AllowedConsumerKind.CANONICAL_CASE
                        and consumer.payload is use
                        for consumer in population.allowed_consumers
                    ):
                        raise ValueError(
                            "query/observation population disallows case use"
                        )
            from .cases import CaseSourceKind, ManufacturedSolutionCaseSource

            if value.case_source.kind is CaseSourceKind.MANUFACTURED_SOLUTION:
                source = exact(
                    value.case_source.payload,
                    ManufacturedSolutionCaseSource,
                    "MMS case source",
                )
                if not value.evidence_campaign_binding.is_bound:
                    raise ValueError("MMS case requires verification campaign binding")
                if (
                    value.evidence_campaign_binding.value
                    != source.verification_campaign_ref
                ):
                    raise ValueError("MMS source/case campaign mismatch")
                if primary.population_role is not PopulationRole.EVIDENCE_CAMPAIGN:
                    raise ValueError(
                        "MMS case requires verification campaign population"
                    )
                if (
                    value.sampling_plan_binding.is_bound
                    and plan.sampling_role is not SamplingRole.VERIFICATION
                ):
                    raise ValueError(
                        "MMS case SamplingPlan must have VERIFICATION role"
                    )
        elif type(value) is CensoringRecord:
            plan = resolve(
                value.sampling_plan_ref, SamplingPlan, "censoring SamplingPlan"
            )
            resolve(
                value.population_ref,
                InstanceDistributionContract,
                "censoring population",
            )
            validate_censoring_against_plan(value, plan)
            validate_replacement_decision(
                value.replacement_decision,
                plan_ref=plan.to_ref(),
                policy=plan.replacement_policy,
                executed=value.replacement_decision.lineage_binding.is_bound,
            )
        elif type(value) is CanonicalCaseDisposition:
            plan = resolve(
                value.sampling_plan_ref,
                SamplingPlan,
                "disposition SamplingPlan",
            )
            primary = resolve(
                value.primary_population_ref,
                InstanceDistributionContract,
                "disposition primary population",
            )
            if plan.primary_population_ref != primary.to_ref():
                raise ValueError("disposition primary population differs from plan")
            if (
                value.evidence_scope.evidence_campaign_binding
                != plan.evidence_campaign_binding
            ):
                raise ValueError("disposition campaign differs from SamplingPlan")
            if (
                value.evidence_scope.query_population_binding
                != plan.query_population_binding
            ):
                raise ValueError(
                    "disposition query population differs from SamplingPlan"
                )
            if (
                value.evidence_scope.observation_population_binding
                != plan.observation_population_binding
            ):
                raise ValueError(
                    "disposition observation population differs from SamplingPlan"
                )
            if (
                value.evidence_scope.intended_estimand_or_reporting_ref
                != plan.intended_estimand_or_reporting_ref
            ):
                raise ValueError("disposition estimand differs from SamplingPlan")
            validate_replacement_decision(
                value.replacement_decision,
                plan_ref=plan.to_ref(),
                policy=plan.replacement_policy,
                executed=value.replacement_decision.lineage_binding.is_bound,
            )
            if value.case_ref_binding.is_bound:
                case = resolve(
                    value.case_ref_binding.value,
                    CanonicalChallengeCase,
                    "disposition case",
                )
                if (
                    case.primary_population_ref != value.primary_population_ref
                    or case.sampling_plan_binding.value != value.sampling_plan_ref
                    or case.evidence_campaign_binding
                    != value.evidence_scope.evidence_campaign_binding
                    or case.query_population_binding
                    != value.evidence_scope.query_population_binding
                    or case.observation_population_binding
                    != value.evidence_scope.observation_population_binding
                ):
                    raise ValueError(
                        "disposition case bindings differ from evidence scope"
                    )
            if value.case_state is CaseState.CENSORED:
                censoring = resolve(
                    value.state_payload.payload,
                    CensoringRecord,
                    "censored disposition record",
                )
                if (
                    censoring.intended_evidence_unit_ref
                    != value.intended_evidence_unit_ref
                    or censoring.sampling_plan_ref != value.sampling_plan_ref
                    or censoring.population_ref != value.primary_population_ref
                    or censoring.evidence_scope != value.evidence_scope
                    or censoring.evidence_campaign_binding
                    != value.evidence_scope.evidence_campaign_binding
                    or censoring.replacement_decision != value.replacement_decision
                ):
                    raise ValueError(
                        "censoring record differs from censored disposition"
                    )
        elif type(value) is RealizedValidEvidenceRecord:
            plan = resolve(
                value.sampling_plan_ref,
                SamplingPlan,
                "realized SamplingPlan",
            )
            if (
                value.primary_population_ref != plan.primary_population_ref
                or value.selection_population_ref != plan.selection_population_ref
                or value.target_population_binding != plan.target_population_binding
                or value.official_proposal_binding != plan.official_proposal_binding
                or value.evidence_weight_binding != plan.evidence_weight_binding
                or value.intended_estimand_or_reporting_ref
                != plan.intended_estimand_or_reporting_ref
                or value.censoring_policy_ref != plan.censoring_policy_ref
            ):
                raise ValueError("realized evidence differs from exact SamplingPlan")
            for disposition_ref in value.disposition_refs:
                disposition = resolve(
                    disposition_ref,
                    CanonicalCaseDisposition,
                    "realized disposition",
                )
                if (
                    disposition.sampling_plan_ref != value.sampling_plan_ref
                    or disposition.primary_population_ref
                    != value.primary_population_ref
                    or disposition.evidence_scope != value.evidence_scope
                ):
                    raise ValueError("realized disposition scope mismatch")


def _closed_record_schemas() -> dict[
    type[object], tuple[str, tuple[str, ...], frozenset[str]]
]:
    """Return the explicit v1 subordinate-record registry.

    This is intentionally a closed table.  It does not inspect arbitrary
    dataclasses, Python type names, or caller mappings.
    """

    from .cases import (
        AnalyticCaseSource,
        CanonicalChallengeCase,
        ExperimentalCaseSource,
        GeneratedCaseSource,
        IndustrialCaseSource,
        InternalCaseIdentityProjection,
        ManufacturedSolutionCaseSource,
        ObservedCaseSource,
        ProtectedCaseIdentityProjection,
        PublicCaseFactBinding,
        PublicCaseIdentityProjection,
        RelatedPopulationBinding,
    )
    from .evidence import (
        CanonicalCaseDisposition,
        CaseEvidenceBinding,
        CensoringRecord,
        EvidenceScopeBinding,
        ExcludedCasePayload,
        GenerationFailurePayload,
        InfrastructureCensoringTrigger,
        RealizedValidEvidenceRecord,
        ReplacementDecision,
        ValidCasePayload,
    )
    from .physical import (
        AssumptionClause,
        AxisContract,
        BoundaryConditionContract,
        BoundaryRegionClause,
        CandidateInputBinding,
        CandidateOutputBinding,
        CandidateOutputContract,
        ConditionInputBinding,
        InitialConditionContract,
        InitialStateClause,
        PhysicalSystemSpec,
        TimeContract,
        TimeHorizonBinding,
        ValueFieldContract,
    )
    from .populations import (
        ExclusionContract,
        FiniteEnumeration,
        InstanceDistributionContract,
        ProbabilityLaw,
        StratificationContract,
        StratumContract,
        SupportContract,
        WeightingPayload,
    )
    from .sampling import (
        DuplicatePolicy,
        FiniteEvidenceDesign,
        FractionAllocation,
        ProspectiveStoppingExtensionPolicy,
        RegisteredAdaptiveAccess,
        RegisteredReplacementPolicy,
        SamplingPlan,
        StratifiedAllocationContract,
        StratumAllocation,
    )
    from .training_support import (
        SourceMaterialBinding,
        TrainingMembershipContract,
        TrainingSupportContract,
    )

    schema: dict[type[object], tuple[str, tuple[str, ...], frozenset[str]]] = {}

    def add(
        cls: type[object],
        record_type: str,
        fields: tuple[str, ...],
        set_like: tuple[str, ...] = (),
    ) -> None:
        schema[cls] = (record_type, fields, frozenset(set_like))

    add(
        AxisContract,
        "axis_contract",
        ("axis_id", "extent", "semantic_role_ref", "unit_ref"),
    )
    add(
        ValueFieldContract,
        "value_field_contract",
        (
            "admissibility_refs",
            "field_id",
            "geometry_binding",
            "nonfinite_policy",
            "precision_contract",
            "presence",
            "representation_ref",
            "semantic_role_ref",
            "shape_contract",
            "unit_ref",
        ),
        ("admissibility_refs", "precision_contract"),
    )
    add(
        AssumptionClause,
        "assumption_clause",
        ("applicability", "assumption_id", "authority_ref", "semantic_ref"),
    )
    add(
        BoundaryRegionClause,
        "boundary_region_clause",
        (
            "applicability",
            "causal_input_binding",
            "condition_semantic_ref",
            "geometry_region_ref",
            "region_clause_id",
            "unit_ref",
        ),
    )
    add(BoundaryConditionContract, "boundary_condition_contract", ("clauses",))
    add(
        InitialStateClause,
        "initial_state_clause",
        (
            "applicability",
            "causal_input_binding",
            "geometry_domain_ref",
            "state_clause_id",
            "state_semantic_ref",
            "time_origin_ref",
        ),
    )
    add(InitialConditionContract, "initial_condition_contract", ("clauses",))
    add(
        TimeContract,
        "time_contract",
        (
            "endpoint_inclusion_semantic_ref",
            "horizon_binding",
            "mode",
            "time_coordinate_binding",
            "time_unit_ref",
        ),
    )
    add(
        CandidateInputBinding,
        "candidate_input_binding",
        ("candidate_field_id", "physical_field_id", "relation"),
    )
    add(
        CandidateOutputBinding,
        "candidate_output_binding",
        (
            "candidate_field_id",
            "physical_quantity_id",
            "relation",
            "semantic_equivalence_ref",
        ),
    )
    add(
        ConditionInputBinding,
        "condition_input_binding",
        ("candidate_field_id", "condition_clause_id", "relation"),
    )
    add(
        TimeHorizonBinding,
        "time_horizon_binding",
        (
            "candidate_field_ids",
            "endpoint_equivalence_ref",
            "horizon_equivalence_ref",
            "time_coordinate_equivalence_ref",
        ),
    )
    add(
        SupportContract,
        "support_contract",
        (
            "boundary_semantics_ref",
            "failure_outcome",
            "membership_decision_ref",
            "membership_rule_ref",
            "physical_support_ref",
            "representation_support_ref",
        ),
    )
    add(
        ProbabilityLaw,
        "probability_law_payload",
        ("base_measure_ref", "law_ref", "normalization_claim_ref"),
    )
    add(
        FiniteEnumeration,
        "finite_enumeration_payload",
        ("member_set_ref", "multiplicity_semantics_ref"),
    )
    add(
        WeightingPayload,
        "weighting_payload",
        (
            "estimand_scope_ref",
            "normalization_semantics_ref",
            "proposal_population_binding",
            "target_population_ref",
            "weighting_role",
            "weighting_rule_ref",
        ),
    )
    add(
        DownstreamPopulationConsumer,
        "downstream_population_consumer",
        ("consumer_contract_ref", "owner"),
    )
    add(
        StratumContract,
        "stratum_contract",
        ("applicability_ref", "hierarchy_binding", "membership_rule_ref", "stratum_id"),
    )
    add(
        StratificationContract,
        "stratification_contract",
        (
            "assignment_rule_ref",
            "basis_population_role",
            "disclosure_contract",
            "hierarchy_semantics_ref",
            "relation",
            "strata",
            "stratification_id",
            "unassigned_member_rule_ref",
        ),
        ("strata",),
    )
    add(
        ExclusionContract,
        "exclusion_contract",
        (
            "applicable_claim_ref",
            "audit_semantics_ref",
            "exclusion_id",
            "membership_rule_ref",
            "scientific_authority_ref",
        ),
    )
    add(
        DisclosureContract,
        "disclosure_contract",
        (
            "aggregation_policy_ref",
            "internal_field_ids",
            "protected_field_ids",
            "public_field_ids",
            "release_policy_ref",
        ),
        ("internal_field_ids", "protected_field_ids", "public_field_ids"),
    )
    add(
        SourceMaterialBinding,
        "source_material_binding",
        (
            "membership_proof_ref",
            "permitted_use_ref",
            "provenance_ref",
            "rights_ref",
            "source_material_ref",
            "source_role_ref",
        ),
    )
    add(
        TrainingMembershipContract,
        "training_membership_contract",
        (
            "admission_rule_ref",
            "failure_outcome",
            "physical_support_ref",
            "representation_support_ref",
        ),
    )
    add(
        FractionAllocation,
        "fraction_allocation",
        ("exact_sum_semantics_ref", "fraction", "zero_allocation_binding"),
    )
    add(
        StratumAllocation,
        "stratum_allocation",
        ("allocation", "primary_stratum_id", "selection_stratum_binding"),
    )
    add(
        StratifiedAllocationContract,
        "stratified_allocation_contract",
        (
            "allocation_total_semantics_ref",
            "allocations",
            "apportionment_rule_ref",
            "overlap_accounting_ref",
            "primary_population_ref",
            "primary_stratification_id",
            "selection_population_ref",
            "selection_stratification_id",
            "stratum_mapping_ref",
            "tie_rule_ref",
        ),
        ("allocations",),
    )
    add(
        DuplicatePolicy,
        "duplicate_policy",
        (
            "near_duplicate_rule_ref",
            "physical_duplicate_rule_ref",
            "repeated_observation_rule_ref",
            "replacement_duplicate_rule_ref",
            "representation_duplicate_rule_ref",
        ),
    )
    add(
        RegisteredReplacementPolicy,
        "registered_replacement_payload",
        (
            "accounting_rule_ref",
            "denominator_effect_ref",
            "maximum_attempt_rule_ref",
            "policy_ref",
            "replacement_selection_law_ref",
            "stratum_treatment_ref",
            "triggers",
            "weight_effect_ref",
        ),
        ("triggers",),
    )
    add(
        RegisteredAdaptiveAccess,
        "candidate_adaptive_access",
        ("coverage_qualification_ref", "sequential_rule_ref"),
    )
    add(
        FiniteEvidenceDesign,
        "finite_evidence_design",
        (
            "base_evidence_requirement_ref",
            "base_intended_count",
            "budget_binding",
            "count_unit_ref",
            "design_mode",
            "extension_ceiling_binding",
            "heuristic_stop_outcome",
            "insufficiency_reason",
            "insufficiency_state",
            "plan_change_rule",
        ),
    )
    add(
        ProspectiveStoppingExtensionPolicy,
        "prospective_stopping_extension_policy",
        (
            "candidate_outcome_access_binding",
            "coverage_qualification_binding",
            "extension_rule_binding",
            "interim_look_binding",
            "modification_authority_ref",
            "sequential_allocation_binding",
            "stopping_rule_ref",
        ),
    )
    add(
        RelatedPopulationBinding,
        "related_population_binding",
        ("population_ref", "relationship_ref"),
    )
    add(
        GeneratedCaseSource,
        "generated_case_source",
        ("generation_event_ref", "generator_ref"),
    )
    add(ObservedCaseSource, "observed_case_source", ("observation_source_ref",))
    add(ExperimentalCaseSource, "experimental_case_source", ("experiment_source_ref",))
    add(IndustrialCaseSource, "industrial_case_source", ("industrial_source_ref",))
    add(AnalyticCaseSource, "analytic_case_source", ("analytic_construction_ref",))
    add(
        ManufacturedSolutionCaseSource,
        "mms_case_source",
        ("verification_campaign_ref", "verification_construction_ref"),
    )
    add(
        PublicCaseFactBinding,
        "public_case_fact_binding",
        ("fact_kind", "public_value_ref"),
    )
    add(
        ProtectedCaseIdentityProjection,
        "protected_case_identity_projection",
        (
            "audit_evidence_refs",
            "case_ref",
            "intended_slot_ref",
            "issuance_ref",
            "payload_ref",
            "realized_stratum_binding",
            "replacement_linkage",
            "schema_version",
        ),
        ("audit_evidence_refs",),
    )
    add(
        InternalCaseIdentityProjection,
        "internal_case_identity_projection",
        (
            "case_ref",
            "evidence_campaign_binding",
            "issuance_ref",
            "primary_population_ref",
            "sampling_plan_binding",
            "schema_version",
            "service_scope_ref",
        ),
    )
    add(
        PublicCaseIdentityProjection,
        "public_case_identity_projection",
        (
            "challenge_key",
            "disclosure_policy_ref",
            "issuance_ref",
            "opaque_public_handle",
            "public_fact_bindings",
            "schema_version",
        ),
        ("public_fact_bindings",),
    )
    add(
        EvidenceScopeBinding,
        "evidence_scope_binding",
        (
            "evidence_campaign_binding",
            "intended_estimand_or_reporting_ref",
            "measurement_applicability_binding",
            "observation_population_binding",
            "query_population_binding",
        ),
    )
    add(
        ValidCasePayload,
        "valid_case_payload",
        ("applicability_evidence_ref", "membership_evidence_ref"),
    )
    add(
        ExcludedCasePayload,
        "excluded_case_payload",
        (
            "assessment_ref",
            "exclusion_contract_ref",
            "inclusion_probability_accounting_ref",
            "prospective_screening_design_ref",
        ),
    )
    add(
        GenerationFailurePayload,
        "generation_failure_payload",
        (
            "accounting_ref",
            "distribution_conformance_ref",
            "failure_evidence_ref",
            "source_ref",
        ),
    )
    add(
        InfrastructureCensoringTrigger,
        "infrastructure_censoring_trigger",
        ("acquisition_operation_ref", "infrastructure_failure_ref"),
    )
    add(
        ReplacementDecision,
        "replacement_decision",
        (
            "accounting_evidence_ref",
            "decision",
            "lineage_binding",
            "policy_binding",
            "sampling_plan_ref",
            "trigger_binding",
        ),
    )
    add(
        CaseEvidenceBinding,
        "case_evidence_binding",
        (
            "applicability_refs",
            "authoritative_case_ref",
            "claim_scope_ref",
            "disclosure_contract",
            "downstream_use_restrictions",
            "evidence_artifact_ref",
            "evidence_campaign_ref",
            "evidence_role",
            "policy_qualification_binding",
            "provenance_refs",
            "public_projection_binding",
            "query_observation_provenance",
            "role_population_ref",
        ),
        (
            "applicability_refs",
            "downstream_use_restrictions",
            "provenance_refs",
            "query_observation_provenance",
        ),
    )
    add(
        CanonicalCaseDisposition,
        "canonical_case_disposition",
        (
            "actor_policy_authority_ref",
            "attempt_commitment_binding",
            "audit_evidence_refs",
            "canonicalization_profile",
            "case_ref_binding",
            "case_state",
            "disclosure_contract",
            "downstream_use_restrictions",
            "evidence_scope",
            "intended_evidence_unit_ref",
            "primary_population_ref",
            "replacement_decision",
            "sampling_plan_ref",
            "schema_version",
            "state_payload",
        ),
        ("audit_evidence_refs", "downstream_use_restrictions"),
    )
    add(
        CensoringRecord,
        "censoring_record",
        (
            "accounting_binding",
            "actor_authority_ref",
            "audit_evidence_refs",
            "canonicalization_profile",
            "censoring_reason",
            "downstream_use_restrictions",
            "evidence_campaign_binding",
            "evidence_scope",
            "intended_evidence_unit_ref",
            "missingness_adjustment_binding",
            "population_ref",
            "query_observation_provenance",
            "replacement_decision",
            "sampling_plan_ref",
            "schema_version",
            "trigger_failure_binding",
        ),
        (
            "audit_evidence_refs",
            "downstream_use_restrictions",
            "query_observation_provenance",
        ),
    )
    add(
        RealizedValidEvidenceRecord,
        "realized_valid_evidence_record",
        (
            "accounting_evidence_ref",
            "canonicalization_profile",
            "challenge_key",
            "censoring_policy_ref",
            "complete_unit_manifest_ref",
            "construction_audit_refs",
            "construction_authority_ref",
            "denominator_policy_ref",
            "disclosure_contract",
            "disposition_refs",
            "distribution_conformance_evidence_ref",
            "downstream_use_restrictions",
            "evidence_scope",
            "evidence_weight_binding",
            "intended_estimand_or_reporting_ref",
            "missingness_adjustment_binding",
            "official_proposal_binding",
            "primary_population_ref",
            "sampling_plan_ref",
            "schema_version",
            "selection_population_ref",
            "sensitivity_analysis_binding",
            "target_population_binding",
        ),
        (
            "construction_audit_refs",
            "disposition_refs",
            "downstream_use_restrictions",
        ),
    )

    common = (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "object_id",
        "object_version",
        "supersedes",
    )
    add(
        PhysicalSystemSpec,
        "physical_system_spec",
        common
        + (
            "governing_job_ref",
            "governing_law_refs",
            "assumptions",
            "causal_inputs",
            "required_physical_quantities",
            "geometry_domain_ref",
            "boundary_conditions",
            "initial_conditions",
            "time_contract",
            "operating_envelope_ref",
            "claim_scope_ref",
            "missing_input_policy",
        ),
        ("assumptions",),
    )
    add(
        CandidateOutputContract,
        "candidate_output_contract",
        common
        + (
            "physical_system_ref",
            "candidate_inputs",
            "causal_input_bindings",
            "required_outputs",
            "physical_output_bindings",
            "candidate_representation_ref",
            "geometry_domain_ref",
            "boundary_input_bindings",
            "initial_input_bindings",
            "time_horizon_binding",
            "operating_envelope_ref",
            "claim_scope_ref",
            "missing_or_extra_policy",
            "malformed_output_policy",
        ),
    )
    add(
        InstanceDistributionContract,
        "instance_distribution_contract",
        common
        + (
            "physical_system_ref",
            "candidate_output_ref",
            "population_role",
            "owning_claim_scope_ref",
            "target_population_binding",
            "proposal_population_binding",
            "support_contract",
            "law_semantics",
            "weighting_semantics",
            "stratification_binding",
            "applicability_refs",
            "exclusions",
            "rights_profile_ref",
            "permitted_use_refs",
            "restrictions",
            "disclosure_contract",
            "allowed_consumers",
            "population_provenance",
        ),
        (
            "applicability_refs",
            "exclusions",
            "permitted_use_refs",
            "restrictions",
            "allowed_consumers",
            "population_provenance",
        ),
    )
    add(
        TrainingSupportContract,
        "training_support_contract",
        common
        + (
            "physical_system_ref",
            "candidate_output_ref",
            "membership_contract",
            "physical_invariant_refs",
            "representation_invariant_refs",
            "permitted_source_materials",
            "permitted_generators",
            "rights_profile_ref",
            "permitted_use_refs",
            "restrictions",
            "provenance_requirements",
            "disclosure_contract",
            "unknown_or_invalid_policy",
        ),
        (
            "physical_invariant_refs",
            "representation_invariant_refs",
            "permitted_source_materials",
            "permitted_use_refs",
            "restrictions",
            "provenance_requirements",
        ),
    )
    add(
        SamplingPlan,
        "sampling_plan",
        common
        + (
            "sampling_role",
            "primary_population_ref",
            "selection_population_ref",
            "target_population_binding",
            "official_proposal_binding",
            "evidence_weight_binding",
            "query_population_binding",
            "observation_population_binding",
            "evidence_campaign_binding",
            "intended_estimand_or_reporting_ref",
            "finite_evidence_design",
            "full_design_law_ref",
            "stratified_allocation_binding",
            "query_observation_allocation_binding",
            "reference_fidelity_allocation_binding",
            "replication_dependence_policy_ref",
            "uncertainty_resolution_objectives_binding",
            "tail_resolution_objectives_binding",
            "minimum_subgroup_objectives_binding",
            "draw_order_semantics_ref",
            "stopping_extension_policy",
            "replacement_policy",
            "duplicate_policy",
            "inclusion_policy_ref",
            "exclusion_policy_ref",
            "censoring_policy_ref",
            "public_authored_facts",
            "protected_realization_fields",
            "statistical_qualification_requirements_ref",
            "plan_provenance_refs",
            "insufficient_or_failure_policy",
        ),
        (
            "public_authored_facts",
            "protected_realization_fields",
            "plan_provenance_refs",
        ),
    )
    add(
        CanonicalChallengeCase,
        "canonical_challenge_case",
        common
        + (
            "physical_system_ref",
            "candidate_output_ref",
            "primary_population_ref",
            "related_population_bindings",
            "sampling_plan_binding",
            "case_source",
            "case_representation_ref",
            "physical_payload_ref",
            "query_population_binding",
            "observation_population_binding",
            "evidence_campaign_binding",
            "intended_slot_binding",
            "prospective_censoring_policy_binding",
            "applicability_bindings",
            "disclosure_class",
            "disclosure_contract",
            "case_provenance_refs",
        ),
        (
            "related_population_bindings",
            "applicability_bindings",
            "case_provenance_refs",
        ),
    )
    return schema


def _empty_canonical_record():
    from .canonical import CanonicalRecord

    return CanonicalRecord("empty_payload", ())


def _inapplicability_payload(reason_ref: object):
    from .canonical import CanonicalRecord, owner_ref_to_canonical

    return CanonicalRecord(
        "not_applicable_payload",
        (("reason_ref", owner_ref_to_canonical(reason_ref)),),
    )


def _union_to_canonical(value: object):
    from .canonical import (
        CanonicalRecord,
        CanonicalTuple,
        CanonicalUInt64,
        CanonicalUnion,
        owner_ref_to_canonical,
    )
    from .cases import CaseSourceBinding
    from .evidence import (
        CaseStatePayload,
        CensoringTrigger,
        EvidenceRoleBinding,
        ReplacementPolicyBinding,
    )
    from .physical import (
        AxisExtent,
        CandidateInputRelation,
        CandidateOutputRelation,
        Presence,
    )
    from .populations import LawSemantics, StratificationRelation, WeightingSemantics
    from .sampling import (
        Allocation,
        CandidateOutcomeAccessBinding,
        ReplacementPolicy,
        ReplacementTrigger,
    )
    from .training_support import PermittedGeneratorBinding

    if type(value) is ApplicabilityBinding:
        if value.is_bound:
            return CanonicalUnion("BOUND", _canonical_value(value.value))
        return CanonicalUnion("NOT_APPLICABLE", _inapplicability_payload(value.value))
    if type(value) is AllowedConsumer:
        payload = (
            _empty_canonical_record()
            if value.payload is None
            else _canonical_value(value.payload)
        )
        return CanonicalUnion(value.kind.value, payload)
    if type(value) is AxisExtent:
        if value.kind.value == "FIXED":
            payload = CanonicalUInt64(value.fixed_extent)
        elif value.kind.value == "SYMBOLIC":
            from .canonical import CanonicalRecord, CanonicalText

            payload = CanonicalRecord(
                "symbolic_extent",
                (
                    ("axis_id", CanonicalText(value.symbolic_axis_id)),
                    ("constraint_ref", owner_ref_to_canonical(value.constraint_ref)),
                ),
            )
        else:
            payload = owner_ref_to_canonical(value.constraint_ref)
        return CanonicalUnion(value.kind.value, payload)
    if type(value) is Presence:
        payload = (
            _empty_canonical_record()
            if value.applicability_ref is None
            else owner_ref_to_canonical(value.applicability_ref)
        )
        return CanonicalUnion(value.kind.value, payload)
    if type(value) in {CandidateInputRelation, CandidateOutputRelation}:
        payload = (
            _empty_canonical_record()
            if value.adapter_contract_ref is None
            else owner_ref_to_canonical(value.adapter_contract_ref)
        )
        return CanonicalUnion(value.kind.value, payload)
    if type(value) in {LawSemantics, WeightingSemantics, StratificationRelation}:
        payload = value.payload if hasattr(value, "payload") else value.semantics_ref
        if getattr(value, "semantics_ref", object()) is None:
            payload = _empty_canonical_record()
        elif type(value) is WeightingSemantics and value.kind.value == "NOT_APPLICABLE":
            payload = _inapplicability_payload(payload)
        else:
            payload = _canonical_value(payload)
        return CanonicalUnion(value.kind.value, payload)
    if type(value) in {
        Allocation,
        ReplacementTrigger,
        CandidateOutcomeAccessBinding,
        CaseSourceBinding,
        EvidenceRoleBinding,
        CensoringTrigger,
        CaseStatePayload,
    }:
        payload = getattr(value, "payload", None)
        if type(value) is EvidenceRoleBinding:
            payload = value.hybrid_role_ref
            if payload is None:
                payload = _empty_canonical_record()
            tag = value.role.value
        elif payload is None:
            payload = _empty_canonical_record()
            tag = value.kind.value
        else:
            tag_value = getattr(value, "kind", getattr(value, "state", None))
            tag = tag_value.value
        if type(value) is Allocation and value.kind.value == "COUNT":
            payload = CanonicalUInt64(payload)
        else:
            payload = (
                payload
                if type(payload) is CanonicalRecord
                else _canonical_value(payload)
            )
        return CanonicalUnion(tag, payload)
    if type(value) is ReplacementPolicy:
        payload = (
            _empty_canonical_record()
            if value.payload is None
            else _canonical_value(value.payload)
        )
        return CanonicalUnion(value.kind.value, payload)
    if type(value) is ReplacementPolicyBinding:
        payload = (
            _empty_canonical_record()
            if value.policy_ref is None
            else owner_ref_to_canonical(value.policy_ref)
        )
        return CanonicalUnion(value.kind.value, payload)
    if type(value) is PermittedGeneratorBinding:
        payload = (
            CanonicalTuple(
                tuple(_canonical_value(item) for item in value.payload), set_like=True
            )
            if type(value.payload) is tuple
            else owner_ref_to_canonical(value.payload)
        )
        return CanonicalUnion(value.kind.value, payload)
    return None


def _canonical_value(value: object, *, set_like: bool = False):
    from enum import Enum as _Enum

    from .canonical import (
        CanonicalFloat64,
        CanonicalRecord,
        CanonicalText,
        CanonicalTuple,
        CanonicalUInt64,
        challenge_key_to_canonical,
        owner_ref_to_canonical,
        top_level_ref_to_canonical,
    )
    from .evidence import (
        CanonicalCaseDispositionRef,
        CensoringRecordRef,
        RealizedValidEvidenceRecordRef,
    )
    from .refs import is_owner_ref, is_top_level_ref

    if type(value) is bool:
        return value
    if type(value) is str:
        return CanonicalText(value)
    if type(value) is int:
        return CanonicalUInt64(value)
    if type(value) is float:
        return CanonicalFloat64(value)
    if isinstance(value, _Enum):
        return CanonicalText(value.value)
    if type(value) is ChallengeKey:
        return challenge_key_to_canonical(value)
    if is_owner_ref(value):
        return owner_ref_to_canonical(value)
    if is_top_level_ref(value):
        return top_level_ref_to_canonical(value)
    derived_ref_types = {
        CanonicalCaseDispositionRef: "canonical_case_disposition_ref",
        CensoringRecordRef: "censoring_record_ref",
        RealizedValidEvidenceRecordRef: "realized_valid_evidence_record_ref",
    }
    derived_ref_type = derived_ref_types.get(type(value))
    if derived_ref_type is not None:
        from .canonical import CanonicalNominalRef

        return CanonicalNominalRef(
            derived_ref_type,
            CanonicalRecord(
                derived_ref_type,
                (
                    (
                        "canonicalization_profile",
                        CanonicalText(value.canonicalization_profile),
                    ),
                    ("content_digest", CanonicalText(value.content_digest)),
                    ("record_type", CanonicalText(value.record_type)),
                    ("schema_version", CanonicalText(value.schema_version)),
                ),
            ),
        )
    if type(value) is tuple:
        return CanonicalTuple(
            tuple(_canonical_value(item) for item in value), set_like=set_like
        )
    union = _union_to_canonical(value)
    if union is not None:
        return union
    schema = _closed_record_schemas().get(type(value))
    if schema is None:
        raise TypeError("value is outside the closed authoring canonical schema")
    record_type, fields, set_fields = schema
    return CanonicalRecord(
        record_type,
        tuple(
            (
                name,
                _canonical_value(
                    object.__getattribute__(value, name), set_like=name in set_fields
                ),
            )
            for name in fields
        ),
    )


def authored_object_to_record(value: object):
    """Convert exactly one of the six top-level types to its closed record."""

    from .canonical import CanonicalRecord

    converted = _canonical_value(value)
    if type(converted) is not CanonicalRecord:
        raise TypeError("value is not a top-level authored identity object")
    allowed = {
        "physical_system_spec",
        "candidate_output_contract",
        "instance_distribution_contract",
        "sampling_plan",
        "training_support_contract",
        "canonical_challenge_case",
    }
    if converted.record_type not in allowed:
        raise TypeError("value is not a top-level authored identity object")
    return converted


def authored_object_canonical_bytes(value: object) -> bytes:
    from .canonical import canonical_document

    record = authored_object_to_record(value)
    return canonical_document(value.object_kind, value.schema_version, record)


def authored_object_to_ref(value: object):
    from .canonical import make_top_level_ref
    from .cases import CanonicalChallengeCase
    from .physical import CandidateOutputContract, PhysicalSystemSpec
    from .populations import InstanceDistributionContract
    from .refs import (
        CandidateOutputContractRef,
        CanonicalChallengeCaseRef,
        InstanceDistributionContractRef,
        PhysicalSystemSpecRef,
        SamplingPlanRef,
        TrainingSupportContractRef,
    )
    from .sampling import SamplingPlan
    from .training_support import TrainingSupportContract

    ref_type = {
        PhysicalSystemSpec: PhysicalSystemSpecRef,
        CandidateOutputContract: CandidateOutputContractRef,
        InstanceDistributionContract: InstanceDistributionContractRef,
        SamplingPlan: SamplingPlanRef,
        TrainingSupportContract: TrainingSupportContractRef,
        CanonicalChallengeCase: CanonicalChallengeCaseRef,
    }.get(type(value))
    if ref_type is None:
        raise TypeError("value is not one of the six exact authored objects")
    return make_top_level_ref(
        ref_type,
        canonical_bytes=authored_object_canonical_bytes(value),
        challenge_key=value.challenge_key,
        object_id=value.object_id,
        object_version=value.object_version,
        schema_version=value.schema_version,
        canonicalization_profile=value.canonicalization_profile,
        expected_population_role=(
            value.population_role.value
            if type(value) is InstanceDistributionContract
            else None
        ),
        disclosure_class=(
            value.disclosure_class.value
            if type(value) is CanonicalChallengeCase
            else None
        ),
    )


def _decode_nominal_ref(value: object) -> object:
    from .canonical import (
        CanonicalNominalRef,
        CanonicalText,
        owner_ref_from_canonical,
        top_level_ref_from_canonical,
    )
    from .evidence import (
        CanonicalCaseDispositionRef,
        CensoringRecordRef,
        RealizedValidEvidenceRecordRef,
    )
    from .refs import OBJECT_KINDS

    if type(value) is not CanonicalNominalRef:
        raise TypeError("expected canonical nominal ref")
    if value.ref_type in {f"{kind}_ref" for kind in OBJECT_KINDS}:
        return top_level_ref_from_canonical(value)
    derived_types = {
        "canonical_case_disposition_ref": CanonicalCaseDispositionRef,
        "censoring_record_ref": CensoringRecordRef,
        "realized_valid_evidence_record_ref": RealizedValidEvidenceRecordRef,
    }
    derived_type = derived_types.get(value.ref_type)
    if derived_type is not None:
        fields = value.record.field_map()
        if value.record.record_type != value.ref_type or set(fields) != {
            "canonicalization_profile",
            "content_digest",
            "record_type",
            "schema_version",
        }:
            raise ValueError("derived nominal ref fields are not exact")
        if any(type(node) is not CanonicalText for node in fields.values()):
            raise TypeError("derived nominal ref fields must be canonical text")
        return derived_type(
            fields["record_type"].value,
            fields["schema_version"].value,
            fields["canonicalization_profile"].value,
            fields["content_digest"].value,
        )
    return owner_ref_from_canonical(value, expected_kind=value.ref_type)


def _decode_union(
    value: object,
    expected: type[object],
    *,
    bound_expected: type[object] | None = None,
) -> object:
    from .canonical import (
        CanonicalRecord,
        CanonicalText,
        CanonicalTuple,
        CanonicalUInt64,
        CanonicalUnion,
    )
    from .cases import CaseSourceBinding, CaseSourceKind
    from .evidence import (
        CaseStatePayload,
        CensoringTrigger,
        CensoringTriggerKind,
        EvidenceRoleBinding,
        InfrastructureCensoringTrigger,
        ReplacementPolicyBinding,
        ReplacementPolicyBindingKind,
    )
    from .physical import (
        AxisExtent,
        AxisExtentKind,
        CandidateInputRelation,
        CandidateInputRelationKind,
        CandidateOutputRelation,
        CandidateOutputRelationKind,
        Presence,
        PresenceKind,
    )
    from .populations import (
        LawKind,
        LawSemantics,
        StratificationRelation,
        StratificationRelationKind,
        WeightingSemantics,
        WeightingSemanticsKind,
    )
    from .sampling import (
        Allocation,
        AllocationKind,
        CandidateOutcomeAccessBinding,
        CandidateOutcomeAccessKind,
        ReplacementPolicy,
        ReplacementPolicyKind,
        ReplacementTrigger,
        ReplacementTriggerKind,
    )
    from .training_support import PermittedGeneratorBinding, PermittedGeneratorKind

    if type(value) is not CanonicalUnion:
        raise TypeError("expected a canonical tagged union")
    tag = value.tag
    payload = value.payload

    def require_empty(candidate: object) -> None:
        if (
            type(candidate) is not CanonicalRecord
            or candidate.record_type != "empty_payload"
            or candidate.fields
        ):
            raise ValueError("zero-payload union requires exact empty_payload record")

    if expected is ApplicabilityBinding:
        if tag == "BOUND":
            decoded_bound = (
                _decode_union(payload, bound_expected)
                if bound_expected is not None
                else _decode_canonical_value(payload)
            )
            return ApplicabilityBinding.bound(decoded_bound)
        if tag != "NOT_APPLICABLE" or type(payload) is not CanonicalRecord:
            raise ValueError("invalid applicability union tag/payload")
        fields = payload.field_map()
        if payload.record_type != "not_applicable_payload" or set(fields) != {
            "reason_ref"
        }:
            raise ValueError("invalid not-applicable payload")
        return ApplicabilityBinding.not_applicable(
            _decode_nominal_ref(fields["reason_ref"])
        )
    if expected is AxisExtent:
        kind = AxisExtentKind(tag)
        if kind is AxisExtentKind.FIXED:
            if type(payload) is not CanonicalUInt64:
                raise TypeError("FIXED extent requires canonical UInt64")
            return AxisExtent(kind, fixed_extent=payload.value)
        if kind is AxisExtentKind.SYMBOLIC:
            if (
                type(payload) is not CanonicalRecord
                or payload.record_type != "symbolic_extent"
            ):
                raise TypeError("SYMBOLIC extent requires symbolic_extent record")
            fields = payload.field_map()
            if set(fields) != {"axis_id", "constraint_ref"}:
                raise ValueError("symbolic_extent fields are not exact")
            if type(fields["axis_id"]) is not CanonicalText:
                raise TypeError("symbolic axis ID must be canonical text")
            return AxisExtent(
                kind,
                symbolic_axis_id=fields["axis_id"].value,
                constraint_ref=_decode_nominal_ref(fields["constraint_ref"]),
            )
        return AxisExtent(kind, constraint_ref=_decode_nominal_ref(payload))
    if expected is Presence:
        kind = PresenceKind(tag)
        if kind is PresenceKind.REQUIRED:
            require_empty(payload)
        return Presence(
            kind,
            None if kind is PresenceKind.REQUIRED else _decode_nominal_ref(payload),
        )
    if expected in {CandidateInputRelation, CandidateOutputRelation}:
        kind_type = (
            CandidateInputRelationKind
            if expected is CandidateInputRelation
            else CandidateOutputRelationKind
        )
        kind = kind_type(tag)
        if tag == "IDENTITY":
            require_empty(payload)
        return expected(
            kind,
            None if tag == "IDENTITY" else _decode_nominal_ref(payload),
        )
    if expected is LawSemantics:
        return LawSemantics(LawKind(tag), _decode_canonical_value(payload))
    if expected is WeightingSemantics:
        kind = WeightingSemanticsKind(tag)
        if kind is WeightingSemanticsKind.NOT_APPLICABLE:
            if type(payload) is not CanonicalRecord:
                raise TypeError("weighting inapplicability requires an exact record")
            fields = payload.field_map()
            if payload.record_type != "not_applicable_payload" or set(fields) != {
                "reason_ref"
            }:
                raise ValueError("weighting inapplicability payload is not exact")
            decoded = _decode_nominal_ref(fields["reason_ref"])
        else:
            decoded = _decode_canonical_value(payload)
        return WeightingSemantics(kind, decoded)
    if expected is StratificationRelation:
        kind = StratificationRelationKind(tag)
        if kind is StratificationRelationKind.DISJOINT_EXHAUSTIVE:
            require_empty(payload)
        return StratificationRelation(
            kind,
            None
            if kind is StratificationRelationKind.DISJOINT_EXHAUSTIVE
            else _decode_nominal_ref(payload),
        )
    if expected is Allocation:
        kind = AllocationKind(tag)
        decoded = (
            payload.value
            if kind is AllocationKind.COUNT and type(payload) is CanonicalUInt64
            else _decode_canonical_value(payload)
        )
        return Allocation(kind, decoded)
    if expected is ReplacementTrigger:
        kind = ReplacementTriggerKind(tag)
        decoded = _decode_canonical_value(payload)
        if kind is ReplacementTriggerKind.CENSORED:
            decoded = CensoringReason(decoded)
        return ReplacementTrigger(kind, decoded)
    if expected is ReplacementPolicy:
        kind = ReplacementPolicyKind(tag)
        if kind is ReplacementPolicyKind.NEVER:
            require_empty(payload)
        return ReplacementPolicy(
            kind,
            None
            if kind is ReplacementPolicyKind.NEVER
            else _decode_canonical_value(payload),
        )
    if expected is CandidateOutcomeAccessBinding:
        return CandidateOutcomeAccessBinding(
            CandidateOutcomeAccessKind(tag), _decode_canonical_value(payload)
        )
    if expected is PermittedGeneratorBinding:
        kind = PermittedGeneratorKind(tag)
        decoded = (
            tuple(_decode_canonical_value(item) for item in payload.items)
            if type(payload) is CanonicalTuple
            else _decode_nominal_ref(payload)
        )
        return PermittedGeneratorBinding(kind, decoded)
    if expected is CaseSourceBinding:
        return CaseSourceBinding(CaseSourceKind(tag), _decode_canonical_value(payload))
    if expected is EvidenceRoleBinding:
        role = EvidenceRole(tag)
        if role is EvidenceRole.REGISTERED_HYBRID:
            return EvidenceRoleBinding(role, _decode_nominal_ref(payload))
        require_empty(payload)
        return EvidenceRoleBinding(role)
    if expected is CensoringTrigger:
        kind = CensoringTriggerKind(tag)
        decoded = (
            _decode_record(payload)
            if kind is CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE
            else _decode_nominal_ref(payload)
        )
        if (
            kind is CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE
            and type(decoded) is not InfrastructureCensoringTrigger
        ):
            raise TypeError("infrastructure censoring trigger has wrong payload")
        return CensoringTrigger(kind, decoded)
    if expected is CaseStatePayload:
        return CaseStatePayload(CaseState(tag), _decode_canonical_value(payload))
    if expected is ReplacementPolicyBinding:
        kind = ReplacementPolicyBindingKind(tag)
        if kind is ReplacementPolicyBindingKind.PLAN_NEVER:
            require_empty(payload)
            return ReplacementPolicyBinding(kind, None)
        return ReplacementPolicyBinding(kind, _decode_nominal_ref(payload))
    if expected is AllowedConsumer:
        kind = AllowedConsumerKind(tag)
        if kind is AllowedConsumerKind.REALIZED_EVIDENCE_DERIVATION:
            require_empty(payload)
            decoded_payload = None
        elif kind is AllowedConsumerKind.SAMPLING_PLAN:
            decoded_payload = SamplingRole(_decode_canonical_value(payload))
        elif kind is AllowedConsumerKind.CANONICAL_CASE:
            decoded_payload = CasePopulationUse(_decode_canonical_value(payload))
        elif kind is AllowedConsumerKind.CASE_EVIDENCE:
            decoded_payload = EvidenceRole(_decode_canonical_value(payload))
        else:
            decoded_payload = _decode_canonical_value(payload)
        return AllowedConsumer(kind, decoded_payload)
    raise TypeError("union type is outside the closed authored-object decoder")


def _field_union_type(cls: type[object], field: str) -> type[object] | None:
    from .cases import (
        CanonicalChallengeCase,
        CaseSourceBinding,
        InternalCaseIdentityProjection,
        ProtectedCaseIdentityProjection,
    )
    from .evidence import (
        CanonicalCaseDisposition,
        CaseEvidenceBinding,
        CaseStatePayload,
        CensoringRecord,
        CensoringTrigger,
        EvidenceRoleBinding,
        EvidenceScopeBinding,
        RealizedValidEvidenceRecord,
        ReplacementDecision,
        ReplacementPolicyBinding,
    )
    from .physical import (
        AssumptionClause,
        AxisContract,
        AxisExtent,
        BoundaryRegionClause,
        CandidateInputBinding,
        CandidateInputRelation,
        CandidateOutputBinding,
        CandidateOutputContract,
        CandidateOutputRelation,
        ConditionInputBinding,
        InitialStateClause,
        PhysicalSystemSpec,
        Presence,
        TimeContract,
        ValueFieldContract,
    )
    from .populations import (
        InstanceDistributionContract,
        LawSemantics,
        StratificationContract,
        StratificationRelation,
        StratumContract,
        WeightingPayload,
        WeightingSemantics,
    )
    from .sampling import (
        Allocation,
        CandidateOutcomeAccessBinding,
        FiniteEvidenceDesign,
        FractionAllocation,
        ProspectiveStoppingExtensionPolicy,
        ReplacementPolicy,
        SamplingPlan,
        StratumAllocation,
    )
    from .training_support import PermittedGeneratorBinding, TrainingSupportContract

    special = {
        (AxisContract, "extent"): AxisExtent,
        (ValueFieldContract, "presence"): Presence,
        (CandidateInputBinding, "relation"): CandidateInputRelation,
        (ConditionInputBinding, "relation"): CandidateInputRelation,
        (CandidateOutputBinding, "relation"): CandidateOutputRelation,
        (InstanceDistributionContract, "law_semantics"): LawSemantics,
        (InstanceDistributionContract, "weighting_semantics"): WeightingSemantics,
        (StratificationContract, "relation"): StratificationRelation,
        (StratumAllocation, "allocation"): Allocation,
        (
            ProspectiveStoppingExtensionPolicy,
            "candidate_outcome_access_binding",
        ): CandidateOutcomeAccessBinding,
        (SamplingPlan, "replacement_policy"): ReplacementPolicy,
        (TrainingSupportContract, "permitted_generators"): PermittedGeneratorBinding,
        (CanonicalChallengeCase, "case_source"): CaseSourceBinding,
        (ReplacementDecision, "policy_binding"): ReplacementPolicyBinding,
        (CanonicalCaseDisposition, "state_payload"): CaseStatePayload,
        (CensoringRecord, "trigger_failure_binding"): CensoringTrigger,
        (CaseEvidenceBinding, "evidence_role"): EvidenceRoleBinding,
    }
    if (cls, field) in special:
        return special[(cls, field)]
    applicability_pairs = {
        (PhysicalSystemSpec, "supersedes"),
        (CandidateOutputContract, "supersedes"),
        (InstanceDistributionContract, "supersedes"),
        (SamplingPlan, "supersedes"),
        (TrainingSupportContract, "supersedes"),
        (CanonicalChallengeCase, "supersedes"),
        (ValueFieldContract, "geometry_binding"),
        (AssumptionClause, "applicability"),
        (BoundaryRegionClause, "causal_input_binding"),
        (BoundaryRegionClause, "applicability"),
        (InitialStateClause, "causal_input_binding"),
        (InitialStateClause, "applicability"),
        (TimeContract, "time_coordinate_binding"),
        (TimeContract, "horizon_binding"),
        (WeightingPayload, "proposal_population_binding"),
        (StratumContract, "hierarchy_binding"),
        (InstanceDistributionContract, "target_population_binding"),
        (InstanceDistributionContract, "proposal_population_binding"),
        (InstanceDistributionContract, "stratification_binding"),
        (StratumAllocation, "selection_stratum_binding"),
        (FractionAllocation, "zero_allocation_binding"),
        (FiniteEvidenceDesign, "budget_binding"),
        (FiniteEvidenceDesign, "extension_ceiling_binding"),
        (ProspectiveStoppingExtensionPolicy, "extension_rule_binding"),
        (ProspectiveStoppingExtensionPolicy, "interim_look_binding"),
        (ProspectiveStoppingExtensionPolicy, "sequential_allocation_binding"),
        (ProspectiveStoppingExtensionPolicy, "coverage_qualification_binding"),
        (SamplingPlan, "target_population_binding"),
        (SamplingPlan, "official_proposal_binding"),
        (SamplingPlan, "evidence_weight_binding"),
        (SamplingPlan, "query_population_binding"),
        (SamplingPlan, "observation_population_binding"),
        (SamplingPlan, "evidence_campaign_binding"),
        (SamplingPlan, "stratified_allocation_binding"),
        (SamplingPlan, "query_observation_allocation_binding"),
        (SamplingPlan, "reference_fidelity_allocation_binding"),
        (SamplingPlan, "uncertainty_resolution_objectives_binding"),
        (SamplingPlan, "tail_resolution_objectives_binding"),
        (SamplingPlan, "minimum_subgroup_objectives_binding"),
        (CanonicalChallengeCase, "sampling_plan_binding"),
        (CanonicalChallengeCase, "query_population_binding"),
        (CanonicalChallengeCase, "observation_population_binding"),
        (CanonicalChallengeCase, "evidence_campaign_binding"),
        (CanonicalChallengeCase, "intended_slot_binding"),
        (CanonicalChallengeCase, "prospective_censoring_policy_binding"),
        (ProtectedCaseIdentityProjection, "realized_stratum_binding"),
        (ProtectedCaseIdentityProjection, "replacement_linkage"),
        (InternalCaseIdentityProjection, "sampling_plan_binding"),
        (InternalCaseIdentityProjection, "evidence_campaign_binding"),
        (EvidenceScopeBinding, "evidence_campaign_binding"),
        (EvidenceScopeBinding, "query_population_binding"),
        (EvidenceScopeBinding, "observation_population_binding"),
        (EvidenceScopeBinding, "measurement_applicability_binding"),
        (ReplacementDecision, "trigger_binding"),
        (ReplacementDecision, "lineage_binding"),
        (CanonicalCaseDisposition, "case_ref_binding"),
        (CanonicalCaseDisposition, "attempt_commitment_binding"),
        (CensoringRecord, "evidence_campaign_binding"),
        (CensoringRecord, "missingness_adjustment_binding"),
        (CaseEvidenceBinding, "public_projection_binding"),
        (CaseEvidenceBinding, "policy_qualification_binding"),
        (RealizedValidEvidenceRecord, "target_population_binding"),
        (RealizedValidEvidenceRecord, "official_proposal_binding"),
        (RealizedValidEvidenceRecord, "evidence_weight_binding"),
        (RealizedValidEvidenceRecord, "missingness_adjustment_binding"),
        (RealizedValidEvidenceRecord, "sensitivity_analysis_binding"),
    }
    if (cls, field) in applicability_pairs:
        return ApplicabilityBinding
    return None


def _field_enum_type(cls: type[object], field: str) -> type[Enum] | None:
    from .cases import CanonicalChallengeCase, PublicCaseFactBinding
    from .evidence import (
        CanonicalCaseDisposition,
        CensoringRecord,
        ReplacementDecision,
        ReplacementDecisionKind,
    )
    from .physical import TimeContract
    from .populations import (
        InstanceDistributionContract,
        StratificationContract,
        WeightingPayload,
    )
    from .sampling import FiniteEvidenceDesign, SamplingPlan

    return {
        (TimeContract, "mode"): TimeMode,
        (InstanceDistributionContract, "population_role"): PopulationRole,
        (StratificationContract, "basis_population_role"): PopulationRole,
        (WeightingPayload, "weighting_role"): WeightingRole,
        (FiniteEvidenceDesign, "design_mode"): FiniteDesignMode,
        (SamplingPlan, "sampling_role"): SamplingRole,
        (CanonicalChallengeCase, "disclosure_class"): DisclosureClass,
        (PublicCaseFactBinding, "fact_kind"): PublicCaseFactKind,
        (ReplacementDecision, "decision"): ReplacementDecisionKind,
        (CanonicalCaseDisposition, "case_state"): CaseState,
        (CensoringRecord, "censoring_reason"): CensoringReason,
        (DownstreamPopulationConsumer, "owner"): DownstreamPopulationOwner,
    }.get((cls, field))


def _applicability_bound_union_type(
    cls: type[object], field: str
) -> type[object] | None:
    """Return the exact nested union type for BOUND applicability payloads."""

    from .evidence import ReplacementDecision
    from .sampling import ReplacementTrigger

    return {
        (ReplacementDecision, "trigger_binding"): ReplacementTrigger,
    }.get((cls, field))


def _decode_record(
    value: object,
    *,
    derived_document: bool = False,
    realized_authorization: tuple[object, tuple[object, ...]] | None = None,
) -> object:
    from .canonical import CanonicalRecord
    from .cases import CanonicalChallengeCase
    from .evidence import (
        RealizedValidEvidenceRecord,
        construct_realized_valid_evidence,
    )
    from .physical import (
        CandidateOutputContract,
        PhysicalSystemSpec,
        ValueFieldContract,
    )
    from .populations import InstanceDistributionContract
    from .sampling import RegisteredReplacementPolicy, SamplingPlan
    from .training_support import TrainingSupportContract

    if type(value) is not CanonicalRecord:
        raise TypeError("expected exact canonical record")
    schemas = _closed_record_schemas()
    reverse = {schema[0]: (cls, schema) for cls, schema in schemas.items()}
    if value.record_type not in reverse:
        raise ValueError("record type is outside the closed authoring schema")
    cls, (_, names, _) = reverse[value.record_type]
    fields = value.field_map()
    if set(fields) != set(names):
        raise ValueError("record fields are not the exact closed schema")
    kwargs: dict[str, object] = {}
    for name in names:
        node = fields[name]
        union_type = _field_union_type(cls, name)
        if cls is InstanceDistributionContract and name == "allowed_consumers":
            from .canonical import CanonicalTuple

            if type(node) is not CanonicalTuple:
                raise TypeError("allowed_consumers must be a canonical tuple")
            decoded = tuple(_decode_union(item, AllowedConsumer) for item in node.items)
        elif cls is RegisteredReplacementPolicy and name == "triggers":
            from .canonical import CanonicalTuple
            from .sampling import ReplacementTrigger

            if type(node) is not CanonicalTuple:
                raise TypeError("replacement triggers must be a canonical tuple")
            decoded = tuple(
                _decode_union(item, ReplacementTrigger) for item in node.items
            )
        elif union_type is not None:
            decoded = _decode_union(
                node,
                union_type,
                bound_expected=_applicability_bound_union_type(cls, name),
            )
        else:
            decoded = _decode_canonical_value(node)
        enum_type = _field_enum_type(cls, name)
        if enum_type is not None:
            decoded = enum_type(decoded)
        if type(decoded) is tuple:
            if cls is ValueFieldContract and name == "precision_contract":
                decoded = tuple(PrecisionLiteral(item) for item in decoded)
            elif cls is SamplingPlan and name == "public_authored_facts":
                decoded = tuple(PublicPlanFactKind(item) for item in decoded)
            elif cls is SamplingPlan and name == "protected_realization_fields":
                decoded = tuple(ProtectedPlanFieldKind(item) for item in decoded)
        kwargs[name] = decoded
    if cls is RealizedValidEvidenceRecord:
        if not derived_document or realized_authorization is None:
            raise PermissionError(
                "realized evidence requires accounting-authorized loading"
            )
        capability, dispositions = realized_authorization
        supplied_disposition_refs = kwargs.pop("disposition_refs")
        supplied_manifest_ref = kwargs.pop("complete_unit_manifest_ref")
        supplied_authority_ref = kwargs.pop("construction_authority_ref")
        supplied_audit_refs = kwargs.pop("construction_audit_refs")
        result = construct_realized_valid_evidence(
            capability,
            dispositions,
            **kwargs,
        )
        if (
            result.disposition_refs != supplied_disposition_refs
            or result.complete_unit_manifest_ref != supplied_manifest_ref
            or result.construction_authority_ref != supplied_authority_ref
            or result.construction_audit_refs != supplied_audit_refs
        ):
            raise ValueError(
                "loaded realized record differs from verified accounting state"
            )
    else:
        result = cls(**kwargs)
    if (
        type(result)
        not in {
            PhysicalSystemSpec,
            CandidateOutputContract,
            InstanceDistributionContract,
            SamplingPlan,
            TrainingSupportContract,
            CanonicalChallengeCase,
        }
        and result.__class__ is not cls
    ):
        raise TypeError("decoded subordinate record changed nominal type")
    return result


def derived_evidence_from_record(
    record: object,
    *,
    realized_authorization: tuple[object, tuple[object, ...]] | None = None,
) -> object:
    """Reconstruct one exact digest-verified derived document record."""

    from .evidence import (
        CanonicalCaseDisposition,
        CensoringRecord,
        RealizedValidEvidenceRecord,
    )

    value = _decode_record(
        record,
        derived_document=True,
        realized_authorization=realized_authorization,
    )
    if type(value) not in {
        CanonicalCaseDisposition,
        CensoringRecord,
        RealizedValidEvidenceRecord,
    }:
        raise TypeError("record is not a closed derived-evidence document")
    return value


def _decode_canonical_value(value: object) -> object:
    from .canonical import (
        CanonicalFloat64,
        CanonicalNominalRef,
        CanonicalRecord,
        CanonicalText,
        CanonicalTuple,
        CanonicalUInt64,
    )

    if type(value) is bool:
        return value
    if type(value) is CanonicalText:
        return value.value
    if type(value) is CanonicalUInt64 or type(value) is CanonicalFloat64:
        return value.value
    if type(value) is CanonicalNominalRef:
        return _decode_nominal_ref(value)
    if type(value) is CanonicalTuple:
        return tuple(_decode_canonical_value(item) for item in value.items)
    if type(value) is CanonicalRecord:
        from .canonical import challenge_key_from_canonical

        if value.record_type == "challenge_key":
            return challenge_key_from_canonical(value)
        return _decode_record(value)
    raise TypeError("canonical node is outside the closed object decoder")


def authored_object_from_record(*, object_kind: str, record: object) -> object:
    """Reconstruct one exact authored object with closed field rejection."""

    from .canonical import CanonicalRecord

    if type(object_kind) is not str:
        raise TypeError("object_kind must be exact str")
    if type(record) is not CanonicalRecord or record.record_type != object_kind:
        raise ValueError("framed object kind and record type differ")
    value = _decode_record(record)
    if value.object_kind != object_kind:
        raise ValueError("decoded object kind differs from framing")
    return value

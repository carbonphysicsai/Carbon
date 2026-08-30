"""Exact nominal references for B-02A scientific-authoring artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypeAlias

from carbon.authoring.errors import AuthoringValidationError
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.registry import ChallengeKey

OBJECT_KINDS = (
    "physical_system_spec",
    "candidate_output_contract",
    "instance_distribution_contract",
    "sampling_plan",
    "training_support_contract",
    "canonical_challenge_case",
)

POPULATION_ROLES = (
    "TARGET_WORKLOAD_P",
    "OFFICIAL_PROPOSAL_Q",
    "EVIDENCE_WEIGHT_W",
    "STRESS",
    "PRACTICE",
    "PRODUCT_QUALIFICATION",
    "DEPLOYMENT",
    "QUERY",
    "OBSERVATION",
    "EVIDENCE_CAMPAIGN",
)

CASE_DISCLOSURE_CLASSES = ("INTERNAL", "PROTECTED")

# This is the closed v1 owner-kind registry.  The generated runtime classes are
# distinct nominal types; the generic notation PinnedOwnerRef<K> exists only in
# the specification and is deliberately not exposed as a runtime value type.
OWNER_REF_KINDS = (
    "accounting_authority",
    "aggregation_policy",
    "allocation_rule",
    "allocation_sum_semantics",
    "allocation_total_semantics",
    "analytic_construction",
    "applicability",
    "applicability_evidence",
    "applicability_reason",
    "apportionment_rule",
    "audit_evidence",
    "audit_semantics",
    "authoring_origin_evidence",
    "authoring_registration",
    "authoring_revocation",
    "authority_evidence",
    "axis_constraint",
    "base_evidence_requirement",
    "base_measure",
    "blinding_policy",
    "case_source",
    "censoring_accounting",
    "censoring_authority",
    "censoring_policy",
    "claim_scope",
    "coverage_qualification",
    "denominator_effect",
    "denominator_policy",
    "disclosure_policy",
    "distribution_conformance",
    "downstream_population_consumer_contract",
    "draft_authority",
    "draw_order_semantics",
    "duplicate_rule",
    "estimand_scope",
    "evidence_acquisition_operation",
    "evidence_artifact",
    "evidence_binding_authority",
    "evidence_budget",
    "evidence_campaign",
    "exclusion_assessment",
    "exclusion_contract",
    "exclusion_policy",
    "experiment_integrity_event",
    "experiment_corrupted",
    "experiment_source",
    "extension_ceiling",
    "extension_rule",
    "fixture_registration",
    "full_design_law",
    "generation_event",
    "generation_failure",
    "generation_failure_accounting",
    "generator",
    "geometry_domain",
    "geometry_region",
    "hybrid_evidence_role",
    "inclusion_probability_accounting",
    "inclusion_policy",
    "industrial_source",
    "infrastructure_failure",
    "intended_estimand_or_reporting",
    "interim_look_rule",
    "internal_service_scope",
    "maximum_attempt_rule",
    "measurement_applicability",
    "measurement_failure",
    "measurement_resource_limit",
    "measurement_timeout",
    "measurement_unavailable",
    "member_set",
    "membership_decision",
    "membership_evidence",
    "membership_proof",
    "membership_rule",
    "missingness_adjustment",
    "modification_authority",
    "multiplicity_semantics",
    "no_generator_reason",
    "no_prevalence_claim",
    "non_probability_reason",
    "nonexhaustive_semantics",
    "normalization_claim",
    "observation_failure",
    "observation_missing",
    "observation_source",
    "observation_timeout",
    "opaque_public_case_handle",
    "operating_envelope",
    "origin_composition_audit",
    "overlap_accounting",
    "overlap_semantics",
    "permitted_use",
    "physical_support",
    "policy_authority",
    "population_relationship",
    "probability_law",
    "projection_issuance",
    "qualification_evidence_bundle",
    "prospective_exclusion_contract",
    "protected_attempt_commitment",
    "protected_case_payload",
    "protected_intended_evidence_unit",
    "protected_intended_slot",
    "protected_replacement_lineage",
    "protected_unit_manifest",
    "provenance",
    "public_case_fact",
    "query_observation_allocation",
    "query_observation_provenance",
    "realized_evidence_accounting",
    "reference_disputed",
    "reference_failure",
    "reference_fidelity_allocation",
    "reference_numerical_failure",
    "reference_qualification_policy",
    "reference_resource_limit",
    "reference_timeout",
    "reference_unavailable",
    "release_policy",
    "replacement_accounting",
    "replacement_eligible_generation_failure_reason",
    "replacement_policy",
    "replacement_selection_law",
    "replacement_stratum_treatment",
    "replication_dependence_policy",
    "representation",
    "representation_adapter",
    "representation_support",
    "restriction",
    "rights_profile",
    "sampling_unit",
    "scientific_authority",
    "screening_design",
    "semantic_clause",
    "semantic_equivalence",
    "sensitivity_analysis",
    "sequential_allocation_rule",
    "source_material",
    "source_material_role",
    "stopping_rule",
    "statistical_qualification_requirement",
    "statistics_objective",
    "stratum_assignment",
    "stratum_hierarchy",
    "stratum_mapping",
    "stratum_unassigned_rule",
    "support_boundary",
    "tie_rule",
    "unit",
    "verification_construction",
    "weight_effect",
    "weight_normalization",
    "weighting_rule",
    "zero_allocation_authority",
)


def _wrong(code: str, message: str, path: str) -> AuthoringValidationError:
    return AuthoringValidationError(code, message, path=path)


@dataclass(frozen=True, slots=True)
class ChallengeScope:
    """Owner reference scope bound to one exact Challenge version."""

    challenge_key: ChallengeKey

    def __post_init__(self) -> None:
        if type(self) is not ChallengeScope:
            raise _wrong(
                "authoring.scope_subclass_rejected",
                "challenge owner scope must have its exact nominal type",
                "/scope_binding",
            )
        object.__setattr__(
            self, "challenge_key", reconstruct_challenge_key(self.challenge_key)
        )


@dataclass(frozen=True, slots=True)
class GlobalScope:
    """Owner reference scope not tied to one Challenge."""

    def __post_init__(self) -> None:
        if type(self) is not GlobalScope:
            raise _wrong(
                "authoring.scope_subclass_rejected",
                "global owner scope must have its exact nominal type",
                "/scope_binding",
            )


OwnerScopeBinding: TypeAlias = ChallengeScope | GlobalScope


@dataclass(frozen=True, slots=True)
class _OwnerRefBase:
    scope_binding: OwnerScopeBinding
    object_id: str
    object_version: str
    content_digest: str

    REF_KIND: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _OWNER_REF_TYPES.get(self.REF_KIND)
        if expected is None or type(self) is not expected:
            raise _wrong(
                "authoring.owner_ref_nominal_type_invalid",
                "owner ref must have its exact closed nominal kind",
                "/ref_kind",
            )
        if type(self.scope_binding) is ChallengeScope:
            owned_scope: OwnerScopeBinding = ChallengeScope(
                self.scope_binding.challenge_key
            )
        elif type(self.scope_binding) is GlobalScope:
            owned_scope = GlobalScope()
        else:
            raise _wrong(
                "authoring.owner_ref_scope_invalid",
                "owner ref scope must be an exact closed scope variant",
                "/scope_binding",
            )
        object.__setattr__(self, "scope_binding", owned_scope)
        object.__setattr__(
            self, "object_id", validate_canonical_id(self.object_id, "object_id")
        )
        object.__setattr__(
            self,
            "object_version",
            validate_version_token(self.object_version, "object_version"),
        )
        object.__setattr__(
            self,
            "content_digest",
            validate_tagged_sha256(self.content_digest, "content_digest"),
        )

    @property
    def ref_kind(self) -> str:
        return self.REF_KIND


_OWNER_REF_TYPES: dict[str, type[_OwnerRefBase]] = {}


def _owner_ref_class_name(kind: str) -> str:
    return "".join(part.capitalize() for part in kind.split("_")) + "Ref"


for _owner_kind in OWNER_REF_KINDS:
    _owner_type = type(
        _owner_ref_class_name(_owner_kind),
        (_OwnerRefBase,),
        {
            "__module__": __name__,
            "__slots__": (),
            "REF_KIND": _owner_kind,
        },
    )
    _OWNER_REF_TYPES[_owner_kind] = _owner_type
    globals()[_owner_type.__name__] = _owner_type


def owner_ref_type(kind: object) -> type[_OwnerRefBase]:
    """Return the one exact nominal class for a closed v1 owner-ref kind."""
    if type(kind) is not str or kind not in _OWNER_REF_TYPES:
        raise _wrong(
            "authoring.owner_ref_kind_unknown",
            "owner ref kind is not in the closed v1 registry",
            "/ref_kind",
        )
    return _OWNER_REF_TYPES[kind]


def owner_ref(
    kind: object,
    *,
    scope_binding: OwnerScopeBinding,
    object_id: object,
    object_version: object,
    content_digest: object,
) -> _OwnerRefBase:
    """Construct the exact nominal owner ref selected by a closed kind literal."""
    ref_type = owner_ref_type(kind)
    return ref_type(scope_binding, object_id, object_version, content_digest)


def is_owner_ref(value: object) -> bool:
    """Return whether a value has one exact closed v1 owner-ref type."""
    return any(type(value) is ref_type for ref_type in _OWNER_REF_TYPES.values())


def require_owner_ref(value: object, kind: object) -> _OwnerRefBase:
    """Defensively reconstruct an exact owner ref of the required nominal kind."""
    expected_type = owner_ref_type(kind)
    if type(value) is not expected_type:
        raise _wrong(
            "authoring.owner_ref_kind_mismatch",
            "owner ref has the wrong exact nominal kind",
            "/ref_kind",
        )
    return expected_type(
        value.scope_binding,
        value.object_id,
        value.object_version,
        value.content_digest,
    )


@dataclass(frozen=True, slots=True)
class _TopLevelRefBase:
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    schema_version: str
    canonicalization_profile: str
    content_digest: str

    OBJECT_KIND: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _TOP_LEVEL_REF_TYPES_BY_KIND.get(self.OBJECT_KIND)
        if expected is None or type(self) is not expected:
            raise _wrong(
                "authoring.top_level_ref_nominal_type_invalid",
                "top-level ref must have its exact closed nominal type",
                "/object_kind",
            )
        object.__setattr__(
            self, "challenge_key", reconstruct_challenge_key(self.challenge_key)
        )
        object.__setattr__(
            self, "object_id", validate_canonical_id(self.object_id, "object_id")
        )
        object.__setattr__(
            self,
            "object_version",
            validate_version_token(self.object_version, "object_version"),
        )
        schema_version = validate_version_token(self.schema_version, "schema_version")
        if schema_version != AUTHORING_SCHEMA_VERSION:
            raise _wrong(
                "authoring.schema_version_unsupported",
                "the v1 top-level ref contract supports only schema version 1.0",
                "/schema_version",
            )
        object.__setattr__(self, "schema_version", schema_version)
        if (
            type(self.canonicalization_profile) is not str
            or self.canonicalization_profile != CANONICALIZATION_PROFILE
        ):
            raise _wrong(
                "authoring.canonicalization_profile_invalid",
                "top-level ref has an unknown canonicalization profile",
                "/canonicalization_profile",
            )
        object.__setattr__(
            self,
            "content_digest",
            validate_tagged_sha256(self.content_digest, "content_digest"),
        )

    @property
    def object_kind(self) -> str:
        return self.OBJECT_KIND

    @property
    def ref_type(self) -> str:
        return f"{self.OBJECT_KIND}_ref"


@dataclass(frozen=True, slots=True)
class PhysicalSystemSpecRef(_TopLevelRefBase):
    OBJECT_KIND: ClassVar[str] = "physical_system_spec"


@dataclass(frozen=True, slots=True)
class CandidateOutputContractRef(_TopLevelRefBase):
    OBJECT_KIND: ClassVar[str] = "candidate_output_contract"


@dataclass(frozen=True, slots=True)
class InstanceDistributionContractRef(_TopLevelRefBase):
    expected_population_role: str

    OBJECT_KIND: ClassVar[str] = "instance_distribution_contract"

    def __post_init__(self) -> None:
        _TopLevelRefBase.__post_init__(self)
        if (
            type(self.expected_population_role) is not str
            or self.expected_population_role not in POPULATION_ROLES
        ):
            raise _wrong(
                "authoring.population_role_invalid",
                "distribution ref has an unknown expected population role",
                "/expected_population_role",
            )


@dataclass(frozen=True, slots=True)
class SamplingPlanRef(_TopLevelRefBase):
    OBJECT_KIND: ClassVar[str] = "sampling_plan"


@dataclass(frozen=True, slots=True)
class TrainingSupportContractRef(_TopLevelRefBase):
    OBJECT_KIND: ClassVar[str] = "training_support_contract"


@dataclass(frozen=True, slots=True)
class CanonicalChallengeCaseRef(_TopLevelRefBase):
    disclosure_class: str

    OBJECT_KIND: ClassVar[str] = "canonical_challenge_case"

    def __post_init__(self) -> None:
        _TopLevelRefBase.__post_init__(self)
        if (
            type(self.disclosure_class) is not str
            or self.disclosure_class not in CASE_DISCLOSURE_CLASSES
        ):
            raise _wrong(
                "authoring.disclosure_class_invalid",
                "case ref disclosure class must be INTERNAL or PROTECTED",
                "/disclosure_class",
            )


TopLevelObjectRef: TypeAlias = (
    PhysicalSystemSpecRef
    | CandidateOutputContractRef
    | InstanceDistributionContractRef
    | SamplingPlanRef
    | TrainingSupportContractRef
    | CanonicalChallengeCaseRef
)

TOP_LEVEL_REF_TYPES = (
    PhysicalSystemSpecRef,
    CandidateOutputContractRef,
    InstanceDistributionContractRef,
    SamplingPlanRef,
    TrainingSupportContractRef,
    CanonicalChallengeCaseRef,
)

_TOP_LEVEL_REF_TYPES_BY_KIND: dict[str, type[_TopLevelRefBase]] = {
    ref_type.OBJECT_KIND: ref_type for ref_type in TOP_LEVEL_REF_TYPES
}


def top_level_ref_type(object_kind: object) -> type[_TopLevelRefBase]:
    """Resolve a closed authored object kind to its exact nominal ref class."""
    if type(object_kind) is not str or object_kind not in _TOP_LEVEL_REF_TYPES_BY_KIND:
        raise _wrong(
            "authoring.object_kind_unknown",
            "object kind is not in the closed B-02A registry",
            "/object_kind",
        )
    return _TOP_LEVEL_REF_TYPES_BY_KIND[object_kind]


def is_top_level_ref(value: object) -> bool:
    """Return whether a value has one exact top-level ref type."""
    return any(type(value) is ref_type for ref_type in TOP_LEVEL_REF_TYPES)


def reconstruct_top_level_ref(value: object) -> TopLevelObjectRef:
    """Defensively reconstruct one exact top-level ref without kind coercion."""
    if not is_top_level_ref(value):
        raise _wrong(
            "authoring.top_level_ref_type_invalid",
            "value is not an exact top-level authoring ref",
            "/ref_type",
        )
    common = (
        value.challenge_key,
        value.object_id,
        value.object_version,
        value.schema_version,
        value.canonicalization_profile,
        value.content_digest,
    )
    if type(value) is InstanceDistributionContractRef:
        return InstanceDistributionContractRef(*common, value.expected_population_role)
    if type(value) is CanonicalChallengeCaseRef:
        return CanonicalChallengeCaseRef(*common, value.disclosure_class)
    return type(value)(*common)

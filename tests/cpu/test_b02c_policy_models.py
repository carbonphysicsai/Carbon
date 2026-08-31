"""Exact top-level B-02C policy-model and ownership-boundary tests."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from carbon.authoring.refs import ChallengeScope, GlobalScope, owner_ref
from carbon.construction.model import (
    CompilerIdentity,
    EnvironmentPin,
    StaticResourceDimension,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
)
from carbon.registry import ChallengeKey
from carbon.resource_policy.errors import ResourcePolicyInputRejected
from carbon.resource_policy.model import (
    AtEnforcementPoint,
    DeclaredResourceCeiling,
    EnforcementMode,
    EnforcementPoint,
    FixtureOfficialShapedResourceContext,
    FixturePracticeResourceContext,
    FixtureResourceAvailability,
    FixtureResourceDecision,
    FixtureResourceProvenance,
    NoAvailabilityInput,
    NoEnforcementEvent,
    NoEnforcementPoint,
    NoIssue,
    OperationalReadinessRequirements,
    OperationalRequirementRequired,
    ResearchResourcePolicy,
    ResourceCancellationRecord,
    ResourceClass,
    ResourceClassPolicyBinding,
    ResourceEnforcementEvent,
    ResourceEnforcementResult,
    ResourceObservationMetric,
    ResourceObservationRole,
    ResourcePolicyAuthorityMarker,
    RuntimeResourceLimit,
    StaticResourceAssessment,
    UnknownOrInvalidPolicy,
)
from carbon.resource_policy.refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    ResourceClassRef,
)

_KEY = ChallengeKey("fixture_resource_policy", "1.0")
_OTHER_KEY = ChallengeKey("other_resource_policy", "1.0")
_DIGEST = "sha256:" + "4" * 64


def _field_names(value_type: type) -> tuple[str, ...]:
    return tuple(field.name for field in fields(value_type))


def _owner(
    kind: str,
    object_id: str,
    *,
    key: ChallengeKey = _KEY,
    portable: bool = False,
) -> object:
    return owner_ref(
        kind,
        scope_binding=GlobalScope() if portable else ChallengeScope(key),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _environment(
    environment_id: str = "fixture_resource_environment",
) -> EnvironmentPin:
    return EnvironmentPin(environment_id, "1.0", _DIGEST)


def _class_ref(*, key: ChallengeKey = _KEY) -> ResourceClassRef:
    return ResourceClassRef(
        key,
        "fixture_resource_class",
        "1.0",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _provenance(*, key: ChallengeKey = _KEY) -> FixtureResourceProvenance:
    return FixtureResourceProvenance(
        _owner("fixture_registration", "resource_fixture", key=key),
        (_owner("provenance", "resource_source", key=key),),
        ResourcePolicyAuthorityMarker.FIXTURE_PROVENANCE_NOT_PRODUCTION,
    )


def _context(*, key: ChallengeKey = _KEY) -> FixturePracticeResourceContext:
    return FixturePracticeResourceContext(
        key,
        "fixture_practice",
        _owner("fixture_registration", "resource_fixture", key=key),
        _owner("internal_service_scope", "resource_practice_scope", key=key),
        ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
    )


def _resource_class(
    *,
    key: ChallengeKey = _KEY,
    provenance: FixtureResourceProvenance | None = None,
    required_environments: tuple[EnvironmentPin, ...] | None = None,
) -> ResourceClass:
    environment = _environment()
    unit = _owner("unit", "fixture_abstract_count", portable=True)
    return ResourceClass(
        "resource_class",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        key,
        "fixture_resource_class",
        "1.0",
        environment,
        required_environments or (environment,),
        (StaticResourceDimension("abstract_units", unit),),
        (
            ResourceObservationMetric(
                "consumed_units",
                unit,
                ResourceObservationRole.RESOURCE_CONSUMPTION,
            ),
            ResourceObservationMetric(
                "latency_units",
                unit,
                ResourceObservationRole.OBSERVED_LATENCY,
            ),
            ResourceObservationMetric(
                "cost_units_not_price",
                unit,
                ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
            ),
        ),
        provenance or _provenance(key=key),
        ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION,
    )


def _binding(*, key: ChallengeKey = _KEY) -> ResourceClassPolicyBinding:
    unit = _owner("unit", "fixture_abstract_count", portable=True)
    return ResourceClassPolicyBinding(
        _class_ref(key=key),
        (DeclaredResourceCeiling("abstract_units", unit, 13),),
        ("backbone_impact", "component_impact", "sampling_impact"),
        (
            RuntimeResourceLimit(
                "runtime_consumption_limit",
                "consumed_units",
                unit,
                21,
                EnforcementPoint.RUNTIME_OBSERVATION,
                EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS,
            ),
        ),
        OperationalReadinessRequirements(
            OperationalRequirementRequired(),
            OperationalRequirementRequired(),
            OperationalRequirementRequired(),
            OperationalRequirementRequired(),
        ),
    )


def _construction_ref(ref_type: type, *, key: ChallengeKey = _KEY) -> object:
    return ref_type(
        key,
        "fixture_construction_object",
        "1.0",
        CONSTRUCTION_SCHEMA_VERSION,
        CONSTRUCTION_CANONICALIZATION_PROFILE,
        _DIGEST,
    )


def _compiler() -> CompilerIdentity:
    return CompilerIdentity(
        "fixture_strategy_compiler",
        "1.0",
        _DIGEST,
        CONSTRUCTION_SCHEMA_VERSION,
        CONSTRUCTION_CANONICALIZATION_PROFILE,
    )


def _policy(*, key: ChallengeKey = _KEY) -> ResearchResourcePolicy:
    return ResearchResourcePolicy(
        "research_resource_policy",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        key,
        "fixture_resource_policy",
        "1.0",
        _construction_ref(CandidateAssemblyContractRef, key=key),
        _construction_ref(ParameterCatalogRef, key=key),
        _compiler(),
        _context(key=key),
        (_binding(key=key),),
        _owner("policy_authority", "fixture_resource_authority", key=key),
        _provenance(key=key),
        UnknownOrInvalidPolicy.REJECT,
        ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION,
    )


def test_top_level_and_nominal_variant_field_inventories_are_exact() -> None:
    assert _field_names(ResourceClass) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "object_id",
        "object_version",
        "execution_environment_pin",
        "required_plan_environment_pins",
        "supported_dimensions",
        "observation_metrics",
        "provenance",
        "authority_marker",
    )
    assert _field_names(ResourceClassPolicyBinding) == (
        "resource_class_ref",
        "ceilings",
        "supported_impact_tags",
        "runtime_limits",
        "readiness_requirements",
    )
    assert _field_names(ResearchResourcePolicy) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "object_id",
        "object_version",
        "candidate_assembly_ref",
        "parameter_catalog_ref",
        "compiler_identity",
        "authority_context",
        "class_bindings",
        "policy_authority_ref",
        "provenance",
        "unknown_or_invalid_policy",
        "authority_marker",
    )
    assert _field_names(StaticResourceAssessment) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "policy_ref",
        "resource_class_ref",
        "expected_active_policy_ref",
        "expected_active_resource_class_ref",
        "construction_plan_ref",
        "authority_context",
        "static_resource_requirements",
        "resource_impact_tags",
        "outcome",
        "issues",
        "epistemic_layer",
        "authority_marker",
    )
    assert _field_names(FixtureResourceAvailability) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "policy_ref",
        "resource_class_ref",
        "authority_context",
        "validator_capacity",
        "reconstruction_funding",
        "queue_availability",
        "evidence_budget_availability",
        "fixture_registration_ref",
        "authority_marker",
    )
    assert _field_names(FixtureResourceDecision) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "assessment_ref",
        "policy_ref",
        "resource_class_ref",
        "authority_context",
        "availability_input",
        "outcome",
        "deferral_causes",
        "authority_marker",
    )
    assert _field_names(ResourceEnforcementEvent) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "policy_ref",
        "resource_class_ref",
        "construction_plan_ref",
        "assessment_ref",
        "decision_ref",
        "authority_context",
        "limit_id",
        "enforcement_point",
        "enforcement_mode",
        "maximum_quantity",
        "observation",
        "action",
        "outcome",
        "issue",
    )
    assert _field_names(ResourceEnforcementResult) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "policy_ref",
        "resource_class_ref",
        "construction_plan_ref",
        "assessment_ref",
        "decision_ref",
        "authority_context",
        "event",
        "outcome",
        "authority_marker",
    )
    assert _field_names(ResourceCancellationRecord) == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "policy_ref",
        "resource_class_ref",
        "construction_plan_ref",
        "assessment_ref",
        "fixture_decision_ref",
        "authority_context",
        "stop_point",
        "actor",
        "reason",
        "enforcement_event_binding",
        "work_started",
        "observed_resource_quantities_so_far",
        "resulting_state",
        "authority_marker",
    )
    assert _field_names(NoAvailabilityInput) == ()
    assert _field_names(NoIssue) == ()
    assert _field_names(NoEnforcementPoint) == ()
    assert _field_names(AtEnforcementPoint) == ("enforcement_point",)
    assert _field_names(NoEnforcementEvent) == ()


def test_resource_class_requires_exact_environment_relation_and_metric_roles() -> None:
    value = _resource_class()

    assert value.execution_environment_pin in value.required_plan_environment_pins
    assert {metric.observation_role for metric in value.observation_metrics} == {
        ResourceObservationRole.RESOURCE_CONSUMPTION,
        ResourceObservationRole.OBSERVED_LATENCY,
        ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
    }
    assert value.authority_marker is (
        ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION
    )

    with pytest.raises(ResourcePolicyInputRejected):
        _resource_class(required_environments=(_environment("other_environment"),))
    with pytest.raises(ResourcePolicyInputRejected):
        replace(
            value,
            observation_metrics=tuple(
                metric
                for metric in value.observation_metrics
                if metric.observation_role
                is not ResourceObservationRole.OBSERVED_LATENCY
            ),
        )


def test_containing_class_rejects_cross_challenge_provenance() -> None:
    cross_challenge = _provenance(key=_OTHER_KEY)

    with pytest.raises(ResourcePolicyInputRejected):
        _resource_class(provenance=cross_challenge)


def test_resource_class_rejects_duplicate_dimensions_and_cross_challenge_unit() -> None:
    value = _resource_class()
    dimension = value.supported_dimensions[0]
    cross_challenge_unit = _owner("unit", "challenge_unit", key=_OTHER_KEY)

    with pytest.raises(ResourcePolicyInputRejected):
        replace(value, supported_dimensions=(dimension, dimension))
    with pytest.raises(ResourcePolicyInputRejected):
        replace(
            value,
            supported_dimensions=(
                StaticResourceDimension("abstract_units", cross_challenge_unit),
            ),
        )


def test_policy_is_exact_challenge_bound_and_fixture_only() -> None:
    value = _policy()

    assert value.challenge_key == _KEY
    assert value.authority_context == _context()
    assert value.unknown_or_invalid_policy is UnknownOrInvalidPolicy.REJECT
    assert value.authority_marker is (
        ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION
    )

    with pytest.raises(ResourcePolicyInputRejected):
        replace(value, authority_context=_context(key=_OTHER_KEY))
    with pytest.raises(ResourcePolicyInputRejected):
        replace(
            value,
            candidate_assembly_ref=_construction_ref(
                CandidateAssemblyContractRef,
                key=_OTHER_KEY,
            ),
        )
    with pytest.raises(ResourcePolicyInputRejected):
        replace(value, provenance=_provenance(key=_OTHER_KEY))
    with pytest.raises(ResourcePolicyInputRejected):
        replace(
            value,
            authority_marker=ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION,
        )


def test_practice_and_official_shaped_contexts_remain_nominally_distinct() -> None:
    practice = _context()
    official_shaped = FixtureOfficialShapedResourceContext(
        _KEY,
        "fixture_official_shaped",
        practice.fixture_registration_ref,
        _owner("internal_service_scope", "official_shaped_scope"),
        ResourcePolicyAuthorityMarker.FIXTURE_OFFICIAL_SHAPED_NOT_OFFICIAL,
    )

    assert type(practice) is not type(official_shaped)
    with pytest.raises(ResourcePolicyInputRejected):
        replace(_policy(), authority_context=object())

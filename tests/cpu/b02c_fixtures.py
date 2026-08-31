"""Closed non-authoritative B-02C fixtures shared by focused tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from b02b_fixtures import CompileFixture, make_compile_fixture, strategy_limits

from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.construction.compiler import (
    SUPPORTED_COMPILER_IDENTITY,
    CompileAccepted,
    compile_strategy,
)
from carbon.construction.model import StaticResourceDimension
from carbon.resource_policy.canonical import (
    research_resource_policy_to_ref,
    resource_class_to_ref,
)
from carbon.resource_policy.model import (
    DeclaredResourceCeiling,
    EnforcementMode,
    EnforcementPoint,
    FixtureAvailabilityState,
    FixturePracticeResourceContext,
    FixtureResourceAvailability,
    FixtureResourceProvenance,
    OperationalReadinessRequirements,
    OperationalRequirementRequired,
    ResearchResourcePolicy,
    ResourceClass,
    ResourceClassPolicyBinding,
    ResourceObservationMetric,
    ResourceObservationRole,
    ResourcePolicyAuthorityMarker,
    RuntimeResourceLimit,
    UnknownOrInvalidPolicy,
)
from carbon.resource_policy.refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    RESOURCE_POLICY_SCHEMA_VERSION,
    ResearchResourcePolicyRef,
    ResourceClassRef,
)

_DIGEST = "sha256:" + "6" * 64
_RETAINED_COMPILE_RESULTS: list[CompileAccepted] = []


@dataclass(frozen=True, slots=True)
class ResourcePolicyFixture:
    compile_fixture: CompileFixture
    compile_result: CompileAccepted
    context: FixturePracticeResourceContext
    resource_class: ResourceClass
    resource_class_ref: ResourceClassRef
    policy: ResearchResourcePolicy
    policy_ref: ResearchResourcePolicyRef

    @property
    def plan(self) -> object:
        return self.compile_result.construction_plan

    @property
    def plan_ref(self) -> object:
        return self.compile_result.construction_plan_ref

    @property
    def class_bundle(self) -> tuple[tuple[ResourceClass, ResourceClassRef], ...]:
        return ((self.resource_class, self.resource_class_ref),)


def _pinned(key: object, kind: str, object_id: str) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(key),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def compile_resource_plan(
    tmp_path: Path,
) -> tuple[CompileFixture, CompileAccepted]:
    """Build one exact B-02B plan without adding any resource-policy meaning."""

    fixture = make_compile_fixture(tmp_path)
    result = compile_strategy(
        fixture.strategy,
        challenge_key=fixture.key,
        candidate_assembly=fixture.assembly,
        candidate_assembly_ref=fixture.assembly.to_ref(),
        parameter_catalog=fixture.catalog,
        parameter_catalog_ref=fixture.catalog.to_ref(
            candidate_assembly=fixture.assembly
        ),
        authoring_origin=fixture.authoring_origin,
        authoring_artifacts=fixture.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )
    assert type(result) is CompileAccepted
    # B-02B intentionally tracks verified plans weakly. These equal fixture plans
    # must remain strongly reachable while a B-02C test session uses them.
    _RETAINED_COMPILE_RESULTS.append(result)
    return fixture, result


def required_readiness() -> OperationalReadinessRequirements:
    return OperationalReadinessRequirements(
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
    )


def make_resource_policy_fixture(
    tmp_path: Path,
    *,
    static_ceiling: int = 13,
    runtime_maximum: int = 20,
    supported_impact_tags: tuple[str, ...] | None = None,
    readiness_requirements: OperationalReadinessRequirements | None = None,
) -> ResourcePolicyFixture:
    compile_fixture, compile_result = compile_resource_plan(tmp_path)
    key = compile_fixture.key
    plan = compile_result.construction_plan
    requirement = plan.static_resource_requirements[0]
    context = FixturePracticeResourceContext(
        key,
        "fixture_resource_practice",
        _pinned(key, "fixture_registration", "fixture_resource_registration"),
        _pinned(key, "internal_service_scope", "fixture_resource_service"),
        ResourcePolicyAuthorityMarker.FIXTURE_PRACTICE_NOT_OFFICIAL,
    )
    provenance = FixtureResourceProvenance(
        context.fixture_registration_ref,
        (_pinned(key, "provenance", "fixture_resource_source"),),
        ResourcePolicyAuthorityMarker.FIXTURE_PROVENANCE_NOT_PRODUCTION,
    )
    resource_class = ResourceClass(
        "resource_class",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        key,
        "fixture_resource_class",
        "1.0",
        plan.environment_pins[0],
        plan.environment_pins,
        (
            StaticResourceDimension(
                requirement.dimension_id,
                requirement.unit_ref,
            ),
        ),
        (
            ResourceObservationMetric(
                "consumed_units",
                requirement.unit_ref,
                ResourceObservationRole.RESOURCE_CONSUMPTION,
            ),
            ResourceObservationMetric(
                "latency_units",
                requirement.unit_ref,
                ResourceObservationRole.OBSERVED_LATENCY,
            ),
            ResourceObservationMetric(
                "cost_units_not_price",
                requirement.unit_ref,
                ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
            ),
        ),
        provenance,
        ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION,
    )
    resource_class_ref = resource_class_to_ref(resource_class)
    binding = ResourceClassPolicyBinding(
        resource_class_ref,
        (
            DeclaredResourceCeiling(
                requirement.dimension_id,
                requirement.unit_ref,
                static_ceiling,
            ),
        ),
        supported_impact_tags or plan.resource_impact_tags,
        (
            RuntimeResourceLimit(
                "pre_allocation_limit",
                "consumed_units",
                requirement.unit_ref,
                runtime_maximum,
                EnforcementPoint.PRE_ALLOCATION_READINESS,
                EnforcementMode.PREVENT_START_ON_EXCESS,
            ),
            RuntimeResourceLimit(
                "pre_execution_limit",
                "consumed_units",
                requirement.unit_ref,
                runtime_maximum,
                EnforcementPoint.PRE_EXECUTION,
                EnforcementMode.PREVENT_NEXT_UNIT_ON_EXCESS,
            ),
            RuntimeResourceLimit(
                "runtime_limit",
                "consumed_units",
                requirement.unit_ref,
                runtime_maximum,
                EnforcementPoint.RUNTIME_OBSERVATION,
                EnforcementMode.STOP_ON_FIRST_OBSERVED_EXCESS,
            ),
        ),
        readiness_requirements or required_readiness(),
    )
    policy = ResearchResourcePolicy(
        "research_resource_policy",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        key,
        "fixture_resource_policy",
        "1.0",
        plan.candidate_assembly_ref,
        plan.parameter_catalog_ref,
        plan.compiler_identity,
        context,
        (binding,),
        _pinned(key, "policy_authority", "fixture_resource_authority"),
        provenance,
        UnknownOrInvalidPolicy.REJECT,
        ResourcePolicyAuthorityMarker.FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION,
    )
    class_bundle = ((resource_class, resource_class_ref),)
    policy_ref = research_resource_policy_to_ref(
        policy,
        class_bundle=class_bundle,
    )
    return ResourcePolicyFixture(
        compile_fixture,
        compile_result,
        context,
        resource_class,
        resource_class_ref,
        policy,
        policy_ref,
    )


def availability(
    fixture: ResourcePolicyFixture,
    *,
    validator_capacity: FixtureAvailabilityState = FixtureAvailabilityState.AVAILABLE,
    reconstruction_funding: FixtureAvailabilityState = FixtureAvailabilityState.AVAILABLE,
    queue_availability: FixtureAvailabilityState = FixtureAvailabilityState.AVAILABLE,
    evidence_budget_availability: FixtureAvailabilityState = FixtureAvailabilityState.AVAILABLE,
) -> FixtureResourceAvailability:
    return FixtureResourceAvailability(
        "fixture_resource_availability",
        RESOURCE_POLICY_SCHEMA_VERSION,
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        fixture.compile_fixture.key,
        fixture.policy_ref,
        fixture.resource_class_ref,
        fixture.context,
        validator_capacity,
        reconstruction_funding,
        queue_availability,
        evidence_budget_availability,
        fixture.context.fixture_registration_ref,
        ResourcePolicyAuthorityMarker.FIXTURE_AVAILABILITY_NOT_OPERATIONAL_COMMITMENT,
    )


__all__ = [
    "ResourcePolicyFixture",
    "availability",
    "compile_resource_plan",
    "make_resource_policy_fixture",
    "required_readiness",
]

"""Fixture readiness and pure inclusive-limit enforcement tests for B-02C."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from b02c_fixtures import (
    ResourcePolicyFixture,
    availability,
    make_resource_policy_fixture,
)

from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.construction.plan import resolved_construction_plan_canonical_bytes
from carbon.resource_policy.canonical import (
    fixture_resource_decision_to_ref,
    static_resource_assessment_to_ref,
)
from carbon.resource_policy.errors import ResourcePolicyInputRejected
from carbon.resource_policy.model import (
    EnforcementObservationKind,
    EnforcementPoint,
    FixtureAvailabilityState,
    FixtureDecisionOutcome,
    NoAvailabilityInput,
    NoIssue,
    ObservedResourceQuantity,
    OperationalReadinessRequirements,
    OperationalRequirementNotApplicable,
    OperationalRequirementRequired,
    ResourceDeferralCause,
    ResourceEnforcementAction,
    ResourceEnforcementObservation,
    ResourceEnforcementOutcome,
    ResourceObservationRole,
    ResourcePolicyAuthorityMarker,
    ResourcePolicyIssue,
    ResourcePolicyIssueCode,
    StaticAssessmentOutcome,
)
from carbon.resource_policy.service import (
    assess_static_resources,
    decide_fixture_readiness,
    evaluate_enforcement,
)

_DIGEST = "sha256:" + "8" * 64


@dataclass(frozen=True, slots=True)
class _ForecastCanary:
    predicted_quantity: int
    confidence: int


@dataclass(frozen=True, slots=True)
class _QuoteCanary:
    admitted_quantity: int
    price: int


def _assessment(fixture: ResourcePolicyFixture) -> tuple[object, object]:
    result = assess_static_resources(
        plan=fixture.plan,
        plan_ref=fixture.plan_ref,
        policy=fixture.policy,
        policy_ref=fixture.policy_ref,
        class_bundle=fixture.class_bundle,
        selected_class=fixture.resource_class,
        selected_class_ref=fixture.resource_class_ref,
        expected_active_policy_ref=fixture.policy_ref,
        expected_active_resource_class_ref=fixture.resource_class_ref,
        authority_context=fixture.context,
    )
    return result, static_resource_assessment_to_ref(result)


def _decision(
    fixture: ResourcePolicyFixture,
    availability_input: object,
) -> tuple[object, object, object, object]:
    assessment, assessment_ref = _assessment(fixture)
    decision = decide_fixture_readiness(
        plan=fixture.plan,
        plan_ref=fixture.plan_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
        policy=fixture.policy,
        policy_ref=fixture.policy_ref,
        class_bundle=fixture.class_bundle,
        selected_class=fixture.resource_class,
        selected_class_ref=fixture.resource_class_ref,
        availability_input=availability_input,
    )
    return (
        assessment,
        assessment_ref,
        decision,
        fixture_resource_decision_to_ref(decision),
    )


def _observation(
    fixture: ResourcePolicyFixture,
    *,
    quantity: int,
    kind: EnforcementObservationKind,
    metric_id: str = "consumed_units",
    role: ResourceObservationRole = ResourceObservationRole.RESOURCE_CONSUMPTION,
) -> ResourceEnforcementObservation:
    unit = fixture.plan.static_resource_requirements[0].unit_ref
    return ResourceEnforcementObservation(
        ObservedResourceQuantity(metric_id, unit, quantity, role),
        kind,
    )


def _enforce(
    fixture: ResourcePolicyFixture,
    *,
    limit_id: object,
    observation: object,
    decision_input: object | None = None,
) -> object:
    availability_input = availability(fixture)
    assessment, assessment_ref, decision, decision_ref = _decision(
        fixture,
        availability_input,
    )
    if decision_input is not None:
        decision = decision_input
        decision_ref = fixture_resource_decision_to_ref(decision_input)
    return evaluate_enforcement(
        plan=fixture.plan,
        plan_ref=fixture.plan_ref,
        policy=fixture.policy,
        policy_ref=fixture.policy_ref,
        class_bundle=fixture.class_bundle,
        selected_class=fixture.resource_class,
        selected_class_ref=fixture.resource_class_ref,
        assessment=assessment,
        assessment_ref=assessment_ref,
        decision=decision,
        decision_ref=decision_ref,
        limit_id=limit_id,
        observation=observation,
    )


def test_no_availability_input_defers_every_required_commitment(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    _, _, first, first_ref = _decision(fixture, NoAvailabilityInput())
    _, _, second, second_ref = _decision(fixture, NoAvailabilityInput())

    assert first == second
    assert first_ref == second_ref
    assert first.outcome is FixtureDecisionOutcome.EVIDENCE_DEFERRED
    assert set(first.deferral_causes) == set(ResourceDeferralCause)
    assert first.authority_marker is (
        ResourcePolicyAuthorityMarker.POLICY_ADMISSIBILITY_NOT_QUOTE_OR_EXECUTION
    )
    assert not hasattr(first, "price")
    assert not hasattr(first, "scientific_outcome")


@pytest.mark.parametrize(
    ("field", "cause"),
    (
        ("validator_capacity", ResourceDeferralCause.CAPACITY_UNAVAILABLE),
        (
            "reconstruction_funding",
            ResourceDeferralCause.RECONSTRUCTION_FUNDING_UNAVAILABLE,
        ),
        ("queue_availability", ResourceDeferralCause.QUEUE_UNAVAILABLE),
        (
            "evidence_budget_availability",
            ResourceDeferralCause.EVIDENCE_BUDGET_UNAVAILABLE,
        ),
    ),
)
def test_each_unavailable_operational_fact_defers_independently(
    tmp_path: Path,
    field: str,
    cause: ResourceDeferralCause,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    provided = availability(
        fixture,
        **{field: FixtureAvailabilityState.UNAVAILABLE},
    )
    _, _, decision, _ = _decision(fixture, provided)

    assert decision.outcome is FixtureDecisionOutcome.EVIDENCE_DEFERRED
    assert decision.deferral_causes == (cause,)


def test_all_available_is_fixture_admissible_and_all_unavailable_collects_all(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    _, _, admitted, _ = _decision(fixture, availability(fixture))
    unavailable = availability(
        fixture,
        validator_capacity=FixtureAvailabilityState.UNAVAILABLE,
        reconstruction_funding=FixtureAvailabilityState.UNAVAILABLE,
        queue_availability=FixtureAvailabilityState.UNAVAILABLE,
        evidence_budget_availability=FixtureAvailabilityState.UNAVAILABLE,
    )
    _, _, deferred, _ = _decision(fixture, unavailable)

    assert admitted.outcome is FixtureDecisionOutcome.FIXTURE_ADMISSIBLE
    assert admitted.deferral_causes == ()
    assert deferred.outcome is FixtureDecisionOutcome.EVIDENCE_DEFERRED
    assert set(deferred.deferral_causes) == set(ResourceDeferralCause)


def test_not_applicable_readiness_cannot_be_promoted_to_availability(
    tmp_path: Path,
) -> None:
    base = make_resource_policy_fixture(tmp_path)
    reason = owner_ref(
        "applicability_reason",
        scope_binding=ChallengeScope(base.compile_fixture.key),
        object_id="capacity_not_applicable",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    readiness = OperationalReadinessRequirements(
        OperationalRequirementNotApplicable(reason),
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
    )
    fixture = make_resource_policy_fixture(
        tmp_path,
        readiness_requirements=readiness,
    )
    valid = availability(
        fixture,
        validator_capacity=FixtureAvailabilityState.NOT_APPLICABLE,
    )
    _, _, admitted, _ = _decision(fixture, valid)
    _, _, absent, _ = _decision(fixture, NoAvailabilityInput())

    assert admitted.outcome is FixtureDecisionOutcome.FIXTURE_ADMISSIBLE
    assert ResourceDeferralCause.CAPACITY_UNAVAILABLE not in absent.deferral_causes
    with pytest.raises(ResourcePolicyInputRejected):
        _decision(fixture, availability(fixture))
    with pytest.raises(ResourcePolicyInputRejected):
        _decision(
            fixture,
            availability(
                fixture,
                validator_capacity=FixtureAvailabilityState.UNAVAILABLE,
            ),
        )


def test_readiness_rejects_wrong_refs_context_bool_and_future_layer_canaries(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    assessment, assessment_ref = _assessment(fixture)
    provided = availability(fixture)

    with pytest.raises(ResourcePolicyInputRejected):
        replace(provided, validator_capacity=True)
    with pytest.raises(ResourcePolicyInputRejected):
        _decision(
            fixture,
            replace(
                provided, policy_ref=replace(fixture.policy_ref, object_id="other")
            ),
        )
    for canary in (_ForecastCanary(12, 95), _QuoteCanary(12, 99)):
        with pytest.raises(ResourcePolicyInputRejected):
            decide_fixture_readiness(
                plan=fixture.plan,
                plan_ref=fixture.plan_ref,
                assessment=canary,
                assessment_ref=assessment_ref,
                policy=fixture.policy,
                policy_ref=fixture.policy_ref,
                class_bundle=fixture.class_bundle,
                selected_class=fixture.resource_class,
                selected_class_ref=fixture.resource_class_ref,
                availability_input=provided,
            )
    assert assessment.outcome is StaticAssessmentOutcome.ADMISSIBLE


@pytest.mark.parametrize(
    ("limit_id", "point", "kind", "breach_action"),
    (
        (
            "pre_allocation_limit",
            EnforcementPoint.PRE_ALLOCATION_READINESS,
            EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL,
            ResourceEnforcementAction.PREVENT_FIXTURE_START,
        ),
        (
            "pre_execution_limit",
            EnforcementPoint.PRE_EXECUTION,
            EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL,
            ResourceEnforcementAction.PREVENT_NEXT_UNIT,
        ),
        (
            "runtime_limit",
            EnforcementPoint.RUNTIME_OBSERVATION,
            EnforcementObservationKind.CURRENT_TOTAL,
            ResourceEnforcementAction.REQUEST_FIXTURE_STOP,
        ),
    ),
)
def test_inclusive_limit_continues_at_limit_and_stops_one_over(
    tmp_path: Path,
    limit_id: str,
    point: EnforcementPoint,
    kind: EnforcementObservationKind,
    breach_action: ResourceEnforcementAction,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path, runtime_maximum=20)
    before = resolved_construction_plan_canonical_bytes(fixture.plan)
    continued = _enforce(
        fixture,
        limit_id=limit_id,
        observation=_observation(fixture, quantity=20, kind=kind),
    )
    stopped = _enforce(
        fixture,
        limit_id=limit_id,
        observation=_observation(fixture, quantity=21, kind=kind),
    )

    assert continued.outcome is ResourceEnforcementOutcome.CONTINUE_FIXTURE
    assert continued.event.enforcement_point is point
    assert continued.event.action is ResourceEnforcementAction.NO_STOP
    assert type(continued.event.issue) is NoIssue
    assert stopped.outcome is ResourceEnforcementOutcome.STOPPED_OVER_LIMIT
    assert stopped.event.action is breach_action
    assert stopped.event.outcome is stopped.outcome
    assert type(stopped.event.issue) is NoIssue
    assert stopped.event.policy_ref == stopped.policy_ref
    assert stopped.event.resource_class_ref == stopped.resource_class_ref
    assert stopped.event.construction_plan_ref == stopped.construction_plan_ref
    assert resolved_construction_plan_canonical_bytes(fixture.plan) == before


@pytest.mark.parametrize(
    "observation",
    (
        "wrong_kind",
        "wrong_metric",
        "wrong_role",
    ),
)
def test_observation_mismatch_fails_closed_without_candidate_failure(
    tmp_path: Path,
    observation: str,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    if observation == "wrong_kind":
        value = _observation(
            fixture,
            quantity=10,
            kind=EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL,
        )
    elif observation == "wrong_metric":
        value = _observation(
            fixture,
            quantity=10,
            kind=EnforcementObservationKind.CURRENT_TOTAL,
            metric_id="latency_units",
        )
    else:
        value = _observation(
            fixture,
            quantity=10,
            kind=EnforcementObservationKind.CURRENT_TOTAL,
            role=ResourceObservationRole.OBSERVED_LATENCY,
        )

    result = _enforce(
        fixture,
        limit_id="runtime_limit",
        observation=value,
    )

    assert result.outcome is ResourceEnforcementOutcome.ENFORCEMENT_FAILURE
    assert result.event.action is ResourceEnforcementAction.FAIL_CLOSED
    assert type(result.event.issue) is ResourcePolicyIssue
    assert result.event.issue.code is (
        ResourcePolicyIssueCode.LIMIT_OBSERVATION_MISMATCH
    )
    assert not hasattr(result, "candidate_outcome")


def test_missing_limit_hard_rejects_before_observation_or_event(
    tmp_path: Path,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)

    with pytest.raises(ResourcePolicyInputRejected) as caught:
        _enforce(
            fixture,
            limit_id="unbound_limit",
            observation=object(),
        )
    assert caught.value.code == "LIMIT_NOT_BOUND"


@pytest.mark.parametrize(
    "limit_id",
    (
        "",
        "NOT_CANONICAL",
        "contains space",
        "a" * 70_000,
    ),
    ids=("empty", "uppercase", "space", "oversized"),
)
def test_malformed_or_oversized_limit_id_is_invalid_not_merely_unbound(
    tmp_path: Path,
    limit_id: str,
) -> None:
    fixture = make_resource_policy_fixture(tmp_path)

    with pytest.raises(ResourcePolicyInputRejected) as caught:
        _enforce(
            fixture,
            limit_id=limit_id,
            observation=object(),
        )
    assert caught.value.code == "INVALID_VALUE"


def test_enforcement_requires_prior_fixture_admissibility(tmp_path: Path) -> None:
    fixture = make_resource_policy_fixture(tmp_path)
    _, _, deferred, _ = _decision(fixture, NoAvailabilityInput())

    with pytest.raises(ResourcePolicyInputRejected):
        _enforce(
            fixture,
            limit_id="runtime_limit",
            observation=_observation(
                fixture,
                quantity=10,
                kind=EnforcementObservationKind.CURRENT_TOTAL,
            ),
            decision_input=deferred,
        )

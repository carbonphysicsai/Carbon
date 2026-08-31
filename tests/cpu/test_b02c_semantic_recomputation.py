"""Hostile self-consistent semantic-bypass regressions for B-02C builders."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from b02c_fixtures import availability, make_resource_policy_fixture

from carbon.resource_policy.canonical import (
    fixture_resource_decision_to_ref,
    static_resource_assessment_to_ref,
)
from carbon.resource_policy.errors import ResourcePolicyInputRejected
from carbon.resource_policy.model import (
    CancellationReason,
    CompleteBuild,
    CompleteBuildIdentity,
    DeclaredResourceEvidenceStage,
    EnforcementObservationKind,
    FixtureRequesterActor,
    NoAvailabilityInput,
    NoEnforcementPoint,
    NoReuse,
    ObservedMetricObserved,
    ObservedResourceQuantity,
    ReplicateNotApplicable,
    ReplicateNotApplicableReason,
    ResourceEnforcementObservation,
    ResourceObservationRole,
    ResourceStopCause,
)
from carbon.resource_policy.service import (
    assess_static_resources,
    decide_fixture_readiness,
    evaluate_enforcement,
    make_cancellation_record,
    make_observed_resource_receipt,
)

_DIGEST = "sha256:" + "b" * 64


def _base(tmp_path: Path) -> tuple[object, ...]:
    fixture = make_resource_policy_fixture(tmp_path)
    assessment = assess_static_resources(
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
    assessment_ref = static_resource_assessment_to_ref(assessment)
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
        availability_input=availability(fixture),
    )
    return (
        fixture,
        assessment,
        assessment_ref,
        decision,
        fixture_resource_decision_to_ref(decision),
    )


def _quantity(fixture: object, metric_id: str, quantity: int, role: object) -> object:
    unit = fixture.plan.static_resource_requirements[0].unit_ref
    return ObservedResourceQuantity(metric_id, unit, quantity, role)


def _assert_downstream_rejects(
    fixture: object,
    assessment: object,
    assessment_ref: object,
    decision: object,
    decision_ref: object,
) -> None:
    common = {
        "plan": fixture.plan,
        "plan_ref": fixture.plan_ref,
        "policy": fixture.policy,
        "policy_ref": fixture.policy_ref,
        "class_bundle": fixture.class_bundle,
        "selected_class": fixture.resource_class,
        "selected_class_ref": fixture.resource_class_ref,
        "assessment": assessment,
        "assessment_ref": assessment_ref,
        "decision": decision,
        "decision_ref": decision_ref,
    }
    with pytest.raises(ResourcePolicyInputRejected):
        evaluate_enforcement(
            **common,
            limit_id="runtime_limit",
            observation=ResourceEnforcementObservation(
                _quantity(
                    fixture,
                    "consumed_units",
                    10,
                    ResourceObservationRole.RESOURCE_CONSUMPTION,
                ),
                EnforcementObservationKind.CURRENT_TOTAL,
            ),
        )
    with pytest.raises(ResourcePolicyInputRejected):
        make_cancellation_record(
            **common,
            actor=FixtureRequesterActor(fixture.context.fixture_registration_ref),
            reason=CancellationReason.REQUESTER_CANCELLED,
            stop_point=NoEnforcementPoint(),
            work_started=False,
            observed_resource_quantities_so_far=(),
        )
    build = CompleteBuildIdentity(
        fixture.compile_fixture.key,
        fixture.plan_ref,
        fixture.policy_ref,
        fixture.resource_class_ref,
        fixture.resource_class.execution_environment_pin,
        "fixture_build_attempt",
        _DIGEST,
    )
    with pytest.raises(ResourcePolicyInputRejected):
        make_observed_resource_receipt(
            **common,
            build_completion=CompleteBuild(build),
            frozen_artifact_reuse=NoReuse(),
            reconstruction_replicate=ReplicateNotApplicable(
                ReplicateNotApplicableReason.NOT_A_RECONSTRUCTION_REPLICATE
            ),
            observed_consumption_quantities=(
                _quantity(
                    fixture,
                    "consumed_units",
                    13,
                    ResourceObservationRole.RESOURCE_CONSUMPTION,
                ),
            ),
            observed_latency=ObservedMetricObserved(
                _quantity(
                    fixture,
                    "latency_units",
                    3,
                    ResourceObservationRole.OBSERVED_LATENCY,
                )
            ),
            observed_cost=ObservedMetricObserved(
                _quantity(
                    fixture,
                    "cost_units_not_price",
                    7,
                    ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
                )
            ),
            evidence_stage_label=DeclaredResourceEvidenceStage.DECLARED_BUILD_ACCOUNTING,
            stop_cause=ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING,
            work_started=True,
        )


def test_digest_valid_admissible_assessment_cannot_bypass_recomputation(
    tmp_path: Path,
) -> None:
    fixture, assessment, _, decision, _ = _base(tmp_path)
    forged_assessment = replace(
        assessment,
        static_resource_requirements=(),
        resource_impact_tags=(),
    )
    forged_assessment_ref = static_resource_assessment_to_ref(forged_assessment)
    forged_decision = replace(decision, assessment_ref=forged_assessment_ref)
    forged_decision_ref = fixture_resource_decision_to_ref(forged_decision)

    with pytest.raises(ResourcePolicyInputRejected):
        decide_fixture_readiness(
            plan=fixture.plan,
            plan_ref=fixture.plan_ref,
            assessment=forged_assessment,
            assessment_ref=forged_assessment_ref,
            policy=fixture.policy,
            policy_ref=fixture.policy_ref,
            class_bundle=fixture.class_bundle,
            selected_class=fixture.resource_class,
            selected_class_ref=fixture.resource_class_ref,
            availability_input=availability(fixture),
        )
    _assert_downstream_rejects(
        fixture,
        forged_assessment,
        forged_assessment_ref,
        forged_decision,
        forged_decision_ref,
    )


def test_digest_valid_admissible_decision_cannot_hide_required_unavailability(
    tmp_path: Path,
) -> None:
    fixture, assessment, assessment_ref, decision, _ = _base(tmp_path)
    forged_decision = replace(
        decision,
        availability_input=NoAvailabilityInput(),
    )
    forged_decision_ref = fixture_resource_decision_to_ref(forged_decision)

    _assert_downstream_rejects(
        fixture,
        assessment,
        assessment_ref,
        forged_decision,
        forged_decision_ref,
    )

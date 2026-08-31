"""Cancellation provenance and resource-only receipt service tests for B-02C."""

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
from carbon.construction.model import EnvironmentPin
from carbon.construction.plan import resolved_construction_plan_canonical_bytes
from carbon.resource_policy.canonical import (
    decode_observed_resource_receipt,
    decode_resource_cancellation_record,
    encode_observed_resource_receipt,
    encode_resource_cancellation_record,
    fixture_resource_decision_to_ref,
    resource_cancellation_record_to_ref,
    resource_policy_content_digest,
    static_resource_assessment_to_ref,
)
from carbon.resource_policy.errors import ResourcePolicyInputRejected
from carbon.resource_policy.model import (
    NO_AVAILABILITY_INPUT,
    AtEnforcementPoint,
    BoundReconstructionReplicate,
    CancellationReason,
    CancellationResultingState,
    CompleteBuild,
    CompleteBuildIdentity,
    DeclaredResourceEvidenceStage,
    EnforcementObservationKind,
    EnforcementPoint,
    FixtureAvailabilityState,
    FixtureRequesterActor,
    IncompleteBuild,
    IncompleteBuildIdentity,
    InfrastructureActor,
    NoBuildStarted,
    NoEnforcementEvent,
    NoEnforcementPoint,
    NoResourceStop,
    NoReuse,
    ObservationUnavailableReason,
    ObservedMetricObserved,
    ObservedMetricUnavailable,
    ObservedResourceQuantity,
    OperationalReadinessRequirements,
    OperationalRequirementNotApplicable,
    OperationalRequirementRequired,
    PolicyEnforcerActor,
    ReconstructionReplicateIdentity,
    ReplicateNotApplicable,
    ReplicateNotApplicableReason,
    ResourceEnforcementObservation,
    ResourceEnforcementOutcome,
    ResourceEpistemicLayer,
    ResourceObservationRole,
    ResourcePolicyAuthorityMarker,
    ResourceStopCause,
)
from carbon.resource_policy.refs import ObservedResourceReceiptRef
from carbon.resource_policy.service import (
    assess_static_resources,
    decide_fixture_readiness,
    evaluate_enforcement,
    make_cancellation_record,
    make_observed_resource_receipt,
    validate_observed_resource_receipt,
)

_DIGEST = "sha256:" + "a" * 64


@dataclass(frozen=True, slots=True)
class _State:
    fixture: ResourcePolicyFixture
    assessment: object
    assessment_ref: object
    decision: object
    decision_ref: object


def _state(
    tmp_path: Path,
    *,
    availability_input: object | None = None,
    readiness_requirements: OperationalReadinessRequirements | None = None,
) -> _State:
    fixture = make_resource_policy_fixture(
        tmp_path,
        readiness_requirements=readiness_requirements,
    )
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
    supplied = (
        availability(fixture) if availability_input is None else availability_input
    )
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
        availability_input=supplied,
    )
    return _State(
        fixture,
        assessment,
        assessment_ref,
        decision,
        fixture_resource_decision_to_ref(decision),
    )


def _pinned(state: _State, kind: str, object_id: str) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(state.fixture.compile_fixture.key),
        object_id=object_id,
        object_version="1.0",
        content_digest=_DIGEST,
    )


def _quantity(
    state: _State,
    metric_id: str,
    quantity: int,
    role: ResourceObservationRole,
) -> ObservedResourceQuantity:
    unit = state.fixture.plan.static_resource_requirements[0].unit_ref
    return ObservedResourceQuantity(metric_id, unit, quantity, role)


def _enforcement(
    state: _State,
    *,
    quantity: int = 21,
    metric_id: str = "consumed_units",
    role: ResourceObservationRole = ResourceObservationRole.RESOURCE_CONSUMPTION,
    limit_id: str = "runtime_limit",
    kind: EnforcementObservationKind = EnforcementObservationKind.CURRENT_TOTAL,
) -> object:
    return evaluate_enforcement(
        plan=state.fixture.plan,
        plan_ref=state.fixture.plan_ref,
        policy=state.fixture.policy,
        policy_ref=state.fixture.policy_ref,
        class_bundle=state.fixture.class_bundle,
        selected_class=state.fixture.resource_class,
        selected_class_ref=state.fixture.resource_class_ref,
        assessment=state.assessment,
        assessment_ref=state.assessment_ref,
        decision=state.decision,
        decision_ref=state.decision_ref,
        limit_id=limit_id,
        observation=ResourceEnforcementObservation(
            _quantity(state, metric_id, quantity, role),
            kind,
        ),
    )


def _cancel(state: _State, **overrides: object) -> object:
    values: dict[str, object] = {
        "plan": state.fixture.plan,
        "plan_ref": state.fixture.plan_ref,
        "policy": state.fixture.policy,
        "policy_ref": state.fixture.policy_ref,
        "class_bundle": state.fixture.class_bundle,
        "selected_class": state.fixture.resource_class,
        "selected_class_ref": state.fixture.resource_class_ref,
        "assessment": state.assessment,
        "assessment_ref": state.assessment_ref,
        "decision": state.decision,
        "decision_ref": state.decision_ref,
        "actor": FixtureRequesterActor(state.fixture.context.fixture_registration_ref),
        "reason": CancellationReason.REQUESTER_CANCELLED,
        "stop_point": NoEnforcementPoint(),
        "work_started": False,
        "observed_resource_quantities_so_far": (),
        "enforcement_result": None,
    }
    values.update(overrides)
    return make_cancellation_record(**values)


def _complete_identity(state: _State) -> CompleteBuildIdentity:
    return CompleteBuildIdentity(
        state.fixture.compile_fixture.key,
        state.fixture.plan_ref,
        state.fixture.policy_ref,
        state.fixture.resource_class_ref,
        state.fixture.resource_class.execution_environment_pin,
        "fixture_build_attempt",
        _DIGEST,
    )


def _incomplete_identity(state: _State) -> IncompleteBuildIdentity:
    return IncompleteBuildIdentity(
        state.fixture.compile_fixture.key,
        state.fixture.plan_ref,
        state.fixture.policy_ref,
        state.fixture.resource_class_ref,
        state.fixture.resource_class.execution_environment_pin,
        "fixture_build_attempt",
        _DIGEST,
    )


def _issued_receipt(state: _State, **overrides: object) -> tuple[object, object]:
    values: dict[str, object] = {
        "plan": state.fixture.plan,
        "plan_ref": state.fixture.plan_ref,
        "policy": state.fixture.policy,
        "policy_ref": state.fixture.policy_ref,
        "class_bundle": state.fixture.class_bundle,
        "selected_class": state.fixture.resource_class,
        "selected_class_ref": state.fixture.resource_class_ref,
        "assessment": state.assessment,
        "assessment_ref": state.assessment_ref,
        "decision": state.decision,
        "decision_ref": state.decision_ref,
        "build_completion": CompleteBuild(_complete_identity(state)),
        "frozen_artifact_reuse": NoReuse(),
        "reconstruction_replicate": ReplicateNotApplicable(
            ReplicateNotApplicableReason.NOT_A_RECONSTRUCTION_REPLICATE
        ),
        "observed_consumption_quantities": (
            _quantity(
                state,
                "consumed_units",
                13,
                ResourceObservationRole.RESOURCE_CONSUMPTION,
            ),
        ),
        "observed_latency": ObservedMetricObserved(
            _quantity(
                state,
                "latency_units",
                3,
                ResourceObservationRole.OBSERVED_LATENCY,
            )
        ),
        "observed_cost": ObservedMetricObserved(
            _quantity(
                state,
                "cost_units_not_price",
                7,
                ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
            )
        ),
        "evidence_stage_label": DeclaredResourceEvidenceStage.DECLARED_BUILD_ACCOUNTING,
        "stop_cause": ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING,
        "work_started": True,
        "stop_record": None,
        "stop_record_ref": None,
        "enforcement_result": None,
    }
    values.update(overrides)
    return make_observed_resource_receipt(**values)


def _receipt(state: _State, **overrides: object) -> object:
    receipt, _ = _issued_receipt(state, **overrides)
    return receipt


def _validate_receipt(
    state: _State,
    receipt: object,
    receipt_ref: object,
    **overrides: object,
) -> tuple[object, object]:
    values: dict[str, object] = {
        "plan": state.fixture.plan,
        "plan_ref": state.fixture.plan_ref,
        "policy": state.fixture.policy,
        "policy_ref": state.fixture.policy_ref,
        "class_bundle": state.fixture.class_bundle,
        "selected_class": state.fixture.resource_class,
        "selected_class_ref": state.fixture.resource_class_ref,
        "assessment": state.assessment,
        "assessment_ref": state.assessment_ref,
        "decision": state.decision,
        "decision_ref": state.decision_ref,
        "stop_record": None,
        "stop_record_ref": None,
        "enforcement_result": None,
    }
    values.update(overrides)
    return validate_observed_resource_receipt(receipt, receipt_ref, **values)


def _structural_receipt_ref(receipt: object) -> ObservedResourceReceiptRef:
    payload = encode_observed_resource_receipt(receipt)
    return ObservedResourceReceiptRef(
        receipt.challenge_key,
        receipt.schema_version,
        receipt.canonicalization_profile,
        resource_policy_content_digest(payload),
    )


def test_requester_and_infrastructure_prework_cancellations_are_non_scientific(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    requester = _cancel(state)
    infrastructure = _cancel(
        state,
        actor=InfrastructureActor(
            _pinned(state, "infrastructure_failure", "fixture_host_failure")
        ),
        reason=CancellationReason.INFRASTRUCTURE_FAILURE,
    )

    assert requester.resulting_state is (
        CancellationResultingState.CANCELLED_NON_SCIENTIFIC
    )
    assert infrastructure.resulting_state is (
        CancellationResultingState.INFRASTRUCTURE_UNAVAILABLE_NON_SCIENTIFIC
    )
    assert type(requester.enforcement_event_binding) is NoEnforcementEvent
    assert requester.authority_marker is (
        ResourcePolicyAuthorityMarker.RESOURCE_STOP_NOT_SCIENTIFIC_OUTCOME
    )


def test_cancellation_actor_identity_reason_and_work_matrix_fail_closed(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    wrong_requester = FixtureRequesterActor(
        _pinned(state, "fixture_registration", "wrong_requester")
    )
    wrong_policy_actor = PolicyEnforcerActor(
        _pinned(state, "policy_authority", "wrong_policy_authority")
    )

    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(state, actor=wrong_requester)
    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(
            state,
            actor=wrong_policy_actor,
            reason=CancellationReason.CAPACITY_WITHDRAWN,
            stop_point=AtEnforcementPoint(EnforcementPoint.PRE_EXECUTION),
            work_started=True,
        )
    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(state, work_started=0)
    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(
            state,
            stop_point=AtEnforcementPoint(EnforcementPoint.PRE_EXECUTION),
        )


@pytest.mark.parametrize(
    ("reason", "field"),
    (
        (CancellationReason.CAPACITY_WITHDRAWN, "validator_capacity"),
        (CancellationReason.FUNDING_WITHDRAWN, "reconstruction_funding"),
        (CancellationReason.QUEUE_WITHDRAWN, "queue_availability"),
        (
            CancellationReason.EVIDENCE_BUDGET_WITHDRAWN,
            "evidence_budget_availability",
        ),
    ),
)
def test_each_required_readiness_withdrawal_defers_evidence_only(
    tmp_path: Path,
    reason: CancellationReason,
    field: str,
) -> None:
    state = _state(tmp_path)
    record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=reason,
        stop_point=AtEnforcementPoint(EnforcementPoint.PRE_EXECUTION),
        work_started=True,
    )

    assert record.resulting_state is CancellationResultingState.EVIDENCE_DEFERRED
    assert (
        type(
            getattr(
                state.fixture.policy.class_bindings[0].readiness_requirements,
                field,
            )
        )
        is OperationalRequirementRequired
    )


def test_not_applicable_readiness_cannot_be_withdrawn(tmp_path: Path) -> None:
    base = _state(tmp_path)
    reason_ref = _pinned(
        base,
        "applicability_reason",
        "funding_not_applicable",
    )
    requirements = OperationalReadinessRequirements(
        OperationalRequirementRequired(),
        OperationalRequirementNotApplicable(reason_ref),
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
    )
    fixture = make_resource_policy_fixture(
        tmp_path,
        readiness_requirements=requirements,
    )
    provided = availability(
        fixture,
        reconstruction_funding=FixtureAvailabilityState.NOT_APPLICABLE,
    )
    state = _state(
        tmp_path,
        availability_input=provided,
        readiness_requirements=requirements,
    )

    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(
            state,
            actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
            reason=CancellationReason.FUNDING_WITHDRAWN,
            stop_point=AtEnforcementPoint(EnforcementPoint.PRE_EXECUTION),
            work_started=True,
        )


@pytest.mark.parametrize(
    ("limit_id", "kind", "work_started", "point"),
    (
        (
            "pre_allocation_limit",
            EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL,
            False,
            EnforcementPoint.PRE_ALLOCATION_READINESS,
        ),
        (
            "pre_execution_limit",
            EnforcementObservationKind.ATTEMPTED_NEXT_TOTAL,
            True,
            EnforcementPoint.PRE_EXECUTION,
        ),
        (
            "runtime_limit",
            EnforcementObservationKind.CURRENT_TOTAL,
            True,
            EnforcementPoint.RUNTIME_OBSERVATION,
        ),
    ),
)
def test_policy_limit_record_binds_exact_event_point_and_work_state(
    tmp_path: Path,
    limit_id: str,
    kind: EnforcementObservationKind,
    work_started: bool,
    point: EnforcementPoint,
) -> None:
    state = _state(tmp_path)
    result = _enforcement(state, limit_id=limit_id, kind=kind)
    observations = (
        (
            _quantity(
                state,
                "consumed_units",
                21,
                ResourceObservationRole.RESOURCE_CONSUMPTION,
            ),
        )
        if work_started
        else ()
    )
    record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.POLICY_LIMIT_REACHED,
        stop_point=AtEnforcementPoint(point),
        work_started=work_started,
        observed_resource_quantities_so_far=observations,
        enforcement_result=result,
    )

    assert result.outcome is ResourceEnforcementOutcome.STOPPED_OVER_LIMIT
    assert record.enforcement_event_binding == result.event
    assert record.work_started is work_started
    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(
            state,
            actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
            reason=CancellationReason.POLICY_LIMIT_REACHED,
            stop_point=AtEnforcementPoint(point),
            work_started=not work_started,
            enforcement_result=result,
        )
    if limit_id == "runtime_limit":
        with pytest.raises(ResourcePolicyInputRejected):
            _cancel(
                state,
                actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
                reason=CancellationReason.POLICY_LIMIT_REACHED,
                stop_point=AtEnforcementPoint(point),
                work_started=True,
                observed_resource_quantities_so_far=(),
                enforcement_result=result,
            )
        with pytest.raises(ResourcePolicyInputRejected):
            _cancel(
                state,
                actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
                reason=CancellationReason.POLICY_LIMIT_REACHED,
                stop_point=AtEnforcementPoint(point),
                work_started=True,
                observed_resource_quantities_so_far=(
                    replace(observations[0], quantity=20),
                ),
                enforcement_result=result,
            )


def test_enforcement_failure_has_distinct_fail_closed_cancellation(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    result = _enforcement(
        state,
        metric_id="latency_units",
    )
    record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.ENFORCEMENT_FAILURE,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
        enforcement_result=result,
    )

    assert result.outcome is ResourceEnforcementOutcome.ENFORCEMENT_FAILURE
    assert record.reason is CancellationReason.ENFORCEMENT_FAILURE
    assert record.resulting_state is (
        CancellationResultingState.CANCELLED_NON_SCIENTIFIC
    )


def test_current_total_failure_preserves_exact_class_metric_but_not_hostile_metric(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    exact_metric_failure = _enforcement(
        state,
        metric_id="latency_units",
        role=ResourceObservationRole.OBSERVED_LATENCY,
    )
    exact_quantity = exact_metric_failure.event.observation.metric_quantity
    exact_record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.ENFORCEMENT_FAILURE,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
        observed_resource_quantities_so_far=(exact_quantity,),
        enforcement_result=exact_metric_failure,
    )

    assert exact_record.observed_resource_quantities_so_far == (exact_quantity,)
    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(
            state,
            actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
            reason=CancellationReason.ENFORCEMENT_FAILURE,
            stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
            work_started=True,
            observed_resource_quantities_so_far=(),
            enforcement_result=exact_metric_failure,
        )

    hostile_failure = _enforcement(state, metric_id="hostile_metric")
    hostile_record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.ENFORCEMENT_FAILURE,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
        observed_resource_quantities_so_far=(),
        enforcement_result=hostile_failure,
    )
    assert hostile_record.observed_resource_quantities_so_far == ()
    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(
            state,
            actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
            reason=CancellationReason.ENFORCEMENT_FAILURE,
            stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
            work_started=True,
            observed_resource_quantities_so_far=(
                hostile_failure.event.observation.metric_quantity,
            ),
            enforcement_result=hostile_failure,
        )

    preallocation_failure = _enforcement(
        state,
        limit_id="pre_allocation_limit",
        kind=EnforcementObservationKind.CURRENT_TOTAL,
    )
    preallocation_record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.ENFORCEMENT_FAILURE,
        stop_point=AtEnforcementPoint(EnforcementPoint.PRE_ALLOCATION_READINESS),
        work_started=False,
        observed_resource_quantities_so_far=(),
        enforcement_result=preallocation_failure,
    )
    assert preallocation_record.work_started is False
    assert preallocation_record.observed_resource_quantities_so_far == ()


@pytest.mark.parametrize(
    "event_override",
    (
        {"limit_id": "forged_limit"},
        {"maximum_quantity": 19},
    ),
)
def test_digest_valid_enforcement_result_is_recomputed_against_active_limit(
    tmp_path: Path,
    event_override: dict[str, object],
) -> None:
    state = _state(tmp_path)
    exact_result = _enforcement(state)
    forged_event = replace(exact_result.event, **event_override)
    forged_result = replace(exact_result, event=forged_event)

    with pytest.raises(ResourcePolicyInputRejected):
        _cancel(
            state,
            actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
            reason=CancellationReason.POLICY_LIMIT_REACHED,
            stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
            work_started=True,
            observed_resource_quantities_so_far=(
                forged_event.observation.metric_quantity,
            ),
            enforcement_result=forged_result,
        )

    exact_record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.POLICY_LIMIT_REACHED,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
        observed_resource_quantities_so_far=(
            exact_result.event.observation.metric_quantity,
        ),
        enforcement_result=exact_result,
    )
    forged_record = replace(
        exact_record,
        enforcement_event_binding=forged_event,
    )
    forged_record_ref = resource_cancellation_record_to_ref(forged_record)
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            state,
            build_completion=IncompleteBuild(_incomplete_identity(state)),
            observed_consumption_quantities=(forged_event.observation.metric_quantity,),
            observed_latency=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            observed_cost=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            stop_cause=ResourceStopCause.POLICY_LIMIT_REACHED,
            stop_record=forged_record,
            stop_record_ref=forged_record_ref,
            enforcement_result=forged_result,
        )


def test_complete_receipt_is_observed_facts_only_and_content_addressed(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    before = resolved_construction_plan_canonical_bytes(state.fixture.plan)
    receipt, receipt_ref = _issued_receipt(state)
    payload = encode_observed_resource_receipt(receipt)

    assert (
        decode_observed_resource_receipt(payload, expected_ref=receipt_ref) == receipt
    )
    assert _validate_receipt(state, receipt, receipt_ref) == (receipt, receipt_ref)
    assert receipt.epistemic_layer is ResourceEpistemicLayer.OBSERVED_RESOURCE_RECEIPT
    assert receipt.authority_marker is (
        ResourcePolicyAuthorityMarker.RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE
    )
    assert not hasattr(receipt, "price")
    assert not hasattr(receipt, "score")
    assert resolved_construction_plan_canonical_bytes(state.fixture.plan) == before


def test_semantic_validator_rejects_self_addressed_completed_receipt_forgery(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    receipt, _ = _issued_receipt(state)
    wrong_environment = EnvironmentPin("wrong_environment", "1.0", _DIGEST)
    forged_environment = replace(
        receipt,
        build_completion=CompleteBuild(
            replace(
                receipt.build_completion.build_identity,
                execution_environment_pin=wrong_environment,
            )
        ),
    )
    forged_metric = replace(
        receipt,
        observed_consumption_quantities=(
            replace(
                receipt.observed_consumption_quantities[0],
                metric_id="forged_consumption_metric",
            ),
        ),
    )

    for forged in (forged_environment, forged_metric):
        forged_ref = _structural_receipt_ref(forged)
        assert (
            decode_observed_resource_receipt(
                encode_observed_resource_receipt(forged),
                expected_ref=forged_ref,
            )
            == forged
        )
        with pytest.raises(ResourcePolicyInputRejected):
            _validate_receipt(state, forged, forged_ref)


def test_prework_deferred_receipt_obeys_complete_no_work_law(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path, availability_input=NO_AVAILABILITY_INPUT)
    receipt = _receipt(
        state,
        build_completion=NoBuildStarted(),
        reconstruction_replicate=ReplicateNotApplicable(
            ReplicateNotApplicableReason.NO_WORK_STARTED
        ),
        observed_consumption_quantities=(),
        observed_latency=ObservedMetricUnavailable(
            ObservationUnavailableReason.NO_WORK_STARTED
        ),
        observed_cost=ObservedMetricUnavailable(
            ObservationUnavailableReason.NO_WORK_STARTED
        ),
        evidence_stage_label=DeclaredResourceEvidenceStage.NO_WORK_STARTED,
        stop_cause=ResourceStopCause.EVIDENCE_DEFERRED,
        work_started=False,
    )

    assert type(receipt.build_completion) is NoBuildStarted
    assert type(receipt.stop_record_binding) is NoResourceStop
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            state,
            build_completion=NoBuildStarted(),
            reconstruction_replicate=ReplicateNotApplicable(
                ReplicateNotApplicableReason.NO_WORK_STARTED
            ),
            observed_consumption_quantities=(),
            observed_latency=ObservedMetricUnavailable(
                ObservationUnavailableReason.NO_WORK_STARTED
            ),
            observed_cost=ObservedMetricUnavailable(
                ObservationUnavailableReason.NO_WORK_STARTED
            ),
            evidence_stage_label=DeclaredResourceEvidenceStage.NO_WORK_STARTED,
            stop_cause=ResourceStopCause.EVIDENCE_DEFERRED,
            work_started=True,
        )


def test_policy_limit_receipt_requires_same_stop_record_and_event(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    result = _enforcement(state)
    stopped_quantity = _quantity(
        state,
        "consumed_units",
        21,
        ResourceObservationRole.RESOURCE_CONSUMPTION,
    )
    record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.POLICY_LIMIT_REACHED,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
        observed_resource_quantities_so_far=(stopped_quantity,),
        enforcement_result=result,
    )
    record_ref = resource_cancellation_record_to_ref(record)
    receipt = _receipt(
        state,
        build_completion=IncompleteBuild(_incomplete_identity(state)),
        observed_consumption_quantities=(stopped_quantity,),
        observed_latency=ObservedMetricUnavailable(
            ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
        ),
        observed_cost=ObservedMetricUnavailable(
            ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
        ),
        stop_cause=ResourceStopCause.POLICY_LIMIT_REACHED,
        stop_record=record,
        stop_record_ref=record_ref,
        enforcement_result=result,
    )

    assert receipt.enforcement_event_binding == result.event
    assert receipt.stop_record_binding == record_ref
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            state,
            build_completion=IncompleteBuild(_incomplete_identity(state)),
            observed_consumption_quantities=(stopped_quantity,),
            observed_latency=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            observed_cost=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            stop_cause=ResourceStopCause.POLICY_LIMIT_REACHED,
            stop_record=record,
            stop_record_ref=record_ref,
        )
    for final_consumption in (
        (),
        (replace(stopped_quantity, quantity=20),),
    ):
        with pytest.raises(ResourcePolicyInputRejected):
            _receipt(
                state,
                build_completion=IncompleteBuild(_incomplete_identity(state)),
                observed_consumption_quantities=final_consumption,
                observed_latency=ObservedMetricUnavailable(
                    ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
                ),
                observed_cost=ObservedMetricUnavailable(
                    ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
                ),
                stop_cause=ResourceStopCause.POLICY_LIMIT_REACHED,
                stop_record=record,
                stop_record_ref=record_ref,
                enforcement_result=result,
            )


def test_enforcement_infrastructure_and_poststart_deferral_receipt_cross_laws(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    failed_enforcement = _enforcement(state, metric_id="latency_units")
    enforcement_record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.ENFORCEMENT_FAILURE,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
        enforcement_result=failed_enforcement,
    )
    enforcement_record_ref = resource_cancellation_record_to_ref(enforcement_record)
    enforcement_receipt = _receipt(
        state,
        build_completion=IncompleteBuild(_incomplete_identity(state)),
        observed_consumption_quantities=(),
        observed_latency=ObservedMetricUnavailable(
            ObservationUnavailableReason.OBSERVATION_FAILED
        ),
        observed_cost=ObservedMetricUnavailable(
            ObservationUnavailableReason.OBSERVATION_FAILED
        ),
        stop_cause=ResourceStopCause.ENFORCEMENT_FAILURE,
        stop_record=enforcement_record,
        stop_record_ref=enforcement_record_ref,
        enforcement_result=failed_enforcement,
    )

    infrastructure_record = _cancel(
        state,
        actor=InfrastructureActor(
            _pinned(state, "infrastructure_failure", "fixture_runtime_failure")
        ),
        reason=CancellationReason.INFRASTRUCTURE_FAILURE,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
    )
    infrastructure_record_ref = resource_cancellation_record_to_ref(
        infrastructure_record
    )
    infrastructure_receipt = _receipt(
        state,
        build_completion=IncompleteBuild(_incomplete_identity(state)),
        observed_consumption_quantities=(),
        observed_latency=ObservedMetricUnavailable(
            ObservationUnavailableReason.INFRASTRUCTURE_FAILURE
        ),
        observed_cost=ObservedMetricUnavailable(
            ObservationUnavailableReason.INFRASTRUCTURE_FAILURE
        ),
        stop_cause=ResourceStopCause.INFRASTRUCTURE_FAILURE,
        stop_record=infrastructure_record,
        stop_record_ref=infrastructure_record_ref,
    )

    deferred_record = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.CAPACITY_WITHDRAWN,
        stop_point=AtEnforcementPoint(EnforcementPoint.PRE_EXECUTION),
        work_started=True,
    )
    deferred_record_ref = resource_cancellation_record_to_ref(deferred_record)
    deferred_receipt = _receipt(
        state,
        build_completion=IncompleteBuild(_incomplete_identity(state)),
        observed_consumption_quantities=(),
        observed_latency=ObservedMetricUnavailable(
            ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
        ),
        observed_cost=ObservedMetricUnavailable(
            ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
        ),
        stop_cause=ResourceStopCause.EVIDENCE_DEFERRED,
        stop_record=deferred_record,
        stop_record_ref=deferred_record_ref,
    )

    assert enforcement_receipt.enforcement_event_binding == (failed_enforcement.event)
    assert infrastructure_receipt.stop_cause is (
        ResourceStopCause.INFRASTRUCTURE_FAILURE
    )
    assert deferred_receipt.stop_cause is ResourceStopCause.EVIDENCE_DEFERRED


def test_receipt_cannot_erase_or_decrease_stop_time_observation(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    earlier = _quantity(
        state,
        "consumed_units",
        10,
        ResourceObservationRole.RESOURCE_CONSUMPTION,
    )
    record = _cancel(
        state,
        stop_point=AtEnforcementPoint(EnforcementPoint.RUNTIME_OBSERVATION),
        work_started=True,
        observed_resource_quantities_so_far=(earlier,),
    )
    record_ref = resource_cancellation_record_to_ref(record)
    common = {
        "build_completion": IncompleteBuild(_incomplete_identity(state)),
        "observed_latency": ObservedMetricUnavailable(
            ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
        ),
        "observed_cost": ObservedMetricUnavailable(
            ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
        ),
        "stop_cause": ResourceStopCause.CANCELLED,
        "stop_record": record,
        "stop_record_ref": record_ref,
    }

    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(state, observed_consumption_quantities=(), **common)
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            state,
            observed_consumption_quantities=(replace(earlier, quantity=9),),
            **common,
        )
    receipt = _receipt(
        state,
        observed_consumption_quantities=(replace(earlier, quantity=11),),
        **common,
    )
    assert receipt.observed_consumption_quantities[0].quantity == 11


def test_receipt_rejects_digest_valid_stop_with_wrong_policy_authority(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    exact = _cancel(
        state,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.CAPACITY_WITHDRAWN,
        stop_point=AtEnforcementPoint(EnforcementPoint.PRE_EXECUTION),
        work_started=True,
    )
    forged = replace(
        exact,
        actor=PolicyEnforcerActor(
            _pinned(state, "policy_authority", "wrong_policy_authority")
        ),
    )
    forged_ref = resource_cancellation_record_to_ref(forged)

    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            state,
            build_completion=IncompleteBuild(_incomplete_identity(state)),
            observed_consumption_quantities=(),
            observed_latency=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            observed_cost=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            stop_cause=ResourceStopCause.EVIDENCE_DEFERRED,
            stop_record=forged,
            stop_record_ref=forged_ref,
        )


def test_receipt_rejects_digest_valid_withdrawal_of_not_applicable_readiness(
    tmp_path: Path,
) -> None:
    base = _state(tmp_path)
    reason_ref = _pinned(
        base,
        "applicability_reason",
        "funding_not_applicable_for_receipt",
    )
    requirements = OperationalReadinessRequirements(
        OperationalRequirementRequired(),
        OperationalRequirementNotApplicable(reason_ref),
        OperationalRequirementRequired(),
        OperationalRequirementRequired(),
    )
    fixture = make_resource_policy_fixture(
        tmp_path,
        readiness_requirements=requirements,
    )
    provided = availability(
        fixture,
        reconstruction_funding=FixtureAvailabilityState.NOT_APPLICABLE,
    )
    state = _state(
        tmp_path,
        availability_input=provided,
        readiness_requirements=requirements,
    )
    requester = _cancel(
        state,
        stop_point=AtEnforcementPoint(EnforcementPoint.PRE_EXECUTION),
        work_started=True,
    )
    forged = replace(
        requester,
        actor=PolicyEnforcerActor(state.fixture.policy.policy_authority_ref),
        reason=CancellationReason.FUNDING_WITHDRAWN,
        resulting_state=CancellationResultingState.EVIDENCE_DEFERRED,
    )
    forged_ref = resource_cancellation_record_to_ref(forged)

    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            state,
            build_completion=IncompleteBuild(_incomplete_identity(state)),
            observed_consumption_quantities=(),
            observed_latency=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            observed_cost=ObservedMetricUnavailable(
                ObservationUnavailableReason.CANCELLED_BEFORE_OBSERVATION
            ),
            stop_cause=ResourceStopCause.EVIDENCE_DEFERRED,
            stop_record=forged,
            stop_record_ref=forged_ref,
        )


def test_receipt_rejects_wrong_environment_metric_and_future_price_shape(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    wrong_environment = EnvironmentPin("wrong_environment", "1.0", _DIGEST)
    wrong_identity = replace(
        _complete_identity(state),
        execution_environment_pin=wrong_environment,
    )

    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(state, build_completion=CompleteBuild(wrong_identity))
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(
            state,
            observed_cost=ObservedMetricObserved(
                _quantity(
                    state,
                    "latency_units",
                    7,
                    ResourceObservationRole.RESOURCE_COST_NOT_PRICE,
                )
            ),
        )
    with pytest.raises(ResourcePolicyInputRejected):
        _receipt(state, observed_cost={"price": 7, "currency": "USD"})


def test_replicate_receipt_uses_exact_bound_identity_only_when_completed(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    replicate = ReconstructionReplicateIdentity(
        state.fixture.compile_fixture.key,
        state.fixture.plan_ref,
        state.fixture.policy_ref,
        state.fixture.resource_class_ref,
        "fixture_replicate",
        _DIGEST,
    )
    receipt = _receipt(
        state,
        reconstruction_replicate=BoundReconstructionReplicate(replicate),
        evidence_stage_label=(
            DeclaredResourceEvidenceStage.DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING
        ),
    )

    assert type(receipt.reconstruction_replicate) is BoundReconstructionReplicate


def test_cancellation_and_receipt_round_trip_with_distinct_nominal_refs(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    record = _cancel(state)
    record_ref = resource_cancellation_record_to_ref(record)
    receipt, receipt_ref = _issued_receipt(state)

    assert (
        decode_resource_cancellation_record(
            encode_resource_cancellation_record(record),
            expected_ref=record_ref,
        )
        == record
    )
    assert (
        decode_observed_resource_receipt(
            encode_observed_resource_receipt(receipt),
            expected_ref=receipt_ref,
        )
        == receipt
    )
    assert type(record_ref) is not type(receipt_ref)

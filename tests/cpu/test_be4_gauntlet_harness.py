"""Focused B-E4 fail-closed harness and semantic-fixture tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from b07c_fixtures import make_fixture

from carbon.gauntlet import (
    AgentProfile,
    ConditionalLeakageObservation,
    EngineeringObservation,
    ExperimentalArm,
    GauntletPreflightError,
    GauntletPreregistration,
    GauntletRecord,
    GauntletStatus,
    HeldoutToyShadowCases,
    IntegrityCase,
    IntegrityDisposition,
    IntegrityObservation,
    MatchedBudget,
    OwnerRatification,
    RatifyingOwner,
    RunIdentity,
    validate_experiment_matrix,
    validate_integrity_matrix,
)
from carbon.practice import PracticeAggregateKind
from carbon.registry import ChallengeKey
from carbon.research import (
    PriorChannel,
    PriorPackRef,
    ResearchEvidenceClass,
    ResearchServiceErrorCode,
)
from carbon.research import (
    TestOnlyPriorAuthorizationReceiptRef as AuthorizationReceiptRef,
)
from carbon.toy import (
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_TRAINING_OBSERVATIONS,
    construct_fixture_model,
    evaluate_fixture_reference,
)

DIGEST = "sha256:" + "a" * 64


def _preregistration(*, complete: bool) -> GauntletPreregistration:
    if not complete:
        return GauntletPreregistration()
    ratifications = tuple(
        OwnerRatification(owner, DIGEST, f"fixture-{owner.value.lower()}-ratification")
        for owner in RatifyingOwner
    )
    return GauntletPreregistration(
        DIGEST,
        "owner-supplied-agent-profile-registration",
        "owner-supplied-matched-budget-registration",
        "owner-supplied-utility-estimand",
        "owner-supplied-practical-effect-floor",
        "owner-supplied-uncertainty-aware-rule",
        "owner-supplied-diversity-metric",
        "owner-supplied-diversity-floor",
        "owner-supplied-conditional-leakage-limit",
        ratifications,
    )


def _pins() -> tuple[PriorPackRef, AuthorizationReceiptRef]:
    key = ChallengeKey("be4_fixture", "1.0")
    return (
        PriorPackRef(key, PriorChannel.TEST_ONLY_FIXTURE, 1, DIGEST),
        AuthorizationReceiptRef(key, "be4_fixture_authorization", DIGEST),
    )


def _runs() -> tuple[RunIdentity, ...]:
    pack, receipt = _pins()
    return tuple(
        RunIdentity(
            profile,
            arm,
            replicate,
            pack if arm is ExperimentalArm.V2_TEST_ONLY_PRIOR else None,
            receipt if arm is ExperimentalArm.V2_TEST_ONLY_PRIOR else None,
        )
        for profile in AgentProfile
        for arm in ExperimentalArm
        for replicate in range(2)
    )


def _budgets() -> tuple[MatchedBudget, ...]:
    return tuple(MatchedBudget(profile, 60.0, 100.0, 4) for profile in AgentProfile)


def test_missing_preregistration_blocks_qualifying_execution() -> None:
    preregistration = _preregistration(complete=False)
    assert "utility_estimand" in preregistration.missing_inputs
    assert "ratification:security" in preregistration.missing_inputs
    with pytest.raises(GauntletPreflightError, match="qualifying gauntlet blocked"):
        validate_experiment_matrix(
            preregistration=preregistration, budgets=_budgets(), runs=_runs()
        )
    with pytest.raises(ValueError, match="blocked before complete preregistration"):
        GauntletRecord(preregistration, (), (), (), (), qualifying_execution=True)


def test_complete_matrix_freezes_exact_v2_pack_and_receipt() -> None:
    validate_experiment_matrix(
        preregistration=_preregistration(complete=True),
        budgets=_budgets(),
        runs=_runs(),
    )
    runs = list(_runs())
    second_pack = replace(runs[-1].prior_pack_ref, publication_sequence=2)
    runs[-1] = replace(runs[-1], prior_pack_ref=second_pack)
    with pytest.raises(GauntletPreflightError, match="freeze one exact"):
        validate_experiment_matrix(
            preregistration=_preregistration(complete=True),
            budgets=_budgets(),
            runs=tuple(runs),
        )


def test_raw_observations_remain_separate_from_preregistered_decisions() -> None:
    observation = EngineeringObservation(
        _runs()[0],
        1.0,
        2.0,
        3.0,
        2,
        0.2,
        0.3,
        True,
        1,
        4,
        ("fixture_sampling_level",),
        DIGEST,
    )
    integrity = tuple(
        IntegrityObservation(
            case,
            IntegrityDisposition.TYPED_REJECTION,
            ResearchServiceErrorCode.DISCLOSURE_REJECTED,
        )
        for case in IntegrityCase
    )
    leakage = ConditionalLeakageObservation(0.2, 0.1, 0.1, DIGEST)
    record = GauntletRecord(
        _preregistration(complete=False),
        _budgets(),
        (observation,),
        integrity,
        (leakage,),
    )
    assert observation.invalid_run_rate == 0.25
    assert record.status is GauntletStatus.BLOCKED_PREREGISTRATION
    assert len(record.integrity_observations) == len(IntegrityCase)
    validate_integrity_matrix(integrity)
    assert not hasattr(record, "utility_passed")


def test_shared_toy_semantics_make_registered_level_causal() -> None:
    coefficient_one, _ = construct_fixture_model(
        FIXTURE_TRAINING_OBSERVATIONS, 1, b"\x00" * 32
    )
    coefficient_two, _ = construct_fixture_model(
        FIXTURE_TRAINING_OBSERVATIONS, 2, b"\x00" * 32
    )
    error_one = evaluate_fixture_reference(
        coefficient_one, FIXTURE_HELDOUT_OBSERVATIONS
    )
    error_two = evaluate_fixture_reference(
        coefficient_two, FIXTURE_HELDOUT_OBSERVATIONS
    )
    assert coefficient_one != coefficient_two
    assert error_one != error_two


def test_practice_uses_toy_semantics_and_stays_non_authoritative(tmp_path) -> None:
    fixture = make_fixture(tmp_path)
    started = fixture.provider.start_research_task(fixture.request("paired"))
    result = fixture.provider.run_queued_task(started.task.task_id)
    private_record = fixture.provider.get_experiment_record(started.task.task_id)
    aggregate_ref = private_record.aggregate_outcome_refs[0]
    aggregate = fixture.practice.get_private_aggregate(aggregate_ref)
    assert aggregate.kind is PracticeAggregateKind.PAIRED_DIFFERENCE
    assert aggregate.aggregate_value != 0.0
    assert (
        private_record.evidence_class
        is ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE
    )
    assert "NOT_OFFICIAL_EVIDENCE" in result.terminal_receipt.limitations


def test_shadow_cases_are_evaluator_held_and_nonserializable() -> None:
    shadow = HeldoutToyShadowCases(
        distribution_ref="declared-synthetic-fixture-distribution-v1",
        cases=((5, 25), (6, 36)),
    )
    assert shadow.evaluate(2.0) > 0.0
    assert repr(shadow) == "HeldoutToyShadowCases(<evaluator-held>)"
    assert not hasattr(shadow, "cases")
    with pytest.raises(TypeError, match="cannot be serialized"):
        shadow.__getstate__()

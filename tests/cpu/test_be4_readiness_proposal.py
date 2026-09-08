"""B-E4 v3 owner proposals remain content-bound and non-authoritative."""

from __future__ import annotations

import json
import math

import pytest

from carbon.gauntlet.agents import fixture_driver_ref
from carbon.gauntlet.design import (
    DECISION_RULE_ID,
    DIVERSITY_METRIC_ID,
    PRIMARY_ESTIMAND_ID,
    PROTECTED_TARGETS,
    REQUIRED_DESIGN_INPUTS,
)
from carbon.gauntlet.meter import METER_POLICY_DIGEST
from carbon.gauntlet.model import AgentProfile, GauntletPreregistration
from carbon.gauntlet.proposal import (
    ENGINEERING_COMPONENT_AUTHORITY_CEILING,
    FIXTURE_LOSS_BEST,
    FIXTURE_LOSS_WORST,
    FIXTURE_PARITY_ROBUST_REFERENCE_STEP,
    FIXTURE_PRACTICAL_EFFECT_FLOOR,
    FIXTURE_PRIMARY_TRANSFORM,
    FIXTURE_SEMANTIC_RESOLUTION,
    FIXTURE_TRANSFER_LOSS_BEST,
    FIXTURE_TRANSFER_LOSS_WORST,
    FIXTURE_TRANSFER_TRANSFORM,
    HISTORICAL_V2_DESIGN_DIGEST,
    NONQUALIFYING_SENSITIVITY_AUTHORITY_CEILING,
    READINESS_PROPOSAL_AUTHORITY_CEILING,
    READINESS_PROPOSAL_SCHEMA_VERSION,
    REQUIRED_ENGINEERING_READINESS_SECTIONS,
    REQUIRED_HUMAN_REQUIREMENTS,
    ExecutionReadinessProposal,
    ReadinessProposalError,
    derive_fixture_grid_geometry,
    derive_v3_resource_estimate,
    fixture_primary_quality,
    fixture_transfer_quality,
    parse_execution_readiness_proposal,
    run_nonqualifying_v3_sensitivity_analysis,
)

_OWNERS = {
    "representative_agent_profiles": ["RESEARCH", "EXACT_PROTOCOL"],
    "matched_time_compute_budgets": ["RESEARCH", "STATISTICS", "EXACT_PROTOCOL"],
    "utility_estimand": ["SCIENCE", "STATISTICS", "RESEARCH"],
    "practical_effect_floor": ["SCIENCE", "STATISTICS"],
    "uncertainty_aware_decision_rule": ["STATISTICS", "SCIENCE", "RESEARCH"],
    "intervention_diversity_metric": [
        "SCIENCE",
        "STATISTICS",
        "RESEARCH",
        "SECURITY",
    ],
    "intervention_diversity_floor": [
        "SCIENCE",
        "STATISTICS",
        "RESEARCH",
        "SECURITY",
    ],
    "conditional_leakage_limit": ["SECURITY", "STATISTICS", "EXACT_PROTOCOL"],
}


def _recommended_values() -> dict[str, object]:
    return {
        "representative_agent_profiles": {
            "capability_policy": "B07S_PLUS_SUBMIT_RESULT_NO_EXTERNAL_IO_OR_CODE_EXECUTION",
            "model_provider": "NONE_DETERMINISTIC_FIXTURE_POLICY",
            "profiles": [
                {
                    "corpus_digest": fixture_driver_ref(profile).corpus_digest,
                    "driver_id": fixture_driver_ref(profile).driver_id,
                    "driver_version": fixture_driver_ref(profile).driver_version,
                    "policy_digest": fixture_driver_ref(profile).policy_digest,
                    "profile": profile.value,
                    "runtime_digest": fixture_driver_ref(profile).runtime_digest,
                }
                for profile in AgentProfile
            ],
        },
        "matched_time_compute_budgets": {
            "attempt_limit": 8,
            "block_failure_ceiling": 0.05,
            "fixture_units_per_run": 223,
            "meter_policy_digest": METER_POLICY_DIGEST,
            "profile_caps": [
                {
                    "normalized_compute_units": compute,
                    "profile": profile.value,
                    "wall_time_seconds": wall,
                }
                for profile, compute, wall in zip(
                    AgentProfile,
                    (35, 35, 39, 39, 20),
                    (1, 1, 1, 1, 1),
                )
            ],
            "replicates_per_profile": 636,
            "reserve_blocks_per_profile": 52,
            "reserve_retention_target": 0.99,
            "saved_time_creates_extra_attempts": False,
        },
        "utility_estimand": {
            "baseline_arms": ["NO_PRIOR", "GENERIC_PRIOR", "V1_DIRECTIVE_PRIOR"],
            "id": PRIMARY_ESTIMAND_ID,
            "invalid_candidate_q": 0.0,
            "loss_best": FIXTURE_LOSS_BEST,
            "loss_worst": FIXTURE_LOSS_WORST,
            "practical_reference_basis": "PARITY_ROBUST_MINIMUM_FEATURE_DEGREE_1_TO_2_Q_GAIN",
            "practical_reference_step": FIXTURE_PARITY_ROBUST_REFERENCE_STEP,
            "primary_endpoint": "INDEPENDENT_HELDOUT_TOY_MSE_Q",
            "primary_transform": FIXTURE_PRIMARY_TRANSFORM,
            "profile_weighting": "EQUAL_REGISTERED_PROFILE",
            "seed_design_status": "UNRESOLVED_CANDIDATE_BOUND_FIXTURE_SEED_BLOCKER",
            "semantic_resolution": FIXTURE_SEMANTIC_RESOLUTION,
            "transfer_contrast": "EQUAL_PROFILE_V2_MINUS_EACH_BASELINE",
            "transfer_endpoint": "TRANSFER_TOY_MSE_Q",
            "transfer_invalid_candidate_q": 0.0,
            "transfer_loss_best": FIXTURE_TRANSFER_LOSS_BEST,
            "transfer_loss_worst": FIXTURE_TRANSFER_LOSS_WORST,
            "transfer_role": "MANDATORY_NON_INFERIORITY_SUPPORT",
            "transfer_transform": FIXTURE_TRANSFER_TRANSFORM,
        },
        "practical_effect_floor": FIXTURE_PRACTICAL_EFFECT_FLOOR,
        "uncertainty_aware_decision_rule": {
            "equality_passes": False,
            "familywise_alpha": 0.05,
            "id": DECISION_RULE_ID,
            "indeterminate_distinct": True,
            "joint_power_target": 0.9,
            "paired_sd_bound": 1.0,
            "primary_contrasts": 3,
            "profile_nonregression_minimum": 4,
            "transfer_constraints": 3,
            "transfer_noninferiority_margin_q": FIXTURE_PRACTICAL_EFFECT_FLOOR,
        },
        "intervention_diversity_metric": DIVERSITY_METRIC_ID,
        "intervention_diversity_floor": {
            "maximum_family_share": 0.5,
            "minimum_effective_diversity": 2.0,
            "minimum_profile_prevalence": 0.1,
            "minimum_profiles": 4,
            "minimum_supported_families": 3,
        },
        "conditional_leakage_limit": {
            "clipping_policy": "epsilon_1_over_2_n_train_plus_1_renormalized/v1",
            "cross_profile_icc_assumption": 0.0,
            "cross_profile_icc_sensitivity": [
                {"replicates_per_profile": n, "rho": rho}
                for rho, n in zip(
                    (0.0, 0.25, 0.5, 0.75, 1.0),
                    (636, 1272, 1908, 2544, 3180),
                    strict=True,
                )
            ],
            "cross_profile_icc_status": "UNVALIDATED_RHO_ZERO_CONDITIONAL_PLANNING_ASSUMPTION",
            "effective_cluster_policy": "ONE_WHOLE_TRANSCRIPT_CLUSTER_PER_PROFILE_BLOCK_PROPOSED",
            "estimator_id": "cross_fitted_shadow_plus_transcript_log_loss/v1",
            "familywise_alpha": 0.05,
            "indeterminate_on_invalid_denominator": True,
            "limit": 0.05,
            "over_limit_alternative": 0.075,
            "planning_cluster_sd": 0.4,
            "planning_status": "UNVALIDATED_NO_SHADOW_CAMPAIGN",
            "protected_targets": list(PROTECTED_TARGETS),
            "single_target_detection_power_target": 0.9,
        },
    }


def _bind_preregistration_digest(payload: dict[str, object]) -> None:
    inputs = payload["design_inputs"]
    assert type(inputs) is dict
    encoded = {
        key: json.dumps(
            inputs[key]["recommended_value"],  # type: ignore[index]
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for key in REQUIRED_DESIGN_INPUTS
    }
    digest = GauntletPreregistration(**encoded).computed_design_digest
    assert digest is not None
    payload["preregistration_design_digest"] = digest


def _payload() -> dict[str, object]:
    recommendations = _recommended_values()
    inputs = {
        key: {
            "change_from_v2": "Prospective readiness evidence replaces an unresolved v2 placeholder.",
            "evidence_refs": [f"fixture-evidence:{key}"],
            "recommended_value": recommendations[key],
            "required_owners": _OWNERS[key],
            "status": "PROPOSED",
        }
        for key in REQUIRED_DESIGN_INPUTS
    }
    engineering = {
        key: {
            "authority_ceiling": ENGINEERING_COMPONENT_AUTHORITY_CEILING,
            "blockers": [],
            "component_ref": f"fixture-component:{key}/v1",
            "evidence_refs": [f"fixture-evidence:{key}/v1"],
            "state": "READY",
            "summary": "Bounded fixture-only readiness component.",
        }
        for key in REQUIRED_ENGINEERING_READINESS_SECTIONS
    }
    engineering["ratification_verifier"] = {
        "authority_ceiling": ENGINEERING_COMPONENT_AUTHORITY_CEILING,
        "blockers": ["AUTHENTICATED_ROLE_TRUST_ROOT_UNAVAILABLE"],
        "component_ref": "fixture-component:ratification-audit/v1",
        "evidence_refs": ["fixture-evidence:ratification-audit/v1"],
        "state": "BLOCKED",
        "summary": "Structural audit only; positive owner verification is unavailable.",
    }
    engineering["shadow_campaign"] = {
        "authority_ceiling": ENGINEERING_COMPONENT_AUTHORITY_CEILING,
        "blockers": ["CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED"],
        "component_ref": "fixture-component:shadow-campaign/v1",
        "evidence_refs": ["fixture-evidence:shadow-campaign/v1"],
        "state": "PARTIAL",
        "summary": "The proposed rho-zero planning assumption remains unvalidated.",
    }
    payload = {
        "authority_ceiling": READINESS_PROPOSAL_AUTHORITY_CEILING,
        "design_inputs": inputs,
        "engineering_readiness": engineering,
        "previous_design_digest": HISTORICAL_V2_DESIGN_DIGEST,
        "ratifications": [],
        "readiness": {
            "engineering_blockers": ["AUTHENTICATED_ROLE_TRUST_ROOT_UNAVAILABLE"],
            "human_ratifications_present": False,
            "human_requirements": list(REQUIRED_HUMAN_REQUIREMENTS),
            "qualifying_execution_ready": False,
        },
        "schema_version": READINESS_PROPOSAL_SCHEMA_VERSION,
        "status": "STILL_BLOCKED",
    }
    payload["readiness"]["engineering_blockers"] = [
        "AUTHENTICATED_ROLE_TRUST_ROOT_UNAVAILABLE",
        "CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED",
    ]
    _bind_preregistration_digest(payload)
    return payload


def _document(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def test_v3_proposal_is_content_bound_but_never_authoritative() -> None:
    proposal = parse_execution_readiness_proposal(_document(_payload()))
    assert proposal.status == "STILL_BLOCKED"
    assert proposal.engineering_blockers == (
        "AUTHENTICATED_ROLE_TRUST_ROOT_UNAVAILABLE",
        "CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED",
    )
    assert proposal.human_requirements == REQUIRED_HUMAN_REQUIREMENTS
    assert not proposal.qualifying_execution_ready
    assert not proposal.is_verified_owner_ratified
    assert repr(proposal) == "ExecutionReadinessProposal(<design-analysis-only>)"
    assert proposal.design_digest == proposal.preregistration_design_digest
    assert proposal.preregistration.is_syntactically_complete
    assert not proposal.preregistration.has_declared_ratifications

    changed = _payload()
    changed["design_inputs"]["matched_time_compute_budgets"][  # type: ignore[index]
        "recommended_value"
    ][
        "profile_caps"
    ][0]["normalized_compute_units"] = 36
    _bind_preregistration_digest(changed)
    assert (
        parse_execution_readiness_proposal(_document(changed)).design_digest
        != proposal.design_digest
    )
    engineering_only = _payload()
    engineering_only["engineering_readiness"]["meter"]["summary"] = (  # type: ignore[index]
        "Changed review-only summary."
    )
    engineering_proposal = parse_execution_readiness_proposal(
        _document(engineering_only)
    )
    assert engineering_proposal.design_digest == proposal.design_digest
    assert engineering_proposal.proposal_digest != proposal.proposal_digest
    with pytest.raises(TypeError, match="validating parser"):
        ExecutionReadinessProposal(
            proposal.canonical_payload,
            proposal.proposal_digest,
            proposal.preregistration,
            proposal.status,
            proposal.engineering_blockers,
            proposal.human_requirements,
            _factory_token=object(),
        )


def test_proposal_rejects_approval_and_execution_claims() -> None:
    payload = _payload()
    payload["ratifications"] = [{"owner": "SCIENCE", "approved": True}]
    with pytest.raises(ReadinessProposalError, match="cannot contain"):
        parse_execution_readiness_proposal(_document(payload))

    payload = _payload()
    payload["readiness"]["qualifying_execution_ready"] = True  # type: ignore[index]
    with pytest.raises(ReadinessProposalError, match="cannot authorize"):
        parse_execution_readiness_proposal(_document(payload))

    payload = _payload()
    payload["status"] = "EXECUTION_READY_PROPOSED"
    for value in payload["engineering_readiness"].values():  # type: ignore[union-attr]
        value["state"] = "READY"
        value["blockers"] = []
    payload["engineering_readiness"]["shadow_campaign"]["state"] = "PARTIAL"  # type: ignore[index]
    payload["engineering_readiness"]["shadow_campaign"]["blockers"] = [  # type: ignore[index]
        "CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED"
    ]
    payload["readiness"]["engineering_blockers"] = [  # type: ignore[index]
        "CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED"
    ]
    with pytest.raises(ReadinessProposalError, match="unavailable without a typed"):
        parse_execution_readiness_proposal(_document(payload))


def test_proposal_rejects_concealed_blockers_and_human_requirements() -> None:
    payload = _payload()
    payload["readiness"]["engineering_blockers"] = [  # type: ignore[index]
        "SUBSTITUTED_ROOT_BLOCKER"
    ]
    with pytest.raises(ReadinessProposalError, match="component-blocker union"):
        parse_execution_readiness_proposal(_document(payload))

    payload = _payload()
    payload["readiness"]["human_requirements"] = list(  # type: ignore[index]
        REQUIRED_HUMAN_REQUIREMENTS[:-1]
    )
    with pytest.raises(ReadinessProposalError, match="every exact remaining human"):
        parse_execution_readiness_proposal(_document(payload))


def test_proposal_rejects_missing_values_unknown_sections_and_hostile_json() -> None:
    payload = _payload()
    payload["design_inputs"]["utility_estimand"]["recommended_value"] = False  # type: ignore[index]
    with pytest.raises(ReadinessProposalError, match="exact registered keys"):
        parse_execution_readiness_proposal(_document(payload))

    payload = _payload()
    payload["engineering_readiness"]["parallel_authority"] = {}  # type: ignore[index]
    with pytest.raises(ReadinessProposalError, match="exact registered keys"):
        parse_execution_readiness_proposal(_document(payload))

    duplicate = _document(_payload()).replace("{", '{"status":"STILL_BLOCKED",', 1)
    with pytest.raises(ReadinessProposalError, match="duplicate JSON key"):
        parse_execution_readiness_proposal(duplicate)

    payload = _payload()
    payload["readiness"]["engineering_blockers"][0] = "\ud800"  # type: ignore[index]
    with pytest.raises(ReadinessProposalError, match="valid UTF-8"):
        parse_execution_readiness_proposal(_document(payload))


def test_proposal_rejects_asserted_authority_bad_owners_and_digest_mismatch() -> None:
    payload = _payload()
    payload["engineering_readiness"]["meter"][  # type: ignore[index]
        "authority_ceiling"
    ] = "LIVE_PRODUCTION_AND_SECURITY_QUALIFIED"
    with pytest.raises(ReadinessProposalError, match="fixture-only engineering"):
        parse_execution_readiness_proposal(_document(payload))

    payload = _payload()
    payload["design_inputs"]["utility_estimand"]["required_owners"] = [  # type: ignore[index]
        "RESEARCH"
    ]
    with pytest.raises(ReadinessProposalError, match="exact approving owners"):
        parse_execution_readiness_proposal(_document(payload))

    payload = _payload()
    payload["preregistration_design_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ReadinessProposalError, match="does not bind"):
        parse_execution_readiness_proposal(_document(payload))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        (
            "loss_worst",
            100.0,
            "loss anchors do not match the complete registered toy grid",
        ),
        (
            "semantic_resolution",
            0.03,
            "semantic resolution does not match the complete registered toy grid",
        ),
        (
            "practical_reference_step",
            0.7,
            "practical reference step is not the parity-robust feature-degree gain",
        ),
    ),
)
def test_proposal_rejects_rebound_mislabeled_fixture_values(
    field: str, value: float, message: str
) -> None:
    payload = _payload()
    utility = payload["design_inputs"]["utility_estimand"]["recommended_value"]
    utility[field] = value  # type: ignore[index]
    if field == "practical_reference_step":
        payload["design_inputs"]["practical_effect_floor"][  # type: ignore[index]
            "recommended_value"
        ] = (value / 2.0)
    _bind_preregistration_digest(payload)
    with pytest.raises(ReadinessProposalError, match=message):
        parse_execution_readiness_proposal(_document(payload))


def test_proposal_rejects_rebound_wrong_practical_floor() -> None:
    payload = _payload()
    payload["design_inputs"]["practical_effect_floor"][  # type: ignore[index]
        "recommended_value"
    ] = 0.35
    _bind_preregistration_digest(payload)
    with pytest.raises(ReadinessProposalError, match="practical floor"):
        parse_execution_readiness_proposal(_document(payload))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        (
            "primary_transform",
            "LINEAR_FROZEN_ANCHOR_QUALITY_Q/v1",
            "primary quality transform is unsupported",
        ),
        (
            "transfer_loss_worst",
            651.0,
            "transfer loss anchors do not match the complete registered toy grid",
        ),
        ("transfer_role", "PRIMARY", "transfer endpoint role is unsupported"),
        ("transfer_endpoint", "HELDOUT_Q", "transfer endpoint is unsupported"),
        (
            "transfer_contrast",
            "V2_MINUS_NO_PRIOR_ONLY",
            "transfer contrast is unsupported",
        ),
        (
            "transfer_transform",
            "ABSOLUTE_LOSS/v1",
            "transfer quality transform is unsupported",
        ),
        (
            "transfer_invalid_candidate_q",
            0.1,
            "invalid transfer outcomes must retain Q=0",
        ),
    ),
)
def test_proposal_rejects_rebound_wrong_transfer_definition(
    field: str, value: object, message: str
) -> None:
    payload = _payload()
    utility = payload["design_inputs"]["utility_estimand"]["recommended_value"]
    utility[field] = value  # type: ignore[index]
    _bind_preregistration_digest(payload)
    with pytest.raises(ReadinessProposalError, match=message):
        parse_execution_readiness_proposal(_document(payload))


def test_proposal_rejects_boolean_candidate_quality() -> None:
    payload = _payload()
    utility = payload["design_inputs"]["utility_estimand"]["recommended_value"]
    utility["transfer_invalid_candidate_q"] = False  # type: ignore[index]
    _bind_preregistration_digest(payload)
    with pytest.raises(ReadinessProposalError, match="bounded finite float"):
        parse_execution_readiness_proposal(_document(payload))


@pytest.mark.parametrize(
    ("value", "message"),
    (
        (
            FIXTURE_PRACTICAL_EFFECT_FLOOR + 0.01,
            "transfer noninferiority margin must equal the practical effect floor",
        ),
        (False, "bounded finite float"),
    ),
)
def test_proposal_rejects_rebound_transfer_margin(value: object, message: str) -> None:
    payload = _payload()
    rule = payload["design_inputs"]["uncertainty_aware_decision_rule"][  # type: ignore[index]
        "recommended_value"
    ]
    rule["transfer_noninferiority_margin_q"] = value
    _bind_preregistration_digest(payload)
    with pytest.raises(ReadinessProposalError, match=message):
        parse_execution_readiness_proposal(_document(payload))


def test_v3_quality_helpers_apply_exact_frozen_anchors() -> None:
    assert fixture_primary_quality(0.0) == 1.0
    assert fixture_primary_quality(90.0) == 0.0
    assert fixture_transfer_quality(0.0) == 1.0
    assert fixture_transfer_quality(650.0) == 0.0
    assert fixture_primary_quality(45.0) == pytest.approx(
        (math.log1p(90.0) - math.log1p(45.0)) / math.log1p(90.0)
    )
    assert fixture_transfer_quality(325.0) == pytest.approx(
        (math.log1p(650.0) - math.log1p(325.0)) / math.log1p(650.0)
    )


def test_v3_fixture_geometry_is_derived_from_the_complete_current_toy_grid() -> None:
    geometry = derive_fixture_grid_geometry()
    assert geometry.configuration_count == 16
    assert geometry.loss_best == FIXTURE_LOSS_BEST == 0.0
    assert geometry.loss_worst == FIXTURE_LOSS_WORST == 90.0
    assert geometry.transfer_loss_best == FIXTURE_TRANSFER_LOSS_BEST == 0.0
    assert geometry.transfer_loss_worst == FIXTURE_TRANSFER_LOSS_WORST == 650.0
    assert geometry.semantic_resolution == pytest.approx(
        FIXTURE_SEMANTIC_RESOLUTION, abs=1e-15
    )
    assert geometry.parity_robust_feature_step == pytest.approx(
        FIXTURE_PARITY_ROBUST_REFERENCE_STEP, abs=1e-15
    )


@pytest.mark.parametrize(
    ("transform", "loss"),
    (
        (fixture_primary_quality, -0.1),
        (fixture_primary_quality, 90.000001),
        (fixture_primary_quality, float("nan")),
        (fixture_primary_quality, 0),
        (fixture_transfer_quality, -0.1),
        (fixture_transfer_quality, 650.000001),
        (fixture_transfer_quality, float("inf")),
        (fixture_transfer_quality, False),
    ),
)
def test_v3_quality_helpers_fail_closed_on_hostile_losses(
    transform: object, loss: object
) -> None:
    with pytest.raises(ValueError, match="fixture losses|frozen fixture anchors"):
        transform(loss)  # type: ignore[operator]


def test_v3_nonqualifying_sensitivity_is_seeded_and_never_ready() -> None:
    proposal = parse_execution_readiness_proposal(_document(_payload()))
    first = run_nonqualifying_v3_sensitivity_analysis(
        proposal=proposal,
        simulation_seed=20260908,
        simulation_draws=20_000,
    )
    second = run_nonqualifying_v3_sensitivity_analysis(
        proposal=proposal,
        simulation_seed=20260908,
        simulation_draws=20_000,
    )
    assert first == second
    assert first.authority_ceiling == NONQUALIFYING_SENSITIVITY_AUTHORITY_CEILING
    assert not first.qualifying_execution_ready
    assert (
        first.aggregate_six_constraint_replicates_per_profile_unrounded
        == pytest.approx(22.447718245989485)
    )
    assert first.aggregate_six_constraint_replicates_per_profile_balanced == 24
    assert first.proposed_replicates_per_profile == 636
    assert first.aggregate_six_constraint_power_lower_bound_at_balanced_n > 0.9
    assert first.aggregate_six_constraint_power_lower_bound_at_proposed_n == 1.0
    assert first.leakage_null_clearance_union_lower_bound == pytest.approx(
        0.999996943921504
    )
    assert first.leakage_one_target_detection_probability == pytest.approx(
        0.9002654032997404
    )
    assert 0.9 < first.simulation_aggregate_six_constraint_pass_at_balanced_n < 0.95
    assert first.simulation_aggregate_six_constraint_pass_at_proposed_n == 1.0
    assert first.simulation_leakage_null_clearance == 1.0
    assert 0.89 < first.simulation_leakage_one_target_detection < 0.91
    assert [
        (point.rho, point.replicates_per_profile)
        for point in first.leakage_cross_profile_icc_sensitivity
    ] == [
        (0.0, 636),
        (0.25, 1272),
        (0.5, 1908),
        (0.75, 2544),
        (1.0, 3180),
    ]
    heterogeneity = {
        item.scenario_id: item for item in first.profile_heterogeneity_sensitivity
    }
    assert heterogeneity[
        "HOMOGENEOUS_REFERENCE_EFFECT"
    ].equal_profile_primary_effect == (
        pytest.approx(FIXTURE_PARITY_ROBUST_REFERENCE_STEP)
    )
    assert (
        heterogeneity[
            "HOMOGENEOUS_REFERENCE_EFFECT"
        ].simulated_full_rule_pass_probability_at_proposed_n
        == 1.0
    )
    assert (
        heterogeneity[
            "FOUR_POSITIVE_ONE_REGRESSION"
        ].simulated_full_rule_pass_probability_at_proposed_n
        == 1.0
    )
    assert (
        heterogeneity[
            "THREE_POSITIVE_TWO_REGRESSIONS"
        ].simulated_full_rule_pass_probability_at_proposed_n
        == 0.0
    )
    assert (
        heterogeneity["THREE_POSITIVE_TWO_REGRESSIONS"].equal_profile_primary_effect
        > FIXTURE_PRACTICAL_EFFECT_FLOOR
    )

    with pytest.raises(ValueError, match="between 1000 and 100000"):
        run_nonqualifying_v3_sensitivity_analysis(
            proposal=proposal, simulation_draws=999
        )
    with pytest.raises(TypeError, match="exact integer"):
        run_nonqualifying_v3_sensitivity_analysis(
            proposal=proposal, simulation_seed=False
        )


def test_v3_resource_estimate_is_mechanically_derived_from_registered_caps() -> None:
    proposal = parse_execution_readiness_proposal(_document(_payload()))
    estimate = derive_v3_resource_estimate(proposal)
    assert not estimate.qualifying_execution_ready
    assert estimate.complete_blocks_planned == 3_180
    assert estimate.complete_blocks_maximum == 3_440
    assert estimate.agent_arm_runs_planned == 12_720
    assert estimate.agent_arm_runs_maximum == 13_760
    assert estimate.policy_work_units_planned == 427_392
    assert estimate.policy_work_units_maximum == 462_336
    assert estimate.wall_seconds_planned == 12_720
    assert estimate.wall_seconds_maximum == 13_760
    assert estimate.fixture_units_planned == 2_836_560
    assert estimate.fixture_units_maximum == 3_068_480


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda leakage: leakage.__setitem__("cross_profile_icc_assumption", 0.25),
            "conditional on the unvalidated rho-zero",
        ),
        (
            lambda leakage: leakage["cross_profile_icc_sensitivity"][2].__setitem__(
                "replicates_per_profile", 1904
            ),
            "ICC sensitivity contradicts",
        ),
    ),
)
def test_v3_leakage_icc_assumption_and_sensitivity_fail_closed(
    mutation, message: str
) -> None:
    payload = _payload()
    leakage = payload["design_inputs"]["conditional_leakage_limit"]["recommended_value"]
    mutation(leakage)
    _bind_preregistration_digest(payload)
    with pytest.raises(ReadinessProposalError, match=message):
        parse_execution_readiness_proposal(_document(payload))


def test_v3_leakage_dependence_blocker_cannot_be_omitted() -> None:
    payload = _payload()
    shadow = payload["engineering_readiness"]["shadow_campaign"]  # type: ignore[index]
    shadow["blockers"].remove(  # type: ignore[index]
        "CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED"
    )
    shadow["state"] = "READY"  # type: ignore[index]
    payload["readiness"]["engineering_blockers"].remove(  # type: ignore[index]
        "CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED"
    )
    with pytest.raises(ReadinessProposalError, match="cross-profile dependence"):
        parse_execution_readiness_proposal(_document(payload))

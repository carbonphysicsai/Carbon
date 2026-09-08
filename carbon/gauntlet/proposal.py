"""Content binding for the post-calibration B-E4 owner proposal.

This is deliberately a review-artifact schema.  Parsing one of these files
proves only that its proposed values and readiness disclosures are internally
bound.  It cannot prove owner approval and cannot authorize an execution.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass
from itertools import pairwise, product
from statistics import NormalDist

from carbon.toy import (
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_TRAINING_OBSERVATIONS,
    FIXTURE_TRANSFER_OBSERVATIONS,
    construct_fixture_model,
    evaluate_fixture_reference,
)

from .agents import fixture_driver_ref
from .design import (
    DECISION_RULE_ID,
    DIVERSITY_METRIC_ID,
    PRIMARY_ESTIMAND_ID,
    PROTECTED_TARGETS,
    REQUIRED_DESIGN_INPUTS,
    REQUIRED_RATIFYING_OWNERS,
    analytic_joint_leakage_clearance,
    analytic_joint_utility_power,
    complete_block_retention_probability,
    fixture_resolution_quality,
    required_leakage_replicates_per_profile,
    required_replicates_per_profile,
)
from .model import AgentProfile, GauntletPreregistration

READINESS_PROPOSAL_SCHEMA_VERSION = "carbon.be4.execution-readiness-proposal.v3"
READINESS_PROPOSAL_AUTHORITY_CEILING = (
    "DESIGN_ANALYSIS_ONLY_NO_EXECUTION_OR_QUALIFICATION_AUTHORITY"
)
READINESS_PROPOSAL_HEADER = b"carbon.be4.execution-readiness-proposal.v3\x00"
READINESS_PROPOSAL_STATUSES = ("EXECUTION_READY_PROPOSED", "STILL_BLOCKED")
ENGINEERING_COMPONENT_AUTHORITY_CEILING = (
    "FIXTURE_ONLY_DESIGN_ANALYSIS_NOT_QUALIFYING_EVIDENCE"
)
NONQUALIFYING_SENSITIVITY_AUTHORITY_CEILING = (
    "SYNTHETIC_GAUSSIAN_DESIGN_ANALYSIS_ONLY_NO_READINESS_OR_QUALIFICATION_AUTHORITY"
)
HISTORICAL_V2_DESIGN_DIGEST = (
    "sha256:e2529e84d9d06882c5296b0a39b3f65219627fac49fbcb278950f753a8b66e37"
)
FIXTURE_PRIMARY_TRANSFORM = "LOG1P_FROZEN_ANCHOR_QUALITY_Q/v1"
FIXTURE_TRANSFER_TRANSFORM = "LOG1P_FROZEN_ANCHOR_QUALITY_Q/v1"


@dataclass(frozen=True, slots=True)
class FixtureGridGeometry:
    """Quality geometry mechanically derived from the complete toy grid."""

    configuration_count: int
    loss_best: float
    loss_worst: float
    transfer_loss_best: float
    transfer_loss_worst: float
    semantic_resolution: float
    parity_robust_feature_step: float


def derive_fixture_grid_geometry() -> FixtureGridGeometry:
    """Enumerate all binary levers under both seed-order parities.

    This binds proposal anchors and materiality geometry to the current shared
    B-07C/B-07F toy arithmetic instead of validating copied numeric constants
    against themselves.  It consumes no gauntlet or protected observation.
    """

    rows: dict[tuple[int, int, int, int], tuple[float, float]] = {}
    for parity, sampling, curriculum, feature in product(
        (0, 1), (1, 2), (1, 2), (1, 2)
    ):
        coefficient, _artifact_digest = construct_fixture_model(
            FIXTURE_TRAINING_OBSERVATIONS,
            sampling,
            bytes((parity,)) + b"be4-proposal-grid",
            curriculum_emphasis=curriculum,
            feature_degree=feature,
        )
        heldout = evaluate_fixture_reference(
            coefficient,
            FIXTURE_HELDOUT_OBSERVATIONS,
            feature_degree=feature,
        )
        transfer = evaluate_fixture_reference(
            coefficient,
            FIXTURE_TRANSFER_OBSERVATIONS,
            feature_degree=feature,
        )
        rows[(parity, sampling, curriculum, feature)] = (heldout, transfer)

    heldout_losses = tuple(row[0] for row in rows.values())
    transfer_losses = tuple(row[1] for row in rows.values())
    loss_best = min(heldout_losses)
    loss_worst = max(heldout_losses)
    transfer_loss_best = min(transfer_losses)
    transfer_loss_worst = max(transfer_losses)
    qualities = tuple(
        fixture_resolution_quality(
            loss,
            loss_best=loss_best,
            loss_worst=loss_worst,
        )
        for loss in heldout_losses
    )
    distinct_qualities = sorted(set(qualities))
    resolutions = tuple(
        upper - lower for lower, upper in pairwise(distinct_qualities) if upper > lower
    )
    feature_steps = tuple(
        fixture_resolution_quality(
            rows[(parity, sampling, curriculum, 2)][0],
            loss_best=loss_best,
            loss_worst=loss_worst,
        )
        - fixture_resolution_quality(
            rows[(parity, sampling, curriculum, 1)][0],
            loss_best=loss_best,
            loss_worst=loss_worst,
        )
        for parity, sampling, curriculum in product((0, 1), (1, 2), (1, 2))
    )
    if (
        len(rows) != 16
        or not resolutions
        or not feature_steps
        or min(feature_steps) <= 0.0
    ):
        raise RuntimeError("the registered toy grid lacks proposal resolution")
    return FixtureGridGeometry(
        len(rows),
        loss_best,
        loss_worst,
        transfer_loss_best,
        transfer_loss_worst,
        min(resolutions),
        min(feature_steps),
    )


_FIXTURE_GRID_GEOMETRY = derive_fixture_grid_geometry()
FIXTURE_LOSS_BEST = _FIXTURE_GRID_GEOMETRY.loss_best
FIXTURE_LOSS_WORST = _FIXTURE_GRID_GEOMETRY.loss_worst
FIXTURE_SEMANTIC_RESOLUTION = _FIXTURE_GRID_GEOMETRY.semantic_resolution
FIXTURE_PARITY_ROBUST_REFERENCE_STEP = _FIXTURE_GRID_GEOMETRY.parity_robust_feature_step
FIXTURE_PRACTICAL_EFFECT_FLOOR = FIXTURE_PARITY_ROBUST_REFERENCE_STEP / 2.0
FIXTURE_TRANSFER_LOSS_BEST = _FIXTURE_GRID_GEOMETRY.transfer_loss_best
FIXTURE_TRANSFER_LOSS_WORST = _FIXTURE_GRID_GEOMETRY.transfer_loss_worst

REQUIRED_ENGINEERING_READINESS_SECTIONS = (
    "agent_drivers",
    "arm_artifacts",
    "attack_evidence",
    "calibration",
    "diversity",
    "execution_evidence",
    "fixture_and_prior",
    "meter",
    "ratification_verifier",
    "shadow_campaign",
)
REQUIRED_HUMAN_REQUIREMENTS = (
    "HUMAN_OWNERS_APPROVE_OR_MODIFY_EIGHT_PROPOSED_VALUES",
    "CARBON_OWNER_ASSIGNS_AUTHENTICATED_ROLE_PRINCIPALS_AND_CURRENTNESS_REVOCATION_POLICY",
    "FIVE_CURRENT_ROLE_HOLDERS_RATIFY_ONE_FUTURE_COMPLETE_EXECUTION_READY_DIGEST",
    "CARBON_OWNER_ISSUES_SEPARATE_ONE_USE_QUALIFYING_EXECUTION_AUTHORIZATION",
)

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_PROPOSAL_FACTORY_TOKEN = object()
_BASELINE_ARMS = ("NO_PRIOR", "GENERIC_PRIOR", "V1_DIRECTIVE_PRIOR")
_LEAKAGE_ICC_SENSITIVITY_LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)
_LEAKAGE_ICC_STATUS = "UNVALIDATED_RHO_ZERO_CONDITIONAL_PLANNING_ASSUMPTION"
_LEAKAGE_DEPENDENCE_BLOCKER = "CROSS_PROFILE_TRANSCRIPT_CLUSTER_DEPENDENCE_UNVALIDATED"
_EXPECTED_INPUT_OWNERS = {
    "representative_agent_profiles": ("RESEARCH", "EXACT_PROTOCOL"),
    "matched_time_compute_budgets": (
        "RESEARCH",
        "STATISTICS",
        "EXACT_PROTOCOL",
    ),
    "utility_estimand": ("SCIENCE", "STATISTICS", "RESEARCH"),
    "practical_effect_floor": ("SCIENCE", "STATISTICS"),
    "uncertainty_aware_decision_rule": (
        "STATISTICS",
        "SCIENCE",
        "RESEARCH",
    ),
    "intervention_diversity_metric": (
        "SCIENCE",
        "STATISTICS",
        "RESEARCH",
        "SECURITY",
    ),
    "intervention_diversity_floor": (
        "SCIENCE",
        "STATISTICS",
        "RESEARCH",
        "SECURITY",
    ),
    "conditional_leakage_limit": ("SECURITY", "STATISTICS", "EXACT_PROTOCOL"),
}


class ReadinessProposalError(ValueError):
    """The proposed owner artifact is malformed or overclaims authority."""


def _reject_constant(value: str) -> object:
    raise ReadinessProposalError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReadinessProposalError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_object(
    value: object, expected: tuple[str, ...], path: str
) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(expected):
        raise ReadinessProposalError(f"{path} must contain the exact registered keys")
    return value


def _text(value: object, path: str) -> str:
    if type(value) is not str or not value:
        raise ReadinessProposalError(f"{path} must be bounded non-empty text")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ReadinessProposalError(f"{path} must be valid UTF-8 text") from exc
    if len(encoded) > 16_384:
        raise ReadinessProposalError(f"{path} must be bounded non-empty text")
    return value


def _text_list(value: object, path: str, *, nonempty: bool) -> tuple[str, ...]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ReadinessProposalError(f"{path} must be an exact text list")
    result = tuple(_text(item, f"{path}/{index}") for index, item in enumerate(value))
    if (nonempty and not result) or len(set(result)) != len(result):
        raise ReadinessProposalError(f"{path} must be non-empty and unique")
    return result


def _positive_int(value: object, path: str, *, maximum: int = 10_000_000) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        raise ReadinessProposalError(f"{path} must be a bounded positive integer")
    return value


def _finite_float(
    value: object,
    path: str,
    *,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> float:
    if (
        type(value) is not float
        or not math.isfinite(value)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        raise ReadinessProposalError(f"{path} must be a bounded finite float")
    return value


def _tagged_digest(value: object, path: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ReadinessProposalError(f"{path} must be an exact tagged SHA-256 digest")
    return value


def fixture_primary_quality(loss: float) -> float:
    """Apply the v3 primary transform with its frozen 0/90 loss anchors."""

    return fixture_resolution_quality(
        loss,
        loss_best=FIXTURE_LOSS_BEST,
        loss_worst=FIXTURE_LOSS_WORST,
    )


def fixture_transfer_quality(loss: float) -> float:
    """Apply the v3 transfer transform with its frozen 0/650 loss anchors."""

    return fixture_resolution_quality(
        loss,
        loss_best=FIXTURE_TRANSFER_LOSS_BEST,
        loss_worst=FIXTURE_TRANSFER_LOSS_WORST,
    )


def _validate_recommended_values(inputs: dict[str, object]) -> None:
    """Validate the eight proposed values, including their cross-bindings."""

    values = {
        key: inputs[key]["recommended_value"]  # type: ignore[index]
        for key in REQUIRED_DESIGN_INPUTS
    }

    profile_registration = _exact_object(
        values["representative_agent_profiles"],
        ("capability_policy", "model_provider", "profiles"),
        "/design_inputs/representative_agent_profiles/recommended_value",
    )
    if profile_registration["model_provider"] != "NONE_DETERMINISTIC_FIXTURE_POLICY":
        raise ReadinessProposalError("fixture profiles cannot claim an external model")
    if (
        profile_registration["capability_policy"]
        != "B07S_PLUS_SUBMIT_RESULT_NO_EXTERNAL_IO_OR_CODE_EXECUTION"
    ):
        raise ReadinessProposalError("fixture profile capability policy is unsupported")
    profiles = profile_registration["profiles"]
    if type(profiles) is not list or len(profiles) != len(AgentProfile):
        raise ReadinessProposalError("exactly five fixture profile pins are required")
    for index, (value, profile) in enumerate(zip(profiles, AgentProfile)):
        item = _exact_object(
            value,
            (
                "corpus_digest",
                "driver_id",
                "driver_version",
                "policy_digest",
                "profile",
                "runtime_digest",
            ),
            f"/design_inputs/representative_agent_profiles/profiles/{index}",
        )
        expected = fixture_driver_ref(profile)
        if item != {
            "corpus_digest": expected.corpus_digest,
            "driver_id": expected.driver_id,
            "driver_version": expected.driver_version,
            "policy_digest": expected.policy_digest,
            "profile": expected.profile.value,
            "runtime_digest": expected.runtime_digest,
        }:
            raise ReadinessProposalError(
                "fixture profile pins do not match the runtime"
            )

    budgets = _exact_object(
        values["matched_time_compute_budgets"],
        (
            "attempt_limit",
            "block_failure_ceiling",
            "fixture_units_per_run",
            "meter_policy_digest",
            "profile_caps",
            "replicates_per_profile",
            "reserve_blocks_per_profile",
            "reserve_retention_target",
            "saved_time_creates_extra_attempts",
        ),
        "/design_inputs/matched_time_compute_budgets/recommended_value",
    )
    if budgets["attempt_limit"] != 8:
        raise ReadinessProposalError(
            "the registered fixture attempt limit must be eight"
        )
    _positive_int(budgets["fixture_units_per_run"], "fixture_units_per_run")
    _tagged_digest(budgets["meter_policy_digest"], "meter_policy_digest")
    replicates = _positive_int(
        budgets["replicates_per_profile"], "replicates_per_profile", maximum=10_000
    )
    if replicates % 4:
        raise ReadinessProposalError("replicates must preserve exact four-arm balance")
    reserves = _positive_int(
        budgets["reserve_blocks_per_profile"],
        "reserve_blocks_per_profile",
        maximum=1_000,
    )
    failure_ceiling = _finite_float(
        budgets["block_failure_ceiling"],
        "block_failure_ceiling",
        maximum=1.0,
    )
    retention_target = _finite_float(
        budgets["reserve_retention_target"],
        "reserve_retention_target",
        maximum=1.0,
    )
    if failure_ceiling <= 0.0 or retention_target <= 0.0:
        raise ReadinessProposalError(
            "failure and retention probabilities must be positive"
        )
    if budgets["saved_time_creates_extra_attempts"] is not False:
        raise ReadinessProposalError("saved resources cannot create an extra attempt")
    caps = budgets["profile_caps"]
    if type(caps) is not list or len(caps) != len(AgentProfile):
        raise ReadinessProposalError("profile_caps must bind every registered profile")
    for index, (cap, profile) in enumerate(zip(caps, AgentProfile)):
        item = _exact_object(
            cap,
            ("normalized_compute_units", "profile", "wall_time_seconds"),
            f"/design_inputs/matched_time_compute_budgets/profile_caps/{index}",
        )
        if item["profile"] != profile.value:
            raise ReadinessProposalError(
                "profile caps must use canonical profile order"
            )
        _positive_int(item["normalized_compute_units"], "normalized_compute_units")
        _positive_int(item["wall_time_seconds"], "wall_time_seconds")

    utility = _exact_object(
        values["utility_estimand"],
        (
            "baseline_arms",
            "id",
            "invalid_candidate_q",
            "loss_best",
            "loss_worst",
            "practical_reference_basis",
            "practical_reference_step",
            "primary_endpoint",
            "primary_transform",
            "profile_weighting",
            "seed_design_status",
            "semantic_resolution",
            "transfer_contrast",
            "transfer_endpoint",
            "transfer_invalid_candidate_q",
            "transfer_loss_best",
            "transfer_loss_worst",
            "transfer_role",
            "transfer_transform",
        ),
        "/design_inputs/utility_estimand/recommended_value",
    )
    if utility["id"] != PRIMARY_ESTIMAND_ID:
        raise ReadinessProposalError("utility estimand identity is unsupported")
    if utility["baseline_arms"] != list(_BASELINE_ARMS):
        raise ReadinessProposalError(
            "the utility estimand must retain all three baselines"
        )
    if utility["primary_endpoint"] != "INDEPENDENT_HELDOUT_TOY_MSE_Q":
        raise ReadinessProposalError("the utility primary endpoint is unsupported")
    if utility["primary_transform"] != FIXTURE_PRIMARY_TRANSFORM:
        raise ReadinessProposalError("the primary quality transform is unsupported")
    if utility["profile_weighting"] != "EQUAL_REGISTERED_PROFILE":
        raise ReadinessProposalError(
            "the utility estimand must equally weight profiles"
        )
    if utility["transfer_role"] != "MANDATORY_NON_INFERIORITY_SUPPORT":
        raise ReadinessProposalError("the transfer endpoint role is unsupported")
    if utility["transfer_endpoint"] != "TRANSFER_TOY_MSE_Q":
        raise ReadinessProposalError("the transfer endpoint is unsupported")
    if utility["transfer_contrast"] != "EQUAL_PROFILE_V2_MINUS_EACH_BASELINE":
        raise ReadinessProposalError("the transfer contrast is unsupported")
    if utility["transfer_transform"] != FIXTURE_TRANSFER_TRANSFORM:
        raise ReadinessProposalError("the transfer quality transform is unsupported")
    transfer_invalid_candidate_q = _finite_float(
        utility["transfer_invalid_candidate_q"],
        "transfer_invalid_candidate_q",
        maximum=1.0,
    )
    if transfer_invalid_candidate_q != 0.0:
        raise ReadinessProposalError("invalid transfer outcomes must retain Q=0")
    transfer_loss_best = _finite_float(
        utility["transfer_loss_best"], "transfer_loss_best"
    )
    transfer_loss_worst = _finite_float(
        utility["transfer_loss_worst"], "transfer_loss_worst"
    )
    if (
        transfer_loss_best != FIXTURE_TRANSFER_LOSS_BEST
        or transfer_loss_worst != FIXTURE_TRANSFER_LOSS_WORST
    ):
        raise ReadinessProposalError(
            "transfer loss anchors do not match the complete registered toy grid"
        )
    invalid_candidate_q = _finite_float(
        utility["invalid_candidate_q"], "invalid_candidate_q", maximum=1.0
    )
    if invalid_candidate_q != 0.0:
        raise ReadinessProposalError("invalid candidate outcomes must retain Q=0")
    loss_best = _finite_float(utility["loss_best"], "loss_best")
    loss_worst = _finite_float(utility["loss_worst"], "loss_worst")
    if not loss_best < loss_worst:
        raise ReadinessProposalError("loss anchors must be strictly ordered")
    semantic_resolution = _finite_float(
        utility["semantic_resolution"], "semantic_resolution", maximum=1.0
    )
    if semantic_resolution <= 0.0:
        raise ReadinessProposalError("semantic resolution must be positive")
    practical_reference_step = _finite_float(
        utility["practical_reference_step"],
        "practical_reference_step",
        maximum=1.0,
    )
    if practical_reference_step < semantic_resolution:
        raise ReadinessProposalError(
            "the practical reference step cannot be finer than semantic resolution"
        )
    if loss_best != FIXTURE_LOSS_BEST or loss_worst != FIXTURE_LOSS_WORST:
        raise ReadinessProposalError(
            "fixture loss anchors do not match the complete registered toy grid"
        )
    if not math.isclose(
        semantic_resolution,
        FIXTURE_SEMANTIC_RESOLUTION,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ReadinessProposalError(
            "semantic resolution does not match the complete registered toy grid"
        )
    if not math.isclose(
        practical_reference_step,
        FIXTURE_PARITY_ROBUST_REFERENCE_STEP,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ReadinessProposalError(
            "practical reference step is not the parity-robust feature-degree gain"
        )
    if (
        utility["practical_reference_basis"]
        != "PARITY_ROBUST_MINIMUM_FEATURE_DEGREE_1_TO_2_Q_GAIN"
        or utility["seed_design_status"]
        != "UNRESOLVED_CANDIDATE_BOUND_FIXTURE_SEED_BLOCKER"
    ):
        raise ReadinessProposalError(
            "the materiality anchor must disclose its robust basis and seed blocker"
        )

    effect_floor = _finite_float(
        values["practical_effect_floor"],
        "practical_effect_floor",
        maximum=1.0,
    )
    if (
        effect_floor <= 0.0
        or not math.isclose(
            effect_floor,
            FIXTURE_PRACTICAL_EFFECT_FLOOR,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        or not math.isclose(
            effect_floor,
            practical_reference_step / 2.0,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        raise ReadinessProposalError(
            "the practical floor must be half the frozen practical reference step"
        )

    rule = _exact_object(
        values["uncertainty_aware_decision_rule"],
        (
            "equality_passes",
            "familywise_alpha",
            "id",
            "indeterminate_distinct",
            "joint_power_target",
            "paired_sd_bound",
            "primary_contrasts",
            "profile_nonregression_minimum",
            "transfer_constraints",
            "transfer_noninferiority_margin_q",
        ),
        "/design_inputs/uncertainty_aware_decision_rule/recommended_value",
    )
    if rule["id"] != DECISION_RULE_ID:
        raise ReadinessProposalError(
            "uncertainty-aware decision identity is unsupported"
        )
    alpha = _finite_float(rule["familywise_alpha"], "familywise_alpha", maximum=1.0)
    power = _finite_float(rule["joint_power_target"], "joint_power_target", maximum=1.0)
    paired_sd = _finite_float(rule["paired_sd_bound"], "paired_sd_bound", maximum=1.0)
    transfer_margin = _finite_float(
        rule["transfer_noninferiority_margin_q"],
        "transfer_noninferiority_margin_q",
        maximum=1.0,
    )
    if min(alpha, power, paired_sd) <= 0.0:
        raise ReadinessProposalError("analysis probabilities and SD must be positive")
    if not math.isclose(
        transfer_margin,
        effect_floor,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ReadinessProposalError(
            "the transfer noninferiority margin must equal the practical effect floor"
        )
    if (
        rule["primary_contrasts"] != 3
        or rule["transfer_constraints"] != 3
        or rule["profile_nonregression_minimum"] != 4
        or rule["equality_passes"] is not False
        or rule["indeterminate_distinct"] is not True
    ):
        raise ReadinessProposalError("uncertainty-aware rule semantics are unsupported")
    utility_required = required_replicates_per_profile(
        paired_sd=paired_sd,
        practical_effect_floor=effect_floor,
        true_effect=practical_reference_step,
        familywise_alpha=alpha,
        joint_power_target=power,
        simultaneous_contrasts=3,
        joint_constraints=6,
    )
    if values["intervention_diversity_metric"] != DIVERSITY_METRIC_ID:
        raise ReadinessProposalError("intervention diversity identity is unsupported")
    diversity = _exact_object(
        values["intervention_diversity_floor"],
        (
            "maximum_family_share",
            "minimum_effective_diversity",
            "minimum_profile_prevalence",
            "minimum_profiles",
            "minimum_supported_families",
        ),
        "/design_inputs/intervention_diversity_floor/recommended_value",
    )
    diversity_effective = _finite_float(
        diversity["minimum_effective_diversity"],
        "minimum_effective_diversity",
    )
    family_share = _finite_float(
        diversity["maximum_family_share"], "maximum_family_share", maximum=1.0
    )
    prevalence = _finite_float(
        diversity["minimum_profile_prevalence"],
        "minimum_profile_prevalence",
        maximum=1.0,
    )
    if (
        diversity["minimum_supported_families"] != 3
        or diversity["minimum_profiles"] != 4
        or diversity_effective < 2.0
        or family_share > 0.5
        or prevalence <= 0.0
    ):
        raise ReadinessProposalError("intervention-diversity floor is too weak")

    leakage = _exact_object(
        values["conditional_leakage_limit"],
        (
            "clipping_policy",
            "cross_profile_icc_assumption",
            "cross_profile_icc_sensitivity",
            "cross_profile_icc_status",
            "effective_cluster_policy",
            "estimator_id",
            "familywise_alpha",
            "indeterminate_on_invalid_denominator",
            "planning_cluster_sd",
            "planning_status",
            "limit",
            "over_limit_alternative",
            "protected_targets",
            "single_target_detection_power_target",
        ),
        "/design_inputs/conditional_leakage_limit/recommended_value",
    )
    if leakage["estimator_id"] != "cross_fitted_shadow_plus_transcript_log_loss/v1":
        raise ReadinessProposalError("conditional-leakage estimator is unsupported")
    if leakage["clipping_policy"] != "epsilon_1_over_2_n_train_plus_1_renormalized/v1":
        raise ReadinessProposalError(
            "conditional-leakage clipping policy is unsupported"
        )
    if leakage["protected_targets"] != list(PROTECTED_TARGETS):
        raise ReadinessProposalError("conditional-leakage targets are incomplete")
    leak_limit = _finite_float(leakage["limit"], "leakage_limit", maximum=1.0)
    leak_alpha = _finite_float(
        leakage["familywise_alpha"], "leakage_familywise_alpha", maximum=1.0
    )
    if (
        leak_limit <= 0.0
        or leak_alpha <= 0.0
        or leakage["indeterminate_on_invalid_denominator"] is not True
    ):
        raise ReadinessProposalError("conditional-leakage decision must fail closed")
    planning_sd = _finite_float(
        leakage["planning_cluster_sd"], "planning_cluster_sd", maximum=1.0
    )
    adverse = _finite_float(
        leakage["over_limit_alternative"],
        "over_limit_alternative",
        maximum=1.0,
    )
    detection_power = _finite_float(
        leakage["single_target_detection_power_target"],
        "single_target_detection_power_target",
        maximum=1.0,
    )
    if (
        planning_sd <= 0.0
        or adverse <= leak_limit
        or not 0.0 < detection_power < 1.0
        or leakage["effective_cluster_policy"]
        != "ONE_WHOLE_TRANSCRIPT_CLUSTER_PER_PROFILE_BLOCK_PROPOSED"
        or leakage["planning_status"] != "UNVALIDATED_NO_SHADOW_CAMPAIGN"
    ):
        raise ReadinessProposalError(
            "conditional-leakage planning assumptions are unsupported"
        )
    cross_profile_icc = _finite_float(
        leakage["cross_profile_icc_assumption"],
        "cross_profile_icc_assumption",
        maximum=1.0,
    )
    if (
        cross_profile_icc != 0.0
        or leakage["cross_profile_icc_status"] != _LEAKAGE_ICC_STATUS
    ):
        raise ReadinessProposalError(
            "the proposed leakage N must remain explicitly conditional on "
            "the unvalidated rho-zero assumption"
        )
    icc_sensitivity = leakage["cross_profile_icc_sensitivity"]
    if type(icc_sensitivity) is not list or len(icc_sensitivity) != len(
        _LEAKAGE_ICC_SENSITIVITY_LEVELS
    ):
        raise ReadinessProposalError(
            "conditional-leakage ICC sensitivity must cover the exact grid"
        )
    for index, (point, rho) in enumerate(
        zip(icc_sensitivity, _LEAKAGE_ICC_SENSITIVITY_LEVELS, strict=True)
    ):
        item = _exact_object(
            point,
            ("replicates_per_profile", "rho"),
            f"/design_inputs/conditional_leakage_limit/icc_sensitivity/{index}",
        )
        registered_rho = _finite_float(item["rho"], f"icc_sensitivity/{index}/rho")
        registered_n = _positive_int(
            item["replicates_per_profile"],
            f"icc_sensitivity/{index}/replicates_per_profile",
            maximum=100_000,
        )
        expected_n = (
            math.ceil(
                required_leakage_replicates_per_profile(
                    cluster_sd=planning_sd,
                    limit=leak_limit,
                    over_limit_alternative=adverse,
                    familywise_alpha=leak_alpha,
                    detection_power_target=detection_power,
                    protected_targets=len(PROTECTED_TARGETS),
                    cross_profile_icc=rho,
                )
                / 4.0
            )
            * 4
        )
        if registered_rho != rho or registered_n != expected_n:
            raise ReadinessProposalError(
                "conditional-leakage ICC sensitivity contradicts the planning model"
            )
    leakage_required = required_leakage_replicates_per_profile(
        cluster_sd=planning_sd,
        limit=leak_limit,
        over_limit_alternative=adverse,
        familywise_alpha=leak_alpha,
        detection_power_target=detection_power,
        protected_targets=len(PROTECTED_TARGETS),
        cross_profile_icc=cross_profile_icc,
    )
    required = max(utility_required, leakage_required)
    if replicates != math.ceil(required / 4.0) * 4:
        raise ReadinessProposalError(
            "replicate count contradicts the frozen utility/leakage power design"
        )
    profile_retention = complete_block_retention_probability(
        required_blocks=replicates,
        reserve_blocks=reserves,
        block_failure_probability=failure_ceiling,
    )
    matrix_retention = max(0.0, 1.0 - len(AgentProfile) * (1.0 - profile_retention))
    if matrix_retention < retention_target:
        raise ReadinessProposalError("reserve blocks do not meet the retention target")


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ReadinessProposalError("proposal is not canonical JSON") from exc


class ExecutionReadinessProposal:
    """Immutable content-bound proposal with no approval or execution power."""

    __slots__ = (
        "__canonical_payload",
        "__engineering_blockers",
        "__human_requirements",
        "__preregistration",
        "__proposal_digest",
        "__status",
    )

    def __init__(
        self,
        canonical_payload: bytes,
        proposal_digest: str,
        preregistration: GauntletPreregistration,
        status: str,
        engineering_blockers: tuple[str, ...],
        human_requirements: tuple[str, ...],
        *,
        _factory_token: object,
    ) -> None:
        if (
            type(self) is not ExecutionReadinessProposal
            or type(canonical_payload) is not bytes
            or type(proposal_digest) is not str
            or type(preregistration) is not GauntletPreregistration
            or status not in READINESS_PROPOSAL_STATUSES
            or type(engineering_blockers) is not tuple
            or type(human_requirements) is not tuple
            or _factory_token is not _PROPOSAL_FACTORY_TOKEN
        ):
            raise TypeError("readiness proposal requires its validating parser")
        expected = (
            "sha256:"
            + hashlib.sha256(READINESS_PROPOSAL_HEADER + canonical_payload).hexdigest()
        )
        if proposal_digest != expected:
            raise ReadinessProposalError("proposal digest does not bind its content")
        if (
            not preregistration.is_syntactically_complete
            or preregistration.ratifications
            or preregistration.design_digest != preregistration.computed_design_digest
        ):
            raise ReadinessProposalError(
                "proposal requires one exact unratified preregistration digest"
            )
        object.__setattr__(
            self, "_ExecutionReadinessProposal__canonical_payload", canonical_payload
        )
        object.__setattr__(
            self, "_ExecutionReadinessProposal__proposal_digest", proposal_digest
        )
        object.__setattr__(
            self, "_ExecutionReadinessProposal__preregistration", preregistration
        )
        object.__setattr__(self, "_ExecutionReadinessProposal__status", status)
        object.__setattr__(
            self,
            "_ExecutionReadinessProposal__engineering_blockers",
            engineering_blockers,
        )
        object.__setattr__(
            self,
            "_ExecutionReadinessProposal__human_requirements",
            human_requirements,
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("readiness proposals are immutable")

    def __repr__(self) -> str:
        return "ExecutionReadinessProposal(<design-analysis-only>)"

    @property
    def canonical_payload(self) -> bytes:
        return self.__canonical_payload

    @property
    def proposal_digest(self) -> str:
        """Digest of the complete engineering review artifact."""

        return self.__proposal_digest

    @property
    def preregistration_design_digest(self) -> str:
        """Bind the exact eight proposed values, without approval authority.

        The full execution-ready freeze and ratification integration remain
        unavailable while this proposal is ``STILL_BLOCKED``.
        """

        value = self.__preregistration.design_digest
        assert type(value) is str
        return value

    @property
    def design_digest(self) -> str:
        """Compatibility alias for the proposed preregistration digest."""

        return self.preregistration_design_digest

    @property
    def preregistration(self) -> GauntletPreregistration:
        return self.__preregistration

    @property
    def status(self) -> str:
        return self.__status

    @property
    def engineering_blockers(self) -> tuple[str, ...]:
        return self.__engineering_blockers

    @property
    def human_requirements(self) -> tuple[str, ...]:
        return self.__human_requirements

    @property
    def qualifying_execution_ready(self) -> bool:
        """A proposed artifact never itself makes an execution ready."""

        return False

    @property
    def is_verified_owner_ratified(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class LeakageIccSensitivityPoint:
    """Prospective leakage N under one exchangeable cross-profile ICC."""

    rho: float
    replicates_per_profile: int


@dataclass(frozen=True, slots=True)
class ProfileHeterogeneitySensitivity:
    """Seeded full-rule diagnostic for one fixed profile-effect vector."""

    scenario_id: str
    true_primary_profile_effects: tuple[float, ...]
    equal_profile_primary_effect: float
    simulated_full_rule_pass_probability_at_proposed_n: float


@dataclass(frozen=True, slots=True)
class V3ResourceEstimate:
    """Prospective cap arithmetic derived from an exact parsed proposal."""

    complete_blocks_planned: int
    complete_blocks_maximum: int
    agent_arm_runs_planned: int
    agent_arm_runs_maximum: int
    policy_work_units_planned: int
    policy_work_units_maximum: int
    wall_seconds_planned: int
    wall_seconds_maximum: int
    fixture_units_planned: int
    fixture_units_maximum: int

    @property
    def authority_ceiling(self) -> str:
        return NONQUALIFYING_SENSITIVITY_AUTHORITY_CEILING

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class V3DesignSensitivityAnalysis:
    """Synthetic planning diagnostics with no readiness or evidence authority."""

    aggregate_six_constraint_replicates_per_profile_unrounded: float
    aggregate_six_constraint_replicates_per_profile_balanced: int
    proposed_replicates_per_profile: int
    aggregate_six_constraint_power_lower_bound_at_balanced_n: float
    aggregate_six_constraint_power_lower_bound_at_proposed_n: float
    leakage_null_clearance_union_lower_bound: float
    leakage_one_target_detection_probability: float
    simulation_aggregate_six_constraint_pass_at_balanced_n: float
    simulation_aggregate_six_constraint_pass_at_proposed_n: float
    simulation_leakage_null_clearance: float
    simulation_leakage_one_target_detection: float
    leakage_cross_profile_icc_sensitivity: tuple[LeakageIccSensitivityPoint, ...]
    profile_heterogeneity_sensitivity: tuple[ProfileHeterogeneitySensitivity, ...]
    simulation_seed: int
    simulation_draws: int

    @property
    def authority_ceiling(self) -> str:
        return NONQUALIFYING_SENSITIVITY_AUTHORITY_CEILING

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def parse_execution_readiness_proposal(document: str) -> ExecutionReadinessProposal:
    """Validate and content-bind one v3 proposal without ratifying it."""

    if type(document) is not str:
        raise ReadinessProposalError("proposal must be bounded UTF-8 text")
    try:
        encoded = document.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ReadinessProposalError("proposal must be valid UTF-8 text") from exc
    if len(encoded) > 1024 * 1024:
        raise ReadinessProposalError("proposal must be bounded UTF-8 text")
    try:
        payload = json.loads(
            document,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except ReadinessProposalError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError) as exc:
        raise ReadinessProposalError("proposal is not valid JSON") from exc

    root = _exact_object(
        payload,
        (
            "authority_ceiling",
            "design_inputs",
            "engineering_readiness",
            "previous_design_digest",
            "preregistration_design_digest",
            "ratifications",
            "readiness",
            "schema_version",
            "status",
        ),
        "/",
    )
    if root["schema_version"] != READINESS_PROPOSAL_SCHEMA_VERSION:
        raise ReadinessProposalError("unsupported readiness proposal schema")
    status = root["status"]
    if status not in READINESS_PROPOSAL_STATUSES:
        raise ReadinessProposalError("readiness status is invalid")
    if root["authority_ceiling"] != READINESS_PROPOSAL_AUTHORITY_CEILING:
        raise ReadinessProposalError("readiness authority ceiling is invalid")
    if root["previous_design_digest"] != HISTORICAL_V2_DESIGN_DIGEST:
        raise ReadinessProposalError("proposal must preserve the historical v2 link")
    if root["ratifications"] != []:
        raise ReadinessProposalError("proposals cannot contain owner ratifications")

    inputs = _exact_object(
        root["design_inputs"], REQUIRED_DESIGN_INPUTS, "/design_inputs"
    )
    for key in REQUIRED_DESIGN_INPUTS:
        item = _exact_object(
            inputs[key],
            (
                "change_from_v2",
                "evidence_refs",
                "recommended_value",
                "required_owners",
                "status",
            ),
            f"/design_inputs/{key}",
        )
        if item["status"] != "PROPOSED":
            raise ReadinessProposalError("reserved decisions must remain PROPOSED")
        _text(item["change_from_v2"], f"/design_inputs/{key}/change_from_v2")
        _text_list(
            item["evidence_refs"],
            f"/design_inputs/{key}/evidence_refs",
            nonempty=True,
        )
        owners = _text_list(
            item["required_owners"],
            f"/design_inputs/{key}/required_owners",
            nonempty=True,
        )
        if owners != _EXPECTED_INPUT_OWNERS[key] or not set(owners).issubset(
            REQUIRED_RATIFYING_OWNERS
        ):
            raise ReadinessProposalError(f"{key} must name its exact approving owners")

    try:
        _validate_recommended_values(inputs)
    except (OverflowError, ValueError) as exc:
        if isinstance(exc, ReadinessProposalError):
            raise
        raise ReadinessProposalError("recommended design values are invalid") from exc

    registered_values = {
        key: _canonical_json(inputs[key]["recommended_value"]).decode("ascii")
        for key in REQUIRED_DESIGN_INPUTS
    }
    preregistration_draft = GauntletPreregistration(**registered_values)
    preregistration_digest = preregistration_draft.computed_design_digest
    if (
        type(preregistration_digest) is not str
        or root["preregistration_design_digest"] != preregistration_digest
    ):
        raise ReadinessProposalError(
            "preregistration_design_digest does not bind the exact eight values"
        )
    preregistration = GauntletPreregistration(
        design_digest=preregistration_digest,
        **registered_values,
    )

    engineering = _exact_object(
        root["engineering_readiness"],
        REQUIRED_ENGINEERING_READINESS_SECTIONS,
        "/engineering_readiness",
    )
    engineering_states: dict[str, str] = {}
    engineering_component_blockers: dict[str, tuple[str, ...]] = {}
    for key in REQUIRED_ENGINEERING_READINESS_SECTIONS:
        item = _exact_object(
            engineering[key],
            (
                "authority_ceiling",
                "blockers",
                "component_ref",
                "evidence_refs",
                "state",
                "summary",
            ),
            f"/engineering_readiness/{key}",
        )
        if item["state"] not in ("READY", "PARTIAL", "BLOCKED"):
            raise ReadinessProposalError(f"{key} has an invalid readiness state")
        engineering_states[key] = item["state"]
        if item["authority_ceiling"] != ENGINEERING_COMPONENT_AUTHORITY_CEILING:
            raise ReadinessProposalError(
                f"{key} must retain the fixture-only engineering ceiling"
            )
        for field in ("component_ref", "summary"):
            _text(item[field], f"/engineering_readiness/{key}/{field}")
        _text_list(
            item["evidence_refs"],
            f"/engineering_readiness/{key}/evidence_refs",
            nonempty=True,
        )
        blockers = _text_list(
            item["blockers"],
            f"/engineering_readiness/{key}/blockers",
            nonempty=False,
        )
        engineering_component_blockers[key] = blockers
        if (item["state"] == "READY") != (not blockers):
            raise ReadinessProposalError(f"{key} READY state and blockers must agree")
    if (
        _LEAKAGE_DEPENDENCE_BLOCKER
        not in engineering_component_blockers["shadow_campaign"]
    ):
        raise ReadinessProposalError(
            "the rho-zero leakage design must retain its cross-profile dependence blocker"
        )

    readiness = _exact_object(
        root["readiness"],
        (
            "engineering_blockers",
            "human_ratifications_present",
            "human_requirements",
            "qualifying_execution_ready",
        ),
        "/readiness",
    )
    engineering_blockers = _text_list(
        readiness["engineering_blockers"],
        "/readiness/engineering_blockers",
        nonempty=False,
    )
    human_requirements = _text_list(
        readiness["human_requirements"],
        "/readiness/human_requirements",
        nonempty=True,
    )
    expected_engineering_blockers = tuple(
        dict.fromkeys(
            blocker
            for key in REQUIRED_ENGINEERING_READINESS_SECTIONS
            if engineering_states[key] != "READY"
            for blocker in engineering_component_blockers[key]
        )
    )
    if engineering_blockers != expected_engineering_blockers:
        raise ReadinessProposalError(
            "root engineering blockers must equal the ordered component-blocker union"
        )
    if human_requirements != REQUIRED_HUMAN_REQUIREMENTS:
        raise ReadinessProposalError(
            "proposal must disclose every exact remaining human requirement"
        )
    if readiness["human_ratifications_present"] is not False:
        raise ReadinessProposalError("proposal cannot assert human ratification")
    if readiness["qualifying_execution_ready"] is not False:
        raise ReadinessProposalError("proposal cannot authorize qualifying execution")
    if status == "EXECUTION_READY_PROPOSED":
        # A JSON assertion cannot establish trusted attack, shadow, execution,
        # or owner-verification evidence.  A later typed verifier may enable
        # this status; this checkpoint deliberately cannot.
        raise ReadinessProposalError(
            "execution-ready status is unavailable without a typed readiness verifier"
        )
    elif not engineering_blockers or not any(
        state != "READY" for state in engineering_states.values()
    ):
        raise ReadinessProposalError("STILL_BLOCKED must disclose engineering blockers")

    canonical = _canonical_json(root)
    digest = (
        "sha256:" + hashlib.sha256(READINESS_PROPOSAL_HEADER + canonical).hexdigest()
    )
    if _DIGEST.fullmatch(digest) is None:  # defensive and unreachable
        raise ReadinessProposalError("computed proposal digest is invalid")
    return ExecutionReadinessProposal(
        canonical,
        digest,
        preregistration,
        status,
        engineering_blockers,
        human_requirements,
        _factory_token=_PROPOSAL_FACTORY_TOKEN,
    )


def derive_v3_resource_estimate(
    proposal: ExecutionReadinessProposal,
) -> V3ResourceEstimate:
    """Derive all proposed cap totals from the exact content-bound values."""

    if type(proposal) is not ExecutionReadinessProposal:
        raise TypeError("resource estimates require an exact parsed v3 proposal")
    payload = json.loads(proposal.canonical_payload.decode("ascii"))
    budget = payload["design_inputs"]["matched_time_compute_budgets"][
        "recommended_value"
    ]
    replicates = budget["replicates_per_profile"]
    maximum_replicates = replicates + budget["reserve_blocks_per_profile"]
    profile_count = len(AgentProfile)
    arm_count = 4
    compute_per_four_arm_block = arm_count * sum(
        item["normalized_compute_units"] for item in budget["profile_caps"]
    )
    wall_per_four_arm_block = arm_count * sum(
        item["wall_time_seconds"] for item in budget["profile_caps"]
    )
    planned_runs = profile_count * arm_count * replicates
    maximum_runs = profile_count * arm_count * maximum_replicates
    return V3ResourceEstimate(
        profile_count * replicates,
        profile_count * maximum_replicates,
        planned_runs,
        maximum_runs,
        compute_per_four_arm_block * replicates,
        compute_per_four_arm_block * maximum_replicates,
        wall_per_four_arm_block * replicates,
        wall_per_four_arm_block * maximum_replicates,
        budget["fixture_units_per_run"] * planned_runs,
        budget["fixture_units_per_run"] * maximum_runs,
    )


def run_nonqualifying_v3_sensitivity_analysis(
    *,
    proposal: ExecutionReadinessProposal,
    simulation_seed: int = 20260908,
    simulation_draws: int = 20_000,
) -> V3DesignSensitivityAnalysis:
    """Stress a parsed v3 proposal with synthetic Gaussian planning draws only.

    Aggregate-endpoint simulations use independent standard-normal constraint
    errors.  Their analytic power and clearance values retain union bounds and
    therefore do not assume constraint/target independence.  Leakage N remains
    explicitly conditional on the registered cross-profile ICC.  Separate
    profile-vector scenarios exercise, but do not power, the 4-of-5 guard.
    Neither path consumes an execution observation or changes the proposal's
    fail-closed readiness state.
    """

    if type(proposal) is not ExecutionReadinessProposal:
        raise TypeError("sensitivity analysis requires an exact parsed v3 proposal")
    if type(simulation_seed) is not int or not 0 <= simulation_seed < 2**63:
        raise TypeError("simulation_seed must be a bounded exact integer")
    if type(simulation_draws) is not int:
        raise TypeError("simulation_draws must be an exact integer")
    if not 1_000 <= simulation_draws <= 100_000:
        raise ValueError("simulation_draws must remain between 1000 and 100000")
    reparsed = parse_execution_readiness_proposal(
        proposal.canonical_payload.decode("ascii")
    )
    if (
        reparsed.proposal_digest != proposal.proposal_digest
        or reparsed.preregistration_design_digest
        != proposal.preregistration_design_digest
    ):
        raise ReadinessProposalError("sensitivity proposal digests are inconsistent")

    payload = json.loads(reparsed.canonical_payload.decode("ascii"))
    inputs = payload["design_inputs"]
    utility = inputs["utility_estimand"]["recommended_value"]
    floor = inputs["practical_effect_floor"]["recommended_value"]
    rule = inputs["uncertainty_aware_decision_rule"]["recommended_value"]
    budget = inputs["matched_time_compute_budgets"]["recommended_value"]
    leakage = inputs["conditional_leakage_limit"]["recommended_value"]

    aggregate_unrounded = required_replicates_per_profile(
        paired_sd=rule["paired_sd_bound"],
        practical_effect_floor=floor,
        true_effect=utility["practical_reference_step"],
        familywise_alpha=rule["familywise_alpha"],
        joint_power_target=rule["joint_power_target"],
        simultaneous_contrasts=rule["primary_contrasts"],
        joint_constraints=(rule["primary_contrasts"] + rule["transfer_constraints"]),
    )
    aggregate_balanced = math.ceil(aggregate_unrounded / 4.0) * 4
    proposed_n = budget["replicates_per_profile"]
    joint_constraints = rule["primary_contrasts"] + rule["transfer_constraints"]

    def utility_power(n: int) -> float:
        return analytic_joint_utility_power(
            replicates_per_profile=n,
            paired_sd=rule["paired_sd_bound"],
            true_effect=utility["practical_reference_step"],
            practical_effect_floor=floor,
            familywise_alpha=rule["familywise_alpha"],
            simultaneous_contrasts=rule["primary_contrasts"],
            joint_constraints=joint_constraints,
        )

    complete_clusters = proposed_n * len(AgentProfile)
    leakage_clearance = analytic_joint_leakage_clearance(
        transcript_clusters=complete_clusters,
        cluster_sd=leakage["planning_cluster_sd"],
        limit=leakage["limit"],
        familywise_alpha=leakage["familywise_alpha"],
        protected_targets=len(leakage["protected_targets"]),
    )
    normal = NormalDist()
    utility_critical = normal.inv_cdf(
        1.0 - rule["familywise_alpha"] / rule["primary_contrasts"]
    )
    leakage_critical = normal.inv_cdf(
        1.0 - leakage["familywise_alpha"] / len(leakage["protected_targets"])
    )
    leakage_se = leakage["planning_cluster_sd"] / math.sqrt(complete_clusters)
    leakage_detection = normal.cdf(
        (leakage["over_limit_alternative"] - leakage["limit"]) / leakage_se
        - leakage_critical
    )

    rng = random.Random(simulation_seed)
    aggregate_balanced_passes = 0
    aggregate_proposed_passes = 0
    leakage_clearances = 0
    leakage_detections = 0
    utility_margins = (
        *(
            utility["practical_reference_step"] - floor
            for _ in range(rule["primary_contrasts"])
        ),
        *(
            rule["transfer_noninferiority_margin_q"]
            for _ in range(rule["transfer_constraints"])
        ),
    )
    balanced_se = rule["paired_sd_bound"] / math.sqrt(
        aggregate_balanced * len(AgentProfile)
    )
    proposed_se = rule["paired_sd_bound"] / math.sqrt(complete_clusters)
    for _ in range(simulation_draws):
        if all(
            margin + balanced_se * rng.gauss(0.0, 1.0) - utility_critical * balanced_se
            > 0.0
            for margin in utility_margins
        ):
            aggregate_balanced_passes += 1
        if all(
            margin + proposed_se * rng.gauss(0.0, 1.0) - utility_critical * proposed_se
            > 0.0
            for margin in utility_margins
        ):
            aggregate_proposed_passes += 1
        if all(
            leakage_se * rng.gauss(0.0, 1.0) + leakage_critical * leakage_se
            <= leakage["limit"]
            for _ in leakage["protected_targets"]
        ):
            leakage_clearances += 1
        if (
            leakage["over_limit_alternative"]
            + leakage_se * rng.gauss(0.0, 1.0)
            - leakage_critical * leakage_se
            > leakage["limit"]
        ):
            leakage_detections += 1

    icc_sensitivity = tuple(
        LeakageIccSensitivityPoint(
            point["rho"],
            point["replicates_per_profile"],
        )
        for point in leakage["cross_profile_icc_sensitivity"]
    )

    heterogeneity_scenarios = (
        (
            "HOMOGENEOUS_REFERENCE_EFFECT",
            tuple(utility["practical_reference_step"] for _ in AgentProfile),
        ),
        ("FOUR_POSITIVE_ONE_REGRESSION", (1.0, 1.0, 1.0, 1.0, -0.1)),
        ("THREE_POSITIVE_TWO_REGRESSIONS", (1.0, 1.0, 1.0, -0.1, -0.1)),
    )
    heterogeneity_rng = random.Random(simulation_seed ^ 0x4245345F48455445)
    profile_mean_se = rule["paired_sd_bound"] / math.sqrt(proposed_n)
    aggregate_mean_se = profile_mean_se / math.sqrt(len(AgentProfile))
    heterogeneity_results: list[ProfileHeterogeneitySensitivity] = []
    for scenario_id, effects in heterogeneity_scenarios:
        full_rule_passes = 0
        for _ in range(simulation_draws):
            passes = True
            for _baseline in range(rule["primary_contrasts"]):
                estimates = tuple(
                    effect + profile_mean_se * heterogeneity_rng.gauss(0.0, 1.0)
                    for effect in effects
                )
                aggregate_estimate = sum(estimates) / len(AgentProfile)
                if (
                    aggregate_estimate - utility_critical * aggregate_mean_se <= floor
                    or sum(estimate >= 0.0 for estimate in estimates)
                    < rule["profile_nonregression_minimum"]
                ):
                    passes = False
            for _transfer in range(rule["transfer_constraints"]):
                transfer_estimate = aggregate_mean_se * heterogeneity_rng.gauss(
                    0.0, 1.0
                )
                if (
                    transfer_estimate - utility_critical * aggregate_mean_se
                    <= -rule["transfer_noninferiority_margin_q"]
                ):
                    passes = False
            if passes:
                full_rule_passes += 1
        heterogeneity_results.append(
            ProfileHeterogeneitySensitivity(
                scenario_id,
                effects,
                sum(effects) / len(AgentProfile),
                full_rule_passes / simulation_draws,
            )
        )

    return V3DesignSensitivityAnalysis(
        aggregate_unrounded,
        aggregate_balanced,
        proposed_n,
        utility_power(aggregate_balanced),
        utility_power(proposed_n),
        leakage_clearance,
        leakage_detection,
        aggregate_balanced_passes / simulation_draws,
        aggregate_proposed_passes / simulation_draws,
        leakage_clearances / simulation_draws,
        leakage_detections / simulation_draws,
        icc_sensitivity,
        tuple(heterogeneity_results),
        simulation_seed,
        simulation_draws,
    )


__all__ = (
    "ENGINEERING_COMPONENT_AUTHORITY_CEILING",
    "FIXTURE_LOSS_BEST",
    "FIXTURE_LOSS_WORST",
    "FIXTURE_PARITY_ROBUST_REFERENCE_STEP",
    "FIXTURE_PRACTICAL_EFFECT_FLOOR",
    "FIXTURE_PRIMARY_TRANSFORM",
    "FIXTURE_SEMANTIC_RESOLUTION",
    "FIXTURE_TRANSFER_LOSS_BEST",
    "FIXTURE_TRANSFER_LOSS_WORST",
    "FIXTURE_TRANSFER_TRANSFORM",
    "HISTORICAL_V2_DESIGN_DIGEST",
    "NONQUALIFYING_SENSITIVITY_AUTHORITY_CEILING",
    "READINESS_PROPOSAL_AUTHORITY_CEILING",
    "READINESS_PROPOSAL_SCHEMA_VERSION",
    "READINESS_PROPOSAL_STATUSES",
    "REQUIRED_ENGINEERING_READINESS_SECTIONS",
    "REQUIRED_HUMAN_REQUIREMENTS",
    "ExecutionReadinessProposal",
    "FixtureGridGeometry",
    "LeakageIccSensitivityPoint",
    "ProfileHeterogeneitySensitivity",
    "ReadinessProposalError",
    "V3DesignSensitivityAnalysis",
    "V3ResourceEstimate",
    "derive_fixture_grid_geometry",
    "derive_v3_resource_estimate",
    "fixture_primary_quality",
    "fixture_transfer_quality",
    "parse_execution_readiness_proposal",
    "run_nonqualifying_v3_sensitivity_analysis",
)

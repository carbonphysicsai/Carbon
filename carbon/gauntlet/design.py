"""Bounded B-E4 preregistration design and non-qualifying analysis helpers.

This module deliberately stops short of owner-ratification verification and
qualifying execution.  Its document type can bind a proposed complete design,
and its numerical helpers can stress decision boundaries using synthetic
values, but neither carries approval or result authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from statistics import NormalDist, StatisticsError

from .model import AgentProfile, ExperimentalArm

DESIGN_SCHEMA_VERSION = "carbon.be4.preregistration-design.v2"
DESIGN_STATUS = "PROPOSED_DESIGN_ANALYSIS_ONLY"
DESIGN_AUTHORITY_CEILING = "NO_QUALIFYING_EXECUTION_OR_QUALIFICATION_AUTHORITY"
DESIGN_DOCUMENT_HEADER = b"carbon.be4.preregistration-design.v2\x00"
PRIMARY_ESTIMAND_ID = "equal_profile_v2_minus_each_baseline_heldout_q_itt/v1"
DECISION_RULE_ID = "profile_stratified_paired_simultaneous_interval/v1"
DIVERSITY_METRIC_ID = "supported_family_equal_profile_inverse_simpson/v2"
PROTECTED_TARGETS = (
    "PROTECTED_CASE_IDENTITY",
    "PROTECTED_MIXTURE_IDENTITY",
    "RELEASE_VARIANT_IDENTITY",
    "MEMBERSHIP_BIT",
)

_DESIGN_FACTORY_TOKEN = object()
_DIVERSITY_FACTORY_TOKEN = object()
_MAX_REGISTERED_COUNT = 10_000_000
_MAX_PROTECTED_TARGETS = 64
_MIN_PROBABILITY = 1e-12

REQUIRED_DESIGN_INPUTS = (
    "representative_agent_profiles",
    "matched_time_compute_budgets",
    "utility_estimand",
    "practical_effect_floor",
    "uncertainty_aware_decision_rule",
    "intervention_diversity_metric",
    "intervention_diversity_floor",
    "conditional_leakage_limit",
)

REQUIRED_EXECUTION_SECTIONS = (
    "agent_profiles",
    "analysis",
    "arms",
    "attack_evidence",
    "budgets",
    "endpoints",
    "fixture_and_prior",
    "matrix",
    "missingness",
    "randomization",
    "ratification_and_freeze",
    "resource_estimate",
    "shadow_campaign",
)

REQUIRED_RATIFYING_OWNERS = (
    "RESEARCH",
    "EXACT_PROTOCOL",
    "SCIENCE",
    "STATISTICS",
    "SECURITY",
)


class DesignDocumentError(ValueError):
    """A proposed design document is malformed or overclaims authority."""


class DesignAnalysisClassification(str, Enum):
    """Counterfactual rule behavior, never a B-E4 execution verdict."""

    PASS_CONDITION = "DESIGN_ANALYSIS_ONLY_PASS_CONDITION"
    FAIL_CONDITION = "DESIGN_ANALYSIS_ONLY_FAIL_CONDITION"
    INDETERMINATE_CONDITION = "DESIGN_ANALYSIS_ONLY_INDETERMINATE_CONDITION"


def _reject_constant(value: str) -> object:
    raise DesignDocumentError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DesignDocumentError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_keys(
    value: object, expected: tuple[str, ...], path: str
) -> dict[str, object]:
    if type(value) is not dict:
        raise DesignDocumentError(f"{path} must be an object")
    if set(value) != set(expected):
        raise DesignDocumentError(f"{path} must contain the exact registered keys")
    return value


def _positive_int(value: object, path: str) -> int:
    if type(value) is not int or value < 1 or value > _MAX_REGISTERED_COUNT:
        raise DesignDocumentError(f"{path} must be a bounded positive integer")
    return value


def _bounded_text(value: object, path: str) -> str:
    if type(value) is not str or not value:
        raise DesignDocumentError(f"{path} must be bounded non-empty text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise DesignDocumentError(f"{path} must be valid UTF-8 text") from exc
    if len(encoded) > 16384:
        raise DesignDocumentError(f"{path} must be bounded non-empty text")
    return value


def _text_object(
    value: object, expected: tuple[str, ...], path: str
) -> dict[str, object]:
    result = _exact_keys(value, expected, path)
    for key in expected:
        _bounded_text(result[key], f"{path}/{key}")
    return result


def _positive_float(value: object, path: str) -> float:
    if (
        type(value) is not float
        or not math.isfinite(value)
        or value <= 0.0
        or value > 1e12
    ):
        raise DesignDocumentError(f"{path} must be a bounded positive finite float")
    return value


def _probability(value: object, path: str) -> float:
    result = _positive_float(value, path)
    if result < _MIN_PROBABILITY or result >= 1.0:
        raise DesignDocumentError(f"{path} must be strictly between zero and one")
    return result


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DesignDocumentError("design is not canonically encodable") from exc


class ProposedGauntletDesign:
    """An immutable, fully content-bound proposal with no approval state."""

    __slots__ = (
        "_canonical_payload",
        "_decision_keys",
        "_design_digest",
        "_readiness_blockers",
    )

    def __init__(
        self,
        canonical_payload: bytes,
        design_digest: str,
        decision_keys: tuple[str, ...],
        readiness_blockers: tuple[str, ...],
        *,
        _factory_token: object,
    ) -> None:
        if (
            type(self) is not ProposedGauntletDesign
            or type(canonical_payload) is not bytes
            or type(design_digest) is not str
            or type(decision_keys) is not tuple
            or type(readiness_blockers) is not tuple
            or _factory_token is not _DESIGN_FACTORY_TOKEN
        ):
            raise TypeError("proposed design requires exact nominal values")
        expected = (
            "sha256:"
            + hashlib.sha256(DESIGN_DOCUMENT_HEADER + canonical_payload).hexdigest()
        )
        if design_digest != expected:
            raise DesignDocumentError("design digest does not bind canonical content")
        if decision_keys != REQUIRED_DESIGN_INPUTS:
            raise DesignDocumentError("proposed design must bind all eight decisions")
        if not readiness_blockers or len(set(readiness_blockers)) != len(
            readiness_blockers
        ):
            raise DesignDocumentError("readiness blockers must be non-empty and unique")
        object.__setattr__(self, "_canonical_payload", canonical_payload)
        object.__setattr__(self, "_design_digest", design_digest)
        object.__setattr__(self, "_decision_keys", decision_keys)
        object.__setattr__(self, "_readiness_blockers", readiness_blockers)

    @property
    def canonical_payload(self) -> bytes:
        return self._canonical_payload

    @property
    def design_digest(self) -> str:
        return self._design_digest

    @property
    def decision_keys(self) -> tuple[str, ...]:
        return self._decision_keys

    @property
    def readiness_blockers(self) -> tuple[str, ...]:
        return self._readiness_blockers

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("proposed designs are immutable")

    def __repr__(self) -> str:
        return "ProposedGauntletDesign(<design-analysis-only>)"

    @property
    def qualifying_execution_ready(self) -> bool:
        return False

    @property
    def is_verified_owner_ratified(self) -> bool:
        return False


def parse_proposed_design(document: str) -> ProposedGauntletDesign:
    """Parse and bind the exact proposed-design document, failing closed.

    Validation is intentionally narrower than a future ratification verifier:
    it proves that the review artifact is structurally complete and internally
    consistent, not that its values are approved, executable, or qualified.
    """

    if type(document) is not str:
        raise DesignDocumentError("design document must be bounded UTF-8 text")
    try:
        document_bytes = document.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise DesignDocumentError("design document must be valid UTF-8 text") from exc
    if len(document_bytes) > 1024 * 1024:
        raise DesignDocumentError("design document must be bounded UTF-8 text")
    try:
        payload = json.loads(
            document,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except DesignDocumentError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError, ValueError) as exc:
        raise DesignDocumentError("design document is not valid JSON") from exc
    root = _exact_keys(
        payload,
        (
            "authority_ceiling",
            "design_inputs",
            "execution_design",
            "ratifications",
            "readiness",
            "schema_version",
            "status",
        ),
        "/",
    )
    if root["schema_version"] != DESIGN_SCHEMA_VERSION:
        raise DesignDocumentError("unsupported design schema")
    if root["status"] != DESIGN_STATUS:
        raise DesignDocumentError("only a proposed design-analysis document is allowed")
    if root["authority_ceiling"] != DESIGN_AUTHORITY_CEILING:
        raise DesignDocumentError("design authority ceiling is invalid")
    if root["ratifications"] != []:
        raise DesignDocumentError("proposal documents cannot contain ratifications")

    inputs = _exact_keys(
        root["design_inputs"], REQUIRED_DESIGN_INPUTS, "/design_inputs"
    )
    for key in REQUIRED_DESIGN_INPUTS:
        item = _exact_keys(
            inputs[key],
            (
                "cheaper_alternative",
                "recommended_default",
                "registered_value",
                "required_owners",
                "rationale",
                "sensitivity",
                "status",
                "stricter_alternative",
            ),
            f"/design_inputs/{key}",
        )
        if item["status"] != "PROPOSED":
            raise DesignDocumentError("every reserved decision must remain PROPOSED")
        for field in (
            "recommended_default",
            "rationale",
            "stricter_alternative",
            "cheaper_alternative",
            "sensitivity",
        ):
            _bounded_text(item[field], f"/design_inputs/{key}/{field}")
        owners = item["required_owners"]
        if (
            type(owners) is not list
            or not owners
            or any(type(owner) is not str for owner in owners)
            or len(set(owners)) != len(owners)
            or not set(owners).issubset(REQUIRED_RATIFYING_OWNERS)
        ):
            raise DesignDocumentError(f"{key} has invalid approving owners")

    execution = _exact_keys(
        root["execution_design"], REQUIRED_EXECUTION_SECTIONS, "/execution_design"
    )
    profiles = execution["agent_profiles"]
    if type(profiles) is not list or len(profiles) != len(AgentProfile):
        raise DesignDocumentError("exactly five agent profiles are required")
    profile_ids: list[str] = []
    for index, profile in enumerate(profiles):
        item = _exact_keys(
            profile,
            (
                "capability_policy",
                "context_policy",
                "driver_ref",
                "model_provider",
                "policy",
                "profile",
                "retry_policy",
                "rng_policy",
                "stopping_policy",
            ),
            f"/execution_design/agent_profiles/{index}",
        )
        profile_ids.append(_bounded_text(item["profile"], "profile"))
        for field in item:
            _bounded_text(item[field], f"agent_profiles/{index}/{field}")
    if set(profile_ids) != {profile.value for profile in AgentProfile}:
        raise DesignDocumentError("agent profile identities are incomplete")

    arms = execution["arms"]
    if type(arms) is not list or len(arms) != 4:
        raise DesignDocumentError("exactly four experimental arms are required")
    arm_ids: list[str] = []
    for index, arm in enumerate(arms):
        item = _exact_keys(
            arm,
            ("arm", "delivery", "material_ref", "selector_policy"),
            f"/execution_design/arms/{index}",
        )
        arm_ids.append(_bounded_text(item["arm"], "arm"))
        for field in item:
            _bounded_text(item[field], f"arms/{index}/{field}")
    if set(arm_ids) != {
        "NO_PRIOR",
        "GENERIC_PRIOR",
        "V1_DIRECTIVE_PRIOR",
        "V2_TEST_ONLY_PRIOR",
    }:
        raise DesignDocumentError("experimental arm identities are incomplete")

    matrix = _exact_keys(
        execution["matrix"],
        (
            "maximum_runs",
            "planned_runs",
            "replicates_per_profile",
            "reserve_blocks_per_profile",
        ),
        "/execution_design/matrix",
    )
    replicates = _positive_int(matrix["replicates_per_profile"], "replicates")
    reserves = _positive_int(matrix["reserve_blocks_per_profile"], "reserves")
    if replicates > 10_000 or reserves > 1_000:
        raise DesignDocumentError("experiment block counts exceed the design bound")
    if replicates % 4 != 0:
        raise DesignDocumentError(
            "replicates must support exact four-arm order balance"
        )
    _positive_int(matrix["planned_runs"], "matrix/planned_runs")
    _positive_int(matrix["maximum_runs"], "matrix/maximum_runs")
    if matrix["planned_runs"] != len(AgentProfile) * 4 * replicates:
        raise DesignDocumentError("planned run count is inconsistent")
    if matrix["maximum_runs"] != len(AgentProfile) * 4 * (replicates + reserves):
        raise DesignDocumentError("maximum run count is inconsistent")

    analysis = _exact_keys(
        execution["analysis"],
        (
            "analysis_implementation_ref",
            "analysis_version",
            "bootstrap",
            "code_tree_ref",
            "decision_rule_id",
            "diversity_floor",
            "diversity_metric_id",
            "effect_floor",
            "infrastructure_block_failure_ceiling",
            "leakage_familywise_alpha",
            "leakage_joint_clearance_target",
            "leakage_limit",
            "leakage_over_limit_alternative",
            "leakage_planning_cluster_sd",
            "loss_best",
            "loss_worst",
            "minimum_profile_prevalence",
            "multiplicity",
            "paired_sd_bound",
            "power_target",
            "primary_estimand_id",
            "protected_targets",
            "reserve_retention_target",
            "semantic_mid_loss",
            "utility_familywise_alpha",
            "utility_joint_constraints",
            "utility_joint_power_target",
            "utility_simultaneous_contrasts",
        ),
        "/execution_design/analysis",
    )
    for field in (
        "analysis_implementation_ref",
        "analysis_version",
        "bootstrap",
        "code_tree_ref",
        "decision_rule_id",
        "diversity_metric_id",
        "multiplicity",
        "power_target",
        "primary_estimand_id",
    ):
        _bounded_text(analysis[field], f"/execution_design/analysis/{field}")
    effect_floor = _positive_float(analysis["effect_floor"], "analysis/effect_floor")
    _positive_float(analysis["diversity_floor"], "analysis/diversity_floor")
    leakage_limit = _positive_float(analysis["leakage_limit"], "analysis/leakage_limit")
    _positive_float(
        analysis["leakage_over_limit_alternative"],
        "analysis/leakage_over_limit_alternative",
    )
    _positive_float(
        analysis["leakage_planning_cluster_sd"],
        "analysis/leakage_planning_cluster_sd",
    )
    if analysis["leakage_over_limit_alternative"] <= analysis["leakage_limit"]:
        raise DesignDocumentError(
            "leakage alternative must be strictly above the registered limit"
        )
    if effect_floor >= 1.0 or leakage_limit >= 1.0:
        raise DesignDocumentError(
            "registered utility and leakage limits must be below one"
        )
    for probability_field in (
        "infrastructure_block_failure_ceiling",
        "leakage_familywise_alpha",
        "leakage_joint_clearance_target",
        "minimum_profile_prevalence",
        "reserve_retention_target",
        "utility_familywise_alpha",
        "utility_joint_power_target",
    ):
        _probability(analysis[probability_field], f"analysis/{probability_field}")
    for field in (
        "loss_best",
        "loss_worst",
        "paired_sd_bound",
        "semantic_mid_loss",
    ):
        _positive_float(analysis[field], f"analysis/{field}")
    if analysis["paired_sd_bound"] > 1.0:
        raise DesignDocumentError("paired Q-difference SD bound cannot exceed one")
    if (
        not analysis["loss_best"]
        < analysis["semantic_mid_loss"]
        < analysis["loss_worst"]
    ):
        raise DesignDocumentError("fixture loss anchors must be strictly ordered")
    for field in (
        "protected_targets",
        "utility_joint_constraints",
        "utility_simultaneous_contrasts",
    ):
        if (
            type(analysis[field]) is not int
            or analysis[field] < 1
            or analysis[field] > _MAX_PROTECTED_TARGETS
        ):
            raise DesignDocumentError(f"analysis/{field} must be a positive integer")
    if (
        analysis["utility_simultaneous_contrasts"] != 3
        or analysis["utility_joint_constraints"] != 6
    ):
        raise DesignDocumentError(
            "the four-arm primary and transfer design requires three and six constraints"
        )
    if not analysis["analysis_implementation_ref"].startswith("UNAVAILABLE_"):
        raise DesignDocumentError(
            "qualifying analysis implementation must remain unavailable"
        )
    if not analysis["code_tree_ref"].startswith("UNPINNED_"):
        raise DesignDocumentError("qualifying code tree must remain unpinned")
    for field, expected in (
        ("primary_estimand_id", PRIMARY_ESTIMAND_ID),
        ("decision_rule_id", DECISION_RULE_ID),
        ("diversity_metric_id", DIVERSITY_METRIC_ID),
    ):
        if analysis[field] != expected:
            raise DesignDocumentError(f"unsupported analysis identity: {field}")

    attack = _text_object(
        execution["attack_evidence"],
        ("available_now", "campaign_ref", "recommended_contract", "unavailable"),
        "/execution_design/attack_evidence",
    )
    if not attack["campaign_ref"].startswith("UNAVAILABLE_"):
        raise DesignDocumentError("attack campaign must remain unavailable")
    budgets = _exact_keys(
        execution["budgets"],
        (
            "attempt_limit",
            "fixture_units_per_run",
            "matched_across_arms",
            "normalized_compute_cap",
            "numeric_caps_ready",
            "saved_time_policy",
            "wall_time_cap",
        ),
        "/execution_design/budgets",
    )
    attempt_limit = _positive_int(budgets["attempt_limit"], "budgets/attempt_limit")
    if attempt_limit > 1_000:
        raise DesignDocumentError("attempt limit exceeds the design bound")
    fixture_units_per_run = _positive_int(
        budgets["fixture_units_per_run"], "budgets/fixture_units_per_run"
    )
    if budgets["matched_across_arms"] is not True:
        raise DesignDocumentError("budgets must be matched across arms")
    if budgets["numeric_caps_ready"] is not False:
        raise DesignDocumentError("unmeasured numeric caps must remain unavailable")
    for field in ("normalized_compute_cap", "saved_time_policy", "wall_time_cap"):
        _bounded_text(budgets[field], f"budgets/{field}")
    _text_object(
        execution["endpoints"],
        ("diagnostic", "primary", "supporting", "translation_boundary"),
        "/execution_design/endpoints",
    )
    fixture = _exact_keys(
        execution["fixture_and_prior"],
        (
            "current_effectful_family_count",
            "current_prior_target",
            "fixture_catalog_ref",
            "fixture_challenge_ref",
            "minimum_required_effectful_family_count",
            "prior_authorization_receipt_ref",
            "prior_pack_ref",
            "required_repair",
            "status",
        ),
        "/execution_design/fixture_and_prior",
    )
    if (
        type(fixture["current_effectful_family_count"]) is not int
        or fixture["current_effectful_family_count"] < 0
    ):
        raise DesignDocumentError("current effectful family count is invalid")
    minimum_families = _positive_int(
        fixture["minimum_required_effectful_family_count"],
        "minimum effectful family count",
    )
    if minimum_families < 3:
        raise DesignDocumentError(
            "the diversity design requires at least three families"
        )
    if fixture["current_effectful_family_count"] >= minimum_families:
        raise DesignDocumentError("analysis-only fixture blocker is inconsistent")
    for field in (
        "current_prior_target",
        "fixture_catalog_ref",
        "fixture_challenge_ref",
        "prior_authorization_receipt_ref",
        "prior_pack_ref",
        "required_repair",
    ):
        _bounded_text(fixture[field], f"fixture_and_prior/{field}")
    if fixture["status"] != "NOT_READY_FOR_RATIFICATION_OR_EXECUTION":
        raise DesignDocumentError("fixture readiness must remain fail closed")

    _text_object(
        execution["missingness"],
        (
            "candidate_invalid",
            "incomplete_after_reserves",
            "infrastructure_or_reference_failure",
        ),
        "/execution_design/missingness",
    )
    _text_object(
        execution["randomization"],
        ("blocking", "order", "seed", "stopping"),
        "/execution_design/randomization",
    )
    ratification = _exact_keys(
        execution["ratification_and_freeze"],
        (
            "approval_statement",
            "approval_surface",
            "freeze",
            "required_roles",
            "separation",
            "status",
        ),
        "/execution_design/ratification_and_freeze",
    )
    for field in (
        "approval_statement",
        "approval_surface",
        "freeze",
        "separation",
    ):
        _bounded_text(ratification[field], f"ratification_and_freeze/{field}")
    roles = ratification["required_roles"]
    if (
        type(roles) is not list
        or tuple(roles) != REQUIRED_RATIFYING_OWNERS
        or any(type(role) is not str for role in roles)
    ):
        raise DesignDocumentError("ratification must name the exact five roles")
    if ratification["status"] != "UNIMPLEMENTED_AND_UNRATIFIED":
        raise DesignDocumentError("ratification integration must remain unavailable")

    resource = _exact_keys(
        execution["resource_estimate"],
        (
            "fixture_units_maximum_with_reserves",
            "fixture_units_planned",
            "total_agent_compute",
            "wall_time",
        ),
        "/execution_design/resource_estimate",
    )
    planned_units = _positive_int(resource["fixture_units_planned"], "planned units")
    maximum_units = _positive_int(
        resource["fixture_units_maximum_with_reserves"], "maximum units"
    )
    if maximum_units < planned_units:
        raise DesignDocumentError("maximum fixture units cannot be below planned units")
    if planned_units != matrix["planned_runs"] * fixture_units_per_run:
        raise DesignDocumentError("planned fixture-unit estimate is inconsistent")
    if maximum_units != matrix["maximum_runs"] * fixture_units_per_run:
        raise DesignDocumentError("maximum fixture-unit estimate is inconsistent")
    _bounded_text(resource["wall_time"], "resource_estimate/wall_time")
    _bounded_text(
        resource["total_agent_compute"], "resource_estimate/total_agent_compute"
    )
    shadow = _exact_keys(
        execution["shadow_campaign"],
        (
            "campaign_ref",
            "denominator_rule",
            "distribution_ref",
            "estimator_ref",
            "fold_policy",
            "probability_clipping",
            "protected_targets",
            "sample_count_rule",
            "status",
            "transcript_cluster_count",
        ),
        "/execution_design/shadow_campaign",
    )
    for field in (
        "campaign_ref",
        "denominator_rule",
        "distribution_ref",
        "estimator_ref",
        "fold_policy",
        "probability_clipping",
        "sample_count_rule",
    ):
        _bounded_text(shadow[field], f"shadow_campaign/{field}")
    shadow_targets = shadow["protected_targets"]
    if (
        type(shadow_targets) is not list
        or len(shadow_targets) != analysis["protected_targets"]
        or any(type(target) is not str or not target for target in shadow_targets)
        or len(set(shadow_targets)) != len(shadow_targets)
    ):
        raise DesignDocumentError("shadow targets must be exact and unique")
    for index, target in enumerate(shadow_targets):
        _bounded_text(target, f"shadow_campaign/protected_targets/{index}")
    if tuple(shadow_targets) != PROTECTED_TARGETS:
        raise DesignDocumentError("shadow campaign uses unsupported target identities")
    transcript_clusters = _positive_int(
        shadow["transcript_cluster_count"],
        "shadow_campaign/transcript_cluster_count",
    )
    if transcript_clusters != replicates * len(AgentProfile):
        raise DesignDocumentError(
            "shadow transcript clusters contradict the registered matrix"
        )
    if shadow["status"] != "UNIMPLEMENTED_AND_UNPINNED":
        raise DesignDocumentError("shadow campaign must remain unavailable")

    registered_profiles = inputs["representative_agent_profiles"]["registered_value"]
    if type(registered_profiles) is not list or tuple(registered_profiles) != tuple(
        profile.value for profile in AgentProfile
    ):
        raise DesignDocumentError("registered profile decision does not bind profiles")
    registered_budget = _exact_keys(
        inputs["matched_time_compute_budgets"]["registered_value"],
        (
            "attempt_limit",
            "fixture_units_per_run",
            "normalized_compute_cap",
            "replicates_per_profile",
            "reserve_blocks_per_profile",
            "wall_time_cap",
        ),
        "/design_inputs/matched_time_compute_budgets/registered_value",
    )
    for key in (
        "attempt_limit",
        "fixture_units_per_run",
        "replicates_per_profile",
        "reserve_blocks_per_profile",
    ):
        _positive_int(registered_budget[key], f"registered budget/{key}")
    for key in ("normalized_compute_cap", "wall_time_cap"):
        _bounded_text(registered_budget[key], f"registered budget/{key}")
    if (
        registered_budget["attempt_limit"] != budgets["attempt_limit"]
        or registered_budget["fixture_units_per_run"]
        != budgets["fixture_units_per_run"]
        or registered_budget["replicates_per_profile"] != replicates
        or registered_budget["reserve_blocks_per_profile"] != reserves
        or registered_budget["normalized_compute_cap"]
        != budgets["normalized_compute_cap"]
        or registered_budget["wall_time_cap"] != budgets["wall_time_cap"]
    ):
        raise DesignDocumentError("registered budget contradicts execution design")
    cross_bindings = (
        ("utility_estimand", "primary_estimand_id"),
        ("uncertainty_aware_decision_rule", "decision_rule_id"),
        ("intervention_diversity_metric", "diversity_metric_id"),
        ("practical_effect_floor", "effect_floor"),
        ("intervention_diversity_floor", "diversity_floor"),
        ("conditional_leakage_limit", "leakage_limit"),
    )
    for decision, analysis_field in cross_bindings:
        if inputs[decision]["registered_value"] != analysis[analysis_field]:
            raise DesignDocumentError(
                f"registered {decision} contradicts execution analysis"
            )
    try:
        expected_floor = (
            1.0
            - fixture_resolution_quality(
                analysis["semantic_mid_loss"],
                loss_best=analysis["loss_best"],
                loss_worst=analysis["loss_worst"],
            )
        ) / 2.0
    except (OverflowError, ValueError) as exc:
        raise DesignDocumentError("fixture resolution design is invalid") from exc
    if not math.isclose(
        analysis["effect_floor"], expected_floor, rel_tol=0.0, abs_tol=1e-15
    ):
        raise DesignDocumentError("effect floor contradicts fixture resolution")
    try:
        required_unrounded = required_replicates_per_profile(
            paired_sd=analysis["paired_sd_bound"],
            practical_effect_floor=analysis["effect_floor"],
            true_effect=expected_floor * 2.0,
            familywise_alpha=analysis["utility_familywise_alpha"],
            joint_power_target=analysis["utility_joint_power_target"],
            simultaneous_contrasts=analysis["utility_simultaneous_contrasts"],
            joint_constraints=analysis["utility_joint_constraints"],
        )
    except (OverflowError, ValueError) as exc:
        raise DesignDocumentError("utility power design is invalid") from exc
    required_balanced = math.ceil(required_unrounded / 4.0) * 4
    if replicates != required_balanced:
        raise DesignDocumentError("replicate count contradicts registered power design")
    normal = NormalDist()
    try:
        leakage_critical = normal.inv_cdf(
            1.0 - analysis["leakage_familywise_alpha"] / analysis["protected_targets"]
        )
        leakage_power_z = normal.inv_cdf(
            1.0
            - (1.0 - analysis["leakage_joint_clearance_target"])
            / analysis["protected_targets"]
        )
    except (OverflowError, StatisticsError, ValueError) as exc:
        raise DesignDocumentError("leakage probability design is invalid") from exc
    leakage_sd_ceiling = (
        analysis["leakage_limit"]
        * math.sqrt(replicates * len(AgentProfile))
        / (leakage_critical + leakage_power_z)
    )
    if analysis["leakage_planning_cluster_sd"] > leakage_sd_ceiling:
        raise DesignDocumentError(
            "leakage planning SD cannot meet the registered clearance target"
        )
    try:
        profile_retention = complete_block_retention_probability(
            required_blocks=replicates,
            reserve_blocks=reserves,
            block_failure_probability=analysis["infrastructure_block_failure_ceiling"],
        )
    except (OverflowError, ValueError) as exc:
        raise DesignDocumentError("reserve-block design is invalid") from exc
    matrix_retention = max(
        0.0,
        1.0 - len(AgentProfile) * (1.0 - profile_retention),
    )
    if matrix_retention < analysis["reserve_retention_target"]:
        raise DesignDocumentError(
            "reserve blocks do not meet the complete-matrix retention target"
        )

    readiness = _exact_keys(
        root["readiness"],
        (
            "blockers",
            "human_ratifications_present",
            "qualifying_execution_ready",
        ),
        "/readiness",
    )
    if readiness["qualifying_execution_ready"] is not False:
        raise DesignDocumentError("proposed design must remain execution-blocked")
    if readiness["human_ratifications_present"] is not False:
        raise DesignDocumentError("proposal cannot assert human ratification")
    blockers = readiness["blockers"]
    if (
        type(blockers) is not list
        or not blockers
        or any(type(item) is not str or not item for item in blockers)
        or len(set(blockers)) != len(blockers)
    ):
        raise DesignDocumentError("readiness blockers must be unique bounded strings")
    for index, blocker in enumerate(blockers):
        _bounded_text(blocker, f"readiness/blockers/{index}")

    canonical = _canonical_json(root)
    digest = "sha256:" + hashlib.sha256(DESIGN_DOCUMENT_HEADER + canonical).hexdigest()
    return ProposedGauntletDesign(
        canonical,
        digest,
        REQUIRED_DESIGN_INPUTS,
        tuple(blockers),
        _factory_token=_DESIGN_FACTORY_TOKEN,
    )


@dataclass(frozen=True, slots=True)
class IntervalBound:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if (
            type(self) is not IntervalBound
            or type(self.lower) is not float
            or type(self.upper) is not float
            or not math.isfinite(self.lower)
            or not math.isfinite(self.upper)
            or self.lower > self.upper
        ):
            raise ValueError("interval bounds must be ordered finite floats")


@dataclass(frozen=True, slots=True)
class UtilityContrastBound:
    """One named v2-baseline contrast; values remain design-analysis-only."""

    baseline: ExperimentalArm
    primary: IntervalBound
    transfer: IntervalBound
    nonnegative_profile_count: int

    def __post_init__(self) -> None:
        if (
            type(self) is not UtilityContrastBound
            or type(self.baseline) is not ExperimentalArm
            or self.baseline is ExperimentalArm.V2_TEST_ONLY_PRIOR
            or type(self.primary) is not IntervalBound
            or type(self.transfer) is not IntervalBound
            or type(self.nonnegative_profile_count) is not int
            or not 0 <= self.nonnegative_profile_count <= len(AgentProfile)
        ):
            raise TypeError("utility contrast requires an exact baseline-bound record")


@dataclass(frozen=True, slots=True)
class LeakageTargetBound:
    """One evaluator-owned protected-target interval for boundary analysis."""

    target: str
    interval: IntervalBound

    def __post_init__(self) -> None:
        if (
            type(self) is not LeakageTargetBound
            or type(self.interval) is not IntervalBound
        ):
            raise TypeError("leakage target requires an exact interval record")
        _bounded_text(self.target, "leakage target")


def fixture_resolution_quality(
    loss: float, *, loss_best: float = 36.5, loss_worst: float = 90.0
) -> float:
    """Map the current fixture's held-out MSE to its preregistered [0, 1] scale."""

    for value in (loss, loss_best, loss_worst):
        if type(value) is not float or not math.isfinite(value) or value < 0.0:
            raise ValueError("fixture losses must be non-negative finite floats")
    if loss_best >= loss_worst or loss < loss_best or loss > loss_worst:
        raise ValueError("loss must lie within the frozen fixture anchors")
    denominator = math.log1p(loss_worst) - math.log1p(loss_best)
    if not math.isfinite(denominator) or denominator <= 0.0:
        raise ValueError("fixture anchors must have finite numeric separation")
    result = (math.log1p(loss_worst) - math.log1p(loss)) / denominator
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError("fixture resolution is outside the bounded quality scale")
    return result


def classify_utility_boundary(
    *,
    contrasts: tuple[UtilityContrastBound, ...],
    practical_effect_floor: float,
    complete_blocks_available: bool,
) -> DesignAnalysisClassification:
    """Exercise the proposed utility rule without recording an experiment result."""

    if (
        type(contrasts) is not tuple
        or len(contrasts) != 3
        or any(type(item) is not UtilityContrastBound for item in contrasts)
        or {item.baseline for item in contrasts}
        != {
            ExperimentalArm.NO_PRIOR,
            ExperimentalArm.GENERIC_PRIOR,
            ExperimentalArm.V1_DIRECTIVE_PRIOR,
        }
        or type(practical_effect_floor) is not float
        or not math.isfinite(practical_effect_floor)
        or practical_effect_floor <= 0.0
        or type(complete_blocks_available) is not bool
    ):
        raise TypeError("utility boundary inputs are invalid")
    if not complete_blocks_available:
        return DesignAnalysisClassification.INDETERMINATE_CONDITION
    if any(item.primary.upper <= practical_effect_floor for item in contrasts) or any(
        item.transfer.upper <= -practical_effect_floor for item in contrasts
    ):
        return DesignAnalysisClassification.FAIL_CONDITION
    if (
        all(item.primary.lower > practical_effect_floor for item in contrasts)
        and all(item.transfer.lower > -practical_effect_floor for item in contrasts)
        and all(item.nonnegative_profile_count >= 4 for item in contrasts)
    ):
        return DesignAnalysisClassification.PASS_CONDITION
    return DesignAnalysisClassification.INDETERMINATE_CONDITION


def classify_leakage_boundary(
    bounds: tuple[LeakageTargetBound, ...],
    *,
    expected_targets: tuple[str, ...],
    limit: float,
) -> DesignAnalysisClassification:
    """Exercise the proposed leakage gate using simultaneous interval bounds."""

    if (
        type(bounds) is not tuple
        or type(expected_targets) is not tuple
        or not expected_targets
        or len(bounds) != len(expected_targets)
        or any(type(item) is not LeakageTargetBound for item in bounds)
        or any(type(item) is not str or not item for item in expected_targets)
        or len(set(expected_targets)) != len(expected_targets)
        or expected_targets != PROTECTED_TARGETS
        or {item.target for item in bounds} != set(expected_targets)
        or type(limit) is not float
        or not math.isfinite(limit)
        or limit < 0.0
    ):
        raise TypeError("leakage boundary inputs are invalid")
    if any(item.interval.lower > limit for item in bounds):
        return DesignAnalysisClassification.FAIL_CONDITION
    if all(item.interval.upper <= limit for item in bounds):
        return DesignAnalysisClassification.PASS_CONDITION
    return DesignAnalysisClassification.INDETERMINATE_CONDITION


def compose_design_analysis_gates(
    *,
    utility: DesignAnalysisClassification,
    diversity: DesignAnalysisClassification,
    leakage: DesignAnalysisClassification,
) -> DesignAnalysisClassification:
    """Compose three analysis-only gates with explicit fail precedence."""

    values = (utility, diversity, leakage)
    if any(type(value) is not DesignAnalysisClassification for value in values):
        raise TypeError("overall gate inputs require exact analysis classifications")
    if DesignAnalysisClassification.FAIL_CONDITION in values:
        return DesignAnalysisClassification.FAIL_CONDITION
    if all(value is DesignAnalysisClassification.PASS_CONDITION for value in values):
        return DesignAnalysisClassification.PASS_CONDITION
    return DesignAnalysisClassification.INDETERMINATE_CONDITION


@dataclass(frozen=True, slots=True)
class CanonicalIntervention:
    """Owner-canonicalized design-analysis input, not caller evidence."""

    profile: AgentProfile
    arm: ExperimentalArm
    replicate: int
    family_identity: str
    semantic_bucket_identity: str
    lineage_root_identity: str
    executed_practice_admissible: bool

    def __post_init__(self) -> None:
        if (
            type(self) is not CanonicalIntervention
            or type(self.profile) is not AgentProfile
            or self.arm is not ExperimentalArm.V2_TEST_ONLY_PRIOR
            or type(self.replicate) is not int
            or self.replicate < 0
        ):
            raise TypeError("canonical intervention requires exact nominal values")
        for name in (
            "family_identity",
            "semantic_bucket_identity",
            "lineage_root_identity",
        ):
            _bounded_text(getattr(self, name), name)
        if type(self.executed_practice_admissible) is not bool:
            raise TypeError("execution state must be exact bool")


@dataclass(frozen=True, slots=True)
class InterventionDiversityAnalysis:
    matrix_complete: bool
    complete_profile_coverage: bool
    observed_families: int
    supported_families: int
    maximum_family_share: float
    inverse_simpson: float
    guarded_effective_diversity: float
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not InterventionDiversityAnalysis
            or self._factory_token is not _DIVERSITY_FACTORY_TOKEN
            or type(self.matrix_complete) is not bool
            or type(self.complete_profile_coverage) is not bool
            or type(self.observed_families) is not int
            or self.observed_families < 0
            or type(self.supported_families) is not int
            or self.supported_families < 0
        ):
            raise TypeError("diversity analysis subclasses are rejected")
        for value in (
            self.maximum_family_share,
            self.inverse_simpson,
            self.guarded_effective_diversity,
        ):
            if type(value) is not float or not math.isfinite(value) or value < 0.0:
                raise ValueError("diversity values must be non-negative finite floats")


def analyze_intervention_diversity(
    interventions: tuple[CanonicalIntervention, ...],
    *,
    expected_replicates_per_profile: int,
    minimum_profile_prevalence: float = 0.10,
    matrix_complete: bool,
) -> InterventionDiversityAnalysis:
    """Compute breadth after run, family, semantic, and lineage collapse.

    A supported family must appear in the registered fraction of runs for at
    least four profiles.  A family counts at most once per run, and reusing one
    lineage across runs counts only once globally.
    """

    if type(interventions) is not tuple or any(
        type(item) is not CanonicalIntervention for item in interventions
    ):
        raise TypeError("interventions require exact canonical records")
    if (
        type(expected_replicates_per_profile) is not int
        or expected_replicates_per_profile < 1
        or type(minimum_profile_prevalence) is not float
        or not math.isfinite(minimum_profile_prevalence)
        or minimum_profile_prevalence <= 0.0
        or minimum_profile_prevalence > 1.0
        or type(matrix_complete) is not bool
    ):
        raise ValueError("diversity registration controls are invalid")
    if any(item.replicate >= expected_replicates_per_profile for item in interventions):
        raise ValueError("intervention replicate is outside the registered matrix")

    admissible = tuple(
        item for item in interventions if item.executed_practice_admissible
    )
    bucket_families: dict[str, str] = {}
    for item in admissible:
        previous_family = bucket_families.setdefault(
            item.semantic_bucket_identity, item.family_identity
        )
        if previous_family != item.family_identity:
            raise ValueError("one semantic bucket cannot claim multiple families")

    lineage_unique: dict[str, CanonicalIntervention] = {}
    for item in sorted(
        admissible,
        key=lambda item: (
            item.family_identity,
            item.lineage_root_identity,
            item.profile.value,
            item.replicate,
            item.semantic_bucket_identity,
        ),
    ):
        previous = lineage_unique.setdefault(item.lineage_root_identity, item)
        if (
            previous.family_identity != item.family_identity
            or previous.semantic_bucket_identity != item.semantic_bucket_identity
        ):
            raise ValueError("one lineage cannot claim multiple semantic identities")
    run_families = {
        (item.profile, item.replicate, item.family_identity)
        for item in lineage_unique.values()
    }
    observed_families = {family for _profile, _replicate, family in run_families}
    supported_families = {
        family
        for family in observed_families
        if sum(
            sum(
                1
                for profile, _replicate, observed_family in run_families
                if profile is candidate_profile and observed_family == family
            )
            / expected_replicates_per_profile
            >= minimum_profile_prevalence
            for candidate_profile in AgentProfile
        )
        >= 4
    }
    profile_families: dict[AgentProfile, list[str]] = {
        profile: [
            family
            for observed_profile, _replicate, family in run_families
            if observed_profile is profile
        ]
        for profile in AgentProfile
    }
    complete_profile_coverage = all(profile_families.values())
    if not complete_profile_coverage:
        return InterventionDiversityAnalysis(
            matrix_complete,
            False,
            len(observed_families),
            len(supported_families),
            0.0,
            0.0,
            0.0,
            _DIVERSITY_FACTORY_TOKEN,
        )
    families = sorted(observed_families)
    shares: dict[str, float] = {family: 0.0 for family in families}
    for values in profile_families.values():
        denominator = float(len(values))
        for family in families:
            shares[family] += values.count(family) / denominator / len(AgentProfile)
    supported_shares = {family: shares[family] for family in sorted(supported_families)}
    unsupported_mass = sum(
        share for family, share in shares.items() if family not in supported_families
    )
    if not supported_shares:
        maximum = 1.0
        inverse_simpson = 0.0
    else:
        largest_supported = min(
            supported_shares,
            key=lambda family: (-supported_shares[family], family),
        )
        supported_shares[largest_supported] += unsupported_mass
        maximum = max(supported_shares.values())
        inverse_simpson = 1.0 / sum(
            value * value for value in supported_shares.values()
        )
    guarded = (
        inverse_simpson if len(supported_families) >= 3 and maximum <= 0.5 else 0.0
    )
    return InterventionDiversityAnalysis(
        matrix_complete,
        True,
        len(observed_families),
        len(supported_families),
        maximum,
        inverse_simpson,
        guarded,
        _DIVERSITY_FACTORY_TOKEN,
    )


def classify_diversity_boundary(
    interventions: tuple[CanonicalIntervention, ...],
    *,
    expected_replicates_per_profile: int,
    minimum_profile_prevalence: float,
    matrix_complete: bool,
    floor: float,
) -> DesignAnalysisClassification:
    """Exercise the proposed diversity gate without producing evidence."""

    if type(floor) is not float or not math.isfinite(floor) or floor <= 0.0:
        raise TypeError("diversity boundary inputs are invalid")
    analysis = analyze_intervention_diversity(
        interventions,
        expected_replicates_per_profile=expected_replicates_per_profile,
        minimum_profile_prevalence=minimum_profile_prevalence,
        matrix_complete=matrix_complete,
    )
    if not analysis.matrix_complete:
        return DesignAnalysisClassification.INDETERMINATE_CONDITION
    if not analysis.complete_profile_coverage:
        return DesignAnalysisClassification.FAIL_CONDITION
    if analysis.guarded_effective_diversity >= floor:
        return DesignAnalysisClassification.PASS_CONDITION
    return DesignAnalysisClassification.FAIL_CONDITION


def required_replicates_per_profile(
    *,
    paired_sd: float,
    practical_effect_floor: float,
    true_effect: float,
    familywise_alpha: float,
    joint_power_target: float,
    simultaneous_contrasts: int,
    joint_constraints: int,
) -> float:
    """Return dependence-robust normal-planning replication before balancing."""

    for value in (
        paired_sd,
        practical_effect_floor,
        true_effect,
        familywise_alpha,
        joint_power_target,
    ):
        if (
            type(value) is not float
            or not math.isfinite(value)
            or value <= 0.0
            or value > 1e6
        ):
            raise ValueError("replicate-design inputs must be positive finite floats")
    if (
        type(simultaneous_contrasts) is not int
        or simultaneous_contrasts < 1
        or simultaneous_contrasts > _MAX_PROTECTED_TARGETS
        or type(joint_constraints) is not int
        or joint_constraints < simultaneous_contrasts
        or joint_constraints > _MAX_PROTECTED_TARGETS
        or familywise_alpha < _MIN_PROBABILITY
        or familywise_alpha >= 1.0
        or joint_power_target < _MIN_PROBABILITY
        or joint_power_target >= 1.0
        or true_effect <= practical_effect_floor
    ):
        raise ValueError("replicate-design controls are invalid")
    normal = NormalDist()
    critical = normal.inv_cdf(1.0 - familywise_alpha / simultaneous_contrasts)
    marginal_power = 1.0 - (1.0 - joint_power_target) / joint_constraints
    power_z = normal.inv_cdf(marginal_power)
    total_blocks = (
        (critical + power_z) * paired_sd / (true_effect - practical_effect_floor)
    ) ** 2
    result = total_blocks / len(AgentProfile)
    if not math.isfinite(result) or result > _MAX_REGISTERED_COUNT:
        raise ValueError("replicate design exceeds the bounded analysis domain")
    return result


def analytic_joint_utility_power(
    *,
    replicates_per_profile: int,
    paired_sd: float,
    true_effect: float = 0.23534629881254276,
    practical_effect_floor: float = 0.11767314940627138,
    familywise_alpha: float = 0.05,
    simultaneous_contrasts: int = 3,
    joint_constraints: int = 6,
) -> float:
    """Bonferroni-union lower bound, requiring no contrast independence."""

    if (
        type(replicates_per_profile) is not int
        or replicates_per_profile < 1
        or replicates_per_profile > _MAX_REGISTERED_COUNT
    ):
        raise ValueError("replicates_per_profile must be a positive integer")
    for value in (
        paired_sd,
        true_effect,
        practical_effect_floor,
        familywise_alpha,
    ):
        if (
            type(value) is not float
            or not math.isfinite(value)
            or value <= 0.0
            or value > 1e6
        ):
            raise ValueError("power inputs must be positive finite floats")
    if (
        type(simultaneous_contrasts) is not int
        or simultaneous_contrasts < 1
        or simultaneous_contrasts > _MAX_PROTECTED_TARGETS
        or type(joint_constraints) is not int
        or joint_constraints < simultaneous_contrasts
        or joint_constraints > _MAX_PROTECTED_TARGETS
        or familywise_alpha < _MIN_PROBABILITY
        or familywise_alpha >= 1.0
    ):
        raise ValueError("power multiplicity controls are invalid")
    if true_effect <= practical_effect_floor:
        return 0.0
    normal = NormalDist()
    critical = normal.inv_cdf(1.0 - familywise_alpha / simultaneous_contrasts)
    complete_blocks = replicates_per_profile * len(AgentProfile)
    one_contrast = normal.cdf(
        (true_effect - practical_effect_floor) * math.sqrt(complete_blocks) / paired_sd
        - critical
    )
    return max(0.0, 1.0 - joint_constraints * (1.0 - one_contrast))


def analytic_joint_leakage_clearance(
    *,
    transcript_clusters: int,
    cluster_sd: float,
    limit: float = 0.05,
    familywise_alpha: float = 0.05,
    protected_targets: int = 4,
) -> float:
    """Union-bound null-clearance probability without target independence."""

    if (
        type(transcript_clusters) is not int
        or transcript_clusters < 1
        or transcript_clusters > _MAX_REGISTERED_COUNT
        or type(protected_targets) is not int
        or protected_targets < 1
        or protected_targets > _MAX_PROTECTED_TARGETS
    ):
        raise ValueError("leakage counts must be positive integers")
    for value in (cluster_sd, limit, familywise_alpha):
        if (
            type(value) is not float
            or not math.isfinite(value)
            or value <= 0.0
            or value > 1e6
        ):
            raise ValueError("leakage inputs must be positive finite floats")
    if familywise_alpha < _MIN_PROBABILITY or familywise_alpha >= 1.0:
        raise ValueError("leakage familywise alpha must be below one")
    normal = NormalDist()
    critical = normal.inv_cdf(1.0 - familywise_alpha / protected_targets)
    one_target = normal.cdf(
        limit * math.sqrt(transcript_clusters) / cluster_sd - critical
    )
    return max(0.0, 1.0 - protected_targets * (1.0 - one_target))


def complete_block_retention_probability(
    *,
    required_blocks: int,
    reserve_blocks: int,
    block_failure_probability: float,
) -> float:
    """Exact binomial probability that numbered reserves retain the matrix."""

    if (
        type(required_blocks) is not int
        or required_blocks < 1
        or required_blocks > _MAX_REGISTERED_COUNT
        or type(reserve_blocks) is not int
        or reserve_blocks < 0
        or reserve_blocks > 1_000
        or type(block_failure_probability) is not float
        or not 0.0 <= block_failure_probability < 1.0
    ):
        raise ValueError("block-retention inputs are invalid")
    if block_failure_probability == 0.0:
        return 1.0
    attempted = required_blocks + reserve_blocks
    log_failure = math.log(block_failure_probability)
    log_success = math.log1p(-block_failure_probability)
    terms = (
        math.exp(
            math.lgamma(attempted + 1)
            - math.lgamma(failures + 1)
            - math.lgamma(attempted - failures + 1)
            + failures * log_failure
            + (attempted - failures) * log_success
        )
        for failures in range(reserve_blocks + 1)
    )
    return min(1.0, math.fsum(terms))


@dataclass(frozen=True, slots=True)
class PowerDesignAnalysis:
    replicates_per_profile_unrounded: float
    replicates_per_profile: int
    reserve_blocks_per_profile: int
    planned_runs: int
    maximum_runs: int
    fixture_units_planned: int
    fixture_units_maximum: int
    practical_effect_floor: float
    paired_sd_bound: float
    primary_joint_power_lower_bound: float
    joint_power_lower_bound: float
    leakage_sd_ceiling: float
    leakage_joint_clearance_lower_bound: float
    profile_retention_at_ceiling: float
    matrix_retention_at_ceiling: float
    profile_retention_at_double_ceiling: float
    matrix_retention_at_double_ceiling: float
    simulation_utility_independent: float
    simulation_utility_shared_correlation: float
    simulation_floor_false_pass: float
    simulation_leakage_independent: float
    simulation_leakage_shared_correlation: float
    simulation_leakage_over_limit_detection: float
    simulation_leakage_over_limit_false_clearance: float
    simulation_seed: int
    simulation_draws: int


def _correlated_standard_normals(
    rng: random.Random, *, count: int, correlation: float
) -> tuple[float, ...]:
    common = rng.gauss(0.0, 1.0)
    common_scale = math.sqrt(correlation)
    independent_scale = math.sqrt(1.0 - correlation)
    return tuple(
        common_scale * common + independent_scale * rng.gauss(0.0, 1.0)
        for _ in range(count)
    )


def run_nonqualifying_power_analysis(
    *,
    design: ProposedGauntletDesign,
    simulation_seed: int = 20260908,
    simulation_draws: int = 20000,
) -> PowerDesignAnalysis:
    """Stress the parsed proposal using synthetic values and no observed outcomes."""

    if type(design) is not ProposedGauntletDesign:
        raise TypeError("analysis requires the exact parsed proposal")
    if type(simulation_seed) is not int or type(simulation_draws) is not int:
        raise TypeError("simulation controls must be exact integers")
    if simulation_draws < 1000 or simulation_draws > 100_000:
        raise ValueError("simulation draws must remain bounded")
    try:
        reparsed = parse_proposed_design(design.canonical_payload.decode("ascii"))
    except (DesignDocumentError, UnicodeError) as exc:
        raise DesignDocumentError("analysis requires a valid parsed proposal") from exc
    if reparsed.design_digest != design.design_digest:
        raise DesignDocumentError("analysis design digest is inconsistent")
    payload = json.loads(reparsed.canonical_payload.decode("ascii"))
    execution = payload["execution_design"]
    analysis = execution["analysis"]
    matrix = execution["matrix"]
    resource = execution["resource_estimate"]

    floor = analysis["effect_floor"]
    quality_mid = fixture_resolution_quality(
        analysis["semantic_mid_loss"],
        loss_best=analysis["loss_best"],
        loss_worst=analysis["loss_worst"],
    )
    semantic_step = 1.0 - quality_mid
    per_profile_unrounded = required_replicates_per_profile(
        paired_sd=analysis["paired_sd_bound"],
        practical_effect_floor=floor,
        true_effect=semantic_step,
        familywise_alpha=analysis["utility_familywise_alpha"],
        joint_power_target=analysis["utility_joint_power_target"],
        simultaneous_contrasts=analysis["utility_simultaneous_contrasts"],
        joint_constraints=analysis["utility_joint_constraints"],
    )
    per_profile = matrix["replicates_per_profile"]
    reserves = matrix["reserve_blocks_per_profile"]
    complete_blocks = per_profile * len(AgentProfile)
    primary_joint_power = analytic_joint_utility_power(
        replicates_per_profile=per_profile,
        paired_sd=analysis["paired_sd_bound"],
        true_effect=semantic_step,
        practical_effect_floor=floor,
        familywise_alpha=analysis["utility_familywise_alpha"],
        simultaneous_contrasts=analysis["utility_simultaneous_contrasts"],
        joint_constraints=analysis["utility_simultaneous_contrasts"],
    )
    joint_power = analytic_joint_utility_power(
        replicates_per_profile=per_profile,
        paired_sd=analysis["paired_sd_bound"],
        true_effect=semantic_step,
        practical_effect_floor=floor,
        familywise_alpha=analysis["utility_familywise_alpha"],
        simultaneous_contrasts=analysis["utility_simultaneous_contrasts"],
        joint_constraints=analysis["utility_joint_constraints"],
    )

    normal = NormalDist()
    leakage_targets = analysis["protected_targets"]
    leakage_alpha = analysis["leakage_familywise_alpha"]
    leakage_target = analysis["leakage_joint_clearance_target"]
    leakage_critical = normal.inv_cdf(1.0 - leakage_alpha / leakage_targets)
    leakage_power_z = normal.inv_cdf(1.0 - (1.0 - leakage_target) / leakage_targets)
    leakage_sd_ceiling = (
        analysis["leakage_limit"]
        * math.sqrt(complete_blocks)
        / (leakage_critical + leakage_power_z)
    )
    leakage_clearance = analytic_joint_leakage_clearance(
        transcript_clusters=complete_blocks,
        cluster_sd=analysis["leakage_planning_cluster_sd"],
        limit=analysis["leakage_limit"],
        familywise_alpha=leakage_alpha,
        protected_targets=leakage_targets,
    )

    rng = random.Random(simulation_seed)
    utility_independent = 0
    utility_shared = 0
    utility_floor_false_pass = 0
    leakage_independent = 0
    leakage_shared = 0
    leakage_over_limit_detected = 0
    leakage_over_limit_false_clearance = 0
    utility_se = analysis["paired_sd_bound"] / math.sqrt(complete_blocks)
    leakage_se = analysis["leakage_planning_cluster_sd"] / math.sqrt(complete_blocks)
    simultaneous_contrasts = analysis["utility_simultaneous_contrasts"]
    joint_constraints = analysis["utility_joint_constraints"]
    utility_critical = normal.inv_cdf(
        1.0 - analysis["utility_familywise_alpha"] / simultaneous_contrasts
    )
    for _ in range(simulation_draws):
        independent_utility = _correlated_standard_normals(
            rng, count=joint_constraints, correlation=0.0
        )
        shared_utility = _correlated_standard_normals(
            rng, count=joint_constraints, correlation=0.5
        )
        if all(
            floor + utility_se * value - utility_critical * utility_se > 0.0
            for value in independent_utility
        ):
            utility_independent += 1
        if all(
            floor + utility_se * value - utility_critical * utility_se > 0.0
            for value in shared_utility
        ):
            utility_shared += 1
        composite_null_margins = (0.0, *(floor for _ in range(joint_constraints - 1)))
        if all(
            margin + utility_se * value - utility_critical * utility_se > 0.0
            for margin, value in zip(
                composite_null_margins, shared_utility, strict=True
            )
        ):
            utility_floor_false_pass += 1

        independent_leakage = _correlated_standard_normals(
            rng, count=leakage_targets, correlation=0.0
        )
        shared_leakage = _correlated_standard_normals(
            rng, count=leakage_targets, correlation=0.5
        )
        if all(
            leakage_se * value + leakage_critical * leakage_se
            <= analysis["leakage_limit"]
            for value in independent_leakage
        ):
            leakage_independent += 1
        if all(
            leakage_se * value + leakage_critical * leakage_se
            <= analysis["leakage_limit"]
            for value in shared_leakage
        ):
            leakage_shared += 1
        leakage_alternatives = (
            analysis["leakage_over_limit_alternative"],
            *(0.0 for _ in range(leakage_targets - 1)),
        )
        if any(
            effect + leakage_se * value - leakage_critical * leakage_se
            > analysis["leakage_limit"]
            for effect, value in zip(leakage_alternatives, shared_leakage, strict=True)
        ):
            leakage_over_limit_detected += 1
        if all(
            effect + leakage_se * value + leakage_critical * leakage_se
            <= analysis["leakage_limit"]
            for effect, value in zip(leakage_alternatives, shared_leakage, strict=True)
        ):
            leakage_over_limit_false_clearance += 1

    failure_ceiling = analysis["infrastructure_block_failure_ceiling"]
    profile_retention = complete_block_retention_probability(
        required_blocks=per_profile,
        reserve_blocks=reserves,
        block_failure_probability=failure_ceiling,
    )
    doubled_profile_retention = complete_block_retention_probability(
        required_blocks=per_profile,
        reserve_blocks=reserves,
        block_failure_probability=min(failure_ceiling * 2.0, 0.999999),
    )
    return PowerDesignAnalysis(
        per_profile_unrounded,
        per_profile,
        reserves,
        matrix["planned_runs"],
        matrix["maximum_runs"],
        resource["fixture_units_planned"],
        resource["fixture_units_maximum_with_reserves"],
        floor,
        analysis["paired_sd_bound"],
        primary_joint_power,
        joint_power,
        leakage_sd_ceiling,
        leakage_clearance,
        profile_retention,
        max(0.0, 1.0 - len(AgentProfile) * (1.0 - profile_retention)),
        doubled_profile_retention,
        max(
            0.0,
            1.0 - len(AgentProfile) * (1.0 - doubled_profile_retention),
        ),
        utility_independent / simulation_draws,
        utility_shared / simulation_draws,
        utility_floor_false_pass / simulation_draws,
        leakage_independent / simulation_draws,
        leakage_shared / simulation_draws,
        leakage_over_limit_detected / simulation_draws,
        leakage_over_limit_false_clearance / simulation_draws,
        simulation_seed,
        simulation_draws,
    )

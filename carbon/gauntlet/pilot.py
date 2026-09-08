"""Fail-closed representation of the proposed B-E4 autonomous-agent pilot.

This module validates a design artifact.  It contains no provider client,
execution adapter, approval act, or path to campaign evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from .model import AgentProfile, ExperimentalArm

PILOT_PROPOSAL_STATUS = "PROPOSED / OWNER_UNAPPROVED / PILOT_NOT_AUTHORIZED"
PILOT_V1_PROPOSAL_STATUS = (
    "ENGINEERING_ACCEPTED / OWNER_UNAPPROVED / PILOT_NOT_AUTHORIZED"
)
PILOT_AUTHORITY_CEILING = (
    "PROPOSAL_ONLY_NO_MODEL_INFERENCE_OR_CAMPAIGN_EXECUTION_AUTHORITY"
)
PILOT_PROPOSAL_PATH = Path(
    ".agent/preregistrations/B-E4_autonomous_agent_pilot_v2.json"
)
PILOT_V1_PROPOSAL_PATH = Path(
    ".agent/preregistrations/B-E4_autonomous_agent_pilot_v1.json"
)
_DOMAINS = {
    "1.0": b"carbon.be4.autonomous-agent-pilot-proposal.v1\x00",
    "2.0": b"carbon.be4.autonomous-agent-pilot-proposal.v2\x00",
}
_V1_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "proposal_id",
        "status",
        "authority_ceiling",
        "pilot_authorized",
        "inference_executed",
        "research_question",
        "model_population",
        "profiles",
        "adaptive_protocol",
        "task_distribution",
        "seed_pairing",
        "budget",
        "evidence_use",
        "owner_decisions",
        "source_verification",
        "proposal_digest",
    }
)
_V2_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "proposal_id",
        "status",
        "authority_ceiling",
        "pilot_authorized",
        "inference_executed",
        "research_question",
        "approval_boundary",
        "model_population",
        "profiles",
        "interaction_state_machine",
        "task_distribution",
        "seed_pairing",
        "budget",
        "data_handling",
        "stages",
        "evidence_use",
        "owner_decisions",
        "source_verification",
        "proposal_digest",
    }
)


class PilotProposalError(ValueError):
    """The design artifact is malformed or crosses its authority boundary."""


@dataclass(frozen=True, slots=True)
class AutonomousPilotProposal:
    proposal_digest: str
    model_id: str
    profile_count: int
    task_cell_count: int
    primary_runs: int
    reserve_runs: int
    maximum_runs: int
    maximum_provider_request_attempts: int
    maximum_billable_input_tokens: int
    maximum_billable_output_tokens: int
    expected_spend_usd: Decimal
    hard_financial_ceiling_usd: Decimal
    schema_version: str = "1.0"
    proposal_id: str = "B-E4-AUTONOMOUS-AGENT-PILOT-V1"
    verified_owner_approval: bool = False
    one_use_execution_authorization: bool = False
    actual_execution_evidence: bool = False

    @property
    def pilot_authorized(self) -> bool:
        return False

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def pilot_proposal_digest(payload: dict[str, Any]) -> str:
    if type(payload) is not dict:
        raise TypeError("pilot proposal digest requires an exact object")
    schema_version = payload.get("schema_version")
    if type(schema_version) is not str or schema_version not in _DOMAINS:
        raise PilotProposalError("pilot proposal schema version is unsupported")
    content = {key: value for key, value in payload.items() if key != "proposal_digest"}
    encoded = json.dumps(
        content,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(_DOMAINS[schema_version] + encoded).hexdigest()


def _object(value: object, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise PilotProposalError(f"{name} must be an exact object")
    return value


def _closed_object(value: object, name: str, fields: frozenset[str]) -> dict[str, Any]:
    result = _object(value, name)
    if set(result) != fields:
        raise PilotProposalError(f"{name} has an unsupported nested shape")
    return result


def _exact_int(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PilotProposalError(f"{name} must be an exact bounded integer")
    return value


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise PilotProposalError(f"{name} must be non-empty exact text")
    return value


def _flag(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise PilotProposalError(f"{name} must be an exact Boolean")
    return value


def _list(value: object, name: str, *, nonempty: bool = True) -> list[Any]:
    if type(value) is not list or (nonempty and not value):
        raise PilotProposalError(f"{name} must be an exact list")
    return value


def _decimal(value: object, name: str) -> Decimal:
    if type(value) not in (int, float) or type(value) is bool:
        raise PilotProposalError(f"{name} must be an exact finite number")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise PilotProposalError(f"{name} must be an exact finite number")
    return result


def _validate_v1_autonomous_pilot_proposal(
    payload: dict[str, Any],
) -> AutonomousPilotProposal:
    if type(payload) is not dict or set(payload) != _V1_TOP_LEVEL_FIELDS:
        raise PilotProposalError("pilot proposal has an unexpected top-level shape")
    if (
        payload["schema_version"] != "1.0"
        or payload["proposal_id"] != "B-E4-AUTONOMOUS-AGENT-PILOT-V1"
        or payload["status"] != PILOT_V1_PROPOSAL_STATUS
        or payload["authority_ceiling"] != PILOT_AUTHORITY_CEILING
        or payload["pilot_authorized"] is not False
        or payload["inference_executed"] is not False
    ):
        raise PilotProposalError("pilot proposal crosses its fixed authority boundary")
    if (
        type(payload["research_question"]) is not str
        or not payload["research_question"]
    ):
        raise PilotProposalError("pilot research question is missing")

    population = _closed_object(
        payload["model_population"],
        "model_population",
        frozenset(
            {
                "design",
                "provider",
                "model_id",
                "model_pin",
                "api",
                "reasoning_effort",
                "verbosity",
                "temperature",
                "top_p",
                "context_limit_tokens",
                "response_format",
                "service_tier",
                "store",
                "built_in_tools_enabled",
                "documented_responses_seed_available",
                "exact_output_replay_claimed",
            }
        ),
    )
    if (
        population.get("design") != "ONE_COMMON_BASE_MODEL_ACROSS_PROFILE_POLICIES"
        or population.get("provider") != "OPENAI_API"
        or population.get("model_id") != "gpt-5.6-terra"
        or population.get("api") != "RESPONSES"
        or population.get("reasoning_effort") != "medium"
        or population.get("service_tier") != "default"
        or _exact_int(
            population.get("context_limit_tokens"), "context limit", minimum=1
        )
        != 32768
        or population.get("store") is not False
        or population.get("built_in_tools_enabled") is not False
        or population.get("documented_responses_seed_available") is not False
        or population.get("exact_output_replay_claimed") is not False
    ):
        raise PilotProposalError(
            "model population is not the reviewed common-model design"
        )

    profiles = payload["profiles"]
    if type(profiles) is not list or len(profiles) != len(AgentProfile):
        raise PilotProposalError("pilot must contain exactly five profile policies")
    profile_names = [item.get("profile") for item in profiles if type(item) is dict]
    if set(profile_names) != {profile.value for profile in AgentProfile}:
        raise PilotProposalError(
            "pilot profile identities are incomplete or duplicated"
        )
    for profile in profiles:
        if (
            set(profile)
            != {
                "profile",
                "policy_id",
                "adaptive",
                "method",
                "corpus",
                "generated_code_execution",
            }
            or profile["generated_code_execution"] is not False
        ):
            raise PilotProposalError("profile capability policy is not closed")
        expected_adaptive = profile["profile"] != AgentProfile.MINIMALIST.value
        if profile["adaptive"] is not expected_adaptive:
            raise PilotProposalError("profile adaptation behavior is inconsistent")
        if profile["profile"] == AgentProfile.LITERATURE_GROUNDED.value:
            if type(profile["corpus"]) is not str or not profile["corpus"]:
                raise PilotProposalError("literature profile requires a frozen corpus")
        elif profile["corpus"] is not None:
            raise PilotProposalError("only the literature profile may receive a corpus")

    protocol = _closed_object(
        payload["adaptive_protocol"],
        "adaptive_protocol",
        frozenset(
            {
                "loop",
                "maximum_attempts_per_run",
                "attempts_include_invalid_or_rejected_proposals",
                "feedback_available",
                "final_selection",
                "nonadaptive_profile",
                "heldout_transfer_shadow_visible_to_agent",
                "v2_specific_branch",
                "saved_budget_creates_extra_attempts",
            }
        ),
    )
    attempts = _exact_int(
        protocol.get("maximum_attempts_per_run"), "attempts", minimum=1
    )
    if (
        protocol.get("loop")
        != "PROPOSAL_TO_PRACTICE_TO_PERMITTED_FEEDBACK_TO_NEXT_PROPOSAL"
        or protocol.get("heldout_transfer_shadow_visible_to_agent") is not False
        or protocol.get("v2_specific_branch") is not False
        or protocol.get("saved_budget_creates_extra_attempts") is not False
        or protocol.get("attempts_include_invalid_or_rejected_proposals") is not True
        or type(protocol.get("feedback_available")) is not list
        or not protocol["feedback_available"]
        or type(protocol.get("final_selection")) is not str
        or not protocol["final_selection"]
        or type(protocol.get("nonadaptive_profile")) is not str
        or not protocol["nonadaptive_profile"]
    ):
        raise PilotProposalError("adaptive protocol violates the arm-neutral boundary")

    tasks = _closed_object(
        payload["task_distribution"],
        "task_distribution",
        frozenset(
            {
                "calibration_realizations_per_cell",
                "candidate_space_policy",
                "development_tasks",
                "direct_candidate_combinations",
                "factorial_cells",
                "factors",
                "inclusion_rule",
                "rejected_task_policy",
                "requires_owner_approval_and_fixture_implementation",
                "selected_using_future_v2_outcomes",
                "separation",
            }
        ),
    )
    factors = _closed_object(
        tasks.get("factors"),
        "task factors",
        frozenset({"resource_regime", "observation_noise", "transfer_shift"}),
    )
    factor_sizes = []
    for name in ("resource_regime", "observation_noise", "transfer_shift"):
        values = factors.get(name)
        if (
            type(values) is not list
            or len(values) < 2
            or len(set(values)) != len(values)
        ):
            raise PilotProposalError(f"task factor {name} is not a closed level set")
        factor_sizes.append(len(values))
    task_cells = math.prod(factor_sizes)
    if (
        task_cells != 12
        or tasks.get("direct_candidate_combinations") != 8
        or attempts >= tasks["direct_candidate_combinations"]
        or tasks.get("selected_using_future_v2_outcomes") is not False
        or tasks.get("requires_owner_approval_and_fixture_implementation") is not True
        or tasks.get("factorial_cells") != 12
        or tasks.get("calibration_realizations_per_cell") != 1
        or type(tasks.get("inclusion_rule")) is not str
        or not tasks["inclusion_rule"]
    ):
        raise PilotProposalError(
            "task distribution does not preserve a non-exhaustive pilot"
        )

    pairing = _closed_object(
        payload["seed_pairing"],
        "seed_pairing",
        frozenset(
            {
                "agent_visible_seed_material",
                "candidate_construction_seed",
                "distinct_hashes_claim_independence",
                "experimental_unit",
                "four_arms_share_task_and_evaluator_realization",
                "future_shadow_allocated",
                "future_shadow_rule",
                "practice_seed",
                "provider_randomness_is_seed_paired",
                "provider_randomness_rule",
                "task_seed",
                "transfer_and_heldout_seed",
                "variance_analysis",
            }
        ),
    )
    if (
        pairing.get("four_arms_share_task_and_evaluator_realization") is not True
        or pairing.get("provider_randomness_is_seed_paired") is not False
        or pairing.get("distinct_hashes_claim_independence") is not False
        or pairing.get("future_shadow_allocated") is not False
        or pairing.get("agent_visible_seed_material") is not False
    ):
        raise PilotProposalError(
            "seed/pairing proposal overclaims experimental dependence"
        )

    budget = _closed_object(
        payload["budget"],
        "budget",
        frozenset(
            {
                "calibration_blocks_per_profile",
                "campaign_wall_seconds",
                "development_blocks_per_profile",
                "expected_spend_usd",
                "expected_token_utilization",
                "fixture_units_per_run",
                "hard_financial_ceiling_usd",
                "input_usd_per_million_tokens",
                "maximum_billable_input_tokens",
                "maximum_billable_output_tokens",
                "maximum_fixture_units",
                "maximum_provider_attempts_per_turn",
                "maximum_provider_request_attempts",
                "maximum_research_service_calls",
                "maximum_run_wall_seconds",
                "maximum_runs",
                "model_call_deadline_seconds",
                "model_turns_per_run",
                "output_usd_per_million_tokens",
                "policy_exhaustion_replaceable",
                "pricing_basis",
                "primary_runs",
                "provider_retry_rule",
                "research_service_calls_per_run",
                "reserve_blocks_per_profile",
                "reserve_runs",
                "successful_input_tokens_per_run",
                "successful_output_tokens_per_run",
                "wall_seconds_per_run",
            }
        ),
    )
    arm_count = len(ExperimentalArm)
    profile_count = len(AgentProfile)
    development_blocks = _exact_int(
        budget.get("development_blocks_per_profile"), "development blocks"
    )
    calibration_blocks = _exact_int(
        budget.get("calibration_blocks_per_profile"), "calibration blocks", minimum=1
    )
    reserve_blocks = _exact_int(
        budget.get("reserve_blocks_per_profile"), "reserve blocks"
    )
    primary_runs = profile_count * arm_count * (development_blocks + calibration_blocks)
    reserve_runs = profile_count * arm_count * reserve_blocks
    maximum_runs = primary_runs + reserve_runs
    turns = _exact_int(budget.get("model_turns_per_run"), "model turns", minimum=1)
    provider_attempts = _exact_int(
        budget.get("maximum_provider_attempts_per_turn"),
        "provider attempts",
        minimum=1,
    )
    input_per_run = _exact_int(
        budget.get("successful_input_tokens_per_run"), "input tokens", minimum=1
    )
    output_per_run = _exact_int(
        budget.get("successful_output_tokens_per_run"), "output tokens", minimum=1
    )
    max_input = maximum_runs * input_per_run * provider_attempts
    max_output = maximum_runs * output_per_run * provider_attempts
    max_requests = maximum_runs * turns * provider_attempts
    derived = {
        "primary_runs": primary_runs,
        "reserve_runs": reserve_runs,
        "maximum_runs": maximum_runs,
        "maximum_provider_request_attempts": max_requests,
        "maximum_billable_input_tokens": max_input,
        "maximum_billable_output_tokens": max_output,
        "maximum_research_service_calls": maximum_runs
        * _exact_int(budget.get("research_service_calls_per_run"), "service calls"),
        "maximum_fixture_units": maximum_runs
        * _exact_int(budget.get("fixture_units_per_run"), "fixture units"),
        "maximum_run_wall_seconds": maximum_runs
        * _exact_int(budget.get("wall_seconds_per_run"), "wall seconds"),
    }
    if any(budget.get(name) != value for name, value in derived.items()):
        raise PilotProposalError("pilot budget arithmetic is inconsistent")
    if budget.get("policy_exhaustion_replaceable") is not False:
        raise PilotProposalError(
            "pilot budget cannot make policy exhaustion replaceable"
        )
    call_deadline = _exact_int(
        budget.get("model_call_deadline_seconds"), "model call deadline", minimum=1
    )
    run_deadline = _exact_int(
        budget.get("wall_seconds_per_run"), "run wall deadline", minimum=1
    )
    campaign_deadline = _exact_int(
        budget.get("campaign_wall_seconds"), "campaign wall deadline", minimum=1
    )
    if call_deadline > run_deadline or run_deadline > campaign_deadline:
        raise PilotProposalError("pilot deadlines are not properly nested")

    input_price = _decimal(budget.get("input_usd_per_million_tokens"), "input price")
    output_price = _decimal(budget.get("output_usd_per_million_tokens"), "output price")
    hard_cost = (
        Decimal(max_input) * input_price + Decimal(max_output) * output_price
    ) / Decimal(1_000_000)
    expected_cost = (
        Decimal(primary_runs)
        * Decimal(str(budget.get("expected_token_utilization")))
        * (
            Decimal(input_per_run) * input_price
            + Decimal(output_per_run) * output_price
        )
        / Decimal(1_000_000)
    )
    if (
        _decimal(budget.get("hard_financial_ceiling_usd"), "financial ceiling")
        != hard_cost
        or _decimal(budget.get("expected_spend_usd"), "expected spend") != expected_cost
    ):
        raise PilotProposalError("pilot financial arithmetic is inconsistent")

    evidence = _closed_object(
        payload["evidence_use"],
        "evidence_use",
        frozenset(
            {
                "development_rows_excluded_from_calibration",
                "may_count_as_shadow_or_attack_evidence",
                "may_qualify_b_e4",
                "may_set_posthoc_thresholds",
                "may_support_pilot_engineering_and_design_revision",
                "partial_and_failed_runs_retained",
                "permitted_outputs",
                "transcripts",
            }
        ),
    )
    if (
        evidence.get("may_support_pilot_engineering_and_design_revision") is not True
        or evidence.get("may_qualify_b_e4") is not False
        or evidence.get("may_set_posthoc_thresholds") is not False
        or evidence.get("may_count_as_shadow_or_attack_evidence") is not False
        or evidence.get("partial_and_failed_runs_retained") is not True
        or evidence.get("development_rows_excluded_from_calibration") is not True
    ):
        raise PilotProposalError("pilot evidence use crosses its maturity ceiling")
    decisions = payload["owner_decisions"]
    expected_decisions = {
        "POPULATION_AND_CAPABILITIES",
        "TASK_ADAPTATION_SEEDS_AND_EVIDENCE",
        "PILOT_RESOURCES_COST_AND_STOPPING",
        "PERMITTED_PILOT_EVIDENCE_USE",
    }
    if (
        type(decisions) is not list
        or len(decisions) != len(expected_decisions)
        or {item.get("decision") for item in decisions if type(item) is dict}
        != expected_decisions
        or any(
            type(item) is not dict
            or set(item) != {"decision", "required_owners", "status"}
            or item.get("status") != "PROPOSED"
            or type(item.get("required_owners")) is not list
            or not item["required_owners"]
            or len(set(item["required_owners"])) != len(item["required_owners"])
            or not set(item["required_owners"])
            <= {"RESEARCH", "EXACT_PROTOCOL", "SCIENCE", "STATISTICS", "SECURITY"}
            for item in decisions
        )
    ):
        raise PilotProposalError("pilot owner decisions must remain exactly proposed")
    sources = payload["source_verification"]
    if (
        type(sources) is not list
        or not sources
        or any(
            type(item) is not dict
            or set(item) != {"claim", "url", "verified_at_utc"}
            or item.get("verified_at_utc") != "2026-09-08T14:00:00Z"
            or not str(item.get("url", "")).startswith(
                ("https://developers.openai.com/", "https://openai.com/")
            )
            for item in sources
        )
    ):
        raise PilotProposalError(
            "model and price sources are not frozen official records"
        )

    digest = pilot_proposal_digest(payload)
    if payload["proposal_digest"] != digest:
        raise PilotProposalError("pilot proposal digest does not bind its content")
    return AutonomousPilotProposal(
        digest,
        population["model_id"],
        profile_count,
        task_cells,
        primary_runs,
        reserve_runs,
        maximum_runs,
        max_requests,
        max_input,
        max_output,
        expected_cost,
        hard_cost,
    )


def _validate_owner_decisions_v2(value: object) -> None:
    decisions = _list(value, "owner_decisions")
    expected = {
        "PILOT_POPULATION_AND_INTERACTION": {
            "RESEARCH",
            "EXACT_PROTOCOL",
            "SECURITY",
        },
        "TASK_FIXTURE_SEEDS_AND_ANALYSIS": {
            "RESEARCH",
            "EXACT_PROTOCOL",
            "SCIENCE",
            "STATISTICS",
            "SECURITY",
        },
        "RESOURCE_COST_AND_STOPPING": {
            "RESEARCH",
            "EXACT_PROTOCOL",
            "STATISTICS",
        },
        "PROVIDER_DATA_EGRESS_AND_RETENTION": {"EXACT_PROTOCOL", "SECURITY"},
        "STAGED_EVIDENCE_USE": {
            "RESEARCH",
            "EXACT_PROTOCOL",
            "SCIENCE",
            "STATISTICS",
            "SECURITY",
        },
    }
    observed: dict[str, set[str]] = {}
    for raw in decisions:
        item = _closed_object(
            raw,
            "owner decision",
            frozenset({"decision", "required_owners", "status"}),
        )
        decision = _text(item["decision"], "owner decision id")
        owners = _list(item["required_owners"], "required owner roles")
        if (
            item["status"] != "PROPOSED"
            or any(type(owner) is not str for owner in owners)
            or len(set(owners)) != len(owners)
        ):
            raise PilotProposalError("owner decisions must be unique and proposed")
        observed[decision] = set(owners)
    if observed != expected or len(decisions) != len(expected):
        raise PilotProposalError("pilot owner-role decisions are incomplete")


def _validate_v2_autonomous_pilot_proposal(
    payload: dict[str, Any],
) -> AutonomousPilotProposal:
    if type(payload) is not dict or set(payload) != _V2_TOP_LEVEL_FIELDS:
        raise PilotProposalError("pilot proposal has an unexpected top-level shape")
    if (
        payload["schema_version"] != "2.0"
        or payload["proposal_id"] != "B-E4-AUTONOMOUS-AGENT-PILOT-V2"
        or payload["status"] != PILOT_PROPOSAL_STATUS
        or payload["authority_ceiling"] != PILOT_AUTHORITY_CEILING
        or payload["pilot_authorized"] is not False
        or payload["inference_executed"] is not False
    ):
        raise PilotProposalError("pilot proposal crosses its fixed authority boundary")
    _text(payload["research_question"], "research question")

    approval = _closed_object(
        payload["approval_boundary"],
        "approval_boundary",
        frozenset(
            {
                "validator_establishes",
                "verified_owner_approval",
                "one_use_execution_authorization",
                "actual_execution_evidence",
                "required_owner_roles",
                "proposal_change_requires_new_version_digest_and_approval",
                "approval_evidence_reference_required",
                "execution_manifest_required_after_implementation_freeze",
            }
        ),
    )
    required_owners = [
        "RESEARCH",
        "EXACT_PROTOCOL",
        "SCIENCE",
        "STATISTICS",
        "SECURITY",
    ]
    if (
        approval["validator_establishes"]
        != "WELL_FORMED_SEMANTICALLY_VALID_PROPOSAL_ONLY"
        or approval["verified_owner_approval"] is not False
        or approval["one_use_execution_authorization"] is not False
        or approval["actual_execution_evidence"] is not False
        or approval["required_owner_roles"] != required_owners
        or approval["proposal_change_requires_new_version_digest_and_approval"]
        is not True
        or approval["approval_evidence_reference_required"] is not True
        or approval["execution_manifest_required_after_implementation_freeze"]
        is not True
    ):
        raise PilotProposalError(
            "proposal validity is conflated with approval or execution"
        )

    population = _closed_object(
        payload["model_population"],
        "model_population",
        frozenset(
            {
                "design",
                "provider",
                "model_id",
                "model_pin",
                "api",
                "reasoning_effort",
                "verbosity",
                "temperature",
                "top_p",
                "context_limit_tokens",
                "response_format",
                "service_tier",
                "record_requested_and_returned_service_tier",
                "record_request_response_timestamps",
                "balanced_interleaved_arm_schedule",
                "store",
                "built_in_tools_enabled",
                "documented_responses_seed_available",
                "exact_output_replay_claimed",
                "network_enabled_by_proposal",
            }
        ),
    )
    if (
        population["design"] != "ONE_COMMON_BASE_MODEL_ACROSS_PROFILE_POLICIES"
        or population["provider"] != "OPENAI_API"
        or population["model_id"] != "gpt-5.6-terra"
        or population["api"] != "RESPONSES"
        or population["reasoning_effort"] != "medium"
        or population["verbosity"] != "low"
        or population["service_tier"] != "default"
        or _exact_int(population["context_limit_tokens"], "context limit", minimum=1)
        != 32768
        or any(
            population[name] is not expected
            for name, expected in (
                ("record_requested_and_returned_service_tier", True),
                ("record_request_response_timestamps", True),
                ("balanced_interleaved_arm_schedule", True),
                ("store", False),
                ("built_in_tools_enabled", False),
                ("documented_responses_seed_available", False),
                ("exact_output_replay_claimed", False),
                ("network_enabled_by_proposal", False),
            )
        )
    ):
        raise PilotProposalError("model population violates the common-model boundary")
    for name in ("model_pin", "response_format", "temperature", "top_p"):
        _text(population[name], f"model_population.{name}")

    profiles = _list(payload["profiles"], "profiles")
    profile_fields = frozenset(
        {
            "profile",
            "policy_id",
            "adaptive",
            "proposal_calls_per_run",
            "selection_calls_per_run",
            "selection_mode",
            "method",
            "corpus",
            "generated_code_execution",
            "external_network_access",
            "tool_access",
            "prompt_configuration",
        }
    )
    by_profile: dict[AgentProfile, dict[str, Any]] = {}
    for raw in profiles:
        item = _closed_object(raw, "profile", profile_fields)
        try:
            identity = AgentProfile(item["profile"])
        except (TypeError, ValueError) as exc:
            raise PilotProposalError("profile identity is unsupported") from exc
        if identity in by_profile:
            raise PilotProposalError("profile identity is duplicated")
        adaptive = identity is not AgentProfile.MINIMALIST
        if (
            item["adaptive"] is not adaptive
            or item["generated_code_execution"] is not False
            or item["external_network_access"] is not False
            or item["tool_access"]
            != "EXACT_B07S_RESEARCH_SERVICE_AND_BOUNDED_FIXTURE_SUBMISSION_ONLY"
            or _exact_int(item["proposal_calls_per_run"], "proposal calls", minimum=1)
            != (4 if adaptive else 1)
            or _exact_int(item["selection_calls_per_run"], "selection calls")
            != (1 if adaptive else 0)
            or item["selection_mode"]
            != (
                "METERED_SELECTION_ONLY_MODEL_CALL"
                if adaptive
                else "DETERMINISTIC_ONLY_ADMISSIBLE_ANCESTOR_OR_STOP"
            )
        ):
            raise PilotProposalError(
                "profile capability or call policy is inconsistent"
            )
        if identity is AgentProfile.LITERATURE_GROUNDED:
            _text(item["corpus"], "literature corpus")
        elif item["corpus"] is not None:
            raise PilotProposalError("only the literature profile may receive a corpus")
        for name in ("policy_id", "method", "prompt_configuration"):
            _text(item[name], f"profile.{name}")
        by_profile[identity] = item
    if set(by_profile) != set(AgentProfile) or len(profiles) != len(AgentProfile):
        raise PilotProposalError("all five exact profile policies are required")

    protocol = _closed_object(
        payload["interaction_state_machine"],
        "interaction_state_machine",
        frozenset(
            {
                "initial_state",
                "maximum_proposal_attempts_for_adaptive_profiles",
                "invalid_refusal_and_truncation_consume_proposal_attempt",
                "provider_retry_is_not_a_research_attempt",
                "verified_provider_failure_maximum_retries",
                "ambiguous_timeout_retry_allowed",
                "final_selection_after_fourth_available_feedback",
                "selection_call_may_only_choose_admissible_ancestor_or_stop",
                "selection_call_may_create_or_evaluate_candidate",
                "minimalist_invalid_first_proposal_gets_another_attempt",
                "saved_time_or_tokens_create_extra_attempts",
                "arm_and_run_transcripts_isolated",
                "events",
            }
        ),
    )
    if (
        protocol["initial_state"] != "READY_FOR_PROPOSAL"
        or protocol["maximum_proposal_attempts_for_adaptive_profiles"] != 4
        or protocol["invalid_refusal_and_truncation_consume_proposal_attempt"]
        is not True
        or protocol["provider_retry_is_not_a_research_attempt"] is not True
        or protocol["verified_provider_failure_maximum_retries"] != 1
        or protocol["ambiguous_timeout_retry_allowed"] is not False
        or protocol["final_selection_after_fourth_available_feedback"] is not True
        or protocol["selection_call_may_only_choose_admissible_ancestor_or_stop"]
        is not True
        or protocol["selection_call_may_create_or_evaluate_candidate"] is not False
        or protocol["minimalist_invalid_first_proposal_gets_another_attempt"]
        is not False
        or protocol["saved_time_or_tokens_create_extra_attempts"] is not False
        or protocol["arm_and_run_transcripts_isolated"] is not True
    ):
        raise PilotProposalError(
            "interaction protocol grants an unregistered advantage"
        )
    expected_events = {
        "VALID_PROPOSAL": (1, 1, True, False, False),
        "INVALID_STRATEGY": (1, 1, False, False, False),
        "SCHEMA_INVALID_OR_MALFORMED_OUTPUT": (1, 1, False, False, False),
        "REFUSAL": (1, 1, False, False, False),
        "TRUNCATED_OR_OUTPUT_BUDGET_EXHAUSTED": (1, 1, False, False, False),
        "EXPLICIT_AGENT_STOP": (0, 1, False, False, True),
        "VERIFIED_EXTERNAL_PROVIDER_FAILURE": (0, 1, False, True, False),
        "AMBIGUOUS_TIMEOUT": (1, 1, False, False, True),
        "PRACTICE_SUCCESS": (0, 0, False, False, False),
        "PRACTICE_FAILURE": (0, 0, False, False, False),
        "FINAL_SELECTION_OR_STOP": (0, 1, False, False, True),
        "RUN_OR_CAMPAIGN_BUDGET_EXHAUSTED": (0, 0, False, False, True),
    }
    observed_events: dict[str, tuple[object, ...]] = {}
    for raw in _list(protocol["events"], "interaction events"):
        event = _closed_object(
            raw,
            "interaction event",
            frozenset(
                {
                    "event",
                    "proposal_attempt_delta",
                    "provider_request_delta",
                    "practice_allowed",
                    "provider_retry_allowed",
                    "terminal",
                }
            ),
        )
        name = _text(event["event"], "event name")
        observed_events[name] = (
            _exact_int(event["proposal_attempt_delta"], "attempt delta"),
            _exact_int(event["provider_request_delta"], "request delta"),
            _flag(event["practice_allowed"], "practice_allowed"),
            _flag(event["provider_retry_allowed"], "provider_retry_allowed"),
            _flag(event["terminal"], "terminal"),
        )
    if observed_events != expected_events or len(protocol["events"]) != len(
        expected_events
    ):
        raise PilotProposalError("interaction event transitions are incomplete")

    tasks = _closed_object(
        payload["task_distribution"],
        "task_distribution",
        frozenset(
            {
                "schema",
                "factorial_cells",
                "calibration_realizations_per_cell",
                "coverage_not_within_cell_identification",
                "target_law",
                "fixed_heldout_x",
                "direct_candidate_combinations",
                "registered_strategy_families",
                "resource_regimes",
                "observation_noise",
                "transfer_shifts",
                "agent_visible_task",
                "evaluator_held",
                "reference_and_measurement",
                "prior_applicability",
                "requires_owner_approval_and_fixture_implementation",
                "selected_using_future_v2_outcomes",
                "generation_audit",
            }
        ),
    )
    if (
        tasks["schema"] != "carbon.be4.synthetic-pilot-task-distribution.v2"
        or tasks["factorial_cells"] != 12
        or tasks["calibration_realizations_per_cell"] != 1
        or tasks["coverage_not_within_cell_identification"] is not True
        or tasks["target_law"]
        != "COUNTERBALANCED_AGENT_VISIBLE_Y_EQUALS_X_OR_X_SQUARED_PLUS_TRAINING_ONLY_NOISE"
        or tasks["fixed_heldout_x"] != [3, 4]
        or tasks["direct_candidate_combinations"] != 8
        or len(_list(tasks["registered_strategy_families"], "strategy families")) != 3
        or tasks["requires_owner_approval_and_fixture_implementation"] is not True
        or tasks["selected_using_future_v2_outcomes"] is not False
    ):
        raise PilotProposalError("task distribution crosses its fixture boundary")
    resource_fields = frozenset(
        {
            "id",
            "training_x",
            "training_observation_count",
            "candidate_fixture_units",
            "paired_practice_fixture_units",
            "what_changes",
            "what_remains_fixed",
        }
    )
    resources = _list(tasks["resource_regimes"], "resource regimes")
    resource_ids: list[str] = []
    previous_units = 0
    for raw in resources:
        item = _closed_object(raw, "resource regime", resource_fields)
        identity = _text(item["id"], "resource regime id")
        training_x = _list(item["training_x"], "training x")
        units = _exact_int(
            item["candidate_fixture_units"], "candidate units", minimum=1
        )
        if (
            item["training_observation_count"] != len(training_x)
            or any(type(x) is not int or x <= 0 for x in training_x)
            or item["paired_practice_fixture_units"] != 2 * units
            or units <= previous_units
        ):
            raise PilotProposalError("resource regime is internally inconsistent")
        _text(item["what_changes"], "resource change")
        _text(item["what_remains_fixed"], "resource fixed factors")
        resource_ids.append(identity)
        previous_units = units
    if resource_ids != ["DATA_SCARCE", "BALANCED", "COMPUTE_SCARCE"]:
        raise PilotProposalError("resource regimes are incomplete or reordered")
    noise_fields = frozenset({"id", "law", "amplitude", "mean", "applies_to"})
    noises = _list(tasks["observation_noise"], "observation noise")
    amplitudes = []
    for raw in noises:
        item = _closed_object(raw, "noise regime", noise_fields)
        amplitudes.append(_exact_int(item["amplitude"], "noise amplitude", minimum=1))
        if (
            item["law"] != "DOMAIN_SEPARATED_SHA256_RADEMACHER_ADDITIVE_TRAINING_NOISE"
            or item["mean"] != 0
            or item["applies_to"] != "TRAINING_ONLY"
        ):
            raise PilotProposalError("noise law leaks or changes evaluator outcomes")
    transfers = _list(tasks["transfer_shifts"], "transfer shifts")
    transfer_fields = frozenset(
        {"id", "transfer_x", "what_changes", "what_remains_fixed"}
    )
    transfer_ids = []
    for raw in transfers:
        item = _closed_object(raw, "transfer shift", transfer_fields)
        transfer_ids.append(_text(item["id"], "transfer id"))
        values = _list(item["transfer_x"], "transfer x")
        if any(
            type(x) is not int or x <= max(tasks["fixed_heldout_x"]) for x in values
        ):
            raise PilotProposalError("transfer covariates are invalid")
    if (
        len(resources) * len(noises) * len(transfers) != 12
        or amplitudes != sorted(set(amplitudes))
        or transfer_ids != ["NEAR_TRANSFER", "FAR_TRANSFER"]
    ):
        raise PilotProposalError("task factor levels do not define twelve exact cells")
    for name in (
        "agent_visible_task",
        "evaluator_held",
        "reference_and_measurement",
        "prior_applicability",
    ):
        _text(tasks[name], f"task_distribution.{name}")
    audit = _closed_object(
        tasks["generation_audit"],
        "generation_audit",
        frozenset(
            {
                "maximum_generation_attempts_per_cell",
                "maximum_total_generation_attempts",
                "candidate_checks_per_attempt",
                "maximum_total_candidate_checks",
                "rejection_reasons_retained",
                "failed_cell_stops_stage",
                "audit_outputs_visible_to_agent",
                "audit_fixture_unit_ceiling",
                "audit_wall_second_ceiling",
                "audit_costs_excluded_from_agent_run_totals_and_accounted_separately",
                "checks",
            }
        ),
    )
    attempts_per_cell = _exact_int(
        audit["maximum_generation_attempts_per_cell"], "generation attempts", minimum=1
    )
    total_attempts = 12 * attempts_per_cell
    checks_per_attempt = _exact_int(
        audit["candidate_checks_per_attempt"], "candidate checks", minimum=1
    )
    if (
        audit["maximum_total_generation_attempts"] != total_attempts
        or audit["maximum_total_candidate_checks"]
        != total_attempts * checks_per_attempt
        or checks_per_attempt != tasks["direct_candidate_combinations"]
        or audit["rejection_reasons_retained"] is not True
        or audit["failed_cell_stops_stage"] is not True
        or audit["audit_outputs_visible_to_agent"] is not False
        or audit["audit_costs_excluded_from_agent_run_totals_and_accounted_separately"]
        is not True
        or _exact_int(audit["audit_fixture_unit_ceiling"], "audit units", minimum=1)
        <= 0
        or _exact_int(audit["audit_wall_second_ceiling"], "audit wall", minimum=1) <= 0
        or len(_list(audit["checks"], "audit checks")) < 6
    ):
        raise PilotProposalError("task inclusion audit is unbounded or incomplete")

    pairing = _closed_object(
        payload["seed_pairing"],
        "seed_pairing",
        frozenset(
            {
                "agent_visible_seed_material",
                "experimental_unit",
                "four_arms_share_task_practice_heldout_and_transfer_realization",
                "provider_randomness_is_seed_paired",
                "provider_draw_ordinal_recorded",
                "task_seed",
                "candidate_construction_seed",
                "practice_seed",
                "heldout_transfer_seed",
                "future_shadow_allocated",
                "distinct_hashes_claim_independence",
                "variance_analysis",
            }
        ),
    )
    expected_pairing_flags = {
        "agent_visible_seed_material": False,
        "four_arms_share_task_practice_heldout_and_transfer_realization": True,
        "provider_randomness_is_seed_paired": False,
        "provider_draw_ordinal_recorded": True,
        "future_shadow_allocated": False,
        "distinct_hashes_claim_independence": False,
    }
    if any(
        pairing[name] is not value for name, value in expected_pairing_flags.items()
    ):
        raise PilotProposalError("seed visibility or pairing semantics changed")
    for name in set(pairing) - set(expected_pairing_flags):
        _text(pairing[name], f"seed_pairing.{name}")

    budget = _closed_object(
        payload["budget"],
        "budget",
        frozenset(
            {
                "development_blocks_per_profile",
                "calibration_blocks_per_profile",
                "reserve_blocks_per_profile",
                "development_runs",
                "calibration_runs",
                "reserve_runs",
                "primary_runs",
                "maximum_runs",
                "adaptive_runs",
                "minimalist_runs",
                "adaptive_proposal_calls_per_run",
                "adaptive_selection_calls_per_run",
                "minimalist_proposal_calls_per_run",
                "maximum_provider_attempts_per_call",
                "maximum_provider_request_attempts",
                "successful_input_tokens_per_run",
                "input_ceiling_includes_repeated_conversation_history",
                "successful_output_tokens_per_run_including_reasoning",
                "output_ceiling_includes_reasoning_tokens",
                "retry_ceiling_replays_applicable_input",
                "maximum_billable_input_tokens",
                "maximum_billable_output_tokens_including_reasoning",
                "research_service_calls_per_run",
                "maximum_research_service_calls",
                "fixture_units_per_run",
                "maximum_fixture_units",
                "model_call_deadline_seconds",
                "run_wall_seconds",
                "development_stage_wall_seconds",
                "calibration_stage_wall_seconds",
                "reserve_stage_wall_seconds",
                "campaign_wall_seconds",
                "deadlines_share_original_run_and_stage_ceiling",
                "provider_retry_rule",
                "ambiguous_timeout_rule",
                "policy_exhaustion_replaceable",
                "pricing_verified_at_utc",
                "standard_input_usd_per_million_tokens",
                "cache_write_input_usd_per_million_tokens",
                "cache_read_input_usd_per_million_tokens",
                "output_usd_per_million_tokens",
                "hard_financial_ceiling_usd",
                "uncached_token_maxima_cost_usd",
                "all_input_cache_write_token_maxima_cost_usd",
                "all_input_cache_write_alternative_status",
                "cache_write_safe_input_tokens_under_current_ceiling",
                "sixty_percent_no_retry_uncached_scenario_usd",
                "sixty_percent_figure_is_scenario_not_expectation",
                "admission_rule",
                "unknown_billing_reservations_retained_until_reconciled",
                "excluded_costs",
            }
        ),
    )
    profiles_n = len(AgentProfile)
    arms_n = len(ExperimentalArm)
    development_blocks = _exact_int(
        budget["development_blocks_per_profile"], "development blocks", minimum=1
    )
    calibration_blocks = _exact_int(
        budget["calibration_blocks_per_profile"], "calibration blocks", minimum=1
    )
    reserve_blocks = _exact_int(
        budget["reserve_blocks_per_profile"], "reserve blocks", minimum=1
    )
    development_runs = profiles_n * arms_n * development_blocks
    calibration_runs = profiles_n * arms_n * calibration_blocks
    reserve_runs = profiles_n * arms_n * reserve_blocks
    primary_runs = development_runs + calibration_runs
    maximum_runs = primary_runs + reserve_runs
    adaptive_runs = (
        (profiles_n - 1)
        * arms_n
        * (development_blocks + calibration_blocks + reserve_blocks)
    )
    minimalist_runs = maximum_runs - adaptive_runs
    derived_runs = {
        "development_runs": development_runs,
        "calibration_runs": calibration_runs,
        "reserve_runs": reserve_runs,
        "primary_runs": primary_runs,
        "maximum_runs": maximum_runs,
        "adaptive_runs": adaptive_runs,
        "minimalist_runs": minimalist_runs,
    }
    if any(budget[name] != expected for name, expected in derived_runs.items()):
        raise PilotProposalError("stage/run budget arithmetic is inconsistent")
    adaptive_calls = _exact_int(
        budget["adaptive_proposal_calls_per_run"], "adaptive proposal calls", minimum=1
    ) + _exact_int(
        budget["adaptive_selection_calls_per_run"],
        "adaptive selection calls",
        minimum=1,
    )
    minimalist_calls = _exact_int(
        budget["minimalist_proposal_calls_per_run"], "minimalist calls", minimum=1
    )
    provider_attempts = _exact_int(
        budget["maximum_provider_attempts_per_call"], "provider attempts", minimum=1
    )
    maximum_requests = (
        adaptive_runs * adaptive_calls + minimalist_runs * minimalist_calls
    ) * provider_attempts
    input_per_run = _exact_int(
        budget["successful_input_tokens_per_run"], "input tokens", minimum=1
    )
    output_per_run = _exact_int(
        budget["successful_output_tokens_per_run_including_reasoning"],
        "output tokens",
        minimum=1,
    )
    maximum_input = maximum_runs * input_per_run * provider_attempts
    maximum_output = maximum_runs * output_per_run * provider_attempts
    fixture_per_run = _exact_int(
        budget["fixture_units_per_run"], "fixture units", minimum=1
    )
    service_calls = _exact_int(
        budget["research_service_calls_per_run"], "service calls", minimum=1
    )
    derived_limits = {
        "maximum_provider_request_attempts": maximum_requests,
        "maximum_billable_input_tokens": maximum_input,
        "maximum_billable_output_tokens_including_reasoning": maximum_output,
        "maximum_research_service_calls": maximum_runs * service_calls,
        "maximum_fixture_units": maximum_runs * fixture_per_run,
    }
    if any(budget[name] != expected for name, expected in derived_limits.items()):
        raise PilotProposalError(
            "token, request, service, or fixture budget is inconsistent"
        )
    if (
        budget["adaptive_proposal_calls_per_run"] != 4
        or budget["adaptive_selection_calls_per_run"] != 1
        or budget["minimalist_proposal_calls_per_run"] != 1
        or provider_attempts != 2
        or fixture_per_run
        != 4 * max(item["paired_practice_fixture_units"] for item in resources)
        + max(item["candidate_fixture_units"] for item in resources)
    ):
        raise PilotProposalError("interaction and resource maxima disagree")
    call_wall = _exact_int(
        budget["model_call_deadline_seconds"], "call deadline", minimum=1
    )
    run_wall = _exact_int(budget["run_wall_seconds"], "run deadline", minimum=1)
    stage_walls = [
        _exact_int(budget[name], name, minimum=1)
        for name in (
            "development_stage_wall_seconds",
            "calibration_stage_wall_seconds",
            "reserve_stage_wall_seconds",
        )
    ]
    if (
        call_wall > run_wall
        or sum(stage_walls) != budget["campaign_wall_seconds"]
        or budget["deadlines_share_original_run_and_stage_ceiling"] is not True
        or budget["policy_exhaustion_replaceable"] is not False
        or budget["unknown_billing_reservations_retained_until_reconciled"] is not True
        or budget["sixty_percent_figure_is_scenario_not_expectation"] is not True
        or budget["input_ceiling_includes_repeated_conversation_history"] is not True
        or budget["output_ceiling_includes_reasoning_tokens"] is not True
        or budget["retry_ceiling_replays_applicable_input"] is not True
    ):
        raise PilotProposalError("time, retry, or exhaustion rules are inconsistent")
    for name in (
        "provider_retry_rule",
        "ambiguous_timeout_rule",
        "pricing_verified_at_utc",
        "all_input_cache_write_alternative_status",
        "admission_rule",
    ):
        _text(budget[name], f"budget.{name}")
    standard_input = _decimal(
        budget["standard_input_usd_per_million_tokens"], "standard input price"
    )
    cache_write = _decimal(
        budget["cache_write_input_usd_per_million_tokens"], "cache-write price"
    )
    cache_read = _decimal(
        budget["cache_read_input_usd_per_million_tokens"], "cache-read price"
    )
    output_price = _decimal(budget["output_usd_per_million_tokens"], "output price")
    if (standard_input, cache_write, cache_read, output_price) != (
        Decimal("2.0"),
        Decimal("2.5"),
        Decimal("0.2"),
        Decimal("12.0"),
    ):
        raise PilotProposalError("proposal uses unsupported provider pricing")
    uncached_cost = (
        Decimal(maximum_input) * standard_input + Decimal(maximum_output) * output_price
    ) / Decimal(1_000_000)
    cache_write_cost = (
        Decimal(maximum_input) * cache_write + Decimal(maximum_output) * output_price
    ) / Decimal(1_000_000)
    hard_ceiling = _decimal(
        budget["hard_financial_ceiling_usd"], "hard financial ceiling"
    )
    safe_cache_write_input = int(
        (hard_ceiling * Decimal(1_000_000) - Decimal(maximum_output) * output_price)
        / cache_write
    )
    scenario = (
        Decimal(primary_runs)
        * Decimal("0.6")
        * (
            Decimal(input_per_run) * standard_input
            + Decimal(output_per_run) * output_price
        )
        / Decimal(1_000_000)
    )
    if (
        _decimal(budget["uncached_token_maxima_cost_usd"], "uncached cost")
        != uncached_cost
        or _decimal(
            budget["all_input_cache_write_token_maxima_cost_usd"],
            "cache-write cost",
        )
        != cache_write_cost
        or hard_ceiling != uncached_cost
        or budget["cache_write_safe_input_tokens_under_current_ceiling"]
        != safe_cache_write_input
        or _decimal(
            budget["sixty_percent_no_retry_uncached_scenario_usd"], "scenario cost"
        )
        != scenario
        or cache_write_cost <= hard_ceiling
    ):
        raise PilotProposalError("financial proposal arithmetic is inconsistent")
    excluded = _list(budget["excluded_costs"], "excluded costs")
    if set(excluded) != {
        "TAXES",
        "INDEPENDENTLY_BILLED_INFRASTRUCTURE",
        "TASK_GENERATION_AND_INCLUSION_AUDIT_REPORTED_SEPARATELY",
    }:
        raise PilotProposalError("financial exclusions are incomplete")

    handling = _closed_object(
        payload["data_handling"],
        "data_handling",
        frozenset(
            {
                "provider_payload_allowlist",
                "forbidden_provider_fields",
                "store_false_required",
                "store_false_claims_zero_retention",
                "account_level_retention_choice",
                "api_data_training_opt_in",
                "extended_prompt_caching_allowed",
                "payload_canary_test_required",
                "proposal_grants_network_or_disclosure_permission",
            }
        ),
    )
    allowlist = _list(handling["provider_payload_allowlist"], "payload allowlist")
    forbidden = _list(handling["forbidden_provider_fields"], "forbidden payload")
    if (
        len(set(allowlist)) != len(allowlist)
        or len(set(forbidden)) != len(forbidden)
        or len(allowlist) < 6
        or len(forbidden) < 9
        or handling["store_false_required"] is not True
        or handling["store_false_claims_zero_retention"] is not False
        or handling["api_data_training_opt_in"] is not False
        or handling["extended_prompt_caching_allowed"] is not False
        or handling["payload_canary_test_required"] is not True
        or handling["proposal_grants_network_or_disclosure_permission"] is not False
    ):
        raise PilotProposalError("provider data boundary is incomplete")
    _text(handling["account_level_retention_choice"], "retention choice")

    stages = _closed_object(
        payload["stages"],
        "stages",
        frozenset({"development", "calibration", "reserve", "revision_rule"}),
    )
    development = _closed_object(
        stages["development"],
        "development stage",
        frozenset(
            {
                "runs",
                "manifest_required",
                "public_fixed_tasks",
                "evidence_role",
                "retained",
                "pooled_into_calibration",
            }
        ),
    )
    calibration = _closed_object(
        stages["calibration"],
        "calibration stage",
        frozenset(
            {
                "runs",
                "manifest_required",
                "private_disjoint_tasks",
                "requires_separate_owner_approval",
                "requires_one_use_execution_authorization",
                "proceeding_requires_positive_v2_performance",
                "evidence_role",
            }
        ),
    )
    reserve = _closed_object(
        stages["reserve"],
        "reserve stage",
        frozenset(
            {
                "runs",
                "manifest_required",
                "prospectively_allocated",
                "one_failed_source_and_one_reserve_each",
                "policy_exhaustion_replaceable",
            }
        ),
    )
    if (
        development["runs"] != development_runs
        or development["manifest_required"] is not True
        or development["public_fixed_tasks"] is not True
        or development["retained"] is not True
        or development["pooled_into_calibration"] is not False
        or calibration["runs"] != calibration_runs
        or calibration["manifest_required"] is not True
        or calibration["private_disjoint_tasks"] is not True
        or calibration["requires_separate_owner_approval"] is not True
        or calibration["requires_one_use_execution_authorization"] is not True
        or calibration["proceeding_requires_positive_v2_performance"] is not False
        or reserve["runs"] != reserve_runs
        or reserve["manifest_required"] is not True
        or reserve["prospectively_allocated"] is not True
        or reserve["one_failed_source_and_one_reserve_each"] is not True
        or reserve["policy_exhaustion_replaceable"] is not False
    ):
        raise PilotProposalError("stage boundaries or evidence roles are inconsistent")
    for value in (
        development["evidence_role"],
        calibration["evidence_role"],
        stages["revision_rule"],
    ):
        _text(value, "stage evidence rule")

    evidence = _closed_object(
        payload["evidence_use"],
        "evidence_use",
        frozenset(
            {
                "development_rows_excluded_from_calibration",
                "partial_and_failed_runs_retained",
                "failed_blocks_excluded_as_whole_from_analysis_rows",
                "may_support_pilot_engineering_and_design_revision",
                "may_qualify_b_e4",
                "may_set_posthoc_thresholds",
                "may_count_as_shadow_or_attack_evidence",
            }
        ),
    )
    expected_evidence = {
        "development_rows_excluded_from_calibration": True,
        "partial_and_failed_runs_retained": True,
        "failed_blocks_excluded_as_whole_from_analysis_rows": True,
        "may_support_pilot_engineering_and_design_revision": True,
        "may_qualify_b_e4": False,
        "may_set_posthoc_thresholds": False,
        "may_count_as_shadow_or_attack_evidence": False,
    }
    if evidence != expected_evidence:
        raise PilotProposalError("pilot evidence use crosses its maturity ceiling")

    _validate_owner_decisions_v2(payload["owner_decisions"])
    sources = _list(payload["source_verification"], "source verification")
    for raw in sources:
        item = _closed_object(
            raw,
            "source verification",
            frozenset({"claim", "url", "verified_at_utc"}),
        )
        _text(item["claim"], "source claim")
        url = _text(item["url"], "source URL")
        verified = _text(item["verified_at_utc"], "source verification time")
        if not url.startswith(
            ("https://developers.openai.com/", "https://platform.openai.com/")
        ) or not verified.endswith("Z"):
            raise PilotProposalError("source is not a frozen official record")
    if len(sources) < 3:
        raise PilotProposalError(
            "model, request, pricing, and retention sources are required"
        )

    digest = pilot_proposal_digest(payload)
    if payload["proposal_digest"] != digest:
        raise PilotProposalError("pilot proposal digest does not bind its content")
    return AutonomousPilotProposal(
        proposal_digest=digest,
        model_id=population["model_id"],
        profile_count=len(by_profile),
        task_cell_count=tasks["factorial_cells"],
        primary_runs=primary_runs,
        reserve_runs=reserve_runs,
        maximum_runs=maximum_runs,
        maximum_provider_request_attempts=maximum_requests,
        maximum_billable_input_tokens=maximum_input,
        maximum_billable_output_tokens=maximum_output,
        expected_spend_usd=scenario,
        hard_financial_ceiling_usd=hard_ceiling,
        schema_version="2.0",
        proposal_id=payload["proposal_id"],
    )


def validate_autonomous_pilot_proposal(
    payload: dict[str, Any],
) -> AutonomousPilotProposal:
    if type(payload) is not dict:
        raise PilotProposalError("pilot proposal must be an exact object")
    version = payload.get("schema_version")
    if version == "1.0":
        return _validate_v1_autonomous_pilot_proposal(payload)
    if version == "2.0":
        return _validate_v2_autonomous_pilot_proposal(payload)
    raise PilotProposalError("pilot proposal schema version is unsupported")


def load_autonomous_pilot_proposal(
    path: Path = PILOT_PROPOSAL_PATH,
) -> AutonomousPilotProposal:
    if not isinstance(path, Path):
        raise TypeError("pilot proposal path must be path-like")

    def reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PilotProposalError(f"duplicate JSON member is forbidden: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_members,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PilotProposalError("pilot proposal is unreadable") from error
    return validate_autonomous_pilot_proposal(payload)


__all__ = (
    "PILOT_AUTHORITY_CEILING",
    "PILOT_PROPOSAL_PATH",
    "PILOT_PROPOSAL_STATUS",
    "PILOT_V1_PROPOSAL_PATH",
    "PILOT_V1_PROPOSAL_STATUS",
    "AutonomousPilotProposal",
    "PilotProposalError",
    "load_autonomous_pilot_proposal",
    "pilot_proposal_digest",
    "validate_autonomous_pilot_proposal",
)

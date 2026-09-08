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

PILOT_PROPOSAL_STATUS = "ENGINEERING_ACCEPTED / OWNER_UNAPPROVED / PILOT_NOT_AUTHORIZED"
PILOT_AUTHORITY_CEILING = (
    "PROPOSAL_ONLY_NO_MODEL_INFERENCE_OR_CAMPAIGN_EXECUTION_AUTHORITY"
)
PILOT_PROPOSAL_PATH = Path(
    ".agent/preregistrations/B-E4_autonomous_agent_pilot_v1.json"
)
_DOMAIN = b"carbon.be4.autonomous-agent-pilot-proposal.v1\x00"
_TOP_LEVEL_FIELDS = frozenset(
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

    @property
    def pilot_authorized(self) -> bool:
        return False

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def pilot_proposal_digest(payload: dict[str, Any]) -> str:
    if type(payload) is not dict:
        raise TypeError("pilot proposal digest requires an exact object")
    content = {key: value for key, value in payload.items() if key != "proposal_digest"}
    encoded = json.dumps(
        content,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(_DOMAIN + encoded).hexdigest()


def _object(value: object, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise PilotProposalError(f"{name} must be an exact object")
    return value


def _exact_int(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PilotProposalError(f"{name} must be an exact bounded integer")
    return value


def _decimal(value: object, name: str) -> Decimal:
    if type(value) not in (int, float) or type(value) is bool:
        raise PilotProposalError(f"{name} must be an exact finite number")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise PilotProposalError(f"{name} must be an exact finite number")
    return result


def validate_autonomous_pilot_proposal(
    payload: dict[str, Any],
) -> AutonomousPilotProposal:
    if type(payload) is not dict or set(payload) != _TOP_LEVEL_FIELDS:
        raise PilotProposalError("pilot proposal has an unexpected top-level shape")
    if (
        payload["schema_version"] != "1.0"
        or payload["proposal_id"] != "B-E4-AUTONOMOUS-AGENT-PILOT-V1"
        or payload["status"] != PILOT_PROPOSAL_STATUS
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

    population = _object(payload["model_population"], "model_population")
    if (
        population.get("design") != "ONE_COMMON_BASE_MODEL_ACROSS_PROFILE_POLICIES"
        or population.get("provider") != "OPENAI_API"
        or population.get("model_id") != "gpt-5.6-terra"
        or population.get("api") != "RESPONSES"
        or population.get("reasoning_effort") != "medium"
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

    protocol = _object(payload["adaptive_protocol"], "adaptive_protocol")
    attempts = _exact_int(
        protocol.get("maximum_attempts_per_run"), "attempts", minimum=1
    )
    if (
        protocol.get("loop")
        != "PROPOSAL_TO_PRACTICE_TO_PERMITTED_FEEDBACK_TO_NEXT_PROPOSAL"
        or protocol.get("heldout_transfer_shadow_visible_to_agent") is not False
        or protocol.get("v2_specific_branch") is not False
        or protocol.get("saved_budget_creates_extra_attempts") is not False
    ):
        raise PilotProposalError("adaptive protocol violates the arm-neutral boundary")

    tasks = _object(payload["task_distribution"], "task_distribution")
    factors = _object(tasks.get("factors"), "task factors")
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
    ):
        raise PilotProposalError(
            "task distribution does not preserve a non-exhaustive pilot"
        )

    pairing = _object(payload["seed_pairing"], "seed_pairing")
    if (
        pairing.get("four_arms_share_task_and_evaluator_realization") is not True
        or pairing.get("provider_randomness_is_seed_paired") is not False
        or pairing.get("distinct_hashes_claim_independence") is not False
        or pairing.get("future_shadow_allocated") is not False
    ):
        raise PilotProposalError(
            "seed/pairing proposal overclaims experimental dependence"
        )

    budget = _object(payload["budget"], "budget")
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

    evidence = _object(payload["evidence_use"], "evidence_use")
    if (
        evidence.get("may_support_pilot_engineering_and_design_revision") is not True
        or evidence.get("may_qualify_b_e4") is not False
        or evidence.get("may_set_posthoc_thresholds") is not False
        or evidence.get("may_count_as_shadow_or_attack_evidence") is not False
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
        or {item.get("decision") for item in decisions if type(item) is dict}
        != expected_decisions
        or any(item.get("status") != "PROPOSED" for item in decisions)
    ):
        raise PilotProposalError("pilot owner decisions must remain exactly proposed")
    sources = payload["source_verification"]
    if (
        type(sources) is not list
        or not sources
        or any(
            type(item) is not dict
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


def load_autonomous_pilot_proposal(
    path: Path = PILOT_PROPOSAL_PATH,
) -> AutonomousPilotProposal:
    if not isinstance(path, Path):
        raise TypeError("pilot proposal path must be path-like")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PilotProposalError("pilot proposal is unreadable") from error
    return validate_autonomous_pilot_proposal(payload)


__all__ = (
    "PILOT_AUTHORITY_CEILING",
    "PILOT_PROPOSAL_PATH",
    "PILOT_PROPOSAL_STATUS",
    "AutonomousPilotProposal",
    "PilotProposalError",
    "load_autonomous_pilot_proposal",
    "pilot_proposal_digest",
    "validate_autonomous_pilot_proposal",
)

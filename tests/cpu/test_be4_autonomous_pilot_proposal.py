from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from carbon.gauntlet.model import AgentProfile
from carbon.gauntlet.pilot import (
    PILOT_PROPOSAL_PATH,
    PILOT_PROPOSAL_STATUS,
    PILOT_V1_PROPOSAL_PATH,
    PilotProposalError,
    load_autonomous_pilot_proposal,
    pilot_proposal_digest,
    validate_autonomous_pilot_proposal,
)
from carbon.gauntlet.pilot_contract import (
    PilotContractError,
    PilotEvent,
    PilotPhase,
    advance_pilot_interaction,
    bounded_provider_deadline_seconds,
    build_offline_provider_payload,
    initial_pilot_interaction,
    proposed_synthetic_task_cells,
    run_offline_synthetic_inclusion_audit,
)


def _payload() -> dict[str, object]:
    return json.loads(PILOT_PROPOSAL_PATH.read_text(encoding="utf-8"))


def _redigest(payload: dict[str, object]) -> None:
    payload["proposal_digest"] = pilot_proposal_digest(payload)


def test_canonical_pilot_proposal_is_exact_and_never_authorized() -> None:
    proposal = load_autonomous_pilot_proposal()
    assert proposal.model_id == "gpt-5.6-terra"
    assert proposal.profile_count == 5
    assert proposal.task_cell_count == 12
    assert proposal.primary_runs == 280
    assert proposal.reserve_runs == 20
    assert proposal.maximum_runs == 300
    assert proposal.schema_version == "2.0"
    assert proposal.maximum_provider_request_attempts == 2520
    assert proposal.maximum_billable_input_tokens == 19_660_800
    assert proposal.maximum_billable_output_tokens == 4_915_200
    assert str(proposal.expected_spend_usd) == "27.52512"
    assert str(proposal.hard_financial_ceiling_usd) == "98.304"
    assert proposal.pilot_authorized is False
    assert proposal.qualifying_execution_ready is False
    assert _payload()["status"] == PILOT_PROPOSAL_STATUS


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("pilot_authorized",), True),
        (("inference_executed",), True),
        (("model_population", "built_in_tools_enabled"), True),
        (("model_population", "documented_responses_seed_available"), True),
        (
            (
                "interaction_state_machine",
                "selection_call_may_create_or_evaluate_candidate",
            ),
            True,
        ),
        (("interaction_state_machine", "arm_and_run_transcripts_isolated"), False),
        (("task_distribution", "selected_using_future_v2_outcomes"), True),
        (("seed_pairing", "distinct_hashes_claim_independence"), True),
        (("budget", "policy_exhaustion_replaceable"), True),
        (
            ("budget", "input_ceiling_includes_repeated_conversation_history"),
            False,
        ),
        (("budget", "output_ceiling_includes_reasoning_tokens"), False),
        (("budget", "retry_ceiling_replays_applicable_input"), False),
        (("evidence_use", "may_qualify_b_e4"), True),
    ],
)
def test_authority_and_hidden_evaluation_escalations_fail_closed(
    path: tuple[str, ...], value: object
) -> None:
    payload = copy.deepcopy(_payload())
    target = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index,assignment]
    target[path[-1]] = value  # type: ignore[index]
    _redigest(payload)
    with pytest.raises(PilotProposalError):
        validate_autonomous_pilot_proposal(payload)


def test_budget_and_price_claims_are_derived_not_asserted() -> None:
    for field in (
        "maximum_runs",
        "maximum_provider_request_attempts",
        "maximum_billable_input_tokens",
        "maximum_billable_output_tokens_including_reasoning",
        "maximum_research_service_calls",
        "maximum_fixture_units",
        "development_runs",
        "hard_financial_ceiling_usd",
    ):
        payload = copy.deepcopy(_payload())
        payload["budget"][field] += 1  # type: ignore[index,operator]
        _redigest(payload)
        with pytest.raises(PilotProposalError):
            validate_autonomous_pilot_proposal(payload)


def test_attempt_budget_remains_non_exhaustive() -> None:
    payload = _payload()
    payload["interaction_state_machine"][  # type: ignore[index]
        "maximum_proposal_attempts_for_adaptive_profiles"
    ] = 8
    _redigest(payload)
    with pytest.raises(PilotProposalError):
        validate_autonomous_pilot_proposal(payload)


def test_owner_decisions_cannot_self_approve() -> None:
    payload = _payload()
    payload["owner_decisions"][0]["status"] = "APPROVED"  # type: ignore[index]
    _redigest(payload)
    with pytest.raises(PilotProposalError):
        validate_autonomous_pilot_proposal(payload)


def test_unbound_or_unreadable_proposal_fails_closed(tmp_path: Path) -> None:
    payload = _payload()
    payload["research_question"] += " changed"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PilotProposalError):
        load_autonomous_pilot_proposal(changed)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(PilotProposalError):
        load_autonomous_pilot_proposal(malformed)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"2.0","schema_version":"2.0"}', encoding="utf-8"
    )
    with pytest.raises(PilotProposalError, match="duplicate JSON member"):
        load_autonomous_pilot_proposal(duplicate)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("seed_pairing", "agent_visible_seed_material"), True),
        (
            (
                "interaction_state_machine",
                "invalid_refusal_and_truncation_consume_proposal_attempt",
            ),
            False,
        ),
        (("evidence_use", "partial_and_failed_runs_retained"), False),
        (("evidence_use", "development_rows_excluded_from_calibration"), False),
        (("profiles", 0, "adaptive"), False),
        (("model_population", "service_tier"), "fast"),
        (("budget", "model_call_deadline_seconds"), 0),
    ],
)
def test_recomputed_digest_cannot_hide_a_semantic_contradiction(
    path: tuple[object, ...], value: object
) -> None:
    payload = copy.deepcopy(_payload())
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    _redigest(payload)
    with pytest.raises(PilotProposalError):
        validate_autonomous_pilot_proposal(payload)


def test_owner_role_sets_and_nested_shapes_are_exact() -> None:
    mutations = []

    missing_owner = copy.deepcopy(_payload())
    missing_owner["owner_decisions"][0]["required_owners"] = []
    mutations.append(missing_owner)

    missing_rule = copy.deepcopy(_payload())
    del missing_rule["task_distribution"]["generation_audit"]
    mutations.append(missing_rule)

    extra_nested = copy.deepcopy(_payload())
    extra_nested["seed_pairing"]["unsupported_extra"] = True
    mutations.append(extra_nested)

    for payload in mutations:
        _redigest(payload)
        with pytest.raises(PilotProposalError):
            validate_autonomous_pilot_proposal(payload)


def test_historical_v1_remains_valid_and_immutable_history() -> None:
    historical = load_autonomous_pilot_proposal(PILOT_V1_PROPOSAL_PATH)
    assert historical.schema_version == "1.0"
    assert historical.proposal_digest == (
        "sha256:8ca1a79a9cd9866d54f52c797baf0ea392087c4652a1439017339a66610469f3"
    )
    assert historical.pilot_authorized is False


def test_adaptive_selection_is_a_metered_fifth_call_and_cannot_create_candidate() -> (
    None
):
    state = initial_pilot_interaction(AgentProfile.PLANNER)
    for index in range(4):
        state = advance_pilot_interaction(
            state, PilotEvent.VALID_PROPOSAL, candidate_id=f"candidate-{index}"
        )
        state = advance_pilot_interaction(state, PilotEvent.PRACTICE_SUCCESS)
    assert state.phase is PilotPhase.READY_FOR_SELECTION
    assert state.provider_requests == 4
    with pytest.raises(PilotContractError, match="existing admissible ancestor"):
        advance_pilot_interaction(
            state, PilotEvent.FINAL_SELECTION_OR_STOP, candidate_id="new-candidate"
        )
    selected = advance_pilot_interaction(
        state, PilotEvent.FINAL_SELECTION_OR_STOP, candidate_id="candidate-2"
    )
    assert selected.phase is PilotPhase.TERMINAL
    assert selected.provider_requests == 5
    assert selected.selected_ancestor_id == "candidate-2"


@pytest.mark.parametrize(
    "event",
    (
        PilotEvent.INVALID_STRATEGY,
        PilotEvent.SCHEMA_INVALID_OR_MALFORMED_OUTPUT,
        PilotEvent.REFUSAL,
        PilotEvent.TRUNCATED_OR_OUTPUT_BUDGET_EXHAUSTED,
    ),
)
def test_invalid_outputs_consume_minimalist_only_attempt(event: PilotEvent) -> None:
    state = advance_pilot_interaction(
        initial_pilot_interaction(AgentProfile.MINIMALIST), event
    )
    assert state.phase is PilotPhase.TERMINAL
    assert state.proposal_attempts == 1
    assert state.provider_requests == 1


def test_provider_retry_and_ambiguous_timeout_are_not_free_attempts() -> None:
    state = initial_pilot_interaction(AgentProfile.EVOLUTIONARY)
    retried = advance_pilot_interaction(
        state, PilotEvent.VERIFIED_EXTERNAL_PROVIDER_FAILURE
    )
    assert retried.proposal_attempts == 0
    assert retried.provider_requests == 1
    exhausted = advance_pilot_interaction(
        retried, PilotEvent.VERIFIED_EXTERNAL_PROVIDER_FAILURE
    )
    assert exhausted.phase is PilotPhase.TERMINAL
    ambiguous = advance_pilot_interaction(state, PilotEvent.AMBIGUOUS_TIMEOUT)
    assert ambiguous.proposal_attempts == 1
    assert ambiguous.provider_requests == 1
    assert ambiguous.unknown_billing_reservation is True


def test_deadlines_are_nested_and_do_not_refresh_on_retry() -> None:
    assert (
        bounded_provider_deadline_seconds(
            requested_call_seconds=120.0,
            remaining_run_seconds=43.0,
            remaining_stage_seconds=500.0,
            remaining_campaign_seconds=900.0,
        )
        == 43.0
    )
    with pytest.raises(PilotContractError):
        bounded_provider_deadline_seconds(
            requested_call_seconds=120.0,
            remaining_run_seconds=0.0,
            remaining_stage_seconds=500.0,
            remaining_campaign_seconds=900.0,
        )


def test_provider_payload_allowlist_rejects_forbidden_canaries() -> None:
    payload = {
        "frozen_system_and_profile_policy": "planner-v2",
        "agent_visible_synthetic_task_description": "public fixture task",
        "current_arm_permitted_prior_material": "no-prior",
        "current_run_permitted_practice_feedback": ("range",),
        "public_resource_facts": {"units": 22},
        "current_run_existing_candidate_ids": ("candidate-1",),
    }
    assert build_offline_provider_payload(payload) == payload
    poisoned = copy.deepcopy(payload)
    poisoned["public_resource_facts"] = {"evaluator_seed": "canary"}
    with pytest.raises(PilotContractError, match="forbidden canary"):
        build_offline_provider_payload(poisoned)
    disguised = copy.deepcopy(payload)
    disguised["public_resource_facts"] = {"Evaluator-Seeds": "canary"}
    with pytest.raises(PilotContractError, match="forbidden canary"):
        build_offline_provider_payload(disguised)
    extra = {**payload, "credentials": "canary"}
    with pytest.raises(PilotContractError, match="allow-listed shape"):
        build_offline_provider_payload(extra)


def test_twelve_cell_recipe_and_bounded_offline_audit_are_nonqualifying() -> None:
    cells = proposed_synthetic_task_cells()
    assert len(cells) == 12
    assert {item.resource_regime for item in cells} == {
        "DATA_SCARCE",
        "BALANCED",
        "COMPUTE_SCARCE",
    }
    audit = run_offline_synthetic_inclusion_audit(
        evaluator_seed=b"be4-v2-offline-design-audit"
    )
    assert audit.cell_count == 12
    assert audit.generation_attempts == 12
    assert audit.candidate_checks == 96
    assert audit.fixture_units == 1824
    assert len(audit.unique_endpoint_counts) == 12
    assert audit.all_candidates_reconstructed
    assert audit.all_families_causally_active
    assert audit.endpoint_ranges_nonzero
    assert audit.no_single_candidate_dominates_all_cells
    assert audit.arm_neutral_baselines_checked
    assert audit.within_cell_saturation_recorded
    assert audit.qualifying_execution_ready is False


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("stages", "development", "pooled_into_calibration"), True),
        (("stages", "calibration", "requires_one_use_execution_authorization"), False),
        (("profiles", 4, "proposal_calls_per_run"), 2),
        (("budget", "maximum_provider_request_attempts"), 2400),
        (("budget", "cache_write_input_usd_per_million_tokens"), 2.0),
        (("data_handling", "store_false_claims_zero_retention"), True),
        (
            (
                "task_distribution",
                "generation_audit",
                "maximum_total_generation_attempts",
            ),
            49,
        ),
    ),
)
def test_v2_cross_field_contradictions_fail_with_fresh_digest(
    path: tuple[object, ...], value: object
) -> None:
    payload = copy.deepcopy(_payload())
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    _redigest(payload)
    with pytest.raises(PilotProposalError):
        validate_autonomous_pilot_proposal(payload)

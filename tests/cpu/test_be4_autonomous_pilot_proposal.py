from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from carbon.gauntlet.pilot import (
    PILOT_PROPOSAL_PATH,
    PILOT_PROPOSAL_STATUS,
    PilotProposalError,
    load_autonomous_pilot_proposal,
    pilot_proposal_digest,
    validate_autonomous_pilot_proposal,
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
    assert proposal.maximum_provider_request_attempts == 2400
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
        (("adaptive_protocol", "v2_specific_branch"), True),
        (("adaptive_protocol", "heldout_transfer_shadow_visible_to_agent"), True),
        (("task_distribution", "selected_using_future_v2_outcomes"), True),
        (("seed_pairing", "distinct_hashes_claim_independence"), True),
        (("budget", "policy_exhaustion_replaceable"), True),
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
        "maximum_billable_output_tokens",
        "maximum_research_service_calls",
        "maximum_fixture_units",
        "maximum_run_wall_seconds",
        "expected_spend_usd",
        "hard_financial_ceiling_usd",
    ):
        payload = copy.deepcopy(_payload())
        payload["budget"][field] += 1  # type: ignore[index,operator]
        _redigest(payload)
        with pytest.raises(PilotProposalError):
            validate_autonomous_pilot_proposal(payload)


def test_attempt_budget_remains_non_exhaustive() -> None:
    payload = _payload()
    payload["adaptive_protocol"]["maximum_attempts_per_run"] = 8  # type: ignore[index]
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

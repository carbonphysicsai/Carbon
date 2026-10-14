"""Public reply selection/negative controls; synthetic task views are fixtures."""

import asyncio
import copy
import json

import pytest
from test_lp_prod_research_tools import ledger
from test_standard_mcp_adapter import make_adapter, reply, workspace

from carbon import research
from carbon.battery.campaign import provider_plan as battery_plan
from carbon.challenge_registry.agent_plan import provider_plan as challenge_plan
from carbon.development_session import research_reply as rr
from carbon.development_session.research_tools import PREFIX, ResearchMinerTools
from carbon.miner_mcp.standard import AdapterFailure, _result


def task(state="QUEUED", revision=0):
    return {
        "task_id": {"value": "rtsk_" + "a" * 64},
        "challenge_key": {"fixture": "public-challenge"},
        "state": state,
        "revision": revision,
        "created_at_micros": 1,
        "updated_at_micros": revision + 1,
        "immutable_bindings": {"fixture": "same-public-bindings"},
        "progress": None,
        "terminal_receipt": None,
    }


def envelope(state="SUCCEEDED", revision=2):
    value = reply("start_research_task")
    value["reply"]["result"] = {"created": True, "task": task()}
    value["terminal_task"] = task(state, revision)
    return value


def test_retained_queued_receipt_and_newer_observation_are_explicit():
    value = envelope()
    original = copy.deepcopy(value)
    new = rr.project(value, rr.RULE)
    assert new["current_task"] == {
        "state": "SUCCEEDED",
        "revision": 2,
        "source": "terminal_task",
        "reply_task_revision": 0,
        "reply_task_role": "RETAINED_PROTOCOL_OBSERVATION",
    }
    assert new["schema"] == rr.RULE
    assert new["reply"] is value["reply"]  # The receipt is not overwritten.
    assert value == original
    assert next(iter(new)) == "current_task"
    assert next(iter(json.loads(json.dumps(new, sort_keys=True)))) == "current_task"
    payload, settled = _result("start_research_task", new, reply_rule=rr.RULE)
    assert payload == new and settled is False


@pytest.mark.parametrize("state", [state.value for state in research.ResearchTaskState])
def test_current_means_returned_observation_not_terminal_or_settled(state):
    value = envelope(state, 2)
    value["requires_reconciliation"] = True
    new = rr.project(value, rr.RULE)
    assert new["current_task"]["state"] == state
    assert _result("start_research_task", new, reply_rule=rr.RULE)[1] is True


@pytest.mark.parametrize("operation", research.SUPPORTED_OPERATIONS)
def test_every_non_task_operation_and_no_task_error_has_explicit_null(operation):
    value = reply(operation)
    new = rr.project(value, rr.RULE)
    assert new["current_task"] is None
    assert _result(operation, new, reply_rule=rr.RULE)[0] == new
    assert rr.project(value, None) is value
    assert set(_result(operation, value)[0]) == rr.LEGACY_FIELDS


def test_receipt_only_and_identical_revision_are_valid_and_task_is_not_duplicated():
    value = envelope("QUEUED", 0)
    assert rr.project(value, rr.RULE)["current_task"]["source"] == "terminal_task"
    value["terminal_task"] = None
    assert rr.project(value, rr.RULE)["current_task"]["source"] == "reply.result.task"
    assert set(rr.project(value, rr.RULE)) == rr.FIELDS


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("task_id", {"value": "rtsk_" + "b" * 64}),
        ("challenge_key", {"fixture": "foreign"}),
        ("immutable_bindings", {"fixture": "different"}),
        ("created_at_micros", 2),
        ("revision", -1),
        ("revision", True),
        ("revision", 2**64),
        ("state", "PASSED"),
        ("private_seed", "NEVER-ECHO"),
    ],
)
def test_foreign_malformed_or_unbound_task_cannot_become_authority(field, replacement):
    value = envelope()
    value["terminal_task"][field] = replacement
    with pytest.raises(ValueError):
        rr.project(value, rr.RULE)


def test_stale_same_revision_disagreement_and_unbound_observation_refuse():
    value = envelope()
    value["reply"]["result"]["task"] = task("RUNNING", 3)
    with pytest.raises(ValueError, match="inconsistent"):
        rr.project(value, rr.RULE)
    value["terminal_task"] = task("SUCCEEDED", 3)
    with pytest.raises(ValueError, match="inconsistent"):
        rr.project(value, rr.RULE)
    value["reply"]["result"] = {}
    with pytest.raises(ValueError, match="unbound"):
        rr.project(value, rr.RULE)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("state", "QUEUED"),
        ("revision", 0),
        ("revision", True),
        ("source", "reply.result.task"),
        ("reply_task_revision", 9),
        ("reply_task_role", "CURRENT"),
        ("extra", "NEVER-ECHO"),
    ],
)
def test_adapter_recomputes_summary_instead_of_trusting_claim(field, replacement):
    value = rr.project(envelope(), rr.RULE)
    value["current_task"][field] = replacement
    with pytest.raises(AdapterFailure, match="INVALID_RESULT") as failure:
        _result("start_research_task", value, reply_rule=rr.RULE)
    assert failure.value.dispatch_may_have_occurred
    assert "NEVER-ECHO" not in str(failure.value)


def test_selected_schema_cannot_silently_upgrade_downgrade_or_accept_extra_fields():
    legacy = envelope()
    new = rr.project(legacy, rr.RULE)
    for value, rule in (
        (legacy, rr.RULE),
        (new, None),
        ({**new, "private": 1}, rr.RULE),
    ):
        with pytest.raises(AdapterFailure, match="INVALID_RESULT"):
            _result("start_research_task", value, reply_rule=rule)


def test_truncation_preserves_compact_authority_and_has_explicit_cut_record():
    value = envelope()
    value["public_result"] = {"stdout": "x" * (2 * 1024**2)}
    new = rr.project(value, rr.RULE)
    payload, _ = _result("start_research_task", new, reply_rule=rr.RULE)
    assert payload["current_task"] == new["current_task"]
    assert payload["reply"]["result"]["task"]["state"] == "QUEUED"
    assert payload["terminal_task"]["state"] == "SUCCEEDED"
    assert payload["truncation"]["cut_total"] >= 1
    assert len(json.dumps(payload, separators=(",", ":")).encode()) <= 1024**2


def test_frozen_selection_reopen_historical_and_unknown_rule(tmp_path, monkeypatch):
    old = ledger(tmp_path / "old", provider={"agent": "none"})
    fresh = ledger(tmp_path / "new", provider={"research_reply": rr.RULE})
    assert rr.campaign_rule(old) is None
    assert rr.campaign_rule(fresh) == rr.RULE
    from carbon.development_session.research_ledger import CampaignLedger

    assert rr.campaign_rule(CampaignLedger(fresh.root)) == rr.RULE
    bad = ledger(
        tmp_path / "bad", provider={"research_reply": "REQUESTER-TEXT-SENTINEL"}
    )
    sdk, _ = make_adapter(ledger=bad)

    async def forbidden(*args, **kwargs):
        pytest.fail("unknown rule reached dispatch")

    monkeypatch.setattr(ResearchMinerTools, "_call", forbidden)
    with pytest.raises(ValueError, match="provider.research_reply") as error:
        asyncio.run(
            sdk.call(PREFIX + "start_research_task", workspace(), "rule-operation-0001")
        )
    assert "REQUESTER-TEXT-SENTINEL" not in str(error.value)


@pytest.mark.parametrize("provider_plan", [battery_plan, challenge_plan])
@pytest.mark.parametrize("agent", ["none", "autonomous"])
def test_new_provider_plans_freeze_reply_rule(provider_plan, agent):
    plan = provider_plan(
        agent, {"ceilings": {"provider_attempts": 96, "provider_nanodollars": 10**10}}
    )
    assert rr.frozen_rule({"provider": plan}) == rr.RULE
    historical = {k: v for k, v in plan.items() if k != "research_reply"}
    assert rr.frozen_rule({"provider": historical}) is None


def test_refusals_and_unavailable_keep_registered_shape():
    value = {
        "operation": "inspect_prior_alignment",
        "status": "UNAVAILABLE",
        "reason": "missing_data_support",
        "detail": "No registered public prior pack",
        "authority_granted": False,
    }
    assert rr.project(value, rr.RULE) is value
    assert _result("inspect_prior_alignment", value, reply_rule=rr.RULE)[0] == value


@pytest.mark.parametrize("provider_plan", [battery_plan, challenge_plan])
def test_new_graphite_provider_plan_freezes_reply_rule(provider_plan):
    from test_battery_graphite_plan import BUDGET, block

    plan = provider_plan("graphite", BUDGET, graphite=block())
    assert rr.frozen_rule({"provider": plan}) == rr.RULE

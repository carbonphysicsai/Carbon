"""Agent-facing door usability (AGENT-DOOR-USABILITY-01).

Found by the Graphite Test executor (GRAPHITE_LAUNCHPAD_FINDINGS rows A1, A2,
A5, A6, A7). Claims tested, each absence paired with the same check finding a
presence:

- A1: every new run plan - agent none, autonomous and Graphite, from both plan
  builders - freezes argument-normalisation.v2; the same plan without it reads
  as no rule, as every plan frozen before does;
- A2: under a v2 plan the miner MCP door's schema admits the string "null"
  for practice action and arguments, so the call reaches the adapter and
  builds the request real null builds; under no rule or v1 the published
  tools are byte for byte the base commit's (pinned), and a schema refusal is
  Carbon's registered correction - the declared field and the fix - never the
  schema library's dump, on the plain tool and on the Tasks start alike;
- A5: a new phase-3 session records budget-status.v2 and its turn status
  drops "0 of 0 research trials left"; a session recorded without a rule
  keeps the line; an unknown rule resumes nothing; an Attacker session
  records none;
- A6: the turn status names the research trials left wherever the ledger
  meters them, under each status builder;
- A7: a phase-3 proposal on a backend these pods do not serve is refused with
  the backends they serve, from the Challenge's public scoring record.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import graphite_phase3_fixtures as p3f
import pytest
from graphite_phase3_fixtures import (
    BASELINE,
    ScriptedPods,
    propose,
    provider,
    run_id,
    session,
    steps,
    text,
    tool,
)
from test_battery_graphite_plan import BUDGET
from test_research_tool_usability import (
    FROZEN_BEFORE,
    NORMALISING_V1,
    NORMALISING_V2,
    OPERATION_ID,
    door_args,
    door_for,
)
from test_standard_mcp_adapter import make_adapter

from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite.provider import SessionMismatch
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session import research_loop
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_tools import (
    ARGUMENT_NORMALISATION_V2,
    PREFIX,
    frozen_argument_normalisation,
)

START = PREFIX + "start_research_task"

# ---- A1. Every new plan freezes argument-normalisation.v2.


@pytest.mark.parametrize("module", ["battery", "registry"])
@pytest.mark.parametrize("agent", ["none", "autonomous"])
def test_every_new_plan_freezes_v2_and_an_older_plan_reads_as_none(module, agent):
    if module == "battery":
        from carbon.battery.campaign import provider_plan
    else:
        from carbon.challenge_registry.agent_plan import provider_plan
    plan = provider_plan(agent, BUDGET)
    assert plan["argument_normalisation"] == ARGUMENT_NORMALISATION_V2
    assert frozen_argument_normalisation({"provider": plan}) == (
        ARGUMENT_NORMALISATION_V2
    )
    # The same plan as it was frozen before: no rule, read as none.
    old = {k: v for k, v in plan.items() if k != "argument_normalisation"}
    assert frozen_argument_normalisation({"provider": old}) is None


def test_the_agentless_plan_is_the_old_plan_plus_the_rule():
    from carbon.challenge_registry.agent_plan import provider_plan

    plan = provider_plan("none", None)
    assert {k: v for k, v in plan.items() if k != "argument_normalisation"} == {
        "agent": "none",
        "model_calls": 0,
    }


# ---- A2. The MCP door agrees with the SDK under the frozen rule.

#: The published tools of the miner MCP door (every tool record, and the
#: start_research_task input schema), as the base commit (e5491d2c) served
#: them: for a campaign with no manifest and for one whose plan froze the
#: tools rule with no normalisation or with v1. A v2 campaign's is the only
#: prospective change.
NO_MANIFEST_TOOLS = (
    "sha256:703eba98fed5f5dd5b2668a50f4203a95e310304c6e8c45464770f4d5e11b74f"
)
TOOLS_RULE_TOOLS = (
    "sha256:4ac1dc11bd442c57f3dcfa4b03a058ea1fbec8a7d567540918d7063c87ea9c8f"
)
START_SCHEMA = "sha256:a071cec5d8d479c90b11924a6115f00c64926596c12c741c7e2de28e638966cf"
#: The v2 campaign's start_research_task input schema (this change).
START_SCHEMA_V2 = (
    "sha256:167839552c2d80a11c0affe13c8c7436a539026930191dc6bc1b7c09046dbb9b"
)


def server_for(adapter):
    from carbon.miner_mcp.standard_server import _create_server

    return _create_server(adapter)


def published(server):
    return [
        tool.model_dump(mode="json", by_alias=True, exclude_none=True)
        for tool in asyncio.run(server.list_tools())
    ]


def start_schema(tools):
    return next(t for t in tools if t["name"] == START)["inputSchema"]


def action_values(schema):
    """The string values start_research_task's action schema enumerates."""
    action = schema["properties"]["action"]
    return [
        v for option in action.get("anyOf", [action]) for v in option.get("enum", [])
    ]


def refused_text(server, arguments):
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError) as raised:
        asyncio.run(
            server.call_tool(START, {**arguments, "operation_id": OPERATION_ID})
        )
    return str(raised.value)


def test_older_plans_publish_the_base_commits_tools_byte_for_byte(tmp_path):
    _, adapter = make_adapter()
    tools = published(server_for(adapter))
    assert digest(canonical(tools)) == NO_MANIFEST_TOOLS
    assert digest(canonical(start_schema(tools))) == START_SCHEMA
    for name, plan in (("before", FROZEN_BEFORE), ("v1", NORMALISING_V1)):
        adapter, _, composition, _ = door_for(tmp_path / name, plan)
        try:
            tools = published(server_for(adapter))
            assert digest(canonical(tools)) == TOOLS_RULE_TOOLS
            assert digest(canonical(start_schema(tools))) == START_SCHEMA
            assert "null" not in action_values(start_schema(tools))
        finally:
            composition.tasks.close()


def test_a_v2_plan_admits_null_for_practice_action_and_arguments(tmp_path):
    adapter, _, composition, built = door_for(tmp_path / "v2", NORMALISING_V2)
    real, _, real_composition, real_built = door_for(tmp_path / "real", NORMALISING_V2)
    try:
        server = server_for(adapter)
        schema = start_schema(published(server))
        assert digest(canonical(schema)) == START_SCHEMA_V2
        assert "null" in action_values(schema)
        text = refused_text(server, door_args(action="null", arguments="null"))
        # It reached the adapter and the SDK: refused only at admission,
        # after the request was built, nothing dispatched.
        assert "CAMPAIGN_ADMISSION_STOPPED" in text, text
        assert "INVALID_ARGUMENT" not in text
        refused_text(server_for(real), door_args())
        from carbon import research

        assert len(built) == len(real_built) == 1
        assert research.canonical_bytes(built[0]) == research.canonical_bytes(
            real_built[0]
        )
    finally:
        composition.tasks.close()
        real_composition.tasks.close()


@pytest.mark.parametrize("plan", [None, FROZEN_BEFORE, NORMALISING_V1])
def test_an_older_plans_null_is_refused_with_its_correction_not_a_dump(tmp_path, plan):
    adapter, _, composition, built = door_for(tmp_path, plan)
    try:
        text = refused_text(server_for(adapter), door_args(action="null"))
        assert text.startswith(
            "Error executing tool " + START + ": INVALID_ARGUMENT; "
            "dispatch_may_have_occurred=false; field=action; next_action="
        ), text
        assert "; correction_code=practice_recipe_required; correction=" in text
        assert 'It holds the string "null".' in text
        assert "The tool: start_research_task." in text
        # No schema-library text, and nothing sent is repeated.
        for dump in ("validation error", "literal_error", "input_value", "pydantic"):
            assert dump not in text
        assert built == []
    finally:
        composition.tasks.close()


@pytest.mark.parametrize(
    ("change", "field", "code"),
    [
        ({"strategy_json": "{}"}, "strategy", "object_field_named"),
        ({"arguments_json": "null"}, "arguments", "object_field_named"),
        ({"hypothesis": ""}, "hypothesis", "tool_text_bounded"),
        ({"kind": "batch"}, "kind", "tool_value_invalid"),
    ],
)
def test_a_schema_refusal_names_the_field_and_the_fix(change, field, code):
    _, adapter = make_adapter()
    text = refused_text(server_for(adapter), {**door_args(), **change})
    assert f"field={field}; next_action=" in text
    assert f"; correction_code={code}; correction=" in text
    assert f"The field that broke the contract: {field}." in text
    assert "validation error" not in text and "extra_forbidden" not in text


def test_an_invented_key_is_never_named_back():
    _, adapter = make_adapter()
    text = refused_text(server_for(adapter), {**door_args(), "my_secret_key": 1})
    assert "my_secret_key" not in text and "field=" not in text
    assert "; correction_code=tool_field_unexpected; correction=" in text


def test_the_tasks_start_refuses_as_the_plain_tool_does(monkeypatch):
    from test_lp_prod_mcp_door import start, tasks_extension

    _, adapter = make_adapter()
    extension, ctx = tasks_extension(adapter, monkeypatch)
    sent = {**door_args(), "action": "null"}
    plain = refused_text(server_for(adapter), sent)
    tasks = start(extension, ctx, {**sent, "operation_id": OPERATION_ID})
    assert plain.endswith(tasks)
    assert tasks.startswith(
        "INVALID_ARGUMENT; dispatch_may_have_occurred=false; field=action; "
    )


def test_hypothesis_and_expected_effect_are_declared_where_the_service_takes_them():
    from carbon.development_session.research_tools import FIELDS

    _, adapter = make_adapter()
    properties = start_schema(published(server_for(adapter)))["properties"]
    for name in ("hypothesis", "expected_effect"):
        assert name in FIELDS["start_research_task"] and name in properties


# ---- A5. Phase-3 sessions record the budget-status rule.

TRIAL_LINE = "research trials left in the campaign budget"


def statuses(graphite):
    """The turn status text each model request carried."""
    found = []
    for request in graphite.model.requests:
        for item in request["input"]:
            content = item.get("content") if type(item) is dict else None
            if type(content) is str and content.startswith("Carbon status"):
                found.append(content)
    return found


def _opened(graphite, number=1):
    return json.loads(
        (graphite._dir(run_id(number)) / "session-open.json").read_bytes()
    )


def test_a_new_phase3_session_records_v2_and_drops_the_unmetered_trial_line(
    tmp_path,
):
    probe = tool(PREFIX + "get_challenge_info", {})
    _, graphite, _ = session(tmp_path, [probe, text("done")], ScriptedPods())
    assert _opened(graphite)["budget_status"] == phase3.BUDGET_STATUS_V2
    seen = statuses(graphite)
    assert seen and not any(TRIAL_LINE in s for s in seen)
    # The money it does meter is still named.
    assert all("provider spend left" in s for s in seen)


def test_a_session_recorded_without_the_rule_keeps_the_v1_line(tmp_path, monkeypatch):
    probe = tool(PREFIX + "get_challenge_info", {})
    monkeypatch.setattr(phase3.Phase3Provider, "NEW_SESSION_BUDGET_STATUS", None)
    _, graphite, _ = session(tmp_path, [probe, text("done")], ScriptedPods())
    assert "budget_status" not in _opened(graphite)
    seen = statuses(graphite)
    assert seen and all("0 of 0 " + TRIAL_LINE in s for s in seen)


def test_an_unknown_budget_status_rule_resumes_nothing():
    with pytest.raises(SessionMismatch, match="budget_status_unknown"):
        phase3.budget_status_of({"budget_status": "carbon.graphite.budget-status.v9"})
    assert phase3.budget_status_of({}) is None


def test_an_attacker_session_records_no_budget_status_rule():
    from carbon.agent_campaign.graphite.phase4 import AttackerProvider

    assert AttackerProvider.NEW_SESSION_BUDGET_STATUS is None
    assert phase3.Phase3Provider.NEW_SESSION_BUDGET_STATUS == phase3.BUDGET_STATUS_V2


# ---- A6. The trials left are named wherever the ledger meters them.


def _status(tmp_path, name, *, trials, used, omit, trial_limit=None):
    return research_loop.budget_status(
        tmp_path,
        name,
        calls_left=None,
        call_limit=None,
        slots_left=None if trial_limit is None else trial_limit - used,
        trial_limit=trial_limit,
        ledger_status={
            "budget": {"research_trials": trials},
            "used": {
                "research_trials": used,
                "provider_attempts": 0,
                "provider_nanodollars": 0,
            },
        },
        provider=SimpleNamespace(reservation_nano=None),
        unit="session",
        offered=[START],
        omit_unmetered_trials=omit,
    )["content"]


@pytest.mark.parametrize("omit", [False, True])
def test_metered_trials_are_named_every_turn_under_either_status_rule(tmp_path, omit):
    assert "9 of 12 " + TRIAL_LINE in _status(
        tmp_path, f"metered-{omit}", trials=12, used=3, omit=omit
    )
    # A per-session slot cap the miner set is named beside it.
    assert "2 of 4 research-trial slots left in this session" in _status(
        tmp_path, f"slots-{omit}", trials=12, used=2, omit=omit, trial_limit=4
    )
    # No ceiling: there is no count to name, and none is invented.
    assert TRIAL_LINE not in _status(
        tmp_path, f"unmetered-{omit}", trials=None, used=0, omit=omit
    )


def test_the_v2_agents_turn_status_names_its_trial_slots(tmp_path):
    message = research_loop.turn_status(
        tmp_path,
        "turn",
        calls_left=5,
        call_limit=48,
        slots_left=2,
        trial_limit=3,
        unit="epoch",
        offered=[START],
    )
    assert "2 of 3 research-trial slots left" in message["content"]


# ---- A7. A refusal on an unserved backend lists the served ones.


def test_an_unserved_backend_refusal_lists_the_served_backends(tmp_path):
    strategy = {
        **BASELINE,
        "parameters": {**BASELINE["parameters"], "backend": "pytorch"},
    }
    account = ScriptedPods(steps=steps(1.0))
    _, graphite, _ = session(tmp_path, [propose(strategy), text("done")], account)
    [record] = graphite.experiment(run_id()).records("proposal")
    assert record["status"] == "REFUSED_BACKEND_NOT_SERVED"
    served = list(challenge_scoring.resolve(p3f.SCORING).served_backends)
    assert record["served_backends"] == served and "pytorch" not in served
    assert account.launched == []
    # The agent's own view of the result carries the list.
    seen = [
        json.loads(item["output"])
        for item in graphite.model.requests[-1]["input"]
        if type(item) is dict and item.get("type") == "function_call_output"
    ]
    assert any(view.get("served_backends") == served for view in seen), seen


def test_a_served_backend_proposal_carries_no_list(tmp_path):
    account = ScriptedPods(steps=steps(1.0, 0.9))
    _, graphite, _ = session(tmp_path, [propose(BASELINE), text("done")], account)
    for record in graphite.experiment(run_id()).records():
        assert "served_backends" not in record


def test_the_provider_fixture_still_opens_on_the_default_rule(tmp_path):
    graphite = provider(tmp_path, [], ScriptedPods())
    assert graphite.opening_rules() == {"budget_status": phase3.BUDGET_STATUS_V2}

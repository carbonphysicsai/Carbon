"""The prospective agent uses the same public direct tool session as a miner."""

import asyncio
import hashlib
import json

import pytest

from carbon.agent_campaign.graphite.direct_tool_session import (
    DIRECT_PREFIX,
    SESSION,
    STAGE_GRAPH,
    SUBMIT,
    DirectToolSession,
    UncertainDirectToolDispatch,
)

CAMPAIGN_A = "sha256:" + "a" * 64
CAMPAIGN_B = "sha256:" + "b" * 64


def operation_id(campaign, identity):
    return (
        "graphite-direct-"
        + hashlib.sha256((campaign + "\0" + identity).encode("utf-8")).hexdigest()
    )


def opened(*, intake=True):
    return {
        "campaign": SESSION,
        "open": True,
        "development_only": True,
        "official_eligible": False,
        "construction_intake_configured": intake,
        "tools": [
            {
                "name": DIRECT_PREFIX + "get_challenge_info",
                "description": "Read public Challenge information",
                "input_schema": {
                    "type": "object",
                    "properties": {"operation_id": {"type": "string"}},
                    "required": [],
                    "additionalProperties": False,
                },
            }
        ],
    }


def route(calls, *, intake=True):
    def invoke(action, value):
        calls.append((action, value))
        return (
            opened(intake=intake) if action == "open" else {"ok": True, "result": value}
        )

    return invoke


def test_open_uses_normal_session_and_exposes_only_offered_tools():
    calls = []
    session = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    assert calls == [("open", {})]
    names = {tool["name"] for tool in session.tools}
    assert names == {DIRECT_PREFIX + "get_challenge_info", STAGE_GRAPH, SUBMIT}
    assert "operation_id" not in session.tools[0]["parameters"]["properties"]
    assert all(tool["strict"] is True for tool in session.tools)

    result = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-000"
        )
    )
    assert result["ok"] is True
    assert calls[-1] == (
        "call",
        {
            "tool": DIRECT_PREFIX + "get_challenge_info",
            "arguments": {
                "operation_id": operation_id(CAMPAIGN_A, "epoch-1-direct-tool-000")
            },
        },
    )


def test_construction_actions_use_public_route_with_unmodified_recipe():
    calls = []
    session = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    recipe = {"challenge": {"id": "public", "version": 1}, "construction": {}}
    raw = json.dumps(recipe)
    staged = asyncio.run(
        session.call(
            STAGE_GRAPH,
            {"recipe_json": raw, "expected_manifest_digest": None},
            "epoch-1-direct-tool-001",
        )
    )
    submitted = asyncio.run(
        session.call(SUBMIT, {"recipe_json": raw}, "epoch-1-direct-tool-002")
    )
    assert staged["ok"] and submitted["ok"]
    assert calls[1:] == [
        (
            "stage_construction_graph",
            {"recipe": recipe, "expected_manifest_digest": None},
        ),
        ("submit_construction", {"recipe": recipe}),
    ]


def test_direct_start_uses_strict_agent_json_and_existing_mcp_tool():
    calls = []
    state = opened()
    state["tools"].append(
        {
            "name": DIRECT_PREFIX + "start_research_task",
            "description": "Start public DEVELOPMENT research",
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string"},
                    "recipe": {"type": "object", "additionalProperties": True},
                },
                "required": ["recipe"],
                "additionalProperties": False,
            },
        }
    )
    session = DirectToolSession(route(calls), state, campaign_identity=CAMPAIGN_A)
    schema = next(
        tool["parameters"]
        for tool in session.tools
        if tool["name"] == DIRECT_PREFIX + "start_research_task"
    )
    assert schema["properties"] == {"recipe_json": schema["properties"]["recipe_json"]}
    assert schema["required"] == ["recipe_json"]
    assert schema["additionalProperties"] is False
    result = asyncio.run(
        session.call(
            DIRECT_PREFIX + "start_research_task",
            {"recipe_json": '{"source":{"kind":"graph"}}'},
            "epoch-1-direct-tool-006",
        )
    )
    assert result["ok"] is True
    assert calls == [
        (
            "call",
            {
                "tool": DIRECT_PREFIX + "start_research_task",
                "arguments": {
                    "recipe": {"source": {"kind": "graph"}},
                    "operation_id": operation_id(CAMPAIGN_A, "epoch-1-direct-tool-006"),
                },
            },
        )
    ]


def test_unoffered_or_malformed_calls_never_dispatch():
    calls = []
    session = DirectToolSession.open(
        route(calls, intake=False), campaign_identity=CAMPAIGN_A
    )
    assert SUBMIT not in {tool["name"] for tool in session.tools}
    bad = [
        (SUBMIT, {"recipe_json": "{}"}),
        (DIRECT_PREFIX + "private_state", {}),
        (DIRECT_PREFIX + "get_challenge_info", {"operation_id": "model-owned"}),
    ]
    for name, arguments in bad:
        result = asyncio.run(session.call(name, arguments, "epoch-1-direct-tool-003"))
        assert result["dispatched"] is False
    assert calls == [("open", {})]

    session = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    for raw in ('{"a":1,"a":2}', "[1]", '{"a":NaN}'):
        result = asyncio.run(
            session.call(SUBMIT, {"recipe_json": raw}, "epoch-1-direct-tool-004")
        )
        assert result["dispatched"] is False
    assert calls == [("open", {}), ("open", {})]


def test_session_close_releases_route_and_refuses_later_dispatch():
    calls = []
    session = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    session.close()
    result = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-005"
        )
    )
    assert calls == [("open", {}), ("close", {})]
    assert result["reason_code"] == "direct_tool_session_closed"
    assert result["dispatched"] is False


def test_invalid_public_description_releases_opened_session():
    calls = []

    def invalid(action, value):
        calls.append((action, value))
        if action == "open":
            state = opened()
            state["tools"][0]["name"] = DIRECT_PREFIX + "private_state"
            return state
        return {"open": False}

    with pytest.raises(ValueError, match="malformed direct tool"):
        DirectToolSession.open(invalid, campaign_identity=CAMPAIGN_A)
    assert calls == [("open", {}), ("close", {})]


def test_operation_id_is_stable_on_retry_and_separate_across_campaigns():
    calls = []
    first = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    second = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_B)
    identity = "epoch-1-direct-tool-007"
    name = DIRECT_PREFIX + "get_challenge_info"
    for session in (first, first, second):
        assert asyncio.run(session.call(name, {}, identity))["ok"] is True
    sent = [
        value["arguments"]["operation_id"]
        for action, value in calls
        if action == "call"
    ]
    assert sent == [
        operation_id(CAMPAIGN_A, identity),
        operation_id(CAMPAIGN_A, identity),
        operation_id(CAMPAIGN_B, identity),
    ]
    assert sent[0] != sent[2]
    assert all(len(value) <= 114 for value in sent)
    assert all(CAMPAIGN_A not in value and CAMPAIGN_B not in value for value in sent)


def test_real_direct_envelope_promotes_reconciliation_to_loop_top_level():
    calls = []

    def uncertain(action, value):
        calls.append((action, value))
        if action == "open":
            return opened()
        return {
            "ok": True,
            "result": {
                "reply": {"status": "OK"},
                "task": None,
                "requires_reconciliation": True,
                "official_eligible": False,
            },
        }

    session = DirectToolSession.open(uncertain, campaign_identity=CAMPAIGN_A)
    result = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-008"
        )
    )
    assert result["requires_reconciliation"] is True
    assert result["result"]["requires_reconciliation"] is True
    assert len(calls) == 2


@pytest.mark.parametrize("outcome", ["timeout", "malformed", "protected"])
def test_post_route_uncertainty_never_claims_nondispatch(outcome):
    calls = []

    def uncertain(action, value):
        calls.append((action, value))
        if action == "open":
            return opened()
        if outcome == "timeout":
            raise TimeoutError("private route diagnostic")
        if outcome == "protected":
            return {"ok": True, "result": {"official_seed": "private"}}
        return None

    session = DirectToolSession.open(uncertain, campaign_identity=CAMPAIGN_A)
    with pytest.raises(
        UncertainDirectToolDispatch, match="direct tool outcome requires reconciliation"
    ) as error:
        asyncio.run(
            session.call(
                DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-009"
            )
        )
    assert "private" not in str(error.value)
    assert len(calls) == 2


@pytest.mark.parametrize("field", ["open", "development_only", "official_eligible"])
def test_wrong_session_authority_is_rejected(field):
    state = opened()
    state[field] = not state[field]
    with pytest.raises(ValueError, match="direct DEVELOPMENT"):
        DirectToolSession(lambda *_: None, state, campaign_identity=CAMPAIGN_A)

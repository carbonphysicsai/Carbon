"""The prospective agent uses the same public direct tool session as a miner."""

import asyncio
import hashlib
import json
import shutil
import time
from itertools import pairwise
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite.direct_tool_session import (
    DIRECT_PREFIX,
    SESSION,
    STAGE_GRAPH,
    SUBMIT,
    DirectToolSession,
    UncertainDirectToolDispatch,
    prepare_direct_agent_campaign,
    run_direct_epoch,
)

CAMPAIGN_A = "sha256:" + "a" * 64
CAMPAIGN_B = "sha256:" + "b" * 64
TASK_ID = "rtsk_" + "a" * 64


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
        "challenge": {"id": "synthetic-linear-field-2d", "version": "1.0"},
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
        if action == "open":
            return opened(intake=intake)
        if action == "close":
            return {"open": False, "closed": True}
        if action == "call":
            result = direct_result(value)
            if value["tool"].removeprefix(DIRECT_PREFIX) in {
                "start_research_task",
                "get_research_result",
                "cancel_research_task",
            }:
                result["task"] = {
                    "task_id": {"value": TASK_ID},
                    "state": "SUCCEEDED",
                }
            return {"ok": True, "result": result}
        return {"ok": True, "result": value}

    return invoke


def direct_result(value, *, reconcile=False):
    return {
        "schema": "carbon.direct-mcp-result.v3",
        "operation": value["tool"].removeprefix(DIRECT_PREFIX),
        "operation_id": value["arguments"]["operation_id"],
        "reply": {"status": "OK"},
        "task": None,
        "public_result": None,
        "requires_reconciliation": reconcile,
        "official_eligible": False,
    }


def test_open_uses_normal_session_and_exposes_only_offered_tools():
    calls = []
    session = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    assert len(calls) == 1 and calls[0][0] == "open"
    assert set(calls[0][1]) == {"exclusive_token"}
    assert len(calls[0][1]["exclusive_token"]) == 32
    names = {tool["name"] for tool in session.tools}
    assert names == {DIRECT_PREFIX + "get_challenge_info", STAGE_GRAPH, SUBMIT}
    assert "operation_id" not in session.tools[0]["parameters"]["properties"]
    assert all(tool["strict"] is True for tool in session.tools)


def test_offered_material_tool_uses_normal_direct_call_with_bounded_fields():
    calls = []

    def invoke(action, value):
        if action == "open":
            state = opened(intake=False)
            state["tools"].append(
                {
                    "name": DIRECT_PREFIX + "stage_research_material",
                    "description": "Stage one pinned material chunk",
                    "input_schema": {"type": "object"},
                }
            )
            return state
        calls.append((action, value))
        return {"ok": True, "result": direct_result(value)}

    session = DirectToolSession.open(invoke, campaign_identity=CAMPAIGN_A)
    name = DIRECT_PREFIX + "stage_research_material"
    tool = next(item for item in session.tools if item["name"] == name)
    assert set(tool["parameters"]["properties"]) == {
        "bundle_digest",
        "name",
        "offset",
        "total_bytes",
        "content_digest",
        "chunk_base64",
    }
    args = {
        "bundle_digest": "sha256:" + "a" * 64,
        "name": "source.tar.gz",
        "offset": 0,
        "total_bytes": 1,
        "content_digest": "sha256:" + "b" * 64,
        "chunk_base64": "eA==",
    }
    result = asyncio.run(session.call(name, args, "epoch-1-direct-tool-910"))
    assert result["ok"] is True
    assert calls[0][0] == "call" and calls[0][1]["tool"] == name
    assert all(calls[0][1]["arguments"][key] == value for key, value in args.items())

    result = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-000"
        )
    )
    assert result["ok"] is True
    action, value = calls[-1]
    assert (
        action == "call" and value["exclusive_token"] == calls[0][1]["exclusive_token"]
    )
    assert {key: item for key, item in value.items() if key != "exclusive_token"} == {
        "tool": DIRECT_PREFIX + "get_challenge_info",
        "arguments": {
            "operation_id": operation_id(CAMPAIGN_A, "epoch-1-direct-tool-000")
        },
    }


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
    assert [
        (action, {k: v for k, v in value.items() if k != "exclusive_token"})
        for action, value in calls[1:]
    ] == [
        (
            "stage_construction_graph",
            {"recipe": recipe, "expected_manifest_digest": None},
        ),
        ("submit_construction", {"recipe": recipe}),
    ]
    assert all(
        value["exclusive_token"] == calls[0][1]["exclusive_token"]
        for _, value in calls[1:]
    )


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
    assert [
        {k: v for k, v in value.items() if k != "exclusive_token"} for _, value in calls
    ] == [
        {
            "tool": DIRECT_PREFIX + "start_research_task",
            "arguments": {
                "recipe": {"source": {"kind": "graph"}},
                "operation_id": operation_id(CAMPAIGN_A, "epoch-1-direct-tool-006"),
            },
        }
    ]
    assert [action for action, _ in calls] == ["call"]


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
    assert len(calls) == 1 and set(calls[0][1]) == {"exclusive_token"}

    session = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    for raw in ('{"a":1,"a":2}', "[1]", '{"a":NaN}'):
        result = asyncio.run(
            session.call(SUBMIT, {"recipe_json": raw}, "epoch-1-direct-tool-004")
        )
        assert result["dispatched"] is False
    assert [action for action, _ in calls] == ["open", "open"]
    assert all(set(value) == {"exclusive_token"} for _, value in calls)


def test_session_close_releases_route_and_refuses_later_dispatch():
    calls = []
    session = DirectToolSession.open(route(calls), campaign_identity=CAMPAIGN_A)
    session.close()
    result = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-005"
        )
    )
    assert [action for action, _ in calls] == ["open", "close"]
    assert calls[0][1] == calls[1][1]
    assert result["reason_code"] == "direct_tool_session_closed"
    assert result["dispatched"] is False


def test_session_close_requires_supervised_release():
    session = DirectToolSession(
        lambda action, _value: {"closed": False} if action == "close" else None,
        opened(),
        campaign_identity=CAMPAIGN_A,
    )
    with pytest.raises(UncertainDirectToolDispatch, match="shutdown requires"):
        session.close()


def test_keepalive_refuses_a_reaped_and_reopened_tools_attachment():
    opens = []

    def invoke(action, value):
        if action == "open":
            opens.append(value)
            state = opened()
            state["opened_unix"] = len(opens)
            return state
        raise AssertionError("a changed attachment must not dispatch")

    session = DirectToolSession.open(invoke, campaign_identity=CAMPAIGN_A)

    async def refresh():
        stop = asyncio.Event()
        await session.keepalive(stop, interval=0.01)

    asyncio.run(refresh())
    assert len(opens) == 2
    with pytest.raises(UncertainDirectToolDispatch, match="attachment needs"):
        asyncio.run(
            session.call(
                DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-025"
            )
        )


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
    assert [action for action, _ in calls] == ["open", "close"]
    assert calls[0][1] == calls[1][1]


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
        return {"ok": True, "result": direct_result(value, reconcile=True)}

    session = DirectToolSession.open(uncertain, campaign_identity=CAMPAIGN_A)
    result = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_challenge_info", {}, "epoch-1-direct-tool-008"
        )
    )
    assert result["requires_reconciliation"] is True
    assert result["result"]["requires_reconciliation"] is True
    assert len(calls) == 2


def test_known_running_task_can_be_observed_without_losing_uncertain_custody():
    state = opened()
    for operation in (
        "start_research_task",
        "get_research_result",
        "cancel_research_task",
    ):
        state["tools"].append(
            {
                "name": DIRECT_PREFIX + operation,
                "description": operation,
                "input_schema": {"type": "object"},
            }
        )
    calls = []
    task_state = ["RUNNING", "RUNNING", "SUCCEEDED"]

    def invoke(action, value):
        calls.append((action, value))
        if action == "open":
            return state
        if action == "close":
            return {"open": False, "closed": True}
        result = direct_result(value, reconcile=task_state[0] != "SUCCEEDED")
        result["task"] = {
            "task_id": {"value": TASK_ID},
            "state": task_state.pop(0),
        }
        return {"ok": True, "result": result}

    session = DirectToolSession.open(invoke, campaign_identity=CAMPAIGN_A)
    started = asyncio.run(
        session.call(
            DIRECT_PREFIX + "start_research_task",
            {"recipe_json": '{"source":{"kind":"graph"}}'},
            "epoch-1-direct-tool-021",
        )
    )
    assert started["task_observation_pending"] is True
    assert started["requires_reconciliation"] is False
    assert started["result"]["requires_reconciliation"] is True
    running = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_research_result",
            {"task_id": TASK_ID},
            "epoch-1-direct-tool-022",
        )
    )
    assert running["task_observation_pending"] is True
    finished = asyncio.run(
        session.call(
            DIRECT_PREFIX + "get_research_result",
            {"task_id": TASK_ID},
            "epoch-1-direct-tool-023",
        )
    )
    assert finished.get("requires_reconciliation") is not True
    assert session._active_tasks == set()


@pytest.mark.parametrize("bad_state", [[], {}])
def test_malformed_task_state_preserves_uncertain_dispatch(bad_state):
    state = opened()
    state["tools"].append(
        {
            "name": DIRECT_PREFIX + "start_research_task",
            "description": "start",
            "input_schema": {"type": "object"},
        }
    )
    calls = []

    def invoke(action, value):
        calls.append(action)
        if action == "open":
            return state
        result = direct_result(value, reconcile=True)
        result["task"] = {"task_id": {"value": TASK_ID}, "state": bad_state}
        return {"ok": True, "result": result}

    session = DirectToolSession.open(invoke, campaign_identity=CAMPAIGN_A)
    with pytest.raises(UncertainDirectToolDispatch, match="task state"):
        asyncio.run(
            session.call(
                DIRECT_PREFIX + "start_research_task",
                {"recipe_json": "{}"},
                "epoch-1-direct-tool-026",
            )
        )
    assert calls == ["open", "call"]


def test_elapsed_campaign_refuses_new_work_but_allows_observe_and_cancel():
    state = opened()
    for operation in ("get_research_result", "cancel_research_task"):
        state["tools"].append(
            {
                "name": DIRECT_PREFIX + operation,
                "description": operation,
                "input_schema": {"type": "object"},
            }
        )
    calls = []

    def invoke(action, value):
        calls.append((action, value))
        if action == "open":
            return state
        result = direct_result(value)
        result["task"] = {"task_id": {"value": TASK_ID}, "state": "SUCCEEDED"}
        return {"ok": True, "result": result}

    session = DirectToolSession.open(
        invoke, campaign_identity=CAMPAIGN_A, admit_new_work=lambda: False
    )
    refused = asyncio.run(
        session.call(SUBMIT, {"recipe_json": "{}"}, "epoch-1-direct-tool-024")
    )
    assert refused["reason_code"] == "direct_agent_elapsed"
    assert [action for action, _ in calls] == ["open"]
    for operation in ("get_research_result", "cancel_research_task"):
        result = asyncio.run(
            session.call(
                DIRECT_PREFIX + operation,
                {"task_id": TASK_ID},
                "epoch-1-direct-tool-" + operation,
            )
        )
        assert result["ok"] is True
    assert [action for action, _ in calls] == ["open", "call", "call"]


def test_finite_agent_requires_calculable_provider_price(tmp_path, monkeypatch):
    from carbon.agent_campaign.graphite import direct_tool_session
    from scripts.dev.miner_launchpad import runner

    class Unpriced:
        reservation_nano = None

    unpriced = Unpriced()
    monkeypatch.setattr(runner, "setup_selection", lambda _profile: unpriced)
    with pytest.raises(ValueError, match="requires a priced model selection"):
        direct_tool_session._installed_provider(
            {"model_selection": {}, "paths": {"api_key_file": str(tmp_path / "key")}}
        )


def test_owned_task_supervision_refreshes_status_past_tools_idle_window(tmp_path):
    from carbon.agent_campaign.graphite.direct_tool_session import (
        _supervise_active_tasks,
    )
    from carbon.development_session.research_ledger import DIRECT_AGENT, CampaignLedger

    now = [1000.0]
    ledger = CampaignLedger(tmp_path / "direct-agent-clock", clock=lambda: now[0])
    manifest = {
        "schema": DIRECT_AGENT,
        "campaign_id": "clock-test",
        "canonical_root": str(ledger.root.resolve(strict=True)),
        "owner": "alice",
        "agent": "graphite-direct",
        "challenge": {"id": "synthetic-linear-field-2d", "version": "1.0"},
        "direct_development_session": SESSION,
        "profile_digest": CAMPAIGN_A,
        "implementation": "a" * 40,
        "challenge_info_digest": CAMPAIGN_A,
        "interaction_manifest_digest": CAMPAIGN_A,
        "provider": {},
        "ceilings": {
            "provider_attempts": 1,
            "provider_nanodollars": 1,
            "retained_bytes": 100000,
        },
        "retained_bytes_scope": "agent_provider_journal_reservation",
        "elapsed_seconds": 1200,
    }
    campaign_digest = ledger.freeze(manifest)
    ledger.reserve(
        "clock-start", owner="alice", phase="selection", request={}, resources={}
    )
    state = opened()
    state["tools"].append(
        {
            "name": DIRECT_PREFIX + "get_research_result",
            "description": "status",
            "input_schema": {"type": "object"},
        }
    )
    state["tools"].append(
        {
            "name": DIRECT_PREFIX + "cancel_research_task",
            "description": "cancel",
            "input_schema": {"type": "object"},
        }
    )
    calls = []

    def invoke(action, value):
        if action == "open":
            return state
        assert action == "call"
        calls.append(now[0])
        if value["tool"].endswith("cancel_research_task"):
            result = direct_result(value, reconcile=True)
            result["task"] = {
                "task_id": {"value": TASK_ID},
                "state": "CANCEL_REQUESTED",
            }
            return {"ok": True, "result": result}
        result = direct_result(value, reconcile=len(calls) < 5)
        result["task"] = {
            "task_id": {"value": TASK_ID},
            "state": "RUNNING" if len(calls) < 5 else "SUCCEEDED",
        }
        return {"ok": True, "result": result}

    session = DirectToolSession.open(
        invoke, campaign_identity=CAMPAIGN_A, known_tasks={TASK_ID: "RUNNING"}
    )

    async def advance(_seconds):
        now[0] += 210

    observed, expired = asyncio.run(
        _supervise_active_tasks(
            session, ledger, CAMPAIGN_A, campaign_digest, 1200, sleep=advance
        )
    )
    assert observed == {TASK_ID: "SUCCEEDED"} and not expired
    assert calls[-1] - calls[0] > 600
    assert all(later - earlier < 600 for earlier, later in pairwise(calls))
    assert session._active_tasks == set()
    now[0] = 2201
    expired_session = DirectToolSession.open(
        invoke, campaign_identity=CAMPAIGN_A, known_tasks={TASK_ID: "RUNNING"}
    )
    cancelled, expired = asyncio.run(
        _supervise_active_tasks(
            expired_session, ledger, CAMPAIGN_A, campaign_digest, 1200, sleep=advance
        )
    )
    assert expired and cancelled == {}
    assert expired_session._active_tasks == {TASK_ID}

    now[0] = 1000
    long_ledger = CampaignLedger(
        tmp_path / "direct-agent-long-clock", clock=lambda: now[0]
    )
    long_digest = long_ledger.freeze(
        {**manifest, "campaign_id": "long-clock-test", "elapsed_seconds": 30000}
    )
    long_ledger.reserve(
        "long-clock-start", owner="alice", phase="selection", request={}, resources={}
    )

    class ManyPolls:
        def __init__(self):
            self._active_tasks = {TASK_ID}
            self.count = 0

        async def call(self, _operation, _arguments, _identity):
            self.count += 1
            state = "RUNNING" if self.count <= 10001 else "SUCCEEDED"
            if state == "SUCCEEDED":
                self._active_tasks.clear()
            return {
                "ok": True,
                "result": {"reply": {"status": "OK"}, "task": {"state": state}},
            }

    async def no_wait(_seconds):
        pass

    many = ManyPolls()
    observed, expired = asyncio.run(
        _supervise_active_tasks(
            many, long_ledger, CAMPAIGN_A, long_digest, 30000, sleep=no_wait
        )
    )
    assert many.count == 10002
    assert observed == {TASK_ID: "SUCCEEDED"} and not expired


@pytest.mark.parametrize(
    "outcome",
    [
        "timeout",
        "malformed",
        "protected",
        "operational_stop",
        "missing_result",
        "null_result",
        "empty_result",
        "wrong_reconciliation_type",
    ],
)
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
        if outcome == "operational_stop":
            return {"ok": False, "error": "DIRECT_OPERATIONAL_STOP"}
        if outcome == "missing_result":
            return {"ok": True}
        if outcome == "null_result":
            return {"ok": True, "result": None}
        if outcome == "empty_result":
            return {"ok": True, "result": {}}
        if outcome == "wrong_reconciliation_type":
            result = direct_result(value)
            result["requires_reconciliation"] = "false"
            return {"ok": True, "result": result}
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


def test_finite_direct_campaign_prepares_then_calls_existing_loop(
    tmp_path, monkeypatch
):
    from carbon.agent_campaign.graphite import direct_tool_session
    from carbon.agent_campaign.graphite.direct_tool_session import (
        _new_work_within_deadline,
    )
    from carbon.development_session import research_loop
    from carbon.development_session.research_agent_policy import GRAPHITE_MINER
    from carbon.development_session.research_ledger import DIRECT_AGENT
    from scripts.dev.miner_launchpad import tool_door

    campaigns_root = tmp_path / "campaigns"
    campaigns_root.mkdir()
    profile = {
        "principal": "alice",
        "campaigns_root": str(campaigns_root),
        "accepted_revision": "a" * 40,
        "paths": {"api_key_file": str(tmp_path / "provider-key")},
    }

    class Host:
        def configured(self):
            return profile

    host = Host()
    calls = []
    challenge = {"id": "synthetic-linear-field-2d", "version": "1.0"}
    current_challenge = [challenge]

    def public_route(given_host, campaign, action, value):
        assert given_host is host and campaign == SESSION
        calls.append((action, value))
        if action == "open":
            state = opened()
            state["challenge"] = current_challenge[0]
            for operation in (
                "get_interaction_manifest",
                "start_research_task",
                "get_research_result",
                "cancel_research_task",
            ):
                state["tools"].append(
                    {
                        "name": DIRECT_PREFIX + operation,
                        "description": operation,
                        "input_schema": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                            "additionalProperties": False,
                        },
                    }
                )
            return state
        if action == "call":
            result = direct_result(value)
            if value["tool"].endswith("start_research_task"):
                result["task"] = {"task_id": {"value": TASK_ID}, "state": "RUNNING"}
                result["requires_reconciliation"] = True
                result["reply"]["result"] = {
                    "created": True,
                    "task": result["task"],
                }
                return {"ok": True, "result": result}
            if value["tool"].endswith("get_research_result"):
                result["task"] = {
                    "task_id": {"value": TASK_ID},
                    "state": "SUCCEEDED",
                }
                result["reply"]["result"] = {"task": result["task"]}
                return {"ok": True, "result": result}
            result["reply"]["result"] = (
                {
                    "challenge_key": challenge,
                    "public_train_digest": "sha256:" + "1" * 64,
                }
                if value["tool"].endswith("get_challenge_info")
                else {
                    "supported_operations": [
                        "get_challenge_info",
                        "get_interaction_manifest",
                    ]
                }
            )
            return {"ok": True, "result": result}
        assert action == "close" and set(value) == {"exclusive_token"}
        return {"open": False, "closed": True}

    monkeypatch.setattr(tool_door, "route", public_route)
    root = campaigns_root / "direct-agent-first"
    ledger = asyncio.run(
        prepare_direct_agent_campaign(
            host,
            root,
            provider_attempts=5,
            provider_nanodollars=1_000_000_000_000,
            retained_bytes=100_000_000,
            elapsed_seconds=600,
        )
    )
    with ledger.db() as db:
        manifest = json.loads(
            db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()[0]
        )
    assert manifest["schema"] == DIRECT_AGENT
    assert manifest["challenge"] == challenge
    assert manifest["owner"] == "alice"
    assert manifest["canonical_root"] == str(ledger.root.resolve(strict=True))
    copied_root = campaigns_root / "direct-agent-copied"
    shutil.copytree(ledger.root, copied_root)
    from carbon.development_session.research_ledger import CampaignLedger

    copied = CampaignLedger(copied_root)
    calls_before_copy_attempt = len(calls)
    with pytest.raises(ValueError, match="campaign differs"):
        asyncio.run(run_direct_epoch(host, copied, epoch=1, max_provider_calls=1))
    assert len(calls) == calls_before_copy_attempt
    assert manifest["ceilings"]["provider_attempts"] == 5
    assert manifest["retained_bytes_scope"] == "agent_provider_journal_reservation"
    assert set(manifest).isdisjoint(
        {"objective", "sampling", "control", "selection", "replica_policy"}
    )
    observed = {}
    real_run_epoch = research_loop.run_epoch
    monkeypatch.setattr(direct_tool_session, "_KEEPALIVE_SECONDS", 0.01)

    async def fake_epoch(*args, **kwargs):
        await asyncio.sleep(0.035)
        observed.update(kwargs)
        assert args == (ledger,)
        return {"status": "STOPPED"}

    monkeypatch.setattr(research_loop, "run_epoch", fake_epoch)
    result = asyncio.run(run_direct_epoch(host, ledger, epoch=1, max_provider_calls=1))
    assert result == {"status": "STOPPED"}
    assert observed["owner"] == "alice"
    assert observed["agent_policy"] == GRAPHITE_MINER
    assert observed["stage"] == "direct"
    assert observed["limits"]["calls_per_epoch"] == 1
    assert (
        observed["initial_observation"]["retained_bytes_scope"]
        == "agent_provider_journal_reservation"
    )
    assert "Practice may use your own data" in observed["instructions"]
    assert "generate with the provided solver" in observed["instructions"]
    assert (
        "Independent reconstruction and evaluation use the Challenge-owned fixed TRAIN"
        in observed["instructions"]
    )
    assert observed["sdk"].challenge == challenge
    assert {tool["name"] for tool in observed["tools"]} >= {
        DIRECT_PREFIX + "get_challenge_info",
        DIRECT_PREFIX + "get_interaction_manifest",
        SUBMIT,
    }
    assert [action for action, _ in calls].count("close") == 2
    assert [action for action, _ in calls].count("open") >= 3
    monkeypatch.setattr(research_loop, "run_epoch", real_run_epoch)

    def stop_transport(request):
        return {
            "model": request["model"],
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "stop-direct-agent",
                    "name": "carbon_autoresearch_stop",
                    "arguments": "{}",
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

    stopped = asyncio.run(
        run_direct_epoch(
            host, ledger, epoch=1, max_provider_calls=1, transport=stop_transport
        )
    )
    assert stopped["status"] == "STOPPED"
    assert ledger.status(owner="alice")["used"]["provider_attempts"] == 1, stopped
    assert [action for action, _ in calls].count("close") == 3
    clock = [ledger.status(owner="alice")["started_unix"] + 599]
    ledger.clock = lambda: clock[0]
    assert _new_work_within_deadline(
        ledger, stopped["accounting"]["campaign_digest"], 600
    )
    clock[0] += 1
    assert not _new_work_within_deadline(
        ledger, stopped["accounting"]["campaign_digest"], 600
    )
    current_challenge[0] = {"id": "changed", "version": "1.0"}
    with pytest.raises(ValueError, match="Challenge binding changed"):
        asyncio.run(run_direct_epoch(host, ledger, epoch=2, max_provider_calls=1))
    assert [action for action, _ in calls].count("close") == 4
    current_challenge[0] = challenge
    ledger.clock = time.time
    turn_names = [
        DIRECT_PREFIX + "start_research_task",
        DIRECT_PREFIX + "get_research_result",
        "carbon_autoresearch_stop",
    ]

    def task_transport(request):
        name = turn_names.pop(0)
        arguments = (
            {"recipe_json": '{"source":{"kind":"graph"}}'}
            if name.endswith("start_research_task")
            else {"task_id": TASK_ID} if name.endswith("get_research_result") else {}
        )
        return {
            "model": request["model"],
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "agent-turn-" + str(len(turn_names)),
                    "name": name,
                    "arguments": json.dumps(arguments),
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

    task_outcome = asyncio.run(
        run_direct_epoch(
            host, ledger, epoch=2, max_provider_calls=3, transport=task_transport
        )
    )
    assert task_outcome["status"] == "STOPPED"
    assert not turn_names
    assert ledger.status(owner="alice")["used"]["provider_attempts"] == 4
    assert [action for action, _ in calls].count("close") == 5
    with pytest.raises(ValueError, match="provider cap differs"):
        asyncio.run(run_direct_epoch(host, ledger, epoch=1, max_provider_calls=6))
    profile["principal"] = "mallory"
    with pytest.raises(ValueError, match="campaign differs"):
        asyncio.run(run_direct_epoch(host, ledger, epoch=1, max_provider_calls=1))
    profile["principal"] = "alice"
    with pytest.raises(ValueError, match="campaign freeze conflict"):
        asyncio.run(
            prepare_direct_agent_campaign(
                host,
                root,
                provider_attempts=1,
                provider_nanodollars=1_000_000_000_000,
                retained_bytes=100_000_000,
                elapsed_seconds=600,
            )
        )

    async def certain_failure(*_args, **_kwargs):
        raise ValueError("plan replay conflict")

    monkeypatch.setattr(research_loop, "run_epoch", certain_failure)
    closed = [action for action, _ in calls].count("close")
    with pytest.raises(ValueError, match="plan replay conflict"):
        asyncio.run(run_direct_epoch(host, ledger, epoch=2, max_provider_calls=1))
    assert [action for action, _ in calls].count("close") == closed + 1

    async def uncertain_failure(*_args, **_kwargs):
        raise UncertainDirectToolDispatch("tool result unknown")

    monkeypatch.setattr(research_loop, "run_epoch", uncertain_failure)
    closed = [action for action, _ in calls].count("close")
    with pytest.raises(UncertainDirectToolDispatch, match="tool result unknown"):
        asyncio.run(run_direct_epoch(host, ledger, epoch=2, max_provider_calls=1))
    assert [action for action, _ in calls].count("close") == closed
    stranded_token = [
        value["exclusive_token"] for action, value in calls if action == "open"
    ][-1]

    async def recovered_epoch(*_args, **_kwargs):
        return {"status": "STOPPED"}

    monkeypatch.setattr(research_loop, "run_epoch", recovered_epoch)
    assert (
        asyncio.run(run_direct_epoch(host, ledger, epoch=2, max_provider_calls=1))[
            "status"
        ]
        == "STOPPED"
    )
    assert [value["exclusive_token"] for action, value in calls if action == "open"][
        -1
    ] == stranded_token
    assert [value["exclusive_token"] for action, value in calls if action == "close"][
        -1
    ] == stranded_token
    with pytest.raises(ValueError, match="owner differs"):
        ledger.reserve(
            "wrong-owner-test",
            owner="mallory",
            phase="research",
            request={},
            resources={},
        )


def test_direct_agent_campaign_rejects_unprepared_or_outside_root(tmp_path):
    class Host:
        def configured(self):
            return {
                "principal": "alice",
                "campaigns_root": str(tmp_path),
                "accepted_revision": "a" * 40,
                "paths": {"api_key_file": str(tmp_path / "provider-key")},
            }

    with pytest.raises(ValueError, match="campaigns root"):
        asyncio.run(
            prepare_direct_agent_campaign(
                Host(),
                Path(tmp_path).parent / "direct-agent-outside",
                provider_attempts=1,
                provider_nanodollars=1,
                retained_bytes=1,
                elapsed_seconds=1,
            )
        )


def test_running_task_survives_call_cap_and_restarts_from_verified_journal(
    tmp_path, monkeypatch
):
    from carbon.agent_campaign.graphite.direct_tool_session import _journaled_tasks
    from carbon.development_session.profile import canonical, digest
    from scripts.dev.miner_launchpad import tool_door

    campaigns_root = tmp_path / "campaigns"
    campaigns_root.mkdir()
    profile = {
        "principal": "alice",
        "campaigns_root": str(campaigns_root),
        "accepted_revision": "a" * 40,
        "paths": {"api_key_file": str(tmp_path / "provider-key")},
    }

    class Host:
        def configured(self):
            return profile

    host = Host()
    calls = []

    def public_route(given_host, campaign, action, value):
        assert given_host is host and campaign == SESSION
        calls.append((action, value))
        if action == "open":
            state = opened()
            for operation in (
                "get_interaction_manifest",
                "start_research_task",
                "get_research_result",
            ):
                state["tools"].append(
                    {
                        "name": DIRECT_PREFIX + operation,
                        "description": operation,
                        "input_schema": {"type": "object"},
                    }
                )
            return state
        if action == "close":
            return {"open": False, "closed": True}
        assert action == "call"
        result = direct_result(value)
        name = value["tool"]
        if name.endswith("start_research_task"):
            result["task"] = {"task_id": {"value": TASK_ID}, "state": "RUNNING"}
            result["requires_reconciliation"] = True
        elif name.endswith("get_research_result"):
            result["task"] = {"task_id": {"value": TASK_ID}, "state": "SUCCEEDED"}
        else:
            result["reply"]["result"] = {"public_material": name}
        return {"ok": True, "result": result}

    monkeypatch.setattr(tool_door, "route", public_route)
    ledger = asyncio.run(
        prepare_direct_agent_campaign(
            host,
            campaigns_root / "direct-agent-restart",
            provider_attempts=3,
            provider_nanodollars=1_000_000_000_000,
            retained_bytes=100_000_000,
            elapsed_seconds=600,
        )
    )
    (ledger.root / "epoch-1" / "direct").mkdir(parents=True)
    with ledger.db() as db:
        campaign = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    identity = digest(canonical(["alice", campaign["campaign_id"]]))
    assert _journaled_tasks(ledger, identity) == {}

    def transport(names):
        def reply(request):
            name = names.pop(0)
            arguments = (
                {"recipe_json": '{"source":{"kind":"graph"}}'}
                if name.endswith("start_research_task")
                else (
                    {"task_id": TASK_ID} if name.endswith("get_research_result") else {}
                )
            )
            return {
                "model": request["model"],
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "task-turn-" + str(len(names)),
                        "name": name,
                        "arguments": json.dumps(arguments),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }

        return reply

    first = asyncio.run(
        run_direct_epoch(
            host,
            ledger,
            epoch=1,
            max_provider_calls=1,
            transport=transport([DIRECT_PREFIX + "start_research_task"]),
        )
    )
    assert first["status"] == "TASK_OBSERVED"
    assert first["task_ids"] == [TASK_ID]
    assert first["task_states"] == {TASK_ID: "SUCCEEDED"}
    assert [action for action, _ in calls].count("close") == 2
    # The recovered identity comes from the frozen campaign, not the model.
    assert _journaled_tasks(ledger, identity) == {TASK_ID: "SUCCEEDED"}
    replay = asyncio.run(
        run_direct_epoch(
            host,
            ledger,
            epoch=1,
            max_provider_calls=1,
            transport=lambda _request: pytest.fail("replay sent another model call"),
        )
    )
    assert replay["status"] == "STOPPED"
    assert [action for action, _ in calls].count("close") == 3

    second = asyncio.run(
        run_direct_epoch(
            host,
            ledger,
            epoch=2,
            max_provider_calls=2,
            transport=transport(
                [DIRECT_PREFIX + "get_research_result", "carbon_autoresearch_stop"]
            ),
        )
    )
    assert second["status"] == "STOPPED"
    assert [action for action, _ in calls].count("close") == 4
    plan = json.loads((ledger.root / "epoch-2" / "direct" / "plan.json").read_bytes())
    assert plan["initial_observation"]["known_tasks"] == [
        {"task_id": TASK_ID, "state": "SUCCEEDED"}
    ]
    assert _journaled_tasks(ledger, identity) == {TASK_ID: "SUCCEEDED"}
    final_ledger = asyncio.run(
        prepare_direct_agent_campaign(
            host,
            campaigns_root / "direct-agent-final-epoch",
            provider_attempts=1,
            provider_nanodollars=1_000_000_000_000,
            retained_bytes=100_000_000,
            elapsed_seconds=600,
        )
    )
    final = asyncio.run(
        run_direct_epoch(
            host,
            final_ledger,
            epoch=2,
            max_provider_calls=1,
            transport=transport([DIRECT_PREFIX + "start_research_task"]),
        )
    )
    assert final["status"] == "TASK_OBSERVED"
    assert final["task_states"] == {TASK_ID: "SUCCEEDED"}
    assert final_ledger.status(owner="alice")["used"]["provider_attempts"] == 1
    local_stop = (
        ledger.root / "epoch-2" / "direct" / "epoch-2-direct-tool-999-intent.json"
    )
    local_stop.write_bytes(
        canonical(
            {
                "name": "carbon_autoresearch_stop",
                "arguments": {},
                "call_id": "interrupted-local-stop",
            }
        )
    )
    unoffered = (
        ledger.root / "epoch-2" / "direct" / "epoch-2-direct-tool-998-intent.json"
    )
    unoffered.write_bytes(
        canonical(
            {
                "name": DIRECT_PREFIX + "not_offered",
                "arguments": {},
                "call_id": "interrupted-unoffered-direct",
            }
        )
    )
    malformed = (
        ledger.root / "epoch-2" / "direct" / "epoch-2-direct-tool-997-intent.json"
    )
    malformed.write_bytes(
        canonical(
            {
                "name": DIRECT_PREFIX + "start_research_task",
                "arguments": None,
                "call_id": "interrupted-malformed-direct",
            }
        )
    )
    locally_rejected = [
        (DIRECT_PREFIX + "start_research_task", {"recipe_json": "not JSON"}),
        (
            DIRECT_PREFIX + "start_research_task",
            {"recipe_json": "{}", "operation_id": "model-owned"},
        ),
        (DIRECT_PREFIX + "submit_construction", {"wrong_key": "{}"}),
    ]
    for number, (name, arguments) in enumerate(locally_rejected, start=993):
        (
            ledger.root
            / "epoch-2"
            / "direct"
            / f"epoch-2-direct-tool-{number}-intent.json"
        ).write_bytes(
            canonical(
                {
                    "name": name,
                    "arguments": arguments,
                    "call_id": f"interrupted-local-refusal-{number}",
                }
            )
        )
    assert _journaled_tasks(ledger, identity) == {TASK_ID: "SUCCEEDED"}
    dispatched = (
        ledger.root / "epoch-2" / "direct" / "epoch-2-direct-tool-996-intent.json"
    )
    dispatched.write_bytes(
        canonical(
            {
                "name": DIRECT_PREFIX + "start_research_task",
                "arguments": {"recipe_json": "{}"},
                "call_id": "interrupted-external-direct",
            }
        )
    )
    with pytest.raises(UncertainDirectToolDispatch, match="intent requires"):
        _journaled_tasks(ledger, identity)
    dispatched.unlink()
    plan["initial_observation"]["known_tasks"] = [
        {"task_id": "rtsk_" + "b" * 64, "state": "RUNNING"}
    ]
    plan_path = ledger.root / "epoch-2" / "direct" / "plan.json"
    plan_path.write_bytes(canonical(plan))
    with pytest.raises(ValueError, match="prior task observation differs"):
        asyncio.run(run_direct_epoch(host, ledger, epoch=2, max_provider_calls=2))
    result_path = (
        ledger.root / "epoch-1" / "direct" / "epoch-1-direct-tool-000-result.json"
    )
    original_result = result_path.read_bytes()
    altered = json.loads(result_path.read_bytes())
    altered["result"]["operation_id"] = "graphite-direct-" + "0" * 64
    result_path.write_bytes(canonical(altered))
    with pytest.raises(ValueError, match="journal result binding differs"):
        _journaled_tasks(ledger, identity)
    # A valid prior task can still be active when a later plan is corrupt.
    # Preflight must reject before opening a session whose close cancels work.
    altered = json.loads(original_result)
    altered["result"]["task"]["state"] = "RUNNING"
    result_path.write_bytes(canonical(altered))
    (ledger.root / "direct-task-observations" / (TASK_ID + ".json")).unlink()
    plan_path.write_bytes(b"corrupt prior plan")
    opened_before = [action for action, _ in calls].count("open")
    closed_before = [action for action, _ in calls].count("close")
    with pytest.raises(ValueError):
        asyncio.run(run_direct_epoch(host, ledger, epoch=2, max_provider_calls=2))
    assert [action for action, _ in calls].count("open") == opened_before
    assert [action for action, _ in calls].count("close") == closed_before


def test_interrupted_owned_task_reopens_observes_and_closes_with_retained_lease(
    tmp_path,
):
    from carbon.agent_campaign.graphite.direct_tool_session import _campaign_lease_token
    from carbon.development_session.research_ledger import CampaignLedger

    ledger = CampaignLedger(tmp_path / "direct-agent-lease-recovery")
    held = [None]
    malformed_open = [False]
    calls = []

    def owned_route(action, value):
        token = value["exclusive_token"]
        calls.append((action, token))
        if action == "open":
            if held[0] is None:
                held[0] = token
            assert held[0] == token
            state = opened()
            for operation in ("start_research_task", "get_research_result"):
                state["tools"].append(
                    {
                        "name": DIRECT_PREFIX + operation,
                        "description": operation,
                        "input_schema": {"type": "object"},
                    }
                )
            if malformed_open[0]:
                malformed_open[0] = False
                state["tools"][0]["name"] = DIRECT_PREFIX + "unoffered"
            return state
        assert held[0] == token
        if action == "call":
            result = direct_result(value)
            state = (
                "RUNNING"
                if value["tool"].endswith("start_research_task")
                else "SUCCEEDED"
            )
            result["task"] = {"task_id": {"value": TASK_ID}, "state": state}
            result["requires_reconciliation"] = state == "RUNNING"
            return {"ok": True, "result": result}
        assert action == "close"
        held[0] = None
        return {"open": False, "closed": True}

    token = _campaign_lease_token(ledger, CAMPAIGN_A)
    try:
        first = DirectToolSession.open(
            owned_route, campaign_identity=CAMPAIGN_A, lease_token=token
        )
        started = asyncio.run(
            first.call(
                DIRECT_PREFIX + "start_research_task",
                {"recipe_json": "{}"},
                "epoch-1-direct-tool-000",
            )
        )
        assert started["task_observation_pending"] is True
        assert first._active_tasks == {TASK_ID}
        # The first owner is interrupted without closing its running task.
        assert _campaign_lease_token(ledger, CAMPAIGN_A) == token
        malformed_open[0] = True
        with pytest.raises(ValueError, match="malformed direct tool"):
            DirectToolSession.open(
                owned_route,
                campaign_identity=CAMPAIGN_A,
                known_tasks={TASK_ID: "RUNNING"},
                lease_token=_campaign_lease_token(ledger, CAMPAIGN_A),
            )
        assert held[0] == token and not any(action == "close" for action, _ in calls)
        recovered = DirectToolSession.open(
            owned_route,
            campaign_identity=CAMPAIGN_A,
            known_tasks={TASK_ID: "RUNNING"},
            lease_token=_campaign_lease_token(ledger, CAMPAIGN_A),
        )
        result = asyncio.run(
            recovered.call(
                DIRECT_PREFIX + "get_research_result",
                {"task_id": TASK_ID},
                "epoch-2-direct-tool-000",
            )
        )
        assert result["result"]["task"]["state"] == "SUCCEEDED"
        assert recovered._active_tasks == set()
        recovered.close()
        assert held[0] is None
        assert {seen for _, seen in calls} == {token}
        with pytest.raises(ValueError, match="lease custody differs"):
            _campaign_lease_token(ledger, CAMPAIGN_B)
    finally:
        assert _campaign_lease_token(ledger, CAMPAIGN_A) == token


def test_two_live_epoch_callers_cannot_share_one_tools_lease(tmp_path, monkeypatch):
    from carbon.agent_campaign.graphite import direct_tool_session
    from carbon.development_session.research_ledger import CampaignLedger
    from scripts.dev.miner_launchpad.controller import LockHeld

    ledger = CampaignLedger(tmp_path / "direct-agent-single-owner")
    entered = asyncio.Event()
    release = asyncio.Event()
    runs = []

    async def owned(_host, _ledger, *, epoch, max_provider_calls, transport):
        runs.append((epoch, max_provider_calls, transport))
        entered.set()
        await release.wait()
        return {"status": "STOPPED"}

    monkeypatch.setattr(direct_tool_session, "_run_direct_epoch_owned", owned)

    async def competing():
        first = asyncio.create_task(
            run_direct_epoch(None, ledger, epoch=1, max_provider_calls=1)
        )
        await entered.wait()
        with pytest.raises(LockHeld, match="Another launcher owns"):
            await run_direct_epoch(None, ledger, epoch=2, max_provider_calls=1)
        assert runs == [(1, 1, None)]  # No second attachment or task close.
        release.set()
        assert (await first)["status"] == "STOPPED"
        assert (await run_direct_epoch(None, ledger, epoch=2, max_provider_calls=1))[
            "status"
        ] == "STOPPED"
        assert runs == [(1, 1, None), (2, 1, None)]

    asyncio.run(competing())


def test_cancelled_epoch_holds_run_fence_until_threaded_route_settles(
    tmp_path, monkeypatch
):
    import threading

    from carbon.agent_campaign.graphite import direct_tool_session
    from carbon.development_session.research_ledger import CampaignLedger
    from scripts.dev.miner_launchpad.controller import LockHeld

    ledger = CampaignLedger(tmp_path / "direct-agent-cancel-fence")
    route_started = threading.Event()
    release_route = threading.Event()
    completed = []

    def slow_route():
        route_started.set()
        assert release_route.wait(5)
        completed.append("route")

    async def owned(_host, _ledger, *, epoch, max_provider_calls, transport):
        if epoch == 1:
            await asyncio.to_thread(slow_route)
        completed.append(f"epoch-{epoch}")
        return {"status": "STOPPED"}

    monkeypatch.setattr(direct_tool_session, "_run_direct_epoch_owned", owned)

    async def competing():
        first = asyncio.create_task(
            run_direct_epoch(None, ledger, epoch=1, max_provider_calls=1)
        )
        assert await asyncio.to_thread(route_started.wait, 5)
        first.cancel()
        await asyncio.sleep(0)
        assert not first.done()
        with pytest.raises(LockHeld, match="Another launcher owns"):
            await run_direct_epoch(None, ledger, epoch=2, max_provider_calls=1)
        assert completed == []
        release_route.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert completed == ["route", "epoch-1"]
        assert (await run_direct_epoch(None, ledger, epoch=2, max_provider_calls=1))[
            "status"
        ] == "STOPPED"
        assert completed == ["route", "epoch-1", "epoch-2"]

    asyncio.run(competing())

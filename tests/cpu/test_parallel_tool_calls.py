"""A provider that returns several tool calls in one turn (owner decision,
28 September 2026).

Some providers ignore `parallel_tool_calls: false` - deepseek-v4-flash on Engy
did on every sampled turn. A campaign that froze `PARALLEL_CALLS` runs the
first call, answers each other with a journalled refusal that dispatches
nothing and consumes no trial slot, and stops only after three consecutive
such turns. A campaign frozen before the rule keeps the historical meaning:
such a turn stops the epoch, retained.

Deterministic Responses mocks test control flow, never agent evidence.
"""

import asyncio
import json

import pytest
from test_cw1_research_ledger import ledger
from test_cw1_research_loop import response

from carbon.development_session.research_agent_policy import (
    PARALLEL_CALLS,
    PARALLEL_REFUSAL,
)
from carbon.development_session.research_campaign import frozen_parallel_calls
from carbon.development_session.research_loop import run_epoch
from carbon.development_session.research_tools import PREFIX

TOOL = PREFIX + "list_public_material"


def call(identity):
    return {
        "type": "function_call",
        "name": TOOL,
        "call_id": identity,
        "arguments": json.dumps({}),
    }


def text(words="Nothing further in this synthetic control."):
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": words}],
    }


class SDK:
    """Records every tool that is actually dispatched."""

    def __init__(self):
        self.dispatched = []

    async def call(self, name, arguments, identity):
        self.dispatched.append((name, identity))
        return {"status": "OK", "fixture": True}


def scripted(turns):
    """A transport replying with each scripted turn's output in order."""
    requests = []

    def transport(request):
        requests.append(request)
        return response(turns[len(requests) - 1])

    return transport, requests


def epoch(meter, sdk, transport, **extra):
    return asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=sdk,
            credential_file=None,
            initial_observation={"fixture": True},
            transport=transport,
            **extra,
        )
    )


def outputs(request):
    return {
        item["call_id"]: json.loads(item["output"])
        for item in request["input"]
        if item.get("type") == "function_call_output"
    }


def test_without_the_frozen_rule_a_parallel_turn_still_stops(tmp_path):
    """The historical meaning, unchanged: a campaign frozen before the rule
    stops, and the retained turn is not reinterpreted."""
    sdk = SDK()
    transport, _ = scripted([[call("a"), call("b")]])
    with pytest.raises(ValueError, match="parallel tool output prohibited"):
        epoch(ledger(tmp_path), sdk, transport)
    assert sdk.dispatched == []


def test_the_first_call_runs_and_every_other_is_refused(tmp_path):
    meter = ledger(tmp_path)
    sdk = SDK()
    transport, requests = scripted([[call("a"), call("b"), call("c")], [text()]])
    result = epoch(meter, sdk, transport, parallel_calls=PARALLEL_CALLS)
    assert result["status"] == "STOPPED"
    # Only the first call was dispatched.
    assert [identity for _, identity in sdk.dispatched] == ["epoch-1-tool-000"]
    # The next request answers every call: the first with its result, the
    # others with the refusal, so the conversation stays well formed.
    answered = outputs(requests[1])
    assert answered["a"] == {"status": "OK", "fixture": True}
    assert answered["b"] == answered["c"] == PARALLEL_REFUSAL
    # Journalled, and nothing consumed.
    root = next(meter.root.rglob("epoch-1-provider-000-parallel-refusal.json"))
    journal = json.loads(root.read_bytes())
    assert journal["ran"] == "a" and journal["refused"] == ["b", "c"]
    assert journal["consecutive"] == 1 and journal["rule"] == PARALLEL_CALLS
    assert meter.status(owner="alice")["used"]["research_trials"] == 0
    # A replay reproduces the outcome with no provider call and no dispatch.
    assert epoch(meter, sdk, transport, parallel_calls=PARALLEL_CALLS) == result
    assert len(requests) == 2 and len(sdk.dispatched) == 1


def test_three_consecutive_parallel_turns_stop_the_epoch(tmp_path):
    sdk = SDK()
    parallel = [call("x"), call("y")]
    turns = [
        [{**item, "call_id": f"{item['call_id']}{n}"} for item in parallel]
        for n in range(3)
    ]
    transport, requests = scripted(turns)
    result = epoch(ledger(tmp_path), sdk, transport, parallel_calls=PARALLEL_CALLS)
    assert result["status"] == "STOPPED"
    assert "3 consecutive turns" in result["reason"]
    assert result["parallel_calls"] == PARALLEL_CALLS
    # The first two turns ran their first call; the third ran nothing.
    assert len(sdk.dispatched) == 2 and len(requests) == 3


def test_a_single_call_turn_resets_the_count(tmp_path):
    sdk = SDK()
    transport, requests = scripted(
        [
            [call("p1"), call("q1")],
            [call("p2"), call("q2")],
            [call("single")],
            [call("p3"), call("q3")],
            [call("p4"), call("q4")],
            [text()],
        ]
    )
    result = epoch(ledger(tmp_path), sdk, transport, parallel_calls=PARALLEL_CALLS)
    # Two, then a reset, then two: never three in a row.
    assert result["status"] == "STOPPED" and "consecutive" not in result["reason"]
    assert len(requests) == 6 and len(sdk.dispatched) == 5


def test_the_rule_is_frozen_never_inferred(tmp_path):
    meter = ledger(tmp_path)
    transport, _ = scripted([[text()]])
    epoch(meter, SDK(), transport, parallel_calls=PARALLEL_CALLS)
    plan = json.loads(next(meter.root.rglob("plan.json")).read_bytes())
    assert plan["parallel_calls"] == PARALLEL_CALLS
    # A plan made without the rule does not name one.
    other = ledger(tmp_path / "historical")
    transport, _ = scripted([[text()]])
    epoch(other, SDK(), transport)
    assert "parallel_calls" not in json.loads(
        next(other.root.rglob("plan.json")).read_bytes()
    )
    # Frozen in a campaign's provider plan; absent from an older one.
    assert frozen_parallel_calls({"provider": {"parallel_calls": PARALLEL_CALLS}}) == (
        PARALLEL_CALLS
    )
    assert frozen_parallel_calls({"provider": {"agent": "autonomous"}}) is None
    assert frozen_parallel_calls({"provider": "engineering-fixture-only"}) is None
    with pytest.raises(ValueError, match="unknown parallel tool call rule"):
        epoch(
            ledger(tmp_path / "unknown"),
            SDK(),
            scripted([[text()]])[0],
            parallel_calls={**PARALLEL_CALLS, "consecutive_limit": 99},
        )


def test_a_new_battery_plan_freezes_the_rule():
    from carbon.battery.campaign import provider_plan

    plan = provider_plan(
        "autonomous",
        {"ceilings": {"provider_attempts": 10, "provider_nanodollars": 10**9}},
    )
    assert plan["parallel_calls"] == PARALLEL_CALLS

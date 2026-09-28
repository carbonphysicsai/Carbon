"""What each research tool call actually consumes, measured on a real ledger.

The metering evidence for the battery agent campaign's step zero
(docs/development/BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2.md). These pin the
cost facts an agent's budget depends on, so a change to what is charged fails
here rather than silently changing an experiment's economics. The charging
decision lives in `ResearchMinerTools.call`; only the downstream research
service is replaced, never the ledger or the charge.
"""

from __future__ import annotations

import asyncio

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session.research_tools import PREFIX, ResearchMinerTools

START = PREFIX + "start_research_task"
WORKSPACE_ACTIONS = (
    "public_material",
    "inventory",
    "read_file",
    "write_file",
    "notebook",
    "capability_request",
    "check_design",
    "roadmap",
)


def tools(tmp_path, service_reply=None):
    meter = ledger(tmp_path)
    value = ResearchMinerTools(
        connection=None, wrapper=None, composition=None, ledger=meter, owner="alice"
    )
    if service_reply is not None:

        async def reached_service(name, args, identity, *, transport_request_id=None):
            return service_reply

        value._call = reached_service
    return value, meter


def trials(meter):
    return meter.status(owner="alice")["used"].get("research_trials", 0)


def start(kind, action=None):
    return {
        "kind": kind,
        "action": action,
        "strategy_json": None,
        "arguments_json": "{}",
        "hypothesis": "metering test",
        "expected_effect": "none",
    }


@pytest.mark.parametrize("action", WORKSPACE_ACTIONS)
def test_workspace_actions_charge_no_research_trial(tmp_path, action):
    value, meter = tools(tmp_path, service_reply={"status": "OK"})
    asyncio.run(value.call(START, start("workspace", action), "id-" + action))
    assert trials(meter) == 0


@pytest.mark.parametrize(
    ("kind", "action"), [("practice", None), ("workspace", "run_python")]
)
def test_practice_and_run_python_each_charge_one_trial(tmp_path, kind, action):
    """The specimen for the zero above: the same meter does count a trial."""
    value, meter = tools(tmp_path, service_reply={"status": "OK"})
    asyncio.run(value.call(START, start(kind, action), "id-numerical"))
    assert trials(meter) == 1


def test_a_malformed_practice_call_is_rejected_and_still_charged(tmp_path):
    """The trial is taken before the arguments are validated: a practice call
    missing its fields starts nothing and still costs a trial."""
    value, meter = tools(tmp_path)
    malformed = {"kind": "practice"}
    result = asyncio.run(value.call(START, malformed, "id-malformed"))
    assert result["status"] == "REJECTED_BEFORE_DISPATCH"
    assert "consumed the applicable proposal counter" in result["detail"]
    assert trials(meter) == 1

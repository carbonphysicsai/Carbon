"""What each research tool call actually consumes, measured on a real ledger.

The metering evidence for the battery agent campaign's step zero
(docs/development/BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2.md). These pin the
cost facts an agent's budget depends on, so a change to what is charged fails
here rather than silently changing an experiment's economics.

A research-trial slot is charged by the executor that starts a task, and only
then (OWNER-BATTERY-V2-DISCLOSURE-01, change 9): `ResearchMinerTools.call`
charges nothing itself. Only the downstream research service or the sandbox
runner is replaced, never the ledger or the charge.
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
def test_the_call_itself_charges_no_trial(tmp_path, kind, action):
    """The request reaches the service, but no executor starts a task here, so
    nothing is charged: the call is not where a trial is taken."""
    value, meter = tools(tmp_path, service_reply={"status": "OK"})
    asyncio.run(value.call(START, start(kind, action), "id-numerical"))
    assert trials(meter) == 0


def test_starting_run_python_charges_one_trial(tmp_path, monkeypatch):
    """The specimen for the zeros here: the run_python executor asks for one
    trial when it starts, and the same meter counts it. Only the sandbox
    runner is replaced; it reserves exactly what the executor hands it."""
    from carbon.development_session import research_carrier
    from carbon.development_session.research_image import ResearchImageIdentity

    meter = ledger(tmp_path)

    def runner(ledger, *, owner, identity, extra_resources, **kwargs):
        ledger.reserve(
            identity,
            owner=owner,
            phase="research",
            request={"source": kwargs["source"]},
            resources=extra_resources,
        )
        return {"operation": identity}

    monkeypatch.setattr(research_carrier, "_run", runner)
    image = ResearchImageIdentity(
        "sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64
    )
    research_carrier.run_script(
        meter,
        owner="alice",
        identity="id-started",
        source="pass",
        files={},
        image=image,
    )
    assert trials(meter) == 1


def test_a_malformed_practice_call_is_rejected_and_charges_nothing(tmp_path):
    """A practice call missing its fields starts nothing and costs no trial
    (change 9; tier 2 lost 4 of 8 slots this way before it)."""
    value, meter = tools(tmp_path)
    malformed = {"kind": "practice"}
    result = asyncio.run(value.call(START, malformed, "id-malformed"))
    assert result["status"] == "REJECTED_BEFORE_DISPATCH"
    assert "no research-trial slot was charged" in result["detail"]
    assert trials(meter) == 0

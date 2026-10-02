"""A Graphite Constructor session on battery's real research path
(CHALLENGE-PROTOCOL-04 slice 3).

Scripted model, so no live inference, key or spend. Everything else is the
battery service test's own campaign: the signed gateway, the durable task
provider, the campaign ledger, recipe compilation, and a real practice trial
on public TRAIN and PRACTICE. The practice runner is the subprocess stand-in
for the Docker carrier, reported as `SUBPROCESS_TEST_ONLY_NOT_ISOLATED`.
This is interoperability evidence, not scientific or security qualification.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPOSITORY),
    str(REPOSITORY / "tests" / "cpu"),
    str(REPOSITORY / "tests" / "service"),
]

from graphite_fixtures import brief, provider
from test_battery_mcp_research import KNN, adapter_for, battery_campaign

from carbon.agent_campaign.graphite import ScriptedModel
from carbon.agent_campaign.graphite import stage as stages
from carbon.agent_campaign.graphite.miner_path import (
    MinerPathRefused,
    check_campaign,
)
from carbon.agent_campaign.graphite.model import text, tool
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import TaskSpec
from carbon.development_session.research_loop import SELECT
from carbon.development_session.research_tools import PREFIX


def _practice(recipe):
    return tool(
        PREFIX + "start_research_task",
        {
            "kind": "practice",
            "strategy_json": json.dumps(recipe),
            "action": None,
            "arguments_json": None,
            "hypothesis": "neighbours interpolate the smooth map",
            "expected_effect": "eligible on public PRACTICE",
        },
    )


def test_graphite_drives_only_a_battery_campaign_without_its_own_agent():
    battery = {"challenge": {"id": KNN["challenge_id"]}, "agent": "none"}
    assert check_campaign(battery) is battery
    with pytest.raises(MinerPathRefused, match="own_agent"):
        check_campaign({**battery, "agent": "autonomous"})
    with pytest.raises(MinerPathRefused, match="not_a_battery"):
        check_campaign({**battery, "challenge": {"id": "burgers"}})


def test_a_constructor_session_practices_and_selects_through_the_battery_path(
    tmp_path, monkeypatch
):
    (tmp_path / "battery").mkdir()
    path, ledger, owner, connection, manifest = battery_campaign(
        tmp_path / "battery", monkeypatch, agent="none"
    )
    check_campaign(manifest)
    composition, _wrapper, adapter = adapter_for(path, ledger, owner, connection)
    script = [
        tool(PREFIX + "get_challenge_info", {}),
        _practice(KNN),
        tool(
            SELECT,
            {
                "strategy_json": json.dumps(KNN),
                "reason": "practiced and eligible; the only measured recipe",
                "used_feedback": False,
            },
        ),
        text("selected"),
    ]
    model = ScriptedModel(script)
    profile = stages.stage_profile("test_iterate")
    graphite = provider(
        tmp_path / "graphite",
        model,
        miner_tools=adapter.in_process_sdk(),
        stage_profile=profile,
    )
    session_brief = brief(RoleName.CONSTRUCTOR)
    spec = TaskSpec(
        campaign_id="c1",
        role=ROLES[RoleName.CONSTRUCTOR].boundary.value,
        workspace_id="ws-c1",
        credential_ref="cred-c1",
        profile_digest=stages.profile_digest(profile),
        instructions_digest=graphite.register_brief(session_brief),
        max_runtime_s=3600,
    )
    run_id = graphite.start(spec, "k1").provider_run_id

    async def scenario():
        try:
            return await graphite.run_async(run_id)
        finally:
            await adapter.shutdown_tasks()
            composition.tasks.close()

    assert asyncio.run(scenario()) == "succeeded"
    outcome = json.loads(
        (graphite._dir(run_id) / "ledger" / "epoch-1" / "outcome.json").read_bytes()
    )
    assert outcome["status"] == "SELECTED"
    # The practice ran on battery's campaign and was charged there once, under
    # an identity namespaced by Graphite's run.
    used = ledger.status(owner=owner)["used"]
    assert used["research_trials"] == 1
    with ledger.db() as db:
        identities = [row[0] for row in db.execute("SELECT id FROM operations")]
    assert any(i.startswith("task-request-" + run_id + ":") for i in identities)
    events = graphite.events(run_id, 0)
    assert [e["kind"] for e in events].count("trial_dispatched") == 1
    # Graphite never submits: nothing reached the validator from this session.
    assert not list((ledger.root).rglob("*submission*"))

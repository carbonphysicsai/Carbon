"""Graphite phase 3 through the real miner path (GRAPHITE-01).

A Constructor session, driven by a scripted model, whose miner tools reach a
battery campaign through the standard miner adapter (`ResearchToolAdapter`
over `ResearchMinerTools` and the battery composition): the same signed
gateway, research adapter, task provider and campaign ledger an external
research agent reaches. Its proposal goes to Carbon's runner on a scripted
pod account.

Real here: the battery composition, the signed gateway, the research adapter,
the campaign ledger, Carbon's reconstruction gate and frozen-rule scoring.
Fixtures: chain registration and signing (as in the battery MCP tests), the
model, and the pods (SYNTHETIC predictions). `miner_path.attach` composes the
same adapter through `standard_cli.attached_profile`, which needs the accepted
host images this fixture does not build; the adapter class and its calls are
the same.

Engineering evidence, not scientific or security qualification.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPOSITORY / "tests" / "service"),
    str(REPOSITORY / "tests" / "cpu"),
]

from graphite_phase3_fixtures import (
    BASELINE,
    ScriptedPods,
    controller,
    propose,
    provider,
    run_id,
    steps,
    text,
    tool,
    variant,
)
from test_battery_mcp_research import adapter_for, battery_campaign

from carbon.agent_campaign.graphite import miner_path, phase3
from carbon.development_session.research_tools import PREFIX


def test_a_constructor_session_reaches_battery_through_the_miner_path(
    tmp_path, monkeypatch
):
    (tmp_path / "miner").mkdir()
    path, ledger, owner, connection, manifest = battery_campaign(
        tmp_path / "miner", monkeypatch
    )
    miner_path.check_battery_development(manifest)
    composition, _wrapper, adapter = adapter_for(path, ledger, owner, connection)
    better = variant(width=128)
    script = [
        tool(PREFIX + "get_challenge_info", {}),
        tool(PREFIX + "dry_validate", {"strategy_json": json.dumps(BASELINE)}),
        tool(PREFIX + "compile_strategy", {"strategy_json": json.dumps(better)}),
        propose(better),
        text("done"),
    ]
    account = ScriptedPods(steps=steps(1.0, 0.4, 1.0))
    try:
        graphite = provider(
            tmp_path / "graphite",
            script,
            account,
            miner=miner_path.MinerPathTools(adapter, session="servicetest"),
        )
        control = controller(tmp_path / "graphite", graphite)
        try:
            result = phase3.run_session(
                control,
                graphite,
                phase3.session_brief(checkout_commit="1" * 40, budget=graphite.budget),
                1,
            )
        finally:
            control.close()
    finally:
        asyncio.run(adapter.shutdown_tasks())
        composition.tasks.close()
    assert result["provider_state"] == "succeeded"
    outputs = [
        json.loads(item["output"])
        for item in graphite.model.requests[-1]["input"]
        if item.get("type") == "function_call_output"
    ]
    # The three miner operations were answered by the battery service.
    info, validated, compiled, feedback = outputs
    for answer in (info, validated, compiled):
        assert answer["reply"]["status"] == "OK", answer
    assert manifest["challenge"]["id"] in json.dumps(info["reply"])
    assert info["operation"] == "get_challenge_info"
    assert compiled["operation"] == "compile_strategy"
    assert feedback["status"] == "SCORED"
    assert feedback["against_baseline"]["outcome"] == "IMPROVEMENT"
    assert result["delivery"]["clean_rebuild"]["status"] == "REBUILT"
    assert account.alive == {}
    assert graphite.experiment(run_id()).ledger.live() == []

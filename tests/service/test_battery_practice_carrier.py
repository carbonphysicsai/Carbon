"""A battery practice runs in the isolated research carrier and is measured.

Every other battery practice test passes the non-isolated subprocess runner.
This one passes nothing, as every campaign door does, so the practice program
runs through `research_carrier._run` in the trusted worker image, and returns
the exam's own aggregate on public PRACTICE with the backend that ran it.

Requires Docker and CARBON_C03_IMAGE_MANIFEST (the trusted worker image).
"""

from __future__ import annotations

import asyncio
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_battery_mcp_research import SMALL_MLP, battery_campaign, practice

from carbon.development_session.research_control import CampaignControl
from carbon.miner_mcp import standard_cli
from carbon.miner_mcp.standard import ResearchToolAdapter


def _worker_image():
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    if not manifest:
        pytest.skip("needs CARBON_C03_IMAGE_MANIFEST (the trusted worker image)")
    return load_image_identity(Path(manifest))


def test_battery_practice_runs_in_the_isolated_carrier(tmp_path, monkeypatch):
    from test_battery_mcp_research import CAMPAIGN

    from carbon.battery.campaign import compose
    from carbon.development_session.research_tools import ResearchMinerTools

    image = _worker_image()
    path, ledger, owner, connection, _ = battery_campaign(tmp_path, monkeypatch)
    profile = standard_cli.load_profile(path, CAMPAIGN)
    control = CampaignControl(ledger)
    ledger.generation = control.acquire()
    # No runner and no backend: what every campaign door passes.
    composition, wrapper = compose(
        ledger=ledger,
        owner=owner,
        image=image,
        analysis=SimpleNamespace(image_id="unused-by-battery-practice"),
        connection=connection,
    )
    sdk = ResearchMinerTools(
        connection=standard_cli._AdmittedConnection(
            connection, profile, ledger, control
        ),
        wrapper=wrapper,
        composition=composition,
        ledger=ledger,
        owner=owner,
    )
    adapter = ResearchToolAdapter(sdk, principal=owner)

    async def scenario():
        try:
            return await practice(adapter, 1, SMALL_MLP)
        finally:
            await adapter.shutdown_tasks()
            composition.tasks.close()

    payload = asyncio.run(scenario())
    assert payload["terminal_task"]["state"] == "SUCCEEDED", payload
    result = payload["public_result"]["result"]
    assert result["provenance"] == "BATTERY_PUBLIC_PRACTICE"
    assert result["backend"]["kind"] == "ISOLATED_CARRIER", result["backend"]
    score = result["summary"]["score"]
    assert isinstance(score, float) and math.isfinite(score), result["summary"]
    assert math.isfinite(result["fit"]["final_loss"])

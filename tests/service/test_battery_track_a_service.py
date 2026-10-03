"""Battery Track A against the pinned worker image (CI-BATTERY-L0-01 slice 3).

A real battery practice runs through the isolated research carrier in the
trusted worker image, as every campaign door runs it. Validator-private
canaries sit beside it on the host:
- a private root's bytes;
- a hidden batch's references and labels;
- a journal line.

After the run, every byte the run left under the test's directory is scanned.
No canary may appear anywhere outside the files that were planted. A specimen
shows the scan finds a canary when one is copied into a stage-like file, so a
clean result is not vacuous.

Requires Docker and CARBON_C03_IMAGE_MANIFEST (the trusted worker image).
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_battery_mcp_research import SMALL_MLP, battery_campaign, practice

from carbon.battery import track_a
from carbon.development_session.research_control import CampaignControl
from carbon.miner_mcp import standard_cli
from carbon.miner_mcp.standard import ResearchToolAdapter

NEEDLES = (
    track_a.CANARY_ROOT,
    track_a.CANARY_LABEL.encode(),
    repr(track_a.CANARY_VALUE).encode(),
)


def _worker_image():
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    if not manifest:
        pytest.skip("needs CARBON_C03_IMAGE_MANIFEST (the trusted worker image)")
    return load_image_identity(Path(manifest))


def _plant(directory):
    """Validator-private material, as a validator's state directory holds it."""
    directory.mkdir(mode=0o700)
    (directory / "private-root.bin").write_bytes(track_a.CANARY_ROOT)
    (directory / "hidden-batch.json").write_text(json.dumps(track_a._hidden_batch()))
    (directory / "journal.jsonl").write_text(
        json.dumps({"kind": "batch", "label": track_a.CANARY_LABEL}) + "\n"
    )
    return {p.resolve() for p in directory.iterdir()}


def _scan(root, planted):
    """Every file under `root`, except the planted ones, holding a canary."""
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.resolve() in planted:
            continue
        try:
            body = path.read_bytes()
        except OSError:
            continue
        found += [(str(path), n[:12]) for n in NEEDLES if n in body]
    return found


def test_the_scan_finds_a_canary_copied_into_a_stage(tmp_path):
    """Specimen: the scan is not vacuous."""
    planted = _plant(tmp_path / "validator-private")
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "leak.bin").write_bytes(b"prefix" + track_a.CANARY_ROOT)
    assert _scan(tmp_path, planted) == [(str(stage / "leak.bin"), NEEDLES[0][:12])]


def test_a_real_battery_practice_leaves_no_private_byte_behind(tmp_path, monkeypatch):
    from test_battery_mcp_research import CAMPAIGN

    from carbon.battery.campaign import compose
    from carbon.development_session.research_tools import ResearchMinerTools

    image = _worker_image()
    path, ledger, owner, connection, _ = battery_campaign(tmp_path, monkeypatch)
    planted = _plant(tmp_path / "validator-private")
    profile = standard_cli.load_profile(path, CAMPAIGN)
    control = CampaignControl(ledger)
    ledger.generation = control.acquire()
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
    assert result["backend"]["kind"] == "ISOLATED_CARRIER", result["backend"]
    assert math.isfinite(result["summary"]["score"])
    # The run really staged and exported files: something was written beside
    # the planted state, so the scan below covers real worker traffic.
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(written) > len(planted)
    assert _scan(tmp_path, planted) == []

"""Actual Julia miner study over external stdio; explicit local fixture grant.

Requires CARBON_JULIA_WORKER_MANIFEST. Only registration/signing and campaign
authority are synthetic fixtures; domain tasks, ledger, C-04 and Julia execute.
No provider, external chain call, final data or qualification is involved.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_julia_research import prepared
from test_standard_mcp_cli import FixtureSigner, fixture_connection

from carbon.development_session.julia_research import (
    MATERIAL,
    JuliaPublicMaterial,
    PublicJuliaStudy,
)
from carbon.development_session.research_admission import Admission
from carbon.development_session.research_data import PublicReferenceData
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_cli import _requester
from carbon.miner_mcp.standard_server import create_stdio_server
from carbon.reconstruction.worker.docker_runtime import load_image_identity


def serve(root, manifest):
    import carbon.chain.auth
    from carbon.development_session import research_tools
    from scripts.dev.miner_launchpad.controller import owner_lock

    carbon.chain.auth.BittensorMessageSigner = FixtureSigner
    research_tools.BittensorMessageSigner = FixtureSigner
    ledger = CampaignLedger(
        root / "campaign",
        clock=lambda: 1000,
        admission=Admission.load(root / "grant.json"),
        generation=1,
    )
    with ledger.db() as db:
        owner = json.loads(
            db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()[0]
        )["owner"]
    image = load_image_identity(manifest)
    data = PublicReferenceData(
        ledger=ledger, owner=owner, image=image, role_root=root / "roles"
    )
    material = JuliaPublicMaterial(PublicMaterial(data), PublicJuliaStudy(data))
    composition = make_research_service(
        root=root / "tasks",
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=material,
        practice=None,
    )
    connection = fixture_connection(root / "campaign")
    sdk = ResearchMinerTools(
        connection=connection,
        wrapper=AuthenticatedResearchService(
            connection.service.gateway, {owner: composition.service}
        ),
        composition=composition,
        ledger=ledger,
        owner=owner,
    )
    with owner_lock(ledger.root):
        try:
            create_stdio_server(ResearchToolAdapter(sdk, principal=owner)).run()
        finally:
            composition.tasks.close()


def test_real_julia_study_through_external_stdio_and_replay(tmp_path, monkeypatch):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    import carbon.chain.auth

    manifest = os.environ.get("CARBON_JULIA_WORKER_MANIFEST")
    assert manifest, "exact Julia worker image manifest required"
    image = load_image_identity(Path(manifest))
    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    (tmp_path / "campaign").mkdir()
    owner = asyncio.run(_requester(fixture_connection(tmp_path / "campaign")))
    _data, ledger, _calls = prepared(tmp_path, monkeypatch, image=image, owner=owner)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", str(tmp_path), manifest],
        cwd=REPOSITORY,
    )
    arguments = {
        "operation_id": "julia-public-study-fixture-0001",
        "kind": "workspace",
        "strategy": None,
        "action": "public_material",
        "arguments": {"name": MATERIAL},
        "hypothesis": "Measure refinement and conservation of registered Julia on one pinned public case",
        "expected_effect": "Observe diagnostic applicability without replacing accepted reference",
    }
    results = []

    async def exercise():
        for _ in range(2):
            async with Client(parameters, read_timeout_seconds=900) as client:
                response = await client.call_tool(
                    "carbon_research_v2__start_research_task", arguments
                )
                assert not response.is_error, response
                body = response.structured_content["payload"]
                assert body["terminal_task"]["state"] == "SUCCEEDED", body
                results.append(body["public_result"]["result"])

    asyncio.run(exercise())
    assert results[0] == results[1]
    result = results[0]
    assert result["language"] == "julia" and result["backend"] == "cpu"
    assert result["diagnostics"]["completed_horizon"] == result["times"][-1]
    status = ledger.status(owner=owner)
    assert status["used"]["reference_invocations"] == 2
    assert status["used"]["reference_trajectories"] == 2
    assert status["used"]["provider_nanodollars"] == 0
    assert all(operation["state"] == "SUCCEEDED" for operation in status["operations"])
    print(
        json.dumps(
            {
                "case": "miner-julia-external-stdio",
                "image": image.image_id,
                "request_digest": result["request_digest"],
                "diagnostics": result["diagnostics"],
                "used": status["used"],
                "reconnect_replay_same_result": True,
                "scientifically_qualified": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    assert sys.argv[1] == "--serve"
    serve(Path(sys.argv[2]), Path(sys.argv[3]))

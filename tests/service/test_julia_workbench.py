"""Native Julia through private Workbench HTTP under explicit fixture authority.

The authenticated registration and reviewed draft are synthetic controls. The
ASGI API, signed gateway, task lifecycle, campaign ledger and C04 Julia execution
are real. No public deployment, provider spending, protected data or promotion.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import httpx2 as httpx

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_julia_research import prepared
from test_standard_mcp_cli import FixtureSigner, fixture_connection

from carbon.development_session.julia_research import (
    JuliaPublicMaterial,
    PublicJuliaStudy,
)
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_cli import _requester
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.scientific_tasks.workbench import (
    REQUEST,
    TEMPLATE,
    RegisteredWorkbenchDraft,
    WorkbenchScience,
    wire_digest,
)
from carbon.scientific_tasks.workbench_http import create_workbench_app


def test_native_julia_workbench_http_replay_saved_identity_and_stale_draft(
    tmp_path, monkeypatch
):
    import carbon.chain.auth
    from carbon.development_session import research_tools

    manifest = os.environ.get("CARBON_JULIA_WORKER_MANIFEST")
    assert manifest, "exact Julia worker image required"
    image = load_image_identity(Path(manifest))
    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    monkeypatch.setattr(research_tools, "BittensorMessageSigner", FixtureSigner)
    (tmp_path / "campaign").mkdir()
    connection = fixture_connection(tmp_path / "campaign")
    owner = asyncio.run(_requester(connection))
    data, ledger, _calls = prepared(tmp_path, monkeypatch, image=image, owner=owner)
    material = JuliaPublicMaterial(PublicMaterial(data), PublicJuliaStudy(data))
    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=material,
        practice=None,
    )
    adapter = ResearchToolAdapter(
        ResearchMinerTools(
            connection=connection,
            wrapper=AuthenticatedResearchService(
                connection.service.gateway, {owner: composition.service}
            ),
            composition=composition,
            ledger=ledger,
            owner=owner,
        ),
        principal=owner,
    )
    records = {}
    service = WorkbenchScience(
        adapter, draft_resolver=lambda p, j, d, r: records.get((p, j, d, r))
    )
    origin = "https://workbench.fixture.invalid"
    app = create_workbench_app(
        service, authorize=lambda req: owner, allowed_origin=origin
    )
    prefix = "/api/scientific-studies/"

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=origin
        ) as client:
            capabilities = (await client.get(prefix + "capabilities")).json()
            physical = capabilities["physical"]
            scope = {
                key: "synthetic operator-reviewed public Burgers source"
                for key in (
                    "inputs",
                    "outputs",
                    "units",
                    "geometry",
                    "conditions",
                    "regime",
                    "exclusions",
                    "query_workload",
                    "reference_equation",
                    "reference_method",
                )
            }
            scope.update(
                physics_family=TEMPLATE,
                requested_goal="Dynamics",
                rights_scope="SYNTHETIC_INTERNAL",
            )
            key = (owner, "fixture-job", "fixture-design", 1)
            records[key] = RegisteredWorkbenchDraft(
                owner, key[1], key[2], 1, 1, scope, physical, "SYNTHETIC_INTERNAL"
            )
            binding = {
                "job_id": key[1],
                "design_id": key[2],
                "design_revision": 1,
                "physical_sha256": wire_digest(
                    {
                        "template_id": TEMPLATE,
                        "physical": physical,
                        "draft_scope": scope,
                    }
                ),
            }
            request = {
                "schema": REQUEST,
                "operation_id": "study-" + wire_digest(binding),
                "action": "REFERENCE_FEASIBILITY",
                "binding": binding,
                "template_id": TEMPLATE,
                "physical": physical,
                "draft_scope": scope,
                "rights_scope": "SYNTHETIC_INTERNAL",
            }
            headers = {"Origin": origin}
            first = await client.post(prefix + "start", json=request, headers=headers)
            assert first.status_code == 200, first.text
            saved = json.loads(
                json.dumps({"request": request, "response": first.json()})
            )
            assert saved["response"]["status"] == "COMPLETE"
            used = ledger.status(owner=owner)["used"]
            for action in ("start", "status", "result"):
                replay = await client.post(
                    prefix + action, json=saved["request"], headers=headers
                )
                assert replay.status_code == 200, replay.text
                assert replay.json()["task_id"] == saved["response"]["task_id"]
                assert replay.json()["result"] == saved["response"]["result"]
            assert ledger.status(owner=owner)["used"] == used
            records[key] = replace(records[key], current_revision=2)
            stale = await client.post(prefix + "result", json=request, headers=headers)
            assert stale.status_code == 403
            cancelled = await client.post(
                prefix + "cancel", json=request, headers=headers
            )
            assert cancelled.status_code == 200
            assert cancelled.json()["task_id"] == saved["response"]["task_id"]
            assert ledger.status(owner=owner)["used"] == used
            return saved["response"], used

    try:
        result, used = asyncio.run(exercise())
        assert used["reference_invocations"] == used["reference_trajectories"] == 2
        assert used["provider_nanodollars"] == 0
        metadata = result["result"]["metadata"]
        assert metadata["diagnostics"]["completed_horizon"] == metadata["times"][-1]
        print(
            json.dumps(
                {
                    "case": "native-julia-workbench-http",
                    "image": image.image_id,
                    "task_id": result["task_id"],
                    "operation_id": result["operation_id"],
                    "diagnostics": metadata["diagnostics"],
                    "used": used,
                    "saved_replay_same_task": True,
                    "stale_result_rejected": True,
                    "completed_task_cancel_no_reexecution": True,
                    "scientifically_qualified": False,
                },
                sort_keys=True,
            )
        )
    finally:
        composition.tasks.close()


def test_owned_actual_worker_cancel_remains_available_after_grant_expiry(
    tmp_path, monkeypatch
):
    from test_workbench_science import configured

    manifest = os.environ.get("CARBON_JULIA_WORKER_MANIFEST")
    assert manifest, "exact Julia worker image required"
    image = load_image_identity(Path(manifest))
    service, request, _records, ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch, image=image
    )
    journals = service.material.study.data.controller.state_root / "launches"

    async def exercise():
        started = asyncio.create_task(service.call("start", request))
        observed = None
        for _ in range(1000):
            for path in journals.glob("*.json"):
                value = json.loads(path.read_bytes())
                if value["state"] == "CONTROLS_VERIFIED":
                    observed = value
                    break
            if observed is not None or started.done():
                break
            await asyncio.sleep(0.01)
        assert (
            observed is not None
        ), "actual owned worker must pass control checks before expiry"
        ledger.clock = lambda: 50001
        used = ledger.status(owner=service.adapter.principal)["used"]
        cancelled = await service.call("cancel", request)
        assert cancelled["status"] in {"CANCEL_REQUESTED", "REQUIRES_RECONCILIATION"}
        terminal = await started
        assert terminal["status"] == "REQUIRES_RECONCILIATION"
        assert ledger.status(owner=service.adapter.principal)["used"] == used
        final = json.loads(next(journals.glob("*.json")).read_bytes())
        assert final["cleanup"] == "CONFIRMED"
        assert final["terminal_code"] == "reconstruction.worker.cancelled"
        result = await asyncio.to_thread(
            subprocess.run,
            ["docker", "inspect", observed["container_name"]],
            capture_output=True,
            timeout=15,
            check=False,
        )
        assert result.returncode != 0, "test-owned container must be absent"
        return used, final

    try:
        used, journal = asyncio.run(exercise())
        assert used["numerical_milliseconds"] == 720000
        assert used["provider_attempts"] == 0
        print(
            json.dumps(
                {
                    "case": "workbench-expired-grant-owned-worker-cleanup",
                    "image": image.image_id,
                    "cleanup": journal["cleanup"],
                    "terminal_code": journal["terminal_code"],
                    "used_conservative_reservation": used,
                    "new_execution_after_expiry": False,
                },
                sort_keys=True,
            )
        )
    finally:
        composition.tasks.close()

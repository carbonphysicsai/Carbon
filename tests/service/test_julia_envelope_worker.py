"""Actual Julia two-case Workbench execution; synthetic draft/session authority.

No paid provider, public listener, protected data or scientific qualification.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx2 as httpx
import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_julia_envelope import request
from test_workbench_science import configured

from carbon.development_session.research_carrier import ACTIVE_TASK, request_cancel
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.scientific_tasks.workbench import WorkbenchScience
from carbon.scientific_tasks.workbench_http import create_workbench_app


@pytest.mark.parametrize("expire_after_first", [False, True])
def test_actual_julia_envelope_draft_replay_and_expired_held_cleanup(
    tmp_path, monkeypatch, expire_after_first
):
    manifest = os.environ.get("CARBON_JULIA_WORKER_MANIFEST")
    assert manifest, "exact existing Julia worker manifest required"
    image = load_image_identity(Path(manifest))
    service, baseline, _, ledger, _, _, composition = configured(
        tmp_path, monkeypatch, image=image, envelope=True
    )
    if expire_after_first:
        execute = service.material.envelope._execute

        def expire(workspace, numerical, child, parent):
            execute(workspace, numerical, child, parent)
            ledger.clock = lambda: 50001

        monkeypatch.setattr(service.material.envelope, "_execute", expire)
    origin = "https://workbench.fixture.invalid"
    app = create_workbench_app(
        service, authorize=lambda req: service.adapter.principal, allowed_origin=origin
    )
    bound = request(service, baseline)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=origin
        ) as client:
            start = await client.post(
                "/api/scientific-studies/start", json=bound, headers={"Origin": origin}
            )
            assert start.status_code == 200, start.text
            saved = json.loads(json.dumps({"request": bound, "response": start.json()}))
            children = saved["response"]["result"]["children"]
            assert [c["state"] for c in children] == (
                ["SUCCEEDED", "CANCELLED"]
                if expire_after_first
                else ["SUCCEEDED", "SUCCEEDED"]
            )
            used = ledger.status(owner=service.adapter.principal)["used"]
            assert used["reference_invocations"] == (2 if expire_after_first else 4)
            assert used["provider_attempts"] == 0
            assert used["provider_nanodollars"] == 0
            assert used["numerical_milliseconds"] > 0
            if not expire_after_first:
                assert saved["response"]["status"] == "COMPLETE"
                reopened = WorkbenchScience(
                    service.adapter, draft_resolver=service.resolver
                )
                for action in ("start", "status", "result"):
                    again = await reopened.call(action, bound)
                    assert again["result"] == saved["response"]["result"]
                    assert again["task_id"] == saved["response"]["task_id"]
            cancel = await client.post(
                "/api/scientific-studies/cancel", json=bound, headers={"Origin": origin}
            )
            assert cancel.status_code == 200, cancel.text
            assert ledger.status(owner=service.adapter.principal)["used"] == used
            for child in children:
                if child["state"] == "SUCCEEDED":
                    assert child["result"]["metadata"]["shape"] == [13, 64]
                    assert (
                        child["result"]["metadata"]["scientifically_qualified"] is False
                    )
                    assert len(child["result"]["values"]) == 13
                else:
                    assert child["actual"]["numerical_milliseconds"] == 0
            journals = list(
                service.material.study.data.controller.state_root.joinpath(
                    "launches"
                ).glob("*.json")
            )
            assert len(journals) == (1 if expire_after_first else 2)
            assert all(
                json.loads(p.read_bytes())["state"] == "ASSOCIATED_DEVELOPMENT_ONLY"
                for p in journals
            )
            evidence = {
                "fixture_only": True,
                "expire_after_first": expire_after_first,
                "saved": saved,
                "used": used,
                "journals": [json.loads(p.read_bytes()) for p in journals],
            }
            (tmp_path / "actual-envelope-evidence.json").write_text(
                json.dumps(evidence, sort_keys=True), encoding="utf8"
            )
            print(
                json.dumps(
                    {
                        "evidence": str(tmp_path / "actual-envelope-evidence.json"),
                        "used": used,
                        "states": [c["state"] for c in children],
                    }
                )
            )

    try:
        asyncio.run(exercise())
    finally:
        composition.tasks.close()


def test_actual_running_envelope_cancel_releases_only_never_claimed_child(
    tmp_path, monkeypatch
):
    manifest = os.environ.get("CARBON_JULIA_WORKER_MANIFEST")
    assert manifest, "exact existing Julia worker manifest required"
    service, baseline, _, ledger, _, _, composition = configured(
        tmp_path, monkeypatch, image=load_image_identity(Path(manifest)), envelope=True
    )
    controller = service.material.study.data.controller
    original = controller._journal

    def cancel_after_controls(launch, body):
        original(launch, body)
        if body["state"] == "CONTROLS_VERIFIED":
            request_cancel(
                ledger, owner=service.adapter.principal, identity=ACTIVE_TASK.get()
            )

    monkeypatch.setattr(controller, "_journal", cancel_after_controls)
    try:
        result = asyncio.run(service.call("start", request(service, baseline)))
        assert result["status"] == "REQUIRES_RECONCILIATION"
        assert [c["state"] for c in result["result"]["children"]] == [
            "RESERVED",
            "CANCELLED",
        ]
        used = ledger.status(owner=service.adapter.principal)["used"]
        assert used["numerical_milliseconds"] == 720000
        assert used["reference_invocations"] == 2
        assert used["provider_nanodollars"] == 0
        journals = [
            json.loads(p.read_bytes())
            for p in controller.state_root.joinpath("launches").glob("*.json")
        ]
        assert len(journals) == 1
        assert journals[0]["cleanup"] == "CONFIRMED"
        assert journals[0]["terminal_code"] == "reconstruction.worker.cancelled"
        assert not controller.cli.run(
            ["ps", "-aq", "--filter", "name=^" + journals[0]["container_name"] + "$"],
            timeout=10,
        ).stdout.strip()
        evidence = {
            "fixture_only": True,
            "response": result,
            "used": used,
            "journal": journals[0],
        }
        (tmp_path / "cancel-envelope-evidence.json").write_text(
            json.dumps(evidence, sort_keys=True), encoding="utf8"
        )
        print(
            json.dumps(
                {
                    "evidence": str(tmp_path / "cancel-envelope-evidence.json"),
                    "used": used,
                }
            )
        )
    finally:
        composition.tasks.close()

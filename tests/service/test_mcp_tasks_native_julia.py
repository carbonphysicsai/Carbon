"""Negotiated stdio Tasks on actual Julia; explicit local engineering authority.

Only external registration/signing and CPU public fixture composition are
substituted. CLI ownership, grants, ledger, tasks, images, carrier and cleanup
execute normally. This is not paid-agent, security or scientific qualification.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_authored_julia_service import assert_removed
from test_standard_mcp_cli import (
    FixtureSigner,
    fixture_connection,
    private_write,
    unavailable_practice,
)

from carbon.development_session.julia_analysis import (
    SCHEMA as IMAGE_SCHEMA,
)
from carbon.development_session.julia_analysis import (
    authored_julia_scope,
    build_julia_analysis_image,
    load_julia_analysis_image,
)
from carbon.development_session.research_admission import (
    MANIFEST,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    CampaignLedger,
)
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.miner_mcp import standard_cli


@pytest.fixture(scope="module")
def image(tmp_path_factory):
    return build_julia_analysis_image(
        Path(os.environ["CARBON_JULIA_WORKER_MANIFEST"]),
        Path(
            os.environ.get(
                "CARBON_AUTHORED_JULIA_IMAGE_ROOT",
                str(tmp_path_factory.mktemp("julia-image")),
            )
        ),
    )


def prepare_native(root, worker, monkeypatch):
    import carbon.chain.auth
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    root.chmod(0o700)
    campaign = root / "campaign"
    campaign.mkdir(mode=0o700)
    owner = asyncio.run(standard_cli._requester(fixture_connection(campaign)))
    runtime = {
        "implementation": {"revision": "f" * 40},
        "images": [worker.parent.parent_image, worker.parent.image_id],
        "authored_research": [authored_julia_scope(worker)],
    }
    grant = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "mcp-tasks-julia-fixture",
        "campaign_id": "mcp-tasks-julia-fixture",
        "root": str(campaign),
        "principal": "fixture-operator",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": runtime,
        "provider": "openai-responses",
        "account_ref": "fixture-no-paid-calls",
        "campaign_count": 1,
        "ceilings": dict(CEILINGS),
        "elapsed_seconds": ELAPSED_SECONDS,
        "expires_unix": time.time() + ELAPSED_SECONDS,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    grant_file = root / "grant.json"
    private_write(grant_file, grant)
    admission = Admission.load(grant_file)
    manifest = {
        "schema": MANIFEST,
        "campaign_id": grant["campaign_id"],
        "authority": grant["authority"],
        "principal": grant["principal"],
        "owner": owner,
        "runtime": runtime,
        "grant": admission.binding(),
        "ceilings": dict(CEILINGS),
        "elapsed_seconds": ELAPSED_SECONDS,
        "implementation": runtime["implementation"],
        "images": runtime["images"],
        **dict.fromkeys(
            (
                "objective",
                "sampling",
                "control",
                "selection",
                "replica_policy",
                "provider",
            ),
            "engineering-fixture-only",
        ),
    }
    ledger = CampaignLedger(campaign, admission=admission)
    ledger.freeze(manifest)
    private_write(campaign / "campaign-manifest.json", manifest)
    private_write(
        campaign / "authored-julia-image.json",
        {"schema": IMAGE_SCHEMA, **asdict(worker)},
    )
    prepared = make_research_service(
        root=campaign / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=worker.parent,
        julia_image=worker,
        public_material=PublicMaterial(None),
        practice=unavailable_practice,
    )
    prepared.tasks.close()
    path = root / "profile.json"
    private_write(
        path,
        {
            "schema": "carbon.launchpad.runner-profile.v1",
            "profile_id": "fixture-profile",
            "principal": grant["principal"],
            "grant_file": str(grant_file),
            "account_ref": grant["account_ref"],
            "enabled": True,
            "paths": {name: str(root / (name + ".json")) for name in PATH_FIELDS},
            "accepted_revision": runtime["implementation"]["revision"],
        },
    )
    return path, ledger, owner


def serve_native(path):
    import carbon.chain.auth
    from carbon.development_session import research_tools

    carbon.chain.auth.BittensorMessageSigner = FixtureSigner
    research_tools.BittensorMessageSigner = FixtureSigner

    def runtime(profile):
        worker = load_julia_analysis_image(profile.root / "authored-julia-image.json")
        return (
            fixture_connection(profile.root),
            worker.parent,
            worker.parent,
            profile.root,
        )

    standard_cli._runtime = runtime
    standard_cli._science = lambda *args, **kwargs: (
        PublicMaterial(None),
        unavailable_practice,
    )
    return standard_cli.main(["--configuration", str(path)])


def arguments(identity, source):
    return {
        "operation_id": identity,
        "kind": "workspace",
        "strategy": None,
        "action": "run_julia",
        "arguments": {
            "source": source,
            "files": [],
            "seconds": 120,
            "hypothesis": "exercise bounded native Tasks lifecycle",
            "expected_effect": "retain output or observe owned cancellation",
        },
        "hypothesis": "exercise bounded native Tasks lifecycle",
        "expected_effect": "retain output or observe owned cancellation",
    }


def test_cli_negotiated_native_completion_reconnect_cancel_and_shutdown(
    image, tmp_path, monkeypatch
):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    from mcp.types import Result as BaseResult
    from pydantic import ConfigDict

    from carbon.reconstruction.worker.docker_runtime import DockerCLI
    from carbon.reconstruction.worker.model import WorkerFailure
    from tests.service.test_standard_mcp_extensions import _wire_types

    class Result(BaseResult):
        model_config = ConfigDict(extra="allow")

    TasksClient, Handle, TaskParams, GetTask, CancelTask, *_ = _wire_types()
    path, ledger, owner = prepare_native(tmp_path, image, monkeypatch)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", str(path)],
        cwd=REPOSITORY,
    )
    successful = arguments(
        "tasks-native-julia-success-0001",
        'write("/scratch/output/squares.f64le",Float64[i^2 for i in 1:8])',
    )
    blocked = arguments(
        "tasks-native-julia-cancel-0001",
        'run(`/bin/sleep 120`;wait=false);write("/scratch/workspace/ready","ready");sleep(120)',
    )
    saved = []
    acknowledgements = []

    async def observe(client, identity):
        reply = await client.session.send_request(
            GetTask(params=TaskParams(taskId=identity)), Result
        )
        return reply.model_dump(by_alias=True, mode="json")

    async def terminal(client, identity):
        for _ in range(120):
            result = await observe(client, identity)
            if result["status"] != "working":
                return result
            await asyncio.sleep(0.25)
        pytest.fail("native task did not reach observed terminal state")

    async def running_worker():
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            for intent_path in ledger.root.glob("operation-*/intent.json"):
                intent = json.loads(intent_path.read_bytes())
                try:
                    result = await asyncio.to_thread(
                        DockerCLI().run,
                        [
                            "exec",
                            intent["container"],
                            "/usr/bin/test",
                            "-f",
                            "/scratch/workspace/ready",
                        ],
                        timeout=2,
                        accepted=(0, 1),
                    )
                    if result.returncode == 0:
                        return
                except WorkerFailure:
                    pass
            await asyncio.sleep(0.1)
        pytest.fail("acknowledged native Julia never became active")

    async def exercise():
        for connection_index in range(2):
            async with Client(
                parameters, extensions=[TasksClient()], read_timeout_seconds=30
            ) as client:
                started = time.monotonic()
                handle = await client.session.call_tool(
                    "carbon_research_v2__start_research_task",
                    successful,
                    allow_claimed=True,
                )
                acknowledgements.append(time.monotonic() - started)
                assert isinstance(handle, Handle), handle
                result = await terminal(client, handle.task_id)
                assert result["status"] == "completed", result
                body = result["result"]["structuredContent"]
                assert body["operation_id"] == successful["operation_id"]
                assert body["payload"]["terminal_task"]["state"] == "SUCCEEDED"
                assert body["official_eligible"] is False
                saved.append(body)
                if connection_index == 0:
                    continue
                pending = await client.session.call_tool(
                    "carbon_research_v2__start_research_task",
                    blocked,
                    allow_claimed=True,
                )
                assert isinstance(pending, Handle) and pending.status == "working"
                # A returned handle and observable running worker coexist. A
                # blocking completed-call wrapper cannot satisfy this assertion.
                await running_worker()
                assert (await observe(client, pending.task_id))["status"] == "working"
                for _ in range(2):
                    ack = await client.session.send_request(
                        CancelTask(params=TaskParams(taskId=pending.task_id)), Result
                    )
                    assert "status" not in ack.model_dump()
                assert (await terminal(client, pending.task_id))[
                    "status"
                ] == "cancelled"
            # CLI lifespan has joined the worker and existing cleanup authority
            # has reconciled its intent before releasing the campaign owner lock.
            assert_removed(ledger)
        async with Client(
            parameters, extensions=[TasksClient()], read_timeout_seconds=30
        ) as client:
            abandoned = await client.session.call_tool(
                "carbon_research_v2__start_research_task",
                dict(blocked, operation_id="tasks-native-julia-eof-0001"),
                allow_claimed=True,
            )
            assert isinstance(abandoned, Handle) and abandoned.status == "working"
            await running_worker()
            # No protocol cancel: the client's normal stdio EOF must make the
            # server lifespan cancel and join this still-running owned worker.
        assert_removed(ledger)
        from carbon import research

        with sqlite3.connect(
            ledger.root / "research-tasks/research-tasks.sqlite3"
        ) as db:
            (encoded,) = db.execute(
                "SELECT view FROM tasks WHERE id=?", (abandoned.task_id,)
            ).fetchone()
        view = research.load_canonical(encoded, research.ResearchTaskView)
        assert view.state is research.ResearchTaskState.CANCELLED

    asyncio.run(exercise())
    assert saved[0] == saved[1]
    status = ledger.status(owner=owner)
    assert status["used"]["research_trials"] == 3
    assert status["used"]["numerical_milliseconds"] >= 240000
    assert (
        status["used"]["provider_attempts"]
        == status["used"]["provider_nanodollars"]
        == 0
    )
    # Existing shared ledger records one trial and one numerical reservation
    # per execution. Reconnect, observations and cancel retries add neither.
    assert len(status["operations"]) == 6
    assert all(op["state"] != "RESERVED" for op in status["operations"])
    assert_removed(ledger)
    print(
        json.dumps(
            {
                "image": image.image_id,
                "ack_seconds": acknowledgements,
                "used": status["used"],
                "operations": status["operations"],
            }
        )
    )


if __name__ == "__main__":
    assert sys.argv[1] == "--serve"
    raise SystemExit(serve_native(Path(sys.argv[2])))

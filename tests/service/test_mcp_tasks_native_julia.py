"""Negotiated stdio Tasks on actual Julia, on a registration-admitted campaign.

Only external registration/signing and CPU public fixture composition are
substituted. CLI ownership, admission, ledger, tasks, images, carrier and
cleanup execute normally. The campaign is a product campaign (C-MLP-02-D11):
admitted by a recorded registration, never by a grant. This is not paid-agent, security or scientific qualification.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_authored_julia_service import assert_removed
from test_standard_mcp_cli import (
    CAMPAIGN,
    FixtureSigner,
    fixture_connection,
    private_write,
)

from carbon.development_session.julia_analysis import (
    build_julia_analysis_image,
    image_record,
    load_julia_analysis_image,
)
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
    """A registration-admitted battery campaign with the host's authored Julia
    image installed, as a Launchpad profile installs it.

    Burgers is retired from the research path, so the native Tasks lifecycle is
    exercised on battery: a product campaign that declares nothing still
    reaches the host's Julia image, and battery's own composition routes
    `run_julia` to it (#388).
    """
    from test_battery_mcp_research import battery_campaign

    path, ledger, owner, _connection, _manifest = battery_campaign(root, monkeypatch)
    record = image_record(worker)
    private_write(ledger.root / "authored-julia-image.json", record)
    # The runner profile names the image record it installs at every attach.
    installed = root / "authored-julia-image-record.json"
    private_write(installed, record)
    profile = json.loads(path.read_bytes())
    profile["authored_julia_image"] = str(installed)
    private_write(path, profile)
    return path, ledger, owner


def serve_native(path):
    import carbon.chain.auth
    from carbon.development_session import research_tools

    carbon.chain.auth.BittensorMessageSigner = FixtureSigner
    research_tools.BittensorMessageSigner = FixtureSigner

    def runtime(profile):
        # The host and its images are the real authored Julia image's; what
        # follows - registration, the frozen record, control and battery's own
        # attach composition with the host's Julia image - runs for real.
        worker = load_julia_analysis_image(profile.root / "authored-julia-image.json")
        return fixture_connection(profile.root), worker.parent, worker.parent, None

    standard_cli._runtime = runtime
    return standard_cli.main(["--configuration", str(path), "--campaign", CAMPAIGN])


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

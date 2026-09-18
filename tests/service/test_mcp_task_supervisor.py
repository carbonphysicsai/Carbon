"""Real signed fixture gateway and durable supervisor; no paid/numerical claims."""

import asyncio
import threading
from types import SimpleNamespace

import pytest
from test_standard_mcp_cli import FixtureSigner, fixture_connection, prepare

from carbon import research
from carbon.development_session import research_tools
from carbon.development_session.research_carrier import _check_cancel
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.miner_mcp.standard import (
    AdapterFailure,
    ResearchToolAdapter,
    ResearchToolRequest,
)
from carbon.miner_mcp.standard_cli import _AdmittedConnection, load_profile


def compose(path, ledger, owner, monkeypatch, *, cleanup=False):
    monkeypatch.setattr(research_tools, "BittensorMessageSigner", FixtureSigner)
    profile = load_profile(path, cleanup_only=cleanup)
    control = CampaignControl(ledger)
    ledger.generation = control.status()["generation"] if cleanup else control.acquire()
    composition = make_research_service(
        root=ledger.root / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=SimpleNamespace(),
        public_material=PublicMaterial(None),
        practice=lambda *args: None,
        cleanup_only=cleanup,
    )
    connection = fixture_connection(ledger.root)
    wrapper = AuthenticatedResearchService(
        connection.service.gateway, {owner: composition.service}
    )
    sdk = ResearchMinerTools(
        connection=_AdmittedConnection(connection, profile, ledger, control),
        wrapper=wrapper,
        composition=composition,
        ledger=ledger,
        owner=owner,
    )
    return composition, ResearchToolAdapter(sdk, principal=owner)


def request(identity="tasks-operation-0001"):
    return ResearchToolRequest(
        "start_research_task",
        identity,
        {
            "kind": "workspace",
            "strategy": None,
            "action": "notebook",
            "arguments": {"kind": "notebook", "body": {"note": "fixture"}},
            "hypothesis": "Observe durable asynchronous work",
            "expected_effect": "One retained fixture note",
        },
    )


def task_id(result):
    return result.payload["terminal_task"]["task_id"]["value"]


def state(result):
    return result.payload["terminal_task"]["state"]


def block(composition):
    ready, release = threading.Event(), threading.Event()
    original = composition.executor._workspace_action

    def execute(spec, identity):
        ready.set()
        while not release.wait(0.01):
            _check_cancel(
                composition.executor.ledger, composition.executor.owner, identity
            )
        return original(spec, identity)

    composition.executor._workspace_action = execute
    return ready, release


def test_acknowledges_before_execution_and_preserves_fallback_polling(
    tmp_path, monkeypatch
):
    path, ledger, owner = prepare(tmp_path, monkeypatch)
    composition, adapter = compose(path, ledger, owner, monkeypatch)
    ready, release = block(composition)

    async def run():
        try:
            started = await adapter.start_task(request())
            identity = task_id(started)
            assert await asyncio.to_thread(ready.wait, 3)
            assert task_id(await adapter.start_task(request())) == identity
            first = await adapter.call(
                ResearchToolRequest(
                    "get_research_result",
                    "fallback-poll-0001",
                    {"task_id": identity, "poll_sequence": 0},
                )
            )
            assert state(first) == "RUNNING"
            observations = await asyncio.gather(
                *(adapter.observe_task(identity) for _ in range(4))
            )
            assert all(
                state(item) == "RUNNING" and item.operation_id == request().operation_id
                for item in observations
            )
            release.set()
            for _ in range(100):
                current = await adapter.observe_task(identity)
                if state(current) == "SUCCEEDED":
                    break
                await asyncio.sleep(0.01)
            assert state(current) == "SUCCEEDED"
            assert current.payload["public_result"]["result"] == {"retained": True}
            repeated = await adapter.call(
                ResearchToolRequest(
                    "get_research_result",
                    "fallback-poll-0002",
                    {"task_id": identity, "poll_sequence": 0},
                )
            )
            assert state(repeated) == "RUNNING"  # Existing replay semantics, unchanged.
            latest = await adapter.call(
                ResearchToolRequest(
                    "get_research_result",
                    "fallback-poll-0003",
                    {"task_id": identity, "poll_sequence": 1},
                )
            )
            assert state(latest) == "SUCCEEDED"
            assert len(ledger.status(owner=owner)["notes"]) >= 1
            return identity, current
        finally:
            release.set()
            await adapter.shutdown_tasks()
            composition.tasks.close()

    identity, terminal = asyncio.run(run())
    reopened, resumed = compose(path, ledger, owner, monkeypatch)
    try:
        current = asyncio.run(resumed.observe_task(identity))
        assert current == terminal
        with reopened.tasks._db() as db:
            db.execute(
                "UPDATE task_observations SET queries=10000 WHERE id=?", (identity,)
            )
        with pytest.raises(AdapterFailure):
            asyncio.run(resumed.observe_task(identity))
        assert state(asyncio.run(resumed.cancel_task(identity))) == "SUCCEEDED"
    finally:
        asyncio.run(resumed.shutdown_tasks())
        reopened.tasks.close()


@pytest.mark.parametrize("fallback_first", [True, False])
def test_cancel_reuses_identity_across_surfaces_and_shutdown_joins(
    tmp_path, monkeypatch, fallback_first
):
    path, ledger, owner = prepare(tmp_path, monkeypatch)
    composition, adapter = compose(path, ledger, owner, monkeypatch)
    ready, release = block(composition)

    async def run():
        try:
            identity = task_id(await adapter.start_task(request()))
            assert await asyncio.to_thread(ready.wait, 3)
            if fallback_first:
                await adapter.call(
                    ResearchToolRequest(
                        "cancel_research_task",
                        "fallback-cancel-0001",
                        {"task_id": identity},
                    )
                )
            await adapter.cancel_task(identity)
            await adapter.cancel_task(identity)
            await adapter.shutdown_tasks()
            assert state(await adapter.observe_task(identity)) == "CANCELLED"
            assert all(
                future.done() for _, future in adapter._sdk.wrapper._active.values()
            )
        finally:
            release.set()
            await adapter.shutdown_tasks()
            composition.tasks.close()

    asyncio.run(run())


def test_cleanup_attachment_reads_and_cancels_expired_owned_work_without_dispatch(
    tmp_path, monkeypatch
):
    path, ledger, owner = prepare(tmp_path, monkeypatch)
    composition, adapter = compose(path, ledger, owner, monkeypatch)
    # Persist an acknowledged QUEUED task, simulating loss before dispatch.
    original = composition.tasks.run_queued_task
    composition.tasks.run_queued_task = lambda task: composition.tasks.task_observation(
        task, composition.discovery.info.challenge_key, count=False
    )[2]

    async def enqueue():
        value = await adapter.start_task(request())
        await asyncio.sleep(0.02)
        await adapter.shutdown_tasks()
        return task_id(value)

    identity = asyncio.run(enqueue())
    composition.tasks.run_queued_task = original
    composition.tasks.close()
    monkeypatch.setattr(
        "carbon.miner_mcp.standard_cli.time.time",
        lambda: ledger.admission.document["expires_unix"] + 1,
    )
    ledger.clock = lambda: ledger.admission.document["expires_unix"] + 1
    with pytest.raises(ValueError):
        load_profile(path)
    cleaned, bound = compose(path, ledger, owner, monkeypatch, cleanup=True)
    try:
        assert state(asyncio.run(bound.observe_task(identity))) == "QUEUED"
        assert state(asyncio.run(bound.cancel_task(identity))) == "CANCELLED"
        with pytest.raises(AdapterFailure):
            asyncio.run(bound.start_task(request("new-expired-task-0001")))
        numerical = request("expired-numerical-0001")
        numerical.arguments.update(
            action="run_python",
            arguments={
                "source": "print(1)",
                "files": [],
                "seconds": 40,
                "hypothesis": "fixture",
                "expected_effect": "fixture",
            },
        )
        with pytest.raises(AdapterFailure):
            asyncio.run(bound.call(numerical))
        with cleaned.tasks._db() as db:
            assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1
        with ledger.db() as db:
            assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0
        bound._sdk.owner = "different-owner"
        with pytest.raises(AdapterFailure):
            asyncio.run(bound.cancel_task(identity))
    finally:
        bound._sdk.owner = owner
        asyncio.run(bound.shutdown_tasks())
        cleaned.tasks.close()


def test_running_orphan_restart_remains_uncertain_and_does_not_redispatch(
    tmp_path, monkeypatch
):
    path, ledger, owner = prepare(tmp_path, monkeypatch)
    composition, adapter = compose(path, ledger, owner, monkeypatch)

    def orphan(task_id):
        with composition.tasks._lock:
            task = composition.tasks._tasks[task_id]
            composition.tasks._transition(task, research.ResearchTaskState.RUNNING)
            return composition.tasks._view(task)

    composition.tasks.run_queued_task = orphan

    async def start():
        value = await adapter.start_task(request())
        await asyncio.sleep(0.05)
        await adapter.shutdown_tasks()
        return task_id(value)

    identity = asyncio.run(start())
    composition.tasks.close()
    resumed, observer = compose(path, ledger, owner, monkeypatch, cleanup=True)
    resumed.tasks.run_queued_task = lambda _: pytest.fail("uncertain work redispatched")
    try:
        value = asyncio.run(observer.observe_task(identity))
        assert state(value) == "RUNNING"
        assert value.requires_reconciliation
        assert value.payload["public_result"] is None
        with pytest.raises(AdapterFailure):
            asyncio.run(observer.observe_task("rtsk_" + "0" * 64))
        assert state(asyncio.run(observer.cancel_task(identity))) == "CANCEL_REQUESTED"
        assert state(asyncio.run(observer.cancel_task(identity))) == "CANCEL_REQUESTED"
    finally:
        asyncio.run(observer.shutdown_tasks())
        resumed.tasks.close()


def test_cancelled_shutdown_retains_lease_until_owned_worker_finishes(
    tmp_path, monkeypatch
):
    path, ledger, owner = prepare(tmp_path, monkeypatch)
    composition, adapter = compose(path, ledger, owner, monkeypatch)
    ready, release = threading.Event(), threading.Event()
    original = composition.executor._workspace_action

    def finishing(spec, identity):
        ready.set()
        assert release.wait(5)
        return original(spec, identity)

    composition.executor._workspace_action = finishing

    async def exercise():
        try:
            await adapter.start_task(request())
            assert await asyncio.to_thread(ready.wait, 3)
            closing = asyncio.create_task(adapter.shutdown_tasks())
            await asyncio.sleep(0.02)
            closing.cancel()
            await asyncio.sleep(0.02)
            assert not closing.done()
            assert not composition.tasks._lease.closed
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await closing
            assert adapter._sdk.wrapper._active == {}
        finally:
            release.set()
            await adapter.shutdown_tasks()
            composition.tasks.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("missing_observation", [False, True])
def test_actual_cli_cleanup_mode_attaches_without_refreezing_expired_grant(
    tmp_path, monkeypatch, missing_observation
):
    from carbon.miner_mcp import standard_cli

    path, ledger, owner = prepare(tmp_path, monkeypatch)
    composition, adapter = compose(path, ledger, owner, monkeypatch)
    composition.tasks.run_queued_task = (
        lambda identity: composition.tasks.task_observation(
            identity, composition.discovery.info.challenge_key, count=False
        )[2]
    )

    async def queued():
        result = await adapter.start_task(request())
        await asyncio.sleep(0.05)
        await adapter.shutdown_tasks()
        return task_id(result)

    identity = asyncio.run(queued())
    if missing_observation:
        # Existing pre-extension task, or crash after durable start and before
        # start-reply metadata was installed. Immutable task/request survive.
        with composition.tasks._db() as db:
            db.execute("DELETE FROM task_observations")
    composition.tasks.close()
    monkeypatch.setattr(
        standard_cli.time, "time", lambda: ledger.admission.document["expires_unix"] + 1
    )
    monkeypatch.setattr(
        standard_cli,
        "_runtime",
        lambda profile: (
            fixture_connection(profile.root),
            SimpleNamespace(),
            SimpleNamespace(),
            profile.root,
        ),
    )
    monkeypatch.setattr(
        standard_cli,
        "_science",
        lambda *args, **kwargs: (PublicMaterial(None), lambda *a: None),
    )
    observed = []

    def server(bound):
        async def run():
            first = await bound.observe_task(identity)
            assert first.operation_id == request().operation_id
            if missing_observation:
                assert first.payload["reply"]["result"]["created"] is False
            observed.append(state(first))
            observed.append(state(await bound.cancel_task(identity)))
            with pytest.raises(AdapterFailure):
                await bound.start_task(request("cleanup-cli-new-0001"))

        return SimpleNamespace(run_async=run)

    monkeypatch.setattr(standard_cli, "create_stdio_server", server)
    assert standard_cli.main(["--configuration", str(path), "--cleanup-only"]) == 0
    assert observed == ["QUEUED", "CANCELLED"]
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0

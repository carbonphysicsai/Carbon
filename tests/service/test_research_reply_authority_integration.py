"""Signed fixture gateway and real supervisor; no host/provider/numerical work."""

import asyncio
import json

import pytest
from test_mcp_task_supervisor import block, compose, request, task_id
from test_standard_mcp_cli import prepare

from carbon import research
from carbon.development_session import research_reply as rr
from carbon.development_session.research_tools import public_wire
from carbon.miner_mcp.standard import ResearchToolRequest


@pytest.mark.parametrize("rule", [None, rr.RULE])
def test_real_sync_async_replay_cancel_and_reopen_preserve_selected_reply(
    tmp_path, monkeypatch, rule
):
    provider = {"agent": "none"}
    if rule is not None:
        provider["research_reply"] = rule
    path, ledger, owner = prepare(tmp_path, monkeypatch, budget={"provider": provider})
    composition, adapter = compose(path, ledger, owner, monkeypatch)
    initial_manifest = (ledger.root / "campaign-manifest.json").read_bytes()

    def check(result):
        value = result.payload
        if rule is None:
            assert set(value) == rr.LEGACY_FIELDS
        else:
            assert set(value) == rr.FIELDS
            assert value["schema"] == rule
            assert value["current_task"] == rr.current_task(value)
        return value

    async def run():
        # Synchronous start retains queued receipt but finishes the public view.
        sync = await adapter.call(request("sync-authority-0001"))
        value = check(sync)
        assert value["reply"]["result"]["task"]["state"] == "QUEUED"
        assert value["terminal_task"]["state"] == "SUCCEEDED"
        if rule:
            assert value["current_task"]["state"] == "SUCCEEDED"
            assert value["current_task"]["reply_task_revision"] == 0
            assert value["current_task"]["revision"] > 0
        assert not sync.requires_reconciliation
        sync_id = task_id(sync)
        with composition.tasks._db() as db:
            retained = db.execute(
                "SELECT initial_reply FROM task_observations WHERE id=?", (sync_id,)
            ).fetchone()[0]
        assert (
            public_wire(research.load_canonical(retained, research.ServiceReply))
            == value["reply"]
        )
        fallback = check(
            await adapter.call(
                ResearchToolRequest(
                    "get_research_result",
                    "plain-observation-01",
                    {"task_id": sync_id, "poll_sequence": 0},
                )
            )
        )
        assert fallback["terminal_task"]["state"] == "SUCCEEDED"
        if rule:
            assert fallback["current_task"]["state"] == "SUCCEEDED"
        with composition.tasks._db() as db:
            assert (
                db.execute(
                    "SELECT initial_reply FROM task_observations WHERE id=?", (sync_id,)
                ).fetchone()[0]
                == retained
            )
        assert (
            check(await adapter.call(request("sync-authority-0001")))["terminal_task"]
            == value["terminal_task"]
        )
        # Native async acknowledgement must never claim completion prematurely.
        ready, release = block(composition)
        try:
            started = await adapter.start_task(request("async-authority-001"))
            identity = task_id(started)
            ack = check(started)
            if rule:
                assert ack["current_task"]["state"] == "QUEUED"
            assert await asyncio.to_thread(ready.wait, 3)
            running = check(await adapter.observe_task(identity))
            assert running["terminal_task"]["state"] == "RUNNING"
            if rule:
                assert running["current_task"]["state"] == "RUNNING"
            assert running["requires_reconciliation"]
            cancelled = await adapter.cancel_task(identity)
            check(cancelled)
            await adapter.shutdown_tasks()
            final = await adapter.observe_task(identity)
            assert check(final)["terminal_task"]["state"] == "CANCELLED"
            assert final.operation_id == "async-authority-001"
            return identity, final
        finally:
            release.set()

    try:
        identity, final = asyncio.run(run())
    finally:
        asyncio.run(adapter.shutdown_tasks())
        composition.tasks.close()
    reopened, resumed = compose(path, ledger, owner, monkeypatch)
    try:
        observed = asyncio.run(resumed.observe_task(identity))
        assert observed == final
        assert rr.campaign_rule(ledger) == rule
        assert (ledger.root / "campaign-manifest.json").read_bytes() == initial_manifest
        assert json.loads(initial_manifest)["provider"] == provider
    finally:
        asyncio.run(resumed.shutdown_tasks())
        reopened.tasks.close()

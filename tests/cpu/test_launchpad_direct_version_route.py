"""Prospective direct kit selection shares the Launchpad tools route."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.dev.miner_launchpad import runner, tool_door
from test_direct_submission import _recipe


@pytest.mark.parametrize(
    ("session", "version"),
    [
        (tool_door.DIRECT_DEVELOPMENT_SESSION, "1.2"),
        (tool_door.DIRECT_DEVELOPMENT_V13_SESSION, "1.3"),
    ],
)
def test_direct_browser_session_selects_exact_installed_kit(
    tmp_path, monkeypatch, session, version
):
    """The prospective alias adds 1.3 without changing the historical door."""
    configuration = tmp_path / "operator-profile.json"
    seen = []
    attached = object()

    @asynccontextmanager
    async def selected(path, *, version):
        seen.append((path, version))
        yield attached, object()

    monkeypatch.setattr(
        "carbon.miner_mcp.standard_cli.attached_installed_direct_development",
        selected,
    )
    target = {
        "intake_url": "http://127.0.0.1:9080",
        "receiver_hotkey": "5" + "a" * 47,
    }
    host = SimpleNamespace(
        configuration=configuration,
        configured=lambda: {"direct_intake_target": target},
    )

    async def open_selected():
        async with tool_door.runner_opener(host)(session) as actual:
            assert actual == tool_door.DirectToolsAttachment(attached, target)

    asyncio.run(open_selected())
    assert seen == [(Path(configuration), version)]

    class Host:
        def __init__(self):
            self.configuration = configuration
            self.tool_sessions = SimpleNamespace(open=lambda value: {"open": True})

        def owned_campaign(self, _campaign):
            raise AssertionError("direct session must not open a product campaign")

    monkeypatch.setattr(runner, "RunnerAdapter", Host)
    assert tool_door.route(Host(), session, "open", {}) == {
        "campaign": session,
        "open": True,
    }


def test_real_mcp_factory_preserves_historical_launch_replay_shape():
    """The shared Operation contract must construct the actual MCP tools."""
    try:
        import mcp.server.mcpserver  # noqa: F401 - check the pinned SDK layout
    except ModuleNotFoundError:
        if os.environ.get("CARBON_REQUIRE_MCP") == "1":
            pytest.fail("Pinned MCP SDK required for Launchpad tool registration")
        pytest.skip("Pinned MCP SDK tool registration runs in canonical Linux")
    from carbon.miner_mcp.mcp_operations import make_operation_tools
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    tools = {tool.name: tool for tool in make_operation_tools(object())}
    assert set(tools) == {"carbon_" + name for name in OPERATIONS}
    launch = tools["carbon_launch"]
    historical = OPERATIONS["launch"].replay_optional
    assert historical == frozenset(
        {"construction_level", "construction_variant_digest", "arm"}
    )
    assert historical.isdisjoint(launch.parameters["properties"])
    assert historical <= set(launch.fn_metadata.arg_model.model_fields)


def test_direct_v13_tools_action_uses_exact_installed_signer_and_pinned_receiver(
    tmp_path, monkeypatch
):
    from carbon.registry.model import ChallengeKey

    target = {
        "intake_url": "http://127.0.0.1:9080",
        "receiver_hotkey": "5" + "a" * 47,
    }
    connection = SimpleNamespace(miner_key=object(), chain_context=object())
    adapter = SimpleNamespace(
        challenge=ChallengeKey("synthetic-linear-field-2d", "1.3"),
        connection=connection,
        owner="owner-hotkey",
        composition=SimpleNamespace(
            tasks=SimpleNamespace(ledger=SimpleNamespace(root=tmp_path))
        ),
    )
    door = object.__new__(tool_door.DirectToolDoor)
    door.adapter, door.intake_target = adapter, target
    captured = []

    def submitted(url, signer, **kwargs):
        captured.append((url, signer, kwargs))
        return {"state": "RECONSTRUCTED", "task_id": "exact-task"}

    monkeypatch.setattr(
        "carbon.development_session.direct_submission.submit_and_wait", submitted
    )
    result = asyncio.run(door.submit_construction({"recipe": _recipe().to_dict()}))
    assert result["ok"] is True
    assert result["result"] == {"state": "RECONSTRUCTED", "task_id": "exact-task"}
    assert result["score_status"] == "SCORE_UNAVAILABLE"
    assert result["official_eligible"] is False
    assert len(captured) == 1
    assert captured[0][0] == target["intake_url"]
    assert captured[0][1] is connection.miner_key
    assert captured[0][2]["receiver"] == target["receiver_hotkey"]
    assert captured[0][2]["context"] is connection.chain_context
    assert captured[0][2]["recipe"].digest == _recipe().digest

    def staged(url, signer, **kwargs):
        captured.append((url, signer, kwargs))
        return {
            "schema": "carbon.construction.source-stage-result.v1",
            "complete": True,
        }

    monkeypatch.setattr(
        "carbon.development_session.direct_source_submission.stage_graph", staged
    )
    stage = asyncio.run(door.stage_construction_graph({"recipe": _recipe().to_dict()}))
    assert stage["ok"] is True and stage["official_eligible"] is False
    assert captured[1][0] == target["intake_url"]
    assert captured[1][1] is connection.miner_key
    assert captured[1][2]["owner"] == "owner-hotkey"
    assert captured[1][2]["ledger"] is adapter.composition.tasks.ledger
    assert captured[1][2]["receiver"] == target["receiver_hotkey"]

    class Host:
        configuration = tmp_path / "operator-profile.json"
        tool_sessions = SimpleNamespace(
            submit_construction=lambda _, value: result,
            stage_construction_graph=lambda _, value: stage,
        )

        def owned_campaign(self, _):
            raise AssertionError("construction submission must not open Battery")

    monkeypatch.setattr(runner, "RunnerAdapter", Host)
    assert (
        tool_door.route(
            Host(),
            tool_door.DIRECT_DEVELOPMENT_V13_SESSION,
            "submit_construction",
            {"recipe": _recipe().to_dict()},
        )
        == result
    )
    assert (
        tool_door.route(
            Host(),
            tool_door.DIRECT_DEVELOPMENT_V13_SESSION,
            "stage_construction_graph",
            {"recipe": _recipe().to_dict()},
        )
        == stage
    )
    from scripts.dev.miner_launchpad.controller import Rejected

    with pytest.raises(Rejected, match="construction_session_required"):
        tool_door.route(
            Host(),
            tool_door.DIRECT_DEVELOPMENT_SESSION,
            "stage_construction_graph",
            {"recipe": _recipe().to_dict()},
        )

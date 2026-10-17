"""Prospective direct kit selection shares the Launchpad tools route."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.dev.miner_launchpad import runner, tool_door


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
    host = SimpleNamespace(configuration=configuration)

    async def open_selected():
        async with tool_door.runner_opener(host)(session) as actual:
            assert actual is attached

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

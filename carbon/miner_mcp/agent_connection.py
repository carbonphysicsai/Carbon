"""How a miner connects their own agent to Carbon's MCP server, and a check.

A miner may bring any MCP-capable agent - their own client, their own model,
their own account. Carbon serves the standard stdio server (`carbon-mcp`,
`standard_cli`) and nothing more: the miner's client starts that process,
talks to it and stops it. **Carbon does not launch, supervise, monitor or stop
an external agent**, and nothing here reports on one.

`connection_instructions` says exactly what to run for each of the three
tiers the command serves and which tools each tier exposes. The tool lists are
read from the same factories the server uses, so they cannot drift.

`check_connection` performs the MCP handshake in-process against the open-tier
server that `carbon-mcp` serves with no arguments, over an in-memory transport:
no subprocess, no network, no chain read. It shows this installation can serve
the protocol. It does not show that the miner's client is configured, that
their profile or campaign loads, or that anything is connected right now.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

CONNECTION = "carbon.mcp.external-agent-connection.v1"
CONNECTION_CHECK = "carbon.mcp.connection-check.v1"
ENTRY_POINT = "carbon-mcp"
LIFECYCLE = (
    "Your MCP client starts this command, owns the process and ends it. Carbon "
    "serves the stdio protocol while it runs; it does not launch, supervise, "
    "monitor or stop your agent."
)
_CAMPAIGN = re.compile(r"[0-9a-f]{32}")


def _command():
    # The entry point installed beside this interpreter serves this same
    # installation; one found elsewhere on PATH might not.
    beside = Path(sys.executable).parent / ENTRY_POINT
    if beside.is_file():
        return [str(beside)], "installed_entry_point"
    installed = shutil.which(ENTRY_POINT)
    if installed is not None:
        return [installed], "installed_entry_point_on_path"
    return (
        [sys.executable, "-m", "carbon.miner_mcp.standard_cli"],
        "entry_point_not_on_path_module_invocation",
    )


def _open_tier_tools():
    from carbon.miner_mcp.open_tier import create_open_tier_server

    return sorted(create_open_tier_server()._tool_manager._tools)


def _operation_tools():
    from carbon.miner_mcp.mcp_operations import PREFIX, operation_tool_names

    return sorted(
        [
            *operation_tool_names(),
            PREFIX + "attach_campaign",
            PREFIX + "detach_campaign",
        ]
    )


def _campaign_tools():
    from carbon import research
    from carbon.miner_mcp.standard_server import PREFIX

    return sorted(PREFIX + op for op in research.SUPPORTED_OPERATIONS)


def connection_instructions(*, configuration=None, campaign=None):
    """What to run to connect an external agent, and what it will reach.

    With no `configuration`: the open tier (onboarding, Challenge discovery,
    the published exam environment). With a runner profile: every miner
    operation plus attach/detach. With a profile and a `campaign` id: that one
    campaign's research tools, under its ownership lock.

    The profile and campaign are named, not loaded: whether they verify is
    decided when the server starts, which is the only honest place to say so.
    """
    if campaign is not None and configuration is None:
        raise ValueError("a campaign needs your runner profile")
    if campaign is not None and (
        type(campaign) is not str or not _CAMPAIGN.fullmatch(campaign)
    ):
        raise ValueError("a campaign id is 32 lowercase hexadecimal characters")
    command, basis = _command()
    arguments = []
    if configuration is not None:
        arguments += ["--configuration", str(configuration)]
    if campaign is not None:
        arguments += ["--campaign", campaign]
    if configuration is None:
        tier, tools = "OPEN", _open_tier_tools()
        access = "no campaign; reading grants no authority"
    elif campaign is None:
        tier, tools = "OPERATIONS", sorted({*_open_tier_tools(), *_operation_tools()})
        access = (
            "every campaign under your runner profile's campaigns_root, through "
            "the operation tools; attach one for its research tools"
        )
    else:
        tier, tools = "CAMPAIGN", _campaign_tools()
        access = "campaign " + campaign + " only, under its ownership lock"
    full = [*command, *arguments]
    return {
        "schema": CONNECTION,
        "transport": "stdio",
        "tier": tier,
        "command": full,
        "command_basis": basis,
        "client_configuration": {
            "mcpServers": {"carbon": {"command": full[0], "args": full[1:]}}
        },
        "campaign_access": access,
        "tools": tools,
        "verified_at_start": (
            []
            if configuration is None
            else [
                "runner profile",
                "subnet registration",
                "accepted runtime",
                *(["campaign exists and is unfinished"] if campaign else []),
            ]
        ),
        "lifecycle": LIFECYCLE,
        "carbon_controls_external_agent": False,
    }


async def check_connection(server_factory=None):
    """Handshake with the open-tier server in-process; CONNECTED or
    DISCONNECTED, with what was observed and what the check cannot show."""
    from mcp import Client

    basis = (
        "in-process MCP handshake over an in-memory transport with the open-tier "
        "server; no subprocess, network or chain read. It does not show that "
        "your client is configured or that your profile or campaign loads."
    )
    try:
        if server_factory is None:
            from carbon.miner_mcp.open_tier import create_open_tier_server

            server_factory = create_open_tier_server
        server = server_factory()
        async with Client(server, read_timeout_seconds=15) as client:
            listed = await client.list_tools()
            info = client.server_info
            return {
                "schema": CONNECTION_CHECK,
                "status": "CONNECTED",
                "protocol_version": client.protocol_version,
                "server_name": None if info is None else info.name,
                "tools": sorted(tool.name for tool in listed.tools),
                "basis": basis,
            }
    except Exception as error:  # noqa: BLE001 - reported by type, never text
        return {
            "schema": CONNECTION_CHECK,
            "status": "DISCONNECTED",
            "reason": type(error).__name__,
            "basis": basis,
        }

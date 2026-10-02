"""A real external client launches exactly what `connection_instructions` says.

`check_connection` proves an in-process handshake only. Here a separate MCP
client process configuration is taken verbatim from `client_configuration`,
spawned as a subprocess over stdio, and must complete the handshake and list
exactly the tools the instructions promise. The campaign tier with an
unverifiable profile must refuse at startup: the prerequisites are not bypassed.
No network, chain or vendor agent is involved.
"""

from __future__ import annotations

import asyncio
import os
import subprocess

from carbon.miner_mcp.agent_connection import connection_instructions

CAMPAIGN = "0123456789abcdef0123456789abcdef"


def _server(instructions):
    server = instructions["client_configuration"]["mcpServers"]["carbon"]
    return server["command"], server["args"]


def test_external_stdio_client_reaches_the_promised_open_tier_tools(tmp_path):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    instructions = connection_instructions()
    command, args = _server(instructions)

    async def exercise():
        parameters = StdioServerParameters(
            command=command,
            args=args,
            cwd=tmp_path,
            env={**os.environ, "HOME": str(tmp_path)},
        )
        async with Client(parameters, read_timeout_seconds=30) as client:
            tools = sorted(t.name for t in (await client.list_tools()).tools)
            return tools, client.server_info

    tools, info = asyncio.run(exercise())
    assert tools == instructions["tools"]
    assert info is not None and info.name
    assert instructions["carbon_controls_external_agent"] is False


def test_campaign_tier_refuses_an_unverifiable_profile_at_startup(tmp_path):
    instructions = connection_instructions(
        configuration=str(tmp_path / "missing-profile.json"), campaign=CAMPAIGN
    )
    command, args = _server(instructions)
    completed = subprocess.run(
        [command, *args],
        check=False,
        input=b"",
        capture_output=True,
        timeout=120,
        cwd=tmp_path,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert completed.returncode != 0
    assert b"unavailable" in completed.stderr.lower()
    assert completed.stdout == b"", "no protocol is served without the prerequisites"

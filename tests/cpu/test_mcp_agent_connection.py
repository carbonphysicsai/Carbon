"""Connection instructions and the in-process handshake check (no network)."""

import asyncio

import pytest

from carbon import research
from carbon.miner_mcp.agent_connection import (
    check_connection,
    connection_instructions,
)
from carbon.miner_mcp.mcp_operations import operation_tool_names
from carbon.miner_mcp.standard_server import PREFIX as RESEARCH_PREFIX

CAMPAIGN = "0123456789abcdef0123456789abcdef"


def test_open_tier_instructions_run_the_entry_point_with_no_arguments():
    value = connection_instructions()
    assert value["tier"] == "OPEN" and value["transport"] == "stdio"
    assert value["command"][-1].endswith(
        ("/carbon-mcp", "carbon.miner_mcp.standard_cli")
    )
    if value["command_basis"] == "installed_entry_point":
        assert value["command"] == [value["command"][0]]
    server = value["client_configuration"]["mcpServers"]["carbon"]
    assert [server["command"], *server["args"]] == value["command"]
    assert "carbon_onboarding_status" in value["tools"]
    assert not [t for t in value["tools"] if t.startswith(RESEARCH_PREFIX)]
    assert value["carbon_controls_external_agent"] is False
    assert "does not launch" in value["lifecycle"]


def test_operations_and_campaign_tiers_name_their_arguments_and_tools():
    operations = connection_instructions(configuration="/miner/profile.json")
    assert operations["command"][-2:] == ["--configuration", "/miner/profile.json"]
    assert set(operation_tool_names()) <= set(operations["tools"])
    assert "carbon_attach_campaign" in operations["tools"]
    attached = connection_instructions(
        configuration="/miner/profile.json", campaign=CAMPAIGN
    )
    assert attached["command"][-4:] == [
        "--configuration",
        "/miner/profile.json",
        "--campaign",
        CAMPAIGN,
    ]
    assert attached["tools"] == sorted(
        RESEARCH_PREFIX + op for op in research.SUPPORTED_OPERATIONS
    )
    assert CAMPAIGN in attached["campaign_access"]
    assert "campaign exists and is unfinished" in attached["verified_at_start"]


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"campaign": CAMPAIGN}, "runner profile"),
        ({"configuration": "/p", "campaign": "../../etc"}, "hexadecimal"),
    ],
)
def test_malformed_requests_are_refused(arguments, message):
    with pytest.raises(ValueError, match=message):
        connection_instructions(**arguments)


def test_the_handshake_connects_in_process():
    result = asyncio.run(check_connection())
    assert result["status"] == "CONNECTED"
    assert result["server_name"] == "Carbon Onboarding"
    assert result["tools"] == connection_instructions()["tools"]
    assert "no subprocess, network or chain read" in result["basis"]


def test_a_failed_handshake_reports_disconnected_without_its_text():
    def broken():
        raise RuntimeError("private detail sk-FIXTURE")

    result = asyncio.run(check_connection(broken))
    assert result["status"] == "DISCONNECTED"
    assert result["reason"] == "RuntimeError"
    assert "sk-FIXTURE" not in str(result)

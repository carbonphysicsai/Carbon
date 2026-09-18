"""Real stdio interoperability; deterministic fixture, no paid model/science run.

The child uses the real adapter, SDK proposal admission and durable campaign
ledger. Only its domain execution reply is replaced with a closed fixture.
This is one external client implementation, not an agent-host acceptance claim.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
OPERATION_ID = "stdio-business-operation-0001"
PREFIX = "carbon_research_v2__"


def _serve_fixture(root: Path) -> None:
    from types import SimpleNamespace

    sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests" / "cpu")]
    from test_cw1_research_ledger import ledger

    from carbon import research
    from carbon.development_session.research_tools import ResearchMinerTools
    from carbon.miner_mcp.standard import ResearchToolAdapter
    from carbon.miner_mcp.standard_server import create_stdio_server

    meter = ledger(root)

    async def fixture_reply(
        self, name, arguments, identity, *, transport_request_id=None
    ):
        operation = name.removeprefix(PREFIX)
        if operation == "get_prior":
            raise RuntimeError("private-controller-detail-must-not-cross-wire")
        return {
            "protocol": research.RESEARCH_NAMESPACE,
            "operation": operation,
            "reply": {
                "status": "OK",
                "fixture_only": True,
                "business_identity": identity,
                "used_trials": meter.status(owner="alice")["used"]["research_trials"],
            },
            "terminal_task": None,
            "public_result": None,
            "requires_reconciliation": False,
        }

    ResearchMinerTools._call = fixture_reply
    sdk = ResearchMinerTools(
        connection=object(),
        wrapper=object(),
        composition=SimpleNamespace(executor=SimpleNamespace(owner="alice")),
        ledger=meter,
        owner="alice",
    )
    create_stdio_server(ResearchToolAdapter(sdk, principal="alice")).run()


def _parameters(root):
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", str(root)],
        cwd=REPOSITORY,
    )


def _practice():
    return {
        "operation_id": OPERATION_ID,
        "kind": "practice",
        "strategy": {"parameters": {"steps": 512}},
        "action": None,
        "arguments": None,
        "hypothesis": "Test the transport with a deterministic admitted fixture",
        "expected_effect": "One durable proposal charge across reconnects",
    }


@pytest.mark.parametrize("mode", ("auto", "legacy"))
def test_external_sdk_stdio_discovery_tools_resources_and_restart(tmp_path, mode):
    from mcp import Client

    from carbon import research
    from carbon.miner_mcp.standard_server import (
        CAPABILITIES_URI,
        CURRENT_GUIDANCE_URI,
        GUIDANCE_URI,
    )

    async def exercise():
        async with Client(
            _parameters(tmp_path), mode=mode, read_timeout_seconds=15
        ) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert set(tools) == {PREFIX + op for op in research.SUPPORTED_OPERATIONS}
            schema = tools[PREFIX + "start_research_task"].input_schema
            assert schema["additionalProperties"] is False
            assert "strategy" in schema["properties"]
            assert "strategy_json" not in schema["properties"]
            assert "principal" not in schema["properties"]
            assert tools[PREFIX + "start_research_task"].output_schema

            resources = {
                str(item.uri) for item in (await client.list_resources()).resources
            }
            from carbon.miner_mcp.mcp_skills import SKILL_URI, WORKFLOW_URI

            assert resources == {
                CAPABILITIES_URI,
                GUIDANCE_URI,
                CURRENT_GUIDANCE_URI,
                SKILL_URI,
                WORKFLOW_URI,
            }
            capabilities = await client.read_resource(CAPABILITIES_URI)
            assert json.loads(capabilities.contents[0].text)["audience"] == "miner"
            guidance = await client.read_resource(GUIDANCE_URI)
            assert "operation_id stable" in guidance.contents[0].text
            prompt = await client.get_prompt("carbon_research_workflow_v1")
            assert "DEVELOPMENT" in prompt.messages[0].content.text
            current = await client.read_resource(CURRENT_GUIDANCE_URI)
            assert "tasks/get" in current.contents[0].text
            current_prompt = await client.get_prompt("carbon_research_workflow_v2")
            assert current_prompt.messages[0].content.text == current.contents[0].text

            discovery = await client.call_tool(
                PREFIX + "get_challenge_info", {"operation_id": OPERATION_ID}
            )
            assert not discovery.is_error
            assert discovery.structured_content["official_eligible"] is False
            assert discovery.content  # Text fallback accompanies structured output.

            first = await client.call_tool(PREFIX + "start_research_task", _practice())
            second = await client.call_tool(PREFIX + "start_research_task", _practice())
            assert not first.is_error and not second.is_error
            assert first.structured_content == second.structured_content
            assert second.structured_content["payload"]["reply"]["used_trials"] == 1

            for invalid in (
                {**_practice(), "principal": "someone-else"},
                {**_practice(), "strategy": json.dumps(_practice()["strategy"])},
                {**_practice(), "operation_id": 1234567890123456},
            ):
                result = await client.call_tool(PREFIX + "start_research_task", invalid)
                assert result.is_error
            invalid_integer = await client.call_tool(
                PREFIX + "forecast_resources",
                {"operation_id": OPERATION_ID, "strategy": {}, "seconds": True},
            )
            assert invalid_integer.is_error
            unknown = await client.call_tool("protected_validator_evaluate", {})
            assert unknown.is_error
            stopped = await client.call_tool(
                PREFIX + "get_prior", {"operation_id": OPERATION_ID}
            )
            assert stopped.is_error
            public_error = str(stopped.content)
            assert "OPERATIONAL_STOP" in public_error
            assert "private-controller-detail" not in public_error

        # A new external connection launches a new server process against the
        # same existing ledger; protocol sessions do not multiply its allowance.
        async with Client(
            _parameters(tmp_path), mode=mode, read_timeout_seconds=15
        ) as client:
            repeated = await client.call_tool(
                PREFIX + "start_research_task", _practice()
            )
            assert not repeated.is_error
            assert repeated.structured_content["payload"]["reply"]["used_trials"] == 1
            conflict = _practice()
            conflict["strategy"] = {"parameters": {"steps": 1024}}
            result = await client.call_tool(PREFIX + "start_research_task", conflict)
            assert result.is_error
            assert "OPERATIONAL_STOP" in str(result.content)

    asyncio.run(exercise())


def test_factory_rejects_unbound_adapters_before_sdk_load():
    from carbon.miner_mcp.standard_server import create_stdio_server

    with pytest.raises(TypeError, match="operator-bound"):
        create_stdio_server(object())


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--serve":
        raise SystemExit(
            "test fixture requires --serve and an isolated ledger directory"
        )
    _serve_fixture(Path(sys.argv[2]))

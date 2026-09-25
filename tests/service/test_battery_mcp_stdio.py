"""Battery through a real external MCP client over stdio.

The child process serves the battery composition with the real adapter, SDK,
signed gateway, durable task provider and campaign ledger; its practice runs
real JAX training in the subprocess stand-in for the carrier. The parent is
the `mcp` SDK's own client, as any miner's tool would be.

Deterministic client acceptance: the client follows a fixed script. It shows
the external protocol path works for battery; it is not a model-driven
session and makes no research-quality claim.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
PREFIX = "carbon_research_v2__"
BATTERY = "battery-fastcharge-ageing-development-v1"
KNN = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "knn",
    "parameters": {"neighbours": 6},
}


def _serve(root: Path) -> None:
    import pytest

    sys.path[:0] = [
        str(REPOSITORY),
        str(REPOSITORY / "tests" / "cpu"),
        str(REPOSITORY / "tests" / "service"),
    ]
    from test_battery_mcp_research import adapter_for, battery_campaign

    from carbon.miner_mcp.standard_server import create_stdio_server

    patch = pytest.MonkeyPatch()
    root.mkdir(mode=0o700, exist_ok=True)
    path, ledger, owner, connection, _ = battery_campaign(root, patch)
    _composition, _wrapper, adapter = adapter_for(path, ledger, owner, connection)
    create_stdio_server(adapter).run()


def _parameters(root):
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", str(root)],
        cwd=REPOSITORY,
    )


def test_an_external_mcp_client_researches_battery(tmp_path):
    from mcp import Client

    async def call(client, operation, number, **arguments):
        result = await client.call_tool(
            PREFIX + operation,
            {"operation_id": f"stdio-battery-{number:04d}-op", **arguments},
        )
        assert not result.is_error, result.content
        return result.structured_content["payload"]

    async def exercise():
        async with Client(
            _parameters(tmp_path / "served"), mode="legacy", read_timeout_seconds=600
        ) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            assert PREFIX + "start_research_task" in tools
            info = await call(client, "get_challenge_info", 1)
            assert info["reply"]["result"]["challenge_key"]["challenge_id"] == BATTERY
            compiled = await call(client, "compile_strategy", 2, strategy=KNN)
            assert compiled["reply"]["result"]["accepted"] is True
            # Another Challenge's family is refused by name, never reinterpreted.
            fno = await call(
                client, "compile_strategy", 3, strategy={**KNN, "backbone": "fno"}
            )
            assert fno["reply"]["result"]["accepted"] is False
            verdict = await call(
                client,
                "start_research_task",
                4,
                kind="workspace",
                strategy=None,
                action="check_design",
                arguments={"design": {"strategy": KNN}},
                hypothesis="Neighbours are a submittable battery design",
                expected_effect="A submittable verdict",
            )
            assert verdict["public_result"]["result"]["verdict"] == "submittable"
            practiced = await call(
                client,
                "start_research_task",
                5,
                kind="practice",
                strategy=KNN,
                action=None,
                arguments=None,
                hypothesis="Neighbours interpolate the smooth input map",
                expected_effect="Eligible on public PRACTICE",
            )
            feedback = practiced["public_result"]["result"]
            assert feedback["provenance"] == "BATTERY_PUBLIC_PRACTICE"
            assert feedback["summary"]["n_cases"] == 200
            assert feedback["final_exam"] is False
            # Nothing private crosses the wire: no seed, root or hidden case.
            text = json.dumps(practiced).lower()
            assert "pscreen" not in text and "pfinal" not in text
            assert '"seed"' not in text

    asyncio.run(exercise())


if __name__ == "__main__":
    if sys.argv[1:2] == ["--serve"]:
        _serve(Path(sys.argv[2]))

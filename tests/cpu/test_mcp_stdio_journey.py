"""A miner's own MCP client completes the journey over stdio.

Onboarding confirm, then launch with no agent, practice, observe, freeze and
submit - through a real stdio server process and a real MCP client, using the
tools the server generates from the shared operations table. The client holds
nothing Carbon issued: its runner profile path, its own hotkey address, and
the server's own tool list.

The server runs the same journey host as the browser smoke
(`scripts/dev/miner_launchpad/journey_fixture.py`): real host, gates, freeze,
submit, ledger and projection; fixture preparation, training and final exam.
The chain it reads is a stub in which the hotkey is registered. The live chain
read is covered by the testnet onboarding test.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}


class _Registered:
    """A chain in which the fixture hotkey holds UID 0."""

    async def capture(self, context):
        from carbon.chain.models import MetagraphSnapshot, Participant
        from scripts.dev.miner_launchpad.journey_fixture import HOTKEY

        return MetagraphSnapshot(
            context=context,
            finalized_block=100,
            block_hash="0x" + "cd" * 32,
            timestamp_ms=1,
            participants=(
                Participant(
                    uid=0, hotkey=HOTKEY, coldkey="5" + "C" * 47, registered_at=1
                ),
            ),
        )


def _serve(root: Path) -> int:
    sys.path.insert(0, str(REPOSITORY))
    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.miner_mcp import open_tier, standard_cli
    from scripts.dev.miner_launchpad import runner
    from scripts.dev.miner_launchpad.journey_fixture import journey_host

    host = journey_host(root)
    runner.RunnerAdapter.for_profile = classmethod(lambda cls, *_, **__: host)
    real = open_tier.create_open_tier_server
    open_tier.create_open_tier_server = lambda **kw: real(
        reader=_Registered(), context=carbon_testnet_context(), **kw
    )
    profile = root / "runner-profile.json"
    profile.write_text("{}")
    return standard_cli.main(["--configuration", str(profile)])


def _parameters(root):
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", str(root)],
        cwd=REPOSITORY,
    )


def test_a_miners_own_client_completes_the_journey_over_stdio(tmp_path):
    from mcp import Client

    from carbon.development_session.research_loop import candidate_record
    from scripts.dev.miner_launchpad.journey_fixture import HOTKEY
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    tmp_path.chmod(0o700)

    async def call(client, name, arguments):
        result = await client.call_tool(name, arguments)
        return result

    async def observe(client, campaign, until, seconds=30):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = await call(client, "carbon_observe", {"campaign": campaign})
            assert not result.is_error, result.content
            value = result.structured_content["payload"]
            if until(value):
                return value
            await asyncio.sleep(0.2)
        raise AssertionError(f"campaign never reached the expected state: {value}")

    async def journey():
        async with Client(_parameters(tmp_path), read_timeout_seconds=30) as client:
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assert {"carbon_" + name for name in OPERATIONS} <= tools
            assert {"carbon_attach_campaign", "carbon_detach_campaign"} <= tools
            assert "carbon_onboarding_confirm" in tools
            assert not [t for t in tools if "official" in t]

            confirmed = await call(
                client, "carbon_onboarding_confirm", {"address": HOTKEY}
            )
            assert not confirmed.is_error, confirmed.content
            payload = confirmed.structured_content["payload"]
            assert payload["confirmed"] is True and payload["unlocks"] == "launch"

            launched = await call(
                client,
                "carbon_launch",
                {"agent": "none", "idempotency_key": "stdio-journey-key-0001"},
            )
            assert not launched.is_error, launched.content
            campaign = launched.structured_content["payload"]["id"]
            ready = await observe(client, campaign, lambda v: v["state"] == "READY")
            assert ready["selects"] == "miner"

            early = await call(client, "carbon_submit", {"campaign": campaign})
            assert early.is_error
            assert "freeze_a_candidate_first" in early.content[0].text

            practiced = await call(
                client,
                "carbon_practice",
                {
                    "campaign": campaign,
                    "strategy": STRATEGY,
                    "hypothesis": "a practice trial from my own client",
                },
            )
            assert not practiced.is_error, practiced.content
            # One operation at a time: act when the campaign is READY again.
            await observe(
                client,
                campaign,
                lambda v: bool(v["experiments"]) and v["state"] == "READY",
            )

            frozen = await call(
                client,
                "carbon_freeze_candidate",
                {"campaign": campaign, "strategy": STRATEGY, "reason": "practiced"},
            )
            assert not frozen.is_error, frozen.content
            await observe(
                client,
                campaign,
                lambda v: v["journey"]["frozen_awaiting_submission"]
                and v["state"] == "READY",
            )

            submitted = await call(client, "carbon_submit", {"campaign": campaign})
            assert not submitted.is_error, submitted.content
            done = await observe(
                client,
                campaign,
                lambda v: v["journey"]["submitted_epochs"] == [1]
                and v["state"] == "READY",
            )
            assert done["state"] == "READY"
            return campaign

    campaign = asyncio.run(journey())
    folder = tmp_path / "campaigns" / campaign / "epoch-1"
    selected = json.loads((folder / "selected-recipe.json").read_bytes())
    assert selected == candidate_record(STRATEGY, "practiced", False)
    outcome = json.loads((folder / "outcome.json").read_bytes())
    assert outcome["selected_by"] == "miner" and outcome["chain_transactions"] == 0
    assert (folder / "permitted-final-feedback.json").exists()


if __name__ == "__main__":
    assert sys.argv[1] == "--serve"
    raise SystemExit(_serve(Path(sys.argv[2])))

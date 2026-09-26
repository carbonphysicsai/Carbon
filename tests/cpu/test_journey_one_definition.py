"""One journey definition, two drivers: the browser's routes and a miner's own
MCP client over stdio.

`JOURNEY` is written once. Each driver runs every step of it and records what
happened - done, or refused with which code - and the test requires both
drivers to produce the same decisions and the same durable records. Two
similar tests could drift apart silently; one definition with two drivers
cannot, because there is only one list of steps.

The drivers are real: the browser driver posts to the controller's HTTP routes
on a running server; the MCP driver is a real client talking to a real stdio
server process. Both reach the same journey host
(`scripts/dev/miner_launchpad/journey_fixture.py`): real host, operations
table, gates, freeze, submit, ledger and projection; fixture preparation,
training and final exam. The MCP server reads a stub chain in which the hotkey
is registered; the live chain read is covered by the testnet onboarding test.
Nothing on either path is issued by Carbon.
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    BATTERY_CONTRACT,
)

REPOSITORY = Path(__file__).resolve().parents[2]
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}
UNPRACTICED = {**STRATEGY, "parameters": {"steps": 96}}
# A family the registry knows but Carbon cannot rebuild yet.
NOT_YET = {**STRATEGY, "backbone": "unet1d", "parameters": {}}


def _ready(check=lambda value: True):
    return lambda value: value["state"] == "READY" and check(value)


@dataclass(frozen=True)
class Step:
    operation: str
    request: object  # dict, or a function of the campaign id
    expect: str = "done"  # or the refusal code both doors must give
    then: object = None  # a state to wait for, from observe


JOURNEY = (
    Step("options", {}),
    Step(
        "launch",
        {
            "agent": "none",
            # A launch names its Challenge; there is no default.
            "challenge": BATTERY_CHALLENGE,
            "challenge_version": BATTERY_CONTRACT.version,
            "budget": {"elapsed_seconds": 3600, "final_reserve": True},
            "idempotency_key": "one-journey-key-0000001",
        },
        then=_ready(),
    ),
    Step("submit", lambda c: {"campaign": c}, expect="freeze_a_candidate_first"),
    # The registry bridge: an option Carbon cannot rebuild is refused at the
    # moment of choosing, by its verdict, never discovered at submission.
    Step(
        "practice",
        lambda c: {"campaign": c, "strategy": NOT_YET, "hypothesis": "u-net"},
        expect="design_not_yet_rebuildable",
    ),
    Step(
        "practice",
        lambda c: {"campaign": c, "strategy": STRATEGY, "hypothesis": "fno"},
        then=_ready(lambda v: bool(v["experiments"])),
    ),
    Step(
        "freeze_candidate",
        lambda c: {"campaign": c, "strategy": UNPRACTICED, "reason": "untried"},
        expect="practice_result_required",
    ),
    Step(
        "freeze_candidate",
        lambda c: {"campaign": c, "strategy": STRATEGY, "reason": "practiced"},
        then=_ready(lambda v: v["journey"]["frozen_awaiting_submission"]),
    ),
    Step(
        "submit",
        lambda c: {"campaign": c},
        then=_ready(lambda v: v["journey"]["submitted_epochs"] == [1]),
    ),
)


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


class BrowserDriver:
    """The browser door: the controller's HTTP routes on a running server."""

    def __init__(self, root, patch):
        from scripts.dev.miner_launchpad import controller
        from scripts.dev.miner_launchpad.journey_fixture import journey_host

        self.token = "x" * 40
        self.server = controller.Server(
            controller.Controller(root / "launchpad.sqlite3"),
            self.token,
            port=0,
            research_runner=journey_host(root, patch=patch),
        )
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _post(self, name, body):
        import http.client

        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=10
        )
        connection.request(
            "POST",
            "/api/v1/operations/" + name,
            json.dumps(body),
            {
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
            },
        )
        response = connection.getresponse()
        value = json.loads(response.read())
        connection.close()
        if response.status == 200:
            return "done", value
        return value["error"], None

    async def perform(self, name, body):
        return await asyncio.to_thread(self._post, name, body)

    async def close(self):
        self.server.shutdown()
        self.server.server_close()


class McpDriver:
    """A miner's own client: a real MCP client and a real stdio server."""

    def __init__(self, root, patch):
        from mcp.client.stdio import StdioServerParameters

        self.parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).resolve()), "--serve", str(root)],
            cwd=REPOSITORY,
        )
        self.client = None

    async def open(self):
        from mcp import Client

        self.client = Client(self.parameters, read_timeout_seconds=30)
        await self.client.__aenter__()
        from scripts.dev.miner_launchpad.journey_fixture import HOTKEY

        confirmed = await self.client.call_tool(
            "carbon_onboarding_confirm", {"address": HOTKEY}
        )
        assert not confirmed.is_error, confirmed.content
        assert confirmed.structured_content["payload"]["unlocks"] == "launch"

    async def perform(self, name, body):
        result = await self.client.call_tool("carbon_" + name, body)
        if result.is_error:
            return result.content[0].text.split(": ")[-1], None
        return "done", result.structured_content["payload"]

    async def close(self):
        await self.client.__aexit__(None, None, None)


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


async def run_journey(driver):
    """Run `JOURNEY` through one driver; return its decisions and campaign."""
    decisions, campaign = [], None
    for step in JOURNEY:
        body = step.request(campaign) if callable(step.request) else step.request
        outcome, value = await driver.perform(step.operation, body)
        decisions.append((step.operation, outcome))
        assert outcome == step.expect, (step, outcome)
        if step.operation == "launch":
            campaign = value["id"]
        if step.operation == "options":
            agents = {a["value"]: a for a in value["agents"]}
            assert agents["none"]["availability"] == "available"
            verdicts = {f["id"]: f["verdict"] for f in value["families"]}
            assert verdicts["model_family.fno"] == "supported"
            assert verdicts["model_family.unet1d"] == "not_yet_rebuildable"
            # The launch form's budget vocabulary is the ledger's own.
            from carbon.development_session.product_campaign import BUDGET_KEYS
            from carbon.development_session.research_ledger import DIMENSIONS

            assert value["budget"]["keys"] == sorted(BUDGET_KEYS)
            assert value["budget"]["ceilings"] == list(DIMENSIONS)
        if step.then is not None:
            deadline = time.monotonic() + 30
            while True:
                _, observed = await driver.perform("observe", {"campaign": campaign})
                if step.then(observed):
                    break
                assert time.monotonic() < deadline, (step, observed)
                await asyncio.sleep(0.2)
    return decisions, campaign


def records(root, campaign):
    manifest = json.loads(
        (root / "campaigns" / campaign / "campaign-manifest.json").read_bytes()
    )
    folder = root / "campaigns" / campaign / "epoch-1"
    selected = json.loads((folder / "selected-recipe.json").read_bytes())
    outcome = json.loads((folder / "outcome.json").read_bytes())
    return {
        "selected": selected,
        "selected_by": outcome["selected_by"],
        "chain_transactions": outcome["chain_transactions"],
        "feedback": (folder / "permitted-final-feedback.json").exists(),
        "budget": {k: manifest.get(k) for k in ("elapsed_seconds", "final_reserve")},
    }


@pytest.fixture
def journeys(tmp_path, monkeypatch):
    results = {}
    for name, factory in (("browser", BrowserDriver), ("mcp", McpDriver)):
        root = tmp_path / name
        root.mkdir(mode=0o700)

        async def drive(factory=factory, root=root):
            driver = factory(root, monkeypatch.setattr)
            if hasattr(driver, "open"):
                await driver.open()
            try:
                return await run_journey(driver)
            finally:
                await driver.close()

        decisions, campaign = asyncio.run(drive())
        results[name] = (decisions, records(root, campaign))
    return results


def test_both_doors_run_one_journey_to_the_same_decisions_and_records(journeys):
    from carbon.development_session.research_loop import candidate_record

    browser, mcp = journeys["browser"], journeys["mcp"]
    assert browser[0] == mcp[0]
    assert [d for d in browser[0] if d[1] != "done"] == [
        ("submit", "freeze_a_candidate_first"),
        ("practice", "design_not_yet_rebuildable"),
        ("freeze_candidate", "practice_result_required"),
    ]
    assert browser[1] == mcp[1]
    assert browser[1]["selected"] == candidate_record(STRATEGY, "practiced", False)
    assert browser[1]["selected_by"] == "miner"
    assert browser[1]["chain_transactions"] == 0
    assert browser[1]["feedback"] is True
    assert browser[1]["budget"] == {"elapsed_seconds": 3600, "final_reserve": True}


def test_every_operation_in_the_table_is_a_step_or_read_by_the_journey():
    """The definition covers the table: an operation added to the table and
    left out of the journey fails here until someone decides where it goes."""
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    covered = {step.operation for step in JOURNEY} | {"observe"}
    # Halt and resume are the lifecycle controls, pinned by the door-parity
    # test through both doors; the journey has no pause in it.
    assert set(OPERATIONS) - covered == {"halt", "resume"}


if __name__ == "__main__":
    assert sys.argv[1] == "--serve"
    raise SystemExit(_serve(Path(sys.argv[2])))

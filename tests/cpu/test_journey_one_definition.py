"""One direct-campaign refusal journey, two drivers: browser and miner MCP.

`JOURNEY` is written once. Both doors must make the same decisions and persist
the same campaign identity. The fixture Challenge has no direct reconstruction
worker, so practice and freeze must refuse before any task or submission.

The drivers are real: the browser driver posts to the controller's HTTP routes
on a running server; the MCP driver is a real client talking to a real stdio
server process. Both reach the same journey host
(`scripts/dev/miner_launchpad/journey_fixture.py`): real host, operations
table, gates, ledger and projection. Served direct-worker behavior is covered
separately by `test_launchpad_direct_doors.py`. The MCP server reads a stub
chain in which the hotkey is registered; the live chain read is covered by the
testnet onboarding test. Nothing on either path is issued by Carbon.
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

REPOSITORY = Path(__file__).resolve().parents[2]
#: journey_fixture.FIXTURE_CHALLENGE, spelled out: the MCP door's subprocess
#: imports this module before `scripts` is importable.
JOURNEY_CHALLENGE = {"id": "fixture-reference-burgers", "version": "0"}
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}
# Another legacy strategy shape must receive the same worker-status refusal.
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
            # A launch names its Challenge; there is no default. This journey
            # drives the reference fixture Challenge that journey_host registers.
            "challenge": JOURNEY_CHALLENGE["id"],
            "challenge_version": JOURNEY_CHALLENGE["version"],
            "budget": {"elapsed_seconds": 3600, "final_reserve": True},
            "idempotency_key": "one-journey-key-0000001",
        },
        then=_ready(),
    ),
    Step("submit", lambda c: {"campaign": c}, expect="freeze_a_candidate_first"),
    Step(
        "practice",
        lambda c: {"campaign": c, "strategy": NOT_YET, "hypothesis": "u-net"},
        expect="construction_reconstruction_unserved",
    ),
    Step(
        "practice",
        lambda c: {"campaign": c, "strategy": STRATEGY, "hypothesis": "fno"},
        expect="construction_reconstruction_unserved",
    ),
    Step(
        "freeze_candidate",
        lambda c: {"campaign": c, "strategy": STRATEGY, "reason": "unserved"},
        expect="construction_reconstruction_unserved",
    ),
    Step("submit", lambda c: {"campaign": c}, expect="freeze_a_candidate_first"),
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
            # The MCP door's refusal is JSON {error, field, next_step}
            # (LP-PROD-B) after the SDK's "Error executing tool <name>: ".
            refusal = json.loads(result.content[0].text.split(": ", 1)[1])
            return refusal["error"], None
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
            paths = value["construction_paths"][JOURNEY_CHALLENGE["id"]]
            assert paths["challenge"] == JOURNEY_CHALLENGE
            assert paths["construction_kit"] is None
            assert {p["id"]: p["availability"] for p in paths["paths"]} == {
                "public_reconstruction": "unserved",
                "official_submission": "unserved",
            }
            assert paths["qualification"] is False
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
    _, observed = await driver.perform("observe", {"campaign": campaign})
    assert observed["state"] == "READY"
    assert observed["experiments"] == []
    assert observed["journey"]["submitted_epochs"] == []
    return decisions, campaign


def records(root, campaign):
    manifest = json.loads(
        (root / "campaigns" / campaign / "campaign-manifest.json").read_bytes()
    )
    assert not (root / "campaigns" / campaign / "epoch-1").exists()
    return {
        "challenge": manifest["challenge"],
        "construction_mode": manifest["construction_mode"],
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
    browser, mcp = journeys["browser"], journeys["mcp"]
    assert browser[0] == mcp[0]
    assert [d for d in browser[0] if d[1] != "done"] == [
        ("submit", "freeze_a_candidate_first"),
        ("practice", "construction_reconstruction_unserved"),
        ("practice", "construction_reconstruction_unserved"),
        ("freeze_candidate", "construction_reconstruction_unserved"),
        ("submit", "freeze_a_candidate_first"),
    ]
    assert browser[1] == mcp[1]
    assert browser[1]["challenge"] == JOURNEY_CHALLENGE
    assert browser[1]["construction_mode"] == "direct"
    assert browser[1]["budget"] == {"elapsed_seconds": 3600, "final_reserve": True}


def test_every_operation_in_the_table_is_a_step_or_read_by_the_journey():
    """The definition covers the table: an operation added to the table and
    left out of the journey fails here until someone decides where it goes."""
    from scripts.dev.miner_launchpad.operations import (
        LIBRARY_READS,
        LIBRARY_WRITES,
        OPERATIONS,
    )

    # The research view, the toolbox, the miner's messages and a run's own
    # output are reads, as observe is (RSURF-D1, D11, D12, D17). The Graphite
    # library and plans are the miner's own curation, outside any campaign,
    # and admit no work: pinned through both doors by
    # tests/cpu/test_launchpad_graphite_library.py (OWNER-GRAPHITE-MINER-01).
    # A Challenge's construction levels are a read too, outside any campaign:
    # pinned through both doors by tests/cpu/test_launchpad_ladder_view.py
    # (LAUNCHPAD-LEVELS-01).
    covered = (
        {step.operation for step in JOURNEY}
        | {
            "observe",
            "campaign_view",
            "toolbox",
            "ladder",
            "messages",
            "run_output",
        }
        | set(LIBRARY_READS)
        | set(LIBRARY_WRITES)
        # The strategy commitment needs a Challenge that commits on chain,
        # which the journey's fixture Challenge does not: pinned through both
        # doors with the real signer by tests/cpu/test_launchpad_commitment.py
        # (LAUNCHPAD-ACCEPT-02).
        | {"commit"}
        # A recipe against its Challenge's compute budget is a read outside
        # any campaign: pinned through both doors by
        # tests/cpu/test_launchpad_compute_budget_status.py
        # (LAUNCHPAD-COMPUTE-BUDGET-STATUS-01).
        | {"budget_status"}
    )
    # Halt and resume are the lifecycle controls, pinned by the door-parity
    # test through both doors; the journey has no pause in it. A journal note
    # starts no work and is pinned by tests/cpu/test_research_surface.py.
    assert set(OPERATIONS) - covered == {"halt", "resume", "note"}


if __name__ == "__main__":
    assert sys.argv[1] == "--serve"
    raise SystemExit(_serve(Path(sys.argv[2])))


def test_the_journey_launches_the_fixture_challenge():
    from scripts.dev.miner_launchpad.journey_fixture import FIXTURE_CHALLENGE

    assert JOURNEY_CHALLENGE == FIXTURE_CHALLENGE

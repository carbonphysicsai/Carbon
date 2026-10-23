"""The "Fund your wallet" read (Validator funding-door ruling, 2026-10-23).

A fresh finalized read every request, its block named, the wallet's figure
at signing the one that counts, `enough` before transaction fees, no USD and
no fee estimate; the address in the body only. No chain is contacted here.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import threading
from pathlib import Path

import pytest

from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
from carbon.development_session import onboarding_funding as funding

COLDKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
TOKEN = "x" * 40


def _context():
    return ChainContext(
        network=CARBON_NETWORK,
        endpoint="wss://entrypoint-finney.opentensor.ai:443",
        provider="test",
        genesis_hash="0x" + "ab" * 32,
        netuid=CARBON_NETUID,
    )


def _fetch(free, burn, frozen=0, block=8286544, calls=None):
    async def fetch(context, address):
        if calls is not None:
            calls.append(address)
        return {
            "block": block,
            "free_rao": free,
            "frozen_rao": frozen,
            "burn_rao": burn,
        }

    return fetch


def test_a_funded_coldkey_reads_enough_at_its_block_before_fees():
    shown = funding.funding(_context(), COLDKEY, fetch=_fetch(1_988_319_933, 500_000))
    assert shown == {
        "schema": "carbon.onboarding.funding.v1",
        "network": CARBON_NETWORK,
        "netuid": CARBON_NETUID,
        "address": COLDKEY,
        "balance_rao": 1_988_319_933,
        "balance_tao": "1.988319933",
        "joining_cost_rao": 500_000,
        "joining_cost_tao": "0.000500000",
        "enough": True,
        "enough_words": "Enough to join, at block 8286544, before transaction fees.",
        "read_at_block": 8286544,
        "note": (
            "Read at block 8286544. Your wallet shows the cost again when you "
            "sign; that figure is the one that counts."
        ),
    }
    text = json.dumps(shown).lower()
    assert "usd" not in text and "fee_estimate" not in text


def test_frozen_balance_is_not_spendable_and_short_reads_not_enough():
    shown = funding.funding(
        _context(), COLDKEY, fetch=_fetch(1_000_000, 900_000, frozen=200_000)
    )
    assert shown["balance_rao"] == 800_000 and shown["enough"] is False
    assert shown["enough_words"].startswith("Not enough to join, at block")


def test_every_request_reads_the_chain_afresh():
    calls = []
    for _ in range(2):
        funding.funding(_context(), COLDKEY, fetch=_fetch(5, 1, calls=calls))
    assert calls == [COLDKEY, COLDKEY]


@pytest.mark.parametrize(
    ("context", "address", "code"),
    [
        (_context(), "not-an-address", "address_invalid"),
        (_context(), None, "address_invalid"),
        (None, COLDKEY, "chain_not_configured"),
    ],
)
def test_bad_input_is_refused_typed(context, address, code):
    with pytest.raises(funding.FundingRefused) as refused:
        funding.funding(context, address, fetch=_fetch(1, 1))
    assert refused.value.code == code
    assert refused.value.body() == {
        "error": code,
        "next_step": funding.FundingRefused.STEPS[code][1],
    }


def test_a_chain_failure_is_infrastructure_and_retryable():
    async def broken(context, address):
        raise OSError("429 Too Many Requests")

    with pytest.raises(funding.FundingRefused) as refused:
        funding.funding(_context(), COLDKEY, fetch=broken)
    assert (refused.value.code, refused.value.status) == (
        "chain_read_failed_infra",
        503,
    )


MODULE = (
    Path(__file__).resolve().parents[2] / "scripts/dev/miner_launchpad/controller.py"
)


@pytest.fixture
def server(tmp_path, monkeypatch):
    from carbon.chain import funding_read

    monkeypatch.setattr(funding_read, "read_funding", _fetch(2_000_000_000, 500_000))
    spec = importlib.util.spec_from_file_location("carbon_launchpad_funding", MODULE)
    launchpad = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launchpad)
    from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

    class _Reader:
        async def capture(self, context):
            raise AssertionError("no metagraph read here")

    onboarding = BrowserOnboarding(reader=_Reader(), context=_context())
    controller = launchpad.Controller(tmp_path / "runs.sqlite3")
    served = launchpad.Server(controller, TOKEN, port=0, onboarding=onboarding)
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    yield served
    served.shutdown()
    served.server_close()
    thread.join(timeout=3)


def _post(server, body):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.request(
        "POST",
        "/api/v1/onboarding/funding",
        json.dumps(body),
        {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    return response.status, payload


def test_the_door_answers_in_the_body_and_refuses_typed(server):
    status, body = _post(server, {"address": COLDKEY})
    assert status == 200 and body["enough"] is True and body["read_at_block"] == 8286544
    assert _post(server, {"address": "nope"}) == (
        400,
        {
            "error": "address_invalid",
            "next_step": funding.FundingRefused.STEPS["address_invalid"][1],
        },
    )
    assert _post(server, {"address": COLDKEY, "extra": 1})[0] == 400

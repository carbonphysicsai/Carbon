"""Actual public-read adapter over a fake SDK only; no RPC or real credentials."""

import asyncio
from types import SimpleNamespace

import pytest
from test_incentive_observer_bindings import CONTEXT, FRESH, NOW, SNAPSHOT

from carbon.chain.sdk import BittensorReader
from scripts.dev.canary import incentive as inc
from scripts.dev.canary import incentive_observation as obs


@pytest.fixture
def sdk(monkeypatch):
    import bittensor as bt

    calls = []
    state = {
        "row": [[0, 43690], [1, 21845]],
        "incentives": [43690, 21845, 0],
        "genesis": CONTEXT.genesis_hash,
        "updates": [0, 0, 8],
        "head": SNAPSHOT.block_hash,
    }

    async def capture(self, context):
        assert context == CONTEXT
        return SNAPSHOT

    monkeypatch.setattr(BittensorReader, "capture", capture)
    monkeypatch.setattr(obs, "FRESHNESS", FRESH)

    class Substrate:
        def __init__(self, endpoint, **kwargs):
            assert endpoint == CONTEXT.endpoint and kwargs["fallback_endpoints"] == []

        async def connect(self):
            calls.append("connect")

        async def block_hash(self, number):
            calls.append(("hash", number))
            return (
                state["genesis"]
                if number == 0
                else state["head"] if number == 10 else "0x" + "8" * 64
            )

        async def query(self, module, name, params=None, *, block_hash):
            calls.append(("query", module, name, params, block_hash))
            if name == "Weights":
                assert block_hash == SNAPSHOT.block_hash
                return state["row"]
            if name == "LastUpdate":
                assert block_hash == SNAPSHOT.block_hash
                return state["updates"]
            assert (module, name) == ("Timestamp", "Now")
            return NOW - 1000

    class Client:
        def __init__(self, endpoint, *, substrate):
            assert endpoint == CONTEXT.endpoint and isinstance(substrate, Substrate)

        async def at(self, block):
            assert block == SNAPSHOT.finalized_block

            async def read(name, **kwargs):
                assert name == "metagraph" and kwargs["netuid"] == CONTEXT.netuid
                return {"incentives": state["incentives"]}

            return SimpleNamespace(read=read)

        async def close(self):
            calls.append("close")

    monkeypatch.setattr(bt, "RpcSubstrate", Substrate)
    monkeypatch.setattr(bt, "Client", Client)
    return state, calls


def read():
    return asyncio.run(
        inc.read_weights(CONTEXT, "5Validator", feed_block=[{"number": 8}])
    )


def test_actual_read_binds_row_incentives_publication_and_older_anchor(sdk):
    _, calls = sdk
    value = read()
    assert value.snapshot == SNAPSHOT
    assert value.row == ((0, 43690), (1, 21845)) and value.incentives == (
        43690,
        21845,
        0,
    )
    assert (
        value.publication
        == value.feed_anchor[8]
        == {"number": 8, "hash": "0x" + "8" * 64, "timestamp_ms": NOW - 1000}
    )
    assert calls[-1] == "close"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("genesis", "0x" + "3" * 64, "endpoint_genesis_mismatch"),
        ("row", [[1, True]], "weights_malformed"),
        ("row", [[1, 1], [1, 2]], "weights_malformed"),
        ("row", [[3, 2]], "weights_malformed"),
        ("incentives", [0, "1", 0], "incentives_malformed"),
        ("incentives", [0, 1], "incentives_malformed"),
    ],
)
def test_wrong_context_or_malformed_sdk_data_refuses_and_closes(
    sdk, field, value, code
):
    state, calls = sdk
    state[field] = value
    with pytest.raises(obs.Unverified, match=code):
        read()
    assert calls[-1] == "close"


def test_unavailable_publication_epoch_is_not_invented(sdk):
    state, _ = sdk
    state["updates"] = [0, 0, 0]
    assert read().publication is None

"""NET-1 read boundary: hostile responses, identity recycling and installed SDK."""

import asyncio
import importlib.util
import os
import subprocess
import sys
from dataclasses import replace

import pytest

from carbon.chain import (
    BittensorReader,
    ChainContext,
    ChainFailure,
    FailureCode,
    ReadOnlyChainAdapter,
)
from carbon.chain.adapter import translate

GENESIS = "0x" + "a" * 64
BLOCK = "0x" + "b" * 64


def context():
    return ChainContext("localnet", "ws://127.0.0.1:9944", "development-a", GENESIS, 1)


def graph():
    return {
        "netuid": 1,
        "num_uids": 2,
        "hotkeys": ["hot-a", "hot-b"],
        "coldkeys": ["cold-a", "cold-b"],
        "block_at_registration": [2, 3],
    }


class FakeReader:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = 0

    async def capture(self, ctx):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value or translate(ctx, 10, BLOCK, 100000, graph())


def observe(reader, minimum=10):
    return asyncio.run(
        ReadOnlyChainAdapter(context(), reader).observe(minimum_finalized_block=minimum)
    )


def test_lazy_construction_and_carbon_only_observation():
    reader = FakeReader()
    ReadOnlyChainAdapter(context(), reader)
    BittensorReader()
    assert reader.calls == 0
    snapshot = observe(reader)
    assert reader.calls == 1
    assert snapshot.resolve("absent") is None
    assert snapshot.resolve("hot-a").uid == 0
    assert snapshot.snapshot_id == observe(FakeReader()).snapshot_id
    assert (
        snapshot.snapshot_id
        != replace(snapshot, context=replace(context(), provider="other")).snapshot_id
    )
    with pytest.raises(AttributeError):
        snapshot.finalized_block = 11


@pytest.mark.parametrize(
    "field,value",
    [
        ("netuid", 2),
        ("num_uids", True),
        ("num_uids", 65537),
        ("hotkeys", ["hot-a"]),
        ("hotkeys", ["hot-a", "hot-a"]),
        ("coldkeys", ["cold-a", None]),
        ("block_at_registration", [2, 11]),
        ("block_at_registration", [2, -1]),
    ],
)
def test_reject_malformed_or_inconsistent_metagraph(field, value):
    raw = graph()
    raw[field] = value
    with pytest.raises(ChainFailure):
        translate(context(), 10, BLOCK, 100000, raw)


@pytest.mark.parametrize(
    "raw,code",
    [
        (None, FailureCode.INCOMPLETE),
        ({}, FailureCode.INCOMPLETE),
        ([], FailureCode.MALFORMED),
    ],
)
def test_missing_is_not_empty_subnet(raw, code):
    with pytest.raises(ChainFailure) as failure:
        translate(context(), 10, BLOCK, 100000, raw)
    assert failure.value.code == code


def test_explicit_empty_subnet_is_valid():
    raw = {
        "netuid": 1,
        "num_uids": 0,
        "hotkeys": [],
        "coldkeys": [],
        "block_at_registration": [],
    }
    assert translate(context(), 10, BLOCK, 100000, raw).participants == ()


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError("PRIVATE"), FailureCode.TIMEOUT),
        (ConnectionError("PRIVATE"), FailureCode.UNAVAILABLE),
        (OSError("PRIVATE"), FailureCode.TRANSPORT),
        (ValueError("PRIVATE"), FailureCode.MALFORMED),
        (NotImplementedError("PRIVATE"), FailureCode.UNSUPPORTED),
        (ChainFailure(FailureCode.CHAIN), FailureCode.CHAIN),
    ],
)
def test_provider_errors_are_closed_and_unchained(error, code):
    with pytest.raises(ChainFailure) as failure:
        observe(FakeReader(error=error))
    assert failure.value.code == code
    assert "PRIVATE" not in str(failure.value)
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None


def test_stale_snapshot_requires_explicit_watermark():
    with pytest.raises(ChainFailure, match="STALE"):
        observe(FakeReader(), minimum=11)


@pytest.mark.parametrize(
    "change", ["uid", "hotkey", "coldkey", "registration", "context", "time"]
)
def test_uid_and_registration_recycling_cannot_inherit_identity(change):
    before = observe(FakeReader())
    original = before.resolve("hot-a")
    members = list(before.participants)
    after = replace(before, finalized_block=11)
    if change == "uid":
        members = [replace(members[1], uid=0), replace(members[0], uid=1)]
    elif change == "hotkey":
        members[0] = replace(original, hotkey="replacement")
    elif change == "coldkey":
        members[0] = replace(original, coldkey="new-wallet")
    elif change == "registration":
        members[0] = replace(original, registered_at=11)
    elif change == "context":
        after = replace(after, context=replace(context(), netuid=2))
    elif change == "time":
        after = replace(after, timestamp_ms=99999)
    after = replace(after, participants=tuple(members))
    with pytest.raises(ChainFailure):
        after.require_identity(before, original)


def test_unchanged_registration_and_same_snapshot_are_valid():
    before = observe(FakeReader())
    member = before.resolve("hot-a")
    assert before.require_identity(before, member) == member
    assert (
        replace(before, finalized_block=11).require_identity(before, member) == member
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "finney",
        "https://127.0.0.1",
        "ws://user:secret@localhost",
        "ws://localhost?token=secret",
        "wss://public.example",
    ],
)
def test_local_endpoint_has_no_public_fallback_or_credentials(endpoint):
    with pytest.raises(ChainFailure):
        replace(context(), endpoint=endpoint)


def test_import_does_not_load_sdk_or_connect():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import carbon.chain; assert 'bittensor' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


class InstalledSubstrate:
    """Only read capabilities. The SDK cannot sign through this test double."""

    def __init__(self):
        self.calls = []
        self.closed = False
        self.genesis = GENESIS

    async def connect(self):
        self.calls.append("connect")

    async def close(self):
        self.closed = True

    async def block_hash(self, block):
        self.calls.append(("hash", block))
        return self.genesis if block == 0 else BLOCK

    async def blocks(self, *, finalized):
        assert finalized is True
        yield {"header": {"number": 10, "parentHash": GENESIS}}

    async def runtime_call(self, api, method, params, *, block_hash):
        assert (api, method, params, block_hash) == (
            "SubnetInfoRuntimeApi",
            "get_metagraph",
            [1],
            BLOCK,
        )
        self.calls.append("metagraph")
        return graph()

    async def query(self, pallet, item, params=None, *, block_hash):
        assert (pallet, item, block_hash) == ("Timestamp", "Now", BLOCK)
        return 100000


def installed_sdk():
    if importlib.util.find_spec("bittensor") is None:
        if os.environ.get("CARBON_REQUIRE_CHAIN_SDK") == "1":
            pytest.fail(
                "The installed chain SDK contract is required in this acceptance lane"
            )
        pytest.skip(
            "Optional chain group absent; installed-SDK contract runs in canonical CI"
        )
    from importlib.metadata import version

    import bittensor

    assert version("bittensor") == "11.1.0"
    return bittensor


def test_installed_sdk_real_client_snapshot_and_read_registry():
    bt = installed_sdk()
    from carbon.chain.sdk import _capture

    substrate = InstalledSubstrate()
    snapshot = asyncio.run(_capture(bt, substrate, context()))
    assert snapshot == observe(FakeReader())
    assert substrate.closed
    assert "metagraph" in substrate.calls


def test_installed_sdk_genesis_rejected_before_metagraph():
    bt = installed_sdk()
    from carbon.chain.sdk import _capture

    substrate = InstalledSubstrate()
    substrate.genesis = BLOCK
    with pytest.raises(ChainFailure, match="IDENTITY"):
        asyncio.run(_capture(bt, substrate, context()))
    assert substrate.closed
    assert "metagraph" not in substrate.calls

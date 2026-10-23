"""A chain read the endpoint refuses is infrastructure, not a capability gap.

12h S4: three of four campaigns launched together from the page went
INTERRUPTED within a minute with UNSUPPORTED_CAPABILITY - the public RPC
refused their concurrent metagraph reads (the SDK's RpcPolicyError: HTTP
429/403, WebSocket 1008 or a JSON-RPC traffic-policy error), and the reader
mapped that refusal to UNSUPPORTED. These tests hold:
- a refused read is retried with bounded backoff, honouring Retry-After;
- campaigns launched together in one process share one read;
- a read still refused after its retries is PROVIDER_RATE_LIMITED, and a run
  it ends stops typed `chain_read_failed_infra` - failed_infra, retryable -
  never UNSUPPORTED_CAPABILITY.
No chain is reached: the SDK is a fake with the SDK's error shapes.
"""

from __future__ import annotations

import asyncio
import threading
import time
import types

import pytest

from carbon.chain import sdk
from carbon.chain.adapter import translate
from carbon.chain.models import ChainContext, ChainFailure, FailureCode
from scripts.dev.miner_launchpad import supervisor
from scripts.dev.miner_launchpad.controller import failure_answer

GENESIS = "0x" + "a" * 64
BLOCK = "0x" + "b" * 64


def context(provider="development-a"):
    return ChainContext("localnet", "ws://127.0.0.1:9944", provider, GENESIS, 1)


def graph():
    return {
        "netuid": 1,
        "num_uids": 1,
        "hotkeys": ["hot-a"],
        "coldkeys": ["cold-a"],
        "block_at_registration": [2],
    }


class RpcConnectionError(Exception):
    pass


class RpcPolicyError(RpcConnectionError):
    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class ChainError(Exception):
    pass


FAKE_SDK = types.SimpleNamespace(
    RpcConnectionError=RpcConnectionError,
    RpcPolicyError=RpcPolicyError,
    ChainError=ChainError,
)


class RateLimitedRpc:
    """A public endpoint that serves one read at a time and refuses any read
    that overlaps another, or comes within `window` seconds of the last one
    it served, as the SDK reports a policy refusal (HTTP 429)."""

    def __init__(self, window=0.0, retry_after=None):
        self.window = window
        self.retry_after = retry_after
        self.lock = threading.Lock()
        self.busy = False
        self.last = None
        self.served = 0
        self.refused = 0

    async def read(self, ctx):
        with self.lock:
            now = time.monotonic()
            if self.busy or (self.last is not None and now - self.last < self.window):
                self.refused += 1
                raise RpcPolicyError(
                    "RPC endpoint rate limited this source (HTTP 429): PRIVATE",
                    retry_after=self.retry_after,
                )
            self.busy = True
        try:
            await asyncio.sleep(0.05)
            return translate(ctx, 10, BLOCK, 100000, graph())
        finally:
            with self.lock:
                self.busy = False
                self.last = time.monotonic()
                self.served += 1


class Reader(sdk.BittensorReader):
    """The real reader over a fake SDK and endpoint; waits are recorded and
    shortened so the test runs in milliseconds."""

    def __init__(self, rpc, attempts=None):
        self.rpc = rpc
        self.waits = []
        if attempts is not None:
            self.attempts = attempts

    def _sdk(self):
        return FAKE_SDK

    async def _sleep(self, seconds):
        self.waits.append(seconds)
        await asyncio.sleep(min(seconds * 0.05, 0.2))

    async def _attempt(self, bt, ctx):
        return await self.rpc.read(ctx)


@pytest.fixture(autouse=True)
def fresh_share(monkeypatch):
    monkeypatch.setattr(sdk, "_shared", {})


# --- retry with bounded backoff ---------------------------------------------------


def test_a_refused_read_is_retried_and_honours_retry_after(monkeypatch):
    class Twice:
        calls = 0

        async def read(self, ctx):
            Twice.calls += 1
            if Twice.calls <= 2:
                raise RpcPolicyError("PRIVATE", retry_after="60")
            return translate(ctx, 10, BLOCK, 100000, graph())

    reader = Reader(Twice())
    snapshot = asyncio.run(reader.capture(context()))
    assert snapshot.finalized_block == 10
    assert Twice.calls == 3
    # The endpoint's Retry-After (the public RPC asks for 10-60 s), honoured.
    assert reader.waits == [60.0, 60.0]


def test_backoff_is_bounded_and_ignores_an_untrusted_retry_after():
    class Always:
        async def read(self, ctx):
            raise RpcPolicyError("PRIVATE", retry_after="Wed, 21 Oct 2026 07:28:00 GMT")

    reader = Reader(Always())
    with pytest.raises(ChainFailure) as failure:
        asyncio.run(reader.capture(context()))
    assert len(reader.waits) == reader.attempts - 1
    assert all(0 < wait <= reader.max_delay for wait in reader.waits)
    huge = Reader(Always())
    huge.base_delay = 1000.0
    with pytest.raises(ChainFailure):
        asyncio.run(huge.capture(context("other")))
    assert huge.waits == [huge.max_delay] * (huge.attempts - 1)
    # A refusal still standing is typed infrastructure, and closed.
    assert failure.value.code is FailureCode.RATE_LIMITED
    assert failure.value.code.value == "PROVIDER_RATE_LIMITED"
    assert "PRIVATE" not in str(failure.value)
    assert failure.value.__context__ is None and failure.value.__cause__ is None


def test_a_dropped_connection_is_retried_and_a_chain_error_is_not():
    class Dropped:
        calls = 0

        async def read(self, ctx):
            Dropped.calls += 1
            raise RpcConnectionError("PRIVATE")

    reader = Reader(Dropped())
    with pytest.raises(ChainFailure) as failure:
        asyncio.run(reader.capture(context()))
    assert failure.value.code is FailureCode.UNAVAILABLE
    assert Dropped.calls == reader.attempts

    class Broken:
        calls = 0

        async def read(self, ctx):
            Broken.calls += 1
            raise ChainError("PRIVATE")

    reader = Reader(Broken())
    with pytest.raises(ChainFailure) as failure:
        asyncio.run(reader.capture(context("broken")))
    assert failure.value.code is FailureCode.CHAIN
    assert Broken.calls == 1 and reader.waits == []


# --- campaigns launched together ---------------------------------------------------


def launch_together(readers, ctx, count):
    results, errors = [None] * count, [None] * count
    start = threading.Barrier(count)

    def launch(index):
        start.wait()
        try:
            results[index] = asyncio.run(readers[index].capture(ctx))
        except ChainFailure as failure:
            errors[index] = failure

    threads = [threading.Thread(target=launch, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results, errors


def test_campaigns_launched_together_share_one_read():
    rpc = RateLimitedRpc(window=10.0)
    readers = [Reader(rpc) for _ in range(4)]
    results, errors = launch_together(readers, context(), 4)
    assert errors == [None] * 4
    assert {r.snapshot_id for r in results} == {results[0].snapshot_id}
    # One connection served all four; none was refused.
    assert (rpc.served, rpc.refused) == (1, 0)


def test_unshared_concurrent_reads_are_refused_then_retried_until_served(monkeypatch):
    """Readers that share nothing - campaigns in separate processes - are
    refused while their reads overlap; each backs off and is served."""
    monkeypatch.setattr(sdk, "_shared_capture", lambda ctx, read: read(ctx))
    rpc = RateLimitedRpc(window=0.0)
    readers = [Reader(rpc, attempts=8) for _ in range(4)]
    results, errors = launch_together(readers, context(), 4)
    assert errors == [None] * 4 and all(results)
    assert rpc.served == 4 and rpc.refused > 0


def test_a_share_expires_and_a_failed_read_is_not_shared(monkeypatch):
    class Once:
        calls = 0

        async def read(self, ctx):
            Once.calls += 1
            if Once.calls == 1:
                raise ChainError("PRIVATE")
            return translate(ctx, 10 + Once.calls, BLOCK, 100000, graph())

    reader = Reader(Once())
    with pytest.raises(ChainFailure):
        asyncio.run(reader.capture(context()))
    first = asyncio.run(reader.capture(context()))
    assert asyncio.run(reader.capture(context())) is first
    monkeypatch.setattr(sdk, "SHARE_SECONDS", 0.0)
    assert (
        asyncio.run(reader.capture(context())).finalized_block > first.finalized_block
    )


# --- the typed infrastructure stop -------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        FailureCode.RATE_LIMITED,
        FailureCode.UNAVAILABLE,
        FailureCode.TIMEOUT,
        FailureCode.TRANSPORT,
    ],
)
def test_a_chain_infra_failure_stops_typed_and_retryable(code):
    failure = ChainFailure(code)
    assert supervisor.chain_interruption_code(failure) == "chain_read_failed_infra"
    # Also when it caused the failure that ended the run.
    try:
        try:
            raise failure
        except ChainFailure as inner:
            raise RuntimeError("session start failed") from inner
    except RuntimeError as outer:
        assert supervisor.chain_interruption_code(outer) == "chain_read_failed_infra"
    entry = supervisor.refusal(
        "chain_read_failed_infra", operation="run", kind="interrupted"
    )
    assert entry["failed_infra"] is True and entry["retryable"] is True
    assert entry["code"] == "chain_read_failed_infra"
    assert "infrastructure" in entry["next_action"]
    assert "Resume" in entry["next_action"]
    assert failure_answer(failure, reading=False) == (503, "chain_read_failed_infra")


@pytest.mark.parametrize(
    "code", [FailureCode.UNSUPPORTED, FailureCode.IDENTITY, FailureCode.CHAIN]
)
def test_other_chain_failures_keep_their_own_code(code):
    assert supervisor.chain_interruption_code(ChainFailure(code)) is None
    assert supervisor.exception_code(ChainFailure(code)) == code.value
    entry = supervisor.refusal(code.value, kind="interrupted")
    assert "failed_infra" not in entry and "retryable" not in entry


def test_a_stored_infra_stop_reads_back_the_same():
    import json

    entry = supervisor.refusal("chain_read_failed_infra", kind="interrupted", at=1.0)
    assert supervisor.read_refusal(json.dumps(entry)) == entry

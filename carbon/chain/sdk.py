"""Bittensor 11.1 boundary. Imports, clients, SDK errors and raw rows stay here."""

import asyncio
import logging
import random
import threading
import time
from contextlib import aclosing
from importlib.metadata import version

from .adapter import translate
from .models import (
    ChainContext,
    ChainFailure,
    FailureCode,
    MetagraphSnapshot,
    hash256,
    uint,
)
from .practice import LOCAL_PRACTICE

SDK_VERSION = "11.1.0"
_log = logging.getLogger(__name__)

#: How long one process shares a metagraph read for the same chain context:
#: campaigns launched together read the chain once, not once each (12h S4:
#: three of four campaigns launched together were refused by the public RPC:
#: HTTP 429 under its WebSocket-upgrade policy, ten connections a minute,
#: retry after 10-60 s). One block: one process opens at most five
#: connections a minute for it, and a reader never sees a finalized block
#: older than one block before its own read would have.
SHARE_SECONDS = 12.0
_shared_lock = threading.Lock()
_shared: dict = {}


class BittensorReader:
    #: A read the endpoint refused under its traffic policy, or dropped, is
    #: infrastructure: tried again up to `attempts` times in all, waiting the
    #: endpoint's Retry-After when it gives one, else doubling from
    #: `base_delay`, never longer than `max_delay` per wait (the public RPC
    #: asks for up to 60 s).
    attempts = 4
    base_delay = 2.0
    max_delay = 60.0

    async def capture(self, context: ChainContext) -> MetagraphSnapshot:
        if context.network == LOCAL_PRACTICE:
            # A practice identity's local context names no chain to read.
            raise ChainFailure(FailureCode.IDENTITY)
        return await _shared_capture(context, self._read)

    @staticmethod
    def _sdk():
        if version("bittensor") != SDK_VERSION:
            raise ChainFailure(FailureCode.UNSUPPORTED)
        import bittensor as bt

        return bt

    @staticmethod
    async def _sleep(seconds):
        await asyncio.sleep(seconds)

    async def _attempt(self, bt, context):
        # Public SDK backend injection keeps endpoint pools empty and lets the
        # installed-SDK tests exercise actual Client/Snapshot/registry code.
        substrate = bt.RpcSubstrate(
            context.endpoint,
            fallback_endpoints=[],
            archive_endpoints=[],
            retry_forever=False,
        )
        return await _capture(bt, substrate, context)

    async def _read(self, context: ChainContext) -> MetagraphSnapshot:
        bt = self._sdk()
        failure = None
        for attempt in range(self.attempts):
            wait = None
            try:
                return await self._attempt(bt, context)
            except bt.RpcPolicyError as refused:
                failure = FailureCode.RATE_LIMITED
                wait = _retry_after(getattr(refused, "retry_after", None))
                # The SDK's typed, bounded fields only, never the message.
                _log.warning(
                    "chain read refused by the endpoint's policy (attempt %d of "
                    "%d): status=%s policy=%s reason=%s retry_after=%s",
                    attempt + 1,
                    self.attempts,
                    getattr(refused, "status_code", None),
                    getattr(refused, "policy", None),
                    getattr(refused, "reason", None),
                    getattr(refused, "retry_after", None),
                )
            except bt.RpcConnectionError:
                failure = FailureCode.UNAVAILABLE
            except bt.ChainError:
                failure = FailureCode.CHAIN
                break
            if attempt + 1 < self.attempts:
                backoff = self.base_delay * 2**attempt * (0.5 + random.random() / 2)
                await self._sleep(min(self.max_delay, max(wait or 0.0, backoff)))
        raise ChainFailure(failure)


def _retry_after(value):
    """The endpoint's Retry-After as seconds, when it is a plain number of
    seconds; otherwise None (a date or a reset time is not trusted)."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if 0.0 <= seconds < 3600.0 else None


async def _shared_capture(context, read):
    """`read(context)`, shared by every caller in this process for the same
    context for `SHARE_SECONDS`, and made by one caller at a time: the others
    wait for its result instead of opening their own connections. A failed
    read is not shared; the next caller reads again. Waiting polls a thread
    lock, so callers on different threads' event loops share it and a
    cancelled waiter holds nothing."""
    with _shared_lock:
        entry = _shared.setdefault(context, {"gate": threading.Lock()})
    gate = entry["gate"]
    while not gate.acquire(blocking=False):
        await asyncio.sleep(0.05)
    try:
        kept = entry.get("snapshot")
        if kept is not None and time.monotonic() - entry["at"] < SHARE_SECONDS:
            return kept
        snapshot = await read(context)
        entry["snapshot"], entry["at"] = snapshot, time.monotonic()
        return snapshot
    finally:
        gate.release()


async def _capture(bt, substrate, context: ChainContext) -> MetagraphSnapshot:
    """Use the SDK's public read contract; no raw RPC or private transport shim."""
    client = bt.Client(context.endpoint, substrate=substrate)
    try:
        # Connect the explicit backend, avoiding Client.connect's unrelated
        # token-symbol/config reads. Identity is checked before metagraph reads.
        await substrate.connect()
        genesis = hash256(await substrate.block_hash(0))
        if genesis != context.genesis_hash:
            raise ChainFailure(FailureCode.IDENTITY)
        async with aclosing(client.blocks(finalized=True)) as headers:
            header = await anext(headers)
        block = uint(header.number)
        digest = hash256(await substrate.block_hash(block))
        view = await client.at(block)
        graph = await view.read("metagraph", netuid=context.netuid)
        timestamp_ms = uint(await view.query(bt.storage.Timestamp.Now))
        # A contradictory provider must not make number-pinned SDK reads look
        # like a consistent hash-pinned observation.
        if (
            hash256(await substrate.block_hash(block)) != digest
            or hash256(await substrate.block_hash(0)) != genesis
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        return translate(context, block, digest, timestamp_ms, graph)
    finally:
        await client.close()

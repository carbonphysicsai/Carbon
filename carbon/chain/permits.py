"""Read-only validator-permit reads at the finalized head (VALIDATOR-19 S2).

The answer-key distribution host admits a hotkey only while it holds a
validator permit on the subnet (OWNER-SHARED-ANSWER-KEY-01, the
standard-Bittensor addendum). This module reads that permit: one finalized
block, genesis-checked, with the metagraph and the `ValidatorPermit` storage
read at the same block hash, as `sdk_weights.capture_capabilities` does. It
never signs or submits anything.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from contextlib import aclosing
from importlib.metadata import version

from .adapter import translate
from .models import ChainContext, ChainFailure, FailureCode, hash256, uint
from .sdk import SDK_VERSION


class PermitUnavailable(RuntimeError):
    """The chain could not be read: infrastructure, never a refusal."""


class ValidatorPermitReader:
    """Reads one subnet's validator permits at the chain's finalized head.

    `fetch(context, hotkey)` is the async read and returns
    `(registered, permit, block)`; tests inject one. The default is the SDK
    read below.
    """

    def __init__(self, context, *, fetch=None):
        if type(context) is not ChainContext:
            raise TypeError("a ChainContext is required")
        self.context = context
        self._fetch = _fetch if fetch is None else fetch

    def read(self, hotkey):
        """`{"permit": bool, "block": int}` for a registered hotkey; None
        for one that is not registered on the subnet."""
        if type(hotkey) is not str or not hotkey:
            return None
        try:
            # A private event loop in a worker thread, so a caller already
            # inside an event loop can still call this.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                found = pool.submit(
                    asyncio.run, self._fetch(self.context, hotkey)
                ).result()
        except ChainFailure as failure:
            raise PermitUnavailable(str(failure)) from None
        except Exception:  # noqa: BLE001 -- any provider error is infrastructure
            raise PermitUnavailable("permit_read_failed") from None
        if type(found) is not tuple or len(found) != 3:
            raise PermitUnavailable("permit_read_malformed")
        registered, permit, block = found
        if type(block) is not int or block < 0 or type(permit) is not bool:
            raise PermitUnavailable("permit_read_malformed")
        if not registered:
            return None
        return {"permit": permit, "block": block}


async def _fetch(context, hotkey):
    if version("bittensor") != SDK_VERSION:
        raise ChainFailure(FailureCode.UNSUPPORTED)
    import bittensor as bt

    substrate = bt.RpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=[],
        retry_forever=False,
    )
    client = bt.Client(context.endpoint, substrate=substrate)
    try:
        await substrate.connect()
        if hash256(await substrate.block_hash(0)) != context.genesis_hash:
            raise ChainFailure(FailureCode.IDENTITY)
        async with aclosing(client.blocks(finalized=True)) as headers:
            header = await anext(headers)
        block = uint(header.number)
        block_hash = hash256(await substrate.block_hash(block))
        view = await client.at(block)
        graph = await view.read("metagraph", netuid=context.netuid)
        now = uint(await view.query(bt.storage.Timestamp.Now))
        snapshot = translate(context, block, block_hash, now, graph)
        member = snapshot.resolve(hotkey)
        if member is None:
            return (False, False, block)
        permits = await substrate.query(
            "SubtensorModule",
            "ValidatorPermit",
            [context.netuid],
            block_hash=block_hash,
        )
        if type(permits) is not list or member.uid >= len(permits):
            raise ChainFailure(FailureCode.INCOMPLETE)
        return (True, permits[member.uid] is True, block)
    finally:
        await client.close()

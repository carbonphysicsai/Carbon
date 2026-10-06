"""Read-only on-chain commitment reader for validator admission (OD-7;
VALIDATOR-14).

A miner commits `carbon.battery.commitment.v1` (`daemon.commitment_digest`),
the `sha256:` digest over its Challenge, contract digest and strategy hash, as
a Raw commitment on the subnet. Its own signer posts it; Carbon never holds a
miner key. A validator configured with `require_commitment` reads the hotkey's
current commitment at a finalized block and admits only a submission whose
expected digest it equals (`BatteryValidator.admit`).

`read(hotkey)` returns `{"digest", "block"}`, or None when the hotkey has no
commitment or the commitment is not a digest. Either way the admission is
refused as `commitment_required`. A chain or provider failure raises
`CommitmentUnavailable`, which the deployment types as infrastructure
(`commitment_reader_unavailable`), never the candidate's fault.

It uses the SDK's public read contract through the same genesis-checked,
finalized-block path as `sdk.BittensorReader`. It never signs, and it holds no
key.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from contextlib import aclosing
from importlib.metadata import version

from .models import ChainContext, ChainFailure, FailureCode, hash256, uint
from .sdk import SDK_VERSION

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class CommitmentUnavailable(RuntimeError):
    """The chain could not be read: infrastructure, never a refusal of the
    submission."""


class ChainCommitmentReader:
    """Reads one subnet's commitments at the chain's finalized head.

    `fetch(context, hotkey)` is the async read; tests inject one. The default
    is the SDK read below.
    """

    def __init__(self, context, *, fetch=None, fetch_all=None):
        if type(context) is not ChainContext:
            raise TypeError("a ChainContext is required")
        self.context = context
        self._fetch = _fetch if fetch is None else fetch
        self._fetch_all = _fetch_all if fetch_all is None else fetch_all

    def holders(self, digest):
        """`[(hotkey, block)]`, earliest first, for every hotkey whose visible
        commitment on this subnet is `digest`, at the finalized head
        (OWNER-COMMITMENT-POSTER-01 D6: across hotkeys, the earliest
        commitment block has priority). Raises `CommitmentUnavailable`."""
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                rows = pool.submit(asyncio.run, self._fetch_all(self.context)).result()
        except ChainFailure as failure:
            raise CommitmentUnavailable(str(failure)) from None
        except Exception:  # noqa: BLE001 -- any provider error is infrastructure
            raise CommitmentUnavailable("commitment_read_failed") from None
        if type(rows) is not list:
            raise CommitmentUnavailable("commitment_rows_malformed")
        found = []
        for row in rows:
            if type(row) is not tuple or len(row) != 3:
                raise CommitmentUnavailable("commitment_rows_malformed")
            hotkey, data, block = row
            if data == digest and type(hotkey) is str and type(block) is int:
                found.append((hotkey, block))
        return sorted(found, key=lambda item: (item[1], item[0]))

    def read(self, hotkey):
        if type(hotkey) is not str or not hotkey:
            return None
        try:
            # A private event loop in a worker thread, so a caller already
            # inside an event loop (an async intake) can still call this.
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                found = pool.submit(
                    asyncio.run, self._fetch(self.context, hotkey)
                ).result()
        except ChainFailure as failure:
            raise CommitmentUnavailable(str(failure)) from None
        except Exception:  # noqa: BLE001 -- any provider error is infrastructure
            raise CommitmentUnavailable("commitment_read_failed") from None
        if found is None:
            return None
        data, block = found
        if type(block) is not int or block < 0:
            raise CommitmentUnavailable("commitment_block_malformed")
        if type(data) is not str or DIGEST.fullmatch(data) is None:
            return None
        return {"digest": data, "block": block}


async def _fetch_all(context):
    """`[(hotkey, data, block)]` for every visible commitment on
    `context.netuid` at the finalized head. Genesis-checked, as `_fetch` is."""
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
        view = await client.at(uint(header.number))
        rows = await view.read("commitments", netuid=context.netuid)
        return [(r["hotkey"], r["commitment"], r["block"]) for r in rows]
    finally:
        await client.close()


async def _fetch(context, hotkey):
    """`(data, block)` of `hotkey`'s commitment on `context.netuid` at the
    finalized head, or None. Genesis-checked, as `sdk._capture` is."""
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
        view = await client.at(uint(header.number))
        found = await view.read("commitment", netuid=context.netuid, hotkey_ss58=hotkey)
        return None if found is None else (found.data, found.block)
    finally:
        await client.close()

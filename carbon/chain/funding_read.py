"""Read-only funding read at the finalized head: one coldkey's free balance and
the subnet's burned-registration cost (Validator funding-door ruling,
2026-10-23).

The same finalized, genesis-checked read as `chain.sdk`'s and
`metagraph_read`'s: one finalized block, `System.Account(address)` and
`SubtensorModule.Burn(netuid)` at that block, and the block hash re-read
afterwards, so a contradictory provider cannot make number-pinned reads look
like one hash-pinned observation. A fresh read every call: nothing is cached
or stored, and the address goes only to the configured chain endpoint. It
never signs or submits anything, and no score input reads it
(`tests/invariants/test_funding_unreachable.py`).
"""

from __future__ import annotations

from contextlib import aclosing
from importlib.metadata import version

from .models import ChainFailure, FailureCode, hash256, identifier, uint
from .sdk import SDK_VERSION


async def read_funding(context, address):
    """`{"block", "free_rao", "frozen_rao", "burn_rao"}` at the finalized head."""
    identifier(address)
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
        genesis = hash256(await substrate.block_hash(0))
        if genesis != context.genesis_hash:
            raise ChainFailure(FailureCode.IDENTITY)
        async with aclosing(client.blocks(finalized=True)) as headers:
            header = await anext(headers)
        block = uint(header.number)
        digest = hash256(await substrate.block_hash(block))
        view = await client.at(block)
        account = await view.query(bt.storage.System.Account, [address])
        burn = await view.query(bt.storage.SubtensorModule.Burn, [context.netuid])
        if (
            hash256(await substrate.block_hash(block)) != digest
            or hash256(await substrate.block_hash(0)) != genesis
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        data = account.get("data") if type(account) is dict else None
        if type(data) is not dict:
            raise ChainFailure(FailureCode.MALFORMED)
        return {
            "block": block,
            "free_rao": uint(data.get("free")),
            "frozen_rao": uint(data.get("frozen", 0)),
            "burn_rao": uint(burn),
        }
    finally:
        await client.close()

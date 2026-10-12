"""Read-only metagraph read at the finalized head, keeping its columns
(DASHBOARD-02 S3).

`chain.sdk._capture`'s read: one finalized block, genesis-checked, the SDK's
metagraph runtime read and `Timestamp.Now` at that block, and the block hash
re-read afterwards, so a contradictory provider cannot make number-pinned
reads look like one hash-pinned observation. `_capture` keeps only the
participants; this keeps the raw metagraph too, so the validator's network
snapshot (`carbon.challenge_validator.network_snapshot`) can take its public
per-UID columns. It never signs or submits anything.
"""

from __future__ import annotations

from contextlib import aclosing
from importlib.metadata import version

from .models import ChainFailure, FailureCode, hash256, uint
from .sdk import SDK_VERSION


async def read_metagraph(context):
    """`{"block", "block_hash", "timestamp_ms", "graph"}` at the finalized head."""
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
        graph = await view.read("metagraph", netuid=context.netuid)
        timestamp_ms = uint(await view.query(bt.storage.Timestamp.Now))
        if (
            hash256(await substrate.block_hash(block)) != digest
            or hash256(await substrate.block_hash(0)) != genesis
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        return {
            "block": block,
            "block_hash": digest,
            "timestamp_ms": timestamp_ms,
            "graph": graph,
        }
    finally:
        await client.close()


__all__ = ["read_metagraph"]

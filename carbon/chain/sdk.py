"""Bittensor 11.1 boundary. Imports, clients, SDK errors and raw rows stay here."""

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

SDK_VERSION = "11.1.0"


class BittensorReader:
    async def capture(self, context: ChainContext) -> MetagraphSnapshot:
        if version("bittensor") != SDK_VERSION:
            raise ChainFailure(FailureCode.UNSUPPORTED)
        # Public SDK backend injection keeps endpoint pools empty and lets the
        # installed-SDK tests exercise actual Client/Snapshot/registry code.
        import bittensor as bt

        substrate = bt.RpcSubstrate(
            context.endpoint,
            fallback_endpoints=[],
            archive_endpoints=[],
            retry_forever=False,
        )
        failure = None
        try:
            return await _capture(bt, substrate, context)
        except bt.RpcPolicyError:
            failure = FailureCode.UNSUPPORTED
        except bt.RpcConnectionError:
            failure = FailureCode.UNAVAILABLE
        except bt.ChainError:
            failure = FailureCode.CHAIN
        raise ChainFailure(failure)


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

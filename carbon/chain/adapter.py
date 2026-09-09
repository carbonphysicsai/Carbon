"""Bounded observation capture shared by the installed-SDK and deterministic fakes."""

import asyncio
from typing import Protocol

from .models import (
    ChainContext,
    ChainFailure,
    FailureCode,
    MetagraphSnapshot,
    Participant,
    hash256,
    uint,
)


class ObservationReader(Protocol):
    async def capture(self, context: ChainContext) -> MetagraphSnapshot: ...


class ReadOnlyChainAdapter:
    """Explicit dependencies; construction/import never opens a connection."""

    def __init__(
        self,
        context: ChainContext,
        reader: ObservationReader,
        *,
        timeout_seconds: int = 30,
    ):
        if type(context) is not ChainContext:
            raise ChainFailure(FailureCode.IDENTITY)
        uint(timeout_seconds, 300)
        if timeout_seconds == 0:
            raise ChainFailure(FailureCode.MALFORMED)
        self._context = context
        self._reader = reader
        self._timeout = timeout_seconds

    async def observe(self, *, minimum_finalized_block: int) -> MetagraphSnapshot:
        uint(minimum_finalized_block)
        failure = None
        try:
            async with asyncio.timeout(self._timeout):
                result = await self._reader.capture(self._context)
            if type(result) is not MetagraphSnapshot or result.context != self._context:
                failure = FailureCode.IDENTITY
            elif result.finalized_block < minimum_finalized_block:
                failure = FailureCode.STALE
            else:
                return result
        except ChainFailure as error:
            failure = error.code
        except TimeoutError:
            failure = FailureCode.TIMEOUT
        except ConnectionError:
            failure = FailureCode.UNAVAILABLE
        except OSError:
            failure = FailureCode.TRANSPORT
        except (NotImplementedError, ImportError):
            failure = FailureCode.UNSUPPORTED
        # Unknown provider failures must not expose private response material.
        except Exception:  # noqa: BLE001
            failure = FailureCode.MALFORMED
        # Outside the handler: no sensitive __context__, even for local diagnostics.
        raise ChainFailure(failure)


def translate(
    context: ChainContext, block: int, block_hash: str, timestamp_ms: int, graph: object
) -> MetagraphSnapshot:
    if graph is None:
        raise ChainFailure(FailureCode.INCOMPLETE)
    if type(graph) is not dict:
        raise ChainFailure(FailureCode.MALFORMED)
    required = {"netuid", "num_uids", "hotkeys", "coldkeys", "block_at_registration"}
    if not required <= graph.keys():
        raise ChainFailure(FailureCode.INCOMPLETE)
    if uint(graph["netuid"], 65535) != context.netuid:
        raise ChainFailure(FailureCode.IDENTITY)
    count = uint(graph["num_uids"], 65536)
    arrays = [graph[name] for name in ("hotkeys", "coldkeys", "block_at_registration")]
    if any(type(values) is not list or len(values) != count for values in arrays):
        raise ChainFailure(FailureCode.INCOMPLETE)
    members = tuple(Participant(i, *values) for i, values in enumerate(zip(*arrays)))
    return MetagraphSnapshot(context, block, hash256(block_hash), timestamp_ms, members)

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
    #: infrastructure: tried again up to `_attempts` times in all, waiting the
    #: endpoint's Retry-After when it gives one, else doubling from
    #: `_base_delay`, never longer than `_max_delay` per wait (the public RPC
    #: asks for up to 60 s).
    _attempts = 4
    _base_delay = 2.0
    _max_delay = 60.0

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
        for attempt in range(self._attempts):
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
                    self._attempts,
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
            if attempt + 1 < self._attempts:
                backoff = self._base_delay * 2**attempt * (0.5 + random.random() / 2)
                await self._sleep(min(self._max_delay, max(wait or 0.0, backoff)))
        raise ChainFailure(failure)


#: The SDK's own connection task (`RpcSession._run`, bittensor 11.1). When a dial fails (an HTTP 429 upgrade refusal,
#: the node down), the read that waited on it already fails typed, but the task's own exception is never collected, so
#: asyncio prints "Task exception was never retrieved" and a Traceback when the task is freed (staging drills F1 / F3 /
#: R7, 7 Nov: four in one run on a door that kept serving).
SESSION_TASK = "rpc-session"
#: The modules whose exceptions are a chain transport fault, not a Carbon bug.
_TRANSPORT_MODULES = ("bittensor", "websockets")


def _chain_transport_fault(failure):
    if isinstance(failure, (OSError, TimeoutError)):
        return True
    return type(failure).__module__.split(".")[0] in _TRANSPORT_MODULES


def session_exception_handler(loop, context):
    """The reader loop's exception handler: an uncollected chain-transport failure of the SDK's session task is ONE
    typed line, ``chain_session_error kind=<type>`` (the read it broke has already failed typed); everything else, a
    Carbon bug included, goes to asyncio's default handler with its Traceback."""
    task = context.get("future") or context.get("task")
    failure = context.get("exception")
    if (
        isinstance(task, asyncio.Task)
        and task.get_name() == SESSION_TASK
        and failure is not None
        and _chain_transport_fault(failure)
    ):
        _log.warning("chain_session_error kind=%s", type(failure).__name__)
        return
    loop.default_exception_handler(context)


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
        return await _observe(bt, substrate, client, context)
    finally:
        await client.close()


async def _observe(bt, substrate, client, context: ChainContext) -> MetagraphSnapshot:
    """One finalized metagraph observation over an already connected backend."""
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


class PersistentBittensorReader(BittensorReader):
    """One open chain connection for a long-running process (a receiver door), reused by every read.

    REG-UNAVAILABLE (TL 3-4 Nov): `BittensorReader` opens a new WebSocket for every read. A door refreshes its
    snapshot every 12 s and four doors share one IP, so the public endpoint's WebSocket-upgrade policy refused them
    (HTTP 429 ``ws_upgrade_60s``, retry after 60 s); the reader's in-read retries then outlived the 60 s snapshot
    freshness and a registration re-check found no current snapshot. This reader connects once, verifies the chain
    identity once per connection (every read still checks it, `_observe`), and keeps the connection open. A policy
    refusal starts a cool-down of the endpoint's Retry-After (else a doubling backoff from `_base_delay` to
    `_max_delay`) during which a read fails at once as PROVIDER_RATE_LIMITED without touching the endpoint; a dropped
    connection is reopened on the next read. The freshness window itself is unchanged (Validator 4 Nov 05:17). All
    reads run on the reader's own event-loop thread, one at a time, so callers on any thread or loop share it.
    """

    #: One connect-and-read may take at most this long (Validator 4 Nov 07:18): a half-open socket would otherwise
    #: block every later read, the not-graded failure again. A read past it drops the connection, fails typed
    #: PROVIDER_UNAVAILABLE, and the next read reconnects. An engineering bound, not a scientific value.
    _read_timeout = 20.0

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._start_lock = threading.Lock()
        self._loop = None
        self._serial = None
        self._open = None  # (substrate, client, context)
        self._cooldown_until = 0.0
        self._refusals = 0

    async def capture(self, context: ChainContext) -> MetagraphSnapshot:
        if context.network == LOCAL_PRACTICE:
            raise ChainFailure(FailureCode.IDENTITY)
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(self._read_open(context), loop)
        return await asyncio.wrap_future(future)

    def _ensure_loop(self):
        with self._start_lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                loop.set_exception_handler(session_exception_handler)
                threading.Thread(
                    target=loop.run_forever, name="chain-reader", daemon=True
                ).start()
                self._loop = loop
            return self._loop

    @staticmethod
    async def _close(client):
        try:
            await client.close()
        except Exception as failure:  # noqa: BLE001 - closing a broken connection
            _log.debug("chain connection close failed: %s", type(failure).__name__)

    async def _close_bounded(self, client):
        try:
            await asyncio.wait_for(self._close(client), 2.0)
        except TimeoutError:
            _log.debug("chain connection close timed out")

    async def _drop(self):
        opened, self._open = self._open, None
        if opened is not None:
            await self._close(opened[1])

    async def _read_open(self, context):
        if self._serial is None:
            self._serial = asyncio.Lock()
        async with self._serial:
            if self._clock() < self._cooldown_until:
                raise ChainFailure(FailureCode.RATE_LIMITED)
            bt = self._sdk()
            try:
                return await asyncio.wait_for(
                    self._connect_and_observe(bt, context), self._read_timeout
                )
            except TimeoutError:
                await self._drop()
                _log.warning(
                    "chain read exceeded %.0f s: connection dropped", self._read_timeout
                )
                raise ChainFailure(FailureCode.UNAVAILABLE) from None

    async def _connect_and_observe(self, bt, context):
        """Connect if needed, then one observation; bounded by `_read_timeout` in `_read_open`."""
        try:
            if self._open is None or self._open[2] != context:
                await self._drop()
                substrate = bt.RpcSubstrate(
                    context.endpoint,
                    fallback_endpoints=[],
                    archive_endpoints=[],
                    retry_forever=False,
                )
                client = bt.Client(context.endpoint, substrate=substrate)
                try:
                    await substrate.connect()
                except BaseException:
                    await self._close(client)
                    raise
                self._open = (substrate, client, context)
            substrate, client, _ = self._open
            snapshot = await _observe(bt, substrate, client, context)
        except bt.RpcPolicyError as refused:
            # An upgrade refused leaves nothing open; a request refused on an open connection keeps it.
            wait = _retry_after(getattr(refused, "retry_after", None))
            backoff = min(self._max_delay, self._base_delay * 2**self._refusals)
            self._refusals += 1
            self._cooldown_until = self._clock() + (
                wait if wait is not None else backoff
            )
            _log.warning(
                "chain read refused by the endpoint's policy: status=%s policy=%s reason=%s retry_after=%s",
                getattr(refused, "status_code", None),
                getattr(refused, "policy", None),
                getattr(refused, "reason", None),
                getattr(refused, "retry_after", None),
            )
            raise ChainFailure(FailureCode.RATE_LIMITED) from None
        except bt.RpcConnectionError:
            await self._drop()
            raise ChainFailure(FailureCode.UNAVAILABLE) from None
        except bt.ChainError:
            await self._drop()
            raise ChainFailure(FailureCode.CHAIN) from None
        except asyncio.CancelledError:
            # Cut off by the read timeout: forget the connection at once and close it in the background, bounded, so a
            # close that hangs on the same half-open socket cannot hold the reader.
            opened, self._open = self._open, None
            if opened is not None:
                asyncio.ensure_future(self._close_bounded(opened[1]))
            raise
        except BaseException:
            await self._drop()
            raise
        self._refusals = 0
        return snapshot

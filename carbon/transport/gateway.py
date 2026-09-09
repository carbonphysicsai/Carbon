"""Authenticated ingress to the existing MCP service, with no public listener."""

import time
from dataclasses import dataclass

from carbon.chain import ChainAdapter, ChainContext
from carbon.chain.auth import HotkeyVerifier
from carbon.fees import RequesterIdentity
from carbon.mcp.model import McpCall, McpField
from carbon.registry import ChallengeKey

from .models import (
    MAX_HEADERS,
    METHOD,
    PATH,
    AuthenticatedReceipt,
    TransportCode,
    TransportFailure,
    canonical,
    digest,
    parse_message,
)
from .store import ReceiptJournal


@dataclass(frozen=True, repr=False)
class ReceivedCall:
    receipt: AuthenticatedReceipt
    call: McpCall
    requester: RequesterIdentity


class AuthenticatedGateway:
    """Trusted composition injects the adapter, verifier, clock and dispatcher."""

    def __init__(
        self,
        context: ChainContext,
        challenge: ChallengeKey,
        receiver: str,
        adapter: ChainAdapter,
        verifier: HotkeyVerifier,
        journal: ReceiptJournal,
        *,
        clock_ns=time.time_ns,
    ):
        if journal.context != context:
            raise TransportFailure(TransportCode.CONTEXT)
        self.context = context
        self.challenge = challenge
        self.receiver = receiver
        self.adapter = adapter
        self.verifier = verifier
        self.journal = journal
        self.clock_ns = clock_ns

    async def receive(
        self, body: bytes, headers: dict[str, str], *, method=METHOD, path=PATH
    ):
        if method != METHOD or path != PATH:
            raise TransportFailure(TransportCode.CONTEXT)
        if type(headers) is not dict or len(headers) > 16:
            raise TransportFailure(TransportCode.MALFORMED)
        lowered = set()
        size = 0
        for key, value in headers.items():
            if type(key) is not str or type(value) is not str:
                raise TransportFailure(TransportCode.MALFORMED)
            size += len(key) + len(value)
            if (
                size > MAX_HEADERS
                or not key.isascii()
                or not value.isascii()
                or "\n" in value
                or "\r" in value
                or key.lower() in lowered
            ):
                raise TransportFailure(TransportCode.MALFORMED)
            lowered.add(key.lower())
        envelope = parse_message(body)
        expected = (
            self.context.network,
            self.context.genesis_hash,
            self.context.netuid,
            self.challenge.challenge_id,
            self.challenge.version,
        )
        observed = tuple(
            envelope[k]
            for k in (
                "network",
                "genesis",
                "netuid",
                "challenge_id",
                "challenge_version",
            )
        )
        if observed != expected:
            raise TransportFailure(TransportCode.CONTEXT)
        snapshot = await self.adapter.observe(
            minimum_finalized_block=self.journal.minimum_block()
        )
        now = self.clock_ns()
        if (
            snapshot.context != self.context
            or snapshot.snapshot_id != envelope["snapshot"]
        ):
            raise TransportFailure(TransportCode.CONTEXT)
        if (
            type(now) is not int
            or not -2000 <= now // 1000000 - snapshot.timestamp_ms <= 60000
        ):
            raise TransportFailure(TransportCode.STALE)
        if snapshot.resolve(self.receiver) is None:
            raise TransportFailure(TransportCode.IDENTITY)
        receipt = self.journal.admit(
            body,
            envelope,
            snapshot,
            now,
            lambda nonces: self.verifier.verify(
                headers,
                body,
                method=method,
                path=path,
                receiver=self.receiver,
                now_ns=now,
                nonce_store=nonces,
            ),
        )
        requester = RequesterIdentity(
            digest(
                canonical(
                    [
                        "carbon.authenticated.requester.v1",
                        self.context.genesis_hash,
                        self.context.netuid,
                        receipt.hotkey,
                        receipt.coldkey,
                        receipt.registered_at,
                    ]
                )
            )
        )
        call = McpCall(
            "1.0",
            envelope["tool"],
            tuple(McpField(key, value) for key, value in envelope["fields"].items()),
        )
        return ReceivedCall(receipt, call, requester)

    async def dispatch(self, body: bytes, headers: dict[str, str], service):
        received = await self.receive(body, headers)
        # Existing MCP owns output bounds, A7 admission and A6 disclosure. Do not
        # generically serialize the result or expose it to another requester.
        return received.receipt.ref, service.call(received.call, received.requester)

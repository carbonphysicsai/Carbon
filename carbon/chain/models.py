"""Immutable, read-only chain observations. No SDK dependency or authority grant."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Protocol
from urllib.parse import urlsplit


class FailureCode(str, Enum):
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "TRANSPORT_TIMEOUT"
    TRANSPORT = "TRANSPORT_FAILURE"
    CHAIN = "CHAIN_FAILURE"
    MALFORMED = "MALFORMED_RESPONSE"
    INCOMPLETE = "INCOMPLETE_RESPONSE"
    IDENTITY = "IDENTITY_MISMATCH"
    STALE = "STALE_SNAPSHOT"
    UNSUPPORTED = "UNSUPPORTED_CAPABILITY"


class ChainFailure(Exception):
    """Closed error; never retains a provider exception or its message."""

    def __init__(self, code: FailureCode):
        self.code = code
        super().__init__(code.value)


def hash256(value: object) -> str:
    if type(value) is not str or not re.fullmatch(r"0x[0-9a-f]{64}", value):
        raise ChainFailure(FailureCode.MALFORMED)
    return value


def uint(value: object, maximum: int = 2**64 - 1) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ChainFailure(FailureCode.MALFORMED)
    return value


def identifier(value: object) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        raise ChainFailure(FailureCode.MALFORMED)
    return value


@dataclass(frozen=True)
class ChainContext:
    network: str
    endpoint: str
    provider: str
    genesis_hash: str
    netuid: int

    def __post_init__(self) -> None:
        identifier(self.network)
        identifier(self.provider)
        hash256(self.genesis_hash)
        uint(self.netuid, 65535)
        url = urlsplit(self.endpoint)
        if (
            url.scheme not in ("ws", "wss")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        if self.network == "localnet" and url.hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            raise ChainFailure(FailureCode.IDENTITY)


@dataclass(frozen=True)
class Participant:
    uid: int
    hotkey: str
    coldkey: str
    registered_at: int

    def __post_init__(self) -> None:
        uint(self.uid, 65535)
        identifier(self.hotkey)
        identifier(self.coldkey)
        uint(self.registered_at)


@dataclass(frozen=True)
class MetagraphSnapshot:
    context: ChainContext
    finalized_block: int
    block_hash: str
    timestamp_ms: int
    participants: tuple[Participant, ...]

    def __post_init__(self) -> None:
        if type(self.context) is not ChainContext:
            raise ChainFailure(FailureCode.MALFORMED)
        uint(self.finalized_block)
        hash256(self.block_hash)
        uint(self.timestamp_ms)
        if type(self.participants) is not tuple or len(self.participants) > 65536:
            raise ChainFailure(FailureCode.MALFORMED)
        for index, member in enumerate(self.participants):
            if (
                type(member) is not Participant
                or member.uid != index
                or member.registered_at > self.finalized_block
            ):
                raise ChainFailure(FailureCode.MALFORMED)
        if len({p.hotkey for p in self.participants}) != len(self.participants):
            raise ChainFailure(FailureCode.IDENTITY)

    @property
    def snapshot_id(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def resolve(self, hotkey: str) -> Participant | None:
        return next((p for p in self.participants if p.hotkey == hotkey), None)

    def require_identity(
        self, previous: "MetagraphSnapshot", member: Participant
    ) -> Participant:
        """A recycled UID/hotkey registration never inherits the former identity."""
        if (
            self.context != previous.context
            or previous.resolve(member.hotkey) != member
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        if (
            self.finalized_block < previous.finalized_block
            or self.timestamp_ms < previous.timestamp_ms
        ):
            raise ChainFailure(FailureCode.STALE)
        if (
            self.finalized_block == previous.finalized_block
            and self.snapshot_id != previous.snapshot_id
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        current = self.resolve(member.hotkey)
        if current != member:
            raise ChainFailure(FailureCode.IDENTITY)
        return current


class ChainAdapter(Protocol):
    async def observe(self, *, minimum_finalized_block: int) -> MetagraphSnapshot:
        """Observe the provider's finalized state; no implicit freshness claim."""

"""Immutable, read-only chain observations. No SDK dependency or authority grant."""

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Protocol
from urllib.parse import urlsplit

#: The network and subnet this PROCESS binds, chosen once at import.
#:
#: The mainnet subnet now exists (finney netuid 116, Chain Auditor 5 Nov, F4),
#: so the one consolidated constant (it replaced six copies asserted across
#: `development_session` and `miner_mcp`) becomes the process's binding: every
#: guard that compares against it moves together, never one copy alone.
#:
#: ``CARBON_CHAIN_NETWORK`` names the row: unset (or empty) is testnet 567,
#: byte for byte as before; ``finney`` is netuid 116; anything else refuses at
#: import. `carbon.chain.networks` holds each row's chain id, genesis and
#: endpoints, and the genesis read at connect is the identity check.
NETWORK_ENVIRONMENT = "CARBON_CHAIN_NETWORK"
_NETUIDS = {"testnet": 567, "finney": 116}
CARBON_NETWORK = os.environ.get(NETWORK_ENVIRONMENT) or "testnet"

#: STAGING ONLY (H8 part 3, owner-accepted 6 Nov via the Lead; Validator-2 09:22): a process bound with
#: ``CARBON_CHAIN_NETWORK=localnet`` gets a third row for the disposable localnet (`carbon.chain.localnet`, netuid 2),
#: whose genesis is fresh per container, so the operator names it: ``CARBON_LOCALNET_GENESIS`` (0x + 64 hex, exact at
#: connect) and ``CARBON_LOCALNET_ENDPOINT`` (a loopback ws/wss URL with a port: the host's own node, never a remote
#: one). Every other process keeps exactly the testnet and finney rows, so nothing else can name localnet. It carries
#: no stage and no weights authority, and a live door or the weights loop refuses it (the H5 switch precheck).
LOCALNET = "localnet"
LOCALNET_NETUID = 2
LOCALNET_GENESIS_ENVIRONMENT = "CARBON_LOCALNET_GENESIS"
LOCALNET_ENDPOINT_ENVIRONMENT = "CARBON_LOCALNET_ENDPOINT"
LOCALNET_GENESIS = LOCALNET_ENDPOINT = None
if CARBON_NETWORK == LOCALNET:
    LOCALNET_GENESIS = os.environ.get(LOCALNET_GENESIS_ENVIRONMENT) or ""
    LOCALNET_ENDPOINT = os.environ.get(LOCALNET_ENDPOINT_ENVIRONMENT) or ""
    if not re.fullmatch(r"0x[0-9a-f]{64}", LOCALNET_GENESIS):
        raise RuntimeError("CARBON_LOCALNET_GENESIS must name the localnet's genesis")
    _endpoint = urlsplit(LOCALNET_ENDPOINT)
    try:
        _port = _endpoint.port
    except ValueError:
        _port = None
    if (
        _endpoint.scheme not in ("ws", "wss")
        or _endpoint.hostname not in ("127.0.0.1", "localhost", "::1")
        or _port is None
        or _endpoint.username
        or _endpoint.password
        or _endpoint.path not in ("", "/")
        or _endpoint.query
        or _endpoint.fragment
    ):
        raise RuntimeError("CARBON_LOCALNET_ENDPOINT must be the host's own node")
    _NETUIDS = {**_NETUIDS, LOCALNET: LOCALNET_NETUID}
if CARBON_NETWORK not in _NETUIDS:
    raise RuntimeError("CARBON_CHAIN_NETWORK names no registered network")
CARBON_NETUID = _NETUIDS[CARBON_NETWORK]


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
    #: The endpoint refused the read under its traffic or access policy
    #: (HTTP 429/403, WebSocket 1008, a JSON-RPC policy error): an
    #: infrastructure failure, retried with backoff, never a capability gap.
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"


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

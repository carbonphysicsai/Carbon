"""Versioned public request encoding. No scientific result projection."""

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum

from carbon.chain import ChainContext
from carbon.registry import ChallengeKey

PROTOCOL = "carbon.mcp.hotkey.v1"
METHOD = "POST"
PATH = "/carbon/v1/mcp"
MAX_BODY = 65536
MAX_HEADERS = 4096


class TransportCode(str, Enum):
    MALFORMED = "TRANSPORT_MALFORMED"
    CONTEXT = "TRANSPORT_CONTEXT"
    IDENTITY = "TRANSPORT_IDENTITY"
    STALE = "TRANSPORT_STALE"
    REPLAY = "TRANSPORT_REPLAY"
    CONFLICT = "TRANSPORT_CONFLICT"
    CAPACITY = "TRANSPORT_CAPACITY"
    RATE = "TRANSPORT_RATE"
    STORE = "TRANSPORT_STORE"


class TransportFailure(Exception):
    def __init__(self, code: TransportCode):
        self.code = code
        super().__init__(code.value)


def _invalid():
    raise TransportFailure(TransportCode.MALFORMED)


def _meter(value, depth=0, budget=None):
    budget = [4096] if budget is None else budget
    budget[0] -= 1
    if budget[0] < 0 or depth > 16:
        _invalid()
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                _invalid()
            _meter(key, depth + 1, budget)
            _meter(child, depth + 1, budget)
    elif type(value) is list:
        for child in value:
            _meter(child, depth + 1, budget)
    elif type(value) is str:
        if len(value) > MAX_BODY or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            _invalid()
    elif type(value) is int:
        if value.bit_length() > 64:
            _invalid()
    elif type(value) is float:
        if not math.isfinite(value):
            _invalid()
    elif value is not None and type(value) is not bool:
        _invalid()


def canonical(value) -> bytes:
    _meter(value)
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")
    if len(encoded) > MAX_BODY:
        _invalid()
    return encoded


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def _token(value):
    if type(value) is not str or not 1 <= len(value) <= 128:
        _invalid()
    if not all(c.isascii() and (c.isalnum() or c in "_.:-") for c in value):
        _invalid()
    return value


def parse_message(body: bytes) -> dict:
    if type(body) is not bytes or not 0 < len(body) <= MAX_BODY:
        _invalid()
    failed = False
    try:
        value = json.loads(body, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError):
        failed = True
    if failed:
        _invalid()
    if type(value) is not dict or canonical(value) != body:
        _invalid()
    expected = {
        "protocol",
        "network",
        "genesis",
        "netuid",
        "challenge_id",
        "challenge_version",
        "snapshot",
        "session",
        "request",
        "tool",
        "fields",
    }
    if set(value) != expected or value["protocol"] != PROTOCOL:
        _invalid()
    for key in expected - {"netuid", "fields"}:
        _token(value[key])
    if type(value["netuid"]) is not int or not 0 <= value["netuid"] <= 65535:
        _invalid()
    if type(value["fields"]) is not dict:
        _invalid()
    for key in ("challenge_id", "challenge_version"):
        if key in value["fields"] and value["fields"][key] != value[key]:
            raise TransportFailure(TransportCode.CONTEXT)
    return value


def message(
    context: ChainContext,
    snapshot_id: str,
    challenge: ChallengeKey,
    *,
    session: str,
    request: str,
    tool: str,
    fields: dict,
) -> bytes:
    body = canonical(
        {
            "protocol": PROTOCOL,
            "network": context.network,
            "genesis": context.genesis_hash,
            "netuid": context.netuid,
            "challenge_id": challenge.challenge_id,
            "challenge_version": challenge.version,
            "snapshot": snapshot_id,
            "session": session,
            "request": request,
            "tool": tool,
            "fields": fields,
        }
    )
    parse_message(body)
    return body


@dataclass(frozen=True)
class ReceiptRef:
    sequence: int
    digest: str


@dataclass(frozen=True, repr=False)
class AuthenticatedReceipt:
    """Journal-issued provenance, never submission/admission/acceptance authority."""

    ref: ReceiptRef
    body_digest: str
    hotkey: str
    coldkey: str
    uid: int
    registered_at: int
    snapshot_id: str
    finalized_block: int
    received_ns: int
    challenge_id: str
    challenge_version: str
    session: str
    request: str


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

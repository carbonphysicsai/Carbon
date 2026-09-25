"""Carbon service-key signatures for battery validator results (OD-6).

Testnet validators have no chain identity: they read the chain and sign what
they produce with a Carbon service key. The key is an operator-held file (32
raw Ed25519 bytes, owner-only, never printed or serialized), loaded the same
way as the private seed root.

Every signature is domain-separated by the payload `kind`, so a result can
never be replayed as a weight intent, or the reverse.

Weight intents are Phase A only (OD-4a): the one intent this module will sign
is ALL_BURN. Winner weights (OD-4b) are not authorized; asking for them is
refused here, not by convention.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

DOMAIN = b"carbon.battery.validator-signature.v1\x00"
KINDS = ("screening_result", "final_result", "weight_intent")
NETUID = 567


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


class ServiceKey:
    """An Ed25519 service key; never printed, pickled or serialized."""

    __slots__ = ("_key", "key_id", "public_key")

    def __init__(self, raw, *, _token=None):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        if _token is not _LOADED or type(raw) is not bytes or len(raw) != 32:
            raise TypeError("a ServiceKey comes only from ServiceKey.load")
        key = Ed25519PrivateKey.from_private_bytes(raw)
        public = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "public_key", public.hex())
        object.__setattr__(
            self,
            "key_id",
            "battery-validator-" + hashlib.sha256(public).hexdigest()[:16],
        )

    def __setattr__(self, name, value):
        raise AttributeError("a ServiceKey is immutable")

    def __repr__(self):
        return f"ServiceKey({self.key_id}, <redacted>)"

    def __reduce__(self):
        raise TypeError("a ServiceKey cannot be serialized")

    @staticmethod
    def load(path):
        path = Path(path)
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ValueError("the service key must be a regular file")
        if info.st_mode & 0o077:
            raise ValueError("the service key must be readable by its owner only")
        if info.st_size != 32:
            raise ValueError("the service key is exactly 32 bytes")
        return ServiceKey(path.read_bytes(), _token=_LOADED)

    @staticmethod
    def create(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(os.urandom(32))
        return ServiceKey.load(path)

    def sign(self, kind, payload):
        if kind not in KINDS:
            raise ValueError("unknown signature kind")
        body = {"kind": kind, "key_id": self.key_id, "payload": payload}
        message = DOMAIN + kind.encode() + b"\x00" + _canonical(body)
        return {
            **body,
            "public_key": self.public_key,
            "signature": self._key.sign(message).hex(),
        }


_LOADED = object()


def verify(signed):
    """True only for an untampered signature by the named public key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        public = bytes.fromhex(signed["public_key"])
        if signed["key_id"] != (
            "battery-validator-" + hashlib.sha256(public).hexdigest()[:16]
        ):
            return False
        body = {k: signed[k] for k in ("kind", "key_id", "payload")}
        message = DOMAIN + signed["kind"].encode() + b"\x00" + _canonical(body)
        Ed25519PublicKey.from_public_bytes(public).verify(
            bytes.fromhex(signed["signature"]), message
        )
    except (InvalidSignature, KeyError, ValueError, TypeError):
        return False
    return signed["kind"] in KINDS


def all_burn_intent(*, pool_version, reason):
    """The only weight intent Phase A allows (OD-4a): burn everything.

    The owner/publisher decides whether and when to publish it, within the
    recorded transaction window. This returns data; it sends nothing.
    """
    return {
        "schema": "carbon.battery.weight-intent.v1",
        "netuid": NETUID,
        "mode": "ALL_BURN",
        "phase": "A",
        "authority": "OWNER-BATTERY-TESTNET-01 OD-4a",
        "pool_version": pool_version,
        "reason": reason,
        "winner_weights": False,
    }


def winner_intent(*args, **kwargs):
    """OD-4b is not authorized: winner-weight intents do not exist yet."""
    raise PermissionError("winner-weight publication is not authorized (OD-4b)")

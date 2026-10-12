"""Read the validator's signed network snapshot and keep only what may be shown.

The snapshot is `carbon.validator.network-snapshot.v1`, as
`carbon.challenge_validator.network_snapshot.build` writes it (DASHBOARD-02
S3): the subnet's public state at one finalized block. The dashboard refuses
the whole document when one check fails; a refusal is never drawn in part
and never replaced by fixture data.

The checks:

1. the pinned schema;
2. an Ed25519 signature over `DOMAIN` + the canonical document without its
   `signature`, by a key pinned in the dashboard's trust (the feed's pinned
   keys: the validator signs both with its feed key). `DOMAIN` is the
   snapshot's own, never the feed's, so neither signature verifies as the
   other;
3. labels: DEVELOPMENT always, TESTNET exactly on testnet, FIXTURE exactly for
   fixtures;
4. fresh: the block's chain timestamp no older than `max_age_seconds` and not
   from the future;
5. the network, block and units well formed, every UID once in order, every
   amount a non-negative integer;
6. allow-listed fields only: anything else is dropped.

Display software only: nothing here ranks, scores, sets weights or settles.
Amounts are copied as given: incentive in u16, emission and stake in rao as
decimal strings (they can exceed a JavaScript number's exact range).
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from carbon.dashboard.feed import FIXTURE_PUBLIC_KEY, Trust, key_id

SCHEMA = "carbon.validator.network-snapshot.v1"
VIEW_SCHEMA = "carbon.dashboard.network.v1"
# network_snapshot.SnapshotKey's signed bytes: this prefix, then
# json.dumps(sort_keys=True, separators=(",", ":"), allow_nan=False), ASCII.
DOMAIN = b"carbon.validator.network-snapshot.v1\x00"
LABELS = ("DEVELOPMENT", "TESTNET")
FIXTURE_LABEL = "FIXTURE"
NETWORKS = ("testnet", "mainnet")
UNITS = {"incentive": "u16", "emission": "rao", "stake": "rao"}
#: Display freshness (DASHBOARD-02 S3, an engineering default the Worker's
#: `SNAPSHOT_MAX_AGE_SECONDS` may set within [MIN, MAX]): an operator timer
#: every few minutes stays well inside it.
MAX_AGE_SECONDS = 1800
MIN_MAX_AGE_SECONDS = 60
MAX_MAX_AGE_SECONDS = 86400
#: Clock skew allowed between the chain's timestamp and the reader's clock.
FUTURE_SKEW_SECONDS = 300
MAX_NEURONS = 4096
U16 = 65535

_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
_FIXTURE_HOTKEY = re.compile(r"fixture-[a-z0-9-]{1,32}")
_HASH = re.compile(r"0x[0-9a-f]{64}")
_HEX_SIGNATURE = re.compile(r"[0-9a-f]{128}")
_TEXT = re.compile(r"[^\x00-\x1f\x7f<>]{1,200}")

__all__ = [
    "DOMAIN",
    "FIXTURE_PUBLIC_KEY",
    "SCHEMA",
    "SnapshotRefused",
    "Trust",
    "project",
    "verify",
]


class SnapshotRefused(ValueError):
    """The whole snapshot is refused; `code` says why."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def canonical_bytes(document):
    body = {k: v for k, v in document.items() if k != "signature"}
    return (
        DOMAIN
        + json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def verify(document, trust):
    """Return the pinned hex key that signed the snapshot, or refuse it."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if type(document) is not dict or document.get("schema") != SCHEMA:
        raise SnapshotRefused("schema_unsupported")
    signature = document.get("signature")
    if type(signature) is not str or not _HEX_SIGNATURE.fullmatch(signature):
        raise SnapshotRefused("signature_missing")
    try:
        message = canonical_bytes(document)
    except (TypeError, ValueError) as exc:
        raise SnapshotRefused("not_canonical") from exc
    for public in sorted(trust.keys):
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(
                bytes.fromhex(signature), message
            )
        except InvalidSignature:
            continue
        return public
    raise SnapshotRefused("signature_invalid")


def _int(value, code, *, maximum=None):
    if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
        raise SnapshotRefused(code)
    return value


def _hash(value, code):
    if type(value) is not str or not _HASH.fullmatch(value):
        raise SnapshotRefused(code)
    return value


def _hotkey(value, trust):
    pattern = _FIXTURE_HOTKEY if trust.fixture else _SS58
    if type(value) is not str or not pattern.fullmatch(value):
        raise SnapshotRefused("hotkey_invalid")
    return value


def _dict(value, code):
    if type(value) is not dict:
        raise SnapshotRefused(code)
    return value


def project(document, trust, *, now_ms=None, max_age_seconds=MAX_AGE_SECONDS):
    """Verify a snapshot and return the dashboard's network view.

    Raises SnapshotRefused with a reason code; never returns a partial view.
    """
    signer = verify(document, trust)
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    network = _dict(document.get("network"), "network_invalid")
    name = network.get("name")
    if name not in NETWORKS:
        raise SnapshotRefused("network_invalid")
    network = {
        "name": name,
        "netuid": _int(network.get("netuid"), "network_invalid", maximum=U16),
        "genesis_hash": _hash(network.get("genesis_hash"), "network_invalid"),
    }
    labels = document.get("labels")
    allowed = set(LABELS) | ({FIXTURE_LABEL} if trust.fixture else set())
    if (
        type(labels) is not list
        or any(type(label) is not str for label in labels)
        or "DEVELOPMENT" not in labels
        or len(set(labels)) != len(labels)
        or not set(labels) <= allowed
        or (FIXTURE_LABEL in labels) != trust.fixture
        or ("TESTNET" in labels) != (name == "testnet")
    ):
        raise SnapshotRefused("labels_invalid")
    block = _dict(document.get("block"), "block_invalid")
    block = {
        "number": _int(block.get("number"), "block_invalid"),
        "hash": _hash(block.get("hash"), "block_invalid"),
        "timestamp_ms": _int(block.get("timestamp_ms"), "block_invalid"),
    }
    age_ms = now_ms - block["timestamp_ms"]
    if age_ms > max_age_seconds * 1000:
        raise SnapshotRefused("snapshot_stale")
    if age_ms < -FUTURE_SKEW_SECONDS * 1000:
        raise SnapshotRefused("snapshot_from_future")
    if document.get("units") != UNITS:
        raise SnapshotRefused("units_invalid")
    validator = _dict(document.get("validator"), "validator_invalid")
    validator = {"hotkey": _hotkey(validator.get("hotkey"), trust)}
    raw = document.get("neurons")
    if type(raw) is not list or len(raw) > MAX_NEURONS:
        raise SnapshotRefused("neurons_invalid")
    rows, seen = [], set()
    for index, neuron in enumerate(raw):
        neuron = _dict(neuron, "neurons_invalid")
        if _int(neuron.get("uid"), "neurons_invalid") != index:
            raise SnapshotRefused("neurons_invalid", f"uid {index}")
        hotkey = _hotkey(neuron.get("hotkey"), trust)
        if hotkey in seen:
            raise SnapshotRefused("neurons_invalid", "duplicate hotkey")
        seen.add(hotkey)
        permit = neuron.get("validator_permit")
        if type(permit) is not bool:
            raise SnapshotRefused("neurons_invalid", "validator_permit")
        rows.append(
            {
                "uid": index,
                "hotkey": hotkey,
                "incentive": _int(
                    neuron.get("incentive"), "neurons_invalid", maximum=U16
                ),
                "emission": str(_int(neuron.get("emission"), "neurons_invalid")),
                "stake": str(_int(neuron.get("stake"), "neurons_invalid")),
                "validator_permit": permit,
            }
        )
    generated_at = document.get("generated_at")
    if generated_at is not None and (
        type(generated_at) is not str or not _TEXT.fullmatch(generated_at)
    ):
        raise SnapshotRefused("generated_at_invalid")
    return {
        "schema": VIEW_SCHEMA,
        "source_schema": SCHEMA,
        "fixture": trust.fixture,
        "labels": list(labels),
        "network": network,
        "block": block,
        "validator": validator,
        "units": dict(UNITS),
        "neurons": rows,
        "summary": {
            "neurons": len(rows),
            "validators": sum(1 for row in rows if row["validator_permit"]),
        },
        "generated_at": generated_at,
        "snapshot": {
            "key_id": key_id(signer),
            "digest": "sha256:" + hashlib.sha256(canonical_bytes(document)).hexdigest(),
        },
    }

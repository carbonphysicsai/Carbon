"""A synthetic, signed network snapshot for testing the dashboard (DASHBOARD-02 S3).

Labelled FIXTURE, DEVELOPMENT and TESTNET. The hotkeys are `fixture-…`, which
can never be valid SS58 addresses; the genesis and block hashes are digests of
made-up strings; the incentive, emission and stake are made up. It is not a
reading of any chain.

It is signed by the dashboard's public fixture key (`fixtures.fixture_key`),
under the snapshot's own domain. `feed.Trust` refuses that key for
production, and a fixture trust accepts nothing else.
"""

from __future__ import annotations

import hashlib
import random

from carbon.dashboard import fixtures, snapshot

#: The fixture's chain timestamp. Tests project it with `now_ms` near this.
TIMESTAMP_MS = 1_791_000_000_000


def _hash(*parts):
    return "0x" + hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()


def snapshot_document(*, timestamp_ms=TIMESTAMP_MS, neurons=8, seed=1):
    """One synthetic snapshot in `network_snapshot`'s v1 shape, unsigned."""
    rng = random.Random(f"network-snapshot|{seed}")
    rows = []
    for uid in range(neurons):
        validator = uid < 2
        rows.append(
            {
                "uid": uid,
                "hotkey": (
                    f"fixture-validator-{uid:02d}"
                    if validator
                    else f"fixture-miner-{uid:02d}"
                ),
                "incentive": 0 if validator else rng.randint(0, 65535),
                "emission": rng.randint(0, 10**9),
                # Larger than a JavaScript number holds exactly.
                "stake": rng.randint(10**16, 10**18) if validator else 0,
                "validator_permit": validator,
            }
        )
    return {
        "schema": snapshot.SCHEMA,
        "labels": ["DEVELOPMENT", "TESTNET", "FIXTURE"],
        "validator": {
            "hotkey": "fixture-validator-00",
            "feed_key": snapshot.FIXTURE_PUBLIC_KEY,
        },
        "network": {
            "name": "testnet",
            "netuid": 567,
            "genesis_hash": _hash("fixture-genesis"),
        },
        "block": {
            "number": 6_000_000 + seed,
            "hash": _hash("fixture-block", seed),
            "timestamp_ms": timestamp_ms,
        },
        "units": dict(snapshot.UNITS),
        "neurons": rows,
        "generated_at": "2026-10-11T00:00:00Z",
    }


def sign(document, key=None):
    """Sign under the snapshot domain with the fixture key (or the key given,
    for refusal tests)."""
    body = {k: v for k, v in document.items() if k != "signature"}
    signature = (key or fixtures.fixture_key()).sign(snapshot.canonical_bytes(body))
    return {**body, "signature": signature.hex()}


def signed_snapshot(**kwargs):
    return sign(snapshot_document(**kwargs))

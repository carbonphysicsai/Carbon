"""A validator's signed network snapshot (DASHBOARD-02 S3): public chain data only.

The public dashboard shows the subnet's state next to the score feed: each
UID's hotkey, incentive, emission, validator permit and stake. Its Worker
cannot decode chain SCALE and may connect only to itself, so the validator
host reads the chain and publishes this signed document beside the feed. The
dashboard verifies it as it verifies the feed (`carbon/dashboard/snapshot.py`,
`carbon/dashboard/worker/snapshot.mjs`).

- **Schema:** `carbon.validator.network-snapshot.v1`, its own.
- **Signed bytes:** `SNAPSHOT_DOMAIN` followed by the snapshot without its
  `signature` field, canonical as the feed's (`feed_file.canonical`). The
  domain is never the feed's (`FEED_DOMAIN`): a snapshot signature never
  verifies as a feed, nor a feed signature as a snapshot.
- **Key:** the validator's feed key (`score_feed.FeedKey`), so the key the
  dashboard pins is unchanged. `SnapshotKey` signs under `SNAPSHOT_DOMAIN`
  only, and `build` signs with nothing else.
- **Chain reads:** the validator's existing public reads only, at one
  finalized block, genesis-checked, with its hash re-read after the reads as
  `carbon.chain.sdk.BittensorReader` does. The participants (uid, hotkey) are
  `carbon.chain.adapter.translate`'s, and incentive is the same metagraph
  read's per-UID column that `scripts/dev/canary/incentive.read_weights`
  uses; emission, stake and validator permit are that read's columns too. No
  raw RPC and no new dependency.
- **Contents:** the block number, hash and timestamp it was read at, the
  network, and per UID: uid, hotkey, incentive (u16), emission (rao), total
  stake (rao) and validator permit. Nothing else: no coldkey, axon address,
  commitment, submission, score, private or hidden state.
- **Never an input:** scoring and weights code never imports this module
  (`tests/invariants/test_network_snapshot_unreachable.py`).

    python -m carbon.challenge_validator.network_snapshot build --config SNAPSHOT.json --out network.json

The config (`CONFIG_SCHEMA`) names the chain context, the feed key's file and
the validator's hotkey:

    {"schema": "carbon.validator.network-snapshot.config.v1",
     "chain": {"network": "testnet", "endpoint": "wss://…", "provider": "…",
               "genesis_hash": "0x…", "netuid": 567},
     "key": "/path/to/FEED.key", "hotkey": "<validator SS58>"}

The operator runs it on a timer and uploads `--out` next to the feed
(`docs/development/DASHBOARD_CLOUDFLARE_SETUP.md`).

DEVELOPMENT only: no qualification, score, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import datetime
import json
import sys
from pathlib import Path

from .feed_file import canonical as _canonical
from .feed_file import write_feed
from .score_feed import FeedKey, FeedRefused

SNAPSHOT_SCHEMA = "carbon.validator.network-snapshot.v1"
SNAPSHOT_DOMAIN = b"carbon.validator.network-snapshot.v1\x00"
CONFIG_SCHEMA = "carbon.validator.network-snapshot.config.v1"
NETWORKS = ("testnet", "mainnet")
#: Each number's unit, carried in the document so a reader never guesses.
UNITS = {"incentive": "u16", "emission": "rao", "stake": "rao"}
#: The metagraph columns read, per UID (the SDK's metagraph runtime read).
COLUMNS = {
    "incentive": "incentives",
    "emission": "emission",
    "stake": "total_stake",
    "validator_permit": "validator_permit",
}


class SnapshotRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class SnapshotKey(FeedKey):
    """The validator's feed key, signing network snapshots: under
    `SNAPSHOT_DOMAIN` only, never the feed's domain."""

    def __repr__(self):
        return "SnapshotKey(<redacted>)"

    def sign(self, document):
        return self._key.sign(SNAPSHOT_DOMAIN + _canonical(document).encode()).hex()


# --- the chain read -----------------------------------------------------------------


async def _read(context):
    """`{"block", "block_hash", "timestamp_ms", "graph"}` at the finalized
    head: `chain.sdk._capture`'s read, keeping the metagraph's columns."""
    from contextlib import aclosing
    from importlib.metadata import version

    from carbon.chain.models import ChainFailure, FailureCode, hash256, uint
    from carbon.chain.sdk import SDK_VERSION

    if version("bittensor") != SDK_VERSION:
        raise ChainFailure(FailureCode.UNSUPPORTED)
    import bittensor as bt

    substrate = bt.RpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=[],
        retry_forever=False,
    )
    client = bt.Client(context.endpoint, substrate=substrate)
    try:
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
        # As `chain.sdk._capture`: a contradictory provider must not make the
        # number-pinned reads look like one hash-pinned observation.
        if (
            hash256(await substrate.block_hash(block)) != digest
            or hash256(await substrate.block_hash(0)) != genesis
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        return {
            "block": block,
            "block_hash": digest,
            "timestamp_ms": timestamp_ms,
            "graph": graph,
        }
    finally:
        await client.close()


def read_chain(context, *, fetch=None):
    """One reading of the subnet at its finalized head. `fetch(context)` is
    the async read; tests inject one. Any provider failure is infrastructure
    (`snapshot_chain_unavailable`), never data."""
    from carbon.chain.models import ChainContext

    if type(context) is not ChainContext:
        raise TypeError("a ChainContext is required")
    try:
        # A private event loop in a worker thread, as `chain.permits` reads.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, (fetch or _read)(context)).result()
    except Exception:  # noqa: BLE001 -- any provider error is infrastructure
        raise SnapshotRefused("snapshot_chain_unavailable") from None


# --- the document -------------------------------------------------------------------


def _column(graph, name, count, check):
    values = graph.get(COLUMNS[name])
    if type(values) is not list or len(values) != count:
        raise SnapshotRefused("snapshot_metagraph_incomplete")
    if not all(check(v) for v in values):
        raise SnapshotRefused("snapshot_metagraph_malformed")
    return values


def _amount(value):
    return type(value) is int and value >= 0


def neurons(context, reading):
    """The allow-listed per-UID rows of one reading. Participants are
    `chain.adapter.translate`'s (it checks the netuid, the count and every
    hotkey); every column must cover every UID."""
    from carbon.chain.adapter import translate
    from carbon.chain.models import ChainFailure

    if type(reading) is not dict:
        raise SnapshotRefused("snapshot_metagraph_malformed")
    graph = reading.get("graph")
    try:
        snapshot = translate(
            context,
            reading.get("block"),
            reading.get("block_hash"),
            reading.get("timestamp_ms"),
            graph,
        )
    except ChainFailure:
        raise SnapshotRefused("snapshot_metagraph_malformed") from None
    count = len(snapshot.participants)
    incentive = _column(graph, "incentive", count, lambda v: _amount(v) and v <= 65535)
    emission = _column(graph, "emission", count, _amount)
    stake = _column(graph, "stake", count, _amount)
    permits = _column(graph, "validator_permit", count, lambda v: type(v) is bool)
    return snapshot, [
        {
            "uid": p.uid,
            "hotkey": p.hotkey,
            "incentive": incentive[p.uid],
            "emission": emission[p.uid],
            "stake": stake[p.uid],
            "validator_permit": permits[p.uid],
        }
        for p in snapshot.participants
    ]


def build(reading, *, key, hotkey, context):
    """The signed snapshot of one chain reading. `key` is a `SnapshotKey`:
    the feed key, under the snapshot's own domain."""
    if type(key) is not SnapshotKey:
        raise SnapshotRefused("snapshot_key_not_a_snapshot_key")
    if context.network not in NETWORKS:
        raise SnapshotRefused("snapshot_network_unknown")
    if type(hotkey) is not str or not hotkey:
        raise SnapshotRefused("snapshot_hotkey_malformed")
    snapshot, rows = neurons(context, reading)
    generated = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    document = {
        "schema": SNAPSHOT_SCHEMA,
        "labels": ["DEVELOPMENT"]
        + (["TESTNET"] if context.network == "testnet" else []),
        "validator": {"hotkey": hotkey, "feed_key": key.public_key},
        "network": {
            "name": context.network,
            "netuid": context.netuid,
            "genesis_hash": context.genesis_hash,
        },
        "block": {
            "number": snapshot.finalized_block,
            "hash": snapshot.block_hash,
            "timestamp_ms": snapshot.timestamp_ms,
        },
        "units": dict(UNITS),
        "neurons": rows,
        "generated_at": generated,
    }
    return {**document, "signature": key.sign(document)}


def verify_snapshot(snapshot, pinned_key=None):
    """Whether a snapshot's signature is its feed key's under
    `SNAPSHOT_DOMAIN`. With `pinned_key`, it must name exactly that key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        if snapshot["schema"] != SNAPSHOT_SCHEMA:
            return False
        if pinned_key is not None and snapshot["validator"]["feed_key"] != pinned_key:
            return False
        body = {k: v for k, v in snapshot.items() if k != "signature"}
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(snapshot["validator"]["feed_key"])
        ).verify(
            bytes.fromhex(snapshot["signature"]),
            SNAPSHOT_DOMAIN + _canonical(body).encode(),
        )
    except (InvalidSignature, KeyError, TypeError, ValueError):
        return False
    return True


# --- the command line ---------------------------------------------------------------


def load_config(path):
    from carbon.chain.models import ChainContext, ChainFailure

    try:
        config = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        raise SnapshotRefused("snapshot_config_unreadable") from None
    if (
        type(config) is not dict
        or set(config) != {"schema", "chain", "key", "hotkey"}
        or config["schema"] != CONFIG_SCHEMA
        or type(config["chain"]) is not dict
        or type(config["key"]) is not str
        or type(config["hotkey"]) is not str
    ):
        raise SnapshotRefused("snapshot_config_malformed")
    try:
        context = ChainContext(**config["chain"])
    except (ChainFailure, TypeError):
        raise SnapshotRefused("snapshot_config_malformed") from None
    return {"context": context, "key": config["key"], "hotkey": config["hotkey"]}


def main(argv=None, *, fetch=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.network_snapshot")
    sub = parser.add_subparsers(dest="command", required=True)
    built = sub.add_parser("build")
    built.add_argument("--config", required=True)
    built.add_argument("--out", required=True, help="the signed snapshot file")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        key = SnapshotKey.load(config["key"])
        reading = read_chain(config["context"], fetch=fetch)
        snapshot = build(
            reading, key=key, hotkey=config["hotkey"], context=config["context"]
        )
        write_feed(args.out, snapshot)
    except (SnapshotRefused, FeedRefused) as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(
        json.dumps(
            {
                "block": snapshot["block"]["number"],
                "neurons": len(snapshot["neurons"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    # The package module's own main, as `score_feed` does.
    from carbon.challenge_validator.network_snapshot import main as _main

    sys.exit(_main())


__all__ = [
    "CONFIG_SCHEMA",
    "SNAPSHOT_DOMAIN",
    "SNAPSHOT_SCHEMA",
    "UNITS",
    "SnapshotKey",
    "SnapshotRefused",
    "build",
    "neurons",
    "read_chain",
    "verify_snapshot",
]

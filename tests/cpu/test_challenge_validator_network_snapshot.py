"""DASHBOARD-02 S3: the validator's signed network snapshot, built and signed.

The chain read is a fake reader returning the SDK metagraph read's shape: no
network, chain or spend. The snapshot is signed with the feed key under its
own domain, and neither domain's signature verifies as the other's. Not a
security audit (AGENTS.md §13).
"""

from __future__ import annotations

import copy
import json

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from carbon.chain.models import ChainContext, ChainFailure, FailureCode
from carbon.challenge_validator import feed_file
from carbon.challenge_validator import network_snapshot as ns
from carbon.challenge_validator.score_feed import FeedKey
from carbon.dashboard import feed as dashboard_feed
from carbon.dashboard import snapshot as dashboard_snapshot

GENESIS = "0x" + "8f" * 32
CONTEXT = ChainContext("testnet", "wss://chain.example:443", "test", GENESIS, 567)
BLOCK = 6_123_456
BLOCK_HASH = "0x" + "ab" * 32
TIMESTAMP_MS = 1_791_000_000_000
VALIDATOR = "5" + "V" * 45


def _hotkey(uid):
    return "5" + "G" * 43 + "A" + "123456789"[uid]


def _graph(n=4):
    """The SDK metagraph read's shape, with fields the snapshot never takes."""
    return {
        "netuid": 567,
        "num_uids": n,
        "hotkeys": [_hotkey(uid) for uid in range(n)],
        "coldkeys": ["5" + "C" * 44 + "123456789"[uid] for uid in range(n)],
        "block_at_registration": [100 + uid for uid in range(n)],
        "incentives": [0, 0, 40_000, 25_535][:n],
        "emission": [0, 10, 2_000_000, 1_000_000][:n],
        # Beyond a JavaScript number's exact range on purpose.
        "total_stake": [123_456_789_012_345_678_901, 5, 0, 0][:n],
        "validator_permit": [True, True, False, False][:n],
        "dividends": [65535, 0, 0, 0][:n],
        "axons": [{"ip": "10.1.2.3", "port": 8091}] * n,
        "pruning_score": [1] * n,
    }


def _reading(graph=None):
    return {
        "block": BLOCK,
        "block_hash": BLOCK_HASH,
        "timestamp_ms": TIMESTAMP_MS,
        "graph": _graph() if graph is None else graph,
    }


def _fake(reading):
    async def fetch(context):
        assert context == CONTEXT
        return copy.deepcopy(reading)

    return fetch


@pytest.fixture
def key(tmp_path):
    return ns.SnapshotKey.create(tmp_path / "feed.key")


def _build(key, reading=None):
    found = ns.read_chain(CONTEXT, fetch=_fake(reading or _reading()))
    return ns.build(found, key=key, hotkey=VALIDATOR, context=CONTEXT)


def test_snapshot_is_signed_and_verifies_under_the_pinned_feed_key(key):
    snapshot = _build(key)
    assert snapshot["schema"] == "carbon.validator.network-snapshot.v1"
    assert snapshot["labels"] == ["DEVELOPMENT", "TESTNET"]
    assert snapshot["block"] == {
        "number": BLOCK,
        "hash": BLOCK_HASH,
        "timestamp_ms": TIMESTAMP_MS,
    }
    assert snapshot["network"] == {
        "name": "testnet",
        "netuid": 567,
        "genesis_hash": GENESIS,
    }
    assert snapshot["validator"] == {"hotkey": VALIDATOR, "feed_key": key.public_key}
    assert ns.verify_snapshot(snapshot, pinned_key=key.public_key)
    assert not ns.verify_snapshot(snapshot, pinned_key="00" * 32)
    # The dashboard accepts it under the same pinned key.
    trust = dashboard_feed.Trust(keys=frozenset({key.public_key}))
    view = dashboard_snapshot.project(snapshot, trust, now_ms=TIMESTAMP_MS + 1000)
    assert view["block"]["number"] == BLOCK
    assert view["neurons"][0]["stake"] == "123456789012345678901"
    assert view["summary"] == {"neurons": 4, "validators": 2}


def test_snapshot_carries_only_allow_listed_public_fields(key):
    snapshot = _build(key)
    for row in snapshot["neurons"]:
        assert set(row) == {
            "uid",
            "hotkey",
            "incentive",
            "emission",
            "stake",
            "validator_permit",
        }
    assert snapshot["neurons"][2] == {
        "uid": 2,
        "hotkey": _hotkey(2),
        "incentive": 40_000,
        "emission": 2_000_000,
        "stake": 0,
        "validator_permit": False,
    }
    text = json.dumps(snapshot)
    for absent in ("coldkey", "5" + "C" * 44, "10.1.2.3", "axon", "dividends", "prun"):
        assert absent not in text
    assert set(snapshot) == {
        "schema",
        "labels",
        "validator",
        "network",
        "block",
        "units",
        "neurons",
        "generated_at",
        "signature",
    }


def test_tampering_breaks_the_signature(key):
    snapshot = _build(key)
    snapshot["neurons"][2]["incentive"] = 65535
    assert not ns.verify_snapshot(snapshot, pinned_key=key.public_key)


def test_a_snapshot_signature_never_verifies_as_a_feed_and_back(tmp_path):
    """Domain separation, both ways, with one and the same feed key."""
    snap_key = ns.SnapshotKey.create(tmp_path / "feed.key")
    feed_key = FeedKey.load(tmp_path / "feed.key")
    assert snap_key.public_key == feed_key.public_key
    assert ns.SNAPSHOT_DOMAIN != feed_file.FEED_DOMAIN
    assert dashboard_snapshot.DOMAIN == ns.SNAPSHOT_DOMAIN
    assert dashboard_snapshot.SCHEMA == ns.SNAPSHOT_SCHEMA
    public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(feed_key.public_key))

    # A snapshot's signature is not a feed signature over the same bytes...
    snapshot = _build(snap_key)
    body = {k: v for k, v in snapshot.items() if k != "signature"}
    with pytest.raises(InvalidSignature):
        public.verify(
            bytes.fromhex(snapshot["signature"]),
            feed_file.FEED_DOMAIN + feed_file.canonical(body).encode(),
        )
    assert not feed_file.verify_feed(snapshot)
    assert not feed_file.verify_feed(snapshot, pinned_key=feed_key.public_key)
    # ...and the feed key's feed signature over a snapshot's bytes is no
    # snapshot signature.
    forged = {**body, "signature": feed_key.sign(body)}
    assert not ns.verify_snapshot(forged)
    trust = dashboard_feed.Trust(keys=frozenset({feed_key.public_key}))
    with pytest.raises(dashboard_snapshot.SnapshotRefused) as refused:
        dashboard_snapshot.verify(forged, trust)
    assert refused.value.code == "signature_invalid"

    # The other way: a feed-shaped document the snapshot key signed.
    feed_body = {
        "schema": feed_file.FEED_SCHEMA,
        "validator": {"hotkey": VALIDATOR, "feed_key": feed_key.public_key},
        "challenge": {"id": "x"},
    }
    as_feed = {**feed_body, "signature": feed_key.sign(feed_body)}
    assert feed_file.verify_feed(as_feed, pinned_key=feed_key.public_key)
    crossed = {**feed_body, "signature": snap_key.sign(feed_body)}
    assert not feed_file.verify_feed(crossed)
    with pytest.raises(dashboard_feed.FeedRefused) as refused:
        dashboard_feed.verify(crossed, trust)
    assert refused.value.code == "signature_invalid"


def test_build_signs_with_a_snapshot_key_only(tmp_path, key):
    plain = FeedKey.load(tmp_path / "feed.key")
    reading = ns.read_chain(CONTEXT, fetch=_fake(_reading()))
    with pytest.raises(ns.SnapshotRefused) as refused:
        ns.build(reading, key=plain, hotkey=VALIDATOR, context=CONTEXT)
    assert refused.value.code == "snapshot_key_not_a_snapshot_key"
    assert "<redacted>" in repr(key)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda g: g.pop("incentives"), "snapshot_metagraph_incomplete"),
        (lambda g: g["total_stake"].pop(), "snapshot_metagraph_incomplete"),
        (
            lambda g: g["incentives"].__setitem__(1, 65536),
            "snapshot_metagraph_malformed",
        ),
        (lambda g: g["emission"].__setitem__(1, True), "snapshot_metagraph_malformed"),
        (lambda g: g["emission"].__setitem__(1, 1.5), "snapshot_metagraph_malformed"),
        (lambda g: g["total_stake"].__setitem__(1, -1), "snapshot_metagraph_malformed"),
        (
            lambda g: g["validator_permit"].__setitem__(1, 1),
            "snapshot_metagraph_malformed",
        ),
        (lambda g: g.__setitem__("netuid", 1), "snapshot_metagraph_malformed"),
        (
            lambda g: g["hotkeys"].__setitem__(1, _hotkey(0)),
            "snapshot_metagraph_malformed",
        ),
    ],
)
def test_an_incomplete_or_malformed_metagraph_is_refused(key, change, code):
    graph = _graph()
    change(graph)
    with pytest.raises(ns.SnapshotRefused) as refused:
        _build(key, _reading(graph))
    assert refused.value.code == code


@pytest.mark.parametrize(
    "error", [ChainFailure(FailureCode.IDENTITY), RuntimeError("x")]
)
def test_a_failed_chain_read_is_infrastructure(error):
    async def fetch(context):
        raise error

    with pytest.raises(ns.SnapshotRefused) as refused:
        ns.read_chain(CONTEXT, fetch=fetch)
    assert refused.value.code == "snapshot_chain_unavailable"


def test_a_localnet_context_is_refused(key):
    local = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", GENESIS, 567)
    with pytest.raises(ns.SnapshotRefused) as refused:
        ns.build(_reading(), key=key, hotkey=VALIDATOR, context=local)
    assert refused.value.code == "snapshot_network_unknown"


def _config(tmp_path, **extra):
    path = tmp_path / "snapshot.json"
    config = {
        "schema": ns.CONFIG_SCHEMA,
        "chain": {
            "network": CONTEXT.network,
            "endpoint": CONTEXT.endpoint,
            "provider": CONTEXT.provider,
            "genesis_hash": CONTEXT.genesis_hash,
            "netuid": CONTEXT.netuid,
        },
        "key": str(tmp_path / "feed.key"),
        "hotkey": VALIDATOR,
        **extra,
    }
    path.write_text(json.dumps(config))
    return path


def test_the_command_builds_signs_and_writes(tmp_path, key, capsys):
    out = tmp_path / "network.json"
    code = ns.main(
        ["build", "--config", str(_config(tmp_path)), "--out", str(out)],
        fetch=_fake(_reading()),
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"block": BLOCK, "neurons": 4}
    written = json.loads(out.read_text())
    assert ns.verify_snapshot(written, pinned_key=key.public_key)
    assert "10.1.2.3" not in out.read_text()


def test_the_command_refuses_a_malformed_config(tmp_path, key, capsys):
    out = tmp_path / "network.json"
    code = ns.main(
        ["build", "--config", str(_config(tmp_path, extra=1)), "--out", str(out)],
        fetch=_fake(_reading()),
    )
    assert code == 2
    assert json.loads(capsys.readouterr().out) == {
        "refused": "snapshot_config_malformed"
    }
    assert not out.exists()


def test_the_command_refuses_a_key_others_can_read(tmp_path, key, capsys):
    (tmp_path / "feed.key").chmod(0o644)
    code = ns.main(
        [
            "build",
            "--config",
            str(_config(tmp_path)),
            "--out",
            str(tmp_path / "n.json"),
        ],
        fetch=_fake(_reading()),
    )
    assert code == 2
    assert json.loads(capsys.readouterr().out) == {"refused": "feed_key_not_owner_only"}

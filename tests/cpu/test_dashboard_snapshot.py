"""DASHBOARD-02 S3: the dashboard reads the signed network snapshot.

`carbon/dashboard/snapshot.py` verifies the validator's network snapshot and
keeps only allow-listed fields; `worker/snapshot.mjs` is its JavaScript port.
These tests check the reader's refusals (tampered, stale, from the future,
the feed's domain, the fixture key in production, every malformed field),
hold the Python and JavaScript readers equal on every case, and check the
Worker's `/data/network.json`: 404 while SNAPSHOT_URLS is unset, a refused
snapshot listed with its reason and no data, never a fixture build or key.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from carbon.dashboard import feed, fixtures, snapshot
from carbon.dashboard import snapshot_fixtures as sfx

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tests" / "cpu" / "dashboard_snapshot_check.mjs"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed here")
NOW = sfx.TIMESTAMP_MS + 60_000
URL = "https://validator.example/valv2/network.json"


def _public(key):
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


def _python(text, trust, max_age=snapshot.MAX_AGE_SECONDS, now=NOW):
    try:
        view = snapshot.project(
            json.loads(text), trust, now_ms=now, max_age_seconds=max_age
        )
    except snapshot.SnapshotRefused as refused:
        return {"code": refused.code}
    return {"view": json.loads(json.dumps(view))}


def _code(document, trust, **kwargs):
    with pytest.raises(snapshot.SnapshotRefused) as refused:
        snapshot.project(document, trust, now_ms=kwargs.pop("now", NOW), **kwargs)
    return refused.value.code


def _feed_signed(body, key=None):
    """`body` signed under the score feed's domain, not the snapshot's."""
    body = {k: v for k, v in body.items() if k != "signature"}
    signature = (key or fixtures.fixture_key()).sign(feed.canonical_bytes(body))
    return {**body, "signature": signature.hex()}


def _ss58(uid):
    return "5" + "G" * 43 + "A" + "123456789"[uid]


def _production(document, key, *, timestamp_ms=None):
    """The fixture made production-shaped: SS58 hotkeys, no FIXTURE label,
    signed by `key`."""
    body = copy.deepcopy(document)
    body["labels"] = [label for label in body["labels"] if label != "FIXTURE"]
    for row in body["neurons"]:
        row["hotkey"] = _ss58(row["uid"])
    body["validator"] = {"hotkey": _ss58(0), "feed_key": _public(key)}
    if timestamp_ms is not None:
        body["block"]["timestamp_ms"] = timestamp_ms
    return sfx.sign(body, key)


# --- the Python reader -------------------------------------------------------------


def test_the_fixture_snapshot_verifies_and_projects():
    view = snapshot.project(sfx.signed_snapshot(), fixtures.fixture_trust(), now_ms=NOW)
    assert view["schema"] == "carbon.dashboard.network.v1"
    assert view["fixture"] is True
    assert view["labels"] == ["DEVELOPMENT", "TESTNET", "FIXTURE"]
    assert view["network"]["netuid"] == 567
    assert view["block"]["timestamp_ms"] == sfx.TIMESTAMP_MS
    assert view["summary"] == {"neurons": 8, "validators": 2}
    stake = view["neurons"][0]["stake"]
    assert type(stake) is str and int(stake) > 2**53
    assert view["snapshot"]["key_id"] == feed.key_id(feed.FIXTURE_PUBLIC_KEY)


def test_only_allow_listed_fields_are_kept():
    body = sfx.snapshot_document()
    body["operator_note"] = "private"
    body["submissions"] = [{"hidden": "case-1"}]
    body["validator"]["endpoint"] = "10.9.9.9"
    body["network"]["endpoint"] = "wss://10.9.9.9"
    body["block"]["extrinsics"] = ["0xdead"]
    body["neurons"][3]["coldkey"] = "fixture-coldkey"
    body["neurons"][3]["axon"] = {"ip": "10.9.9.9"}
    view = snapshot.project(sfx.sign(body), fixtures.fixture_trust(), now_ms=NOW)
    text = json.dumps(view)
    for absent in ("private", "hidden", "case-1", "10.9.9.9", "coldkey", "0xdead"):
        assert absent not in text
    assert set(view) == {
        "schema",
        "source_schema",
        "fixture",
        "labels",
        "network",
        "block",
        "validator",
        "units",
        "neurons",
        "summary",
        "generated_at",
        "snapshot",
    }
    assert set(view["validator"]) == {"hotkey"}
    assert set(view["network"]) == {"name", "netuid", "genesis_hash"}
    assert set(view["block"]) == {"number", "hash", "timestamp_ms"}
    for row in view["neurons"]:
        assert set(row) == {
            "uid",
            "hotkey",
            "incentive",
            "emission",
            "stake",
            "validator_permit",
        }


def test_a_tampered_snapshot_is_refused():
    signed = sfx.signed_snapshot()
    signed["neurons"][4]["incentive"] = 65535
    assert _code(signed, fixtures.fixture_trust()) == "signature_invalid"


def test_a_stale_or_future_snapshot_is_refused():
    trust = fixtures.fixture_trust()
    signed = sfx.signed_snapshot()
    edge = sfx.TIMESTAMP_MS + snapshot.MAX_AGE_SECONDS * 1000
    assert snapshot.project(signed, trust, now_ms=edge)["block"]
    assert _code(signed, trust, now=edge + 1) == "snapshot_stale"
    assert _code(signed, trust, max_age_seconds=59) == "snapshot_stale"
    skew = sfx.TIMESTAMP_MS - snapshot.FUTURE_SKEW_SECONDS * 1000
    assert snapshot.project(signed, trust, now_ms=skew)["block"]
    assert _code(signed, trust, now=skew - 1) == "snapshot_from_future"


def test_the_feed_domain_never_verifies_as_a_snapshot_and_back():
    trust = fixtures.fixture_trust()
    # A snapshot body signed as a feed is refused as a snapshot.
    crossed = _feed_signed(sfx.snapshot_document())
    assert _code(crossed, trust) == "signature_invalid"
    # A feed signed as a snapshot is refused as a feed.
    board = fixtures.board_document("fixture-challenge-alpha", "cpu", seed=2)
    as_snapshot = sfx.sign(board)
    with pytest.raises(feed.FeedRefused) as refused:
        feed.project(as_snapshot, trust)
    assert refused.value.code == "signature_invalid"
    # And each schema is refused by the other reader before any signature.
    with pytest.raises(feed.FeedRefused) as refused:
        feed.project(sfx.signed_snapshot(), trust)
    assert refused.value.code == "schema_unsupported"
    assert _code(fixtures.sign(board), trust) == "schema_unsupported"
    assert snapshot.DOMAIN != feed.DOMAIN


def test_the_fixture_key_is_refused_in_production():
    with pytest.raises(ValueError):
        feed.Trust(keys=frozenset({feed.FIXTURE_PUBLIC_KEY}))
    key = Ed25519PrivateKey.generate()
    production = feed.Trust(keys=frozenset({_public(key)}))
    # The fixture, signed by the fixture key: not a production signature.
    assert _code(sfx.signed_snapshot(), production) == "signature_invalid"
    # A FIXTURE-labelled snapshot under a production key: refused.
    assert _code(sfx.sign(sfx.snapshot_document(), key), production) == (
        "labels_invalid"
    )
    # Fixture hotkeys under a production key: refused.
    unlabelled = sfx.snapshot_document()
    unlabelled["labels"] = ["DEVELOPMENT", "TESTNET"]
    assert _code(sfx.sign(unlabelled, key), production) == "hotkey_invalid"
    # A production snapshot under the fixture trust: refused.
    good = _production(sfx.snapshot_document(), key)
    assert snapshot.project(good, production, now_ms=NOW)["fixture"] is False
    assert _code(good, fixtures.fixture_trust()) == "signature_invalid"


def _variants():
    """Unsigned fixture snapshots, each meant to be refused or accepted."""
    out = [("accepted", sfx.snapshot_document())]

    def edit(name, change):
        body = sfx.snapshot_document()
        change(body)
        out.append((name, body))

    edit("extra", lambda b: b["neurons"][0].__setitem__("coldkey", "x"))
    edit("no_testnet", lambda b: b.__setitem__("labels", ["DEVELOPMENT", "FIXTURE"]))
    edit("mainnet_testnet", lambda b: b["network"].__setitem__("name", "mainnet"))
    edit("localnet", lambda b: b["network"].__setitem__("name", "localnet"))
    edit("netuid_big", lambda b: b["network"].__setitem__("netuid", 70000))
    edit(
        "genesis_upper",
        lambda b: b["network"].__setitem__("genesis_hash", "0x" + "A" * 64),
    )
    edit("block_float", lambda b: b["block"].__setitem__("number", 6.0))
    edit("block_hash_short", lambda b: b["block"].__setitem__("hash", "0xab"))
    edit("units", lambda b: b["units"].__setitem__("stake", "tao"))
    edit("units_extra", lambda b: b["units"].__setitem__("dividends", "u16"))
    edit("incentive_big", lambda b: b["neurons"][3].__setitem__("incentive", 65536))
    edit("emission_negative", lambda b: b["neurons"][3].__setitem__("emission", -1))
    edit("stake_float", lambda b: b["neurons"][3].__setitem__("stake", 1.5))
    edit("stake_bool", lambda b: b["neurons"][3].__setitem__("stake", True))
    edit("permit_int", lambda b: b["neurons"][3].__setitem__("validator_permit", 1))
    edit("uid_order", lambda b: b["neurons"].reverse())
    edit(
        "duplicate",
        lambda b: b["neurons"][3].__setitem__("hotkey", b["neurons"][2]["hotkey"]),
    )
    edit("markup_hotkey", lambda b: b["neurons"][3].__setitem__("hotkey", "<b>x</b>"))
    edit("neurons_dict", lambda b: b.__setitem__("neurons", {}))
    edit("validator_list", lambda b: b.__setitem__("validator", []))
    edit("generated_markup", lambda b: b.__setitem__("generated_at", "<x>"))
    edit("generated_absent", lambda b: b.pop("generated_at"))
    edit("non_ascii", lambda b: b.__setitem__("generated_at", "règle·ü"))
    edit("empty", lambda b: b.__setitem__("neurons", []))
    edit("stale", lambda b: b["block"].__setitem__("timestamp_ms", NOW - 1_800_001))
    edit("future", lambda b: b["block"].__setitem__("timestamp_ms", NOW + 300_001))
    return out


def test_every_variant_is_refused_with_its_code():
    trust = fixtures.fixture_trust()
    codes = {
        name: _python(json.dumps(sfx.sign(body)), trust).get("code")
        for name, body in _variants()
    }
    assert codes == {
        "accepted": None,
        "extra": None,
        "no_testnet": "labels_invalid",
        "mainnet_testnet": "labels_invalid",
        "localnet": "network_invalid",
        "netuid_big": "network_invalid",
        "genesis_upper": "network_invalid",
        "block_float": "block_invalid",
        "block_hash_short": "block_invalid",
        "units": "units_invalid",
        "units_extra": "units_invalid",
        "incentive_big": "neurons_invalid",
        "emission_negative": "neurons_invalid",
        "stake_float": "neurons_invalid",
        "stake_bool": "neurons_invalid",
        "permit_int": "neurons_invalid",
        "uid_order": "neurons_invalid",
        "duplicate": "neurons_invalid",
        "markup_hotkey": "hotkey_invalid",
        "neurons_dict": "neurons_invalid",
        "validator_list": "validator_invalid",
        "generated_markup": "generated_at_invalid",
        "generated_absent": None,
        "non_ascii": None,
        "empty": None,
        "stale": "snapshot_stale",
        "future": "snapshot_from_future",
    }


# --- Python and JavaScript held equal ----------------------------------------------


def _node(spec, tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    result = subprocess.run(
        [NODE, str(CHECK), str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@needs_node
@pytest.mark.parametrize("indent", [None, 1])
def test_worker_projection_matches_snapshot_py(tmp_path, indent):
    trust = fixtures.fixture_trust()
    keys = sorted(trust.keys)
    items, expected = [], []
    for name, body in _variants():
        text = json.dumps(sfx.sign(body), indent=indent)
        items.append({"text": text, "fixture": True, "keys": keys})
        expected.append((name, _python(text, trust)))
    tampered = sfx.signed_snapshot()
    tampered["block"]["number"] = 7
    extra = [
        ("tampered", json.dumps(tampered), None),
        ("feed_domain", json.dumps(_feed_signed(sfx.snapshot_document())), None),
        ("short_max_age", json.dumps(sfx.signed_snapshot()), 59),
    ]
    for name, text, max_age in extra:
        items.append({"text": text, "fixture": True, "keys": keys, "max_age": max_age})
        expected.append(
            (name, _python(text, trust, max_age or snapshot.MAX_AGE_SECONDS))
        )
    got = _node({"mode": "project", "now_ms": NOW, "items": items}, tmp_path)
    for (name, want), have in zip(expected, got, strict=True):
        assert have == want, name
    codes = {name: want.get("code") for name, want in expected}
    assert codes["accepted"] is None and codes["tampered"] == "signature_invalid"
    assert codes["feed_domain"] == "signature_invalid"
    assert codes["short_max_age"] == "snapshot_stale"


@needs_node
def test_worker_projection_matches_for_a_production_key(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    text = json.dumps(_production(sfx.snapshot_document(), key))
    (have,) = _node(
        {
            "mode": "project",
            "now_ms": NOW,
            "items": [{"text": text, "fixture": False, "keys": [_public(key)]}],
        },
        tmp_path,
    )
    assert have == _python(text, trust)
    assert have["view"]["neurons"][0]["stake"] == str(
        sfx.snapshot_document()["neurons"][0]["stake"]
    )


@needs_node
def test_the_worker_feed_reader_refuses_a_snapshot_signed_feed(tmp_path):
    trust = fixtures.fixture_trust()
    board = fixtures.board_document("fixture-challenge-alpha", "cpu", seed=2)
    items = [
        {
            "text": json.dumps(sfx.sign(board)),
            "fixture": True,
            "keys": sorted(trust.keys),
        },
        {
            "text": json.dumps(fixtures.sign(board)),
            "fixture": True,
            "keys": sorted(trust.keys),
        },
    ]
    crossed, own = _node({"mode": "feed", "items": items}, tmp_path)
    assert crossed == {"code": "signature_invalid"}
    assert "board" in own


# --- the Worker's /data/network.json -----------------------------------------------


def _site(tmp_path, *, fixture=False):
    site = tmp_path / "site"
    (site / "data").mkdir(parents=True)
    (site / "data" / "index.json").write_text(
        json.dumps(
            {"schema": "carbon.dashboard.index.v1", "fixture": fixture, "boards": []}
        )
    )
    (site / "index.html").write_text("<!doctype html><title>x</title>\n")
    return str(site)


def _worker(tmp_path, site, env, feeds, requests):
    return _node(
        {
            "mode": "worker",
            "site": site,
            "env": env,
            "feeds": feeds,
            "requests": requests,
        },
        tmp_path,
    )


@needs_node
def test_worker_serves_a_verified_snapshot_and_never_unverified_data(tmp_path):
    key = Ed25519PrivateKey.generate()
    now = int(time.time() * 1000)
    good = _production(sfx.snapshot_document(), key, timestamp_ms=now)
    site = _site(tmp_path)
    env = {"SNAPSHOT_URLS": URL, "FEED_KEYS": _public(key)}
    (response,) = _worker(
        tmp_path, site, env, {URL: json.dumps(good)}, ["/data/network.json"]
    )
    assert response["status"] == 200
    assert "frame-ancestors 'none'" in response["headers"]["content-security-policy"]
    body = json.loads(response["body"])
    assert body["schema"] == "carbon.dashboard.network-index.v1"
    assert body["fixture"] is False
    (entry,) = body["snapshots"]
    assert entry["state"] == "ACCEPTED" and entry["summary"]["neurons"] == 8
    # Tampered, stale or unreachable: listed with the reason, and no data.
    tampered = copy.deepcopy(good)
    tampered["neurons"][5]["emission"] = 1
    stale = _production(sfx.snapshot_document(), key, timestamp_ms=now - 7_200_000)
    for feeds, code in (
        ({URL: json.dumps(tampered)}, "signature_invalid"),
        ({URL: json.dumps(stale)}, "snapshot_stale"),
        ({URL: json.dumps(_feed_signed(good, key))}, "signature_invalid"),
        ({}, "snapshot_unavailable"),
        ({URL: "{not json"}, "not_canonical"),
    ):
        (response,) = _worker(tmp_path, site, env, feeds, ["/data/network.json"])
        assert response["status"] == 200
        assert json.loads(response["body"])["snapshots"] == [
            {"state": "REFUSED", "code": code}
        ]


@needs_node
def test_worker_answers_404_while_snapshot_urls_is_unset(tmp_path):
    site = _site(tmp_path)
    for env in (
        {"FEED_KEYS": "ab" * 32},
        {"SNAPSHOT_URLS": " ", "FEED_KEYS": "ab" * 32},
    ):
        (response,) = _worker(tmp_path, site, env, {}, ["/data/network.json"])
        assert response["status"] == 404


@needs_node
@pytest.mark.parametrize(
    "env",
    [
        {"SNAPSHOT_URLS": URL, "FEED_KEYS": feed.FIXTURE_PUBLIC_KEY},
        {"SNAPSHOT_URLS": URL, "FEED_KEYS": ""},
        {"SNAPSHOT_URLS": URL.replace("https", "http"), "FEED_KEYS": "ab" * 32},
    ],
)
def test_worker_refuses_unsafe_snapshot_configuration(tmp_path, env):
    good = sfx.signed_snapshot(timestamp_ms=int(time.time() * 1000))
    (response,) = _worker(
        tmp_path, _site(tmp_path), env, {URL: json.dumps(good)}, ["/data/network.json"]
    )
    assert response["status"] == 503
    assert "neurons" not in response["body"]


@needs_node
def test_worker_never_serves_a_snapshot_from_a_fixture_build(tmp_path):
    good = sfx.signed_snapshot(timestamp_ms=int(time.time() * 1000))
    env = {"SNAPSHOT_URLS": URL, "FEED_KEYS": "ab" * 32}
    (response,) = _worker(
        tmp_path,
        _site(tmp_path, fixture=True),
        env,
        {URL: json.dumps(good)},
        ["/data/network.json"],
    )
    assert response["status"] == 503


def test_wrangler_config_holds_no_snapshot_url():
    text = (ROOT / "carbon/dashboard/wrangler.dashboard.toml").read_text(
        encoding="utf-8"
    )
    assert "SNAPSHOT_URLS" not in text.split("[vars]")[1]

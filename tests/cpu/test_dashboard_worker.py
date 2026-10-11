"""DASHBOARD-01 D4: the carbon-dashboard Worker reads the feed as feed.py does.

The Worker re-implements the feed reader in JavaScript so the public board
stays live without redeploys. These tests hold the two equal on every fixture
and every refusal case, in the bytes a validator door serves, and check the
Worker's fail-closed serving: never a FIXTURE build, never the fixture key,
a refused feed keeps the last built board.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from carbon.dashboard import build, feed, fixtures

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tests" / "cpu" / "dashboard_worker_check.mjs"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed here")


def _public(key):
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


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


def _python(text, trust):
    try:
        return {"board": json.loads(json.dumps(feed.project(json.loads(text), trust)))}
    except feed.FeedRefused as refused:
        return {"code": refused.code}


def _fixture():
    return fixtures.board_document("fixture-challenge-alpha", "gpu:FIXTURE-GPU", seed=1)


def _variants():
    """Unsigned fixture documents, each meant to be refused or accepted."""
    out = [("accepted", _fixture())]

    def edit(name, change):
        body = copy.deepcopy(_fixture())
        change(body)
        out.append((name, body))

    edit("live", lambda b: b.__setitem__("live", {"x": 1}))
    edit("values_live", lambda b: b["values"].__setitem__("live", {"p": 1}))
    edit(
        "unrounded",
        lambda b: b["submissions"][0]["sections"].__setitem__("accuracy", 0.41612),
    )
    edit(
        "unreleased",
        lambda b: b["submissions"][0].__setitem__("windows", ["sha256:" + "0" * 64]),
    )
    edit("labels", lambda b: b.__setitem__("labels", ["TESTNET", "FIXTURE"]))
    edit(
        "mixed",
        lambda b: (
            b.pop("device_class"),
            b["submissions"][0].__setitem__("device_class", "cpu"),
        ),
    )
    edit(
        "markup", lambda b: b["submissions"][0].__setitem__("submission_id", "<b>x</b>")
    )
    edit(
        "rank_float", lambda b: b["leaderboard"]["standing"][0].__setitem__("rank", 1.0)
    )
    edit("history_list", lambda b: b["leaderboard"].__setitem__("history", []))
    edit("standing_dict", lambda b: b["leaderboard"].__setitem__("standing", {}))
    edit("non_ascii", lambda b: b["challenge"].__setitem__("rule", "règle·ü"))
    edit(
        "extra",
        lambda b: (
            b.__setitem__("operator_note", "x"),
            b["submissions"][0].__setitem__("endpoint", "1.2.3.4"),
        ),
    )
    edit("bad_sense", lambda b: b["sections"]["accuracy"].__setitem__("sense", "up"))
    edit("showcase", lambda b: b.__setitem__("showcase", fixtures.unavailable_panel(b)))
    edit(
        "showcase_predicted",
        lambda b: b.__setitem__(
            "showcase",
            {
                **fixtures.unavailable_panel(b),
                "state": "PREDICTED",
                "predictions": {
                    "ev4:D-T5-S0.12:c1=0.5,c2=0.2:0": {
                        "time_to_cv_onset_s": 1800.0,
                        "reach_class": 1,
                        "plating_margin_v": 0.01,
                        "peak_temperature_c": 31.0,
                        "architecture": "x",
                    }
                },
            },
        ),
    )
    edit(
        "showcase_hidden_case",
        lambda b: b.__setitem__(
            "showcase",
            {
                **fixtures.unavailable_panel(b),
                "state": "PREDICTED",
                "predictions": {"hidden:1": {}},
            },
        ),
    )
    return out


@pytest.mark.parametrize("indent", [None, 1])
def test_worker_projection_matches_feed_py(tmp_path, indent):
    trust = fixtures.fixture_trust()
    items, expected = [], []
    for name, body in _variants():
        text = json.dumps(fixtures.sign(body), indent=indent)
        items.append({"text": text, "fixture": True, "keys": sorted(trust.keys)})
        expected.append((name, _python(text, trust)))
    tampered = fixtures.sign(_fixture())
    tampered["version"] = 99
    text = json.dumps(tampered)
    items.append({"text": text, "fixture": True, "keys": sorted(trust.keys)})
    expected.append(("tampered", _python(text, trust)))
    got = _node({"mode": "project", "items": items}, tmp_path)
    for (name, want), have in zip(expected, got, strict=True):
        assert have == want, name
    codes = {name: want.get("code") for name, want in expected}
    assert codes["accepted"] is None and codes["tampered"] == "signature_invalid"
    assert codes["rank_float"] == "leaderboard_invalid"


def _production(document, key):
    text = json.dumps(document).replace("fixture-miner-0", "5" + "G" * 44 + "A")
    body = json.loads(text)
    body["labels"] = [label for label in body["labels"] if label != "FIXTURE"]
    return fixtures.sign(body, key)


def test_worker_projection_matches_for_a_production_key(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    document = _production(_fixture(), key)
    text = json.dumps(document)
    (have,) = _node(
        {
            "mode": "project",
            "items": [{"text": text, "fixture": False, "keys": [_public(key)]}],
        },
        tmp_path,
    )
    assert have == _python(text, trust)
    assert "board" in have


def _site(tmp_path, documents, trust):
    out = tmp_path / "site"
    build.build(out, documents, trust)
    return str(out)


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


def test_worker_serves_live_boards_and_keeps_the_last_good_one(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    built = _production(_fixture(), key)
    site = _site(tmp_path, [built], trust)
    newer = _production({**_fixture(), "version": 9}, key)
    env = {
        "FEED_URLS": "https://validator.example/carbon/v1/feed/a",
        "FEED_KEYS": _public(key),
    }
    url = env["FEED_URLS"]
    index, page = _worker(
        tmp_path, site, env, {url: json.dumps(newer)}, ["/data/index.json", "/"]
    )
    assert index["status"] == 200
    live = json.loads(index["body"])
    assert live["fixture"] is False
    assert [b["version"] for b in live["boards"]] == [9]
    assert page["status"] == 200
    assert "frame-ancestors 'none'" in page["headers"]["content-security-policy"]
    # A refused (tampered) feed keeps the statically built board, marked REFUSED.
    bad = copy.deepcopy(newer)
    bad["version"] = 10
    (index,) = _worker(
        tmp_path, site, env, {url: json.dumps(bad)}, ["/data/index.json"]
    )
    (entry,) = json.loads(index["body"])["boards"]
    assert entry["state"] == "REFUSED" and entry["code"] == "signature_invalid"
    assert entry["version"] == built["version"]


def test_worker_never_serves_a_fixture_build(tmp_path):
    site = _site(tmp_path, fixtures.documents(), fixtures.fixture_trust())
    env = {"FEED_URLS": "https://validator.example/feed", "FEED_KEYS": "ab" * 32}
    for response in _worker(
        tmp_path, site, env, {}, ["/", "/data/index.json", "/showcase/index.json"]
    ):
        assert response["status"] == 503


@pytest.mark.parametrize(
    "env",
    [
        {
            "FEED_URLS": "https://validator.example/feed",
            "FEED_KEYS": feed.FIXTURE_PUBLIC_KEY,
        },
        {"FEED_URLS": "http://validator.example/feed", "FEED_KEYS": "ab" * 32},
        {"FEED_URLS": "", "FEED_KEYS": "ab" * 32},
    ],
)
def test_worker_refuses_unsafe_configuration(tmp_path, env):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    site = _site(tmp_path, [_production(_fixture(), key)], trust)
    (response,) = _worker(tmp_path, site, env, {}, ["/data/index.json"])
    assert response["status"] == 503


def test_wrangler_config_holds_no_account_or_secret():
    text = (ROOT / "carbon/dashboard/wrangler.dashboard.toml").read_text(
        encoding="utf-8"
    )
    assert "account_id" not in text
    assert "FEED_URLS" not in text.split("[vars]")[1]
    assert "FEED_KEYS" not in text.split("[vars]")[1]
    assert 'binding = "ASSETS"' in text and "run_worker_first = true" in text

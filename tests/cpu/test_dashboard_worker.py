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

from carbon.dashboard import board_v2, build, feed, fixtures

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


# --- DASHBOARD-02 S1: board.v2 parity and serving ---------------------------


def _python_v2(text, trust, now, card):
    try:
        board = feed.project(json.loads(text), trust)
    except feed.FeedRefused as refused:
        return {"code": refused.code}
    return {"board": json.loads(json.dumps(board_v2.project(board, now, card)))}


def _cards(document):
    digest = document["challenge"]["rule_digest"]
    return [
        None,
        {"digest": "sha256:" + "c" * 64, "rule": {"digest": digest}},
        {"digest": "sha256:" + "c" * 64, "rule": {"digest": "sha256:" + "d" * 64}},
    ]


def test_worker_board_v2_matches_board_v2_py(tmp_path):
    trust = fixtures.fixture_trust()
    documents = [fixtures.sign(body) for _, body in _variants()]
    documents += fixtures.documents() + fixtures.phase_documents()
    body = _fixture()
    del body["leaderboard"]["incumbent"]["since_block"]
    body["generated_at"] = "2026-02-30T00:00:00Z"
    documents.append(fixtures.sign(body))
    documents.append(fixtures.sign({**_fixture(), "generated_at": None}))
    for change in (
        {"status": "SEALED_UNTIL_GRAIN"},
        {"displayed_score": None},
        {"displayed_score": 0.12345},
        {"rank": 1.0},
        {"hotkeys": ["fixture-miner-01", "fixture-miner-01"]},
        {"best_submission_id": "<b>"},
        {"best_submission_id": None, "displayed_at_block": None},
        {"displayed_at_block": 2.0},
    ):
        body = fixtures.ladder_document(
            "fixture-challenge-epsilon", "gpu:FIXTURE-GPU", seed=6, sealed=False
        )
        body["leaderboard"]["ladder"]["coldkeys"][0].update(change)
        documents.append(fixtures.sign(body))
    for grain in (None, 0, 2.25, True):
        body = fixtures.ladder_document(
            "fixture-challenge-epsilon", "gpu:FIXTURE-GPU", seed=6, sealed=False
        )
        body["leaderboard"]["ladder"]["grain_pct"] = grain
        documents.append(fixtures.sign(body))
    items, expected = [], []
    for document in documents:
        text = json.dumps(document)
        for now in (fixtures.FIXTURE_NOW, fixtures.FIXTURE_NOW + 7_201):
            for card in _cards(document):
                items.append(
                    {
                        "text": text,
                        "fixture": True,
                        "keys": sorted(trust.keys),
                        "now": now,
                        "card": card,
                    }
                )
                expected.append(_python_v2(text, trust, now, card))
    got = _node({"mode": "project_v2", "items": items}, tmp_path)
    assert len(got) == len(expected)
    for index, (have, want) in enumerate(zip(got, expected, strict=True)):
        assert have == want, index
    phases = {w["board"]["phase"] for w in expected if "board" in w}
    assert phases == {"LIVE", "PRE_FIRST_RELEASE", "STALE"}


def test_worker_board_v2_matches_for_a_production_key(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    document = _production(_fixture(), key)
    text = json.dumps(document)
    now = fixtures.FIXTURE_NOW
    (have,) = _node(
        {
            "mode": "project_v2",
            "items": [
                {"text": text, "fixture": False, "keys": [_public(key)], "now": now}
            ],
        },
        tmp_path,
    )
    assert have == _python_v2(text, trust, now, None)
    assert have["board"]["fixture"] is False


def test_worker_serves_board_v2_and_keeps_the_last_good_one(tmp_path):
    key = Ed25519PrivateKey.generate()
    trust = feed.Trust(keys=frozenset({_public(key)}))
    built = _production(_fixture(), key)
    site = _site(tmp_path, [built], trust)
    slug = feed.project(built, trust)["slug"]
    env = {
        "FEED_URLS": "https://validator.example/carbon/v1/feed/a",
        "FEED_KEYS": _public(key),
    }
    url = env["FEED_URLS"]
    newer = _production({**_fixture(), "version": 9}, key)
    (page,) = _worker(
        tmp_path, site, env, {url: json.dumps(newer)}, [f"/data/v2/{slug}.json"]
    )
    assert page["status"] == 200
    board = json.loads(page["body"])
    assert board["schema"] == board_v2.SCHEMA and board["version"] == 9
    assert board["feed_state"] == {"state": "ACCEPTED", "code": None}
    assert board["rules"]["status"] == "UNAVAILABLE"
    bad = copy.deepcopy(newer)
    bad["version"] = 10
    (page,) = _worker(
        tmp_path, site, env, {url: json.dumps(bad)}, [f"/data/v2/{slug}.json"]
    )
    board = json.loads(page["body"])
    assert board["feed_state"] == {"state": "REFUSED", "code": "signature_invalid"}
    assert board["version"] == built["version"]
    (missing,) = _worker(
        tmp_path, site, env, {url: json.dumps(newer)}, ["/data/v2/nobody.json"]
    )
    assert missing["status"] == 404


def test_worker_never_serves_a_fixture_v2_board(tmp_path):
    documents = fixtures.documents() + fixtures.phase_documents()
    site = _site(tmp_path, documents, fixtures.fixture_trust())
    slugs = [feed.project(d, fixtures.fixture_trust())["slug"] for d in documents]
    env = {"FEED_URLS": "https://validator.example/feed", "FEED_KEYS": "ab" * 32}
    requests = [f"/data/v2/{slug}.json" for slug in slugs]
    for response in _worker(tmp_path, site, env, {}, requests):
        assert response["status"] == 503

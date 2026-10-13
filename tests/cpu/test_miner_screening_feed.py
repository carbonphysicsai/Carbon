"""PLT-08 signed-feed integration on a real store with synthetic bank cases."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_challenge_validator_battery_bank import run  # noqa: F401
from test_challenge_validator_score_feed import insert_scored, validator  # noqa: F401

from carbon.challenge_validator import canary, score_feed
from carbon.challenge_validator import screening_ladder as sl


def test_status_and_rounded_screening_are_signed_without_released_windows(
    validator, tmp_path, monkeypatch  # noqa: F811
):
    sg = pytest.importorskip("carbon.challenge_validator.screening_grain")
    target, store = validator["target"], validator["store"]
    monkeypatch.setitem(target.rule, "rule_version", "v2-bank-sched")
    identity = target.identities()
    screening = validator["windows"]["screening"]
    finalist = validator["windows"]["finalist"]
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", ("5Canary",))
    for sid, hk, windows, error in (
        ("s1", "5Miner", [screening], 0.1234),
        ("s2", "5Other", [screening], 0.12),
        ("fresh", "5Miner", [finalist], 0.001),
        ("canary", "5Canary", [screening], 0.001),
    ):
        insert_scored(store, sid, hk, windows, score=error)
        with store.transaction() as db:
            body = json.loads(
                db.execute(
                    "SELECT record FROM scores WHERE submission_id=?", (sid,)
                ).fetchone()[0]
            )
            body.update(
                rule_digest=identity["rule_digest"],
                screening_noise={"errors": [0.1] * 10},
            )
            db.execute(
                "UPDATE scores SET record=? WHERE submission_id=?",
                (json.dumps(body), sid),
            )
            db.execute(
                "UPDATE submissions SET binding=? WHERE submission_id=?",
                (
                    json.dumps(
                        {
                            "rule_digest": identity["rule_digest"],
                            "receipt": {"block": 100},
                        }
                    ),
                    sid,
                ),
            )
    doc = {"noise_floor": {"min_cases": 10, "min_design_questions": 4}}
    entry = {
        "grain": 0.04,
        "grain_pct": 4.0,
        "sense": "lower_is_better",
        "match": {"rule": "v2-bank-sched"},
    }
    monkeypatch.setattr(sl, "load_grain", lambda *args: (sg, doc, entry))
    from carbon.challenge_validator.ledger import AttemptLedger

    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "ledger.sqlite"
    AttemptLedger(path)
    chain = {
        "block": 100,
        "hash": "0x" + "1" * 64,
        "timestamp_ms": 1000,
        "participants": {
            "5Miner": {"coldkey": "5Owner", "uid": 1},
            "5Other": {"coldkey": "5Owner", "uid": 2},
            "5Canary": {"coldkey": "5OwnerCanary", "uid": 3},
        },
    }
    key = score_feed.FeedKey.create(tmp_path / "feed.key")
    feed = score_feed.build(
        target,
        key=key,
        hotkey="5Validator",
        network="testnet",
        chain=chain,
        attempt_ledger=path,
    )
    assert score_feed.verify_feed(feed, pinned_key=key.public_key)
    assert feed["released_windows"] == [] and feed["submissions"] == []
    assert feed["miner_status"] == [
        {"hotkey": "5Miner", "received": 0, "scored": 1, "refused": {}},
        {"hotkey": "5Other", "received": 0, "scored": 1, "refused": {}},
    ]
    ladder = feed["leaderboard"]["ladder"]
    assert len(ladder["coldkeys"]) == 1
    assert ladder["coldkeys"][0]["hotkeys"] == ["5Miner", "5Other"]
    assert ladder["coldkeys"][0]["displayed_score"] >= 0.12
    assert feed["as_of_block"]["number"] == chain["block"]
    public = json.dumps(feed)
    assert all(
        value not in public
        for value in (
            screening,
            finalist,
            "5Canary",
            "screening_noise",
            "errors",
            "regrets",
        )
    )
    again = score_feed.build(
        target,
        key=key,
        hotkey="5Validator",
        network="testnet",
        chain=chain,
        attempt_ledger=path,
    )
    assert again["version"] == feed["version"]
    monkeypatch.setattr(sl, "load_grain", lambda *args: None)
    sealed = score_feed.build(
        target, key=key, hotkey="5Validator", network="testnet", chain=chain
    )
    assert sealed["leaderboard"]["ladder"]["coldkeys"][0]["displayed_score"] is None
    assert sealed["miner_status"] is None
    # -04 reserves mainnet: a registered testnet grain confers no authority
    # there, and the builder must not even read the ledger for these fields.
    monkeypatch.setattr(
        score_feed,
        "_screening_disclosure",
        lambda *args: pytest.fail("mainnet disclosure called"),
    )
    mainnet = score_feed.build(
        target, key=key, hotkey="5Validator", network="mainnet", chain=chain
    )
    assert mainnet["miner_status"] is None and mainnet["leaderboard"]["ladder"] is None


def test_late_worker_completion_appends_instead_of_reordering_display(
    validator,  # noqa: F811
):
    store = validator["store"]
    window = validator["windows"]["screening"]
    insert_scored(store, "completed-first", "5Miner", [window], score=0.123)
    insert_scored(store, "completed-late", "5Miner", [window], score=0.12)
    with store.transaction() as db:
        db.execute(
            "UPDATE submissions SET created=0 WHERE submission_id='completed-late'"
        )
    assert [r["submission_id"] for r in store.scored_submissions()] == [
        "completed-late",
        "completed-first",
    ]
    assert [
        r["submission_id"] for r in store.scored_submissions(scoring_order=True)
    ] == ["completed-first", "completed-late"]

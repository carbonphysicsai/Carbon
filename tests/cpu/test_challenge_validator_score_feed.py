"""The validator's public score feed (VALIDATOR-29): released windows only.

Release records: a toy design bank retires and publishes real signed training
files, which are served as the distribution host serves them, verified in
full, and recorded. The feed: real battery windows (the pool-bank fixture),
imported by a validator; scored submissions appear only when every window
they used is released, rounded to the registered precision, canaries
excluded, the document signed and versioned. No case id appears in a feed.

Synthetic roots and scripted solves only: no container, chain, network or
spend. Not a security audit (AGENTS.md §13).
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_battery_bank import adapter, run  # noqa: F401
from test_challenge_validator_design_bank import ToyLaw, solve_all

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import canary, feed_file
from carbon.challenge_validator import design_bank as db
from carbon.challenge_validator import score_feed as sf
from carbon.challenge_validator.training_pool import TrainingPool


def test_published_cases_are_recorded_only_from_verified_files(tmp_path, monkeypatch):
    monkeypatch.setitem(
        db.DESIGN_BANKS, "toy", {"k": 2, "size": 2, "retire_at": 1, "values": "TEST"}
    )
    bank = db.DesignBank(tmp_path / "bank", ToyLaw(), solve_all)
    bank.top_up()
    bank.ledger.draw_window(bank.bank, 1, {"all": 1}, retire_at=1)
    bank.ledger.reveal_window(bank.bank, 1)
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    out = tmp_path / "published"
    out.mkdir(mode=0o700)
    bank.ledger.publish(out, key)
    files = sorted(out.rglob("*.json"))
    assert files
    folder = tmp_path / "pool" / "toy-challenge"
    folder.mkdir(parents=True)
    for path in files:
        shutil.copy(path, folder / path.name)
    pool = TrainingPool(tmp_path / "pool", key.public_key)
    store = adapter(tmp_path / "validator", import_only=True).target.store
    found = sf.record_releases(store, pool.answer, "toy-challenge", key.public_key)
    assert found["files"] == len(files) and found["new_cases"] == 1
    assert len(store.published_case_ids()) == 1
    # Another producer's key verifies nothing, and nothing is recorded.
    other = ak.ProducerKey.create(tmp_path / "other.key")
    fresh = adapter(tmp_path / "validator2", import_only=True).target.store
    refused = sf.record_releases(fresh, pool.answer, "toy-challenge", other.public_key)
    assert refused["new_cases"] == 0 and not fresh.published_case_ids()


def insert_scored(store, sid, hotkey, windows, *, score, eligible=True, block=100):
    now = time.time()
    with store.transaction() as db_:
        db_.execute(
            "INSERT INTO submissions VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                sid,
                "d-" + sid,
                hotkey,
                "battery",
                "{}",
                json.dumps({"receipt": {"block": block}}),
                "SCORED",
                None,
                now,
                now,
            ),
        )
        db_.execute(
            "INSERT INTO scores VALUES(?,?,?,?)",
            (
                sid,
                1,
                json.dumps(
                    {
                        "active_batches": windows,
                        "score": score,
                        "important_score": score / 2,
                        "eligible": eligible,
                        "gate_failures": [] if eligible else ["G-FEAS"],
                    }
                ),
                "{}",
            ),
        )


@pytest.fixture
def validator(run, tmp_path):  # noqa: F811
    validator = adapter(tmp_path / "validator", import_only=True)
    ak.import_local(validator, run["key"].public_key, run["outbox"])
    store = validator.target.store
    kinds = {v["manifest"]["commitment"]["kind"]: v for v in run["packages"].values()}
    windows = {
        kind: value["manifest"]["commitment"]["fingerprint"]
        for kind, value in kinds.items()
    }
    drawn = {
        kind: sorted(value["payload"]["references"]) for kind, value in kinds.items()
    }
    return {
        "target": validator.target,
        "store": store,
        "windows": windows,
        "drawn": drawn,
    }


def test_only_released_submissions_appear_rounded_and_signed(
    validator, tmp_path, monkeypatch
):
    store, w = validator["store"], validator["windows"]
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", ("5Canary",))
    insert_scored(store, "s1", "5Miner", [w["screening"]], score=0.123456, block=101)
    insert_scored(
        store, "s2", "5Other", [w["screening"], w["finalist"]], score=0.1, block=102
    )
    insert_scored(store, "s3", "5Canary", [w["screening"]], score=0.05, block=103)
    with store.transaction() as db_:
        db_.execute("INSERT INTO incumbent VALUES(1, 's1', 'first', 0)")
    key = sf.FeedKey.create(tmp_path / "feed.key")
    # Nothing is released yet: the feed shows no submission at all.
    empty = sf.build(validator["target"], key=key, hotkey="5Val", network="testnet")
    assert empty["submissions"] == [] and empty["released_windows"] == []
    assert empty["excluded"] == {"canary_hotkeys": 0}
    # The screening window's every drawn case is published: it is released.
    store.record_published("file-1", validator["drawn"]["screening"])
    feed = sf.build(validator["target"], key=key, hotkey="5Val", network="testnet")
    assert feed["released_windows"] == [w["screening"]]
    assert [s["submission_id"] for s in feed["submissions"]] == ["s1"]
    sections = feed["submissions"][0]["sections"]
    assert sections["accuracy"] == 0.123 and sections["near_limit"] == 0.062
    assert sections["gates"] == {"eligible": "PASS"}
    assert feed["excluded"] == {"canary_hotkeys": 1}
    assert feed["leaderboard"]["incumbent"]["hotkey"] == "5Miner"
    assert feed["leaderboard"]["standing"][0]["rank"] == 1
    assert feed["labels"] == ["DEVELOPMENT", "TESTNET"]
    assert feed["values"]["live"] is None
    assert feed["release"]["expected_lag_blocks"] == 5 * 1080
    assert sf.verify_feed(feed)
    assert sf.verify_feed(feed, pinned_key=key.public_key)
    assert not sf.verify_feed(feed, pinned_key="00" * 32)
    assert not sf.verify_feed({**feed, "version": feed["version"] + 1})
    assert feed["sections"]["accuracy"]["sense"] == "lower_is_better"
    assert feed["generated_at"].endswith("Z")
    # No case id appears anywhere in the feed.
    text = json.dumps(feed)
    assert not any(
        case_id in text for ids in validator["drawn"].values() for case_id in ids
    )
    # Unchanged: the same version. Both windows released: a new version, and
    # the two-window submission appears.
    again = sf.build(validator["target"], key=key, hotkey="5Val", network="testnet")
    assert again["version"] == feed["version"]
    store.record_published("file-2", validator["drawn"]["finalist"])
    both = sf.build(validator["target"], key=key, hotkey="5Val", network="mainnet")
    assert both["version"] == feed["version"] + 1
    assert [s["submission_id"] for s in both["submissions"]] == ["s1", "s2"]
    assert both["labels"] == ["DEVELOPMENT"]
    assert [e["hotkey"] for e in both["leaderboard"]["standing"]] == [
        "5Other",
        "5Miner",
    ]
    assert both["device_class"] == "cpu"
    # Another class's feed carries none of these CPU scores.
    gpu = sf.build(
        validator["target"],
        key=key,
        hotkey="5Val",
        network="mainnet",
        device_class="gpu:NVIDIA A40",
    )
    assert gpu["submissions"] == [] and gpu["leaderboard"]["standing"] == []


def test_the_feed_key_is_owner_only_and_never_printed(tmp_path):
    key = sf.FeedKey.create(tmp_path / "feed.key")
    assert "redacted" in repr(key)
    (tmp_path / "feed.key").chmod(0o644)
    with pytest.raises(sf.FeedRefused) as refused:
        sf.FeedKey.load(tmp_path / "feed.key")
    assert refused.value.code == "feed_key_not_owner_only"


def test_the_door_serves_only_a_verified_feed(tmp_path, monkeypatch):
    """`GET /carbon/v1/feed/<challenge>` returns the signed file, or refuses
    by name: no feed configured, or a file that does not verify."""
    import functools

    from carbon.battery import intake as ib
    from carbon.battery.challenge import CHALLENGE

    key = sf.FeedKey.create(tmp_path / "feed.key")
    document = {
        "schema": sf.FEED_SCHEMA,
        "validator": {"hotkey": "5Val", "feed_key": key.public_key},
        "challenge": {"id": CHALLENGE.challenge_id},
        "version": 1,
        "submissions": [],
    }
    feed = {**document, "signature": key.sign(document)}
    path = tmp_path / "feed.json"
    sf.write_feed(path, feed)
    door = ib.BatteryIntake.__new__(ib.BatteryIntake)
    door.challenge = CHALLENGE
    route = ib.FEED_PATH + CHALLENGE.challenge_id
    door.feed = None
    assert door.score_feed() == ib.Answer(404, {"refused": "feed_not_served"})
    door.feed = functools.partial(feed_file.read_feed, path, CHALLENGE.challenge_id)
    assert door.score_feed() == ib.Answer(200, feed)
    # A tampered file, or another Challenge's, is never served.
    sf.write_feed(path, {**feed, "version": 2})
    assert door.score_feed() == ib.Answer(503, {"refused": "feed_unavailable"})
    assert feed_file.read_feed(path, "another-challenge") is None
    assert route == "/carbon/v1/feed/" + CHALLENGE.challenge_id


def test_the_showcase_is_the_live_incumbents_panel_on_public_inputs(
    validator, tmp_path, monkeypatch
):
    """The live incumbent's rebuilt model (the owner's request; its hotkey is
    public through the weights), queried on EV4's public development scenarios
    only; the panel carries its identity digest and predicted quantities,
    never a recipe."""
    from carbon.battery.value import contract as ev

    store, w = validator["store"], validator["windows"]
    insert_scored(store, "s1", "5Miner", [w["screening"]], score=0.2, block=101)
    with store.transaction() as db_:
        db_.execute("INSERT INTO incumbent VALUES(1, 's1', 'first', 0)")
        db_.execute(
            "INSERT INTO models VALUES(?,?,?,?,?,?)",
            (
                "s1",
                "sha256:" + "a" * 64,
                0,
                "sha256:" + __import__("hashlib").sha256(b"state").hexdigest(),
                b"state",
                "{}",
            ),
        )
    asked = []

    def predict(sid, inputs, tag, namespace=None):
        asked.append((sid, namespace, len(inputs)))
        return {
            c: {
                "voltage_v": [3.5, 3.9, 4.1, 4.2],
                "temperature_c": [25.0, 30.0],
                "plating_margin_v": 0.01,
            }
            for c in inputs
        }

    monkeypatch.setattr(validator["target"], "_quiz_predictions", predict)
    key = sf.FeedKey.create(tmp_path / "feed.key")
    # The live incumbent drives the showcase before its windows are released
    # (the owner's request; its hotkey is public through the weights).
    feed = sf.build(
        validator["target"], key=key, hotkey="5V", network="testnet", with_showcase=True
    )
    assert feed["submissions"] == []  # its scores are still not released
    shown = feed["showcase"]
    contract, digest = ev.load(REPOSITORY / sf.SHOWCASE["contract"])
    jobs = ev.decision_cases(contract, "development")
    assert shown["state"] == "PREDICTED" and shown["schema"] == sf.SHOWCASE_SCHEMA
    assert shown["label"] == "current incumbent, public cases"
    assert shown["task"]["incumbent"] == "LIVE"
    assert shown["contract_digest"] == digest
    assert set(shown["predictions"]) == {job["case_id"] for job in jobs}
    assert asked == [("s1", sf.SHOWCASE_PREDICTIONS, len(jobs))]
    assert shown["model"]["hotkey"] == "5Miner"
    assert shown["model"]["submission_id"] == "s1"
    first = next(iter(shown["predictions"].values()))
    assert set(first) == {
        "time_to_cv_onset_s",
        "reach_class",
        "plating_margin_v",
        "peak_temperature_c",
    }
    assert feed["values"]["showcase_task"] == sf.SHOWCASE["task_id"]
    assert "recipe" not in json.dumps(shown) and sf.verify_feed(feed)

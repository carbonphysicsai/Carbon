"""Rule `v2-bank-e1-r360` and the producer's release step
(OWNER-BANK-EXPOSURE-E1-TESTNET-01; OWNER-AUTO-PUBLISH-RETIRED-01).

At E = 1 every case serves exactly one window. When the window's scheduled
retire block passes, the producer's tick reveals it and publishes its cases,
signed, into `outbox/<cid>/training/<cid>/`, which the existing push carries
to the distribution host's training pool. A case of a live window is never
published, a published case is never drawn again by any producer on that
bank, and a short bank leaves the slot unfilled (`bank_short`) instead of
aborting the tick. There is no container, chain, network or spend. Not a
security audit (AGENTS.md §13): hidden-case publication is for the owner's
security review.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from carbon.battery import exam
from carbon.battery.daemon import rule_digest
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator import training_pool
from carbon.challenge_validator.battery_bank import BANK, BankedBatterySource

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

import test_challenge_validator_battery_bank as banked
from test_challenge_validator_producer import scripted_solve

RULE = exam.RULES["v2-bank-e1-r360"]
POOL = RULE["bank"]["pool"]
EVERY = RULE["rotation"]["every_blocks"]
ACTIVE = RULE["active_batches"]


def test_only_exposure_rotation_and_refill_differ_from_v2_bank():
    base = exam.RULES["v2-bank"]
    assert POOL["retire_at"] == 1 and POOL["top_up"] is False and EVERY == 360
    assert POOL["size"] == 4000  # at least 24 h of draws
    per_day = 2 * POOL["window_cases"] * (7200 // EVERY)
    assert POOL["size"] >= per_day
    keep = ("retire_at", "top_up", "size")
    assert {k: v for k, v in POOL.items() if k not in keep} == {
        k: v for k, v in base["bank"]["pool"].items() if k not in keep
    }
    rest = dict(RULE, authority=None, bank=None, rotation=None)
    assert rest == dict(base, authority=None, bank=None, rotation=None)
    assert RULE["rotation"]["basis"] == base["rotation"]["basis"]
    assert "OWNER-BANK-EXPOSURE-E1-TESTNET-01" in RULE["authority"]
    assert rule_digest(RULE) != rule_digest(base)
    assert exam.disclosure(RULE) == exam.disclosure(base)


def _source(directory, bank_dir):
    return BankedBatterySource(
        banked.adapter(directory),
        bank_dir,
        overlay=directory.parent / "overlay",
        repository=REPOSITORY,
        runner=scripted_solve,
    )


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """One producer under rule e1-r360, its bank filled by the refill (as
    the operator's timer does), ticked at block 0 and at slot 1's retire
    block."""
    original = banked.RULE
    banked.RULE = RULE
    try:
        tmp = tmp_path_factory.mktemp("e1")
        source = _source(tmp / "producer-state", tmp / "bank")
        source.top_up()
        key = ak.ProducerKey.create(tmp / "producer.key")
        producer = pr.Producer(tmp / "producer", [source], signing_key=key)
        cid = source.challenge_id
        first = producer.tick(0)[cid]
        drawn_first = {
            case
            for slot_key in (2, 3)  # slot 1's screening and finalist windows
            for case in source.ledger.window_cases(BANK, slot_key)["cases"]
        }
        retire = (1 + ACTIVE) * EVERY
        before = producer.tick(retire - 1)[cid]
        after = producer.tick(retire)[cid]
        yield {
            "tmp": tmp,
            "source": source,
            "key": key,
            "producer": producer,
            "cid": cid,
            "first": first,
            "before": before,
            "after": after,
            "drawn_first": drawn_first,
            "training": tmp / "producer" / "outbox" / cid / "training",
        }
    finally:
        banked.RULE = original


def _published(run):
    pool = training_pool.TrainingPool(run["training"], run["key"].public_key)
    cases = set()
    # `files` serves only verified files, by name: what the host would serve.
    for name in pool.files(run["cid"]):
        value = json.loads((run["training"] / run["cid"] / name).read_text())
        training_pool.verify(value, run["key"].public_key)
        cases |= {r["case_id"] for r in value["records"]}
    return cases


def test_nothing_publishes_before_the_window_retires(run):
    assert run["first"]["filled"] == [1]
    assert run["before"]["released"]["published_cases"] == 0
    assert run["before"]["bank"]["state"] == "OK"


def test_the_ended_windows_cases_publish_at_its_retire_block(run):
    assert run["after"]["released"]["revealed"] == 2
    assert run["after"]["released"]["published_cases"] == 2 * POOL["window_cases"]
    assert _published(run) == run["drawn_first"]


def test_a_live_windows_cases_are_never_published(run):
    published = _published(run)
    for entry in run["producer"].journal.entries():
        if entry["event"] != "scheduled":
            continue
        if entry["window"]["retire_block"] <= (1 + ACTIVE) * EVERY:
            continue
        key, _ = run["source"]._window(run["source"]._row(entry["fingerprint"])["role"])
        live = set(run["source"].ledger.window_cases(BANK, key)["cases"])
        assert live and not live & published


def test_a_published_case_is_never_drawn_again_by_any_producer_on_the_bank(run):
    published = _published(run)
    # This producer's later windows and a second producer's source on the
    # same bank directory: every draw excludes a retired case.
    other = _source(run["tmp"] / "second-producer-state", run["tmp"] / "bank")
    for source in (run["source"], other):
        for slot in range(40, 44):
            for kind in (0, 1):
                key = 2 * slot + kind
                drawn = source.ledger.draw_window(
                    BANK,
                    key,
                    {"all": POOL["window_cases"]},
                    retire_at=POOL["retire_at"],
                )
                assert not set(drawn) & published
                assert not set(drawn) & run["drawn_first"]


def test_a_rerun_publishes_nothing_twice(run):
    again = run["producer"].tick((1 + ACTIVE) * EVERY)[run["cid"]]
    assert again["released"]["published_cases"] == 0
    assert len(list((run["training"] / run["cid"]).glob("*.json"))) == 1


def test_a_short_bank_fails_closed_and_the_tick_still_runs(tmp_path):
    original = banked.RULE
    banked.RULE = RULE
    try:
        source = _source(tmp_path / "producer-state", tmp_path / "bank")
        key = ak.ProducerKey.create(tmp_path / "producer.key")
        producer = pr.Producer(tmp_path / "producer", [source], signing_key=key)
        report = producer.tick(0)[source.challenge_id]
    finally:
        banked.RULE = original
    # Nothing refilled inside the tick: the slot is unfilled, typed, and the
    # bank reports BANK_LOW for the operator's refill timer.
    assert report["filled"] == [] and report["unfilled"] == [1]
    assert report["bank"] == {"state": "BANK_LOW", "live": 0, "size": POOL["size"]}
    unfilled = [e for e in producer.journal.entries() if e["event"] == "slot_unfilled"]
    assert unfilled and all(e["reason"] == "bank_short" for e in unfilled)


def test_release_needs_the_producer_signing_key(run, tmp_path):
    from carbon.challenge_validator.batch_source import ProducerRefused

    with pytest.raises(ProducerRefused, match="producer_no_signing_key"):
        run["source"].release([], tmp_path / "t", None)


def test_the_feed_states_the_e1_lag_as_the_windows_live_span():
    """`expected_lag_blocks` at E = 1 is `active_batches` rotations: 1,080
    blocks for this rule, not `retire_at x rotation` (360)."""
    import inspect

    from carbon.challenge_validator import score_feed

    source = inspect.getsource(score_feed.build)
    assert 'rule["active_batches"] * rotation' in source
    assert ACTIVE * EVERY == 1080

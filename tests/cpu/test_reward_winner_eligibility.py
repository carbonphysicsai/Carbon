"""Who a Challenge's testnet weight goes to (VALIDATOR-14).

Pure decisions on synthetic promotions, plus the first-incumbent path read
from battery's real daemon fixtures. A final's promotion is read from a
duck-typed validator state.
"""

import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    make,
    refs,  # noqa: F401 - fixture
    submission,
)

from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import DAY_MS, Q12

POLICY = wd.load_policy()
BATTERY = POLICY.challenges[0]
T0 = 20 * DAY_MS


def final(model, hotkey, previous, previous_hotkey, *, overdue=False):
    return {
        "model_id": model,
        "hotkey": hotkey,
        "previous": previous,
        "previous_hotkey": previous_hotkey,
        "kind": we.FINAL,
        "final_id": "final-" + model,
        "fresh_set": "fp-" + model,
        "nomination_pool_version": 2,
        "nomination_overdue": overdue,
    }


def first(model, hotkey):
    return {"model_id": model, "hotkey": hotkey, "previous": None, "kind": we.FIRST}


def ledger(tmp_path):
    return we.WinnerLedger(tmp_path / "winners.jsonl")


def test_a_first_incumbent_is_eligible_while_no_baseline_is_registered(tmp_path):
    record = ledger(tmp_path).observe(POLICY, BATTERY, first("m1", "hk-a"), {}, T0)
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "first_incumbent_no_baseline",
        T0,
    )


def test_with_a_registered_baseline_a_first_incumbent_is_not_paid(tmp_path):
    import dataclasses

    policy = dataclasses.replace(
        POLICY,
        baselines=tuple(
            (c, "sha256:" + "c" * 64 if c == BATTERY else None)
            for c in POLICY.challenges
        ),
    )
    record = ledger(tmp_path).observe(policy, BATTERY, first("m1", "hk-a"), {}, T0)
    assert record["eligible"] is False


def test_an_improvement_final_by_another_miner_restarts_the_clock(tmp_path):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {}, T0)
    later = T0 + 3 * DAY_MS
    record = book.observe(
        POLICY, BATTERY, final("m2", "hk-b", "m1", "hk-a"), {"hk-b": "ck-b"}, later
    )
    assert (record["eligible"], record["clock_ms"]) == (True, later)


def test_a_promotion_nominated_on_an_overdue_pool_pays_nobody(tmp_path):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {}, T0)
    record = book.observe(
        POLICY, BATTERY, final("m2", "hk-b", "m1", "hk-a", overdue=True), {}, T0 + 5
    )
    assert (record["eligible"], record["reason"]) == (
        False,
        "nomination_on_overdue_pool",
    )
    assert we.payable(record, {"hk-a", "hk-b"}) is None


@pytest.mark.parametrize(
    ("hotkey", "coldkeys"),
    [
        ("hk-a", {}),  # the same hotkey
        ("hk-a2", {"hk-a": "ck-a", "hk-a2": "ck-a"}),  # another hotkey, same coldkey
    ],
)
def test_the_same_miner_beating_itself_keeps_its_old_clock(tmp_path, hotkey, coldkeys):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), coldkeys, T0)
    record = book.observe(
        POLICY, BATTERY, final("m2", hotkey, "m1", "hk-a"), coldkeys, T0 + 2 * DAY_MS
    )
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "same_miner_no_reset",
        T0,
    )
    paid = wd.epoch_targets(
        POLICY, {BATTERY: we.payable(record, {hotkey})}, T0 + 2 * DAY_MS
    )
    assert paid["winners"] == {hotkey: (Q12 // 3) // 4}


def test_a_promotion_is_recorded_once_and_its_clock_never_moves(tmp_path):
    book = ledger(tmp_path)
    first_seen = book.observe(POLICY, BATTERY, first("m1", "hk-a"), {}, T0)
    again = book.observe(POLICY, BATTERY, first("m1", "hk-a"), {}, T0 + DAY_MS)
    assert again == first_seen
    assert len(book.records()) == 1


def test_an_unregistered_winner_is_not_paid(tmp_path):
    record = ledger(tmp_path).observe(POLICY, BATTERY, first("m1", "hk-a"), {}, T0)
    assert we.payable(record, {"hk-other"}) is None
    assert we.payable(record, {"hk-a"}) == wd.Winner("hk-a", T0)


def test_the_ledger_must_be_owner_only(tmp_path):
    path = tmp_path / "winners.jsonl"
    path.write_text("")
    path.chmod(0o644)
    with pytest.raises(we.RewardFailure):
        we.WinnerLedger(path)


def test_a_battery_first_incumbent_is_read_from_the_validator(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    target = make(tmp_path, refs, backend)
    assert we.battery_promotion(target) is None
    sid = target.admit(submission("hk1"))["submission_id"]
    target.process(sid)
    target.run_pending()
    promotion = we.battery_promotion(target)
    assert promotion["kind"] == we.FIRST
    assert (promotion["model_id"], promotion["hotkey"]) == (sid, "hk1")
    assert promotion["contract_digest"]

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


@pytest.mark.parametrize(
    ("new_hotkey", "coldkeys"),
    [
        ("hk-a", {"hk-a": "ck-a"}),
        ("hk-new", {"hk-new": "ck-a"}),
    ],
)
def test_first_incumbent_after_cutover_keeps_the_same_miners_clock(
    tmp_path, new_hotkey, coldkeys
):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    record = book.observe(
        POLICY, BATTERY, first("m2", new_hotkey), coldkeys, T0 + 3 * DAY_MS
    )
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "same_miner_no_reset",
        T0,
    )
    paid = wd.epoch_targets(
        POLICY, {BATTERY: we.payable(record, {new_hotkey})}, T0 + 3 * DAY_MS
    )
    assert paid["winners"] == {new_hotkey: (Q12 // 3) // 8}


def test_first_incumbent_after_cutover_from_a_distinct_miner_keeps_first_rule(tmp_path):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    later = T0 + 3 * DAY_MS
    record = book.observe(
        POLICY,
        BATTERY,
        first("m2", "hk-new"),
        {"hk-new": "ck-b"},
        later,
    )
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "first_incumbent_no_baseline",
        later,
    )


def test_cutover_with_missing_legacy_coldkey_refuses_before_append(tmp_path):
    book = ledger(tmp_path)
    old = we.decide(POLICY, BATTERY, first("m1", "hk-a"), None, {}, T0)
    old["schema"] = we.LEGACY_LEDGER_SCHEMA
    del old["winner_coldkey"]
    book._append(old)
    prior = book.path.read_bytes()
    with pytest.raises(we.RewardFailure, match="PREDECESSOR_IDENTITY_UNAVAILABLE"):
        book.observe(
            POLICY,
            BATTERY,
            first("m2", "hk-new"),
            {"hk-new": "ck-a"},
            T0 + 3 * DAY_MS,
        )
    assert book.path.read_bytes() == prior


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


@pytest.mark.parametrize(
    ("new_hotkey", "new_coldkey"),
    [
        ("hk-a", "ck-a"),
        ("hk-new", "ck-a"),
        ("hk-new", "ck-b"),
    ],
)
def test_registered_baseline_cutover_with_existing_winner_refuses_without_record(
    tmp_path, new_hotkey, new_coldkey
):
    import dataclasses

    policy = dataclasses.replace(
        POLICY,
        baselines=tuple(
            (c, "sha256:" + "c" * 64 if c == BATTERY else None)
            for c in POLICY.challenges
        ),
    )
    book = ledger(tmp_path)
    old = book.observe(
        policy,
        BATTERY,
        final("m1", "hk-a", "m0", "hk-0"),
        {"hk-a": "ck-a", "hk-0": "ck-0"},
        T0,
    )
    assert old["eligible"] is True
    prior = book.path.read_bytes()
    with pytest.raises(we.WinnerCutoverFailure, match="BASELINE_CUTOVER_UNRESOLVED"):
        book.observe(
            policy,
            BATTERY,
            first("m2", new_hotkey),
            {new_hotkey: new_coldkey},
            T0 + DAY_MS,
        )
    assert book.path.read_bytes() == prior


def test_an_improvement_final_by_another_miner_restarts_the_clock(tmp_path):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    later = T0 + 3 * DAY_MS
    record = book.observe(
        POLICY, BATTERY, final("m2", "hk-b", "m1", "hk-a"), {"hk-b": "ck-b"}, later
    )
    assert (record["eligible"], record["clock_ms"]) == (True, later)


@pytest.mark.parametrize(
    ("challenger_coldkey", "reason", "clock"),
    [
        ("ck-a", "same_miner_no_reset", T0),
        ("ck-b", "final_improvement", T0 + 3 * DAY_MS),
    ],
)
def test_predecessor_disappears_but_its_frozen_identity_controls_the_clock(
    tmp_path, challenger_coldkey, reason, clock
):
    book = ledger(tmp_path)
    old = book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    assert old["winner_coldkey"] == "ck-a"
    later = T0 + 3 * DAY_MS
    # hk-a has deregistered; the finalized snapshot only contains hk-new.
    new = book.observe(
        POLICY,
        BATTERY,
        final("m2", "hk-new", "m1", "hk-a"),
        {"hk-new": challenger_coldkey},
        later,
    )
    assert (new["reason"], new["clock_ms"], new["winner_coldkey"]) == (
        reason,
        clock,
        challenger_coldkey,
    )
    assert we.payable(old, {"hk-new"}) is None
    assert we.payable(new, {"hk-new"}) == wd.Winner("hk-new", clock)


def test_frozen_identity_outweighs_later_snapshot_association(tmp_path):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    record = book.observe(
        POLICY,
        BATTERY,
        final("m2", "hk-new", "m1", "hk-a"),
        {"hk-a": "ck-other", "hk-new": "ck-a"},
        T0 + DAY_MS,
    )
    assert (record["reason"], record["clock_ms"]) == ("same_miner_no_reset", T0)


def test_legacy_predecessor_uses_a_still_present_snapshot_identity(tmp_path):
    book = ledger(tmp_path)
    old = we.decide(POLICY, BATTERY, first("m1", "hk-a"), None, {}, T0)
    old["schema"] = we.LEGACY_LEDGER_SCHEMA
    del old["winner_coldkey"]
    book._append(old)
    record = book.observe(
        POLICY,
        BATTERY,
        final("m2", "hk-new", "m1", "hk-a"),
        {"hk-a": "ck-a", "hk-new": "ck-a"},
        T0 + DAY_MS,
    )
    assert (record["reason"], record["clock_ms"]) == ("same_miner_no_reset", T0)
    assert book.records()[0] == old


def test_legacy_predecessor_without_snapshot_identity_refuses_before_append(tmp_path):
    book = ledger(tmp_path)
    old = we.decide(POLICY, BATTERY, first("m1", "hk-a"), None, {}, T0)
    old["schema"] = we.LEGACY_LEDGER_SCHEMA
    del old["winner_coldkey"]
    book._append(old)
    before = book.path.read_bytes()
    with pytest.raises(we.RewardFailure, match="PREDECESSOR_IDENTITY_UNAVAILABLE"):
        book.observe(
            POLICY,
            BATTERY,
            final("m2", "hk-new", "m1", "hk-a"),
            {"hk-new": "ck-a"},
            T0 + DAY_MS,
        )
    assert book.path.read_bytes() == before


@pytest.mark.parametrize("bad_coldkey", [None, "", 12, ["ck-a"]])
def test_missing_or_malformed_frozen_identity_does_not_infer_a_reset(
    tmp_path, bad_coldkey
):
    book = ledger(tmp_path)
    old = we.decide(POLICY, BATTERY, first("m1", "hk-a"), None, {}, T0)
    old["winner_coldkey"] = bad_coldkey
    book._append(old)
    with pytest.raises(we.RewardFailure, match="PREDECESSOR_IDENTITY_UNAVAILABLE"):
        book.observe(
            POLICY,
            BATTERY,
            final("m2", "hk-new", "m1", "hk-a"),
            {"hk-new": "ck-b", "hk-a": "ck-a"},
            T0 + DAY_MS,
        )
    assert len(book.records()) == 1


@pytest.mark.parametrize("challenger_coldkey", [None, "", 12])
def test_unavailable_challenger_identity_does_not_infer_a_takeover(
    tmp_path, challenger_coldkey
):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    with pytest.raises(we.RewardFailure, match="WINNER_IDENTITY_UNAVAILABLE"):
        book.observe(
            POLICY,
            BATTERY,
            final("m2", "hk-new", "m1", "hk-a"),
            {"hk-new": challenger_coldkey},
            T0 + DAY_MS,
        )
    assert len(book.records()) == 1


def test_frozen_identity_cannot_be_used_for_a_different_predecessor(tmp_path):
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    with pytest.raises(we.RewardFailure, match="PREDECESSOR_RECORD_MISMATCH"):
        book.observe(
            POLICY,
            BATTERY,
            final("m3", "hk-new", "m2", "hk-a"),
            {"hk-new": "ck-a"},
            T0 + DAY_MS,
        )
    assert len(book.records()) == 1


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


def bank(model, hotkey, previous, previous_hotkey):
    return {
        "model_id": model,
        "hotkey": hotkey,
        "previous": previous,
        "previous_hotkey": previous_hotkey,
        "kind": we.BANK,
    }


def test_a_bank_improvement_by_another_miner_restarts_the_clock(tmp_path):
    """KOTH-TAKEOVER-RULE-01 §1: no fresh-case tournament; the better score on
    the shared bank key takes the crown and starts a full 24 hours."""
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), {"hk-a": "ck-a"}, T0)
    later = T0 + 3 * DAY_MS
    record = book.observe(
        POLICY, BATTERY, bank("m2", "hk-b", "m1", "hk-a"), {"hk-b": "ck-b"}, later
    )
    assert (record["eligible"], record["reason"], record["clock_ms"]) == (
        True,
        "bank_improvement",
        later,
    )
    paid = wd.epoch_targets(POLICY, {BATTERY: we.payable(record, {"hk-b"})}, later)
    assert paid["winners"] == {"hk-b": Q12 // 3}


@pytest.mark.parametrize(
    ("hotkey", "coldkeys"),
    [("hk-a", {}), ("hk-a2", {"hk-a": "ck-a", "hk-a2": "ck-a"})],
)
def test_a_king_beating_himself_on_the_bank_keeps_his_clock(tmp_path, hotkey, coldkeys):
    """KOTH-TAKEOVER-RULE-01 §2: the better model is the incumbent, the clock
    does not reset, and halving continues from the first promotion."""
    book = ledger(tmp_path)
    book.observe(POLICY, BATTERY, first("m1", "hk-a"), coldkeys, T0)
    record = book.observe(
        POLICY, BATTERY, bank("m2", hotkey, "m1", "hk-a"), coldkeys, T0 + 2 * DAY_MS
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

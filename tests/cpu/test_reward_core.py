"""Synthetic analytical vectors; none authenticate or accept scientific work."""

import math
from dataclasses import replace
from decimal import Decimal, localcontext
from itertools import permutations

import pytest

from carbon.rewards.core import (
    ARITHMETIC,
    DAY_MS,
    Q12,
    DevelopmentTerms,
    Holder,
    Record,
    RewardFailure,
    State,
    WinnerStatus,
    advance_batch,
    fraction,
    opening,
    targets,
)
from carbon.rewards.review import HOUR_MS, Hour, review
from carbon.rewards.treasury import DisabledTreasury


def terms(context="a", allocation=Q12):
    return DevelopmentTerms(
        context * 64,
        "b" * 64,
        (0.8).hex(),
        "1",
        0,
        29 * DAY_MS,
        30 * DAY_MS,
        ((0, allocation),),
    )


def record(score=0.99, hotkey="alice", order=1):
    return Record(
        f"{order:064x}",
        f"{order+100:064x}",
        score.hex(),
        Holder(hotkey, "cold-" + hotkey, 1),
        order,
    )


def winner(score=0.99, t=None):
    return advance_batch(opening(t or terms()), (record(score),), 0)


def projected(*states, now=0, status=WinnerStatus.USABLE):
    return targets(states, now, {s.terms.context_id: status for s in states})


def test_required_golden_fraction_and_zero_opening_credit():
    assert fraction(opening(terms()), 0) == 0
    state = winner()
    assert [fraction(state, day * DAY_MS) for day in (0, 1, 7)] == [
        950000000000,
        475000000000,
        7421875000,
    ]
    assert projected(state).burn == 50000000000


def test_no_winner_and_no_challenge_preserve_complete_burn():
    assert projected().burn == Q12
    result = projected(opening(terms()))
    assert result.burn == Q12 and result.winners == ()
    assert result.challenges[0].unearned == Q12


@pytest.mark.parametrize("score", [0.8, 0.89, 0.9])
def test_ties_and_nonimprovement_keep_incumbent_and_age(score):
    state = winner(0.9)
    new = advance_batch(state, (record(score, "bob", 2),), DAY_MS)
    assert new is state
    assert fraction(new, DAY_MS) == Q12 // 4


@pytest.mark.parametrize("hotkey", ["alice", "bob"])
def test_self_improvement_and_takeover_add_only_gain(hotkey):
    state = advance_batch(winner(0.9), (record(0.92, hotkey, 2),), DAY_MS)
    result = projected(state, now=DAY_MS)
    assert fraction(state, DAY_MS) == 350000000000
    assert result.winners == ((Holder(hotkey, "cold-" + hotkey, 1), 350000000000),)
    assert result.burn == 650000000000


def test_closed_batch_selects_best_once_and_authentic_order_breaks_new_tie():
    batch = (record(0.91, "alice", 1), record(0.92, "bob", 2), record(0.92, "carol", 3))
    states = [
        advance_batch(opening(terms()), order, DAY_MS) for order in permutations(batch)
    ]
    assert all(state == states[0] for state in states)
    assert states[0].holder.hotkey == "bob"
    assert fraction(states[0], DAY_MS) == 600000000000


def test_multiple_challenges_aggregate_shared_winner_and_keep_independent_remainders():
    a, b = winner(0.9, terms("a", Q12 // 2)), winner(0.99, terms("c", Q12 // 4))
    result = projected(a, b)
    assert result.winners[0][1] == 487500000000
    assert result.burn == 512500000000
    assert [(r.earned, r.unearned) for r in result.challenges] == [
        (250000000000, 250000000000),
        (237500000000, 12500000000),
    ]


def test_unearned_challenge_allocation_never_moves_to_another_winner():
    result = projected(
        winner(0.99, terms("a", Q12 // 2)), opening(terms("c", Q12 // 2))
    )
    assert result.winners[0][1] == 475000000000
    assert result.burn == 525000000000


@pytest.mark.parametrize(
    "status", [WinnerStatus.MISSING, WinnerStatus.DISQUALIFIED, WinnerStatus.CONTESTED]
)
def test_unusable_winner_burns_without_promoting_a_worse_result(status):
    result = projected(winner(), status=status)
    assert result.winners == () and result.burn == Q12


def test_allocation_changes_never_change_record_or_credit_age():
    t = replace(terms(), allocation=((0, Q12 // 2), (DAY_MS, Q12)))
    state = winner(0.99, t)
    assert projected(state).winners[0][1] == 475000000000
    assert projected(state, now=DAY_MS).winners[0][1] == 475000000000
    assert state.anchor_ms == 0
    assert projected(state, now=t.funded_until_ms).burn == Q12


def test_floor_dust_is_unearned_and_total_is_exact():
    state = winner(0.99, terms(allocation=3))
    result = projected(state)
    assert result.winners[0][1] == 2
    assert result.challenges[0].unearned == 1
    assert result.burn + sum(v for _, v in result.winners) == Q12


def test_checkpoint_restart_and_queries_do_not_refresh_or_round_state():
    state = winner(0.9)
    for day in range(1, 10):
        state = advance_batch(
            state, (record(0.9 + day * 0.005, "alice", day + 1),), day * DAY_MS
        )
    restored = State(
        state.terms,
        state.record_hex,
        state.holder,
        state.event,
        state.gain_at_anchor,
        state.anchor_ms,
    )
    prior = restored.gain_at_anchor
    for now in range(9 * DAY_MS, 10 * DAY_MS, 1234567):
        assert fraction(state, now) == fraction(restored, now)
    assert restored.gain_at_anchor == prior
    with pytest.raises(RewardFailure, match="STALE_TIME"):
        fraction(state, 0)


def test_finite_lifetime_bound_is_target_only():
    with localcontext(ARITHMETIC):
        days = Decimal(1) / Decimal(2).ln()
    assert 1.4426 < float(days) < 1.4427
    assert fraction(winner(1.0), 0) == Q12
    assert fraction(winner(1.0), DAY_MS) == Q12 // 2


def test_withholding_can_shift_target_into_later_higher_allocation():
    t = replace(terms(), allocation=((0, Q12 // 100), (DAY_MS, Q12)))
    early = winner(0.99, t)
    withheld = advance_batch(opening(t), (record(),), DAY_MS)
    assert (
        projected(withheld, now=DAY_MS).winners[0][1]
        > projected(early, now=DAY_MS).winners[0][1]
    )


def test_drip_feeding_can_extend_target_and_identity_splitting_confers_no_old_share():
    immediate = winner(0.99)
    drip = advance_batch(winner(0.9), (record(0.99, "bob", 2),), DAY_MS)
    assert fraction(drip, DAY_MS) > fraction(immediate, DAY_MS)
    assert [h.hotkey for h, _ in projected(drip, now=DAY_MS).winners] == ["bob"]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -0.0, -0.1, 1.1])
def test_bad_scientific_scores_rejected(bad):
    with pytest.raises(RewardFailure):
        record(bad)


def test_invalid_range_windows_overallocation_and_duplicate_batches_fail():
    with pytest.raises(RewardFailure):
        replace(terms(), upper="0.8")
    with pytest.raises(RewardFailure):
        replace(terms(), admits_until_ms=31 * DAY_MS)
    with pytest.raises(RewardFailure, match="OVERALLOCATED"):
        projected(winner(t=terms("a")), winner(t=terms("c")))
    with pytest.raises(RewardFailure, match="DUPLICATE"):
        advance_batch(opening(terms()), (record(), record()), 0)


def hours(earned=5, allocated=100):
    return tuple(
        Hour(start, allocated, earned, True, True, 3, 1)
        for start in range(4 * DAY_MS, 7 * DAY_MS, HOUR_MS)
    )


@pytest.mark.parametrize(
    "earned,status", [(9, "PLATEAU_REVIEW"), (10, "CONTINUE"), (11, "CONTINUE")]
)
def test_weekly_review_is_strict_and_opening_anchored(earned, status):
    result = review(0, 7 * DAY_MS, hours(earned))
    assert result.status == status
    assert result.submissions == 216 and result.accepted == 72
    assert review(0, 7 * DAY_MS + 1, hours()).status == "NOT_SCHEDULED"


@pytest.mark.parametrize(
    "changed", ["missing", "duplicate", "unhealthy", "zero", "invalid"]
)
def test_review_indeterminate_windows_never_retire_or_reset(changed):
    source = hours()
    if changed == "missing":
        source = source[:-1]
    if changed == "duplicate":
        source = source[:-1] + (source[0],)
    if changed == "unhealthy":
        source = (replace(source[0], publisher_healthy=False),) + source[1:]
    if changed == "zero":
        source = hours(0, 0)
    if changed == "invalid":
        source = (replace(source[0], earned=101),) + source[1:]
    assert review(0, 7 * DAY_MS, source).status.startswith("INDETERMINATE")


def test_treasury_absent_needs_no_state_or_destination():
    assert DisabledTreasury().new_allocation() == 0
    assert projected(winner()).burn == 50000000000
    with pytest.raises(RewardFailure, match="NOT_IMPLEMENTED"):
        DisabledTreasury().enable()


def test_tiny_positive_gains_accumulate_without_q12_credit_discarding():
    state = opening(terms())
    for i in range(1, 20):
        state = advance_batch(state, (record(0.8 + i * 1e-14, "alice", i),), 0)
    assert fraction(state, 0) == 0
    state = advance_batch(state, (record(0.8 + 3e-13, "alice", 20),), 0)
    assert fraction(state, 0) == 1
    assert state.gain_at_anchor != "0"


def test_new_version_requires_its_own_baseline_and_starts_without_holder_credit():
    old = winner()
    new = opening(replace(terms("c"), baseline_hex=old.record_hex))
    assert fraction(new, 0) == 0 and new.holder is None
    assert advance_batch(new, (record(),), 0) == new

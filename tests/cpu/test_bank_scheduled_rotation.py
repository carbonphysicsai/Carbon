"""Rule `v2-bank-sched` and the bank's scheduled draw
(OWNER-BANK-SCHEDULED-ROTATION-01; OWNER-BANK-ARCHITECTURE-01).

The owner-approved bank (B = 20n, E = 5) with a scheduled rotation in place
of uniform draws:
- a case's E exposures fall in windows `stride` slots apart, one lane, so
  they never meet in concurrently live windows;
- a lane's first window staggers its cases' budgets (E, E-1, ... 1), so one
  group retires each window and the lane stays balanced;
- after that, each window draws about n/E fresh cases;
- a window's cases have all retired (E - 1) strides after it;
- a case due in a window that was never drawn is lapsed (retired, never
  drawn late);
- no case is drawn past its budget.
The Q3 design bank uses the same ledger code. Synthetic sources and scripted
solves only: no container, chain, network or spend.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

from carbon.battery import exam
from carbon.battery.daemon import rule_digest
from carbon.challenge_validator.bank import BankLedger, BankRefused

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_bank import Synthetic, fill

RULE = exam.RULES["v2-bank-sched"]
E = 5
N = 20
STRIDE = 6  # battery: 2 keys a slot x 3 active slots


def lane_draws(ledger, start, windows, *, n=N, stride=STRIDE, skip=()):
    """Draw `windows` windows of one lane; returns {key: drawn}."""
    drawn = {}
    for i in range(windows):
        key = start + i * stride
        if key in skip:
            continue
        active = [k for k in drawn if 0 < key - k < stride]
        drawn[key] = ledger.draw_window(
            "pool", key, {"all": n}, active_slots=active, retire_at=E, stride=stride
        )
    return drawn


@pytest.fixture
def ledger(tmp_path):
    ledger = BankLedger(tmp_path / "bank", Synthetic())
    fill(ledger, "pool", 400)
    return ledger


def _cases(ledger):
    with ledger._db() as db:
        return {
            r["case_id"]: dict(r)
            for r in db.execute(
                "SELECT case_id, exposures, retired_slot, due_slot, budget FROM cases"
            ).fetchall()
        }


def test_the_rule_is_v2_bank_with_a_scheduled_rotation():
    base = exam.RULES["v2-bank"]
    pool = RULE["bank"]["pool"]
    assert pool["retire_at"] == E and pool["draw"] == "scheduled"
    assert pool["top_up"] is False and pool["size"] == 20 * 100  # B = 20n
    assert RULE["rotation"]["every_blocks"] == 360 and RULE["active_batches"] == 3
    assert RULE["design"] == {
        "bank": "design:battery-q3",
        "k": 8,
        "retire_at": 10,
        "draw": "scheduled",
        "top_up": False,
    }
    rest = dict(RULE, authority=None, bank=None, rotation=None, design=None)
    assert rest == dict(base, authority=None, bank=None, rotation=None, design=None)
    assert "OWNER-BANK-SCHEDULED-ROTATION-01" in RULE["authority"]
    assert rule_digest(RULE) != rule_digest(base)
    assert exam.disclosure(RULE) == exam.disclosure(base)


def test_a_lane_bootstraps_staggered_and_then_draws_n_over_e_fresh(ledger):
    drawn = lane_draws(ledger, 0, 12)
    assert all(len(cases) == N for cases in drawn.values())
    keys = sorted(drawn)
    seen = set()
    for i, key in enumerate(keys):
        fresh = set(drawn[key]) - seen
        if i == 0:
            assert len(fresh) == N
        else:
            assert len(fresh) == N // E  # one group retired, one enters
        seen |= set(drawn[key])


def test_exposures_fall_one_stride_apart_and_never_exceed_e(ledger):
    drawn = lane_draws(ledger, 0, 12)
    appearances = {}
    for key in sorted(drawn):
        for case in drawn[key]:
            appearances.setdefault(case, []).append(key)
    for case, keys in appearances.items():
        assert len(keys) <= E
        assert all(b - a == STRIDE for a, b in itertools.pairwise(keys)), case
    cases = _cases(ledger)
    assert all(row["exposures"] <= (row["budget"] or E) for row in cases.values())


def test_live_windows_never_share_a_case(ledger):
    """Windows less than a stride apart are live together; lanes interleave."""
    drawn = {}
    for key in range(30):
        active = [k for k in drawn if 0 < key - k < STRIDE]
        held = set().union(*(set(drawn[k]) for k in active)) if active else set()
        drawn[key] = ledger.draw_window(
            "pool", key, {"all": N}, active_slots=active, retire_at=E, stride=STRIDE
        )
        assert not set(drawn[key]) & held, key


def test_a_window_has_fully_retired_e_minus_one_strides_later(ledger):
    drawn = lane_draws(ledger, 0, 12)
    cases = _cases(ledger)
    for key in sorted(drawn)[: 12 - (E - 1)]:
        last = key + (E - 1) * STRIDE
        assert all(
            cases[c]["retired_slot"] is not None and cases[c]["retired_slot"] <= last
            for c in drawn[key]
        ), key


def test_a_skipped_window_lapses_its_due_cases_and_never_draws_them_late(ledger):
    drawn = lane_draws(ledger, 0, 3)  # keys 0, 6, 12
    due_at_18 = [c for c, row in _cases(ledger).items() if row["due_slot"] == 18]
    assert due_at_18
    later = ledger.draw_window(
        "pool", 24, {"all": N}, retire_at=E, stride=STRIDE
    )  # 18 was never drawn
    assert not set(later) & set(due_at_18)
    cases = _cases(ledger)
    assert all(cases[c]["retired_slot"] == 24 for c in due_at_18)
    assert all(cases[c]["due_slot"] is None for c in due_at_18)
    assert drawn


def test_retired_cases_publish_after_their_windows_end(ledger):
    """The release step's rule holds: a scheduled case is publishable only
    once retired and every window that drew it is revealed."""
    drawn = lane_draws(ledger, 0, E)
    first = set(drawn[0])
    for key in drawn:
        ledger.reveal_window("pool", key)
    publishable = set(ledger.publishable())
    assert first <= publishable  # window 0's cases all retired by key 24


def test_a_short_bank_refuses_and_never_reuses(tmp_path):
    ledger = BankLedger(tmp_path / "bank", Synthetic())
    fill(ledger, "pool", N)
    ledger.draw_window("pool", 0, {"all": N}, retire_at=E, stride=STRIDE)
    with pytest.raises(BankRefused, match="bank_short"):
        ledger.draw_window("pool", 1, {"all": N}, retire_at=E, stride=STRIDE)


def test_a_stratified_quota_is_refused_for_a_scheduled_draw(ledger):
    with pytest.raises(BankRefused, match="bank_schedule_stratified"):
        ledger.draw_window("pool", 0, {"lo": 5, "hi": 5}, retire_at=E, stride=STRIDE)


def test_the_uniform_draw_is_unchanged_without_a_stride(ledger):
    drawn = ledger.draw_window("pool", 0, {"all": N}, retire_at=E)
    rows = _cases(ledger)
    assert all(rows[c]["due_slot"] is None for c in drawn)


def test_the_question_lane_uses_the_same_schedule(tmp_path):
    """The Q3 design bank: k questions a screening window, E_q exposures one
    stride (3 screening slots) apart."""
    ledger = BankLedger(tmp_path / "design", Synthetic())
    fill(ledger, "pool", 200)
    e_q, k, stride = 10, 8, 3
    appearances = {}
    for slot in range(0, 40 * stride, stride):
        for case in ledger.draw_window(
            "pool", slot, {"all": k}, retire_at=e_q, stride=stride
        ):
            appearances.setdefault(case, []).append(slot)
    assert all(len(v) <= e_q for v in appearances.values())
    assert any(len(v) == e_q for v in appearances.values())


def test_the_producer_uses_the_rules_stride():
    from types import SimpleNamespace

    from carbon.challenge_validator.battery_bank import BankedBatterySource

    source = object.__new__(BankedBatterySource)
    source.adapter = SimpleNamespace(target=SimpleNamespace(rule=RULE))
    assert source._stride(RULE["bank"]["pool"], keys_per_slot=2) == 6
    assert source._stride(RULE["design"], keys_per_slot=1) == 3
    assert (
        source._stride(exam.RULES["v2-bank"]["bank"]["pool"], keys_per_slot=2) is None
    )


def test_the_feed_states_the_scheduled_lag():
    """E x active rotations: 5 x 3 x 360 = 5,400 blocks (~18 h)."""
    import inspect

    from carbon.challenge_validator import score_feed

    source = inspect.getsource(score_feed.build)
    assert 'bank["retire_at"] * rule["active_batches"] * rotation' in source
    assert E * RULE["active_batches"] * RULE["rotation"]["every_blocks"] == 5400

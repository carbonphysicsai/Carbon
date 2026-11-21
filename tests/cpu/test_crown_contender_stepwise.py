"""A contender's crown decision runs ONE new rebuild per call and is resumed by the sweep (Bundle A2, 14 Nov 2026).

Before: a crown-changing contender's N rebuilds plus the host-fault second build ran inline in one grade round (4 x ~34 min at
N = 3), so every pending grade waited behind them. Now (`Active(stepwise=True)`, on at the receiver's install) each call runs at
most ONE new rebuild, keeps it (`PoolStore.crown_rebuild_cached`), and returns UNAVAILABLE ``crown_average_rebuild_in_progress``;
the contender stays filed for the sweep, which resumes it on its next tick (no attempt counted, no spacing, no alert) and
decides from the kept rebuilds. The decision, its record and its outcome equal the single-call ones. Synthetic fixtures only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_crown_average_wiring import (
    KEY,
    Repeat,
    _active,
    _body,
    _comparator,
    _flow,
    _pair,
    _Pairs,
)

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import crown_pause_sweep as sweep
from carbon.challenge_validator import lean_recipe_retention as lrr
from carbon.challenge_validator.interface import digest


@pytest.fixture(autouse=True)
def _sweep_process_state_is_not_left_behind():
    """`crown_pause_sweep` keeps process-wide first-seen / king-changed times per store: a test of the sweep must not leave
    its entries for a later test whose store happens to share a key (test_king_upkeep reads the same module state).
    """
    first, changed = dict(sweep._FIRST_SEEN), dict(sweep._KING_CHANGED)
    yield
    sweep._FIRST_SEEN.clear()
    sweep._FIRST_SEEN.update(first)
    sweep._KING_CHANGED.clear()
    sweep._KING_CHANGED.update(changed)


N = 3
CALLS = (
    N + 1
)  # N seeded rebuilds + the host-fault second build, one new rebuild per call


def _stepped(tmp_path):
    active = _active(tmp_path, n=N)
    active.stepwise = True
    return active


def _king_and_contender(tmp_path, monkeypatch, contender_total=0.71, king_total=0.70):
    a, b = _body("a", king_total), _body("b", contender_total)
    store, flow = _flow(tmp_path, monkeypatch, {"a": _pair(a, None), "b": _pair(b, a)})
    plain = _active(
        tmp_path, n=N
    )  # the king is crowned by the single-call rule (stepwise off)
    flow.consider_private(
        "a", KEY, _comparator(), repeat=Repeat("a", [king_total] * N), average=plain
    )
    assert store.incumbent()["model_id"] == "a"
    return store, flow


def test_the_default_is_the_whole_decision_in_one_call_and_the_receiver_turns_stepwise_on(
    tmp_path,
):
    assert _active(tmp_path).stepwise is False
    # S7 C2 301: a receiver never turns the average on (official-score crowns for every version)
    from carbon.challenge_validator import crown_average as ca
    from carbon.challenge_validator import crown_average_host as host

    previous, ca.ACTIVE = ca.ACTIVE, object()
    try:
        host.install({"crown_average": {"key_file": "/nonexistent"}})
        assert ca.ACTIVE is None
    finally:
        ca.ACTIVE = previous


def test_a_contender_takes_one_new_rebuild_per_call_and_the_last_call_decides(
    tmp_path, monkeypatch
):
    store, flow = _king_and_contender(tmp_path, monkeypatch)
    repeat = Repeat("b", [0.71] * N)
    average = _stepped(tmp_path)
    reasons = []
    for call in range(1, CALLS + 1):
        outcome = flow.consider_private(
            "b", KEY, _comparator(), repeat=repeat, average=average
        )
        reasons.append((outcome["outcome"], outcome["reason"]))
        assert (
            len(repeat.asked) == call
        )  # exactly one NEW rebuild this call, never a cached one again
    assert reasons[:-1] == [(bp.UNAVAILABLE, ca.REBUILD_IN_PROGRESS)] * (CALLS - 1)
    assert reasons[-1] == (bp.CHALLENGER, ca.MEAN_EXCEEDS)
    assert store.incumbent()["model_id"] == "b"
    assert store.crown_mean("b") == pytest.approx(0.71)


def test_nothing_moves_until_the_last_call(tmp_path, monkeypatch):
    store, flow = _king_and_contender(tmp_path, monkeypatch)
    repeat, average = Repeat("b", [0.71] * N), _stepped(tmp_path)
    for _ in range(CALLS - 1):
        flow.consider_private("b", KEY, _comparator(), repeat=repeat, average=average)
        assert (
            store.incumbent()["model_id"] == "a"
        )  # the king keeps the crown meanwhile
        assert store.crown_mean("b") is None  # no mean is filed from a partial set


def test_the_stepwise_decision_equals_the_single_call_one(tmp_path, monkeypatch):
    singles = tmp_path / "single"
    singles.mkdir()
    store1, flow1 = _king_and_contender(singles, monkeypatch, contender_total=0.7123)
    flow1.consider_private(
        "b",
        KEY,
        _comparator(),
        repeat=Repeat("b", [0.7123] * N),
        average=_active(singles, n=N),
    )
    stepped = tmp_path / "stepped"
    stepped.mkdir()
    store2, flow2 = _king_and_contender(stepped, monkeypatch, contender_total=0.7123)
    repeat, average = Repeat("b", [0.7123] * N), _stepped(stepped)
    for _ in range(CALLS):
        outcome = flow2.consider_private(
            "b", KEY, _comparator(), repeat=repeat, average=average
        )
    assert outcome["outcome"] == bp.CHALLENGER
    assert store2.crown_mean("b") == store1.crown_mean("b")
    assert store2.incumbent()["model_id"] == store1.incumbent()["model_id"] == "b"


def test_one_inadmissible_seed_is_no_takeover_when_stepped(tmp_path, monkeypatch):
    store, flow = _king_and_contender(tmp_path, monkeypatch, contender_total=0.95)
    repeat = Repeat("b", [0.95] * N, statuses={2: "MANDATORY_GATE_FAILED"})
    average = _stepped(tmp_path)
    outcomes = [
        flow.consider_private("b", KEY, _comparator(), repeat=repeat, average=average)
        for _ in range(
            N
        )  # the three seeded rebuilds; the decision is then UNSTABLE (no host-fault build is run)
    ]
    assert (outcomes[-1]["outcome"], outcomes[-1]["reason"]) == (
        bp.INCUMBENT_KEEPS,
        ca.UNSTABLE,
    )
    assert store.incumbent()["model_id"] == "a" and store.crown_mean("b") is None


def test_a_failed_rebuild_is_retried_inside_the_call_and_never_kept(
    tmp_path, monkeypatch
):
    store, flow = _king_and_contender(tmp_path, monkeypatch)

    class Flaky(Repeat):
        failures = 1

        def rebuild_at(self, seed):
            if self.failures:
                self.failures -= 1
                raise ca.RebuildInfra("host busy")
            return super().rebuild_at(seed)

    repeat, average = Flaky("b", [0.71] * N), _stepped(tmp_path)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=average
    )
    # the infrastructure failure was retried inside this call (ca._one) and the retry was the one new rebuild
    assert (outcome["outcome"], outcome["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_IN_PROGRESS,
    )
    assert len(repeat.asked) == 1 and store.kept_crown_rebuilds("b", KEY) == 1


def test_a_rebuild_that_never_recovers_is_a_counted_unavailable_not_an_endless_in_progress(
    tmp_path, monkeypatch
):
    """A persistent fault must not burn the GPU every tick: after the in-call retries it is UNAVAILABLE rebuild_unavailable,
    which the sweep counts, spaces and alerts, exactly as before stepwise."""
    store, flow = _king_and_contender(tmp_path, monkeypatch)

    class Broken(Repeat):
        def rebuild_at(self, seed):
            self.asked.append(seed)
            raise ca.RebuildInfra("host busy")

    repeat = Broken("b", [0.71] * N)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=_stepped(tmp_path)
    )
    assert (outcome["outcome"], outcome["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_UNAVAILABLE,
    )
    assert (
        len(repeat.asked) == 3
    )  # the registered retries (2) plus the first try, all the same seed
    assert store.kept_crown_rebuilds("b", KEY) == 0


@pytest.mark.parametrize("unmeasured", ["FAILED_INFRA", "INDETERMINATE_EVIDENCE"])
def test_a_returned_unmeasured_body_once_is_retried_inside_the_call_and_the_step_is_the_kept_one(
    tmp_path, monkeypatch, unmeasured
):
    store, flow = _king_and_contender(tmp_path, monkeypatch)

    class OnceUnmeasured(Repeat):
        bad = 1

        def rebuild_at(self, seed):
            self.asked.append(seed)
            if self.bad:
                self.bad -= 1
                return _body("b", None, unmeasured)
            index = self.order.setdefault(seed, len(self.order))
            return _body("b", self.totals[index])

    repeat, average = OnceUnmeasured("b", [0.71] * N), _stepped(tmp_path)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=average
    )
    assert (outcome["outcome"], outcome["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_IN_PROGRESS,
    )
    assert len(repeat.asked) == 2  # the unmeasured body, then the retry that measured
    assert (
        store.kept_crown_rebuilds("b", KEY) == 1
    )  # the unmeasured body was never kept


@pytest.mark.parametrize("unmeasured", ["FAILED_INFRA", "INDETERMINATE_EVIDENCE"])
def test_a_returned_unmeasured_body_always_is_a_counted_unavailable_never_an_endless_in_progress(
    tmp_path, monkeypatch, unmeasured
):
    store, flow = _king_and_contender(tmp_path, monkeypatch)

    class AlwaysUnmeasured(Repeat):
        def rebuild_at(self, seed):
            self.asked.append(seed)
            return _body("b", None, unmeasured)

    repeat, average = AlwaysUnmeasured("b", [0.71] * N), _stepped(tmp_path)
    for tick in range(
        3
    ):  # tick after tick: every one is the counted refusal, never a silent in-progress
        outcome = flow.consider_private(
            "b", KEY, _comparator(), repeat=repeat, average=average
        )
        assert (outcome["outcome"], outcome["reason"]) == (
            bp.UNAVAILABLE,
            ca.REBUILD_UNAVAILABLE,
        )
        assert len(repeat.asked) == 3 * (
            tick + 1
        )  # the in-call retries (2) plus the first try, each tick
    assert store.kept_crown_rebuilds("b", KEY) == 0


# --- the live trigger files it and the sweep resumes it ------------------------------------------------------------------------


def test_the_live_trigger_files_an_in_progress_decision_without_an_attempt(
    tmp_path, monkeypatch
):
    store, flow = _king_and_contender(tmp_path, monkeypatch)
    repeat = Repeat("b", [0.71] * N)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=_stepped(tmp_path)
    )
    repeat.entry_id = digest("entry")
    lrr._file_if_paused(
        store, outcome, "pack", "b", digest("exam"), repeat, digest("pin")
    )
    assert [r["submission_id"] for r in store.paused_crowns("pack")] == ["b"]
    assert store.crown_pause_attempts("b", KEY) == (
        0,
        None,
    )  # no failed attempt counted


def test_the_sweep_resumes_it_every_tick_without_spacing_alert_or_resolution_until_decided(
    tmp_path, monkeypatch
):
    store, flow = _king_and_contender(tmp_path, monkeypatch)
    repeat, average = Repeat("b", [0.71] * N), _stepped(tmp_path)
    exam = digest("exam")
    first = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=average
    )
    repeat.entry_id = digest("entry")
    lrr._file_if_paused(store, first, "pack", "b", exam, repeat, digest("pin"))

    def reconsider(record):
        return flow.consider_private(
            record["submission_id"],
            record["evaluation_key"],
            _comparator(),
            repeat=repeat,
            average=average,
        )

    resolved_by_tick = []
    for _tick in range(
        CALLS - 1
    ):  # the live call was the first rebuild; each tick runs one more
        resolved_by_tick.append(
            sweep.sweep(store, reconsider, kind="pack", current_exam=exam)
        )
        assert store.crown_pause_attempts("b", KEY) == (
            0,
            None,
        )  # never counted, so never spaced and never alerted
    assert resolved_by_tick[:-1] == [[]] * (CALLS - 2)
    assert resolved_by_tick[-1] == [("b", f"{bp.CHALLENGER}:{ca.MEAN_EXCEEDS}")]
    assert store.incumbent()["model_id"] == "b"
    assert store.paused_crowns("pack") == []
    assert (
        len(repeat.asked) == CALLS
    )  # every rebuild ran exactly once across the live call and the ticks


def test_a_stepped_decision_resumes_across_a_restart_from_the_kept_rebuilds_and_equals_the_single_call_one(
    tmp_path, monkeypatch
):
    """Run 2 of the N + 1 stepped rebuilds (the live call and one sweep tick), then RESTART: a NEW PoolStore on the same file, a
    fresh Active and flow, cleared sweep process state. The sweep resumes from the rebuilds kept on disk: the kept ones are
    not run again, the decision and its private record equal the single-call ones, and the crown moves exactly once.
    """
    from carbon.battery.pool_store import PoolStore

    single = tmp_path / "single"
    single.mkdir()
    store0, flow0 = _king_and_contender(single, monkeypatch, contender_total=0.7123)
    flow0.consider_private(
        "b",
        KEY,
        _comparator(),
        repeat=Repeat("b", [0.7123] * N),
        average=_active(single, n=N),
    )
    expected_mean = store0.crown_mean("b")
    assert store0.incumbent()["model_id"] == "b" and expected_mean is not None

    stepped = tmp_path / "stepped"
    stepped.mkdir()
    store, flow = _king_and_contender(stepped, monkeypatch, contender_total=0.7123)
    exam = digest("exam")
    before = Repeat("b", [0.7123] * N)
    first = flow.consider_private(
        "b", KEY, _comparator(), repeat=before, average=_stepped(stepped)
    )
    before.entry_id = digest("entry")
    lrr._file_if_paused(store, first, "pack", "b", exam, before, digest("pin"))

    def tick(the_store, the_flow, the_repeat, the_average):
        return sweep.sweep(
            the_store,
            lambda record: the_flow.consider_private(
                record["submission_id"],
                record["evaluation_key"],
                _comparator(),
                repeat=the_repeat,
                average=the_average,
            ),
            kind="pack",
            current_exam=exam,
        )

    assert tick(store, flow, before, _stepped(stepped)) == []  # the second rebuild
    assert len(before.asked) == 2 and store.kept_crown_rebuilds("b", KEY) == 2
    assert store.incumbent()["model_id"] == "a"  # nothing moved yet

    # --- the restart: a new store on the SAME file, a new flow and Active, cleared process state ---
    del store, flow
    sweep._FIRST_SEEN.clear()
    sweep._KING_CHANGED.clear()
    reopened = PoolStore(stepped / "pool.sqlite", clock=lambda: 0.0)
    a, b = _body("a", 0.70), _body("b", 0.7123)
    monkeypatch.setattr(
        reopened,
        "private_evaluation_pair",
        _Pairs({"a": _pair(a, None), "b": _pair(b, a)}),
    )
    new_flow = bp.BankPromotion(
        reopened, registered_source_receipt_sha256=digest("pin")
    )
    after = Repeat("b", [0.7123] * N)
    after.entry_id = digest("entry")
    assert (
        reopened.kept_crown_rebuilds("b", KEY) == 2
    )  # the kept rebuilds survived the restart
    average = _stepped(stepped)
    resolved = []
    for _ in range(CALLS):  # more ticks than needed: the rest are no-ops
        resolved += tick(reopened, new_flow, after, average)
    assert resolved == [("b", f"{bp.CHALLENGER}:{ca.MEAN_EXCEEDS}")]  # decided once
    # the kept rebuilds were not run again: the remaining two ran, the first two did not
    assert len(before.asked) + len(after.asked) == CALLS
    assert len(after.asked) == CALLS - 2
    assert reopened.incumbent()["model_id"] == "b"
    assert (
        reopened.crown_mean("b") == expected_mean
    )  # equals the single-call decision's mean
    assert reopened.paused_crowns("pack") == []


def test_a_second_contender_waits_behind_the_one_in_progress(tmp_path, monkeypatch):
    a, b, c = _body("a", 0.70), _body("b", 0.71), _body("c", 0.72)
    store, flow = _flow(
        tmp_path,
        monkeypatch,
        {"a": _pair(a, None), "b": _pair(b, a), "c": _pair(c, a)},
    )
    flow.consider_private(
        "a",
        KEY,
        _comparator(),
        repeat=Repeat("a", [0.70] * N),
        average=_active(tmp_path, n=N),
    )
    average = _stepped(tmp_path)
    repeat_b = Repeat("b", [0.71] * N)
    first = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat_b, average=average
    )
    repeat_b.entry_id = digest("entry-b")
    lrr._file_if_paused(
        store, first, "pack", "b", digest("exam"), repeat_b, digest("pin")
    )
    repeat_c = Repeat("c", [0.72] * N)
    outcome = flow.consider_private(
        "c", KEY, _comparator(), repeat=repeat_c, average=average
    )
    assert (outcome["outcome"], outcome["reason"]) == (bp.UNAVAILABLE, bp.CROWN_QUEUED)
    assert (
        repeat_c.asked == []
    )  # no rebuild is spent on a contender that waits its turn


def test_a_genuine_failure_is_still_a_counted_attempt_and_alert_path(
    tmp_path, monkeypatch
):
    """Only REBUILD_IN_PROGRESS skips the attempt count: a real UNAVAILABLE (rebuild_unavailable) still counts."""
    store, _flow_unused = _king_and_contender(tmp_path, monkeypatch)
    repeat = Repeat("b", [0.71] * N)
    repeat.entry_id = digest("entry")
    failed = {
        "outcome": bp.UNAVAILABLE,
        "reason": ca.REBUILD_UNAVAILABLE,
        "evaluation_key": KEY,
    }
    lrr._file_if_paused(
        store, failed, "pack", "b", digest("exam"), repeat, digest("pin")
    )
    assert store.crown_pause_attempts("b", KEY)[0] == 1


def test_the_one_rebuild_helper_is_what_the_kings_stepwise_remeasure_uses():
    assert lrr.RebuildStep is ca.RebuildStep
    assert lrr._one_rebuild_per_call.__module__ == lrr.__name__

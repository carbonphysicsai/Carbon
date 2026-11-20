"""Over-broad audit #10 (V2's ruling: NARROW): already-admitted work reads the last good chain snapshot up to one epoch.

Between the 60 s window and one epoch (360 blocks x 12 s) grading goes on, the provider's registration re-check and the
allowance group read the last good snapshot, and every crown in the process waits for a fresh snapshot (a deregistration
inside the window is caught at the next fresh one, before any crown). Request authentication, admission and the public
answer keep the 60 s window. Past one epoch, a high-water conflict, or an unavailable watermark: as before (no snapshot).
"""

from __future__ import annotations

import io
import json
import threading
from types import SimpleNamespace

import pytest

from carbon.battery import intake
from carbon.battery.intake import (
    GRADING_SNAPSHOT_MAX_AGE_S,
    SNAPSHOT_MAX_AGE_S,
    SnapshotWindow,
    grading_snapshot,
)
from carbon.challenge_validator import operator_pause

EPOCH = 360 * 12.0


class _Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def _snapshot(taken_at, *, context="ctx", members=None, block=100):
    members = {} if members is None else members
    return SimpleNamespace(
        snapshot_id=f"snap-{taken_at}",
        timestamp_ms=int(taken_at * 1000),
        context=context,
        finalized_block=block,
        resolve=lambda hotkey: members.get(hotkey),
    )


def _window(age_s, **kwargs):
    clock = _Clock()
    window = SnapshotWindow(clock=clock)
    window.add(_snapshot(clock.now - age_s, **kwargs))
    return window


@pytest.fixture(autouse=True)
def _clean_process_state():
    previous = operator_pause.hold_crowns_until_fresh(None)
    intake._STALE.update(since=None, uses=0)
    yield
    operator_pause.hold_crowns_until_fresh(previous)
    intake._STALE.update(since=None, uses=0)


def _lines(out):
    return [json.loads(line) for line in out.getvalue().splitlines()]


# --- the window ---------------------------------------------------------------------------------------------------


def test_the_grading_bound_is_one_epoch_and_the_request_window_stays_60_s():
    assert GRADING_SNAPSHOT_MAX_AGE_S == EPOCH
    assert SNAPSHOT_MAX_AGE_S == 60.0


@pytest.mark.parametrize("age", [0.0, 30.0, 60.0])
def test_inside_60_s_both_reads_answer_the_same_snapshot(age):
    window = _window(age)
    assert window.latest() is not None
    assert grading_snapshot(window) is window.latest()


@pytest.mark.parametrize("age", [61.0, 600.0, EPOCH])
def test_a_blip_past_60_s_keeps_the_last_good_snapshot_for_grading_only(age):
    window = _window(age)
    assert (
        window.latest() is None
    )  # request authentication, admission and the public answer: 503 as before
    assert grading_snapshot(window) is window.latest_good(EPOCH) is not None


def test_past_one_epoch_there_is_no_snapshot_as_before():
    window = _window(EPOCH + 1)
    assert window.latest() is None and grading_snapshot(window) is None


def test_a_window_without_latest_good_answers_latest():
    fake = SimpleNamespace(latest=lambda: "fresh-or-none")
    assert grading_snapshot(fake) == "fresh-or-none"


def test_one_loud_line_when_the_stale_use_starts_and_one_when_it_ends():
    clock = _Clock()
    window = SnapshotWindow(clock=clock)
    window.add(_snapshot(clock.now))
    out = io.StringIO()
    assert grading_snapshot(window, out=out) is not None and _lines(out) == []
    clock.now += 120.0
    for _ in range(3):
        assert grading_snapshot(window, out=out) is not None
    started = _lines(out)
    assert [line["event"] for line in started] == ["chain_snapshot_stale_in_epoch"]
    assert started[0]["age_s"] == 120 and started[0]["max_age_s"] == int(EPOCH)
    window.add(_snapshot(clock.now))  # the refresher reads the chain again
    assert grading_snapshot(window, out=out) is not None
    ended = _lines(out)[-1]
    assert ended["event"] == "chain_snapshot_fresh_again" and ended["uses"] == 3
    # counts only: no snapshot id, block, hotkey or path in any line
    assert all(
        set(line) <= {"ts", "service", "event", "age_s", "max_age_s", "uses", "stale_s"}
        for line in _lines(out)
    )


def test_running_past_the_epoch_ends_the_stale_use_loudly():
    clock = _Clock()
    window = SnapshotWindow(clock=clock)
    window.add(_snapshot(clock.now))
    out = io.StringIO()
    clock.now += 61.0
    assert grading_snapshot(window, out=out) is not None
    clock.now += EPOCH
    assert grading_snapshot(window, out=out) is None
    assert _lines(out)[-1]["event"] == "chain_snapshot_stale_past_epoch"


def _receiver_window(age_s, *, conflict=False, unavailable=False):
    from carbon.challenge_validator.direct_receiver import ReceiverSnapshotWindow

    window = object.__new__(ReceiverSnapshotWindow)
    window._window = _window(age_s)
    window._lock = threading.RLock()
    window._state = {"conflict": conflict}
    window._unavailable = unavailable
    return window


def test_the_receiver_window_keeps_the_last_good_snapshot_up_to_one_epoch():
    window = _receiver_window(300.0)
    assert window.latest() is None and grading_snapshot(window) is not None
    assert grading_snapshot(_receiver_window(EPOCH + 1)) is None


@pytest.mark.parametrize("age", [0.0, 300.0])
def test_a_conflict_or_an_unavailable_watermark_grants_nothing_at_any_age(age):
    assert grading_snapshot(_receiver_window(age, conflict=True)) is None
    # a fresher read whose watermark was not made durable: the older snapshot may predate a revocation
    assert grading_snapshot(_receiver_window(age, unavailable=True)) is None


# --- grading goes on; crowns wait for a fresh snapshot ---------------------------------------------------------------


def _grader(window):
    from carbon.challenge_validator.auto_grade import AutoGrader

    grader = object.__new__(AutoGrader)
    grader.intake = SimpleNamespace(window=window)
    return grader


def test_a_chain_blip_past_60_s_no_longer_pauses_grading():
    assert _grader(_window(61.0)).chain_degraded() is False
    assert _grader(_window(EPOCH - 1)).chain_degraded() is False


def test_past_one_epoch_grading_pauses_as_before():
    assert _grader(_window(EPOCH + 1)).chain_degraded() is True


def test_crowns_wait_for_a_fresh_snapshot_and_weights_are_untouched(tmp_path):
    window = _window(61.0)
    operator_pause.hold_crowns_until_fresh(lambda: window.latest() is not None)
    assert operator_pause.crowns_paused(tmp_path) is True
    assert (
        operator_pause.weights_paused(tmp_path) is False
    )  # weights read the chain themselves
    window.add(_snapshot(window.clock.now, block=101))
    assert operator_pause.crowns_paused(tmp_path) is False


def test_an_unreadable_freshness_holds_crowns():
    def broken():
        raise OSError("high-water file unreadable")

    operator_pause.hold_crowns_until_fresh(broken)
    assert operator_pause.chain_stale() is True and operator_pause.crowns_paused(None)


def test_no_hold_registered_changes_nothing(tmp_path):
    assert operator_pause.chain_stale() is False
    assert operator_pause.crowns_paused(tmp_path) is False


def test_the_operators_flag_still_pauses_with_a_fresh_chain(tmp_path):
    import os

    flag = operator_pause.flag_path(tmp_path)
    flag.write_text(json.dumps({"crowns_paused": True}), encoding="utf-8")
    os.chmod(flag, 0o600)
    operator_pause.hold_crowns_until_fresh(lambda: True)
    assert operator_pause.crowns_paused(tmp_path) is True


def test_the_crown_sweep_decides_nothing_while_the_chain_is_stale(tmp_path):
    from carbon.challenge_validator import crown_pause_sweep

    class Store:
        path = tmp_path / "pool.sqlite3"
        reads = 0

        def paused_crowns(self, kind):
            Store.reads += 1
            return []

    window = _window(61.0)
    operator_pause.hold_crowns_until_fresh(lambda: window.latest() is not None)

    def reconsider(_record):
        raise AssertionError("no crown is decided on a stale chain")

    assert (
        crown_pause_sweep.sweep(Store(), reconsider, kind="pack", current_exam="e")
        == []
    )
    assert Store.reads == 0
    window.add(_snapshot(window.clock.now, block=101))
    assert (
        crown_pause_sweep.sweep(Store(), reconsider, kind="pack", current_exam="e")
        == []
    )
    assert (
        Store.reads == 1
    )  # fresh again: the sweep runs (and decides the held records in filing order)


# --- registration re-check and allowance group read the same bound ---------------------------------------------------


def _providers(window, snapshot):
    from carbon.challenge_validator.direct_receiver import OwnerProviders

    providers = object.__new__(OwnerProviders)
    providers.window, providers.snapshot = window, snapshot
    return providers


def test_the_owner_registration_recheck_reads_the_last_good_snapshot_up_to_one_epoch():
    start = _snapshot(0.0)
    stale = _window(300.0)
    assert _providers(stale, start)._observed() is stale.latest_good(EPOCH)
    assert (
        _providers(_window(EPOCH + 1), start)._observed() is None
    )  # unknown, not revoked
    other = _window(300.0, context="other-chain")
    assert _providers(other, start)._observed() is None


def test_a_funded_hotkey_keeps_its_group_through_a_blip():
    from carbon.challenge_validator.allowance_groups import Grouping
    from carbon.challenge_validator.funder_map import FunderMap

    members = {"5Hot": SimpleNamespace(coldkey="5Cold")}
    configured = {
        "unmapped_coldkey": "per_coldkey",
        "unresolved_hotkey": "per_hotkey",
        "max_map_age_blocks": 100,
    }
    expected = FunderMap.empty().group("5Cold")
    for age in (0.0, 61.0, EPOCH):
        grouping = Grouping(configured, _window(age, members=members), lambda: None)
        assert (
            grouping("5Hot") == expected
        )  # never the per-hotkey fallback inside the epoch
    past = Grouping(configured, _window(EPOCH + 1, members=members), lambda: None)
    assert past("5Hot") == "h:5Hot"  # past one epoch: as before

"""Mainnet first for the host's official-grading lock (owner, 13 Nov 2026: "mainnet first").

When the lock frees, a waiting door bound to finney 116 takes it before any testnet door. Host side only: grading itself
is untouched, a round that already holds the lock is never preempted, and a door alone on the host (or doors of one
network) order exactly as before (`test_grade_age_order`, `test_door_drain`). Testnet is never starved forever: a testnet
round held back for `MAINNET_FIRST_PATIENCE_S` counts as outranking too. Fixture pids, times and networks only.
"""

from __future__ import annotations

import fcntl
import os
import threading
import time

import pytest

from carbon.backbone_catalog.receipt_job import GRADING_LOCK
from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.direct_intake import _WorkLock

POLL = 0.05
OTHER = 4001  # another door's pid on the host
OTHER_START = 11


@pytest.fixture
def host(tmp_path, monkeypatch):
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    (host / direct_intake.WAITING_DIR).mkdir(mode=0o700)
    live = {OTHER: OTHER_START, 4002: 22}
    real = direct_intake._process_start
    monkeypatch.setattr(
        direct_intake,
        "_process_start",
        lambda pid: live[pid] if pid in live else real(pid),
    )
    return host


def _other_waits(host, since, *, pid=OTHER, start=OTHER_START, mainnet=False):
    """Another door's entry in the host's waiting list; ``mainnet`` also puts it in the priority list."""
    name = f"{pid}-{start}"
    if mainnet:
        (host / direct_intake.PRIORITY_DIR).mkdir(mode=0o700, exist_ok=True)
        (host / direct_intake.PRIORITY_DIR / name).touch()
    (host / direct_intake.WAITING_DIR / name).write_text(str(since))
    return name


def _leave(host, name):
    (host / direct_intake.WAITING_DIR / name).unlink()
    (host / direct_intake.PRIORITY_DIR / name).unlink(missing_ok=True)


def _try(work, kind, **kw):
    """Enter one round in a thread; returns (entered event, release event, thread, outcome list)."""
    entered, release, outcome = threading.Event(), threading.Event(), []

    def run():
        try:
            with work.taking(kind, **kw):
                entered.set()
                release.wait(5)
        except direct_intake.WorkDeclined as declined:
            outcome.append(declined.reason)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return entered, release, thread, outcome


def _finish(release, thread):
    release.set()
    thread.join(5)
    assert not thread.is_alive()


def _entries(host, directory):
    path = host / directory
    return sorted(p.name for p in path.iterdir()) if path.exists() else []


GRADE = {"has_work": lambda: True}


# --- a mainnet waiter beats a testnet waiter ----------------------------------------------------------------------------


def test_a_testnet_round_waits_for_a_waiting_mainnet_door_even_with_the_older_submission(
    host,
):
    """The testnet round's place (1000) is OLDER than the finney door's (5000): ordinary first come, first served would
    let it go first. Mainnet first holds it back, and it goes the moment the finney door's turn is over.
    """
    name = _other_waits(host, 5000, mainnet=True)
    work = _WorkLock(host, poll_s=POLL, network="testnet")
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 1000)
    time.sleep(8 * POLL)
    assert not entered.is_set()
    _leave(host, name)  # the finney door has had its turn
    assert entered.wait(2)
    _finish(release, thread)


def test_a_mainnet_round_goes_ahead_of_an_older_testnet_waiter(host):
    _other_waits(
        host, 1000
    )  # a testnet door waiting since the older submission, no priority file
    work = _WorkLock(host, poll_s=POLL, network="finney")
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 5000)
    assert entered.wait(2)
    _finish(release, thread)


def test_a_mainnet_round_holds_a_priority_entry_only_while_it_waits(host):
    """While it waits the finney door is in BOTH lists (the priority file first); once it holds the lock, in neither."""
    holder = os.open(host / GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(holder, fcntl.LOCK_EX)  # a testnet grade is running
    try:
        work = _WorkLock(host, poll_s=POLL, network="finney")
        entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 5000)
        deadline = time.time() + 2
        while time.time() < deadline and not _entries(host, direct_intake.PRIORITY_DIR):
            time.sleep(POLL)
        assert _entries(host, direct_intake.PRIORITY_DIR) == _entries(
            host, direct_intake.WAITING_DIR
        )
        assert len(_entries(host, direct_intake.WAITING_DIR)) == 1
        assert not entered.is_set()  # the running grade is never preempted
    finally:
        fcntl.flock(holder, fcntl.LOCK_UN)
        os.close(holder)
    assert entered.wait(2)
    assert _entries(host, direct_intake.WAITING_DIR) == []
    assert _entries(host, direct_intake.PRIORITY_DIR) == []
    _finish(release, thread)


def test_an_advance_round_without_a_place_also_waits_for_a_mainnet_door(host):
    """An unqueued testnet round (a rebuild with nothing ungraded on its door) never queues among testnet doors, but it
    does not jump a waiting finney door either."""
    name = _other_waits(host, 5000, mainnet=True)
    work = _WorkLock(host, poll_s=POLL, network="testnet")
    entered, release, thread, _ = _try(work, "advance")
    time.sleep(8 * POLL)
    assert not entered.is_set()
    _leave(host, name)
    assert entered.wait(2)
    _finish(release, thread)


def test_a_mainnet_door_never_yields_to_a_testnet_waiter_of_any_age(host):
    _other_waits(host, 1)  # the oldest possible testnet place
    work = _WorkLock(host, poll_s=POLL, network="finney")
    entered, release, thread, _ = _try(work, "advance")
    assert entered.wait(2)
    _finish(release, thread)


def test_two_mainnet_doors_keep_the_first_come_order(host):
    _other_waits(host, 1000, mainnet=True)
    work = _WorkLock(host, poll_s=POLL, network="finney")
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 2000)
    time.sleep(8 * POLL)
    assert not entered.is_set()
    _leave(host, f"{OTHER}-{OTHER_START}")
    assert entered.wait(2)
    _finish(release, thread)


# --- testnet is never starved forever -----------------------------------------------------------------------------------


def test_a_testnet_round_held_back_past_its_patience_goes_before_a_newer_mainnet_waiter(
    host, monkeypatch
):
    monkeypatch.setattr(direct_intake, "MAINNET_FIRST_PATIENCE_S", 0.4)
    _other_waits(
        host, 5000, mainnet=True
    )  # a finney door that arrived later and never leaves
    work = _WorkLock(host, poll_s=POLL, network="testnet")
    started = time.monotonic()
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 1000)
    time.sleep(0.2)
    assert not entered.is_set()  # still inside its patience
    assert entered.wait(3)
    assert time.monotonic() - started >= 0.4
    _finish(release, thread)


def test_a_promoted_testnet_round_still_waits_for_an_older_mainnet_waiter(
    host, monkeypatch
):
    """Patience puts a testnet round in the priority class, first come within it: a finney door whose place is older
    still goes first. The testnet round is then in the priority list while it waits."""
    monkeypatch.setattr(direct_intake, "MAINNET_FIRST_PATIENCE_S", 0.2)
    name = _other_waits(host, 500, mainnet=True)
    work = _WorkLock(host, poll_s=POLL, network="testnet")
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 1000)
    time.sleep(1.0)
    assert not entered.is_set()
    mine = [n for n in _entries(host, direct_intake.PRIORITY_DIR) if n != name]
    assert len(mine) == 1  # promoted: visible to the other doors as outranking
    _leave(host, name)
    assert entered.wait(2)
    assert _entries(host, direct_intake.PRIORITY_DIR) == []
    _finish(release, thread)


def test_the_patience_is_a_finite_operational_bound():
    assert 0 < direct_intake.MAINNET_FIRST_PATIENCE_S <= 24 * 3600


def test_patience_starts_again_for_every_round(host, monkeypatch):
    monkeypatch.setattr(direct_intake, "MAINNET_FIRST_PATIENCE_S", 0.2)
    name = _other_waits(host, 5000, mainnet=True)
    work = _WorkLock(host, poll_s=POLL, network="testnet")
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 1000)
    assert entered.wait(3)  # promoted after its patience
    _finish(release, thread)
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 1001)
    time.sleep(0.1)
    assert not entered.is_set()  # a new round is held back again, with a fresh patience
    _leave(host, name)
    assert entered.wait(2)
    _finish(release, thread)


# --- the pause flag still works --------------------------------------------------------------------------------------------


def test_a_draining_mainnet_door_leaves_both_lists_and_holds_nobody_back(
    host, tmp_path
):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    holder = os.open(host / GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(holder, fcntl.LOCK_EX)
    try:
        work = _WorkLock(host, state_dir=state, poll_s=POLL, network="finney")
        entered, release, thread, outcome = _try(
            work, "grade", **GRADE, since=lambda: 5000
        )
        deadline = time.time() + 2
        while time.time() < deadline and not _entries(host, direct_intake.PRIORITY_DIR):
            time.sleep(POLL)
        assert len(_entries(host, direct_intake.PRIORITY_DIR)) == 1
        (state / direct_intake.DRAIN_NAME).write_text("")
        thread.join(3)
        assert not thread.is_alive()
        assert outcome == ["draining"]
        assert _entries(host, direct_intake.WAITING_DIR) == []
        assert _entries(host, direct_intake.PRIORITY_DIR) == []
    finally:
        fcntl.flock(holder, fcntl.LOCK_UN)
        os.close(holder)
    # a testnet door is no longer held back
    testnet = _WorkLock(host, poll_s=POLL, network="testnet")
    entered, release, thread, _ = _try(testnet, "grade", **GRADE, since=lambda: 1000)
    assert entered.wait(2)
    _finish(release, thread)


def test_a_draining_testnet_door_held_back_by_mainnet_gives_up_at_once(host, tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    _other_waits(host, 5000, mainnet=True)
    work = _WorkLock(host, state_dir=state, poll_s=POLL, network="testnet")
    entered, _release, thread, outcome = _try(
        work, "grade", **GRADE, since=lambda: 1000
    )
    time.sleep(4 * POLL)
    assert not entered.is_set()
    (state / direct_intake.DRAIN_NAME).write_text("")
    thread.join(3)
    assert not thread.is_alive()
    assert outcome == ["draining"]
    assert _entries(host, direct_intake.WAITING_DIR) == [
        f"{OTHER}-{OTHER_START}"
    ]  # only the other door's


def test_a_stopping_door_held_back_by_mainnet_gives_up(host):
    stop = threading.Event()
    _other_waits(host, 5000, mainnet=True)
    work = _WorkLock(host, poll_s=POLL, stop=stop, network="testnet")
    _entered, _release, thread, outcome = _try(work, "advance")
    time.sleep(4 * POLL)
    stop.set()
    thread.join(3)
    assert outcome == ["stopping"]


# --- unchanged where there is nothing to prioritise -----------------------------------------------------------------------


@pytest.mark.parametrize("network", ["testnet", "finney"])
@pytest.mark.parametrize("kind", ["grade", "advance"])
def test_a_door_alone_on_the_host_is_unchanged(host, network, kind):
    work = _WorkLock(host, poll_s=POLL, network=network)
    kw = {"has_work": lambda: True} if kind == "grade" else {}
    entered, release, thread, _ = _try(work, kind, **kw, since=lambda: 1000)
    assert entered.wait(2)
    assert _entries(host, direct_intake.PRIORITY_DIR) == []
    _finish(release, thread)


def test_testnet_doors_order_by_place_exactly_as_before(host):
    """No priority entry anywhere: the oldest submission's door goes first, whatever the network the others bind."""
    _other_waits(host, 1000)
    work = _WorkLock(host, poll_s=POLL, network="testnet")
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 2000)
    time.sleep(8 * POLL)
    assert not entered.is_set()
    _leave(host, f"{OTHER}-{OTHER_START}")
    assert entered.wait(2)
    _finish(release, thread)


def test_a_door_without_a_network_binds_the_process_row(host, monkeypatch):
    from carbon.chain import models

    monkeypatch.setattr(models, "CARBON_NETWORK", "finney")
    assert _WorkLock(host)._mainnet
    monkeypatch.setattr(models, "CARBON_NETWORK", "testnet")
    assert not _WorkLock(host)._mainnet


def test_localnet_is_not_a_mainnet_door(host):
    assert not _WorkLock(host, network="localnet")._mainnet


def test_an_older_build_writing_no_priority_file_counts_as_testnet(host):
    """A waiting entry with no priority file (an older build's door) is class 1: a finney door goes before it."""
    work = _WorkLock(host, poll_s=POLL, network="finney")
    _other_waits(host, 1)
    assert work._classed_waiters() == [(1, 1, OTHER)]
    _other_waits(host, 1, mainnet=True)
    assert work._classed_waiters() == [(0, 1, OTHER)]


def test_a_dead_door_leaves_no_rank(host, monkeypatch):
    """A finney door that crashed while waiting leaves both files behind, but its pid no longer names that process."""
    _other_waits(host, 5000, mainnet=True, pid=4099, start=7)
    work = _WorkLock(host, poll_s=POLL, network="testnet")
    assert work._classed_waiters() == []
    entered, release, thread, _ = _try(work, "grade", **GRADE, since=lambda: 1000)
    assert entered.wait(2)
    _finish(release, thread)

"""Per-door drain (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A; Validator 17:19 conditions).

A door never blocks on the host's grading lock: it polls, gives up the round on stop or DRAINING, takes the host
lock only when it has something to grade, and keeps an atomic in-flight record a deploy reads instead of the host
lock. The host lock stays the one grading mutex (one grade per host at a time)."""

from __future__ import annotations

import fcntl
import json
import os
import threading
import time

import pytest

from carbon.backbone_catalog import receipt_job
from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.direct_intake import (
    DRAIN_NAME,
    INFLIGHT_NAME,
    WAIT_NAME,
    _WorkLock,
)
from scripts.dev.release import door_drain

POLL = 0.05


@pytest.fixture
def dirs(tmp_path):
    host = tmp_path / "host"
    state = tmp_path / "state"
    for d in (host, state):
        d.mkdir(mode=0o700)
    return host, state


def _hold_host(host):
    """Another door (or the Deploy Engineer's grade_lock.py) holding the host's grading lock."""
    fd = os.open(host / receipt_job.GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


class Grader:
    def __init__(self, work=True, seen=None, during=None):
        self.work, self.seen, self.during = (
            work,
            seen if seen is not None else [],
            during,
        )

    def has_work(self):
        return self.work

    def run_once(self):
        self.seen.append(time.monotonic())
        if self.during is not None:
            self.during()


def _loop(grader, stop, work):
    thread = threading.Thread(
        target=direct_intake._grade_loop, args=(grader, stop, work), daemon=True
    )
    thread.start()
    return thread


def test_draining_is_read_before_every_attempt_with_a_planted_pending_task(
    dirs, monkeypatch
):
    host, state = dirs
    monkeypatch.setattr(direct_intake, "_backoff_s", lambda n: POLL)
    (state / DRAIN_NAME).write_text("{}")
    stop = threading.Event()
    grader = Grader(work=True)
    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    with (
        pytest.raises(direct_intake.WorkDeclined, match="draining"),
        work.taking("grade", has_work=grader.has_work),
    ):
        pytest.fail("work taken while draining")
    assert receipt_job.grading_busy(host) is False
    (state / DRAIN_NAME).unlink()
    with work.taking("grade", has_work=grader.has_work):
        assert receipt_job.grading_busy(host) is True
        assert json.loads((state / INFLIGHT_NAME).read_text())["kind"] == "grade"
    assert (
        not (state / INFLIGHT_NAME).exists() and receipt_job.grading_busy(host) is False
    )


def test_a_door_waiting_on_another_doors_grade_holds_nothing_and_stops_promptly(dirs):
    host, state = dirs
    fd = _hold_host(host)
    stop = threading.Event()
    grader = Grader(work=True)
    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    thread = _loop(grader, stop, work)
    try:
        deadline = time.monotonic() + 5
        while not (state / WAIT_NAME).exists() and time.monotonic() < deadline:
            time.sleep(POLL)
        assert (
            state / WAIT_NAME
        ).exists()  # the starvation-alert input: waiting since when
        assert not (
            state / INFLIGHT_NAME
        ).exists()  # waiting is not in flight: the deploy sees this door idle
        assert door_drain.read_once(state)["busy"] is False
        stop.set()  # SIGTERM while waiting: the loop ends, no work starts after stop
        thread.join(2)
        assert not thread.is_alive() and grader.seen == []
        assert not (state / WAIT_NAME).exists()
    finally:
        stop.set()
        _release(fd)


def test_the_host_lock_stays_the_one_grading_mutex(dirs):
    host, state = dirs
    fd = _hold_host(host)
    stop = threading.Event()
    seen = []
    busy = []
    grader = Grader(
        work=True,
        seen=seen,
        during=lambda: busy.append(door_drain.read_once(state)["busy"]),
    )
    thread = _loop(
        grader, stop, _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    )
    try:
        time.sleep(10 * POLL)
        assert seen == []  # no grade while another holds the host lock
        _release(fd)
        fd = None
        deadline = time.monotonic() + 5
        while not seen and time.monotonic() < deadline:
            time.sleep(POLL)
        assert seen and busy[0] is True  # in flight, by this live process
    finally:
        stop.set()
        thread.join(2)
        if fd is not None:
            _release(fd)


def test_an_idle_door_never_takes_the_host_lock(dirs, monkeypatch):
    host, state = dirs
    calls = []
    real = _WorkLock._try_host
    monkeypatch.setattr(
        _WorkLock, "_try_host", lambda self: calls.append(1) or real(self)
    )
    stop = threading.Event()
    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    with (
        pytest.raises(direct_intake.WorkDeclined, match="idle"),
        work.taking("grade", has_work=lambda: False),
    ):
        pass
    assert calls == [] and not (state / WAIT_NAME).exists()


def test_a_record_left_by_a_crash_is_set_aside_at_start_never_trusted(dirs):
    host, state = dirs
    (state / INFLIGHT_NAME).write_text(
        json.dumps({"pid": 1, "pid_start": 1, "kind": "grade"})
    )
    (state / WAIT_NAME).write_text("{}")
    _WorkLock(host, state_dir=state)
    assert not (state / INFLIGHT_NAME).exists() and not (state / WAIT_NAME).exists()
    names = sorted(p.name for p in state.iterdir())
    assert [n.split(".stale-")[0] for n in names] == [INFLIGHT_NAME, WAIT_NAME]


def test_the_in_flight_record_is_written_atomically(dirs, monkeypatch):
    host, state = dirs
    replaced = []
    real = os.replace
    monkeypatch.setattr(
        direct_intake.os, "replace", lambda a, b: replaced.append(str(b)) or real(a, b)
    )
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    with work.taking("advance"):
        assert str(state / INFLIGHT_NAME) in replaced
        assert not [
            p for p in state.iterdir() if p.name.startswith(".")
        ]  # no staging file left


def test_a_failed_round_releases_both_locks_and_the_record(dirs):
    host, state = dirs
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    with pytest.raises(RuntimeError), work.taking("grade"):
        raise RuntimeError("grade failed")
    assert (
        receipt_job.grading_busy(host) is False and not (state / INFLIGHT_NAME).exists()
    )
    with work.taking("grade"):  # the door's own lock was released too
        pass


def test_snapshot_refresh_never_waits_on_the_host_lock(dirs):
    """Validator 17:19 (1): skipping work rounds never starves the registration snapshot: the refresher is its own
    thread and takes no work lock, so snapshots stay fresh while every work round is declined.
    """
    import asyncio

    from carbon.battery.intake import refresher

    host, state = dirs
    fd = _hold_host(host)
    (state / DRAIN_NAME).write_text("{}")
    added = []

    class Window:
        def add(self, snapshot):
            added.append(snapshot)

    class Reader:
        async def capture(self, context):
            await asyncio.sleep(0)
            return object()

    stop = threading.Event()
    thread = threading.Thread(
        target=refresher,
        args=(Window(), None),
        kwargs={"reader": Reader(), "period": POLL, "stop": stop},
    )
    thread.start()
    try:
        time.sleep(10 * POLL)
    finally:
        stop.set()
        thread.join(2)
        _release(fd)
    assert len(added) >= 3
    import inspect

    source = inspect.getsource(direct_intake.serve_loopback)
    refresh_args = source[
        source.index("target=refresher") : source.index("target=_advance_loop")
    ]
    assert "work" not in refresh_args


def test_door_drain_tool_reads_this_door_only(dirs):
    host, state = dirs
    fd = _hold_host(host)  # another door grades: this door is still idle
    try:
        door_drain.start(state)
        assert door_drain.status(state, gap=0)["state"] == "IDLE"
        # a live in-flight record (this test process) = busy; a dead one = stale, not busy
        (state / INFLIGHT_NAME).write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "pid_start": direct_intake._process_start(os.getpid()),
                }
            )
        )
        assert door_drain.status(state, gap=0)["state"] == "BUSY"
        (state / INFLIGHT_NAME).write_text(
            json.dumps({"pid": 2**22 + 7, "pid_start": 5})
        )
        read = door_drain.status(state, gap=0)
        assert read["state"] == "IDLE" and read["read"]["stale_record"] is True
        (state / INFLIGHT_NAME).write_text(
            json.dumps({"pid": os.getpid(), "pid_start": 1})
        )
        assert (
            door_drain.status(state, gap=0)["state"] == "IDLE"
        )  # pid reused by another process
        (state / INFLIGHT_NAME).write_text("{not json")
        assert door_drain.status(state, gap=0)["state"] == "BUSY"  # doubt is never idle
        (state / INFLIGHT_NAME).write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "pid_start": direct_intake._process_start(os.getpid()),
                }
            )
        )
        ticks = iter(range(100))
        timed = door_drain.wait(
            state, 3, gap=0, poll=0, sleep=lambda s: None, clock=lambda: next(ticks)
        )
        assert timed["state"] == "TIMED_OUT" and (state / DRAIN_NAME).exists()
        assert (
            door_drain.clear(state) == {"state": "NOT_DRAINING"}
            and not (state / DRAIN_NAME).exists()
        )
    finally:
        _release(fd)

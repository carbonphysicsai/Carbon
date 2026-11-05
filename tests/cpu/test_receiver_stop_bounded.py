"""Design §2.3 / H4a: a receiver stop is bounded. The TL's 91 s stop + SIGKILL, reproduced (by the H3 implementer).

These run the REAL ``serve_loopback`` work loops (``_advance_loop``, ``_grade_loop``, ``_WorkLock``) with a
stand-in intake and grader, exactly as the existing receiver tests do (``object.__new__(DirectRecipeIntake)``).
Before H4a both failed (the work-lock waits were blocking and ignored stop); H4a's `_WorkLock` polls and gives up
the round on stop, so both pass.
"""

from __future__ import annotations

import fcntl
import os
import sys
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="flock + Linux")

#: The test's stop budget. Design §2.3 asks ≤ 10 s for the whole stop (TimeoutStopSec=15); the work loops'
#: own share must be far smaller, so 5 s here keeps the test fast and still separates bounded from unbounded.
STOP_BUDGET_S = 5.0


def _intake(calls, stop):
    from carbon.challenge_validator import direct_intake

    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.window, intake.context = object(), object()

    def advance():
        calls.append(("advance", stop.is_set()))

    intake.advance = advance
    return intake


def _serve_in_thread(direct_intake, intake, stop, **kwargs):
    returned = threading.Event()

    def run():
        try:
            direct_intake.serve_loopback(
                intake, {"host": "127.0.0.1", "port": 0}, stop=stop, **kwargs
            )
        finally:
            returned.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, returned


def test_stop_at_listening_while_another_door_holds_the_host_lock_is_bounded(
    tmp_path, monkeypatch
):
    """A just-started receiver is stopped right at LISTENING while ANOTHER door is grading (it holds the
    host-wide official-grading.lock). Today the stop waits for that other door's whole grade; under systemd's
    default TimeoutStopSec=90 s that is the observed 91 s + SIGKILL."""
    from carbon.backbone_catalog import receipt_job
    from carbon.challenge_validator import direct_intake

    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    other_door = os.open(
        tmp_path / receipt_job.GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600
    )
    fcntl.flock(other_door, fcntl.LOCK_EX)  # another door's grade in progress
    stop, calls = threading.Event(), []
    thread, returned = _serve_in_thread(
        direct_intake,
        _intake(calls, stop),
        stop,
        ready=lambda _address: stop.set(),  # SIGTERM right at LISTENING
        grading_lock_dir=tmp_path,
    )
    try:
        assert returned.wait(STOP_BUDGET_S), "stop was not bounded"
        assert calls == [], "no work may start after stop"
    finally:
        fcntl.flock(
            other_door, fcntl.LOCK_UN
        )  # the other door's grade ends: today's stop completes here
        os.close(other_door)
        thread.join(10)


def test_stop_while_own_grade_holds_the_work_lock_is_bounded(monkeypatch):
    """This door's own grade holds the work lock (a just-started spare picks up a PENDING entry at once);
    the advance thread queues behind it. Today the stop waits for the whole grade."""
    from carbon.challenge_validator import direct_intake

    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    grading, release = threading.Event(), threading.Event()

    class Grader:
        def run_once(self):
            grading.set()
            release.wait(60)  # a long grade

    stop, calls = threading.Event(), []

    def ready(_address):
        assert grading.wait(5)
        time.sleep(
            1.3
        )  # the advance loop's 1 s idle wait ends; it now blocks on the work lock
        stop.set()

    thread, returned = _serve_in_thread(
        direct_intake, _intake(calls, stop), stop, ready=ready, grader=Grader()
    )
    try:
        assert returned.wait(1.3 + STOP_BUDGET_S), "stop was not bounded"
        assert not [c for c in calls if c[1]], "no advance pass may start after stop"
    finally:
        release.set()
        thread.join(10)

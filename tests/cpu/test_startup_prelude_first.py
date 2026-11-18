"""Restart speed (case-procs + V2, 18 Nov 2026): the build rounds wait (bounded) for the grader's start-up filing of
stranded challengers, so no build takes the owners that filing needs first."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace

from carbon.challenge_validator import direct_intake


def _run(monkeypatch, ready, bound=5.0):
    monkeypatch.setattr(direct_intake, "STARTUP_PRELUDE_WAIT_SECONDS", bound)

    @contextmanager
    def fake_round(work, kind, since=None):
        yield

    monkeypatch.setattr(direct_intake, "_round", fake_round)
    stop, first = threading.Event(), []

    def advance():
        first.append(time.monotonic())
        stop.set()
        return 0

    began = time.monotonic()
    thread = threading.Thread(
        target=direct_intake._advance_loop,
        args=(SimpleNamespace(advance=advance), stop, object()),
        kwargs={"ready": ready},
        daemon=True,
    )
    thread.start()
    thread.join(10)
    return first[0] - began


def test_the_first_build_waits_for_the_start_up_filing(monkeypatch):
    filed_at = time.monotonic() + 1.2
    waited = _run(monkeypatch, lambda: time.monotonic() >= filed_at)
    assert 1.0 <= waited < 4.0


def test_the_wait_is_bounded(monkeypatch):
    waited = _run(monkeypatch, lambda: False, bound=1.0)
    assert 0.9 <= waited < 3.0

"""Live 116, 19 Nov 2026 (py-spy 17:02Z: 37 of 54 request threads waited at `QueueView.snapshot`'s lock while ONE refresh
globbed and stat'ed 1,322 markers under it, so submits found no free request thread): the public queue documents are
rebuilt by one caller at a time OUTSIDE the lock, every other reader gets the last built copy at once, and only the very
first build is waited for. Same documents, up to one rebuild older. Fixture doubles only (the rebuild is a sleep).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from carbon.challenge_validator import queue_public as qp
from carbon.challenge_validator import queue_view

SLOW_S = 1.0


class _Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


def _view(tmp_path, clock):
    view = queue_view.QueueView(None, None, tmp_path, clock=clock)
    calls = {"read": 0, "rows": 0, "inside": 0, "most": 0}
    guard = threading.Lock()

    def slow(kind, value):
        with guard:
            calls[kind] += 1
            calls["inside"] += 1
            calls["most"] = max(calls["most"], calls["inside"])
        time.sleep(calls["delay"])
        with guard:
            calls["inside"] -= 1
        return value()

    calls["delay"] = 0.0
    view._read = lambda: slow("read", lambda: {"as_of_unix": clock(), "grading_now": calls["read"]})
    view._read_rows = lambda boundary: slow("rows", lambda: ([], []))
    return view, calls


def test_fifty_reads_and_a_submit_on_eight_request_threads_while_a_slow_rebuild_runs(tmp_path):
    clock = _Clock()
    view, calls = _view(tmp_path, clock)
    first = view.snapshot()  # the first build (waited for once)
    clock.now += queue_view.CACHE_S + 1  # stale: the next read rebuilds
    calls["delay"] = SLOW_S
    submitted = {}

    def submit():
        submitted["at"] = time.monotonic()  # a submit needs only a free request thread

    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=8) as pool:
        reads = [pool.submit(view.snapshot) for _ in range(50)]
        done = pool.submit(submit)
        done.result(10)
        results = [r.result(10) for r in reads]
    assert submitted["at"] - began < SLOW_S / 2  # never waits out the rebuild
    assert calls["read"] == 2 and calls["most"] == 1  # one rebuild at a time, once
    # every reader got a whole document: the last copy, or the rebuilt one
    assert all(r["as_of_unix"] in (first["as_of_unix"], clock.now) for r in results)


def test_rows_rebuild_single_flight_and_serve_the_last_copy(tmp_path):
    clock = _Clock()
    view, calls = _view(tmp_path, clock)
    view.snapshot_v3()
    clock.now += qp.ROWS_QUANTUM_S + queue_view.CACHE_S + 1
    calls["delay"] = SLOW_S
    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=8) as pool:
        out = [pool.submit(view.snapshot_v3) for _ in range(20)]
        quick = [f.result(10) for f in out]
    assert calls["rows"] == 2 and calls["read"] == 2  # each rebuilt once, never per reader
    assert all(qp.ROWS in doc and qp.ROWS_V4 in doc for doc in quick)
    assert time.monotonic() - began < SLOW_S * 3  # the snapshot and the rows rebuilt once each, not per reader


def test_before_the_first_build_readers_wait_for_it_and_a_failed_build_raises_to_its_caller_only(tmp_path):
    clock = _Clock()
    view = queue_view.QueueView(None, None, tmp_path, clock=clock)
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("markers unreadable")
        return {"as_of_unix": clock()}

    view._read = flaky
    with pytest.raises(OSError):
        view.snapshot()
    assert view.snapshot()["as_of_unix"] == clock.now  # the next caller builds it
    # a later failed rebuild leaves the last copy for everyone else
    clock.now += queue_view.CACHE_S + 1
    kept = dict(view._cached)

    def broken():
        raise OSError("markers unreadable")

    view._read = broken
    with pytest.raises(OSError):
        view.snapshot()
    assert view._cached == kept


def test_a_copy_older_than_the_bound_is_never_served_and_a_failed_rebuild_is_logged(tmp_path, capsys):
    """V2 terms: staleness <= STALE_MAX_S (stated, <= 60 s); a failed rebuild logs, keeps the last copy, and the next
    reader retries."""
    assert queue_view.STALE_MAX_S <= 60
    clock = _Clock()
    view, calls = _view(tmp_path, clock)
    view.snapshot()
    clock.now += queue_view.STALE_MAX_S + 5  # the last copy is past the bound
    calls["delay"] = 0.3
    with ThreadPoolExecutor(max_workers=4) as pool:
        out = [pool.submit(view.snapshot) for _ in range(8)]
        docs = [f.result(10) for f in out]
    assert all(clock.now - d["as_of_unix"] <= queue_view.STALE_MAX_S for d in docs)
    assert calls["read"] == 2

    def broken():
        raise OSError("markers unreadable")

    view._read = broken
    clock.now += queue_view.CACHE_S + 1
    with pytest.raises(OSError):
        view.snapshot()
    assert '"event": "queue_view_rebuild_failed"' in capsys.readouterr().err


def test_the_cached_document_is_the_live_read(tmp_path):
    """Same answers as the live read: on a fixed tree the served document is exactly what `_read` builds."""
    clock = _Clock()
    view = queue_view.QueueView(None, None, tmp_path, clock=clock)
    fixed = {"as_of_unix": clock(), "waiting_to_build": 3, "grading_now": 1, "waits_s": [12.0, 40.0]}
    view._read = lambda: dict(fixed)
    assert view.snapshot() == fixed

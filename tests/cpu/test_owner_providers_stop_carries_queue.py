"""A receiver stop leaves QUEUED tasks QUEUED (Bundle A, queue-carry; 14 Nov 2026).

`OwnerProviders.cancel` (the stop's `closing=` callback and the `finally` of `serve`) used to cancel EVERY task view: a task not yet
built ended CANCELLED, so every restart or door switch cancelled the miners' queued submissions and left each identical resubmission
waiting behind a CANCELLED first with no marker (13 Nov: 75 tasks). It now cancels only what holds work (RUNNING, CANCEL_REQUESTED,
and the rest as before) and leaves QUEUED ones durable for the next start, which restores a live owner's queue and builds it.
Synthetic ids and fixtures only.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carbon import research
from carbon.challenge_validator import direct_receiver as receiver

State = research.DirectTaskStateV3
OWNER = "5" + "A" * 47


def _view(task, state):
    return SimpleNamespace(task_id=task, state=state)


def _provider(views, calls, fail=()):
    def cancel(task_id, challenge):
        calls.append(task_id)
        if task_id in fail:
            raise RuntimeError("cancel failed")

    return SimpleNamespace(
        _lock=threading.RLock(),
        _views={v.task_id: v for v in views},
        cancel_observed_task=cancel,
    )


def _pool(tmp_path, providers):
    pool = receiver.OwnerProviders(
        tmp_path, SimpleNamespace(info=SimpleNamespace(challenge_key="key")), None, None
    )
    for i, provider in enumerate(providers):
        pool._providers[f"owner{i}"] = provider
    return pool


def test_a_stop_cancels_what_holds_work_and_leaves_queued_tasks_queued(tmp_path):
    calls = []
    views = [
        _view("queued-1", State.QUEUED),
        _view("running", State.RUNNING),
        _view("cancel-requested", State.CANCEL_REQUESTED),
        _view("queued-2", State.QUEUED),
        _view("done", State.SUCCEEDED),
    ]
    pool = _pool(tmp_path, [_provider(views, calls)])
    pool.cancel()
    assert sorted(calls) == [
        "cancel-requested",
        "done",
        "running",
    ]  # terminal ones answer TOO_LATE, as before
    assert "queued-1" not in calls and "queued-2" not in calls
    assert pool._closing is True  # admission is closed whatever the queue holds


def test_every_owner_is_handled_alike_and_a_failure_is_still_reported_after_all_were_tried(
    tmp_path,
):
    calls = []
    first = _provider(
        [_view("a-run", State.RUNNING), _view("a-queued", State.QUEUED)],
        calls,
        fail={"a-run"},
    )
    second = _provider(
        [_view("b-run", State.RUNNING), _view("b-queued", State.QUEUED)], calls
    )
    pool = _pool(tmp_path, [first, second])
    with pytest.raises(receiver.ReceiverUnavailable, match="cancellation_unresolved"):
        pool.cancel()
    assert sorted(calls) == [
        "a-run",
        "b-run",
    ]  # the failing one did not stop the other owner's cancel


def test_a_pool_with_only_queued_tasks_cancels_nothing_and_does_not_fail(tmp_path):
    calls = []
    pool = _pool(tmp_path, [_provider([_view("q", State.QUEUED)], calls)])
    pool.cancel()
    assert calls == []


def test_a_real_queued_task_survives_the_stop_and_is_queued_after_the_restart(
    tmp_path, monkeypatch
):
    """The whole path on the real durable provider: a started task is QUEUED; the pool's stop leaves it QUEUED; a new provider on
    the same store (the next start) sees it QUEUED, ready for the advance loop."""
    from test_direct_v3_durable_tasks import _fixture

    request, make_provider, discovery = _fixture(tmp_path, monkeypatch)
    provider = make_provider()
    started = provider.start_research_task(request).task
    assert started.state is State.QUEUED
    pool = receiver.OwnerProviders(tmp_path / "owners", discovery, None, None)
    pool._providers["miner"] = provider
    pool.cancel()
    assert provider._views[started.task_id.value].state is State.QUEUED
    provider.close()
    reopened = make_provider()
    try:
        assert reopened._views[started.task_id.value].state is State.QUEUED
        assert started.task_id in reopened.queued_tasks()
    finally:
        reopened.close()


def test_the_stop_still_cancels_a_real_running_task_view(tmp_path, monkeypatch):
    """A task that is not QUEUED is still cancelled through the real provider (the state machine's own cancel)."""
    from test_direct_v3_durable_tasks import _fixture

    request, make_provider, discovery = _fixture(tmp_path, monkeypatch)
    provider = make_provider()
    started = provider.start_research_task(request).task
    # cancel it once the way an earlier stop would have: CANCELLED stays CANCELLED, TOO_LATE on a second request
    provider.cancel_observed_task(started.task_id, discovery.info.challenge_key)
    assert provider._views[started.task_id.value].state is State.CANCELLED
    pool = receiver.OwnerProviders(tmp_path / "owners", discovery, None, None)
    pool._providers["miner"] = provider
    pool.cancel()  # a terminal view is still handed to cancel_observed_task (TOO_LATE), never an error
    assert provider._views[started.task_id.value].state is State.CANCELLED
    provider.close()

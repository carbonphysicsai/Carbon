"""Submit latency (live 116, 21 Nov 2026: submit_timing named ``start_task`` at 326 ms to 29,352 ms): the owner's
storage walk makes one ``stat`` per file with the SAME answer as the rglob walk it replaces, the provider lock journals
a long outermost hold with the holding function's name, and a start's sub-steps are named in the submit's timings.
"""

from __future__ import annotations

import os
import threading

import pytest
import test_direct_v3_durable_tasks as durable

from carbon.challenge_validator import step_timing
from carbon.development_session import research_tasks
from carbon.development_session.research_ledger import _campaign_bytes


def _rglob_bytes(root):
    """The walk `CampaignLedger.check_storage` made before (the reference answer)."""
    paths = list(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("campaign symlink rejected")
    return sum(path.stat().st_size for path in paths if path.is_file())


def _tree(root):
    (root / "a" / "b" / "c").mkdir(parents=True)
    (root / "empty").mkdir()
    (root / "top.bin").write_bytes(b"x" * 11)
    (root / ".hidden").write_bytes(b"y" * 7)
    (root / "a" / "one").write_bytes(b"z" * 1024)
    (root / "a" / "b" / ".dot").write_bytes(b"")
    (root / "a" / "b" / "c" / "deep").write_bytes(b"w" * 4097)
    return root


def test_the_walk_answers_exactly_what_the_rglob_walk_answered(tmp_path):
    root = _tree(tmp_path / "ledger")
    assert _campaign_bytes(root) == _rglob_bytes(root) == 11 + 7 + 1024 + 4097
    assert (
        _campaign_bytes(tmp_path / "absent") == _rglob_bytes(tmp_path / "absent") == 0
    )


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks here")
@pytest.mark.parametrize("kind", ["file", "dir", "dangling"])
def test_any_symlink_in_the_tree_still_refuses(tmp_path, kind):
    root = _tree(tmp_path / "ledger")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big").write_bytes(b"q" * 99)
    target = {
        "file": outside / "big",
        "dir": outside,
        "dangling": outside / "missing",
    }[kind]
    os.symlink(target, root / "a" / "b" / "link")
    for walk in (_rglob_bytes, _campaign_bytes):
        with pytest.raises(ValueError, match="campaign symlink rejected"):
            walk(root)


def _lines(monkeypatch):
    import carbon.battery.intake

    lines = []
    monkeypatch.setattr(
        carbon.battery.intake,
        "log",
        lambda event, **fields: lines.append((event, fields)),
    )
    return lines


def test_the_held_lock_is_reentrant_and_exclusive(monkeypatch):
    _lines(monkeypatch)
    lock = research_tasks._HeldLock()
    other = []
    with lock, lock:  # reentrant in its own thread
        thread = threading.Thread(
            target=lambda: other.append(lock.acquire(timeout=0.05))
        )
        thread.start()
        thread.join()
    assert other == [False]  # another thread waits while it is held
    assert lock.acquire(timeout=1)
    lock.release()


def test_a_long_outermost_hold_is_journalled_once_with_its_site_only(monkeypatch):
    lines = _lines(monkeypatch)
    monkeypatch.setattr(research_tasks, "HOLD_LOG_SECONDS", 0.0)
    lock = research_tasks._HeldLock()

    def a_result_read():
        with lock, lock:
            pass

    a_result_read()
    assert [event for event, _ in lines] == ["provider_lock_held"]
    ((_, fields),) = lines
    assert set(fields) == {"site", "held_ms"}
    assert fields["site"] == "a_result_read"
    assert type(fields["held_ms"]) is int

    lines.clear()

    def a_submit_start():
        with step_timing.collecting() as steps, step_timing.held(lock, "st_lock_wait"):
            pass
        return steps

    steps = a_submit_start()
    assert set(steps) == {"st_lock_wait"}
    # taken through `step_timing.held`: the site is the caller, not contextlib or step_timing
    assert [fields["site"] for _, fields in lines] == ["a_submit_start"]


def test_a_short_hold_writes_nothing(monkeypatch):
    lines = _lines(monkeypatch)
    lock = research_tasks._HeldLock()
    with lock:
        pass
    assert lines == []


def test_held_releases_a_plain_lock_on_an_exception():
    lock = threading.Lock()
    with pytest.raises(RuntimeError), step_timing.held(lock, "wait"):
        assert lock.locked()
        raise RuntimeError("body")
    assert not lock.locked()


def test_a_start_names_its_sub_steps_in_the_submit_timings(tmp_path, monkeypatch):
    request, provider, _ = durable._fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        assert isinstance(tasks._lock, research_tasks._HeldLock)
        with step_timing.collecting() as steps:
            started = tasks.start_research_task(request)
        assert started.created
        assert {"st_lock_wait", "st_bindings", "st_images", "st_save"} <= set(steps)
        assert all(type(ms) is int and ms >= 0 for ms in steps.values())
        # outside a submit the same start records nothing and behaves as before
        again = tasks.start_research_task(request)
        assert (again.created, again.task) == (False, started.task)
    finally:
        tasks.close()

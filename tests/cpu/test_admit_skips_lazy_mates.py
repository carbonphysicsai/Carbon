"""Live 116, 19 Nov 2026: no construction-submit completed for an hour. The admission check's group read
(`LeanRecipeAdapter._pending_group_blocks`) runs under the intake's one admission lock and opened every group-mate's
provider (lazily RESTORING each) and waited on each mate's own lock. Now a LAZY mate's task (terminal by definition) is
never opened, an OPEN mate's task is read from its view without its lock, and the blocks are the same.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.registry.model import ChallengeKey
from carbon.research import DirectTaskStateV3

CONTRACT = "sha256:" + "a" * 64
KEY = ChallengeKey("electric-motor-magnetics", "1.8")
BLOCK = 360 * 100 + 200  # the new submission's receipt block
GROUP = "g:farm"


def _hotkey(i):
    return f"5Mate{i:05d}"


def _task(i):
    return "rtsk_" + f"{i:064x}"


class _Ledger:
    def __init__(self, rows):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.executescript(
            "CREATE TABLE attempts (seq INTEGER PRIMARY KEY, kind TEXT, contract_digest TEXT, hotkey TEXT,"
            " submission_id TEXT, receipt TEXT);"
            "CREATE TABLE exam_graded (submission_id TEXT, kind TEXT);"
            "CREATE TABLE exam_requeues (submission_id TEXT);"
        )
        for hotkey, task, block in rows:
            self.conn.execute(
                "INSERT INTO attempts (kind, contract_digest, hotkey, submission_id, receipt) VALUES (?,?,?,?,?)",
                ("OUTCOME", CONTRACT, hotkey, task, json.dumps({"block": block})),
            )

    @contextlib.contextmanager
    def _db(self):
        yield self.conn


class _Provider:
    """An OPEN mate: its views, and a lock its build may hold (the admission must not wait on it)."""

    def __init__(self, views):
        self._views = views
        self._lock = threading.RLock()

    def get_research_result(self, request):
        with self._lock:
            return SimpleNamespace(task=self._views[request.task_id.value])


def _door(rows, *, lazy=(), opened=None, closed=None):
    """``lazy``: task ids lazy owners hold; ``opened``: {hotkey: _Provider}; ``closed``: {hotkey: _Provider} reached only
    through `_provider` (neither open nor lazy). `_provider` records every owner it is asked for."""
    asked = []
    opened = dict(opened or {})
    closed = dict(closed or {})

    def provider(owner):
        asked.append(owner)
        if owner in closed:
            return closed[owner]
        raise AssertionError(f"opened {owner}")

    door = SimpleNamespace(
        ledger=_Ledger(rows),
        contract_digest=CONTRACT,
        discovery=SimpleNamespace(info=SimpleNamespace(challenge_key=KEY)),
        provider_for=SimpleNamespace(lazy_tasks=lambda: frozenset(lazy), _providers=opened),
        _provider=provider,
    )
    return door, asked


@pytest.fixture(autouse=True)
def one_group():
    exam_cap.install_grouping(lambda hotkey: GROUP)
    yield
    exam_cap.install_grouping(None)


def _view(state):
    return SimpleNamespace(state=state, challenge_key=KEY)


def _blocks(door):
    return LeanRecipeAdapter._pending_group_blocks(door, _hotkey(0), _task(0), BLOCK)


def test_a_lazy_group_mate_is_never_opened_during_admit():
    rows = [(_hotkey(0), _task(0), BLOCK), (_hotkey(1), _task(1), BLOCK - 10)]
    door, asked = _door(rows, lazy={_task(1)})
    assert _blocks(door) == ()
    assert asked == []


def test_admit_stays_bounded_with_400_lazy_owners_in_the_group_window():
    rows = [(_hotkey(0), _task(0), BLOCK)] + [
        (_hotkey(i), _task(i), BLOCK - i) for i in range(1, 401)
    ]
    door, asked = _door(rows, lazy={_task(i) for i in range(1, 401)})
    began = time.monotonic()
    assert _blocks(door) == ()
    assert asked == []
    assert time.monotonic() - began < 5.0


def test_an_open_mate_is_read_without_waiting_on_its_lock():
    busy = _Provider({_task(1): _view(DirectTaskStateV3.RUNNING)})
    rows = [(_hotkey(0), _task(0), BLOCK), (_hotkey(1), _task(1), BLOCK - 10)]
    door, asked = _door(rows, opened={_hotkey(1): busy})
    held, release = threading.Event(), threading.Event()

    def build():
        with busy._lock:
            held.set()
            release.wait(10)

    worker = threading.Thread(target=build)
    worker.start()
    held.wait(5)
    try:
        began = time.monotonic()
        assert _blocks(door) == (BLOCK - 10,)
        assert time.monotonic() - began < 2.0
    finally:
        release.set()
        worker.join()
    assert asked == []


def test_the_blocks_are_unchanged_when_a_lazy_mate_has_nothing_queued():
    """The same rows read the old way (every mate through `_provider`) and the new way give the same blocks."""
    states = {
        1: DirectTaskStateV3.FAILED_INFRA,  # lazy: terminal
        2: DirectTaskStateV3.CANCELLED,  # lazy: terminal
        3: DirectTaskStateV3.RUNNING,  # open: counted
        4: DirectTaskStateV3.SUCCEEDED,  # open: built, not counted
        5: DirectTaskStateV3.QUEUED,  # neither: read as before, counted
    }
    rows = [(_hotkey(0), _task(0), BLOCK)] + [
        (_hotkey(i), _task(i), BLOCK - 10 * i) for i in states
    ]
    every = {_hotkey(i): _Provider({_task(i): _view(s)}) for i, s in states.items()}
    old, _ = _door(rows, closed=every)
    new, asked = _door(
        rows,
        lazy={_task(1), _task(2)},
        opened={_hotkey(3): every[_hotkey(3)], _hotkey(4): every[_hotkey(4)]},
        closed={_hotkey(5): every[_hotkey(5)]},
    )
    assert _blocks(new) == _blocks(old) == (BLOCK - 30, BLOCK - 50)
    assert asked == [_hotkey(5)]


def test_an_open_mate_view_that_lacks_the_task_falls_through_to_the_old_read():
    """V2 (3f5d4c0e): this block is the probing bound, so a task the open view does not hold is read as before."""
    rows = [(_hotkey(0), _task(0), BLOCK), (_hotkey(1), _task(1), BLOCK - 10)]
    door, asked = _door(
        rows,
        opened={_hotkey(1): _Provider({})},
        closed={_hotkey(1): _Provider({_task(1): _view(DirectTaskStateV3.QUEUED)})},
    )
    assert _blocks(door) == (BLOCK - 10,)
    assert asked == [_hotkey(1)]


def test_a_lazy_mate_that_submits_is_opened_and_leaves_the_lazy_tasks():
    """The real receiver: its first touch (a submit's `_provider` -> `OwnerProviders._open`) restores it, after which
    its tasks are no longer lazy, so the group read sees its new task through its open view."""
    import hashlib

    from carbon.challenge_validator.direct_receiver import OwnerProviders

    mate = _hotkey(1)
    name = hashlib.sha256(mate.encode()).hexdigest()
    receiver = object.__new__(OwnerProviders)
    receiver._lock = threading.RLock()
    receiver._lazy = {name: mate}
    receiver._lazy_index = {name: {_task(1): ("FAILED_INFRA", 0)}}
    receiver._lazy_gates = {}
    receiver._set_aside = {}
    receiver._closing = False
    receiver._providers = {}
    opened = _Provider({_task(2): _view(DirectTaskStateV3.QUEUED)})
    receiver._build = lambda hotkey, restoring, host: (opened, None, None, None)

    def register(hotkey, provider, control, frozen_admission, live, *, restoring):
        receiver._providers[hotkey] = provider

    receiver._register = register
    assert _task(1) in receiver.lazy_tasks()
    receiver._restore_lazy(mate)
    assert receiver._providers == {mate: opened}
    assert receiver.lazy_tasks() == frozenset()
    rows = [(_hotkey(0), _task(0), BLOCK), (mate, _task(2), BLOCK - 10)]
    door, asked = _door(rows)
    door.provider_for = receiver
    assert _blocks(door) == (BLOCK - 10,)
    assert asked == []

"""LOCK + CACHE AUDIT #2 (door-code, 19 Nov 2026; owner: "prepare for the worst and be as efficient as possible"): no
door-wide admission lock. `DirectRecipeIntake._write` held EVERY submit's whole evaluation (ledger write transactions, a
group read over every hotkey the door ever saw, `start_research_task` with its image checks and disk writes), so one slow
submit held every miner's. Now an admission holds its owner's lock, then the locks of the scopes its cross-owner rules
read (its allowance group, its coldkey), sorted; the group's hotkeys come from the latest snapshot's members (once per
snapshot and funder map), never from every hotkey in the ledger; the coldkey guard locks one coldkey. Fixture doubles.
"""

from __future__ import annotations

import contextlib
import threading
import time
from types import SimpleNamespace

from test_admit_skips_lazy_mates import (
    BLOCK,
    GROUP,
    _door,
    _hotkey,
    _Provider,
    _task,
    _view,
)

from carbon.challenge_validator import coldkey_waiting as cw
from carbon.challenge_validator import exam_cap
from carbon.challenge_validator.direct_intake import DirectRecipeIntake
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter, _group_mates
from carbon.research import DirectTaskStateV3


class _Snapshot:
    def __init__(self, coldkeys):
        self.participants = tuple(
            SimpleNamespace(hotkey=h, coldkey=c) for h, c in coldkeys.items()
        )
        self.finalized_block = 7

    def resolve(self, hotkey):
        return next((p for p in self.participants if p.hotkey == hotkey), None)


class _Grouping:
    """`allowance_groups.Grouping`'s shape: a window, a funder map, and ``hotkey -> group`` (an unresolved hotkey is its
    own ``h:`` group)."""

    def __init__(self, snapshot, groups):
        self.window = SimpleNamespace(latest=lambda: snapshot)
        self._map = object()
        self.funder_map = lambda: self._map
        self._snapshot, self._groups = snapshot, groups
        self.calls = 0

    def __call__(self, hotkey):
        self.calls += 1
        if self._snapshot.resolve(hotkey) is None:
            return "h:" + hotkey
        return self._groups.get(hotkey, "h:" + hotkey)


def _intake(evaluate, snapshot=None):
    intake = object.__new__(DirectRecipeIntake)
    intake.door = SimpleNamespace(evaluate=evaluate)
    intake._note_recipe_digest = lambda result: None
    if snapshot is not None:
        intake.window = SimpleNamespace(latest=lambda: snapshot)
    return intake


def test_an_unrelated_owners_submit_never_waits_for_a_slow_one():
    """A submit whose evaluation is stuck (a slow image check, a ledger wait) holds only its owner and its scopes."""
    snapshot = _Snapshot({"5Slow": "ck-slow", "5Fast": "ck-fast"})
    stuck, release = threading.Event(), threading.Event()

    def evaluate(submitted):
        if submitted.hotkey == "5Slow":
            stuck.set()
            release.wait(10)
        return {"kind": "OUTCOME", "hotkey": submitted.hotkey}

    intake = _intake(evaluate, snapshot)
    slow = threading.Thread(
        target=intake._admit, args=(SimpleNamespace(hotkey="5Slow"),)
    )
    slow.start()
    assert stuck.wait(5)
    began = time.monotonic()
    assert intake._admit(SimpleNamespace(hotkey="5Fast"))["hotkey"] == "5Fast"
    assert time.monotonic() - began < 1.0
    release.set()
    slow.join(5)


def test_hotkeys_of_one_coldkey_or_one_group_are_decided_one_at_a_time():
    for coldkeys, grouping in (
        ({"5A": "ck", "5B": "ck"}, None),  # one coldkey, no grouping installed
        # two coldkeys, one funder group
        ({"5A": "ck-a", "5B": "ck-b"}, lambda hotkey: "farm"),
    ):
        snapshot = _Snapshot(coldkeys)
        state = {"inside": 0, "max": 0}
        guard = threading.Lock()

        def evaluate(submitted, state=state, guard=guard):
            with guard:
                state["inside"] += 1
                state["max"] = max(state["max"], state["inside"])
            time.sleep(0.02)
            with guard:
                state["inside"] -= 1
            return {"kind": "OUTCOME"}

        exam_cap.install_grouping(grouping)
        try:
            intake = _intake(evaluate, snapshot)
            threads = [
                threading.Thread(
                    target=intake._admit, args=(SimpleNamespace(hotkey=h),)
                )
                for h in ["5A", "5B"] * 6
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(20)
        finally:
            exam_cap.install_grouping(None)
        assert state["max"] == 1, (coldkeys, state)


def test_the_admission_keys_are_the_group_and_the_coldkey_sorted():
    snapshot = _Snapshot({"5A": "ck-a"})
    intake = _intake(lambda submitted: None, snapshot)
    exam_cap.install_grouping(lambda hotkey: "farm")
    try:
        assert intake._admission_keys("5A") == ["c:ck-a", "g:farm"]
        # no coldkey: the group only
        assert intake._admission_keys("5Unknown") == ["g:farm"]
    finally:
        exam_cap.install_grouping(None)

    def refuse(hotkey):
        raise exam_cap.ExamCapRefused("allowance_group_unresolved")

    exam_cap.install_grouping(refuse)
    try:
        # a refusing grouping adds no key
        assert intake._admission_keys("5A") == ["c:ck-a"]
    finally:
        exam_cap.install_grouping(None)
    # no window, no grouping
    assert _intake(lambda s: None)._admission_keys("5A") == ["g:h:5A"]


def test_the_coldkey_guard_locks_one_coldkey_not_the_door():
    snapshot = _Snapshot({"5A": "ck-a", "5B": "ck-b"})
    guard = cw.Guard(opened=dict, pending=list, snapshot=lambda: snapshot)
    assert guard.key_of("5A") == "c:ck-a"
    assert guard.key_of("5A", "hotkey") == "h:5A"
    assert guard.key_of("5Unknown") == "h:5Unknown"
    assert guard.lock_for("c:ck-a") is guard.lock_for("c:ck-a")
    with guard.lock_for("c:ck-a"):
        assert guard.lock_for("c:ck-b").acquire(blocking=False)
        guard.lock_for("c:ck-b").release()


class _RecordingLedger:
    """The fixture ledger, recording every statement the group read runs."""

    def __init__(self, ledger):
        self._ledger, self.sql = ledger, []

    @contextlib.contextmanager
    def _db(self):
        with self._ledger._db() as conn:
            yield self._Conn(conn, self.sql)

    class _Conn:
        def __init__(self, conn, sql):
            self._conn, self._sql = conn, sql

        def execute(self, statement, args=()):
            self._sql.append(statement)
            return self._conn.execute(statement, args)


def test_the_group_read_uses_the_snapshot_members_and_gives_the_same_blocks():
    """Same blocks as the old read over every hotkey in the ledger; no DISTINCT scan; `group_of` once per member per
    snapshot (not per submit)."""
    mates = [_hotkey(i) for i in range(4)]
    outsider, gone = _hotkey(8), _hotkey(9)
    rows = [(h, _task(i + 1), BLOCK - 360 * (i + 1)) for i, h in enumerate(mates)]
    rows += [(outsider, _task(20), BLOCK - 360), (gone, _task(21), BLOCK - 360)]
    snapshot = _Snapshot({**{h: "ck-" + h for h in mates}, outsider: "ck-out"})
    groups = {**{h: GROUP for h in mates}, outsider: "g:other"}
    opened = {
        h: _Provider({_task(i + 1): _view(DirectTaskStateV3.QUEUED)})
        for i, h in enumerate(mates)
    }
    opened[outsider] = _Provider({_task(20): _view(DirectTaskStateV3.QUEUED)})

    def blocks(grouping):
        door, asked = _door(rows, opened=opened)
        door.ledger = _RecordingLedger(door.ledger)
        exam_cap.install_grouping(grouping)
        try:
            found = LeanRecipeAdapter._pending_group_blocks(
                door, mates[0], _task(0), BLOCK
            )
        finally:
            exam_cap.install_grouping(None)
        return found, door

    def old_grouping(h):
        return groups.get(h, "h:" + h) if snapshot.resolve(h) else "h:" + h

    old, old_door = blocks(old_grouping)
    grouping = _Grouping(snapshot, groups)
    new, new_door = blocks(grouping)
    # the submitter's own earlier queued task and its 3 mates', never the outsider's or the deregistered hotkey's
    assert sorted(new) == sorted(old) and len(new) == 4
    assert any("SELECT DISTINCT" in s for s in old_door.ledger.sql)
    assert not any("SELECT DISTINCT" in s for s in new_door.ledger.sql)
    # the member map is built once per (snapshot, funder map)
    door = SimpleNamespace()
    exam_cap.install_grouping(grouping)
    try:
        before = grouping.calls
        assert _group_mates(door, mates[0], GROUP) == sorted(mates)
        built = grouping.calls - before
        assert _group_mates(door, mates[1], GROUP) == sorted(mates)
        assert grouping.calls - before == built
        assert _group_mates(door, gone, "h:" + gone) == [gone]
    finally:
        exam_cap.install_grouping(None)
    # no grouping: the old read
    assert _group_mates(SimpleNamespace(), mates[0], GROUP) is None


def test_lazy_tasks_are_gathered_for_the_group_only():
    from carbon.challenge_validator.direct_receiver import OwnerProviders

    owners = object.__new__(OwnerProviders)
    owners._lock = threading.RLock()
    owners._lazy = {"d1": "5A", "d2": "5B", "d3": "5C"}
    owners._lazy_index = {"d1": {"t1": 1}, "d2": {"t2": 1, "t3": 1}, "d3": {"t4": 1}}
    assert owners.lazy_tasks_of({"5A", "5B"}) == frozenset({"t1", "t2", "t3"})
    assert owners.lazy_tasks_of(set()) == frozenset()
    assert owners.lazy_tasks() == frozenset({"t1", "t2", "t3", "t4"})


"""Live 116, 19 Nov 2026 07:47Z: settling stop-cancelled queue places opened every marked task's owner (a lazy owner's
full restore) in the incumbent's steps after each start, and no grade was claimed meanwhile. An owner with nothing
waiting, and a task that already gave its place, are skipped before any owner is opened. Fixture ids only.
"""

from __future__ import annotations

import pytest
from test_queue_place import (
    CONTRACT,
    HOTKEYS,
    A,
    B,
    C,
    N,
    _door,
    _mark,
    _queue,
)

from carbon.challenge_validator.ledger import AttemptLedger


@pytest.fixture
def ledger(tmp_path):
    clock = iter(range(1000, 100_000, 10))
    return AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))


def _opened(door):
    opened = []

    def provider(owner):
        opened.append(owner)
        raise LookupError("not opened in this test")

    door._provider = provider
    return opened


def test_an_owner_with_nothing_waiting_is_never_opened(tmp_path, ledger):
    _queue(ledger)  # A (stop-cancelled), B and C, all one owner
    _mark(tmp_path, A)
    _mark(tmp_path, B, state="GRADED", code=None)
    _mark(tmp_path, C, state="GRADED", code=None)
    door = _door(ledger)
    opened = _opened(door)
    assert door.settle_stop_cancelled_places() == 0
    assert opened == []


def test_a_task_that_already_gave_its_place_is_never_looked_at(tmp_path, ledger):
    _queue(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    assert (
        ledger.grant_queue_place(CONTRACT, from_task=A, new_task=N, hotkey=HOTKEYS[0])
        == "granted"
    )
    _mark(tmp_path, A)
    door = _door(ledger)
    opened = _opened(door)
    assert door.settle_stop_cancelled_places() == 0
    assert opened == []
    assert ledger.queue_place_from_tasks(CONTRACT) == {A}


def test_an_owner_with_a_waiting_task_is_still_looked_at(tmp_path, ledger):
    _queue(ledger)  # B and C carry no marker: they wait
    _mark(tmp_path, A)
    door = _door(ledger)
    opened = _opened(door)
    assert door.settle_stop_cancelled_places() == 1  # asked again next call, as before
    assert opened == [HOTKEYS[0]]


def test_300_cancelled_owners_and_one_waiting_open_one(tmp_path, ledger):
    """Lead (19 Nov 2026): ~300 lazy owners after a start, one real place to settle: only that owner is opened."""
    from test_queue_place import _outcome

    owners = ["5Owner" + f"{i:03d}" + "x" * 38 for i in range(300)]
    for i, owner in enumerate(owners):
        cancelled = "rtsk_" + f"{i:064x}"
        _outcome(ledger, cancelled, hotkey=owner)
        _mark(tmp_path, cancelled)
    waiting = "rtsk_" + "f" * 64  # the one owner's resubmission, not yet settled
    _outcome(ledger, waiting, hotkey=owners[7])
    door = _door(ledger)
    opened = _opened(door)
    door.settle_stop_cancelled_places()
    assert opened == [owners[7]]

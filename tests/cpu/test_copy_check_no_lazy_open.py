"""Live 116, 19 Nov 2026 (77 lazy owners opened one by one after each start, at the claim's copy check): an earlier
same-contract task with no exam row that is settled (a marker) or ended unbuilt is never a first, so the copy check
never computes its digest or opens its owner. Same decisions; a still-building earlier task is looked at as before.
"""

from __future__ import annotations

import pytest
from test_recipe_graded_once import CHALLENGE, EXAM, HOTKEYS, Door, T, _recipe

from carbon.challenge_validator import recipe_copies


@pytest.fixture
def door(tmp_path):
    return Door(tmp_path)


def _counting(door):
    asked = []
    owners = door.owners

    def owner(sid):
        asked.append(sid)
        return owners.get(sid)

    door.adapter.owner = owner
    return asked


def _decide(door, sid):
    return recipe_copies.decide(
        adapter=door.adapter,
        ledger=door.ledger,
        marker=door.grader.marker,
        submission_id=sid,
        challenge_id=CHALLENGE.challenge_id,
        challenge_version=CHALLENGE.version,
        exam_key=EXAM,
    )


def test_an_earlier_task_that_ended_unbuilt_is_never_opened(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.adapter._ended_unbuilt = lambda: {T[0]}
    asked = _counting(door)
    assert _decide(door, T[1]) == (recipe_copies.GRADE, None)
    assert T[0] not in asked


def test_an_earlier_settled_task_without_an_exam_row_is_never_opened(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.grader._write(T[0], "FAILED", code="worker_failure")
    asked = _counting(door)
    assert _decide(door, T[1]) == (recipe_copies.GRADE, None)
    assert T[0] not in asked


def test_an_earlier_task_still_building_is_looked_at_as_before(door):
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    door.adapter._ended_unbuilt = lambda: set()
    asked = _counting(door)
    assert _decide(door, T[1]) == (recipe_copies.WAIT, T[0])
    assert T[0] in asked


def _stored_and_unreadable(door):
    """Both tasks' digests stored (as `note_admitted` stores them at admission), and an owner that cannot be opened
    now: `outcome` raises, as for a lazy or set-aside owner."""
    door.submit(T[0], HOTKEYS[0], _recipe())
    door.submit(T[1], HOTKEYS[1], _recipe())
    for sid in (T[0], T[1]):
        recipe_copies.recipe_digest(door.adapter, sid, door.ledger)

    def outcome(sid):
        raise LookupError("owner_unavailable")

    door.adapter.outcome = outcome


def test_a_stored_digest_task_the_door_indexes_as_ended_is_never_a_first(door):
    _stored_and_unreadable(door)
    door.adapter._ended_unbuilt = lambda: {T[0]}
    assert _decide(door, T[1]) == (recipe_copies.GRADE, None)


def test_a_task_that_gave_its_queue_place_is_never_a_first(door):
    """live 116, 20 Nov 2026: rtsk_7f5e880a waited 24 h behind its stop-cancelled same-recipe ancestors."""
    _stored_and_unreadable(door)
    door.adapter._ended_unbuilt = lambda: set()
    with door.ledger._db() as db:
        db.execute(
            "INSERT INTO queue_place_grants VALUES(?,?,?,?,?,?)",
            (door.adapter.contract_digest, T[1], T[0], HOTKEYS[1], 1, 0),
        )
    assert _decide(door, T[1]) == (recipe_copies.GRADE, None)


def test_an_unreadable_unended_earlier_task_still_waits_as_before(door):
    _stored_and_unreadable(door)
    door.adapter._ended_unbuilt = lambda: set()
    assert _decide(door, T[1]) == (recipe_copies.WAIT, T[0])

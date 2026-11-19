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

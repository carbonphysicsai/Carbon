"""The queue rows count a GRANTED task's wait from the original arrival (owner, 14 Nov: a short in_queue above rows that waited all day).

A resubmission of a stop-cancelled task is a NEW task that takes the original task's queue PLACE (`AttemptLedger.grant_queue_place`):
its rank is the original's, so its wait must run from the original arrival too, never from the new task's creation. No new field: the
v3 document, the Worker and the page are unchanged; the 300 s floor still applies. Fixture ids only.
"""

from __future__ import annotations

from test_queue_place import (  # noqa: F401
    HOTKEYS,
    A,
    B,
    C,
    N,
    _grant,
    _outcome,
    _queue,
    ledger,
)
from test_queue_public import CHALLENGE, NOW, TASKS, _door
from test_recipe_graded_once import CONTRACT

from carbon.challenge_validator import queue_public
from carbon.research import DirectTaskStateV3

Q = queue_public.ROWS_QUANTUM_S
START = (int(NOW) // Q) * Q + 10.0
BOUNDARY = START // Q * Q


# --- the ledger read -------------------------------------------------------------------------------------------------------


def test_a_granted_task_is_listed_with_its_originals_arrival(ledger):  # noqa: F811
    _queue(ledger)  # A, B, C accepted in that order
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    assert _grant(ledger) == "granted"
    origins = ledger.queue_place_origins(CONTRACT)
    assert origins == {N: ledger.first_outcome_ns(CONTRACT, A)}
    assert origins[N] < ledger.first_outcome_ns(CONTRACT, B)
    # a task that holds no place is not listed, and another contract's grants are not read
    assert B not in origins and C not in origins
    assert ledger.queue_place_origins("sha256:" + "9" * 64) == {}


def test_the_read_ignores_the_new_tasks_own_late_outcome(ledger):  # noqa: F811
    _queue(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    _grant(ledger)
    before = ledger.queue_place_origins(CONTRACT)
    _outcome(ledger, N)  # its own (later) accepted submission
    assert ledger.queue_place_origins(CONTRACT) == before


def test_no_grants_no_origins(ledger):  # noqa: F811
    _queue(ledger)
    assert ledger.queue_place_origins(CONTRACT) == {}


# --- the rows ----------------------------------------------------------------------------------------------------------


def _states(now):
    return {
        TASKS[0]: (DirectTaskStateV3.QUEUED, now - 100),  # no grant
        TASKS[1]: (
            DirectTaskStateV3.QUEUED,
            now - 100,
        ),  # a grant: its original arrived long ago
        TASKS[2]: (
            DirectTaskStateV3.QUEUED,
            now - 3 * Q,
        ),  # a grant whose "original" is LATER than its own creation
    }


def _view(tmp_path, origins):
    view, _grader = _door(tmp_path, _states(START), pending=TASKS[:3], clock=START)
    view.intake.adapter.ledger.queue_place_origins = lambda contract: {
        task: int(at * 1e9) for task, at in origins.items()
    }
    return view


def _ages(view):
    return [row["in_queue_s"] for row in view.snapshot_v3()["rows"]["rows"]]


def test_a_granted_row_counts_from_the_original_arrival_never_later(tmp_path):
    plain = _ages(_view(tmp_path, {}))
    long_ago = START - 20_000  # the original arrived ~5.5 h ago
    later = (
        START - 10
    )  # an "original" newer than the task: ignored (never moves the clock later)
    ages = _ages(_view(tmp_path, {TASKS[1]: long_ago, TASKS[2]: later}))
    assert ages[0] == plain[0]  # no grant: unchanged
    assert ages[1] == queue_public.floor_to_quantum(BOUNDARY - long_ago)
    assert ages[1] > plain[1] + 10_000
    assert (
        ages[2] == plain[2]
    )  # the grant could only move the clock earlier: the task's own creation stands


def test_the_quantum_floor_still_applies_and_no_field_is_added(tmp_path):
    view = _view(tmp_path, {TASKS[1]: START - 20_000})
    for age in _ages(view):
        assert age % Q == 0
    status, body = queue_public.serve_v3(view, CHALLENGE)
    assert status == 200
    assert set(body) == queue_public.FIELDS_V3
    assert all(set(row) == queue_public.ROW_FIELDS for row in body["rows"])


def test_positions_and_states_are_unchanged_by_the_clock(tmp_path):
    base = _view(tmp_path, {}).snapshot_v3()["rows"]["rows"]
    granted = _view(tmp_path, {TASKS[1]: START - 20_000}).snapshot_v3()["rows"]["rows"]
    assert [(r["position"], r["state"], r["hotkey"]) for r in base] == [
        (r["position"], r["state"], r["hotkey"]) for r in granted
    ]


def test_a_ledger_that_cannot_be_read_is_unavailable_never_a_guess(tmp_path):
    view, _grader = _door(tmp_path, _states(START), pending=TASKS[:3], clock=START)

    def broken(_contract):
        raise OSError("ledger")

    view.intake.adapter.ledger.queue_place_origins = broken
    assert queue_public.serve_v3(view, CHALLENGE)[0] == 503
    assert queue_public.serve(view, CHALLENGE)[0] == 200  # the counts never read it


def test_a_ledger_without_the_read_changes_nothing(tmp_path):
    view, _grader = _door(tmp_path, _states(START), pending=TASKS[:3], clock=START)
    assert not hasattr(view.intake.adapter.ledger, "queue_place_origins")
    assert len(_ages(view)) == 3

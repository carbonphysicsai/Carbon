"""A resubmission of a stop-cancelled task's recipe takes that task's original queue place (owner ruling, 14 Nov 2026).

The 75 tasks a receiver stop cancelled carry the terminal marker `cancelled_by_carbon_stop`. When the miner resubmits the
identical recipe, the door starts the next generation (a new task id); this gives that new task the cancelled task's ORIGINAL
arrival place in `AttemptLedger.submitted_outcomes`, once per cancelled task, only for the same hotkey, only for marked tasks,
and only for a resubmission that arrives after the change (a queue already formed is not re-ordered). Fixture ids only.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_recipe_graded_once import CONTRACT, HOTKEYS

from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.ledger import AttemptLedger

IDS = {name: "rtsk_" + char * 64 for name, char in zip("ABCNMX", "abcdef", strict=True)}
A, B, C, N, M, X = (IDS[k] for k in "ABCNMX")


def _outcome(ledger, sid, hotkey=HOTKEYS[0]):
    ledger.record(
        SimpleNamespace(
            hotkey=hotkey,
            receipt={"sequence": 1, "digest": "d", "block": 1},
            contract_digest=CONTRACT,
        ),
        kind="OUTCOME",
        submission_id=sid,
    )


@pytest.fixture
def ledger(tmp_path):
    clock = iter(range(1000, 10_000, 10))
    return AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))


def _queue(ledger):
    for sid in (A, B, C):  # A is the one a stop cancelled; B and C queued behind it
        _outcome(ledger, sid)


def _grant(ledger, **changes):
    values = {"from_task": A, "new_task": N, "hotkey": HOTKEYS[0], **changes}
    return ledger.grant_queue_place(CONTRACT, **values)


# --- ordering -----------------------------------------------------------------------------------------------------------


def test_a_resubmission_without_a_grant_waits_at_the_back(ledger):
    _queue(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    _outcome(ledger, N)
    assert ledger.submitted_outcomes(CONTRACT) == (A, B, C, N)


def test_the_granted_resubmission_takes_the_original_place_before_and_after_its_own_outcome_row(
    ledger,
):
    _queue(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")  # intent only
    assert _grant(ledger) == "granted"
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(B) < order.index(C)
    _outcome(ledger, N)  # its own (late) accepted submission must not move it back
    after = ledger.submitted_outcomes(CONTRACT)
    assert after.index(N) < after.index(B) < after.index(C)
    assert set(after) == {A, B, C, N}


def test_a_place_in_the_middle_is_the_original_middle(ledger):
    _outcome(ledger, B)
    _outcome(ledger, A)  # A arrived second
    _outcome(ledger, C)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    _outcome(ledger, N)
    assert ledger.submitted_outcomes(CONTRACT) == (B, A, C, N)
    assert _grant(ledger) == "granted"
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(B) < order.index(N) < order.index(C)


# --- once, the same hotkey, unmarked ------------------------------------------------------------------------------------------


def test_a_cancelled_task_gives_its_place_once_only(ledger):
    _queue(ledger)
    for sid in (N, M):
        ledger.record_recipe_task_intent(CONTRACT, sid, HOTKEYS[0], "r")
    assert _grant(ledger) == "granted"
    assert _grant(ledger) == "already_granted"  # the same pair again is a no-op
    assert _grant(ledger, new_task=M) == "from_task_used"  # a second task never gets it
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(B) and order.index(M) > order.index(C)


def test_a_wrong_hotkey_is_refused_and_nothing_moves(ledger):
    _queue(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[1], "r")
    before = ledger.submitted_outcomes(CONTRACT)
    assert _grant(ledger, hotkey=HOTKEYS[1]) == "hotkey_mismatch"
    assert ledger.submitted_outcomes(CONTRACT) == before
    assert _grant(ledger) == "granted"  # the refusal used nothing


def test_a_task_with_no_accepted_submission_gives_no_place(ledger):
    _queue(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    assert _grant(ledger, from_task=X) == "no_original"
    assert _grant(ledger, from_task=N) == "same_task"
    assert _grant(ledger, hotkey="") == "incomplete"


def test_the_grant_is_another_tables_fact_not_an_attempt_row(ledger):
    _queue(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    with ledger._db() as db:
        before = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    assert _grant(ledger) == "granted"
    with ledger._db() as db:
        assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == before


# --- the door's hook: only marked tasks, never a failure ----------------------------------------------------------------


def _door(ledger):
    door = object.__new__(LeanRecipeAdapter)
    door.ledger, door.contract_digest = ledger, CONTRACT
    return door


def _mark(tmp_path, task, *, state="FAILED", code="cancelled_by_carbon_stop"):
    directory = tmp_path / "auto-grade" / "markers"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (task + ".json")).write_text(
        json.dumps({"state": state, "code": code})
    )


def _behind_c(ledger, task=N):
    order = ledger.submitted_outcomes(CONTRACT)
    return order.index(task) > order.index(C)


def test_only_a_task_marked_cancelled_by_carbon_stop_gives_its_place(tmp_path, ledger):
    _queue(ledger)
    door = _door(ledger)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[0], "r")
    door._give_back_queue_place([A], N, HOTKEYS[0])  # no marker at all: unaffected
    assert _behind_c(ledger)
    for state, code in (
        ("FAILED", "worker_wall_limit_reached"),
        ("GRADED", "cancelled_by_carbon_stop"),
    ):
        _mark(tmp_path, A, state=state, code=code)
        door._give_back_queue_place([A], N, HOTKEYS[0])
        assert _behind_c(ledger)  # a miner's own cancel, any other marker: unaffected
    _mark(tmp_path, A)
    door._give_back_queue_place([A], N, HOTKEYS[0])
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(N) < order.index(B)


def test_the_door_hook_refuses_the_wrong_hotkey_and_gives_the_place_once(
    tmp_path, ledger
):
    _queue(ledger)
    door = _door(ledger)
    _mark(tmp_path, A)
    ledger.record_recipe_task_intent(CONTRACT, N, HOTKEYS[1], "r")
    door._give_back_queue_place(
        [A], N, HOTKEYS[1]
    )  # another hotkey submitted the same recipe
    assert _behind_c(ledger)
    ledger.record_recipe_task_intent(CONTRACT, M, HOTKEYS[0], "r")
    door._give_back_queue_place([A], M, HOTKEYS[0])
    door._give_back_queue_place([A], N, HOTKEYS[0])  # the place is already M's
    order = ledger.submitted_outcomes(CONTRACT)
    assert order.index(M) < order.index(B) and _behind_c(ledger, N)


def test_a_failing_grant_never_fails_the_submission(tmp_path, ledger, monkeypatch):
    _queue(ledger)
    door = _door(ledger)
    _mark(tmp_path, A)

    def boom(*args, **kwargs):
        raise RuntimeError("ledger busy")

    monkeypatch.setattr(ledger, "grant_queue_place", boom)
    door._give_back_queue_place(
        [A], N, HOTKEYS[0]
    )  # returns: the task stays at the back
    door._give_back_queue_place([], N, HOTKEYS[0])
    door.ledger = SimpleNamespace()  # a ledger without the method is a no-op
    door._give_back_queue_place([A], N, HOTKEYS[0])


def test_a_bad_task_id_never_reaches_a_path(ledger):
    door = _door(ledger)
    assert door._stop_cancelled("../../etc/passwd") is False
    assert door._stop_cancelled("rtsk_short") is False


# --- the grader asks the adapter until every cancelled task has been looked at, within a bound -------------------------------


def _grader(settle):
    from carbon.challenge_validator.auto_grade import AutoGrader

    grader = object.__new__(AutoGrader)
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(settle_stop_cancelled_places=settle)
    )
    return grader


def test_the_grader_asks_until_nothing_is_left_spaced_in_time_and_never_fails_a_tick(
    monkeypatch,
):
    from carbon.challenge_validator import auto_grade

    clock = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: clock[0])
    answers = iter([1, RuntimeError("boom"), 0])
    asked = []

    def settle():
        asked.append(clock[0])
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    grader = _grader(settle)
    grader._settle_queue_places()
    grader._settle_queue_places()  # inside the spacing: not asked again
    assert asked == [1000.0]
    for _ in range(4):
        clock[0] += grader.PLACES_RETRY_SECONDS
        grader._settle_queue_places()
    assert (
        len(asked) == 3
    )  # unresolved -> asked again; an error -> asked again; 0 -> never again
    # an adapter without the method (a fixture) settles at once
    plain = _grader(None)
    plain.intake = SimpleNamespace(adapter=SimpleNamespace())
    plain._settle_queue_places()
    assert plain._places_settled is True


def test_an_owner_who_never_becomes_available_costs_a_bounded_number_of_scans(
    monkeypatch,
):
    from carbon.challenge_validator import auto_grade

    clock = [0.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: clock[0])
    asked = []

    journal = []
    monkeypatch.setattr(
        "carbon.challenge_validator.koth_journal.note",
        lambda event, **fields: journal.append((event, fields)),
    )

    def settle():
        asked.append(1)
        return 1  # one marked task whose owner is never available

    grader = _grader(settle)
    grader.intake.adapter.queue_places_unresolved = (A,)
    for _ in range(500):  # a tick every minute for a long while
        grader._settle_queue_places()
        clock[0] += 60.0
    assert len(asked) == grader.PLACES_MAX_ASKS  # then it stops until the next start
    assert journal == [
        ("queue_place_gave_up", {"tasks": [A]})
    ]  # the leftover ids, once

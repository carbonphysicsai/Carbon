"""R39 (Validator-2B 7 Nov rulings (1)-(3)): a grade that fails on Carbon's infrastructure gets a verdict and, once, a
free automatic retry; a charged slot whose verdict was never delivered is released only when every condition holds.

Claims:
1. Only a transient Carbon code is retried: never a version-wide gap, a duplicate or an untyped value.
2. One retry per task for life, persisted (the schedule log and any ledger re-queue), spaced, idle-first, never while
   the door drains; applied through infra_requeue's own criteria (auto: no incident cause filter), reusing its row;
   a refused retry writes an alert line.
3. The real auto-grader writes the next step on every FAILED marker and re-grades the task itself, once.
4. A COUNTED slot is released only when the pool store was read and holds no evaluation (a missing or unreadable
   store refuses), no Ladder document, exactly one COUNTED row and a scored status; anything else keeps the slot
   and writes an alert.
SYNTHETIC tasks and rows (test_infra_requeue's door fixtures)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_retry
from tests.cpu.test_infra_requeue import (  # noqa: F401  (served is an autouse fixture)
    HOTKEY,
    A,
    B,
    C,
    _failed,
    _root,
    _row,
    _rows,
    served,
)

S = 1_000_000_000


def _log(root, name=auto_retry.LOG_NAME):
    path = root / "auto-grade" / "requeued" / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize(
    "code, expected",
    [
        ("evaluation_pack_binding_unavailable", False),
        ("pool_constants_not_registered", False),
        ("exam_cadence_unregistered", False),
        ("menu_draw_unavailable", False),
        ("menu_rowcheck_unavailable", False),
        ("PoolConstantsNotRegistered", False),
        ("DUPLICATE_OF_EARLIER", False),
        ("", False),
        (None, False),
        ("inference_pair_incomplete", True),
        ("WorkerFailure", True),
        ("graded_query_unavailable:unrecorded", True),
        ("single_call_evidence_unavailable", True),
    ],
)
def test_only_a_transient_carbon_code_is_retried(code, expected):
    assert auto_retry.retryable(code) is expected


def test_a_task_is_scheduled_once_for_life_and_spaced(tmp_path):
    root, ledger = _root(tmp_path)
    t0 = 10_000 * S
    assert auto_retry.schedule(
        root, A, "inference_pair_incomplete", ledger=ledger, clock=lambda: t0
    )
    assert not auto_retry.schedule(
        root, A, "inference_pair_incomplete", ledger=ledger, clock=lambda: t0
    )
    assert not auto_retry.schedule(
        root, B, "pool_constants_x", ledger=ledger, clock=lambda: t0
    )
    early = t0 + (auto_retry.RETRY_SECONDS - 1) * S
    assert auto_retry.due(root, clock=lambda: early) == []
    ready = t0 + auto_retry.RETRY_SECONDS * S
    assert auto_retry.due(root, clock=lambda: ready) == [A]
    # a busy door waits for an idle tick until the retry is overdue
    assert auto_retry.due(root, clock=lambda: ready, idle=False) == []
    overdue = t0 + (auto_retry.RETRY_SECONDS + auto_retry.OVERDUE_SECONDS) * S
    assert auto_retry.due(root, clock=lambda: overdue, idle=False) == [A]
    # a task the operator already re-queued (a ledger requeue row) never gets an automatic one
    from carbon.challenge_validator.exam_cap import ExamCap

    ExamCap(ledger).mark_requeued(C)
    assert not auto_retry.schedule(root, C, "inference_pair_incomplete", ledger=ledger)


def test_applying_reuses_infra_requeues_criteria_without_the_incident_cause(tmp_path):
    root, ledger = _root(tmp_path)
    _failed(
        root, ledger, A, cause="inference_pair_incomplete"
    )  # not a 4 Nov incident cause
    _failed(root, ledger, B, cause="inference_pair_incomplete")
    _row(
        ledger, B, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE"
    )  # a graded task is NEVER re-queued
    t0 = 1_000 * S
    for task in (A, B):
        assert auto_retry.schedule(
            root, task, "inference_pair_incomplete", ledger=ledger, clock=lambda: t0
        )
    later = t0 + auto_retry.RETRY_SECONDS * S
    assert (
        auto_retry.apply_due(root, draining=True, clock=lambda: later) == []
    )  # never in a drain
    out = dict(auto_retry.apply_due(root, clock=lambda: later))
    assert out == {A: None, B: "exam_row_counted_or_reserved"}
    # B's marker still says retry_scheduled (write-once): only the refused one reaches the operator's alert log
    assert [
        (r["task"], r["event"], r["reason"]) for r in _log(root, auto_retry.ALERT_NAME)
    ] == [(B, "auto_retry_refused", "exam_row_counted_or_reserved")]
    assert not (
        root / "auto-grade" / "markers" / (A + ".json")
    ).exists()  # handed back to the grader
    requeued = (root / "auto-grade" / "requeued" / "requeues.jsonl").read_text()
    assert json.loads(requeued.splitlines()[-1])["auto"] is True
    # recorded applied/refused exactly once: nothing is due again
    assert auto_retry.apply_due(root, clock=lambda: later + 10**12) == []
    assert auto_retry.used(root, A, ledger) and auto_retry.used(root, B, ledger)


def _intake(ledger, retain):
    class Intake:
        adapter = SimpleNamespace(
            contract_digest="sha256:c",
            challenge_id="f02",
            challenge_version="2.5",
            discovery=SimpleNamespace(evaluation_pack_digest="sha256:" + "e" * 64),
            ledger=ledger,
            owner=lambda submission_id: HOTKEY,
        )

        def draining(self):
            return False

        def retain_result(self, submission_id, **kwargs):
            return retain(submission_id)

    ledger.submitted_outcomes = lambda contract: (A,)
    return Intake()


def test_the_real_grader_writes_the_next_step_and_regrades_once(tmp_path, monkeypatch):
    from carbon.challenge_validator import auto_grade
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    root, ledger = _root(tmp_path)
    _failed(
        root, ledger, A, cause="x"
    )  # its arrival, owner store and recipe (the marker is replaced below)
    (root / "auto-grade" / "markers" / (A + ".json")).unlink()
    attempts = []

    def retain(task):
        attempts.append(task)
        if len(attempts) in (1, 3):
            raise RetentionUnavailable("inference_pair_incomplete")
        return {"entry_id": "sha256:" + "1" * 64}

    monkeypatch.setattr(auto_retry, "RETRY_SECONDS", 0)
    grader = auto_grade.AutoGrader(_intake(ledger, retain), root)
    assert grader.run_once() == (A, "FAILED")
    marker = grader.marker(A)
    assert marker["next_step"] == "retry_scheduled"
    assert _rows(ledger, A) == [("RELEASED", "FAILED_INFRA")]
    # the next (idle) tick hands it back and grades it again, on its own row: no new slot
    assert grader.run_once() == (A, "GRADED")
    assert attempts == [A, A]
    assert "next_step" not in grader.marker(A)
    assert len(_rows(ledger, A)) == 1


def test_a_second_infra_failure_gets_no_second_retry(tmp_path, monkeypatch):
    from carbon.challenge_validator import auto_grade
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause="x")
    (root / "auto-grade" / "markers" / (A + ".json")).unlink()

    def retain(task):
        raise RetentionUnavailable("inference_pair_incomplete")

    monkeypatch.setattr(auto_retry, "RETRY_SECONDS", 0)
    grader = auto_grade.AutoGrader(_intake(ledger, retain), root)
    assert grader.run_once() == (A, "FAILED")
    assert grader.run_once() == (A, "FAILED")  # the one retry, failed again
    assert grader.marker(A)["next_step"] == "slot_returned"
    assert grader.run_once() is None  # never a third grade


def test_a_version_wide_gap_is_given_back_for_a_resubmit_after_the_fix(tmp_path):
    from carbon.challenge_validator import auto_grade
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    root, ledger = _root(tmp_path)

    def retain(task):
        raise RetentionUnavailable("menu_draw_unavailable")

    grader = auto_grade.AutoGrader(_intake(ledger, retain), root)
    assert grader.run_once() == (A, "FAILED")
    assert grader.marker(A)["next_step"] == "resubmit_after_fix"
    assert _log(root) == []


class _Pool:
    def __init__(self, bodies=()):
        self.bodies = list(bodies)

    def private_evaluation_bodies(self):
        return self.bodies


@pytest.mark.parametrize(
    "status, pool, ladder, extra_counted, refusal",
    [
        ("SCORED_DEVELOPMENT_CANDIDATE", (), False, False, None),
        ("MANDATORY_GATE_FAILED", (), False, False, "candidate_status"),
        ("DUPLICATE_OF_EARLIER", (), False, False, "duplicate_status"),
        (
            "SCORED_DEVELOPMENT_CANDIDATE",
            ({"submission_id": A},),
            False,
            False,
            "pool_store_has_a_graded_evaluation",
        ),
        ("SCORED_DEVELOPMENT_CANDIDATE", (), True, False, "ladder_shows_this_round"),
        (
            "SCORED_DEVELOPMENT_CANDIDATE",
            (),
            False,
            True,
            "not_exactly_one_counted_row",
        ),
    ],
)
def test_a_counted_slot_is_released_only_when_every_condition_holds(
    tmp_path, status, pool, ladder, extra_counted, refusal
):
    root, ledger = _root(tmp_path)
    _row(ledger, A, "COUNTED", status)
    if extra_counted:
        with ledger._db() as db:  # the same submission COUNTED on a second exam key
            db.execute(
                "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, epoch, "
                "submission_id, state, status, reserved_ns) VALUES(?,'f02','2.5',?,'GRADED',21,?,'COUNTED',?,1)",
                (HOTKEY, "sha256:" + "f" * 64, A, status),
            )
    if ladder:
        with ledger._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS ladder_feedback(hotkey, challenge_id, exam_key, best, latest, updated_ns)"
            )
            db.execute(
                "INSERT INTO ladder_feedback VALUES(?,?,?,?,?,?)",
                (
                    HOTKEY,
                    "f02",
                    "sha256:" + "e" * 64,
                    json.dumps({"epoch": 20}),
                    None,
                    5,
                ),
            )
    assert (
        auto_retry.undelivered_refusal(
            A, "WorkerFailure", ledger=ledger, pool_store=_Pool(pool)
        )
        == refusal
    )
    released = auto_retry.release_undelivered(
        root, A, "WorkerFailure", ledger=ledger, pool_store=_Pool(pool)
    )
    assert released is (refusal is None)
    if refusal is None:
        assert ("RELEASED", "FAILED_INFRA") in _rows(ledger, A)
    else:
        assert all(state == "COUNTED" for state, _s in _rows(ledger, A))
        assert _log(root, auto_retry.ALERT_NAME)[-1]["reason"] == refusal


class _Broken:
    def private_evaluation_bodies(self):
        raise OSError("locked")


@pytest.mark.parametrize("store", [None, _Broken()], ids=["missing", "unreadable"])
def test_an_unreadable_pool_store_never_proves_nothing_was_graded(tmp_path, store):
    root, ledger = _root(tmp_path)
    _row(ledger, A, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
    assert (
        auto_retry.undelivered_refusal(
            A, "WorkerFailure", ledger=ledger, pool_store=store
        )
        == "pool_store_unreadable"
    )
    assert not auto_retry.release_undelivered(
        root, A, "WorkerFailure", ledger=ledger, pool_store=store
    )
    assert _rows(ledger, A) == [("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")]
    assert _log(root, auto_retry.ALERT_NAME)[-1]["reason"] == "pool_store_unreadable"


@pytest.mark.parametrize("configured", ["vanished", "corrupt", "not_configured"])
def test_the_real_grader_keeps_a_counted_slot_when_the_pool_store_cannot_be_opened(
    tmp_path, configured
):
    """Validator-2B 8 Nov: the grader opens the pool store itself (`_pool`) when the grade fails. A configured store
    gone by then (`PoolStoreUnavailable`: the refund check gets None), one that cannot be read, or none configured at
    all must keep the charged slot."""
    from carbon.battery.pool_store import PoolStore
    from carbon.challenge_validator import auto_grade
    from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

    root, ledger = _root(tmp_path)
    _failed(root, ledger, A, cause="x")
    (root / "auto-grade" / "markers" / (A + ".json")).unlink()
    with ledger._db() as db:
        db.execute("DELETE FROM exam_graded WHERE submission_id=?", (A,))

    store = None if configured == "not_configured" else tmp_path / "pool.sqlite3"
    if store is not None:
        PoolStore(store)  # readable when the tick starts

    def retain(task):  # the grade settled COUNTED, then the verdict was never delivered
        _row(ledger, task, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")
        if configured == "vanished":
            store.unlink()
        elif configured == "corrupt":
            store.write_bytes(b"not a database")
        raise RetentionUnavailable("inference_pair_incomplete")

    grader = auto_grade.AutoGrader(_intake(ledger, retain), root, pool_store=store)
    assert grader.run_once() == (A, "FAILED")
    marker = grader.marker(A)
    assert marker["code"] == "inference_pair_incomplete:counted"
    assert "next_step" not in marker  # no next step: the operator decides
    assert _rows(ledger, A) == [("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")]
    assert _log(root, auto_retry.ALERT_NAME)[-1]["reason"] == "pool_store_unreadable"


def test_each_next_step_has_its_one_sentence():
    assert set(auto_retry.NEXT_STEPS) == {
        "retry_scheduled",
        "slot_returned",
        "resubmit_after_fix",
    }
    assert all(type(s) is str and s for s in auto_retry.NEXT_STEPS.values())

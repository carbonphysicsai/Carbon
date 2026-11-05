"""The receiver keeps its own king comparable on its current exam (owner via Lead, 5 Nov: one upgrade, no operator step).

Claims. (1) A stepwise crown re-measure runs ONE new rebuild per call, keeps each in the pool store, and the call that
finds them all done files the mean on the given key: N + 1 calls (the host-fault second build), every seed built once; a
failed build keeps nothing and is tried again on the next call. (2) `king_upkeep.step` regrades the king when a challenger
on the current pack waits for it, through the receiver's own regrade, once per epoch on failure, with an operator alert
after repeated failures and a typed failure when the regrade lands on another key; on an averaging door it re-measures
the king one rebuild per tick, then stops; nothing is due when the king can already be met and measured. (3) The tick
runs the start-up filing once, then the upkeep, then the sweep, then grades. (4) Every crown comparison writes one
journal line. Synthetic grades and stand-ins; no model runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_crown_remeasure import (
    CROWN_KEY,
    KEY,
    KING,
    N,
    _active,
    _comparator,
    _Repeat,
    _Rule,
    _store,
)

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import crown_pause_sweep as sweeper
from carbon.challenge_validator import king_upkeep, koth_journal
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import digest

EXAM = digest("current pack")


def _tick(store, base):
    """One upkeep call: a fresh repeat over the same builds (as each tick builds its own), wrapped stepwise."""
    repeat = SimpleNamespace(
        rebuild_at=base.rebuild_at, rebuild_again_at=base.rebuild_again_at
    )
    retention._one_rebuild_per_call(repeat, store, KING, KEY)
    try:
        return _active().measure_incumbent(store, KING, KEY, _comparator(), repeat)
    except retention.RebuildStep:
        return None


def test_a_stepwise_remeasure_runs_one_rebuild_per_call_and_files_the_mean_on_its_key(
    tmp_path,
):
    store, base = _store(tmp_path), _Repeat()
    again = []
    first_again = base.rebuild_again_at
    base.rebuild_again_at = lambda seed: again.append(seed) or first_again(seed)
    outcomes = [_tick(store, base) for _ in range(N + 1)]
    assert (
        outcomes[:N] == [None] * N
    )  # each of these ran exactly one new rebuild and stopped
    assert outcomes[N] == {
        "outcome": ca.KING_MEASURED,
        "reason": ca.FIRST_BEATS_BASELINE,
    }
    assert base.calls == ca.derive_seeds(
        CROWN_KEY, "electric-motor-magnetics", KING, N, _Rule.seed_range
    )
    assert len(again) == 1  # the host-fault second build, once
    assert store.crown_mean(KING, KEY) == pytest.approx(0.70)
    assert store.crown_mean(KING, digest("another key")) is None


def test_a_failed_rebuild_keeps_nothing_and_is_tried_again_next_call(tmp_path):
    store, base = _store(tmp_path), _Repeat(fail={0})
    assert (
        _tick(store, base) is None
        and store.crown_rebuild_cached(KING, KEY, base.calls[0], False) is None
    )
    assert _tick(store, base) is None  # the same seed again, now built and kept
    assert base.calls[0] == base.calls[1]
    assert store.crown_rebuild_cached(KING, KEY, base.calls[1], False) is not None


# --- the upkeep step -------------------------------------------------------------------------------------------------


class _Pool:
    """The pool reads `king_upkeep` uses: a king whose evaluation on the current exam exists or not, waiting records."""

    def __init__(self, store, *, waiting=1, king_key=None, mean=None):
        self.store, self.clock = store, store.clock
        self.waiting, self.king_key, self.mean = waiting, king_key, mean
        self.king_upkeep_attempts = store.king_upkeep_attempts
        self.note_king_upkeep_attempt = store.note_king_upkeep_attempt
        self.db = store.db

    def incumbent(self):
        return {"model_id": KING}

    def paused_crowns(self, kind=None):
        return [
            {
                "submission_id": "rtsk_" + f"{n:064x}",
                "evaluation_key": KEY,
                "exam": EXAM,
            }
            for n in range(3)
        ]

    def awaits_incumbent_regrade(self, record):
        return self.waiting > 0

    def private_evaluation_bodies(self):
        if self.king_key is None:
            return []
        return [
            {
                "submission_id": KING,
                "evaluation_key": self.king_key,
                "evidence": {"evaluation_pack_digest": EXAM},
            }
        ]

    def crown_mean(self, sid, key=None):
        return self.mean

    def crown_average_unstable(self, sid, key=None):
        return False


class _Intake:
    def __init__(self, pool, *, lands=True, fails=False):
        self.adapter = SimpleNamespace(
            discovery=SimpleNamespace(evaluation_pack_digest=EXAM)
        )
        self.pool, self.lands, self.fails, self.calls = pool, lands, fails, []
        self.unbound = None

    def regrade_result(
        self, entry_id, *, artifact_directory, entry_directory, promotion
    ):
        self.calls.append((entry_id, promotion))
        if self.fails:
            raise retention.RetentionUnavailable("regrade_case_bank_unavailable")
        if self.unbound:
            # the grade returns its typed reason instead of raising (lean_recipe_retention's evaluation step)
            return {
                "status": "CREATED",
                "private_evaluation_state": "UNAVAILABLE",
                "private_evaluation_reason": self.unbound,
            }
        if self.lands:
            self.pool.waiting = 0
        return {
            "status": "CREATED",
            "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
        }


def _step(pool, intake, active=None):
    return king_upkeep.step(
        pool,
        intake,
        root=Path("."),
        artifacts=Path("a"),
        entries=Path("e"),
        active=active,
    )


@pytest.fixture
def entry(monkeypatch):
    monkeypatch.setattr(
        king_upkeep, "king_origin_entry", lambda pool, root, king: digest("king entry")
    )
    # a king built on this receiver's image: the plain regrade (route (b) is its own tests)
    monkeypatch.setattr(retention, "king_parent_moved", lambda *a, **k: False)


def test_a_waiting_challenger_makes_the_receiver_regrade_its_king(
    tmp_path, entry, capsys
):
    pool = _Pool(_store(tmp_path))
    intake = _Intake(pool)
    assert _step(pool, intake) == {"step": "regrade", "state": "DONE"}
    assert intake.calls == [
        (digest("king entry"), pool)
    ]  # the receiver's own regrade, recorded into this pool
    assert _step(pool, intake) is None  # nothing waits any more: nothing due
    events = [
        json.loads(line)["event"] for line in capsys.readouterr().err.splitlines()
    ]
    assert events == ["king_regrade_started", "king_regraded"]


def test_a_failing_regrade_is_retried_once_per_epoch_and_alerts(
    tmp_path, entry, capsys
):
    clock = [1_000.0]
    store = _store(tmp_path)
    store.clock = lambda: clock[0]
    pool = _Pool(store)
    intake = _Intake(pool, fails=True)
    assert _step(pool, intake)["code"] == "regrade_case_bank_unavailable"
    assert (
        _step(pool, intake) is None and len(intake.calls) == 1
    )  # inside the epoch: not tried again
    for _ in range(2):
        clock[0] += sweeper.RETRY_SECONDS
        _step(pool, intake)
    assert len(intake.calls) == 3
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    (alert,) = [line for line in lines if line["event"] == "operator_alert"]
    assert alert["code"] == "king_upkeep_regrade_failing" and alert["attempts"] == 3


def test_a_regrade_that_lands_on_another_key_is_a_typed_failure(tmp_path, entry):
    pool = _Pool(_store(tmp_path))
    assert _step(pool, _Intake(pool, lands=False))["code"] == "king_regrade_key_differs"


def test_an_unresolved_king_entry_is_a_typed_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(king_upkeep, "king_origin_entry", lambda pool, root, king: None)
    pool = _Pool(_store(tmp_path))
    intake = _Intake(pool)
    assert _step(pool, intake)["code"] == "king_entry_unresolved" and intake.calls == []


def test_on_an_averaging_door_the_king_is_remeasured_one_rebuild_per_tick(
    tmp_path, entry, monkeypatch
):
    store = _store(tmp_path)
    pool = _Pool(store, waiting=0, king_key=KEY)
    asked = []

    def remeasure(
        adapter,
        pool_,
        *,
        submission_id,
        evaluation_key,
        entry_id,
        artifact_directory,
        entry_directory,
        stepwise,
    ):
        asked.append((submission_id, evaluation_key, entry_id, stepwise))
        if len(asked) < 3:
            store.record_crown_rebuild(KING, KEY, len(asked), False, {"evidence": {}})
            return {
                "outcome": retention.REMEASURE_IN_PROGRESS,
                "reason": "one_rebuild_done",
            }
        pool.mean = 0.7
        return {"outcome": ca.KING_MEASURED, "reason": ca.FIRST_BEATS_BASELINE}

    monkeypatch.setattr(retention, "remeasure_incumbent_pack", remeasure)
    active = object()
    assert [_step(pool, _Intake(pool), active)["state"] for _ in range(3)] == [
        "IN_PROGRESS",
        "IN_PROGRESS",
        "DONE",
    ]
    assert asked[0] == (KING, KEY, digest("king entry"), True)
    assert (
        _step(pool, _Intake(pool), active) is None
    )  # measured on this key: nothing due
    assert (
        _step(_Pool(store, waiting=0, king_key=KEY), _Intake(pool), None) is None
    )  # averaging off: nothing


def test_no_remeasure_where_margin_n_is_not_registered(tmp_path, entry, monkeypatch):
    pool = _Pool(_store(tmp_path), waiting=0, king_key=KEY)
    monkeypatch.setattr(
        retention, "remeasure_incumbent_pack", lambda *a, **k: pytest.fail("ran")
    )
    intake = _Intake(pool)
    intake.adapter.challenge_id = "electric-motor-magnetics"
    active = SimpleNamespace(rule=SimpleNamespace(margin_for=lambda challenge: None))
    assert _step(pool, intake, active) is None


def test_a_remeasure_call_that_kept_no_rebuild_counts_as_a_failure(
    tmp_path, entry, monkeypatch
):
    store = _store(tmp_path)
    pool = _Pool(store, waiting=0, king_key=KEY)
    monkeypatch.setattr(
        retention,
        "remeasure_incumbent_pack",
        lambda *a, **k: {
            "outcome": retention.REMEASURE_IN_PROGRESS,
            "reason": "one_rebuild_done",
        },
    )
    assert _step(pool, _Intake(pool), object())["code"] == "crown_rebuild_not_measured"
    assert store.king_upkeep_attempts(KING, EXAM, "remeasure")[0] == 1


def test_the_upkeep_never_raises_into_the_grading_loop(tmp_path):
    class Broken(_Pool):
        def incumbent(self):
            raise OSError("disk")

    assert _step(Broken(_store(tmp_path)), _Intake(None))["state"] == "ERROR"


def test_the_tick_files_stranded_challengers_once_then_runs_upkeep_then_the_sweep_then_grades(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import auto_grade

    order = []
    monkeypatch.setattr(
        king_upkeep,
        "file_stranded",
        lambda *a: order.append("stranded") or (king_upkeep.STRANDED_DONE, 0),
    )
    monkeypatch.setattr(king_upkeep, "step", lambda *a, **k: order.append("upkeep"))
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.root, grader.pool_store = tmp_path, tmp_path / "pool.sqlite3"
    grader.artifacts = grader.entries = tmp_path
    grader.intake = SimpleNamespace(adapter=SimpleNamespace(discovery=None))
    monkeypatch.setattr(auto_grade.AutoGrader, "_pool", lambda self: object())
    monkeypatch.setattr(
        auto_grade.AutoGrader,
        "_resume_paused_crowns",
        lambda self: order.append("sweep"),
    )
    monkeypatch.setattr(
        auto_grade.AutoGrader, "pending", lambda self: order.append("grades") or []
    )
    grader.run_once()
    grader.run_once()
    assert order == [
        "stranded",
        "upkeep",
        "sweep",
        "grades",
        "upkeep",
        "sweep",
        "grades",
    ]


# --- journal lines ---------------------------------------------------------------------------------------------------


def test_every_crown_comparison_writes_one_journal_line(capsys):
    koth_journal.contention(
        "live",
        "rtsk_x",
        {"outcome": bp.INCUMBENT_KEEPS, "reason": "kept", "evaluation_key": KEY},
        "rtsk_k",
    )
    koth_journal.contention("live", "rtsk_y", {"error": "pool_owner_unknown"})
    koth_journal.contention("sweep", "rtsk_z", "not a dict")
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [
        (line["candidate"], line["incumbent"], line.get("outcome"), line.get("error"))
        for line in lines
    ] == [
        ("rtsk_x", "rtsk_k", bp.INCUMBENT_KEEPS, None),
        ("rtsk_y", None, None, "pool_owner_unknown"),
    ]
    assert all(line["event"] == "koth_contention" for line in lines)


def test_the_sweep_journals_each_decision(tmp_path, capsys):
    from carbon.battery.pool_store import PoolStore

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = PoolStore(state / "pool.sqlite3")
    store.record_crown_paused(
        "rtsk_" + "1" * 64,
        KEY,
        kind="pack",
        exam=EXAM,
        entry_id=digest("e"),
        pin=digest("p"),
    )
    sweeper.sweep(
        store,
        lambda r: {"outcome": bp.INCUMBENT_KEEPS, "reason": "kept"},
        kind="pack",
        current_exam=EXAM,
    )
    (line,) = [json.loads(x) for x in capsys.readouterr().err.splitlines()]
    assert (line["event"], line["path"], line["outcome"]) == (
        "koth_contention",
        "sweep",
        bp.INCUMBENT_KEEPS,
    )


def test_a_waiting_live_grade_runs_after_at_most_one_king_job(tmp_path, monkeypatch):
    """Validator 06:47 (C): with N rebuilds still to run and live tasks waiting, a king job never runs twice in a row."""
    from carbon.challenge_validator import auto_grade

    order, live = [], ["rtsk_" + "1" * 64, "rtsk_" + "2" * 64]
    monkeypatch.setattr(
        king_upkeep, "file_stranded", lambda *a: (king_upkeep.STRANDED_DONE, 0)
    )
    monkeypatch.setattr(king_upkeep, "step", lambda *a, **k: order.append("king job"))
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.root, grader.pool_store = tmp_path, tmp_path / "pool.sqlite3"
    grader.artifacts = grader.entries = tmp_path
    grader.intake = SimpleNamespace(adapter=SimpleNamespace(discovery=None))
    monkeypatch.setattr(auto_grade.AutoGrader, "_pool", lambda self: object())
    monkeypatch.setattr(
        auto_grade.AutoGrader, "_resume_paused_crowns", lambda self: None
    )
    monkeypatch.setattr(auto_grade.AutoGrader, "pending", lambda self: live[:1])

    def grade(self, submission_id, **kwargs):
        order.append("live " + submission_id[-1])
        live.pop(0)
        return {"entry_id": None}

    grader.intake.retain_result = lambda submission_id, **kwargs: grade(
        None, submission_id
    )
    monkeypatch.setattr(auto_grade.AutoGrader, "_write", lambda self, *a, **k: None)
    monkeypatch.setattr(
        auto_grade, "_Sampler", lambda *a: __import__("contextlib").nullcontext()
    )
    grader.containers, grader.sample_seconds = (lambda: 0), 1.0
    for _ in range(4):
        grader.run_once()
    assert order == ["king job", "live 1", "king job", "live 2", "king job", "king job"]


# --- the sweep runs at most one GPU decision per tick (Validator 5 Nov, the 7b5ed970 must-fix) ------------------------


def _queued(tmp_path, count=3):
    from carbon.battery.pool_store import PoolStore

    state = tmp_path / "state"
    state.mkdir(mode=0o700, exist_ok=True)
    store = PoolStore(state / "pool.sqlite3")
    ids = ["rtsk_" + f"{n:064x}" for n in range(1, count + 1)]
    for sid in ids:
        store.record_crown_paused(
            sid, KEY, kind="pack", exam=EXAM, entry_id=digest("e"), pin=digest("p")
        )
    return store, ids


def test_three_queued_crown_changers_and_a_live_task_the_live_task_runs_after_at_most_one(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import auto_grade

    store, _ids = _queued(tmp_path)
    order, live = [], ["rtsk_" + "f" * 64]

    def reconsider(
        adapter, pool, record, **kwargs
    ):  # each runs its repeat + averaging rebuilds
        order.append("crown " + record["submission_id"][-1])
        return {"outcome": bp.INCUMBENT_KEEPS, "reason": ca.MEAN_WITHIN, "spent": True}

    monkeypatch.setattr(retention, "reconsider_paused_pack", reconsider)
    monkeypatch.setattr(
        king_upkeep, "file_stranded", lambda *a: (king_upkeep.STRANDED_DONE, 0)
    )
    monkeypatch.setattr(king_upkeep, "step", lambda *a, **k: None)
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.root, grader.pool_store = tmp_path, store.path
    grader.artifacts = grader.entries = tmp_path
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(discovery=SimpleNamespace(evaluation_pack_digest=EXAM))
    )
    monkeypatch.setattr(auto_grade.AutoGrader, "_pool", lambda self: store)
    monkeypatch.setattr(auto_grade.AutoGrader, "pending", lambda self: live[:1])

    def graded(submission_id, **kwargs):
        order.append("live")
        live.clear()
        return {"entry_id": None}

    grader.intake.retain_result = graded
    monkeypatch.setattr(auto_grade.AutoGrader, "_write", lambda self, *a, **k: None)
    monkeypatch.setattr(
        auto_grade, "_Sampler", lambda *a: __import__("contextlib").nullcontext()
    )
    grader.containers, grader.sample_seconds = (lambda: 0), 1.0
    for _ in range(3):
        grader.run_once()
    assert order == ["crown 1", "live", "crown 2", "crown 3"]
    assert store.paused_crowns() == []  # all three decided, one per tick


def test_cheap_no_crown_comparisons_still_finish_in_one_tick(tmp_path):
    store, ids = _queued(tmp_path)
    done = sweeper.sweep(
        store,
        lambda r: {"outcome": bp.INCUMBENT_KEEPS, "reason": "kept"},
        kind="pack",
        current_exam=EXAM,
    )
    assert [sid for sid, _ in done] == ids


def test_the_spend_watch_passes_the_repeat_through_and_marks_gpu_work():
    calls = []
    repeat = SimpleNamespace(
        entry_id=digest("e"),
        rebuild_at=lambda seed, i=0: calls.append(("rebuild", seed, i)),
    )
    watched = retention.SpendWatch(repeat)
    assert watched.entry_id == digest("e") and not watched.spent
    assert watched.mark({"outcome": "X"}) == {"outcome": "X"}
    watched.rebuild_at(7, 1)
    assert calls == [("rebuild", 7, 1)] and watched.spent
    assert watched.mark({"outcome": "X"}) == {"outcome": "X", "spent": True}
    assert getattr(retention.SpendWatch(SimpleNamespace()), "rebuild_at", None) is None


# --- the start-up filing is never silent and is retried until it is made (Deploy 5 Nov 09:3x) ----------------------


def test_every_start_up_check_writes_one_line_whatever_it_found(
    tmp_path, capsys, monkeypatch
):
    from carbon.challenge_validator import recontend

    assert king_upkeep.file_stranded(
        tmp_path, tmp_path / "p", SimpleNamespace(evaluation_pack_digest=None)
    ) == (
        king_upkeep.STRANDED_RETRY,
        0,
    )
    monkeypatch.setattr(
        recontend,
        "file",
        lambda *a, **k: (_ for _ in ()).throw(
            recontend.RecontendRefused("no_incumbent")
        ),
    )
    assert king_upkeep.file_stranded(
        tmp_path, tmp_path / "p", SimpleNamespace(evaluation_pack_digest=EXAM)
    )[0] == (king_upkeep.STRANDED_DONE)
    monkeypatch.setattr(
        recontend,
        "file",
        lambda *a, **k: (_ for _ in ()).throw(
            recontend.RecontendRefused("pool_store_unavailable")
        ),
    )
    assert king_upkeep.file_stranded(
        tmp_path, tmp_path / "p", SimpleNamespace(evaluation_pack_digest=EXAM)
    )[0] == (king_upkeep.STRANDED_RETRY)
    monkeypatch.setattr(
        recontend,
        "file",
        lambda *a, **k: {"king": "rtsk_k", "filed": [], "skipped": {}},
    )
    assert king_upkeep.file_stranded(
        tmp_path, tmp_path / "p", SimpleNamespace(evaluation_pack_digest=EXAM)
    ) == (
        king_upkeep.STRANDED_DONE,
        0,
    )
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [(line["event"], line["state"], line.get("code")) for line in lines] == [
        ("recontend_checked", "RETRY", "no_exam"),
        ("recontend_checked", "DONE", "no_incumbent"),
        ("recontend_checked", "RETRY", "pool_store_unavailable"),
        ("recontend_checked", "DONE", None),
    ]
    assert (lines[-1]["filed"], lines[-1]["skipped"]) == (
        0,
        0,
    )  # an empty plan still says so


def test_a_check_that_could_not_be_made_is_retried_a_minute_later_not_left_until_a_restart(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import auto_grade

    now, calls = [100.0], []
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    results = [(king_upkeep.STRANDED_RETRY, 0), (king_upkeep.STRANDED_DONE, 129)]
    monkeypatch.setattr(
        king_upkeep,
        "file_stranded",
        lambda *a: calls.append(now[0]) or results[len(calls) - 1],
    )
    monkeypatch.setattr(king_upkeep, "step", lambda *a, **k: None)
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.root, grader.pool_store = tmp_path, tmp_path / "pool.sqlite3"
    grader.artifacts = grader.entries = tmp_path
    grader.intake = SimpleNamespace(adapter=SimpleNamespace(discovery=None))
    monkeypatch.setattr(auto_grade.AutoGrader, "_pool", lambda self: object())
    assert grader._stranded_due()
    grader._king_upkeep()  # could not be made: tried again later
    assert not grader._stranded_due()
    now[0] += 30
    grader._king_upkeep()
    assert calls == [100.0]  # inside the minute: not again (no host lock every poll)
    now[0] += king_upkeep.STRANDED_RETRY_SECONDS
    assert grader._stranded_due()
    grader._king_upkeep()
    assert len(calls) == 2 and not grader._stranded_due()
    now[0] += 10 * king_upkeep.STRANDED_RETRY_SECONDS
    grader._king_upkeep()
    assert len(calls) == 2  # made: never again this start


def test_a_regrade_that_returns_unbound_fails_with_its_own_reason_not_the_key_check(
    tmp_path, entry, capsys
):
    """Deploy 5 Nov 10:5x: the grade returned UNAVAILABLE (leg_minimum_platform_mismatch); only key_differs was logged."""
    pool = _Pool(_store(tmp_path))
    intake = _Intake(pool)
    intake.unbound = "leg_minimum_platform_mismatch"
    assert _step(pool, intake) == {
        "step": "regrade",
        "state": "FAILED",
        "code": "regrade_unbound:leg_minimum_platform_mismatch",
    }
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    (failed,) = [line for line in lines if line["event"] == "king_upkeep_failed"]
    assert failed["code"] == "regrade_unbound:leg_minimum_platform_mismatch"


def test_each_landed_king_step_reopens_the_waiting_decisions_and_a_failure_does_not(
    tmp_path, entry, monkeypatch
):
    """Lead 5 Nov: the king's regrade landing, his rebuild landing and his crown mean filing each make every waiting
    decision due at once (`crown_pause_sweep.king_changed` on this pool); a failed step changes nothing.
    """
    changed = []
    monkeypatch.setattr(sweeper, "king_changed", lambda pool: changed.append(pool))
    pool = _Pool(_store(tmp_path))
    assert _step(pool, _Intake(pool)) == {"step": "regrade", "state": "DONE"}
    assert changed == [pool]
    store = _store(tmp_path / "remeasure")
    pool = _Pool(store, waiting=0, king_key=KEY)

    def remeasure(adapter, pool_, **kwargs):
        pool.mean = 0.7
        return {"outcome": ca.KING_MEASURED, "reason": ca.FIRST_BEATS_BASELINE}

    monkeypatch.setattr(retention, "remeasure_incumbent_pack", remeasure)
    assert _step(pool, _Intake(pool), object())["state"] == "DONE"
    assert changed[-1] is pool and len(changed) == 2
    failing = _Pool(_store(tmp_path / "failing"))
    assert _step(failing, _Intake(failing, fails=True))["state"] == "FAILED"
    assert len(changed) == 2

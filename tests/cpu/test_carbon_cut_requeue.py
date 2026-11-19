"""CARBON-CUT REQUEUE (V2's ruling + the Lead's code row, 18 Nov 2026): our own failures re-run, miners never resubmit.

- A FAILED grade marker (Carbon's by construction) whose exam rows hold no slot is requeueable by the operator's
  `requeue` whatever its code, and the grader's hourly sweep schedules its automatic retry (D16 caps) when none was
  ever scheduled: a grade cut by our own stop or restart is marked at restore and was never scheduled.
- A FAILED marker whose exam row is still COUNTED is never retried by the sweep: it is named once on the owed list.
- A build the receiver's own stop cancelled is recorded at the stop and re-run at the next start (a miner's own
  cancel or withdrawal never is).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time

import pytest
from test_build_requeue import HOTKEYS, A, N, _door, _Provider, _queue

from carbon.challenge_validator import auto_retry, infra_requeue, lean_recipe
from carbon.challenge_validator import direct_receiver as receiver
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.research import DirectTaskStateV3, ResearchTaskId

T = {k: "rtsk_" + c * 64 for k, c in zip("RCKO", "1234", strict=True)}


def _state(tmp_path, rows):
    """A door state with one GRADED exam row per ``rows`` entry ``{task: state}``."""
    db = sqlite3.connect(tmp_path / "attempts.sqlite3")
    db.execute("CREATE TABLE exam_graded (submission_id TEXT, kind TEXT, state TEXT)")
    for task, state in rows.items():
        db.execute("INSERT INTO exam_graded VALUES (?, 'GRADED', ?)", (task, state))
    db.commit()
    db.close()
    markers = tmp_path / "auto-grade" / "markers"
    markers.mkdir(parents=True)
    return markers


def _marker(markers, task, state, code, age=0.0):
    path = markers / f"{task}.json"
    path.write_text(json.dumps({"state": state, "code": code}))
    if age:
        then = time.time() - age
        os.utime(path, (then, then))


def _scheduled(tmp_path):
    log = tmp_path / "auto-grade" / "requeued" / auto_retry.LOG_NAME
    if not log.exists():
        return []
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    return [line["task"] for line in lines if line["kind"] == "scheduled"]


def _alerts(tmp_path):
    log = tmp_path / "auto-grade" / "requeued" / auto_retry.ALERT_NAME
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


@pytest.fixture(autouse=True)
def _fresh_sweep(monkeypatch):
    monkeypatch.setattr(auto_retry, "_SWEPT", {})


@pytest.fixture(autouse=True)
def _plain_requests(monkeypatch):
    # the door double's requests are plain tuples, not wire records: their intent digest is over their repr
    import carbon.research

    monkeypatch.setattr(
        carbon.research, "canonical_bytes", lambda request: repr(request).encode()
    )


@pytest.fixture
def door_ledger(tmp_path):
    clock = iter(range(1000, 100_000, 10))
    return AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))


def test_a_carbon_cut_grade_gets_its_retry_scheduled_by_the_sweep(tmp_path):
    markers = _state(tmp_path, {T["R"]: "RELEASED", T["K"]: "COUNTED"})
    # cut by our stop
    _marker(markers, T["R"], "FAILED", "Unavailable:unrecorded")
    _marker(markers, T["C"], "CANDIDATE_FAILED", "candidate_program_failed")
    # a COUNTED row: never retried here
    _marker(markers, T["K"], "FAILED", "WorkerFailure")
    # too old
    _marker(markers, T["O"], "FAILED", "WorkerFailure", age=2 * 86400)
    assert auto_retry.sweep_carbon_cut(tmp_path) == [T["R"]]
    assert _scheduled(tmp_path) == [T["R"]]
    (alert,) = _alerts(tmp_path)
    assert (alert["task"], alert["event"]) == (T["K"], auto_retry.COUNTED_UNDER_FAILED)


def test_the_sweep_runs_at_most_hourly_and_names_a_counted_row_once(tmp_path):
    markers = _state(tmp_path, {T["K"]: "COUNTED"})
    _marker(markers, T["K"], "FAILED", "WorkerFailure")
    clock = iter([0.0, 10.0, 4000.0, 8000.0])

    def monotonic():
        return next(clock)

    auto_retry.sweep_carbon_cut(tmp_path, monotonic=monotonic)
    # within the hour: nothing
    auto_retry.sweep_carbon_cut(tmp_path, monotonic=monotonic)
    auto_retry.sweep_carbon_cut(tmp_path, monotonic=monotonic)
    assert len(_alerts(tmp_path)) == 1


def test_a_task_whose_retries_are_spent_is_not_scheduled_again(tmp_path):
    markers = _state(tmp_path, {T["R"]: "RELEASED"})
    _marker(markers, T["R"], "FAILED", "WorkerFailure")
    log = tmp_path / "auto-grade" / "requeued"
    log.mkdir(parents=True, exist_ok=True)
    with open(log / auto_retry.LOG_NAME, "a") as out:
        for k in range(auto_retry.PER_CAUSE_RETRIES):
            out.write(
                json.dumps(
                    {"task": T["R"], "kind": "scheduled", "code": "WorkerFailure"}
                )
                + "\n"
            )
            out.write(json.dumps({"task": T["R"], "kind": "refused"}) + "\n")
    assert auto_retry.sweep_carbon_cut(tmp_path) == []


def test_the_manual_requeue_takes_a_failed_marker_whose_rows_hold_no_slot(tmp_path):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE exam_graded (submission_id TEXT, kind TEXT, state TEXT)")
    db.executemany(
        "INSERT INTO exam_graded VALUES (?, 'GRADED', ?)",
        [(T["R"], "RELEASED"), (T["K"], "COUNTED"), (T["C"], "RESERVED")],
    )
    assert infra_requeue._carbon_settled(db, T["R"]) is True
    # no row: cut before its reservation
    assert infra_requeue._carbon_settled(db, T["O"]) is True
    assert infra_requeue._carbon_settled(db, T["K"]) is False
    assert infra_requeue._carbon_settled(db, T["C"]) is False


def test_the_stop_records_the_builds_it_cancelled(tmp_path):
    receiver._record_stop_cancelled(tmp_path, [T["R"], T["C"]])
    receiver._record_stop_cancelled(tmp_path, [])
    path = tmp_path / "auto-grade" / "requeued" / lean_recipe.STOP_CANCELLED
    assert [json.loads(line)["task"] for line in path.read_text().splitlines()] == [
        T["R"],
        T["C"],
    ]


def _stop_cancelled(door_ledger, task):
    directory = door_ledger.path.parent / "auto-grade" / "requeued"
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / lean_recipe.STOP_CANCELLED, "a") as log:
        log.write(json.dumps({"task": task}) + "\n")
    return directory


def test_a_build_our_stop_cancelled_re_runs_at_the_next_start(door_ledger):
    _queue(door_ledger)
    door, provider = _door(door_ledger), _Provider({A: DirectTaskStateV3.CANCELLED})
    provider._cancellations = {A: "mcp-cancel-" + A}
    door._active_owner = lambda sid: HOTKEYS[0]
    door._provider = lambda owner: provider
    directory = _stop_cancelled(door_ledger, A)
    door._apply_rebuild_requests()
    assert provider.started == [(("req", HOTKEYS[0], 1), False)]
    (applied,) = [
        json.loads(line)
        for line in (directory / lean_recipe.REBUILD_APPLIED).read_text().splitlines()
    ]
    assert (applied["task"], applied["new_task"], applied["ruling"]) == (
        A,
        N,
        lean_recipe.STOP_CANCEL_RULING,
    )
    door._apply_rebuild_requests()  # once
    assert len(provider.started) == 1


def test_a_miners_own_withdrawal_or_an_unrecorded_cancel_never_re_runs(door_ledger):
    _queue(door_ledger)
    door, provider = _door(door_ledger), _Provider({A: DirectTaskStateV3.CANCELLED})
    provider._cancellations = {A: lean_recipe.WITHDRAW_PREFIX + A}
    door._active_owner = lambda sid: HOTKEYS[0]
    door._provider = lambda owner: provider
    _stop_cancelled(door_ledger, A)
    door._apply_rebuild_requests()
    assert provider.started == []
    # the automatic path after a build never takes a CANCELLED task (no stop record, no receipt)
    other = _Provider({A: DirectTaskStateV3.CANCELLED})
    other._cancellations = {A: "mcp-cancel-" + A}
    assert door._requeue_failed_build(HOTKEYS[0], ResearchTaskId(A), other) is None
    assert other.started == []

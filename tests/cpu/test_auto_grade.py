"""A receiver that grades its own submissions (E2E gap 1): once per task, typed
failures, never concurrent with a reconstruction, configured explicitly."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, direct_intake, direct_receiver
from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

A, B, C = ("rtsk_" + c * 64 for c in "abc")


class FakeIntake:
    def __init__(self, tasks, behaviour):
        self.adapter = SimpleNamespace(
            contract_digest="sha256:" + "0" * 64,
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: tuple(tasks)),
        )
        self.behaviour = behaviour
        self.calls = []

    def retain_result(self, submission_id, **kwargs):
        self.calls.append((submission_id, sorted(kwargs)))
        outcome = self.behaviour[submission_id]
        if isinstance(outcome, Exception):
            raise outcome
        return {"entry_id": outcome}


def _grader(tmp_path, tasks, behaviour):
    intake = FakeIntake(tasks, behaviour)
    return auto_grade.AutoGrader(intake, tmp_path), intake


def _marker(tmp_path, task):
    return json.loads(
        (tmp_path / "auto-grade" / "markers" / (task + ".json")).read_text()
    )


def test_each_ready_task_is_graded_once_and_marked(tmp_path):
    grader, intake = _grader(
        tmp_path, [A, B], {A: "sha256:" + "1" * 64, B: "sha256:" + "2" * 64}
    )
    assert grader.run_once() == (A, "GRADED")
    assert grader.run_once() == (B, "GRADED")
    assert grader.run_once() is None
    assert [c[0] for c in intake.calls] == [A, B]  # never retained twice
    marker = _marker(tmp_path, A)
    assert marker["state"] == "GRADED" and marker["entry_id"] == "sha256:" + "1" * 64
    # The operator directories are the receiver's own, owner-only.
    assert intake.calls[0][1] == ["artifact_directory", "entry_directory", "pool_store"]
    assert (tmp_path / "auto-grade" / "entries").is_dir()


def test_a_task_still_building_is_left_alone_until_it_succeeds(tmp_path):
    behaviour = {A: RetentionUnavailable("task_not_succeeded")}
    grader, intake = _grader(tmp_path, [A], behaviour)
    assert grader.run_once() is None
    assert not list((tmp_path / "auto-grade" / "markers").glob("*.json"))
    behaviour[A] = "sha256:" + "3" * 64
    assert grader.run_once() == (A, "GRADED")


def test_a_failed_retention_is_a_typed_marker_and_is_never_retried(tmp_path):
    behaviour = {
        A: RetentionUnavailable("inference_pair_identity_already_used"),
        B: "x",
    }
    grader, intake = _grader(tmp_path, [A, B], behaviour)
    assert grader.run_once() == (A, "FAILED")
    marker = _marker(tmp_path, A)
    assert marker["state"] == "FAILED"
    assert marker["code"] == "inference_pair_identity_already_used"
    assert marker["entry_id"] is None
    assert grader.run_once() == (B, "GRADED")
    assert grader.run_once() is None
    assert [c[0] for c in intake.calls].count(A) == 1


def test_an_unexpected_error_is_recorded_by_type_only(tmp_path):
    behaviour = {A: RuntimeError("secret detail /private/path")}
    grader, _ = _grader(tmp_path, [A], behaviour)
    assert grader.run_once() == (A, "FAILED")
    text = (tmp_path / "auto-grade" / "markers" / (A + ".json")).read_text()
    assert "RuntimeError" in text and "secret" not in text and "/private" not in text


def test_a_marker_is_create_only_and_an_operator_deleting_it_retries(tmp_path):
    behaviour = {A: RetentionUnavailable("verified_attempt_gone")}
    grader, intake = _grader(tmp_path, [A], behaviour)
    grader.run_once()
    behaviour[A] = "sha256:" + "4" * 64
    assert grader.run_once() is None
    (tmp_path / "auto-grade" / "markers" / (A + ".json")).unlink()
    assert grader.run_once() == (A, "GRADED")


def test_a_malformed_task_id_is_never_passed_on(tmp_path):
    grader, intake = _grader(tmp_path, ["../../etc/passwd", "rtsk_short"], {})
    assert grader.run_once() is None and intake.calls == []


def test_grading_and_advancing_never_run_at_the_same_time():
    work = threading.Lock()
    inside, overlap = [], []
    stop = threading.Event()

    class Advancer:
        def advance(self):
            if inside:
                overlap.append("advance during grade")
            inside.append("advance")
            threading.Event().wait(0.02)
            inside.pop()

    class Grader:
        calls = 0

        def run_once(self):
            if inside:
                overlap.append("grade during advance")
            inside.append("grade")
            threading.Event().wait(0.02)
            inside.pop()
            Grader.calls += 1
            if Grader.calls >= 5:
                stop.set()
            return (A, "GRADED")

    threads = [
        threading.Thread(
            target=direct_intake._advance_loop, args=(Advancer(), stop, work)
        ),
        threading.Thread(target=direct_intake._grade_loop, args=(Grader(), stop, work)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert Grader.calls >= 5 and overlap == []


@pytest.mark.parametrize(
    "value,ok",
    [
        ({}, True),
        ({"pool_store": "/abs/pool.sqlite3"}, True),
        ({"pool_store": "relative.sqlite3"}, False),
        ({"pool_store": 3}, False),
        ({"extra": 1}, False),
        (True, False),
    ],
)
def test_the_receiver_configuration_validates_auto_grade(
    tmp_path, monkeypatch, value, ok
):
    from test_direct_receiver import _config

    cfg = {**_config(tmp_path), "auto_grade": value}
    monkeypatch.setattr(direct_receiver, "private_json", lambda _: cfg)
    if ok:
        assert direct_receiver.load_config(tmp_path / "config.json") == cfg
    else:
        with pytest.raises(ValueError):
            direct_receiver.load_config(tmp_path / "config.json")


def test_a_receiver_without_auto_grade_is_unchanged(tmp_path, monkeypatch):
    from test_direct_receiver import _config

    cfg = _config(tmp_path)
    monkeypatch.setattr(direct_receiver, "private_json", lambda _: cfg)
    assert "auto_grade" not in direct_receiver.load_config(tmp_path / "config.json")

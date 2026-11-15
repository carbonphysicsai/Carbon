"""The v8 feedback reply (Lead 15 Nov: "for every settled task ... which phase/pass ... plus a public line on the grade worker").

Claims: v8 is opt-in by the kit's request and advertised; it is v7 plus ``failure.pass`` (which pass of a counted grade a wall
stop ended, from the grade marker, closed names) and ``grade_worker`` (the grading machine's public facts: CPU model, the
registered CPU count and memory, GPU or not); every older reply is unchanged; the pass is set where each counted wall stop
is settled and carried on the marker; the kit asks for v8 only where advertised and refuses anything outside its shape.
Nothing measured anywhere. Synthetic fixtures only.
"""

# ruff: noqa: F811
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_gate_failure_feedback import (  # noqa: F401 - the fixtures and helpers
    EXAM,
    HOTKEY,
    SID,
    _intake,
    ledger,
)

from carbon.challenge_validator import direct_intake
from carbon.development_session import direct_submission as client

WALL = {
    "child": "inference",
    "observation": "WORKER_WALL_LIMIT_REACHED",
    "limit": {"name": "inference_wall_seconds_max", "value": 648},
    "code": None,
}
WORKER = {
    "cpu_model": "AMD EPYC 7402P 24-Core Processor",
    "cpu_count": 4,
    "memory_bytes": 16 * 1024**3,
    "gpu": False,
}
V7 = {"v4": True, "v5": True, "v6": True, "v7": True}
V8 = {**V7, "v8": True}


def _intake8(ledger, pass_name="graded_pass"):
    intake = _intake(ledger, {SID: HOTKEY})
    intake._grade_state_v4 = lambda hotkey, sid: ("CANDIDATE_FAILED", dict(WALL))
    intake.grade_marker = lambda sid: {
        "state": "CANDIDATE_FAILED",
        "code": "WORKER_WALL_LIMIT_REACHED",
        **({} if pass_name is None else {"pass": pass_name}),
    }
    intake.grade_worker = lambda: dict(WORKER)
    return intake


def _reply(intake, **kw):
    return direct_intake.DirectRecipeIntake._feedback(
        intake, HOTKEY, submission_id=SID, **kw
    )


def test_v8_adds_the_pass_and_the_grade_worker_and_v7_is_unchanged(ledger):
    intake = _intake8(ledger)
    v8 = _reply(intake, **V8)
    assert v8.status == 200
    assert v8.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V8
    submission = v8.body["submission"]
    assert submission["failure"] == {**WALL, "pass": "graded_pass"}
    assert submission["grade_worker"] == WORKER
    v7 = _reply(intake, **V7).body["submission"]
    assert (
        v7["failure"] == WALL and "grade_worker" not in v7
    )  # an older reply keeps v4's closed keys


@pytest.mark.parametrize("marker_pass", [None, "a_new_pass", 7])
def test_an_unnamed_or_unknown_pass_is_none_never_guessed(ledger, marker_pass):
    failure = _reply(_intake8(ledger, marker_pass), **V8).body["submission"]["failure"]
    assert failure["pass"] is None


def test_v8_is_opt_in_recognised_and_advertised():
    assert direct_intake.feedback_reply({"reply": "v8", "submission_id": SID}) == "v8"
    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"exam_feedback_v8"' in text
    assert direct_intake.FAILURE_PASSES == client.FAILURE_PASSES


def test_the_grade_worker_is_the_hosts_cpu_and_the_registered_public_limits(
    monkeypatch,
):
    monkeypatch.setattr(direct_intake, "_cpu_model", lambda: "Some CPU")
    policy = {"cpu_count_max": 4, "memory_bytes_max": 16 * 1024**3, "x": 1}
    door = SimpleNamespace(
        adapter=SimpleNamespace(
            discovery=SimpleNamespace(
                _material={
                    "construction_limits_document": {
                        "reconstruction_resource_policy": policy
                    }
                }
            )
        )
    )
    worker = direct_intake.DirectRecipeIntake.grade_worker(door)
    assert worker == {
        "cpu_model": "Some CPU",
        "cpu_count": 4,
        "memory_bytes": 16 * 1024**3,
        "gpu": False,
    }
    door.grading_gpu = True
    assert direct_intake.DirectRecipeIntake.grade_worker(door)["gpu"] is True
    door.adapter = SimpleNamespace(discovery=SimpleNamespace(_material={}))
    assert direct_intake.DirectRecipeIntake.grade_worker(door)["cpu_count"] is None


# --- where the pass is set -----------------------------------------------------------------------------------------


def test_a_settled_wall_stop_keeps_only_a_closed_pass_name():
    from carbon.challenge_validator import lean_recipe_retention as retention

    assert retention.WALL_STOP_PASSES == direct_intake.FAILURE_PASSES
    for name in retention.WALL_STOP_PASSES:
        settled = retention._settle_candidate_wall_hit(None, None, {}, name)
        assert settled["private_evaluation_pass"] == name
    assert "private_evaluation_pass" not in retention._settle_candidate_wall_hit(
        None, None, {}, "other"
    )


def test_the_official_pairs_second_wall_names_the_inference_pair(tmp_path, monkeypatch):
    from test_while_walls_typed_candidate_failure import _pair, _pair_failure, _wall

    from carbon.challenge_validator import lean_recipe_retention as retention

    run, _calls = _pair(
        tmp_path, monkeypatch, [_pair_failure(_wall()), _pair_failure(_wall())]
    )
    with pytest.raises(retention.CandidateWallLimitReached) as caught:
        run()
    assert caught.value.carbon_pass == "inference_pair"


def test_the_grade_marker_carries_the_pass_of_a_settled_wall_stop(tmp_path):
    from test_while_walls_typed_candidate_failure import _grader

    grader, *_rest, task = _grader(
        tmp_path,
        {
            "entry_id": "sha256:" + "1" * 64,
            "private_evaluation_state": "CANDIDATE_FAILED",
            "private_evaluation_reason": "WORKER_WALL_LIMIT_REACHED",
            "private_evaluation_pass": "inference_pair",
        },
    )
    assert grader.run_once() == (task, "CANDIDATE_FAILED")
    assert grader.marker(task)["pass"] == "inference_pair"


# --- the kit -------------------------------------------------------------------------------------------------------


def _kit(monkeypatch, reply, versions):
    """The v7 test's kit harness (`test_feedback_reply_v7._kit`, which advertises v2..v7), plus v8's facts entry when
    ``versions`` names it."""
    from test_feedback_reply_v7 import _kit as kit7

    if "v8" in versions:
        original = client.read_exam_feedback

        def with_v8(*args, read, **kw):
            facts = {**read(None), "exam_feedback_v8": client.FEEDBACK_V8_FACTS}
            return original(*args, read=lambda url: facts, **kw)

        monkeypatch.setattr(client, "read_exam_feedback", with_v8)
    return kit7(monkeypatch, reply, tuple(v for v in versions if v != "v8"))


def test_a_v8_kit_asks_for_v8_where_advertised_and_keeps_the_pass_and_worker(
    ledger, monkeypatch
):
    body = _reply(_intake8(ledger), **V8).body
    got, sent = _kit(monkeypatch, body, ("v2", "v3", "v4", "v5", "v6", "v7", "v8"))
    assert sent == {"reply": "v8", "submission_id": SID}
    assert got["submission"]["failure"]["pass"] == "graded_pass"
    assert got["submission"]["grade_worker"] == WORKER


@pytest.mark.parametrize(
    "change",
    [
        {"failure": {**WALL, "pass": "slow"}},
        {"failure": {**WALL, "pass": "graded_pass", "seconds": 700}},
        {"grade_worker": {**WORKER, "measured_seconds": 1}},
        {"grade_worker": {**WORKER, "cpu_count": True}},
        {"grade_worker": {**WORKER, "cpu_model": "x" * 97}},
    ],
)
def test_a_v8_kit_refuses_anything_outside_the_shape(ledger, monkeypatch, change):
    body = _reply(_intake8(ledger), **V8).body
    bad = {**body, "submission": {**body["submission"], **change}}
    with pytest.raises(client.DirectIntakeRefusal):
        _kit(monkeypatch, bad, ("v2", "v3", "v4", "v5", "v6", "v7", "v8"))


def test_a_v8_kit_against_a_receiver_without_v8_asks_v7_unchanged(ledger, monkeypatch):
    body = _reply(_intake8(ledger), **V7).body
    got, sent = _kit(monkeypatch, body, ("v2", "v3", "v4", "v5", "v6", "v7"))
    assert sent == {"reply": "v7", "submission_id": SID}
    assert got["submission"]["failure"] == WALL

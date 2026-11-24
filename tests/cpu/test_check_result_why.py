"""check_result says WHY a try ended as it did (Lead 15 Nov: "for every settled task ... the failure code, which phase/pass,
and the limit ... plus a public line on the grade worker"). The receiver's signed exam_feedback v4+ sends THIS submission's
closed ``grade_state`` and allow-listed ``failure`` (v8 adds the pass and the grade worker); the kit's projection shows them
as ``why``, in words and as data, only for a reply about this very task. Nothing measured is shown: the receiver sends no
seconds or memory of a hidden-input run (Validator ruling, 4 Nov). Synthetic replies only.
"""

from __future__ import annotations

import pytest

from carbon.challenge_validator import direct_intake
from carbon.development_session import direct_submission as client
from scripts.dev.miner_launchpad import projection

DIGEST = "sha256:" + "d" * 64
SID = "rtsk_" + "a" * 64
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


def _ladder(submission):
    return {"best": None, "latest": None, "submission": submission}


def _block(grade_state, failure, sid=SID, **extra):
    return {
        "submission_id": sid,
        "grade_state": grade_state,
        "failure": failure,
        "held_position": None,
        "gate_failures": None,
        **extra,
    }


def _why(block, task=SID):
    return projection._grade(_ladder(block), submission=DIGEST, task=task).get("why")


def test_a_counted_wall_stop_says_which_step_what_happened_and_the_public_limit():
    why = _why(_block("CANDIDATE_FAILED", WALL))
    assert why["grade_state"] == "CANDIDATE_FAILED" and why["failure"] == WALL
    assert why["words"] == (
        "counted as your try: your model's own run failed while it was being graded; "
        "your model's inference on the exam ran into the time limit "
        "(inference_wall_seconds_max = 648 s)"
    )


def test_v8_adds_the_pass_and_the_grade_worker_line():
    why = _why(
        _block("CANDIDATE_FAILED", {**WALL, "pass": "graded_pass"}, grade_worker=WORKER)
    )
    assert (
        "ran into the time limit in the graded pass (inference_wall_seconds_max = 648 s)"
        in (why["words"])
    )
    assert why["words"].endswith(
        "graded on AMD EPYC 7402P 24-Core Processor, 4 CPUs, 16 GiB, no GPU"
    )
    assert why["grade_worker"] == WORKER
    early = _why(_block("CANDIDATE_FAILED", {**WALL, "pass": "early_stop"}))
    assert "stopped early" in early["words"]


def test_a_reply_about_another_task_shows_nothing():
    """A stale stored read (the task was resubmitted, the refresh failed) never explains the new task."""
    assert _why(_block("CANDIDATE_FAILED", WALL, sid="rtsk_" + "b" * 64)) is None
    assert _why(_block("CANDIDATE_FAILED", WALL), task=None) is None


@pytest.mark.parametrize(
    ("state", "phrase"),
    [
        ("FAILED_INFRA", "not your result"),
        ("NOT_GRADED", "given back"),
        ("QUEUED", "waiting"),
        ("GRADED", "counted as your try"),
        ("ROUND_LIMIT_REACHED", "already used"),
        ("SUPERSEDED_BY_OWN_LATER_SUBMIT", "later submission"),
        ("CROWN_HELD_FOR_REVIEW", "held for review"),
        ("WITHDRAWN_BY_MINER", "used no try"),
        ("RERUN", "re-ran this submission at no charge"),
    ],
)
def test_every_state_reads_in_words_and_claims_no_ladder_line(state, phrase):
    why = _why(_block(state, None))
    assert why["grade_state"] == state and why["failure"] is None
    assert phrase in why["words"] and "Ladder" not in why["words"]


def test_every_state_and_observation_the_receiver_can_send_has_words():
    # v9 adds WITHDRAWN_BY_MINER (a miner's own withdrawal of a queued submission), v12 RERUN (the door's re-run under a new
    # id): every state a v12 reply can send has words
    assert set(projection.GRADE_STATE_WORDS) == set(client.GRADE_STATES_V12)
    assert set(projection.FAILURE_OBSERVATION_WORDS) == set(client.FAILURE_OBSERVATIONS)
    assert set(projection.FAILURE_CHILD_WORDS) == set(client.FAILURE_CHILDREN)
    assert set(projection.FAILURE_PASS_WORDS) == set(direct_intake.FAILURE_PASSES)


def test_a_failed_inference_child_and_a_missing_observation_read_whole():
    words = _why(
        _block("RECONSTRUCTION_FAILED", {**WALL, "limit": None, "code": "x_y"})
    )["words"]
    assert "your model's inference on the exam ran into the time limit" in words
    assert "practice" not in words
    bare = _why(
        _block("CANDIDATE_FAILED", {**WALL, "observation": None, "limit": None})
    )
    assert bare["words"].endswith("; failing step: your model's inference on the exam")


def test_memory_reads_in_gib_and_the_code_is_named():
    failure = {
        "child": "build",
        "observation": "WORKER_MEMORY_LIMIT_REACHED",
        "limit": {"name": "memory_bytes_max", "value": 16 * 1024**3},
        "code": "worker_memory_limit_reached",
    }
    words = _why(_block("RECONSTRUCTION_FAILED", failure))["words"]
    assert "the build of your model reached the memory limit" in words
    assert (
        "(memory_bytes_max = 16 GiB)" in words
        and "code worker_memory_limit_reached" in words
    )


def test_an_older_reply_or_a_malformed_block_shows_no_why():
    assert _why({"submission_id": SID, "grade_state": "CANDIDATE_FAILED"}) is None
    assert _why(None) is None
    for bad in (
        _block(
            "CANDIDATE_FAILED", {**WALL, "seconds": 700}
        ),  # never outside the allow-list
        _block("CANDIDATE_FAILED", {**WALL, "observation": "SLOW"}),
        _block("CANDIDATE_FAILED", {**WALL, "limit": {"name": "x", "value": 1}}),
        _block("SOMETHING_NEW", None),
    ):
        assert _why(bad) is None


def test_the_words_carry_no_measured_value():
    for failure in (WALL, {**WALL, "pass": "graded_pass"}):
        why = _why(_block("CANDIDATE_FAILED", failure, grade_worker=WORKER))
        words = why["words"].replace("7402P", "").replace("24-Core", "")
        digits = "".join(c if c.isdigit() else " " for c in words).split()
        # only the PUBLIC registered limit and the worker's registered CPU count and memory
        assert digits == ["648", "4", "16"]

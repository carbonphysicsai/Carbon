"""check_result says WHY a try ended as it did (Lead 15 Nov: "for every settled task ... show the failure code, which phase,
and the limit"). The receiver's signed exam_feedback v4+ already sends this submission's closed ``grade_state`` and its
allow-listed ``failure`` (failing step, observation, public registered limit, code); the kit's projection dropped them. It
now shows them as ``why``, in words and as data, read only from the miner's own signed reply. Nothing measured is shown:
the receiver sends no seconds or memory of a hidden-input run (Validator ruling, 4 Nov). Synthetic replies only.
"""

from __future__ import annotations

import pytest

from scripts.dev.miner_launchpad import projection

DIGEST = "sha256:" + "d" * 64
SID = "rtsk_" + "a" * 64


def _ladder(submission):
    return {
        "best": None,
        "latest": None,
        "submission": submission,
    }


def _block(grade_state, failure, **extra):
    return {
        "submission_id": SID,
        "grade_state": grade_state,
        "failure": failure,
        "held_position": None,
        "gate_failures": None,
        **extra,
    }


WALL = {
    "child": "inference",
    "observation": "WORKER_WALL_LIMIT_REACHED",
    "limit": {"name": "inference_wall_seconds_max", "value": 648},
    "code": None,
}


def test_a_counted_wall_stop_says_which_step_what_happened_and_the_public_limit():
    shown = projection._grade(
        _ladder(_block("CANDIDATE_FAILED", WALL)), submission=DIGEST
    )
    why = shown["why"]
    assert why["grade_state"] == "CANDIDATE_FAILED" and why["failure"] == WALL
    assert why["words"] == (
        "counted as your try: your model's own run failed while it was being graded; "
        "your model's inference on the exam ran into the time limit "
        "(inference_wall_seconds_max = 648 s)"
    )


@pytest.mark.parametrize(
    ("state", "phrase"),
    [
        ("FAILED_INFRA", "nothing was charged"),
        ("NOT_GRADED", "given back"),
        ("QUEUED", "waiting"),
        ("GRADED", "counted as your try"),
        ("ROUND_LIMIT_REACHED", "already used"),
        ("SUPERSEDED_BY_OWN_LATER_SUBMIT", "later submission"),
    ],
)
def test_every_settled_or_waiting_state_reads_in_words(state, phrase):
    why = projection._grade(_ladder(_block(state, None)), submission=DIGEST)["why"]
    assert why["grade_state"] == state and why["failure"] is None
    assert phrase in why["words"]


def test_a_reconstruction_failure_names_the_build_its_code_and_memory_in_gib():
    failure = {
        "child": "build",
        "observation": "WORKER_MEMORY_LIMIT_REACHED",
        "limit": {"name": "memory_bytes_max", "value": 16 * 1024**3},
        "code": "worker_memory_limit_reached",
    }
    words = projection._grade(
        _ladder(_block("RECONSTRUCTION_FAILED", failure)), submission=DIGEST
    )["why"]["words"]
    assert "the build of your model reached the memory limit" in words
    assert (
        "(memory_bytes_max = 16 GiB)" in words
        and "code worker_memory_limit_reached" in words
    )


def test_an_older_reply_or_a_malformed_block_shows_no_why():
    # v2/v3 replies carry no failure key: nothing is guessed
    older = {"submission_id": SID, "grade_state": "CANDIDATE_FAILED"}
    assert "why" not in projection._grade(_ladder(older), submission=DIGEST)
    assert "why" not in projection._grade(_ladder(None), submission=DIGEST)
    for bad in (
        _block(
            "CANDIDATE_FAILED", {**WALL, "seconds": 700}
        ),  # never a field outside the allow-list
        _block("CANDIDATE_FAILED", {**WALL, "observation": "SLOW"}),
        _block("CANDIDATE_FAILED", {**WALL, "limit": {"name": "x", "value": 1}}),
        _block("SOMETHING_NEW", None),
    ):
        assert "why" not in projection._grade(_ladder(bad), submission=DIGEST)


def test_the_words_carry_no_measured_value():
    why = projection._grade(
        _ladder(_block("CANDIDATE_FAILED", WALL)), submission=DIGEST
    )["why"]
    # the only number is the PUBLIC registered limit the reply named
    digits = "".join(c if c.isdigit() else " " for c in why["words"]).split()
    assert digits == ["648"]

"""Feedback v13, the kit's side (owner G-LEAD-78; door-code 6981), and the words of a proven non-finite answer (G-LEAD-75).

- v13 is asked for only where the door advertises it; ``submission.refusal_detail`` is a closed code on RECONSTRUCTION_FAILED
  only, and the kit prints it; any other shape is refused whole.
- The newest advertised reply is chosen from one table, for every version back to v1.
- ``nonfinite_output`` in a v4+ ``failure`` reads 'the model returned a non-finite value'.

Synthetic replies only.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake
from carbon.development_session import direct_submission as client
from scripts.dev.miner_launchpad import projection

SID = "rtsk_" + "a" * 64
CODE = "graph_route_nonfinite_state"
WORKER = {
    "cpu_model": "AMD EPYC",
    "cpu_count": 4,
    "memory_bytes": 16 * 1024**3,
    "gpu": False,
}
NUMBERS = tuple(number for number, _, _ in client.FEEDBACK_REPLIES)


def _submission(number, grade_state, **extra):
    """The ``submission`` of a v``number`` reply for SID."""
    submission = {"submission_id": SID, "grade_state": grade_state}
    for start, name, value in (
        (4, "failure", None),
        (5, "held_position", None),
        (6, "gate_failures", None),
        (8, "grade_worker", WORKER),
        (10, "failure_class", None),
        (12, "rerun_task_id", None),
        (13, "refusal_detail", None),
    ):
        if number >= start:
            submission[name] = value
    submission.update(extra)
    return submission


def _kit(monkeypatch, number, submission, *, advertised=None):
    """Read a v``number`` reply against a door advertising v2..``advertised`` (default v``number``)."""
    sent = []
    newest = number if advertised is None else advertised
    recipe = object.__new__(client.ConstructionRecipe)
    challenge = {"id": "electric-motor-magnetics", "version": "1.8"}
    monkeypatch.setattr(
        client.ConstructionRecipe, "to_dict", lambda self: {"challenge": challenge}
    )
    monkeypatch.setattr(client, "_body", lambda facts, **kw: {"fields": kw["fields"]})
    monkeypatch.setattr(
        client,
        "BittensorMessageSigner",
        lambda signer: SimpleNamespace(sign=lambda body, **kw: {}),
    )
    facts = {"exam_feedback": client.FEEDBACK_FACTS}
    schema = client.FEEDBACK_REPLY_SCHEMA
    for known, advertised_facts, reply_schema in client.FEEDBACK_REPLIES:
        if known <= newest:
            facts[f"exam_feedback_v{known}"] = advertised_facts
        if known == number:
            schema = reply_schema
    reply = {"schema": schema, "challenge": challenge, "best": None, "latest": None}
    if number >= 2:
        reply["submission"] = submission

    def send(url, body, headers):
        sent.append(body["fields"])
        return 200, reply

    got = client.read_exam_feedback(
        "http://127.0.0.1:1",
        "external-signer",
        recipe=recipe,
        contract_digest="sha256:" + "c" * 64,
        receiver="validator",
        context=None,
        read=lambda url: facts,
        send=send,
        submission_id=SID,
    )
    return got, sent[-1]


def _why(submission):
    return projection._grade(
        {"best": None, "latest": None, "submission": submission},
        submission="sha256:" + "d" * 64,
        task=SID,
    )["why"]


def test_the_table_is_newest_first_and_pins_the_doors_schemas():
    assert NUMBERS == tuple(range(13, 1, -1))
    for number, facts, schema in client.FEEDBACK_REPLIES:
        assert schema.endswith(f".v{number}")
        assert facts["reply_schema"] == schema
        # v13's own door head may land after this kit: pinned once the door has it
        door = getattr(direct_intake, f"FEEDBACK_REPLY_SCHEMA_V{number}", None)
        assert door == schema or (door is None and number == 13)


@pytest.mark.parametrize("number", NUMBERS)
def test_the_kit_asks_for_the_newest_reply_advertised(monkeypatch, number):
    got, sent = _kit(monkeypatch, number, _submission(number, "QUEUED"))
    expected = {"submission_id": SID}
    if number >= 3:
        expected["reply"] = f"v{number}"
    assert sent == expected
    assert got["submission"]["grade_state"] == "QUEUED"


def test_a_door_without_v2_is_read_as_v1(monkeypatch):
    got, sent = _kit(monkeypatch, 1, None)
    assert sent == {} and "submission" not in got


@pytest.mark.parametrize("number", NUMBERS)
def test_no_state_is_read_only_before_v4(monkeypatch, number):
    submission = _submission(number, None)
    if number < 4:
        got, _ = _kit(monkeypatch, number, submission)
        assert got["submission"]["grade_state"] is None
    else:
        with pytest.raises(client.DirectIntakeRefusal):
            _kit(monkeypatch, number, submission)


def test_a_refused_builds_code_is_read_and_printed(monkeypatch):
    submission = _submission(13, "RECONSTRUCTION_FAILED", refusal_detail=CODE)
    got, _ = _kit(monkeypatch, 13, submission)
    assert got["submission"]["refusal_detail"] == CODE
    why = _why(got["submission"])
    assert why["refusal_detail"] == CODE
    assert "Refusal code " + CODE in why["words"]
    # none kept (a refusal recorded before the code was): the state alone, as before
    got, _ = _kit(monkeypatch, 13, _submission(13, "RECONSTRUCTION_FAILED"))
    why = _why(got["submission"])
    assert "refusal_detail" not in why and "Refusal code" not in why["words"]


@pytest.mark.parametrize(
    "submission",
    [
        _submission(13, "GRADED", refusal_detail=CODE),  # another state
        _submission(13, "RECONSTRUCTION_FAILED", refusal_detail="Not A Code"),
        _submission(13, "RECONSTRUCTION_FAILED", refusal_detail="a" * 65),
        _submission(13, "RECONSTRUCTION_FAILED", refusal_detail=7),
        _submission(13, "QUEUED", extra=1),
        _submission(12, "QUEUED"),  # the v13 key missing
    ],
)
def test_a_v13_reply_of_any_other_shape_is_refused_whole(monkeypatch, submission):
    with pytest.raises(client.DirectIntakeRefusal):
        _kit(monkeypatch, 13, submission)


def test_an_older_schema_where_v13_was_asked_is_refused(monkeypatch):
    with pytest.raises(client.DirectIntakeRefusal):
        _kit(monkeypatch, 12, _submission(12, "QUEUED"), advertised=13)


@pytest.mark.parametrize("state", ["NOT_GRADED", "CANDIDATE_FAILED"])
def test_a_proven_non_finite_answer_says_so(monkeypatch, state):
    failure = {
        "child": "inference",
        "observation": None,
        "limit": None,
        "code": "nonfinite_output",
        "pass": None,
    }
    got, _ = _kit(monkeypatch, 12, _submission(12, state, failure=failure))
    words = _why(got["submission"])["words"]
    assert "(the model returned a non-finite value) code nonfinite_output" in words

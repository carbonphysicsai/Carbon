"""The miner side of the held-contender view (Miner X-B / TE-B, 7 Nov).

- The client asks the signed feedback read for v5 only where the receiver advertises it, and accepts back only
  v5's allow-listed shape: v4 plus the CROWN_HELD_FOR_REVIEW state and ``held_position`` {place, of}, present exactly
  when the submission is held.
- The projection turns that reply into one plain sentence for the page and the MCP result; nothing is computed.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.development_session import direct_submission as client
from carbon.registry.model import ChallengeKey
from scripts.dev.miner_launchpad import projection

MOTOR = ChallengeKey("electric-motor-magnetics", "1.8")
CONTRACT = "sha256:" + "c" * 64
A = "task-" + "a" * 16
OK_FAILURE = None


@pytest.fixture
def read(monkeypatch):
    """The client's read against a fixture receiver advertising ``versions``; returns (run, sent fields)."""
    sent = []
    recipe = object.__new__(client.ConstructionRecipe)
    monkeypatch.setattr(
        client.ConstructionRecipe,
        "to_dict",
        lambda self: {
            "challenge": {"id": MOTOR.challenge_id, "version": MOTOR.version}
        },
    )
    monkeypatch.setattr(client, "_body", lambda facts, **kw: {"fields": kw["fields"]})
    monkeypatch.setattr(
        client,
        "BittensorMessageSigner",
        lambda signer: SimpleNamespace(sign=lambda body, **kw: {}),
    )
    every = {
        "v2": ("exam_feedback_v2", client.FEEDBACK_V2_FACTS),
        "v3": ("exam_feedback_v3", client.FEEDBACK_V3_FACTS),
        "v4": ("exam_feedback_v4", client.FEEDBACK_V4_FACTS),
        "v5": ("exam_feedback_v5", client.FEEDBACK_V5_FACTS),
    }

    def run(reply, *, versions=("v2", "v3", "v4", "v5")):
        facts = {"exam_feedback": client.FEEDBACK_FACTS}
        facts.update(dict(every[v] for v in versions))

        def send(url, body, headers):
            sent.append(body["fields"])
            return 200, {
                "challenge": {"id": MOTOR.challenge_id, "version": MOTOR.version},
                "best": None,
                "latest": None,
                **reply,
            }

        return client.read_exam_feedback(
            "http://127.0.0.1:1",
            "external-signer",
            recipe=recipe,
            contract_digest=CONTRACT,
            receiver="validator",
            context=None,
            read=lambda url: facts,
            send=send,
            submission_id=A,
        )

    return run, sent


def _v5(grade_state, held_position):
    return {
        "schema": client.FEEDBACK_REPLY_SCHEMA_V5,
        "submission": {
            "submission_id": A,
            "grade_state": grade_state,
            "failure": OK_FAILURE,
            "held_position": held_position,
        },
    }


def test_the_names_are_the_door_heads_posted_shape():
    # TE-B's teb/queue-held b8951090 (board 15:37): the same strings on both sides.
    assert (
        client.FEEDBACK_REPLY_SCHEMA_V5
        == "carbon.private-exam.ladder-feedback-reply.v5"
    )
    assert client.HELD_STATE == "CROWN_HELD_FOR_REVIEW"
    assert client.FEEDBACK_V5_FACTS["fields"] == ["reply", "submission_id"]
    assert client.GRADE_STATES_V5 == (*client.GRADE_STATES_V4, "CROWN_HELD_FOR_REVIEW")


def test_the_client_asks_v5_where_advertised_and_reads_the_held_place(read):
    run, sent = read
    got = run(_v5("CROWN_HELD_FOR_REVIEW", {"place": 2, "of": 3}))
    assert sent[-1] == {"reply": "v5", "submission_id": A}
    assert got["submission"]["held_position"] == {"place": 2, "of": 3}
    got = run(_v5("GRADED", None))
    assert got["submission"]["grade_state"] == "GRADED"


def test_a_receiver_without_v5_still_gets_v4_unchanged(read):
    run, sent = read
    run(
        {
            "schema": client.FEEDBACK_REPLY_SCHEMA_V4,
            "submission": {
                "submission_id": A,
                "grade_state": "GRADED",
                "failure": None,
            },
        },
        versions=("v2", "v3", "v4"),
    )
    assert sent[-1] == {"reply": "v4", "submission_id": A}


@pytest.mark.parametrize(
    "grade_state, held",
    [
        ("CROWN_HELD_FOR_REVIEW", None),  # held, but no place
        ("GRADED", {"place": 1, "of": 1}),  # a place on a submission that is not held
        ("CROWN_HELD_FOR_REVIEW", {"place": 0, "of": 3}),
        ("CROWN_HELD_FOR_REVIEW", {"place": 4, "of": 3}),
        (
            "CROWN_HELD_FOR_REVIEW",
            {"place": 1, "of": 2, "hotkey": "5Other"},
        ),  # an extra field
        ("CROWN_HELD_FOR_REVIEW", {"place": 1.0, "of": 2}),
        ("CROWN_HELD_FOR_REVIEW", {"place": True, "of": 2}),
        ("ON_FIRE", None),
    ],
)
def test_any_other_v5_shape_is_refused_never_trimmed(read, grade_state, held):
    run, _sent = read
    with pytest.raises(client.DirectIntakeRefusal):
        run(_v5(grade_state, held))


def test_a_v5_reply_without_held_position_is_refused(read):
    run, _sent = read
    reply = _v5("GRADED", None)
    del reply["submission"]["held_position"]
    with pytest.raises(client.DirectIntakeRefusal):
        run(reply)


def test_the_projection_says_it_in_words_only_when_held():
    held = {
        "submission_id": A,
        "grade_state": "CROWN_HELD_FOR_REVIEW",
        "held_position": {"place": 2, "of": 3},
    }
    review = projection._crown_review(held)
    assert review["place"] == 2 and review["of"] == 3
    assert "(2 of 3 held)" in review["words"]
    assert "the king keeps the crown" in review["words"]
    grade = projection._grade(
        {"best": None, "latest": None, "submission": held}, "sha256:" + "d" * 64
    )
    assert grade["crown_review"] == review
    plain = projection._grade(
        {
            "best": None,
            "latest": None,
            "submission": {**held, "grade_state": "GRADED", "held_position": None},
        },
        "sha256:" + "d" * 64,
    )
    assert "crown_review" not in plain
    assert "crown_review" not in projection._grade({"best": None, "latest": None}, None)
    bad = {**held, "held_position": {"place": 5, "of": 3}}
    assert projection._crown_review(bad) is None

"""The held-contender queue view (Miner X-B / TE-B 7 Nov): the public queue v2 adds ``held_for_review`` (a count on a
crown-hold door, None elsewhere; v1 byte-identical), and the signed feedback v5 tells the caller, for its OWN held
submission only, CROWN_HELD_FOR_REVIEW and its place among the held contenders. Fixture values only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_queue_public import CHALLENGE, TASKS, _door, _snapshot, _View

from carbon.challenge_validator import crown_hold, direct_intake, queue_public

HOTKEY, OTHER = "5" + "M" * 47, "5" + "N" * 47


@pytest.fixture
def hold(monkeypatch):
    monkeypatch.setattr(crown_hold, "ACTIVE", True)


class _Store:
    def __init__(self, ids):
        self.ids = list(ids)

    def paused_crowns(self, kind=None):
        assert kind is None  # every kind: a pack contender and a set contender both wait
        return [{"submission_id": i, "evaluation_key": "sha256:" + "a" * 64} for i in self.ids]


# --- the public document ---------------------------------------------------------------------------------------------


def test_v1_is_unchanged_by_the_held_count():
    plain = queue_public.serve(_View(_snapshot()), CHALLENGE)
    with_held = queue_public.serve(_View(_snapshot(held_for_review=3)), CHALLENGE)
    assert plain == with_held
    assert plain[1]["schema"] == queue_public.SCHEMA and "held_for_review" not in plain[1]


def test_v2_adds_held_for_review_a_count_or_null():
    status, body = queue_public.serve_v2(_View(_snapshot(held_for_review=2)), CHALLENGE)
    assert status == 200 and body["schema"] == queue_public.SCHEMA_V2
    assert set(body) == queue_public.FIELDS_V2 and body["held_for_review"] == 2
    _status, off = queue_public.serve_v2(_View(_snapshot(held_for_review=None)), CHALLENGE)
    assert off["held_for_review"] is None  # a door that holds no crown: null, never 0
    v1 = queue_public.serve(_View(_snapshot(held_for_review=2)), CHALLENGE)[1]
    assert {k: v for k, v in body.items() if k not in ("schema", "held_for_review")} == {
        k: v for k, v in v1.items() if k != "schema"
    }


@pytest.mark.parametrize("bad", [-1, True, 1.0, "2"])
def test_a_malformed_held_count_is_unavailable(bad):
    status, body = queue_public.serve_v2(_View(_snapshot(held_for_review=bad)), CHALLENGE)
    assert status == 503 and body == {"refused": "queue_held_invalid"}


def test_v2_needs_the_held_field_from_the_view():
    status, body = queue_public.serve_v2(_View(_snapshot()), CHALLENGE)
    assert status == 503 and body == {"refused": "queue_held_invalid"}


# --- the view --------------------------------------------------------------------------------------------------------


def test_held_is_none_without_a_crown_hold(tmp_path):
    view, grader = _door(tmp_path, {}, pending=[])
    grader._pool = lambda: _Store(TASKS[:2])
    assert view.held() is None
    assert view.snapshot()["held_for_review"] is None


def test_held_lists_every_filed_contender_in_filing_order(tmp_path, hold):
    view, grader = _door(tmp_path, {}, pending=[])
    grader._pool = lambda: _Store([TASKS[3], TASKS[1]])
    assert view.held() == [TASKS[3], TASKS[1]]
    assert view.snapshot()["held_for_review"] == 2
    grader._pool = lambda: None  # a crown-hold door with no pool store: nothing held, not unknown
    assert view.held() == []


def test_the_v2_route_serves_this_challenge_only(tmp_path, hold):
    view, grader = _door(tmp_path, {}, pending=[])
    grader._pool = lambda: _Store([TASKS[0]])
    door = SimpleNamespace(challenge=CHALLENGE, queue_view=view)
    ok = direct_intake.DirectRecipeIntake._queue(
        door, queue_public.PATH + CHALLENGE.challenge_id + queue_public.V2_SUFFIX
    )
    assert ok.status == 200 and ok.body["held_for_review"] == 1
    assert ok.body["schema"] == queue_public.SCHEMA_V2
    v1 = direct_intake.DirectRecipeIntake._queue(door, queue_public.PATH + CHALLENGE.challenge_id)
    assert v1.status == 200 and "held_for_review" not in v1.body
    other = direct_intake.DirectRecipeIntake._queue(
        door, queue_public.PATH + "f08-ribbed-bracket" + queue_public.V2_SUFFIX
    )
    assert other.status == 404


# --- the signed feedback v5 ------------------------------------------------------------------------------------------


def _intake(held, owners):
    intake = SimpleNamespace(
        challenge=SimpleNamespace(challenge_id=CHALLENGE.challenge_id, version=CHALLENGE.version),
        grade_marker=lambda sid: {"state": "GRADED"},
        adapter=SimpleNamespace(
            owner=lambda sid: owners.get(sid),
            discovery=SimpleNamespace(evaluation_pack_snapshot=None),
        ),
        queue_view=SimpleNamespace(held=lambda: held),
    )
    intake._grade_state_v4 = lambda hotkey, sid: ("GRADED", None)
    intake._grade_state = lambda hotkey, sid: "GRADED"
    intake._held = lambda: direct_intake.DirectRecipeIntake._held(intake)
    return intake


def _v5(intake, hotkey, sid):
    return direct_intake.DirectRecipeIntake._feedback(
        intake, hotkey, submission_id=sid, v4=True, v5=True
    )


def test_v5_tells_the_owner_its_held_state_and_place_only():
    owners = {TASKS[0]: OTHER, TASKS[1]: HOTKEY, TASKS[2]: OTHER}
    intake = _intake([TASKS[0], TASKS[1], TASKS[2]], owners)
    reply = _v5(intake, HOTKEY, TASKS[1])
    assert reply.status == 200
    assert reply.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V5
    assert reply.body["submission"] == {
        "submission_id": TASKS[1],
        "grade_state": "CROWN_HELD_FOR_REVIEW",
        "failure": None,
        "held_position": {"place": 2, "of": 3},
    }
    flat = repr(reply.body)
    assert TASKS[0] not in flat and TASKS[2] not in flat and OTHER not in flat


def test_v5_for_a_submission_that_is_not_held_says_nothing_held():
    intake = _intake([TASKS[0]], {TASKS[0]: OTHER, TASKS[1]: HOTKEY})
    reply = _v5(intake, HOTKEY, TASKS[1])
    assert reply.body["submission"]["grade_state"] == "GRADED"
    assert reply.body["submission"]["held_position"] is None
    off = _intake(None, {TASKS[1]: HOTKEY})  # a door with no crown hold
    assert _v5(off, HOTKEY, TASKS[1]).body["submission"]["held_position"] is None


def test_v5_never_answers_for_another_hotkeys_submission():
    intake = _intake([TASKS[0]], {TASKS[0]: OTHER})
    reply = _v5(intake, HOTKEY, TASKS[0])
    assert reply.status == 404 and reply.body["refused"] == "feedback_submission_unknown"


def test_v4_is_unchanged_on_a_held_submission():
    intake = _intake([TASKS[1]], {TASKS[1]: HOTKEY})
    reply = direct_intake.DirectRecipeIntake._feedback(
        intake, HOTKEY, submission_id=TASKS[1], v4=True
    )
    assert reply.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V4
    assert reply.body["submission"] == {"submission_id": TASKS[1], "grade_state": "GRADED", "failure": None}


def test_v5_is_a_recognised_reply_and_advertised():
    assert direct_intake.feedback_reply({"reply": "v5", "submission_id": TASKS[0]}) == "v5"
    assert direct_intake.feedback_reply({"reply": "v6", "submission_id": TASKS[0]}) is None
    text = open(direct_intake.__file__, encoding="utf-8").read()
    assert '"exam_feedback_v5"' in text and "FEEDBACK_REPLY_SCHEMA_V5" in text

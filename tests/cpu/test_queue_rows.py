"""The public per-submission queue rows (owner 14 Nov, "show the actual queue"): ``GET /carbon/v1/queue/<id>/v3``.

One row per pending submission: position, short hotkey (first and last 4), state and time in queue. Nothing about recipes, scores or
the exam; no finer timing than the quantum; v1 and v2 unchanged. Real `queue_public`, `queue_view` and `AutoGrader`; only the providers
and the pool are stood in.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_queue_public import CHALLENGE, NOW, TASKS, _door, _snapshot

from carbon.challenge_validator import direct_intake, queue_public
from carbon.research import DirectTaskStateV3

HOTKEY = "5" + "M" * 47
Q = queue_public.ROWS_QUANTUM_S
#: A boundary of the quantum, so the floors below are exact.
START = (int(NOW) // Q) * Q + 10.0


def _rows_snapshot(rows, *, boundary=START // Q * Q, **change):
    return {
        **_snapshot(**change),
        "held_for_review": None,
        "rows": {"rows": rows, "as_of_unix": boundary},
    }


def _row(position, state="waiting to build", hotkey="5MMM…MMMM", in_queue_s=0):
    return {
        "position": position,
        "hotkey": hotkey,
        "state": state,
        "in_queue_s": in_queue_s,
    }


class _View:
    def __init__(self, snapshot):
        self.value = snapshot

    def snapshot(self):  # v1 / v2
        return {k: v for k, v in self.value.items() if k != "rows"}

    def snapshot_v3(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


# --- the pure document ------------------------------------------------------------------------------------------------


def test_the_v3_document_is_v2_plus_the_closed_rows():
    rows = [
        _row(1, "in grading", in_queue_s=900),
        _row(2, "in grading", in_queue_s=600),
        _row(3, "building", in_queue_s=300),
        _row(4, "waiting to build"),
        _row(5, "crown check", hotkey=None, in_queue_s=3000),
    ]
    status, body = queue_public.serve_v3(_View(_rows_snapshot(rows)), CHALLENGE)
    assert status == 200 and set(body) == queue_public.FIELDS_V3
    assert body["schema"] == queue_public.SCHEMA_V3 and body["more_rows"] == 0
    assert body["rows"] == rows and all(
        set(r) == queue_public.ROW_FIELDS for r in body["rows"]
    )
    v2 = queue_public.serve_v2(_View(_rows_snapshot(rows)), CHALLENGE)[1]
    assert {k: v for k, v in body.items() if k in v2 and k != "schema"} == {
        k: v for k, v in v2.items() if k != "schema"
    }
    raw = json.dumps(body)
    assert "rtsk_" not in raw and len(raw) <= queue_public.MAX_BYTES_V3


def test_v1_and_v2_are_byte_identical_to_before_and_carry_no_rows():
    snapshot = _rows_snapshot([_row(1)])
    v1 = queue_public.serve(_View(snapshot), CHALLENGE)[1]
    v2 = queue_public.serve_v2(_View(snapshot), CHALLENGE)[1]
    assert set(v1) == queue_public.FIELDS and set(v2) == queue_public.FIELDS_V2
    assert "rows" not in v1 and "rows" not in v2


def test_at_most_a_hundred_rows_and_the_rest_are_counted():
    rows = [_row(i + 1) for i in range(130)]
    status, body = queue_public.serve_v3(_View(_rows_snapshot(rows)), CHALLENGE)
    assert status == 200 and len(body["rows"]) == queue_public.MAX_ROWS
    assert body["more_rows"] == 30
    assert body["rows"][-1]["position"] == queue_public.MAX_ROWS


@pytest.mark.parametrize(
    "bad",
    [
        [{**_row(1), "task_id": "rtsk_" + "0" * 64}],  # an extra field
        [{**_row(1), "score": 0.5}],
        [{k: v for k, v in _row(1).items() if k != "state"}],
        [_row(2)],  # positions run 1, 2, ...
        [_row(1, state="queued for the exam")],
        [_row(1, hotkey="5MMMMMMMMMMMM")],  # not first 4 + ellipsis + last 4
        [_row(1, hotkey="5MMM…MMMM and more")],
        [_row(1, in_queue_s=301)],  # not a whole quantum
        [_row(1, in_queue_s=-300)],
        [_row(1, in_queue_s=300.0)],
        [_row(1, in_queue_s=True)],
        "rows",
    ],
)
def test_a_malformed_row_is_unavailable_never_partial(bad):
    status, body = queue_public.serve_v3(_View(_rows_snapshot(bad)), CHALLENGE)
    assert status == 503 and set(body) == {"refused"}


def test_a_snapshot_without_rows_or_with_a_bad_stamp_is_unavailable():
    plain = {**_snapshot(), "held_for_review": None}
    assert queue_public.serve_v3(_View(plain), CHALLENGE)[0] == 503
    bad = _rows_snapshot([_row(1)])
    bad["rows"]["as_of_unix"] = float("nan")
    assert queue_public.serve_v3(_View(bad), CHALLENGE)[0] == 503
    assert queue_public.serve_v3(_View(OSError("disk")), CHALLENGE)[0] == 503
    assert queue_public.serve_v3(None, CHALLENGE) == (
        404,
        {"refused": "queue_not_served"},
    )


def test_a_short_hotkey_is_first_four_ellipsis_last_four_or_nothing():
    assert queue_public.short_hotkey(HOTKEY) == "5MMM…MMMM"
    real = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    assert queue_public.short_hotkey(real) == "5Grw…utQY"
    for bad in (None, 5, "", "5abc", "0OIl" * 3, "5Grw" + "é" * 10, "5" * 65):
        assert queue_public.short_hotkey(bad) is None


def test_time_is_floored_to_the_quantum():
    assert queue_public.floor_to_quantum(0) == 0
    assert queue_public.floor_to_quantum(Q - 1) == 0
    assert queue_public.floor_to_quantum(Q) == Q
    assert queue_public.floor_to_quantum(2.9 * Q) == 2 * Q
    assert queue_public.floor_to_quantum(-50) == 0


# --- the receiver's reader --------------------------------------------------------------------------------------------


def _states(now):
    return {
        TASKS[0]: (
            DirectTaskStateV3.SUCCEEDED,
            now - 2 * Q - 5,
        ),  # built, no verdict yet
        TASKS[1]: (DirectTaskStateV3.SUCCEEDED, now - Q - 5),  # built, no verdict yet
        TASKS[2]: (DirectTaskStateV3.RUNNING, now - 100),  # building
        TASKS[3]: (DirectTaskStateV3.QUEUED, now - 3 * Q + 1),  # waiting to build
        TASKS[4]: (DirectTaskStateV3.FAILED_INFRA, now - 50),  # closed: never a row
        TASKS[5]: (
            (DirectTaskStateV3.CANCELLED, now - 50)
            if hasattr(DirectTaskStateV3, "CANCELLED")
            else (DirectTaskStateV3.FAILED_INFRA, now - 50)
        ),
    }


def test_one_row_per_pending_submission_oldest_first_with_the_states(tmp_path):
    view, _grader = _door(tmp_path, _states(START), pending=TASKS[:6], clock=START)
    rows = view.snapshot_v3()["rows"]
    assert rows["as_of_unix"] == START // Q * Q
    assert [r["position"] for r in rows["rows"]] == [1, 2, 3, 4]
    assert [r["state"] for r in rows["rows"]] == [
        "in grading",
        "in grading",
        "building",
        "waiting to build",
    ]
    assert {r["hotkey"] for r in rows["rows"]} == {"5MMM…MMMM"}
    boundary = START // Q * Q
    assert [r["in_queue_s"] for r in rows["rows"]] == [
        queue_public.floor_to_quantum(boundary - START + 2 * Q + 5),
        queue_public.floor_to_quantum(boundary - START + Q + 5),
        queue_public.floor_to_quantum(boundary - START + 100),
        queue_public.floor_to_quantum(boundary - START + 3 * Q - 1),
    ]
    status, body = queue_public.serve_v3(view, CHALLENGE)
    assert status == 200 and len(body["rows"]) == 4


def test_a_built_submission_is_one_state_whatever_the_grader_is_doing(tmp_path):
    """V2C 14 Nov: 'grading' and 'waiting to grade' are not told apart per row (a visible grade start would expose each grade's
    length in quantum steps): a built submission with no verdict is 'in grading' whether the grader is on it, on another or idle.
    """
    assert queue_public.ROW_STATES == (
        "waiting to build",
        "building",
        "in grading",
        "crown check",
    )
    view, grader = _door(tmp_path, _states(START), pending=TASKS[:4], clock=START)
    seen = []
    for activity in (None, "grade", "king"):
        grader.activity = activity
        view._rows_cached = None
        seen.append(
            [
                r["state"]
                for r in view.snapshot_v3()["rows"]["rows"]
                if r["position"] <= 2
            ]
        )
    assert seen == [["in grading", "in grading"]] * 3
    for row in view.snapshot_v3()["rows"]["rows"]:
        assert row["state"] not in ("grading", "waiting to grade")


def test_nothing_changes_within_a_quantum_and_the_rows_follow_the_next_boundary(
    tmp_path,
):
    now = [START]
    view, _grader = _door(tmp_path, _states(START), pending=TASKS[:4], clock=START)
    view.clock = lambda: now[0]
    first = view.snapshot_v3()["rows"]
    provider = view.intake.adapter.provider_for._providers[HOTKEY]
    provider._views[TASKS[3]].state = (
        DirectTaskStateV3.RUNNING
    )  # waiting to build -> building
    now[0] = (
        START + Q - 20
    )  # still the same quantum: not rebuilt, whatever happened meanwhile
    assert view.snapshot_v3()["rows"] == first
    assert first["rows"][-1]["state"] == "waiting to build"
    now[0] = (START // Q + 1) * Q + 1  # the next boundary
    later = view.snapshot_v3()["rows"]
    assert later["as_of_unix"] == (START // Q + 1) * Q
    assert later["rows"][-1]["state"] == "building"
    assert [r["state"] for r in later["rows"][:2]] == ["in grading", "in grading"]


def test_the_rows_never_ask_owner_or_provider_and_carry_no_task_id(tmp_path):
    view, _grader = _door(
        tmp_path, _states(START), pending=TASKS[:6], clock=START
    )  # owner() / _provider() raise
    body = queue_public.serve_v3(view, CHALLENGE)[1]
    flat = json.dumps(body)
    for task in TASKS[:6]:
        assert task not in flat
    assert HOTKEY not in flat  # only the short form leaves the door


class _Store:
    def __init__(self, ids):
        self.ids = list(ids)

    def paused_crowns(self, kind=None):
        return [
            {"submission_id": i, "evaluation_key": "sha256:" + "a" * 64}
            for i in self.ids
        ]


def test_graded_contenders_waiting_for_the_crown_sweep_are_crown_check_rows_after_the_pending(
    tmp_path,
):
    states = {**_states(START), TASKS[8]: (DirectTaskStateV3.SUCCEEDED, START - 4000)}
    view, grader = _door(
        tmp_path,
        states,
        pending=TASKS[:4],
        verdicts=[(TASKS[8], START - 650), (TASKS[9], START - 10)],
        clock=START,
    )
    grader._pool = lambda: _Store([TASKS[8], TASKS[9]])
    rows = view.snapshot_v3()["rows"]["rows"]
    assert [r["state"] for r in rows][-2:] == ["crown check", "crown check"]
    assert [r["position"] for r in rows] == list(range(1, len(rows) + 1))
    first, second = rows[-2:]
    assert (
        first["hotkey"] == "5MMM…MMMM" and second["hotkey"] is None
    )  # TASKS[9] has no open provider
    assert first["in_queue_s"] == queue_public.floor_to_quantum(
        START // Q * Q - (START - 650)
    )
    assert second["in_queue_s"] == 0  # graded after the boundary: never negative


def test_a_pool_that_cannot_be_read_is_unavailable_never_a_partial_queue(tmp_path):
    view, grader = _door(tmp_path, _states(START), pending=TASKS[:4], clock=START)

    def broken():
        raise OSError("pool")

    grader._pool = broken
    assert queue_public.serve_v3(view, CHALLENGE)[0] == 503
    # the v1 and v2 documents never read the rows: they are unaffected
    assert queue_public.serve(view, CHALLENGE)[0] == 200
    assert queue_public.serve_v2(view, CHALLENGE)[0] == 200


# --- the route --------------------------------------------------------------------------------------------------------


def test_the_v3_route_serves_this_challenge_only_and_v1_v2_are_unchanged(tmp_path):
    view, _ = _door(tmp_path, _states(START), pending=TASKS[:4], clock=START)
    door = SimpleNamespace(challenge=CHALLENGE, queue_view=view)
    route = direct_intake.DirectRecipeIntake._queue
    v3 = route(
        door, queue_public.PATH + CHALLENGE.challenge_id + queue_public.V3_SUFFIX
    )
    assert v3.status == 200 and v3.body["schema"] == queue_public.SCHEMA_V3
    assert len(v3.body["rows"]) == 4
    v1 = route(door, queue_public.PATH + CHALLENGE.challenge_id)
    assert v1.status == 200 and "rows" not in v1.body
    v2 = route(
        door, queue_public.PATH + CHALLENGE.challenge_id + queue_public.V2_SUFFIX
    )
    assert v2.status == 200 and "rows" not in v2.body
    other = route(
        door, queue_public.PATH + "f08-ribbed-bracket" + queue_public.V3_SUFFIX
    )
    assert other.status == 404

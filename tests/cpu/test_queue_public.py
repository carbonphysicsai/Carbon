"""The public queue view, ``GET /carbon/v1/queue/<challenge_id>`` (owner 6 Nov; Miner X spec QUEUE_VISIBILITY_SPEC):
counts and the door's state in plain words, a closed field set, no hotkey / task id / score / per-submission timing,
counts that match the door's own records (every pending task counted once, infra requeues included), and the paused /
draining / king states. Real `queue_public`, `queue_view` and `AutoGrader` markers; only the providers are stood in.
"""

from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import (
    auto_grade,
    direct_intake,
    queue_public,
    queue_view,
)
from carbon.research import DirectTaskStateV3

CHALLENGE = SimpleNamespace(challenge_id="electric-motor-magnetics", version="1.5")
TASKS = ["rtsk_" + f"{i:064x}" for i in range(12)]
NOW = 1_800_000_000.0


def _snapshot(**change):
    return {
        "door_state": queue_public.GRADING,
        "waiting_to_build": 2,
        "building_now": 1,
        "waiting_to_grade": 3,
        "grading_now": 1,
        "waits_s": [60, 120, 180, 240, 300],
        "as_of_unix": NOW,
        **change,
    }


class _View:
    def __init__(self, snapshot):
        self.value = snapshot

    def snapshot(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


# --- the pure document -----------------------------------------------------------------------------------------------


def test_the_document_is_the_closed_field_set_with_counts_only():
    status, body = queue_public.serve(_View(_snapshot()), CHALLENGE)
    assert status == 200
    assert set(body) == queue_public.FIELDS
    assert set(body["wait_24h"]) == queue_public.WAIT_FIELDS
    assert body["challenge_id"] == CHALLENGE.challenge_id
    assert (
        body["waiting_to_build"],
        body["building_now"],
        body["waiting_to_grade"],
        body["grading_now"],
    ) == (2, 1, 3, 1)
    assert body["wait_24h"] == {
        "verdicts": 5,
        "median_s": 180,
        "p90_s": 300,
        "reason": None,
    }
    assert body["as_of"] == "2027-01-15T08:00:00Z"
    raw = json.dumps(body)
    assert "rtsk_" not in raw and len(raw) <= queue_public.MAX_BYTES


def test_fewer_than_five_verdicts_shows_no_wait_and_says_why():
    _status, body = queue_public.serve(_View(_snapshot(waits_s=[60, 90])), CHALLENGE)
    assert body["wait_24h"] == {
        "verdicts": 2,
        "median_s": None,
        "p90_s": None,
        "reason": "fewer_than_5_verdicts_in_24h",
    }


def test_median_and_p90_are_the_middle_and_the_nearest_rank():
    summary = queue_public.wait_summary(list(range(1, 11)))  # 1..10 s
    assert (summary["median_s"], summary["p90_s"]) == (
        6,
        9,
    )  # (5+6)/2 = 5.5 rounds to 6; rank ceil(9) = 9


@pytest.mark.parametrize("state", queue_public.DOOR_STATES)
def test_every_door_state_is_plain_words(state):
    status, body = queue_public.serve(_View(_snapshot(door_state=state)), CHALLENGE)
    assert status == 200 and body["door_state"] == state


@pytest.mark.parametrize(
    "change",
    [
        {"door_state": "drained by deploy 3"},
        {"waiting_to_build": -1},
        {"waiting_to_grade": 1.5},
        {"grading_now": 2},
        {"building_now": True},
        {"waits_s": [60, float("nan")]},
        {"waits_s": [-5]},
        {"as_of_unix": 0},
        {"hotkey": "5" + "M" * 47},
        {"task_ids": TASKS},
    ],
)
def test_a_malformed_or_extra_snapshot_is_unavailable_never_partial(change):
    status, body = queue_public.serve(_View(_snapshot(**change)), CHALLENGE)
    assert status == 503 and set(body) == {"refused"}


def test_no_view_is_not_served_and_a_failing_view_is_unavailable():
    assert queue_public.serve(None, CHALLENGE) == (404, {"refused": "queue_not_served"})
    assert queue_public.serve(_View(OSError("disk")), CHALLENGE)[0] == 503


# --- the receiver's reader over the door's own records ---------------------------------------------------------------


class _Provider:
    def __init__(self, states):
        self._views = {
            task: SimpleNamespace(state=state, created_at_micros=int(created * 1e6))
            for task, (state, created) in states.items()
        }


def _forbidden(*_args):
    raise AssertionError(
        "the queue view asked owner() / _provider() (Validator-2 12:37)"
    )


def _door(tmp_path, states, *, pending, verdicts=(), clock=NOW):
    provider = _Provider(states)
    adapter = SimpleNamespace(
        contract_digest="sha256:" + "0" * 64,
        ledger=SimpleNamespace(
            submitted_outcomes=lambda contract: tuple(
                pending + [v[0] for v in verdicts]
            )
        ),
        # only providers ALREADY open are read; asking for one would open it (Validator-2 12:37)
        provider_for=SimpleNamespace(_providers={"5" + "M" * 47: provider}),
        owner=_forbidden,
        _provider=_forbidden,
    )
    intake = SimpleNamespace(adapter=adapter)
    grader = auto_grade.AutoGrader(intake, tmp_path)
    grader.chain_degraded = lambda: False
    for task, written in verdicts:
        grader._write(task, "GRADED", entry_id="sha256:" + "1" * 64)
        os.utime(grader._marker(task), (written, written))
    return queue_view.QueueView(intake, grader, tmp_path, clock=lambda: clock), grader


def test_every_pending_task_is_counted_once_by_its_own_stage(tmp_path):
    states = {
        TASKS[0]: (DirectTaskStateV3.QUEUED, NOW - 100),
        TASKS[1]: (DirectTaskStateV3.QUEUED, NOW - 90),
        TASKS[2]: (DirectTaskStateV3.RUNNING, NOW - 80),
        TASKS[3]: (DirectTaskStateV3.SUCCEEDED, NOW - 70),
        TASKS[4]: (
            DirectTaskStateV3.FAILED_INFRA,
            NOW - 60,
        ),  # requeued after an infrastructure failure
    }
    # TASKS[5]: admitted under an earlier contract, no provider here: still waiting, never dropped
    view, _grader = _door(tmp_path, states, pending=TASKS[:6])
    snap = view.snapshot()
    assert (
        snap["waiting_to_build"],
        snap["building_now"],
        snap["waiting_to_grade"],
    ) == (2, 1, 3)
    assert (
        snap["waiting_to_build"] + snap["building_now"] + snap["waiting_to_grade"] == 6
    )
    assert snap["door_state"] == queue_public.GRADING and snap["grading_now"] == 0


def test_the_wait_is_marker_time_minus_task_creation_over_the_last_day(tmp_path):
    states = {task: (DirectTaskStateV3.SUCCEEDED, NOW - 10_000) for task in TASKS[:7]}
    verdicts = [(TASKS[i], NOW - 10_000 + 600 * (i + 1)) for i in range(6)]
    verdicts.append((TASKS[6], NOW - 2 * 86400))  # older than a day: not counted
    view, _ = _door(tmp_path, states, pending=[], verdicts=verdicts)
    _status, body = queue_public.serve(view, CHALLENGE)
    assert body["wait_24h"]["verdicts"] == 6
    assert body["wait_24h"]["median_s"] == 2100 and body["wait_24h"]["p90_s"] == 3600


def test_draining_paused_and_king_states(tmp_path):
    view, grader = _door(tmp_path, {}, pending=[])
    assert view._read()["door_state"] == queue_public.GRADING
    grader.activity = "king"
    assert view._read()["door_state"] == queue_public.KING
    grader.chain_degraded = lambda: True
    assert view._read()["door_state"] == queue_public.PAUSED
    (tmp_path / "draining").write_text("")
    assert view._read()["door_state"] == queue_public.DRAINING


def test_grading_now_needs_this_doors_grade_round_and_a_graded_submission(tmp_path):
    view, grader = _door(tmp_path, {}, pending=[])
    inflight = tmp_path / "work-inflight.json"
    inflight.write_text(json.dumps({"kind": "grade"}))
    assert view._read()["grading_now"] == 0  # a grade round doing its king's upkeep
    grader.activity = "grade"
    assert view._read()["grading_now"] == 1
    inflight.write_text(json.dumps({"kind": "advance"}))
    assert view._read()["grading_now"] == 0
    inflight.unlink()
    assert view._read()["grading_now"] == 0


def test_the_snapshot_is_cached_briefly(tmp_path):
    now = [NOW]
    view, _ = _door(tmp_path, {}, pending=[])
    view.clock = lambda: now[0]
    first = view.snapshot()
    (tmp_path / "draining").write_text("")
    assert view.snapshot()["door_state"] == first["door_state"]
    now[0] += queue_view.CACHE_S
    assert view.snapshot()["door_state"] == queue_public.DRAINING


# --- the route and the grader's activity ------------------------------------------------------------------------------


def test_the_route_serves_this_challenge_only(tmp_path):
    view, _ = _door(tmp_path, {}, pending=[])
    door = SimpleNamespace(challenge=CHALLENGE, queue_view=view)
    answer = direct_intake.DirectRecipeIntake._queue(
        door, queue_public.PATH + CHALLENGE.challenge_id
    )
    assert answer.status == 200
    other = direct_intake.DirectRecipeIntake._queue(
        door, queue_public.PATH + "f08-ribbed-bracket"
    )
    assert other.status == 404
    door.queue_view = None
    assert (
        direct_intake.DirectRecipeIntake._queue(
            door, queue_public.PATH + CHALLENGE.challenge_id
        ).status
        == 404
    )


def test_the_grader_marks_grade_while_retaining_and_clears_after(tmp_path):
    seen = []

    class Intake:
        adapter = SimpleNamespace(
            contract_digest="sha256:" + "0" * 64,
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: (TASKS[0],)),
            owner=lambda task: None,
        )

        def retain_result(self, submission_id, **kwargs):
            seen.append(grader.activity)
            return {"entry_id": "sha256:" + "1" * 64}

    grader = auto_grade.AutoGrader(Intake(), tmp_path)
    grader.chain_degraded = lambda: False
    assert grader.activity is None
    assert grader.run_once() == (TASKS[0], "GRADED")
    assert seen == ["grade"] and grader.activity is None


def test_a_snapshot_opens_no_provider_and_hashes_no_served_source(
    tmp_path, monkeypatch
):
    from carbon.challenge_validator import lean_recipe

    def forbidden():
        raise AssertionError("a public GET recomputed the served source identity")

    monkeypatch.setattr(lean_recipe, "_implementation_identity", forbidden)
    monkeypatch.setattr(lean_recipe, "_source_identity", forbidden)
    states = {TASKS[0]: (DirectTaskStateV3.QUEUED, NOW - 10)}
    view, _ = _door(tmp_path, states, pending=TASKS[:2])
    snap = view.snapshot()  # owner()/_provider() raise if called (see _door)
    assert (snap["waiting_to_build"], snap["waiting_to_grade"]) == (1, 1)


def test_a_get_while_a_build_holds_its_provider_lock_returns_at_once(tmp_path):
    import threading

    states = {TASKS[0]: (DirectTaskStateV3.RUNNING, NOW - 10)}
    view, _ = _door(tmp_path, states, pending=TASKS[:1])
    provider = view.intake.adapter.provider_for._providers["5" + "M" * 47]
    provider._lock = threading.Lock()
    provider._lock.acquire()  # a running build holds the provider lock
    try:
        started = time.monotonic()
        status, body = queue_public.serve(view, CHALLENGE)
        assert time.monotonic() - started < 2.0
        assert status == 200 and body["building_now"] == 1
    finally:
        provider._lock.release()


def test_a_malformed_provider_view_is_unavailable_never_a_guess(tmp_path):
    view, _ = _door(
        tmp_path, {TASKS[0]: (DirectTaskStateV3.QUEUED, NOW)}, pending=TASKS[:1]
    )
    provider = view.intake.adapter.provider_for._providers["5" + "M" * 47]
    provider._views[TASKS[0]] = SimpleNamespace(
        state="QUEUED"
    )  # no enum, no creation time
    status, body = queue_public.serve(view, CHALLENGE)
    assert status == 503 and body == {"refused": "queue_provider_state_invalid"}


def test_a_provider_changing_mid_read_is_skipped_not_fatal(tmp_path):
    view, _ = _door(tmp_path, {}, pending=TASKS[:1])

    class Changing(dict):
        def items(self):
            raise RuntimeError("dictionary changed size during iteration")

    view.intake.adapter.provider_for._providers["5" + "M" * 47]._views = Changing()
    snap = view.snapshot()
    assert snap["waiting_to_grade"] == 1  # its task waits to grade in this snapshot

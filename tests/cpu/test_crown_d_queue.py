"""Crown-time D custody queue: caps, FIFO, cache, fail-closed outcomes."""

from __future__ import annotations

import datetime
import json

import pytest

from carbon.challenge_validator.crown_d_queue import (
    NOT_CLOSED,
    CrownDQueue,
    CrownDQueueRefused,
    iso_week,
)

T0 = datetime.datetime(2026, 11, 5, 12, tzinfo=datetime.UTC).timestamp()
WEEK = 7 * 86400.0


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


class Solver:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = dict(replies or {})

    def __call__(self, target, fixed, design, rung):
        self.calls.append((target, rung, tuple(design)))
        reply = self.replies.get(target)
        if isinstance(reply, list):
            reply = reply.pop(0) if reply else None
        if reply is None:
            return {"status": "OK", "outputs": {"y": float(sum(design))}}
        return reply


def _queue(tmp_path, clock=None):
    return CrownDQueue(tmp_path / "crown_d.sqlite", clock=clock or Clock())


def _enqueue(
    queue, target, *, submission="sub-1", key=None, design=(0.1, 0.2), ch="C1"
):
    return queue.enqueue(
        challenge=ch,
        version="v1",
        submission=submission,
        target=target,
        rung="coarse",
        key=key or f"key-{target}",
        fixed={"load": 3.0},
        design=list(design),
    )


def test_enqueue_idempotent_and_changed_body_refused(tmp_path):
    queue = _queue(tmp_path)
    first = _enqueue(queue, "t1")
    assert _enqueue(queue, "t1") == first
    with pytest.raises(CrownDQueueRefused) as refused:
        _enqueue(queue, "t1", design=(0.9, 0.2))
    assert refused.value.code == "crown_d_request_changed"


def test_cache_hit_is_solved_without_budget_or_solve(tmp_path):
    queue, solve = _queue(tmp_path), Solver()
    _enqueue(queue, "t1", key="shared")
    queue.run_once(solve, weekly_solves=5)
    assert queue.budget_used("C1") == 1
    _enqueue(queue, "t1", submission="sub-2", key="shared")
    assert queue.results("sub-2")[("t1", "coarse")]["state"] == "SOLVED"
    assert queue.run_once(solve, weekly_solves=5) == []
    assert len(solve.calls) == 1 and queue.budget_used("C1") == 1


def test_fifo_order(tmp_path):
    queue, solve = _queue(tmp_path), Solver()
    for target in ("t3", "t1", "t2"):
        _enqueue(queue, target)
    done = queue.run_once(solve, weekly_solves=10)
    assert [call[0] for call in solve.calls] == ["t3", "t1", "t2"]
    assert [d["id"] for d in done] == sorted(d["id"] for d in done)
    assert queue.results("sub-1")[("t2", "coarse")]["outputs"] == {"y": 0.1 + 0.2}


def test_weekly_budget_defers_then_next_week_runs(tmp_path):
    clock = Clock()
    queue, solve = _queue(tmp_path, clock), Solver()
    for target in ("t1", "t2", "t3"):
        _enqueue(queue, target)
    done = queue.run_once(solve, weekly_solves=2)
    assert [d["state"] for d in done] == ["SOLVED", "SOLVED"]
    third = next(s for s in queue.status("sub-1") if s["target"] == "t3")
    assert third == {
        "target": "t3",
        "rung": "coarse",
        "state": "QUEUED",
        "position": 1,
        "of": 1,
        "deferred": True,
    }
    assert queue.budget_used("C1") == 2
    clock.now += WEEK
    assert iso_week(clock.now) != iso_week(T0)
    third = next(s for s in queue.status("sub-1") if s["target"] == "t3")
    assert third["deferred"] is False
    done = queue.run_once(solve, weekly_solves=2)
    assert [d["state"] for d in done] == ["SOLVED"]
    assert queue.budget_used("C1") == 1
    assert queue.budget_used("C1", iso_week(T0)) == 2


def test_failed_infra_requeues_in_place_and_refunds(tmp_path):
    queue = _queue(tmp_path)
    solve = Solver({"t1": [{"status": "FAILED_INFRA"}]})
    first = _enqueue(queue, "t1")
    _enqueue(queue, "t2")
    _enqueue(queue, "t3")
    solve.replies["t2"] = {"status": "FAILED_INFRA"}
    done = queue.run_once(solve, weekly_solves=3)
    assert done[0] == {"id": first, "state": "QUEUED", "code": "FAILED_INFRA"}
    assert [d["state"] for d in done] == ["QUEUED", "QUEUED", "SOLVED"]
    assert queue.budget_used("C1") == 1
    view = {s["target"]: s for s in queue.status("sub-1")}
    assert (view["t1"]["position"], view["t1"]["of"]) == (1, 2)
    assert (view["t2"]["position"], view["t2"]["of"]) == (2, 2)
    with queue.db() as db:
        assert db.execute(
            "SELECT attempts FROM requests WHERE id=?", (first,)
        ).fetchone() == (1,)
    done = queue.run_once(solve, weekly_solves=3)
    assert done[0] == {"id": first, "state": "SOLVED", "code": None}


def test_reference_failure_is_terminal(tmp_path):
    queue = _queue(tmp_path)
    solve = Solver({"t1": {"status": "REFERENCE_NO_CONVERGENCE"}})
    _enqueue(queue, "t1")
    done = queue.run_once(solve, weekly_solves=3)
    assert done[0]["state"] == "REFERENCE_FAILED"
    assert queue.results("sub-1")[("t1", "coarse")] == {
        "state": "REFERENCE_FAILED",
        "outputs": None,
        "code": "REFERENCE_NO_CONVERGENCE",
    }
    assert queue.run_once(solve, weekly_solves=3) == []
    assert len(solve.calls) == 1


@pytest.mark.parametrize(
    "reply", [{"status": "WEIRD"}, {"status": "OK"}, "OK", {"status": "reference_x"}]
)
def test_unclosed_status_is_infra(tmp_path, reply):
    queue = _queue(tmp_path)
    _enqueue(queue, "t1")
    done = queue.run_once(Solver({"t1": reply}), weekly_solves=3)
    assert done[0]["state"] == "QUEUED" and done[0]["code"] == NOT_CLOSED
    assert queue.unclosed_statuses == 1
    assert queue.budget_used("C1") == 0
    assert queue.results("sub-1")[("t1", "coarse")]["outputs"] is None


def test_crash_left_solving_reset_on_reopen(tmp_path):
    queue = _queue(tmp_path)
    request = _enqueue(queue, "t1")
    with queue.transaction() as db:
        db.execute("UPDATE requests SET state='SOLVING' WHERE id=?", (request,))
    reopened = _queue(tmp_path)
    assert reopened.status("sub-1")[0]["state"] == "QUEUED"
    assert reopened.run_once(Solver(), weekly_solves=1)[0]["state"] == "SOLVED"


def test_status_view_carries_no_custody_values(tmp_path):
    queue, solve = _queue(tmp_path), Solver()
    _enqueue(queue, "t1", key="SECRETKEY", design=(0.123456, 0.654321))
    _enqueue(queue, "t2", key="OTHERKEY", design=(0.777777, 0.1))
    queue.run_once(solve, weekly_solves=1)
    text = json.dumps(queue.status("sub-1"))
    for needle in ("SECRETKEY", "OTHERKEY", "0.123456", "0.777777", "load", "outputs"):
        assert needle not in text
    assert '"y"' not in text and "fixed" not in text and "design" not in text


@pytest.mark.parametrize("value", [0, None, "3", -1, True, 2.0])
def test_weekly_solves_refused(tmp_path, value):
    queue = _queue(tmp_path)
    with pytest.raises(CrownDQueueRefused) as refused:
        queue.run_once(Solver(), weekly_solves=value)
    assert refused.value.code == "crown_d_weekly_solves_invalid"


def test_symlink_state_refused(tmp_path):
    target = tmp_path / "real.sqlite"
    CrownDQueue(target, clock=Clock())
    link = tmp_path / "link.sqlite"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(CrownDQueueRefused) as refused:
        CrownDQueue(link, clock=Clock())
    assert refused.value.code == "crown_d_state_not_owner_only"

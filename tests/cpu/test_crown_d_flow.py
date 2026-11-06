"""Crown-time D end to end: pick -> coarse solve -> (fine when near a limit or the zero) -> d -> the hold decision, with
the owner's weekly cap, the dedupe cache and the hold bound. Analytic stand-in solver; every number is a fixture.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_crown_d import HOST, _evaluator, _problem, _rule, _sha

from carbon.challenge_validator import crown_d_flow as flow
from carbon.challenge_validator.crown_d_queue import CrownDQueue
from carbon.scoring import crown_d as cd

ZERO = {
    "schema": cd.ZERO_SCHEMA,
    "targets": {
        "t1": {"s_zero": 0.6, "s_ref": 1.0, "source": "fit_pick"},
        "t2": {"s_zero": 1.2, "s_ref": 2.0, "source": "shortcut"},
    },
}
IDS = {"challenge": "fixture-motor", "version": "9.9"}


class Clock:
    def __init__(self):
        self.t = 1_794_000_000.0

    def __call__(self):
        return self.t


def _setup(tmp_path, **rule):
    problems = {
        "t1": _problem(target_id="t1"),
        "t2": _problem(target_id="t2", fixed={"load": 2.0}),
    }
    rule = _rule(zero_sha256=_sha(ZERO), **rule)
    zero = cd.attach_zero(rule, ZERO, list(problems.values()))
    clock = Clock()
    queue = CrownDQueue(tmp_path / "crown_d.sqlite3", clock=clock)
    return problems, rule, zero, queue, clock


def _solver(calls, fail=None):
    def solve(target_id, fixed, design, rung):
        calls.append((target_id, rung))
        if fail and fail(target_id, rung):
            return {"status": fail(target_id, rung)}
        x0, x1 = design
        return {
            "status": "OK",
            "outputs": {"f": fixed["load"] * (x0 + x1), "g": x0 * x0 + x1 * x1},
        }

    return solve


def _request(queue, rule, zero, problems, submission):
    evaluators = {t: _evaluator() for t in problems}
    return flow.request_contender(
        queue,
        rule,
        zero,
        problems,
        evaluators,
        submission=submission,
        host_class=HOST,
        **IDS,
    )


def _advance(queue, rule, zero, problems, picks, submission, clock, start):
    return flow.advance(
        queue,
        rule,
        zero,
        problems,
        picks,
        submission=submission,
        requested_at=start,
        now=clock(),
        **IDS,
    )


def test_coarse_then_fine_near_the_limit_then_a_d(tmp_path):
    problems, rule, zero, queue, clock = _setup(tmp_path)
    start = clock()
    picks = _request(queue, rule, zero, problems, "sub-a")
    assert (
        _advance(queue, rule, zero, problems, picks, "sub-a", clock, start)["state"]
        == "HOLD"
    )
    calls = []
    queue.run_once(_solver(calls), weekly_solves=rule.weekly_solves)
    assert sorted(calls) == [("t1", "coarse"), ("t2", "coarse")]
    # the model's optimum sits on the g <= 0.5 limit, within U: the fine rung is queued, D still holds
    assert (
        _advance(queue, rule, zero, problems, picks, "sub-a", clock, start)["state"]
        == "HOLD"
    )
    queue.run_once(_solver(calls), weekly_solves=rule.weekly_solves)
    assert sorted(calls[2:]) == [("t1", "fine"), ("t2", "fine")]
    out = _advance(queue, rule, zero, problems, picks, "sub-a", clock, start)
    assert out["state"] == "SOLVED" and out["targets"] == 2 and 0.0 <= out["d"] <= 1.0


def test_the_weekly_cap_defers_and_never_scores_zero(tmp_path):
    problems, rule, zero, queue, clock = _setup(tmp_path, weekly_solves=1)
    start = clock()
    picks = _request(queue, rule, zero, problems, "sub-a")
    queue.run_once(_solver([]), weekly_solves=rule.weekly_solves)
    out = _advance(queue, rule, zero, problems, picks, "sub-a", clock, start)
    assert out == {"state": cd.CROWN_DEFERRED_D_BUDGET}


def test_a_second_contender_with_the_same_picks_costs_no_solve(tmp_path):
    problems, rule, zero, queue, clock = _setup(tmp_path)
    calls = []
    for submission in ("sub-a", "sub-b"):
        picks = _request(queue, rule, zero, problems, submission)
        for _ in range(3):
            queue.run_once(_solver(calls), weekly_solves=rule.weekly_solves)
            _advance(queue, rule, zero, problems, picks, submission, clock, clock())
    assert (
        len(calls) == 4
    )  # 2 targets x (coarse + fine), once: sub-b is answered from the cache
    out = _advance(queue, rule, zero, problems, picks, "sub-b", clock, clock())
    assert out["state"] == "SOLVED"


def test_a_reference_failure_drops_its_target_and_the_rest_decide(tmp_path):
    problems, rule, zero, queue, clock = _setup(tmp_path, min_targets=1)
    start = clock()
    picks = _request(queue, rule, zero, problems, "sub-a")
    fail = _solver(
        [], fail=lambda t, r: "REFERENCE_NO_CONVERGENCE" if t == "t2" else None
    )
    for _ in range(3):
        queue.run_once(fail, weekly_solves=rule.weekly_solves)
        out = _advance(queue, rule, zero, problems, picks, "sub-a", clock, start)
    assert out["state"] == "SOLVED" and out["targets"] == 1 and out["dropped"] == 1


def test_infrastructure_faults_hold_until_the_bound_then_fail_as_infrastructure(
    tmp_path,
):
    problems, rule, zero, queue, clock = _setup(tmp_path)
    start = clock()
    picks = _request(queue, rule, zero, problems, "sub-a")
    down = _solver([], fail=lambda t, r: "FAILED_INFRA")
    queue.run_once(down, weekly_solves=rule.weekly_solves)
    assert (
        _advance(queue, rule, zero, problems, picks, "sub-a", clock, start)["state"]
        == "HOLD"
    )
    assert (
        queue.budget_used(IDS["challenge"]) == 0
    )  # an infrastructure fault burns none of the owner's count
    clock.t += rule.hold_seconds + 1
    out = _advance(queue, rule, zero, problems, picks, "sub-a", clock, start)
    assert out == {"state": "FAILED_INFRA", "reason": "hold_bound_reached"}


def test_the_pick_is_the_fixed_optimizer_on_the_contenders_model(tmp_path):
    problems, rule, zero, queue, _clock = _setup(tmp_path)
    tilted = {t: replace(p, seed=3) for t, p in problems.items()}
    try:
        _request(queue, rule, zero, tilted, "sub-a")
    except cd.CrownDRefused as refused:
        assert refused.code == "crown_d_pick_not_the_fixed_optimizer"
    else:
        raise AssertionError("a non-fixed optimizer was accepted")

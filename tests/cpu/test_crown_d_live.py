"""Crown-time D cost shape (D_CROWN_COST_OPTIONS_20261107: C + B + A + D): picks from the registered rebuild, the
epoch's k-of-N draw, the cached king picks and one parallel solve round. All fixtures are SYNTHETIC.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_crown_d import HOST, _evaluator, _problem, _rule, _sha
from test_crown_d_flow import _solver

from carbon.challenge_validator import crown_d_flow as flow
from carbon.challenge_validator.crown_d_queue import (
    CrownDQueue,
    CrownDQueueRefused,
)
from carbon.scoring import crown_d as cd

KEY = b"d" * 32  # synthetic draw key
IDS = {"challenge": "fixture-motor", "version": "9.9"}
TARGETS = ("t1", "t2", "t3", "t4", "t5")
ZERO = {
    "schema": cd.ZERO_SCHEMA_V1,
    "targets": {
        t: {"s_zero": 0.6, "s_ref": 1.0, "source": "fit_pick"} for t in TARGETS
    },
}


def _draw(rule=None, key=KEY, epoch="2026-W45", targets=TARGETS):
    return cd.draw_targets(
        rule or _rule(tasks_per_epoch=3),
        key,
        challenge_id="fixture-motor",
        version="9.9",
        epoch=epoch,
        targets=list(targets),
    )


# --- D: the epoch's k of N ---


def test_the_draw_is_k_sorted_and_the_same_for_everyone_in_an_epoch():
    drawn = _draw()
    assert (
        len(drawn) == 3 and drawn == tuple(sorted(drawn)) and set(drawn) <= set(TARGETS)
    )
    assert _draw() == drawn  # king and every contender: same key, same epoch
    assert (
        _draw(targets=reversed(TARGETS)) == drawn
    )  # order of registration is irrelevant
    epochs = {_draw(epoch=f"2026-W{w}") for w in range(40, 52)}
    assert len(epochs) > 1  # the draw moves with the epoch
    assert _draw(key=b"e" * 32) != drawn or _draw(key=b"f" * 32) != drawn


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"key": b"short"}, "crown_d_draw_key_invalid"),
        ({"key": "d" * 32}, "crown_d_draw_key_invalid"),
        ({"epoch": ""}, "crown_d_draw_ids_invalid"),
        ({"targets": ("t1", "t1", "t2")}, "crown_d_draw_targets_invalid"),
        ({"targets": ("t1", "t2")}, "crown_d_tasks_per_epoch_above_pool"),
    ],
)
def test_draw_refusals(kw, code):
    with pytest.raises(cd.CrownDRefused) as err:
        _draw(**kw)
    assert err.value.code == code


def test_k_and_the_rebuild_seed_are_registered_values():
    for name in ("pick_rebuild_seed", "tasks_per_epoch"):
        with pytest.raises(cd.CrownDRefused, match=f"crown_d_{name}_is_human_input"):
            cd.check_rule(_rule(**{name: None}))
    with pytest.raises(cd.CrownDRefused, match="crown_d_tasks_per_epoch_invalid"):
        cd.check_rule(_rule(tasks_per_epoch=0))
    with pytest.raises(cd.CrownDRefused, match="crown_d_pick_rebuild_seed_invalid"):
        cd.check_rule(_rule(pick_rebuild_seed=-1))


# --- C + D through the flow ---


def _setup(tmp_path, **rule):
    problems = {t: _problem(target_id=t) for t in TARGETS}
    rule = _rule(zero_sha256=_sha(ZERO), tasks_per_epoch=3, **rule)
    zero = cd.attach_zero(rule, ZERO, list(problems.values()))
    return problems, rule, zero, CrownDQueue(tmp_path / "q.sqlite3")


def _request(
    queue, rule, zero, problems, *, submission, model_sha256, evaluators, seed=0
):
    return flow.request_contender(
        queue,
        rule,
        zero,
        problems,
        evaluators,
        submission=submission,
        host_class=HOST,
        model_sha256=model_sha256,
        rebuild_seed=seed,
        epoch="2026-W45",
        draw_key=KEY,
        **IDS,
    )


def _counting(built):
    def make(target_id):
        built.append(target_id)
        return _evaluator()

    return make


def test_picks_only_for_the_drawn_targets_and_the_decision_rests_on_them(tmp_path):
    problems, rule, zero, queue = _setup(tmp_path)
    built = []
    picks = _request(
        queue,
        rule,
        zero,
        problems,
        submission="sub-a",
        model_sha256="aa" * 32,
        evaluators=_counting(built),
    )
    assert tuple(sorted(picks)) == _draw(rule) and sorted(built) == sorted(picks)
    for _ in range(3):
        queue.run_round(_solver([]), weekly_solves=rule.weekly_solves, width=8)
        out = flow.advance(
            queue,
            rule,
            zero,
            problems,
            picks,
            submission="sub-a",
            requested_at=0.0,
            now=1.0,
            **IDS,
        )
    assert out["state"] == "SOLVED" and out["targets"] == 3


def test_a_model_from_another_rebuild_refuses(tmp_path):
    problems, rule, zero, queue = _setup(tmp_path)
    with pytest.raises(
        cd.CrownDRefused, match="crown_d_pick_not_from_the_registered_rebuild"
    ):
        _request(
            queue,
            rule,
            zero,
            problems,
            submission="sub-a",
            model_sha256="aa" * 32,
            evaluators=_counting([]),
            seed=3,
        )


def test_the_kings_picks_are_searched_once(tmp_path):
    problems, rule, zero, queue = _setup(tmp_path)
    built = []
    first = _request(
        queue,
        rule,
        zero,
        problems,
        submission="king-epoch-1",
        model_sha256="aa" * 32,
        evaluators=_counting(built),
    )
    again = _request(
        queue,
        rule,
        zero,
        problems,
        submission="king-epoch-1b",
        model_sha256="aa" * 32,
        evaluators=_counting(built),
    )
    assert (
        first == again and len(built) == 3
    )  # the same model + seed: read from the pick cache, no search
    _request(
        queue,
        rule,
        zero,
        problems,
        submission="challenger",
        model_sha256="bb" * 32,
        evaluators=_counting(built),
    )
    assert len(built) == 6  # a different model is searched


def test_a_pick_key_changes_with_the_model_the_optimizer_and_the_problem():
    rule = _rule()
    base = cd.pick_key("c", "1", "t1", _problem(), rule, model_sha256="aa" * 32)
    assert base == cd.pick_key("c", "1", "t1", _problem(), rule, model_sha256="aa" * 32)
    others = {
        cd.pick_key("c", "1", "t1", _problem(), rule, model_sha256="bb" * 32),
        cd.pick_key(
            "c", "1", "t1", _problem(fixed={"load": 2.0}), rule, model_sha256="aa" * 32
        ),
        cd.pick_key(
            "c",
            "1",
            "t1",
            _problem(),
            _rule(optimizer="de_polish_v1", model_call_budget=3000),
            model_sha256="aa" * 32,
        ),
        cd.pick_key(
            "c",
            "1",
            "t1",
            _problem(),
            _rule(pick_rebuild_seed=1),
            model_sha256="aa" * 32,
        ),
        cd.pick_key("c", "2", "t1", _problem(), rule, model_sha256="aa" * 32),
    }
    assert base not in others and len(others) == 5
    with pytest.raises(cd.CrownDRefused, match="crown_d_model_sha256_invalid"):
        cd.pick_key("c", "1", "t1", _problem(), rule, model_sha256="nope")


def test_a_stored_pick_never_changes(tmp_path):
    queue = CrownDQueue(tmp_path / "q.sqlite3")
    queue.store_pick("k1", [0.1, 0.2], True)
    queue.store_pick("k1", [0.1, 0.2], True)  # idempotent
    assert queue.cached_pick("k1") == ((0.1, 0.2), True)
    assert queue.cached_pick("k2") is None
    with pytest.raises(CrownDQueueRefused, match="crown_d_pick_changed"):
        queue.store_pick("k1", [0.1, 0.3], True)


# --- A: one parallel round ---


def _enqueue(queue, n, challenge="fixture-motor"):
    for i in range(n):
        queue.enqueue(
            challenge=challenge,
            version="9.9",
            submission=f"s{i}",
            target="t1",
            rung="coarse",
            key=f"key-{i}",
            fixed={"load": 1.0},
            design=[0.1 * i, 0.2],
        )


def test_a_round_runs_its_solves_at_the_same_time(tmp_path):
    queue = CrownDQueue(tmp_path / "q.sqlite3")
    _enqueue(queue, 4)
    gate = threading.Barrier(
        3, timeout=10
    )  # only passes if 3 solves are in flight together

    def solve(target_id, fixed, design, rung):
        gate.wait()
        return {"status": "OK", "outputs": {"f": design[0], "g": 0.0}}

    done = queue.run_round(solve, weekly_solves=10, width=3)
    assert [row["state"] for row in done] == ["SOLVED"] * 3  # FIFO: the first three
    assert [row["state"] for row in queue.status("s3")] == ["QUEUED"]


def test_a_round_keeps_the_budget_the_cache_and_the_failure_types(tmp_path):
    queue = CrownDQueue(tmp_path / "q.sqlite3")
    _enqueue(queue, 6)

    def solve(target_id, fixed, design, rung):
        index = round(design[0] * 10)
        if index == 1:
            return {"status": "FAILED_INFRA"}
        if index == 2:
            return {"status": "REFERENCE_NO_CONVERGENCE"}
        if index == 3:
            raise RuntimeError("host lost")
        if index == 4:
            return {"status": "maybe"}
        return {"status": "OK", "outputs": {"f": 1.0}}

    done = {row["id"]: row for row in queue.run_round(solve, weekly_solves=5, width=8)}
    assert len(done) == 5  # the weekly count stops the sixth: deferred, not dropped
    assert queue.unclosed_statuses == 1
    states = {
        s: queue.status(s)[0]["state"] for s in ("s0", "s1", "s2", "s3", "s4", "s5")
    }
    assert states["s0"] == "SOLVED" and states["s2"] == "REFERENCE_FAILED"
    # infrastructure faults (incl. an unclosed status) are re-queued in place
    assert states["s1"] == states["s3"] == states["s4"] == "QUEUED"
    # over the weekly count at claim time: not attempted, stays queued, never dropped (the 3 faults refund
    # their units, so it runs next round)
    assert states["s5"] == "QUEUED" and queue.budget_used("fixture-motor") == 2
    with pytest.raises(CrownDQueueRefused, match="crown_d_round_width_invalid"):
        queue.run_round(solve, weekly_solves=5, width=0)


def test_run_once_is_unchanged_by_the_round(tmp_path):
    a, b = CrownDQueue(tmp_path / "a.sqlite3"), CrownDQueue(tmp_path / "b.sqlite3")
    _enqueue(a, 3)
    _enqueue(b, 3)
    solve = _solver([])
    once = [(r["state"], r["code"]) for r in a.run_once(solve, weekly_solves=10)]
    round_ = [
        (r["state"], r["code"]) for r in b.run_round(solve, weekly_solves=10, width=3)
    ]
    assert once == round_
    assert replace(_rule(), weekly_solves=10).weekly_solves == 10

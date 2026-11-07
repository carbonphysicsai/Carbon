"""Crown-time D cost shape (D_CROWN_COST_OPTIONS_20261107: C + B + A + D, with the Validator's 7 Nov 08:18 rulings):
picks from the epoch's DRAWN rebuild, the k-of-N draw over scored kinds (k >= 3, CONTROL never, stratified), the cached
king picks and one parallel solve round. All fixtures are SYNTHETIC."""

from __future__ import annotations

import sys
import threading
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

K_CROWN = b"c" * 32  # synthetic custody crown key
KEY = cd.derive_key(K_CROWN, "d-task-draw")
IDS = {"challenge": "fixture-motor", "version": "9.9"}
EPOCH = "2026-W45"
KINDS = {
    "t1": "onset",
    "t2": "onset",
    "t3": "onset",
    "t4": "limit",
    "t5": "limit",
    "t6": "limit",
    "c1": "CONTROL",
}
TARGETS = tuple(KINDS)
ZERO = {
    "schema": cd.ZERO_SCHEMA_V1,
    "targets": {
        t: {"s_zero": 0.6, "s_ref": 1.0, "source": "fit_pick"} for t in TARGETS
    },
}


def _draw(rule=None, key=KEY, epoch=EPOCH, targets=None):
    return cd.draw_targets(
        rule or _rule(tasks_per_epoch=4),
        key,
        challenge_id="fixture-motor",
        version="9.9",
        epoch=epoch,
        targets=dict(KINDS if targets is None else targets),
    )


# --- D: the epoch's k of the scored pool ---


def test_the_draw_takes_scored_kinds_in_proportion_and_never_control():
    drawn = _draw()
    assert len(drawn) == 4 and drawn == tuple(sorted(drawn)) and "c1" not in drawn
    kinds = [KINDS[t] for t in drawn]
    assert kinds.count("onset") == 2 and kinds.count("limit") == 2  # 3:3 mix -> 2:2
    assert _draw() == drawn  # king and every contender: same key, same epoch
    assert len({_draw(epoch=f"2026-W{w}") for w in range(40, 52)}) > 1
    for w in range(40, 52):
        assert "c1" not in _draw(epoch=f"2026-W{w}")


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"key": b"short"}, "crown_d_draw_key_invalid"),
        ({"epoch": ""}, "crown_d_draw_ids_invalid"),
        ({"targets": {"t1": ""}}, "crown_d_draw_targets_invalid"),
        (
            {"targets": {"t1": "a", "t2": "a", "t3": "CONTROL", "t4": "CONTROL"}},
            "crown_d_tasks_per_epoch_above_pool",
        ),
    ],
)
def test_draw_refusals(kw, code):
    with pytest.raises(cd.CrownDRefused) as err:
        _draw(rule=_rule(tasks_per_epoch=3), **kw)
    assert err.value.code == code


def test_k_is_at_least_three_and_the_rebuild_count_is_registered():
    for name in ("rebuilds", "tasks_per_epoch"):
        with pytest.raises(cd.CrownDRefused, match=f"crown_d_{name}_is_human_input"):
            cd.check_rule(_rule(**{name: None}))
    for k in (0, 1, 2):
        with pytest.raises(cd.CrownDRefused, match="crown_d_tasks_per_epoch_invalid"):
            cd.check_rule(_rule(tasks_per_epoch=k))
    with pytest.raises(cd.CrownDRefused, match="crown_d_rebuilds_invalid"):
        cd.check_rule(_rule(rebuilds=0))


# --- C: the drawn rebuild ---


def test_the_rebuild_is_drawn_per_epoch_from_the_crown_key():
    rule = _rule(rebuilds=10)
    picks = {
        cd.draw_rebuild(rule, K_CROWN, version="9.9", epoch=f"2026-W{w}")
        for w in range(30, 52)
    }
    assert picks <= set(range(10)) and len(picks) > 1  # moves with the epoch
    one = cd.draw_rebuild(rule, K_CROWN, version="9.9", epoch=EPOCH)
    assert one == cd.draw_rebuild(rule, K_CROWN, version="9.9", epoch=EPOCH)
    with pytest.raises(cd.CrownDRefused, match="crown_d_draw_key_invalid"):
        cd.draw_rebuild(rule, b"short", version="9.9", epoch=EPOCH)


def _setup(tmp_path, **rule):
    problems = {t: _problem(target_id=t) for t in TARGETS}
    rule = _rule(zero_sha256=_sha(ZERO), tasks_per_epoch=3, **rule)
    zero = cd.attach_zero(rule, ZERO, list(problems.values()))
    return problems, rule, zero, CrownDQueue(tmp_path / "q.sqlite3")


def _drawn_rebuild(rule):
    return cd.draw_rebuild(rule, K_CROWN, version=IDS["version"], epoch=EPOCH)


def _request(
    queue, rule, zero, problems, *, submission, model_sha256, evaluators, index=None
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
        rebuild_index=_drawn_rebuild(rule) if index is None else index,
        epoch=EPOCH,
        k_crown=K_CROWN,
        kinds=KINDS,
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
    assert "c1" not in picks
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
    other = (_drawn_rebuild(rule) + 1) % rule.rebuilds
    with pytest.raises(
        cd.CrownDRefused, match="crown_d_pick_not_from_the_drawn_rebuild"
    ):
        _request(
            queue,
            rule,
            zero,
            problems,
            submission="sub-a",
            model_sha256="aa" * 32,
            evaluators=_counting([]),
            index=other,
        )


def test_the_kings_picks_are_searched_once(tmp_path):
    problems, rule, zero, queue = _setup(tmp_path)
    built = []
    kw = {"evaluators": _counting(built)}
    first = _request(
        queue, rule, zero, problems, submission="king-1", model_sha256="aa" * 32, **kw
    )
    again = _request(
        queue, rule, zero, problems, submission="king-1b", model_sha256="aa" * 32, **kw
    )
    assert first == again and len(built) == 3  # same model + rebuild: from the cache
    _request(
        queue,
        rule,
        zero,
        problems,
        submission="challenger",
        model_sha256="bb" * 32,
        **kw,
    )
    assert len(built) == 6  # a different model is searched


def test_the_pick_key_carries_optimizer_budget_rebuild_model_and_problem():
    rule = _rule()

    def key(problem=None, r=rule, sha="aa" * 32, index=0, version="1"):
        return cd.pick_key(
            "c",
            version,
            "t1",
            problem or _problem(),
            r,
            model_sha256=sha,
            rebuild_index=index,
        )

    base = key()
    assert base == key()
    others = {
        key(sha="bb" * 32),
        key(problem=_problem(fixed={"load": 2.0})),
        key(r=_rule(optimizer="de_polish_v1", model_call_budget=3000)),
        key(r=_rule(optimizer="de_polish_v1", model_call_budget=4000)),
        key(index=1),
        key(version="2"),
    }
    assert base not in others and len(others) == 6
    with pytest.raises(cd.CrownDRefused, match="crown_d_model_sha256_invalid"):
        key(sha="nope")
    with pytest.raises(cd.CrownDRefused, match="crown_d_rebuild_index_invalid"):
        key(index=rule.rebuilds)


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


def test_a_round_keeps_the_budget_and_the_failure_types(tmp_path):
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

    done = queue.run_round(solve, weekly_solves=5, width=8)
    assert len(done) == 5  # the weekly count stops the sixth at claim time
    assert queue.unclosed_statuses == 1
    states = {s: queue.status(s)[0]["state"] for s in [f"s{i}" for i in range(6)]}
    assert states["s0"] == "SOLVED" and states["s2"] == "REFERENCE_FAILED"
    # infrastructure faults (incl. an unclosed status) are re-queued in place and refund their units
    assert states["s1"] == states["s3"] == states["s4"] == "QUEUED"
    assert states["s5"] == "QUEUED" and queue.budget_used("fixture-motor") == 2
    with pytest.raises(CrownDQueueRefused, match="crown_d_round_width_invalid"):
        queue.run_round(solve, weekly_solves=5, width=0)


def test_run_once_and_a_round_agree(tmp_path):
    a, b = CrownDQueue(tmp_path / "a.sqlite3"), CrownDQueue(tmp_path / "b.sqlite3")
    _enqueue(a, 3)
    _enqueue(b, 3)
    once = [(r["state"], r["code"]) for r in a.run_once(_solver([]), weekly_solves=10)]
    round_ = [
        (r["state"], r["code"])
        for r in b.run_round(_solver([]), weekly_solves=10, width=3)
    ]
    assert once == round_
